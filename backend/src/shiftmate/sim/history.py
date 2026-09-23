"""History generator: `shiftmate sim generate --days 42 --seed 7` (TRD §7, history mode).

Runs every site day by day at 30 s ticks and writes, under `data/history/`:
- `machines.parquet`, `operators.parquet` (public reference data)
- `tasks.parquet`, `dispatch_log.parquet`, `weather_hourly.parquet`
- `ticks_30s/site_id=<id>/day=<yyyy-mm-dd>/part-0.parquet` (the sensor ticks)
- `truth/ticks_truth/...` and `truth/personalities.parquet` — ground truth, read only by
  `shiftmate.eval` and simulator tests (golden rule 5)
- `fleet.duckdb` (tables for reference data and views over the Parquet files)
- `SUMMARY.md` and `manifest.json` (row counts, label distributions, condition stats, hashes)

Memory stays small: each site-day is written as soon as it is simulated. Sites run in parallel
processes; each site's days run in order because engine hours, positions and weather carry over.
"""

from __future__ import annotations

import hashlib
import json
import logging
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig, load_config
from shiftmate.sim.fleet import Fleet, build_fleet
from shiftmate.sim.site import SiteWorld

log = logging.getLogger(__name__)

TRUTH_FLAGS = [
    "habit_idle",
    "unattended",
    "seatbelt",
    "speed_near_person",
    "fuel_abnormal",
    "low_productivity",
]


@dataclass
class SiteOutput:
    site_id: str
    tasks: pd.DataFrame
    dispatch: pd.DataFrame
    weather: pd.DataFrame
    tick_rows: int
    tick_hash: str
    truth_counts: dict[str, int]
    idle_truth_minutes: dict[str, float]
    idle_truth_segments: dict[str, int]
    shortages: int


def history_dates(end_date: date, days: int) -> list[tuple[int, date]]:
    """(day_index, date) for days 1..N ending at end_date."""
    return [(i, end_date - timedelta(days=days - i)) for i in range(1, days + 1)]


def build_history_fleet(cfg: ShiftMateConfig, seed: int) -> Fleet:
    return build_fleet(cfg, np.random.default_rng(np.random.SeedSequence([seed, 1_000_003])))


def _frame_hash(df: pd.DataFrame) -> str:
    return hashlib.sha256(pd.util.hash_pandas_object(df, index=False).values.tobytes()).hexdigest()


def _segments(truth: pd.DataFrame) -> tuple[dict[str, float], dict[str, int]]:
    """Minutes and segment counts of true idle reasons (contiguous runs per machine)."""
    minutes: dict[str, float] = {}
    counts: dict[str, int] = {}
    for _, g in truth.groupby("machine_id", sort=False):
        reasons = g["idle_reason"].fillna("").to_numpy()
        change = np.r_[True, reasons[1:] != reasons[:-1]]
        for reason, run in zip(
            reasons[change], np.diff(np.r_[np.flatnonzero(change), len(reasons)]), strict=True
        ):
            if reason:
                counts[reason] = counts.get(reason, 0) + 1
                minutes[reason] = minutes.get(reason, 0.0) + float(run)
    return minutes, counts


