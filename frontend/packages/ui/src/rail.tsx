/**
 * The cab frame (DESIGN §10 StatusRail, RiskIndicator, AlertQueue pip, BottomNav).
 *
 * StatusRail, left → right: Reach segment (the only light segment, so proximity reads first),
 * risk stack light + word + reason, seatbelt, machine (Paused only), flexible gap, queue pip,
 * sync, clock. Paused 96 px, Working 176 px. The rail is never covered except by a P1.
 */
import type { ReactNode } from "react";

import {
  BeltGlyph,
  MachineGlyph,
  type MachineState,
  NetGlyph,
  type NetState,
  type Priority,
  PriorityGlyph,
  type ProximityTier,
  ProximityGlyph,
} from "./glyphs";
import { Reach } from "./reach";

export type RiskBand = "green" | "amber" | "red";

/** Stack light: three lamps, red top, amber middle, green bottom; only the current one is lit. */
export function StackLight({
  band,
  label,
  size = "rail",
}: {
  band: RiskBand;
  label: string;
  size?: "rail" | "working" | "surface";
}) {
  const dims = { rail: "h-18 w-8", working: "h-28 w-12", surface: "h-18 w-8" }[size];
  const lamps: [RiskBand, string][] = [
    ["red", "bg-safety-risk-red"],
    ["amber", "bg-safety-risk-amber"],
    ["green", "bg-safety-risk-green"],
  ];
  return (
    <span
      role="img"
      aria-label={label}
      className={`flex shrink-0 flex-col justify-between rounded-chip border-2 p-1 ${dims} ${size === "surface" ? "border-ink bg-surface" : "border-on-rail bg-rail"}`}
    >
      {lamps.map(([b, lit]) => (
        <span
          key={b}
          className={`aspect-square w-full rounded-disc border-2 ${b === band ? `${lit} border-ink` : "border-rail-rule bg-transparent"}`}
        />
      ))}
    </span>
  );
}

/**
 * "No update 40 s" with the dashed stale mark. In the status rail only the mark and `short`
 * ("40 s") are drawn, in every language (D-071); the full sentence stays the accessible name.
 */
export function StaleMark({ text, short }: { text: string; short?: string }) {
  return (
    <span className="sm-num text-cab-meta" aria-label={text} role="img">
      <span aria-hidden className="mr-2 inline-block h-4 w-4 border-2 border-dashed border-current" />
      <span aria-hidden className={short ? "sm-stale-long" : undefined}>{text}</span>
      {short && <span aria-hidden className="sm-stale-short">{short}</span>}
    </span>
  );
}

export function QueuePip({ priority, count, label }: { priority: Priority; count: number; label: string }) {
  return (
    <span role="img" aria-label={label} className="sm-num flex items-center gap-2 rounded-chip bg-surface px-2 py-1 text-ink text-cab-label">
      <PriorityGlyph priority={priority} size={36} />+{count}
    </span>
  );
}

export type StatusRailProps = {
  mode: "working" | "paused";
  proximity: {
    tier: ProximityTier;
    bearing?: number | null;
    boomAngle?: number;
    word: string;
    label: string;
    noSensing?: boolean;
    stale?: string;
    staleShort?: string;
  };
  risk: { band: RiskBand; word: string; reason?: string; label: string };
  belt: { fastened: boolean; word: string } | null;
  machine?: { id: string; state: MachineState; word: string };
  queue?: { priority: Priority; count: number; label: string } | null;
  /** `short` ("48") stands in for `words` where the rail has no room for them. */
  sync: { state: NetState; words?: string; short?: string; label: string };
  clock: string;
};

function Segment({
  children,
  light = false,
  className = "",
}: {
  children: ReactNode;
  light?: boolean;
  className?: string;
}) {
  return (
    <div
      className={`sm-rail-seg flex h-full shrink-0 items-center gap-2 px-3 ${light ? "bg-surface text-ink" : "border-r-2 border-rail-rule"} ${className}`}
    >
      {children}
    </div>
  );
}

