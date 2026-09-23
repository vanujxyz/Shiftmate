"""Live mode: the simulated site running at 1 s ticks, driven by a scenario (TRD §7, §8).

`LiveSite` wraps a `SiteWorld` for the scenario's site and day: the focus machine (Ravi's EXC001)
runs a full `MachineRuntime`; background machines run in the world only (map, trucks, workers —
D-052). `ScenarioPlayer` fires the scenario's beats at their times and supports play / pause /
speed / seek. Seeking restores a snapshot taken when that beat last fired, or fast-forwards
deterministically (same seed ⇒ same world ⇒ same events).
"""

from __future__ import annotations

import copy
import math
import time as _time
from collections import deque
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import yaml
from pydantic import BaseModel, Field

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.edge.resources import EdgeResources
from shiftmate.edge.runtime import MachineRuntime
from shiftmate.edge.store import EdgeStore
from shiftmate.engines.dispatch_view import DispatchLogEntry, DispatchView
from shiftmate.engines.pipeline import TaskInfo
from shiftmate.engines.risk import Thresholds, proximity_tier
from shiftmate.schema.enums import EventType, Language, QuantityUnit, TaskStatus
from shiftmate.schema.reference import Task
from shiftmate.settings import REPO_ROOT
from shiftmate.sim.history import build_history_fleet
from shiftmate.sim.site import SiteWorld
from shiftmate.sim.tasks import PlannedTask

SCENARIO_DIR = REPO_ROOT / "scenarios"
FLEET_SEED = 7  # the live fleet is the same fleet as the history (same machines and people)


# --- scenario file -------------------------------------------------------------------------------


class ScenarioTask(BaseModel):
    task_type: str
    planned_quantity: float
    quantity_unit: QuantityUnit
    zone_id: str
    scheduled_start: time


class WeatherStep(BaseModel):
    at: time
    temp_c: float | None = None
    rh: float | None = None
    precip_mm_h: float | None = None
    ground: str | None = None


class Beat(BaseModel):
    id: str
    at: time
    action: str
    params: dict[str, Any] = {}
    caption: dict[str, str] | None = None


class Scenario(BaseModel):
    name: str
    title: dict[str, str]
    site_id: str
    date: date
    start: time
    seed: int
    focus_machine: str
    operator: str | None
    language: Language
    background_machines: int = 0
    background_machine_ids: list[str] = []
    tasks: list[ScenarioTask] = []
    weather_script: list[WeatherStep] = []
    beats: list[Beat] = Field(default_factory=list)

    @classmethod
    def load(cls, name: str, directory: Path = SCENARIO_DIR) -> Scenario:
        path = directory / f"{name}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"scenario '{name}' not found")
        return cls.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# --- the live site -------------------------------------------------------------------------------