def simulate_site(
    cfg: ShiftMateConfig,
    fleet: Fleet,
    site_id: str,
    seed: int,
    days: list[tuple[int, date]],
    out_dir: Path | None,
    dt: float,
) -> SiteOutput:
    site = cfg.sites[site_id]
    site_index = cfg.simulator.fleet.site_order.index(site_id)
    world = SiteWorld(cfg, site, fleet, site_index, seed)
    tasks, dispatch, weather_rows = [], [], []
    tick_rows = 0
    hasher = hashlib.sha256()
    truth_counts = dict.fromkeys(TRUTH_FLAGS, 0)
    idle_minutes: dict[str, float] = {}
    idle_segments: dict[str, int] = {}
    shortages = 0
    step_minutes = dt / 60
    for day_index, day in days:
        result = world.run_day(day_index, day, dt)
        ticks = pd.DataFrame(result.ticks)
        truth = pd.DataFrame(result.truth)
        ticks["day_index"] = day_index
        truth["day_index"] = day_index
        tick_rows += len(ticks)
        hasher.update(_frame_hash(ticks).encode())
        hasher.update(_frame_hash(truth).encode())
        for flag in TRUTH_FLAGS:
            truth_counts[flag] += int(truth[flag].sum())
        minutes, segments = _segments(truth)
        for k, v in minutes.items():
            idle_minutes[k] = idle_minutes.get(k, 0.0) + v * step_minutes
        for k, v in segments.items():
            idle_segments[k] = idle_segments.get(k, 0) + v
        shortages += len(result.shortages)
        if out_dir is not None:
            part = f"site_id={site_id}/day={day.isoformat()}"
            tick_dir = out_dir / "ticks_30s" / part
            truth_dir = out_dir / "truth" / "ticks_truth" / part
            tick_dir.mkdir(parents=True, exist_ok=True)
            truth_dir.mkdir(parents=True, exist_ok=True)
            ticks.drop(columns=["site_id"]).to_parquet(tick_dir / "part-0.parquet", index=False)
            truth.to_parquet(truth_dir / "part-0.parquet", index=False)
        for t in result.tasks:
            row = t.model_dump(mode="python")
            cond = row.pop("conditions_at_start") or {}
            row.update({f"start_{k}": v for k, v in cond.items()})
            row["day_index"] = day_index
            tasks.append(row)
        for e in result.dispatch:
            dispatch.append(
                {
                    "ts": e.ts,
                    "true_ts": e.true_ts,
                    "site_id": e.site_id,
                    "zone_id": e.zone_id,
                    "truck_id": e.truck_id,
                    "event": e.event,
                    "day_index": day_index,
                }
            )
        w = result.weather
        for hour in range(24):
            m = hour * 60 + 30
            weather_rows.append(
                {
                    "site_id": site_id,
                    "day": day,
                    "day_index": day_index,
                    "hour": hour,
                    "temp_c": float(w.temp_c[m]),
                    "rh_pct": float(w.rh_pct[m]),
                    "heat_index_c": float(w.heat_index_c[m]),
                    "precip_mm_h": float(w.precip_mm_h[m]),
                    "visibility_m": float(w.visibility_m[m]),
                    "is_night": bool(w.is_night[m]),
                    "ground": str(w.ground[m]),
                }
            )
        log.info("site %s day %s: %d ticks", site_id, day, len(ticks))
    return SiteOutput(
        site_id=site_id,
        tasks=pd.DataFrame(tasks),
        dispatch=pd.DataFrame(dispatch),
        weather=pd.DataFrame(weather_rows),
        tick_rows=tick_rows,
        tick_hash=hasher.hexdigest(),
        truth_counts=truth_counts,
        idle_truth_minutes=idle_minutes,
        idle_truth_segments=idle_segments,
        shortages=shortages,
    )


def _simulate_site_job(args: tuple) -> SiteOutput:
    config_dir, site_id, seed, days, out_dir, dt = args
    cfg = load_config(config_dir)
    fleet = build_history_fleet(cfg, seed)
    return simulate_site(cfg, fleet, site_id, seed, days, out_dir, dt)


