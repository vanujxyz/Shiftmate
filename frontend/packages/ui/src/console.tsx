/**
 * Console pieces built once here (DESIGN §9 site map symbology, §10 DemoControlBar, FleetTiles).
 * The full site map, detail panel and supervisor panels are composed in the console app
 * (milestone 13) from these and the shared glyphs.
 */
import type { ReactNode } from "react";

/** The site map legend: a bottom-left plate with a 2 px frame. */
export function MapLegend({
  title,
  items,
}: {
  title: string;
  items: { symbol: ReactNode; label: string }[];
}) {
  return (
    <aside aria-label={title} className="sm-rule inline-flex flex-col gap-2 bg-surface p-3 text-con-meta">
      <p className="text-con-label">{title}</p>
      {items.map((i) => (
        <p key={i.label} className="flex items-center gap-3">
          <span aria-hidden className="inline-flex w-8 justify-center">{i.symbol}</span>
          {i.label}
        </p>
      ))}
    </aside>
  );
}

/** Map symbols in console size (drawn with the same ring logic as the Reach). */
export function MapSymbol({ kind }: { kind: "machine" | "truck" | "worker" | "zone" | "rings" }) {
  return (
    <svg aria-hidden viewBox="0 0 32 32" width={28} height={28} fill="none" stroke="var(--sm-color-ink)" strokeWidth="2">
      {kind === "machine" && (
        <>
          <rect x="10" y="10" width="12" height="12" fill="var(--sm-color-ink)" />
          <line x1="16" y1="10" x2="16" y2="2" strokeWidth="3" />
        </>
      )}
      {kind === "truck" && (
        <>
          <rect x="4" y="10" width="18" height="12" />
          <rect x="22" y="13" width="6" height="9" fill="var(--sm-color-ink)" />
        </>
      )}
      {kind === "worker" && (
        <circle cx="16" cy="16" r="5" fill="var(--sm-color-ink)" stroke="var(--sm-color-surface)" strokeWidth="3" />
      )}
      {kind === "zone" && <rect x="3" y="7" width="26" height="18" strokeDasharray="4 3" />}
      {kind === "rings" && (
        <>
          <circle cx="16" cy="16" r="14" stroke="var(--sm-color-mark)" strokeDasharray="4 3" />
          <circle cx="16" cy="16" r="10" stroke="var(--sm-color-mark)" />
          <circle cx="16" cy="16" r="6" strokeWidth="3" />
        </>
      )}
    </svg>
  );
}

/** Demo builds only: a dashed bar that makes simulated data impossible to mistake for live. */
export function DemoBar({ label, children }: { label: string; children?: ReactNode }) {
  return (
    <div role="region" aria-label={label} className="sm-dash flex flex-wrap items-center gap-4 bg-surface px-4 py-2">
      <span className="text-con-label">{label}</span>
      {children}
    </div>
  );
}

/** A fleet site tile: country and local time, name, machines active of total, risk split. */
export function FleetTile({
  country,
  localTime,
  name,
  active,
  bands,
  bandsLabel,
  condition,
}: {
  country: string;
  localTime: string;
  name: string;
  /** "12 of 24 machines active". */
  active: string;
  bands: { green: number; amber: number; red: number };
  bandsLabel: string;
  condition?: string;
}) {
  const total = bands.green + bands.amber + bands.red || 1;
  return (
    <section className="sm-rule flex flex-col gap-3 bg-surface p-4">
      <p className="sm-num flex justify-between text-con-meta text-ink-3">
        <span className="sm-decal">{country}</span>
        <span>{localTime}</span>
      </p>
      <h3 className="text-con-heading">{name}</h3>
      <p className="text-con-body">{active}</p>
      <div role="img" aria-label={bandsLabel} className="flex h-4 w-full gap-0.5">
        <span className="bg-safety-risk-green" style={{ width: `${(bands.green / total) * 100}%` }} />
        <span className="bg-safety-risk-amber" style={{ width: `${(bands.amber / total) * 100}%` }} />
        <span className="bg-safety-risk-red" style={{ width: `${(bands.red / total) * 100}%` }} />
      </div>
      <p className="text-con-meta">{bandsLabel}</p>
      {condition && <p className="text-con-meta text-ink-2">{condition}</p>}
    </section>
  );
}
