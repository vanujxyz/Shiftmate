"""Alert policy: one interrupting alert, pre-emption, queueing, dedupe, paused delivery,
acknowledgement, reduced P1 and escalation (TRD §6.8, DESIGN AlertQueue, D-007)."""

from datetime import UTC, datetime, timedelta

from hypothesis import given, settings
from hypothesis import strategies as st

from shiftmate.config_loader import get_config
from shiftmate.engines.alerts import AlertPolicyEngine
from shiftmate.engines.safety import RaisedAlert, SafetyOutput
from shiftmate.schema.enums import CabMode, Priority

T0 = datetime(2026, 9, 24, 9, 30, tzinfo=UTC)
W, P = CabMode.WORKING, CabMode.PAUSED


def policy():
    return AlertPolicyEngine(get_config().alert_policy, "EXC001")


def raised(rule_id, priority, category="general", ts=T0):
    return RaisedAlert(rule_id, Priority(priority), f"alert.{rule_id.lower()}", category, ts)


def step(engine, ts, mode=W, raise_=(), clear=(), active=()):
    return engine.update(ts, mode, SafetyOutput(list(raise_), list(clear), set(active)))


def test_p1_preempts_p2_which_returns_after_ack() -> None:
    e = policy()
    step(e, T0, raise_=[raised("UNATTENDED_RUNNING", "P2", "unattended")])
    assert e.current.rule_id == "UNATTENDED_RUNNING"
    t1 = T0 + timedelta(seconds=1)
    step(e, t1, raise_=[raised("SEATBELT_MOVING", "P1", "seatbelt", t1)])
    assert e.current.rule_id == "SEATBELT_MOVING"
    assert [q.rule_id for q in e.queue] == ["UNATTENDED_RUNNING"]
    e.acknowledge(e.current.alert_id, t1 + timedelta(seconds=2))
    assert e.current.rule_id == "UNATTENDED_RUNNING"  # still true, so it comes back


def test_lower_priority_waits_behind_p1() -> None:
    e = policy()
    step(e, T0, raise_=[raised("PROXIMITY_CRITICAL", "P1", "proximity")])
    step(e, T0, raise_=[raised("FATIGUE_LIMIT", "P2", "fatigue")])
    assert e.current.rule_id == "PROXIMITY_CRITICAL"
    assert e.snapshot()["queue_count"] == 1


def test_proximity_not_displaced_by_same_priority_non_proximity() -> None:
    e = policy()
    step(e, T0, raise_=[raised("PROXIMITY_DANGER", "P2", "proximity")])
    step(e, T0 + timedelta(seconds=1), raise_=[raised("FATIGUE_LIMIT", "P2", "fatigue")])
    assert e.current.rule_id == "PROXIMITY_DANGER"
    step(e, T0 + timedelta(seconds=2), raise_=[raised("HEAT_NO_BREAK", "P2", "heat")])
    assert e.current.rule_id == "PROXIMITY_DANGER"


def test_newest_wins_at_equal_priority() -> None:
    e = policy()
    step(e, T0, raise_=[raised("FATIGUE_LIMIT", "P2", "fatigue")])
    step(e, T0 + timedelta(seconds=1), raise_=[raised("PROXIMITY_DANGER", "P2", "proximity")])
    assert e.current.rule_id == "PROXIMITY_DANGER"


def test_dedupe_within_30_seconds() -> None:
    e = policy()
    out1 = step(e, T0, raise_=[raised("FATIGUE_LIMIT", "P2", "fatigue")])
    out2 = step(e, T0 + timedelta(seconds=10), raise_=[raised("FATIGUE_LIMIT", "P2", "fatigue")])
    assert len([m for m in out1.events if m["type"] == "alert"]) == 1
    assert out2.events == []


def test_p3_held_while_working_and_delivered_when_paused() -> None:
    e = policy()
    step(e, T0, raise_=[raised("FATIGUE_WARN", "P3", "fatigue")], active={"FATIGUE_WARN"})
    assert e.strip is None and e.snapshot()["queue_count"] == 1
    step(e, T0 + timedelta(seconds=40), mode=P, active={"FATIGUE_WARN"})
    assert e.strip is not None and e.strip.rule_id == "FATIGUE_WARN"


def test_caution_no_longer_true_goes_to_feed_not_strip() -> None:
    # D-007: caution shows live on the gauge; a late strip would be misleading
    e = policy()
    step(e, T0, raise_=[raised("PROXIMITY_CAUTION", "P3", "proximity")])
    step(e, T0 + timedelta(seconds=20), clear=["PROXIMITY_CAUTION"])
    step(e, T0 + timedelta(seconds=60), mode=P)
    assert e.strip is None
    assert [f.rule_id for f in e.feed] == ["PROXIMITY_CAUTION"]


