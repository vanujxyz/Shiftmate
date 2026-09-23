/**
 * The alert layer (DESIGN §10 AlertTakeoverP1, AlertBannerP2, AlertStripP3, AlertFeedP4,
 * AlertQueue). One interrupting alert at a time; the app's alert store decides which one shows
 * (P1 > P2 > P3 > P4). These components only draw it:
 * - P1: full screen, above everything, appears in 0 ms, a 12 px frame flashing red ↔ ink at 1 Hz,
 *   a hatch band, the cause drawn big on the left, one action ("I've stopped"), no dismiss.
 * - P2: orange banner under the rail with the triangle, one action ("Seen"); content stays usable.
 * - P3: yellow strip at the bottom with the diamond, one optional action; clear of push-to-talk.
 * - P4: a quiet feed row with the square; never interrupts, never makes a sound.
 * Night drops large fields of colour (P1 keeps the frame, P2/P3 become bordered surfaces).
 */
import type { ReactNode } from "react";

import { PriorityGlyph } from "./glyphs";

export function AlertTakeoverP1({
  command,
  situation,
  instruction,
  where,
  cause,
  ackLabel,
  onAck,
  queueLine,
  queuePriority,
  inline = false,
}: {
  command: string;
  situation: string;
  instruction: string;
  where?: string;
  /** The cause drawn big: the Reach (460 px) or the seatbelt glyph (300 px). */
  cause: ReactNode;
  ackLabel: string;
  onAck: () => void;
  queueLine?: string;
  queuePriority?: "P1" | "P2" | "P3" | "P4";
  /** Kitchen sink / previews: a 1280 × 800 plate in place instead of covering the screen. */
  inline?: boolean;
}) {
  return (
    <div
      role="alertdialog"
      aria-modal="true"
      aria-label={`${command} ${situation}`}
      className={`sm-p1-fill sm-alert-frame sm-p1-flash z-(--sm-layer-p1) flex bg-surface text-ink ${inline ? "relative h-200 w-320" : "fixed inset-0"}`}
    >
      <div className="flex w-1/2 items-center justify-center p-6">{cause}</div>
      <div className="flex w-1/2 min-w-0 flex-col gap-4 px-8 py-6">
        <div aria-hidden className="sm-hatch h-8 w-full shrink-0" />
        {/* the message may shrink or scroll; the acknowledge button below is always on screen */}
        <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto">
          <div className="flex items-center gap-5">
            <PriorityGlyph priority="P1" size={104} />
            <span className="sm-t-p1">{command}</span>
          </div>
          <p className="sm-t-p1">{situation}</p>
          <p className="sm-t-p1-do">{instruction}</p>
          {where && <p className="sm-num sm-t-p1-do text-ink-2">{where}</p>}
        </div>
        <button
          type="button"
          onClick={onAck}
          className="sm-focus sm-press min-h-33 w-full shrink-0 rounded-control border-(length:--sm-border-rule) border-action-border bg-action text-cab-title text-on-action active:bg-action-pressed"
        >
          {ackLabel}
        </button>
        {queueLine && (
          <p className="flex shrink-0 items-center gap-3 text-cab-meta">
            {queuePriority && <PriorityGlyph priority={queuePriority} size={32} />}
            {queueLine}
          </p>
        )}
      </div>
    </div>
  );
}

export function AlertBannerP2({
  situation,
  detail,
  seenLabel,
  onSeen,
  inline = false,
}: {
  situation: string;
  detail?: string;
  seenLabel: string;
  onSeen: () => void;
  /** Kitchen sink / previews: draw in place instead of anchoring under the rail. */
  inline?: boolean;
}) {
  return (
    <div
      role="alert"
      className={`sm-p2 sm-drop-in flex min-h-34 w-full items-center gap-6 bg-safety-alert-p2 px-8 py-4 text-safety-on-warning ${inline ? "" : "absolute left-0 z-(--sm-layer-p2)"}`}
      style={{ boxShadow: "var(--sm-elev-banner)" }}
    >
      <PriorityGlyph priority="P2" size={84} />
      <div className="flex-1">
        <p className="sm-t-p2">{situation}</p>
        {detail && <p className="text-cab-label">{detail}</p>}
      </div>
      <button
        type="button"
        onClick={onSeen}
        className="sm-focus sm-press min-h-(--sm-size-target) min-w-50 rounded-control border-(length:--sm-border-rule) border-action-border bg-action px-6 text-cab-label text-on-action"
      >
        {seenLabel}
      </button>
    </div>
  );
}

export function AlertStripP3({
  text,
  actionLabel,
  onAction,
  inline = false,
}: {
  text: string;
  actionLabel?: string;
  onAction?: () => void;
  inline?: boolean;
}) {
  return (
    <div
      role="status"
      className={`sm-p3 sm-rise-in flex min-h-21 w-full items-center gap-5 border-y-3 border-ink bg-safety-alert-p3 py-3 pl-8 pr-58 text-safety-on-caution ${inline ? "" : "absolute left-0 z-(--sm-layer-p3)"}`}
    >
      <PriorityGlyph priority="P3" size={52} />
      <p className="sm-t-p3 flex-1">{text}</p>
      {actionLabel && onAction && (
        <button
          type="button"
          onClick={onAction}
          className="sm-focus min-h-(--sm-size-target-min) px-4 text-cab-label underline decoration-3 underline-offset-8"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}

export function AlertFeedP4({
  items,
  label,
}: {
  items: { id: string; title: string; meta: string; unread?: boolean }[];
  label: string;
}) {
  return (
    <ul aria-label={label} role="status" className="flex flex-col">
      {items.map((i) => (
        <li key={i.id} className="sm-rule-soft-b flex items-start gap-4 py-3">
          <PriorityGlyph priority="P4" size={36} />
          <div className="flex-1">
            <p className="sm-t-feed flex items-center gap-3">
              {i.title}
              {i.unread && <span aria-hidden className="h-3 w-3 bg-safety-info" />}
            </p>
            <p className="sm-t-small text-ink-3">{i.meta}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}
