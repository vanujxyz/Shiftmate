import { describe, expect, it } from "vitest";

import { operatorFromBadge } from "./screens/BadgeScanner";
import { addClock, clockOf, formatQty, sideOf } from "./text";

describe("text helpers", () => {
  it("bearing → side, clockwise from forward", () => {
    expect([0, 44, 45, 134, 135, 224, 225, 314, 315, -90, null].map(sideOf)).toEqual([
      "front", "front", "right", "right", "rear", "rear", "left", "left", "front", "left", "front",
    ]);
  });

  it("clock arithmetic stays on the site's wall clock", () => {
    expect(addClock("07:15", 95)).toBe("08:50");
    expect(addClock("23:30", 45)).toBe("00:15");
    expect(clockOf("2026-09-24T10:42:05+05:30")).toBe("10:42");
    expect(clockOf(null)).toBeNull();
  });

  it("quantities stay whole when whole", () => {
    expect(formatQty(18)).toBe("18");
    expect(formatQty(42.25)).toBe("42.3");
  });

  it("badges read SHIFTMATE:<operator>, nothing else", () => {
    expect(operatorFromBadge("SHIFTMATE:OP1001")).toBe("OP1001");
    expect(operatorFromBadge("OP1001")).toBeNull();
    expect(operatorFromBadge("SHIFTMATE:ADMIN")).toBeNull();
  });
});

describe("alert history order", () => {
  it("newest raised first, whatever order they were filed in", async () => {
    const { newestFirst } = await import("./text");
    const { alert } = await import("./test-fixtures");
    const filed = [
      alert({ alert_id: "a", raised_at: "2026-09-24T10:45:00+05:30" }),
      alert({ alert_id: "b", raised_at: "2026-09-24T09:30:00+05:30" }),
      alert({ alert_id: "c", raised_at: "2026-09-24T10:20:00+05:30" }),
    ];
    expect(newestFirst(filed).map((a) => a.alert_id)).toEqual(["a", "c", "b"]);
  });
});
