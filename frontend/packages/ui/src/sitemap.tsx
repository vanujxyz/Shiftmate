/**
 * ConsoleSiteMap (DESIGN §9 Site map symbology, §10 ConsoleSiteMap): a live top-down drawing of
 * one site at a fixed metres-per-pixel scale (it scrolls, it never squashes). Survey grid every
 * 50 m (heavier every 250 m), haul roads as bands with a dashed centreline, zones as dashed
 * rectangles with a decal label, machines with the Reach ring geometry at map scale (2× reach
 * dashed, reach + 2 m solid, swing radius heavy), the boom line, and a house square whose fill is
 * the state (solid working or moving, open with bars idle, dashed engine off). A person inside a
 * machine's rings shows as the cab's tier sector toward them; the hatch only for critical. Trucks
 * are plan rectangles with a cab block (open waiting, filled moving); people are dots with a halo.
 * North is up; world y grows to the north. Every word arrives through props.
 */
import { type KeyboardEvent, useId } from "react";

import type { ProximityTier } from "./glyphs";

export type MapZone = {
  id: string;
  type: string;
  polygon?: [number, number][] | null;
  polyline?: [number, number][] | null;
};
export type MapMachine = {
  id: string;
  label: string;
  state: "working" | "idle" | "travel" | "off";
  x: number;
  y: number;
  heading: number;
  rings: { caution: number; danger: number; critical: number };
  tier: ProximityTier | null;
  /** Where the nearest person is, degrees clockwise from north, when someone is in the rings. */
  personBearing?: number | null;
};
export type MapTruck = { id: string; x: number; y: number; heading: number; waiting: boolean };
export type MapPerson = { id: string; x: number; y: number };

const PAD = 24;
const ROAD_PX = 30;

function sector(cx: number, cy: number, r0: number, r1: number, bearing: number, width = 56): string {
  const pt = (r: number, deg: number) => {
    const a = ((deg - 90) * Math.PI) / 180;
    return [cx + r * Math.cos(a), cy + r * Math.sin(a)];
  };
  const [x0, y0] = pt(r1, bearing - width / 2);
  const [x1, y1] = pt(r1, bearing + width / 2);
  const [x2, y2] = pt(r0, bearing + width / 2);
  const [x3, y3] = pt(r0, bearing - width / 2);
  const inner = r0 > 0 ? `L ${x2} ${y2} A ${r0} ${r0} 0 0 0 ${x3} ${y3}` : `L ${cx} ${cy}`;
  return `M ${x0} ${y0} A ${r1} ${r1} 0 0 1 ${x1} ${y1} ${inner} Z`;
}

