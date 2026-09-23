/**
 * Sound timing exactly per alert_policy.yaml (DESIGN §8): the timings come from /cab/config, so
 * these tests use the same numbers the policy file holds today.
 */
import type { AlertTimings } from "@shiftmate/contracts";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { alert } from "../test-fixtures";
import { AlertEffects, type Deps } from "./effects";
import { emptyAlerts, reduceAlerts } from "./store";

const TIMINGS: AlertTimings = {
  p1_speech_repeat_s: 4,
  p2_tone_repeat_s: 20,
  reduced_p1_repeat_s: 5,
  p3_snooze_min: 10,
  paused_idle_seconds: 30,
};

type Mocked = Omit<Deps, "play" | "speak"> & {
  play: ReturnType<typeof vi.fn<Deps["play"]>>;
  speak: ReturnType<typeof vi.fn<Deps["speak"]>>;
};
let deps: Mocked;

beforeEach(() => {
  vi.useFakeTimers();
  deps = {
    play: vi.fn<Deps["play"]>(),
    speak: vi.fn<Deps["speak"]>(),
    setTimer: (fn: () => void, ms: number) => setTimeout(fn, ms) as unknown as number,
    setRepeat: (fn: () => void, ms: number) => setInterval(fn, ms) as unknown as number,
    clearTimer: (id: number) => {
      clearTimeout(id);
      clearInterval(id);
    },
  };
});
afterEach(() => vi.useRealTimers());

const tones = (name: string) => deps.play.mock.calls.filter(([n]) => n === name).length;

describe("alert sound", () => {
  it("P1: tone every 1 s until acknowledged, speech once and again after 4 s", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    const p1 = alert();
    fx.update(reduceAlerts(emptyAlerts(), "alert", p1));
    expect(tones("critical_tone")).toBe(1);
    expect(deps.speak).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(3000);
    expect(tones("critical_tone")).toBe(4);
    expect(deps.speak).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(1000);
    expect(deps.speak).toHaveBeenCalledTimes(2);

    fx.acknowledge(p1);
    expect(tones("ack_confirm")).toBe(1);
    const before = tones("critical_tone");
    vi.advanceTimersByTime(10_000);
    expect(tones("critical_tone")).toBe(before);
    expect(deps.speak).toHaveBeenCalledTimes(2);
  });

  it("acknowledging before 4 s means the spoken line is not repeated", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    const p1 = alert();
    fx.update(reduceAlerts(emptyAlerts(), "alert", p1));
    vi.advanceTimersByTime(2000);
    fx.acknowledge(p1);
    vi.advanceTimersByTime(5000);
    expect(deps.speak).toHaveBeenCalledTimes(1);
  });

  it("P2: tone once, spoken once, tone again after 20 s if still up", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    fx.update(reduceAlerts(emptyAlerts(), "alert", alert({ priority: "P2", sound: "urgent_tone", presentation: "banner" })));
    expect(tones("urgent_tone")).toBe(1);
    expect(deps.speak).toHaveBeenCalledTimes(1);
    vi.advanceTimersByTime(19_999);
    expect(tones("urgent_tone")).toBe(1);
    vi.advanceTimersByTime(1);
    expect(tones("urgent_tone")).toBe(2);
    vi.advanceTimersByTime(60_000);
    expect(tones("urgent_tone")).toBe(2);
  });

  it("seen P2 is not a P1: no confirming tone", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    const p2 = alert({ priority: "P2", sound: "urgent_tone" });
    fx.update(reduceAlerts(emptyAlerts(), "alert", p2));
    fx.acknowledge(p2);
    expect(tones("ack_confirm")).toBe(0);
    vi.advanceTimersByTime(30_000);
    expect(tones("urgent_tone")).toBe(1);
  });

  it("a reduced P1 repeats its tone every 5 s until it clears", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    const p1 = alert();
    let s = reduceAlerts(emptyAlerts(), "alert", p1);
    fx.update(s);
    fx.acknowledge(p1);
    deps.play.mockClear();
    s = reduceAlerts(s, "alert", alert({ status: "reduced" }));
    fx.update(s);
    vi.advanceTimersByTime(15_000);
    expect(tones("critical_tone")).toBe(3);
    s = reduceAlerts(s, "alert_cleared", alert({ status: "cleared" }));
    fx.update(s);
    vi.advanceTimersByTime(15_000);
    expect(tones("critical_tone")).toBe(3);
  });

  it("a pre-empting P1 stops the P2 repeat", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    const p2 = alert({ alert_id: "b", priority: "P2", sound: "urgent_tone" });
    let s = reduceAlerts(emptyAlerts(), "alert", p2);
    fx.update(s);
    s = reduceAlerts(s, "alert_queued", { ...p2, status: "queued" });
    s = reduceAlerts(s, "alert", alert({ alert_id: "c" }));
    fx.update(s);
    fx.acknowledge(alert({ alert_id: "c" }));
    vi.advanceTimersByTime(30_000);
    expect(tones("urgent_tone")).toBe(1);
  });

  it("P3 and P4 are silent", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    fx.update(reduceAlerts(emptyAlerts(), "alert", alert({ priority: "P3", status: "strip", sound: "none", speak: false })));
    vi.advanceTimersByTime(30_000);
    expect(deps.play).not.toHaveBeenCalled();
    expect(deps.speak).not.toHaveBeenCalled();
  });

  it("dispose stops everything", () => {
    const fx = new AlertEffects(TIMINGS, deps);
    fx.update(reduceAlerts(emptyAlerts(), "alert", alert()));
    fx.dispose();
    deps.play.mockClear();
    vi.advanceTimersByTime(10_000);
    expect(deps.play).not.toHaveBeenCalled();
  });
});
