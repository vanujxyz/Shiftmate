import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../../App";
import { reduce, useLive } from "../../live/store";
import { useSession } from "../../session";
import { envelope, insights, shift, snapshot } from "../../test-fixtures";
import { fakeEdge, renderAt } from "../../test-render";
import { FEEDBACK_MS, heardStop, SCENE_MS } from "./Drill";
import { whyText } from "./words";

class QuietSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

const CONFIG = { alerts: { p1_speech_repeat_s: 4, p2_tone_repeat_s: 20, reduced_p1_repeat_s: 5, p3_snooze_min: 10, paused_idle_seconds: 30 }, checklist: [], languages: ["en", "hi", "ta"] };
const lt = (en: string) => ({ en, hi: `${en} (hi)`, ta: `${en} (ta)` });

const SUMMARIES = [
  { id: "L-SHUTDOWN", title: lt("Shut down before you step out"), format: "narrated_cards", duration_s: 90, triggers: ["UNATTENDED_RUNNING"], completed: false, art: "bucket-lowered" },
  { id: "L-SEATBELT", title: lt("Belt on before the machine moves"), format: "narrated_cards", duration_s: 90, triggers: [], completed: true, art: "belt-buckle" },
  { id: "D-HAZARD-DRILL-1", title: lt("Spot the hazard"), format: "drill", duration_s: 120, triggers: [], completed: false, art: "drill-intro" },
];

const SHUTDOWN = {
  id: "L-SHUTDOWN",
  title: lt("Shut down before you step out"),
  format: "narrated_cards",
  duration_s: 90,
  triggers: ["UNATTENDED_RUNNING"],
  cards: [
    { text: lt("Lower the bucket to the ground."), illustration: "bucket-lowered" },
    { text: lt("Lock the controls, then turn the engine off."), illustration: "controls-locked" },
    { text: lt("A bumped lever can move the machine."), illustration: "cab-exit-idle" },
  ],
  quiz: [
    {
      q: lt("You need to step out. What first?"),
      options: [lt("Leave the engine running"), lt("Lower, lock, switch off")],
      answer: 1,
      explain: lt("Then the machine cannot move."),
    },
  ],
};

const scene = (id: string, is_hazard: boolean) => ({ id, text: lt(`Scene ${id}`), is_hazard, scene: "swing-worker" });
const DRILL = {
  id: "D-HAZARD-DRILL-1",
  title: lt("Spot the hazard"),
  format: "drill",
  duration_s: 120,
  triggers: [],
  art: "drill-intro",
  hazards: [scene("h1", true), scene("h2", true), scene("s1", false), scene("s2", false), scene("h3", true)],
};

const PROGRESS = {
  operator_id: "OP1001",
  lessons_done: 1,
  lessons_total: 12,
  streak_days: 2,
  completed: [{ lesson_id: "L-SEATBELT", ts: "2026-09-24T10:00:00+05:30", score: 1, duration_s: 80 }],
  drills: [{ drill_id: "D-HAZARD-DRILL-1", ts: "2026-09-23T11:00:00+05:30", correct: 6, total: 7, mean_reaction_ms: 820 }],
  bookings: [{ booking_id: "b1", slot_id: "SLOT-2", dealer_centre: "Cat dealer training centre — Chennai", start: "2026-09-26T14:00:00+05:30", topic: "L-SEATBELT", status: "booked" }],
  habits: [{ lesson_id: "L-SEATBELT", codes: ["SEATBELT_MOVING"], previous_week: 3, this_week: 1 }],
};

const base = {
  "/cab/config": CONFIG,
  "/operators/OP1001/shift": shift(),
  "/lessons/recommended": [{ lesson: SUMMARIES[0], score: 2.5, because: ["UNATTENDED_RUNNING", "idle_unattended_min"] }],
  "/lessons?": SUMMARIES,
  "/lessons/L-SHUTDOWN": SHUTDOWN,
  "/lessons/D-HAZARD-DRILL-1": DRILL,
  "/training/progress": PROGRESS,
};