export function StatusRail(p: StatusRailProps) {
  const working = p.mode === "working";
  const text = working ? "text-cab-heading" : "text-cab-label";
  return (
    <header
      className={`sm-rail sm-rule-b sticky top-0 z-(--sm-layer-rail) flex w-full items-stretch bg-rail text-on-rail ${working ? "h-(--sm-size-rail-working)" : "h-(--sm-size-rail-paused)"}`}
      style={{ transition: "height var(--sm-motion-mode) var(--sm-motion-ease)" }}
    >
      <Segment light>
        <Reach
          tier={p.proximity.tier}
          bearing={p.proximity.bearing}
          boomAngle={p.proximity.boomAngle}
          size={working ? 148 : 84}
          label={p.proximity.label}
          noSensing={p.proximity.noSensing}
        />
        <span className={`sm-rail-word sm-rail-prox flex flex-col ${text}`}>
          <span className="flex items-center gap-2">
            {p.proximity.tier === "clear" && !p.proximity.noSensing ? (
              <PriorityGlyph priority="safe" size={working ? 44 : 32} />
            ) : !p.proximity.noSensing ? (
              <ProximityGlyph tier={p.proximity.tier} size={working ? 44 : 32} />
            ) : null}
            {p.proximity.word}
          </span>
          {p.proximity.stale && <StaleMark text={p.proximity.stale} short={p.proximity.staleShort} />}
        </span>
      </Segment>
      <Segment>
        <StackLight band={p.risk.band} label={p.risk.label} size={working ? "working" : "rail"} />
        <span className={`sm-rail-word flex flex-col ${text}`}>
          <span>{p.risk.word}</span>
          {p.risk.reason && <span className="sm-rail-reason text-cab-meta">{p.risk.reason}</span>}
        </span>
      </Segment>
      {p.belt && (
        <Segment>
          <BeltGlyph fastened={p.belt.fastened} size={working ? 56 : 44} />
          <span className={`sm-rail-word ${text}`}>{p.belt.word}</span>
        </Segment>
      )}
      {!working && p.machine && (
        <Segment className="sm-rail-machine">
          <MachineGlyph state={p.machine.state} size={44} label={p.machine.word} />
          <span className="sm-decal text-cab-decal">{p.machine.id}</span>
          <span aria-hidden className="sm-rail-word sm-rail-repeat text-cab-label">{p.machine.word}</span>
        </Segment>
      )}
      <div className="min-w-0 flex-1" />
      {p.queue && (
        <div className="flex items-center px-3">
          <QueuePip {...p.queue} />
        </div>
      )}
      <div className="sm-rail-seg flex shrink-0 items-center gap-2 px-3">
        <NetGlyph state={p.sync.state} size={working ? 48 : 40} label={p.sync.label} />
        {p.sync.words && (
          <span className="sm-rail-word text-cab-meta">
            <span className={p.sync.short ? "sm-rail-long" : undefined}>{p.sync.words}</span>
            {p.sync.short && <span className="sm-rail-short sm-num">{p.sync.short}</span>}
          </span>
        )}
      </div>
      <div
        className={`sm-num flex items-center px-4 font-semibold ${working ? "text-[56px]" : "text-[40px]"}`}
      >
        {p.clock}
      </div>
    </header>
  );
}

// --- BottomNav: five tabs + the push-to-talk cell; Paused mode only -------------------------------------

export function BottomNav({
  tabs,
  current,
  onSelect,
  label,
  ptt,
}: {
  tabs: { id: string; label: string; glyph: ReactNode }[];
  current: string;
  onSelect: (id: string) => void;
  label: string;
  ptt: ReactNode;
}) {
  return (
    <nav
      aria-label={label}
      className="sm-nav sm-rule-t grid h-(--sm-size-nav) w-full bg-surface"
      style={{ gridTemplateColumns: `repeat(${tabs.length}, minmax(0, 1fr)) var(--sm-nav-ptt-cell)` }}
    >
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          aria-current={t.id === current ? "page" : undefined}
          onClick={() => onSelect(t.id)}
          className={`sm-focus flex flex-col items-center justify-center gap-1 border-r-2 border-line-soft text-cab-meta font-semibold ${t.id === current ? "bg-selected text-on-selected" : "text-ink active:bg-surface-sunk"}`}
        >
          <span aria-hidden>{t.glyph}</span>
          <span className="sm-dense text-center leading-tight">{t.label}</span>
        </button>
      ))}
      <div className="relative flex items-end justify-end pr-10 pb-5">{ptt}</div>
    </nav>
  );
}
