import { act, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "./App";
import { useLive } from "./live/store";
import { useSession } from "./session";
import { alert, envelope, shift, snapshot, telemetry } from "./test-fixtures";
import { fakeEdge, renderAt } from "./test-render";

class QuietSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

const CONFIG = {
  alerts: { p1_speech_repeat_s: 4, p2_tone_repeat_s: 20, reduced_p1_repeat_s: 5, p3_snooze_min: 10, paused_idle_seconds: 30 },
  checklist: [
    { id: "tyres", text: { en: "Tracks and tyres look sound", hi: "ट्रैक ठीक", ta: "தடங்கள் சரி" }, illustration: "tracks" },
    { id: "mirrors", text: { en: "Mirrors and camera clean", hi: "शीशे साफ़", ta: "கண்ணாடிகள் சுத்தம்" }, illustration: "mirror" },
  ],
  languages: ["en", "hi", "ta"],
};
const DEMO = { scenario: "ravi_shift", site_id: "CHN-HWY-01", focus_machine: "EXC001", sim_time: null, playing: false, speed: 1, waiting_for: null, online: true, captions: false, beats: [], signed_in: null };

function signInAs(language: "en" | "ta" = "en") {
  useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language });
}

function push(type: string, payload: unknown) {
  act(() => useLive.getState().apply(envelope(type, payload)));
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", QuietSocket);
  window.localStorage.clear();
  useLive.getState().reset();
  useSession.setState({ signedIn: null, language: "en", theme: "day", readAloud: true });
});
afterEach(() => vi.unstubAllGlobals());

describe("start of shift", () => {
  it("says the machine is not ready when no shift is loaded", async () => {
    fakeEdge({ "/demo/state": { ...DEMO, scenario: null, focus_machine: null }, "/cab/config": CONFIG });
    renderAt(<App />, "/start");
    expect(await screen.findByText("The machine is not ready")).toBeInTheDocument();
  });

  it("says when the machine gateway cannot be reached", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("offline")));
    renderAt(<App />, "/start");
    expect(await screen.findByText("Machine gateway not reachable yet")).toBeInTheDocument();
  });

  it("language → PIN (a wrong one first) → checklist → My Shift", async () => {
    const calls = fakeEdge({
      "/demo/state": DEMO,
      "/cab/config": CONFIG,
      "/session/sign-in": (_url: string, init?: RequestInit) => {
        const body = JSON.parse(String(init?.body));
        return body.pin === "1001"
          ? { profile: { operator: { name: "Ravi" } }, machine: {}, shift: shift() }
          : new Response(JSON.stringify({ error: { message: "That PIN didn't match." } }), { status: 401 });
      },
      "/checklist": { saved: true, problems: 0, report_ids: [] },
      "/operators/OP1001/shift": shift(),
    });
    renderAt(<App />, "/start");
    fireEvent.click(await screen.findByRole("button", { name: "தமிழ்" }));
    expect(useSession.getState().language).toBe("ta");
    fireEvent.click(await screen.findByRole("button", { name: "English" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));

    for (const d of "1234") fireEvent.click(screen.getByRole("button", { name: d }));
    expect(await screen.findByText("That PIN didn't match. Try again.")).toBeInTheDocument();
    for (const d of "1001") fireEvent.click(screen.getByRole("button", { name: d }));

    expect(await screen.findByText("Welcome, Ravi")).toBeInTheDocument();
    const signIns = calls.filter((c) => c.url === "/session/sign-in");
    expect(signIns.at(-1)?.body).toMatchObject({ operator_id: "OP1001", machine_id: "EXC001", pin: "1001", language: "en" });

    const start = screen.getByRole("button", { name: "Start work" });
    expect(start).toBeDisabled();
    fireEvent.click(screen.getAllByRole("button", { name: "Problem" })[1]!);
    fireEvent.click(screen.getByRole("button", { name: "All OK" }));
    fireEvent.click(start);
    await waitFor(() => expect(calls.some((c) => c.url === "/checklist")).toBe(true));
    const sent = calls.find((c) => c.url === "/checklist")!.body as { answers: { item_id: string; ok: boolean }[] };
    expect(sent.answers).toEqual([
      { item_id: "tyres", ok: true },
      { item_id: "mirrors", ok: false },
    ]);
  });
});

