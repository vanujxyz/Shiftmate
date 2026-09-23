"""Pydantic models for every file in `config/` (TRD §4).

Golden rule 3: every threshold, weight, distance, lesson, rule, site and machine profile lives in
config and is validated here. Models forbid unknown keys so a typo fails fast at start-up.
"""

from __future__ import annotations

import re
from datetime import time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from shiftmate.schema.enums import (
    GroundCondition,
    IdleReason,
    Language,
    LessonFormat,
    MachineType,
    Priority,
    ProximityTier,
    QuantityUnit,
    ReportType,
    RiskBand,
    SensorTier,
    ZoneType,
)

UPPER_SNAKE = re.compile(r"^[A-Z][A-Z0-9_]*$")


class Strict(BaseModel):
    """Base for config models: unknown keys are errors."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class LocalizedText(Strict):
    """A user-facing string in all three languages (golden rule 10)."""

    en: str = Field(min_length=1)
    hi: str = Field(min_length=1)
    ta: str = Field(min_length=1)

    def get(self, language: Language | str) -> str:
        return getattr(self, str(language))


# --- machine profiles (§4.1) ---------------------------------------------------------------


class MinMax(Strict):
    min: float
    max: float

    @model_validator(mode="after")
    def _ordered(self) -> MinMax:
        if self.min > self.max:
            raise ValueError("min must be <= max")
        return self


class MeanSd(Strict):
    mean: float = Field(gt=0)
    sd: float = Field(ge=0)


class FuelRates(Strict):
    idle: float = Field(gt=0)
    working: float = Field(gt=0)
    travel: float = Field(gt=0)


class RpmLevels(Strict):
    idle: float = Field(gt=0)
    working: float = Field(gt=0)


class WarmUp(Strict):
    coolant_ready_c: float
    max_minutes_normal: float = Field(gt=0)
    max_minutes_below_0c: float = Field(gt=0)


class IdleThresholds(Strict):
    segment_min_seconds: float = Field(gt=0)
    habit_threshold_minutes: float = Field(gt=0)
    unattended_seat_empty_seconds: float = Field(gt=0)


class ProximityDistances(Strict):
    caution: float = Field(gt=0)
    danger: float = Field(gt=0)
    critical: float = Field(gt=0)

    @model_validator(mode="after")
    def _ordered(self) -> ProximityDistances:
        if not self.caution > self.danger > self.critical:
            raise ValueError("proximity distances must satisfy caution > danger > critical")
        return self


class UnsafeThresholds(Strict):
    speed_near_person_kmh: float = Field(gt=0)
    continuous_operation_warn_min: float = Field(gt=0)
    continuous_operation_limit_min: float = Field(gt=0)


class TaskProfile(Strict):
    """How a task type behaves for this machine type (used by the simulator and estimation)."""

    quantity_unit: QuantityUnit
    base_rate_per_h: float = Field(gt=0)  # quantity units per productive hour, good conditions
    truck_dependent: bool = False
    typical_quantity: MinMax


class MachineProfile(Strict):
    machine_type: MachineType
    display_name: LocalizedText
    id_prefix: str = Field(pattern=r"^[A-Z]{3}$")
    example_models: list[str] = Field(min_length=1)
    load_cycle_definition: str
    passes_per_load: MinMax
    seconds_per_pass: MeanSd
    fuel_lph: FuelRates
    rpm: RpmLevels
    max_travel_speed_kmh: float = Field(gt=0)
    warm_up: WarmUp
    idle: IdleThresholds
    proximity_m: ProximityDistances
    unsafe: UnsafeThresholds
    task_types: list[str] = Field(min_length=1)
    tasks: dict[str, TaskProfile]

    @model_validator(mode="after")
    def _tasks_match(self) -> MachineProfile:
        if set(self.task_types) != set(self.tasks):
            raise ValueError("task_types and tasks must list the same task types")
        return self


# --- sensor tiers (§4.2) -------------------------------------------------------------------


class TierDefinition(Strict):
    inherits: SensorTier | None = None
    signals: list[str]


class SensorTiersConfig(Strict):
    tiers: dict[SensorTier, TierDefinition]
    feature_availability: dict[str, list[SensorTier]]

    @model_validator(mode="after")
    def _all_tiers(self) -> SensorTiersConfig:
        if set(self.tiers) != set(SensorTier):
            raise ValueError("sensor_tiers must define basic, standard and advanced")
        return self

    def signals_for(self, tier: SensorTier) -> set[str]:
        """All signals available at a tier, following `inherits`."""
        out: set[str] = set()
        current: SensorTier | None = tier
        seen: set[SensorTier] = set()
        while current is not None:
            if current in seen:
                raise ValueError(f"sensor tier inheritance loop at {current}")
            seen.add(current)
            definition = self.tiers[current]
            out |= set(definition.signals)
            current = definition.inherits
        return out

    def feature_enabled(self, feature: str, tier: SensorTier) -> bool:
        return tier in self.feature_availability.get(feature, [])


# --- sites (§4.3) --------------------------------------------------------------------------


class MonthProfile(Strict):
    temp_mean_c: float
    temp_amp_c: float = Field(ge=0)
    rh_mean: float = Field(ge=0, le=100)
    rain_prob: float = Field(ge=0, le=1)  # probability an hour starts raining (Markov dry→rain)
    rain_mean_mm_h: float = Field(default=3.0, gt=0)
    wind_mean_kmh: float = Field(default=10.0, ge=0)
    dust_event_prob: float = Field(default=0.0, ge=0, le=1)  # per hour, lowers visibility
    fog_prob: float = Field(default=0.0, ge=0, le=1)  # per hour, lowers visibility


class SeasonSpan(Strict):
    """History days [first, last] (1-based, inclusive) use this month's climate and daylight."""

    days: tuple[int, int]
    month: int = Field(ge=1, le=12)


