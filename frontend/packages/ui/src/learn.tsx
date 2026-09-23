/**
 * Training hub pieces (DESIGN §10 LessonCard, NarratedCardPlayer, QuizOption, DrillFrame,
 * BookingSlot, ProgressView). Status is a word, not a colour; results are big figures with no
 * score and no leaderboard; the drill STOP is the only danger-filled button in the product.
 */
import type { ReactNode } from "react";

import { Button } from "./controls";
import { PriorityGlyph } from "./glyphs";

export function LessonCard({
  status,
  title,
  meta,
  art,
  onOpen,
}: {
  status?: string;
  title: string;
  /** "2 min · Narrated". */
  meta: string;
  art?: ReactNode;
  onOpen?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="sm-focus sm-rule flex min-h-42 w-full items-center gap-5 bg-surface p-4 text-left active:bg-surface-sunk"
    >
      <span className="flex h-32 w-50 shrink-0 items-center justify-center rounded-bezel bg-surface-sunk">
        {art}
      </span>
      <span className="flex flex-col gap-1">
        {status && <span className="text-cab-meta text-ink-2">{status}</span>}
        <span className="sm-t-32">{title}</span>
        <span className="text-cab-meta text-ink-2">{meta}</span>
      </span>
    </button>
  );
}

export function NarratedCardPlayer({
  diagram,
  sentence,
  fact,
  card,
  cards,
  progressLabel,
  playing,
  playLabel,
  pauseLabel,
  againLabel,
  onPlayPause,
  onAgain,
  language,
}: {
  diagram: ReactNode;
  sentence: string;
  fact?: string;
  card: number;
  cards: number;
  progressLabel: string;
  playing: boolean;
  playLabel: string;
  pauseLabel: string;
  againLabel: string;
  onPlayPause: () => void;
  onAgain: () => void;
  language?: ReactNode;
}) {
  return (
    <section className="sm-heavy flex flex-col gap-5 rounded-bezel bg-surface p-6">
      {language && <div className="flex justify-end">{language}</div>}
      <div className="flex h-82 items-center justify-center rounded-bezel bg-surface-sunk">{diagram}</div>
      <p className="text-cab-title">{sentence}</p>
      {fact && <p className="text-cab-body text-ink-2">{fact}</p>}
      <div role="img" aria-label={progressLabel} className="flex gap-2">
        {Array.from({ length: cards }, (_, i) => (
          <span key={i} className={`h-4 flex-1 border-2 border-ink ${i < card ? "bg-ink" : ""}`} />
        ))}
      </div>
      <div className="flex justify-between">
        <Button variant="secondary" onClick={onAgain}>{againLabel}</Button>
        <Button size="xl" onClick={onPlayPause}>{playing ? pauseLabel : playLabel}</Button>
      </div>
    </section>
  );
}

export function QuizOption({
  letter,
  text,
  state,
  explanation,
  onChoose,
}: {
  letter: string;
  text: string;
  state: "open" | "right" | "wrong" | "other";
  explanation?: string;
  onChoose?: () => void;
}) {
  const look = {
    open: "sm-rule bg-surface",
    right: "border-5 border-safety-safe bg-surface",
    wrong: "sm-dash bg-surface text-ink-2",
    other: "sm-rule bg-surface text-ink-2",
  }[state];
  return (
    <button
      type="button"
      disabled={state !== "open"}
      onClick={onChoose}
      className={`sm-focus flex min-h-24 w-full items-center gap-5 px-5 text-left ${look}`}
    >
      <span className="sm-decal flex h-14 w-14 shrink-0 items-center justify-center rounded-chip border-2 border-ink text-cab-label">
        {letter}
      </span>
      <span className="flex flex-1 flex-col">
        <span className="text-cab-label">{text}</span>
        {state === "right" && explanation && <span className="text-cab-meta">{explanation}</span>}
      </span>
      {state === "right" && <PriorityGlyph priority="safe" size={48} />}
    </button>
  );
}

export function DrillFrame({
  scene,
  markers,
  stopLabel,
  onStop,
  pausedNote,
}: {
  scene: ReactNode;
  markers: { id: string; x: number; y: number; found: boolean; label: string }[];
  stopLabel: string;
  onStop: () => void;
  pausedNote?: string;
}) {
  return (
    <section className="flex flex-col gap-5">
      {pausedNote && <p className="text-cab-meta text-ink-2">{pausedNote}</p>}
      <div className="sm-heavy relative h-100 overflow-hidden rounded-bezel bg-surface-sunk">
        {scene}
        {markers.map((m) => (
          <span
            key={m.id}
            role="img"
            aria-label={m.label}
            className={`absolute h-24 w-24 -translate-x-1/2 -translate-y-1/2 rounded-disc border-6 ${m.found ? "border-safety-caution" : "border-chalk"}`}
            style={{ left: `${m.x}%`, top: `${m.y}%`, outline: "2px solid var(--sm-color-ink)" }}
          />
        ))}
      </div>
      <Button variant="stop" size="xl" onClick={onStop} className="min-h-35 w-full">
        {stopLabel}
      </Button>
    </section>
  );
}

export function BookingSlot({
  day,
  time,
  who,
  where,
  state,
  fullLabel,
  onSelect,
}: {
  day: string;
  time: string;
  who: string;
  where: string;
  state: "open" | "selected" | "full";
  fullLabel: string;
  onSelect?: () => void;
}) {
  const look = {
    open: "sm-rule bg-surface text-ink",
    selected: "sm-heavy bg-selected text-on-selected",
    full: "sm-dash bg-surface-sunk text-ink-2",
  }[state];
  return (
    <button
      type="button"
      disabled={state === "full"}
      aria-pressed={state === "selected"}
      onClick={onSelect}
      className={`sm-focus flex min-h-26 w-full flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3 text-left ${look}`}
    >
      <span className="flex flex-col">
        <span className="text-cab-meta">{day}</span>
        <span className="sm-num sm-t-32">{time}</span>
      </span>
      <span className="flex min-w-0 flex-1 basis-40 flex-col text-cab-meta">
        <span>{who}</span>
        <span>{where}</span>
      </span>
      {state === "full" && <span className="text-cab-label">{fullLabel}</span>}
    </button>
  );
}

export function SkillLadder({
  name,
  level,
  levels,
  next,
  label,
}: {
  name: string;
  level: number;
  levels: number;
  next: string;
  label: string;
}) {
  return (
    <div className="flex flex-col gap-2">
      <p className="text-cab-label">{name}</p>
      <div role="img" aria-label={label} className="flex gap-2">
        {Array.from({ length: levels }, (_, i) => (
          <span key={i} className={`h-11 flex-1 border-2 border-ink ${i < level ? "bg-ink" : "bg-surface"}`} />
        ))}
      </div>
      <p className="text-cab-meta text-ink-2">{next}</p>
    </div>
  );
}
