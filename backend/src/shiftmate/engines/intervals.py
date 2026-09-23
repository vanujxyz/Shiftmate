"""Interval builder: ticks → interval records in the brief's format (TRD §5.3, §6.5).

An interval closes at every quarter hour of machine time (xx:00, :15, :30, :45) and whenever the
active task changes, and summarises the time since the previous close (D-002). Intervals with no
engine-on time are skipped. The brief's nine columns:
- Engine Hours — hour meter at the end (1 decimal)
- Fuel Used (L) — Σ fuel rate × tick time
- Load Cycles — increase of the machine's cycle counter (D-001, D-035)
- Idling Time (min) — ticks in state IDLE
- Seatbelt Status — at the end of the interval
- Safety Alert Triggered — Yes if any P1/P2 rule was raised in the interval (D-003)
plus the extension fields (working/travel minutes, conditions, proximity counts, idle minutes by
reason, fuel per load cycle, max risk score, …). Idle minutes by reason use each segment's final
reason when it closed inside the interval, otherwise its provisional reason at the interval end.
Pure: no clock reads, no I/O.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from shiftmate.schema.enums import (
    IdleReason,
    MachineState,
    MachineType,
    SeatbeltStatus,
    SensorTier,
    YesNo,
)
from shiftmate.schema.intervals import IntervalRecord
from shiftmate.util.ids import interval_record_id

IDLE_FIELD = {
    IdleReason.WARM_UP: "idle_warmup_min",
    IdleReason.SCHEDULED_BREAK: "idle_break_min",
    IdleReason.WAITING_FOR_TRUCK: "idle_truck_wait_min",
    IdleReason.UNATTENDED_RUNNING: "idle_unattended_min",
    IdleReason.HABIT: "idle_habit_min",
    IdleReason.UNKNOWN: "idle_unknown_min",
}
PROXIMITY_RULES = {
    "PROXIMITY_CAUTION": "proximity_caution_count",
    "PROXIMITY_DANGER": "proximity_danger_count",
    "PROXIMITY_CRITICAL": "proximity_critical_count",
}


@dataclass
class IntervalTick:
    """What the builder needs from one tick plus the other engines' outputs for it."""

    ts: datetime
    dt: float
    operator_id: str | None
    task_id: str | None
    task_type: str | None
    state: MachineState
    engine_on: bool
    engine_hours: float
    fuel_rate_lph: float
    load_cycles_total: int
    seatbelt_fastened: bool
    seat_occupied: bool | None
    engine_rpm: float | None
    travel_speed_kmh: float
    truck_present: bool | None
    truck_known: bool  # truck presence is known (sensor or dispatch log)
    truck_sensor: bool  # it comes from a sensor (advanced tier)
    proximity_m: float | None
    ambient_temp_c: float
    relative_humidity_pct: float
    heat_index_c: float
    precipitation_mm_h: float
    wind_kmh: float
    visibility_m: float
    is_night: bool
    ground_condition: str
    continuous_operation_min: float
    coolant_temp_c: float | None
    task_progress_qty: float
    risk_score: int
    raised_rules: list[tuple[str, str]]  # (rule_id, priority) raised on this tick
    idle_segment_start: datetime | None  # the open idle segment this tick belongs to


@dataclass
class _Acc:
    start: datetime
    task_id: str | None = None
    task_type: str | None = None
    operator_id: str | None = None
    seconds: float = 0.0
    engine_on_s: float = 0.0
    working_s: float = 0.0
    travel_s: float = 0.0
    idle_s: float = 0.0
    seat_s: float = 0.0
    seat_known: bool = True
    belt_off_working_s: float = 0.0
    rpm_sum: float = 0.0
    rpm_n: int = 0
    max_speed: float = 0.0
    truck_present_s: float = 0.0
    truck_wait_s: float = 0.0
    truck_sensor: bool = False
    min_prox: float | None = None
    counts: Counter = field(default_factory=Counter)
    fuel_l: float = 0.0
    cycles_start: int | None = None
    cycles_end: int = 0
    progress_start: float | None = None
    progress_end: float = 0.0
    sums: Counter = field(default_factory=Counter)
    precip_mm: float = 0.0
    night_s: float = 0.0
    grounds: Counter = field(default_factory=Counter)
    coolant_min: float | None = None
    alert: bool = False
    risk_max: int = 0
    idle_by_segment: dict[datetime, float] = field(default_factory=dict)
    last: IntervalTick | None = None


