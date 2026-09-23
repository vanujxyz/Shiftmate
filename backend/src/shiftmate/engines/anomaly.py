"""Unusual-behaviour features, personal baselines and explanations (TRD §6.6; PRD F-INS-04/05).

Features per interval (missing ones are dropped for that machine's tier):
idle ratio, fuel per load cycle, fuel per engine hour, load cycles per working hour, seconds
unbelted while working, top travel speed, close calls (danger + critical), habit idle minutes,
cab-empty idle minutes, average rpm.

Personal baseline ("what is normal for me"): for each feature, the median and MAD over the
trailing 14 days of the same (operator, machine type, task type). With fewer than 20 intervals
there, fall back to (machine type, task type, site). The robust z-score is
    z = (x − median) / (1.4826 × MAD + ε).
The 14-day window ends at the start of the interval's day, so a day never judges itself.

Decision: an interval is unusual if its IsolationForest score is in the top 5 % for its
(machine type, tier) group AND at least one feature is ≥ 3 robust z-scores in its "worse"
direction — OR any P1 safety rule fired in it (hard rule). The IsolationForest is trained in
`shiftmate ml train` (milestone 6); this module provides features, baselines and explanations.

Explanation: up to three features with the largest z in the worse direction, each with the
interval's value and the operator's usual value (median), for a sentence like
"Fuel per truck was 2.1 L, your usual is 0.7 L".
Pure functions over data passed in; no I/O.
"""

from __future__ import annotations

import math
import warnings
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

import numpy as np
import pandas as pd

from shiftmate.schema.config import AnomalyConfig

# (z-scores are clipped to ±10 before the IsolationForest: when a behaviour is normally absent,
# MAD = 0 and the raw z is enormous; clipping keeps one feature from swamping the others, D-050)

MIN_WORKING_MIN_FOR_RATE = 5.0  # below this, loads per working hour is not meaningful


def interval_features(r: Mapping[str, object]) -> dict[str, float | None]:
    """Feature values for one interval record (dict or pandas row). None = not available."""

    def num(name: str) -> float | None:
        v = r.get(name)
        if v is None or (isinstance(v, float) and math.isnan(v)):
            return None
        return float(v)  # type: ignore[arg-type]

    engine_on = num("engine_on_min") or 0.0
    working = num("working_min") or 0.0
    cycles = num("load_cycles") or 0.0
    fuel = num("fuel_used_l") or 0.0
    danger = num("proximity_danger_count")
    critical = num("proximity_critical_count")
    close_calls = None
    if num("min_proximity_m") is not None or danger or critical:
        close_calls = (danger or 0.0) + (critical or 0.0)
    return {
        "idle_ratio": (num("idling_time_min") or 0.0) / engine_on if engine_on > 0 else None,
        "fuel_per_load_cycle_l": fuel / cycles if cycles > 0 else None,
        "fuel_lph": fuel / (engine_on / 60) if engine_on >= 1 else None,
        "load_cycles_per_working_h": cycles / (working / 60)
        if working >= MIN_WORKING_MIN_FOR_RATE
        else None,
        "seatbelt_unfastened_working_s": num("seatbelt_unfastened_working_s"),
        "max_travel_speed_kmh": num("max_travel_speed_kmh"),
        "proximity_close_count": close_calls,
        "idle_habit_min": num("idle_habit_min"),
        "idle_unattended_min": num("idle_unattended_min")
        if r.get("seat_occupied_min") is not None
        else None,
        "avg_engine_rpm": num("avg_engine_rpm"),
    }


def features_frame(intervals: pd.DataFrame) -> pd.DataFrame:
    rows = [interval_features(r) for r in intervals.to_dict("records")]
    return pd.DataFrame(rows, index=intervals.index, dtype="float64")


@dataclass(frozen=True)
class BaselineStat:
    median: float
    mad: float
    n: int


def robust_z(x: float, stat: BaselineStat, cfg: AnomalyConfig) -> float:
    return (x - stat.median) / (cfg.mad_scale * stat.mad + cfg.epsilon)


def _stats(values: np.ndarray) -> BaselineStat | None:
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return None
    med = float(np.median(values))
    return BaselineStat(med, float(np.median(np.abs(values - med))), len(values))


class Baselines:
    """Personal and group baselines from past intervals (trailing window, per day)."""

    PERSONAL = ("operator_id", "machine_type", "task_type")
    GROUP = ("machine_type", "task_type", "site_id")

    def __init__(self, history: pd.DataFrame, cfg: AnomalyConfig) -> None:
        """`history`: interval records with feature columns and a `day` (date) column."""
        self.cfg = cfg
        self.history = history
        self._cache: dict[tuple, dict[str, BaselineStat | None]] = {}

    def _window(self, day: pd.Timestamp) -> pd.DataFrame:
        lo = day - pd.Timedelta(days=self.cfg.baseline_days)
        h = self.history
        return h[(h["day"] >= lo) & (h["day"] < day)]

    def stats_for(
        self, row: Mapping[str, object], features: Iterable[str]
    ) -> tuple[dict[str, BaselineStat | None], str]:
        """Baseline per feature for this interval and which level was used."""
        day = pd.Timestamp(row["day"])  # type: ignore[arg-type]
        personal_key = ("p", day, *(row.get(k) for k in self.PERSONAL))
        group_key = ("g", day, *(row.get(k) for k in self.GROUP))
        for key, cols, level in (
            (personal_key, self.PERSONAL, "personal"),
            (group_key, self.GROUP, "group"),
        ):
            if key not in self._cache:
                w = self._window(day)
                mask = np.ones(len(w), dtype=bool)
                for col, value in zip(cols, key[2:], strict=True):
                    mask &= (w[col] == value).to_numpy()
                sel = w[mask]
                if len(sel) < self.cfg.baseline_min_intervals:
                    self._cache[key] = {}
                else:
                    self._cache[key] = {
                        f: _stats(sel[f].to_numpy(dtype="float64")) for f in features
                    }
            if self._cache[key]:
                return self._cache[key], level
        return {}, "none"


