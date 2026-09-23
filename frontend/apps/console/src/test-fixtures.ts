/** Shared console test data, shaped like the gateway's /ws/site entities. */
import type { Entities } from "./live/site";

export const machine = (over: Partial<Entities["machines"][number]> = {}): Entities["machines"][number] => ({
  id: "EXC001",
  type: "excavator",
  tier: "advanced",
  x_m: 100,
  y_m: 100,
  heading_deg: 350,
  state: "working",
  proximity_tier: "clear",
  rings: { caution_m: 14, danger_m: 9, critical_m: 7 },
  focus: true,
  ...over,
});

export const entities = (over: Partial<Entities> = {}): Entities => ({
  ts: "2026-09-24T09:30:00+05:30",
  site_id: "CHN-HWY-01",
  machines: [machine()],
  trucks: [{ id: "TRK01", x_m: 200, y_m: 80, heading_deg: 90, state: "moving", zone_id: "LOAD-A" }],
  workers: [{ id: "W1", x_m: 20, y_m: 20 }],
  ...over,
});
