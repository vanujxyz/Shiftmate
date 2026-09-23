"""Idle-reason engine: why was the machine idle? (TRD §4.7, §6.4; PRD F-INS-01..03)

1. **Segmentation.** A segment starts when the machine state becomes IDLE and ends when it leaves
   IDLE. Segments shorter than the profile's `segment_min_seconds` (60 s) are ignored. While a
   segment is open it is re-classified every 10 s (provisional); it is final when it closes.
2. **Classification** — first match in `idle_rules.yaml` order:
   - SCHEDULED_BREAK: ≥ 50 % of the segment falls inside a scheduled break window.
   - WARM_UP: starts within 2 min of engine start and, where a coolant sensor exists, the coolant
     was below the ready temperature; on basic machines the segment is short enough
     (≤ 5 min, or ≤ 15 min below 0 °C).
   - UNATTENDED_RUNNING (needs a seat sensor): the seat was empty for ≥ 120 s in the segment.
   - WAITING_FOR_TRUCK: the task needs trucks, the operator stayed seated (or the seat is not
     sensed), and no truck was present for ≥ 70 % of the segment — from the truck sensor on
     advanced machines, else from the site dispatch log (lower confidence).
   - HABIT: seated (or not sensed), not truck-limited, and at least 5 minutes long.
   - UNKNOWN: anything else ("Not sure" is an honest answer).
3. **Fuel** used while idle = Σ fuel rate × tick time.
4. **Response** comes from `idle_rules.yaml` (offer a lesson, safety reminder, coaching, none).
Each result carries a confidence (per reason and sensor tier) and the evidence codes used.
Pure: no clock reads, no I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from shiftmate.schema.config import IdleRulesConfig, MachineProfile
from shiftmate.schema.enums import IdleReason, MachineState, SensorTier


@dataclass(frozen=True)
class IdleTick:
    ts: datetime
    dt: float
    state: MachineState
    seat_occupied: bool | None
    coolant_temp_c: float | None
    ambient_temp_c: float
    fuel_rate_lph: float
    engine_started_at: datetime | None
    task_type: str | None
    truck_present: bool | None  # None when no truck information applies
    truck_source: str | None  # "sensor" | "dispatch_log"
    in_break_window: bool


@dataclass
class _Open:
    start: datetime
    duration_s: float = 0.0
    seat_empty_s: float = 0.0
    seat_known: bool = True
    truck_absent_s: float = 0.0
    truck_known_s: float = 0.0
    truck_source: str | None = None
    break_s: float = 0.0
    fuel_l: float = 0.0
    starts_after_engine_start_s: float | None = None
    coolant_at_start: float | None = None
    ambient_at_start: float = 0.0
    task_type: str | None = None
    last_provisional_s: float = 0.0


@dataclass(frozen=True)
class IdleResult:
    start: datetime
    end: datetime
    duration_s: float
    reason: IdleReason
    confidence: float
    evidence: list[str]
    fuel_l: float
    response: str
    supervisor: str
    lesson: str | None
    provisional: bool

    def payload(self) -> dict:
        return {
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "duration_s": round(self.duration_s, 1),
            "reason": self.reason.value,
            "confidence": self.confidence,
            "evidence": self.evidence,
            "fuel_l": round(self.fuel_l, 3),
            "response_taken": self.response,
            "provisional": self.provisional,
        }


@dataclass
class IdleUpdate:
    provisional: IdleResult | None = None
    closed: IdleResult | None = None
    discarded: bool = False
    extra: list[IdleResult] = field(default_factory=list)


class IdleReasonEngine:
    def __init__(self, rules: IdleRulesConfig, profile: MachineProfile, tier: SensorTier) -> None:
        self.rules = rules
        self.profile = profile
        self.tier = tier
        self.open: _Open | None = None

    # --- classification ----------------------------------------------------------------------
    def _conf(self, key: str) -> float:
        return self.rules.confidence[key][self.tier]

    def classify(self, seg: _Open, end: datetime, provisional: bool) -> IdleResult:
        p = self.rules.params
        dur = max(seg.duration_s, 1e-9)
        reason = IdleReason.UNKNOWN
        evidence: list[str] = []
        confidence = self._conf("UNKNOWN")
        seat_sensed = seg.seat_known and self.tier != SensorTier.BASIC
        seated = (
            not seat_sensed
        ) or seg.seat_empty_s < self.profile.idle.unattended_seat_empty_seconds
        truck_task = seg.task_type in p.truck_dependent_task_types
        truck_limited = (
            truck_task
            and seg.truck_known_s > 0
            and seg.truck_absent_s / dur >= p.truck_absent_min_fraction
        )
        for candidate in self.rules.order:
            if (
                candidate == IdleReason.SCHEDULED_BREAK
                and seg.break_s / dur >= p.break_overlap_min_fraction
            ):
                reason, evidence, confidence = (
                    candidate,
                    ["in_break_window"],
                    self._conf("SCHEDULED_BREAK"),
                )
                break
            if candidate == IdleReason.WARM_UP and (
                seg.starts_after_engine_start_s is not None
                and seg.starts_after_engine_start_s <= p.warmup_start_window_s
            ):
                if seg.coolant_at_start is not None:
                    if seg.coolant_at_start < self.profile.warm_up.coolant_ready_c:
                        reason = candidate
                        evidence = ["after_engine_start", "coolant_cold"]
                        confidence = self._conf("WARM_UP_COOLANT")
                        break
                else:
                    cold = seg.ambient_at_start < 0
                    limit = (
                        self.profile.warm_up.max_minutes_below_0c
                        if cold
                        else self.profile.warm_up.max_minutes_normal
                    )
                    if dur <= limit * 60:
                        reason = candidate
                        evidence = ["after_engine_start", "time_based"]
                        confidence = self._conf("WARM_UP_TIME")
                        break
            if (
                candidate == IdleReason.UNATTENDED_RUNNING
                and seat_sensed
                and seg.seat_empty_s >= self.profile.idle.unattended_seat_empty_seconds
            ):
                reason, evidence, confidence = (
                    candidate,
                    ["seat_empty"],
                    self._conf("UNATTENDED_RUNNING"),
                )
                break
            if candidate == IdleReason.WAITING_FOR_TRUCK and truck_limited and seated:
                source = (
                    "no_truck_sensor" if seg.truck_source == "sensor" else "no_truck_dispatch_log"
                )
                reason, evidence, confidence = candidate, [source], self._conf("WAITING_FOR_TRUCK")
                break
            if (
                candidate == IdleReason.HABIT
                and seated
                and not truck_limited
                and dur >= self.profile.idle.habit_threshold_minutes * 60
            ):
                ev = (
                    ["seated_idle", "long_idle"]
                    if seat_sensed
                    else ["long_idle", "seat_not_sensed"]
                )
                reason, evidence, confidence = candidate, ev, self._conf("HABIT")
                break
            if candidate == IdleReason.UNKNOWN:
                reason, evidence, confidence = candidate, ["no_clear_cause"], self._conf("UNKNOWN")
                break
        response = self.rules.responses[reason]
        return IdleResult(
            start=seg.start,
            end=end,
            duration_s=seg.duration_s,
            reason=reason,
            confidence=confidence,
            evidence=evidence,
            fuel_l=seg.fuel_l,
            response=response.operator,
            supervisor=response.supervisor,
            lesson=response.lesson,
            provisional=provisional,
        )

    # --- per tick ----------------------------------------------------------------------------
    def update(self, t: IdleTick) -> IdleUpdate:
        out = IdleUpdate()
        if t.state == MachineState.IDLE:
            if self.open is None:
                after = (
                    (t.ts - t.engine_started_at).total_seconds()
                    if t.engine_started_at is not None
                    else None
                )
                self.open = _Open(
                    start=t.ts,
                    starts_after_engine_start_s=after,
                    coolant_at_start=t.coolant_temp_c,
                    ambient_at_start=t.ambient_temp_c,
                    task_type=t.task_type,
                )
            seg = self.open
            seg.duration_s += t.dt
            seg.fuel_l += t.fuel_rate_lph * t.dt / 3600
            if t.seat_occupied is None:
                seg.seat_known = False
            elif not t.seat_occupied:
                seg.seat_empty_s += t.dt
            if t.truck_present is not None:
                seg.truck_known_s += t.dt
                seg.truck_source = t.truck_source
                if not t.truck_present:
                    seg.truck_absent_s += t.dt
            if t.in_break_window:
                seg.break_s += t.dt
            if seg.task_type is None:
                seg.task_type = t.task_type
            p = self.rules.params
            min_s = self.profile.idle.segment_min_seconds
            if seg.duration_s >= min_s and (
                seg.duration_s - seg.last_provisional_s >= p.provisional_update_s
                or seg.last_provisional_s == 0
            ):
                seg.last_provisional_s = seg.duration_s
                end = t.ts + timedelta(seconds=t.dt)
                out.provisional = self.classify(seg, end, provisional=True)
            return out
        if self.open is not None:
            out = self.close(t.ts)
        return out

    def close(self, end: datetime) -> IdleUpdate:
        """Close the open segment at `end` (state left IDLE, or the day ended)."""
        out = IdleUpdate()
        seg = self.open
        self.open = None
        if seg is None:
            return out
        if seg.duration_s < self.profile.idle.segment_min_seconds:
            out.discarded = True
            return out
        out.closed = self.classify(seg, end, provisional=False)
        return out

    def peek(self, end: datetime) -> IdleResult | None:
        """Provisional classification of the open segment (used when an interval closes)."""
        if self.open is None or self.open.duration_s < self.profile.idle.segment_min_seconds:
            return None
        return self.classify(self.open, end, provisional=True)
