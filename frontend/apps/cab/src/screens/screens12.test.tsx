import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { useLive } from "../live/store";
import { pendingReports } from "../offline/reports";
import { store } from "../offline/db";
import { useSession } from "../session";
import { envelope, insights, shift, snapshot } from "../test-fixtures";
import { fakeEdge, renderAt } from "../test-render";
import { mergeSplit, splitKind, stopGroups } from "./MyDay";
import { mergeDraft } from "./Report";

class QuietSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

const CONFIG = {
  alerts: { p1_speech_repeat_s: 4, p2_tone_repeat_s: 20, reduced_p1_repeat_s: 5, p3_snooze_min: 10, paused_idle_seconds: 30 },
  checklist: [],
  languages: ["en", "hi", "ta"],
};

function paused(language: "en" | "ta" = "en") {
  useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language });
  act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "paused" }))));
}

beforeEach(async () => {
  vi.stubGlobal("WebSocket", QuietSocket);
  useLive.getState().reset();
  for (const r of await store.pending.all()) await store.pending.delete(r.id);
  for (const r of await store.drafts.all()) await store.drafts.delete(r.id);
});
afterEach(() => vi.unstubAllGlobals());

describe("My Day pieces", () => {
  it("moving counts as working; neighbours of one kind are drawn as one", () => {
    expect(["working", "travel", "engine_off", "HABIT", "nonsense"].map(splitKind)).toEqual([
      "WORKING", "WORKING", "OFF", "HABIT", "UNKNOWN",
    ]);
    expect(mergeSplit(insights().time_split).map((s) => [s.kind, s.minutes])).toEqual([
      ["OFF", 4], ["WARM_UP", 4], ["WORKING", 114], ["WAITING_FOR_TRUCK", 37], ["WORKING", 101], ["HABIT", 20],
    ]);
  });

  it("stops are grouped by cause, longest first, with the evidence of the longest one", () => {
    const g = stopGroups(insights());
    expect(g.map((x) => [x.reason, x.minutes, x.count])).toEqual([
      ["WAITING_FOR_TRUCK", 37, 2], ["HABIT", 20, 1], ["WARM_UP", 4, 1],
    ]);
    expect(g[0]?.evidence).toEqual(["no_truck_sensor"]);
    expect(g[0]?.fuel).toBeCloseTo(2.0);
  });
});

describe("My Day screen", () => {
  it("shows the time split, stops with causes, fuel against usual, and the notes", async () => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/insights/OP1001": insights() });
    paused();
    renderAt(<App />, "/insights");
    expect(await screen.findByText("Only you can see this page.")).toBeInTheDocument();
    expect(await screen.findByText("Working 3 h 35 m, stopped 1 h 01 m, engine off 4 m", { selector: "p" })).toBeInTheDocument();
    expect(screen.getByText("Waiting for a truck", { selector: "span" })).toBeInTheDocument();
    expect(screen.getByText("No truck at the loading point · 2 stops · 2 L")).toBeInTheDocument();
    expect(screen.getByText("Waiting for trucks is a site delay, not your idle time.")).toBeInTheDocument();
    expect(screen.getByText("1.6 L")).toBeInTheDocument();
    expect(screen.getByText("your usual 3 L")).toBeInTheDocument();
    expect(screen.getByText("18 of 18 loads done.")).toBeInTheDocument();
    expect(screen.getByText(/Short stops added up to 20 min today/)).toBeInTheDocument();
  });

  it("in Tamil the unit inside a note is Tamil too", async () => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/insights/OP1001": insights() });
    paused("ta");
    renderAt(<App />, "/insights", "ta");
    expect(await screen.findByText("18-ல் 18 லோடு முடிந்தது.")).toBeInTheDocument();
  });

  it("the week view lists earlier days", async () => {
    const week = {
      ...insights(),
      range: "week",
      days: [{ day: "2026-09-22", engine_on_min: 446, working_min: 260, truck_wait_min: 121, short_stops_min: 18, loads: 54, fuel_per_load_l: 1.41 }],
    };
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/insights/OP1001?range=week": week, "/insights/OP1001": insights() });
    paused();
    renderAt(<App />, "/insights");
    fireEvent.click(await screen.findByRole("button", { name: "This week" }));
    expect(await screen.findByText("2 h 01 m")).toBeInTheDocument();
    expect(screen.getByText("54")).toBeInTheDocument();
    expect(screen.getByText("1.4 L")).toBeInTheDocument();
  });
});

