import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { Markdown } from "./lib/markdown";
import { entities, machine } from "./test-fixtures";
import { patternText } from "./screens/Fleet";
import { dayOptions, suggestionText } from "./screens/Supervisor";
import { fakeServices, renderAt } from "./test-render";

/** A socket the test drives by hand. */
class FakeSocket {
  static last: FakeSocket | null = null;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(readonly url: string) {
    FakeSocket.last = this;
  }
  close() {}
  send(type: string, payload: unknown) {
    act(() => this.onmessage?.({ data: JSON.stringify({ type, seq: 1, ts: "", machine_id: null, site_id: "CHN-HWY-01", payload }) }));
  }
}

const DEMO = {
  scenario: "ravi_shift",
  site_id: "CHN-HWY-01",
  focus_machine: "EXC001",
  sim_time: "2026-09-24T09:30:00+05:30",
  playing: false,
  speed: 1,
  waiting_for: null,
  online: true,
  captions: false,
  signed_in: "OP1001",
  beats: [
    { id: "sign_in", at: "07:00", action: "await_operator_sign_in", caption: { en: "Ravi signs in", hi: "रवि साइन इन", ta: "ரவி உள்நுழைகிறார்" }, done: true },
    { id: "worker_near", at: "09:30", action: "camera_or_sim_person", caption: { en: "A worker walks into the swing zone", hi: "एक मज़दूर", ta: "ஒரு தொழிலாளி சுழலும் பகுதிக்குள் நுழைகிறார்" }, done: false },
  ],
};
const LAYOUT = {
  site_id: "CHN-HWY-01",
  name: "Chennai Outer Ring Road — Package 3",
  timezone: "Asia/Kolkata",
  focus_machine: "EXC001",
  layout: {
    size: { w: 400, h: 260 },
    zones: [
      { id: "LOAD-A", type: "loading", polygon: [[170, 60], [210, 60], [210, 100], [170, 100]] },
      { id: "HAUL", type: "haul_road", polyline: [[210, 80], [380, 80]] },
    ],
  },
};
const SUMMARY = {
  site_id: "CHN-HWY-01",
  date: "2026-09-23",
  timezone: "Asia/Kolkata",
  tasks_total: 3,
  tasks_done: 2,
  tasks_behind: 1,
  tasks_on_track: 0,
  machines: [
    {
      machine_id: "EXC001",
      machine_type: "excavator",
      model: "Cat 320",
      sensor_tier: "advanced",
      operator_id: "OP1001",
      operator_name: "Ravi Kumar",
      tasks: [
        { task_id: "t1", task_type: "truck_loading", zone_id: "LOAD-A", planned_quantity: 18, done_quantity: 18, unit: "loads", status: "done", progress_pct: 100, expected_min: 100, elapsed_min: 95, track: "done" },
        { task_id: "t2", task_type: "trenching", zone_id: "DIG-A", planned_quantity: 60, done_quantity: 20, unit: "m", status: "active", progress_pct: 33, expected_min: 150, elapsed_min: 90, track: "behind" },
      ],
      engine_on_min: 300,
      working_min: 240,
      idle_min: 45,
      last_seen: null,
      track: "behind",
    },
  ],
};
const IDLE = {
  site_id: "CHN-HWY-01",
  date: "2026-09-23",
  machines: 24,
  total_idle_min: 1880.5,
  lead: { reason: "WAITING_FOR_TRUCK", minutes: 200, share: 0.4, site_issue: true },
  causes: [
    { reason: "WAITING_FOR_TRUCK", minutes: 200, share: 0.4, site_issue: true },
    { reason: "HABIT", minutes: 150, share: 0.3, site_issue: false },
  ],
  truck_wait_by_hour: [{ hour: 9, minutes: 20 }, { hour: 14, minutes: 59 }],
  suggestion: { key: "suggest.add_truck", reason: "WAITING_FOR_TRUCK", minutes: 200, zone_id: "LOAD-A", window_start: "12:00", window_end: "14:00", save_min_low: 27, save_min_high: 54, basis_days: 8, lesson_id: null },
  suggestions: [],
};
const SAFETY = {
  site_id: "CHN-HWY-01",
  date: "2026-09-23",
  p1: [{ event_id: "e1", ts: "2026-09-23T02:10:00Z", type: "alert", priority: "P1", code: "PROXIMITY_CRITICAL", machine_id: "EXC001", operator_id: "OP1001", operator_name: "Ravi Kumar", detail: { phase: "raised" } }],
  p2: [],
  p2_counts: { HEAT_NO_BREAK: 4 },
  incidents: [],
  near_misses: [],
  unattended: [],
  site_issues: [],
  reports: [],
  risk: [{ machine_id: "EXC001", band: "amber", score: 45, amber_min: 120, red_min: 0 }],
};
const TRENDS = {
  site_id: "CHN-HWY-01",
  days: 14,
  min_group_size: 3,
  daily: [{ day: "2026-09-22", operators: 24, suppressed: false, truck_wait_min: 130 }, { day: "2026-09-23", operators: 24, suppressed: false, truck_wait_min: 240 }],
  by_experience: [
    { group: "0–3 years", operators: 2, suppressed: true },
    { group: "3–6 years", operators: 5, suppressed: false, habit_idle_min_per_h: 2.08, seatbelt_unfastened_s_per_h: 10.97, fuel_per_load_cycle_l: 2.68, p1_per_100h: 4.68 },
  ],
};
const SITES = [{ site_id: "CHN-HWY-01", name: LAYOUT.name, country: "IN", timezone: "Asia/Kolkata", machines: 24, first_date: "2026-08-13", last_date: "2026-09-23" }];