def test_newer_p3_replaces_older_which_moves_to_feed() -> None:
    e = policy()
    step(e, T0, mode=P, raise_=[raised("FATIGUE_WARN", "P3", "fatigue")])
    step(e, T0 + timedelta(seconds=5), mode=P, raise_=[raised("RISK_BAND_RAISED", "P3", "risk")])
    assert e.strip.rule_id == "RISK_BAND_RAISED"
    assert [f.rule_id for f in e.feed] == ["FATIGUE_WARN"]


def test_p1_ack_then_reduced_while_still_true_then_cleared() -> None:
    e = policy()
    step(e, T0, raise_=[raised("PROXIMITY_CRITICAL", "P1", "proximity")])
    alert_id = e.current.alert_id
    ack = e.acknowledge(alert_id, T0 + timedelta(seconds=2))
    assert [ev["type"] for ev in ack.events] == ["alert_ack"]
    assert ack.events[0]["payload"]["reaction_s"] == 2.0
    step(e, T0 + timedelta(seconds=4))
    assert "PROXIMITY_CRITICAL" not in e.reduced  # re-check happens 3 s after ack
    out = step(e, T0 + timedelta(seconds=5))
    assert e.reduced["PROXIMITY_CRITICAL"].status == "reduced"
    assert out.messages[-1]["payload"]["presentation"] == "reduced"
    out = step(e, T0 + timedelta(seconds=9), clear=["PROXIMITY_CRITICAL"])
    assert e.reduced == {}
    assert [m["type"] for m in out.messages] == ["alert_cleared"]


def test_seatbelt_p1_clears_itself_when_belt_latches() -> None:
    e = policy()
    step(e, T0, raise_=[raised("SEATBELT_MOVING", "P1", "seatbelt")])
    out = step(e, T0 + timedelta(seconds=6), clear=["SEATBELT_MOVING"])
    assert e.current is None
    assert [ev["type"] for ev in out.events] == ["alert_cleared"]


def test_unacknowledged_p1_escalates_after_20s_and_is_shared() -> None:
    e = policy()
    step(e, T0, raise_=[raised("SEATBELT_MOVING", "P1", "seatbelt")])
    out = step(e, T0 + timedelta(seconds=19))
    assert not e.current.escalated
    out = step(e, T0 + timedelta(seconds=20))
    assert e.current.escalated
    esc = [ev for ev in out.events if ev["payload"].get("phase") == "escalated"]
    assert esc and esc[0]["shared_with_supervisor"]


def test_queued_alert_that_stopped_becomes_history() -> None:
    e = policy()
    step(e, T0, raise_=[raised("PROXIMITY_CRITICAL", "P1", "proximity")])
    step(e, T0, raise_=[raised("HEAT_NO_BREAK", "P2", "heat")])
    step(e, T0 + timedelta(seconds=3), clear=["HEAT_NO_BREAK"])
    e.acknowledge(e.current.alert_id, T0 + timedelta(seconds=4))
    assert e.current is None
    assert [f.rule_id for f in e.feed] == ["HEAT_NO_BREAK"]


def test_p1_and_p2_are_shared_with_supervisor_p3_is_not() -> None:
    e = policy()
    out = step(
        e,
        T0,
        raise_=[
            raised("SEATBELT_MOVING", "P1", "seatbelt"),
            raised("FATIGUE_WARN", "P3", "fatigue"),
        ],
    )
    shared = {ev["code"]: ev["shared_with_supervisor"] for ev in out.events}
    assert shared == {"SEATBELT_MOVING": True, "FATIGUE_WARN": False}


RULES = [
    ("SEATBELT_MOVING", "P1", "seatbelt"),
    ("PROXIMITY_CRITICAL", "P1", "proximity"),
    ("PROXIMITY_DANGER", "P2", "proximity"),
    ("UNATTENDED_RUNNING", "P2", "unattended"),
    ("FATIGUE_WARN", "P3", "fatigue"),
    ("RISK_BAND_RAISED", "P3", "risk"),
]


@settings(max_examples=60, deadline=None)
@given(
    st.lists(
        st.tuples(
            st.sampled_from(["raise", "clear", "ack", "pause", "work"]),
            st.integers(0, len(RULES) - 1),
        ),
        max_size=40,
    )
)
def test_never_more_than_one_interrupting_alert(actions) -> None:
    e = policy()
    ts = T0
    mode = W
    for action, i in actions:
        ts += timedelta(seconds=7)
        rule_id, prio, cat = RULES[i]
        if action == "raise":
            step(e, ts, mode, raise_=[raised(rule_id, prio, cat, ts)])
        elif action == "clear":
            step(e, ts, mode, clear=[rule_id])
        elif action == "ack" and e.current is not None:
            e.acknowledge(e.current.alert_id, ts)
        else:
            mode = P if action == "pause" else W
            step(e, ts, mode)
        showing = [a for a in [e.current, *e.queue] if a is not None and a.status == "showing"]
        assert len(showing) <= 1
        if e.current is not None:
            queued_p1 = [q for q in e.queue if q.status == "queued" and q.priority == "P1"]
            if e.current.priority == "P2":
                assert not [q for q in queued_p1 if q.active]
