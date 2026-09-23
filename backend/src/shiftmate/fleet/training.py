"""Fleet-side model training: `shiftmate ml train` (TRD §6.6, §6.7; PRD F-FLT-04, F-FLT-05).

Data split by history day (TRD §6.7): train days 1–32, validation 33–35, test 36–42. Nothing is
fitted, tuned or early-stopped on test days; test days are only used by `shiftmate eval`.

Estimation: three LightGBM quantile regressors (0.1 / 0.5 / 0.9) on log(task minutes) with the
features in `estimation.yaml`. `operator_skill_index` is the operator's median of
actual ÷ expected minutes for the same task type over the previous 30 days (1.0 without history),
where expected = planned quantity ÷ the profile's base rate. Early stopping uses the validation
days. Saved to `models/estimation/<version>/` with a manifest (features, categories, metrics).

Anomaly: robust z-scores against personal baselines (engines/anomaly.py), turned "worse is
positive" and clipped, feed one IsolationForest per (machine type, sensor tier) trained on the
training days. The score that marks the top 5 % of training intervals is stored as the threshold.
Also saved: the latest baselines (last 14 days) for the edge to use live.
"""

from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import Any

import joblib
import lightgbm as lgb
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.engines.anomaly import baseline_z_frame, features_frame, worse_z_matrix
from shiftmate.engines.estimation import expected_minutes

log = logging.getLogger(__name__)


# --- shared data loading ----------------------------------------------------------------------


def history_manifest(history_dir: Path) -> dict[str, Any]:
    return json.loads((history_dir / "manifest.json").read_text(encoding="utf-8"))


def day_index_of(dates: pd.Series, first_day: date) -> pd.Series:
    return (pd.to_datetime(dates) - pd.Timestamp(first_day)).dt.days + 1


def load_intervals(cfg: ShiftMateConfig, history_dir: Path) -> pd.DataFrame:
    """Intervals with local `day`, `day_index` and anomaly features added."""
    iv = pd.read_parquet(history_dir / "intervals.parquet")
    first = date.fromisoformat(history_manifest(history_dir)["first_day"])
    tz = {s: cfg.sites[s].timezone for s in iv["site_id"].unique()}
    local = [
        ts.tz_convert(tz[site]).date()
        for ts, site in zip(iv["timestamp"], iv["site_id"], strict=True)
    ]
    iv["day"] = pd.to_datetime(local)
    iv["day_index"] = day_index_of(iv["day"], first)
    feats = features_frame(iv)
    for col in feats.columns:  # some features share a name with an interval column
        iv[col] = feats[col]
    return iv


def split_of(day_index: pd.Series, cfg: ShiftMateConfig) -> pd.Series:
    s = cfg.estimation.split_days
    out = pd.Series("none", index=day_index.index)
    out[day_index.between(*s.train)] = "train"
    out[day_index.between(*s.validation)] = "validation"
    out[day_index.between(*s.test)] = "test"
    return out


# --- estimation --------------------------------------------------------------------------------