class LiveSite:
    def __init__(
        self,
        cfg: ShiftMateConfig,
        scenario: Scenario,
        resources: EdgeResources,
        store: EdgeStore,
    ) -> None:
        self.cfg = cfg
        self.scenario = scenario
        self.site = cfg.sites[scenario.site_id]
        fleet = build_history_fleet(cfg, FLEET_SEED)
        at_site = {m.machine_id for m in fleet.machines_at(self.site.site_id)}
        ids = [scenario.focus_machine, *scenario.background_machine_ids]
        unknown = [m for m in ids if m not in at_site]
        if unknown:
            raise ValueError(f"machines {unknown} are not at {self.site.site_id}")
        site_index = sorted(cfg.sites).index(self.site.site_id)
        self.world = SiteWorld(cfg, self.site, fleet, site_index, scenario.seed, machine_ids=ids)
        for machine_id, agent in self.world.agents.items():
            hours = resources.last_engine_hours(machine_id)
            if hours is not None:
                agent.engine_hours = hours
        self.focus_id = scenario.focus_machine
        focus_agent = self.world.agents[self.focus_id]
        day_index = max(resources.history_days, 0) + 1
        overrides = {}
        if scenario.tasks:
            overrides[self.focus_id] = self._scenario_tasks(focus_agent)
        self.state = self.world.begin_day(
            day_index,
            scenario.date,
            1.0,
            month_number=scenario.date.month,
            task_overrides=overrides,
        )
        if any(b.action == "await_operator_sign_in" for b in scenario.beats):
            focus_agent.hold()
        tasks = {
            pt.task.task_id: TaskInfo(pt.task.task_id, pt.task.task_type, pt.task.zone_id)
            for pt in (focus_agent.plan.tasks if focus_agent.plan else [])
        }
        self.dispatch_view = DispatchView(cfg.idle_rules.params.dispatch_presence_timeout_min)
        self._log_cursor = 0
        self.runtime = MachineRuntime(
            cfg,
            focus_agent.machine,
            self.site,
            tasks,
            self.dispatch_view,
            store,
            resources,
            scenario.seed,
        )
        self.last_ticks: dict[str, dict[str, Any]] = {}
        self._task_seen: dict[str, tuple[str, int]] = {}  # task_id → (status, whole units done)

    def _scenario_tasks(self, agent) -> list[PlannedTask]:
        s = self.scenario
        rng = np.random.default_rng(np.random.SeedSequence([s.seed, 5]))
        out = []
        for n, t in enumerate(s.tasks, start=1):
            task = Task(
                task_id=f"T-{s.site_id}-{s.date:%Y%m%d}-{n}",
                site_id=s.site_id,
                machine_id=s.focus_machine,
                operator_id=s.operator or "",
                task_type=t.task_type,
                zone_id=t.zone_id,
                planned_quantity=t.planned_quantity,
                quantity_unit=t.quantity_unit,
                scheduled_start=datetime.combine(s.date, t.scheduled_start, tzinfo=self.world.tz),
                status=TaskStatus.SCHEDULED,
            )
            zone = self.site.layout.zone(t.zone_id)
            spot = zone.centroid()
            if t.task_type == "truck_loading":  # stand at the zone's edge, trucks at the centre
                spot = (spot[0] - 12.0, spot[1])
            noise = self.world.task_noise(rng)
            out.append(PlannedTask(task=task, noise=noise, work_spot=spot))
        return out

    @property
    def now(self) -> datetime:
        return self.state.now

    def local(self, t: time) -> datetime:
        return datetime.combine(self.scenario.date, t, tzinfo=self.world.tz)

    def step(self, wall: float) -> None:
        results = self.world.step()
        log = self.state.dispatcher.log
        if self._log_cursor < len(log):
            new = log[self._log_cursor :]
            self.dispatch_view.add(
                [DispatchLogEntry(e.ts, e.zone_id, e.truck_id, e.event) for e in new]
            )
            for e in new:  # the supervisor's map shows the dispatch log as it happens
                self.runtime.site_messages.append(
                    {
                        "type": "dispatch",
                        "payload": {
                            "ts": e.ts.isoformat(),
                            "zone_id": e.zone_id,
                            "truck_id": e.truck_id,
                            "event": e.event,
                        },
                    }
                )
            self._log_cursor = len(log)
        for tick, _truth in results:  # truth is never passed to the edge (golden rule 5)
            self.last_ticks[str(tick["machine_id"])] = tick
            if tick["machine_id"] == self.focus_id:
                self.runtime.step(tick, 1.0, wall)
        self._watch_tasks()

    def _watch_tasks(self) -> None:
        """Push `task_progress` when a task starts, gains a whole unit or ends; queue summaries."""
        agent = self.world.agents[self.focus_id]
        for pt in agent.plan.tasks if agent.plan else []:
            t = pt.task
            seen = (t.status.value, int(pt.progress))
            if self._task_seen.get(t.task_id) == seen or t.status == TaskStatus.SCHEDULED:
                continue
            self._task_seen[t.task_id] = seen
            self.runtime.push(
                "task_progress",
                {
                    "task_id": t.task_id,
                    "status": t.status.value,
                    "done_qty": round(min(pt.progress, t.planned_quantity), 2),
                    "planned_qty": t.planned_quantity,
                    "unit": t.quantity_unit.value,
                },
            )
            if t.status == TaskStatus.DONE and t.actual_end is not None:
                self.runtime.store.add_task_summary(
                    {
                        **t.model_dump(mode="json", exclude={"conditions_at_start"}),
                        "actual_end": t.actual_end,
                        "done_qty": round(min(pt.progress, t.planned_quantity), 2),
                    }
                )

    def entities(self) -> dict[str, Any]:
        """Everything on the site map (`/ws/site`): machines, trucks, workers."""
        machines = []
        for machine_id, tick in self.last_ticks.items():
            agent = self.world.agents[machine_id]
            profile = agent.profile
            if machine_id == self.focus_id and self.runtime.last_step is not None:
                risk = self.runtime.last_step.risk
                tier = self.runtime.telemetry(
                    self.runtime.last_step, self.runtime.last_tick or tick
                )["proximity_tier"]
                rings = vars(risk.thresholds)
            else:
                base = Thresholds(
                    profile.proximity_m.caution,
                    profile.proximity_m.danger,
                    profile.proximity_m.critical,
                    0,
                    0,
                )
                has = tick.get("proximity_m") is not None and tick["engine_on"]
                tier = proximity_tier(tick.get("proximity_m"), base).value if has else None
                rings = {
                    "caution_m": base.caution_m,
                    "danger_m": base.danger_m,
                    "critical_m": base.critical_m,
                }
            machines.append(
                {
                    "id": machine_id,
                    "type": profile.machine_type.value,
                    "tier": agent.machine.sensor_tier.value,
                    "x_m": tick["x_m"],
                    "y_m": tick["y_m"],
                    "heading_deg": tick["heading_deg"],
                    "state": "off"
                    if not tick["engine_on"]
                    else (
                        "working"
                        if tick["hydraulic_active"]
                        else ("travel" if tick["travel_speed_kmh"] >= 0.5 else "idle")
                    ),
                    "proximity_tier": tier,
                    "rings": {k: round(v, 2) for k, v in rings.items() if k.endswith("_m")},
                    "focus": machine_id == self.focus_id,
                }
            )
        workers = [
            {"id": w.worker_id, "x_m": round(w.x, 1), "y_m": round(w.y, 1)}
            for w in self.state.crowd.workers
        ]
        return {
            "ts": self.now.isoformat(),
            "site_id": self.site.site_id,
            "machines": machines,
            "trucks": self.state.dispatcher.positions(self.now),
            "workers": workers,
        }

    def forecast(self, when: datetime) -> dict[str, Any]:
        """Conditions expected at a future time: generated weather plus the scenario script."""
        o: dict[str, Any] = {}
        for step in self.scenario.weather_script:
            if self.local(step.at) <= when:
                o.update(
                    {k: v for k, v in step.model_dump().items() if k != "at" and v is not None}
                )
        saved = self.state.weather_override
        try:
            self.state.weather_override = o
            return self.world.conditions(when)
        finally:
            self.state.weather_override = saved


