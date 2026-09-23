"""Request and response bodies of the Edge Gateway REST API (TRD §9.1).

All exported to `packages/contracts`, so the cab and console never hand-write API types.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import AwareDatetime, BaseModel, Field

from shiftmate.schema.enums import (
    CabMode,
    GroundCondition,
    IdleReason,
    Language,
    MachineState,
    ProximityTier,
    RiskBand,
    SensorTier,
    TaskStatus,
)
from shiftmate.schema.events import ReportDraft
from shiftmate.schema.reference import Machine, Operator, Task

# --- machines and session --------------------------------------------------------------------


class Capability(BaseModel):
    id: str  # rule id or feature name
    enabled: bool
    reason: str | None = None  # why it is off ("needs seat sensor")


class MachineInfo(BaseModel):
    machine: Machine
    focus: bool
    capabilities: list[Capability]
    features: dict[str, bool]  # sensor_tiers.feature_availability for this tier
    low_confidence: bool  # basic machines: results are less certain (F-FLT-02)


class SignInRequest(BaseModel):
    operator_id: str
    machine_id: str
    pin: str | None = None
    badge: str | None = None  # QR badge contents
    language: Language


class Conditions(BaseModel):
    ambient_temp_c: float
    relative_humidity_pct: float
    heat_index_c: float
    precipitation_mm_h: float
    wind_kmh: float
    visibility_m: float
    is_night: bool
    ground_condition: GroundCondition
    sunrise: str | None = None
    sunset: str | None = None


class EstimateReason(BaseModel):
    key: str
    feature: str
    minutes: float


class TaskEstimate(BaseModel):
    p10: float
    p50: float
    p90: float
    reasons: list[EstimateReason]
    low_confidence: bool = False
    remaining: bool = False  # True when this is the live remaining time of the active task


class ShiftTask(BaseModel):
    task: Task
    estimate: TaskEstimate | None
    progress_qty: float = 0.0
    zone_decal: str


class SuggestedBreak(BaseModel):
    at: str  # HH:MM local
    minutes: int
    reason_key: str  # "shift.break_scheduled" | "shift.break_heat"


class ShiftResponse(BaseModel):
    date: str
    operator_id: str
    machine_id: str
    conditions: Conditions
    tasks: list[ShiftTask]
    likely_finish: TaskEstimate | None
    breaks: list[SuggestedBreak]


class OperatorProfile(BaseModel):
    operator: Operator
    language: Language
    skill_index: dict[str, float]  # task type → recent actual ÷ expected (1.0 = as expected)
    lessons_completed: int
    drills_done: int
    recent_lessons: list[str]


class SessionResponse(BaseModel):
    profile: OperatorProfile
    machine: MachineInfo
    shift: ShiftResponse


class ChecklistAnswer(BaseModel):
    item_id: str
    ok: bool
    note: str | None = None


class ChecklistSubmit(BaseModel):
    operator_id: str
    machine_id: str
    answers: list[ChecklistAnswer]


class ChecklistResult(BaseModel):
    saved: bool
    problems: int
    report_ids: list[str]


class AckRequest(BaseModel):
    action: Literal["ack", "later", "done"] = "ack"


# --- reports ----------------------------------------------------------------------------------


class ReportParseRequest(BaseModel):
    transcript: str = Field(min_length=1)
    language: Language


class ReportContextModel(BaseModel):
    ts: AwareDatetime
    machine_id: str
    operator_id: str | None
    site_id: str
    zone_id: str | None
    task_id: str | None
    weather: dict[str, Any]
    risk_score: int | None
    language: Language


class ReportParseResponse(BaseModel):
    draft: ReportDraft
    context: ReportContextModel
    mode: Literal["online", "offline"]


class ReportSaveRequest(BaseModel):
    draft: ReportDraft
    context: ReportContextModel
    transcript: str | None = None


class SavedReport(BaseModel):
    report_id: str
    ts: AwareDatetime
    draft: ReportDraft
    context: ReportContextModel
    synced: bool


# --- insights ---------------------------------------------------------------------------------


class TimeSplitSegment(BaseModel):
    kind: str  # working | travel | engine_off | one of IdleReason
    start: AwareDatetime
    end: AwareDatetime
    minutes: float


class IdleSegmentView(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    minutes: float
    reason: IdleReason
    confidence: float
    evidence: list[str]
    fuel_l: float


class InsightNote(BaseModel):
    key: str  # i18n key
    values: dict[str, Any] = {}
    lesson_id: str | None = None


class FuelMetrics(BaseModel):
    fuel_l: float
    idle_fuel_l: float
    fuel_per_load_l: float | None
    usual_fuel_per_load_l: float | None
    loads: int


class InsightsResponse(BaseModel):
    operator_id: str
    range: Literal["shift", "week"]
    totals_min: dict[str, float]
    time_split: list[TimeSplitSegment]
    idle_segments: list[IdleSegmentView]
    fuel: FuelMetrics
    anomalies: list[dict[str, Any]]
    coaching: list[InsightNote]
    positives: list[InsightNote]
    days: list[dict[str, Any]] = []  # week view: one summary per day


# --- learning ---------------------------------------------------------------------------------


class LessonSummary(BaseModel):
    id: str
    title: dict[str, str]
    format: str
    duration_s: int
    triggers: list[str]
    completed: bool = False


class Recommendation(BaseModel):
    lesson: LessonSummary
    score: float
    because: list[str]


class LessonCompleteRequest(BaseModel):
    operator_id: str
    score: float = Field(ge=0, le=1)
    duration_s: float = Field(ge=0)
    language: Language


class HazardAnswer(BaseModel):
    hazard_id: str
    reaction_ms: int | None = None
    correct: bool


class DrillResultRequest(BaseModel):
    operator_id: str
    drill_id: str
    hazards: list[HazardAnswer]


class BookingRequest(BaseModel):
    operator_id: str
    slot_id: str


# --- assistant (milestone 14 fills the online path) --------------------------------------------


class AskRequest(BaseModel):
    question: str = Field(min_length=1)
    language: Language
    machine_id: str | None = None
    operator_id: str | None = None


class Citation(BaseModel):
    chunk_id: str
    title: str
    section: str


class AskResponse(BaseModel):
    answer: str
    citations: list[Citation]
    answerable: bool
    mode: Literal["online", "offline"]
    language: Language
    notice_key: str | None = None  # e.g. "ask.offline_label"


class IntentRequest(BaseModel):
    utterance: str
    language: Language


class IntentResponse(BaseModel):
    intent: str  # one of the intents in intents.yaml, or "question"
    slots: dict[str, Any] = {}
    matched: str | None = None


# --- camera and sync ---------------------------------------------------------------------------


class CameraReading(BaseModel):
    machine_id: str
    distance_m: float = Field(gt=0)
    confidence: float = Field(ge=0, le=1)
    bearing_deg: float | None = None
    ts: AwareDatetime | None = None


class SyncStatus(BaseModel):
    online: bool
    outbox_size: int
    last_sync: AwareDatetime | None
    last_error: str | None = None
    estimation_model: str | None = None  # version in use
    estimation_source: str | None = None  # fleet (downloaded) | cache | bundled


# --- live state (cab telemetry, WebSocket) -----------------------------------------------------


class Telemetry(BaseModel):
    ts: AwareDatetime
    machine_id: str
    state: MachineState
    mode: CabMode
    engine_on: bool
    travel_speed_kmh: float
    seatbelt_fastened: bool
    seat_occupied: bool | None
    proximity_m: float | None
    proximity_bearing_deg: float | None
    proximity_source: str | None
    proximity_tier: ProximityTier | None  # None = no people sensing on this machine
    heat_index_c: float
    risk_score: int
    risk_band: RiskBand
    task_id: str | None
    task_progress_qty: float
    continuous_operation_min: float
    sensor_tier: SensorTier
    thresholds: dict[str, float]  # proximity rings in use now (caution_m, danger_m, critical_m…)
    x_m: float | None = None
    y_m: float | None = None
    heading_deg: float | None = None


class TaskProgress(BaseModel):
    task_id: str
    status: TaskStatus
    done_qty: float
    planned_qty: float
    unit: str


class EstimateUpdate(BaseModel):
    task_id: str | None  # the active task, if any
    estimate: TaskEstimate | None  # its live remaining time
    likely_finish: TaskEstimate | None  # all remaining work


class Connectivity(BaseModel):
    online: bool


class SyncUpdate(BaseModel):
    online: bool
    outbox_size: int
    last_sync: AwareDatetime | None
    last_error: str | None = None
    synced_now: int = 0  # records accepted by the fleet in this round


class SiteEntities(BaseModel):
    """`entities` on /ws/site: everything on the map (5 Hz)."""

    ts: AwareDatetime
    site_id: str
    machines: list[dict[str, Any]]
    trucks: list[dict[str, Any]]
    workers: list[dict[str, Any]]


CabMessageType = Literal[
    "snapshot",  # sent on connect and after load/seek: the full current state
    "telemetry",
    "mode",
    "risk_update",
    "alert",
    "alert_cleared",
    "alert_queued",
    "alert_feed",
    "idle_segment",
    "insight",
    "task_progress",
    "estimate_update",
    "lesson_offer",
    "session",
    "connectivity",
    "sync",
    "scenario_caption",  # demo only; sent only while the console has captions on
    "demo",  # demo player notices (waiting for a beat, seeked, end of shift)
]
SiteMessageType = Literal["snapshot", "entities", "dispatch", "site_event", "demo"]


class WsEnvelope(BaseModel):
    """Every WebSocket message (TRD §9): `seq` increases by one per channel."""

    type: str
    seq: int
    ts: AwareDatetime | None
    machine_id: str | None
    site_id: str | None
    payload: dict[str, Any]


# --- demo control ------------------------------------------------------------------------------


class ScenarioLoadRequest(BaseModel):
    name: str


class SpeedRequest(BaseModel):
    x: float = Field(gt=0, le=120)


class SeekRequest(BaseModel):
    beat_id: str


class NetworkRequest(BaseModel):
    online: bool


class CaptionsRequest(BaseModel):
    on: bool


class BeatView(BaseModel):
    id: str
    at: str
    action: str
    caption: dict[str, str] | None
    done: bool


class DemoState(BaseModel):
    scenario: str | None
    site_id: str | None
    focus_machine: str | None
    sim_time: AwareDatetime | None
    playing: bool
    speed: float
    waiting_for: str | None  # beat id the player is waiting on (sign-in, voice report)
    online: bool
    captions: bool
    beats: list[BeatView]
    signed_in: str | None
