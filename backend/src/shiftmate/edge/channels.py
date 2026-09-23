"""Live WebSocket channels of the Edge Gateway (TRD §9.1).

Two channels:
- `/ws/cab/{machine_id}` — everything the cab screen needs about its machine;
- `/ws/site/{site_id}` — the supervisor's live map: entities (5 Hz), dispatch log, site events.

How messages flow:
1. The world runs in the clock task. The runtime, the live site and the scenario player append
   plain `{type, payload}` messages to their queues as things happen (every world second).
2. After each clock step, `Feeds.pump()` drains those queues, wraps each message in the TRD §9
   envelope `{type, seq, ts, machine_id, site_id, payload}` and hands it to the `Hub`.
3. The `Hub` copies it into the queue of every connected socket on that channel; each socket's
   writer task sends from its own queue, so one slow client never holds up the world.

Rates: at 60× many world seconds pass per real second, but a screen only needs the latest
telemetry, so `telemetry` is sent at `edge.yaml → feeds.telemetry_hz` (latest value wins) and
provisional idle-segment updates are coalesced the same way. Everything else (alerts, mode
changes, segments that close, insights, lesson offers) is sent in order, every time.

On connect, and whenever the demo loads or seeks (the world is replaced), a `snapshot` message
carries the full current state, so a client that reconnects never shows stale data.
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from shiftmate.edge.app import EdgeContext

log = logging.getLogger(__name__)

QUEUE_SIZE = 1000  # per socket; if a client falls this far behind, the oldest messages are dropped
LATEST_ONLY = {"telemetry"}  # only the newest matters to a screen


class Subscriber:
    """One connected socket: its outgoing queue."""

    def __init__(self) -> None:
        self.queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=QUEUE_SIZE)
        self.dropped = 0

    def offer(self, message: dict[str, Any]) -> None:
        if self.queue.full():
            self.queue.get_nowait()  # drop the oldest; the next snapshot/telemetry catches up
            self.dropped += 1
        self.queue.put_nowait(message)


class Hub:
    """Connected sockets per channel and a sequence number per channel."""

    def __init__(self) -> None:
        self.subscribers: dict[str, set[Subscriber]] = defaultdict(set)
        self.seq: dict[str, int] = defaultdict(int)

    def subscribe(self, channel: str) -> Subscriber:
        sub = Subscriber()
        self.subscribers[channel].add(sub)
        return sub

    def unsubscribe(self, channel: str, sub: Subscriber) -> None:
        self.subscribers[channel].discard(sub)

    def envelope(
        self,
        channel: str,
        kind: str,
        payload: dict[str, Any],
        ts: datetime | None,
        machine_id: str | None,
        site_id: str | None,
    ) -> dict[str, Any]:
        self.seq[channel] += 1
        return {
            "type": kind,
            "seq": self.seq[channel],
            "ts": ts.isoformat() if ts else None,
            "machine_id": machine_id,
            "site_id": site_id,
            "payload": payload,
        }

    def publish(
        self,
        channel: str,
        kind: str,
        payload: dict[str, Any],
        ts: datetime | None,
        machine_id: str | None = None,
        site_id: str | None = None,
        only: Subscriber | None = None,
    ) -> dict[str, Any] | None:
        subs = [only] if only else list(self.subscribers.get(channel, ()))
        if not subs:
            return None  # nobody listening: no sequence number used
        env = self.envelope(channel, kind, payload, ts, machine_id, site_id)
        for sub in subs:
            sub.offer(env)
        return env


def cab_channel(machine_id: str) -> str:
    return f"cab:{machine_id}"


def site_channel(site_id: str) -> str:
    return f"site:{site_id}"


class Feeds:
    """Turns what the world produced since the last pump into channel messages."""

    def __init__(self, ctx: EdgeContext) -> None:
        self.ctx = ctx
        self.hub = Hub()
        self._site_obj: object | None = None  # the LiveSite we last pumped (changes on load/seek)
        self._last_telemetry_wall = -1e9
        self._last_entities_wall = -1e9
        self._pending_telemetry: dict[str, Any] | None = None
        self._last_estimate_sim: datetime | None = None
        self._estimate_due = True

    # --- snapshots ---------------------------------------------------------------------------
    def cab_snapshot(self) -> dict[str, Any]:
        ctx = self.ctx
        site = ctx.player.site
        if site is None:
            return {"loaded": False}
        rt = site.runtime
        step = rt.last_step
        alerts = rt.pipeline.alerts.snapshot() if rt.pipeline.alerts else None
        return {
            "loaded": True,
            "machine_id": site.focus_id,
            "operator_id": rt.operator_id,
            "language": rt.language.value,
            "telemetry": rt.telemetry(step, rt.last_tick) if step and rt.last_tick else None,
            "mode": step.state.mode.value if step else None,
            "alerts": alerts,
            "online": ctx.player.online,
            "sync": ctx.sync.status_payload() if ctx.sync else None,
            "captions": ctx.player.captions,
            "waiting_for": ctx.player.waiting_for,
        }

    def site_snapshot(self) -> dict[str, Any]:
        site = self.ctx.player.site
        if site is None:
            return {"loaded": False}
        return {
            "loaded": True,
            "entities": site.entities(),
            "focus_machine": site.focus_id,
            "online": self.ctx.player.online,
        }

    def send_snapshots(self) -> None:
        site = self.ctx.player.site
        if site is None:
            return
        now = site.now
        self.hub.publish(
            cab_channel(site.focus_id), "snapshot", self.cab_snapshot(), now, site.focus_id
        )
        self.hub.publish(
            site_channel(site.site.site_id),
            "snapshot",
            self.site_snapshot(),
            now,
            site_id=site.site.site_id,
        )

    # --- the pump ------------------------------------------------------------------------------
    def pump(self, wall: float) -> None:
        """Called after every clock step (and after demo actions that change the world)."""
        ctx = self.ctx
        site = ctx.player.site
        if site is None:
            return
        if site is not self._site_obj:  # a new world (load or seek): everyone resynchronises
            self._site_obj = site
            self._pending_telemetry = None
            self._last_estimate_sim = None
            self._estimate_due = True
            site.runtime.drain()
            site.runtime.drain_site()
            ctx.player.drain_events()
            self.send_snapshots()
            return
        machine_id = site.focus_id
        site_id = site.site.site_id
        cab = cab_channel(machine_id)
        now = site.now

        latest_provisional: dict[str, Any] | None = None
        for m in site.runtime.drain():
            kind, payload = m["type"], m["payload"]
            if kind in LATEST_ONLY:
                self._pending_telemetry = payload
            elif kind == "idle_segment" and payload.get("provisional"):
                latest_provisional = payload
            else:
                if kind == "idle_segment":
                    latest_provisional = None  # the segment closed; its provisional is stale
                if kind == "task_progress":
                    self._estimate_due = True
                self.hub.publish(cab, kind, payload, now, machine_id, site_id)
        if latest_provisional is not None:
            self.hub.publish(cab, "idle_segment", latest_provisional, now, machine_id, site_id)

        for e in ctx.player.drain_events():
            self._player_event(e, cab, now, machine_id, site_id)

        telemetry_period = 1.0 / ctx.cfg.edge.feeds.telemetry_hz
        if (
            self._pending_telemetry is not None
            and wall - self._last_telemetry_wall >= telemetry_period
        ):
            self.hub.publish(cab, "telemetry", self._pending_telemetry, now, machine_id, site_id)
            self._pending_telemetry = None
            self._last_telemetry_wall = wall

        self._maybe_estimate(cab, now, machine_id, site_id)

        sc = site_channel(site_id)
        for m in site.runtime.drain_site():
            self.hub.publish(sc, m["type"], m["payload"], now, site_id=site_id)
        entities_period = 1.0 / ctx.cfg.edge.feeds.site_entities_hz
        if self.hub.subscribers.get(sc) and wall - self._last_entities_wall >= entities_period:
            self.hub.publish(sc, "entities", site.entities(), now, site_id=site_id)
            self._last_entities_wall = wall

    def _player_event(
        self, e: dict[str, Any], cab: str, now: datetime, machine_id: str, site_id: str
    ) -> None:
        kind, payload = e["type"], e["payload"]
        sc = site_channel(site_id)
        if kind == "scenario_caption":
            if self.ctx.player.captions:  # demo only, hidden unless the console turns it on
                self.hub.publish(cab, kind, payload, now, machine_id, site_id)
                self.hub.publish(sc, "demo", {"event": kind, **payload}, now, site_id=site_id)
        elif kind == "connectivity":
            self.hub.publish(cab, kind, payload, now, machine_id, site_id)
            self.hub.publish(sc, "demo", {"event": kind, **payload}, now, site_id=site_id)
        elif kind == "seeked":  # the world jumped: send the new state to everyone
            self.send_snapshots()
            self.hub.publish(sc, "demo", {"event": kind, **payload}, now, site_id=site_id)
        else:  # waiting, camera_beat, end_shift, scale_demo
            self.hub.publish(cab, "demo", {"event": kind, **payload}, now, machine_id, site_id)
            self.hub.publish(sc, "demo", {"event": kind, **payload}, now, site_id=site_id)

    def _maybe_estimate(self, cab: str, now: datetime, machine_id: str, site_id: str) -> None:
        """Live remaining time for the active task: on progress, else every N world seconds."""
        ctx = self.ctx
        if ctx.resources.estimation is None or not self.hub.subscribers.get(cab):
            return
        every = ctx.cfg.edge.feeds.estimate_update_sim_s
        due = self._estimate_due or (
            self._last_estimate_sim is None
            or (now - self._last_estimate_sim).total_seconds() >= every
        )
        if not due:
            return
        self._estimate_due = False
        self._last_estimate_sim = now
        payload = estimate_payload(ctx)
        self.hub.publish(cab, "estimate_update", payload, now, machine_id, site_id)

    def publish_sync(self, payload: dict[str, Any]) -> None:
        site = self.ctx.player.site
        if site is None:
            return
        self.hub.publish(
            cab_channel(site.focus_id),
            "sync",
            payload,
            site.now,
            site.focus_id,
            site.site.site_id,
        )


def estimate_payload(ctx: EdgeContext) -> dict[str, Any]:
    from shiftmate.edge.services import build_shift
    from shiftmate.schema.enums import TaskStatus

    shift = build_shift(ctx.cfg, ctx.resources, ctx.site)
    active = next((t for t in shift.tasks if t.task.status == TaskStatus.ACTIVE), None)
    return {
        "task_id": active.task.task_id if active else None,
        "estimate": active.estimate.model_dump(mode="json") if active and active.estimate else None,
        "likely_finish": shift.likely_finish.model_dump(mode="json")
        if shift.likely_finish
        else None,
    }
