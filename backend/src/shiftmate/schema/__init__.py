"""Pydantic models for every piece of data that crosses a module or network boundary (TRD §5).

`EXPORTED_MODELS` lists the models that `shiftmate schema export` turns into JSON Schema, from
which `frontend/packages/contracts` generates TypeScript types.
"""

import inspect

from pydantic import BaseModel

from shiftmate.schema import api as _api
from shiftmate.schema import fleet as _fleet
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
# Every Edge Gateway request/response and WebSocket model (schema/api.py) and every
# Fleet Service request/response model (schema/fleet.py), by name.
EXPORTED_MODELS += [
    obj
    for module in (_api, _fleet)
    for _, obj in inspect.getmembers(module, inspect.isclass)
    if issubclass(obj, BaseModel) and obj.__module__ == module.__name__
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
