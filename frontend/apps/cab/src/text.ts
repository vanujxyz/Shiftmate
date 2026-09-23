/**
 * Turning edge data into the operator's words. Pure functions over `t`, so the same data reads
 * the same in en, hi and ta and every rule is testable without rendering.
 */
import type { AlertView, QuantityUnit, RiskBand } from "@shiftmate/contracts";
import { formatMetres } from "@shiftmate/ui";
import type { TFunction } from "i18next";

/** Where a person is, from a bearing clockwise from the machine's forward direction. */
export function sideOf(bearing: number | null | undefined): "front" | "right" | "rear" | "left" {
  if (bearing == null) return "front";
  const b = ((bearing % 360) + 360) % 360;
  if (b < 45 || b >= 315) return "front";
  if (b < 135) return "right";
  if (b < 225) return "rear";
  return "left";
}

/** 18 → "18", 42.5 → "42.5": whole numbers stay whole, others keep one decimal. */
export function formatQty(n: number): string {
  return Number.isInteger(n) ? String(n) : n.toFixed(1);
}

export function quantity(t: TFunction, unit: QuantityUnit | string, n: number): string {
  return t(`unit.${unit}`, { count: formatQty(n) });
}

/** "07:15" + 95 min → "08:50" (wraps past midnight). */
export function addClock(hhmm: string, minutes: number): string {
  const [h = 0, m = 0] = hhmm.split(":").map(Number);
  const total = (((h * 60 + m + Math.round(minutes)) % 1440) + 1440) % 1440;
  return `${String(Math.floor(total / 60)).padStart(2, "0")}:${String(total % 60).padStart(2, "0")}`;
}

/** The site-local wall clock of an edge timestamp ("2026-09-24T10:42:05+05:30" → "10:42"). */
export function clockOf(ts: string | null | undefined): string | null {
  return ts && ts.length >= 16 ? ts.slice(11, 16) : null;
}

export const RISK_WORD: Record<RiskBand, string> = {
  green: "ui.rail.risk_low",
  amber: "ui.rail.risk_raised",
  red: "ui.rail.risk_high",
};

/** A risk factor in running text: "heat" in English, unchanged in scripts without case. */
export function factorWord(t: TFunction, component: string): string {
  return t(`ui.risk.${component}`).toLocaleLowerCase();
}

export type AlertWords = { title: string; action: string; speak: string; where?: string };

/** An alert's words; proximity alerts add where the person is ("behind you · 2 m"). */
export function alertWords(t: TFunction, a: AlertView): AlertWords {
  const ctx = a.context ?? {};
  const distance = typeof ctx.distance_m === "number" ? ctx.distance_m : null;
  const bearing = typeof ctx.bearing_deg === "number" ? ctx.bearing_deg : null;
  return {
    title: t(`${a.message_key}.title`),
    action: t(`${a.message_key}.action`),
    speak: t(`${a.message_key}.speak`),
    where:
      distance != null
        ? t("ui.p1.where", { side: t(`ui.side.${sideOf(bearing)}`), distance: formatMetres(distance) })
        : undefined,
  };
}

/** Alerts newest first by when they were raised (the edge files them in the order they ended). */
export function newestFirst(alerts: AlertView[]): AlertView[] {
  return [...alerts].sort((a, b) => b.raised_at.localeCompare(a.raised_at));
}
