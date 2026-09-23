"""History replay through the engine pipeline: interval invariants (TRD §7.5) and determinism.

Generates a small history (one site, two days), replays it, and checks every interval against
the ticks it summarises. Simulator/eval tests may read ground truth; this one does not need to.
"""

import pandas as pd
import pytest

from shiftmate.edge.replay import replay_history
from shiftmate.sim.history import generate_history


@pytest.fixture(scope="module")
def replayed(tmp_path_factory):
    out = tmp_path_factory.mktemp("hist")
    generate_history(days=2, seed=3, out_dir=out, sites=["PNQ-MET-01"], workers=1)
    counts = replay_history(out, sites=["PNQ-MET-01"], workers=1)
    ticks = pd.read_parquet(out / "ticks_30s")
    ticks["ts"] = pd.to_datetime(ticks["ts"], utc=True)
    return (
        out,
        counts,
        pd.read_parquet(out / "intervals.parquet"),
        pd.read_parquet(out / "events.parquet"),
        ticks,
    )


def test_replay_produces_outputs(replayed) -> None:
    _, counts, intervals, events, _ = replayed
    assert counts["intervals"] > 100 and counts["events"] > 0 and counts["idle_segments"] > 20
    brief = [
        "machine_id",
        "operator_id",
        "engine_hours",
        "fuel_used_l",
        "load_cycles",
        "idling_time_min",
        "seatbelt_status",
        "safety_alert_triggered",
    ]
    assert intervals[brief].notna().all().all()
    assert set(events["type"]) >= {"alert", "idle_segment"}


def test_idling_within_engine_on_within_interval(replayed) -> None:
    _, _, iv, _, _ = replayed
    assert (iv["idling_time_min"] <= iv["engine_on_min"].round() + 0.5).all()
    assert (iv["engine_on_min"] <= iv["interval_minutes"] + 1e-6).all()
    assert (iv["interval_minutes"] <= 15 + 1e-6).all()


def test_engine_hours_and_fuel_match_ticks(replayed) -> None:
    _, _, iv, _, ticks = replayed
    for r in iv.sample(60, random_state=1).itertuples():
        t = ticks[
            (ticks.machine_id == r.machine_id)
            & (ticks.ts >= r.interval_start)
            & (ticks.ts < r.timestamp)
        ]
        on_h = t["engine_on"].sum() * 30 / 3600
        assert r.engine_on_min / 60 == pytest.approx(on_h, abs=1e-6)
        fuel = (t["fuel_rate_lph"] * 30 / 3600).sum()
        assert r.fuel_used_l == pytest.approx(fuel, abs=0.051)
        seat = t.sort_values("ts").iloc[-1]["seatbelt_fastened"]
        assert r.seatbelt_status == ("Fastened" if seat else "Unfastened")


def test_engine_hours_increase_by_engine_on_time(replayed) -> None:
    _, _, iv, _, _ = replayed
    for _, g in iv.groupby("machine_id"):
        g = g.sort_values("timestamp")
        same_day = g["timestamp"].dt.date.eq(g["timestamp"].dt.date.shift())
        diff = g["engine_hours"].diff()[same_day]
        on = (g["engine_on_min"] / 60)[same_day]
        assert ((diff - on).abs() <= 0.1 + 1e-9).all()  # hour meter shows 1 decimal


def test_safety_alert_iff_p1_or_p2_in_interval(replayed) -> None:
    _, _, iv, ev, _ = replayed
    raised = ev[(ev.type == "alert") & ev.priority.isin(["P1", "P2"])]
    for r in iv.itertuples():
        e = raised[
            (raised.machine_id == r.machine_id)
            & (raised.ts >= r.interval_start)
            & (raised.ts < r.timestamp)
        ]
        assert (r.safety_alert_triggered == "Yes") == (len(e) > 0), r.record_id


def test_replay_is_deterministic(tmp_path) -> None:
    generate_history(days=1, seed=4, out_dir=tmp_path, sites=["TRO-RD-01"], workers=1)
    replay_history(tmp_path, sites=["TRO-RD-01"], workers=1)
    a = pd.read_parquet(tmp_path / "events.parquet")
    replay_history(tmp_path, sites=["TRO-RD-01"], workers=1)
    b = pd.read_parquet(tmp_path / "events.parquet")
    pd.testing.assert_frame_equal(a, b)
