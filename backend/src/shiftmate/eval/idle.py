"""Idle-reason evaluation (TRD §12; PRD §10 targets: accuracy ≥ 0.90 advanced, ≥ 0.75 basic).

For every idle segment the engines classified on the test days, the true reason is the
majority true reason over that segment's ticks. We report accuracy (overall and by sensor tier),
per-class precision and recall, the confusion matrix, and how many true idle periods of at least
a minute were never classified (missed segments).
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.eval.report import md_table, pct, verdict
from shiftmate.eval.truth import assign_to_spans, load_truth, test_dates
from shiftmate.fleet.training import history_manifest
from shiftmate.schema.enums import IdleReason

REASONS = [r.value for r in IdleReason]
TARGETS = {"advanced": 0.90, "standard": None, "basic": 0.75}


def evaluate_idle(cfg: ShiftMateConfig, history_dir: Path) -> tuple[dict, str]:
    manifest = history_manifest(history_dir)
    dates = test_dates(date.fromisoformat(manifest["first_day"]), cfg.estimation.split_days.test)
    dt = float(manifest["tick_seconds"])
    segs = pd.read_parquet(history_dir / "idle_segments.parquet")
    segs["start"] = pd.to_datetime(segs["start"], utc=True)
    segs["end"] = pd.to_datetime(segs["end"], utc=True)
    tz = {s: cfg.sites[s].timezone for s in segs.site_id.unique()}
    segs["local_day"] = [
        s.tz_convert(tz[site]).date() for s, site in zip(segs.start, segs.site_id, strict=True)
    ]
    segs = segs[segs.local_day.isin(dates)].reset_index(drop=True)
    segs["seg_id"] = np.arange(len(segs))

    truth = load_truth(history_dir, dates, ["ts", "machine_id", "idle_reason"])
    joined = assign_to_spans(truth, segs, "start", "end", "seg_id")
    in_seg = joined.dropna(subset=["seg_id"])
    majority = (
        in_seg.dropna(subset=["idle_reason"])
        .groupby("seg_id")["idle_reason"]
        .agg(lambda s: s.value_counts().index[0])
    )
    segs["truth"] = segs["seg_id"].map(majority).fillna("NOT_IDLE")
    segs["correct"] = segs["truth"] == segs["reason"]

    # missed: true idle runs of ≥ 60 s with no tick inside any classified segment
    joined = joined.sort_values(["machine_id", "ts"])
    r = joined["idle_reason"].fillna("")
    new_run = (r != r.shift()) | (joined["machine_id"] != joined["machine_id"].shift())
    joined["run"] = new_run.cumsum()
    runs = (
        joined[joined.idle_reason.notna()]
        .groupby("run")
        .agg(
            reason=("idle_reason", "first"),
            ticks=("ts", "size"),
            covered=("seg_id", lambda s: s.notna().any()),
        )
    )
    runs = runs[runs.ticks * dt >= 60]
    missed = runs[~runs.covered]

    by_tier = (
        segs.groupby("sensor_tier")["correct"]
        .agg(["mean", "size"])
        .reindex(["advanced", "standard", "basic"])
    )
    labels = [*REASONS, "NOT_IDLE"]
    conf = pd.crosstab(segs["truth"], segs["reason"]).reindex(
        index=labels, columns=REASONS, fill_value=0
    )
    per_class = []
    for reason in REASONS:
        tp = int(((segs.reason == reason) & (segs.truth == reason)).sum())
        pred = int((segs.reason == reason).sum())
        actual = int((segs.truth == reason).sum())
        per_class.append(
            {
                "reason": reason,
                "precision": tp / pred if pred else float("nan"),
                "recall": tp / actual if actual else float("nan"),
                "true segments": actual,
                "predicted": pred,
            }
        )
    per_class_df = pd.DataFrame(per_class)
    macro_recall = float(per_class_df["recall"].mean())
    metrics = {
        "segments": int(len(segs)),
        "accuracy": float(segs["correct"].mean()),
        "macro_recall": macro_recall,
        "by_tier": {t: float(v) for t, v in by_tier["mean"].items() if pd.notna(v)},
        "missed_true_segments": int(len(missed)),
        "true_segments_over_1_min": int(len(runs)),
    }

    tier_rows = []
    for tier, row in by_tier.iterrows():
        target = TARGETS[tier]
        tier_rows.append(
            {
                "sensor tier": tier,
                "segments": int(row["size"]) if pd.notna(row["size"]) else 0,
                "accuracy": pct(row["mean"]),
                "target": pct(target) if target else "–",
                "result": verdict(row["mean"], target) if target and pd.notna(row["mean"]) else "–",
            }
        )
    conf_md = conf.reset_index().rename(
        columns={"truth": "true \\ predicted", "index": "true \\ predicted"}
    )
    missed_by = (
        missed["reason"].value_counts().rename_axis("true reason").reset_index(name="missed")
    )
    md = "\n\n".join(
        [
            "## Idle reasons (F-INS-02)",
            f"Test days {cfg.estimation.split_days.test[0]}–{cfg.estimation.split_days.test[1]} "
            f"({dates[0]} to {dates[-1]}): {metrics['segments']:,} idle segments classified by the "
            "engines, each compared with the majority true reason over its ticks.",
            f"**Overall accuracy {pct(metrics['accuracy'])}**, macro-average recall "
            f"{pct(macro_recall)} (every reason weighted equally, so the common 'Not sure' class "
            "cannot hide weak classes).",
            md_table(pd.DataFrame(tier_rows)),
            "### Per reason",
            md_table(
                per_class_df.assign(
                    precision=per_class_df.precision.map(pct), recall=per_class_df.recall.map(pct)
                )
            ),
            "### Confusion matrix (rows: true reason, columns: predicted)",
            md_table(conf_md),
            "### True idle periods that were never classified",
            f"{metrics['missed_true_segments']:,} of {metrics['true_segments_over_1_min']:,} "
            "true idle periods of at least a minute had no classified segment (they were merged "
            "into, or split from, neighbouring states at 30 s resolution).",
            md_table(missed_by) if len(missed_by) else "None.",
        ]
    )
    return metrics, md
