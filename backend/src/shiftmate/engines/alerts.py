"""Alert policy: what the operator sees, hears and must acknowledge (TRD §4.6, §6.8;
PRD F-SAFE-08, F-SAFE-09; DESIGN AlertQueue).

Rules, in plain words:
1. **One interrupting alert at a time.** P1 (full-screen takeover) and P2 (banner) interrupt;
   only one is on screen.
2. **Pre-emption.** A higher priority replaces a lower one at once; the lower one waits in the
   queue. At equal priority the newest wins, except that a proximity alert is never pushed aside
   by a non-proximity alert of the same priority.
3. **Low priority waits for a pause.** P3 (strip) and P4 (feed) are held while the machine is
   working and delivered when it is paused. Rules shown live on the proximity gauge
   (`live_in_rail_while_working`, D-007) are held the same way, and dropped to the feed as history
   if they are no longer true when the machine pauses.
4. **Dedupe.** The same rule raised again within 30 s is ignored (cooldowns are applied earlier,
   in the Safety engine).
5. **Queue hygiene.** When an alert's turn comes, it is shown only if its condition is still true;
   otherwise it goes to the feed as history. The queue is re-checked every 30 s.
6. **Acknowledge.** P1 and P2 need an acknowledgement ("I've stopped" / "Seen"). If a P1's
   condition is still true 3 s after acknowledgement, it returns as a *reduced* P1 (rail segment
   plus a tone every 5 s) until the condition clears.
7. **Escalation.** A P1 not acknowledged within 20 s is escalated: repeated tone, louder voice and
   shared with the supervisor.
The engine returns messages for the cab and events for the store; it keeps no clock of its own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from shiftmate.engines.safety import RaisedAlert, SafetyOutput
from shiftmate.schema.config import AlertPolicyConfig
from shiftmate.schema.enums import CabMode, EventType, Priority

RANK = {Priority.P1: 0, Priority.P2: 1, Priority.P3: 2, Priority.P4: 3}
INTERRUPTING = (Priority.P1, Priority.P2)
FEED_LIMIT = 50


@dataclass
class AlertInstance:
    alert_id: str
    rule_id: str
    priority: Priority
    message_key: str
    category: str
    raised_at: datetime
    status: str = "new"  # showing | queued | held | strip | feed | acknowledged | reduced | cleared
    active: bool = True  # the underlying condition is still true
    acked_at: datetime | None = None
    escalated: bool = False
    not_before: datetime | None = None  # "Later" on a P3 strip
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class AlertUpdate:
    messages: list[dict[str, Any]] = field(default_factory=list)  # for the cab channel
    events: list[dict[str, Any]] = field(default_factory=list)  # for the local store / outbox


class AlertPolicyEngine:
    def __init__(self, policy: AlertPolicyConfig, machine_id: str) -> None:
        self.policy = policy
        self.machine_id = machine_id
        self.current: AlertInstance | None = None
        self.queue: list[AlertInstance] = []
        self.strip: AlertInstance | None = None
        self.feed: list[AlertInstance] = []
        self.watch: list[AlertInstance] = []  # acknowledged P1s waiting for the 3 s re-check
        self.reduced: dict[str, AlertInstance] = {}
        self.last_raised: dict[str, datetime] = {}
        self.last_queue_check: datetime | None = None
        self.mode = CabMode.PAUSED

    # --- views -------------------------------------------------------------------------------
    def view(self, a: AlertInstance) -> dict[str, Any]:
        p = self.policy.priorities[a.priority]
        return {
            "alert_id": a.alert_id,
            "rule_id": a.rule_id,
            "priority": a.priority.value,
            "message_key": a.message_key,
            "category": a.category,
            "raised_at": a.raised_at.isoformat(),
            "status": a.status,
            "presentation": "reduced" if a.status == "reduced" else p.presentation,
            "sound": p.sound,
            "speak": p.speak and a.status == "showing",
            "requires_ack": p.requires_ack,
            "escalated": a.escalated,
            "queued_count": len([q for q in self.queue if q.status == "queued"]),
            "context": a.context,
        }

    def snapshot(self) -> dict[str, Any]:
        queued = [q for q in self.queue if q.status in ("queued", "held")]
        best = min(queued, key=lambda q: RANK[q.priority]) if queued else None
        return {
            "current": self.view(self.current) if self.current else None,
            "strip": self.view(self.strip) if self.strip else None,
            "reduced": [self.view(a) for a in self.reduced.values()],
            "queue_count": len(queued),
            "queue_top_priority": best.priority.value if best else None,
            "feed": [self.view(a) for a in self.feed[-10:]],
        }

    # --- helpers -----------------------------------------------------------------------------
    def _event(self, kind: EventType, a: AlertInstance, ts: datetime, **payload: Any) -> dict:
        shared = a.priority in self.policy.supervisor_share
        return {
            "ts": ts,
            "type": kind.value,
            "priority": a.priority.value,
            "code": a.rule_id,
            "shared_with_supervisor": shared,
            "payload": {"alert_id": a.alert_id, "message_key": a.message_key, **payload},
        }

    def _to_feed(self, a: AlertInstance, out: AlertUpdate) -> None:
        a.status = "feed"
        self.feed.append(a)
        del self.feed[:-FEED_LIMIT]
        out.messages.append({"type": "alert_feed", "payload": self.view(a)})

    def _show(self, a: AlertInstance, out: AlertUpdate) -> None:
        a.status = "showing"
        self.current = a
        if a in self.queue:
            self.queue.remove(a)
        out.messages.append({"type": "alert", "payload": self.view(a)})

    def _enqueue(self, a: AlertInstance, status: str = "queued") -> None:
        a.status = status
        if a not in self.queue:
            self.queue.append(a)

    def _beats(self, new: AlertInstance, current: AlertInstance) -> bool:
        if RANK[new.priority] != RANK[current.priority]:
            return RANK[new.priority] < RANK[current.priority]
        # newest wins, unless it would push a proximity alert aside
        return not (current.category == "proximity" and new.category != "proximity")

    def _promote(self, ts: datetime, out: AlertUpdate) -> None:
        """Show the best queued interrupting alert whose condition is still true."""
        while self.current is None:
            candidates = [
                q for q in self.queue if q.status == "queued" and q.priority in INTERRUPTING
            ]
            if not candidates:
                return
            best = min(
                candidates,
                key=lambda q: (
                    RANK[q.priority],
                    q.category != "proximity",
                    -q.raised_at.timestamp(),
                ),
            )
            self.queue.remove(best)
            if best.active:
                self._show(best, out)
            else:
                self._to_feed(best, out)

    def _deliver_paused(self, ts: datetime, out: AlertUpdate) -> None:
        held = [q for q in self.queue if q.status == "held"]
        for a in sorted(held, key=lambda q: q.raised_at):
            if a.not_before and ts < a.not_before:
                continue
            self.queue.remove(a)
            if not a.active or a.priority == Priority.P4:
                self._to_feed(a, out)
                continue
            if self.strip is not None:
                self._to_feed(self.strip, out)  # a newer P3 replaces the older one
            a.status = "strip"
            self.strip = a
            out.messages.append({"type": "alert", "payload": self.view(a)})

    # --- main update -------------------------------------------------------------------------
    def update(
        self,
        ts: datetime,
        mode: CabMode,
        safety: SafetyOutput,
        contexts: dict[str, dict[str, Any]] | None = None,
    ) -> AlertUpdate:
        out = AlertUpdate()
        contexts = contexts or {}
        self.mode = mode

        # 1. conditions that stopped
        for rule_id in safety.cleared:
            for a in [
                self.current,
                self.strip,
                *self.queue,
                *self.watch,
                self.reduced.get(rule_id),
            ]:
                if a is not None and a.rule_id == rule_id:
                    a.active = False
            if self.current and self.current.rule_id == rule_id:
                a = self.current
                a.status = "cleared"
                self.current = None
                out.messages.append({"type": "alert_cleared", "payload": self.view(a)})
                out.events.append(self._event(EventType.ALERT_CLEARED, a, ts))
            if rule_id in self.reduced:
                a = self.reduced.pop(rule_id)
                a.status = "cleared"
                out.messages.append({"type": "alert_cleared", "payload": self.view(a)})
                out.events.append(self._event(EventType.ALERT_CLEARED, a, ts))
            if self.strip and self.strip.rule_id == rule_id and self.strip.priority != Priority.P3:
                self._to_feed(self.strip, out)
                self.strip = None
            self.watch = [w for w in self.watch if w.rule_id != rule_id]

        # 2. new alerts
        for raised in safety.raised:
            self._raise(raised, ts, mode, contexts.get(raised.rule_id, {}), out)

        # 3. acknowledged P1s still true after 3 s come back reduced
        for a in list(self.watch):
            if a.acked_at and (ts - a.acked_at).total_seconds() >= self.policy.ack_recheck_s:
                self.watch.remove(a)
                if a.active:
                    a.status = "reduced"
                    self.reduced[a.rule_id] = a
                    out.messages.append({"type": "alert", "payload": self.view(a)})

        # 4. escalation of an unacknowledged P1
        cur = self.current
        esc = self.policy.priorities[Priority.P1].escalate_after_s
        if (
            cur is not None
            and cur.priority == Priority.P1
            and not cur.escalated
            and esc is not None
            and (ts - cur.raised_at).total_seconds() >= esc
        ):
            cur.escalated = True
            out.messages.append({"type": "alert", "payload": self.view(cur)})
            ev = self._event(EventType.ALERT, cur, ts, phase="escalated")
            ev["shared_with_supervisor"] = True
            out.events.append(ev)

        # 5. queue hygiene every 30 s: inactive interrupting alerts become history
        if (
            self.last_queue_check is None
            or (ts - self.last_queue_check).total_seconds() >= self.policy.queue_reevaluate_s
        ):
            self.last_queue_check = ts
            for q in [q for q in self.queue if q.status == "queued" and not q.active]:
                self.queue.remove(q)
                self._to_feed(q, out)

        # 6. fill the screen and deliver held advice when paused
        self._promote(ts, out)
        if mode == CabMode.PAUSED:
            self._deliver_paused(ts, out)
        return out

    def _raise(
        self,
        raised: RaisedAlert,
        ts: datetime,
        mode: CabMode,
        context: dict[str, Any],
        out: AlertUpdate,
    ) -> None:
        last = self.last_raised.get(raised.rule_id)
        if last is not None and (ts - last).total_seconds() < self.policy.dedupe_window_s:
            return
        self.last_raised[raised.rule_id] = ts
        a = AlertInstance(
            alert_id=f"{self.machine_id}-{raised.rule_id}-{int(ts.timestamp() * 1000)}",
            rule_id=raised.rule_id,
            priority=raised.priority,
            message_key=raised.message_key,
            category=raised.category,
            raised_at=ts,
            context=context,
        )
        out.events.append(self._event(EventType.ALERT, a, ts, phase="raised", **context))
        # a reduced P1 for the same rule is replaced by the new full alert
        self.reduced.pop(raised.rule_id, None)
        if a.priority in INTERRUPTING:
            if self.current is None:
                self._show(a, out)
            elif self._beats(a, self.current):
                bumped = self.current
                self.current = None
                self._enqueue(bumped)
                out.messages.append({"type": "alert_queued", "payload": self.view(bumped)})
                self._show(a, out)
            else:
                self._enqueue(a)
                out.messages.append({"type": "alert_queued", "payload": self.view(a)})
            return
        # P3 / P4: held while working (and while paused they are delivered in step 6)
        self._enqueue(a, status="held")

    # --- operator actions --------------------------------------------------------------------
    def acknowledge(self, alert_id: str, ts: datetime, action: str = "ack") -> AlertUpdate:
        """ "I've stopped" (P1), "Seen" (P2), "Done" or "Later" (P3)."""
        out = AlertUpdate()
        cur = self.current
        if cur is not None and cur.alert_id == alert_id:
            cur.status = "acknowledged"
            cur.acked_at = ts
            self.current = None
            if cur.priority == Priority.P1:
                self.watch.append(cur)
            out.messages.append({"type": "alert_cleared", "payload": self.view(cur)})
            reaction = (ts - cur.raised_at).total_seconds()
            out.events.append(
                self._event(EventType.ALERT_ACK, cur, ts, reaction_s=round(reaction, 1))
            )
            self._promote(ts, out)
            return out
        if self.strip is not None and self.strip.alert_id == alert_id:
            a = self.strip
            self.strip = None
            if action == "later" and a.active:
                a.not_before = ts + timedelta(minutes=self.policy.p3_snooze_min)
                self._enqueue(a, status="held")
            else:
                self._to_feed(a, out)
            out.messages.append({"type": "alert_cleared", "payload": self.view(a)})
            return out
        for a in self.reduced.values():
            if a.alert_id == alert_id:
                out.events.append(self._event(EventType.ALERT_ACK, a, ts, phase="reduced"))
        return out