# --- the scenario player -------------------------------------------------------------------------


class ScenarioPlayer:
    """Plays a scenario on a LiveSite: beats, play/pause/speed/seek, captions, network toggle."""

    def __init__(self, cfg: ShiftMateConfig, resources: EdgeResources, store: EdgeStore) -> None:
        self.cfg = cfg
        self.resources = resources
        self.store = store
        self.site: LiveSite | None = None
        self.scenario: Scenario | None = None
        self.playing = False
        self.speed = 1.0
        self.captions = False
        self.online = True
        self.waiting_for: str | None = None
        self.fired: set[str] = set()
        self.snapshots: dict[str, tuple[Any, ...]] = {}
        self.events: deque[dict[str, Any]] = deque(maxlen=500)  # captions, network, waits, …
        self.camera_fallback: tuple[float, list[list[float]], float] | None = None
        self._carry = 0.0
        self.wait_started_reports = 0

    # --- lifecycle ------------------------------------------------------------------------------
    def load(self, name: str) -> None:
        self.scenario = Scenario.load(name)
        self.store.reset()
        self.site = LiveSite(self.cfg, self.scenario, self.resources, self.store)
        self.playing = False
        self.waiting_for = None
        self.fired = set()
        self.snapshots = {}
        self.online = True
        start = self.site.local(self.scenario.start)
        self._apply_weather_script()
        while self.site.now < start:  # the world runs silently up to the scenario start
            self.site.step(wall=0.0)
            self._apply_weather_script()
        self.site.runtime.drain()

    def _apply_weather_script(self) -> None:
        assert self.site and self.scenario
        o: dict[str, Any] = {}
        for step in self.scenario.weather_script:
            if self.site.local(step.at) <= self.site.now:
                o.update(
                    {k: v for k, v in step.model_dump().items() if k != "at" and v is not None}
                )
        self.site.state.weather_override = o

    def emit(self, kind: str, payload: dict[str, Any]) -> None:
        self.events.append({"type": kind, "payload": payload})

    def drain_events(self) -> list[dict[str, Any]]:
        out = list(self.events)
        self.events.clear()
        return out

    # --- advancing --------------------------------------------------------------------------------
    def advance(self, seconds: int, wall: float = 0.0, auto: bool = False) -> int:
        """Run up to `seconds` world seconds; stops early at an await beat. Returns seconds run."""
        assert self.site and self.scenario
        done = 0
        for _ in range(seconds):
            if self.waiting_for and not self._wait_satisfied(auto):
                break
            self._fire_due_beats(auto)
            if self.waiting_for and not self._wait_satisfied(auto):
                break
            self._apply_weather_script()
            self.site.step(wall)
            done += 1
        return done

    def tick_wall(self, wall_dt: float, wall: float) -> int:
        """Called by the clock task: advance `speed × wall_dt` world seconds when playing."""
        if not self.playing or self.site is None:
            return 0
        self._check_camera_fallback(wall)
        self._carry += self.speed * wall_dt
        n = int(self._carry)
        self._carry -= n
        return self.advance(n, wall) if n else 0

    def _wait_satisfied(self, auto: bool) -> bool:
        assert self.site
        beat = self.waiting_for
        if beat is None:
            return True
        ok = False
        action = next(b.action for b in self.scenario.beats if b.id == beat)  # type: ignore[union-attr]
        if action == "await_operator_sign_in":
            if auto and not self.site.runtime.operator_id:
                self.auto_sign_in()
            ok = self.site.runtime.operator_id is not None
        elif action == "await_voice_report":
            ok = auto or self.site.runtime.reports_saved > self.wait_started_reports
        if ok:
            self.waiting_for = None
            self.emit("waiting", {"beat": None})
        return ok

    def continue_(self) -> None:
        """The console's Play also releases a wait (e.g. skip the voice report)."""
        if self.waiting_for:
            self.waiting_for = None
            self.emit("waiting", {"beat": None})

    def auto_sign_in(self) -> None:
        assert self.site and self.scenario
        op = self.scenario.operator or self.site.world.agents[self.site.focus_id].plan.operator_id  # type: ignore[union-attr]
        if op:
            self.site.runtime.sign_in(op, self.scenario.language, self.site.now)

    def _fire_due_beats(self, auto: bool) -> None:
        assert self.site and self.scenario
        for beat in self.scenario.beats:
            if beat.id in self.fired or self.site.local(beat.at) > self.site.now:
                continue
            if beat.id not in self.snapshots:
                self.snapshots[beat.id] = self._snapshot()
            self.fired.add(beat.id)
            self._apply(beat, auto)
            if self.waiting_for:
                return

    # --- beat actions -----------------------------------------------------------------------------
    def _apply(self, beat: Beat, auto: bool) -> None:
        site = self.site
        assert site is not None
        now = site.now
        agent = site.world.agents[site.focus_id]
        p = beat.params
        if beat.caption:
            self.emit("scenario_caption", {"beat": beat.id, "caption": beat.caption})
        if beat.action == "await_operator_sign_in":
            if not site.runtime.operator_id:
                self.waiting_for = beat.id
                self.emit("waiting", {"beat": beat.id})
        elif beat.action == "engine_start":
            if not site.runtime.operator_id:
                self.auto_sign_in()
            agent.start_engine(now, 1.0, coolant_c=p.get("coolant_c"))
        elif beat.action == "truck_shortage":
            site.state.dispatcher.block_zone(
                p["zone"], now + timedelta(minutes=float(p["minutes"]))
            )
        elif beat.action == "camera_or_sim_person":
            path, step_s = p["path"], float(p.get("seconds_per_step", 4))
            wall = self._wall()
            if auto or not site.runtime.camera_active(wall):
                self._script_person(path, step_s)
            else:  # a live camera is on: a real person walks up; scripted only if it goes quiet
                self.camera_fallback = (wall + self.cfg.edge.camera.wait_s, path, step_s)
                self.emit("camera_beat", {"beat": beat.id, "wait_s": self.cfg.edge.camera.wait_s})
        elif beat.action == "set_signal":
            if p.get("seatbelt_fastened") is False:
                seconds = float(p.get("seconds", 20))
                agent.unbelt_for(now, seconds)
                if p.get("while") == "working":
                    agent.force(now, "work", seconds + 5, 1.0)
        elif beat.action == "skip_scheduled_break":
            day_breaks = [site.local(b.start) for b in site.site.shift.breaks]
            upcoming = [b for b in day_breaks if b >= now - timedelta(minutes=5)]
            if upcoming:
                agent.skip_break_at(min(upcoming))
        elif beat.action == "operator_leaves_seat":
            agent.force(now, "step_out", float(p.get("minutes", 6)) * 60, 1.0)
        elif beat.action == "await_voice_report":
            self.wait_started_reports = site.runtime.reports_saved
            if not auto:
                self.waiting_for = beat.id
                self.emit("waiting", {"beat": beat.id})
        elif beat.action == "set_network":
            self.set_network(bool(p["online"]))
        elif beat.action == "end_shift_summary":
            self.emit("end_shift", {"operator_id": site.runtime.operator_id})
            if not auto:
                self.playing = False
        elif beat.action == "scale_demo":
            self.emit("scale_demo", dict(p))

    def _wall(self) -> float:
        return _time.monotonic()

    def _check_camera_fallback(self, wall: float) -> None:
        """TRD §8: if the camera stops reporting during the worker_near beat, script the person."""
        if self.camera_fallback is None or self.site is None:
            return
        deadline, path, step_s = self.camera_fallback
        if not self.site.runtime.camera_active(wall):
            self.camera_fallback = None
            self._script_person(path, step_s)
        elif wall >= deadline:
            self.camera_fallback = None  # the camera carried the beat

    def _script_person(self, path: list[list[float]], seconds_per_step: float) -> None:
        """Place a person along `path` = [[forward_m, left_m], …] in front of the focus machine."""
        site = self.site
        assert site is not None
        agent = site.world.agents[site.focus_id]
        h = math.radians(agent.heading)
        fwd = (math.sin(h), math.cos(h))
        left = (-math.cos(h), math.sin(h))
        points = [
            (agent.x + f * fwd[0] + lft * left[0], agent.y + f * fwd[1] + lft * left[1])
            for f, lft in path
        ]
        # walk in over the path, hold at the closest point one more step, then leave
        points.append(points[-1])
        site.state.crowd.script_path("W-SCENARIO", points, seconds_per_step, points[0])

    def set_network(self, online: bool) -> None:
        self.online = online
        if self.site:
            self.site.runtime.record(
                EventType.CONNECTIVITY,
                self.site.now,
                "online" if online else "offline",
                {"online": online},
            )
        self.emit("connectivity", {"online": online})

    # --- seek -------------------------------------------------------------------------------------
    def _shared(self) -> dict[int, Any]:
        """Objects every snapshot shares instead of copying (store, loaded models, config)."""
        return {
            id(self.store): self.store,
            id(self.resources): self.resources,
            id(self.cfg): self.cfg,
        }

    def _snapshot(self) -> tuple[Any, ...]:
        """An in-memory copy of the live world, taken just before a beat fires."""
        assert self.site
        return copy.deepcopy((self.site, set(self.fired), self.online), self._shared())

    def seek(self, beat_id: str) -> None:
        assert self.site and self.scenario
        beat = next((b for b in self.scenario.beats if b.id == beat_id), None)
        if beat is None:
            raise KeyError(beat_id)
        target = self.site.local(beat.at)
        was_playing = self.playing
        self.playing = False
        self.waiting_for = None
        if beat_id in self.snapshots:
            site, fired, online = copy.deepcopy(self.snapshots[beat_id], self._shared())
            self.site, self.fired, self.online = site, set(fired), online
            self.store.truncate_after(target)
        elif target < self.site.now:
            name = self.scenario.name
            snaps = self.snapshots
            self.load(name)
            self.snapshots = snaps
            self._fast_forward(target)
        else:
            self._fast_forward(target)
        self.site.runtime.drain()
        self.playing = was_playing
        self.emit("seeked", {"beat": beat_id, "sim_time": self.site.now.isoformat()})

    def _fast_forward(self, target: datetime) -> None:
        assert self.site
        while self.site.now < target:
            ran = self.advance(int((target - self.site.now).total_seconds()), auto=True)
            if ran == 0 and self.waiting_for is None:
                break
