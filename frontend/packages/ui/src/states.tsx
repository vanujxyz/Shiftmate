/**
 * Quiet states and the report draft (DESIGN §10 SystemStates, SyncStates, ReportDraftCard).
 * Empty, error, stale and offline share one form: a dashed plate, a glyph, a heading saying what
 * happened, a sentence saying what it means, at most one action. Offline is calm: no red, no
 * exclamation marks. A report draft is laid out as fields to check; nothing is sent until the
 * operator confirms, and Send and Delete are never adjacent.
 */
import type { ReactNode } from "react";

import { Button } from "./controls";
import { NetGlyph, type NetState } from "./glyphs";

export function SystemState({
  kind,
  glyph,
  heading,
  text,
  action,
}: {
  kind: "empty" | "error" | "stale" | "offline";
  glyph?: ReactNode;
  heading: string;
  text: string;
  action?: ReactNode;
}) {
  return (
    <section
      role={kind === "error" ? "alert" : "status"}
      className="sm-dash flex items-start gap-5 bg-surface p-6"
    >
      {glyph && <span aria-hidden className="shrink-0">{glyph}</span>}
      <div className="flex flex-col gap-2">
        <h3 className="text-cab-heading">{heading}</h3>
        <p className="text-cab-body text-ink-2">{text}</p>
        {action && <div className="pt-2">{action}</div>}
      </div>
    </section>
  );
}

/** Sync state as the rail and panels show it: the mast glyph, words only when something waits. */
export function SyncState({ state, words, label }: { state: NetState; words?: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-3 text-cab-label">
      <NetGlyph state={state} size={44} label={label} />
      {words && <span>{words}</span>}
    </span>
  );
}

export function ReportDraftCard({
  fields,
  editLabel,
  sendLabel,
  deleteLabel,
  offlineTag,
  onEdit,
  onSend,
  onDelete,
}: {
  fields: { key: string; name: string; value: string; unsure?: string }[];
  editLabel: string;
  sendLabel: string;
  deleteLabel: string;
  /** "Will send when back online". */
  offlineTag?: string;
  onEdit: (key: string) => void;
  onSend: () => void;
  onDelete: () => void;
}) {
  return (
    <section className="sm-heavy flex flex-col bg-surface">
      {offlineTag && (
        <span className="sm-dash m-4 self-start rounded-chip px-3 py-1 text-cab-meta">{offlineTag}</span>
      )}
      <dl>
        {fields.map((f) => (
          <div key={f.key} className="sm-rule-soft-b grid grid-cols-[220px_minmax(0,1fr)_132px] items-center gap-4 px-5 py-3">
            <dt className="text-cab-meta text-ink-2">{f.name}</dt>
            <dd className="sm-t-row">
              <span className={f.unsure ? "underline decoration-dotted decoration-3 underline-offset-8" : ""}>
                {f.value}
              </span>
              {f.unsure && <span className="block text-cab-meta text-ink-2">{f.unsure}</span>}
            </dd>
            <dd>
              <Button variant="secondary" size="compact" className="w-full" onClick={() => onEdit(f.key)}>
                {editLabel}
              </Button>
            </dd>
          </div>
        ))}
      </dl>
      <div className="flex items-center justify-between p-5">
        <Button variant="danger-quiet" onClick={onDelete}>{deleteLabel}</Button>
        <Button size="xl" onClick={onSend}>{sendLabel}</Button>
      </div>
    </section>
  );
}