class IntervalBuilder:
    def __init__(
        self,
        machine_id: str,
        site_id: str,
        machine_type: MachineType,
        tier: SensorTier,
        truck_dependent_task_types: list[str],
        minutes: int = 15,
    ) -> None:
        self.machine_id = machine_id
        self.site_id = site_id
        self.machine_type = machine_type
        self.tier = tier
        self.truck_tasks = set(truck_dependent_task_types)
        self.minutes = minutes
        self.acc: _Acc | None = None
        self.segment_reasons: dict[datetime, IdleReason] = {}  # closed segments → final reason
        self.incidents = 0
        self.near_misses = 0

    def _boundary(self, ts: datetime) -> datetime:
        """Next quarter-hour boundary strictly after ts."""
        base = ts.replace(
            minute=(ts.minute // self.minutes) * self.minutes, second=0, microsecond=0
        )
        return base + timedelta(minutes=self.minutes)

    def record_segment(self, start: datetime, reason: IdleReason) -> None:
        self.segment_reasons[start] = reason

    def record_report(self, kind: str) -> None:
        if kind == "incident":
            self.incidents += 1
        elif kind == "near_miss":
            self.near_misses += 1

    def add(
        self, t: IntervalTick, provisional_reason: IdleReason | None = None
    ) -> list[IntervalRecord]:
        """Add a tick. Returns intervals closed before this tick (zero or one)."""
        closed: list[IntervalRecord] = []
        acc = self.acc
        if acc is not None and (t.ts >= self._boundary(acc.start) or t.task_id != acc.task_id):
            record = self.close(t.ts, provisional_reason, next_tick=t)
            if record:
                closed.append(record)
        if self.acc is None:
            self.acc = _Acc(start=t.ts, task_id=t.task_id, task_type=t.task_type)
        self._accumulate(self.acc, t)
        return closed

    def _accumulate(self, a: _Acc, t: IntervalTick) -> None:
        dt = t.dt
        a.seconds += dt
        a.last = t
        if t.operator_id:
            a.operator_id = t.operator_id
        if t.engine_on:
            a.engine_on_s += dt
        if t.state == MachineState.WORKING:
            a.working_s += dt
        elif t.state == MachineState.TRAVELLING:
            a.travel_s += dt
        elif t.state == MachineState.IDLE:
            a.idle_s += dt
            if t.idle_segment_start is not None:
                a.idle_by_segment[t.idle_segment_start] = (
                    a.idle_by_segment.get(t.idle_segment_start, 0.0) + dt
                )
        if t.seat_occupied is None:
            a.seat_known = False
        elif t.seat_occupied:
            a.seat_s += dt
        if not t.seatbelt_fastened and t.state in (MachineState.WORKING, MachineState.TRAVELLING):
            a.belt_off_working_s += dt
        if t.engine_rpm is not None and t.engine_on:
            a.rpm_sum += t.engine_rpm
            a.rpm_n += 1
        a.max_speed = max(a.max_speed, t.travel_speed_kmh)
        if t.truck_sensor:
            a.truck_sensor = True
            if t.truck_present:
                a.truck_present_s += dt
        if (
            t.task_type in self.truck_tasks
            and t.state == MachineState.IDLE
            and t.truck_known
            and not t.truck_present
        ):
            a.truck_wait_s += dt
        if t.proximity_m is not None:
            a.min_prox = t.proximity_m if a.min_prox is None else min(a.min_prox, t.proximity_m)
        for rule_id, priority in t.raised_rules:
            if rule_id in PROXIMITY_RULES:
                a.counts[PROXIMITY_RULES[rule_id]] += 1
            if priority in ("P1", "P2"):
                a.alert = True
        a.fuel_l += t.fuel_rate_lph * dt / 3600
        if a.cycles_start is None:
            a.cycles_start = t.load_cycles_total
        a.cycles_end = t.load_cycles_total
        if a.progress_start is None:
            a.progress_start = t.task_progress_qty
        a.progress_end = t.task_progress_qty
        for name in (
            "ambient_temp_c",
            "relative_humidity_pct",
            "heat_index_c",
            "wind_kmh",
            "visibility_m",
        ):
            a.sums[name] += getattr(t, name) * dt
        a.precip_mm += t.precipitation_mm_h * dt / 3600
        if t.is_night:
            a.night_s += dt
        a.grounds[t.ground_condition] += dt
        if t.coolant_temp_c is not None:
            a.coolant_min = (
                t.coolant_temp_c if a.coolant_min is None else min(a.coolant_min, t.coolant_temp_c)
            )
        a.risk_max = max(a.risk_max, t.risk_score)

    def close(
        self,
        end: datetime,
        provisional_reason: IdleReason | None = None,
        next_tick: IntervalTick | None = None,
    ) -> IntervalRecord | None:
        """Close the open interval at `end`. `next_tick` (the first tick after it) gives exact
        end readings of the counters; without it (end of day) the last tick's values are used."""
        a = self.acc
        self.acc = None
        if a is None or a.engine_on_s <= 0 or a.last is None or a.operator_id is None:
            return None
        last = a.last
        idle_min = dict.fromkeys(IDLE_FIELD.values(), 0.0)
        for seg_start, seconds in a.idle_by_segment.items():
            reason = self.segment_reasons.get(seg_start, provisional_reason)
            if reason is not None:
                idle_min[IDLE_FIELD[reason]] += seconds / 60
        # Counters are read at the start of each tick, so work done during the last tick shows
        # on the next one. Use the next tick when we have it (same task), else the last tick.
        same_task = next_tick is not None and next_tick.task_id == a.task_id
        cycles_end = next_tick.load_cycles_total if next_tick is not None else a.cycles_end
        if same_task and next_tick is not None:
            a.progress_end = next_tick.task_progress_qty
        cycles = max(0, cycles_end - (a.cycles_start or 0))
        fuel = round(a.fuel_l, 1)
        engine_on_min = a.engine_on_s / 60
        hours_end = (
            next_tick.engine_hours
            if next_tick is not None
            else last.engine_hours + (last.dt / 3600 if last.engine_on else 0.0)
        )
        record = IntervalRecord(
            timestamp=end,
            machine_id=self.machine_id,
            operator_id=a.operator_id,
            engine_hours=round(hours_end, 1),
            fuel_used_l=fuel,
            load_cycles=cycles,
            idling_time_min=int(round(a.idle_s / 60)),
            seatbelt_status=SeatbeltStatus.FASTENED
            if last.seatbelt_fastened
            else SeatbeltStatus.UNFASTENED,
            safety_alert_triggered=YesNo.YES if a.alert else YesNo.NO,
            record_id=interval_record_id(self.machine_id, end),
            interval_start=a.start,
            interval_minutes=round(a.seconds / 60, 2),
            site_id=self.site_id,
            machine_type=self.machine_type,
            sensor_tier=self.tier,
            task_id=a.task_id,
            task_type=a.task_type,
            engine_on_min=round(engine_on_min, 2),
            working_min=round(a.working_s / 60, 2),
            travel_min=round(a.travel_s / 60, 2),
            seat_occupied_min=round(a.seat_s / 60, 2) if a.seat_known else None,
            seatbelt_unfastened_working_s=int(a.belt_off_working_s),
            avg_engine_rpm=round(a.rpm_sum / a.rpm_n, 0) if a.rpm_n else None,
            max_travel_speed_kmh=round(a.max_speed, 2),
            truck_present_min=round(a.truck_present_s / 60, 2) if a.truck_sensor else None,
            truck_wait_min=round(a.truck_wait_s / 60, 2),
            min_proximity_m=round(a.min_prox, 2) if a.min_prox is not None else None,
            proximity_caution_count=a.counts["proximity_caution_count"],
            proximity_danger_count=a.counts["proximity_danger_count"],
            proximity_critical_count=a.counts["proximity_critical_count"],
            ambient_temp_c=round(a.sums["ambient_temp_c"] / a.seconds, 1),
            relative_humidity_pct=round(a.sums["relative_humidity_pct"] / a.seconds, 1),
            heat_index_c=round(a.sums["heat_index_c"] / a.seconds, 1),
            precipitation_mm=round(a.precip_mm, 2),
            wind_kmh=round(a.sums["wind_kmh"] / a.seconds, 1),
            visibility_m=round(a.sums["visibility_m"] / a.seconds, 0),
            is_night=a.night_s * 2 > a.seconds,
            ground_condition=a.grounds.most_common(1)[0][0],
            continuous_operation_min=round(last.continuous_operation_min, 1),
            coolant_temp_c=a.coolant_min,
            incident_count=self.incidents,
            near_miss_count=self.near_misses,
            **{k: round(v, 2) for k, v in idle_min.items()},
            fuel_per_load_cycle_l=round(a.fuel_l / cycles, 2) if cycles else None,
            task_progress_qty=round(max(0.0, a.progress_end - (a.progress_start or 0.0)), 3),
            risk_score_max=a.risk_max,
        )
        self.incidents = 0
        self.near_misses = 0
        return record