class Climate(Strict):
    month_profiles: dict[int, MonthProfile]
    history_seasons: list[SeasonSpan] = Field(min_length=1)

    @model_validator(mode="after")
    def _seasons_known(self) -> Climate:
        for span in self.history_seasons:
            if span.month not in self.month_profiles:
                raise ValueError(f"history season month {span.month} has no month profile")
        return self


class BreakWindow(Strict):
    start: time
    minutes: int = Field(gt=0)


class Shift(Strict):
    start: time
    end: time
    breaks: list[BreakWindow]


class Size(Strict):
    w: float = Field(gt=0)
    h: float = Field(gt=0)


class Zone(Strict):
    id: str = Field(pattern=r"^[A-Z0-9-]+$")
    type: ZoneType
    polygon: list[tuple[float, float]] | None = None
    polyline: list[tuple[float, float]] | None = None

    @model_validator(mode="after")
    def _one_shape(self) -> Zone:
        if (self.polygon is None) == (self.polyline is None):
            raise ValueError(f"zone {self.id} needs exactly one of polygon or polyline")
        return self

    def centroid(self) -> tuple[float, float]:
        points = self.polygon or self.polyline or []
        return (
            sum(p[0] for p in points) / len(points),
            sum(p[1] for p in points) / len(points),
        )


class Layout(Strict):
    size: Size
    zones: list[Zone]

    @model_validator(mode="after")
    def _zones_valid(self) -> Layout:
        ids = [z.id for z in self.zones]
        if len(ids) != len(set(ids)):
            raise ValueError("zone ids must be unique")
        for zone in self.zones:
            for x, y in zone.polygon or zone.polyline or []:
                if not (0 <= x <= self.size.w and 0 <= y <= self.size.h):
                    raise ValueError(f"zone {zone.id} point ({x}, {y}) is outside the site")
        return self

    def zone(self, zone_id: str) -> Zone:
        for zone in self.zones:
            if zone.id == zone_id:
                return zone
        raise KeyError(zone_id)

    def zones_of(self, zone_type: ZoneType) -> list[Zone]:
        return [z for z in self.zones if z.type == zone_type]


class ShortageWindow(Strict):
    day: int = Field(ge=1)
    start: time
    minutes: int = Field(gt=0)


