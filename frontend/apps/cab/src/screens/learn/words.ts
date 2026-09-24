/**
 * Shared words for the training hub: a lesson's text in the operator's language (English when a
 * translation is missing), why a lesson is suggested, and seconds as "0.8 s".
 */
import type { LocalizedText } from "@shiftmate/contracts";
import type { TFunction } from "i18next";

export function loc(text: LocalizedText | Record<string, string> | undefined, language: string): string {
  if (!text) return "";
  return (text as Record<string, string>)[language] || text.en || "";
}

/** Recommender trigger codes (lessons.yaml `triggers`) grouped into one plain reason each. */
const WHY: Record<string, string> = {
  UNATTENDED_RUNNING: "engine_left",
  idle_unattended_min: "engine_left",
  HABIT: "long_idle",
  idle_habit_min: "long_idle",
  idle_ratio: "long_idle",
  fuel_per_load_cycle_l: "long_idle",
  SEATBELT_MOVING: "belt",
  seatbelt_unfastened_working_s: "belt",
  PROXIMITY_CAUTION: "people_close",
  PROXIMITY_DANGER: "people_close",
  PROXIMITY_CRITICAL: "people_close",
  SPEED_NEAR_PERSON: "people_close",
  proximity_close_count: "people_close",
  HEAT: "heat",
  HEAT_NO_BREAK: "heat",
  WET_GROUND: "wet",
  RAIN: "wet",
  NIGHT: "night",
  WAITING_FOR_TRUCK: "trucks",
  load_cycles_per_working_h: "trucks",
  FATIGUE_WARN: "tired",
  FATIGUE_LIMIT: "tired",
};

/** "Suggested because: …" with each reason said once, in the order the edge gave them. */
export function whyText(t: TFunction, because: string[]): string | null {
  const keys = [...new Set(because.map((c) => WHY[c]).filter((k): k is string => Boolean(k)))];
  if (keys.length === 0) return null;
  return t("ui.learn.why", { reason: keys.map((k) => t(`ui.learn.why_${k}`)).join(", ") });
}

export function seconds(ms: number): string {
  return `${(Math.round(ms / 100) / 10).toFixed(1)} s`;
}

export function formatKey(format: string): string {
  return format === "quiz" ? "ui.learn.fmt_quiz" : format === "drill" ? "ui.learn.fmt_drill" : "ui.learn.fmt_cards";
}
