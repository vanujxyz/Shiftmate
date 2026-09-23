"""Replay stored history ticks through the engine pipeline (D-015).

What the Edge Gateway would have produced live, rebuilt for the 42 simulated days: for every
machine, its 30 s ticks run through `MachinePipeline` in time order (one pipeline per machine,
kept across days), with the site's dispatch log and task list. Outputs, under `data/history/`:
- `intervals.parquet` — interval records (the brief's columns + extensions), timestamps in UTC
- `events.parquet` — alerts, idle segments, risk band changes (deterministic uuid7 ids)
- `idle_segments.parquet` — one row per classified idle segment (flat, for evaluation)
Reads only ticks, tasks, machines and the dispatch log — never the `truth/` folder.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig, load_config
from shiftmate.engines.dispatch_view import DispatchLogEntry, DispatchView
from shiftmate.engines.pipeline import MachinePipeline, TaskInfo
from shiftmate.schema.reference import Machine
from shiftmate.util.ids import uuid7_from

log = logging.getLogger(__name__)


def _to_utc(ts: Any) -> datetime:
    return pd.Timestamp(ts).tz_convert("UTC").to_pydatetime()


def replay_site(
    cfg: ShiftMateConfig, history_dir: Path, site_id: str, seed: int = 7
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    site = cfg.sites[site_id]
    # tick period of the stored history (written by the generator)
    dt = float(json.loads((history_dir / "manifest.json").read_text())["tick_seconds"])
    site_index = sorted(cfg.sites).index(site_id)
    machines = pd.read_parquet(history_dir / "machines.parquet")
    machines = machines[machines.site_id == site_id]
    tasks = pd.read_parquet(history_dir / "tasks.parquet")
    tasks = tasks[tasks.site_id == site_id]
    task_info = {r.task_id: TaskInfo(r.task_id, r.task_type, r.zone_id) for r in tasks.itertuples()}
    dispatch_df = pd.read_parquet(history_dir / "dispatch_log.parquet")
    dispatch_df = dispatch_df[dispatch_df.site_id == site_id]
    entries = [
        DispatchLogEntry(pd.Timestamp(r.ts).to_pydatetime(), r.zone_id, r.truck_id, r.event)
        for r in dispatch_df.itertuples()
    ]

    pipelines: dict[str, MachinePipeline] = {}
    rngs: dict[str, np.random.Generator] = {}
    for i, row in enumerate(machines.to_dict("records")):
        machine = Machine.model_validate(row)
        view = DispatchView(cfg.idle_rules.params.dispatch_presence_timeout_min)
        view.add(entries)
        pipelines[machine.machine_id] = MachinePipeline(
            cfg, machine, site, task_info, view, with_alert_policy=False
        )
        rngs[machine.machine_id] = np.random.default_rng(
            np.random.SeedSequence([seed, 77, site_index, i])
        )

    intervals: list[dict[str, Any]] = []
    events: list[dict[str, Any]] = []
    segments: list[dict[str, Any]] = []
    tick_root = history_dir / "ticks_30s" / f"site_id={site_id}"
    for day_dir in sorted(tick_root.iterdir()):
        ticks = pd.read_parquet(day_dir / "part-0.parquet")
        ticks = ticks.sort_values(["machine_id", "ts"], kind="stable")
        for machine_id, g in ticks.groupby("machine_id", sort=True):
            pipe = pipelines[machine_id]
            rows = g.to_dict("records")
            for tick in rows:
                tick["ts"] = pd.Timestamp(tick["ts"]).to_pydatetime()
                for k, v in list(tick.items()):
                    if isinstance(v, float) and np.isnan(v):
                        tick[k] = None
                out = pipe.step(tick, dt, proximity_age_s=0.0)
                for rec in out.intervals:
                    intervals.append(rec.model_dump())
                for ev in out.events:
                    events.append(_event_row(ev, pipe, tick, rngs[machine_id]))
                if out.idle.closed is not None:
                    segments.append(_segment_row(out.idle.closed, pipe, tick))
            end = rows[-1]["ts"] + pd.Timedelta(seconds=dt).to_pytimedelta()
            recs, evs = pipe.finish(end)
            intervals.extend(r.model_dump() for r in recs)
            for ev in evs:
                events.append(_event_row(ev, pipe, rows[-1], rngs[machine_id]))
                if ev["type"] == "idle_segment":
                    segments.append(_segment_from_event(ev, pipe, rows[-1]))
        log.info("replayed %s %s", site_id, day_dir.name)
    return pd.DataFrame(intervals), pd.DataFrame(events), pd.DataFrame(segments)


def _event_row(ev: dict[str, Any], pipe: MachinePipeline, tick: dict, rng) -> dict[str, Any]:
    ts = ev["ts"]
    return {
        "event_id": uuid7_from(ts, rng),
        "ts": _to_utc(ts),
        "machine_id": pipe.machine.machine_id,
        "operator_id": tick.get("operator_id"),
        "site_id": pipe.site.site_id,
        "type": ev["type"],
        "priority": ev["priority"],
        "code": ev["code"],
        "payload": json.dumps(ev["payload"], default=str),
        "shared_with_supervisor": bool(ev["shared_with_supervisor"]),
        "synced": False,
    }


def _segment_row(result, pipe: MachinePipeline, tick: dict) -> dict[str, Any]:
    return {
        "machine_id": pipe.machine.machine_id,
        "site_id": pipe.site.site_id,
        "operator_id": tick.get("operator_id"),
        "sensor_tier": pipe.tier.value,
        "machine_type": pipe.machine.machine_type.value,
        "start": _to_utc(result.start),
        "end": _to_utc(result.end),
        "duration_s": result.duration_s,
        "reason": result.reason.value,
        "confidence": result.confidence,
        "evidence": ",".join(result.evidence),
        "fuel_l": round(result.fuel_l, 3),
    }


def _segment_from_event(ev: dict[str, Any], pipe: MachinePipeline, tick: dict) -> dict[str, Any]:
    p = ev["payload"]
    return {
        "machine_id": pipe.machine.machine_id,
        "site_id": pipe.site.site_id,
        "operator_id": tick.get("operator_id"),
        "sensor_tier": pipe.tier.value,
        "machine_type": pipe.machine.machine_type.value,
        "start": _to_utc(p["start"]),
        "end": _to_utc(p["end"]),
        "duration_s": p["duration_s"],
        "reason": p["reason"],
        "confidence": p["confidence"],
        "evidence": ",".join(p["evidence"]),
        "fuel_l": p["fuel_l"],
    }


def _job(args: tuple) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    config_dir, history_dir, site_id, seed = args
    return replay_site(load_config(config_dir), history_dir, site_id, seed)


def replay_history(
    history_dir: Path,
    config_dir: Path | None = None,
    sites: list[str] | None = None,
    workers: int = 4,
    seed: int = 7,
) -> dict[str, int]:
    cfg = load_config(config_dir)
    site_ids = sites or sorted(
        p.name.split("=", 1)[1] for p in (history_dir / "ticks_30s").iterdir() if p.is_dir()
    )
    jobs = [(config_dir, history_dir, s, seed) for s in site_ids]
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            results = list(pool.map(_job, jobs))
    else:
        results = [replay_site(cfg, history_dir, s, seed) for s in site_ids]
    intervals = pd.concat([r[0] for r in results], ignore_index=True)
    events = pd.concat([r[1] for r in results], ignore_index=True)
    segments = pd.concat([r[2] for r in results], ignore_index=True)
    for col in ("timestamp", "interval_start"):
        intervals[col] = pd.to_datetime(intervals[col], utc=True)
    intervals = intervals.sort_values(["machine_id", "timestamp"], kind="stable")
    events = events.sort_values(["ts", "machine_id", "event_id"], kind="stable")
    intervals.to_parquet(history_dir / "intervals.parquet", index=False)
    events.to_parquet(history_dir / "events.parquet", index=False)
    segments.to_parquet(history_dir / "idle_segments.parquet", index=False)
    _append_summary(history_dir, intervals, events, segments)
    return {"intervals": len(intervals), "events": len(events), "idle_segments": len(segments)}


def _append_summary(
    history_dir: Path, intervals: pd.DataFrame, events: pd.DataFrame, segments: pd.DataFrame
) -> None:
    """Add what the engines produced to SUMMARY.md (predictions, not ground truth)."""
    path = history_dir / "SUMMARY.md"
    if not path.exists():
        return
    text = path.read_text(encoding="utf-8").split("\n## Engine replay")[0].rstrip()
    alerts = events[events.type == "alert"]
    lines = [
        "",
        "## Engine replay (what the edge engines produced from the ticks)",
        "",
        f"Intervals: {len(intervals):,} · events: {len(events):,} · "
        f"idle segments: {len(segments):,} · intervals with a safety alert: "
        f"{(intervals.safety_alert_triggered == 'Yes').mean():.1%}",
        "",
        "| Predicted idle reason | Segments |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in segments["reason"].value_counts().items()],
        "",
        "| Alert rule | Raised |",
        "|---|---|",
        *[f"| {k} | {v} |" for k, v in alerts["code"].value_counts().items()],
        "",
    ]
    path.write_text(text + "\n" + "\n".join(lines), encoding="utf-8")