class Trucks(Strict):
    count: int = Field(ge=0)
    dispatch_mean_interval_min: float = Field(gt=0)
    shortage_windows: list[ShortageWindow] = []  # scripted ones; random ones come from the sim
    random_shortages_per_week: MinMax = MinMax(min=1, max=2)
    random_shortage_minutes: MinMax = MinMax(min=20, max=90)
    shortage_interval_multiplier: float = Field(default=3.0, ge=1)


class Workers(Strict):
    count: int = Field(ge=0)
    swing_entry_prob_per_h: float = Field(default=0.05, ge=0, le=1)  # per machine-hour


class FleetMix(Strict):
    excavator: int = Field(ge=0)
    wheel_loader: int = Field(ge=0)
    dozer: int = Field(ge=0)

    def count(self, machine_type: MachineType) -> int:
        return getattr(self, machine_type.value)


class Site(Strict):
    site_id: str = Field(pattern=r"^[A-Z]{3}-[A-Z]{2,3}-\d{2}$")
    name: str
    country: str = Field(pattern=r"^[A-Z]{2}$")
    timezone: str
    latitude: float = Field(ge=-90, le=90)
    locale_default: Language
    languages: list[Language] = Field(min_length=1)
    units: Literal["metric"]
    climate: Climate
    shift: Shift
    layout: Layout
    trucks: Trucks
    workers: Workers
    fleet: FleetMix
    operators: int = Field(gt=0)
    ground_baseline: GroundCondition = GroundCondition.DRY
    training_centre: str
    operator_names: list[str] = Field(min_length=1)
    safety_overrides: dict[str, float] = {}

    @model_validator(mode="after")
    def _consistent(self) -> Site:
        if self.locale_default not in self.languages:
            raise ValueError("locale_default must be one of languages")
        return self


# --- safety rules (§4.4) -------------------------------------------------------------------


class SafetyRule(Strict):
    id: str
    when: str = Field(min_length=1)
    priority: Priority
    message_key: str = Field(pattern=r"^alert\.[a-z0-9_]+$")
    sustain_s: float = Field(default=0, ge=0)
    cooldown_s: float | None = Field(default=None, ge=0)  # None → alert_policy.default_cooldown_s
    requires_signals: list[str] = []
    trigger: Literal["level", "edge"] = "level"  # edge: fire only when the condition becomes true
    category: Literal["seatbelt", "proximity", "unattended", "fatigue", "heat", "risk"]

    @field_validator("id")
    @classmethod
    def _upper(cls, v: str) -> str:
        if not UPPER_SNAKE.match(v):
            raise ValueError("rule ids are UPPER_SNAKE")
        return v


class SafetyRulesConfig(Strict):
    rules: list[SafetyRule]

    @model_validator(mode="after")
    def _unique(self) -> SafetyRulesConfig:
        ids = [r.id for r in self.rules]
        if len(ids) != len(set(ids)):
            raise ValueError("safety rule ids must be unique")
        return self

    def rule(self, rule_id: str) -> SafetyRule:
        for rule in self.rules:
            if rule.id == rule_id:
                return rule
        raise KeyError(rule_id)


# --- risk model (§4.5) ---------------------------------------------------------------------


class Band(Strict):
    """One step of a banded component: `lt` (score while value < lt) or a final `gte`."""

    lt: float | None = None
    gte: float | None = None
    points: int = Field(ge=0)

    @model_validator(mode="after")
    def _one_bound(self) -> Band:
        if (self.lt is None) == (self.gte is None):
            raise ValueError("each band needs exactly one of lt or gte")
        return self


class PerEventCap(Strict):
    per_event: int = Field(ge=0)
    max: int = Field(ge=0)


class RiskComponents(Strict):
    heat_index_c: list[Band]
    precipitation_mm_h: list[Band]
    ground_condition: dict[GroundCondition, int]
    is_night: dict[bool, int]
    visibility_m: list[Band]
    continuous_operation_min: list[Band]
    proximity_state: dict[ProximityTier, int]
    seatbelt_unfastened_while_working: dict[bool, int]
    near_miss_last_24h: PerEventCap


