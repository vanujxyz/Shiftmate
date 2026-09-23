"""Fleet Service (milestone 9): ingest, supervisor views, privacy, model registry, live feed.

Runs on a clean clone: the store starts empty (no history seeding) and the tests upload their
own records, built with the helpers below, then check what the supervisor would see.
"""

import dataclasses
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from shiftmate.config_loader import load_config
from shiftmate.fleet.app import create_app

SITE = "CHN-HWY-01"
TZ = ZoneInfo("Asia/Kolkata")
DAY = datetime(2026, 9, 24, tzinfo=TZ)


def at(hh: int, mm: int = 0, day: int = 0) -> datetime:
    return DAY.replace(hour=hh) + timedelta(minutes=mm, days=day)


def interval(machine: str, operator: str, end: datetime, **kw) -> dict:
    """One 15-minute interval summary, as an edge uploads it."""
    base = {
        "timestamp": end.isoformat(),
        "interval_start": (end - timedelta(minutes=15)).isoformat(),
        "interval_minutes": 15,
        "record_id": f"{machine}|{end.isoformat()}",
        "machine_id": machine,
        "operator_id": operator,
        "site_id": SITE,
        "engine_hours": 1000.0,
        "fuel_used_l": 4.0,
        "load_cycles": 5,
        "idling_time_min": 0,
        "seatbelt_status": "Fastened",
        "safety_alert_triggered": "No",
        "engine_on_min": 15.0,
        "working_min": 15.0,
        "idle_warmup_min": 0.0,
        "idle_break_min": 0.0,
        "idle_truck_wait_min": 0.0,
        "idle_unattended_min": 0.0,
        "idle_habit_min": 0.0,
        "idle_unknown_min": 0.0,
        "seatbelt_unfastened_working_s": 0,
        "risk_score_max": 20,
        "p1_alert_count": 0,
        "near_miss_count": 0,
        "incident_count": 0,
        "task_progress_qty": 0.0,
    }
    return {**base, **kw}


def event(event_id: str, machine: str, operator: str | None, ts: datetime, **kw) -> dict:
    return {
        "event_id": event_id,
        "ts": ts.isoformat(),
        "machine_id": machine,
        "operator_id": operator,
        "site_id": SITE,
        "type": "alert",
        "priority": "P1",
        "code": "SEATBELT_MOVING",
        "payload": {"phase": "raised"},
        "shared_with_supervisor": True,
        **kw,
    }


def task(task_id: str, machine: str, status: str, **kw) -> dict:
    return {
        "task_id": task_id,
        "site_id": SITE,
        "machine_id": machine,
        "operator_id": "OP1001",
        "task_type": "trenching",
        "zone_id": "DIG-A",
        "planned_quantity": 10.0,
        "quantity_unit": "m",
        "scheduled_start": at(7).isoformat(),
        "status": status,
        **kw,
    }


def report(report_id: str, kind: str, ts: datetime, operator: str = "OP1001") -> dict:
    return {
        "report_id": report_id,
        "operator_id": operator,
        "machine_id": "EXC001",
        "ts": ts.isoformat(),
        "draft": {"type": kind, "severity": "medium", "summary_en": f"a {kind}"},
        "context": {"site_id": SITE, "machine_id": "EXC001"},
    }


def make_app(tmp_path, cfg=None):
    return create_app(
        cfg=cfg,
        db_path=tmp_path / "fleet.duckdb",
        history_dir=tmp_path / "history",
        models_dir=tmp_path / "models",
        seed=False,
    )


@pytest.fixture
def client(tmp_path):
    with TestClient(make_app(tmp_path)) as c:
        yield c


def post(client, kind: str, records: list[dict], source: str = "EXC001"):
    return client.post(f"/ingest/{kind}", json={"source": source, "records": records})


# --- ingest -------------------------------------------------------------------------------------


def test_ingest_is_idempotent(client) -> None:
    rows = [interval("EXC001", "OP1001", at(8, 15 * k)) for k in range(4)]
    first = post(client, "intervals", rows).json()
    assert first == {
        "kind": "intervals",
        "received": 4,
        "inserted": 4,
        "updated": 0,
        "duplicates": 0,
        "rejected": 0,
    }
    again = post(client, "intervals", rows).json()  # the edge re-sends after a timeout
    assert again["inserted"] == 0 and again["duplicates"] == 4
    ev = [event("e1", "EXC001", "OP1001", at(9))]
    assert post(client, "events", ev).json()["inserted"] == 1
    assert post(client, "events", ev).json()["duplicates"] == 1
    rep = [report("r1", "near_miss", at(10))]
    assert post(client, "reports", rep).json()["inserted"] == 1
    assert post(client, "reports", rep).json()["duplicates"] == 1
    totals = client.get("/scale/stats").json()["totals"]
    assert totals == {"intervals": 4, "events": 1, "reports": 1, "tasks": 0}


