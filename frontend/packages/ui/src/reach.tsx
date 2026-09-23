/**
 * The Reach (DESIGN §10 Reach): ShiftMate's one signature element. A plan-view gauge of the
 * machine's working envelope — swing radius (heavy ink), reach + 2 m (solid mark), 2× reach
 * (dashed mark) — with the boom showing the current swing, and the occupied band drawn as a 56°
 * sector: caution yellow in the outer band, warning orange in the middle band, and the 45° hatch
 * only when someone is inside the swing radius. Machines without proximity sensing show the
 * dashed, slashed "no sensing" gauge, never an empty (clear-looking) one.
 */
import { useId } from "react";

import type { ProximityTier } from "./glyphs";

export type ReachProps = {
  tier: ProximityTier;
  /** Where the person is, degrees clockwise from the machine's forward direction. */
  bearing?: number | null;
  /** The boom's current direction, degrees clockwise from forward. */
  boomAngle?: number;
  size?: number;
  /** Spoken/aria text, e.g. "One person, caution ring, right rear, 7 metres". */
  label: string;
  /** Ring radii in metres (swing, reach + 2 m, 2× reach); the drawing keeps their proportions. */
  rings?: { swing: number; danger: number; caution: number };
  noSensing?: boolean;
};

const R_OUT = 92; // drawing units for the 2× reach ring

function polar(r: number, deg: number): [number, number] {
  const a = ((deg - 90) * Math.PI) / 180;
  return [r * Math.cos(a), r * Math.sin(a)];
}

function sector(r0: number, r1: number, bearing: number, width = 56): string {
  const a0 = bearing - width / 2;
  const a1 = bearing + width / 2;
  const [x0, y0] = polar(r1, a0);
  const [x1, y1] = polar(r1, a1);
  const [x2, y2] = polar(r0, a1);
  const [x3, y3] = polar(r0, a0);
  const inner = r0 > 0 ? `L ${x2} ${y2} A ${r0} ${r0} 0 0 0 ${x3} ${y3}` : "L 0 0";
  return `M ${x0} ${y0} A ${r1} ${r1} 0 0 1 ${x1} ${y1} ${inner} Z`;
}

export function Reach({
  tier,
  bearing = null,
  boomAngle = 0,
  size = 148,
  label,
  rings = { swing: 7, danger: 9, caution: 14 },
  noSensing = false,
}: ReachProps) {
  const hatchId = `sm-hatch-${useId().replace(/:/g, "")}`;
  const scale = R_OUT / rings.caution;
  const rSwing = rings.swing * scale;
  const rDanger = rings.danger * scale;
  const ticks = size >= 120;
  const tracks = size >= 200;
  const band: Record<ProximityTier, [number, number] | null> = {
    clear: null,
    caution: [rDanger, R_OUT],
    danger: [rSwing, rDanger],
    critical: [0, rSwing],
  };
  const occupied = band[tier];
  const fill =
    tier === "critical"
      ? `url(#${hatchId})`
      : tier === "danger"
        ? "var(--sm-safety-prox-danger)"
        : "var(--sm-safety-prox-caution)";
  const person =
    occupied && bearing !== null ? polar((occupied[0] + occupied[1]) / 2, bearing) : null;

  return (
    <svg
      viewBox="-100 -100 200 200"
      width={size}
      height={size}
      role="img"
      aria-label={label}
      className="sm-reach shrink-0"
      fill="none"
    >
      <defs>
        <pattern id={hatchId} width="16" height="16" patternUnits="userSpaceOnUse"
          patternTransform="rotate(45)">
          <rect width="16" height="16" fill="var(--sm-safety-hatch)" />
          <rect width="8" height="16" fill="var(--sm-safety-danger)" />
        </pattern>
      </defs>
      <circle r="99" fill="var(--sm-color-surface)" />
      {/* the undercarriage stays fixed and sits under everything else */}
      {tracks && (
        <g fill="var(--sm-color-surface-sunk)" stroke="var(--sm-color-ink)" strokeWidth="3">
          <rect x="-26" y="-22" width="10" height="44" />
          <rect x="16" y="-22" width="10" height="44" />
        </g>
      )}
      {noSensing ? (
        <g stroke="var(--sm-color-mark)" strokeWidth="6">
          <circle r={R_OUT} strokeDasharray="10 8" />
          <line x1="-70" y1="70" x2="70" y2="-70" />
        </g>
      ) : (
        <>
          {ticks &&
            Array.from({ length: 12 }, (_, i) => {
              const [x0, y0] = polar(99, i * 30);
              const [x1, y1] = polar(i % 3 === 0 ? 88 : 93, i * 30);
              return (
                <line key={i} x1={x0} y1={y0} x2={x1} y2={y1}
                  stroke="var(--sm-color-ink)" strokeWidth={i % 3 === 0 ? 4 : 2} />
              );
            })}
          {occupied && bearing !== null && (
            <path d={sector(occupied[0], occupied[1], bearing)} fill={fill}
              stroke="var(--sm-color-ink)" strokeWidth="2" />
          )}
          <circle r={R_OUT} stroke="var(--sm-color-mark)" strokeWidth="3" strokeDasharray="8 6" />
          <circle r={rDanger} stroke="var(--sm-color-mark)" strokeWidth="3" />
          <circle r={rSwing} stroke="var(--sm-color-ink)" strokeWidth="6" />
          {person && (
            <circle cx={person[0]} cy={person[1]} r="7" fill="var(--sm-color-ink)"
              stroke="var(--sm-color-surface)" strokeWidth="3" />
          )}
        </>
      )}
      <g transform={`rotate(${boomAngle})`} stroke="var(--sm-color-ink)">
        <rect x="-12" y="-12" width="24" height="24" fill="var(--sm-color-ink)" strokeWidth="2" />
        <line x1="0" y1="-12" x2="0" y2={-rSwing + 4} strokeWidth="7" />
      </g>
    </svg>
  );
}
