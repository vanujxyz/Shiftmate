"""Deterministic identifiers (D-017).

`uuid7_from(ts, rng)` builds an RFC 9562 version-7 UUID whose 48-bit time field comes from the
*simulated* timestamp and whose 74 random bits come from a seeded numpy generator. Same clock and
seed ⇒ same ids, which keeps event logs reproducible and still time-sortable.
"""

import uuid
from datetime import datetime

import numpy as np


def uuid7_from(ts: datetime, rng: np.random.Generator) -> str:
    unix_ms = int(ts.timestamp() * 1000) & ((1 << 48) - 1)
    rand_a = int(rng.integers(0, 1 << 12))
    rand_b = int(rng.integers(0, 1 << 62))
    value = (unix_ms << 80) | (0x7 << 76) | (rand_a << 64) | (0b10 << 62) | rand_b
    return str(uuid.UUID(int=value))


def interval_record_id(machine_id: str, end: datetime) -> str:
    return f"{machine_id}|{end.isoformat()}"
