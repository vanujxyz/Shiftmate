"""Signal tick: one sample of a machine's sensors plus site conditions (TRD §5.2).

1 Hz in live mode, 30 s in stored history. Optional fields are `None` when the machine's sensor
tier lacks that sensor (TRD §4.2); engines must treat `None` as "not sensed", never as a value.
"""

from pydantic import AwareDatetime, BaseModel, Field

from shiftmate.schema.enums import GroundCondition, ProximitySource


class Gps(BaseModel):
    """Local site coordinates in metres (site layout frame)."""

    x_m: float
    y_m: float


class SignalTick(BaseModel):
    ts: AwareDatetime
    machine_id: str
    operator_id: str | None = None
    # basic tier (the brief's columns + GPS)
    engine_on: bool
    engine_hours: float = Field(ge=0)
    fuel_rate_lph: float = Field(ge=0)
    hydraulic_active: bool
    travel_speed_kmh: float = Field(ge=0)
    seatbelt_fastened: bool
    gps: Gps
    heading_deg: float = Field(ge=0, lt=360)
    load_cycles_total: int = Field(default=0, ge=0)  # machine cycle counter (brief column, D-035)
    # standard tier
    seat_occupied: bool | None = None
    engine_rpm: float | None = None
    coolant_temp_c: float | None = None
    # advanced tier (or camera add-on for proximity)
    proximity_m: float | None = None
    proximity_bearing_deg: float | None = None  # 0 = boom forward, clockwise (DESIGN Reach)
    proximity_source: ProximitySource | None = None
    truck_in_loading_zone: bool | None = None
    # site conditions (from the site weather feed; available on every tier)
    ambient_temp_c: float
    relative_humidity_pct: float = Field(ge=0, le=100)
    heat_index_c: float
    precipitation_mm_h: float = Field(ge=0)
    wind_kmh: float = Field(ge=0)
    visibility_m: float = Field(ge=0)
    is_night: bool
    ground_condition: GroundCondition
    # task context
    task_id: str | None = None
    task_progress_qty: float = Field(default=0, ge=0)
