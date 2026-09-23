"""Fleet-learned patterns (TRD §6.7; PRD F-FLT-05).

Interpretable multipliers learned across all machines from completed tasks, e.g. "across 58
machines, wet ground adds about 17 % to trenching". For each task type we take the median of
actual ÷ expected minutes in each condition and compare it with the same task type in the
reference condition (dry or rocky ground; the lowest heat band of the risk model). Counts and
the number of distinct machines are kept, and a pattern needs at least 3 machines.

Uses history days 1–35 only (train + validation), never the test days (D-019).
Only task summaries are used — no raw ticks, no personal details (P-05).
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from shiftmate.config_loader import ShiftMateConfig

MIN_COUNT = 10  # smallest group of tasks reported as a pattern
MIN_MACHINES = 3  # a "fleet" pattern must come from at least this many machines


def heat_bands(cfg: ShiftMateConfig) -> list[tuple[float, float, str]]:
    """Heat bands from the risk model (so patterns and risk use the same boundaries)."""
    edges = [b.lt for b in cfg.risk_model.components.heat_index_c if b.lt is not None]
    bands, lo = [], float("-inf")
    for hi in edges:
        name = f"below {hi:g} °C" if lo == float("-inf") else f"{lo:g}–{hi:g} °C"
        bands.append((lo, hi, name))
        lo = hi
    bands.append((lo, float("inf"), f"{lo:g} °C and above"))
    return bands


def heat_band(value: float, bands: list[tuple[float, float, str]]) -> str:
    for lo, hi, name in bands:
        if lo <= value < hi:
            return name
    return bands[-1][2]


def fleet_patterns(cfg: ShiftMateConfig, tasks: pd.DataFrame) -> list[dict[str, Any]]:
    """`tasks`: the estimation dataset (done tasks with `ratio`, conditions and `day_index`)."""
    s = cfg.estimation.split_days
    df = tasks[(tasks.status == "done") & (tasks.day_index <= s.validation[1])].copy()
    bands = heat_bands(cfg)
    df["heat_band"] = df["heat_index_c"].map(lambda v: heat_band(v, bands))
    out: list[dict[str, Any]] = []
    for dimension, reference in (
        ("ground_condition", ("dry", "rocky")),
        ("heat_band", (bands[0][2],)),
    ):
        for task_type, g in df.groupby("task_type"):
            ref = g[g[dimension].isin(reference)]
            if len(ref) < MIN_COUNT:
                continue
            base = float(ref["ratio"].median())
            for value, h in g.groupby(dimension):
                if (
                    value in reference
                    or len(h) < MIN_COUNT
                    or h["machine_id"].nunique() < MIN_MACHINES
                ):
                    continue
                ratio = float(h["ratio"].median())
                out.append(
                    {
                        "dimension": dimension,
                        "task_type": task_type,
                        "condition": value,
                        "multiplier": round(ratio / base, 3),
                        "change_pct": round((ratio / base - 1) * 100, 1),
                        "tasks": int(len(h)),
                        "machines": int(h["machine_id"].nunique()),
                        "reference": "/".join(reference),
                    }
                )
    out.sort(key=lambda r: (-abs(r["change_pct"]), r["task_type"]))
    return out
