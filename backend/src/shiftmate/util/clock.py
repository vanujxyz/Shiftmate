"""Injected clocks (CLAUDE.md §4): engines and the simulator never call `datetime.now()`."""

from datetime import datetime, timedelta
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime: ...


class SimClock:
    """A clock that only moves when told to. Timezone-aware."""

    def __init__(self, start: datetime) -> None:
        if start.tzinfo is None:
            raise ValueError("SimClock needs a timezone-aware start time")
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> datetime:
        self._now = self._now + timedelta(seconds=seconds)
        return self._now

    def set(self, when: datetime) -> None:
        self._now = when
