import { act, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { App } from "../App";
import { useLive } from "../live/store";
import { useSession } from "../session";
import { envelope, shift, snapshot } from "../test-fixtures";
import { fakeEdge, renderAt } from "../test-render";

class QuietSocket {
  onopen: (() => void) | null = null;
  onmessage: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  close() {}
}

const CONFIG = { alerts: { p1_speech_repeat_s: 4, p2_tone_repeat_s: 20, reduced_p1_repeat_s: 5, p3_snooze_min: 10, paused_idle_seconds: 30 }, checklist: [], languages: ["en", "hi", "ta"] };
const base = { "/cab/config": CONFIG, "/operators/OP1001/shift": shift() };

function paused(language: "en" | "ta" = "en") {
  useSession.setState({ signedIn: { operatorId: "OP1001", machineId: "EXC001", name: "Ravi" }, language });
  act(() => useLive.getState().apply(envelope("snapshot", snapshot({ mode: "paused" }))));
}

beforeEach(() => {
  vi.stubGlobal("WebSocket", QuietSocket);
  useLive.getState().reset();
});
afterEach(() => vi.unstubAllGlobals());

describe("Ask Cat", () => {
  it("an online answer shows its sources", async () => {
    const calls = fakeEdge({
      ...base,
      "/assistant/ask": {
        answer: "A cup every 15 to 20 minutes in hot weather.",
        citations: [{ chunk_id: "heat_hydration#2", title: "Heat stress and water breaks", section: "Water breaks" }],
        answerable: true,
        mode: "online",
        language: "en",
        notice_key: null,
      },
    });
    paused();
    renderAt(<App />, "/ask");
    fireEvent.click(await screen.findByRole("button", { name: "How often should I drink water in hot weather?" }));
    expect(await screen.findByText("A cup every 15 to 20 minutes in hot weather.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Heat stress and water breaks/ })).toBeInTheDocument();
    expect(screen.queryByText(/Offline answer/)).not.toBeInTheDocument();
    await waitFor(() =>
      expect(calls.find((c) => c.url === "/assistant/ask")?.body).toEqual({ question: "How often should I drink water in hot weather?", language: "en" }),
    );
    expect(screen.getByText(/Sample manual content written for this prototype/)).toBeInTheDocument();
  });

  it("an offline answer is labelled, and says when it is only in English", async () => {
    fakeEdge({
      ...base,
      "/assistant/ask": {
        answer: "Keep the swing radius clear of people at all times.",
        citations: [{ chunk_id: "swing_radius#1", title: "Swing radius", section: "The danger zone" }],
        answerable: true,
        mode: "offline",
        language: "ta",
        notice_key: "ask.offline_english",
      },
    });
    paused("ta");
    renderAt(<App />, "/ask", "ta");
    fireEvent.change(await screen.findByLabelText("உங்கள் கேள்வி"), { target: { value: "சுழற்சி வட்டம்?" } });
    fireEvent.click(screen.getByRole("button", { name: "கேள்" }));
    expect(await screen.findByText("Keep the swing radius clear of people at all times.")).toBeInTheDocument();
    expect(screen.getByText("இணைப்பில்லா பதில்: கையேட்டின் பகுதி, எழுதியபடியே")).toBeInTheDocument();
    expect(screen.getByText("கையேட்டின் இந்தப் பகுதி ஆங்கிலத்தில் மட்டுமே உள்ளது.")).toBeInTheDocument();
  });

  it("when the manuals have no answer it says so, in the operator's language", async () => {
    fakeEdge({ ...base, "/assistant/ask": { answer: "", citations: [], answerable: false, mode: "online", language: "en", notice_key: "ask.refuse_bypass" } });
    paused();
    renderAt(<App />, "/ask");
    fireEvent.change(await screen.findByLabelText("Your question"), { target: { value: "How do I bypass the seatbelt switch?" } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));
    expect(await screen.findByText(/I can't help with switching off or getting round a safety system/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Sources/ })).not.toBeInTheDocument();
  });
});
