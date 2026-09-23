"""Scale mode: thousands of synthetic machines streaming summaries to the Fleet Service (TRD §7.6).

`shiftmate sim scale --machines 10000 --sim-minutes 60 --speed max`

A lightweight statistical generator, with no per-tick physics: each synthetic machine copies a
stretch of real interval summaries (and the shared events in it) from a machine of the simulated
history, re-labelled with its own ids and moved to "now". Resampling keeps the machine type,
sensor tier and site mix of the history fleet (TRD §7.1) and gives realistic record sizes and
event rates without inventing any numbers.

Records are sent in time order — every machine's interval for 07:15, then 07:30, … — in batches
of `fleet.yaml → scale.batch_size` through the real ingest endpoints, exactly as edges would send
them. At `--speed max` nothing waits; at `--speed 60` one simulated hour takes one real minute.
The run measures ingest throughput (records per second of time spent inside ingest requests, one
client sending sequentially), request latency and bytes per machine per hour.

Synthetic machines are tagged `source="scale"` and belong to synthetic sites (`SCALE-<country>`),
so they never mix with the real sites' supervisor views.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Protocol

import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.fleet.store import SCALE_SOURCE, SHAREABLE_TYPES
from shiftmate.schema.fleet import ScaleRun

NAMESPACE = uuid.UUID("5c0a1e00-0000-4000-8000-000000000000")


class PostClient(Protocol):
    def post(self, url: str, **kwargs: Any) -> Any: ...


@dataclass
class Pool:
    """Template summaries to resample: the history's intervals and shared events."""

    intervals: pd.DataFrame
    events: pd.DataFrame

    @classmethod
    def from_history(cls, history_dir: Path) -> Pool:
        iv_path, ev_path = history_dir / "intervals.parquet", history_dir / "events.parquet"
        if not iv_path.exists():
            raise FileNotFoundError(
                f"{iv_path} not found: run `shiftmate sim generate` first (scale mode resamples it)"
            )
        iv = pd.read_parquet(iv_path)
        ev = pd.read_parquet(ev_path) if ev_path.exists() else pd.DataFrame()
        if len(ev):
            ev = ev[ev.shared_with_supervisor | ev.type.isin(SHAREABLE_TYPES)]
        return cls(iv, ev)


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """JSON-ready dicts (ISO timestamps, NaN → null), as an edge would send them."""
    return json.loads(df.to_json(orient="records", date_format="iso", date_unit="s"))


