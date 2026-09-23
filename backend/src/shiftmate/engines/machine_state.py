"""Machine state, cab mode and continuous operation (TRD §6.1).

State each tick:
- ENGINE_OFF  — engine off
- WORKING     — hydraulics active
- TRAVELLING  — moving at ≥ 0.5 km/h without hydraulics
- IDLE        — engine on, no hydraulics, speed < 0.5 km/h

Cab mode (for the UI): Paused when the machine has been IDLE for ≥ 30 s or the engine is off;
Working otherwise. Any movement switches back to Working immediately (DESIGN ModeTransition).

Continuous operation counts engine-on time since the last real rest. A rest is time with the
engine off, or idle inside a scheduled break window, or an operator-declared break ("start
break"); it resets the count once it has lasted 10 minutes. Waiting for a truck in the seat is
not rest (D-006). `minutes_since_break` is the wall-clock time since that last completed rest.

Each tick holds for `dt` seconds (the tick period), so the same engine works at 1 s and 30 s.
Pure: no clock reads, no I/O; time comes from the ticks.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time, timedelta

from shiftmate.schema.enums import CabMode, MachineState

MOVING_KMH = 0.5


@dataclass(frozen=True)
class BreakWindow:
    start: time
    minutes: int


@dataclass(frozen=True)
class MachineStateOutput:
    state: MachineState
    mode: CabMode
    idle_seconds: float  # how long the current IDLE run has lasted (0 when not idle)
    continuous_operation_min: float
    minutes_since_break: float
    engine_started_at: datetime | None
    resting: bool
    mode_changed: bool


def classify_state(
    engine_on: bool, hydraulic_active: bool, travel_speed_kmh: float
) -> MachineState:
    if not engine_on:
        return MachineState.ENGINE_OFF
    if hydraulic_active:
        return MachineState.WORKING
    if travel_speed_kmh >= MOVING_KMH:
        return MachineState.TRAVELLING
    return MachineState.IDLE


class MachineStateEngine:
    def __init__(
        self,
        paused_idle_seconds: float,
        rest_reset_min: float,
        breaks: list[BreakWindow] | None = None,
    ) -> None:
        self.paused_idle_seconds = paused_idle_seconds
        self.rest_reset_s = rest_reset_min * 60
        self.breaks = breaks or []
        self.idle_seconds = 0.0
        self.rest_seconds = 0.0
        self.continuous_s = 0.0
        self.last_rest_end: datetime | None = None
        self.engine_started_at: datetime | None = None
        self.mode = CabMode.PAUSED
        self.manual_break = False
        self._prev_engine_on = False

    def set_manual_break(self, on: bool) -> None:
        """Operator said "start break" / "end break" (F-ASK-04)."""
        self.manual_break = on

    def _in_break_window(self, ts: datetime) -> bool:
        for b in self.breaks:
            start = datetime.combine(ts.date(), b.start, tzinfo=ts.tzinfo)
            if start <= ts < start + timedelta(minutes=b.minutes):
                return True
        return False

    def update(
        self,
        ts: datetime,
        engine_on: bool,
        hydraulic_active: bool,
        travel_speed_kmh: float,
        dt: float,
    ) -> MachineStateOutput:
        state = classify_state(engine_on, hydraulic_active, travel_speed_kmh)
        if engine_on and not self._prev_engine_on:
            self.engine_started_at = ts
        self._prev_engine_on = engine_on
        if self.last_rest_end is None:
            self.last_rest_end = ts

        # idle run (the tick holds for dt, so a tick that starts idle has been idle for dt)
        self.idle_seconds = self.idle_seconds + dt if state == MachineState.IDLE else 0.0

        # rest and continuous operation
        resting = state == MachineState.ENGINE_OFF or (
            state == MachineState.IDLE and (self.manual_break or self._in_break_window(ts))
        )
        if resting:
            self.rest_seconds += dt
            if self.rest_seconds >= self.rest_reset_s:
                self.continuous_s = 0.0
                self.last_rest_end = ts + timedelta(seconds=dt)
        else:
            self.rest_seconds = 0.0
            if engine_on:
                self.continuous_s += dt

        # cab mode: paused after 30 s idle or with the engine off; working immediately on movement
        previous = self.mode
        if state == MachineState.ENGINE_OFF or self.idle_seconds >= self.paused_idle_seconds:
            self.mode = CabMode.PAUSED
        elif state in (MachineState.WORKING, MachineState.TRAVELLING):
            self.mode = CabMode.WORKING
        # (a short idle keeps the current mode)

        since_break = (ts + timedelta(seconds=dt) - self.last_rest_end).total_seconds() / 60
        return MachineStateOutput(
            state=state,
            mode=self.mode,
            idle_seconds=self.idle_seconds,
            continuous_operation_min=self.continuous_s / 60,
            minutes_since_break=max(0.0, since_break) if not resting else 0.0,
            engine_started_at=self.engine_started_at if engine_on else None,
            resting=resting,
            mode_changed=self.mode != previous,
        )
