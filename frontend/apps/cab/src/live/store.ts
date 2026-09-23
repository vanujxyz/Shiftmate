/**
 * Live cab state, fed by /ws/cab (TRD §9.1). `reduce` is a pure function from (state, message) to
 * the next state, so every rule is testable without a socket; the zustand store just holds it.
 *
 * Alerts are a projection of what the edge's alert policy engine decided (engines/alerts.py):
 * - `alert` with status "showing" is the one interrupting alert (P1 takeover or P2 banner);
 *   "strip" is the P3 strip; "reduced" is an acknowledged P1 whose condition is still true.
 * - `alert_queued` moves an alert into the queue (it was pre-empted, or waits behind a higher one);
 *   `alert_feed` files it as history; `alert_cleared` removes it everywhere.
 * - every alert payload carries `queued_count`, the edge's own count for the rail's queue pip.
 * The cab never re-decides priorities; it only draws them (and plays sound, see effects.ts).
 */
import type {
  AlertView,
  CabMode,
  CabSnapshot,
  EstimateUpdate,
  InsightNote,
  LessonOffer,
  RiskUpdate,
  SyncUpdate,
  TaskProgress,
  Telemetry,
  WsEnvelope,
} from "@shiftmate/contracts";
import { create } from "zustand";

type Priority = AlertView["priority"];
const RANK: Record<Priority, number> = { P1: 0, P2: 1, P3: 2, P4: 3 };
const FEED_LIMIT = 50;
const NOTES_LIMIT = 20;

export type AlertsState = {
  current: AlertView | null;
  strip: AlertView | null;
  reduced: Record<string, AlertView>; // by rule id
  queue: Record<string, AlertView>; // by alert id
  queuedCount: number; // the edge's count of queued interrupting alerts
  queueTop: Priority | null;
  feed: AlertView[];
};

export type LiveState = {
  connected: boolean;
  lastMessageAt: number | null; // wall clock ms of the last message
  lastTelemetryAt: number | null;
  seq: number | null;
  loaded: boolean;
  machineId: string | null;
  operatorId: string | null;
  language: string | null;
  telemetry: Telemetry | null;
  mode: CabMode;
  risk: RiskUpdate | null;
  alerts: AlertsState;
  progress: Record<string, TaskProgress>;
  estimate: EstimateUpdate | null;
  sync: SyncUpdate | null;
  online: boolean;
  lessonOffer: LessonOffer | null;
  notes: InsightNote[];
  waitingFor: string | null;
};

export const emptyAlerts = (): AlertsState => ({
  current: null,
  strip: null,
  reduced: {},
  queue: {},
  queuedCount: 0,
  queueTop: null,
  feed: [],
});

export const initialLive = (): LiveState => ({
  connected: false,
  lastMessageAt: null,
  lastTelemetryAt: null,
  seq: null,
  loaded: false,
  machineId: null,
  operatorId: null,
  language: null,
  telemetry: null,
  mode: "paused",
  risk: null,
  alerts: emptyAlerts(),
  progress: {},
  estimate: null,
  sync: null,
  online: true,
  lessonOffer: null,
  notes: [],
  waitingFor: null,
});

function without<T>(record: Record<string, T>, key: string): Record<string, T> {
  if (!(key in record)) return record;
  const rest = { ...record };
  delete rest[key];
  return rest;
}

function topOf(queue: Record<string, AlertView>): Priority | null {
  const ps = Object.values(queue).map((a) => a.priority);
  return ps.length ? ps.reduce((a, b) => (RANK[a] <= RANK[b] ? a : b)) : null;
}

/** Remove an alert from every place it could be shown. */
function removeEverywhere(s: AlertsState, a: AlertView): AlertsState {
  const queue = without(s.queue, a.alert_id);
  const reduced =
    s.reduced[a.rule_id]?.alert_id === a.alert_id ? without(s.reduced, a.rule_id) : s.reduced;
  return {
    ...s,
    current: s.current?.alert_id === a.alert_id ? null : s.current,
    strip: s.strip?.alert_id === a.alert_id ? null : s.strip,
    reduced,
    queue,
    queueTop: topOf(queue),
  };
}