def synth_steps(
    cfg: ShiftMateConfig,
    pool: Pool,
    machines: int,
    sim_minutes: int,
    start: datetime,
    seed: int = 7,
) -> Iterator[tuple[datetime, list[dict[str, Any]], list[dict[str, Any]]]]:
    """Yield (interval end, interval records, event records) for each interval step."""
    step = cfg.fleet.scale.interval_minutes
    n_steps = max(1, sim_minutes // step)
    rng = np.random.default_rng(np.random.SeedSequence([seed, 7_600]))
    iv = pool.intervals.sort_values(["machine_id", "timestamp"]).reset_index(drop=True)
    by_machine = {m: g.index.to_numpy() for m, g in iv.groupby("machine_id")}
    templates = sorted(by_machine)
    countries = {sid: s.country for sid, s in cfg.sites.items()}
    ev = pool.events
    ev_by_machine: dict[str, tuple[pd.DataFrame, np.ndarray]] = {}
    if len(ev):
        ev = ev.assign(ts=pd.to_datetime(ev.ts, utc=True)).sort_values("ts")
        for m, g in ev.groupby("machine_id"):
            ev_by_machine[m] = (g, g.ts.to_numpy(dtype="datetime64[ns]"))

    plan = []  # per synthetic machine: (id, site, template rows, time shift)
    for i in range(machines):
        template = templates[int(rng.integers(len(templates)))]
        rows = by_machine[template]
        first = int(rng.integers(max(1, len(rows) - n_steps)))
        chosen = rows[first : first + n_steps]
        t0 = pd.Timestamp(iv.at[chosen[0], "timestamp"])
        shift = pd.Timestamp(start) + pd.Timedelta(minutes=step) - t0.tz_convert(UTC)
        site = f"SCALE-{countries.get(str(iv.at[chosen[0], 'site_id']), 'XX')}"
        plan.append((f"SX{i + 1:05d}", site, template, chosen, shift))

    for k in range(n_steps):
        end = start + timedelta(minutes=step * (k + 1))
        rows = [
            (mid, site, tmpl, chosen[k], shift)
            for mid, site, tmpl, chosen, shift in plan
            if k < len(chosen)
        ]
        frame = iv.loc[[r[3] for r in rows]].copy()
        orig_end = frame["timestamp"]
        frame["machine_id"] = [r[0] for r in rows]
        frame["site_id"] = [r[1] for r in rows]
        frame["operator_id"] = [f"SXOP{r[0][2:]}" for r in rows]
        shifts = pd.Series(pd.to_timedelta([r[4] for r in rows]), index=frame.index)
        frame["timestamp"] = pd.to_datetime(orig_end, utc=True) + shifts
        frame["interval_start"] = pd.to_datetime(frame["interval_start"], utc=True) + shifts
        frame["record_id"] = frame.machine_id + "|" + frame["timestamp"].map(pd.Timestamp.isoformat)
        frame["task_id"] = None
        intervals = _records(frame)

        events = []
        for (mid, site, tmpl, _row, shift), s_end in zip(rows, orig_end, strict=True):
            found = ev_by_machine.get(tmpl)
            if found is None:
                continue
            g, times = found
            s_end = pd.Timestamp(s_end).tz_convert(UTC)
            s_start = s_end - pd.Timedelta(minutes=step)
            lo = np.searchsorted(times, s_start.tz_localize(None).to_datetime64(), side="right")
            hi = np.searchsorted(times, s_end.tz_localize(None).to_datetime64(), side="right")
            if lo == hi:
                continue
            hit = g.iloc[lo:hi].copy()
            hit["ts"] = hit.ts + shift
            hit["event_id"] = [str(uuid.uuid5(NAMESPACE, f"{mid}|{e}")) for e in hit.event_id]
            hit["machine_id"] = mid
            hit["site_id"] = site
            hit["operator_id"] = f"SXOP{mid[2:]}"
            events.extend(_records(hit.drop(columns=["synced"], errors="ignore")))
        yield end, intervals, events


def run_scale(
    cfg: ShiftMateConfig,
    client: PostClient,
    pool: Pool,
    machines: int,
    sim_minutes: int,
    speed: str = "max",
    start: datetime | None = None,
    seed: int = 7,
    progress: Any = None,
) -> ScaleRun:
    """Stream the synthetic fleet to the Fleet Service and measure it."""
    batch = cfg.fleet.scale.batch_size
    step_s = cfg.fleet.scale.interval_minutes * 60
    pace = None if speed == "max" else float(speed)
    start = start or datetime.now(UTC).replace(second=0, microsecond=0)
    latencies: list[float] = []
    n_iv = n_ev = requests = sent = 0
    began = time.perf_counter()
    for k, (end, intervals, events) in enumerate(
        synth_steps(cfg, pool, machines, sim_minutes, start, seed)
    ):
        for kind, records in (("intervals", intervals), ("events", events)):
            for i in range(0, len(records), batch):
                body = json.dumps({"source": SCALE_SOURCE, "records": records[i : i + batch]})
                t = time.perf_counter()
                r = client.post(
                    f"/ingest/{kind}",
                    content=body,
                    headers={"content-type": "application/json"},
                )
                latencies.append((time.perf_counter() - t) * 1000)
                if r.status_code >= 300:
                    raise RuntimeError(f"fleet replied {r.status_code}: {r.text[:200]}")
                requests += 1
                sent += len(body.encode())
        n_iv += len(intervals)
        n_ev += len(events)
        if progress:
            progress(k + 1, end, n_iv + n_ev)
        if pace:  # hold real time to sim time / speed
            due = began + (k + 1) * step_s / pace
            time.sleep(max(0.0, due - time.perf_counter()))
    seconds = time.perf_counter() - began
    in_requests = sum(latencies) / 1000  # ingest throughput excludes generating the records
    hours = sim_minutes / 60
    records = n_iv + n_ev
    return ScaleRun(
        machines=machines,
        sim_minutes=sim_minutes,
        records=records,
        intervals=n_iv,
        events=n_ev,
        requests=requests,
        seconds=round(seconds, 2),
        records_per_s=round(records / in_requests, 1) if in_requests else 0.0,
        request_ms_p50=round(float(np.percentile(latencies, 50)), 1) if latencies else 0.0,
        request_ms_p95=round(float(np.percentile(latencies, 95)), 1) if latencies else 0.0,
        bytes_sent=sent,
        bytes_per_machine_per_hour=round(sent / machines / hours, 1),
        records_per_machine_per_hour=round(records / machines / hours, 2),
        finished_at=datetime.now(UTC),
    )