class Scaling(Strict):
    proximity: float = Field(ge=1)
    fatigue: float = Field(ge=1)


class HeatFatigueOverride(Strict):
    heat_index_gte: float
    fatigue_divisor: float = Field(ge=1)


class RiskModelConfig(Strict):
    components: RiskComponents
    bands: dict[RiskBand, tuple[int, int]]
    threshold_scaling: dict[RiskBand, Scaling]
    heat_fatigue_override: HeatFatigueOverride
    max_score: int = 100
    hysteresis_down_s: float = Field(default=120, ge=0)
    publish_min_delta: int = Field(default=3, ge=1)
    top_contributors: int = Field(default=3, ge=1)
    rest_reset_min: float = Field(default=10, gt=0)

    @model_validator(mode="after")
    def _bands_cover(self) -> RiskModelConfig:
        if set(self.bands) != set(RiskBand) or set(self.threshold_scaling) != set(RiskBand):
            raise ValueError("bands and threshold_scaling must define green, amber and red")
        ordered = [self.bands[b] for b in (RiskBand.GREEN, RiskBand.AMBER, RiskBand.RED)]
        if ordered[0][0] != 0 or ordered[-1][1] != self.max_score:
            raise ValueError("risk bands must cover 0..max_score")
        for (_, hi), (lo, _) in zip(ordered, ordered[1:], strict=False):
            if lo != hi + 1:
                raise ValueError("risk bands must be contiguous")
        return self


# --- alert policy (§4.6) -------------------------------------------------------------------


class PriorityPolicy(Strict):
    presentation: Literal["takeover", "banner", "strip", "feed"]
    sound: Literal["critical_tone", "urgent_tone", "none"]
    speak: bool
    requires_ack: bool
    escalate_after_s: float | None = None
    deliver_when: Literal["always", "paused"] = "always"


class PausedDefinition(Strict):
    idle_seconds: float = Field(gt=0)


class AlertPolicyConfig(Strict):
    priorities: dict[Priority, PriorityPolicy]
    max_interrupting_alerts: int = Field(ge=1)
    default_cooldown_s: float = Field(ge=0)
    dedupe_window_s: float = Field(ge=0)
    paused_definition: PausedDefinition
    supervisor_share: list[Priority]
    ack_recheck_s: float = Field(default=3, ge=0)
    reduced_p1_repeat_s: float = Field(default=5, gt=0)
    queue_reevaluate_s: float = Field(default=30, gt=0)
    p1_speech_repeat_s: float = Field(default=4, gt=0)
    p2_tone_repeat_s: float = Field(default=20, gt=0)
    p3_snooze_min: float = Field(default=10, gt=0)
    live_in_rail_while_working: list[str] = []  # rule ids shown on the Reach, not as a strip

    @model_validator(mode="after")
    def _all_priorities(self) -> AlertPolicyConfig:
        if set(self.priorities) != set(Priority):
            raise ValueError("alert policy must define P1..P4")
        return self


# --- idle rules (§4.7) ---------------------------------------------------------------------


class IdleResponse(Strict):
    operator: Literal["none", "offer_lesson", "safety_reminder_on_return", "coach_after_segment"]
    supervisor: Literal["none", "site_issue_truck_supply", "safety_event", "aggregate_only"]
    lesson: str | None = None


class IdleParams(Strict):
    break_overlap_min_fraction: float = Field(gt=0, le=1)
    warmup_start_window_s: float = Field(gt=0)
    truck_absent_min_fraction: float = Field(gt=0, le=1)
    provisional_update_s: float = Field(gt=0)
    truck_dependent_task_types: list[str]
    dispatch_presence_timeout_min: float = Field(default=15, gt=0)


