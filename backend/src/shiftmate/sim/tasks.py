"""Daily task plans and productivity (TRD §5.1, §7.2).

Planning: each machine gets 2–4 tasks from its profile, sized from the profile's typical
quantities, until the expected work time fills about 85 % of the shift. `truck_loading` needs a
loading zone of its own, so it is only planned for machines given one that day.

Productivity at any moment = base rate × ground × heat × night × operator skill × task noise
(lognormal, σ 0.08) × any injected low-productivity factor. `actual_duration_min` is whatever
emerges from running the day (D-034: task time excludes scheduled breaks actually taken).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

import numpy as np

from shiftmate.schema.config import MachineProfile, Site
from shiftmate.schema.enums import GroundCondition, TaskStatus, ZoneType
from shiftmate.schema.reference import Task
from shiftmate.sim.params import ProductivityParams, TaskParams


@dataclass
class PlannedTask:
    task: Task
    noise: float  # lognormal task-level productivity noise
    progress: float = 0.0
    work_seconds: float = 0.0  # time counted as task time (excludes breaks)
    work_spot: tuple[float, float] = (0.0, 0.0)
    extras: dict[str, float] = field(default_factory=dict)


def shift_minutes(site: Site) -> float:
    start = site.shift.start.hour * 60 + site.shift.start.minute
    end = site.shift.end.hour * 60 + site.shift.end.minute
    return end - start - sum(b.minutes for b in site.shift.breaks)


def random_point(site: Site, zone_id: str, rng: np.random.Generator) -> tuple[float, float]:
    zone = site.layout.zone(zone_id)
    xs = [p[0] for p in zone.polygon or zone.polyline or []]
    ys = [p[1] for p in zone.polygon or zone.polyline or []]
    return float(rng.uniform(min(xs), max(xs))), float(rng.uniform(min(ys), max(ys)))


def zone_for(task_type: str, site: Site, loading_zone: str | None, rng: np.random.Generator) -> str:
    if task_type == "truck_loading" and loading_zone:
        return loading_zone
    if task_type == "stockpile_moving":
        piles = site.layout.zones_of(ZoneType.STOCKPILE)
        if piles:
            return piles[int(rng.integers(0, len(piles)))].id
    digs = site.layout.zones_of(ZoneType.DIG)
    return digs[int(rng.integers(0, len(digs)))].id


def plan_day(
    *,
    site: Site,
    profile: MachineProfile,
    machine_id: str,
    operator_id: str,
    day: date,
    shift_start: datetime,
    loading_zone: str | None,
    params: TaskParams,
    productivity: ProductivityParams,
    rng: np.random.Generator,
    counter_start: int,
) -> list[PlannedTask]:
    available = shift_minutes(site) * params.fill_fraction
    n_max = int(params.per_day.max)
    n_min = int(params.per_day.min)
    choices = [
        t
        for t in profile.task_types
        if t != "truck_loading" or (loading_zone is not None and profile.tasks[t].truck_dependent)
    ]
    planned: list[PlannedTask] = []
    minutes = params.first_start_offset_min
    total = 0.0
    while len(planned) < n_max and (total < available or len(planned) < n_min):
        # machines with a loading zone mostly load trucks
        if loading_zone and "truck_loading" in choices and rng.random() < 0.7:
            task_type = "truck_loading"
        else:
            others = [c for c in choices if c != "truck_loading"] or choices
            task_type = others[int(rng.integers(0, len(others)))]
        tp = profile.tasks[task_type]
        qty = float(rng.uniform(tp.typical_quantity.min, tp.typical_quantity.max))
        qty = float(round(qty)) if tp.quantity_unit == "loads" else float(round(qty / 5) * 5)
        expected = qty / tp.base_rate_per_h * 60
        if planned and total + expected > available * 1.15:
            # shrink the last task to fit the day
            qty = max(tp.typical_quantity.min / 2, qty * (available - total) / expected)
            qty = float(round(qty)) if tp.quantity_unit == "loads" else float(round(qty / 5) * 5)
            if qty <= 0:
                break
            expected = qty / tp.base_rate_per_h * 60
        zone_id = zone_for(task_type, site, loading_zone, rng)
        n = counter_start + len(planned) + 1
        task = Task(
            task_id=f"T-{site.site_id}-{day:%Y%m%d}-{n}",
            site_id=site.site_id,
            machine_id=machine_id,
            operator_id=operator_id,
            task_type=task_type,
            zone_id=zone_id,
            planned_quantity=qty,
            quantity_unit=tp.quantity_unit,
            scheduled_start=shift_start + timedelta(minutes=minutes),
            status=TaskStatus.SCHEDULED,
        )
        noise = float(rng.lognormal(0.0, productivity.noise_sigma))
        spot = random_point(site, zone_id, rng)
        planned.append(PlannedTask(task=task, noise=noise, work_spot=spot))
        minutes += expected
        total += expected
    return planned


def condition_multiplier(
    productivity: ProductivityParams,
    ground: GroundCondition,
    heat_index_c: float,
    is_night: bool,
) -> float:
    m = productivity.ground[ground]
    if heat_index_c > 46:
        m *= productivity.heat_over_46
    elif heat_index_c > 40:
        m *= productivity.heat_over_40
    if is_night:
        m *= productivity.night
    return m
