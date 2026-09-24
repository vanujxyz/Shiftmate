"""Headless scenario run: the whole Edge Gateway, driven by a fake clock, with no browser (TRD §8).

This is how we check that Ravi's shift behaves as PRD §9 describes without anyone watching:

1. Build the real app (`create_app`) with the clock and sync loops off, and a fake fleet service
   (an `httpx.MockTransport`) that accepts every upload and remembers what it received.
2. Subscribe to both live channels (`cab:EXC001`, `site:CHN-HWY-01`) like a cab and a console.
3. Loop on a fake wall clock in 0.1 s steps, doing exactly what the app's clock task does:
   advance the player `speed × 0.1` world seconds, pump the feeds, and tick the sync worker.
4. Play Ravi through the real REST API: sign in when the scenario waits for sign-in, speak a
   near-miss report when it waits for one (parse, then save — the same calls the cab makes), and
   report an equipment problem while the internet is down, so it has to queue (PRD §9 beat 10).
5. Stop at the end-of-shift beat and return everything that happened: beat times, store events,
   channel messages, the outbox size over time and what the fake fleet received.

Nothing here reads ground truth; it only watches what the edge itself produced. Everything is
deterministic: the world is seeded and the fake clock replaces real time.
"""

from __future__ import annotations

import json
import tempfile
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from shiftmate.config_loader import ShiftMateConfig, load_config
from shiftmate.edge.channels import cab_channel, site_channel

WALL_STEP_S = 0.1  # the app's clock period (edge/app.py CLOCK_PERIOD_S)
WALL_START = 1000.0  # any positive number: the runtime treats wall > 0 as "running live"
NEAR_MISS_TRANSCRIPT = "I almost hit a worker near the truck at LOAD-A, he walked behind the bucket"
# PRD §9 beat 10: while the internet is down, Ravi reports a problem and it waits in the outbox.
OFFLINE_REPORT_TRANSCRIPT = "Small hydraulic oil leak under the boom, please check at the break"


@dataclass
class FakeFleet:
    """Stands in for the Fleet Service: accepts every ingest, has no newer model."""

    received: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    online: bool = True

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path.startswith("/ingest/") and request.method == "POST":
            body = json.loads(request.content)
            self.received.setdefault(path.removeprefix("/ingest/"), []).extend(body["records"])
            return httpx.Response(200, json={"accepted": len(body["records"])})
        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


@dataclass
class HeadlessResult:
    scenario: str
    beats: list[dict[str, Any]]  # {id, at (scheduled), fired (sim time), caption}
    events: list[dict[str, Any]]  # the store's event log, in time order
    cab: list[dict[str, Any]]  # every cab channel envelope, in order
    site: list[dict[str, Any]]  # every site channel envelope, in order
    outbox: list[tuple[datetime, bool, int]]  # (sim time, online, outbox size) after each step
    fleet_received: dict[str, list[dict[str, Any]]]
    reports: list[dict[str, Any]]
    wall_steps: int

    def beat(self, beat_id: str) -> dict[str, Any]:
        return next(b for b in self.beats if b["id"] == beat_id)

    def event_log(self) -> list[tuple[Any, ...]]:
        """The comparable part of the event log (for the determinism check)."""
        return [
            (e["event_id"], e["ts"], e["type"], e["code"], json.dumps(e["payload"], sort_keys=True))
            for e in self.events
        ]


