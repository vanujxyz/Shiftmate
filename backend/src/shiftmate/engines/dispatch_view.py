"""Truck presence per loading zone as seen through the site dispatch log (TRD §6.4).

Machines without a truck sensor (basic and standard tiers) cannot see trucks. The site's truck
management system publishes a dispatch log (assigned / arrived / departed per zone). This view
replays those entries in time order and answers "is a truck logged as present in zone Z now?":
a truck is present from its `arrived` entry until its `departed` entry. Because real logs miss
entries, a truck with no `departed` entry stops counting after `presence_timeout_min`.
Pure: entries and times are passed in.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta


@dataclass(frozen=True)
class DispatchLogEntry:
    ts: datetime
    zone_id: str
    truck_id: str
    event: str  # assigned | arrived | departed


@dataclass
class DispatchView:
    presence_timeout_min: float
    _entries: list[DispatchLogEntry] = field(default_factory=list)
    _cursor: int = 0
    _present: dict[str, dict[str, datetime]] = field(default_factory=dict)  # zone → truck → since

    def add(self, entries: list[DispatchLogEntry]) -> None:
        """Add log entries (any order); they are applied as time passes."""
        self._entries.extend(entries)
        self._entries.sort(key=lambda e: (e.ts, e.truck_id, e.event))

    def truck_present(self, zone_id: str, now: datetime) -> bool:
        while self._cursor < len(self._entries) and self._entries[self._cursor].ts <= now:
            e = self._entries[self._cursor]
            self._cursor += 1
            zone = self._present.setdefault(e.zone_id, {})
            if e.event == "arrived":
                zone[e.truck_id] = e.ts
            elif e.event == "departed":
                zone.pop(e.truck_id, None)
        zone = self._present.get(zone_id, {})
        limit = timedelta(minutes=self.presence_timeout_min)
        return any(now - since <= limit for since in zone.values())