class IdleRulesConfig(Strict):
    order: list[IdleReason]
    responses: dict[IdleReason, IdleResponse]
    params: IdleParams
    confidence: dict[str, dict[SensorTier, float]]

    @model_validator(mode="after")
    def _complete(self) -> IdleRulesConfig:
        if sorted(self.order) != sorted(IdleReason) or len(self.order) != len(IdleReason):
            raise ValueError("idle order must list every idle reason exactly once")
        if set(self.responses) != set(IdleReason):
            raise ValueError("idle responses must cover every idle reason")
        for key, per_tier in self.confidence.items():
            if set(per_tier) != set(SensorTier):
                raise ValueError(f"confidence {key} must give basic, standard and advanced")
            if any(not 0 <= v <= 1 for v in per_tier.values()):
                raise ValueError(f"confidence {key} values must be in [0, 1]")
        return self


# --- privacy (§4.8) ------------------------------------------------------------------------


class PrivacyConfig(Strict):
    supervisor_sees_operator_detail_for: list[str]
    supervisor_aggregates_min_group_size: int = Field(ge=1)
    truck_wait_attribution: Literal["site"]
    fleet_upload: list[Literal["interval_summaries", "task_summaries", "events_shared"]]


# --- edge gateway (§9.1, §9.3) --------------------------------------------------------------


class FeedsConfig(Strict):
    telemetry_hz: float = Field(gt=0)
    site_entities_hz: float = Field(gt=0)
    estimate_update_sim_s: int = Field(gt=0)


class CameraConfig(Strict):
    fresh_s: float = Field(gt=0)
    active_s: float = Field(gt=0)
    wait_s: float = Field(ge=0)


class SyncConfig(Strict):
    interval_s: float = Field(gt=0)
    batch_size: int = Field(ge=1, le=500)
    timeout_s: float = Field(gt=0)
    backoff_max_s: float = Field(gt=0)
    model_check_s: float = Field(gt=0)


class EdgeConfig(Strict):
    feeds: FeedsConfig
    camera: CameraConfig
    sync: SyncConfig


# --- anomaly and estimation (§6.6, §6.7) ---------------------------------------------------


class AnomalyFeature(Strict):
    code: str = Field(pattern=r"^[a-z0-9_]+$")
    message_key: str = Field(pattern=r"^insight\.[a-z0-9_]+$")
    higher_is_worse: bool = True


class IsolationForestParams(Strict):
    n_estimators: int = Field(gt=0)
    contamination: float = Field(gt=0, lt=0.5)
    random_state: int


class AnomalyConfig(Strict):
    features: list[AnomalyFeature]
    baseline_days: int = Field(gt=0)
    baseline_min_intervals: int = Field(gt=0)
    mad_scale: float = Field(gt=0)
    epsilon: float = Field(gt=0)
    z_threshold: float = Field(gt=0)
    if_top_fraction: float = Field(gt=0, lt=1)
    max_explanations: int = Field(ge=1)
    isolation_forest: IsolationForestParams

    def codes(self) -> list[str]:
        return [f.code for f in self.features]


class LightGbmParams(Strict):
    num_leaves: int
    learning_rate: float
    n_estimators: int
    min_data_in_leaf: int
    early_stopping_rounds: int


class DaySplit(Strict):
    train: tuple[int, int]
    validation: tuple[int, int]
    test: tuple[int, int]


class ReasonKeys(Strict):
    """Message key when a feature makes the task slower / faster (None = not shown as a reason)."""

    slower: str | None = Field(default=None, pattern=r"^reason\.[a-z0-9_{}]+$")  # {value} allowed
    faster: str | None = Field(default=None, pattern=r"^reason\.[a-z0-9_{}]+$")

    def expanded(self, values: list[str]) -> list[str]:
        """All concrete keys (a `{value}` key expands for every possible feature value)."""
        out = []
        for key in (self.slower, self.faster):
            if key is None:
                continue
            out.extend([key.replace("{value}", v) for v in values] if "{value}" in key else [key])
        return out


class EstimationConfig(Strict):
    quantiles: list[float]
    features: list[str]
    categorical: list[str]
    lightgbm: LightGbmParams
    split_days: DaySplit
    skill_window_days: int = Field(gt=0)
    blend_max_weight: float = Field(gt=0, le=1)
    top_reasons: int = Field(ge=1)
    reason_keys: dict[str, ReasonKeys]  # source feature → message keys by direction
    reference_values: dict[str, str | float] = {}  # what-if baseline per reason feature (D-054)
    min_similar_days_for_confidence: int = Field(ge=1)


