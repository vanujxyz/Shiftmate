/**
 * Number formats used on every screen (DESIGN §3 Numerals): durations "1 h 05 m", ranges with an
 * en dash, 24-hour clock. The same figures in every script, so they read the same in en, hi, ta.
 */

/** 65 → "1 h 05 m", 55 → "55 m", 0 → "0 m". */
export function formatDuration(minutes: number): string {
  const total = Math.max(0, Math.round(minutes));
  const h = Math.floor(total / 60);
  const m = total % 60;
  if (h === 0) return `${m} m`;
  return `${h} h ${String(m).padStart(2, "0")} m`;
}

/** 55, 85 → "55 m – 1 h 25 m" (en dash with spaces). */
export function formatRange(low: number, high: number): string {
  return `${formatDuration(low)} – ${formatDuration(high)}`;
}

/** A Date or ISO string → "10:42" (24 h), in the given IANA time zone if any. */
export function formatClock(value: Date | string, timeZone?: string): string {
  const d = typeof value === "string" ? new Date(value) : value;
  return new Intl.DateTimeFormat("en-GB", {
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
    timeZone,
  }).format(d);
}

/** Whole metres, "2 m"; one decimal under 10 m where it matters, "4.5 m". */
export function formatMetres(m: number): string {
  return m < 10 && !Number.isInteger(m) ? `${m.toFixed(1)} m` : `${Math.round(m)} m`;
}
