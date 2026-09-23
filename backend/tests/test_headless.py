"""Headless run of Ravi's shift at 60× (CLAUDE.md Phase 5 DoD, PRD §9, TRD §8).

The whole Edge Gateway plays `ravi_shift` on a fake clock (`edge/headless.py`) and these tests
check that every beat produced what PRD §9 promises, looking only at what the edge itself
recorded (events, channel messages, outbox, uploads) — never at ground truth. A second run checks
determinism: the same scenario gives the same event log, id for id.

Like the API tests, this runs on a clean clone (no generated history or models), so it checks
the rules and engines, not a trained model. Each run takes about 20 seconds.
"""

import asyncio
from datetime import datetime, timedelta

import pytest

from shiftmate.edge.headless import run_headless


def _run(tmp_path_factory, name: str):
    tmp = tmp_path_factory.mktemp(name)
    return asyncio.run(
        run_headless(
            "ravi_shift",
            speed=60,
            workdir=tmp,
            history_dir=tmp / "history",
            models_dir=tmp / "models",
        )
    )


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    return _run(tmp_path_factory, "headless1")


@pytest.fixture(scope="module")
def run2(tmp_path_factory):
    return _run(tmp_path_factory, "headless2")


def at(run, hhmm: str) -> datetime:
    """A local wall time on the scenario day (same tz as the beat times)."""
    first = run.beats[0]["fired"]
    h, m = map(int, hhmm.split(":"))
    return first.replace(hour=h, minute=m, second=0)


def events(run, type_: str, code: str | None = None, start=None, end=None) -> list[dict]:
    out = []
    for e in run.events:
        ts = datetime.fromisoformat(e["ts"])
        if e["type"] != type_ or (code is not None and e["code"] != code):
            continue
        if (start and ts < start) or (end and ts > end):
            continue
        out.append({**e, "ts": ts})
    return out


def test_every_beat_fires_on_time(run) -> None:
    ids = [b["id"] for b in run.beats]
    assert ids == [
        "sign_in",
        "cold_start",
        "my_shift",
        "truck_delay",
        "worker_near",
        "seatbelt",
        "skip_break",
        "heat",
        "step_out",
        "near_miss",
        "offline",
        "online",
        "end_shift",
    ]
    for b in run.beats:
        assert b["fired"].strftime("%H:%M") == b["at"]


def test_cold_start_warm_up_segment(run) -> None:
    start = at(run, "07:02")
    warm = events(run, "idle_segment", "WARM_UP", start, start + timedelta(minutes=15))
    assert warm, "no WARM_UP idle segment after the cold start"
    seg = warm[0]["payload"]
    assert datetime.fromisoformat(seg["start"]) - start < timedelta(minutes=2)
    assert seg["duration_s"] >= 60


def test_truck_delay_is_a_site_issue_not_the_operator(run) -> None:
    beat = at(run, "08:10")
    waits = [
        e
        for e in events(run, "idle_segment", "WAITING_FOR_TRUCK", beat, beat + timedelta(hours=1))
        if abs(datetime.fromisoformat(e["payload"]["start"]) - beat) < timedelta(minutes=5)
    ]
    assert waits, "no WAITING_FOR_TRUCK segment at the truck delay"
    wait = waits[0]["payload"]
    assert wait["duration_s"] >= 15 * 60  # the beat blocks trucks for 18 minutes
    # the supervisor sees a site issue for the same wait, with no operator attached (PRD P-04)
    issues = [
        e
        for e in events(run, "site_issue", "WAITING_FOR_TRUCK")
        if e["payload"]["start"] == wait["start"]
    ]
    assert len(issues) == 1
    issue = issues[0]
    assert issue["operator_id"] is None and issue["shared_with_supervisor"]
    assert issue["payload"]["minutes"] >= 15
    # … live on the site map while it is happening, then closed
    site_events = [m["payload"] for m in run.site if m["type"] == "site_event"]
    assert any(
        p["type"] == "site_issue" and p.get("status") == "open" and p["since"] == wait["start"]
        for p in site_events
    )
    assert any(
        p["type"] == "site_issue" and p["payload"].get("start") == wait["start"]
        for p in site_events
        if "payload" in p
    )
    # the operator is told it was not their idle time
    assert any(
        m["type"] == "insight" and m["payload"]["key"] == "insight.truck_wait_not_you"
        for m in run.cab
    )
    assert any(m["type"] == "dispatch" for m in run.site)


