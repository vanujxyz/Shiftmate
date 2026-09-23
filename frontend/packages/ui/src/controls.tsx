/**
 * Glove-sized controls (DESIGN §4 targets, §10 Button, LargeToggle, SegmentedControl,
 * PinPadAndBadge, ChecklistItem, PushToTalk). Targets are ≥ 68 px (18 mm), standard 88 px;
 * pressed = darker fill + 2 px down-shift; focus = 4 px ring outside a 3 px chalk gap; no hover.
 * Components never carry text of their own: every word arrives translated through props.
 */
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { PriorityGlyph } from "./glyphs";

type Variant = "primary" | "secondary" | "quiet" | "stop" | "danger-quiet";

const VARIANT: Record<Variant, string> = {
  // Night: a dark slab whose lit border carries the shape (in Day the border matches the fill)
  primary: "bg-action text-on-action border-(length:--sm-border-rule) border-action-border active:bg-action-pressed",
  secondary: "bg-surface text-ink border-(length:--sm-border-rule) border-action-border active:bg-surface-sunk",
  quiet: "bg-transparent text-ink underline decoration-3 underline-offset-8 active:bg-surface-sunk",
  stop: "bg-safety-danger text-safety-on-danger active:bg-action-pressed",
  "danger-quiet": "bg-transparent text-safety-danger-ink border-(length:--sm-border-rule) border-safety-danger-ink",
};

export type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: "standard" | "xl" | "console" | "compact";
  glyph?: ReactNode;
  loading?: boolean;
};

export function Button({
  variant = "primary",
  size = "standard",
  glyph,
  loading = false,
  disabled,
  className,
  children,
  ...rest
}: ButtonProps) {
  const sizing = {
    standard: "min-h-(--sm-size-target) min-w-(--sm-size-target-min) px-6 text-cab-label",
    xl: "min-h-(--sm-size-target-xl) px-8 text-cab-heading",
    console: "min-h-(--sm-size-console-target) px-4 text-con-label",
    compact: "min-h-(--sm-size-target-min) min-w-(--sm-size-target-min) px-3 text-cab-label",
  }[size];
  const look = disabled ? "bg-disabled text-on-disabled" : VARIANT[variant];
  return (
    <button
      type="button"
      disabled={disabled}
      aria-busy={loading || undefined}
      className={`sm-focus sm-press relative inline-flex items-center justify-center gap-3 rounded-control ${sizing} ${look} ${className ?? ""}`}
      {...rest}
    >
      {variant === "stop" && !disabled && <PriorityGlyph priority="P1" size={56} />}
      {glyph && !disabled && <span aria-hidden className="inline-flex">{glyph}</span>}
      <span className={loading ? "invisible" : undefined}>{children}</span>
      {loading && (
        <span aria-hidden className="absolute h-1 w-1/2 border-t-(length:--sm-border-dash) border-dashed border-current" />
      )}
    </button>
  );
}

// --- LargeToggle: the state is written inside, never only the knob position ------------------------

export function LargeToggle({
  on,
  onChange,
  label,
  onText,
  offText,
  disabled,
}: {
  on: boolean;
  onChange: (on: boolean) => void;
  label: string;
  onText: string;
  offText: string;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={disabled}
      onClick={() => onChange(!on)}
      className="sm-focus flex min-h-(--sm-size-target) w-full items-center justify-between gap-6 text-left text-cab-label"
    >
      <span>{label}</span>
      <span
        className={`sm-heavy relative flex h-18 w-34 shrink-0 items-center rounded-control px-2 ${on ? "justify-end bg-action text-on-action" : "justify-start bg-surface-sunk text-ink"}`}
      >
        <span className="absolute inset-x-0 text-center text-cab-meta">{on ? onText : offText}</span>
        <span className={`z-10 h-12 w-10 rounded-chip ${on ? "bg-on-action" : "bg-ink"}`} />
      </span>
    </button>
  );
}

// --- SegmentedControl: 2–4 exclusive options; selected = inversion ----------------------------------

