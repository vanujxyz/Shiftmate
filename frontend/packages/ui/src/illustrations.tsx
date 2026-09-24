/**
 * Lesson, checklist and drill illustrations (DESIGN §6, D-014): drawn in-house from a few plan-view
 * parts — the machine, a truck, a person, the swing ring, a clock, water, light — on a 160 × 100
 * grid, `currentColor`, square caps, the glyph stroke. A person in danger is the only filled
 * shape. Names come from config (`illustration:` and drill `scene:`); an unknown name draws the
 * machine alone rather than nothing.
 */
import type { ReactNode } from "react";

type P = { x: number; y: number };

const Exc = ({ x, y, r = 0, arm = 26, off = false }: P & { r?: number; arm?: number; off?: boolean }) => (
  <g transform={`translate(${x} ${y}) rotate(${r})`} strokeDasharray={off ? "4 4" : undefined}>
    <rect x={-16} y={-14} width={7} height={28} />
    <rect x={9} y={-14} width={7} height={28} />
    <rect x={-8} y={-8} width={16} height={16} />
    <line x1={0} y1={-8} x2={0} y2={-8 - arm} />
    <rect x={-4} y={-14 - arm} width={8} height={6} />
  </g>
);

const Truck = ({ x, y, r = 0 }: P & { r?: number }) => (
  <g transform={`translate(${x} ${y}) rotate(${r})`}>
    <rect x={-9} y={-22} width={18} height={10} />
    <rect x={-10} y={-10} width={20} height={32} />
  </g>
);

const Person = ({ x, y, danger = false }: P & { danger?: boolean }) => (
  <g>
    <circle cx={x} cy={y} r={5} fill={danger ? "currentColor" : "none"} />
    <line x1={x - 8} y1={y + 9} x2={x + 8} y2={y + 9} />
  </g>
);

const Ring = ({ x, y, r }: P & { r: number }) => <circle cx={x} cy={y} r={r} strokeDasharray="6 5" />;

const Clock = ({ x, y }: P) => (
  <g>
    <circle cx={x} cy={y} r={14} />
    <polyline points={`${x},${y - 9} ${x},${y} ${x + 7},${y + 4}`} />
  </g>
);

const Drop = ({ x, y }: P) => <path d={`M${x} ${y - 14} L${x + 9} ${y + 2} A9 9 0 1 1 ${x - 9} ${y + 2} Z`} />;

const Sun = ({ x, y }: P) => (
  <g>
    <circle cx={x} cy={y} r={8} />
    {[0, 45, 90, 135, 180, 225, 270, 315].map((a) => (
      <line key={a} x1={x} y1={y - 12} x2={x} y2={y - 17} transform={`rotate(${a} ${x} ${y})`} />
    ))}
  </g>
);

const Moon = ({ x, y }: P) => <path d={`M${x + 4} ${y - 12} A12 12 0 1 0 ${x + 10} ${y + 8} A9 9 0 1 1 ${x + 4} ${y - 12} Z`} />;

const Arrow = ({ x1, y1, x2, y2 }: { x1: number; y1: number; x2: number; y2: number }) => {
  const a = Math.atan2(y2 - y1, x2 - x1);
  const h = (d: number) => `${x2 - 7 * Math.cos(a + d)},${y2 - 7 * Math.sin(a + d)}`;
  return (
    <g>
      <line x1={x1} y1={y1} x2={x2} y2={y2} />
      <polyline points={`${h(0.5)} ${x2},${y2} ${h(-0.5)}`} />
    </g>
  );
};

const Cross = ({ x, y }: P) => (
  <g>
    <line x1={x - 8} y1={y - 8} x2={x + 8} y2={y + 8} />
    <line x1={x + 8} y1={y - 8} x2={x - 8} y2={y + 8} />
  </g>
);

const Tick = ({ x, y }: P) => <polyline points={`${x - 9},${y} ${x - 3},${y + 7} ${x + 10},${y - 8}`} />;

