"""Lesson recommender (TRD §6.9; PRD F-LRN-02, F-LRN-03).

Recommending: for each operator, count the triggers seen in their events over the last 7 days —
idle reasons (e.g. UNATTENDED_RUNNING), safety rule ids (e.g. SEATBELT_MOVING), anomaly feature
codes (e.g. idle_habit_min) and condition flags from the start of the shift (HEAT, RAIN, NIGHT,
WET_GROUND). Each lesson scores Σ over its triggers of count × recency, where recency =
1 / (1 + days since that trigger was last seen). The top 3 are recommended, skipping lessons
completed in the last 3 days.

Offering: a lesson is offered (a quiet P4 `lesson_offered`) only when a pause begins that is
expected to last at least 90 s — waiting for a truck, a scheduled break, or the engine switched
off — and at most once every 30 minutes. Never while working (F-LRN-03).
Pure: events, completions and times are passed in.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

from shiftmate.engines.risk import banded_points
from shiftmate.schema.config import LessonsConfig, RiskModelConfig
from shiftmate.schema.enums import ConditionFlag, GroundCondition, IdleReason, MachineState

LONG_PAUSE_REASONS = {IdleReason.WAITING_FOR_TRUCK, IdleReason.SCHEDULED_BREAK}


@dataclass(frozen=True)
class TriggerEvent:
    ts: datetime
    code: str  # idle reason, rule id, anomaly feature code or condition flag


@dataclass(frozen=True)
class Recommendation:
    lesson_id: str
    score: float
    triggers: list[str]


def condition_flags(
    risk_model: RiskModelConfig,
    heat_index_c: float,
    precipitation_mm_h: float,
    ground: str,
    is_night: bool,
) -> list[str]:
    """Condition triggers at shift start: a condition counts when it scores risk points."""
    c = risk_model.components
    flags = []
    if banded_points(c.heat_index_c, heat_index_c) > 0:
        flags.append(ConditionFlag.HEAT.value)
    if banded_points(c.precipitation_mm_h, precipitation_mm_h) > 0:
        flags.append(ConditionFlag.RAIN.value)
    if ground in (GroundCondition.WET, GroundCondition.MUDDY):
        flags.append(ConditionFlag.WET_GROUND.value)
    if is_night:
        flags.append(ConditionFlag.NIGHT.value)
    return flags


def recommend(
    config: LessonsConfig,
    events: Iterable[TriggerEvent],
    completed: Iterable[tuple[str, datetime]],
    now: datetime,
) -> list[Recommendation]:
    p = config.recommender
    since = now - timedelta(days=p.window_days)
    counts: dict[str, int] = {}
    last_seen: dict[str, datetime] = {}
    for e in events:
        if since <= e.ts <= now:
            counts[e.code] = counts.get(e.code, 0) + 1
            last_seen[e.code] = max(last_seen.get(e.code, e.ts), e.ts)
    recent_done = {
        lesson_id
        for lesson_id, ts in completed
        if now - ts <= timedelta(days=p.exclude_completed_days)
    }
    scored: list[Recommendation] = []
    for lesson in config.lessons:
        if lesson.id in recent_done:
            continue
        score = 0.0
        hits = []
        for trigger in lesson.triggers:
            if trigger in counts:
                days = (now - last_seen[trigger]).total_seconds() / 86400
                score += counts[trigger] / (1 + days)
                hits.append(trigger)
        if score > 0:
            scored.append(Recommendation(lesson.id, round(score, 3), hits))
    scored.sort(key=lambda r: (-r.score, r.lesson_id))
    return scored[: p.max_recommendations]


class LessonOfferer:
    """Decides when a pause is a good moment to offer a lesson."""

    def __init__(self, config: LessonsConfig) -> None:
        self.p = config.recommender
        self.last_offer: datetime | None = None
        self.offered_this_pause = False

    def update(
        self,
        ts: datetime,
        state: MachineState,
        paused: bool,
        provisional_idle_reason: IdleReason | None,
        recommendations: list[Recommendation],
    ) -> Recommendation | None:
        if not paused:
            self.offered_this_pause = False
            return None
        if self.offered_this_pause or not recommendations:
            return None
        long_pause = (
            state == MachineState.ENGINE_OFF or provisional_idle_reason in LONG_PAUSE_REASONS
        )
        if not long_pause:
            return None
        if self.last_offer and ts - self.last_offer < timedelta(minutes=self.p.offer_min_gap_min):
            return None
        self.last_offer = ts
        self.offered_this_pause = True
        return recommendations[0]
