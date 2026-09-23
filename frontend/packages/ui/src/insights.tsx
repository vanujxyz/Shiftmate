/**
 * My Day pieces (DESIGN §9 Time-split bar, Sparkline; §10 TimeSplit, IdleSegmentRow, CoachingNote).
 * Idle categories are told apart by lightness and pattern (never a safety hue, never the
 * diagonal hatch); every chart carries a sentence and a table for screen readers.
 */
import type { ReactNode } from "react";

import { formatDuration } from "./format";
import { type IdleReason, IdleGlyph } from "./glyphs";

export type SplitKind = "WORKING" | "OFF" | IdleReason;

export function TimeSplit({
  segments,
  axis,
  summary,
  names,
  height = 68,
}: {
  /** In time order; minutes each. */
  segments: { kind: SplitKind; minutes: number }[];
  /** Axis labels at shift start, every 2 h and shift end, e.g. ["07:00", "09:00", …]. */
  axis: string[];
  /** "Working 5 h 10 m, idle 2 h 45 m, engine off 35 m". */
  summary: string;
  /** Names of each kind in the operator's language, for the table. */
  names: Record<SplitKind, string>;
  height?: number;
}) {
  const total = segments.reduce((s, x) => s + x.minutes, 0) || 1;
  return (
    <figure className="flex flex-col gap-2">
      <figcaption className="sr-only">{summary}</figcaption>
      <div aria-hidden className="sm-heavy flex w-full gap-0.75 bg-surface" style={{ height }}>
        {segments.map((s, i) => (
          <span key={i} className={`sm-idle-${s.kind} h-full`} style={{ width: `${(s.minutes / total) * 100}%` }} />
        ))}
      </div>
      <div aria-hidden className="sm-num sm-t-small flex justify-between text-ink-2">
        {axis.map((a) => (
          <span key={a}>{a}</span>
        ))}
      </div>
      <table className="sr-only">
        <tbody>
          {segments.map((s, i) => (
            <tr key={i}>
              <td>{names[s.kind]}</td>
              <td>{formatDuration(s.minutes)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </figure>
  );
}

export function IdleSegmentRow({
  reason,
  name,
  why,
  minutes,
}: {
  reason: IdleReason;
  name: string;
  /** The cause, not the person: "Trucks were late 10:10–10:40". */
  why: string;
  minutes: number;
}) {
  return (
    <div className="sm-rule-soft-b grid grid-cols-[40px_28px_minmax(0,250px)_minmax(0,1fr)_100px] items-start gap-4 py-3">
      <IdleGlyph reason={reason} size={40} />
      <span aria-hidden className={`sm-idle-${reason} mt-1 h-7 w-7 border-2 border-ink`} />
      <span className="sm-t-feed">{name}</span>
      <span className="sm-t-small text-ink-2">{why}</span>
      <span className="sm-num sm-t-feed text-right font-bold">{formatDuration(minutes)}</span>
    </div>
  );
}

export function CoachingNote({
  kind,
  heading,
  text,
  action,
}: {
  kind: "went-well" | "idea";
  heading: string;
  text: string;
  action?: ReactNode;
}) {
  const wentWell = kind === "went-well";
  return (
    <section className={`flex gap-4 bg-surface p-5 ${wentWell ? "sm-heavy" : "sm-rule"}`}>
      <svg aria-hidden viewBox="0 0 48 48" width={44} height={44} className="sm-glyph shrink-0"
        fill={wentWell ? "currentColor" : "none"} stroke="currentColor">
        {wentWell ? (
          <polygon points="24,4 30,18 45,18 33,28 37,43 24,34 11,43 15,28 3,18 18,18" />
        ) : (
          <path d="M6 10 L24 14 L42 10 L42 38 L24 42 L6 38 Z M24 14 L24 42" />
        )}
      </svg>
      <div className="flex flex-col gap-2">
        <h3 className="text-cab-label">{heading}</h3>
        <p className="text-cab-body">{text}</p>
        {action}
      </div>
    </section>
  );
}

/** Console sparkline: a polyline and a baseline; the last value and the peak written beside it. */
export function Sparkline({
  values,
  width = 240,
  height = 48,
  lastLabel,
  peakLabel,
  label,
}: {
  values: number[];
  width?: number;
  height?: number;
  lastLabel: string;
  peakLabel: string;
  label: string;
}) {
  const max = Math.max(...values, 1);
  const step = values.length > 1 ? width / (values.length - 1) : width;
  const points = values.map((v, i) => `${i * step},${height - (v / max) * (height - 4) - 2}`).join(" ");
  return (
    <div className="flex items-center gap-4">
      <svg role="img" aria-label={label} viewBox={`0 0 ${width} ${height}`} width={width} height={height}>
        <line x1="0" y1={height - 1} x2={width} y2={height - 1} stroke="var(--sm-color-line-soft)" strokeWidth="1" />
        <polyline points={points} fill="none" stroke="var(--sm-color-ink)" strokeWidth="2.5" />
      </svg>
      <span className="sm-num flex flex-col text-con-meta">
        <span className="text-con-label">{lastLabel}</span>
        <span className="text-ink-3">{peakLabel}</span>
      </span>
    </div>
  );
}
