"""The Fleet Service's store: one DuckDB file holding what the machines uploaded (TRD §9.2).

Tables:
- `intervals` — 15-minute interval summaries (every `IntervalRecord` field), keyed by `record_id`;
- `events` — events the edge shares (safety-critical events, site issues, reports' events),
  keyed by `event_id`;
- `reports` — incident, near-miss and equipment reports, keyed by `report_id`;
- `tasks` — task summaries (plans and outcomes), keyed by `task_id`;
- `machines`, `operators` — the roster (reference data the fleet owns);
- `ingest_log` — one row per ingest request, for live rates and `/scale/stats`.

**Idempotent ingest.** Every table has a primary key and records are inserted with
`INSERT OR IGNORE`, so a batch the edge re-sends after a timeout changes nothing. Tasks are the
one exception: a task is sent when it starts and again when it ends, and the later status
replaces the earlier one (scheduled → active → done, never backwards).

**Privacy at the door.** Events that are neither shared with the supervisor nor an incident or
near miss are rejected, even if a client sends them (P-03, P-05); raw ticks have no endpoint.

**Seeding.** A new, empty store is filled with the simulated history exactly as the edges would
have uploaded it (the edge-replay output in `data/history`), so the supervisor views have weeks
of data. Ground-truth files are never read (golden rule 5).

Times are stored in UTC; the aggregates convert to each site's local day.
"""

from __future__ import annotations

import json
import logging
import types
import typing
from datetime import UTC, date, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd
from pydantic import AwareDatetime, ValidationError

from shiftmate.schema.intervals import IntervalRecord

log = logging.getLogger(__name__)

SHAREABLE_TYPES = ("incident", "near_miss")  # always uploaded, even if not flagged shared
STATUS_RANK = {"scheduled": 0, "active": 1, "done": 2}
SCALE_SOURCE = "scale"

EVENT_COLUMNS = {
    "event_id": "VARCHAR PRIMARY KEY",
    "ts": "TIMESTAMPTZ",
    "machine_id": "VARCHAR",
    "operator_id": "VARCHAR",
    "site_id": "VARCHAR",
    "type": "VARCHAR",
    "priority": "VARCHAR",
    "code": "VARCHAR",
    "payload": "VARCHAR",
    "shared_with_supervisor": "BOOLEAN",
    "source": "VARCHAR",
}
REPORT_COLUMNS = {
    "report_id": "VARCHAR PRIMARY KEY",
    "ts": "TIMESTAMPTZ",
    "machine_id": "VARCHAR",
    "operator_id": "VARCHAR",
    "site_id": "VARCHAR",
    "type": "VARCHAR",
    "severity": "VARCHAR",
    "summary_en": "VARCHAR",
    "data": "VARCHAR",
    "source": "VARCHAR",
}
TASK_COLUMNS = {
    "task_id": "VARCHAR PRIMARY KEY",
    "site_id": "VARCHAR",
    "machine_id": "VARCHAR",
    "operator_id": "VARCHAR",
    "task_type": "VARCHAR",
    "zone_id": "VARCHAR",
    "planned_quantity": "DOUBLE",
    "quantity_unit": "VARCHAR",
    "scheduled_start": "TIMESTAMPTZ",
    "actual_start": "TIMESTAMPTZ",
    "actual_end": "TIMESTAMPTZ",
    "actual_duration_min": "DOUBLE",
    "status": "VARCHAR",
    "done_qty": "DOUBLE",
    "source": "VARCHAR",
}


def _duck_type(annotation: Any) -> str:
    """DuckDB column type for a pydantic field annotation (Optional[...] unwrapped)."""
    if isinstance(annotation, types.UnionType) or typing.get_origin(annotation) is typing.Union:
        args = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _duck_type(args[0])
    if annotation is AwareDatetime or annotation is datetime:
        return "TIMESTAMPTZ"
    if annotation is bool:
        return "BOOLEAN"
    if annotation is int:
        return "BIGINT"
    if annotation is float:
        return "DOUBLE"
    if isinstance(annotation, type) and issubclass(annotation, Enum):
        return "VARCHAR"
    return "VARCHAR"


