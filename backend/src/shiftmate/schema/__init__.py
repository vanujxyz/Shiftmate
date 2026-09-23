"""Pydantic models for every piece of data that crosses a module or network boundary (TRD §5).

`EXPORTED_MODELS` lists the models that `shiftmate schema export` turns into JSON Schema, from
which `frontend/packages/contracts` generates TypeScript types.
"""

from pydantic import BaseModel

from shiftmate.schema.common import ErrorBody, ErrorResponse, HealthResponse
from shiftmate.schema.config import ChecklistItem, Lesson, LocalizedText, MachineProfile, Site
from shiftmate.schema.events import Event, IdleSegmentPayload, ReportDraft
from shiftmate.schema.intervals import IntervalRecord
from shiftmate.schema.reference import Machine, Operator, Task, TaskConditions
from shiftmate.schema.signals import Gps, SignalTick
from shiftmate.schema.training import (
    Booking,
    DrillResult,
    HazardResult,
    LessonCompletion,
    TrainingSlot,
)

EXPORTED_MODELS: list[type[BaseModel]] = [
    HealthResponse,
    ErrorResponse,
    ErrorBody,
    Machine,
    Operator,
    Task,
    TaskConditions,
    Gps,
    SignalTick,
    IntervalRecord,
    Event,
    IdleSegmentPayload,
    ReportDraft,
    LessonCompletion,
    HazardResult,
    DrillResult,
    TrainingSlot,
    Booking,
    LocalizedText,
    Lesson,
    ChecklistItem,
    MachineProfile,
    Site,
]

__all__ = [
    "EXPORTED_MODELS",
    "Booking",
    "DrillResult",
    "ErrorBody",
    "ErrorResponse",
    "Event",
    "Gps",
    "HazardResult",
    "HealthResponse",
    "IdleSegmentPayload",
    "IntervalRecord",
    "Lesson",
    "LessonCompletion",
    "Machine",
    "Operator",
    "ReportDraft",
    "SignalTick",
    "Task",
    "TaskConditions",
    "TrainingSlot",
]
