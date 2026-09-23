/**
 * My Shift pieces (DESIGN §9 Estimate range bar, Risk contributions; §10 TaskRow, RangeBar,
 * ReasonChip, ConditionsSummary). Every estimate is a range with a most-likely value; low
 * confidence is drawn (a dashed band and a note), never hidden; unknown says so in words.
 */
import type { ReactNode } from "react";

import { formatDuration, formatRange } from "./format";
import { SensorGlyph } from "./glyphs";
import { type RiskBand, StackLight } from "./rail";

// --- RangeBar ------------------------------------------------------------------------------------

export function RangeBar({
  likely,
  low,
  high,
  scaleMax = 180,
  elapsed,
  confidence = "normal",
  lowNote,
  unknownText,
  label,
  width = 280,
}: {
  likely?: number | null;
  low?: number | null;
  high?: number | null;
  /** Shared scale for every row on a screen, in minutes (0–3 h), so bars compare. */
  scaleMax?: number;
  elapsed?: number | null;
  confidence?: "normal" | "low" | "unknown";
  lowNote?: string;
  unknownText?: string;
  /** "Likely 1 hour 5 minutes, between 55 minutes and 1 hour 25 minutes". */
  label: string;
  width?: number;
}) {
  if (confidence === "unknown" || likely == null || low == null || high == null) {
    return <p className="sm-t-small text-ink-2" style={{ width }}>{unknownText}</p>;
  }
  const pct = (m: number) => `${Math.min(100, Math.max(0, (m / scaleMax) * 100))}%`;
  const dashed = confidence === "low";
  return (
    <div role="img" aria-label={label} className="flex flex-col gap-2" style={{ width }}>
      <span className="sm-num sm-t-big">~{formatDuration(likely)}</span>
      <div className="relative h-6 border-2 border-mark bg-surface-sunk">
        {elapsed != null && elapsed > 0 && (
          <div className="absolute inset-y-0 left-0 bg-mark" style={{ width: pct(elapsed) }} />
        )}
        <div
          className={`absolute inset-y-0 ${dashed ? "border-y-4 border-dashed border-ink" : "bg-ink"}`}
          style={{ left: pct(low), width: `calc(${pct(high)} - ${pct(low)})` }}
        />
        <div
          className="absolute -inset-y-2.5 w-1.5 bg-ink"
          style={{ left: `calc(${pct(likely)} - 3px)`, boxShadow: "0 0 0 2px var(--sm-color-surface)" }}
        />
      </div>
      <span className="sm-num sm-t-small text-ink-2">{formatRange(low, high)}</span>
      {dashed && lowNote && (
        <span className="sm-t-small flex items-center gap-2 text-ink-2">
          <SensorGlyph tier="basic" size={28} />
          {lowNote}
        </span>
      )}
    </div>
  );
}

// --- ReasonChip ------------------------------------------------------------------------------------

export function ReasonChip({
  glyph,
  text,
  effect,
  adds = false,
}: {
  glyph?: ReactNode;
  text: string;
  effect?: string;
  adds?: boolean;
}) {
  return (
    <span
      className={`sm-dense inline-flex min-h-12 items-center gap-2 rounded-chip border-2 border-ink px-3 py-1 text-cab-meta font-semibold ${adds ? "bg-surface-sunk" : "bg-surface"}`}
    >
      {glyph && <span aria-hidden className="inline-flex">{glyph}</span>}
      <span>{text}</span>
      {effect && <span className="sm-num font-bold">{effect}</span>}
    </span>
  );
}

// --- Load blocks: progress as blocks, not a ring ------------------------------------------------------

export function LoadBlocks({ done, total, label }: { done: number; total: number; label: string }) {
  return (
    <div role="img" aria-label={label} className="flex flex-wrap gap-1.5">
      {Array.from({ length: total }, (_, i) => (
        <span key={i} className={`h-8 w-5 border-2 border-ink ${i < done ? "bg-ink" : "bg-surface"}`} />
      ))}
    </div>
  );
}

// --- TaskRow -----------------------------------------------------------------------------------------