def test_worker_near_escalates_caution_danger_critical(run) -> None:
    beat = at(run, "09:30")
    window = (beat, beat + timedelta(minutes=5))
    raised = [
        e
        for e in events(run, "alert", None, *window)
        if e["code"].startswith("PROXIMITY_") and e["payload"].get("phase") == "raised"
    ]
    order = [e["code"] for e in raised]
    assert order[:3] == ["PROXIMITY_CAUTION", "PROXIMITY_DANGER", "PROXIMITY_CRITICAL"]
    assert [e["priority"] for e in raised[:3]] == ["P3", "P2", "P1"]
    assert raised[2]["shared_with_supervisor"]  # P1 is shared with the supervisor
    cab_alerts = [m["payload"] for m in run.cab if m["type"] == "alert"]
    assert any(a.get("rule_id") == "PROXIMITY_CRITICAL" for a in cab_alerts)


def test_seatbelt_p1(run) -> None:
    beat = at(run, "10:20")
    p1 = [
        e
        for e in events(run, "alert", None, beat, beat + timedelta(minutes=1))
        if e["code"].startswith("SEATBELT_") and e["priority"] == "P1"
    ]
    assert p1, "no P1 seatbelt alert"
    assert any(
        m["type"] == "alert" and m["payload"].get("rule_id", "").startswith("SEATBELT_")
        for m in run.cab
    )


def test_heat_turns_risk_amber(run) -> None:
    """The heat beat: the scripted heat index reaches 43 °C at 10:45 and 45 °C at 11:00."""
    changes = events(run, "risk_band_change", "amber", at(run, "10:30"), at(run, "11:05"))
    heat_led = [e for e in changes if e["payload"]["top"][0][0] == "heat"]
    assert heat_led, f"no heat-led amber band change: {[e['payload'] for e in changes]}"
    assert any(m["type"] == "risk_update" and m["payload"]["band"] == "amber" for m in run.cab)


def test_step_out_unattended_running(run) -> None:
    beat = at(run, "11:40")
    segs = events(run, "idle_segment", "UNATTENDED_RUNNING", beat, beat + timedelta(minutes=15))
    assert segs, "no UNATTENDED_RUNNING segment"
    seg = segs[0]["payload"]
    assert datetime.fromisoformat(seg["start"]) - beat < timedelta(minutes=2)
    assert seg["duration_s"] >= 5 * 60
    assert events(run, "alert", "UNATTENDED_RUNNING", beat, beat + timedelta(minutes=10))


def test_near_miss_report(run) -> None:
    nm = events(run, "near_miss", None, at(run, "12:10"), at(run, "12:15"))
    assert len(nm) == 1 and nm[0]["shared_with_supervisor"]
    types = [r["draft"]["type"] for r in run.reports]
    assert "near_miss" in types


def test_offline_outbox_grows_then_drains(run) -> None:
    off, on = at(run, "13:00"), at(run, "13:08")
    before = [n for ts, _online, n in run.outbox if ts <= off]
    during = [(online, n) for ts, online, n in run.outbox if off < ts < on]  # after the beat
    after = [n for ts, _online, n in run.outbox if on <= ts <= on + timedelta(minutes=2)]
    assert during and all(not online for online, _ in during)
    assert max(n for _, n in during) > before[-1], "the outbox did not grow while offline"
    assert after[-1] == 0, "the outbox did not drain after reconnecting"
    assert run.outbox[-1][2] == 0
    # the report filed offline queued, then reached the fleet
    offline_reports = [r for r in run.reports if r["draft"]["type"] == "equipment_problem"]
    assert len(offline_reports) == 1 and offline_reports[0]["synced"]
    sent = {r["report_id"] for r in run.fleet_received["reports"]}
    assert {r["report_id"] for r in run.reports} <= sent


def test_uploads_respect_privacy(run) -> None:
    """Only shared events (or reports the operator chose to file) leave the machine."""
    for e in run.fleet_received["events"]:
        assert e["shared_with_supervisor"] or e["type"] in ("incident", "near_miss")
    assert set(run.fleet_received) <= {"intervals", "events", "reports", "tasks"}
    assert run.fleet_received["intervals"]
    ids = [r["record_id"] for r in run.fleet_received["intervals"]]
    assert len(ids) == len(set(ids))


def test_channels_are_ordered_and_start_with_a_snapshot(run) -> None:
    for messages in (run.cab, run.site):
        assert messages[0]["type"] == "snapshot"
        seqs = [m["seq"] for m in messages]
        assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))
    kinds = {m["type"] for m in run.cab}
    assert {"telemetry", "mode", "alert", "idle_segment", "risk_update", "sync"} <= kinds
    assert {"entities", "site_event", "dispatch"} <= {m["type"] for m in run.site}


def test_determinism(run, run2) -> None:
    assert run.event_log() == run2.event_log()
    assert [b["fired"] for b in run.beats] == [b["fired"] for b in run2.beats]
    for kind in ("intervals", "events", "reports", "tasks"):
        a = [r.get("record_id") or r.get("event_id") for r in run.fleet_received.get(kind, [])]
        b = [r.get("record_id") or r.get("event_id") for r in run2.fleet_received.get(kind, [])]
        assert a == b
