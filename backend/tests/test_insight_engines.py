"""Interval builder, anomaly features and baselines, lesson recommender, offline report parser."""

from datetime import UTC, datetime, timedelta

import pandas as pd
import pytest

from shiftmate.config_loader import get_config
from shiftmate.engines.anomaly import (
    Baselines,
    explain,
    features_frame,
    interval_features,
    is_unusual,
    z_scores,
)
from shiftmate.engines.intervals import IntervalBuilder, IntervalTick
from shiftmate.engines.lessons import LessonOfferer, TriggerEvent, condition_flags, recommend
from shiftmate.engines.reports import auto_fill, parse_offline
from shiftmate.schema.enums import (
    IdleReason,
    Language,
    MachineState,
    MachineType,
    ReportType,
    SensorTier,
    Severity,
)

T0 = datetime(2026, 9, 24, 7, 50, tzinfo=UTC)


# --- interval builder -------------------------------------------------------------------------


def itick(ts, **kw) -> IntervalTick:
    base = dict(
        ts=ts,
        dt=30.0,
        operator_id="OP1001",
        task_id="T1",
        task_type="truck_loading",
        state=MachineState.WORKING,
        engine_on=True,
        engine_hours=1520.0,
        fuel_rate_lph=15.0,
        load_cycles_total=0,
        seatbelt_fastened=True,
        seat_occupied=True,
        engine_rpm=1800.0,
        travel_speed_kmh=0.0,
        truck_present=True,
        truck_known=True,
        truck_sensor=True,
        proximity_m=30.0,
        ambient_temp_c=30.0,
        relative_humidity_pct=60.0,
        heat_index_c=33.0,
        precipitation_mm_h=0.0,
        wind_kmh=5.0,
        visibility_m=10000.0,
        is_night=False,
        ground_condition="dry",
        continuous_operation_min=20.0,
        coolant_temp_c=85.0,
        task_progress_qty=0.0,
        risk_score=10,
        raised_rules=[],
        idle_segment_start=None,
    )
    base.update(kw)
    return IntervalTick(**base)


def builder() -> IntervalBuilder:
    return IntervalBuilder(
        "EXC001", "CHN-HWY-01", MachineType.EXCAVATOR, SensorTier.ADVANCED, ["truck_loading"]
    )


def test_interval_closes_at_quarter_hour_with_brief_columns() -> None:
    b = builder()
    records = []
    hours, cycles = 1520.0, 0
    ts = T0
    idle_start = T0 + timedelta(minutes=5)
    for i in range(40):  # 20 minutes of 30 s ticks: 07:50 → 08:10
        idle = 10 <= i < 20
        records += b.add(
            itick(
                ts,
                engine_hours=hours,
                load_cycles_total=cycles,
                state=MachineState.IDLE if idle else MachineState.WORKING,
                fuel_rate_lph=3.2 if idle else 15.0,
                truck_present=not idle,
                idle_segment_start=idle_start if idle else None,
                raised_rules=[("SEATBELT_MOVING", "P1")] if i == 25 else [],
                seatbelt_fastened=i < 24,
            )
        )
        if i == 19:
            b.record_segment(idle_start, IdleReason.WAITING_FOR_TRUCK)
        hours += 30 / 3600
        if i % 8 == 7:
            cycles += 1
        ts += timedelta(seconds=30)
    assert len(records) == 1
    r = records[0]
    assert r.timestamp == datetime(2026, 9, 24, 8, 0, tzinfo=UTC)
    assert r.interval_minutes == 10
    assert r.engine_on_min == 10 and r.idling_time_min == 5
    assert r.idle_truck_wait_min == pytest.approx(5) and r.truck_wait_min == pytest.approx(5)
    assert r.fuel_used_l == pytest.approx(round((5 * 15 + 5 * 3.2) / 60, 1))
    assert r.load_cycles == 2 and r.fuel_per_load_cycle_l == pytest.approx(
        (5 * 15 + 5 * 3.2) / 60 / 2, abs=0.01
    )
    assert r.engine_hours == pytest.approx(1520.2, abs=0.05)
    assert r.safety_alert_triggered == "No" and r.seatbelt_status == "Fastened"
    tail = b.close(ts)
    assert tail.safety_alert_triggered == "Yes" and tail.seatbelt_status == "Unfastened"
    assert tail.seatbelt_unfastened_working_s == 16 * 30
    assert tail.record_id == f"EXC001|{ts.isoformat()}"


def test_task_change_closes_interval() -> None:
    b = builder()
    b.add(itick(T0))
    closed = b.add(itick(T0 + timedelta(seconds=30), task_id="T2", task_type="trenching"))
    assert len(closed) == 1 and closed[0].task_id == "T1"


def test_no_interval_without_engine_time_or_operator() -> None:
    b = builder()
    b.add(itick(T0, engine_on=False, state=MachineState.ENGINE_OFF))
    assert b.close(T0 + timedelta(minutes=1)) is None
    b.add(itick(T0, operator_id=None))
    assert b.close(T0 + timedelta(minutes=1)) is None