export function TaskRow({
  number,
  title,
  where,
  zone,
  nowLabel,
  status,
  reasons,
  range,
  actual,
}: {
  number: number;
  title: string;
  where: string;
  zone?: string;
  nowLabel?: string;
  status: "active" | "next" | "done";
  reasons?: ReactNode;
  range?: ReactNode;
  /** Done rows show the actual time instead of the range. */
  actual?: string;
}) {
  const active = status === "active";
  return (
    <div
      className={`flex min-h-(--sm-size-target) items-start gap-5 bg-surface p-4 ${active ? "sm-heavy" : "sm-rule-b"}`}
    >
      <span
        className={`sm-num flex h-14 w-14 shrink-0 items-center justify-center rounded-chip text-cab-label ${active ? "bg-action text-on-action" : status === "done" ? "bg-surface-sunk text-ink-2" : "border-2 border-ink"}`}
      >
        {number}
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-2">
        <p className={`sm-t-row flex flex-wrap items-center gap-3 ${status === "done" ? "text-ink-2" : ""}`}>
          {title}
          {active && nowLabel && (
            <span className="rounded-chip bg-action px-2 text-cab-meta text-on-action">{nowLabel}</span>
          )}
        </p>
        <p className="sm-dense text-cab-meta text-ink-2">
          {where}
          {zone && (
            <>
              {" · "}
              <span className="sm-decal font-bold text-ink">{zone}</span>
            </>
          )}
        </p>
        {reasons && <div className="flex flex-wrap gap-2">{reasons}</div>}
      </div>
      <div className="shrink-0">
        {status === "done" ? <span className="sm-num sm-t-big text-ink-2">{actual}</span> : range}
      </div>
    </div>
  );
}

// --- ConditionsSummary --------------------------------------------------------------------------------

export function ConditionsSummary({
  heading,
  finish,
  note,
  rows,
  risk,
}: {
  heading: string;
  /** "15:10 – 15:55": always a range, never a single time. */
  finish: string;
  note?: string;
  rows: { glyph: ReactNode; label: string; value: string }[];
  risk?: { band: RiskBand; sentence: string; label: string };
}) {
  return (
    <section className="sm-rule flex flex-col gap-4 bg-surface p-5">
      <h2 className="text-cab-label">{heading}</h2>
      <p className="sm-num text-cab-title">{finish}</p>
      {note && <p className="text-cab-meta text-ink-2">{note}</p>}
      <ul className="flex flex-col gap-3">
        {rows.map((r) => (
          <li key={r.label} className="flex flex-wrap items-center gap-x-3 text-cab-label">
            <span aria-hidden>{r.glyph}</span>
            {/* content-sized basis: a long value wraps to its own line instead of overlapping */}
            <span className="min-w-0 flex-[1_1_auto]">{r.label}</span>
            <span className="sm-num ml-auto whitespace-nowrap font-bold">{r.value}</span>
          </li>
        ))}
      </ul>
      {risk && (
        <p className="flex items-center gap-3 text-cab-meta">
          <StackLight band={risk.band} label={risk.label} size="surface" />
          {risk.sentence}
        </p>
      )}
    </section>
  );
}

// --- Risk contributions: ink bars; the band is the only hazard signal -------------------------------------

export function RiskContributions({
  rows,
}: {
  rows: { glyph?: ReactNode; factor: string; share: number }[];
}) {
  return (
    <ul className="flex flex-col gap-4">
      {[...rows]
        .sort((a, b) => b.share - a.share)
        .map((r) => (
          <li key={r.factor} className="flex flex-col gap-1">
            <span className="flex items-center gap-3 text-cab-label">
              {r.glyph && <span aria-hidden>{r.glyph}</span>}
              <span className="flex-1">{r.factor}</span>
              <span className="sm-num font-bold">{Math.round(r.share * 100)} %</span>
            </span>
            <span className="h-5.5 w-full bg-surface-sunk">
              <span className="block h-full bg-ink" style={{ width: `${Math.round(r.share * 100)}%` }} />
            </span>
          </li>
        ))}
    </ul>
  );
}
