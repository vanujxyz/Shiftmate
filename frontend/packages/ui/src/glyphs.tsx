/**
 * ShiftMate glyphs (DESIGN §6): machine states, idle reasons, proximity tiers, seatbelt, sync,
 * sensor tier, priority shapes and conditions. 48-unit grid, plan view for machines, square caps,
 * mitred joins, `currentColor`, stroke `--sm-icon-stroke` that never scales with the glyph.
 * Priority shapes and the safe tick are the only coloured glyphs (safety fill + ink keyline).
 * A glyph with `label` is announced (`role="img"`); without, it is decorative.
 */
import type { ReactNode } from "react";

export type GlyphProps = { size?: number; label?: string; className?: string };

function Svg({ size = 48, label, className, children }: GlyphProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 48 48"
      width={size}
      height={size}
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={`sm-glyph shrink-0 ${className ?? ""}`}
      fill="none"
      stroke="currentColor"
      strokeLinecap="square"
      strokeLinejoin="miter"
    >
      {children}
    </svg>
  );
}

const DASH = "4 4";

// --- machine state (plan view: two tracks, a house square, the boom) ---------------------------

export type MachineState = "working" | "idle" | "travel" | "off";

export function MachineGlyph({ state, ...p }: GlyphProps & { state: MachineState }) {
  const off = state === "off";
  const dash = off ? DASH : undefined;
  return (
    <Svg {...p}>
      <rect x="6" y="10" width="7" height="30" strokeDasharray={dash}
        fill={state === "travel" ? "currentColor" : "none"} />
      <rect x="35" y="10" width="7" height="30" strokeDasharray={dash}
        fill={state === "travel" ? "currentColor" : "none"} />
      <rect x="16" y="17" width="16" height="16" strokeDasharray={dash}
        fill={state === "working" ? "currentColor" : "none"} />
      <line x1="24" y1="17" x2="24" y2={state === "working" ? 3 : 9} strokeDasharray={dash} />
      {state === "idle" && (
        <>
          <line x1="21" y1="21" x2="21" y2="29" />
          <line x1="27" y1="21" x2="27" y2="29" />
        </>
      )}
      {state === "travel" && <polyline points="17,8 24,3 31,8" />}
      {off && <line x1="6" y1="44" x2="42" y2="4" />}
    </Svg>
  );
}

// --- idle reasons (none of them points at a person) --------------------------------------------

export type IdleReason =
  | "WAITING_FOR_TRUCK"
  | "WARM_UP"
  | "SCHEDULED_BREAK"
  | "UNATTENDED_RUNNING"
  | "HABIT"
  | "UNKNOWN";

export function IdleGlyph({ reason, ...p }: GlyphProps & { reason: IdleReason }) {
  switch (reason) {
    case "WAITING_FOR_TRUCK": // a truck, and the empty bay it should be in
      return (
        <Svg {...p}>
          <rect x="4" y="14" width="20" height="14" />
          <rect x="24" y="18" width="8" height="10" />
          <line x1="8" y1="34" x2="12" y2="34" />
          <line x1="22" y1="34" x2="26" y2="34" />
          <rect x="34" y="12" width="10" height="24" strokeDasharray={DASH} />
        </Svg>
      );
    case "WARM_UP": // a gauge with the needle low
      return (
        <Svg {...p}>
          <path d="M8 34 A16 16 0 0 1 40 34" />
          <line x1="24" y1="34" x2="12" y2="27" />
          <line x1="8" y1="40" x2="40" y2="40" />
        </Svg>
      );
    case "SCHEDULED_BREAK": // a steel tea tumbler
      return (
        <Svg {...p}>
          <path d="M12 12 L16 42 L32 42 L36 12 Z" />
          <line x1="10" y1="12" x2="38" y2="12" />
          <line x1="14" y1="20" x2="34" y2="20" />
        </Svg>
      );
    case "UNATTENDED_RUNNING": // an empty seat, the engine still humming
      return (
        <Svg {...p}>
          <path d="M10 8 L10 30 L28 30 L28 40" />
          <line x1="10" y1="30" x2="10" y2="40" />
          <path d="M34 14 Q38 18 34 22" />
          <path d="M38 10 Q44 18 38 26" />
        </Svg>
      );
    case "HABIT": // a loop
      return (
        <Svg {...p}>
          <path d="M36 16 A13 13 0 1 0 38 28" />
          <polyline points="30,16 36,16 36,10" />
        </Svg>
      );
    case "UNKNOWN": // a dashed circle and a question mark: honesty over guessing
      return (
        <Svg {...p}>
          <circle cx="24" cy="24" r="19" strokeDasharray={DASH} />
          <path d="M18 19 A6 6 0 1 1 26 24 L24 26 L24 29" />
          <rect x="22" y="33" width="4" height="4" fill="currentColor" stroke="none" />
        </Svg>
      );
  }
}

