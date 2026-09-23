"""The per-machine engine pipeline (TRD §1.1): one tick in, every engine's output out.

    tick → machine state → risk → safety rules → alert policy
                        ↘ idle-reason → interval builder

The same pipeline runs in two places, so there is exactly one implementation of the logic:
- the history replay (`edge/replay.py`) feeds it the stored 30 s ticks to build interval records
  and events for evaluation and fleet training;
- the live Edge Gateway (milestone 7) feeds it 1 s ticks and forwards its outputs to the cab.

It only reads what the machine's sensor tier provides (plus the site dispatch log and schedule),
never ground truth. Events are returned without ids; the caller assigns deterministic ids.
Pure: no clock reads, no I/O.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.engines.alerts import AlertPolicyEngine, AlertUpdate
from shiftmate.engines.dispatch_view import DispatchView
from shiftmate.engines.idle_reason import IdleReasonEngine, IdleResult, IdleTick, IdleUpdate
from shiftmate.engines.intervals import IntervalBuilder, IntervalTick
from shiftmate.engines.machine_state import BreakWindow, MachineStateEngine, MachineStateOutput
from shiftmate.engines.risk import RiskEngine, RiskInputs, RiskOutput
from shiftmate.engines.safety import SafetyEngine, SafetyOutput
from shiftmate.schema.config import Site
from shiftmate.schema.enums import EventType, IdleReason, MachineState, Priority
from shiftmate.schema.intervals import IntervalRecord
from shiftmate.schema.reference import Machine


@dataclass(frozen=True)
class TaskInfo:
    task_id: str
    task_type: str
    zone_id: str


@dataclass
class PipelineStep:
    ts: datetime
    state: MachineStateOutput
    risk: RiskOutput
    safety: SafetyOutput
    alerts: AlertUpdate | None
    idle: IdleUpdate
    intervals: list[IntervalRecord]
    events: list[dict[str, Any]] = field(default_factory=list)
    truck_present: bool | None = None


class MachinePipeline:
    def __init__(
        self,
        cfg: ShiftMateConfig,
        machine: Machine,
        site: Site,
        tasks: Mapping[str, TaskInfo] | None = None,
        dispatch: DispatchView | None = None,
        with_alert_policy: bool = True,
    ) -> None:
        self.cfg = cfg
        self.machine = machine
        self.site = site
        self.profile = cfg.profiles[machine.machine_type]
        self.tier = machine.sensor_tier
        self.signals = cfg.sensor_tiers.signals_for(self.tier)
        self.tasks: dict[str, TaskInfo] = dict(tasks or {})
        self.dispatch = dispatch or DispatchView(
            cfg.idle_rules.params.dispatch_presence_timeout_min
        )
        breaks = [BreakWindow(b.start, b.minutes) for b in site.shift.breaks]
        self.state = MachineStateEngine(
            cfg.alert_policy.paused_definition.idle_seconds, cfg.risk_model.rest_reset_min, breaks
        )
        self.risk = RiskEngine(cfg.risk_model, self.profile)
        self.safety = SafetyEngine(
            cfg.safety_rules, self.signals, cfg.alert_policy.default_cooldown_s
        )
        self.alerts = (
            AlertPolicyEngine(cfg.alert_policy, machine.machine_id) if with_alert_policy else None
        )
        self.idle = IdleReasonEngine(cfg.idle_rules, self.profile, self.tier)
        self.intervals = IntervalBuilder(
            machine.machine_id,
            site.site_id,
            machine.machine_type,
            self.tier,
            cfg.idle_rules.params.truck_dependent_task_types,
        )
        self.truck_tasks = set(cfg.idle_rules.params.truck_dependent_task_types)
        self.near_misses_24h = 0
        self.last_tick: Mapping[str, Any] | None = None

    def add_task(self, task: TaskInfo) -> None:
        self.tasks[task.task_id] = task

    def capabilities(self, extra_signals: Iterable[str] = ()) -> dict[str, bool]:
        return self.safety.capabilities(extra_signals)

    # ------------------------------------------------------------------------------------------
    def _truck_presence(
        self, tick: Mapping[str, Any], task: TaskInfo | None
    ) -> tuple[bool | None, str | None]:
        if task is None or task.task_type not in self.truck_tasks:
            return None, None
        if (
            "truck_in_loading_zone" in self.signals
            and tick.get("truck_in_loading_zone") is not None
        ):
            return bool(tick["truck_in_loading_zone"]), "sensor"
        return self.dispatch.truck_present(task.zone_id, tick["ts"]), "dispatch_log"

    def _in_break(self, ts: datetime) -> bool:
        return self.state._in_break_window(ts)

    def step(
        self,
        tick: Mapping[str, Any],
        dt: float,
        extra_signals: Iterable[str] = (),
        proximity_age_s: float | None = None,
    ) -> PipelineStep:
        """Process one tick (a mapping with SignalTick fields; position as x_m / y_m)."""
        ts: datetime = tick["ts"]
        extra = set(extra_signals)
        task = self.tasks.get(tick.get("task_id") or "")
        st = self.state.update(
            ts,
            bool(tick["engine_on"]),
            bool(tick["hydraulic_active"]),
            float(tick["travel_speed_kmh"]),
            dt,
        )
        working = st.state in (MachineState.WORKING, MachineState.TRAVELLING)
        proximity = tick.get("proximity_m")
        has_proximity = "proximity_m" in self.signals or "proximity_m" in extra
        risk = self.risk.update(
            ts,
            RiskInputs(
                heat_index_c=float(tick["heat_index_c"]),
                precipitation_mm_h=float(tick["precipitation_mm_h"]),
                ground_condition=tick["ground_condition"],
                is_night=bool(tick["is_night"]),
                visibility_m=float(tick["visibility_m"]),
                continuous_operation_min=st.continuous_operation_min,
                proximity_m=proximity if has_proximity else None,
                seatbelt_unfastened_while_working=working and not tick["seatbelt_fastened"],
                near_misses_last_24h=self.near_misses_24h,
            ),
        )
        th = risk.thresholds
        context = {
            **{
                k: tick.get(k)
                for k in (
                    "engine_on",
                    "hydraulic_active",
                    "travel_speed_kmh",
                    "seatbelt_fastened",
                    "seat_occupied",
                    "engine_rpm",
                    "coolant_temp_c",
                    "proximity_m",
                    "truck_in_loading_zone",
                    "heat_index_c",
                    "precipitation_mm_h",
                    "visibility_m",
                    "is_night",
                )
            },
            "caution_m": th.caution_m,
            "danger_m": th.danger_m,
            "critical_m": th.critical_m,
            "fatigue_warn_min": th.fatigue_warn_min,
            "fatigue_limit_min": th.fatigue_limit_min,
            "speed_near_person_kmh": self.profile.unsafe.speed_near_person_kmh,
            "continuous_operation_min": st.continuous_operation_min,
            "minutes_since_break": st.minutes_since_break,
            "risk_band_rank": risk.band_rank,
            "proximity_age_s": proximity_age_s if has_proximity else None,
        }
        # people-sensing rules only apply while the engine runs
        if not tick["engine_on"]:
            context["proximity_m"] = None
        safety = self.safety.update(ts, dt, context, extra)
        alerts = None
        rule_context = {
            "PROXIMITY_CAUTION": {
                "distance_m": proximity,
                "bearing_deg": tick.get("proximity_bearing_deg"),
            },
            "PROXIMITY_DANGER": {
                "distance_m": proximity,
                "bearing_deg": tick.get("proximity_bearing_deg"),
            },
            "PROXIMITY_CRITICAL": {
                "distance_m": proximity,
                "bearing_deg": tick.get("proximity_bearing_deg"),
            },
        }
        events: list[dict[str, Any]] = []
        if self.alerts is not None:
            alerts = self.alerts.update(ts, st.mode, safety, rule_context)
            events.extend(alerts.events)
        else:
            for r in safety.raised:
                events.append(
                    {
                        "ts": ts,
                        "type": EventType.ALERT.value,
                        "priority": r.priority.value,
                        "code": r.rule_id,
                        "shared_with_supervisor": r.priority
                        in self.cfg.alert_policy.supervisor_share,
                        "payload": {"message_key": r.message_key, "phase": "raised"},
                    }
                )
        if risk.band_changed:
            events.append(
                {
                    "ts": ts,
                    "type": EventType.RISK_BAND_CHANGE.value,
                    "priority": None,
                    "code": risk.band.value,
                    "shared_with_supervisor": False,
                    "payload": {"score": risk.score, "top": risk.top},
                }
            )

        truck_present, truck_source = self._truck_presence(tick, task)
        open_before = self.idle.open.start if self.idle.open else None
        idle = self.idle.update(
            IdleTick(
                ts=ts,
                dt=dt,
                state=st.state,
                seat_occupied=tick.get("seat_occupied"),
                coolant_temp_c=tick.get("coolant_temp_c"),
                ambient_temp_c=float(tick["ambient_temp_c"]),
                fuel_rate_lph=float(tick["fuel_rate_lph"]),
                engine_started_at=st.engine_started_at,
                task_type=task.task_type if task else None,
                truck_present=truck_present,
                truck_source=truck_source,
                in_break_window=self._in_break(ts),
            )
        )
        if idle.closed is not None:
            self.intervals.record_segment(idle.closed.start, idle.closed.reason)
            events.append(self._idle_event(idle.closed, tick))
        segment_start = self.idle.open.start if self.idle.open else None
        if segment_start is None and st.state == MachineState.IDLE:
            segment_start = open_before
        peek = self.idle.peek(ts)
        closed = self.intervals.add(
            IntervalTick(
                ts=ts,
                dt=dt,
                operator_id=tick.get("operator_id"),
                task_id=tick.get("task_id"),
                task_type=task.task_type if task else None,
                state=st.state,
                engine_on=bool(tick["engine_on"]),
                engine_hours=float(tick["engine_hours"]),
                fuel_rate_lph=float(tick["fuel_rate_lph"]),
                load_cycles_total=int(tick.get("load_cycles_total") or 0),
                seatbelt_fastened=bool(tick["seatbelt_fastened"]),
                seat_occupied=tick.get("seat_occupied"),
                engine_rpm=tick.get("engine_rpm"),
                travel_speed_kmh=float(tick["travel_speed_kmh"]),
                truck_present=truck_present,
                truck_known=truck_present is not None,
                truck_sensor=truck_source == "sensor" or ("truck_in_loading_zone" in self.signals),
                proximity_m=proximity if has_proximity and tick["engine_on"] else None,
                ambient_temp_c=float(tick["ambient_temp_c"]),
                relative_humidity_pct=float(tick["relative_humidity_pct"]),
                heat_index_c=float(tick["heat_index_c"]),
                precipitation_mm_h=float(tick["precipitation_mm_h"]),
                wind_kmh=float(tick["wind_kmh"]),
                visibility_m=float(tick["visibility_m"]),
                is_night=bool(tick["is_night"]),
                ground_condition=str(tick["ground_condition"]),
                continuous_operation_min=st.continuous_operation_min,
                coolant_temp_c=tick.get("coolant_temp_c"),
                task_progress_qty=float(tick.get("task_progress_qty") or 0.0),
                risk_score=risk.score,
                raised_rules=[(r.rule_id, r.priority.value) for r in safety.raised],
                idle_segment_start=segment_start if st.state == MachineState.IDLE else None,
            ),
            provisional_reason=peek.reason if peek else None,
        )
        self.last_tick = tick
        return PipelineStep(ts, st, risk, safety, alerts, idle, closed, events, truck_present)

    def _idle_event(self, result: IdleResult, tick: Mapping[str, Any]) -> dict[str, Any]:
        shared = result.reason.value in self.cfg.privacy.supervisor_sees_operator_detail_for
        return {
            "ts": result.end,
            "type": EventType.IDLE_SEGMENT.value,
            "priority": Priority.P2.value
            if result.reason == IdleReason.UNATTENDED_RUNNING
            else None,
            "code": result.reason.value,
            "shared_with_supervisor": shared,
            "payload": result.payload(),
        }

    def finish(self, end: datetime) -> tuple[list[IntervalRecord], list[dict[str, Any]]]:
        """Close any open idle segment and interval (end of day / end of replay)."""
        events: list[dict[str, Any]] = []
        closed = self.idle.close(end)
        if closed.closed is not None:
            self.intervals.record_segment(closed.closed.start, closed.closed.reason)
            events.append(self._idle_event(closed.closed, self.last_tick or {}))
        record = self.intervals.close(end)
        return ([record] if record else []), events
