"""Safety engine: sustain, cooldown, tier gating, edge rules, clearing (TRD §6.2)."""

from datetime import UTC, datetime, timedelta

import pytest

from shiftmate.config_loader import get_config
from shiftmate.engines.safety import SafetyEngine
from shiftmate.schema.enums import SensorTier

T0 = datetime(2026, 9, 24, 10, 20, tzinfo=UTC)


def base_context(**kw):
    ctx = {
        "engine_on": True,
        "hydraulic_active": True,
        "travel_speed_kmh": 0.0,
        "seatbelt_fastened": True,
        "seat_occupied": True,
        "proximity_m": 30.0,
        "heat_index_c": 33.0,
        "caution_m": 10.0,
        "danger_m": 6.0,
        "critical_m": 3.5,
        "fatigue_warn_min": 150.0,
        "fatigue_limit_min": 240.0,
        "speed_near_person_kmh": 3.0,
        "continuous_operation_min": 30.0,
        "minutes_since_break": 30.0,
        "risk_band_rank": 0,
        "proximity_age_s": 0.0,
    }
    ctx.update(kw)
    return ctx


def engine_for(tier: SensorTier) -> SafetyEngine:
    cfg = get_config()
    return SafetyEngine(
        cfg.safety_rules, cfg.sensor_tiers.signals_for(tier), cfg.alert_policy.default_cooldown_s
    )


def run(engine, contexts, dt=1.0, start=T0):
    raised, cleared, ts = [], [], start
    for ctx in contexts:
        out = engine.update(ts, dt, ctx)
        raised += [(ts, r.rule_id) for r in out.raised]
        cleared += [(ts, c) for c in out.cleared]
        ts += timedelta(seconds=dt)
    return raised, cleared, ts


def test_seatbelt_needs_two_seconds_at_1hz() -> None:
    e = engine_for(SensorTier.ADVANCED)
    unbelted = base_context(seatbelt_fastened=False)
    raised, _, _ = run(e, [unbelted])
    assert raised == []
    raised, _, _ = run(e, [unbelted], start=T0 + timedelta(seconds=1))
    assert [r for _, r in raised] == ["SEATBELT_MOVING"]


def test_seatbelt_fires_on_first_30s_tick() -> None:
    e = engine_for(SensorTier.BASIC)
    raised, _, _ = run(e, [base_context(seatbelt_fastened=False)], dt=30)
    assert [r for _, r in raised] == ["SEATBELT_MOVING"]


def test_seatbelt_parked_does_not_fire() -> None:
    e = engine_for(SensorTier.ADVANCED)
    raised, _, _ = run(e, [base_context(seatbelt_fastened=False, hydraulic_active=False)] * 5)
    assert raised == []


def test_clear_and_cooldown() -> None:
    e = engine_for(SensorTier.ADVANCED)
    off = base_context(seatbelt_fastened=False)
    on = base_context()
    raised, cleared, ts = run(e, [off] * 5 + [on] * 5 + [off] * 5)
    assert [r for _, r in raised] == ["SEATBELT_MOVING"]  # second episode inside the 60 s cooldown
    assert [c for _, c in cleared] == ["SEATBELT_MOVING"]
    raised, _, _ = run(e, [on] * 60 + [off] * 3, start=ts)  # after the cooldown it raises again
    assert [r for _, r in raised] == ["SEATBELT_MOVING"]


def test_unattended_disabled_on_basic_and_needs_120s() -> None:
    empty = base_context(seat_occupied=False, hydraulic_active=False)
    basic = engine_for(SensorTier.BASIC)
    assert not basic.capabilities()["UNATTENDED_RUNNING"]
    raised, _, _ = run(basic, [empty] * 200)
    assert "UNATTENDED_RUNNING" not in [r for _, r in raised]
    std = engine_for(SensorTier.STANDARD)
    raised, _, _ = run(std, [empty] * 119)
    assert "UNATTENDED_RUNNING" not in [r for _, r in raised]
    raised, _, _ = run(std, [empty], start=T0 + timedelta(seconds=119))
    assert [r for _, r in raised] == ["UNATTENDED_RUNNING"]


def test_proximity_tiers_escalate_along_the_demo_path() -> None:
    e = engine_for(SensorTier.ADVANCED)
    path = [14, 14, 8, 8, 5, 5, 3, 3]  # the worker_near beat, metres
    raised, _, _ = run(e, [base_context(proximity_m=d) for d in path])
    names = [r for _, r in raised]
    assert names.index("PROXIMITY_CAUTION") < names.index("PROXIMITY_DANGER")
    assert names.index("PROXIMITY_DANGER") < names.index("PROXIMITY_CRITICAL")


def test_proximity_rules_disabled_without_sensor_but_camera_enables_them() -> None:
    e = engine_for(SensorTier.STANDARD)
    ctx = base_context(proximity_m=3.0)
    assert e.update(T0, 1.0, ctx).raised == []
    out = e.update(T0 + timedelta(seconds=1), 1.0, ctx, extra_signals={"proximity_m"})
    assert "PROXIMITY_CRITICAL" in {r.rule_id for r in out.raised}


def test_wider_thresholds_catch_further_people() -> None:
    e = engine_for(SensorTier.ADVANCED)
    ctx = base_context(proximity_m=11.0)  # outside the green caution distance (10 m)
    assert e.update(T0, 1.0, ctx).raised == []
    amber = base_context(proximity_m=11.0, caution_m=12.5, danger_m=7.5, critical_m=4.4)
    out = e.update(T0 + timedelta(seconds=1), 1.0, amber)
    assert [r.rule_id for r in out.raised] == ["PROXIMITY_CAUTION"]


def test_edge_rule_raises_once_while_band_holds() -> None:
    e = engine_for(SensorTier.ADVANCED)
    amber = base_context(risk_band_rank=1)
    raised, _, _ = run(e, [amber] * 30)
    assert [r for _, r in raised].count("RISK_BAND_RAISED") == 1


def test_heat_no_break() -> None:
    e = engine_for(SensorTier.BASIC)
    hot = base_context(heat_index_c=45.1, minutes_since_break=235)
    out = e.update(T0, 30, hot)
    assert "HEAT_NO_BREAK" in {r.rule_id for r in out.raised}
    rested = base_context(heat_index_c=45.1, minutes_since_break=20)
    e2 = engine_for(SensorTier.BASIC)
    assert "HEAT_NO_BREAK" not in {r.rule_id for r in e2.update(T0, 30, rested).raised}


@pytest.mark.parametrize("tier", list(SensorTier))
def test_missing_signals_never_crash(tier) -> None:
    e = engine_for(tier)
    ctx = base_context(seat_occupied=None, proximity_m=None, coolant_temp_c=None)
    e.update(T0, 1.0, ctx)
