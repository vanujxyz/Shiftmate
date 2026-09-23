import { createI18n } from "@shiftmate/i18n";
import { describe, expect, it } from "vitest";

import { initialLive, reduce } from "../live/store";
import { envelope, snapshot, telemetry } from "../test-fixtures";
import { railProps, staleSeconds } from "./railProps";

const en = createI18n("en").t;

function liveWith(tel = telemetry(), now = 1000) {
  const s = reduce(initialLive(), envelope("snapshot", snapshot({ telemetry: tel })), now);
  return { ...s, connected: true };
}

describe("status rail", () => {
  it("clear proximity, belt on, synced shows no sync words", () => {
    const p = railProps(liveWith(), en, 1000, "EXC001");
    expect(p.proximity.word).toBe("Clear");
    expect(p.proximity.stale).toBeUndefined();
    expect(p.belt?.word).toBe("Belt on");
    expect(p.sync.words).toBeUndefined();
    expect(p.clock).toBe("09:30");
    expect(p.machine).toMatchObject({ id: "EXC001", state: "working" });
  });

  it("a person says the tier, distance and side", () => {
    const tel = telemetry({ proximity_tier: "danger", proximity_m: 8, proximity_bearing_deg: 200 });
    const p = railProps(liveWith(tel), en, 1000, "EXC001");
    expect(p.proximity.tier).toBe("danger");
    expect(p.proximity.label).toBe("Too close: person 8 m away, behind you");
  });

  it("no people sensing is never drawn as clear", () => {
    const p = railProps(liveWith(telemetry({ proximity_tier: null })), en, 1000, "EXC001");
    expect(p.proximity.noSensing).toBe(true);
    expect(p.proximity.word).toBe("No sensing");
  });

  it("telemetry older than 30 s gets the stale mark", () => {
    const live = liveWith();
    expect(staleSeconds(live, 1000 + 29_000)).toBeNull();
    expect(staleSeconds(live, 1000 + 40_000)).toBe(40);
    expect(railProps(live, en, 41_000, "EXC001").proximity.stale).toBe("No update 40 s");
  });

  it("past two minutes the stale mark reads in minutes", () => {
    const p = railProps(liveWith(), en, 1000 + 257_000, "EXC001");
    expect(p.proximity.stale).toBe("No update 4 min");
    expect(p.proximity.staleShort).toBe("4 min");
  });

  it("a dropped socket marks the data stale at once", () => {
    expect(staleSeconds({ ...liveWith(), connected: false }, 3000)).toBe(2);
  });

  it("raised risk names its main reason", () => {
    const live = reduce(
      liveWith(),
      envelope("risk_update", { score: 45, band: "amber", top: [{ component: "heat", points: 25 }], thresholds: {} }),
      1000,
    );
    const p = railProps(live, en, 1000, "EXC001");
    expect(p.risk).toMatchObject({ band: "amber", word: "Risk raised", reason: "Mainly heat" });
  });

  it("offline with reports waiting says so in words", () => {
    let live = reduce(liveWith(), envelope("sync", { online: false, outbox_size: 3, last_sync: null }), 1000);
    expect(railProps(live, en, 1000, "EXC001").sync).toMatchObject({ state: "offline", words: "3 waiting" });
    live = reduce(live, envelope("sync", { online: true, outbox_size: 0, last_sync: null }), 1000);
    expect(railProps(live, en, 1000, "EXC001").sync.state).toBe("synced");
  });

  it("the queue pip shows the edge's own count", () => {
    const live = liveWith();
    const p = railProps(
      { ...live, alerts: { ...live.alerts, queuedCount: 2, queueTop: "P2" } },
      en,
      1000,
      "EXC001",
    );
    expect(p.queue).toMatchObject({ priority: "P2", count: 2 });
  });
});
