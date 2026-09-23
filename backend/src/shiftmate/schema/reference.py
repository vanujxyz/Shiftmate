"""Reference tables: machines, operators, tasks (TRD §5.1).

Operator `personality` is simulator-only and deliberately NOT part of `Operator`; it lives in
`shiftmate.sim` so engines, the edge and the UI cannot see it (golden rule 5).
"""

from pydantic import AwareDatetime, BaseModel, Field

from shiftmate.schema.enums import (
    GroundCondition,
    Language,
    MachineType,
    QuantityUnit,
    SensorTier,
    TaskStatus,
)


class Machine(BaseModel):
    machine_id: str = Field(pattern=r"^[A-Z]{3}\d{3}$", examples=["EXC001"])
    machine_type: MachineType
    model: str
    model_year: int = Field(ge=2010, le=2026)
    sensor_tier: SensorTier
    site_id: str
    engine_hours_start: float = Field(ge=0)


class Operator(BaseModel):
    operator_id: str = Field(pattern=r"^OP\d{4}$", examples=["OP1001"])
    name: str
    preferred_language: Language
    experience_years: float = Field(ge=0)
    home_site_id: str
    certifications: list[MachineType]


class TaskConditions(BaseModel):
    ground_condition: GroundCondition
    heat_index_c: float
    precipitation_mm_h: float = Field(ge=0)
    is_night: bool


class Task(BaseModel):
    task_id: str = Field(examples=["T-CHN-HWY-01-20260924-1"])
    site_id: str
    machine_id: str
    operator_id: str
    task_type: str
    zone_id: str
    planned_quantity: float = Field(gt=0)
    quantity_unit: QuantityUnit
    scheduled_start: AwareDatetime
    actual_start: AwareDatetime | None = None
    actual_end: AwareDatetime | None = None
    actual_duration_min: float | None = None
    status: TaskStatus = TaskStatus.SCHEDULED
    conditions_at_start: TaskConditions | None = None