// --- proximity tier (the Reach in miniature) ----------------------------------------------------

export type ProximityTier = "clear" | "caution" | "danger" | "critical";

export function ProximityGlyph({ tier, ...p }: GlyphProps & { tier: ProximityTier }) {
  const dot = { caution: 20, danger: 14, critical: 0, clear: 0 }[tier];
  return (
    <Svg {...p}>
      <circle cx="24" cy="24" r="21" strokeDasharray={DASH} />
      <circle cx="24" cy="24" r="15" />
      <circle cx="24" cy="24" r="9" />
      {tier === "critical" && (
        <path d="M24 24 L17.6 17 A9 9 0 0 1 30.4 17 Z" fill="currentColor" />
      )}
      {dot > 0 && <circle cx="24" cy={24 - dot + 2} r="3" fill="currentColor" />}
    </Svg>
  );
}

// --- seatbelt ------------------------------------------------------------------------------------

export function BeltGlyph({ fastened, ...p }: GlyphProps & { fastened: boolean }) {
  return (
    <Svg {...p}>
      <path d="M14 44 L14 20 A10 10 0 0 1 34 20 L34 44" />
      <circle cx="24" cy="8" r="5" />
      {fastened ? (
        <>
          <line x1="16" y1="18" x2="32" y2="40" />
          <rect x="21" y="26" width="6" height="6" fill="currentColor" />
        </>
      ) : (
        <>
          <path d="M16 18 L20 26" />
          <line x1="38" y1="30" x2="38" y2="42" />
          <rect x="35" y="42" width="6" height="4" fill="currentColor" />
        </>
      )}
    </Svg>
  );
}

// --- connectivity (a site mast, not a phone signal) ----------------------------------------------

export type NetState = "online" | "offline" | "waiting" | "syncing" | "synced";

export function NetGlyph({ state, ...p }: GlyphProps & { state: NetState }) {
  const arcs = state === "online" || state === "syncing" || state === "waiting";
  const dash = state === "syncing" ? DASH : undefined;
  return (
    <Svg {...p}>
      <line x1="24" y1="18" x2="24" y2="44" />
      <polyline points="16,44 24,30 32,44" />
      {arcs && (
        <>
          <path d="M17 12 A10 10 0 0 0 17 26" strokeDasharray={dash} />
          <path d="M31 12 A10 10 0 0 1 31 26" strokeDasharray={dash} />
          <path d="M11 7 A17 17 0 0 0 11 31" strokeDasharray={dash} />
          <path d="M37 7 A17 17 0 0 1 37 31" strokeDasharray={dash} />
        </>
      )}
      {state === "offline" && (
        <>
          <line x1="8" y1="18" x2="14" y2="18" />
          <line x1="34" y1="18" x2="40" y2="18" />
        </>
      )}
      {state === "waiting" && <rect x="34" y="34" width="10" height="10" fill="currentColor" />}
      {state === "synced" && <polyline points="30,12 36,18 46,6" />}
    </Svg>
  );
}

// --- sensor tier ---------------------------------------------------------------------------------

export function SensorGlyph({
  tier,
  ...p
}: GlyphProps & { tier: "basic" | "standard" | "advanced" }) {
  const filled = { basic: 1, standard: 2, advanced: 3 }[tier];
  return (
    <Svg {...p}>
      {[10, 24, 38].map((cx, i) => (
        <circle key={cx} cx={cx} cy="24" r="5" fill={i < filled ? "currentColor" : "none"} />
      ))}
    </Svg>
  );
}

// --- priority shapes: shape = priority, independent of colour -------------------------------------

export type Priority = "P1" | "P2" | "P3" | "P4";

const PRIORITY_FILL: Record<Priority | "safe", string> = {
  P1: "var(--sm-safety-alert-p1)",
  P2: "var(--sm-safety-alert-p2)",
  P3: "var(--sm-safety-alert-p3)",
  P4: "var(--sm-safety-alert-p4)",
  safe: "var(--sm-safety-safe)",
};