export function ConsoleSiteMap({
  size,
  zones,
  machines,
  trucks,
  people,
  selected,
  onSelect,
  label,
  northLabel,
  scaleLabel,
  metresPerPx = 0.45,
}: {
  size: { w: number; h: number };
  zones: MapZone[];
  machines: MapMachine[];
  trucks: MapTruck[];
  people: MapPerson[];
  selected?: string | null;
  onSelect?: (id: string) => void;
  /** The sentence that says what the map shows ("24 machines, 6 trucks and 14 people on site"). */
  label: string;
  northLabel: string;
  scaleLabel: string;
  metresPerPx?: number;
}) {
  const hatchId = `sm-map-hatch-${useId().replace(/:/g, "")}`;
  const k = 1 / metresPerPx;
  const W = size.w * k + PAD * 2;
  const H = size.h * k + PAD * 2;
  const px = (x: number) => PAD + x * k;
  const py = (y: number) => PAD + (size.h - y) * k;
  const pts = (list: [number, number][]) => list.map(([x, y]) => `${px(x)},${py(y)}`).join(" ");

  const grid: { d: string; heavy: boolean }[] = [];
  for (let x = 0; x <= size.w; x += 50) grid.push({ d: `M ${px(x)} ${py(0)} V ${py(size.h)}`, heavy: x % 250 === 0 });
  for (let y = 0; y <= size.h; y += 50) grid.push({ d: `M ${px(0)} ${py(y)} H ${px(size.w)}`, heavy: y % 250 === 0 });

  const key = (id: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect?.(id);
    }
  };

  return (
    <svg
      role="group"
      aria-label={label}
      viewBox={`0 0 ${W} ${H}`}
      width={W}
      height={H}
      className="block bg-surface"
      fill="none"
    >
      <defs>
        <pattern id={hatchId} width="10" height="10" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <rect width="10" height="10" fill="var(--sm-safety-hatch)" />
          <rect width="5" height="10" fill="var(--sm-safety-danger)" />
        </pattern>
      </defs>

      {/* survey grid */}
      <g aria-hidden>
        {grid.map((g, i) => (
          <path key={i} d={g.d} stroke="var(--sm-color-line-soft)" strokeWidth={g.heavy ? 2 : 1} />
        ))}
      </g>

      {/* haul roads, then zones */}
      <g aria-hidden>
        {zones
          .filter((z) => z.polyline)
          .map((z) => (
            <g key={z.id}>
              <polyline points={pts(z.polyline!)} stroke="var(--sm-color-surface-sunk)" strokeWidth={ROAD_PX} strokeLinejoin="round" />
              <polyline points={pts(z.polyline!)} stroke="var(--sm-color-mark)" strokeWidth="2" strokeDasharray="10 8" />
            </g>
          ))}
        {zones
          .filter((z) => z.polygon)
          .map((z) => {
            const xs = z.polygon!.map((p) => px(p[0]));
            const ys = z.polygon!.map((p) => py(p[1]));
            return (
              <g key={z.id}>
                <polygon points={pts(z.polygon!)} stroke="var(--sm-color-ink)" strokeWidth="2" strokeDasharray="8 6" />
                <text
                  x={Math.min(...xs) + 6}
                  y={Math.min(...ys) + 16}
                  fill="var(--sm-color-ink-2)"
                  className="sm-decal"
                  fontSize="13"
                  fontWeight="700"
                >
                  {z.id}
                </text>
              </g>
            );
          })}
      </g>

      {/* machines: rings, tier sector, boom, house, ID plate */}
      {machines.map((m) => {
        const cx = px(m.x);
        const cy = py(m.y);
        const r = { caution: m.rings.caution * k, danger: m.rings.danger * k, critical: m.rings.critical * k };
        const isSel = m.id === selected;
        const band: Record<ProximityTier, [number, number] | null> = {
          clear: null,
          caution: [r.danger, r.caution],
          danger: [r.critical, r.danger],
          critical: [0, r.critical],
        };
        const occupied = m.tier ? band[m.tier] : null;
        const sectorFill =
          m.tier === "critical"
            ? `url(#${hatchId})`
            : m.tier === "danger"
              ? "var(--sm-safety-prox-danger)"
              : "var(--sm-safety-prox-caution)";
        const a = ((m.heading - 90) * Math.PI) / 180;
        const house = 10;
        return (
          <g
            key={m.id}
            role="button"
            tabIndex={0}
            aria-label={m.label}
            aria-pressed={isSel}
            onClick={() => onSelect?.(m.id)}
            onKeyDown={key(m.id)}
            className="sm-focus cursor-pointer"
          >
            {isSel && <circle cx={cx} cy={cy} r={r.critical} fill="var(--sm-color-surface-sunk)" />}
            {occupied && m.personBearing != null && (
              <path d={sector(cx, cy, occupied[0], occupied[1], m.personBearing)} fill={sectorFill} stroke="var(--sm-color-ink)" strokeWidth="1" />
            )}
            <circle cx={cx} cy={cy} r={r.caution} stroke="var(--sm-color-mark)" strokeWidth="1.5" strokeDasharray="5 4" />
            <circle cx={cx} cy={cy} r={r.danger} stroke="var(--sm-color-mark)" strokeWidth="1.5" />
            <circle cx={cx} cy={cy} r={r.critical} stroke="var(--sm-color-ink)" strokeWidth="3" />
            <line
              x1={cx}
              y1={cy}
              x2={cx + r.critical * Math.cos(a)}
              y2={cy + r.critical * Math.sin(a)}
              stroke="var(--sm-color-ink)"
              strokeWidth="3"
            />
            <g transform={`rotate(${m.heading} ${cx} ${cy})`}>
              <rect
                x={cx - house / 2}
                y={cy - house / 2}
                width={house}
                height={house}
                fill={m.state === "working" || m.state === "travel" ? "var(--sm-color-ink)" : "var(--sm-color-surface)"}
                stroke="var(--sm-color-ink)"
                strokeWidth="2"
                strokeDasharray={m.state === "off" ? "3 2" : undefined}
              />
              {m.state === "idle" && (
                <g stroke="var(--sm-color-ink)" strokeWidth="1.5">
                  <line x1={cx - 2} y1={cy - 3} x2={cx - 2} y2={cy + 3} />
                  <line x1={cx + 2} y1={cy - 3} x2={cx + 2} y2={cy + 3} />
                </g>
              )}
            </g>
            <g transform={`translate(${cx + r.critical * 0.75 + 4} ${cy - r.critical * 0.75 - 4})`}>
              <rect
                x="0"
                y="-13"
                width={m.id.length * 8 + 10}
                height="18"
                fill={isSel ? "var(--sm-color-selected)" : "var(--sm-color-surface)"}
                stroke="var(--sm-color-ink)"
                strokeWidth="1.5"
              />
              <text
                x="5"
                y="1"
                fontSize="12"
                fontWeight="700"
                className="sm-decal"
                fill={isSel ? "var(--sm-color-on-selected)" : "var(--sm-color-ink)"}
              >
                {m.id}
              </text>
            </g>
          </g>
        );
      })}

      {/* trucks and people */}
      <g aria-hidden>
        {trucks.map((t) => {
          const cx = px(t.x);
          const cy = py(t.y);
          return (
            <g key={t.id}>
              <g transform={`rotate(${t.heading} ${cx} ${cy})`}>
                <rect x={cx - 5} y={cy - 7} width="10" height="12" fill={t.waiting ? "var(--sm-color-surface)" : "var(--sm-color-ink)"} stroke="var(--sm-color-ink)" strokeWidth="1.5" />
                <rect x={cx - 5} y={cy - 12} width="10" height="5" fill="var(--sm-color-ink)" />
              </g>
              <text x={cx + 9} y={cy + 4} fontSize="11" fill="var(--sm-color-ink-2)" className="sm-num">
                {t.id}
              </text>
            </g>
          );
        })}
        {people.map((p) => (
          <circle key={p.id} cx={px(p.x)} cy={py(p.y)} r="2.5" fill="var(--sm-color-ink)" stroke="var(--sm-color-surface)" strokeWidth="2" />
        ))}
      </g>

      {/* north arrow and the 50 m scale bar, always visible */}
      <g aria-hidden transform={`translate(${W - PAD - 18} ${PAD + 6})`}>
        <path d="M 0 24 L 8 0 L 16 24 L 8 18 Z" fill="var(--sm-color-ink)" />
        <text x="8" y="40" fontSize="11" textAnchor="middle" fill="var(--sm-color-ink)">
          {northLabel}
        </text>
      </g>
      <g aria-hidden transform={`translate(${W - PAD - 50 * k} ${H - PAD / 2 - 4})`}>
        <path d={`M 0 -6 V 0 H ${50 * k} V -6`} stroke="var(--sm-color-ink)" strokeWidth="2" />
        <text x={(50 * k) / 2} y="-9" fontSize="11" textAnchor="middle" fill="var(--sm-color-ink)">
          {scaleLabel}
        </text>
      </g>
    </svg>
  );
}
