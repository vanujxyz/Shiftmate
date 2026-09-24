import { createI18n } from "@shiftmate/i18n";
import { act, fireEvent, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { useLive } from "../live/store";
import { useSession } from "../session";
import { envelope, shift, snapshot } from "../test-fixtures";
import { fakeEdge, renderAt } from "../test-render";
import { checklistAnswer, planAction } from "./commands";
import { listen } from "./recognizer";

class QuietSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

/** A stand-in for the browser's speech recognizer: the test says what was heard. */
class FakeSpeech {
  static last: FakeSpeech | null = null;
  lang = "";
  interimResults = false;
  continuous = false;
  maxAlternatives = 1;
  onresult: ((e: unknown) => void) | null = null;
  onerror: ((e: { error: string }) => void) | null = null;
  onend: (() => void) | null = null;
  private results: { isFinal: boolean; 0: { transcript: string } }[] = [];
  constructor() {
    FakeSpeech.last = this;
  }
  start() {}
  stop() {
    this.onend?.();
  }
  abort() {}
  hear(text: string, isFinal: boolean) {
    const index = this.results.length > 0 && !this.results[this.results.length - 1]!.isFinal ? this.results.length - 1 : this.results.length;
    this.results[index] = { isFinal, 0: { transcript: text } };
    this.onresult?.({ resultIndex: 0, results: this.results });
  }
}

const WORDS = {
  ok: { en: ["ok", "okay", "fine"], hi: ["ठीक"], ta: ["சரி"] },
  problem: { en: ["problem", "not ok"], hi: ["समस्या", "ठीक नहीं"], ta: ["பிரச்சினை"] },
  all_ok: { en: ["all ok", "all fine"], hi: ["सब ठीक"], ta: ["எல்லாம் சரி"] },
};

const CONFIG = {
  alerts: { p1_speech_repeat_s: 4, p2_tone_repeat_s: 20, reduced_p1_repeat_s: 5, p3_snooze_min: 10, paused_idle_seconds: 30 },
  checklist: [],
  checklist_voice: WORDS,
  languages: ["en", "hi", "ta"],
};

const t = createI18n("en").t;

function paused() {
  useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language: "en" });
  act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "paused" }))));
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", QuietSocket);
  useLive.getState().reset();
  FakeSpeech.last = null;
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("planAction", () => {
  it("next task names the first scheduled task", () => {
    const a = planAction("next_task", "next task", t, shift(), useLive.getState());
    expect(a).toEqual({ kind: "navigate", to: "/", say: "Next: Trenching at DIG-A, starting 09:40." });
  });

  it("time left reads the live estimate, or says there is none", () => {
    expect(planAction("time_left", "how long", t, shift(), useLive.getState())).toEqual({
      kind: "say",
      text: "No estimate yet. It comes once the task has started.",
    });
    const live = { ...useLive.getState(), estimate: { task_id: "T1", estimate: { p10: 55, p50: 65, p90: 85, reasons: [] }, likely_finish: null } };
    expect(planAction("time_left", "how long", t, shift(), live)).toEqual({ kind: "say", text: "About 1 h 05 m left on Truck loading." });
  });

  it("reports, questions, repeat and acknowledge", () => {
    const live = useLive.getState();
    expect(planAction("report_problem", "hydraulic leak", t, shift(), live)).toEqual({ kind: "navigate", to: "/report", state: { transcript: "hydraulic leak" } });
    expect(planAction("question", "what is the swing radius", t, shift(), live)).toEqual({ kind: "navigate", to: "/ask", state: { question: "what is the swing radius" } });
    expect(planAction("repeat_last", "repeat", t, shift(), live)).toEqual({ kind: "repeat" });
    expect(planAction("ack_alert", "ok", t, shift(), live)).toEqual({ kind: "ack" });
  });
});

describe("checklistAnswer", () => {
  it("longer phrases win, in every language", () => {
    expect(checklistAnswer("OK", WORDS)).toBe("ok");
    expect(checklistAnswer("it is not ok", WORDS)).toBe("problem");
    expect(checklistAnswer("all ok", WORDS)).toBe("all_ok");
    expect(checklistAnswer("எல்லாம் சரி", WORDS)).toBe("all_ok");
    expect(checklistAnswer("ठीक नहीं है", WORDS)).toBe("problem");
    expect(checklistAnswer("booked", WORDS)).toBeNull();
    expect(checklistAnswer("ok", undefined)).toBeNull();
  });
});

