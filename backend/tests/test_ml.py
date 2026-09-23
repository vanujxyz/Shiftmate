"""Milestone 6: estimation inference maths, vectorised baselines, fleet patterns, EVAL.md writer."""

import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest

from shiftmate.config_loader import get_config
from shiftmate.engines.anomaly import Baselines, baseline_z_frame, features_frame, worse_z_matrix
from shiftmate.engines.estimation import Estimate, EstimationModels, predict, remaining
from shiftmate.eval.report import write_section
from shiftmate.fleet.patterns import fleet_patterns, heat_bands


@pytest.fixture(scope="module")
def tiny_models():
    """Three small quantile models on synthetic tasks: minutes grow with quantity and mud."""
    cfg = get_config()
    rng = np.random.default_rng(0)
    n = 600
    df = pd.DataFrame(
        {
            "task_type": rng.choice(["trenching", "backfilling"], n),
            "machine_type": "excavator",
            "model": "Cat 320",
            "planned_quantity": rng.uniform(20, 120, n),
            "quantity_unit": "m",
            "operator_experience_years": rng.uniform(1, 20, n),
            "operator_skill_index": 1.0,
            "ground_condition": rng.choice(["dry", "muddy"], n),
            "heat_index_c": 30.0,
            "precipitation_mm_h": 0.0,
            "is_night": 0.0,
            "site_id": "CHN-HWY-01",
            "expected_truck_interval_min": 0.0,
            "hour_of_day": 8,
        }
    )
    minutes = df.planned_quantity * 2.4 * np.where(df.ground_condition == "muddy", 1.4, 1.0)
    y = np.log(minutes * rng.lognormal(0, 0.08, n))
    cats = {f: sorted(df[f].astype(str).unique()) for f in cfg.estimation.categorical}
    features = cfg.estimation.features
    models = EstimationModels({}, features, cats, "test")
    X = models.frame(df.to_dict("records"))
    boosters = {}
    for a in (0.1, 0.5, 0.9):
        params = {
            "objective": "quantile",
            "alpha": a,
            "verbose": -1,
            "seed": 1,
            "min_data_in_leaf": 10,
        }
        boosters[a] = lgb.train(params, lgb.Dataset(X, y, categorical_feature=list(cats)), 120)
    return EstimationModels(boosters, features, cats, "test"), df


def test_predictions_are_ordered_ranges_with_reasons(tiny_models) -> None:
    models, df = tiny_models
    cfg = get_config().estimation
    rows = [
        {**df.iloc[0].to_dict(), "planned_quantity": 60, "ground_condition": "muddy"},
        {**df.iloc[0].to_dict(), "planned_quantity": 60, "ground_condition": "dry"},
    ]
    muddy, dry = predict(models, rows, cfg)
    for e in (muddy, dry):
        assert e.p10 <= e.p50 <= e.p90
    assert muddy.p50 > dry.p50 * 1.2
    # D-054: the ground reason names the actual ground and is measured against dry ground.
    ground = [r for r in muddy.reasons if r.feature == "ground_condition"]
    assert ground and ground[0].key == "reason.ground_muddy_slower" and ground[0].minutes > 0


def test_remaining_time_blends_model_and_observed_rate() -> None:
    cfg = get_config().estimation
    est = Estimate(p10=90, p50=100, p90=130, reasons=[])
    fresh = remaining(est, planned_qty=18, done_qty=0, elapsed_min=0, cfg=cfg)
    assert fresh.p50 == pytest.approx(100)
    # half done in 80 min: slower than the model (50 min per half) → remaining grows past 50
    half = remaining(est, planned_qty=18, done_qty=9, elapsed_min=80, cfg=cfg)
    w = 0.5
    rate = w * (9 / 80) + (1 - w) * (18 / 100)
    assert half.p50 == pytest.approx(9 / rate)
    assert half.p10 == pytest.approx(half.p50 * 0.9) and half.p90 == pytest.approx(half.p50 * 1.3)
    nearly = remaining(est, planned_qty=18, done_qty=17, elapsed_min=170, cfg=cfg)
    assert nearly.p50 < half.p50


def test_vectorised_baselines_match_the_reference_implementation() -> None:
    cfg = get_config().anomaly
    rng = np.random.default_rng(3)
    rows = []
    for i in range(300):
        rows.append(
            {
                "day": pd.Timestamp("2026-09-01") + pd.Timedelta(days=int(i % 20)),
                "operator_id": ["OP1", "OP2", "OP3"][i % 3],
                "machine_type": "excavator",
                "task_type": "trenching",
                "site_id": "CHN-HWY-01",
                "engine_on_min": 15.0,
                "working_min": 12.0,
                "idling_time_min": float(rng.integers(0, 6)),
                "load_cycles": int(rng.integers(1, 4)),
                "fuel_used_l": float(rng.uniform(2, 4)),
            }
        )
    df = pd.DataFrame(rows)
    feats = features_frame(df)
    for c in feats.columns:
        df[c] = feats[c]
    fast = baseline_z_frame(df, cfg)
    ref = Baselines(df, cfg)
    for i in [250, 255, 299]:  # rows whose day has 14 days of history before it
        stats, level = ref.stats_for(df.iloc[i].to_dict(), cfg.codes())
        assert fast.loc[i, "baseline_level"] == level
        s = stats["idle_ratio"]
        z = (df.loc[i, "idle_ratio"] - s.median) / (cfg.mad_scale * s.mad + cfg.epsilon)
        assert fast.loc[i, "idle_ratio"] == pytest.approx(z)
    W = worse_z_matrix(fast, cfg)
    assert W.abs().max().max() <= 10 and not W.isna().any().any()


def test_fleet_patterns_need_enough_tasks_and_machines() -> None:
    cfg = get_config()
    rows = []
    for i in range(120):
        muddy = i % 2 == 0
        rows.append(
            {
                "status": "done",
                "day_index": 5,
                "task_type": "trenching",
                "ground_condition": "muddy" if muddy else "dry",
                "heat_index_c": 30.0,
                "ratio": 1.3 if muddy else 1.0,
                "machine_id": f"EXC{i % 6:03d}",
            }
        )
    rows.append(
        {
            "status": "done",
            "day_index": 40,
            "task_type": "trenching",  # test day: ignored
            "ground_condition": "muddy",
            "heat_index_c": 30.0,
            "ratio": 9.0,
            "machine_id": "EXC999",
        }
    )
    out = fleet_patterns(cfg, pd.DataFrame(rows))
    mud = [p for p in out if p["condition"] == "muddy"][0]
    assert mud["change_pct"] == pytest.approx(30.0) and mud["machines"] == 3
    assert heat_bands(cfg)[0][2] == "below 32 °C"


def test_eval_sections_are_replaced_in_order(tmp_path) -> None:
    path = tmp_path / "EVAL.md"
    write_section("estimation", "## Estimation\nfirst", path)
    write_section("idle", "## Idle\nx", path)
    write_section("estimation", "## Estimation\nsecond", path)
    text = path.read_text(encoding="utf-8")
    assert "first" not in text and "second" in text
    assert text.index("## Idle") < text.index("## Estimation")