def generate_history(
    *,
    days: int,
    seed: int,
    out_dir: Path,
    config_dir: Path | None = None,
    sites: list[str] | None = None,
    workers: int = 4,
) -> dict[str, object]:
    cfg = load_config(config_dir)
    fleet = build_history_fleet(cfg, seed)
    dates = history_dates(cfg.simulator.history.end_date, days)
    site_ids = sites or cfg.simulator.fleet.site_order
    dt = float(cfg.simulator.history.tick_seconds)
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in ("ticks_30s", "truth"):
        target = out_dir / old
        if target.exists():
            import shutil

            shutil.rmtree(target)
    jobs = [(config_dir, s, seed, dates, out_dir, dt) for s in site_ids]
    if workers > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=min(workers, len(jobs))) as pool:
            outputs = list(pool.map(_simulate_site_job, jobs))
    else:
        outputs = [simulate_site(cfg, fleet, s, seed, dates, out_dir, dt) for s in site_ids]

    machines = pd.DataFrame([m.model_dump(mode="json") for m in fleet.machines])
    operators = pd.DataFrame(
        [
            {**o.model_dump(mode="json"), "certifications": ",".join(o.certifications)}
            for o in fleet.operators
        ]
    )
    personalities = pd.DataFrame(
        [{"operator_id": k, **v.model_dump()} for k, v in fleet.personalities.items()]
    )
    tasks = pd.concat([o.tasks for o in outputs], ignore_index=True)
    dispatch = pd.concat([o.dispatch for o in outputs], ignore_index=True)
    weather = pd.concat([o.weather for o in outputs], ignore_index=True)
    machines.to_parquet(out_dir / "machines.parquet", index=False)
    operators.to_parquet(out_dir / "operators.parquet", index=False)
    tasks.to_parquet(out_dir / "tasks.parquet", index=False)
    dispatch.to_parquet(out_dir / "dispatch_log.parquet", index=False)
    weather.to_parquet(out_dir / "weather_hourly.parquet", index=False)
    (out_dir / "truth").mkdir(exist_ok=True)
    personalities.to_parquet(out_dir / "truth" / "personalities.parquet", index=False)
    _write_duckdb(out_dir)

    manifest = {
        "seed": seed,
        "days": days,
        "first_day": dates[0][1].isoformat(),
        "last_day": dates[-1][1].isoformat(),
        "tick_seconds": dt,
        "sites": site_ids,
        "machines": len(machines),
        "operators": len(operators),
        "tick_rows": sum(o.tick_rows for o in outputs),
        "tasks": len(tasks),
        "tasks_done": int((tasks["status"] == "done").sum()) if len(tasks) else 0,
        "dispatch_entries": len(dispatch),
        "site_hashes": {o.site_id: o.tick_hash for o in outputs},
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    _write_summary(out_dir, manifest, outputs, machines, operators, personalities, tasks, weather)
    return manifest


def _write_duckdb(out_dir: Path) -> None:
    db_path = out_dir / "fleet.duckdb"
    if db_path.exists():
        db_path.unlink()
    con = duckdb.connect(str(db_path))
    try:
        for name in ("machines", "operators", "tasks", "dispatch_log", "weather_hourly"):
            path = (out_dir / f"{name}.parquet").as_posix()
            con.execute(f"CREATE TABLE {name} AS SELECT * FROM read_parquet('{path}')")
        ticks = (out_dir / "ticks_30s" / "**" / "*.parquet").as_posix()
        con.execute(
            "CREATE VIEW ticks_30s AS SELECT * FROM "
            f"read_parquet('{ticks}', hive_partitioning=true)"
        )
    finally:
        con.close()


def _pct(n: float, total: float) -> str:
    return f"{100 * n / total:.1f} %" if total else "–"


def _write_summary(
    out_dir, manifest, outputs, machines, operators, personalities, tasks, weather
) -> None:
    lines = [
        "# Simulated history — summary",
        "",
        f"Seed {manifest['seed']} · {manifest['days']} days ({manifest['first_day']} to "
        f"{manifest['last_day']}) · {manifest['tick_seconds']:.0f} s ticks · generated by "
        "`shiftmate sim generate`. Simulated data, not real machines.",
        "",
        "## Row counts",
        "",
        "| Table | Rows |",
        "|---|---|",
        f"| machines | {manifest['machines']} |",
        f"| operators | {manifest['operators']} |",
        f"| ticks_30s | {manifest['tick_rows']:,} |",
        f"| tasks (done) | {manifest['tasks']} ({manifest['tasks_done']}) |",
        f"| dispatch_log | {manifest['dispatch_entries']} |",
        "",
        "## Fleet",
        "",
        "| Site | Excavators | Wheel loaders | Dozers | Basic | Standard | Advanced |",
        "|---|---|---|---|---|---|---|",
    ]
    for site_id, g in machines.groupby("site_id", sort=False):
        t = g["machine_type"].value_counts()
        tier = g["sensor_tier"].value_counts()
        lines.append(
            f"| {site_id} | {t.get('excavator', 0)} | {t.get('wheel_loader', 0)} | "
            f"{t.get('dozer', 0)} | {tier.get('basic', 0)} | {tier.get('standard', 0)} | "
            f"{tier.get('advanced', 0)} |"
        )
    exc = machines[machines.machine_id == "EXC001"].iloc[0]
    whl = machines[machines.machine_id == "WHL014"].iloc[0]
    ravi = operators[operators.operator_id == "OP1001"].iloc[0]
    lines += [
        "",
        f"EXC001: {exc.model}, {exc.model_year}, {exc.sensor_tier}, {exc.site_id}, "
        f"engine hours start {exc.engine_hours_start}. WHL014: {whl.model}, {whl.model_year}, "
        f"{whl.sensor_tier}, {whl.site_id}. OP1001: {ravi['name']}, {ravi.preferred_language}, "
        f"{ravi.experience_years} years.",
        "",
        "Operators with an elevated trait (> 0.6, simulator-only): "
        + ", ".join(
            f"{t} {int((personalities[t] > 0.6).sum())}"
            for t in [
                "idle_habit",
                "seatbelt_skipper",
                "steps_out_engine_on",
                "speeds_near_people",
                "skips_breaks",
            ]
        ),
        "",
        "## Ground truth: idle reasons",
        "",
        "| Reason | Segments | Minutes |",
        "|---|---|---|",
    ]
    idle_min: dict[str, float] = {}
    idle_seg: dict[str, int] = {}
    for o in outputs:
        for k, v in o.idle_truth_minutes.items():
            idle_min[k] = idle_min.get(k, 0) + v
        for k, v in o.idle_truth_segments.items():
            idle_seg[k] = idle_seg.get(k, 0) + v
    for reason in sorted(idle_min, key=lambda r: -idle_min[r]):
        lines.append(f"| {reason} | {idle_seg.get(reason, 0)} | {idle_min[reason]:,.0f} |")
    lines += [
        "",
        "## Ground truth: anomaly ticks",
        "",
        "| Type | Ticks | Share of ticks |",
        "|---|---|---|",
    ]
    total_ticks = manifest["tick_rows"]
    for flag in TRUTH_FLAGS:
        n = sum(o.truth_counts[flag] for o in outputs)
        lines.append(f"| {flag} | {n:,} | {_pct(n, total_ticks)} |")
    lines += [
        "",
        "## Conditions per site (shift hours)",
        "",
        "| Site | Mean heat index °C | Max heat index °C | Min temp °C | Rain hours "
        "| Night share | Ground (share of hours) | Truck shortage windows |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for o in outputs:
        w = weather[(weather.site_id == o.site_id) & weather.hour.between(6, 17)]
        ground = w["ground"].value_counts(normalize=True)
        ground_txt = ", ".join(f"{k} {v:.0%}" for k, v in ground.items())
        lines.append(
            f"| {o.site_id} | {w.heat_index_c.mean():.1f} | {w.heat_index_c.max():.1f} | "
            f"{w.temp_c.min():.1f} | {int((w.precip_mm_h > 0).sum())} | "
            f"{w.is_night.mean():.0%} | {ground_txt} | {o.shortages} |"
        )
    done = tasks[tasks.status == "done"]
    lines += ["", "## Tasks", "", "| Task type | Done | Median minutes |", "|---|---|---|"]
    for tt, g in done.groupby("task_type"):
        lines.append(f"| {tt} | {len(g)} | {g.actual_duration_min.median():.0f} |")
    lines.append("")
    (out_dir / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