function paused() {
  useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language: "en" });
  act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "paused" }))));
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", QuietSocket);
  useLive.getState().reset();
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("Learn", () => {
  it("suggests lessons with the reason, lists every lesson with whether it is done", async () => {
    fakeEdge(base);
    paused();
    renderAt(<App />, "/learn");
    expect(await screen.findByText("Suggested because: engine left running")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: /Done.*Belt on before the machine moves/s })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Spot the hazard.*hazard drill/s })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Learn" })).toHaveAttribute("aria-current", "page");
    fireEvent.click(screen.getAllByRole("button", { name: /Shut down before you step out/ })[0]!);
    expect(await screen.findByText("Lower the bucket to the ground.")).toBeInTheDocument();
    // a lesson page keeps the Learn tab marked
    expect(screen.getByRole("button", { name: "Learn" })).toHaveAttribute("aria-current", "page");
  });

  it("cards, then the quiz, then the result is saved to progress", async () => {
    const calls = fakeEdge({ ...base, "/lessons/L-SHUTDOWN/complete": { ok: true } });
    paused();
    renderAt(<App />, "/learn/L-SHUTDOWN");
    expect(await screen.findByText("Lower the bucket to the ground.")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Card 1 of 3" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Lock the controls, then turn the engine off.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("You need to step out. What first?")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /Leave the engine running/ }));
    expect(screen.getByText("Not quite. The right answer is marked.")).toBeInTheDocument();
    expect(screen.getByText("Then the machine cannot move.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Finish lesson" }));
    expect(await screen.findByText("Saved to your progress.")).toBeInTheDocument();
    expect(screen.getByText("0 of 1 answers right")).toBeInTheDocument();
    const body = calls.find((c) => c.url === "/lessons/L-SHUTDOWN/complete")?.body as Record<string, unknown>;
    expect(body).toMatchObject({ operator_id: "OP1001", score: 0, language: "en" });
  });

  it("the hazard drill scores decisions and stop times, and saves them", async () => {
    const calls = fakeEdge({ ...base, "/drills/results": { ok: true } });
    paused();
    renderAt(<App />, "/learn/D-HAZARD-DRILL-1");
    fireEvent.click(await screen.findByRole("button", { name: "Start drill" }));
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout"] });
    const stop = () => fireEvent.click(screen.getByRole("button", { name: "STOP" }));
    const wait = (ms: number) => act(() => vi.advanceTimersByTime(ms));
    // h1: stop (right) · h2: miss · s1: stop (wrong) · s2: wait (right) · h3: stop (right)
    expect(screen.getByText("Scene 1 of 5")).toBeInTheDocument();
    stop();
    expect(screen.getByText(/Right: stop\./)).toBeInTheDocument();
    wait(FEEDBACK_MS);
    wait(SCENE_MS);
    expect(screen.getByText("Missed: this was a danger.")).toBeInTheDocument();
    wait(FEEDBACK_MS);
    stop();
    expect(screen.getByText("No danger here: this one was safe.")).toBeInTheDocument();
    wait(FEEDBACK_MS);
    wait(SCENE_MS);
    expect(screen.getByText("Right: this one was safe.")).toBeInTheDocument();
    wait(FEEDBACK_MS);
    stop();
    wait(FEEDBACK_MS);
    vi.useRealTimers();
    expect(await screen.findByText("3 of 5 right decisions")).toBeInTheDocument();
    expect(await screen.findByText("Saved to your progress.")).toBeInTheDocument();
    const body = calls.find((c) => c.url === "/drills/results")?.body as { hazards: { hazard_id: string; correct: boolean; reaction_ms: number | null }[] };
    expect(body.hazards.map((h) => [h.hazard_id, h.correct])).toEqual([
      ["h1", true],
      ["h2", false],
      ["s1", false],
      ["s2", true],
      ["h3", true],
    ]);
    expect(body.hazards[1]!.reaction_ms).toBeNull();
    expect(body.hazards[0]!.reaction_ms).toBeGreaterThanOrEqual(0);
  });

  it("booking: pick a session, book it; your own sessions say Booked", async () => {
    let booked: unknown = null;
    const slot = (id: string, start: string, seats: number) => ({ slot_id: id, dealer_centre: "Cat dealer training centre — Chennai", site_id: "CHN-HWY-01", start, topic: "L-SHUTDOWN", seats_left: seats });
    fakeEdge({
      ...base,
      "/training/slots": [slot("SLOT-1", "2026-09-25T09:00:00+05:30", 3), slot("SLOT-2", "2026-09-26T14:00:00+05:30", 5), slot("SLOT-3", "2026-09-27T09:00:00+05:30", 0)],
      "/training/bookings": (_u: string, init?: RequestInit) => {
        booked = JSON.parse(String(init?.body));
        return { ok: true, booking_id: "b2" };
      },
    });
    paused();
    renderAt(<App />, "/learn/book");
    const first = await screen.findByRole("button", { name: /09:00.*3 seats left/s });
    await waitFor(() => expect(screen.getByRole("button", { name: /14:00.*Booked/s })).toBeDisabled());
    expect(screen.getByRole("button", { name: /Full/ })).toBeDisabled();
    fireEvent.click(first);
    fireEvent.click(screen.getByRole("button", { name: "Book this session" }));
    expect(await screen.findByText(/Booked: .*09:00, Shut down before you step out\./)).toBeInTheDocument();
    expect(booked).toEqual({ operator_id: "OP1001", slot_id: "SLOT-1" });
  });

  it("progress shows facts: lessons, days in a row, drills, habits and bookings", async () => {
    fakeEdge(base);
    paused();
    renderAt(<App />, "/learn/progress");
    expect(await screen.findByText("1 of 12")).toBeInTheDocument();
    expect(screen.getByText("Days in a row").nextSibling).toHaveTextContent("2");
    expect(screen.getByText("Seen 3 times the week before, 1 this week")).toBeInTheDocument();
    expect(screen.getByText(/6 of 7 right decisions · 0\.8 s/)).toBeInTheDocument();
    expect(screen.getByText(/Belt on before the machine moves · Cat dealer training centre/)).toBeInTheDocument();
  });

  it("a lesson offered for this pause shows with Start and Not now; work ends it", async () => {
    fakeEdge(base);
    paused();
    act(() => useLive.getState().apply(envelope("lesson_offer", { lesson_id: "L-SHUTDOWN", because: ["UNATTENDED_RUNNING"], reason: "ENGINE_OFF" })));
    renderAt(<App />, "/");
    expect(await screen.findByText("A short lesson for this pause")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Start lesson" }));
    expect(await screen.findByText("Lower the bucket to the ground.")).toBeInTheDocument();
    expect(useLive.getState().lessonOffer).toBeNull();

    const s = reduce(useLive.getState(), envelope("lesson_offer", { lesson_id: "L-SHUTDOWN", because: [], reason: "ENGINE_OFF" }), 0);
    expect(reduce(s, envelope("mode", { mode: "working" }), 0).lessonOffer).toBeNull();
  });

  it("an idea in My Day opens its lesson", async () => {
    fakeEdge({ ...base, "/insights/OP1001": insights(), "/lessons/L-IDLE-FUEL": { ...SHUTDOWN, id: "L-IDLE-FUEL" } });
    paused();
    renderAt(<App />, "/insights");
    fireEvent.click(await screen.findByRole("button", { name: "Open the lesson" }));
    expect(await screen.findByText("Lower the bucket to the ground.")).toBeInTheDocument();
  });

  it("words: reasons said once, and stop heard in any language", () => {
    const t = ((k: string, v?: Record<string, string>) => (v ? `${k}:${v.reason}` : k)) as never;
    expect(whyText(t, ["UNATTENDED_RUNNING", "idle_unattended_min", "HEAT"])).toBe("ui.learn.why:ui.learn.why_engine_left, ui.learn.why_heat");
    expect(whyText(t, ["WHATEVER"])).toBeNull();
    expect(heardStop("STOP now")).toBe(true);
    expect(heardStop("रुको")).toBe(true);
    expect(heardStop("நிறுத்து")).toBe(true);
    expect(heardStop("go on")).toBe(false);
  });
});