def test_tasks_move_forward_only(client) -> None:
    assert post(client, "tasks", [task("T1", "EXC001", "active")]).json()["inserted"] == 1
    done = post(client, "tasks", [task("T1", "EXC001", "done", done_qty=10)]).json()
    assert done["updated"] == 1 and done["inserted"] == 0
    stale = post(client, "tasks", [task("T1", "EXC001", "active")]).json()  # late re-send
    assert stale["duplicates"] == 1 and stale["updated"] == 0
    s = client.get(f"/sites/{SITE}/summary?date=2026-09-24").json()
    exc = next(m for m in s["machines"] if m["machine_id"] == "EXC001")
    assert exc["tasks"][0]["status"] == "done"


def test_ingest_rejects_invalid_and_oversized(client) -> None:
    bad = interval("EXC001", "OP1001", at(8))
    del bad["record_id"]
    naive = interval("EXC001", "OP1001", at(8, 15))
    naive["timestamp"] = "2026-09-24T08:15:00"  # no time zone
    r = post(client, "intervals", [bad, naive]).json()
    assert r["rejected"] == 2 and r["inserted"] == 0
    too_many = [interval("EXC001", "OP1001", at(8) + timedelta(minutes=k)) for k in range(501)]
    assert post(client, "intervals", too_many).status_code == 413
    assert client.post("/ingest/ticks", json={"records": []}).status_code == 422  # no raw ticks


# --- privacy ------------------------------------------------------------------------------------


def test_private_events_never_enter_the_fleet(client) -> None:
    private = event(
        "p1",
        "EXC001",
        "OP1001",
        at(9),
        type="idle_segment",
        code="HABIT",
        priority=None,
        shared_with_supervisor=False,
    )
    r = post(client, "events", [private]).json()
    assert r["rejected"] == 1 and r["inserted"] == 0
    near_miss = event(
        "n1",
        "EXC001",
        "OP1001",
        at(9),
        type="near_miss",
        code="near_miss",
        priority=None,
        shared_with_supervisor=False,
    )
    assert post(client, "events", [near_miss]).json()["inserted"] == 1  # always allowed (P-03)


def test_safety_names_operators_only_where_allowed(client) -> None:
    post(client, "intervals", [interval("EXC001", "OP1001", at(9), risk_score_max=55)])
    post(
        client,
        "events",
        [
            event("a1", "EXC001", "OP1001", at(9, 1)),  # P1 alert: named (P-03)
            event("a2", "EXC001", "OP1001", at(9, 2), priority="P2", code="HEAT_NO_BREAK"),
            event(
                "s1",
                "EXC001",
                None,
                at(9, 3),
                type="site_issue",
                code="WAITING_FOR_TRUCK",
                priority=None,
                payload={"minutes": 18, "zone_id": "LOAD-A"},
            ),
            event(
                "n1",
                "EXC001",
                "OP1001",
                at(9, 4),
                type="near_miss",
                code="near_miss",
                priority=None,
            ),
        ],
    )
    post(
        client,
        "reports",
        [report("r1", "near_miss", at(9, 5)), report("r2", "equipment_problem", at(9, 6))],
    )
    s = client.get(f"/sites/{SITE}/safety?date=2026-09-24").json()
    assert [(e["code"], e["operator_id"], e["operator_name"]) for e in s["p1"]] == [
        ("SEATBELT_MOVING", "OP1001", "Ravi Kumar")
    ]
    assert s["p2_counts"] == {"HEAT_NO_BREAK": 1}
    assert s["near_misses"][0]["operator_id"] == "OP1001"
    issue = s["site_issues"][0]
    assert issue["operator_id"] is None and issue["detail"] == {"minutes": 18, "zone_id": "LOAD-A"}
    reports = {r["type"]: r["operator_id"] for r in s["reports"]}
    assert reports == {"near_miss": "OP1001", "equipment_problem": None}
    assert s["risk"] == [
        {"machine_id": "EXC001", "band": "amber", "score": 55, "amber_min": 15.0, "red_min": 0.0}
    ]