export function reduceAlerts(s: AlertsState, type: string, a: AlertView): AlertsState {
  let next: AlertsState;
  switch (type) {
    case "alert":
      next = removeEverywhere(s, a);
      if (a.status === "showing") next = { ...next, current: a };
      else if (a.status === "strip") next = { ...next, strip: a };
      else if (a.status === "reduced") next = { ...next, reduced: { ...next.reduced, [a.rule_id]: a } };
      break;
    case "alert_queued":
      next = removeEverywhere(s, a);
      next = { ...next, queue: { ...next.queue, [a.alert_id]: a } };
      next = { ...next, queueTop: topOf(next.queue) };
      break;
    case "alert_feed":
      next = removeEverywhere(s, a);
      next = { ...next, feed: [...next.feed, a].slice(-FEED_LIMIT) };
      break;
    case "alert_cleared":
      next = removeEverywhere(s, a);
      break;
    default:
      return s;
  }
  return { ...next, queuedCount: a.queued_count };
}

function fromSnapshot(snap: CabSnapshot, prev: LiveState): LiveState {
  const al = snap.alerts;
  return {
    ...prev,
    loaded: snap.loaded,
    machineId: snap.machine_id ?? prev.machineId,
    operatorId: snap.operator_id ?? null,
    language: snap.language ?? prev.language,
    telemetry: snap.telemetry ?? null,
    mode: snap.mode ?? prev.mode,
    online: snap.online ?? prev.online,
    sync: snap.sync ?? prev.sync,
    waitingFor: snap.waiting_for ?? null,
    risk: snap.risk ?? null,
    alerts: al
      ? {
          current: al.current,
          strip: al.strip,
          reduced: Object.fromEntries(al.reduced.map((a) => [a.rule_id, a])),
          queue: {},
          queuedCount: al.queue_count,
          queueTop: al.queue_top_priority,
          feed: al.feed,
        }
      : emptyAlerts(),
    // a snapshot means the world was replaced (load or seek): live task numbers start again
    progress: {},
    estimate: null,
    lessonOffer: null,
  };
}

/** Apply one /ws/cab message. `now` is the wall clock (ms), used only for staleness. */
export function reduce(state: LiveState, env: WsEnvelope, now: number): LiveState {
  const s: LiveState = { ...state, lastMessageAt: now, seq: env.seq };
  const p = env.payload as Record<string, unknown>;
  switch (env.type) {
    case "snapshot": {
      const next = fromSnapshot(p as unknown as CabSnapshot, s);
      return { ...next, lastTelemetryAt: next.telemetry ? now : null };
    }
    case "telemetry": {
      const t = p as unknown as Telemetry;
      return { ...s, telemetry: t, mode: t.mode, lastTelemetryAt: now };
    }
    case "mode":
      return { ...s, mode: p.mode as CabMode };
    case "risk_update":
      return { ...s, risk: p as unknown as RiskUpdate };
    case "alert":
    case "alert_queued":
    case "alert_feed":
    case "alert_cleared":
      return { ...s, alerts: reduceAlerts(s.alerts, env.type, p as unknown as AlertView) };
    case "task_progress": {
      const tp = p as unknown as TaskProgress;
      return { ...s, progress: { ...s.progress, [tp.task_id]: tp } };
    }
    case "estimate_update":
      return { ...s, estimate: p as unknown as EstimateUpdate };
    case "sync":
      return { ...s, sync: p as unknown as SyncUpdate, online: (p as { online: boolean }).online };
    case "connectivity":
      return { ...s, online: Boolean(p.online) };
    case "session":
      return {
        ...s,
        operatorId: (p.operator_id as string | null) ?? null,
        language: (p.language as string | undefined) ?? s.language,
      };
    case "lesson_offer":
      return { ...s, lessonOffer: p as unknown as LessonOffer };
    case "insight":
      return { ...s, notes: [...s.notes, p as unknown as InsightNote].slice(-NOTES_LIMIT) };
    case "demo":
      if (p.event === "waiting") return { ...s, waitingFor: (p.beat as string | null) ?? null };
      return s;
    default:
      return s; // idle_segment, scenario_caption, … are used by later screens
  }
}

type LiveStore = LiveState & {
  apply: (env: WsEnvelope) => void;
  setConnected: (connected: boolean) => void;
  reset: () => void;
};

export const useLive = create<LiveStore>((set) => ({
  ...initialLive(),
  apply: (env) => set((s) => reduce(s, env, Date.now())),
  setConnected: (connected) => set({ connected }),
  reset: () => set(initialLive()),
}));