def test_open_segment_uses_provisional_reason() -> None:
    b = builder()
    start = T0
    for i in range(10):
        b.add(
            itick(T0 + timedelta(seconds=30 * i), state=MachineState.IDLE, idle_segment_start=start)
        )
    r = b.close(T0 + timedelta(minutes=5), provisional_reason=IdleReason.HABIT)
    assert r.idle_habit_min == pytest.approx(5)


# --- anomaly features and baselines ----------------------------------------------------------


def test_interval_features() -> None:
    f = interval_features(
        {
            "engine_on_min": 15,
            "working_min": 12,
            "idling_time_min": 3,
            "load_cycles": 2,
            "fuel_used_l": 3.0,
            "seatbelt_unfastened_working_s": 0,
            "max_travel_speed_kmh": 1.0,
            "proximity_danger_count": 1,
            "proximity_critical_count": 0,
            "min_proximity_m": 5.0,
            "idle_habit_min": 0,
            "idle_unattended_min": 0,
            "seat_occupied_min": 15,
            "avg_engine_rpm": 1700,
        }
    )
    assert f["idle_ratio"] == pytest.approx(0.2)
    assert f["fuel_per_load_cycle_l"] == pytest.approx(1.5)
    assert f["fuel_lph"] == pytest.approx(12.0)
    assert f["load_cycles_per_working_h"] == pytest.approx(10.0)
    assert f["proximity_close_count"] == 1


def test_basic_tier_features_are_dropped_not_faked() -> None:
    f = interval_features(
        {"engine_on_min": 15, "working_min": 2, "load_cycles": 0, "fuel_used_l": 3}
    )
    assert f["fuel_per_load_cycle_l"] is None and f["load_cycles_per_working_h"] is None
    assert f["idle_unattended_min"] is None and f["avg_engine_rpm"] is None


def _history(n_personal: int) -> pd.DataFrame:
    rows = []
    day0 = pd.Timestamp("2026-09-01")
    for i in range(60):
        rows.append(
            {
                "day": day0 + pd.Timedelta(days=i % 10),
                "operator_id": "OP1" if i < n_personal else "OP2",
                "machine_type": "excavator",
                "task_type": "truck_loading",
                "site_id": "CHN-HWY-01",
                "fuel_used_l": 3.0 + (i % 5) * 0.1,
                "load_cycles": 3,
                "engine_on_min": 15,
                "working_min": 12,
                "idling_time_min": 3,
            }
        )
    df = pd.DataFrame(rows)
    return pd.concat([df, features_frame(df)], axis=1)


def test_personal_baseline_and_fallback() -> None:
    cfg = get_config().anomaly
    hist = _history(n_personal=40)
    b = Baselines(hist, cfg)
    row = {
        "day": pd.Timestamp("2026-09-12"),
        "operator_id": "OP1",
        "machine_type": "excavator",
        "task_type": "truck_loading",
        "site_id": "CHN-HWY-01",
    }
    stats, level = b.stats_for(row, cfg.codes())
    assert level == "personal" and stats["fuel_per_load_cycle_l"].median == pytest.approx(
        1.07, abs=0.02
    )
    stats, level = b.stats_for({**row, "operator_id": "OP9"}, cfg.codes())
    assert level == "group"


def test_z_scores_explanations_and_decision() -> None:
    cfg = get_config().anomaly
    hist = _history(n_personal=40)
    b = Baselines(hist, cfg)
    row = {
        "day": pd.Timestamp("2026-09-12"),
        "operator_id": "OP1",
        "machine_type": "excavator",
        "task_type": "truck_loading",
        "site_id": "CHN-HWY-01",
    }
    stats, _ = b.stats_for(row, cfg.codes())
    values = interval_features(
        {
            "engine_on_min": 15,
            "working_min": 12,
            "idling_time_min": 3,
            "load_cycles": 3,
            "fuel_used_l": 7.0,
        }
    )
    z = z_scores(values, stats, cfg)
    assert z["fuel_per_load_cycle_l"] > 3
    reasons = explain(values, z, stats, cfg)
    # more fuel for the same work shows up both per truck and per hour
    keys = {r["message_key"]: r for r in reasons}
    assert {"insight.fuel_per_load_high", "insight.fuel_rate_high"} <= set(keys)
    per_load = keys["insight.fuel_per_load_high"]
    assert per_load["usual"] == pytest.approx(stats["fuel_per_load_cycle_l"].median)
    assert per_load["value"] == pytest.approx(7.0 / 3)
    assert is_unusual(True, z, False, cfg)
    assert not is_unusual(False, z, False, cfg)  # needs the IsolationForest too
    assert is_unusual(False, {}, True, cfg)  # hard rule: a P1 fired


def test_lower_productivity_counts_as_worse() -> None:
    cfg = get_config().anomaly
    from shiftmate.engines.anomaly import worse_z

    assert worse_z({"load_cycles_per_working_h": -4.0}, cfg)["load_cycles_per_working_h"] == 4.0