export function PriorityGlyph({ priority, ...p }: GlyphProps & { priority: Priority | "safe" }) {
  const common = { fill: PRIORITY_FILL[priority], stroke: "var(--sm-color-ink)" };
  const mark = (color: string) => ({ stroke: color, fill: "none" });
  switch (priority) {
    case "P1":
      return (
        <Svg {...p}>
          <polygon points="16,3 32,3 45,16 45,32 32,45 16,45 3,32 3,16" {...common} />
          <line x1="12" y1="24" x2="36" y2="24" {...mark("var(--sm-safety-on-danger)")} />
        </Svg>
      );
    case "P2":
      return (
        <Svg {...p}>
          <polygon points="24,3 46,43 2,43" {...common} />
          <line x1="24" y1="17" x2="24" y2="30" {...mark("var(--sm-safety-on-warning)")} />
          <line x1="24" y1="35" x2="24" y2="37" {...mark("var(--sm-safety-on-warning)")} />
        </Svg>
      );
    case "P3":
      return (
        <Svg {...p}>
          <polygon points="24,2 46,24 24,46 2,24" {...common} />
          <line x1="24" y1="14" x2="24" y2="27" {...mark("var(--sm-safety-on-caution)")} />
          <line x1="24" y1="32" x2="24" y2="34" {...mark("var(--sm-safety-on-caution)")} />
        </Svg>
      );
    case "P4":
      return (
        <Svg {...p}>
          <rect x="5" y="5" width="38" height="38" {...common} />
          <line x1="24" y1="20" x2="24" y2="35" {...mark("var(--sm-safety-on-info)")} />
          <line x1="24" y1="13" x2="24" y2="15" {...mark("var(--sm-safety-on-info)")} />
        </Svg>
      );
    case "safe":
      return (
        <Svg {...p}>
          <circle cx="24" cy="24" r="21" {...common} />
          <polyline points="14,24 21,31 34,17" {...mark("var(--sm-safety-on-safe)")} />
        </Svg>
      );
  }
}

// --- conditions ------------------------------------------------------------------------------------

export type Condition = "heat" | "rain" | "wet-ground" | "dark" | "fatigue" | "clock";

export function ConditionGlyph({ condition, ...p }: GlyphProps & { condition: Condition }) {
  switch (condition) {
    case "heat":
      return (
        <Svg {...p}>
          <path d="M20 30 L20 8 A4 4 0 0 1 28 8 L28 30 A8 8 0 1 1 20 30 Z" />
          <circle cx="24" cy="36" r="3" fill="currentColor" />
          <line x1="36" y1="12" x2="44" y2="12" />
          <line x1="36" y1="20" x2="44" y2="20" />
        </Svg>
      );
    case "rain":
      return (
        <Svg {...p}>
          <path d="M12 28 A8 8 0 0 1 14 12 A11 11 0 0 1 35 13 A8 8 0 0 1 36 28 Z" />
          <line x1="16" y1="34" x2="14" y2="42" />
          <line x1="25" y1="34" x2="23" y2="42" />
          <line x1="34" y1="34" x2="32" y2="42" />
        </Svg>
      );
    case "wet-ground":
      return (
        <Svg {...p}>
          <line x1="4" y1="30" x2="44" y2="30" />
          <path d="M8 38 Q14 34 20 38 Q26 42 32 38 Q38 34 44 38" />
          <path d="M24 6 L18 18 A6 6 0 1 0 30 18 Z" />
        </Svg>
      );
    case "dark":
      return (
        <Svg {...p}>
          <path d="M30 6 A18 18 0 1 0 42 32 A14 14 0 0 1 30 6 Z" />
        </Svg>
      );
    case "fatigue":
      return (
        <Svg {...p}>
          <path d="M6 24 Q24 38 42 24" />
          <line x1="12" y1="30" x2="9" y2="35" />
          <line x1="24" y1="33" x2="24" y2="39" />
          <line x1="36" y1="30" x2="39" y2="35" />
          <line x1="30" y1="8" x2="40" y2="8" />
          <polyline points="30,8 40,16 30,16" />
        </Svg>
      );
    case "clock":
      return (
        <Svg {...p}>
          <circle cx="24" cy="24" r="19" />
          <polyline points="24,12 24,24 32,28" />
        </Svg>
      );
  }
}
