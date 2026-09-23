"""Scale mode, runtime benchmark and projection (TRD §7.6), and the edge → fleet path end to end.

Small sizes here (tens of machines, minutes of simulated time); the full 10,000-machine run is a
CLI command whose results go to docs/EVAL.md.
"""

import asyncio
from datetime import UTC, datetime

import httpx
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from shiftmate.config_loader import load_config
from shiftmate.edge.headless import run_headless
from shiftmate.fleet.scale import eval_section, projection, read_scale_file, write_scale_file
from shiftmate.schema.fleet import BenchResult, ScaleRun
from shiftmate.sim.bench import bench_runtime
from shiftmate.sim.scale import Pool, run_scale
from test_fleet import SITE, at, event, interval, make_app

CFG = load_config()


def tiny_pool() -> Pool:
    """Three template machines with an hour of summaries each and one shared P1 event."""
    rows = [
        interval(m, op, at(9, 15 * k), idle_habit_min=float(k))
        for m, op in (("EXC001", "OP1001"), ("WHL001", "OP1002"), ("DOZ001", "OP1003"))
        for k in range(1, 5)
    ]
    iv = pd.DataFrame(rows)
    for col in ("timestamp", "interval_start"):
        iv[col] = pd.to_datetime(iv[col], utc=True)
    ev = pd.DataFrame([event("t1", "EXC001", "OP1001", at(9, 20))])
    ev["ts"] = pd.to_datetime(ev.ts, utc=True)
    return Pool(iv, ev)


def test_scale_run_streams_synthetic_machines(tmp_path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        start = datetime(2026, 9, 24, 3, 0, tzinfo=UTC)
        run = run_scale(CFG, client, tiny_pool(), machines=40, sim_minutes=30, start=start)
        assert run.intervals == 80 and run.requests >= 1  # 40 machines × 2 intervals
        assert run.records == run.intervals + run.events and run.records_per_s > 0
        assert run.bytes_per_machine_per_hour > 0 and run.request_ms_p95 >= run.request_ms_p50
        stats = client.get("/scale/stats").json()
        assert stats["scale_machines"] == 40 and stats["totals"]["intervals"] == 80
        assert stats["live"]["records_last_60s"] == run.records
        # synthetic machines never appear in a real site's views
        o = client.get("/fleet/overview").json()
        assert o["records"]["intervals"] == 0 and o["scale_machines"] == 40
        s = client.get(f"/sites/{SITE}/summary").json()
        assert all(not m["machine_id"].startswith("SX") for m in s["machines"])
        # re-running the same stream is idempotent
        again = run_scale(CFG, client, tiny_pool(), machines=40, sim_minutes=30, start=start)
        assert again.intervals == 80
        assert client.get("/scale/stats").json()["totals"]["intervals"] == 80


def test_projection_is_linear_and_labelled(tmp_path) -> None:
    now = datetime.now(UTC)
    run = ScaleRun(
        machines=10_000,
        sim_minutes=60,
        records=50_000,
        intervals=40_000,
        events=10_000,
        requests=100,
        seconds=20.0,
        records_per_s=5_000.0,
        request_ms_p50=80.0,
        request_ms_p95=120.0,
        bytes_sent=100_000_000,
        bytes_per_machine_per_hour=10_000.0,
        records_per_machine_per_hour=5.0,
        finished_at=now,
    )
    p = projection(CFG, run, None)
    assert p.label == "projection" and p.machines == 1_600_000
    assert p.uplink_bytes_per_day == 10_000 * 24 * 1_600_000
    assert p.records_per_s == round(5 * 24 * 1_600_000 / 86_400, 1)
    assert p.ingest_nodes_at_measured_rate == round(p.records_per_s / 5_000, 2)
    bench = BenchResult(
        machines=200,
        sim_minutes=30,
        ticks=360_000,
        cpu_ms_per_tick_mean=0.2,
        cpu_ms_per_tick_p95=0.4,
        memory_mb_per_machine=0.5,
        upload_bytes_per_machine_per_hour=8_000.0,
        records_per_machine_per_hour=4.5,
        finished_at=now,
    )
    assert projection(CFG, run, bench).basis.startswith("runtime benchmark")  # footprint wins
    path = tmp_path / "scale.json"
    write_scale_file(path, run=run)
    write_scale_file(path, bench=bench)  # keeps the run
    assert read_scale_file(path) == (run, bench)
    md = eval_section(CFG, run, bench)
    assert "a linear projection, not a measurement" in md and "10,000 synthetic machines" in md
    assert projection(CFG, None, None) is None


def test_bench_runtime_small(tmp_path) -> None:
    result = bench_runtime(CFG, tmp_path / "h", tmp_path / "m", machines=4, sim_minutes=2)
    assert result.machines == 4 and result.ticks == 4 * 120
    assert 0 < result.cpu_ms_per_tick_mean <= result.cpu_ms_per_tick_p95 * 10
    assert result.memory_mb_per_machine > 0


@pytest.fixture(scope="module")
def shift_in_fleet(tmp_path_factory):
    """Ravi's shift played headless, uploading to a real Fleet Service (no history seeded)."""
    tmp = tmp_path_factory.mktemp("e2e")
    fleet = make_app(tmp)
    edge_tmp = tmp / "edge"
    result = asyncio.run(
        run_headless(
            workdir=edge_tmp,
            history_dir=edge_tmp / "history",
            models_dir=edge_tmp / "models",
            fleet_transport=httpx.ASGITransport(app=fleet),
        )
    )
    with TestClient(fleet) as client:
        yield result, client


def test_edge_uploads_reach_the_supervisor(shift_in_fleet) -> None:
    result, client = shift_in_fleet
    assert result.outbox[-1][2] == 0  # everything synced
    s = client.get(f"/sites/{SITE}/summary?date=2026-09-24").json()
    exc = next(m for m in s["machines"] if m["machine_id"] == "EXC001")
    assert exc["operator_id"] == "OP1001" and exc["last_seen"] is not None
    kinds = [t["task_type"] for t in exc["tasks"]]
    assert kinds == ["truck_loading", "trenching", "backfilling"]
    assert exc["tasks"][0]["status"] == "done" and exc["tasks"][2]["status"] == "active"
    safety = client.get(f"/sites/{SITE}/safety?date=2026-09-24").json()
    assert {e["code"] for e in safety["p1"]} >= {"PROXIMITY_CRITICAL", "SEATBELT_MOVING"}
    assert all(e["operator_id"] == "OP1001" for e in safety["p1"])
    assert safety["near_misses"] and safety["site_issues"]
    assert all(e["operator_id"] is None for e in safety["site_issues"])
    assert {r["type"] for r in safety["reports"]} == {"near_miss", "equipment_problem"}
    idle = client.get(f"/sites/{SITE}/idle-causes?date=2026-09-24").json()
    assert idle["lead"]["reason"] == "WAITING_FOR_TRUCK"
    truck = next(x for x in idle["suggestions"] if x["key"] == "suggest.add_truck")
    assert truck["zone_id"] == "LOAD-A" and truck["basis_days"] == 1  # no history seeded
    assert truck["save_min_low"] is None  # one day is not enough for a range
