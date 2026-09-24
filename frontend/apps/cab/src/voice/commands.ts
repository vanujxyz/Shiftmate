/**
 * What a spoken command does (TRD §10.5; F-ASK-04; DESIGN PushToTalk "routes by intent"). The
 * gateway names the intent (keyword rules, then the model when online); this turns it into one
 * action. Every voice action also has a big button on its screen. There is no "call supervisor"
 * intent (owner decision D-009).
 */
import type { ShiftResponse } from "@shiftmate/contracts";
import { formatDuration } from "@shiftmate/ui";
import type { TFunction } from "i18next";

import type { LiveState } from "../live/store";
import { clockOf } from "../text";

export type VoiceAction =
  | { kind: "navigate"; to: string; state?: Record<string, string>; say?: string }
  | { kind: "say"; text: string }
  | { kind: "ack" }
  | { kind: "repeat" };

export function planAction(
  intent: string,
  utterance: string,
  t: TFunction,
  shift: ShiftResponse | undefined,
  live: LiveState,
): VoiceAction {
  switch (intent) {
    case "next_task": {
      const next = shift?.tasks.find((x) => (live.progress[x.task.task_id]?.status ?? x.task.status) === "scheduled");
      const text = next
        ? t("ui.voice.next_task", {
            task: t(`task.${next.task.task_type}`),
            zone: next.zone_decal,
            time: clockOf(next.task.scheduled_start) ?? "",
          })
        : t("ui.voice.no_next");
      return { kind: "navigate", to: "/", say: text };
    }
    case "time_left": {
      const e = live.estimate?.estimate;
      const active = shift?.tasks.find((x) => x.task.task_id === live.estimate?.task_id);
      const text =
        e && active
          ? t("ui.voice.time_left", { time: formatDuration(e.p50), task: t(`task.${active.task.task_type}`) })
          : t("ui.voice.no_estimate");
      return { kind: "say", text };
    }
    case "report_problem":
      return { kind: "navigate", to: "/report", state: { transcript: utterance } };
    case "start_break":
      return { kind: "say", text: t("ui.voice.break_start") };
    case "end_break":
      return { kind: "say", text: t("ui.voice.break_end") };
    case "repeat_last":
      return { kind: "repeat" };
    case "ack_alert":
      return { kind: "ack" };
    case "open_lessons":
      return { kind: "navigate", to: "/learn" };
    case "help":
      return { kind: "say", text: t("ui.voice.help") };
    default:
      return { kind: "navigate", to: "/ask", state: { question: utterance } };
  }
}

/** Checklist answers by voice (F-START-04): longer phrases win, so "all ok" beats "ok". */
export function checklistAnswer(
  utterance: string,
  words: Record<string, Record<string, string[]>> | undefined,
): "ok" | "problem" | "all_ok" | null {
  if (!words) return null;
  const text = ` ${utterance.toLowerCase().replace(/[^\p{L}\p{M}\p{N}\s]/gu, " ").replace(/\s+/g, " ").trim()} `;
  let best: { len: number; answer: "ok" | "problem" | "all_ok" } | null = null;
  for (const answer of ["all_ok", "problem", "ok"] as const) {
    for (const list of Object.values(words[answer] ?? {})) {
      for (const w of list) {
        const p = w.toLowerCase().trim();
        const found = /^[\x20-\x7e]+$/.test(p) ? text.includes(` ${p} `) : text.includes(p);
        if (found && (!best || p.length > best.len)) best = { len: p.length, answer };
      }
    }
  }
  return best?.answer ?? null;
}
