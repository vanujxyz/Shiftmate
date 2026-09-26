import { act, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { reduce, useLive } from "../live/store";
import { useSession } from "../session";
import { envelope, insights, shift, snapshot } from "../test-fixtures";
import { fakeEdge, renderAt } from "../test-render";

class QuietSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

const CONFIG = { alerts: { p1_speech_repeat_s: 4, p2_tone_repeat_s: 20, reduced_p1_repeat_s: 5, p3_snooze_min: 10, paused_idle_seconds: 30 }, checklist: [], languages: ["en", "hi", "ta"] };
const CAPTION = { en: "A worker walks into the swing zone", hi: "एक मज़दूर घुमाव के दायरे में आता है", ta: "ஒரு தொழிலாளி சுழலும் பகுதிக்குள் நுழைகிறார்" };

beforeEach(() => {
  vi.stubGlobal("WebSocket", QuietSocket);
  useLive.getState().reset();
});
afterEach(() => vi.unstubAllGlobals());

describe("demo polish in the cab", () => {
  it("a story caption shows in the operator's language when the console turns captions on", async () => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift() });
    useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language: "ta" });
    act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "paused" }))));
    renderAt(<App />, "/", "ta");
    act(() => useLive.getState().apply(envelope("scenario_caption", { beat: "worker_near", caption: CAPTION })));
    expect(await screen.findByTestId("demo-caption")).toHaveTextContent(CAPTION.ta);
    // captions turned off (a snapshot says so): the caption goes
    const s = reduce(useLive.getState(), envelope("snapshot", { ...snapshot({ mode: "paused" }), captions: false }), 0);
    expect(s.caption).toBeNull();
  });

  it("the end of the shift opens My Day", async () => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/insights/OP1001": insights() });
    useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language: "en" });
    act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "paused" }))));
    renderAt(<App />, "/");
    act(() => useLive.getState().apply(envelope("demo", { event: "end_shift", operator_id: "OP1001" })));
    expect(await screen.findByRole("button", { name: "My day" })).toHaveAttribute("aria-current", "page");
  });

  it("the end of the shift shows My Day even if the machine was still working", async () => {
    fakeEdge({ "/cab/config": CONFIG, "/operators/OP1001/shift": shift(), "/insights/OP1001": insights() });
    useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language: "en" });
    act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "working" }))));
    renderAt(<App />, "/");
    act(() => useLive.getState().apply(envelope("demo", { event: "end_shift", operator_id: "OP1001" })));
    expect(await screen.findByRole("heading", { name: "My day" })).toBeVisible();
  });
});
