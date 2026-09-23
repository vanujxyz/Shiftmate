"""Local SQLite store on the machine (TRD §1.1, §9.3).

Everything the cab needs works from this file with no network: events, interval records,
reports, lesson and drill results, instructor slots and bookings. The `outbox` table queues what
must reach the fleet service (interval summaries, shared events, reports, task summaries —
`privacy.yaml → fleet_upload`); `edge/sync.py` drains it when online.

Rows keep their full JSON next to a few indexed columns, which keeps the schema small and easy to
explain. Times are stored as ISO 8601 UTC strings.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import (
    Boolean,
    Column,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    delete,
    func,
    insert,
    select,
    update,
)

metadata = MetaData()

events = Table(
    "events",
    metadata,
    Column("event_id", String, primary_key=True),
    Column("ts", String, index=True),
    Column("machine_id", String, index=True),
    Column("operator_id", String, index=True),
    Column("site_id", String),
    Column("type", String, index=True),
    Column("priority", String),
    Column("code", String),
    Column("payload", Text),
    Column("shared_with_supervisor", Boolean),
    Column("synced", Boolean, default=False),
)
intervals = Table(
    "intervals",
    metadata,
    Column("record_id", String, primary_key=True),
    Column("ts", String, index=True),
    Column("machine_id", String, index=True),
    Column("operator_id", String, index=True),
    Column("data", Text),
)
reports = Table(
    "reports",
    metadata,
    Column("report_id", String, primary_key=True),
    Column("ts", String, index=True),
    Column("operator_id", String, index=True),
    Column("machine_id", String),
    Column("data", Text),
)
completions = Table(
    "lesson_completions",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("operator_id", String, index=True),
    Column("lesson_id", String),
    Column("ts", String),
    Column("score", Float),
    Column("duration_s", Float),
    Column("language", String),
)
drills = Table(
    "drill_results",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("operator_id", String, index=True),
    Column("drill_id", String),
    Column("ts", String),
    Column("score", Float),
    Column("data", Text),
)
slots = Table(
    "training_slots",
    metadata,
    Column("slot_id", String, primary_key=True),
    Column("site_id", String, index=True),
    Column("start", String),
    Column("data", Text),
    Column("seats_left", Integer),
)
bookings = Table(
    "bookings",
    metadata,
    Column("booking_id", String, primary_key=True),
    Column("operator_id", String, index=True),
    Column("slot_id", String),
    Column("status", String),
    Column("ts", String),
)
outbox = Table(
    "outbox",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("kind", String),  # interval | event | report | task
    Column("record_id", String, index=True),
    Column("ts", String, index=True),
    Column("payload", Text),
    Column("synced_at", String, nullable=True),
)


def iso(ts: datetime) -> str:
    return ts.astimezone(UTC).isoformat()


class EdgeStore:
    def __init__(self, path: Path | None) -> None:
        url = f"sqlite:///{path.as_posix()}" if path else "sqlite://"
        if path:
            path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, future=True)
        metadata.create_all(self.engine)

    # --- generic -----------------------------------------------------------------------------
    def reset(self) -> None:
        with self.engine.begin() as c:
            for table in reversed(metadata.sorted_tables):
                if table.name not in ("training_slots",):
                    c.execute(delete(table))

    def truncate_after(self, ts: datetime) -> None:
        """Forget everything recorded after `ts` (used when the demo seeks backwards)."""
        cut = iso(ts)
        with self.engine.begin() as c:
            for table in (events, intervals, reports, completions, drills, outbox):
                c.execute(delete(table).where(table.c.ts > cut))
            c.execute(delete(bookings).where(bookings.c.ts > cut))

    # --- events and intervals -----------------------------------------------------------------
    def add_event(self, e: dict[str, Any]) -> None:
        row = {
            "event_id": e["event_id"],
            "ts": iso(e["ts"]),
            "machine_id": e["machine_id"],
            "operator_id": e.get("operator_id"),
            "site_id": e["site_id"],
            "type": e["type"],
            "priority": e.get("priority"),
            "code": e.get("code"),
            "payload": json.dumps(e.get("payload", {}), default=str),
            "shared_with_supervisor": bool(e.get("shared_with_supervisor")),
            "synced": False,
        }
        with self.engine.begin() as c:
            c.execute(insert(events).prefix_with("OR REPLACE"), row)
            if row["shared_with_supervisor"] or e["type"] in ("incident", "near_miss"):
                c.execute(
                    insert(outbox),
                    {
                        "kind": "event",
                        "record_id": row["event_id"],
                        "ts": row["ts"],
                        "payload": json.dumps(row),
                    },
                )

    def list_events(
        self,
        operator_id: str | None = None,
        machine_id: str | None = None,
        since: datetime | None = None,
        types: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        q = select(events).order_by(events.c.ts)
        if operator_id:
            q = q.where(events.c.operator_id == operator_id)
        if machine_id:
            q = q.where(events.c.machine_id == machine_id)
        if since:
            q = q.where(events.c.ts >= iso(since))
        if types:
            q = q.where(events.c.type.in_(types))
        with self.engine.connect() as c:
            rows = [dict(r._mapping) for r in c.execute(q)]
        for r in rows:
            r["payload"] = json.loads(r["payload"] or "{}")
        return rows

    def add_interval(self, record: dict[str, Any]) -> None:
        with self.engine.begin() as c:
            c.execute(
                insert(intervals).prefix_with("OR REPLACE"),
                {
                    "record_id": record["record_id"],
                    "ts": iso(record["timestamp"]),
                    "machine_id": record["machine_id"],
                    "operator_id": record["operator_id"],
                    "data": json.dumps(record, default=str),
                },
            )
            c.execute(
                insert(outbox),
                {
                    "kind": "interval",
                    "record_id": record["record_id"],
                    "ts": iso(record["timestamp"]),
                    "payload": json.dumps(record, default=str),
                },
            )

    def list_intervals(
        self, operator_id: str | None = None, since: datetime | None = None
    ) -> list[dict[str, Any]]:
        q = select(intervals.c.data).order_by(intervals.c.ts)
        if operator_id:
            q = q.where(intervals.c.operator_id == operator_id)
        if since:
            q = q.where(intervals.c.ts >= iso(since))
        with self.engine.connect() as c:
            return [json.loads(r[0]) for r in c.execute(q)]

    # --- reports ------------------------------------------------------------------------------
    def add_report(
        self, report_id: str, ts: datetime, operator_id: str | None, machine_id: str, data: dict
    ) -> None:
        with self.engine.begin() as c:
            c.execute(
                insert(reports),
                {
                    "report_id": report_id,
                    "ts": iso(ts),
                    "operator_id": operator_id,
                    "machine_id": machine_id,
                    "data": json.dumps(data, default=str),
                },
            )
            # the fleet ingests idempotently by report_id, so the uploaded record carries it
            upload = {
                "report_id": report_id,
                "operator_id": operator_id,
                "machine_id": machine_id,
                **data,
            }
            c.execute(
                insert(outbox),
                {
                    "kind": "report",
                    "record_id": report_id,
                    "ts": iso(ts),
                    "payload": json.dumps(upload, default=str),
                },
            )

    def add_task_summary(self, summary: dict[str, Any]) -> None:
        """A finished task, queued for the fleet (privacy.yaml → task_summaries)."""
        with self.engine.begin() as c:
            c.execute(
                insert(outbox),
                {
                    "kind": "task",
                    "record_id": summary["task_id"],
                    "ts": iso(summary["actual_end"]),
                    "payload": json.dumps(summary, default=str),
                },
            )

    def list_reports(self, operator_id: str | None = None, limit: int = 20) -> list[dict[str, Any]]:
        q = select(reports.c.report_id, reports.c.data).order_by(reports.c.ts.desc()).limit(limit)
        if operator_id:
            q = q.where(reports.c.operator_id == operator_id)
        with self.engine.connect() as c:
            out = []
            for report_id, data in c.execute(q):
                row = json.loads(data)
                row["report_id"] = report_id
                row["synced"] = self.is_synced(report_id)
                out.append(row)
            return out

    # --- learning -----------------------------------------------------------------------------
    def add_completion(
        self,
        operator_id: str,
        lesson_id: str,
        ts: datetime,
        score: float,
        duration_s: float,
        language: str,
    ) -> None:
        with self.engine.begin() as c:
            c.execute(
                insert(completions),
                {
                    "operator_id": operator_id,
                    "lesson_id": lesson_id,
                    "ts": iso(ts),
                    "score": score,
                    "duration_s": duration_s,
                    "language": language,
                },
            )

    def list_completions(self, operator_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            q = (
                select(completions)
                .where(completions.c.operator_id == operator_id)
                .order_by(completions.c.ts)
            )
            return [dict(r._mapping) for r in c.execute(q)]

    def add_drill(
        self, operator_id: str, drill_id: str, ts: datetime, score: float, data: dict
    ) -> None:
        with self.engine.begin() as c:
            c.execute(
                insert(drills),
                {
                    "operator_id": operator_id,
                    "drill_id": drill_id,
                    "ts": iso(ts),
                    "score": score,
                    "data": json.dumps(data, default=str),
                },
            )

    def list_drills(self, operator_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            q = select(drills).where(drills.c.operator_id == operator_id).order_by(drills.c.ts)
            rows = [dict(r._mapping) for r in c.execute(q)]
        for r in rows:
            r["data"] = json.loads(r["data"])
        return rows

    def upsert_slots(self, site_id: str, rows: list[dict[str, Any]]) -> None:
        with self.engine.begin() as c:
            existing = {
                r[0] for r in c.execute(select(slots.c.slot_id).where(slots.c.site_id == site_id))
            }
            for r in rows:
                if r["slot_id"] not in existing:
                    c.execute(
                        insert(slots),
                        {
                            "slot_id": r["slot_id"],
                            "site_id": site_id,
                            "start": r["start"],
                            "data": json.dumps(r, default=str),
                            "seats_left": r["seats_left"],
                        },
                    )

    def list_slots(self, site_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            q = (
                select(slots.c.data, slots.c.seats_left)
                .where(slots.c.site_id == site_id)
                .order_by(slots.c.start)
            )
            return [{**json.loads(d), "seats_left": s} for d, s in c.execute(q)]

    def book(self, booking_id: str, operator_id: str, slot_id: str, ts: datetime) -> bool:
        with self.engine.begin() as c:
            seats = c.execute(select(slots.c.seats_left).where(slots.c.slot_id == slot_id)).scalar()
            if seats is None or seats <= 0:
                return False
            already = c.execute(
                select(func.count())
                .select_from(bookings)
                .where(
                    (bookings.c.operator_id == operator_id)
                    & (bookings.c.slot_id == slot_id)
                    & (bookings.c.status == "booked")
                )
            ).scalar()
            if already:
                return True
            c.execute(update(slots).where(slots.c.slot_id == slot_id).values(seats_left=seats - 1))
            c.execute(
                insert(bookings),
                {
                    "booking_id": booking_id,
                    "operator_id": operator_id,
                    "slot_id": slot_id,
                    "status": "booked",
                    "ts": iso(ts),
                },
            )
            return True

    def list_bookings(self, operator_id: str) -> list[dict[str, Any]]:
        with self.engine.connect() as c:
            q = select(bookings).where(bookings.c.operator_id == operator_id)
            return [dict(r._mapping) for r in c.execute(q)]

    # --- outbox -------------------------------------------------------------------------------
    def outbox_pending(
        self, limit: int = 500, kinds: list[str] | None = None
    ) -> list[dict[str, Any]]:
        q = select(outbox).where(outbox.c.synced_at.is_(None)).order_by(outbox.c.id).limit(limit)
        if kinds is not None:
            q = q.where(outbox.c.kind.in_(kinds))
        with self.engine.connect() as c:
            return [dict(r._mapping) for r in c.execute(q)]

    def outbox_size(self, kinds: list[str] | None = None) -> int:
        q = select(func.count()).select_from(outbox).where(outbox.c.synced_at.is_(None))
        if kinds is not None:
            q = q.where(outbox.c.kind.in_(kinds))
        with self.engine.connect() as c:
            return int(c.execute(q).scalar() or 0)

    def mark_synced(self, ids: list[int], when: datetime) -> None:
        if not ids:
            return
        with self.engine.begin() as c:
            c.execute(update(outbox).where(outbox.c.id.in_(ids)).values(synced_at=iso(when)))

    def is_synced(self, record_id: str) -> bool:
        with self.engine.connect() as c:
            rows = c.execute(
                select(outbox.c.synced_at).where(outbox.c.record_id == record_id)
            ).fetchall()
        return bool(rows) and all(r[0] is not None for r in rows)
