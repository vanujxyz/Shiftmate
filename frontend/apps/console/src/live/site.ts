/**
 * The live site feed (/ws/site/{site}): entities at 5 Hz, shared site events and demo events.
 * The map is drawn one update behind and moves smoothly between the last two updates
 * (`interpolate`), so machines and trucks glide at the screen's frame rate instead of jumping five
 * times a second (TRD §11.3). A seek or a new scenario (`snapshot`) jumps without gliding.
 */
import type { WsEnvelope } from "@shiftmate/contracts";
import { useEffect } from "react";
import { create } from "zustand";

import { siteSocketUrl } from "../api";

export type Tier = "clear" | "caution" | "danger" | "critical";
export type EntityMachine = {
  id: string;
  type: string;
  tier: string;
  x_m: number;
  y_m: number;
  heading_deg: number;
  state: "working" | "idle" | "travel" | "off";
  proximity_tier: Tier | null;
  rings: { caution_m: number; danger_m: number; critical_m: number };
  focus: boolean;
};
export type EntityTruck = { id: string; x_m: number; y_m: number; heading_deg: number; state: "waiting" | "moving"; zone_id: string };
export type EntityWorker = { id: string; x_m: number; y_m: number };
export type Entities = {
  ts: string;
  site_id: string;
  machines: EntityMachine[];
  trucks: EntityTruck[];
  workers: EntityWorker[];
};
export type SiteEvent = {
  key: string;
  ts: string;
  type: string;
  priority?: string | null;
  code?: string | null;
  machine_id?: string;
  status?: string;
  zone_id?: string | null;
};

export type SiteState = {
  connected: boolean;
  loaded: boolean | null;
  prev: { at: number; data: Entities } | null;
  next: { at: number; data: Entities } | null;
  lastAt: number | null;
  events: SiteEvent[];
};

export const initialSite = (): SiteState => ({
  connected: false,
  loaded: null,
  prev: null,
  next: null,
  lastAt: null,
  events: [],
});

const EVENTS_LIMIT = 40;

export function reduceSite(s: SiteState, env: WsEnvelope, now: number): SiteState {
  const p = env.payload as Record<string, unknown>;
  switch (env.type) {
    case "snapshot": {
      if (!p.loaded) return { ...s, loaded: false, prev: null, next: null, lastAt: now };
      const data = p.entities as Entities;
      return { ...s, loaded: true, prev: { at: now, data }, next: { at: now, data }, lastAt: now };
    }
    case "entities": {
      const data = p as unknown as Entities;
      return { ...s, loaded: true, prev: s.next ?? { at: now, data }, next: { at: now, data }, lastAt: now };
    }
    case "site_event": {
      const e: SiteEvent = {
        key: String(p.event_id ?? `${env.seq}`),
        ts: String(p.ts ?? p.since ?? env.ts),
        type: String(p.type ?? ""),
        priority: (p.priority as string | null) ?? null,
        code: (p.code as string | null) ?? null,
        machine_id: p.machine_id as string | undefined,
        status: p.status as string | undefined,
        zone_id: (p.zone_id as string | null) ?? null,
      };
      return { ...s, lastAt: now, events: [e, ...s.events].slice(0, EVENTS_LIMIT) };
    }
    case "demo":
      // a seek replaces the world: start the glide again from the next update
      if (p.event === "seeked") return { ...s, prev: s.next, lastAt: now, events: [] };
      return { ...s, lastAt: now };
    default:
      return s;
  }
}

const lerp = (a: number, b: number, t: number) => a + (b - a) * t;
const lerpAngle = (a: number, b: number, t: number) => {
  const d = ((((b - a) % 360) + 540) % 360) - 180;
  return a + d * t;
};

/** Positions between the last two updates; `t` 0 → prev, 1 → next. Ids missing from prev jump. */
export function interpolate(prev: Entities, next: Entities, t: number): Entities {
  const u = Math.min(1, Math.max(0, t));
  const pm = new Map(prev.machines.map((m) => [m.id, m]));
  const pt = new Map(prev.trucks.map((m) => [m.id, m]));
  const pw = new Map(prev.workers.map((m) => [m.id, m]));
  return {
    ...next,
    machines: next.machines.map((m) => {
      const a = pm.get(m.id);
      return a
        ? { ...m, x_m: lerp(a.x_m, m.x_m, u), y_m: lerp(a.y_m, m.y_m, u), heading_deg: lerpAngle(a.heading_deg, m.heading_deg, u) }
        : m;
    }),
    trucks: next.trucks.map((m) => {
      const a = pt.get(m.id);
      return a
        ? { ...m, x_m: lerp(a.x_m, m.x_m, u), y_m: lerp(a.y_m, m.y_m, u), heading_deg: lerpAngle(a.heading_deg, m.heading_deg, u) }
        : m;
    }),
    workers: next.workers.map((m) => {
      const a = pw.get(m.id);
      return a ? { ...m, x_m: lerp(a.x_m, m.x_m, u), y_m: lerp(a.y_m, m.y_m, u) } : m;
    }),
  };
}

/** Bearing (degrees clockwise from north) from a machine to the nearest person inside its rings. */
export function nearestPersonBearing(m: EntityMachine, workers: EntityWorker[]): number | null {
  let best: { d: number; b: number } | null = null;
  for (const w of workers) {
    const dx = w.x_m - m.x_m;
    const dy = w.y_m - m.y_m;
    const d = Math.hypot(dx, dy);
    if (d <= m.rings.caution_m && (!best || d < best.d)) {
      best = { d, b: ((Math.atan2(dx, dy) * 180) / Math.PI + 360) % 360 };
    }
  }
  return best ? best.b : null;
}

type SiteStore = SiteState & {
  apply: (env: WsEnvelope) => void;
  setConnected: (c: boolean) => void;
  reset: () => void;
};

export const useSite = create<SiteStore>((set) => ({
  ...initialSite(),
  apply: (env) => set((s) => reduceSite(s, env, Date.now())),
  setConnected: (connected) => set({ connected }),
  reset: () => set(initialSite()),
}));

/** Keep the store fed from the site's socket (reconnecting 1, 2, 4, 8, 10 s) while mounted. */
export function useSiteSocket(siteId: string | null, Impl: typeof WebSocket = WebSocket): void {
  const apply = useSite((s) => s.apply);
  const setConnected = useSite((s) => s.setConnected);
  const reset = useSite((s) => s.reset);
  useEffect(() => {
    if (!siteId) return;
    reset();
    let ws: WebSocket | null = null;
    let timer: number | null = null;
    let attempt = 0;
    let stopped = false;
    const open = () => {
      ws = new Impl(siteSocketUrl(siteId));
      ws.onopen = () => {
        attempt = 0;
        setConnected(true);
      };
      ws.onmessage = (ev: MessageEvent) => {
        try {
          apply(JSON.parse(String(ev.data)) as WsEnvelope);
        } catch {
          /* dropped; the next update corrects the map */
        }
      };
      ws.onclose = () => {
        setConnected(false);
        if (stopped) return;
        timer = window.setTimeout(open, Math.min(1000 * 2 ** attempt++, 10_000));
      };
      ws.onerror = () => ws?.close();
    };
    open();
    return () => {
      stopped = true;
      if (timer !== null) window.clearTimeout(timer);
      ws?.close();
    };
  }, [siteId, Impl, apply, setConnected, reset]);
}
