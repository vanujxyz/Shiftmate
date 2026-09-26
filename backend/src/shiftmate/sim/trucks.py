"""Haul trucks, the site dispatcher and its dispatch log (TRD §7.2).

Each loading zone that has a machine doing `truck_loading` gets trucks sent to it at random
(exponential) intervals around `dispatch_mean_interval_min`. A truck drives in along the haul
road, waits in the zone until a machine has loaded it, drives out, spends some minutes off-site
(dumping and returning) and then becomes available again. If every truck is busy, the zone simply
waits — that is a natural truck shortage. On top of that, random shortage windows (1–2 per
site-week, 20–90 min) multiply the dispatch interval by 3.

The dispatch log (assigned / arrived / departed per zone) stands in for the site's truck
management system. Like a real one it is imperfect: entries are logged a little late and a few
are missing. Machines without a truck sensor rely on this log (TRD §6.4), so their "waiting for
truck" classification is honestly less certain.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from shiftmate.schema.config import Site, Zone
from shiftmate.schema.enums import ZoneType
from shiftmate.sim.params import TruckParams

Point = tuple[float, float]


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _path_length(path: list[Point]) -> float:
    return sum(_dist(a, b) for a, b in zip(path, path[1:], strict=False))


def point_along(path: list[Point], fraction: float) -> tuple[Point, float]:
    """Position and heading (deg, 0 = +y / north, clockwise) at a fraction of the path."""
    fraction = min(max(fraction, 0.0), 1.0)
    total = _path_length(path)
    target = fraction * total
    for a, b in zip(path, path[1:], strict=False):
        seg = _dist(a, b)
        if target <= seg or b == path[-1]:
            f = 0.0 if seg == 0 else min(target / seg, 1.0)
            pos = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            heading = math.degrees(math.atan2(b[0] - a[0], b[1] - a[1])) % 360
            return pos, heading
        target -= seg
    return path[-1], 0.0


def route_to_zone(site: Site, zone: Zone) -> list[Point]:
    """Road route from the site entry (far end of the main haul road) to the zone centre."""
    roads = site.layout.zones_of(ZoneType.HAUL_ROAD)
    main = next((r for r in roads if r.id == "HAUL"), roads[0])
    centre = zone.centroid()
    serving = min(
        roads,
        key=lambda r: min(_dist(p, centre) for p in (r.polyline or [])),
    )
    main_line = list(main.polyline or [])
    entry_route = list(reversed(main_line))  # entry is the far end of the main road
    if serving.id == main.id:
        return [*entry_route, centre]
    serving_line = list(serving.polyline or [])
    # orient the serving road so it ends near the zone
    if _dist(serving_line[0], centre) < _dist(serving_line[-1], centre):
        serving_line.reverse()
    junction = serving_line[0]
    # walk the main road from the entry until the point nearest to the junction
    nearest_idx = min(range(len(entry_route)), key=lambda i: _dist(entry_route[i], junction))
    return [*entry_route[: nearest_idx + 1], *serving_line, centre]


@dataclass
class Truck:
    truck_id: str
    state: str = "depot"  # depot | inbound | in_zone | outbound | offsite
    zone_id: str | None = None
    route: list[Point] = field(default_factory=list)
    leg_start: datetime | None = None
    leg_seconds: float = 0.0
    arrived_at: datetime | None = None
    loaded: bool = False
    loading_by: str | None = None
    available_at: datetime | None = None

    def position(self, now: datetime) -> tuple[Point, float] | None:
        """Map position while on site; None when at the depot or off-site."""
        if self.state in ("depot", "offsite") or not self.route:
            return None
        if self.state == "in_zone":
            return self.route[-1], 0.0
        elapsed = (now - self.leg_start).total_seconds() if self.leg_start else 0.0
        fraction = elapsed / self.leg_seconds if self.leg_seconds else 1.0
        if self.state == "outbound":
            fraction = 1.0 - fraction
        return point_along(self.route, fraction)


@dataclass
class DispatchEntry:
    ts: datetime  # when it was logged (may lag the true time)
    true_ts: datetime
    site_id: str
    zone_id: str
    truck_id: str
    event: str  # assigned | arrived | departed


@dataclass
class ShortageWindow:
    start: datetime
    end: datetime


class Dispatcher:
    """Sends trucks to active loading zones and keeps the (imperfect) dispatch log."""

    def __init__(
        self, site: Site, params: TruckParams, rng: np.random.Generator, prefix: str = "TRK"
    ) -> None:
        self.site = site
        self.p = params
        self.rng = rng
        self.trucks = [Truck(f"{prefix}-{i + 1:02d}") for i in range(site.trucks.count)]
        self.routes = {z.id: route_to_zone(site, z) for z in site.layout.zones_of(ZoneType.LOADING)}
        self.next_dispatch: dict[str, datetime] = {}
        self.active_zones: set[str] = set()
        self.shortages: list[ShortageWindow] = []
        self.log: list[DispatchEntry] = []
        self.interval_multiplier_override: dict[str, float] = {}  # scenario hook
        self.blocked: dict[str, datetime] = {}  # scenario hook: zone → no dispatch until

    def block_zone(self, zone_id: str, until: datetime) -> None:
        self.blocked[zone_id] = until

    def positions(self, now: datetime) -> list[dict[str, object]]:
        """Trucks on the site map: id, position, heading, state."""
        out = []
        for t in self.trucks:
            pos = t.position(now)
            if pos is not None:
                (x, y), heading = pos
                out.append(
                    {
                        "id": t.truck_id,
                        "x_m": round(x, 1),
                        "y_m": round(y, 1),
                        "heading_deg": round(heading, 0),
                        "state": "waiting" if t.state == "in_zone" else "moving",
                        "zone_id": t.zone_id,
                    }
                )
        return out

    # --- configuration per day -------------------------------------------------------------
    def set_shortages(self, windows: list[ShortageWindow]) -> None:
        self.shortages = windows

    def set_active_zones(self, zones: set[str], now: datetime) -> None:
        for zone_id in sorted(zones - self.active_zones):  # sorted: set order changes per process
            self.next_dispatch[zone_id] = now + timedelta(seconds=self._draw_interval_s(now))
        self.active_zones = set(zones)

    def _in_shortage(self, now: datetime) -> bool:
        return any(w.start <= now < w.end for w in self.shortages)

    def _draw_interval_s(self, now: datetime, zone_id: str | None = None) -> float:
        mean_min = self.site.trucks.dispatch_mean_interval_min
        if self._in_shortage(now):
            mean_min *= self.site.trucks.shortage_interval_multiplier
        if zone_id and zone_id in self.interval_multiplier_override:
            mean_min *= self.interval_multiplier_override[zone_id]
        return float(self.rng.exponential(mean_min * 60))

    def _log(self, now: datetime, zone_id: str, truck_id: str, event: str) -> None:
        if self.rng.random() < self.p.dispatch_log_missing_prob:
            return
        delay = self.rng.uniform(self.p.dispatch_log_delay_s.min, self.p.dispatch_log_delay_s.max)
        self.log.append(
            DispatchEntry(
                ts=now + timedelta(seconds=float(delay)),
                true_ts=now,
                site_id=self.site.site_id,
                zone_id=zone_id,
                truck_id=truck_id,
                event=event,
            )
        )

    def _travel_seconds(self, zone_id: str) -> float:
        return _path_length(self.routes[zone_id]) / (self.p.speed_kmh / 3.6)

    # --- simulation step ---------------------------------------------------------------------
    def step(self, now: datetime) -> None:
        """Advance truck legs and send new trucks. Call once per world step, before machines."""
        for truck in self.trucks:
            if truck.state == "inbound" and truck.leg_start is not None:
                if (now - truck.leg_start).total_seconds() >= truck.leg_seconds:
                    truck.state = "in_zone"
                    truck.arrived_at = now
                    self._log(now, truck.zone_id or "", truck.truck_id, "arrived")
            elif truck.state == "outbound" and truck.leg_start is not None:
                if (now - truck.leg_start).total_seconds() >= truck.leg_seconds:
                    truck.state = "offsite"
            elif truck.state == "offsite" and truck.available_at and now >= truck.available_at:
                truck.state = "depot"
                truck.zone_id = None
                truck.route = []
        for zone_id in sorted(self.active_zones):
            due = self.next_dispatch.get(zone_id)
            if due is None or now < due:
                continue
            blocked_until = self.blocked.get(zone_id)
            if blocked_until is not None and now < blocked_until:
                continue  # scenario: no trucks for this zone (TRD §8 truck_shortage)
            truck = next((t for t in self.trucks if t.state == "depot"), None)
            if truck is None:
                continue  # no truck free: try again next step (natural shortage)
            truck.state = "inbound"
            truck.zone_id = zone_id
            truck.route = self.routes[zone_id]
            truck.leg_start = now
            truck.leg_seconds = self._travel_seconds(zone_id)
            truck.loaded = False
            truck.loading_by = None
            self._log(now, zone_id, truck.truck_id, "assigned")
            self.next_dispatch[zone_id] = now + timedelta(
                seconds=self._draw_interval_s(now, zone_id)
            )

    # --- machine interface -------------------------------------------------------------------
    def waiting_truck(self, zone_id: str) -> Truck | None:
        """The earliest-arrived truck in the zone that nobody is loading yet."""
        waiting = [
            t
            for t in self.trucks
            if t.state == "in_zone" and t.zone_id == zone_id and not t.loaded and not t.loading_by
        ]
        return min(waiting, key=lambda t: (t.arrived_at, t.truck_id)) if waiting else None

    def truck_in_zone(self, zone_id: str) -> bool:
        return any(t.state == "in_zone" and t.zone_id == zone_id for t in self.trucks)

    def finish_loading(self, truck: Truck, now: datetime) -> None:
        truck.loaded = True
        truck.loading_by = None
        truck.state = "outbound"
        truck.leg_start = now
        truck.leg_seconds = self._travel_seconds(truck.zone_id or "")
        offsite = self.rng.uniform(self.p.offsite_minutes.min, self.p.offsite_minutes.max)
        dump = self.rng.uniform(self.p.dump_minutes.min, self.p.dump_minutes.max)
        truck.available_at = now + timedelta(seconds=truck.leg_seconds + float(offsite + dump) * 60)
        self._log(now, truck.zone_id or "", truck.truck_id, "departed")
