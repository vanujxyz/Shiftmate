"""Edge Gateway REST API: every endpoint in TRD §9.1 (milestone 7).

The app runs without generated history or models here (a clean clone): the roster comes from
the deterministic fleet and features that need models say so. The clock task is off; tests
advance the world explicitly.
"""

import pytest
from fastapi.testclient import TestClient

from shiftmate.edge.app import create_app


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("edge")
    return create_app(
        history_dir=tmp / "history",
        models_dir=tmp / "models",
        db_path=tmp / "edge.db",
        autorun=False,
    )


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


def ctx(app):
    return app.state.ctx


def sign_in(client, pin="1001", **kw):
    body = {"operator_id": "OP1001", "machine_id": "EXC001", "pin": pin, "language": "ta", **kw}
    return client.post("/session/sign-in", json=body)


def test_health_and_demo_state(client) -> None:
    h = client.get("/health").json()
    assert h["service"] == "edge" and h["network_online"] is True
    assert h["sim_clock"].startswith("2026-09-24T06:58")
    state = client.get("/demo/state").json()
    assert state["scenario"] == "ravi_shift" and state["focus_machine"] == "EXC001"
    assert [b["id"] for b in state["beats"]][:2] == ["sign_in", "cold_start"]


def test_machines(client) -> None:
    machines = client.get("/machines").json()
    assert len(machines) == 12
    focus = next(m for m in machines if m["focus"])
    assert (
        focus["machine"]["machine_id"] == "EXC001" and focus["machine"]["sensor_tier"] == "advanced"
    )
    assert all(c["enabled"] for c in focus["capabilities"])
    basic = [m for m in machines if m["machine"]["sensor_tier"] == "basic"]
    if basic:  # a basic machine says what it cannot do, and why
        caps = {c["id"]: c for c in basic[0]["capabilities"]}
        assert caps["UNATTENDED_RUNNING"]["enabled"] is False
        assert "seat_occupied" in caps["UNATTENDED_RUNNING"]["reason"]
        assert basic[0]["low_confidence"] is True
    assert client.get("/machines/EXC001").json()["focus"] is True
    r = client.get("/machines/NOPE01")
    assert r.status_code == 404 and "error" in r.json()


def test_sign_in_rules(client) -> None:
    assert sign_in(client, pin="9999").status_code == 401
    assert (
        client.post(
            "/session/sign-in",
            json={"operator_id": "OP9999", "machine_id": "EXC001", "pin": "9999", "language": "en"},
        ).status_code
        == 404
    )
    assert sign_in(client, machine_id="EXC002").status_code == 409
    r = sign_in(client, pin=None, badge="SHIFTMATE:OP1001")
    assert r.status_code == 200
    body = r.json()
    assert body["profile"]["operator"]["name"] == "Ravi Kumar"
    assert body["profile"]["language"] == "ta"
    assert [t["task"]["task_type"] for t in body["shift"]["tasks"]] == [
        "truck_loading",
        "trenching",
        "backfilling",
    ]
    assert body["shift"]["conditions"]["ground_condition"] == "wet"


def test_profile_and_shift(client) -> None:
    sign_in(client)
    p = client.get("/operators/OP1001/profile").json()
    assert p["operator"]["experience_years"] == 9.0
    assert client.get("/operators/OP9999/profile").status_code == 404
    shift = client.get("/operators/OP1001/shift").json()
    assert shift["machine_id"] == "EXC001" and shift["date"] == "2026-09-24"
    assert any(b["reason_key"] == "shift.break_scheduled" for b in shift["breaks"])
    assert client.get("/operators/OP1002/shift").status_code == 404
    assert client.get("/operators/OP1001/shift?date=2026-01-01").status_code == 404
    # no estimation model in a clean clone: the task says so rather than inventing a number
    task_id = shift["tasks"][0]["task"]["task_id"]
    assert client.get(f"/tasks/{task_id}/estimate").status_code == 404
    assert client.get("/tasks/T-NOPE/estimate").status_code == 404


