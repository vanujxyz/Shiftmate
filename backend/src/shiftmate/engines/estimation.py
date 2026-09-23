"""Task time estimation at the edge (TRD §6.7; PRD F-SHIFT-02, 03, 04).

Three LightGBM models trained on the fleet (quantiles 0.1, 0.5, 0.9 of log task minutes) give a
range and a most-likely value. After prediction the three are sorted so p10 ≤ p50 ≤ p90.

Reasons (D-054): only conditions an operator recognises are reasons (config `reason_keys`).
For a condition with a natural reference (dry ground, no rain, daytime, 30 °C, an average
operator) the effect is a what-if: the p50 now minus the p50 of the same task with that one
condition at its reference value. Conditions without a reference (quantity, truck supply) use
LightGBM's `pred_contrib`, which splits the p50 (in log minutes) into per-feature parts:
    effect = p50 − p50 · exp(−contribution)
The largest effects of at least a minute become keys with a direction and minutes, e.g.
"reason.ground_wet_slower" +15 min.

Live remaining time for the active task:
    observed_rate = done / elapsed,  model_rate = planned / p50,
    rate = w · observed + (1 − w) · model,  w = min(0.8, progress fraction)
    remaining p50 = (planned − done) / rate, with p10/p90 scaled by the original p10/p50, p90/p50.
Early in a task the model dominates; as work progresses what actually happens takes over.

Pure: models are loaded elsewhere (edge/fleet) and passed in; no I/O here.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from shiftmate.schema.config import EstimationConfig


@dataclass(frozen=True)
class Reason:
    key: str
    feature: str
    minutes: float  # positive = adds time, negative = saves time


@dataclass(frozen=True)
class Estimate:
    p10: float
    p50: float
    p90: float
    reasons: list[Reason]
    low_confidence: bool = False

    def payload(self) -> dict[str, Any]:
        return {
            "p10": round(self.p10, 1),
            "p50": round(self.p50, 1),
            "p90": round(self.p90, 1),
            "reasons": [
                {"key": r.key, "feature": r.feature, "minutes": round(r.minutes, 1)}
                for r in self.reasons
            ],
            "low_confidence": self.low_confidence,
        }


@dataclass
class EstimationModels:
    """The three quantile boosters plus what is needed to rebuild their input frame."""

    boosters: Mapping[float, Any]  # quantile → lightgbm.Booster
    features: list[str]
    categorical: dict[str, list[str]]  # categorical feature → categories seen in training
    version: str

    def frame(self, rows: list[Mapping[str, Any]]) -> pd.DataFrame:
        df = pd.DataFrame([{f: r.get(f) for f in self.features} for r in rows])
        for f in self.features:
            if f in self.categorical:
                df[f] = pd.Categorical(df[f].astype("object"), categories=self.categorical[f])
            else:
                df[f] = pd.to_numeric(df[f], errors="coerce").astype("float64")
        return df


def predict(
    models: EstimationModels,
    rows: list[Mapping[str, Any]],
    cfg: EstimationConfig,
    low_confidence: list[bool] | None = None,
) -> list[Estimate]:
    X = models.frame(rows)
    q = sorted(models.boosters)
    preds = np.column_stack([models.boosters[a].predict(X) for a in q])
    preds = np.exp(np.sort(preds, axis=1))  # enforce p10 ≤ p50 ≤ p90, back to minutes
    contrib = models.boosters[0.5].predict(X, pred_contrib=True)
    # What-if effects (D-054): the same task with one condition at its reference value.
    refs = {f: v for f, v in cfg.reference_values.items() if f in models.features}
    what_if: dict[str, np.ndarray] = {}
    for feature, value in refs.items():
        alt = models.frame([{**r, feature: value} for r in rows])
        what_if[feature] = np.exp(models.boosters[0.5].predict(alt))
    out = []
    for i in range(len(rows)):
        p10, p50, p90 = (float(v) for v in preds[i])
        effects: list[tuple[str, float]] = []
        for j, feature in enumerate(models.features):
            if feature not in cfg.reason_keys:
                continue
            if feature in what_if:
                minutes = p50 - float(what_if[feature][i])  # vs the reference
            else:
                c = float(contrib[i, j])  # no natural reference (quantity, truck supply)
                minutes = p50 - p50 * math.exp(-c)
            effects.append((feature, minutes))
        reasons = []
        for feature, minutes in sorted(effects, key=lambda fm: -abs(fm[1])):
            if len(reasons) >= cfg.top_reasons or abs(minutes) < 1.0:  # under a minute: no chip
                break
            keys = cfg.reason_keys[feature]
            key = keys.slower if minutes > 0 else keys.faster
            if key is not None:
                key = key.replace("{value}", str(rows[i].get(feature)))
                reasons.append(Reason(key, feature, minutes))
        lc = bool(low_confidence[i]) if low_confidence else False
        out.append(Estimate(p10, p50, p90, reasons, lc))
    return out


def remaining(
    estimate: Estimate,
    planned_qty: float,
    done_qty: float,
    elapsed_min: float,
    cfg: EstimationConfig,
) -> Estimate:
    """Live remaining time for the active task (TRD §6.7)."""
    if planned_qty <= 0:
        return estimate
    done_qty = min(max(done_qty, 0.0), planned_qty)
    progress = done_qty / planned_qty
    model_rate = planned_qty / max(estimate.p50, 1e-6)
    observed_rate = done_qty / elapsed_min if elapsed_min > 0 else model_rate
    w = min(cfg.blend_max_weight, progress)
    rate = w * observed_rate + (1 - w) * model_rate
    if rate <= 0:
        rate = model_rate
    p50 = (planned_qty - done_qty) / rate
    lo = estimate.p10 / estimate.p50 if estimate.p50 else 1.0
    hi = estimate.p90 / estimate.p50 if estimate.p50 else 1.0
    return Estimate(p50 * lo, p50, p50 * hi, estimate.reasons, estimate.low_confidence)


def expected_minutes(planned_quantity: float, base_rate_per_h: float) -> float:
    """What the profile says a task should take in good conditions (skill index baseline)."""
    return planned_quantity / base_rate_per_h * 60