describe("report", () => {
  it("taps beat keywords; no words means no summary", () => {
    const parsed = { type: "incident", severity: "high", summary_en: "x", summary_local: "x", people_involved: true, injury: true, parser: "offline" } as const;
    expect(mergeDraft(parsed, { type: "near_miss", text: "", people: false, injury: true })).toMatchObject({
      type: "near_miss", severity: "high", people_involved: false, injury: false, summary_en: "", parser: "offline+tap",
    });
    expect(mergeDraft(null, { type: "incident", text: "cut hand", people: true, injury: true }).severity).toBe("high");
  });

  it("type → words → check (filled in by the gateway) → send; listed with its sync state", async () => {
    let saved: unknown = null;
    const parsed = {
      draft: { type: "near_miss", severity: "medium", summary_en: "worker behind bucket", summary_local: "worker behind bucket", people_involved: true, injury: false, parser: "offline" },
      context: { ts: "2026-09-24T12:10:00+05:30", machine_id: "EXC001", operator_id: "OP1001", site_id: "CHN-HWY-01", zone_id: "DIG-A", task_id: "T2", weather: {}, risk_score: 40, language: "en" },
      mode: "offline",
    };
    fakeEdge({
      "/cab/config": CONFIG,
      "/operators/OP1001/shift": shift(),
      "/reports/parse": parsed,
      "/reports?operator_id": () => (saved ? [{ report_id: "r1", ts: "2026-09-24T12:10:00+05:30", draft: parsed.draft, context: parsed.context, synced: false }] : []),
      "/reports": (_u: string, init?: RequestInit) => {
        saved = JSON.parse(String(init?.body));
        return { report_id: "r1", ts: "2026-09-24T12:10:00+05:30", draft: parsed.draft, context: parsed.context, synced: false };
      },
    });
    paused();
    renderAt(<App />, "/report");
    expect(await screen.findByText("No reports yet.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Near miss/ }));
    fireEvent.change(screen.getByLabelText("Report text"), { target: { value: "worker behind bucket" } });
    fireEvent.click(screen.getAllByRole("button", { name: "Yes" })[0]!);
    fireEvent.click(screen.getByRole("button", { name: "Check this" }));
    expect(await screen.findByText("DIG-A · 12:10")).toBeInTheDocument();
    expect(screen.getByText("Yes, people were involved")).toBeInTheDocument();
    // change how serious it was, with big buttons
    fireEvent.click(screen.getAllByRole("button", { name: "Edit" })[1]!);
    fireEvent.click(screen.getByRole("button", { name: "Very serious" }));
    fireEvent.click(screen.getByRole("button", { name: "Send report" }));
    expect(await screen.findByText("Report saved. Your supervisor will see it.")).toBeInTheDocument();
    expect(saved).toMatchObject({ draft: { type: "near_miss", severity: "high", people_involved: true }, context: { zone_id: "DIG-A" } });
    expect(await screen.findByText("Waiting for internet")).toBeInTheDocument();
  });

  it("with the gateway unreachable the report waits on the tablet", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
    paused();
    renderAt(<App />, "/report");
    fireEvent.click(await screen.findByRole("button", { name: /Machine problem/ }));
    fireEvent.change(screen.getByLabelText("Report text"), { target: { value: "Left mirror cracked" } });
    fireEvent.click(screen.getByRole("button", { name: "Check this" }));
    expect(await screen.findByText("Filled in when it reaches the machine")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Send when online" }));
    expect(await screen.findByText("Saved on this tablet. It goes to the machine as soon as it reconnects.")).toBeInTheDocument();
    await waitFor(async () => expect(await pendingReports("OP1001")).toHaveLength(1));
    expect(await screen.findByText("On this tablet, not at the machine yet")).toBeInTheDocument();
  });
});
