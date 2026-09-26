"""Milestone 3: simulator invariants (TRD §7.5), determinism and fleet facts (TRD §7.1).

Simulator tests may read ground truth and personalities (golden rule 5 allows it here).
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from shiftmate.config_loader import get_config
from shiftmate.schema.enums import IdleReason, SensorTier
from shiftmate.sim.fleet import build_fleet
from shiftmate.sim.history import build_history_fleet
from shiftmate.sim.site import SiteWorld
from shiftmate.util.heat_index import heat_index_c
from shiftmate.util.solar import day_length_hours

DT = 30.0


@pytest.fixture(scope="module")
def cfg():
    return get_config()


def run_days(cfg, site_id: str, seed: int, days: list[int], dt: float = DT):
    fleet = build_history_fleet(cfg, seed)
    site_index = cfg.simulator.fleet.site_order.index(site_id)
    world = SiteWorld(cfg, cfg.sites[site_id], fleet, site_index, seed)
    ticks, truth, tasks = [], [], []
    for d in days:
        r = world.run_day(d, date(2026, 9, 1 + d % 20), dt)
        ticks.append(pd.DataFrame(r.ticks))
        truth.append(pd.DataFrame(r.truth))
        tasks.extend(r.tasks)
    return fleet, pd.concat(ticks, ignore_index=True), pd.concat(truth, ignore_index=True), tasks


@pytest.fixture(scope="module")
def chennai(cfg):
    return run_days(cfg, "CHN-HWY-01", 7, [22, 23])


# --- fleet (TRD §7.1) -------------------------------------------------------------------------


def test_fleet_fixed_machines_and_ravi(cfg) -> None:
    fleet = build_history_fleet(cfg, 7)
    machines = {m.machine_id: m for m in fleet.machines}
    assert len(machines) == 60
    exc = machines["EXC001"]
    assert (exc.model, exc.model_year, exc.sensor_tier, exc.site_id, exc.engine_hours_start) == (
        "Cat 320",
        2023,
        SensorTier.ADVANCED,
        "CHN-HWY-01",
        1520.0,
    )
    whl = machines["WHL014"]
    assert (whl.model, whl.model_year, whl.sensor_tier, whl.site_id) == (
        "Cat 950 GC",
        2013,
        SensorTier.BASIC,
        "PIL-MIN-01",
    )
    ravi = next(o for o in fleet.operators if o.operator_id == "OP1001")
    assert (ravi.name, ravi.preferred_language, ravi.experience_years) == ("Ravi Kumar", "ta", 9.0)
    assert fleet.usual_machine["OP1001"] == "EXC001"
    assert len(fleet.operators) == 80


def test_tiers_follow_model_year_or_one_lower(cfg) -> None:
    fleet = build_history_fleet(cfg, 7)
    order = [SensorTier.BASIC, SensorTier.STANDARD, SensorTier.ADVANCED]
    for m in fleet.machines:
        year_tier = (
            SensorTier.BASIC
            if m.model_year < 2016
            else SensorTier.STANDARD
            if m.model_year < 2022
            else SensorTier.ADVANCED
        )
        assert order.index(year_tier) - order.index(m.sensor_tier) in (0, 1), m.machine_id


def test_about_fifteen_percent_elevated_traits(cfg) -> None:
    fleet = build_fleet(cfg, np.random.default_rng(123))
    elevated = [
        p
        for p in fleet.personalities.values()
        if max(
            p.idle_habit,
            p.seatbelt_skipper,
            p.steps_out_engine_on,
            p.speeds_near_people,
            p.skips_breaks,
        )
        > 0.6
    ]
    assert 3 <= len(elevated) <= 25  # 15 % of 80 ≈ 12, binomial spread


# --- tick invariants (TRD §7.5) ---------------------------------------------------------------


def _check_invariants(cfg, fleet, ticks: pd.DataFrame, truth: pd.DataFrame, dt: float) -> None:
    machines = {m.machine_id: m for m in fleet.machines}
    for machine_id, g in ticks.groupby("machine_id"):
        g = g.sort_values("ts")
        hours = g["engine_hours"].to_numpy()
        on = g["engine_on"].to_numpy()
        # engine hours never go down, and grow by exactly the engine-on time
        steps = np.diff(hours)
        assert (steps >= -1e-9).all(), machine_id
        # consecutive ticks within a day: increment equals engine_on × dt
        same_day = np.diff(g["ts"].astype("int64").to_numpy()) == int(dt * 1e9)
        expected = on[:-1] * dt / 3600
        assert np.allclose(steps[same_day], expected[same_day], atol=1e-4), machine_id
        # load cycle counter never goes down within a day
        cycles = g["load_cycles_total"].to_numpy()
        assert (np.diff(cycles)[same_day] >= 0).all(), machine_id
        # sensor-tier nulls
        tier = machines[machine_id].sensor_tier
        if tier == SensorTier.BASIC:
            assert g["seat_occupied"].isna().all()
            assert g["engine_rpm"].isna().all()
            assert g["coolant_temp_c"].isna().all()
        else:
            assert g["seat_occupied"].notna().all()
        if tier != SensorTier.ADVANCED:
            assert g["proximity_m"].isna().all(), machine_id  # no camera in history
            assert g["truck_in_loading_zone"].isna().all()
        else:
            assert g["proximity_m"].notna().all()

    # fuel: Σ rate × time within 2 % of the profile's state rates (excluding injected episodes)
    merged = ticks.merge(truth, on=["ts", "machine_id"])
    for machine_id, g in merged[~merged["fuel_abnormal"]].groupby("machine_id"):
        profile = cfg.profiles[machines[machine_id].machine_type]
        nominal = np.where(
            ~g["engine_on"],
            0.0,
            np.where(
                g["hydraulic_active"],
                profile.fuel_lph.working,
                np.where(g["activity"] == "travel", profile.fuel_lph.travel, profile.fuel_lph.idle),
            ),
        )
        actual = (g["fuel_rate_lph"] * dt / 3600).sum()
        expected = (nominal * dt / 3600).sum()
        if expected > 0:
            assert abs(actual - expected) / expected < 0.02, machine_id

    # ground-truth idle reasons only on idle ticks (engine on, no hydraulics, not moving)
    labelled = merged[merged["idle_reason"].notna()]
    assert labelled["engine_on"].all()
    assert not labelled["hydraulic_active"].any()
    assert (labelled["travel_speed_kmh"] < 0.5).all()
    assert set(labelled["idle_reason"]) <= {r.value for r in IdleReason}


def test_tick_invariants_chennai(cfg, chennai) -> None:
    fleet, ticks, truth, _ = chennai
    _check_invariants(cfg, fleet, ticks, truth, DT)


def test_every_idle_reason_occurs(chennai) -> None:
    _, _, truth, _ = chennai
    seen = set(truth["idle_reason"].dropna())
    for reason in ("WARM_UP", "SCHEDULED_BREAK", "WAITING_FOR_TRUCK", "UNKNOWN"):
        assert reason in seen


def test_tasks_emerge_with_durations(chennai) -> None:
    _, _, _, tasks = chennai
    done = [t for t in tasks if t.status == "done"]
    assert len(done) > 20
    for t in done:
        assert t.actual_duration_min and t.actual_duration_min > 0
        assert t.actual_start and t.actual_end and t.actual_end > t.actual_start
        assert t.conditions_at_start is not None


def test_ravi_on_exc001_every_day(chennai) -> None:
    _, ticks, _, _ = chennai
    exc = ticks[(ticks.machine_id == "EXC001") & ticks.engine_on]
    assert set(exc["operator_id"]) == {"OP1001"}


@settings(max_examples=5, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(seed=st.integers(min_value=0, max_value=10_000))
def test_invariants_hold_for_any_seed(seed) -> None:
    cfg = get_config()
    fleet, ticks, truth, _ = run_days(cfg, "TRO-RD-01", seed, [5], dt=60.0)
    _check_invariants(cfg, fleet, ticks, truth, 60.0)


# --- determinism (TRD §7.5) -------------------------------------------------------------------


def test_same_seed_same_world(cfg) -> None:
    _, a, ta, _ = run_days(cfg, "PNQ-MET-01", 11, [3])
    _, b, tb, _ = run_days(cfg, "PNQ-MET-01", 11, [3])
    pd.testing.assert_frame_equal(a, b)
    pd.testing.assert_frame_equal(ta, tb)
    _, c, _, _ = run_days(cfg, "PNQ-MET-01", 12, [3])
    assert not a.equals(c)


# --- weather and daylight ---------------------------------------------------------------------


def test_heat_index_matches_scenario_values() -> None:
    assert heat_index_c(35, 60) == pytest.approx(45.1, abs=0.3)  # D-005
    assert heat_index_c(34, 62) == pytest.approx(43.0, abs=0.3)
    assert heat_index_c(29, 78) == pytest.approx(34.3, abs=0.3)
    assert heat_index_c(20, 50) == 20.0  # below ~27 °C the air temperature is reported


def test_polar_night_and_tropical_day() -> None:
    assert day_length_hours(69.65, 349) == 0.0  # Tromsø mid-December
    assert 11.5 < day_length_hours(13.08, 267) < 12.6  # Chennai late September


def test_tromso_winter_is_frozen_and_dark(cfg) -> None:
    _, ticks, _, _ = run_days(cfg, "TRO-RD-01", 7, [10])
    on = ticks[ticks.engine_on]
    assert (on["ground_condition"] == "frozen").mean() > 0.8
    assert on["is_night"].all()


def test_generator_is_deterministic_and_writes_outputs(tmp_path) -> None:
    from shiftmate.sim.history import generate_history

    a = generate_history(days=2, seed=5, out_dir=tmp_path / "a", sites=["TRO-RD-01"], workers=1)
    b = generate_history(days=2, seed=5, out_dir=tmp_path / "b", sites=["TRO-RD-01"], workers=1)
    assert a["site_hashes"] == b["site_hashes"]
    for name in ("machines", "operators", "tasks", "dispatch_log", "weather_hourly"):
        assert (tmp_path / "a" / f"{name}.parquet").exists()
    assert (tmp_path / "a" / "fleet.duckdb").exists()
    assert (tmp_path / "a" / "SUMMARY.md").read_text(encoding="utf-8").startswith("# Simulated")
    ticks = pd.read_parquet(tmp_path / "a" / "ticks_30s")
    assert "label" not in " ".join(ticks.columns)  # ground truth lives only under truth/


def test_history_is_the_same_in_any_process(tmp_path) -> None:
    # string sets iterate in a different order in each process (hash randomisation), so any
    # random draw made while looping over one would change the world between runs
    import os
    import subprocess
    import sys

    code = (
        "import sys; from pathlib import Path; from shiftmate.sim.history import generate_history; "
        "m = generate_history(days=4, seed=7, out_dir=Path(sys.argv[1]), sites=['CHN-HWY-01'], "
        "workers=1); print(m['site_hashes']['CHN-HWY-01'])"
    )
    hashes = []
    for hash_seed in ("1", "2"):
        env = {**os.environ, "PYTHONHASHSEED": hash_seed}
        out = subprocess.run(
            [sys.executable, "-c", code, str(tmp_path / hash_seed)],
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        hashes.append(out.stdout.strip().splitlines()[-1])
    assert hashes[0] == hashes[1]


def test_warm_up_only_when_the_engine_is_cold(cfg, chennai) -> None:
    # D-050: a true warm-up always starts below the coolant ready temperature
    _, ticks, truth, _ = chennai
    m = ticks.merge(truth, on=["ts", "machine_id"]).sort_values(["machine_id", "ts"])
    m = m[m["coolant_temp_c"].notna()]
    starts = m[
        (m["idle_reason"] == "WARM_UP")
        & (m.groupby("machine_id")["idle_reason"].shift() != "WARM_UP")
    ]
    assert len(starts) > 0
    assert (starts["coolant_temp_c"] < 60).all()


def test_engine_is_cold_every_morning(cfg, chennai) -> None:
    # D-050: coolant cools to air temperature overnight
    _, ticks, _, _ = chennai
    first = (
        ticks[ticks["coolant_temp_c"].notna()]
        .sort_values("ts")
        .groupby(["machine_id", ticks["ts"].dt.date])
        .head(1)
    )
    assert (first["coolant_temp_c"] - first["ambient_temp_c"]).abs().max() < 1.0