# --- lessons (§4.9) and checklist (§4.10) --------------------------------------------------


class LessonCard(Strict):
    text: LocalizedText
    illustration: str = Field(pattern=r"^[a-z0-9-]+$")


class QuizQuestion(Strict):
    q: LocalizedText
    options: list[LocalizedText] = Field(min_length=2, max_length=4)
    answer: int = Field(ge=0)
    explain: LocalizedText

    @model_validator(mode="after")
    def _answer_in_range(self) -> QuizQuestion:
        if self.answer >= len(self.options):
            raise ValueError("quiz answer index is out of range")
        return self


class DrillHazard(Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    text: LocalizedText
    is_hazard: bool  # False = a normal scene where the right decision is not to stop
    scene: str = Field(pattern=r"^[a-z0-9-]+$")


class Lesson(Strict):
    id: str = Field(pattern=r"^[LD]-[A-Z0-9-]+$")
    title: LocalizedText
    format: LessonFormat
    duration_s: int = Field(ge=60, le=180)  # PRD F-LRN-01: 1–3 minutes (D-013)
    triggers: list[str]
    cards: list[LessonCard] = []
    quiz: list[QuizQuestion] = []
    hazards: list[DrillHazard] = []

    @model_validator(mode="after")
    def _shape_matches_format(self) -> Lesson:
        if self.format == LessonFormat.NARRATED_CARDS and not 3 <= len(self.cards) <= 6:
            raise ValueError(f"{self.id}: narrated lessons need 3–6 cards")
        if self.format == LessonFormat.QUIZ and len(self.quiz) < 3:
            raise ValueError(f"{self.id}: quiz lessons need at least 3 questions")
        if self.format == LessonFormat.DRILL and len(self.hazards) < 5:
            raise ValueError(f"{self.id}: drills need at least 5 hazard scenes")
        return self


class RecommenderParams(Strict):
    window_days: int = Field(gt=0)
    max_recommendations: int = Field(ge=1)
    exclude_completed_days: int = Field(ge=0)
    min_expected_pause_s: float = Field(ge=0)
    offer_min_gap_min: float = Field(ge=0)


class LessonsConfig(Strict):
    recommender: RecommenderParams
    lessons: list[Lesson]

    def lesson(self, lesson_id: str) -> Lesson:
        for lesson in self.lessons:
            if lesson.id == lesson_id:
                return lesson
        raise KeyError(lesson_id)


class ChecklistItem(Strict):
    id: str = Field(pattern=r"^[a-z0-9_]+$")
    text: LocalizedText
    illustration: str = Field(pattern=r"^[a-z0-9-]+$")


class ChecklistConfig(Strict):
    items: list[ChecklistItem] = Field(min_length=6, max_length=8)


# --- report parser keywords (§6.10) --------------------------------------------------------


class ReportKeywords(Strict):
    type: dict[ReportType, dict[Language, list[str]]]
    severity: dict[Literal["high", "medium"], dict[Language, list[str]]]
    people: dict[Language, list[str]]
    injury: dict[Language, list[str]]

    @model_validator(mode="after")
    def _complete(self) -> ReportKeywords:
        if set(self.type) != set(ReportType):
            raise ValueError("report keywords must cover every report type")
        return self


# --- assistant intents (§10.5) -------------------------------------------------------------

INTENT_NAMES = (
    "next_task",
    "time_left",
    "report_problem",
    "start_break",
    "end_break",
    "repeat_last",
    "ack_alert",
    "open_lessons",
    "help",
)


class IntentsConfig(Strict):
    intents: dict[str, dict[Language, list[str]]]

    @model_validator(mode="after")
    def _complete(self) -> IntentsConfig:
        if set(self.intents) != set(INTENT_NAMES):
            raise ValueError(f"intents must be exactly {INTENT_NAMES}")
        for name, per_lang in self.intents.items():
            if set(per_lang) != set(Language) or any(not v for v in per_lang.values()):
                raise ValueError(f"intent {name} needs keywords in en, hi and ta")
        return self
