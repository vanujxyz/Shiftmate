"""Idle-reason engine: one test per reason × sensor tier (TRD §6.4, CLAUDE Phase 3 DoD)."""

from datetime import UTC, datetime, timedelta

import pytest

from shiftmate.config_loader import get_config
from shiftmate.engines.idle_reason import IdleReasonEngine, IdleTick
from shiftmate.schema.enums import IdleReason, MachineState, MachineType, SensorTier

T0 = datetime(2026, 9, 24, 8, 0, tzinfo=UTC)
ALL = list(SensorTier)
SEAT_SENSED = [SensorTier.STANDARD, SensorTier.ADVANCED]


def engine(tier: SensorTier) -> IdleReasonEngine:
    cfg = get_config()
    return IdleReasonEngine(cfg.idle_rules, cfg.profiles[MachineType.EXCAVATOR], tier)


def idle_run(
    tier: SensorTier,
    minutes: float,
    *,
    dt: float = 30.0,
    seat: bool | None = True,
    coolant: float | None = 85.0,
    ambient: float = 30.0,
    engine_started_s_before: float | None = 3600,
    task_type: str | None = "trenching",
    truck: bool | None = None,
    in_break: bool = False,
):
    """Feed an idle segment then one working tick; return (result, provisional results)."""
    e = engine(tier)
    started = (
        T0 - timedelta(seconds=engine_started_s_before)
        if engine_started_s_before is not None
        else None
    )
    sensed = tier != SensorTier.BASIC
    source = None
    if truck is not None:
        source = "sensor" if tier == SensorTier.ADVANCED else "dispatch_log"
    provisional = []
    ts = T0
    for _ in range(int(minutes * 60 / dt)):
        out = e.update(
            IdleTick(
                ts=ts,
                dt=dt,
                state=MachineState.IDLE,
                seat_occupied=seat if sensed else None,
                coolant_temp_c=coolant if sensed else None,
                ambient_temp_c=ambient,
                fuel_rate_lph=3.2,
                engine_started_at=started,
                task_type=task_type,
                truck_present=truck,
                truck_source=source,
                in_break_window=in_break,
            )
        )
        if out.provisional:
            provisional.append(out.provisional)
        ts += timedelta(seconds=dt)
    out = e.update(
        IdleTick(
            ts=ts,
            dt=dt,
            state=MachineState.WORKING,
            seat_occupied=True if sensed else None,
            coolant_temp_c=coolant,
            ambient_temp_c=ambient,
            fuel_rate_lph=15,
            engine_started_at=started,
            task_type=task_type,
            truck_present=truck,
            truck_source=source,
            in_break_window=False,
        )
    )
    return out, provisional


@pytest.mark.parametrize("tier", ALL)
def test_scheduled_break(tier) -> None:
    out, _ = idle_run(tier, 15, in_break=True)
    assert out.closed.reason == IdleReason.SCHEDULED_BREAK
    assert out.closed.evidence == ["in_break_window"]


@pytest.mark.parametrize("tier", SEAT_SENSED)
def test_warm_up_by_coolant(tier) -> None:
    out, _ = idle_run(tier, 4, coolant=35.0, engine_started_s_before=0)
    assert out.closed.reason == IdleReason.WARM_UP
    assert "coolant_cold" in out.closed.evidence and out.closed.confidence == 0.9


def test_warm_up_time_based_on_basic() -> None:
    out, _ = idle_run(SensorTier.BASIC, 4, engine_started_s_before=0)
    assert out.closed.reason == IdleReason.WARM_UP
    assert "time_based" in out.closed.evidence and out.closed.confidence == 0.7


def test_long_cold_warm_up_allowed_below_zero_on_basic() -> None:
    out, _ = idle_run(SensorTier.BASIC, 12, engine_started_s_before=0, ambient=-6)
    assert out.closed.reason == IdleReason.WARM_UP
    warm, _ = idle_run(SensorTier.BASIC, 12, engine_started_s_before=0, ambient=20)
    assert warm.closed.reason != IdleReason.WARM_UP  # 12 min is too long when it is not freezing


@pytest.mark.parametrize("tier", SEAT_SENSED)
def test_warm_engine_restart_is_not_warm_up(tier) -> None:
    out, _ = idle_run(tier, 3, coolant=80.0, engine_started_s_before=0)
    assert out.closed.reason != IdleReason.WARM_UP


@pytest.mark.parametrize("tier", SEAT_SENSED)
def test_unattended_running(tier) -> None:
    out, _ = idle_run(tier, 6, seat=False)
    assert out.closed.reason == IdleReason.UNATTENDED_RUNNING
    assert out.closed.response == "safety_reminder_on_return"
    assert out.closed.lesson == "L-SHUTDOWN"


def test_unattended_cannot_be_seen_on_basic() -> None:
    out, _ = idle_run(SensorTier.BASIC, 6, seat=False)
    assert out.closed.reason != IdleReason.UNATTENDED_RUNNING


@pytest.mark.parametrize(
    ("tier", "confidence", "evidence"),
    [
        (SensorTier.ADVANCED, 0.95, "no_truck_sensor"),
        (SensorTier.STANDARD, 0.8, "no_truck_dispatch_log"),
        (SensorTier.BASIC, 0.7, "no_truck_dispatch_log"),
    ],
)
def test_waiting_for_truck(tier, confidence, evidence) -> None:
    out, _ = idle_run(tier, 18, task_type="truck_loading", truck=False)
    assert out.closed.reason == IdleReason.WAITING_FOR_TRUCK
    assert out.closed.confidence == confidence and out.closed.evidence == [evidence]
    assert (
        out.closed.response == "offer_lesson" and out.closed.supervisor == "site_issue_truck_supply"
    )


@pytest.mark.parametrize("tier", ALL)
def test_truck_present_is_not_waiting(tier) -> None:
    out, _ = idle_run(tier, 8, task_type="truck_loading", truck=True)
    assert out.closed.reason == IdleReason.HABIT


@pytest.mark.parametrize(
    ("tier", "confidence"),
    [(SensorTier.BASIC, 0.6), (SensorTier.STANDARD, 0.85), (SensorTier.ADVANCED, 0.85)],
)
def test_habit(tier, confidence) -> None:
    out, _ = idle_run(tier, 8)
    assert out.closed.reason == IdleReason.HABIT and out.closed.confidence == confidence
    assert out.closed.response == "coach_after_segment"


@pytest.mark.parametrize("tier", ALL)
def test_unknown_short_seated_idle(tier) -> None:
    out, _ = idle_run(tier, 2)
    assert out.closed.reason == IdleReason.UNKNOWN


@pytest.mark.parametrize("tier", ALL)
def test_short_idle_is_ignored(tier) -> None:
    out, _ = idle_run(tier, 0.5)
    assert out.closed is None and out.discarded


def test_fuel_and_provisional_updates_at_1hz() -> None:
    out, provisional = idle_run(SensorTier.ADVANCED, 3, dt=1.0)
    assert out.closed.fuel_l == pytest.approx(3.2 * 3 / 60, rel=1e-6)
    assert len(provisional) >= 12  # every 10 s after the first minute
    assert all(p.provisional for p in provisional)