export function SegmentedControl<T extends string>({
  options,
  value,
  onChange,
  label,
  dense = false,
}: {
  options: { value: T; label: string; lang?: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
  dense?: boolean;
}) {
  return (
    <div role="group" aria-label={label} className="sm-heavy inline-flex rounded-control bg-surface">
      {options.map((o, i) => (
        <button
          key={o.value}
          type="button"
          lang={o.lang}
          aria-pressed={o.value === value}
          onClick={() => onChange(o.value)}
          className={`sm-focus min-w-24 px-5 ${dense ? "min-h-(--sm-size-console-target) text-con-label" : "min-h-20 text-cab-label"} ${i > 0 ? "border-l-2 border-line" : ""} ${o.value === value ? "bg-selected text-on-selected" : "text-ink active:bg-surface-sunk"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

// --- PIN pad and badge target -------------------------------------------------------------------------

export function PinPad({
  length = 4,
  entered,
  onDigit,
  onBackspace,
  label,
  backspaceLabel,
  error,
}: {
  length?: number;
  entered: number;
  onDigit: (d: string) => void;
  onBackspace: () => void;
  label: string;
  backspaceLabel: string;
  error?: string;
}) {
  const keys = ["1", "2", "3", "4", "5", "6", "7", "8", "9", "", "0", "⌫"];
  return (
    <div className="flex flex-col items-center gap-6">
      <div aria-label={label} role="status" className="flex gap-5">
        {Array.from({ length }, (_, i) => (
          <span key={i} className={`h-7 w-7 rounded-disc border-4 border-ink ${i < entered ? "bg-ink" : ""}`} />
        ))}
      </div>
      {error && <p className="text-cab-body">{error}</p>}
      <div className="grid grid-cols-3 gap-4">
        {keys.map((k, i) =>
          k === "" ? (
            <span key={i} />
          ) : (
            <button
              key={i}
              type="button"
              aria-label={k === "⌫" ? backspaceLabel : k}
              onClick={() => (k === "⌫" ? onBackspace() : onDigit(k))}
              className="sm-focus sm-press sm-rule sm-num h-24 w-28 rounded-control bg-surface text-[44px] font-semibold active:bg-surface-sunk"
            >
              {k}
            </button>
          ),
        )}
      </div>
    </div>
  );
}

export function BadgeTarget({ title, hint, children }: { title: string; hint: string; children?: ReactNode }) {
  return (
    <div className="sm-dash flex h-57 w-90 flex-col items-center justify-center gap-3 rounded-bezel bg-surface p-6 text-center">
      <p className="text-cab-heading">{title}</p>
      <p className="text-cab-meta text-ink-2">{hint}</p>
      {children}
    </div>
  );
}

// --- ChecklistItem: two explicit answers, never a lone tick box -----------------------------------------

export function ChecklistItem({
  text,
  answer,
  onAnswer,
  okLabel,
  problemLabel,
}: {
  text: string;
  answer: "ok" | "problem" | null;
  onAnswer: (a: "ok" | "problem") => void;
  okLabel: string;
  problemLabel: string;
}) {
  const choice = (value: "ok" | "problem", label: string) => (
    <button
      type="button"
      aria-pressed={answer === value}
      onClick={() => onAnswer(value)}
      className={`sm-focus sm-press h-19 w-45 rounded-control border-(length:--sm-border-rule) border-action-border text-cab-label ${answer === value ? "bg-selected text-on-selected" : "bg-surface text-ink"}`}
    >
      {label}
    </button>
  );
  return (
    <div className="sm-rule-soft-b flex items-center justify-between gap-6 py-4">
      <p className="text-cab-body">{text}</p>
      <div className="flex shrink-0 gap-4">
        {choice("ok", okLabel)}
        {choice("problem", problemLabel)}
      </div>
    </div>
  );
}

// --- PushToTalk: same place in both modes; hold to talk, tap for a 6 s window ------------------------------

export type PttState = "idle" | "listening" | "transcribing" | "thinking" | "error" | "offline";

export function PushToTalk({
  state,
  label,
  onPress,
  onRelease,
  size = 136,
}: {
  state: PttState;
  /** "Hold to talk", "Listening…", … in the operator's language. */
  label: string;
  onPress?: () => void;
  onRelease?: () => void;
  size?: number;
}) {
  const listening = state === "listening";
  return (
    <button
      type="button"
      aria-label={label}
      aria-pressed={listening}
      onPointerDown={onPress}
      onPointerUp={onRelease}
      style={{ width: size, height: size }}
      className="sm-focus relative flex items-center justify-center rounded-disc border-(length:--sm-border-heavy) border-action-border bg-action text-on-action active:bg-action-pressed"
    >
      {listening && (
        <span aria-hidden className="sm-listen-ring absolute inset-0 rounded-disc border-4 border-action-border" />
      )}
      <span aria-hidden className="absolute inset-2 rounded-disc border-6 border-chalk" />
      <svg aria-hidden viewBox="0 0 48 48" width={size * 0.44} height={size * 0.44}
        className="sm-glyph" fill="none" stroke="currentColor">
        <rect x="17" y="4" width="14" height="24" rx="7" fill={listening ? "currentColor" : "none"} />
        <path d="M10 22 A14 14 0 0 0 38 22" />
        <line x1="24" y1="36" x2="24" y2="44" />
      </svg>
    </button>
  );
}
