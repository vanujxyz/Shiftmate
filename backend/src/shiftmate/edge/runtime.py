"""MachineRuntime: one machine's live brain on the edge (TRD §1.1, §9.1).

Each second it takes the machine's signal tick and:
1. merges a fresh camera proximity reading (source `camera` wins over the sensor when it is
   less than 1 s old; a camera also switches proximity rules on for machines without a sensor);
2. runs the engine pipeline (state, risk, safety rules, alert policy, idle reasons, intervals);
3. stores events and interval records locally (and queues what the fleet needs in the outbox);
4. scores closed intervals for unusual behaviour against the operator's own baseline;
5. offers a lesson when a long pause begins;
6. queues messages for the cab (telemetry, mode, risk, alerts, idle segments, insights, …).

It also holds the operator session. Everything here is deterministic given the ticks, except
camera readings, which by nature arrive in real time.
"""

from __future__ import annotations

import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Any

import numpy as np

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.edge.resources import EdgeResources
from shiftmate.edge.store import EdgeStore
from shiftmate.engines.anomaly import interval_features, is_unusual
from shiftmate.engines.dispatch_view import DispatchView
from shiftmate.engines.idle_reason import IdleResult
from shiftmate.engines.lessons import (
    LessonOfferer,
    Recommendation,
    TriggerEvent,
    condition_flags,
    recommend,
)
from shiftmate.engines.pipeline import MachinePipeline, PipelineStep, TaskInfo
from shiftmate.schema.config import Site
from shiftmate.schema.enums import CabMode, EventType, IdleReason, Language, MachineState
from shiftmate.schema.intervals import IntervalRecord
from shiftmate.schema.reference import Machine
from shiftmate.util.ids import uuid7_from

log = logging.getLogger(__name__)

CAMERA_FRESH_S = 1.0  # camera overrides the sensor while its reading is this fresh (TRD §5)
CAMERA_ACTIVE_S = 5.0  # a camera that has reported recently counts as a proximity source
MESSAGE_BUFFER = 2000


