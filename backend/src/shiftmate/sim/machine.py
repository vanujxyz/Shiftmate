"""One simulated machine and its operator, stepped through a working day (TRD §7.2, §7.3).

The machine is always doing one *activity*: off, walkaround, board, warmup, travel, work,
load_truck, wait_truck, habit, pause, step_out, break_off, break_idle or done. Each world step
the agent (1) picks the activity for the step if the last one ended, (2) reports a signal tick
describing that instant, and (3) integrates the step: task progress, load cycles, engine hours,
coolant temperature and position. Activity lengths are whole numbers of steps, so every tick
describes its whole step exactly and the tick-level invariants in TRD §7.5 hold exactly.

A day: the operator arrives before the shift, walks around the machine, climbs in, starts the
engine and idles until the coolant is warm, then works through the planned tasks. Truck loading
waits for trucks from the dispatcher. Scheduled breaks are taken (engine off, or idling in the
cab) unless the operator tends to skip breaks. Personality traits add Poisson-timed episodes:
unexplained seated idle (habit), stepping out with the engine running, working unbelted and
driving fast near people. Separately injected episodes make fuel use abnormal or productivity
low. Everything that really happened is written to a ground-truth record that engines never see.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import numpy as np

from shiftmate.schema.config import MachineProfile, Site
from shiftmate.schema.enums import IdleReason, SensorTier, TaskStatus
from shiftmate.schema.reference import Machine, TaskConditions
from shiftmate.sim.params import Personality, SimulatorConfig
from shiftmate.sim.tasks import PlannedTask, condition_multiplier
from shiftmate.sim.trucks import Dispatcher, Truck
from shiftmate.sim.workers import WorkerCrowd

ENGINE_OFF_KINDS = {"off", "walkaround", "board", "break_off", "done"}
SEATED_KINDS = {"board", "warmup", "travel", "work", "load_truck", "wait_truck", "habit", "pause"}
IDLE_TRUTH = {
    "warmup": IdleReason.WARM_UP,
    "wait_truck": IdleReason.WAITING_FOR_TRUCK,
    "habit": IdleReason.HABIT,
    "pause": IdleReason.UNKNOWN,
    "step_out": IdleReason.UNATTENDED_RUNNING,
    "break_idle": IdleReason.SCHEDULED_BREAK,
}
BREAK_KINDS = {"break_off", "break_idle"}
WORK_CHUNK_S = 120  # work is done in short chunks so events and breaks can start promptly
ANOMALY_TYPES = (
    "habit_idle",
    "unattended",
    "seatbelt",
    "speed_near_person",
    "fuel_abnormal",
    "low_productivity",
)


@dataclass
class Activity:
    kind: str
    remaining_s: float | None  # None = open-ended (re-checked every step)
    seated: bool = True  # used by break_idle
    target: tuple[float, float] | None = None
    truck: Truck | None = None
    fast_near_people: bool = False  # travel: this operator keeps speed near people


@dataclass
class BreakPlan:
    start: datetime
    minutes: int
    decided: bool = False
    skip: bool = False
    taken: bool = False


@dataclass
class DayPlan:
    operator_id: str | None
    personality: Personality | None
    tasks: list[PlannedTask]
    arrival: datetime
    shift_start: datetime
    shift_end: datetime
    breaks: list[BreakPlan]
    loading_zone: str | None
    events: list[tuple[datetime, str, float]] = field(default_factory=list)  # (time, kind, minutes)


def _ceil_steps(seconds: float, dt: float) -> float:
    return max(dt, math.ceil(seconds / dt - 1e-9) * dt)


class MachineAgent:
    def __init__(
        self,
        machine: Machine,
        profile: MachineProfile,
        site: Site,
        sim: SimulatorConfig,
        position: tuple[float, float],
    ) -> None:
        self.machine = machine
        self.profile = profile
        self.site = site
        self.sim = sim
        self.engine_hours = machine.engine_hours_start
        self.load_cycles = 0.0
        self.coolant_c: float | None = None
        self.x, self.y = position
        self.heading = 0.0
        self.plan: DayPlan | None = None
        self.activity = Activity("off", None, seated=False)
        self.rng = np.random.default_rng(0)
        self.task_index = 0
        self.belt_fastened = False
        self.belt_off_until: datetime | None = None
        self.fuel_multiplier_until: tuple[datetime, float] | None = None
        self.low_prod_until: tuple[datetime, float] | None = None
        self.pending: list[tuple[str, float]] = []  # (kind, minutes) waiting for a boundary
        self.engine_started_at: datetime | None = None
        self.overrides: dict[str, object] = {}  # scenario hooks (live mode)
        self._warm_extra_s = 0.0
        self._event_index = 0
        self._now: datetime | None = None

    # ------------------------------------------------------------------------------------------
    def start_day(self, plan: DayPlan, rng: np.random.Generator, ambient_c: float) -> None:
        self.plan = plan
        self.rng = rng
        self.task_index = 0
        self.activity = Activity("off", None, seated=False)
        self.belt_fastened = False
        self.belt_off_until = None
        self.fuel_multiplier_until = None
        self.low_prod_until = None
        self.pending = []
        self.coolant_c = ambient_c if self.coolant_c is None else self.coolant_c
        self._event_index = 0
        # Operators who speed near people do so on some days (trait-driven), in travel and work.
        self.speeder_today = rng.random() < self._trait("speeds_near_people") * (
            self.sim.behaviour.speeding_prob
        )

    @property
    def current_task(self) -> PlannedTask | None:
        if self.plan and self.task_index < len(self.plan.tasks):
            return self.plan.tasks[self.task_index]
        return None

    @property
    def engine_on(self) -> bool:
        return self.activity.kind not in ENGINE_OFF_KINDS

    @property
    def seat_occupied(self) -> bool:
        if self.activity.kind == "break_idle":
            return self.activity.seated
        return self.activity.kind in SEATED_KINDS

    # ------------------------------------------------------------------------------------------
    def _trait(self, name: str) -> float:
        if not self.plan or not self.plan.personality:
            return 0.0
        return float(getattr(self.plan.personality, name))

    def _start(self, kind: str, seconds: float | None, dt: float, **kw: object) -> Activity:
        was_on = self.engine_on
        self.activity = Activity(kind, None if seconds is None else _ceil_steps(seconds, dt), **kw)
        if not was_on and self.engine_on:
            self.engine_started_at = self._now
        return self.activity

    def _due_break(self, now: datetime) -> BreakPlan | None:
        if not self.plan:
            return None
        for b in self.plan.breaks:
            if b.taken or now < b.start:
                continue
            if not b.decided:
                b.decided = True
                b.skip = self.rng.random() < self._trait("skips_breaks") * (
                    self.sim.behaviour.skip_break_prob
                )
            if not b.skip and not b.taken:
                return b
        return None

    def _fire_events(self, now: datetime, crowd: WorkerCrowd) -> None:
        """Move events whose time has come into pending lists or timers."""
        if not self.plan:
            return
        events = self.plan.events
        while self._event_index < len(events) and events[self._event_index][0] <= now:
            _, kind, minutes = events[self._event_index]
            self._event_index += 1
            if not self.engine_on:
                continue  # these behaviours only happen with the engine running
            if kind in ("habit", "pause", "step_out"):
                self.pending.append((kind, minutes))
            elif kind == "seatbelt":
                self.belt_off_until = now + timedelta(minutes=minutes)
            elif kind == "fuel":
                mult = self.rng.uniform(
                    self.sim.anomalies.fuel_multiplier.min, self.sim.anomalies.fuel_multiplier.max
                )
                self.fuel_multiplier_until = (now + timedelta(minutes=minutes), float(mult))
            elif kind == "lowprod":
                factor = self.rng.uniform(
                    self.sim.anomalies.low_productivity_factor.min,
                    self.sim.anomalies.low_productivity_factor.max,
                )
                self.low_prod_until = (now + timedelta(minutes=minutes), float(factor))
            elif kind == "approach":
                crowd.start_approach(self.machine.machine_id, self.profile.proximity_m)

    def _productivity_factor(self, now: datetime, weather: dict[str, object]) -> float:
        m = condition_multiplier(
            self.sim.productivity,
            weather["ground_condition"],  # type: ignore[arg-type]
            float(weather["heat_index_c"]),  # type: ignore[arg-type]
            bool(weather["is_night"]),
        )
        skill = self.plan.personality.skill if self.plan and self.plan.personality else 1.0
        task = self.current_task
        noise = task.noise if task else 1.0
        low = (
            self.low_prod_until[1] if self.low_prod_until and now < self.low_prod_until[0] else 1.0
        )
        return m * skill * noise * low

    def _choose_activity(
        self, now: datetime, dt: float, weather: dict[str, object], dispatcher: Dispatcher
    ) -> None:
        plan = self.plan
        kind = self.activity.kind
        if plan is None or plan.operator_id is None:
            self._start("off", None, dt, seated=False)
            return
        if now >= plan.shift_end or kind == "done":
            self._start("done", None, dt, seated=False)
            return
        if kind == "off":
            if now >= plan.arrival:
                self._start(
                    "walkaround",
                    self.rng.uniform(
                        self.sim.behaviour.walkaround_min.min, self.sim.behaviour.walkaround_min.max
                    )
                    * 60,
                    dt,
                    seated=False,
                )
            else:
                self._start("off", None, dt, seated=False)
            return
        if kind in ("walkaround", "break_off"):
            self._start("board", 30, dt)
            return
        if kind == "board":
            self.belt_fastened = True
            self._start("warmup", None, dt)
            self._warm_extra_s = (
                self.rng.uniform(
                    self.sim.warm_up.extra_idle_min.min, self.sim.warm_up.extra_idle_min.max
                )
                * 60
            )
            return
        if kind == "warmup":
            ready = self.profile.warm_up.coolant_ready_c
            if (self.coolant_c or 0) < ready:
                return  # keep warming (open-ended)
            if self._warm_extra_s > 0:
                self._warm_extra_s -= dt
                return
        # A break that is due starts at this boundary.
        brk = self._due_break(now)
        if brk is not None:
            brk.taken = True
            minutes = max(1.0, brk.minutes - (now - brk.start).total_seconds() / 60)
            if self.rng.random() < self.sim.behaviour.break_engine_off_prob:
                self.belt_fastened = False
                self._start("break_off", minutes * 60, dt, seated=False)
            else:
                seated = self.rng.random() < self.sim.behaviour.break_seat_occupied_prob
                if not seated:
                    self.belt_fastened = False
                self._start("break_idle", minutes * 60, dt, seated=seated)
            return
        if kind == "break_idle" or kind == "step_out":
            self.belt_fastened = True
        # Behaviour episodes wait for a moment when the machine is working.
        if self.pending and kind in ("work", "load_truck", "wait_truck", "travel"):
            ev_kind, minutes = self.pending.pop(0)
            if ev_kind == "step_out":
                self.belt_fastened = False
                self._start("step_out", minutes * 60, dt, seated=False)
            else:
                self._start(ev_kind, minutes * 60, dt)
            return
        task = self.current_task
        if task is None:
            self._start("done", None, dt, seated=False)
            return
        if task.task.actual_start is None:
            task.task.actual_start = now
            task.task.status = TaskStatus.ACTIVE
            task.task.conditions_at_start = TaskConditions(
                ground_condition=weather["ground_condition"],  # type: ignore[arg-type]
                heat_index_c=float(weather["heat_index_c"]),  # type: ignore[arg-type]
                precipitation_mm_h=float(weather["precipitation_mm_h"]),  # type: ignore[arg-type]
                is_night=bool(weather["is_night"]),
            )
        tx, ty = task.work_spot
        distance = math.hypot(tx - self.x, ty - self.y)
        if distance > 3:
            self._start("travel", None, dt, target=(tx, ty), fast_near_people=self.speeder_today)
            return
        if task.task.task_type == "truck_loading" and plan.loading_zone:
            truck = dispatcher.waiting_truck(plan.loading_zone)
            if truck is None:
                self._start("wait_truck", None, dt)
                return
            truck.loading_by = self.machine.machine_id
            passes = int(
                self.rng.integers(
                    int(self.profile.passes_per_load.min), int(self.profile.passes_per_load.max) + 1
                )
            )
            pass_s = self.profile.seconds_per_pass.mean * float(
                self.rng.lognormal(0.0, self.sim.productivity.pass_time_noise)
            )
            seconds = passes * pass_s / self._productivity_factor(now, weather)
            self._start("load_truck", seconds, dt, truck=truck)
            return
        self._start("work", WORK_CHUNK_S, dt)

    # ------------------------------------------------------------------------------------------
    def step(
        self,
        now: datetime,
        dt: float,
        weather: dict[str, object],
        dispatcher: Dispatcher,
        crowd: WorkerCrowd,
    ) -> tuple[dict[str, object], dict[str, object]]:
        """Report the tick for `now` and advance to `now + dt`. Returns (tick, truth)."""
        self._now = now
        self._fire_events(now, crowd)
        a = self.activity
        ended = a.remaining_s is not None and a.remaining_s <= 0
        if a.kind == "wait_truck" and self.plan and self.plan.loading_zone:
            ended = ended or dispatcher.waiting_truck(self.plan.loading_zone) is not None
            ended = ended or self._due_break(now) is not None
        if a.kind in ("off", "warmup", "done"):
            ended = True  # re-evaluated every step
        if ended:
            self._choose_activity(now, dt, weather, dispatcher)
        a = self.activity
        kind = a.kind
        tier = self.machine.sensor_tier
        profile = self.profile
        ambient = float(weather["ambient_temp_c"])  # type: ignore[arg-type]

        # --- people nearby (geometric truth; the sensor sees it only on advanced machines) ---
        nearest = crowd.nearest((self.x, self.y), self.heading)
        # Operators notice people a little before the caution ring (they slow down early).
        near_radius = (
            profile.proximity_m.caution * self.sim.behaviour.slow_near_person_radius_factor
        )
        person_near = nearest is not None and nearest[0] <= near_radius

        # --- motion for this step ---
        speed_kmh = 0.0
        if kind == "travel":
            speed_kmh = self.sim.travel.speed_kmh[profile.machine_type]
            if person_near and not a.fast_near_people:
                speed_kmh = min(speed_kmh, self.sim.behaviour.slow_near_person_kmh)
        elif kind in ("work", "load_truck"):
            if profile.machine_type != "excavator":
                speed_kmh = float(self.rng.uniform(3.0, 7.0))
                if person_near and not self.speeder_today:
                    speed_kmh = min(speed_kmh, self.sim.behaviour.slow_near_person_kmh)
        hydraulic = kind in ("work", "load_truck")
        seatbelt = self.belt_fastened and not (self.belt_off_until and now < self.belt_off_until)
        seated = self.seat_occupied
        if not seated:
            seatbelt = False
        engine_on = self.engine_on

        # --- fuel and rpm ---
        if not engine_on:
            fuel = 0.0
            rpm = 0.0
        elif hydraulic:
            fuel, rpm = profile.fuel_lph.working, profile.rpm.working
        elif kind == "travel":
            fuel, rpm = profile.fuel_lph.travel, 0.85 * profile.rpm.working
        else:
            fuel, rpm = profile.fuel_lph.idle, profile.rpm.idle
        fuel_abnormal = bool(
            engine_on and self.fuel_multiplier_until and now < self.fuel_multiplier_until[0]
        )
        if fuel_abnormal and self.fuel_multiplier_until:
            fuel *= self.fuel_multiplier_until[1]
        if engine_on:
            fuel *= 1 + self.rng.normal(0, self.sim.signals.fuel_rate_noise_sd)
            rpm += self.rng.normal(0, self.sim.signals.rpm_noise_sd)

        task = self.current_task
        tick: dict[str, object] = {
            "ts": now,
            "machine_id": self.machine.machine_id,
            "operator_id": self.plan.operator_id if self.plan else None,
            "engine_on": engine_on,
            "engine_hours": round(self.engine_hours, 5),
            "fuel_rate_lph": round(max(fuel, 0.0), 3),
            "hydraulic_active": hydraulic,
            "travel_speed_kmh": round(speed_kmh, 2),
            "seatbelt_fastened": seatbelt,
            "x_m": round(self.x, 2),
            "y_m": round(self.y, 2),
            "heading_deg": round(self.heading % 360, 1),
            "load_cycles_total": int(self.load_cycles),
            "seat_occupied": seated if tier != SensorTier.BASIC else None,
            "engine_rpm": round(rpm, 0) if tier != SensorTier.BASIC else None,
            "coolant_temp_c": round(self.coolant_c or ambient, 1)
            if tier != SensorTier.BASIC
            else None,
            "proximity_m": None,
            "proximity_bearing_deg": None,
            "proximity_source": None,
            "truck_in_loading_zone": None,
            **weather,
            "task_id": task.task.task_id if task and task.task.actual_start else None,
            "task_progress_qty": round(task.progress, 3) if task else 0.0,
        }
        if tier == SensorTier.ADVANCED:
            in_range = nearest is not None and nearest[0] <= self.sim.workers.sensor_range_m
            tick["proximity_m"] = (
                round(nearest[0], 2) if in_range and nearest else (self.sim.workers.sensor_range_m)
            )
            tick["proximity_bearing_deg"] = round(nearest[1], 0) if in_range and nearest else None
            tick["proximity_source"] = "sensor"
            if self.plan and self.plan.loading_zone:
                tick["truck_in_loading_zone"] = dispatcher.truck_in_zone(self.plan.loading_zone)
            else:
                tick["truck_in_loading_zone"] = False

        truth: dict[str, object] = {
            "ts": now,
            "machine_id": self.machine.machine_id,
            "activity": kind,
            "idle_reason": (
                IDLE_TRUTH[kind].value
                if engine_on and not hydraulic and speed_kmh < 0.5 and kind in IDLE_TRUTH
                else None
            ),
            "habit_idle": kind == "habit",
            "unattended": kind == "step_out",
            "seatbelt": engine_on and not seatbelt and seated and (hydraulic or speed_kmh > 0.5),
            "speed_near_person": bool(
                person_near and speed_kmh > profile.unsafe.speed_near_person_kmh
            ),
            "fuel_abnormal": fuel_abnormal,
            "low_productivity": bool(
                hydraulic and self.low_prod_until and now < self.low_prod_until[0]
            ),
        }

        # --- integrate the step ---
        if engine_on:
            self.engine_hours += dt / 3600
            rise = (
                self.sim.warm_up.coolant_rise_c_per_min
                if ambient >= 0
                else self.sim.warm_up.coolant_rise_below_0c_c_per_min
            )
            self.coolant_c = min(
                self.sim.warm_up.coolant_working_c, (self.coolant_c or ambient) + rise * dt / 60
            )
        else:
            cool = self.sim.warm_up.coolant_cooling_c_per_min * dt / 60
            self.coolant_c = max(ambient, (self.coolant_c or ambient) - cool)
        factor = self._productivity_factor(now, weather) if hydraulic else 1.0
        counts_as_task_time = kind not in BREAK_KINDS and kind not in (
            "off",
            "done",
            "walkaround",
            "board",
        )
        if task and counts_as_task_time and task.task.actual_start is not None:
            task.work_seconds += dt
        if kind == "work" and task:
            rate = profile.tasks[task.task.task_type].base_rate_per_h * factor
            task.progress += rate * dt / 3600
            # Load cycles (D-001): dozers count every push; excavators and loaders on tasks
            # without trucks count the share of passes that fill a truck elsewhere.
            passes_per_load = (profile.passes_per_load.min + profile.passes_per_load.max) / 2
            share = 1.0 if passes_per_load == 1 else self.sim.productivity.non_truck_load_share
            self.load_cycles += (
                share * dt * factor / (profile.seconds_per_pass.mean * passes_per_load)
            )
            self.heading += float(
                self.rng.uniform(
                    -self.sim.signals.work_heading_step_deg, self.sim.signals.work_heading_step_deg
                )
            )
            if task.progress >= task.task.planned_quantity:
                self._complete_task(task, now + timedelta(seconds=dt))
                a.remaining_s = 0
        elif kind == "load_truck":
            self.heading += float(self.rng.uniform(-60, 60))
        elif kind == "travel" and a.target:
            # Travel is open-ended: it ends on the step the machine reaches its target.
            tx, ty = a.target
            step_m = speed_kmh / 3.6 * dt
            d = math.hypot(tx - self.x, ty - self.y)
            if d > 0:
                self.heading = math.degrees(math.atan2(tx - self.x, ty - self.y)) % 360
            if d <= step_m:
                self.x, self.y = tx, ty
                a.remaining_s = dt  # reaches zero below, so the next step picks a new activity
            else:
                self.x += (tx - self.x) / d * step_m
                self.y += (ty - self.y) / d * step_m
        if a.remaining_s is not None:
            a.remaining_s -= dt
            if a.kind == "load_truck" and a.remaining_s <= 0 and a.truck is not None and task:
                dispatcher.finish_loading(a.truck, now + timedelta(seconds=dt))
                self.load_cycles += 1
                task.progress += 1
                a.truck = None
                if task.progress >= task.task.planned_quantity:
                    self._complete_task(task, now + timedelta(seconds=dt))
        return tick, truth

    def _complete_task(self, task: PlannedTask, end: datetime) -> None:
        task.task.actual_end = end
        task.task.actual_duration_min = round(task.work_seconds / 60, 1)
        task.task.status = TaskStatus.DONE
        self.task_index += 1

    def end_day(self) -> None:
        """Close unfinished tasks for the day (they stay active, with no duration)."""
        self.activity = Activity("off", None, seated=False)
