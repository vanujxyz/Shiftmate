"""Interval record: the brief's sample schema, extended (TRD §5.3, PRD §7).

The first nine fields are the brief's columns with the semantics in D-001..D-003. CSV/Parquet
exports use the brief's original header text for those nine and snake_case for the rest.

Ground-truth labels are NOT fields here: the simulator writes them to a separate `labels` table
(TRD §7), so nothing that reads an IntervalRecord can see them (golden rule 5, D-027).
"""

import csv
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from pydantic import AwareDatetime, BaseModel, Field

from shiftmate.schema.enums import GroundCondition, MachineType, SeatbeltStatus, SensorTier, YesNo

# Brief column header text → field name, in the brief's order.
BRIEF_COLUMNS: dict[str, str] = {
    "Timestamp": "timestamp",
    "Machine ID": "machine_id",
    "Operator ID": "operator_id",
    "Engine Hours": "engine_hours",
    "Fuel Used (L)": "fuel_used_l",
    "Load Cycles": "load_cycles",
    "Idling Time (min)": "idling_time_min",
    "Seatbelt Status": "seatbelt_status",
    "Safety Alert Triggered": "safety_alert_triggered",
}


class IntervalRecord(BaseModel):
    # --- the brief's nine columns ---
    timestamp: AwareDatetime  # interval end
    machine_id: str
    operator_id: str
    engine_hours: float = Field(ge=0)  # hour meter at interval end
    fuel_used_l: float = Field(ge=0)  # during the interval
    load_cycles: int = Field(ge=0)  # during the interval (profile definition, D-001)
    idling_time_min: int = Field(ge=0)
    seatbelt_status: SeatbeltStatus  # at interval end
    safety_alert_triggered: YesNo  # Yes if any P1/P2 alert in the interval (D-003)
    # --- extensions (null for the brief's sample rows) ---
    record_id: str | None = None  # "<machine_id>|<interval end ISO>", idempotency key for ingest
    interval_start: AwareDatetime | None = None
    interval_minutes: float | None = None
    site_id: str | None = None
    machine_type: MachineType | None = None
    sensor_tier: SensorTier | None = None
    task_id: str | None = None
    task_type: str | None = None
    engine_on_min: float | None = None
    working_min: float | None = None
    travel_min: float | None = None
    seat_occupied_min: float | None = None
    seatbelt_unfastened_working_s: int | None = None
    avg_engine_rpm: float | None = None
    max_travel_speed_kmh: float | None = None
    truck_present_min: float | None = None
    truck_wait_min: float | None = None
    min_proximity_m: float | None = None
    proximity_caution_count: int | None = None
    proximity_danger_count: int | None = None
    proximity_critical_count: int | None = None
    ambient_temp_c: float | None = None
    relative_humidity_pct: float | None = None
    heat_index_c: float | None = None
    precipitation_mm: float | None = None  # total over the interval
    wind_kmh: float | None = None
    visibility_m: float | None = None
    is_night: bool | None = None  # majority of the interval
    ground_condition: GroundCondition | None = None
    continuous_operation_min: float | None = None  # at interval end
    coolant_temp_c: float | None = None  # interval minimum
    incident_count: int | None = None
    near_miss_count: int | None = None
    idle_warmup_min: float | None = None
    idle_break_min: float | None = None
    idle_truck_wait_min: float | None = None
    idle_unattended_min: float | None = None
    idle_habit_min: float | None = None
    idle_unknown_min: float | None = None
    fuel_per_load_cycle_l: float | None = None  # null if load_cycles = 0
    task_progress_qty: float | None = None  # quantity done during the interval
    risk_score_max: int | None = None
    p1_alert_count: int | None = None  # P1 rules raised in the interval (anomaly hard rule, §6.6)


def read_brief_csv(path: Path, timezone: str = "Asia/Kolkata") -> list[IntervalRecord]:
    """Read a CSV that uses the brief's header text. Naive timestamps get the site timezone."""
    tz = ZoneInfo(timezone)
    records: list[IntervalRecord] = []
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            data: dict[str, object] = {}
            for header, value in row.items():
                field = BRIEF_COLUMNS.get(header, header)
                data[field] = value if value != "" else None
            ts = datetime.fromisoformat(str(data["timestamp"]))
            data["timestamp"] = ts if ts.tzinfo else ts.replace(tzinfo=tz)
            records.append(IntervalRecord.model_validate(data))
    return records


def to_export_row(record: IntervalRecord) -> dict[str, object]:
    """Row for CSV/Parquet export: brief header text for the nine columns, snake_case after."""
    data = record.model_dump(mode="json")
    names = {field: header for header, field in BRIEF_COLUMNS.items()}
    return {names.get(key, key): value for key, value in data.items()}
