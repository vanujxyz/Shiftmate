/**
 * Voice pieces (DESIGN §10 TranscriptSheet, AssistantAnswer). The sheet shows what ShiftMate
 * hears while push-to-talk is active (non-final words in ink-2 with a dashed underline); errors
 * are calm, never red. An answer shows the question as heard, a short answer and its sources;
 * offline answers carry a dashed tag, and "I don't know" is a first-class answer.
 */
import type { ReactNode } from "react";

export function TranscriptSheet({
  stateWord,
  finalText,
  pendingText,
  helper,
  level = 0,
  inline = false,
  error,
}: {
  stateWord: string;
  finalText: string;
  pendingText?: string;
  helper?: string;
  /** Microphone level 0–1: 13 bars prove the mic is hearing. */
  level?: number;
  inline?: boolean;
  error?: string;
}) {
  const bars = Math.round(Math.max(0, Math.min(1, level)) * 13);
  return (
    <section
      aria-live="polite"
      className={`sm-rise-in flex w-full flex-col gap-4 border-t-4 border-ink bg-surface py-6 pr-60 pl-8 ${inline ? "" : "absolute bottom-0 left-0 z-(--sm-layer-sheet)"}`}
      style={{ boxShadow: "var(--sm-elev-sheet)" }}
    >
      <div className="flex items-center gap-4">
        <span className="text-[26px] font-bold">{stateWord}</span>
        <span aria-hidden className="flex h-8 items-end gap-1">
          {Array.from({ length: 13 }, (_, i) => (
            <span key={i} className={`w-1.5 ${i < bars ? "bg-ink" : "bg-surface-sunk"}`}
              style={{ height: `${30 + ((i * 37) % 70)}%` }} />
          ))}
        </span>
      </div>
      {error ? (
        <p className="sm-t-transcript">{error}</p>
      ) : (
        <p className="sm-t-transcript">
          {finalText}{" "}
          {pendingText && (
            <mark className="bg-transparent text-ink-2 underline decoration-dashed decoration-2 underline-offset-8">
              {pendingText}
            </mark>
          )}
        </p>
      )}
      {helper && <p className="text-cab-meta text-ink-2">{helper}</p>}
    </section>
  );
}

export function SourceChip({
  title,
  section,
  offline = false,
  onOpen,
}: {
  title: string;
  section: string;
  offline?: boolean;
  onOpen?: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className={`sm-focus flex min-h-(--sm-size-target-min) items-center gap-3 rounded-chip bg-surface px-4 text-cab-meta ${offline ? "sm-dash" : "border-2 border-ink"}`}
    >
      <svg aria-hidden viewBox="0 0 48 48" width={32} height={32} className="sm-glyph" fill="none" stroke="currentColor">
        <path d="M10 4 L30 4 L38 12 L38 44 L10 44 Z" />
        <line x1="16" y1="20" x2="32" y2="20" />
        <line x1="16" y1="28" x2="32" y2="28" />
      </svg>
      <span className="font-semibold">{title}</span>
      <span className="text-ink-2">{section}</span>
    </button>
  );
}

export function AssistantAnswer({
  question,
  answer,
  sources,
  offlineTag,
  unknown = false,
  actions,
}: {
  question: string;
  answer: string;
  sources?: ReactNode;
  /** "Offline answer · manual saved 18 Sep". */
  offlineTag?: string;
  unknown?: boolean;
  actions?: ReactNode;
}) {
  return (
    <section className={`flex flex-col gap-4 bg-surface p-6 ${unknown ? "sm-dash" : "sm-heavy"}`}>
      {offlineTag && (
        <span className="sm-dash self-start rounded-chip px-3 py-1 text-cab-meta">{offlineTag}</span>
      )}
      <p className="sm-t-feed text-ink-2">{question}</p>
      <p className="sm-t-answer">{answer}</p>
      {sources && <div className="flex flex-wrap gap-3">{sources}</div>}
      {actions && <div className="flex flex-wrap gap-4">{actions}</div>}
    </section>
  );
}
