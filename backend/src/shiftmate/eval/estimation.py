"""Task time estimation evaluation (TRD §12; PRD §10: median absolute error ≤ 12 % of actual,
75–85 % of actual durations inside the p10–p90 range).

Test tasks are the completed tasks on test days. Reported: MAE (minutes), median and mean
absolute percentage error, p10–p90 coverage, per task type; the same for a naive estimate
(planned quantity ÷ the profile's base rate) so the model's value is visible; and the top fleet
patterns learned from days 1–35.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.engines.estimation import predict
from shiftmate.eval.report import md_table, pct, verdict
from shiftmate.fleet.patterns import fleet_patterns
from shiftmate.fleet.training import estimation_dataset, load_estimation_models


def _metrics(actual: np.ndarray, p50: np.ndarray, p10=None, p90=None) -> dict[str, float]:
    ape = np.abs(p50 - actual) / actual
    out = {
        "mae_min": float(np.mean(np.abs(p50 - actual))),
        "median_ape": float(np.median(ape)),
        "mean_ape": float(np.mean(ape)),
    }
    if p10 is not None:
        out["coverage"] = float(np.mean((actual >= p10) & (actual <= p90)))
    return out


def evaluate_estimation(
    cfg: ShiftMateConfig, history_dir: Path, models_dir: Path
) -> tuple[dict, str]:
    df = estimation_dataset(cfg, history_dir)
    models, manifest = load_estimation_models(models_dir)
    done = df[(df.status == "done") & (df.actual_duration_min > 0)]
    results = {}
    tables = {}
    for split in ("validation", "test"):
        part = done[done.split == split].reset_index(drop=True)
        est = predict(models, part.to_dict("records"), cfg.estimation)
        part["p10"] = [e.p10 for e in est]
        part["p50"] = [e.p50 for e in est]
        part["p90"] = [e.p90 for e in est]
        actual = part["actual_duration_min"].to_numpy()
        results[split] = {
            "tasks": len(part),
            **_metrics(actual, part.p50.to_numpy(), part.p10.to_numpy(), part.p90.to_numpy()),
            "naive": _metrics(actual, part["expected_min"].to_numpy()),
        }
        tables[split] = part
    test = tables["test"]
    rows = []
    for tt, g in test.groupby("task_type"):
        m = _metrics(
            g.actual_duration_min.to_numpy(), g.p50.to_numpy(), g.p10.to_numpy(), g.p90.to_numpy()
        )
        rows.append(
            {
                "task type": tt,
                "tasks": len(g),
                "MAE (min)": round(m["mae_min"], 1),
                "median error": pct(m["median_ape"]),
                "mean error": pct(m["mean_ape"]),
                "inside p10–p90": pct(m["coverage"]),
            }
        )
    t = results["test"]
    patterns = fleet_patterns(cfg, df)[:8]
    pattern_rows = [
        {
            "task type": p["task_type"],
            "condition": p["condition"],
            "effect": f"{p['change_pct']:+.0f} %",
            "tasks": p["tasks"],
            "machines": p["machines"],
            "compared with": p["reference"],
        }
        for p in patterns
    ]
    coverage_ok = 0.75 <= t["coverage"] <= 0.85
    md = "\n\n".join(
        [
            "## Task time estimation (F-SHIFT-02, F-SHIFT-03, F-FLT-05)",
            f"Model `{manifest['version']}` (LightGBM quantile 0.1 / 0.5 / 0.9, trained on days "
            f"{manifest['trained_on_days'][0]}–{manifest['trained_on_days'][1]}, "
            f"early stopping on days "
            f"{manifest['validated_on_days'][0]}–{manifest['validated_on_days'][1]}). "
            f"Test: {t['tasks']:,} completed tasks on days 36–42.",
            md_table(
                pd.DataFrame(
                    [
                        {
                            "metric": "median absolute error (% of actual)",
                            "model": pct(t["median_ape"]),
                            "naive base-rate estimate": pct(t["naive"]["median_ape"]),
                            "target": "≤ 12.0 %",
                            "result": verdict(t["median_ape"], 0.12, higher_is_better=False),
                        },
                        {
                            "metric": "mean absolute error (% of actual)",
                            "model": pct(t["mean_ape"]),
                            "naive base-rate estimate": pct(t["naive"]["mean_ape"]),
                            "target": "≤ 12.0 % (TRD)",
                            "result": verdict(t["mean_ape"], 0.12, higher_is_better=False),
                        },
                        {
                            "metric": "mean absolute error (minutes)",
                            "model": f"{t['mae_min']:.1f}",
                            "naive base-rate estimate": f"{t['naive']['mae_min']:.1f}",
                            "target": "–",
                            "result": "–",
                        },
                        {
                            "metric": "actual inside p10–p90",
                            "model": pct(t["coverage"]),
                            "naive base-rate estimate": "–",
                            "target": "75–85 %",
                            "result": "met" if coverage_ok else "**not met**",
                        },
                    ]
                )
            ),
            "Validation days (used for early stopping): median error "
            f"{pct(results['validation']['median_ape'])}, "
            f"coverage {pct(results['validation']['coverage'])}.",
            "### Per task type (test days)",
            md_table(pd.DataFrame(rows)),
            "### Fleet-learned patterns (days 1–35, all machines)",
            md_table(pd.DataFrame(pattern_rows)) if pattern_rows else "No group had enough tasks.",
        ]
    )
    return results, md
