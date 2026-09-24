/**
 * Push-to-talk (DESIGN §10 PushToTalk, TranscriptSheet; TRD §11.2 Speech; F-ASK-01, 04,
 * F-REP-01). Hold to talk and release to finish, or tap once for a 6 s window ("Tap again to
 * stop") for gloves that cannot hold. While listening, the transcript sheet shows the words as
 * they are heard. The gateway names the intent and `planAction` decides what happens: a
 * question opens Ask Cat and reads the answer aloud; "report…" opens a report draft from what was
 * said; "next task", "how long left", "repeat", "acknowledge", breaks and help are answered in
 * speech. Nothing is sent before the operator checks it. The disc hides behind a P1 takeover.
 */
import type { ShiftResponse } from "@shiftmate/contracts";
import { PushToTalk, type PttState, TranscriptSheet } from "@shiftmate/ui";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";

import { api } from "../api";
import { playTone, repeatLast, speak } from "../live/audio";
import { useLive } from "../live/store";
import { useSession } from "../session";
import { planAction } from "./commands";
import { type Heard, type Listener, listen, speechSupport } from "./recognizer";

export const HOLD_MS = 400; // a press longer than this is hold-to-talk; shorter is a tap
export const TAP_WINDOW_MS = 6000;
const ERROR_SHOWN_MS = 4000;

type State = "idle" | "listening" | "thinking" | "error";

export function VoiceControl({ hidden = false }: { hidden?: boolean }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const language = useSession((s) => s.language);
  const operatorId = useSession((s) => s.signedIn?.operatorId ?? null);
  const [state, setState] = useState<State>("idle");
  const [heard, setHeard] = useState<Heard>({ final: "", pending: "" });
  const [error, setError] = useState<string | null>(null);
  const [tapMode, setTapMode] = useState(false);
  const listener = useRef<Listener | null>(null);
  const pressedAt = useRef(0);
  const timers = useRef<number[]>([]);

  const clearTimers = () => {
    timers.current.forEach((id) => window.clearTimeout(id));
    timers.current = [];
  };
  useEffect(() => () => {
    clearTimers();
    listener.current?.abort();
  }, []);

  const say = (text: string) => speak(text, i18n.language, language === "en" ? text : "");

  const fail = (key: string) => {
    playTone("error_tick");
    setError(t(key));
    setState("error");
    timers.current.push(window.setTimeout(() => setState((s) => (s === "error" ? "idle" : s)), ERROR_SHOWN_MS));
  };

  const route = async (text: string) => {
    setState("thinking");
    let intent = "question";
    try {
      intent = (await api.intent(text, language)).intent;
    } catch {
      /* the gateway is unreachable: treat it as a question, Ask Cat will say so */
    }
    const shift = queryClient.getQueryData<ShiftResponse>(["shift", operatorId]);
    const action = planAction(intent, text, t, shift, useLive.getState());
    setState("idle");
    switch (action.kind) {
      case "navigate":
        void navigate(action.to, { state: action.state });
        if (action.say) say(action.say);
        break;
      case "say":
        say(action.text);
        break;
      case "repeat":
        if (!repeatLast()) say(t("ui.voice.nothing_to_repeat"));
        break;
      case "ack": {
        const current = useLive.getState().alerts.current;
        if (current) {
          void api.ack(current.alert_id, "ack").catch(() => undefined);
          say(t("ui.voice.acked"));
        } else say(t("ui.voice.no_alert"));
        break;
      }
    }
  };

  const stop = () => {
    clearTimers();
    listener.current?.stop();
  };

  const start = () => {
    const Ctor = speechSupport();
    if (!Ctor) return fail("ui.voice.not_supported");
    clearTimers();
    setError(null);
    setHeard({ final: "", pending: "" });
    setTapMode(false);
    playTone("listen_tick");
    setState("listening");
    pressedAt.current = Date.now();
    listener.current = listen(
      Ctor,
      language,
      setHeard,
      (text) => {
        listener.current = null;
        if (text) void route(text);
        else fail("ui.ptt.error");
      },
      (code) => {
        listener.current = null;
        fail(code === "not-allowed" || code === "service-not-allowed" ? "ui.voice.no_mic" : "ui.ptt.error");
      },
    );
  };

  const onPress = () => {
    if (state === "listening" && tapMode) return stop(); // "tap again to stop"
    if (state === "listening" || state === "thinking") return;
    start();
  };

  const onRelease = () => {
    if (state !== "listening" && listener.current == null) return;
    if (Date.now() - pressedAt.current >= HOLD_MS) return stop(); // hold-to-talk: release ends it
    setTapMode(true);
    timers.current.push(window.setTimeout(stop, TAP_WINDOW_MS));
  };

  if (hidden) return null;
  const ptt: PttState = state === "listening" ? "listening" : state === "thinking" ? "thinking" : state === "error" ? "error" : "idle";
  const label = t(state === "listening" ? "ui.ptt.listening" : state === "thinking" ? "ui.ptt.thinking" : "ui.ptt.idle");
  return (
    <>
      {state !== "idle" && (
        <div className="fixed inset-x-0 bottom-0 z-(--sm-layer-sheet)">
          <TranscriptSheet
            inline
            stateWord={label}
            finalText={heard.final}
            pendingText={heard.pending}
            level={state === "listening" ? (heard.final || heard.pending ? 0.7 : 0.25) : 0}
            helper={state === "listening" && tapMode ? t("ui.ptt.tap_again") : t("ui.ptt.helper")}
            error={state === "error" ? (error ?? undefined) : undefined}
          />
        </div>
      )}
      <div className="fixed right-10 bottom-5.5 z-(--sm-layer-sheet)">
        <PushToTalk state={ptt} label={label} onPress={onPress} onRelease={onRelease} />
      </div>
    </>
  );
}