describe("the cab frame", () => {
  beforeEach(() => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/alerts/": { ok: true } });
  });

  it("without a session it goes to /start", async () => {
    fakeEdge({ "/demo/state": DEMO, "/cab/config": CONFIG });
    renderAt(<App />, "/");
    expect(await screen.findByText("Start your shift")).toBeInTheDocument();
  });

  it("Paused: rail, today's tasks with ranges and reasons, conditions, nav", async () => {
    signInAs();
    renderAt(<App />, "/");
    push("snapshot", snapshot({ mode: "paused", telemetry: telemetry({ mode: "paused", state: "IDLE" }) }));
    expect(await screen.findByText("Truck loading")).toBeInTheDocument();
    expect(screen.getByText("Trenching")).toBeInTheDocument();
    // the live telemetry (7 loads) wins over the plan's last saved progress (6)
    expect(screen.getByText(/^7 of 18 loads/)).toBeInTheDocument();
    expect(screen.getByText("Wet ground adds time")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Likely 1 h 05 m, between 55 m and 1 h 25 m." })).toBeInTheDocument();
    expect(screen.getByText("Not enough data yet")).toBeInTheDocument();
    // likely finish is a range of clock times from the machine's own clock (09:30 + 200…270 min)
    expect(screen.getByText("12:50 – 14:00")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Sections" })).toBeInTheDocument();
    expect(screen.getByText("Machine EXC001 · Ravi")).toBeInTheDocument();
  });

  it("live progress and estimates replace the plan's numbers", async () => {
    signInAs();
    renderAt(<App />, "/");
    push("snapshot", snapshot({ mode: "paused" }));
    await screen.findByText("Truck loading");
    push("mode", { mode: "paused", state: "IDLE" });
    push("task_progress", { task_id: "T1", status: "active", done_qty: 9, planned_qty: 18, unit: "loads" });
    expect(await screen.findByText(/^9 of 18 loads/)).toBeInTheDocument();
  });

  it("Working: only the rail and the active task line; the nav is hidden", async () => {
    signInAs();
    renderAt(<App />, "/");
    push("snapshot", snapshot({ mode: "working" }));
    expect(await screen.findByText("About 1 h 05 m left")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Sections" })).not.toBeInTheDocument();
    expect(screen.queryByText("Trenching")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Hold to talk" })).toBeInTheDocument();
  });

  it("Tamil: task names in Tamil and the machine ID in the content header (D-068)", async () => {
    signInAs("ta");
    renderAt(<App />, "/", "ta");
    push("snapshot", snapshot({ mode: "paused" }));
    expect(await screen.findByText("லாரி ஏற்றுதல்")).toBeInTheDocument();
    expect(screen.getByText("இயந்திரம் EXC001 · Ravi")).toBeInTheDocument();
  });

  it("a P1 takes over the screen; 'I've stopped' acknowledges it on the edge", async () => {
    signInAs();
    const calls = fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/alerts/": { ok: true } });
    renderAt(<App />, "/");
    push("snapshot", snapshot());
    push("alert", alert({ queued_count: 1 }));
    const dialog = await screen.findByRole("alertdialog");
    expect(within(dialog).getByText("Person inside the swing zone")).toBeInTheDocument();
    expect(within(dialog).getByText("behind you · 2.5 m")).toBeInTheDocument();
    expect(within(dialog).getByText("1 more alert after this")).toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole("button", { name: "I've stopped" }));
    await waitFor(() => expect(calls.some((c) => c.url === "/alerts/a1/ack")).toBe(true));
    push("alert", alert({ status: "reduced" }));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(screen.getByTestId("reduced-p1")).toBeInTheDocument();
  });

  it("a P2 banner sits under the rail and leaves the task line visible", async () => {
    signInAs();
    renderAt(<App />, "/");
    push("snapshot", snapshot());
    push("alert", alert({ alert_id: "b", rule_id: "PROXIMITY_DANGER", priority: "P2", message_key: "alert.proximity_danger", presentation: "banner" }));
    expect(await screen.findByText("Person close to the swing zone")).toBeInTheDocument();
    expect(await screen.findByText("About 1 h 05 m left")).toBeInTheDocument();
  });

  it("a P3 strip offers 'Later', which snoozes it on the edge", async () => {
    signInAs();
    const calls = fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/alerts/": { ok: true } });
    renderAt(<App />, "/");
    push("snapshot", snapshot({ mode: "paused" }));
    push("alert", alert({ alert_id: "s", rule_id: "FATIGUE_WARN", priority: "P3", message_key: "alert.fatigue_warn", status: "strip", presentation: "strip", sound: "none", speak: false }));
    fireEvent.click(await screen.findByRole("button", { name: "Later" }));
    await waitFor(() => expect(calls.find((c) => c.url === "/alerts/s/ack")?.body).toEqual({ action: "later" }));
  });

  it("a risk notice strip is simply 'Done'", async () => {
    signInAs();
    const calls = fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/alerts/": { ok: true } });
    renderAt(<App />, "/");
    push("snapshot", snapshot({ mode: "paused" }));
    push("alert", alert({ alert_id: "r", rule_id: "RISK_BAND_RAISED", priority: "P3", category: "risk", message_key: "alert.risk_band_raised", status: "strip", presentation: "strip", sound: "none", speak: false }));
    fireEvent.click(await screen.findByRole("button", { name: "Done" }));
    await waitFor(() => expect(calls.find((c) => c.url === "/alerts/r/ack")?.body).toEqual({ action: "done" }));
  });

  it("another operator signing in on the edge sends the tablet back to /start", async () => {
    signInAs();
    fakeEdge({ "/demo/state": DEMO, "/cab/config": CONFIG, "/operators/OP1001/shift": shift() });
    renderAt(<App />, "/");
    push("snapshot", snapshot({ operator_id: "OP1002" }));
    expect(await screen.findByText("Start your shift")).toBeInTheDocument();
    expect(useSession.getState().signedIn).toBeNull();
  });

  it("Safety: people, distances, risk contributions and settings", async () => {
    signInAs();
    renderAt(<App />, "/safety");
    push("snapshot", snapshot({ mode: "paused", telemetry: telemetry({ mode: "paused", proximity_tier: "caution", proximity_m: 12, proximity_bearing_deg: 90 }) }));
    push("risk_update", { score: 45, band: "amber", top: [{ component: "heat", points: 30 }, { component: "fatigue", points: 10 }], thresholds: { caution_m: 18, danger_m: 11, critical_m: 7, fatigue_warn_min: 180, fatigue_limit_min: 240 } });
    expect(await screen.findAllByText("One person 12 m away, on your right.")).not.toHaveLength(0);
    expect(screen.getByText("18 m")).toBeInTheDocument();
    expect(screen.getByText("Distances are wider now because risk is raised.")).toBeInTheDocument();
    expect(screen.getByText("75 %")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Night" }));
    expect(useSession.getState().theme).toBe("night");
    await waitFor(() => expect(document.documentElement.dataset.theme).toBe("night"));
  });
});