INTERVAL_COLUMNS = {
    name: _duck_type(field.annotation) for name, field in IntervalRecord.model_fields.items()
}
INTERVAL_COLUMNS["record_id"] = "VARCHAR PRIMARY KEY"
INTERVAL_COLUMNS["source"] = "VARCHAR"


def _ddl(table: str, columns: dict[str, str]) -> str:
    cols = ", ".join(f'"{c}" {t}' for c, t in columns.items())
    return f"CREATE TABLE IF NOT EXISTS {table} ({cols})"


def _utc(value: Any) -> datetime | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    ts = pd.Timestamp(value)
    if ts.tzinfo is None:
        raise ValueError(f"timestamp without a time zone: {value!r}")
    return ts.tz_convert(UTC).to_pydatetime()


class FleetStore:
    def __init__(self, path: Path | None = None) -> None:
        if path is not None:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.con = duckdb.connect(str(path) if path else ":memory:")
        self.con.execute("SET TimeZone = 'UTC'")
        self.con.execute(_ddl("intervals", INTERVAL_COLUMNS))
        self.con.execute(_ddl("events", EVENT_COLUMNS))
        self.con.execute(_ddl("reports", REPORT_COLUMNS))
        self.con.execute(_ddl("tasks", TASK_COLUMNS))
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS ingest_log (received_at TIMESTAMPTZ, kind VARCHAR, "
            "source VARCHAR, received BIGINT, inserted BIGINT, bytes BIGINT)"
        )
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS machines (machine_id VARCHAR PRIMARY KEY, "
            "machine_type VARCHAR, model VARCHAR, model_year BIGINT, sensor_tier VARCHAR, "
            "site_id VARCHAR)"
        )
        self.con.execute(
            "CREATE TABLE IF NOT EXISTS operators (operator_id VARCHAR PRIMARY KEY, name VARCHAR, "
            "preferred_language VARCHAR, experience_years DOUBLE, home_site_id VARCHAR)"
        )

    def close(self) -> None:
        self.con.close()

    # --- reference data and seeding ----------------------------------------------------------
    def count(self, table: str, where: str = "", params: list[Any] | None = None) -> int:
        sql = f"SELECT count(*) FROM {table}" + (f" WHERE {where}" if where else "")
        return int(self.con.execute(sql, params or []).fetchone()[0])

    def load_roster(self, machines: pd.DataFrame, operators: pd.DataFrame) -> None:
        m = machines[
            ["machine_id", "machine_type", "model", "model_year", "sensor_tier", "site_id"]
        ]
        o = operators[
            ["operator_id", "name", "preferred_language", "experience_years", "home_site_id"]
        ]
        self.con.register("m_in", m)
        self.con.register("o_in", o)
        self.con.execute("INSERT OR IGNORE INTO machines SELECT * FROM m_in")
        self.con.execute("INSERT OR IGNORE INTO operators SELECT * FROM o_in")
        self.con.unregister("m_in")
        self.con.unregister("o_in")

    def seed_from_history(self, history_dir: Path) -> dict[str, int]:
        """Load what the edges would have uploaded during the simulated history."""
        h = history_dir
        out: dict[str, int] = {}
        if (h / "intervals.parquet").exists():
            cols = [c for c in INTERVAL_COLUMNS if c != "source"]
            sel = ", ".join(f'"{c}"' for c in cols)
            path = (h / "intervals.parquet").as_posix()
            out["intervals"] = self.con.execute(
                f"INSERT OR IGNORE INTO intervals SELECT {sel}, 'history' "
                f"FROM read_parquet('{path}')"
            ).fetchone()[0]
        if (h / "events.parquet").exists():
            path = (h / "events.parquet").as_posix()
            cols = [c for c in EVENT_COLUMNS if c != "source"]
            sel = ", ".join(f'"{c}"' for c in cols)
            out["events"] = self.con.execute(
                f"INSERT OR IGNORE INTO events SELECT {sel}, 'history' FROM read_parquet('{path}') "
                f"WHERE shared_with_supervisor OR type IN {SHAREABLE_TYPES}"
            ).fetchone()[0]
        if (h / "tasks.parquet").exists():
            path = (h / "tasks.parquet").as_posix()
            out["tasks"] = self.con.execute(
                "INSERT OR IGNORE INTO tasks SELECT task_id, site_id, machine_id, operator_id, "
                "task_type, zone_id, planned_quantity, quantity_unit, scheduled_start, "
                "actual_start, actual_end, actual_duration_min, status, "
                "CASE WHEN status = 'done' THEN planned_quantity ELSE NULL END, 'history' "
                f"FROM read_parquet('{path}')"
            ).fetchone()[0]
        return {k: int(v) for k, v in out.items()}

    def is_empty(self) -> bool:
        return all(self.count(t) == 0 for t in ("intervals", "events", "tasks", "reports"))

    # --- ingest ---------------------------------------------------------------------------------
    def _insert(self, table: str, columns: list[str], rows: list[dict[str, Any]]) -> int:
        if not rows:
            return 0
        df = pd.DataFrame(rows, columns=columns)
        self.con.register("batch_in", df)
        try:
            sel = ", ".join(f'"{c}"' for c in columns)
            return int(
                self.con.execute(
                    f"INSERT OR IGNORE INTO {table} ({sel}) SELECT {sel} FROM batch_in"
                ).fetchone()[0]
            )
        finally:
            self.con.unregister("batch_in")

    def ingest_intervals(self, records: list[dict[str, Any]], source: str | None) -> dict:
        rows, rejected = [], 0
        for r in records:
            try:
                rec = IntervalRecord.model_validate(r)
                if not rec.record_id or not rec.site_id:
                    raise ValueError("record_id and site_id are required")
            except (ValidationError, ValueError):
                rejected += 1
                continue
            row = rec.model_dump()
            for k, v in row.items():
                if isinstance(v, Enum):
                    row[k] = v.value
                elif isinstance(v, datetime):
                    row[k] = _utc(v)
            row["source"] = source
            rows.append(row)
        inserted = self._insert("intervals", list(INTERVAL_COLUMNS), rows)
        return _result("intervals", len(records), inserted, rejected)

    def ingest_events(self, records: list[dict[str, Any]], source: str | None) -> dict:
        rows, rejected = [], 0
        for r in records:
            try:
                shared = bool(r.get("shared_with_supervisor"))
                if not shared and r.get("type") not in SHAREABLE_TYPES:
                    raise ValueError("not shared with the supervisor (privacy)")
                payload = r.get("payload") or {}
                rows.append(
                    {
                        "event_id": str(r["event_id"]),
                        "ts": _utc(r["ts"]),
                        "machine_id": str(r["machine_id"]),
                        "operator_id": r.get("operator_id"),
                        "site_id": str(r["site_id"]),
                        "type": str(r["type"]),
                        "priority": r.get("priority"),
                        "code": r.get("code"),
                        "payload": payload if isinstance(payload, str) else json.dumps(payload),
                        "shared_with_supervisor": shared,
                        "source": source,
                    }
                )
            except (KeyError, ValueError, TypeError):
                rejected += 1
        inserted = self._insert("events", list(EVENT_COLUMNS), rows)
        return _result("events", len(records), inserted, rejected)

    def ingest_reports(self, records: list[dict[str, Any]], source: str | None) -> dict:
        rows, rejected = [], 0
        for r in records:
            try:
                draft = r["draft"]
                context = r.get("context") or {}
                rows.append(
                    {
                        "report_id": str(r["report_id"]),
                        "ts": _utc(r["ts"]),
                        "machine_id": str(r.get("machine_id") or context["machine_id"]),
                        "operator_id": r.get("operator_id") or context.get("operator_id"),
                        "site_id": str(context["site_id"]),
                        "type": str(draft["type"]),
                        "severity": draft.get("severity"),
                        "summary_en": draft.get("summary_en"),
                        "data": json.dumps(r, default=str),
                        "source": source,
                    }
                )
            except (KeyError, ValueError, TypeError):
                rejected += 1
        inserted = self._insert("reports", list(REPORT_COLUMNS), rows)
        return _result("reports", len(records), inserted, rejected)

    def ingest_tasks(self, records: list[dict[str, Any]], source: str | None) -> dict:
        """Tasks are upserted: a later status (active → done) replaces the stored row."""
        rows, rejected = [], 0
        for r in records:
            try:
                status = str(r["status"])
                if status not in STATUS_RANK:
                    raise ValueError(status)
                rows.append(
                    {
                        "task_id": str(r["task_id"]),
                        "site_id": str(r["site_id"]),
                        "machine_id": str(r["machine_id"]),
                        "operator_id": r.get("operator_id"),
                        "task_type": str(r["task_type"]),
                        "zone_id": r.get("zone_id"),
                        "planned_quantity": float(r["planned_quantity"]),
                        "quantity_unit": r.get("quantity_unit"),
                        "scheduled_start": _utc(r.get("scheduled_start")),
                        "actual_start": _utc(r.get("actual_start")),
                        "actual_end": _utc(r.get("actual_end")),
                        "actual_duration_min": r.get("actual_duration_min"),
                        "status": status,
                        "done_qty": r.get("done_qty"),
                        "source": source,
                    }
                )
            except (KeyError, ValueError, TypeError):
                rejected += 1
        existing: dict[str, str] = {}
        if rows:
            ids = [r["task_id"] for r in rows]
            found = self.con.execute(
                "SELECT task_id, status FROM tasks WHERE task_id IN (SELECT unnest(?))", [ids]
            ).fetchall()
            existing = dict(found)
        fresh, newer, duplicates = [], [], 0
        latest: dict[str, dict[str, Any]] = {}
        for row in rows:  # within one batch, keep the most advanced status per task
            prev = latest.get(row["task_id"])
            if prev is None or STATUS_RANK[row["status"]] >= STATUS_RANK[prev["status"]]:
                latest[row["task_id"]] = row
        for task_id, row in latest.items():
            old = existing.get(task_id)
            if old is None:
                fresh.append(row)
            elif STATUS_RANK[row["status"]] > STATUS_RANK.get(old, -1):
                newer.append(row)
            else:
                duplicates += 1
        duplicates += len(rows) - len(latest)
        if newer:
            self.con.execute(
                "DELETE FROM tasks WHERE task_id IN (SELECT unnest(?))",
                [[r["task_id"] for r in newer]],
            )
        self._insert("tasks", list(TASK_COLUMNS), fresh + newer)
        return {
            "kind": "tasks",
            "received": len(records),
            "inserted": len(fresh),
            "updated": len(newer),
            "duplicates": duplicates,
            "rejected": rejected,
        }

    def log_ingest(
        self, kind: str, source: str | None, received: int, inserted: int, nbytes: int
    ) -> None:
        self.con.execute(
            "INSERT INTO ingest_log VALUES (?, ?, ?, ?, ?, ?)",
            [datetime.now(UTC), kind, source, received, inserted, nbytes],
        )

    # --- queries (DataFrames for the aggregates) ------------------------------------------------
    def df(self, sql: str, params: list[Any] | None = None) -> pd.DataFrame:
        return self.con.execute(sql, params or []).df()

    def intervals(self, site_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        return self.df(
            'SELECT * FROM intervals WHERE site_id = ? AND "timestamp" > ? AND "timestamp" <= ? '
            'ORDER BY machine_id, "timestamp"',
            [site_id, start, end],
        )

    def events(self, site_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        return self.df(
            "SELECT * FROM events WHERE site_id = ? AND ts >= ? AND ts < ? ORDER BY ts",
            [site_id, start, end],
        )

    def reports(self, site_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        return self.df(
            "SELECT * FROM reports WHERE site_id = ? AND ts >= ? AND ts < ? ORDER BY ts",
            [site_id, start, end],
        )

    def tasks(self, site_id: str, start: datetime, end: datetime) -> pd.DataFrame:
        """Tasks scheduled or worked on in [start, end)."""
        return self.df(
            "SELECT * FROM tasks WHERE site_id = ? AND ("
            "(scheduled_start >= ? AND scheduled_start < ?) OR "
            "(actual_start >= ? AND actual_start < ?)) ORDER BY machine_id, scheduled_start",
            [site_id, start, end, start, end],
        )

    def done_tasks(self, start: datetime, end: datetime) -> pd.DataFrame:
        """Finished tasks across the whole fleet (baselines for on-track status)."""
        return self.df(
            "SELECT t.task_type, m.machine_type, t.planned_quantity, t.actual_duration_min "
            "FROM tasks t LEFT JOIN machines m USING (machine_id) "
            "WHERE t.status = 'done' AND t.actual_duration_min > 0 AND t.actual_end >= ? "
            "AND t.actual_end < ?",
            [start, end],
        )

    def machines(self, site_id: str | None = None) -> pd.DataFrame:
        if site_id is None:
            return self.df("SELECT * FROM machines ORDER BY machine_id")
        return self.df("SELECT * FROM machines WHERE site_id = ? ORDER BY machine_id", [site_id])

    def operators(self) -> pd.DataFrame:
        return self.df("SELECT * FROM operators ORDER BY operator_id")

    def _one_time(self, sql: str, params: list[Any]) -> datetime | None:
        """A single timestamp result (read through pandas: DuckDB's fetch needs pytz)."""
        value = self.df(sql, params).iloc[0, 0]
        return None if pd.isna(value) else pd.Timestamp(value).to_pydatetime()

    def interval_span(self, site_id: str) -> tuple[datetime | None, datetime | None]:
        d = self.df(
            'SELECT min("timestamp") AS a, max("timestamp") AS b FROM intervals WHERE site_id = ?',
            [site_id],
        )
        a, b = d.a.iloc[0], d.b.iloc[0]
        return (
            None if pd.isna(a) else pd.Timestamp(a).to_pydatetime(),
            None if pd.isna(b) else pd.Timestamp(b).to_pydatetime(),
        )

    def last_ingest(self, site_id: str) -> datetime | None:
        """When the fleet last received an upload from a machine at this site."""
        return self._one_time(
            "SELECT max(l.received_at) FROM ingest_log l JOIN machines m "
            "ON l.source = m.machine_id WHERE m.site_id = ?",
            [site_id],
        )

    def totals(self) -> dict[str, int]:
        return {t: self.count(t) for t in ("intervals", "events", "reports", "tasks")}

    def site_totals(self) -> dict[str, int]:
        """Stored records that belong to real sites (everything except the scale run)."""
        return {
            t: self.count(t, "source IS DISTINCT FROM ?", [SCALE_SOURCE])
            for t in ("intervals", "events", "reports", "tasks")
        }

    def scale_machines(self) -> int:
        return int(
            self.con.execute(
                "SELECT count(DISTINCT machine_id) FROM intervals WHERE source = ?", [SCALE_SOURCE]
            ).fetchone()[0]
        )

    def recent_ingest(self, seconds: float) -> int:
        since = datetime.now(UTC) - timedelta(seconds=seconds)
        row = self.con.execute(
            "SELECT coalesce(sum(received), 0) FROM ingest_log WHERE received_at >= ?", [since]
        ).fetchone()
        return int(row[0])

    def clear_scale(self) -> None:
        """Remove an earlier scale run (its synthetic machines only)."""
        for t in ("intervals", "events"):
            self.con.execute(f"DELETE FROM {t} WHERE source = ?", [SCALE_SOURCE])


def _result(kind: str, received: int, inserted: int, rejected: int) -> dict[str, Any]:
    return {
        "kind": kind,
        "received": received,
        "inserted": inserted,
        "updated": 0,
        "duplicates": received - inserted - rejected,
        "rejected": rejected,
    }


def local_day(tz: str, day: date) -> tuple[datetime, datetime]:
    """[start, end) of a site's local calendar day, in UTC."""
    start = pd.Timestamp(datetime.combine(day, datetime.min.time())).tz_localize(tz)
    end = pd.Timestamp(datetime.combine(day + timedelta(days=1), datetime.min.time())).tz_localize(
        tz
    )  # not start + 24 h: a day with a clock change is 23 or 25 hours long
    return start.tz_convert(UTC).to_pydatetime(), end.tz_convert(UTC).to_pydatetime()