describe("recognizer", () => {
  it("listens in the operator's language and passes partial, then final, words", () => {
    const heard: unknown[] = [];
    const done = vi.fn();
    const l = listen(FakeSpeech, "ta", (h) => heard.push(h), done, vi.fn());
    const r = FakeSpeech.last!;
    expect(r.lang).toBe("ta-IN");
    r.hear("அடுத்த", false);
    r.hear("அடுத்த வேலை", true);
    expect(heard).toEqual([
      { final: "", pending: "அடுத்த" },
      { final: "அடுத்த வேலை", pending: "" },
    ]);
    l.stop();
    expect(done).toHaveBeenCalledWith("அடுத்த வேலை");
  });
});

describe("push-to-talk", () => {
  it("hold, ask a question, release: Ask Cat answers it", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeSpeech);
    fakeEdge({
      "/cab/config": CONFIG,
      "/operators/OP1001/shift": shift(),
      "/assistant/intent": { intent: "question", source: "rules" },
      "/assistant/ask": { answer: "About five minutes.", citations: [], answerable: true, mode: "online", language: "en", notice_key: null },
    });
    paused();
    renderAt(<App />, "/");
    const disc = await screen.findByRole("button", { name: "Hold to talk" });
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000);
    fireEvent.pointerDown(disc);
    act(() => FakeSpeech.last!.hear("how long to warm up", true));
    expect(screen.getByText("how long to warm up")).toBeInTheDocument();
    now.mockReturnValue(2_000);
    act(() => fireEvent.pointerUp(disc));
    expect(await screen.findByText("About five minutes.")).toBeInTheDocument();
  });

  it("a spoken report opens a draft to check", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeSpeech);
    const parsed = {
      draft: { type: "near_miss", severity: "medium", summary_en: "worker behind bucket", summary_local: "worker behind bucket", people_involved: true, injury: false, parser: "offline" },
      context: { ts: "2026-09-24T12:10:00+05:30", machine_id: "EXC001", operator_id: "OP1001", site_id: "CHN-HWY-01", zone_id: "DIG-A", task_id: "T2", weather: {}, risk_score: 40, language: "en" },
      mode: "offline",
    };
    fakeEdge({
      "/cab/config": CONFIG,
      "/operators/OP1001/shift": shift(),
      "/assistant/intent": { intent: "report_problem", source: "rules" },
      "/reports/parse": parsed,
      "/reports?operator_id": [],
    });
    paused();
    renderAt(<App />, "/");
    const disc = await screen.findByRole("button", { name: "Hold to talk" });
    const now = vi.spyOn(Date, "now").mockReturnValue(1_000);
    fireEvent.pointerDown(disc);
    act(() => FakeSpeech.last!.hear("report worker behind bucket", true));
    now.mockReturnValue(2_000);
    act(() => fireEvent.pointerUp(disc));
    expect(await screen.findByText("DIG-A · 12:10")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send report" })).toBeInTheDocument();
  });

  it("a quick tap keeps listening until tapped again", async () => {
    vi.stubGlobal("webkitSpeechRecognition", FakeSpeech);
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift() });
    paused();
    renderAt(<App />, "/");
    const disc = await screen.findByRole("button", { name: "Hold to talk" });
    vi.spyOn(Date, "now").mockReturnValue(1_000);
    fireEvent.pointerDown(disc);
    fireEvent.pointerUp(disc);
    expect(await screen.findByText("Tap again to stop")).toBeInTheDocument();
  });

  it("without speech support it says to use the buttons", async () => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift() });
    paused();
    renderAt(<App />, "/");
    const disc = await screen.findByRole("button", { name: "Hold to talk" });
    fireEvent.pointerDown(disc);
    expect(await screen.findByText("Voice is not available in this browser. Use the buttons.")).toBeInTheDocument();
  });
});