class MachineRuntime:
    def __init__(
        self,
        cfg: ShiftMateConfig,
        machine: Machine,
        site: Site,
        tasks: dict[str, TaskInfo],
        dispatch: DispatchView,
        store: EdgeStore,
        resources: EdgeResources,
        seed: int,
    ) -> None:
        self.cfg = cfg
        self.machine = machine
        self.site = site
        self.store = store
        self.resources = resources
        self.pipeline = MachinePipeline(cfg, machine, site, tasks, dispatch, with_alert_policy=True)
        self.rng = np.random.default_rng(np.random.SeedSequence([seed, 991]))
        self.operator_id: str | None = None
        self.language: Language = Language.EN
        self.signed_in_at: datetime | None = None
        self.messages: deque[dict[str, Any]] = deque(maxlen=MESSAGE_BUFFER)
        self.last_step: PipelineStep | None = None
        self.last_tick: dict[str, Any] | None = None
        self.last_mode: CabMode | None = None
        self.idle_today: list[IdleResult] = []
        self.intervals_today: list[IntervalRecord] = []
        self.anomalies_today: list[dict[str, Any]] = []
        self.near_misses: list[datetime] = []
        self.reports_saved = 0
        self.offerer = LessonOfferer(cfg.lessons)
        self.start_conditions: list[str] = []
        self.camera: dict[str, Any] | None = None  # last camera reading + wall time received
        self.last_estimate_push: datetime | None = None
        self.timeline: list[list[Any]] = []  # [kind, start, end] runs for the My Day time split

    # --- session ------------------------------------------------------------------------------
    def sign_in(self, operator_id: str, language: Language, now: datetime) -> None:
        self.operator_id = operator_id
        self.language = language
        self.signed_in_at = now
        self.push("session", {"operator_id": operator_id, "language": language.value})

    def sign_out(self) -> None:
        self.operator_id = None
        self.signed_in_at = None
        self.push("session", {"operator_id": None})

    # --- messages -----------------------------------------------------------------------------
    def push(self, kind: str, payload: dict[str, Any]) -> None:
        self.messages.append({"type": kind, "payload": payload})

    def drain(self) -> list[dict[str, Any]]:
        out = list(self.messages)
        self.messages.clear()
        return out

    # --- camera ---------------------------------------------------------------------------------
    def camera_reading(
        self, distance_m: float, confidence: float, bearing: float | None, wall: float
    ) -> None:
        self.camera = {
            "distance_m": distance_m,
            "confidence": confidence,
            "bearing": bearing,
            "wall": wall,
        }

    def camera_active(self, wall: float) -> bool:
        return self.camera is not None and wall - self.camera["wall"] <= CAMERA_ACTIVE_S

    # --- the tick -------------------------------------------------------------------------------
    def step(self, tick: dict[str, Any], dt: float, wall: float) -> PipelineStep:
        tick = dict(tick)
        tick["operator_id"] = self.operator_id or tick.get("operator_id")
        extra: set[str] = set()
        age: float | None = 0.0 if tick.get("proximity_m") is not None else None
        # A camera is a real-time sensor: it only counts while the world runs live (wall > 0),
        # never during fast-forward or seek, where many world seconds pass per real second.
        if self.camera is not None and wall > 0:
            cam_age = wall - self.camera["wall"]
            if cam_age <= CAMERA_ACTIVE_S:
                extra.add("proximity_m")
            if cam_age <= CAMERA_FRESH_S:
                tick["proximity_m"] = self.camera["distance_m"]
                tick["proximity_bearing_deg"] = self.camera["bearing"]
                tick["proximity_source"] = "camera"
                age = cam_age
            elif tick.get("proximity_m") is None and "proximity_m" in extra:
                age = cam_age  # camera is the only source and it has gone quiet
        step = self.pipeline.step(tick, dt, extra_signals=extra, proximity_age_s=age)
        ts: datetime = tick["ts"]
        self.last_step, self.last_tick = step, tick

        for ev in step.events:
            self._record_event(ev, tick)
        if step.alerts is not None:
            for m in step.alerts.messages:
                self.messages.append(m)
        if step.state.mode != self.last_mode:
            self.last_mode = step.state.mode
            self.push("mode", {"mode": step.state.mode.value, "state": step.state.state.value})
        if step.risk.publish:
            self.push(
                "risk_update",
                {
                    "score": step.risk.score,
                    "band": step.risk.band.value,
                    "top": [{"component": k, "points": v} for k, v in step.risk.top],
                    "thresholds": vars(step.risk.thresholds),
                },
            )
        if step.idle.provisional is not None:
            self.push("idle_segment", step.idle.provisional.payload())
        if step.idle.closed is not None:
            self._idle_closed(step.idle.closed, ts)
        for record in step.intervals:
            self._interval_closed(record, ts)
        self._maybe_offer_lesson(step, ts)
        self._extend_timeline(step.state.state, ts, dt)
        self.push("telemetry", self.telemetry(step, tick))
        return step

    def _extend_timeline(self, state: MachineState, ts: datetime, dt: float) -> None:
        if not self.operator_id:
            return
        kind = {
            MachineState.WORKING: "working",
            MachineState.TRAVELLING: "travel",
            MachineState.ENGINE_OFF: "engine_off",
            MachineState.IDLE: "idle",
        }[state]
        end = ts + timedelta(seconds=dt)
        if self.timeline and self.timeline[-1][0] == kind and self.timeline[-1][2] == ts:
            self.timeline[-1][2] = end
        else:
            self.timeline.append([kind, ts, end])

    def telemetry(self, step: PipelineStep, tick: dict[str, Any]) -> dict[str, Any]:
        has_prox = (
            "proximity_m" in self.pipeline.signals or tick.get("proximity_source") == "camera"
        )
        return {
            "ts": tick["ts"].isoformat(),
            "machine_id": self.machine.machine_id,
            "state": step.state.state.value,
            "mode": step.state.mode.value,
            "engine_on": bool(tick["engine_on"]),
            "travel_speed_kmh": tick["travel_speed_kmh"],
            "seatbelt_fastened": bool(tick["seatbelt_fastened"]),
            "seat_occupied": tick.get("seat_occupied"),
            "proximity_m": tick.get("proximity_m") if has_prox else None,
            "proximity_bearing_deg": tick.get("proximity_bearing_deg") if has_prox else None,
            "proximity_source": tick.get("proximity_source") if has_prox else None,
            "proximity_tier": step.risk.proximity_tier.value
            if has_prox and tick["engine_on"]
            else ("clear" if has_prox else None),
            "heat_index_c": tick["heat_index_c"],
            "risk_score": step.risk.score,
            "risk_band": step.risk.band.value,
            "task_id": tick.get("task_id"),
            "task_progress_qty": tick.get("task_progress_qty", 0.0),
            "continuous_operation_min": round(step.state.continuous_operation_min, 1),
            "sensor_tier": self.machine.sensor_tier.value,
            "thresholds": vars(step.risk.thresholds),
            "x_m": tick.get("x_m"),
            "y_m": tick.get("y_m"),
            "heading_deg": tick.get("heading_deg"),
        }

    # --- helpers ----------------------------------------------------------------------------------
    def _record_event(self, ev: dict[str, Any], tick: dict[str, Any]) -> dict[str, Any]:
        row = {
            **ev,
            "event_id": uuid7_from(ev["ts"], self.rng),
            "machine_id": self.machine.machine_id,
            "operator_id": self.operator_id or tick.get("operator_id"),
            "site_id": self.site.site_id,
        }
        self.store.add_event(row)
        return row

    def record(
        self,
        kind: EventType,
        ts: datetime,
        code: str,
        payload: dict[str, Any],
        shared: bool = False,
        priority: str | None = None,
    ) -> dict[str, Any]:
        return self._record_event(
            {
                "ts": ts,
                "type": kind.value,
                "priority": priority,
                "code": code,
                "payload": payload,
                "shared_with_supervisor": shared,
            },
            self.last_tick or {},
        )

    def _idle_closed(self, result: IdleResult, ts: datetime) -> None:
        self.idle_today.append(result)
        self.push("idle_segment", result.payload())
        if result.reason == IdleReason.HABIT:
            self.push(
                "insight",
                {
                    "key": "insight.coach_short_stop",
                    "values": {
                        "minutes": round(result.duration_s / 60),
                        "fuel_l": round(result.fuel_l, 1),
                    },
                    "lesson_id": result.lesson,
                },
            )
        elif result.reason == IdleReason.UNATTENDED_RUNNING:
            self.push(
                "insight",
                {
                    "key": "insight.reminder_cab_empty",
                    "values": {
                        "minutes": round(result.duration_s / 60),
                        "fuel_l": round(result.fuel_l, 1),
                    },
                    "lesson_id": result.lesson,
                },
            )
        elif result.reason == IdleReason.WAITING_FOR_TRUCK:
            self.push(
                "insight",
                {
                    "key": "insight.truck_wait_not_you",
                    "values": {"minutes": round(result.duration_s / 60)},
                },
            )

    def _interval_closed(self, record: IntervalRecord, ts: datetime) -> None:
        self.intervals_today.append(record)
        data = record.model_dump()
        self.store.add_interval(data)
        verdict = self.score_interval(data)
        if verdict is not None:
            self.anomalies_today.append(verdict)
            self.record(
                EventType.ANOMALY, record.timestamp, verdict["top_feature"] or "p1_rule", verdict
            )
            self.push("insight", {"key": "insight.unusual_interval", "values": verdict})

    def score_interval(self, data: dict[str, Any]) -> dict[str, Any] | None:
        """TRD §6.6 decision for one live interval (None if nothing unusual or no model)."""
        cfg = self.cfg.anomaly
        values = interval_features(data)
        base = self.resources.baseline_for(
            data.get("operator_id"),
            self.machine.machine_type.value,
            data.get("task_type"),
            self.site.site_id,
        )
        signs = {f.code: 1.0 if f.higher_is_worse else -1.0 for f in cfg.features}
        worse: dict[str, float] = {}
        for code, (median, mad) in base.items():
            x = values.get(code)
            if x is None:
                continue
            worse[code] = signs[code] * (x - median) / (cfg.mad_scale * mad + cfg.epsilon)
        model = self.resources.anomaly_models.get(
            f"{self.machine.machine_type.value}_{self.machine.sensor_tier.value}"
        )
        if_top = False
        if model is not None:
            row = [[max(-10.0, min(10.0, worse.get(f, 0.0))) for f in model["features"]]]
            if_top = float(-model["model"].score_samples(row)[0]) >= model["threshold"]
        p1 = (data.get("p1_alert_count") or 0) > 0
        z_raw = {k: v * signs[k] for k, v in worse.items()}
        if not is_unusual(if_top, z_raw, p1, cfg):
            return None
        keys = {f.code: f.message_key for f in cfg.features}
        explanations = [
            {
                "feature": k,
                "message_key": keys[k],
                "value": values.get(k),
                "usual": base[k][0],
                "z": round(v, 2),
            }
            for k, v in sorted(worse.items(), key=lambda kv: -kv[1])
            if v >= cfg.z_threshold
        ][: cfg.max_explanations]
        return {
            "record_id": data["record_id"],
            "if_top": if_top,
            "p1_rule": p1,
            "explanations": explanations,
            "top_feature": explanations[0]["feature"] if explanations else None,
        }

    # --- lessons ----------------------------------------------------------------------------------
    def recommendations(self, now: datetime) -> list[Recommendation]:
        if not self.operator_id:
            return []
        events: list[TriggerEvent] = []
        hist = self.resources.history_events
        if not hist.empty:
            mine = hist[hist.operator_id == self.operator_id]
            for r in mine.itertuples():
                events.append(TriggerEvent(r.ts.to_pydatetime(), r.code))
        for e in self.store.list_events(
            operator_id=self.operator_id, since=now - timedelta(days=7)
        ):
            events.append(TriggerEvent(datetime.fromisoformat(e["ts"]), e["code"] or ""))
        for anomaly in self.anomalies_today:
            if anomaly["top_feature"]:
                events.append(TriggerEvent(now, anomaly["top_feature"]))
        for flag in self.start_conditions:
            events.append(TriggerEvent(now, flag))
        done = [
            (c["lesson_id"], datetime.fromisoformat(c["ts"]))
            for c in self.store.list_completions(self.operator_id)
        ]
        return recommend(self.cfg.lessons, events, done, now)

    def note_shift_conditions(self, conditions: dict[str, Any]) -> None:
        self.start_conditions = condition_flags(
            self.cfg.risk_model,
            float(conditions["heat_index_c"]),
            float(conditions["precipitation_mm_h"]),
            str(conditions["ground_condition"]),
            bool(conditions["is_night"]),
        )

    def _maybe_offer_lesson(self, step: PipelineStep, ts: datetime) -> None:
        if not self.operator_id:
            return
        paused = step.state.mode == CabMode.PAUSED
        provisional = step.idle.provisional.reason if step.idle.provisional else None
        if (
            paused
            and not self.offerer.offered_this_pause
            and (
                step.state.state == MachineState.ENGINE_OFF
                or provisional in (IdleReason.WAITING_FOR_TRUCK, IdleReason.SCHEDULED_BREAK)
            )
        ):
            recs = self.recommendations(ts)
            if provisional is not None:
                # the moment itself matters most: a lesson about this pause comes first (D-053)
                recent = timedelta(days=self.cfg.lessons.recommender.exclude_completed_days)
                done = {
                    c["lesson_id"]
                    for c in self.store.list_completions(self.operator_id)
                    if ts - datetime.fromisoformat(c["ts"]) <= recent
                }
                situational = [
                    Recommendation(lesson.id, 999.0, [provisional.value])
                    for lesson in self.cfg.lessons.lessons
                    if provisional.value in lesson.triggers and lesson.id not in done
                ]
                recs = situational + [
                    r for r in recs if r.lesson_id not in {s.lesson_id for s in situational}
                ]
        else:
            recs = []
        offer = self.offerer.update(ts, step.state.state, paused, provisional, recs)
        if offer is not None:
            payload = {
                "lesson_id": offer.lesson_id,
                "because": offer.triggers,
                "reason": (provisional.value if provisional else "ENGINE_OFF"),
            }
            self.record(EventType.LESSON_OFFERED, ts, offer.lesson_id, payload, priority="P4")
            self.push("lesson_offer", payload)