def test_idle_causes_never_name_operators(client) -> None:
    rows = [
        interval("EXC001", "OP1001", at(10, 15 * k), idle_truck_wait_min=10.0, task_id="T1")
        for k in range(1, 5)
    ]
    post(client, "intervals", rows)
    body = client.get(f"/sites/{SITE}/idle-causes?date=2026-09-24").json()
    assert "OP1" not in json.dumps(body)  # site issue, attributed to the site (P-04)
    assert body["lead"] == {
        "reason": "WAITING_FOR_TRUCK",
        "minutes": 40.0,
        "share": 1.0,
        "site_issue": True,
    }


def _operators_on(client, day: int, operators: list[str]) -> None:
    rows = [
        interval(f"EXC00{i + 1}", op, at(9, day=day), idle_habit_min=3.0)
        for i, op in enumerate(operators)
    ]
    post(client, "intervals", rows)


def test_trends_hide_small_groups(tmp_path) -> None:
    with TestClient(make_app(tmp_path)) as client:
        _operators_on(client, -1, ["OP1001", "OP1002"])  # 2 operators: hidden
        _operators_on(client, 0, ["OP1001", "OP1002", "OP1003"])  # 3: shown
        t = client.get(f"/sites/{SITE}/trends?days=2").json()
        days = {d["day"]: d for d in t["daily"]}
        assert days["2026-09-23"]["suppressed"] and days["2026-09-23"]["idle_min_by_reason"] is None
        assert not days["2026-09-24"]["suppressed"]
        assert days["2026-09-24"]["idle_min_by_reason"]["HABIT"] == 9.0
        assert t["min_group_size"] == 3
        for g in t["by_experience"]:  # every experience group has < 3 of these operators
            assert g["suppressed"] or g["operators"] >= 3
            if g["suppressed"]:
                assert g["habit_idle_min_per_h"] is None
    # P-06: privacy rules are configuration; a stricter site hides the 3-operator day too
    cfg = load_config()
    strict = dataclasses.replace(
        cfg,
        privacy=cfg.privacy.model_copy(update={"supervisor_aggregates_min_group_size": 5}),
    )
    with TestClient(make_app(tmp_path, strict)) as client:
        t = client.get(f"/sites/{SITE}/trends?days=2").json()
        assert all(d["suppressed"] for d in t["daily"]) and t["min_group_size"] == 5


# --- supervisor views ---------------------------------------------------------------------------


def test_summary_on_track_and_behind(client) -> None:
    # baseline: five finished trenching tasks on excavators, 10 min per metre
    done = [
        task(
            f"B{k}",
            "EXC002",
            "done",
            actual_start=at(7, day=-2).isoformat(),
            actual_end=at(8, 40, day=-2).isoformat(),
            actual_duration_min=100.0,
            done_qty=10,
        )
        for k in range(5)
    ]
    post(client, "tasks", done)
    post(
        client,
        "tasks",
        [
            task("T-ON", "EXC001", "active", actual_start=at(8).isoformat()),
            task("T-LATE", "EXC003", "active", actual_start=at(8).isoformat()),
            task("T-NEXT", "EXC001", "scheduled", scheduled_start=at(13).isoformat()),
        ],
    )
    # both have done 5 of 10 m (should take 50 min; behind after 50 × 1.15 + 10 = 67.5 min)
    post(
        client,
        "intervals",
        [
            interval("EXC001", "OP1001", at(9), task_id="T-ON", task_progress_qty=5.0),
            interval("EXC003", "OP1003", at(9), task_id="T-LATE", task_progress_qty=2.5),
            interval("EXC003", "OP1003", at(9, 15), task_id="T-LATE", task_progress_qty=2.5),
        ],
    )
    s = client.get(f"/sites/{SITE}/summary?date=2026-09-24").json()
    tasks = {t["task_id"]: t for m in s["machines"] for t in m["tasks"]}
    assert tasks["T-ON"]["expected_min"] == 100.0 and tasks["T-ON"]["elapsed_min"] == 60.0
    assert tasks["T-ON"]["track"] == "on_track" and tasks["T-ON"]["progress_pct"] == 50.0
    assert tasks["T-LATE"]["elapsed_min"] == 75.0 and tasks["T-LATE"]["track"] == "behind"
    assert tasks["T-NEXT"]["track"] == "not_started"
    machines = {m["machine_id"]: m for m in s["machines"]}
    assert machines["EXC001"]["track"] == "on_track" and machines["EXC003"]["track"] == "behind"
    assert machines["EXC001"]["operator_name"] == "Ravi Kumar"
    assert s["tasks_behind"] == 1 and s["tasks_on_track"] == 1
    assert len(s["machines"]) == 24  # every machine at the site is listed, working or not


