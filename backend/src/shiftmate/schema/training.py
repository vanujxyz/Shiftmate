"""Training records: lessons, drills, instructor booking (TRD §5.5)."""

from pydantic import AwareDatetime, BaseModel, Field

from shiftmate.schema.enums import BookingStatus, Language


class LessonCompletion(BaseModel):
    operator_id: str
    lesson_id: str
    ts: AwareDatetime
    score: float = Field(ge=0, le=1)
    duration_s: float = Field(ge=0)
    language: Language


class HazardResult(BaseModel):
    hazard_id: str
    reaction_ms: int | None = Field(default=None, ge=0)  # None = did not press stop
    correct: bool


class DrillResult(BaseModel):
    operator_id: str
    drill_id: str
    ts: AwareDatetime
    hazards: list[HazardResult]
    score: float = Field(ge=0, le=1)  # stored; shown as facts, not a number (D-013)


class TrainingSlot(BaseModel):
    slot_id: str
    dealer_centre: str
    site_id: str
    start: AwareDatetime
    topic: str
    seats_left: int = Field(ge=0)


class Booking(BaseModel):
    booking_id: str
    operator_id: str
    slot_id: str
    status: BookingStatus