def test_checklist_problem_creates_report(client) -> None:
    sign_in(client)
    answers = [
        {"item_id": i, "ok": i != "leaks"}
        for i in [
            "tracks_tyres",
            "leaks",
            "lights_horn",
            "mirrors_camera",
            "seatbelt_condition",
            "fire_extinguisher",
            "area_clear",
        ]
    ]
    r = client.post(
        "/checklist", json={"operator_id": "OP1001", "machine_id": "EXC001", "answers": answers}
    ).json()
    assert r["problems"] == 1 and len(r["report_ids"]) == 1
    bad = client.post(
        "/checklist",
        json={
            "operator_id": "OP1001",
            "machine_id": "EXC001",
            "answers": [{"item_id": "nope", "ok": True}],
        },
    )
    assert bad.status_code == 422


def test_reports_parse_save_list(client) -> None:
    sign_in(client)
    parsed = client.post(
        "/reports/parse", json={"transcript": "I almost hit a worker near LOAD-A", "language": "en"}
    ).json()
    assert parsed["mode"] == "offline" and parsed["draft"]["type"] == "near_miss"
    assert (
        parsed["context"]["machine_id"] == "EXC001" and parsed["context"]["operator_id"] == "OP1001"
    )
    saved = client.post(
        "/reports",
        json={
            "draft": parsed["draft"],
            "context": parsed["context"],
            "transcript": "I almost hit a worker near LOAD-A",
        },
    ).json()
    assert saved["draft"]["type"] == "near_miss" and saved["synced"] is False
    listed = client.get("/reports?operator_id=OP1001").json()
    assert saved["report_id"] in [r["report_id"] for r in listed]


def test_insights_are_private(client, app) -> None:
    sign_in(client)
    ctx(app).player.advance(20 * 60, auto=True)
    assert client.get("/insights/OP1002").status_code == 403
    day = client.get("/insights/OP1001").json()
    assert day["range"] == "shift" and day["totals_min"]
    week = client.get("/insights/OP1001?range=week").json()
    assert week["days"][-1]["day"] == "2026-09-24"
    assert client.get("/insights/OP1001?range=year").status_code == 422


def test_lessons(client) -> None:
    sign_in(client)
    lessons = client.get("/lessons").json()
    assert len(lessons) == 12
    detail = client.get("/lessons/L-SHUTDOWN?lang=ta").json()
    assert detail["title"]["ta"] and len(detail["cards"]) >= 3
    assert client.get("/lessons/L-NOPE").status_code == 404
    assert client.get("/lessons/recommended?operator_id=OP1001").status_code == 200
    assert client.get("/lessons/recommended?operator_id=OP1002").status_code == 403
    r = client.post(
        "/lessons/L-SHUTDOWN/complete",
        json={"operator_id": "OP1001", "score": 1.0, "duration_s": 88, "language": "ta"},
    )
    assert r.json()["ok"]
    assert next(
        x for x in client.get("/lessons?operator_id=OP1001").json() if x["id"] == "L-SHUTDOWN"
    )["completed"]
    assert (
        client.post(
            "/lessons/L-NOPE/complete",
            json={"operator_id": "OP1001", "score": 1, "duration_s": 1, "language": "en"},
        ).status_code
        == 404
    )


def test_drills(client) -> None:
    body = {
        "operator_id": "OP1001",
        "drill_id": "D-HAZARD-DRILL-1",
        "hazards": [
            {"hazard_id": "worker_swing_zone", "reaction_ms": 800, "correct": True},
            {"hazard_id": "safe_truck_parked", "reaction_ms": None, "correct": True},
            {"hazard_id": "ground_edge", "reaction_ms": None, "correct": False},
        ],
    }
    r = client.post("/drills/results", json=body).json()
    assert r["correct"] == 2 and r["total"] == 3 and r["mean_reaction_ms"] == 800
    assert (
        client.post("/drills/results", json={**body, "drill_id": "L-SHUTDOWN"}).status_code == 404
    )