def test_truck_suggestion_names_zone_window_and_basis(client) -> None:
    post(
        client,
        "tasks",
        [
            task(
                "L1",
                "EXC001",
                "active",
                task_type="truck_loading",
                zone_id="LOAD-A",
                actual_start=at(7, day=-3).isoformat(),
            )
        ],
    )
    rows = []
    for day, per in ((0, 12.0), (-1, 8.0), (-2, 10.0)):  # 10:00–12:00 on three days
        for k in range(1, 9):
            rows.append(
                interval(
                    "EXC001",
                    "OP1001",
                    at(10, day=day) + timedelta(minutes=15 * k),
                    idle_truck_wait_min=per,
                    task_id="L1",
                )
            )
    post(client, "intervals", rows)
    body = client.get(f"/sites/{SITE}/idle-causes?date=2026-09-24").json()
    s = body["suggestion"]
    assert s["key"] == "suggest.add_truck" and s["zone_id"] == "LOAD-A"
    assert (s["window_start"], s["window_end"]) == ("10:00", "12:00")
    assert s["basis_days"] == 3  # today and two similar days
    # intervals count by their start hour: all eight (10:00–11:45) fall in the window, so the
    # three days waited 96, 64 and 80 min; the quartiles of those are 72 and 88
    assert (s["save_min_low"], s["save_min_high"]) == (72.0, 88.0)
    hours = {h["hour"]: h["minutes"] for h in body["truck_wait_by_hour"]}
    assert hours[10] == 48.0 and hours[11] == 48.0


def test_sites_and_overview(client) -> None:
    post(
        client,
        "intervals",
        [
            interval(
                "EXC001",
                "OP1001",
                at(9),
                heat_index_c=41.0,
                ground_condition="wet",
                risk_score_max=75,
            )
        ],
    )
    sites = {s["site_id"]: s for s in client.get("/sites").json()}
    assert set(sites) == {"CHN-HWY-01", "PNQ-MET-01", "PIL-MIN-01", "TRO-RD-01"}
    assert sites[SITE]["last_date"] == "2026-09-24" and sites["TRO-RD-01"]["last_date"] is None
    o = client.get("/fleet/overview").json()
    assert o["machines_total"] == 60 and sum(o["by_type"].values()) == 60
    chn = next(s for s in o["sites"] if s["site_id"] == SITE)
    assert chn["machines_active"] == 1 and chn["risk_bands"]["red"] == 1
    assert chn["ground_condition"] == "wet" and chn["last_ingest"] is not None
    assert client.get("/sites/NOPE/summary").status_code == 404
    assert client.get("/fleet/patterns").json() == []  # not trained in a clean clone


# --- model registry and live feed ---------------------------------------------------------------


def test_model_registry(tmp_path) -> None:
    app = make_app(tmp_path)
    with TestClient(app) as client:
        assert client.get("/models/estimation/latest").status_code == 404
        d = tmp_path / "models" / "estimation" / "est-x"
        d.mkdir(parents=True)
        (d / "manifest.json").write_text('{"version": "est-x"}', encoding="utf-8")
        (d / "q50.txt").write_text("tree", encoding="utf-8")
        (tmp_path / "models" / "estimation" / "LATEST").write_text("est-x", encoding="utf-8")
        latest = client.get("/models/estimation/latest").json()
        assert latest["version"] == "est-x" and latest["files"] == ["manifest.json", "q50.txt"]
        assert client.get("/models/estimation/est-x/files/q50.txt").text == "tree"
        assert client.get("/models/estimation/est-x/files/nope.txt").status_code == 404
        assert client.get("/models/estimation/..%2F..%2Fsecret/files/x").status_code == 404
        assert client.get("/models/estimation/est-x/files/..%5Cmanifest.json").status_code == 404


def test_ws_fleet_counts_ingest_and_shows_p1(client) -> None:
    with client.websocket_connect("/ws/fleet") as ws:
        snap = ws.receive_json()
        assert snap["type"] == "snapshot" and snap["payload"]["totals"]["events"] == 0
        post(client, "events", [event("w1", "EXC001", "OP1001", at(9))])
        first = ws.receive_json()
        assert first["type"] == "site_event" and first["payload"]["code"] == "SEATBELT_MOVING"
        assert "operator_id" not in first["payload"]
        counters = ws.receive_json()
        assert counters["type"] == "ingest" and counters["payload"]["totals"]["events"] == 1
        assert counters["seq"] == first["seq"] + 1
