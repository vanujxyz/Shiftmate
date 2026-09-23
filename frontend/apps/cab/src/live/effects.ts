/**
 * What the operator hears (DESIGN §8 Sound, alert_policy.yaml timings).
 *
 * - P1: the critical tone every 1 s cycle until acknowledged; the spoken line once, and once more
 *   after `p1_speech_repeat_s` if still not acknowledged.
 * - P2: the urgent tone once and the spoken line once; the tone again after `p2_tone_repeat_s`
 *   if the banner is still up.
 * - A reduced P1 (acknowledged but still true): the tone every `reduced_p1_repeat_s`.
 * - Acknowledging a P1 plays the confirming falling pair. P3 and P4 are silent.
 * Whether an alert has a sound or speech at all comes from the edge (`sound`, `speak` in the view).
 */
import type { AlertTimings, AlertView } from "@shiftmate/contracts";

import type { AlertsState } from "./store";

export const P1_CYCLE_MS = 1000; // DESIGN §8: the 1.0 s P1 cycle

export type Deps = {
  play: (sound: "critical_tone" | "urgent_tone" | "ack_confirm") => void;
  speak: (alert: AlertView) => void;
  setTimer: (fn: () => void, ms: number) => number;
  setRepeat: (fn: () => void, ms: number) => number;
  clearTimer: (id: number) => void;
};

export class AlertEffects {
  private currentId: string | null = null;
  private currentTimers: number[] = [];
  private reducedTimers = new Map<string, number>(); // alert id → repeating timer
  private acknowledged = new Set<string>();

  constructor(
    private readonly timings: AlertTimings,
    private readonly deps: Deps,
  ) {}

  /** The operator pressed "I've stopped" / "Seen": stop the repeats now, confirm a P1. */
  acknowledge(alert: AlertView): void {
    this.acknowledged.add(alert.alert_id);
    if (alert.alert_id === this.currentId) this.stopCurrent();
    if (alert.priority === "P1") this.deps.play("ack_confirm");
  }

  update(alerts: AlertsState): void {
    const cur = alerts.current;
    if ((cur?.alert_id ?? null) !== this.currentId) {
      this.stopCurrent();
      this.currentId = cur?.alert_id ?? null;
      if (cur && !this.acknowledged.has(cur.alert_id)) this.startCurrent(cur);
    }
    const reducedIds = new Set(Object.values(alerts.reduced).map((a) => a.alert_id));
    for (const [id, timer] of this.reducedTimers) {
      if (!reducedIds.has(id)) {
        this.deps.clearTimer(timer);
        this.reducedTimers.delete(id);
      }
    }
    for (const a of Object.values(alerts.reduced)) {
      if (!this.reducedTimers.has(a.alert_id) && a.sound !== "none") {
        const every = this.timings.reduced_p1_repeat_s * 1000;
        this.reducedTimers.set(a.alert_id, this.deps.setRepeat(() => this.deps.play("critical_tone"), every));
      }
    }
  }

  dispose(): void {
    this.stopCurrent();
    for (const timer of this.reducedTimers.values()) this.deps.clearTimer(timer);
    this.reducedTimers.clear();
  }

  private startCurrent(a: AlertView): void {
    const { deps, timings } = this;
    if (a.priority === "P1") {
      if (a.sound !== "none") {
        deps.play("critical_tone");
        this.currentTimers.push(deps.setRepeat(() => deps.play("critical_tone"), P1_CYCLE_MS));
      }
      if (a.speak) {
        deps.speak(a);
        this.currentTimers.push(deps.setTimer(() => deps.speak(a), timings.p1_speech_repeat_s * 1000));
      }
    } else if (a.priority === "P2") {
      if (a.sound !== "none") {
        deps.play("urgent_tone");
        this.currentTimers.push(deps.setTimer(() => deps.play("urgent_tone"), timings.p2_tone_repeat_s * 1000));
      }
      if (a.speak) deps.speak(a);
    }
  }

  private stopCurrent(): void {
    for (const timer of this.currentTimers) this.deps.clearTimer(timer);
    this.currentTimers = [];
  }
}
