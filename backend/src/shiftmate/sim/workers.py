"""Site workers and their approaches to machines (TRD §7.2).

Workers wander between zones at walking pace. Separately, each running machine has random
"approach" events (Poisson in engine-on time): a free worker walks to a start point about 18 m
from the machine, walks straight in to a closest distance, pauses briefly and walks away. The
closest distance is drawn evenly from the caution, danger and critical bands of the machine
profile, so entries into the swing radius happen at the site's `swing_entry_prob_per_h` and the
wider bands proportionally more often. The machine's proximity sensor (advanced tier) then sees
the real geometric distance to the nearest person.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from shiftmate.schema.config import ProximityDistances, Site
from shiftmate.schema.enums import ZoneType
from shiftmate.sim.params import WorkerParams

Point = tuple[float, float]


@dataclass
class Approach:
    machine_id: str
    bearing_deg: float  # world bearing from the machine to the start point
    min_distance_m: float
    duration_s: float  # time from the start point, in and back out
    elapsed_s: float = 0.0
    walking_in: bool = True  # walking to the start point first


@dataclass
class Worker:
    worker_id: str
    x: float
    y: float
    target: Point
    approach: Approach | None = None


def draw_min_distance(distances: ProximityDistances, rng: np.random.Generator) -> float:
    band = int(rng.integers(0, 3))
    if band == 0:
        return float(rng.uniform(1.0, distances.critical))
    if band == 1:
        return float(rng.uniform(distances.critical, distances.danger))
    return float(rng.uniform(distances.danger, distances.caution))


class WorkerCrowd:
    def __init__(self, site: Site, params: WorkerParams, rng: np.random.Generator) -> None:
        self.site = site
        self.p = params
        self.rng = rng
        self.zones = [
            z for z in site.layout.zones if z.type != ZoneType.HAUL_ROAD and z.polygon is not None
        ]
        self.workers = []
        for i in range(site.workers.count):
            x, y = self._random_point()
            self.workers.append(Worker(f"W-{i + 1:02d}", x, y, self._random_point()))

    def _random_point(self) -> Point:
        zone = self.zones[int(self.rng.integers(0, len(self.zones)))]
        xs = [p[0] for p in zone.polygon or []]
        ys = [p[1] for p in zone.polygon or []]
        return float(self.rng.uniform(min(xs), max(xs))), float(self.rng.uniform(min(ys), max(ys)))

    def start_approach(
        self, machine_id: str, distances: ProximityDistances, fixed: Approach | None = None
    ) -> bool:
        """Send a free worker towards a machine. Returns False if nobody is free."""
        free = [w for w in self.workers if w.approach is None]
        if not free:
            return False
        worker = free[int(self.rng.integers(0, len(free)))]
        worker.approach = fixed or Approach(
            machine_id=machine_id,
            bearing_deg=float(self.rng.uniform(0, 360)),
            min_distance_m=draw_min_distance(distances, self.rng),
            duration_s=float(self.rng.uniform(self.p.approach_s.min, self.p.approach_s.max)),
        )
        return True

    def step(self, dt: float, machine_positions: dict[str, Point]) -> None:
        speed = self.p.walk_speed_mps
        for w in self.workers:
            a = w.approach
            if a is not None and a.machine_id in machine_positions:
                mx, my = machine_positions[a.machine_id]
                rad = math.radians(a.bearing_deg)
                if a.walking_in:
                    sx = mx + self.p.start_distance_m * math.sin(rad)
                    sy = my + self.p.start_distance_m * math.cos(rad)
                    if self._walk_to(w, (sx, sy), speed * dt):
                        a.walking_in = False
                    continue
                a.elapsed_s += dt
                if a.elapsed_s >= a.duration_s:
                    w.approach = None
                    w.target = self._random_point()
                    continue
                # in over the first 40 %, pause for 20 %, out over the last 40 %
                f = a.elapsed_s / a.duration_s
                if f < 0.4:
                    k = f / 0.4
                elif f < 0.6:
                    k = 1.0
                else:
                    k = 1.0 - (f - 0.6) / 0.4
                d = self.p.start_distance_m - k * (self.p.start_distance_m - a.min_distance_m)
                w.x, w.y = mx + d * math.sin(rad), my + d * math.cos(rad)
            else:
                if a is not None:  # machine gone (engine off): give up
                    w.approach = None
                if self._walk_to(w, w.target, speed * dt):
                    w.target = self._random_point()

    @staticmethod
    def _walk_to(w: Worker, target: Point, step: float) -> bool:
        dx, dy = target[0] - w.x, target[1] - w.y
        d = math.hypot(dx, dy)
        if d <= step:
            w.x, w.y = target
            return True
        w.x += dx / d * step
        w.y += dy / d * step
        return False

    def nearest(self, pos: Point, heading_deg: float) -> tuple[float, float] | None:
        """Distance and bearing (relative to the machine heading) of the nearest person."""
        best: tuple[float, float] | None = None
        for w in self.workers:
            d = math.hypot(w.x - pos[0], w.y - pos[1])
            if best is None or d < best[0]:
                world = math.degrees(math.atan2(w.x - pos[0], w.y - pos[1])) % 360
                best = (d, (world - heading_deg) % 360)
        return best
