"""Scale results and the 1.6 million machine projection (TRD §7.6, PRD F-FLT-07).

`shiftmate sim scale` and `shiftmate bench runtime` write their measurements to
`data/fleet/scale.json`; `/scale/stats` and the `EVAL.md` scale section read them from there.

The projection is linear and says so (golden rule 11: a projection is labelled, never shown as a
measurement). Per-machine footprint comes from the runtime benchmark when it has been run (full
`MachineRuntime`s producing real uploads), otherwise from the scale run:

    uplink bytes per day   = bytes per machine per hour × hours_per_day × machines
    records per second     = records per machine per hour × hours_per_day × machines / 86 400
    ingest nodes needed    = records per second ÷ the ingest rate measured in the scale run

`hours_per_day` (fleet.yaml) is 24, an upper bound: real machines work shifts.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.schema.fleet import BenchResult, Projection, ScaleRun


def read_scale_file(path: Path) -> tuple[ScaleRun | None, BenchResult | None]:
    if not path.exists():
        return None, None
    data = json.loads(path.read_text(encoding="utf-8"))
    run = ScaleRun(**data["run"]) if data.get("run") else None
    bench = BenchResult(**data["bench"]) if data.get("bench") else None
    return run, bench


def write_scale_file(
    path: Path, run: ScaleRun | None = None, bench: BenchResult | None = None
) -> None:
    """Update one part of the results file, keeping the other."""
    data: dict[str, Any] = {}
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
    if run is not None:
        data["run"] = run.model_dump(mode="json")
    if bench is not None:
        data["bench"] = bench.model_dump(mode="json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def projection(
    cfg: ShiftMateConfig, run: ScaleRun | None, bench: BenchResult | None
) -> Projection | None:
    s = cfg.fleet.scale
    if bench is not None:
        bytes_h = bench.upload_bytes_per_machine_per_hour
        records_h = bench.records_per_machine_per_hour
        basis = f"runtime benchmark ({bench.machines} full machine runtimes)"
    elif run is not None:
        bytes_h = run.bytes_per_machine_per_hour
        records_h = run.records_per_machine_per_hour
        basis = f"scale run ({run.machines:,} synthetic machines)"
    else:
        return None
    n = s.projection_machines
    per_day_bytes = bytes_h * s.hours_per_day * n
    per_day_records = records_h * s.hours_per_day * n
    per_s = per_day_records / 86_400
    return Projection(
        machines=n,
        basis=basis,
        hours_per_day=s.hours_per_day,
        uplink_bytes_per_day=round(per_day_bytes),
        uplink_gb_per_day=round(per_day_bytes / 1e9, 2),
        records_per_day=round(per_day_records),
        records_per_s=round(per_s, 1),
        ingest_nodes_at_measured_rate=round(per_s / run.records_per_s, 2)
        if run is not None and run.records_per_s
        else None,
    )


def eval_section(cfg: ShiftMateConfig, run: ScaleRun | None, bench: BenchResult | None) -> str:
    """Markdown for the `scale` section of docs/EVAL.md."""
    lines = ["## Scale (F-FLT-07)", ""]
    if run is None and bench is None:
        lines.append("Not run yet: `shiftmate sim scale` and `shiftmate bench runtime`.")
        return "\n".join(lines)
    if run is not None:
        lines += [
            f"**Scale run** (`shiftmate sim scale`, {run.finished_at:%Y-%m-%d}): "
            f"{run.machines:,} synthetic machines, {run.sim_minutes} simulated minutes, "
            "interval summaries and shared events resampled from the simulated history, posted "
            "to the Fleet Service in batches of "
            f"{cfg.fleet.scale.batch_size} by one sequential client on the demo laptop.",
            "",
            "| Measure | Value |",
            "|---|---|",
            f"| Records ingested | {run.records:,} ({run.intervals:,} intervals, "
            f"{run.events:,} events) in {run.requests:,} requests |",
            f"| Ingest throughput | {run.records_per_s:,.0f} records/s "
            "(time inside ingest requests) |",
            f"| Request latency per batch | p50 {run.request_ms_p50:.0f} ms, "
            f"p95 {run.request_ms_p95:.0f} ms |",
            f"| Wall time | {run.seconds:.1f} s |",
            f"| Upload per machine | {run.bytes_per_machine_per_hour / 1000:.1f} kB/h, "
            f"{run.records_per_machine_per_hour:.1f} records/h |",
            "",
        ]
    if bench is not None:
        lines += [
            f"**Runtime benchmark** (`shiftmate bench runtime`, {bench.finished_at:%Y-%m-%d}): "
            f"{bench.machines} full machine runtimes (all engines), {bench.sim_minutes} simulated "
            f"minutes at 1 s ticks ({bench.ticks:,} runtime steps), on the demo laptop.",
            "",
            "| Measure | Value |",
            "|---|---|",
            f"| CPU per machine per tick | mean {bench.cpu_ms_per_tick_mean:.3f} ms, "
            f"p95 {bench.cpu_ms_per_tick_p95:.3f} ms |",
            f"| Memory per machine runtime | {bench.memory_mb_per_machine:.2f} MB "
            "(Python allocations over the first minute; a lower bound) |",
            f"| Upload per machine | {bench.upload_bytes_per_machine_per_hour / 1000:.1f} kB/h, "
            f"{bench.records_per_machine_per_hour:.1f} records/h |",
            "",
        ]
    p = projection(cfg, run, bench)
    if p is not None:
        lines += [
            f"**Projection to {p.machines:,} machines — a linear projection, not a "
            f"measurement.** Basis: {p.basis}; {p.hours_per_day:g} reporting hours a day "
            "(upper bound).",
            "",
            "| Projected | Value |",
            "|---|---|",
            f"| Uplink | {p.uplink_gb_per_day:,.1f} GB/day |",
            f"| Records | {p.records_per_day:,.0f}/day ≈ {p.records_per_s:,.0f}/s |",
        ]
        if p.ingest_nodes_at_measured_rate is not None:
            lines.append(
                f"| Ingest capacity | ≈ {p.ingest_nodes_at_measured_rate:,.1f}× the single "
                "laptop process measured above |"
            )
    return "\n".join(lines)