# --- lesson recommender ------------------------------------------------------------------------


def test_recommend_by_count_and_recency_skipping_recent_completions() -> None:
    lessons = get_config().lessons
    now = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)
    events = (
        [TriggerEvent(now - timedelta(hours=1), "UNATTENDED_RUNNING")]
        + [TriggerEvent(now - timedelta(days=5), "HABIT") for _ in range(3)]
        + [TriggerEvent(now - timedelta(days=10), "SEATBELT_MOVING")]
    )  # outside the 7-day window
    recs = recommend(lessons, events, [], now)
    assert [r.lesson_id for r in recs][:2] == ["L-SHUTDOWN", "L-IDLE-FUEL"]
    assert "L-SEATBELT" not in [r.lesson_id for r in recs]
    recs = recommend(lessons, events, [("L-SHUTDOWN", now - timedelta(days=1))], now)
    assert recs[0].lesson_id == "L-IDLE-FUEL"


def test_lessons_offered_only_in_long_pauses() -> None:
    cfg = get_config()
    offerer = LessonOfferer(cfg.lessons)
    now = datetime(2026, 9, 24, 8, 12, tzinfo=UTC)
    recs = recommend(cfg.lessons, [TriggerEvent(now, "WAITING_FOR_TRUCK")], [], now)
    assert offerer.update(now, MachineState.WORKING, False, None, recs) is None
    assert offerer.update(now, MachineState.IDLE, True, IdleReason.UNKNOWN, recs) is None
    offer = offerer.update(now, MachineState.IDLE, True, IdleReason.WAITING_FOR_TRUCK, recs)
    assert offer.lesson_id == "L-TRUCK-LOADING-FLOW"
    assert offerer.update(now, MachineState.IDLE, True, IdleReason.WAITING_FOR_TRUCK, recs) is None
    offerer.update(now, MachineState.WORKING, False, None, recs)
    later = now + timedelta(minutes=10)
    assert offerer.update(later, MachineState.ENGINE_OFF, True, None, recs) is None  # 30-min gap
    assert offerer.update(now + timedelta(minutes=31), MachineState.ENGINE_OFF, True, None, recs)


def test_condition_flags_come_from_risk_bands() -> None:
    rm = get_config().risk_model
    assert condition_flags(rm, 45, 0.0, "wet", False) == ["HEAT", "WET_GROUND"]
    assert condition_flags(rm, 25, 2.0, "dry", True) == ["RAIN", "NIGHT"]


# --- offline report parser -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "lang", "rtype", "severity", "people", "injury"),
    [
        (
            "I almost hit a worker near LOAD-A",
            "en",
            ReportType.NEAR_MISS,
            Severity.MEDIUM,
            True,
            False,
        ),
        (
            "Hydraulic oil leak under the machine",
            "en",
            ReportType.EQUIPMENT_PROBLEM,
            Severity.LOW,
            False,
            False,
        ),
        (
            "The helper fell from the step and was injured",
            "en",
            ReportType.INCIDENT,
            Severity.HIGH,
            True,
            True,
        ),
        (
            "एक मज़दूर बाल-बाल बचा, बकेट के पास आ गया था",
            "hi",
            ReportType.NEAR_MISS,
            Severity.MEDIUM,
            True,
            False,
        ),
        (
            "லாரி கிட்டத்தட்ட ஒரு தொழிலாளியை மோதியது",
            "ta",
            ReportType.NEAR_MISS,
            Severity.MEDIUM,
            True,
            False,
        ),
        (
            "இயந்திரத்தின் கீழே எண்ணெய் கசிவு",
            "ta",
            ReportType.EQUIPMENT_PROBLEM,
            Severity.LOW,
            False,
            False,
        ),
    ],
)
def test_offline_report_parser(text, lang, rtype, severity, people, injury) -> None:
    draft = parse_offline(text, Language(lang), get_config().report_keywords)
    assert (draft.type, draft.severity, draft.people_involved, draft.injury) == (
        rtype,
        severity,
        people,
        injury,
    )
    assert draft.parser == "offline" and draft.summary_local == text


def test_auto_fill_finds_zone_from_position() -> None:
    site = get_config().sites["CHN-HWY-01"]
    ctx = auto_fill(
        ts=T0,
        machine_id="EXC001",
        operator_id="OP1001",
        site_id=site.site_id,
        layout=site.layout,
        x_m=190,
        y_m=80,
        task_id="T1",
        weather={"heat_index_c": 45.1},
        risk_score=53,
        language=Language.TA,
    )
    assert ctx.zone_id == "LOAD-A" and ctx.risk_score == 53
    road = auto_fill(
        ts=T0,
        machine_id="EXC001",
        operator_id=None,
        site_id=site.site_id,
        layout=site.layout,
        x_m=300,
        y_m=90,
        task_id=None,
        weather={},
        risk_score=None,
        language=Language.EN,
    )
    assert road.zone_id == "HAUL"
