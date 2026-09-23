import { describe, expect, it } from "vitest";

import { alert, envelope, snapshot, telemetry } from "../test-fixtures";
import { initialLive, reduce, reduceAlerts, emptyAlerts } from "./store";

describe("live reducer", () => {
  it("a snapshot replaces the world and clears live task numbers", () => {
    let s = reduce(initialLive(), envelope("task_progress", { task_id: "T1", status: "active", done_qty: 3, planned_qty: 18, unit: "loads" }), 1);
    expect(s.progress.T1?.done_qty).toBe(3);
    const risk = { score: 40, band: "amber", top: [{ component: "heat", points: 25 }], thresholds: {} };
    s = reduce(s, envelope("snapshot", snapshot({ mode: "paused", risk } as never)), 2);
    expect(s.loaded).toBe(true);
    expect(s.operatorId).toBe("OP1001");
    expect(s.mode).toBe("paused");
    expect(s.progress).toEqual({});
    expect(s.risk?.band).toBe("amber");
    expect(s.lastTelemetryAt).toBe(2);
  });

  it("telemetry carries the mode and stamps its arrival", () => {
    const s = reduce(initialLive(), envelope("telemetry", telemetry({ mode: "paused" })), 50);
    expect(s.mode).toBe("paused");
    expect(s.lastTelemetryAt).toBe(50);
    expect(s.lastMessageAt).toBe(50);
  });

  it("connectivity and sync set the online state", () => {
    let s = reduce(initialLive(), envelope("connectivity", { online: false }), 1);
    expect(s.online).toBe(false);
    s = reduce(s, envelope("sync", { online: true, outbox_size: 2, last_sync: null }), 2);
    expect(s.online).toBe(true);
    expect(s.sync?.outbox_size).toBe(2);
  });

  it("a session message with nobody signed in clears the operator", () => {
    let s = reduce(initialLive(), envelope("snapshot", snapshot()), 1);
    s = reduce(s, envelope("session", { operator_id: null }), 2);
    expect(s.operatorId).toBeNull();
  });
});

describe("alert projection (engines/alerts.py decides, the cab draws)", () => {
  it("a higher alert pre-empts: the P2 moves to the queue, the P1 shows", () => {
    const p2 = alert({ alert_id: "b", rule_id: "PROXIMITY_DANGER", priority: "P2", presentation: "banner" });
    let s = reduceAlerts(emptyAlerts(), "alert", p2);
    expect(s.current?.alert_id).toBe("b");
    s = reduceAlerts(s, "alert_queued", { ...p2, status: "queued", queued_count: 1 });
    s = reduceAlerts(s, "alert", alert({ alert_id: "c", queued_count: 1 }));
    expect(s.current?.alert_id).toBe("c");
    expect(Object.keys(s.queue)).toEqual(["b"]);
    expect(s.queueTop).toBe("P2");
    expect(s.queuedCount).toBe(1);
  });

  it("a cleared alert disappears from every place", () => {
    let s = reduceAlerts(emptyAlerts(), "alert", alert());
    s = reduceAlerts(s, "alert_cleared", alert({ status: "cleared" }));
    expect(s.current).toBeNull();
    expect(s.queuedCount).toBe(0);
  });

  it("an acknowledged P1 still true becomes reduced, keyed by rule", () => {
    let s = reduceAlerts(emptyAlerts(), "alert", alert());
    s = reduceAlerts(s, "alert", alert({ status: "reduced", presentation: "reduced" }));
    expect(s.current).toBeNull();
    expect(s.reduced.PROXIMITY_CRITICAL?.alert_id).toBe("a1");
  });

  it("a newer P3 replaces the strip; the older one is filed in the feed", () => {
    const p3 = (id: string) => alert({ alert_id: id, rule_id: "FATIGUE_WARN", priority: "P3", presentation: "strip", status: "strip", message_key: "alert.fatigue_warn" });
    let s = reduceAlerts(emptyAlerts(), "alert", p3("x"));
    s = reduceAlerts(s, "alert_feed", { ...p3("x"), status: "feed" });
    s = reduceAlerts(s, "alert", p3("y"));
    expect(s.strip?.alert_id).toBe("y");
    expect(s.feed.map((a) => a.alert_id)).toEqual(["x"]);
  });

  it("the feed keeps the newest 50", () => {
    let s = emptyAlerts();
    for (let i = 0; i < 60; i++) s = reduceAlerts(s, "alert_feed", alert({ alert_id: `f${i}`, priority: "P4" }));
    expect(s.feed).toHaveLength(50);
    expect(s.feed[49]?.alert_id).toBe("f59");
  });

  it("unknown message types leave the state alone", () => {
    const s = emptyAlerts();
    expect(reduceAlerts(s, "nonsense", alert())).toBe(s);
  });
});