def z_scores(
    values: Mapping[str, float | None],
    stats: Mapping[str, BaselineStat | None],
    cfg: AnomalyConfig,
) -> dict[str, float]:
    out: dict[str, float] = {}
    for feature in cfg.features:
        x = values.get(feature.code)
        stat = stats.get(feature.code)
        if x is None or stat is None or (isinstance(x, float) and math.isnan(x)):
            continue
        out[feature.code] = robust_z(x, stat, cfg)
    return out


def worse_z(z: Mapping[str, float], cfg: AnomalyConfig) -> dict[str, float]:
    """z-scores oriented so that positive always means 'worse than usual'."""
    direction = {f.code: 1.0 if f.higher_is_worse else -1.0 for f in cfg.features}
    return {k: v * direction[k] for k, v in z.items()}


def explain(
    values: Mapping[str, float | None],
    z: Mapping[str, float],
    stats: Mapping[str, BaselineStat | None],
    cfg: AnomalyConfig,
) -> list[dict[str, object]]:
    """Up to `max_explanations` features that are most worse-than-usual (z ≥ threshold)."""
    keys = {f.code: f.message_key for f in cfg.features}
    worst = sorted(worse_z(z, cfg).items(), key=lambda kv: -kv[1])
    out = []
    for code, wz in worst:
        if wz < cfg.z_threshold or len(out) >= cfg.max_explanations:
            break
        stat = stats.get(code)
        out.append(
            {
                "feature": code,
                "message_key": keys[code],
                "value": values.get(code),
                "usual": stat.median if stat else None,
                "z": round(wz, 2),
            }
        )
    return out


def baseline_z_frame(df: pd.DataFrame, cfg: AnomalyConfig) -> pd.DataFrame:
    """Robust z-scores (raw sign) for every interval in `df`, vectorised.

    `df` needs the feature columns plus `day`, `operator_id`, `machine_type`, `task_type` and
    `site_id`. For each interval the baseline is the trailing `baseline_days` window of its
    personal group, falling back to its site group when the personal group has too few rows.
    Returns one column per feature, plus `baseline_level` (personal / group / none) and, per
    feature, the baseline median as `<feature>__usual`.
    """
    codes = cfg.codes()
    n = len(df)
    out = np.full((n, len(codes)), np.nan)
    usual = np.full((n, len(codes)), np.nan)
    level = np.full(n, "none", dtype=object)
    days = pd.to_datetime(df["day"]).to_numpy()
    window = np.timedelta64(cfg.baseline_days, "D")
    values = df[codes].to_numpy(dtype="float64")
    for level_name, keys in (("group", Baselines.GROUP), ("personal", Baselines.PERSONAL)):
        # group first, then personal overwrites where personal has enough history
        for idx in df.groupby(list(keys), dropna=False, sort=False).indices.values():
            order = idx[np.argsort(days[idx], kind="stable")]
            gdays = days[order]
            for d in np.unique(gdays):
                lo = np.searchsorted(gdays, d - window, side="left")
                hi = np.searchsorted(gdays, d, side="left")
                if hi - lo < cfg.baseline_min_intervals:
                    continue
                past = values[order[lo:hi]]
                with np.errstate(all="ignore"), warnings.catch_warnings():
                    warnings.simplefilter("ignore", RuntimeWarning)  # all-NaN feature columns
                    med = np.nanmedian(past, axis=0)
                    mad = np.nanmedian(np.abs(past - med), axis=0)
                rows = order[gdays == d]
                out[rows] = (values[rows] - med) / (cfg.mad_scale * mad + cfg.epsilon)
                usual[rows] = med
                level[rows] = level_name
    result = pd.DataFrame(out, index=df.index, columns=codes)
    result = pd.concat(
        [result, pd.DataFrame(usual, index=df.index, columns=[f"{c}__usual" for c in codes])],
        axis=1,
    )
    result["baseline_level"] = level
    return result


def worse_z_matrix(z: pd.DataFrame, cfg: AnomalyConfig, clip: float = 10.0) -> pd.DataFrame:
    """Worse-direction z-scores clipped to ±clip; missing features become 0 (neutral)."""
    signs = {f.code: 1.0 if f.higher_is_worse else -1.0 for f in cfg.features}
    m = pd.DataFrame({c: z[c] * signs[c] for c in cfg.codes()}, index=z.index)
    return m.clip(-clip, clip).fillna(0.0)


def is_unusual(
    if_top: bool,
    z: Mapping[str, float],
    p1_fired: bool,
    cfg: AnomalyConfig,
) -> bool:
    """TRD §6.6 decision rule."""
    strong = any(v >= cfg.z_threshold for v in worse_z(z, cfg).values())
    return (if_top and strong) or p1_fired
