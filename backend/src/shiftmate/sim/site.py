"""One site's world: weather, dispatcher, workers and machines on one clock (TRD §7).

`SiteWorld` keeps what carries over between days (engine hours, machine positions, weather
state). A day is `begin_day(...)` followed by `step()` calls, one per tick period; `run_day`
does both for the history generator (30 s steps). Live mode (the Edge Gateway) calls `step()`
itself at 1 s and uses the scenario hooks (`weather_override`, `block_trucks`, …).

Randomness: every site-day gets its own seed sequence `[seed, site_index, day_index]`, split into
independent streams for weather, trucks, workers, planning and each machine. Same seed ⇒ same
world, and sites can be generated in parallel without changing the result.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.schema.config import MonthProfile, Site
from shiftmate.schema.enums import GroundCondition, ZoneType
from shiftmate.schema.reference import Task
from shiftmate.sim.fleet import Fleet
from shiftmate.sim.machine import BreakPlan, DayPlan, MachineAgent
from shiftmate.sim.tasks import PlannedTask, plan_day
from shiftmate.sim.trucks import DispatchEntry, Dispatcher, ShortageWindow
from shiftmate.sim.weather import DayWeather, WeatherModel
from shiftmate.sim.workers import WorkerCrowd
from shiftmate.util.heat_index import heat_index_c


@dataclass
class DayResult:
    ticks: list[dict[str, object]]
    truth: list[dict[str, object]]
    tasks: list[Task]
    dispatch: list[DispatchEntry]
    weather: DayWeather
    shortages: list[ShortageWindow]
    day: date


@dataclass
class DayState:
    day: date
    day_index: int
    dt: float
    weather: DayWeather
    dispatcher: Dispatcher
    crowd: WorkerCrowd
    shortages: list[ShortageWindow]
    zone_of: dict[str, str]
    shift_start: datetime
    shift_end: datetime
    t0: datetime
    t1: datetime
    midnight: datetime
    now: datetime
    weather_override: dict[str, float | str] = field(default_factory=dict)


def season_month(site: Site, day_index: int) -> int:
    for span in site.climate.history_seasons:
        if span.days[0] <= day_index <= span.days[1]:
            return span.month
    return site.climate.history_seasons[-1].month


class SiteWorld:
    def task_noise(self, rng: np.random.Generator) -> float:
        """Task-level productivity noise, drawn the same way as in history mode."""
        return float(rng.lognormal(0.0, self.sim.productivity.noise_sigma))

    def __init__(
        self,
        cfg: ShiftMateConfig,
        site: Site,
        fleet: Fleet,
        site_index: int,
        seed: int,
        machine_ids: Iterable[str] | None = None,
    ):
        self.cfg = cfg
        self.site = site
        self.fleet = fleet
        self.site_index = site_index
        self.seed = seed
        self.sim = cfg.simulator
        self.tz = ZoneInfo(site.timezone)
        self.weather_model = WeatherModel(site, self.sim.weather)
        rest = site.layout.zones_of(ZoneType.BREAK_AREA)[0].centroid()
        wanted = set(machine_ids) if machine_ids is not None else None
        self.agents: dict[str, MachineAgent] = {}
        for i, machine in enumerate(fleet.machines_at(site.site_id)):
            if wanted is not None and machine.machine_id not in wanted:
                continue
            park = (rest[0] + (i % 6) * 4.0, rest[1] - (i // 6) * 4.0)
            park = (min(max(park[0], 1.0), site.layout.size.w - 1), max(park[1], 1.0))
            self.agents[machine.machine_id] = MachineAgent(
                machine, cfg.profiles[machine.machine_type], site, self.sim, park
            )
        self.operators = fleet.operators_at(site.site_id)
        self.fixed_pairs = {f.operator_id: f.machine_id for f in self.sim.operators.fixed}
        self.state: DayState | None = None

    # ------------------------------------------------------------------------------------------
    def _local(self, day: date, t: time) -> datetime:
        return datetime.combine(day, t, tzinfo=self.tz)

    def _assign_operators(self, rng: np.random.Generator) -> dict[str, str | None]:
        free = {o.operator_id: o for o in self.operators}
        assignment: dict[str, str | None] = {}
        # fixed pairs (Ravi on EXC001) first
        for op_id, machine_id in self.fixed_pairs.items():
            if op_id in free and machine_id in self.agents:
                assignment[machine_id] = op_id
                free.pop(op_id)
        for machine_id, agent in self.agents.items():
            if machine_id in assignment:
                continue
            usual = [
                op_id
                for op_id, m in self.fleet.usual_machine.items()
                if m == machine_id and op_id in free
            ]
            if usual and rng.random() < self.sim.operators.same_machine_prob:
                chosen = usual[0]
            else:
                certified = sorted(
                    op_id
                    for op_id, op in free.items()
                    if agent.machine.machine_type in op.certifications
                )
                chosen = certified[int(rng.integers(0, len(certified)))] if certified else None
            assignment[machine_id] = chosen
            if chosen:
                free.pop(chosen)
        return assignment

    def _events(
        self, agent: MachineAgent, op_id: str | None, start: datetime, end: datetime, rng
    ) -> list[tuple[datetime, str, float]]:
        if op_id is None:
            return []
        b = self.sim.behaviour
        an = self.sim.anomalies
        p = self.fleet.personalities[op_id]
        hours = (end - start).total_seconds() / 3600
        specs = [
            ("habit", b.habit_floor_per_h + b.habit_per_h * p.idle_habit, b.habit_min),
            ("pause", b.short_pause_per_h, None),
            ("step_out", b.step_out_per_h * p.steps_out_engine_on, b.step_out_min),
            ("seatbelt", b.seatbelt_off_per_h * p.seatbelt_skipper, b.seatbelt_off_min),
            ("fuel", an.fuel_abnormal_per_h, an.fuel_min),
            ("lowprod", an.low_productivity_per_h, an.low_productivity_min),
            (
                "approach",
                self.site.workers.swing_entry_prob_per_h
                * self.sim.workers.caution_approach_multiplier,
                None,
            ),
        ]
        events: list[tuple[datetime, str, float]] = []
        for kind, rate, dur in specs:
            n = int(rng.poisson(max(rate, 0.0) * hours))
            for _ in range(n):
                at = start + timedelta(seconds=float(rng.uniform(0, hours * 3600)))
                if kind == "pause":
                    minutes = float(rng.uniform(b.short_pause_s.min, b.short_pause_s.max)) / 60
                elif dur is not None:
                    minutes = float(rng.uniform(dur.min, dur.max))
                else:
                    minutes = 0.0
                events.append((at, kind, minutes))
        events.sort(key=lambda e: (e[0], e[1]))
        return events

    # ------------------------------------------------------------------------------------------
    def begin_day(
        self,
        day_index: int,
        day: date,
        dt: float,
        month_override: MonthProfile | None = None,
        month_number: int | None = None,
        task_overrides: dict[str, list[PlannedTask]] | None = None,
    ) -> DayState:
        """Set up weather, trucks, workers, operators and task plans for a day."""
        seq = np.random.SeedSequence([self.seed, self.site_index, day_index])
        s_weather, s_trucks, s_workers, s_assign, s_plan, s_machines = seq.spawn(6)
        rng_weather = np.random.default_rng(s_weather)
        rng_plan = np.random.default_rng(s_plan)

        month_no = month_number or season_month(self.site, day_index)
        month = month_override or self.site.climate.month_profiles[month_no]
        daylight_doy = date(day.year, month_no, 15).timetuple().tm_yday
        weather = self.weather_model.generate_day(day, month, daylight_doy, rng_weather)

        shift_start = self._local(day, self.site.shift.start)
        shift_end = self._local(day, self.site.shift.end)
        t0 = shift_start - timedelta(minutes=self.sim.history.pre_shift_min)
        t1 = shift_end + timedelta(minutes=self.sim.history.post_shift_min)

        dispatcher = Dispatcher(self.site, self.sim.trucks, np.random.default_rng(s_trucks))
        crowd = WorkerCrowd(self.site, self.sim.workers, np.random.default_rng(s_workers))

        # random truck shortage windows: 1–2 per site-week on average
        shortages: list[ShortageWindow] = []
        per_week = float(
            rng_plan.uniform(
                self.site.trucks.random_shortages_per_week.min,
                self.site.trucks.random_shortages_per_week.max,
            )
        )
        for _ in range(int(rng_plan.poisson(per_week / 7))):
            minutes = float(
                rng_plan.uniform(
                    self.site.trucks.random_shortage_minutes.min,
                    self.site.trucks.random_shortage_minutes.max,
                )
            )
            start = shift_start + timedelta(
                seconds=float(rng_plan.uniform(0, (shift_end - shift_start).total_seconds()))
            )
            shortages.append(ShortageWindow(start, start + timedelta(minutes=minutes)))
        for w in self.site.trucks.shortage_windows:
            if w.day == day_index:
                start = self._local(day, w.start)
                shortages.append(ShortageWindow(start, start + timedelta(minutes=w.minutes)))
        dispatcher.set_shortages(shortages)

        assignment = self._assign_operators(np.random.default_rng(s_assign))
        loading_zones = [z.id for z in self.site.layout.zones_of(ZoneType.LOADING)]
        loaders = [
            m_id
            for m_id, a in self.agents.items()
            if assignment.get(m_id) and any(tp.truck_dependent for tp in a.profile.tasks.values())
        ]
        rng_plan.shuffle(loaders)
        zone_of = dict(zip(loaders, loading_zones, strict=False))
        overrides = task_overrides or {}
        for machine_id, planned in overrides.items():
            # a scripted task list pins the machine to the zone of its truck-loading task
            for pt in planned:
                if pt.task.task_type == "truck_loading":
                    for other, zone in list(zone_of.items()):
                        if zone == pt.task.zone_id and other != machine_id:
                            zone_of.pop(other)
                    zone_of[machine_id] = pt.task.zone_id

        machine_seqs = s_machines.spawn(len(self.agents))
        counter = 0
        midnight = self._local(day, time(0, 0))
        minute0 = weather.at((t0 - midnight).total_seconds() / 60)
        for (machine_id, agent), mseq in zip(self.agents.items(), machine_seqs, strict=True):
            rng_m = np.random.default_rng(mseq)
            op_id = assignment.get(machine_id)
            tasks = []
            if op_id:
                tasks = plan_day(
                    site=self.site,
                    profile=agent.profile,
                    machine_id=machine_id,
                    operator_id=op_id,
                    day=day,
                    shift_start=shift_start,
                    loading_zone=zone_of.get(machine_id),
                    params=self.sim.tasks,
                    productivity=self.sim.productivity,
                    rng=rng_m,
                    counter_start=counter,
                )
                counter += len(tasks)
            if machine_id in overrides:
                tasks = overrides[machine_id]
            arrival = shift_start - timedelta(
                minutes=float(
                    rng_m.uniform(
                        self.sim.behaviour.arrival_before_shift_min.min,
                        self.sim.behaviour.arrival_before_shift_min.max,
                    )
                )
            )
            breaks = [
                BreakPlan(self._local(day, b.start), b.minutes) for b in self.site.shift.breaks
            ]
            plan = DayPlan(
                operator_id=op_id,
                personality=self.fleet.personalities.get(op_id) if op_id else None,
                tasks=tasks,
                arrival=arrival,
                shift_start=shift_start,
                shift_end=shift_end,
                breaks=breaks,
                loading_zone=zone_of.get(machine_id),
                events=self._events(agent, op_id, shift_start, shift_end, rng_m),
            )
            agent.start_day(plan, rng_m, float(minute0["ambient_temp_c"]))  # type: ignore[arg-type]

        self.state = DayState(
            day=day,
            day_index=day_index,
            dt=dt,
            weather=weather,
            dispatcher=dispatcher,
            crowd=crowd,
            shortages=shortages,
            zone_of=zone_of,
            shift_start=shift_start,
            shift_end=shift_end,
            t0=t0,
            t1=t1,
            midnight=midnight,
            now=t0,
        )
        return self.state

    def conditions(self, now: datetime | None = None) -> dict[str, object]:
        """Site conditions at a time (scripted overrides applied, heat index recomputed)."""
        s = self.state
        assert s is not None
        when = now or s.now
        w = dict(s.weather.at((when - s.midnight).total_seconds() / 60))
        o = s.weather_override
        if o:
            if "temp_c" in o:
                w["ambient_temp_c"] = float(o["temp_c"])
            if "rh" in o:
                w["relative_humidity_pct"] = float(o["rh"])
            if "precip_mm_h" in o:
                w["precipitation_mm_h"] = float(o["precip_mm_h"])
            if "ground" in o:
                w["ground_condition"] = GroundCondition(str(o["ground"]))
            w["heat_index_c"] = heat_index_c(
                float(w["ambient_temp_c"]),  # type: ignore[arg-type]
                float(w["relative_humidity_pct"]),  # type: ignore[arg-type]
            )
        return w

    def step(self) -> list[tuple[dict[str, object], dict[str, object]]]:
        """Advance the world by one tick period. Returns (tick, truth) for every machine."""
        s = self.state
        assert s is not None
        now, dt = s.now, s.dt
        w = self.conditions(now)
        active = {
            s.zone_of[m_id]
            for m_id, a in self.agents.items()
            if m_id in s.zone_of
            and a.engine_on
            and a.current_task is not None
            and a.current_task.task.task_type == "truck_loading"
        }
        s.dispatcher.set_active_zones(active, now)
        s.dispatcher.step(now)
        s.crowd.step(dt, {m_id: (a.x, a.y) for m_id, a in self.agents.items() if a.engine_on})
        out = []
        for agent in self.agents.values():
            tick, tr = agent.step(now, dt, w, s.dispatcher, s.crowd)
            tick["site_id"] = self.site.site_id
            out.append((tick, tr))
        s.now = now + timedelta(seconds=dt)
        return out

    def end_day(self) -> list[Task]:
        tasks_out: list[Task] = []
        for agent in self.agents.values():
            if agent.plan:
                tasks_out.extend(pt.task for pt in agent.plan.tasks)
            agent.end_day()
        return tasks_out

    def run_day(
        self,
        day_index: int,
        day: date,
        dt: float,
        month_override: MonthProfile | None = None,
    ) -> DayResult:
        s = self.begin_day(day_index, day, dt, month_override)
        ticks: list[dict[str, object]] = []
        truth: list[dict[str, object]] = []
        while s.now < s.t1:
            for tick, tr in self.step():
                ticks.append(tick)
                truth.append(tr)
        tasks_out = self.end_day()
        return DayResult(ticks, truth, tasks_out, s.dispatcher.log, s.weather, s.shortages, day)
