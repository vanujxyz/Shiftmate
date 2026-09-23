"""Events and their payloads (TRD §5.4)."""

from typing import Any

from pydantic import AwareDatetime, BaseModel, Field

from shiftmate.schema.enums import (
    EventType,
    IdleReason,
    Priority,
    ReportType,
    Severity,
)


class Event(BaseModel):
    event_id: str  # uuid7 built from the sim clock and a seeded generator (D-017)
    ts: AwareDatetime
    machine_id: str
    operator_id: str | None = None
    site_id: str
    type: EventType
    priority: Priority | None = None
    code: str  # rule id, idle reason, anomaly feature, lesson id, …
    payload: dict[str, Any] = {}
    shared_with_supervisor: bool = False
    synced: bool = False


class IdleSegmentPayload(BaseModel):
    start: AwareDatetime
    end: AwareDatetime
    duration_s: float = Field(ge=0)
    reason: IdleReason
    confidence: float = Field(ge=0, le=1)
    evidence: list[str]
    fuel_l: float = Field(ge=0)
    response_taken: str
    provisional: bool = False


class ReportDraft(BaseModel):
    """Structured incident / near-miss report (TRD §6.10)."""

    type: ReportType
    severity: Severity
    summary_en: str
    summary_local: str
    people_involved: bool
    injury: bool
    parser: str = Field(description="online | offline")