def estimation_dataset(cfg: ShiftMateConfig, history_dir: Path) -> pd.DataFrame:
    tasks = pd.read_parquet(history_dir / "tasks.parquet")
    machines = pd.read_parquet(history_dir / "machines.parquet")[
        ["machine_id", "machine_type", "model"]
    ]
    operators = pd.read_parquet(history_dir / "operators.parquet")[
        ["operator_id", "experience_years"]
    ]
    df = tasks.merge(machines, on="machine_id").merge(operators, on="operator_id")
    df = df.rename(columns={"experience_years": "operator_experience_years"})
    df["expected_min"] = [
        expected_minutes(q, cfg.profiles[mt].tasks[tt].base_rate_per_h)
        for q, mt, tt in zip(df.planned_quantity, df.machine_type, df.task_type, strict=True)
    ]
    df["ratio"] = df["actual_duration_min"] / df["expected_min"]
    # operator skill index: trailing 30-day median actual/expected, same task type, done tasks
    window = cfg.estimation.skill_window_days
    df = df.sort_values(["day_index", "task_id"], kind="stable").reset_index(drop=True)
    done = df[df.status == "done"]
    skill = np.ones(len(df))
    groups = {k: g for k, g in done.groupby(["operator_id", "task_type"])}
    for i, r in enumerate(df.itertuples()):
        g = groups.get((r.operator_id, r.task_type))
        if g is None:
            continue
        past = g[(g.day_index < r.day_index) & (g.day_index >= r.day_index - window)]
        if len(past):
            skill[i] = float(past["ratio"].median())
    df["operator_skill_index"] = skill
    df["ground_condition"] = df["start_ground_condition"]
    df["heat_index_c"] = df["start_heat_index_c"]
    df["precipitation_mm_h"] = df["start_precipitation_mm_h"]
    df["is_night"] = df["start_is_night"].astype("float64")
    df["expected_truck_interval_min"] = [
        cfg.sites[s].trucks.dispatch_mean_interval_min
        if cfg.profiles[mt].tasks[tt].truck_dependent
        else 0.0
        for s, mt, tt in zip(df.site_id, df.machine_type, df.task_type, strict=True)
    ]
    tz = {s: cfg.sites[s].timezone for s in df.site_id.unique()}
    df["hour_of_day"] = [
        pd.Timestamp(ts).tz_convert(tz[s]).hour
        for ts, s in zip(df.scheduled_start, df.site_id, strict=True)
    ]
    df["split"] = split_of(df["day_index"], cfg)
    return df


def _frame(
    df: pd.DataFrame, cfg: ShiftMateConfig, categories: dict[str, list[str]]
) -> pd.DataFrame:
    X = pd.DataFrame(index=df.index)
    for f in cfg.estimation.features:
        if f in categories:
            X[f] = pd.Categorical(df[f].astype("object"), categories=categories[f])
        else:
            X[f] = pd.to_numeric(df[f], errors="coerce").astype("float64")
    return X


