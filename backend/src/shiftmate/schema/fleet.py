"""Fleet Service request and response models (TRD §9.2).

Everything the supervisor console and the edge exchange with the Fleet Service. Operator
identities only appear where `privacy.yaml → supervisor_sees_operator_detail_for` allows it
(PRD P-02, P-03); the models make that explicit with nullable operator fields.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

IngestKind = Literal["intervals", "events", "reports", "tasks"]
Track = Literal["done", "on_track", "behind", "not_started", "unknown"]


# --- ingest ------------------------------------------------------------------------------------


class IngestRequest(BaseModel):
    source: str | None = Field(None, description="Sending machine or process (e.g. EXC001).")
    records: list[dict[str, Any]]


class IngestResponse(BaseModel):
    kind: IngestKind
    received: int
    inserted: int  # new records
    updated: int = 0  # tasks only: a later status replaced an earlier one
    duplicates: int  # already stored (idempotent re-send)
    rejected: int = 0  # not allowed to leave the machine (privacy) or invalid


# --- sites -------------------------------------------------------------------------------------


class SiteInfo(BaseModel):
    site_id: str
    name: str
    country: str
    timezone: str
    machines: int
    first_date: date | None
    last_date: date | None


class TaskProgressView(BaseModel):
    task_id: str
    task_type: str
    zone_id: str | None
    planned_quantity: float | None
    done_quantity: float
    unit: str | None
    status: str
    progress_pct: float | None
    expected_min: float | None  # fleet baseline for the whole task
    elapsed_min: float | None
    track: Track


class MachineDaySummary(BaseModel):
    machine_id: str
    machine_type: str | None
    model: str | None
    sensor_tier: str | None
    operator_id: str | None  # who is assigned to the machine (roster, not a behaviour metric)
    operator_name: str | None
    tasks: list[TaskProgressView]
    engine_on_min: float
    working_min: float
    idle_min: float
    last_seen: datetime | None
    track: Track


class SiteSummary(BaseModel):
    site_id: str
    date: date
    timezone: str
    machines: list[MachineDaySummary]
    tasks_total: int
    tasks_done: int
    tasks_behind: int
    tasks_on_track: int


class IdleCause(BaseModel):
    reason: str
    minutes: float
    share: float
    site_issue: bool  # attributed to the site, never to an operator (P-04)


class HourMinutes(BaseModel):
    hour: int
    minutes: float


class Suggestion(BaseModel):
    """One plain-language suggestion; the console turns `key` + values into text."""

    key: str
    reason: str
    minutes: float  # what the suggestion is about, today
    zone_id: str | None = None
    window_start: str | None = None  # "10:00"
    window_end: str | None = None
    save_min_low: float | None = None
    save_min_high: float | None = None
    basis_days: int | None = None
    lesson_id: str | None = None


class IdleCausesResponse(BaseModel):
    site_id: str
    date: date
    machines: int
    total_idle_min: float
    lead: IdleCause | None
    causes: list[IdleCause]
    truck_wait_by_hour: list[HourMinutes]
    suggestion: Suggestion | None  # the one to show first
    suggestions: list[Suggestion]


class SafetyEventView(BaseModel):
    event_id: str
    ts: datetime
    type: str
    priority: str | None
    code: str | None
    machine_id: str
    operator_id: str | None  # only for types privacy.yaml allows (P-03)
    operator_name: str | None
    detail: dict[str, Any] = {}


class ReportView(BaseModel):
    report_id: str
    ts: datetime
    type: str
    severity: str | None
    summary_en: str | None
    machine_id: str
    operator_id: str | None


class MachineRisk(BaseModel):
    machine_id: str
    band: str | None  # latest interval of the day
    score: int | None
    amber_min: float
    red_min: float


class SafetyResponse(BaseModel):
    site_id: str
    date: date
    p1: list[SafetyEventView]
    p2: list[SafetyEventView]
    p2_counts: dict[str, int]
    incidents: list[SafetyEventView]
    near_misses: list[SafetyEventView]
    unattended: list[SafetyEventView]
    site_issues: list[SafetyEventView]
    reports: list[ReportView]
    risk: list[MachineRisk]


class TrendDay(BaseModel):
    day: date
    operators: int
    suppressed: bool  # fewer operators than the privacy minimum: no numbers
    idle_min_by_reason: dict[str, float] | None = None
    truck_wait_min: float | None = None
    p1: int | None = None
    p2: int | None = None
    near_misses: int | None = None
    incidents: int | None = None
    fuel_per_load_cycle_l: float | None = None
    seatbelt_unfastened_s_per_h: float | None = None


class TrendGroup(BaseModel):
    group: str  # e.g. "3–6 years"
    operators: int
    suppressed: bool
    habit_idle_min_per_h: float | None = None
    seatbelt_unfastened_s_per_h: float | None = None
    fuel_per_load_cycle_l: float | None = None
    p1_per_100h: float | None = None


class TrendsResponse(BaseModel):
    site_id: str
    days: int
    min_group_size: int
    daily: list[TrendDay]
    by_experience: list[TrendGroup]


# --- fleet ---------------------------------------------------------------------------------------


class FleetSite(BaseModel):
    site_id: str
    name: str
    country: str
    timezone: str
    latest_date: date | None
    machines_total: int
    machines_active: int  # sent data on the latest date
    by_type: dict[str, int]
    by_tier: dict[str, int]
    risk_bands: dict[str, int]  # machines per band, latest interval of the latest date
    ground_condition: str | None
    heat_index_c: float | None
    last_ingest: datetime | None


class FleetOverview(BaseModel):
    sites: list[FleetSite]
    machines_total: int
    by_type: dict[str, int]
    by_tier: dict[str, int]
    records: dict[str, int]  # stored records by kind (site data, not the scale run)
    scale_machines: int


class FleetPattern(BaseModel):
    dimension: str
    task_type: str
    condition: str
    multiplier: float
    change_pct: float
    tasks: int
    machines: int
    reference: str


class ModelRef(BaseModel):
    version: str
    files: list[str]
    manifest: dict[str, Any]


# --- scale ---------------------------------------------------------------------------------------


class ScaleRun(BaseModel):
    machines: int
    sim_minutes: int
    records: int
    intervals: int
    events: int
    requests: int
    seconds: float
    records_per_s: float
    request_ms_p50: float
    request_ms_p95: float
    bytes_sent: int
    bytes_per_machine_per_hour: float
    records_per_machine_per_hour: float
    finished_at: datetime


class BenchResult(BaseModel):
    machines: int
    sim_minutes: int
    ticks: int
    cpu_ms_per_tick_mean: float
    cpu_ms_per_tick_p95: float
    memory_mb_per_machine: float
    upload_bytes_per_machine_per_hour: float
    records_per_machine_per_hour: float
    finished_at: datetime


class Projection(BaseModel):
    """Linear projection to the whole connected fleet. A projection, not a measurement."""

    label: Literal["projection"] = "projection"
    machines: int
    basis: str
    hours_per_day: float
    uplink_bytes_per_day: float
    uplink_gb_per_day: float
    records_per_day: float
    records_per_s: float
    ingest_nodes_at_measured_rate: float | None


class LiveIngest(BaseModel):
    records_last_60s: int
    records_per_s: float


class ScaleStats(BaseModel):
    totals: dict[str, int]  # every stored record by kind (site data + scale run)
    scale_machines: int
    live: LiveIngest
    run: ScaleRun | None
    bench: BenchResult | None
    projection: Projection | None