const Key = ({ x, y }: P) => (
  <g>
    <circle cx={x - 8} cy={y} r={6} />
    <polyline points={`${x - 2},${y} ${x + 14},${y} ${x + 14},${y + 5}`} />
    <line x1={x + 8} y1={y} x2={x + 8} y2={y + 5} />
  </g>
);

const Buckle = ({ x, y, open = false }: P & { open?: boolean }) => (
  <g>
    <line x1={x - 24} y1={y} x2={x - 6} y2={y} />
    <rect x={x - 6} y={y - 6} width={12} height={12} />
    <line x1={x + (open ? 12 : 6)} y1={y} x2={x + 24} y2={y} />
  </g>
);

const Lamp = ({ x, y }: P) => (
  <g>
    <circle cx={x} cy={y} r={5} />
    <line x1={x + 8} y1={y - 6} x2={x + 26} y2={y - 14} />
    <line x1={x + 9} y1={y} x2={x + 28} y2={y} />
    <line x1={x + 8} y1={y + 6} x2={x + 26} y2={y + 14} />
  </g>
);

const Edge = ({ y }: { y: number }) => (
  <g>
    <line x1={8} y1={y} x2={152} y2={y} />
    {Array.from({ length: 12 }, (_, i) => (
      <line key={i} x1={14 + i * 12} y1={y} x2={8 + i * 12} y2={y + 8} />
    ))}
  </g>
);

const Wire = ({ y }: { y: number }) => (
  <g>
    <line x1={10} y1={y} x2={150} y2={y} strokeDasharray="10 4" />
    <rect x={8} y={y - 4} width={6} height={8} fill="currentColor" />
    <rect x={146} y={y - 4} width={6} height={8} fill="currentColor" />
  </g>
);

const Cone = ({ x, y }: P) => <polygon points={`${x},${y - 9} ${x + 7},${y + 7} ${x - 7},${y + 7}`} />;

const Fuel = ({ x, y }: P) => (
  <g>
    <rect x={x - 9} y={y - 10} width={18} height={22} />
    <line x1={x - 4} y1={y - 14} x2={x + 4} y2={y - 14} />
    <Drop x={x} y={y + 2} />
  </g>
);

const Mirror = ({ x, y }: P) => (
  <g>
    <rect x={x - 8} y={y - 11} width={16} height={22} rx={3} />
    <line x1={x} y1={y + 11} x2={x} y2={y + 18} />
  </g>
);

const Eye = ({ x, y }: P) => (
  <g>
    <path d={`M${x - 16} ${y} Q${x} ${y - 13} ${x + 16} ${y} Q${x} ${y + 13} ${x - 16} ${y} Z`} />
    <circle cx={x} cy={y} r={4} />
  </g>
);

const Extinguisher = ({ x, y }: P) => (
  <g>
    <rect x={x - 6} y={y - 10} width={12} height={24} rx={3} />
    <polyline points={`${x},${y - 10} ${x},${y - 15} ${x + 10},${y - 17}`} />
  </g>
);

const Pile = ({ x, y }: P) => <path d={`M${x - 18} ${y + 8} Q${x} ${y - 16} ${x + 18} ${y + 8} Z`} />;

const Slope = () => (
  <g>
    <line x1={10} y1={88} x2={150} y2={30} />
    <line x1={10} y1={88} x2={150} y2={88} />
  </g>
);

const Rest = ({ x, y }: P) => (
  <g>
    <Person x={x} y={y} />
    <line x1={x - 14} y1={y + 16} x2={x + 14} y2={y + 16} />
  </g>
);

