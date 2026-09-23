"""Ground-truth access for evaluation (this package is the only reader besides the simulator).

The simulator writes one truth row per tick (D-036). Here those rows are loaded for the test
days and joined to what the engines produced.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd


def test_dates(first_day: date, days: tuple[int, int]) -> list[date]:
    return [first_day + timedelta(days=d - 1) for d in range(days[0], days[1] + 1)]


def load_truth(
    history_dir: Path, dates: list[date], columns: list[str] | None = None
) -> pd.DataFrame:
    root = history_dir / "truth" / "ticks_truth"
    wanted = {d.isoformat() for d in dates}
    frames = []
    for site_dir in sorted(root.iterdir()):
        for day_dir in sorted(site_dir.iterdir()):
            if day_dir.name.split("=", 1)[1] not in wanted:
                continue
            df = pd.read_parquet(day_dir / "part-0.parquet", columns=columns)
            df["ts"] = pd.to_datetime(df["ts"]).dt.tz_convert("UTC")
            df["site_id"] = site_dir.name.split("=", 1)[1]
            frames.append(df)
    return pd.concat(frames, ignore_index=True)


def assign_to_spans(
    ticks: pd.DataFrame, spans: pd.DataFrame, start: str, end: str, span_id: str
) -> pd.DataFrame:
    """Attach to each tick the span (same machine) with start ≤ ts < end, else NaN."""
    t = ticks.sort_values("ts").reset_index(drop=True)
    s = spans[["machine_id", start, end, span_id]].sort_values(start).reset_index(drop=True)
    merged = pd.merge_asof(
        t, s, left_on="ts", right_on=start, by="machine_id", direction="backward"
    )
    outside = merged["ts"] >= merged[end]
    merged.loc[outside, span_id] = pd.NA
    return merged
