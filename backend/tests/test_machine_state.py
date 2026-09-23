"""Machine state, cab mode and continuous operation (TRD §6.1, D-006)."""

from datetime import UTC, datetime, time, timedelta

import pytest

from shiftmate.engines.machine_state import BreakWindow, MachineStateEngine, classify_state
from shiftmate.schema.enums import CabMode, MachineState

T0 = datetime(2026, 9, 24, 7, 0, tzinfo=UTC)


def run(engine, pattern, dt=1.0, start=T0):
    """pattern: list of (seconds, engine_on, hydraulic, speed)."""
    ts = start
    out = None
    for seconds, on, hyd, speed in pattern:
        for _ in range(int(seconds / dt)):
            out = engine.update(ts, on, hyd, speed, dt)
            ts += timedelta(seconds=dt)
    return out, ts


def test_classify_state() -> None:
    assert classify_state(False, True, 3) == MachineState.ENGINE_OFF
    assert classify_state(True, True, 3) == MachineState.WORKING
    assert classify_state(True, False, 0.6) == MachineState.TRAVELLING
    assert classify_state(True, False, 0.2) == MachineState.IDLE


@pytest.mark.parametrize("dt", [1.0, 30.0])
def test_paused_after_30s_idle_and_working_on_movement(dt) -> None:
    e = MachineStateEngine(paused_idle_seconds=30, rest_reset_min=10)
    out, ts = run(e, [(120, True, True, 0)], dt)
    assert out.mode == CabMode.WORKING
    out, ts = run(e, [(dt, True, False, 0)], dt, ts)  # a short idle keeps Working (at 1 s)
    if dt < 30:
        assert out.mode == CabMode.WORKING
    out, ts = run(e, [(30, True, False, 0)], dt, ts)
    assert out.mode == CabMode.PAUSED
    out, _ = run(e, [(dt, True, False, 1.0)], dt, ts)  # any travel → Working immediately
    assert out.mode == CabMode.WORKING and out.mode_changed


def test_engine_off_is_paused() -> None:
    e = MachineStateEngine(30, 10)
    out, _ = run(e, [(5, False, False, 0)])
    assert out.state == MachineState.ENGINE_OFF and out.mode == CabMode.PAUSED


def test_waiting_for_truck_does_not_reset_continuous_operation() -> None:
    e = MachineStateEngine(30, 10)
    out, ts = run(e, [(3600, True, True, 0), (18 * 60, True, False, 0), (600, True, True, 0)], 30)
    assert out.continuous_operation_min == pytest.approx(60 + 18 + 10)


def test_ten_minutes_engine_off_resets() -> None:
    e = MachineStateEngine(30, 10)
    out, ts = run(e, [(3600, True, True, 0), (9 * 60, False, False, 0)], 30)
    assert out.continuous_operation_min == pytest.approx(60)  # 9 min is not enough
    out, ts = run(e, [(60, False, False, 0), (300, True, True, 0)], 30, ts)
    assert out.continuous_operation_min == pytest.approx(5)
    assert out.minutes_since_break == pytest.approx(5)


def test_idle_in_scheduled_break_window_resets() -> None:
    brk = [BreakWindow(time(10, 30), 15)]
    e = MachineStateEngine(30, 10, brk)
    start = datetime(2026, 9, 24, 8, 30, tzinfo=UTC)
    out, ts = run(e, [(2 * 3600, True, True, 0), (15 * 60, True, False, 0)], 30, start)
    assert out.resting and out.continuous_operation_min == 0


def test_skipped_break_keeps_counting() -> None:
    brk = [BreakWindow(time(10, 30), 15)]
    e = MachineStateEngine(30, 10, brk)
    start = datetime(2026, 9, 24, 7, 5, tzinfo=UTC)
    out, _ = run(e, [(int(3.9 * 3600), True, True, 0)], 30, start)  # works through 10:30
    assert out.continuous_operation_min == pytest.approx(3.9 * 60)
    assert out.minutes_since_break == pytest.approx(3.9 * 60)


def test_manual_break() -> None:
    e = MachineStateEngine(30, 10)
    out, ts = run(e, [(3600, True, True, 0)], 30)
    e.set_manual_break(True)
    out, ts = run(e, [(600, True, False, 0)], 30, ts)
    assert out.continuous_operation_min == 0


def test_engine_start_time_tracked() -> None:
    e = MachineStateEngine(30, 10)
    _, ts = run(e, [(60, False, False, 0)])
    out = e.update(ts, True, False, 0, 1.0)
    assert out.engine_started_at == ts