beforeEach(() => vi.stubGlobal("WebSocket", FakeSocket));
afterEach(() => vi.unstubAllGlobals());

describe("console frame", () => {
  it("opens on the live site's map, with the sections and the demo-mode strip", async () => {
    fakeServices({ "/demo/state": DEMO, "/site/layout": LAYOUT, "/sites/": SUMMARY });
    renderAt(<App />, "/");
    expect(await screen.findByRole("heading", { name: /Live site map/ })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Console sections" });
    expect(within(nav).getAllByRole("link").map((a) => a.textContent)).toEqual(["Live map", "Day summary", "Fleet", "Demo", "Evaluation"]);
    expect(screen.getByRole("region", { name: "Demo mode · simulated data" })).toBeInTheDocument();
  });

  it("says when the gateway has no scenario", async () => {
    fakeServices({
      "/demo/state": { ...DEMO, scenario: null, site_id: null },
      "/site/layout": new Response(JSON.stringify({ error: { message: "No scenario is loaded." } }), { status: 409 }),
    });
    renderAt(<App />, "/site/CHN-HWY-01");
    expect(await screen.findByText("No demo scenario is loaded. Load one on the Demo page.")).toBeInTheDocument();
  });
});

describe("live map", () => {
  it("draws the site from the socket and shows a machine's day when selected", async () => {
    fakeServices({ "/demo/state": DEMO, "/site/layout": LAYOUT, "/sites/CHN-HWY-01/summary": SUMMARY });
    renderAt(<App />, "/site/CHN-HWY-01");
    await waitFor(() => expect(FakeSocket.last?.url).toMatch(/\/ws\/site\/CHN-HWY-01$/));
    FakeSocket.last!.send("snapshot", {
      loaded: true,
      entities: entities({
        machines: [machine({ proximity_tier: "danger" }), machine({ id: "EXC002", focus: false, state: "idle", proximity_tier: null, x_m: 50 })],
        workers: [{ id: "W1", x_m: 100, y_m: 108 }],
      }),
    });
    const map = await screen.findByRole("group", { name: "2 machines, 1 trucks and 1 people on site" });
    expect(within(map).getByRole("button", { name: "EXC001 · Excavator · Working · Danger" })).toBeInTheDocument();
    fireEvent.click(within(map).getByRole("button", { name: /EXC002/ }));
    expect(await screen.findByText("No people sensing")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Close" }));
    fireEvent.click(within(map).getByRole("button", { name: /EXC001/ }));
    expect(await screen.findByText("Operator: Ravi Kumar")).toBeInTheDocument();
    expect(screen.getByText("Warning rings 14 m · 9 m · 7 m")).toBeInTheDocument();
    expect(screen.getByText("20 of 60 m done")).toBeInTheDocument();

    FakeSocket.last!.send("site_event", { event_id: "e9", ts: "2026-09-24T09:31:00+05:30", type: "alert", priority: "P1", code: "PROXIMITY_CRITICAL", machine_id: "EXC001" });
    expect(await screen.findByText("Person inside the swing zone")).toBeInTheDocument();
  });
});

describe("day summary", () => {
  it("names the cause, gives one suggestion with its basis, and keeps small groups hidden", async () => {
    fakeServices({
      "/demo/state": DEMO,
      "/sites/CHN-HWY-01/summary": SUMMARY,
      "/sites/CHN-HWY-01/idle-causes": IDLE,
      "/sites/CHN-HWY-01/safety": SAFETY,
      "/sites/CHN-HWY-01/trends": TRENDS,
      "/sites": SITES,
    });
    renderAt(<App />, "/supervisor/CHN-HWY-01");
    expect(await screen.findByText("3 h 20 m waiting for trucks")).toBeInTheDocument();
    expect(screen.getByText("Add one truck to LOAD-A, 12:00–14:00 · would likely save 27 m – 54 m · based on 8 similar days")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 tasks done · 1 behind")).toBeInTheDocument();
    expect(screen.getByText("Most waiting at 14:00 (59 m).")).toBeInTheDocument();
    expect(await screen.findByText("Person inside the swing zone")).toBeInTheDocument();
    expect(screen.getByText("07:40")).toBeInTheDocument(); // 02:10 UTC in Chennai
    expect(screen.getByText("Hidden (fewer than 3)")).toBeInTheDocument();
    expect(screen.getByText("Counts are for learning, not ranking. Operators see the same data about themselves.")).toBeInTheDocument();
  });

  it("offers the fleet's days, newest first", () => {
    expect(dayOptions("2026-09-20", "2026-09-23")).toEqual(["2026-09-23", "2026-09-22", "2026-09-21", "2026-09-20"]);
    expect(dayOptions(null, null)).toEqual([]);
  });

  it("writes a suggestion without a saving when there is no basis", async () => {
    const { createI18n } = await import("@shiftmate/i18n");
    const t = createI18n("en").t;
    expect(suggestionText(t, { key: "suggest.toolbox_idle", reason: "HABIT", minutes: 400 })).toBe(
      "Talk about short stops at the next toolbox meeting",
    );
  });
});

describe("fleet", () => {
  it("keeps the projection apart from what was measured", async () => {
    fakeServices({
      "/demo/state": DEMO,
      "/fleet/overview": {
        machines_total: 60,
        by_type: { excavator: 30, wheel_loader: 18, dozer: 12 },
        by_tier: { basic: 22, standard: 22, advanced: 16 },
        records: {},
        scale_machines: 10000,
        sites: [{ site_id: "CHN-HWY-01", name: LAYOUT.name, country: "IN", timezone: "Asia/Kolkata", latest_date: "2026-09-23", machines_total: 24, machines_active: 20, by_type: {}, by_tier: {}, risk_bands: { green: 2, amber: 16, red: 2 }, ground_condition: "muddy", heat_index_c: 41.3, last_ingest: null }],
      },
      "/fleet/patterns": [{ dimension: "ground_condition", task_type: "trenching", condition: "muddy", multiplier: 1.303, change_pct: 30.3, tasks: 144, machines: 25, reference: "dry/rocky" }],
      "/scale/stats": {
        totals: { intervals: 138159, events: 15947, reports: 1, tasks: 8240 },
        scale_machines: 10000,
        live: { records_last_60s: 0, records_per_s: 0 },
        run: { machines: 10000, sim_minutes: 60, records: 44612, intervals: 40000, events: 4612, requests: 92, seconds: 29.66, records_per_s: 4081.9, request_ms_p50: 119.6, request_ms_p95: 146.7, bytes_sent: 1, bytes_per_machine_per_hour: 5650.7, records_per_machine_per_hour: 4.46, finished_at: "" },
        bench: null,
        projection: { label: "projection", machines: 1600000, basis: "runtime benchmark (200 full machine runtimes)", hours_per_day: 24, uplink_bytes_per_day: 1, uplink_gb_per_day: 183.48, records_per_day: 1, records_per_s: 1688.9, ingest_nodes_at_measured_rate: 0.41 },
      },
    });
    renderAt(<App />, "/fleet");
    expect(await screen.findByText("20 of 24 machines active")).toBeInTheDocument();
    expect(screen.getByText("Trenching on muddy ground: +30 % time compared with dry or rocky ground")).toBeInTheDocument();
    expect(await screen.findByText(/Measured: 10,000 simulated machines sent 44,612 records/)).toBeInTheDocument();
    expect(screen.getByText("Projection, not measured. Basis: runtime benchmark (200 full machine runtimes).")).toBeInTheDocument();
  });

  it("pattern lines read in every language", async () => {
    const { createI18n } = await import("@shiftmate/i18n");
    const p = { dimension: "heat_band", task_type: "grading", condition: "40–52 °C", multiplier: 1.2, change_pct: 20, tasks: 10, machines: 3, reference: "below 32 °C" };
    expect(patternText(createI18n("ta").t, p)).toBe("வெப்பக் குறியீடு 40–52 °C-இல் தரை சமன் செய்தல்: 32 °C-க்குக் குறைவை விட +20 % நேரம்");
  });
});

describe("demo control", () => {
  it("loads, plays and jumps to a beat; captions follow the language", async () => {
    const calls = fakeServices({
      "/demo/state": DEMO,
      "/demo/scenarios": [
        { name: "fleet_tour", title: { en: "Fleet tour", hi: "फ़्लीट दौरा", ta: "ஃப்ளீட் சுற்றுப்பயணம்" }, site_id: "PIL-MIN-01", focus_machine: "WHL014" },
        { name: "ravi_shift", title: { en: "Ravi's shift", hi: "रवि की शिफ़्ट", ta: "ரவியின் பணி நேரம்" }, site_id: "CHN-HWY-01", focus_machine: "EXC001" },
      ],
      "/demo/": () => DEMO,
    });
    renderAt(<App />, "/demo", "ta");
    expect(await screen.findByText("ஒரு தொழிலாளி சுழலும் பகுதிக்குள் நுழைகிறார்")).toBeInTheDocument();
    fireEvent.click(screen.getAllByRole("button", { name: "இங்கே செல்" })[1]!);
    await waitFor(() => expect(calls.find((c) => c.url === "/demo/seek")?.body).toEqual({ beat_id: "worker_near" }));
    fireEvent.click(screen.getByRole("button", { name: /ஃப்ளீட் சுற்றுப்பயணம்/ }));
    await waitFor(() => expect(calls.find((c) => c.url === "/demo/scenario/load")?.body).toEqual({ name: "fleet_tour" }));
    fireEvent.click(screen.getByRole("button", { name: "60×" }));
    await waitFor(() => expect(calls.find((c) => c.url === "/demo/speed")?.body).toEqual({ x: 60 }));
  });
});

describe("evaluation", () => {
  it("shows docs/EVAL.md as written", async () => {
    fakeServices({ "/demo/state": DEMO });
    renderAt(<App />, "/eval");
    expect(await screen.findByRole("heading", { name: "ShiftMate — Evaluation results" })).toBeInTheDocument();
    expect(screen.getAllByRole("table").length).toBeGreaterThan(3);
  });

  it("the markdown reader never renders HTML from the file", () => {
    const { container } = renderAt(<Markdown source={"# T\n\n<b>x</b> and **bold** and `code`\n\n| a | b |\n|---|---|\n| 1 | 2 |"} />, "/");
    expect(container.querySelector("b")).toBeNull();
    expect(container.querySelector("strong")?.textContent).toBe("bold");
    expect(container.querySelectorAll("td")).toHaveLength(2);
  });
});
