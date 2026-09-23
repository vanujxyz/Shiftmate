"""Risk engine: points, bands, hysteresis and tightened thresholds (TRD §6.3, D-005, D-006)."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from shiftmate.config_loader import get_config
from shiftmate.engines.risk import RiskEngine, RiskInputs
from shiftmate.schema.enums import GroundCondition, MachineType, ProximityTier, RiskBand

T0 = datetime(2026, 9, 24, 11, 0, tzinfo=UTC)
CALM = RiskInputs(
    heat_index_c=30,
    precipitation_mm_h=0,
    ground_condition=GroundCondition.DRY,
    is_night=False,
    visibility_m=10000,
    continuous_operation_min=30,
    proximity_m=None,
    seatbelt_unfastened_while_working=False,
    near_misses_last_24h=0,
)


@pytest.fixture
def engine():
    cfg = get_config()
    return RiskEngine(cfg.risk_model, cfg.profiles[MachineType.EXCAVATOR])


def test_calm_is_green(engine) -> None:
    out = engine.update(T0, CALM)
    assert out.score == 0 and out.band == RiskBand.GREEN and out.band_rank == 0


def test_demo_heat_beat_is_amber(engine) -> None:
    # D-005/D-006: heat index 45 (25) + ~4 h without a break (20) + wet ground (8) = 53 → amber
    x = replace(CALM, heat_index_c=45.1, continuous_operation_min=235, ground_condition="wet")
    out = engine.update(T0, x)
    assert out.components["heat"] == 25 and out.components["fatigue"] == 20
    assert out.score == 53 and out.band == RiskBand.AMBER
    assert [k for k, _ in out.top] == ["heat", "fatigue", "ground"]


def test_heat_alone_stays_green(engine) -> None:
    assert engine.update(T0, replace(CALM, heat_index_c=45)).band == RiskBand.GREEN


def test_band_goes_up_at_once_and_down_after_hysteresis(engine) -> None:
    hot = replace(CALM, heat_index_c=53, ground_condition="muddy", is_night=True, visibility_m=150)
    assert engine.update(T0, hot).band == RiskBand.RED  # 40 + 15 + 10 + 15 = 80
    ts = T0
    for s in range(0, 119, 1):  # below the floor, but not for 120 s yet
        ts = T0 + timedelta(seconds=1 + s)
        assert engine.update(ts, CALM).band == RiskBand.RED
    out = engine.update(T0 + timedelta(seconds=121), CALM)
    assert out.band == RiskBand.GREEN and out.band_changed


def test_brief_dip_does_not_lower_band(engine) -> None:
    amber = replace(CALM, heat_index_c=45, continuous_operation_min=200)  # 25 + 20
    engine.update(T0, amber)
    engine.update(T0 + timedelta(seconds=60), CALM)
    out = engine.update(T0 + timedelta(seconds=90), amber)
    assert out.band == RiskBand.AMBER
    out = engine.update(T0 + timedelta(seconds=200), CALM)  # hysteresis timer restarted
    assert out.band == RiskBand.AMBER


def test_thresholds_tighten_with_band_and_heat(engine) -> None:
    green = engine.update(T0, CALM).thresholds
    assert (green.caution_m, green.danger_m, green.critical_m) == (10.0, 6.0, 3.5)
    assert green.fatigue_warn_min == 150
    amber = engine.update(
        T0, replace(CALM, heat_index_c=45.1, continuous_operation_min=235)
    ).thresholds
    assert amber.caution_m == pytest.approx(12.5)
    assert amber.critical_m == pytest.approx(3.5 * 1.25)
    # amber fatigue factor 1.2 × heat divisor 1.5
    assert amber.fatigue_warn_min == pytest.approx(150 / 1.8)
    assert amber.fatigue_limit_min == pytest.approx(240 / 1.8)


def test_proximity_and_seatbelt_components(engine) -> None:
    out = engine.update(T0, replace(CALM, proximity_m=3.0, seatbelt_unfastened_while_working=True))
    assert out.proximity_tier == ProximityTier.CRITICAL
    assert out.components["proximity"] == 35 and out.components["seatbelt"] == 25
    assert out.band == RiskBand.AMBER


def test_near_miss_points_are_capped(engine) -> None:
    out = engine.update(T0, replace(CALM, near_misses_last_24h=10))
    assert out.components["near_miss"] == 15


def test_publish_only_on_meaningful_change(engine) -> None:
    assert engine.update(T0, CALM).publish  # first value is always published
    # rocky ground adds 5 → published; then the same score again → not published
    assert engine.update(T0 + timedelta(seconds=1), replace(CALM, ground_condition="rocky")).publish
    assert not engine.update(
        T0 + timedelta(seconds=2), replace(CALM, ground_condition="rocky")
    ).publish
    # a change of less than 3 points is not published (5 → 5+0); 10 more points is
    big = engine.update(
        T0 + timedelta(seconds=3), replace(CALM, ground_condition="rocky", heat_index_c=35)
    )
    assert big.publish and big.score == 15
