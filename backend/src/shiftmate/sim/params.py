"""Validated simulator parameters (`config/simulator.yaml`).

Only the simulator reads these. They describe how the fake world behaves (weather, trucks,
operator habits, injected anomalies), never how ShiftMate's engines decide anything.
"""

from __future__ import annotations

from datetime import date, time

from pydantic import Field

from shiftmate.schema.config import MinMax, Strict
from shiftmate.schema.enums import GroundCondition, Language, MachineType, SensorTier


class HistoryParams(Strict):
    days: int = Field(gt=0)
    end_date: date
    tick_seconds: int = Field(gt=0)
    pre_shift_min: int = Field(ge=0)
    post_shift_min: int = Field(ge=0)


class FixedMachine(Strict):
    machine_id: str
    model: str
    model_year: int
    sensor_tier: SensorTier
    site_id: str
    engine_hours_start: float


class FleetParams(Strict):
    site_order: list[str]
    basic_before_year: int
    advanced_from_year: int
    tier_downgrade_prob: float = Field(ge=0, le=1)
    model_year: MinMax
    engine_hours_start: MinMax
    fixed_machines: list[FixedMachine]


class Personality(Strict):
    """Simulator-only operator traits in [0, 1] (TRD §7.3). Never visible to engines."""

    idle_habit: float = Field(ge=0, le=1)
    seatbelt_skipper: float = Field(ge=0, le=1)
    steps_out_engine_on: float = Field(ge=0, le=1)
    speeds_near_people: float = Field(ge=0, le=1)
    skips_breaks: float = Field(ge=0, le=1)
    skill: float = Field(ge=0.5, le=1.5)  # productivity multiplier


TRAITS = (
    "idle_habit",
    "seatbelt_skipper",
    "steps_out_engine_on",
    "speeds_near_people",
    "skips_breaks",
)


class FixedOperator(Strict):
    operator_id: str
    name: str
    preferred_language: Language
    experience_years: float
    home_site_id: str
    machine_id: str
    personality: Personality


class OperatorParams(Strict):
    first_id: int
    experience_years: MinMax
    elevated_trait_share: float = Field(ge=0, le=1)
    elevated_trait: MinMax
    normal_trait: MinMax
    skill_per_experience_year: float
    skill_noise_sd: float = Field(ge=0)
    same_machine_prob: float = Field(ge=0, le=1)
    fixed: list[FixedOperator]


class BehaviourParams(Strict):
    arrival_before_shift_min: MinMax
    walkaround_min: MinMax
    habit_per_h: float = Field(ge=0)
    habit_min: MinMax
    habit_floor_per_h: float = Field(ge=0)
    step_out_per_h: float = Field(ge=0)
    step_out_min: MinMax
    seatbelt_off_per_h: float = Field(ge=0)
    seatbelt_off_min: MinMax
    speeding_prob: float = Field(ge=0, le=1)
    skip_break_prob: float = Field(ge=0, le=1)
    short_pause_per_h: float = Field(ge=0)
    short_pause_s: MinMax
    break_engine_off_prob: float = Field(ge=0, le=1)
    break_seat_occupied_prob: float = Field(ge=0, le=1)
    slow_near_person_kmh: float = Field(gt=0)


class WarmUpParams(Strict):
    coolant_rise_c_per_min: float = Field(gt=0)
    coolant_rise_below_0c_c_per_min: float = Field(gt=0)
    coolant_working_c: float
    coolant_cooling_c_per_min: float = Field(gt=0)
    extra_idle_min: MinMax


class TravelParams(Strict):
    speed_kmh: dict[MachineType, float]


class ProductivityParams(Strict):
    ground: dict[GroundCondition, float]
    heat_over_46: float
    heat_over_40: float
    night: float
    noise_sigma: float = Field(ge=0)
    pass_time_noise: float = Field(ge=0)
    non_truck_load_share: float = Field(gt=0, le=1)


class TaskParams(Strict):
    first_start_offset_min: float = Field(ge=0)
    per_day: MinMax
    fill_fraction: float = Field(gt=0, le=1.5)


class TruckParams(Strict):
    speed_kmh: float = Field(gt=0)
    offsite_minutes: MinMax
    dump_minutes: MinMax
    dispatch_log_delay_s: MinMax
    dispatch_log_missing_prob: float = Field(ge=0, le=1)


class WorkerParams(Strict):
    walk_speed_mps: float = Field(gt=0)
    caution_approach_multiplier: float = Field(ge=1)
    approach_s: MinMax
    start_distance_m: float = Field(gt=0)
    sensor_range_m: float = Field(gt=0)


class AnomalyParams(Strict):
    fuel_abnormal_per_h: float = Field(ge=0)
    fuel_multiplier: MinMax
    fuel_min: MinMax
    low_productivity_per_h: float = Field(ge=0)
    low_productivity_factor: MinMax
    low_productivity_min: MinMax


class SignalParams(Strict):
    fuel_rate_noise_sd: float = Field(ge=0)
    rpm_noise_sd: float = Field(ge=0)
    work_heading_step_deg: float = Field(ge=0)


class WeatherParams(Strict):
    temp_ar1_phi: float = Field(ge=0, lt=1)
    temp_noise_sd: float = Field(ge=0)
    rh_per_c_above_mean: float
    rh_noise_sd: float = Field(ge=0)
    rain_stop_prob: float = Field(gt=0, le=1)
    wet_mm_in_2h: float = Field(gt=0)
    muddy_mm_in_6h: float = Field(gt=0)
    dry_after_h: float = Field(gt=0)
    dry_after_h_cold: float = Field(gt=0)
    clear_visibility_m: float = Field(gt=0)
    rain_visibility_factor: float = Field(ge=0)
    dust_visibility_m: MinMax
    dust_hours: MinMax
    fog_visibility_m: MinMax
    fog_hours: MinMax
    wind_sd_kmh: float = Field(ge=0)
    solar_noon: time


class SimulatorConfig(Strict):
    history: HistoryParams
    fleet: FleetParams
    operators: OperatorParams
    behaviour: BehaviourParams
    warm_up: WarmUpParams
    travel: TravelParams
    productivity: ProductivityParams
    tasks: TaskParams
    trucks: TruckParams
    workers: WorkerParams
    anomalies: AnomalyParams
    signals: SignalParams
    weather: WeatherParams
