"""Enumerations shared by config, engines, APIs and the frontend (TRD §5).

Values are identical across backend, contracts and i18n keys (CLAUDE.md §4 naming).
"""

from enum import StrEnum


class MachineType(StrEnum):
    EXCAVATOR = "excavator"
    WHEEL_LOADER = "wheel_loader"
    DOZER = "dozer"


class SensorTier(StrEnum):
    BASIC = "basic"
    STANDARD = "standard"
    ADVANCED = "advanced"


class Language(StrEnum):
    EN = "en"
    HI = "hi"
    TA = "ta"


class GroundCondition(StrEnum):
    DRY = "dry"
    WET = "wet"
    MUDDY = "muddy"
    ROCKY = "rocky"
    FROZEN = "frozen"


class QuantityUnit(StrEnum):
    LOADS = "loads"
    M = "m"
    M2 = "m2"
    M3 = "m3"


class TaskStatus(StrEnum):
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    DONE = "done"


class SeatbeltStatus(StrEnum):
    """Brief column `Seatbelt Status` (exact text from the sample)."""

    FASTENED = "Fastened"
    UNFASTENED = "Unfastened"


class YesNo(StrEnum):
    """Brief column `Safety Alert Triggered` (exact text from the sample)."""

    YES = "Yes"
    NO = "No"


class Priority(StrEnum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class EventType(StrEnum):
    ALERT = "alert"
    ALERT_ACK = "alert_ack"
    ALERT_CLEARED = "alert_cleared"
    IDLE_SEGMENT = "idle_segment"
    ANOMALY = "anomaly"
    INCIDENT = "incident"
    NEAR_MISS = "near_miss"
    EQUIPMENT_PROBLEM = "equipment_problem"
    LESSON_OFFERED = "lesson_offered"
    LESSON_COMPLETED = "lesson_completed"
    DRILL_RESULT = "drill_result"
    BOOKING = "booking"
    CHECKLIST = "checklist"
    RISK_BAND_CHANGE = "risk_band_change"
    CONNECTIVITY = "connectivity"
    SITE_ISSUE = "site_issue"  # e.g. truck shortage: attributed to the site, no operator (P-04)


class IdleReason(StrEnum):
    SCHEDULED_BREAK = "SCHEDULED_BREAK"
    WARM_UP = "WARM_UP"
    UNATTENDED_RUNNING = "UNATTENDED_RUNNING"
    WAITING_FOR_TRUCK = "WAITING_FOR_TRUCK"
    HABIT = "HABIT"
    UNKNOWN = "UNKNOWN"


class MachineState(StrEnum):
    ENGINE_OFF = "ENGINE_OFF"
    IDLE = "IDLE"
    WORKING = "WORKING"
    TRAVELLING = "TRAVELLING"


class CabMode(StrEnum):
    WORKING = "working"
    PAUSED = "paused"


class ProximitySource(StrEnum):
    SENSOR = "sensor"
    CAMERA = "camera"


class ProximityTier(StrEnum):
    CLEAR = "clear"
    CAUTION = "caution"
    DANGER = "danger"
    CRITICAL = "critical"


class RiskBand(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


class LessonFormat(StrEnum):
    NARRATED_CARDS = "narrated_cards"
    QUIZ = "quiz"
    DRILL = "drill"


class ConditionFlag(StrEnum):
    """Condition triggers for lessons (TRD §4.9), derived from risk components at shift start."""

    HEAT = "HEAT"
    RAIN = "RAIN"
    NIGHT = "NIGHT"
    WET_GROUND = "WET_GROUND"


class ReportType(StrEnum):
    INCIDENT = "incident"
    NEAR_MISS = "near_miss"
    EQUIPMENT_PROBLEM = "equipment_problem"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ZoneType(StrEnum):
    DIG = "dig"
    LOADING = "loading"
    HAUL_ROAD = "haul_road"
    STOCKPILE = "stockpile"
    BREAK_AREA = "break_area"


class BookingStatus(StrEnum):
    BOOKED = "booked"
    CANCELLED = "cancelled"
