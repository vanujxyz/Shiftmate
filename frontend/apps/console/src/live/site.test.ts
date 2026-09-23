import type { WsEnvelope } from "@shiftmate/contracts";
import { describe, expect, it } from "vitest";

import { entities, machine } from "../test-fixtures";
import { initialSite, interpolate, nearestPersonBearing, reduceSite } from "./site";

const env = (type: string, payload: unknown, seq = 1): WsEnvelope =>
  ({ type, seq, ts: "2026-09-24T09:30:00+05:30", machine_id: null, site_id: "CHN-HWY-01", payload }) as unknown as WsEnvelope;

describe("site feed", () => {
  it("a snapshot jumps; entities glide from the previous update", () => {
    let s = reduceSite(initialSite(), env("snapshot", { loaded: true, entities: entities() }), 0);
    expect(s.prev?.data).toBe(s.next?.data);
    s = reduceSite(s, env("entities", entities({ machines: [machine({ x_m: 110, heading_deg: 10 })] })), 200);
    const mid = interpolate(s.prev!.data, s.next!.data, 0.5);
    expect(mid.machines[0]?.x_m).toBe(105);
    // the heading turns the short way round, through north
    expect(mid.machines[0]?.heading_deg).toBe(360);
    expect(interpolate(s.prev!.data, s.next!.data, 7).machines[0]?.x_m).toBe(110);
  });

  it("an unloaded gateway clears the map", () => {
    const s = reduceSite(initialSite(), env("snapshot", { loaded: false }), 0);
    expect(s.loaded).toBe(false);
    expect(s.next).toBeNull();
  });

  it("site events are kept newest first; a seek clears them", () => {
    let s = reduceSite(initialSite(), env("site_event", { event_id: "e1", ts: "t1", type: "alert", priority: "P1", code: "PROXIMITY_CRITICAL", machine_id: "EXC001" }), 0);
    s = reduceSite(s, env("site_event", { type: "site_issue", code: "WAITING_FOR_TRUCK", status: "open", machine_id: "EXC001", zone_id: "LOAD-A", since: "t2" }, 2), 1);
    expect(s.events.map((e) => e.type)).toEqual(["site_issue", "alert"]);
    s = reduceSite(s, env("demo", { event: "seeked" }), 2);
    expect(s.events).toEqual([]);
  });

  it("the tier sector points at the nearest person inside the rings", () => {
    const m = machine();
    expect(nearestPersonBearing(m, [{ id: "a", x_m: 100, y_m: 108 }, { id: "b", x_m: 105, y_m: 100 }])).toBe(90);
    expect(nearestPersonBearing(m, [{ id: "a", x_m: 100, y_m: 108 }])).toBe(0);
    expect(nearestPersonBearing(m, [{ id: "far", x_m: 300, y_m: 300 }])).toBeNull();
  });
});
