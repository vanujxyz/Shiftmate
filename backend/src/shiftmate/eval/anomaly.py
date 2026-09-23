"""Unusual-behaviour evaluation (TRD §12; PRD §10 target: precision and recall ≥ 0.80).

Truth: an interval is anomalous if any of its ticks carries a simulator anomaly flag
(habit idle, cab empty with engine on, unbelted work, speeding near people, abnormal fuel, low
productivity) — D-036. Prediction: the TRD §6.6 rule (IsolationForest top 5 % AND a worse-than-
usual z ≥ 3) OR a P1 safety rule fired in the interval. Reported: overall precision / recall /
F1, recall per anomaly type, results per sensor tier, and what drives false alarms.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.eval.report import md_table, pct, verdict
from shiftmate.eval.truth import assign_to_spans, load_truth, test_dates
from shiftmate.fleet.training import (
    anomaly_matrix,
    history_manifest,
    load_intervals,
    score_anomaly,
    split_of,
)

TYPES = [
    "habit_idle",
    "unattended",
    "seatbelt",
    "speed_near_person",
    "fuel_abnormal",
    "low_productivity",
]


def prf(pred: pd.Series, truth: pd.Series) -> tuple[float, float, float]:
    tp = int((pred & truth).sum())
    p = tp / int(pred.sum()) if pred.sum() else float("nan")
    r = tp / int(truth.sum()) if truth.sum() else float("nan")
    f = 2 * p * r / (p + r) if p and r and not np.isnan(p) and not np.isnan(r) else float("nan")
    return p, r, f


def evaluate_anomaly(cfg: ShiftMateConfig, history_dir: Path, models_dir: Path) -> tuple[dict, str]:
    manifest = history_manifest(history_dir)
    iv = load_intervals(cfg, history_dir)
    z, W = anomaly_matrix(cfg, iv)
    iv["if_top"] = score_anomaly(models_dir, iv, W)
    worse = W  # already oriented and clipped
    iv["strong"] = (worse >= cfg.anomaly.z_threshold).any(axis=1)
    iv["p1"] = iv["p1_alert_count"].fillna(0) > 0
    iv["pred"] = (iv["if_top"] & iv["strong"]) | iv["p1"]
    test = iv[split_of(iv["day_index"], cfg) == "test"].copy()
    test["iv_id"] = np.arange(len(test))

    dates = test_dates(date.fromisoformat(manifest["first_day"]), cfg.estimation.split_days.test)
    truth = load_truth(history_dir, dates, ["ts", "machine_id", *TYPES])
    test["interval_start"] = pd.to_datetime(test["interval_start"], utc=True)
    test["timestamp"] = pd.to_datetime(test["timestamp"], utc=True)
    joined = assign_to_spans(truth, test, "interval_start", "timestamp", "iv_id").dropna(
        subset=["iv_id"]
    )
    flags = joined.groupby("iv_id")[TYPES].any()
    for t in TYPES:
        test[t] = test["iv_id"].map(flags[t]).fillna(False).astype(bool)
    test["truth"] = test[TYPES].any(axis=1)

    p, r, f = prf(test["pred"], test["truth"])
    p_nohard, r_nohard, f_nohard = prf(test["if_top"] & test["strong"], test["truth"])
    rows = []
    for t in TYPES:
        n = int(test[t].sum())
        rows.append(
            {
                "anomaly type": t,
                "true intervals": n,
                "recall": pct(test.loc[test[t], "pred"].mean()) if n else "–",
            }
        )
    tier_rows = []
    for tier in ["advanced", "standard", "basic"]:
        g = test[test.sensor_tier == tier]
        tp, tr, tf = prf(g["pred"], g["truth"])
        tier_rows.append(
            {
                "sensor tier": tier,
                "intervals": len(g),
                "anomalous (truth)": int(g["truth"].sum()),
                "precision": pct(tp),
                "recall": pct(tr),
                "F1": pct(tf),
            }
        )
    fp = test[test["pred"] & ~test["truth"]]
    fp_rows = [
        {
            "false alarm driven by": "a P1 safety rule (e.g. a person inside the swing radius)",
            "intervals": int((fp["p1"]).sum()),
        },
        {
            "false alarm driven by": "IsolationForest + z-score only",
            "intervals": int((~fp["p1"]).sum()),
        },
    ]
    metrics = {
        "intervals": len(test),
        "anomalous": int(test["truth"].sum()),
        "predicted": int(test["pred"].sum()),
        "precision": p,
        "recall": r,
        "f1": f,
        "precision_without_hard_rule": p_nohard,
        "recall_without_hard_rule": r_nohard,
    }
    md = "\n\n".join(
        [
            "## Unusual behaviour (F-INS-04, F-INS-05)",
            f"Test days: {len(test):,} intervals, {metrics['anomalous']:,} truly anomalous "
            f"({pct(metrics['anomalous'] / max(len(test), 1))}); {metrics['predicted']:,} flagged.",
            md_table(
                pd.DataFrame(
                    [
                        {
                            "metric": "precision",
                            "value": pct(p),
                            "target": "80.0 %",
                            "result": verdict(p, 0.80),
                        },
                        {
                            "metric": "recall",
                            "value": pct(r),
                            "target": "80.0 %",
                            "result": verdict(r, 0.80),
                        },
                        {"metric": "F1", "value": pct(f), "target": "–", "result": "–"},
                    ]
                )
            ),
            f"Without the P1 hard rule (model and z-score only): precision {pct(p_nohard)}, "
            f"recall {pct(r_nohard)}.",
            f"Why recall is limited: the TRD rule lets the model flag only intervals in its top "
            f"{pct(cfg.anomaly.if_top_fraction)} (and only those that are also ≥ "
            f"{cfg.anomaly.z_threshold:g} robust z-scores worse than the operator's own normal), "
            f"while {pct(metrics['anomalous'] / max(len(test), 1))} of test intervals are truly "
            "anomalous. Behaviour that is habitual for an operator is part of their own baseline "
            "and is not unusual for them, and machines without a proximity or seat sensor cannot "
            "see speeding near people or an empty cab.",
            "### Recall per anomaly type",
            md_table(pd.DataFrame(rows)),
            "### By sensor tier",
            md_table(pd.DataFrame(tier_rows)),
            "### What drives the false alarms",
            md_table(pd.DataFrame(fp_rows)),
        ]
    )
    return metrics, md