def train_estimation(
    cfg: ShiftMateConfig, history_dir: Path, models_dir: Path, seed: int
) -> dict[str, Any]:
    df = estimation_dataset(cfg, history_dir)
    done = df[(df.status == "done") & (df.actual_duration_min > 0)]
    train, val = done[done.split == "train"], done[done.split == "validation"]
    categories = {
        f: sorted(str(v) for v in done[f].dropna().unique()) for f in cfg.estimation.categorical
    }
    Xtr, Xva = _frame(train, cfg, categories), _frame(val, cfg, categories)
    ytr, yva = np.log(train.actual_duration_min), np.log(val.actual_duration_min)
    p = cfg.estimation.lightgbm
    manifest_hist = history_manifest(history_dir)
    version = f"est-{manifest_hist['last_day'].replace('-', '')}-s{seed}"
    out_dir = models_dir / "estimation" / version
    out_dir.mkdir(parents=True, exist_ok=True)
    best_iterations = {}
    for alpha in cfg.estimation.quantiles:
        params = {
            "objective": "quantile",
            "alpha": alpha,
            "metric": "quantile",
            "num_leaves": p.num_leaves,
            "learning_rate": p.learning_rate,
            "min_data_in_leaf": p.min_data_in_leaf,
            "seed": seed,
            "deterministic": True,
            "force_row_wise": True,
            "num_threads": 1,
            "verbose": -1,
        }
        booster = lgb.train(
            params,
            lgb.Dataset(Xtr, ytr, categorical_feature=list(categories)),
            num_boost_round=p.n_estimators,
            valid_sets=[lgb.Dataset(Xva, yva, categorical_feature=list(categories))],
            callbacks=[lgb.early_stopping(p.early_stopping_rounds, verbose=False)],
        )
        best_iterations[str(alpha)] = booster.best_iteration
        booster.save_model(
            str(out_dir / f"q{int(alpha * 100):02d}.txt"), num_iteration=booster.best_iteration
        )
    manifest = {
        "version": version,
        "trained_on_days": list(cfg.estimation.split_days.train),
        "validated_on_days": list(cfg.estimation.split_days.validation),
        "history_last_day": manifest_hist["last_day"],
        "seed": seed,
        "features": cfg.estimation.features,
        "categorical": categories,
        "quantiles": cfg.estimation.quantiles,
        "best_iterations": best_iterations,
        "n_train": len(train),
        "n_validation": len(val),
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (models_dir / "estimation" / "LATEST").write_text(version, encoding="utf-8")
    return manifest


def load_estimation_models(models_dir: Path, version: str | None = None):
    from shiftmate.engines.estimation import EstimationModels

    root = models_dir / "estimation"
    version = version or (root / "LATEST").read_text(encoding="utf-8").strip()
    manifest = json.loads((root / version / "manifest.json").read_text(encoding="utf-8"))
    boosters = {
        float(a): lgb.Booster(model_file=str(root / version / f"q{int(float(a) * 100):02d}.txt"))
        for a in manifest["quantiles"]
    }
    return EstimationModels(
        boosters, manifest["features"], manifest["categorical"], version
    ), manifest


# --- anomaly -------------------------------------------------------------------------------------


def anomaly_matrix(cfg: ShiftMateConfig, iv: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    z = baseline_z_frame(iv, cfg.anomaly)
    return z, worse_z_matrix(z, cfg.anomaly)


def train_anomaly(cfg: ShiftMateConfig, history_dir: Path, models_dir: Path) -> dict[str, Any]:
    iv = load_intervals(cfg, history_dir)
    z, W = anomaly_matrix(cfg, iv)
    split = split_of(iv["day_index"], cfg)
    out_dir = models_dir / "anomaly"
    out_dir.mkdir(parents=True, exist_ok=True)
    p = cfg.anomaly.isolation_forest
    groups = {}
    for (mtype, tier), idx in iv.groupby(["machine_type", "sensor_tier"]).groups.items():
        rows = [i for i in idx if split[i] == "train"]
        if len(rows) < 50:
            continue
        Xg = W.loc[rows]
        feats = [c for c in Xg.columns if Xg[c].abs().sum() > 0]
        model = IsolationForest(
            n_estimators=p.n_estimators, contamination=p.contamination, random_state=p.random_state
        ).fit(Xg[feats].to_numpy())
        scores = -model.score_samples(Xg[feats].to_numpy())  # higher = more unusual
        threshold = float(np.quantile(scores, 1 - cfg.anomaly.if_top_fraction))
        name = f"{mtype}_{tier}"
        joblib.dump(
            {"model": model, "features": feats, "threshold": threshold}, out_dir / f"{name}.joblib"
        )
        groups[name] = {"features": feats, "threshold": threshold, "n_train": len(rows)}
    # baselines for live use: the last 14 days of history, per personal and group key
    last = iv["day"].max() + pd.Timedelta(days=1)
    recent = iv[iv["day"] >= last - pd.Timedelta(days=cfg.anomaly.baseline_days)]
    rows = []
    for level, keys in (
        ("personal", ["operator_id", "machine_type", "task_type"]),
        ("group", ["machine_type", "task_type", "site_id"]),
    ):
        for key, g in recent.groupby(keys):
            if len(g) < cfg.anomaly.baseline_min_intervals:
                continue
            for f in cfg.anomaly.codes():
                v = g[f].dropna().to_numpy()
                if len(v) == 0:
                    continue
                med = float(np.median(v))
                rows.append(
                    {
                        "level": level,
                        **dict(zip(keys, key, strict=True)),
                        "feature": f,
                        "median": med,
                        "mad": float(np.median(np.abs(v - med))),
                        "n": len(v),
                    }
                )
    pd.DataFrame(rows).to_parquet(out_dir / "baselines_latest.parquet", index=False)
    manifest = {"groups": groups, "trained_on_days": list(cfg.estimation.split_days.train)}
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def score_anomaly(models_dir: Path, iv: pd.DataFrame, W: pd.DataFrame) -> pd.Series:
    """IsolationForest 'top 5 %' flag for every interval (False where no model exists)."""
    flag = pd.Series(False, index=iv.index)
    for (mtype, tier), idx in iv.groupby(["machine_type", "sensor_tier"]).groups.items():
        path = models_dir / "anomaly" / f"{mtype}_{tier}.joblib"
        if not path.exists():
            continue
        bundle = joblib.load(path)
        scores = -bundle["model"].score_samples(W.loc[idx, bundle["features"]].to_numpy())
        flag.loc[idx] = scores >= bundle["threshold"]
    return flag
