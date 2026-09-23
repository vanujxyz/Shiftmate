/** Shared test data shaped exactly like the edge's messages (types from @shiftmate/contracts). */
import type {
  AlertView,
  CabSnapshot,
  ShiftResponse,
  Telemetry,
  WsEnvelope,
} from "@shiftmate/contracts";

let seq = 0;

export function envelope(type: string, payload: unknown): WsEnvelope {
  seq += 1;
  return {
    type,
    seq,
    ts: "2026-09-24T09:30:00+05:30",
    machine_id: "EXC001",
    site_id: "CHN-HWY-01",
    payload: payload as WsEnvelope["payload"],
  } as WsEnvelope;
}

export function alert(over: Partial<AlertView> = {}): AlertView {
  return {
    alert_id: "a1",
    rule_id: "PROXIMITY_CRITICAL",
    priority: "P1",
    message_key: "alert.proximity_critical",
    category: "proximity",
    raised_at: "2026-09-24T09:30:12+05:30",
    status: "showing",
    presentation: "takeover",
    sound: "critical_tone",
    speak: true,
    requires_ack: true,
    escalated: false,
    queued_count: 0,
    context: { distance_m: 2.5, bearing_deg: 180 },
    ...over,
  };
}

export function telemetry(over: Partial<Telemetry> = {}): Telemetry {
  return {
    ts: "2026-09-24T09:30:00+05:30",
    machine_id: "EXC001",
    state: "WORKING",
    mode: "working",
    engine_on: true,
    travel_speed_kmh: 0,
    seatbelt_fastened: true,
    seat_occupied: true,
    proximity_m: null,
    proximity_bearing_deg: null,
    proximity_source: null,
    proximity_tier: "clear",
    heat_index_c: 38.2,
    risk_score: 20,
    risk_band: "green",
    task_id: "T1",
    task_progress_qty: 7,
    continuous_operation_min: 42,
    sensor_tier: "advanced",
    thresholds: { caution_m: 14, danger_m: 9, critical_m: 7, fatigue_warn_min: 240, fatigue_limit_min: 300 },
    ...over,
  };
}

export function snapshot(over: Partial<CabSnapshot> = {}): CabSnapshot {
  return {
    loaded: true,
    machine_id: "EXC001",
    operator_id: "OP1001",
    language: "ta",
    telemetry: telemetry(),
    mode: "working",
    alerts: { current: null, strip: null, reduced: [], queue_count: 0, queue_top_priority: null, feed: [] },
    online: true,
    sync: { online: true, outbox_size: 0, last_sync: null },
    captions: false,
    waiting_for: null,
    risk: null,
    ...over,
  };
}

export function shift(): ShiftResponse {
  const task = (id: string, type: string, qty: number, unit: "loads" | "m" | "m3", zone: string, start: string, status: "active" | "scheduled" | "done") => ({
    task_id: id,
    site_id: "CHN-HWY-01",
    machine_id: "EXC001",
    operator_id: "OP1001",
    task_type: type,
    zone_id: zone,
    planned_quantity: qty,
    quantity_unit: unit,
    scheduled_start: `2026-09-24T${start}:00+05:30`,
    status,
  });
  return {
    date: "2026-09-24",
    operator_id: "OP1001",
    machine_id: "EXC001",
    conditions: {
      ambient_temp_c: 29,
      relative_humidity_pct: 78,
      heat_index_c: 35.1,
      precipitation_mm_h: 0,
      wind_kmh: 6,
      visibility_m: 8000,
      is_night: false,
      ground_condition: "wet",
    },
    tasks: [
      {
        task: task("T1", "truck_loading", 18, "loads", "LOAD-A", "07:10", "active"),
        estimate: {
          p10: 55,
          p50: 65,
          p90: 85,
          reasons: [{ key: "reason.ground_wet_slower", feature: "ground", minutes: 15 }],
          remaining: true,
        },
        progress_qty: 6,
        zone_decal: "LOAD-A",
      },
      {
        task: task("T2", "trenching", 60, "m", "DIG-A", "09:40", "scheduled"),
        estimate: { p10: 120, p50: 140, p90: 170, reasons: [] },
        progress_qty: 0,
        zone_decal: "DIG-A",
      },
      {
        task: task("T3", "backfilling", 120, "m3", "DIG-A", "12:40", "scheduled"),
        estimate: null,
        progress_qty: 0,
        zone_decal: "DIG-A",
      },
    ],
    likely_finish: { p10: 200, p50: 230, p90: 270, reasons: [] },
    breaks: [{ at: "10:30", minutes: 15, reason_key: "shift.break_scheduled" }],
  };
}