const SCENES: Record<string, () => ReactNode> = {
  "bucket-lowered": () => <><Exc x={60} y={58} /><Arrow x1={100} y1={24} x2={100} y2={62} /><line x1={84} y1={70} x2={116} y2={70} /></>,
  "controls-locked": () => <><rect x={48} y={30} width={24} height={40} /><rect x={88} y={30} width={24} height={40} /><Key x={78} y={84} /></>,
  "cab-exit-idle": () => <><Exc x={56} y={56} /><Person x={112} y={60} /><Arrow x1={82} y1={60} x2={100} y2={60} /></>,
  "fuel-saved": () => <><Fuel x={60} y={52} /><Tick x={104} y={52} /></>,
  "engine-idle": () => <><Exc x={60} y={56} /><Clock x={116} y={46} /></>,
  "key-off": () => <><Key x={70} y={50} /><Cross x={116} y={50} /></>,
  "plan-next-cut": () => <><Exc x={50} y={56} /><path d="M92 34 L140 34 L140 76 L92 76 Z" strokeDasharray="6 5" /><Arrow x1={72} y1={56} x2={90} y2={56} /></>,
  "belt-buckle": () => <Buckle x={80} y={50} />,
  "rops-frame": () => <><rect x={48} y={20} width={64} height={60} /><Person x={80} y={48} /></>,
  "hold-on": () => <><rect x={48} y={20} width={64} height={60} /><Person x={80} y={48} /><line x1={64} y1={66} x2={96} y2={66} /></>,
  "belt-check": () => <><Buckle x={70} y={50} /><Eye x={126} y={50} /></>,
  "swing-radius": () => <><Ring x={80} y={50} r={40} /><Exc x={80} y={56} arm={18} /></>,
  "person-in-zone": () => <><Ring x={70} y={50} r={40} /><Exc x={70} y={56} arm={18} /><Person x={100} y={30} danger /></>,
  "no-cab-swing": () => <><Truck x={116} y={50} /><Exc x={50} y={56} r={90} arm={22} /><Cross x={116} y={26} /></>,
  "cones-zone": () => <><Ring x={80} y={50} r={36} /><Cone x={36} y={50} /><Cone x={124} y={50} /><Cone x={80} y={16} /><Cone x={80} y={84} /></>,
  "spotter-meet": () => <><Person x={60} y={50} /><Person x={100} y={50} /><line x1={70} y1={50} x2={90} y2={50} strokeDasharray="4 4" /></>,
  "spotter-lost": () => <><Exc x={60} y={56} /><Person x={126} y={40} /><Cross x={100} y={40} /></>,
  "heat-break": () => <><Sun x={50} y={40} /><Drop x={100} y={50} /><Clock x={134} y={50} /></>,
  "water-cup": () => <><path d="M64 26 L96 26 L90 80 L70 80 Z" /><Drop x={80} y={52} /></>,
  "shade-rest": () => <><Sun x={34} y={28} /><line x1={70} y1={30} x2={140} y2={30} /><line x1={105} y1={30} x2={105} y2={84} /><Rest x={112} y={58} /></>,
  "cab-cool": () => <><rect x={48} y={20} width={64} height={60} /><Arrow x1={60} y1={36} x2={100} y2={36} /><Arrow x1={100} y1={62} x2={60} y2={62} /></>,
  "clock-wet": () => <><Clock x={60} y={50} /><Drop x={104} y={50} /></>,
  "slope-slow": () => <><Slope /><Exc x={80} y={50} r={-22} /></>,
  "trench-edge": () => <><Edge y={30} /><Exc x={80} y={66} arm={14} /></>,
  "under-check": () => <><Exc x={60} y={50} /><Eye x={116} y={78} /><Drop x={60} y={84} /></>,
  "night-look": () => <><Moon x={30} y={30} /><Eye x={100} y={50} /></>,
  "work-lights": () => <><Exc x={50} y={56} /><Lamp x={78} y={40} /></>,
  "torch-walk": () => <><Person x={50} y={50} /><Lamp x={60} y={50} /><Moon x={130} y={24} /></>,
  "night-break": () => <><Moon x={46} y={40} /><Clock x={110} y={50} /></>,
  "truck-angle": () => <><Exc x={50} y={56} r={60} arm={22} /><Truck x={110} y={50} r={20} /></>,
  "prep-pile": () => <><Pile x={50} y={56} /><Exc x={110} y={56} r={-90} arm={20} /></>,
  "even-load": () => <><Truck x={80} y={50} r={90} /><Pile x={80} y={52} /></>,
  "mirror-check": () => <><Mirror x={60} y={46} /><Eye x={110} y={50} /></>,
  "walkaround": () => <><Exc x={80} y={56} /><path d="M40 16 L120 16 L120 94 L40 94 Z" strokeDasharray="6 5" /><Person x={40} y={50} /></>,
  "tired-eyes": () => <><Eye x={80} y={46} /><line x1={60} y1={66} x2={100} y2={66} /></>,
  "break-clock": () => <><Clock x={60} y={50} /><Rest x={112} y={48} /></>,
  "walk-water": () => <><Person x={60} y={50} /><Drop x={110} y={50} /></>,
  "clean-steps": () => <><line x1={50} y1={80} x2={80} y2={80} /><line x1={80} y1={80} x2={80} y2={60} /><line x1={80} y1={60} x2={110} y2={60} /><line x1={110} y1={60} x2={110} y2={40} /><Tick x={132} y={30} /></>,
  "check-tracks": () => <><rect x={50} y={20} width={14} height={60} /><rect x={96} y={20} width={14} height={60} /><Eye x={80} y={88} /></>,
  "check-leaks": () => <><Exc x={80} y={46} /><Drop x={80} y={84} /></>,
  "check-lights": () => <><Lamp x={60} y={50} /><Tick x={120} y={50} /></>,
  "check-mirrors": () => <><Mirror x={60} y={50} /><Tick x={110} y={50} /></>,
  "check-belt": () => <><Buckle x={70} y={50} /><Tick x={124} y={50} /></>,
  "check-extinguisher": () => <><Extinguisher x={70} y={52} /><Tick x={110} y={50} /></>,
  "check-area": () => <><Ring x={80} y={50} r={40} /><Exc x={80} y={56} arm={18} /><Tick x={130} y={20} /></>,
  "drill-intro": () => <><Ring x={80} y={50} r={40} /><Exc x={80} y={56} arm={18} /><Person x={112} y={24} /></>,
  // drill scenes: five hazards and two safe scenes (D-032)
  "swing-worker": () => <><Ring x={70} y={50} r={40} /><Exc x={70} y={56} r={30} arm={20} /><Person x={100} y={44} danger /></>,
  "truck-reversing": () => <><Truck x={80} y={40} r={180} /><Arrow x1={80} y1={70} x2={80} y2={92} /><Person x={112} y={82} danger /></>,
  "ground-edge": () => <><Edge y={24} /><Exc x={80} y={44} arm={10} /><Arrow x1={80} y1={78} x2={80} y2={62} /></>,
  "overhead-line": () => <><Wire y={22} /><Exc x={80} y={70} arm={36} /></>,
  "worker-behind": () => <><Exc x={80} y={40} /><Person x={80} y={80} danger /></>,
  "truck-parked": () => <><Exc x={50} y={56} r={60} arm={22} /><Truck x={120} y={50} /></>,
  "spotter-clear": () => <><Exc x={60} y={56} /><Person x={130} y={40} /><Tick x={130} y={70} /></>,
};

export const ILLUSTRATIONS = Object.keys(SCENES);

export function Illustration({ name, label, className }: { name: string; label?: string; className?: string }) {
  const draw = SCENES[name] ?? (() => <Exc x={80} y={56} />);
  return (
    <svg
      viewBox="0 0 160 100"
      role={label ? "img" : undefined}
      aria-label={label}
      aria-hidden={label ? undefined : true}
      className={`sm-glyph h-full w-full ${className ?? ""}`}
      fill="none"
      stroke="currentColor"
      strokeLinecap="square"
      strokeLinejoin="miter"
      data-illustration={name}
    >
      {draw()}
    </svg>
  );
}