async def run_headless(
    scenario: str = "ravi_shift",
    speed: float = 60.0,
    cfg: ShiftMateConfig | None = None,
    workdir: Path | None = None,
    history_dir: Path | None = None,
    models_dir: Path | None = None,
    on_beat: Callable[[dict[str, Any]], None] | None = None,
    fleet_transport: httpx.AsyncBaseTransport | None = None,
) -> HeadlessResult:
    """Play `scenario` start to end at `speed`× on a fake clock. See the module docstring.

    `fleet_transport` sends uploads to a real Fleet Service app (e.g. `httpx.ASGITransport`)
    instead of the fake one; `fleet_received` is then empty and the fleet holds the records.
    """
    from shiftmate.edge.app import create_app  # imported here: app imports this package

    cfg = cfg or load_config()
    with tempfile.TemporaryDirectory(
        prefix="shiftmate-headless-", ignore_cleanup_errors=True
    ) as tmp:
        work = workdir or Path(tmp)
        fleet = FakeFleet()
        app = create_app(
            cfg=cfg,
            history_dir=history_dir,
            models_dir=models_dir,
            db_path=work / "edge.db",
            scenario=scenario,
            autorun=False,
            cache_dir=work / "cache",
            fleet_transport=fleet_transport or fleet.transport(),
        )
        ctx = app.state.ctx
        player, feeds, sync = ctx.player, ctx.feeds, ctx.sync
        site = player.site
        assert site is not None and player.scenario is not None
        cab_sub = feeds.hub.subscribe(cab_channel(site.focus_id))
        site_sub = feeds.hub.subscribe(site_channel(site.site.site_id))
        cab: list[dict[str, Any]] = []
        site_msgs: list[dict[str, Any]] = []
        outbox: list[tuple[datetime, bool, int]] = []
        beats: list[dict[str, Any]] = []
        captions = {b.id: b for b in player.scenario.beats}

        def collect() -> None:
            for sub, sink in ((cab_sub, cab), (site_sub, site_msgs)):
                while not sub.queue.empty():
                    sink.append(sub.queue.get_nowait())

        def note_beats() -> None:
            for beat_id in [b.id for b in player.scenario.beats]:
                if beat_id in player.fired and all(b["id"] != beat_id for b in beats):
                    b = captions[beat_id]
                    row = {
                        "id": beat_id,
                        "at": b.at.strftime("%H:%M"),
                        # the world moves in 1 s steps and a beat fires on the first step at or
                        # after its time, so it fired exactly at its scheduled time
                        "fired": player.site.local(b.at),
                        "caption": (b.caption or {}).get("en"),
                    }
                    beats.append(row)
                    if on_beat:
                        on_beat(row)

        api = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://edge")
        wall = WALL_START
        steps = 0
        offline_report_done = False
        end_at = player.site.local(max(b.at for b in player.scenario.beats))
        try:
            feeds.pump(wall)  # first pump: snapshots to both channels
            player.speed = speed
            player.beat_speeds = False  # a headless run keeps its speed through every beat
            player.playing = True
            while True:
                wall += WALL_STEP_S
                steps += 1
                player.tick_wall(WALL_STEP_S, wall)
                feeds.pump(wall)
                await sync.tick(wall)
                collect()
                note_beats()
                outbox.append((player.site.now, player.online, sync.outbox_size()))
                if player.waiting_for:
                    await _operator_acts(api, player)
                if not player.online and not offline_report_done:
                    await _report(api, OFFLINE_REPORT_TRANSCRIPT)
                    offline_report_done = True
                if not player.playing:  # the end_shift beat pauses the demo
                    break
                if player.site.now > end_at and "end_shift" not in player.fired:
                    raise RuntimeError("scenario ran past its last beat without ending")
            # let the outbox drain after the last beat, as a parked tablet would
            for _ in range(int(3 * cfg.edge.sync.interval_s / WALL_STEP_S)):
                wall += WALL_STEP_S
                await sync.tick(wall)
            collect()
            outbox.append((player.site.now, player.online, sync.outbox_size()))
        finally:
            await api.aclose()
            feeds.hub.unsubscribe(cab_channel(site.focus_id), cab_sub)
            feeds.hub.unsubscribe(site_channel(site.site.site_id), site_sub)

        result = HeadlessResult(
            scenario=scenario,
            beats=beats,
            events=ctx.store.list_events(),
            cab=cab,
            site=site_msgs,
            outbox=outbox,
            fleet_received=fleet.received,
            reports=ctx.store.list_reports(limit=100),
            wall_steps=steps,
        )
        ctx.store.engine.dispose()  # release the SQLite file (Windows keeps open files locked)
        return result


async def _operator_acts(api: httpx.AsyncClient, player) -> None:
    """What Ravi does when the scenario waits for him (the cab's own REST calls)."""
    scenario = player.scenario
    site = player.site
    if player.waiting_for == "sign_in":
        r = await api.post(
            "/session/sign-in",
            json={
                "operator_id": scenario.operator,
                "machine_id": site.focus_id,
                "badge": f"SHIFTMATE:{scenario.operator}",
                "language": scenario.language.value,
            },
        )
        r.raise_for_status()
    elif player.waiting_for == "near_miss":
        await _report(api, NEAR_MISS_TRANSCRIPT)


async def _report(api: httpx.AsyncClient, transcript: str) -> None:
    """A spoken report: parse the transcript, then save the draft with its auto-filled context."""
    parsed = await api.post("/reports/parse", json={"transcript": transcript, "language": "en"})
    parsed.raise_for_status()
    body = parsed.json()
    saved = await api.post(
        "/reports",
        json={"draft": body["draft"], "context": body["context"], "transcript": transcript},
    )
    saved.raise_for_status()


def describe(result: HeadlessResult) -> list[str]:
    """Beat-by-beat lines for the CLI: each beat, then what the edge recorded until the next."""
    lines: list[str] = []
    fired = sorted(result.beats, key=lambda b: b["fired"])
    for i, b in enumerate(fired):
        start = b["fired"]
        end = fired[i + 1]["fired"] if i + 1 < len(fired) else None
        lines.append(f"{start:%H:%M:%S}  ▶ {b['id']:<12} {b['caption'] or ''}")
        counts: dict[str, int] = {}
        order: list[str] = []
        for e in result.events:
            ts = datetime.fromisoformat(e["ts"])
            if ts < start or (end is not None and ts >= end):
                continue
            key = " ".join(x for x in (e["type"], e["priority"], e["code"]) if x)
            if key not in counts:
                order.append(key)
            counts[key] = counts.get(key, 0) + 1
        for key in order:
            n = counts[key]
            lines.append(f"            · {key}" + (f" ×{n}" if n > 1 else ""))
        sizes = [
            size for ts, _on, size in result.outbox if ts >= start and (end is None or ts < end)
        ]
        if b["id"] in ("offline", "online") and sizes:
            lines.append(f"            · outbox {sizes[0]} → {sizes[-1]} (max {max(sizes)})")
    received = {k: len(v) for k, v in result.fleet_received.items()}
    lines.append(f"fleet received: {received}")
    lines.append(f"final outbox: {result.outbox[-1][2] if result.outbox else 0}")
    return lines