def test_training_slots_and_booking(client) -> None:
    slots = client.get("/training/slots").json()
    assert len(slots) == 20 and slots[0]["dealer_centre"].startswith("Cat dealer training centre")
    slot = slots[0]["slot_id"]
    assert client.post(
        "/training/bookings", json={"operator_id": "OP1001", "slot_id": slot}
    ).json()["ok"]
    for i in range(2, 7):  # fill the remaining five seats
        client.post("/training/bookings", json={"operator_id": f"OP10{i:02d}", "slot_id": slot})
    assert (
        client.post(
            "/training/bookings", json={"operator_id": "OP1010", "slot_id": slot}
        ).status_code
        == 409
    )
    assert client.get("/training/slots?site_id=NOPE").status_code == 404


def test_assistant_endpoints(client) -> None:
    r = client.post(
        "/assistant/ask", json={"question": "How do I check the seatbelt?", "language": "en"}
    ).json()
    assert (
        r["mode"] == "offline" and r["answerable"] is False and r["notice_key"] == "ask.not_indexed"
    )
    assert (
        client.post(
            "/assistant/intent", json={"utterance": "Next task please", "language": "en"}
        ).json()["intent"]
        == "next_task"
    )
    assert (
        client.post(
            "/assistant/intent", json={"utterance": "அடுத்த வேலை என்ன?", "language": "ta"}
        ).json()["intent"]
        == "next_task"
    )
    assert (
        client.post(
            "/assistant/intent", json={"utterance": "मुझे समस्या बतानी है", "language": "hi"}
        ).json()["intent"]
        == "report_problem"
    )
    assert (
        client.post(
            "/assistant/intent", json={"utterance": "What is hydraulic oil?", "language": "en"}
        ).json()["intent"]
        == "question"
    )


def test_camera_and_sync(client) -> None:
    assert client.post(
        "/proximity/camera", json={"machine_id": "EXC001", "distance_m": 4.2, "confidence": 0.8}
    ).json()["ok"]
    assert (
        client.post(
            "/proximity/camera", json={"machine_id": "EXC002", "distance_m": 4.2, "confidence": 0.8}
        ).status_code
        == 404
    )
    s = client.get("/sync/status").json()
    assert s["online"] is True and s["outbox_size"] >= 1


def test_alert_ack(client, app) -> None:
    sign_in(client)
    player = ctx(app).player
    client.post("/demo/seek", json={"beat_id": "seatbelt"})
    player.advance(8, auto=True)
    current = player.site.runtime.pipeline.alerts.current
    assert current is not None and current.rule_id == "SEATBELT_MOVING"
    r = client.post(f"/alerts/{current.alert_id}/ack", json={"action": "ack"})
    assert r.status_code == 200
    assert client.post("/alerts/nope/ack", json={"action": "ack"}).status_code == 404


def test_demo_controls(client) -> None:
    assert client.post("/demo/speed", json={"x": 30}).json()["speed"] == 30
    assert client.post("/demo/speed", json={"x": 0}).status_code == 422
    assert client.post("/demo/pause").json()["playing"] is False
    assert client.post("/demo/play").json()["playing"] is True
    client.post("/demo/pause")
    assert client.post("/demo/network", json={"online": False}).json()["online"] is False
    assert client.get("/health").json()["network_online"] is False
    client.post("/demo/network", json={"online": True})
    assert client.post("/demo/captions", json={"online": True}).json()["captions"] is True
    assert client.post("/demo/seek", json={"beat_id": "nope"}).status_code == 404
    seek = client.post("/demo/seek", json={"beat_id": "truck_delay"}).json()
    assert seek["sim_time"].startswith("2026-09-24T08:1") or seek["sim_time"].startswith(
        "2026-09-24T08:0"
    )
    assert client.post("/demo/scenario/load", json={"name": "nope"}).status_code == 404
    loaded = client.post("/demo/scenario/load", json={"name": "fleet_tour"}).json()
    assert loaded["focus_machine"] == "WHL014" and loaded["site_id"] == "PIL-MIN-01"
    whl = client.get("/machines/WHL014").json()
    assert whl["machine"]["sensor_tier"] == "basic" and whl["low_confidence"]
    client.post("/demo/scenario/load", json={"name": "ravi_shift"})
