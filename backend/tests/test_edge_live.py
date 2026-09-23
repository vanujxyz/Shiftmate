"""Edge Gateway live parts (milestone 8): WebSocket channels, outbox sync, model download and the
camera proximity override (TRD §9.1, §9.3).

A fake fleet service (an `httpx.MockTransport`) stands in for milestone 9's Fleet Service; tests
can make it fail, and it can serve estimation models. Like the API tests, this runs without
generated history or models; the model-download tests train three tiny boosters in a temp folder.
"""

import json
import re
from collections import defaultdict
from types import SimpleNamespace

import httpx
import lightgbm as lgb
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from shiftmate.edge.app import create_app
from shiftmate.edge.resources import EdgeResources
from shiftmate.edge.sync import SyncWorker
from shiftmate.schema.enums import EventType

QUANTILES = (0.1, 0.5, 0.9)


class FakeFleet:
    """Accepts uploads (or fails with 503 when told to) and serves estimation models."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.fail = False
        self.received: dict[str, list[dict]] = defaultdict(list)
        self.posts = 0
        self.latest: str | None = None
        self.files: dict[str, dict[str, bytes]] = {}  # version → file name → bytes
        self.unserved: set[str] = set()  # file names listed in the manifest but not served

    def handler(self, request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if self.fail:
            return httpx.Response(503, json={"error": {"code": "unavailable", "message": "down"}})
        if path.startswith("/ingest/"):
            self.posts += 1
            body = json.loads(request.content)
            self.received[path.removeprefix("/ingest/")].extend(body["records"])
            return httpx.Response(200, json={"accepted": len(body["records"])})
        if path == "/models/estimation/latest" and self.latest:
            return httpx.Response(
                200, json={"version": self.latest, "files": sorted(self.files[self.latest])}
            )
        m = re.fullmatch(r"/models/estimation/([^/]+)/files/([^/]+)", path)
        if m and m[2] in self.files.get(m[1], {}) and m[2] not in self.unserved:
            return httpx.Response(200, content=self.files[m[1]][m[2]])
        return httpx.Response(404, json={"error": {"code": "not_found", "message": path}})


@pytest.fixture(scope="module")
def fleet():
    return FakeFleet()


@pytest.fixture(scope="module")
def app(tmp_path_factory, fleet):
    tmp = tmp_path_factory.mktemp("edge_live")
    return create_app(
        history_dir=tmp / "history",
        models_dir=tmp / "models",
        db_path=tmp / "edge.db",
        cache_dir=tmp / "cache",
        autorun=False,
        fleet_transport=httpx.MockTransport(fleet.handler),
    )


@pytest.fixture(scope="module")
def client(app):
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def _fresh(fleet, app):
    fleet.reset()
    player = app.state.ctx.player
    if not player.online:  # only when a test left it off (toggling queues a message)
        player.set_network(True)
    yield


def ctx(app):
    return app.state.ctx


def receive_until(ws, kind: str, limit: int = 500) -> list[dict]:
    """Messages up to and including the first of `kind`."""
    out = []
    for _ in range(limit):
        out.append(ws.receive_json())
        if out[-1]["type"] == kind:
            return out
    raise AssertionError(f"no {kind} message in {limit}")


def run_world(app, seconds: int, wall: float) -> None:
    """What the clock task does, in the app's event loop: settle, advance, pump."""
    c = ctx(app)
    c.feeds.pump(wall)
    c.player.advance(seconds, wall=wall, auto=True)
    c.feeds.pump(wall + 2.0)


# --- WebSocket channels ---------------------------------------------------------------------


def test_cab_socket_snapshot_then_ordered_messages(client, app) -> None:
    with client.websocket_connect("/ws/cab/EXC001") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot" and first["seq"] >= 1
        snap = first["payload"]
        assert snap["loaded"] and snap["machine_id"] == "EXC001" and snap["online"] is True
        client.portal.call(run_world, app, 30, 5000.0)
        msgs = receive_until(ws, "telemetry")
        seqs = [first["seq"]] + [m["seq"] for m in msgs]
        assert seqs == list(range(seqs[0], seqs[0] + len(seqs)))  # in order, nothing skipped
        t = msgs[-1]
        assert t["machine_id"] == "EXC001" and t["site_id"] == "CHN-HWY-01"
        assert t["payload"]["machine_id"] == "EXC001" and "risk_band" in t["payload"]


def test_unknown_machine_or_site_closes_4404(client) -> None:
    for url in ("/ws/cab/NOPE01", "/ws/cab/EXC002", "/ws/site/NOPE"):
        with pytest.raises(WebSocketDisconnect) as exc, client.websocket_connect(url) as ws:
            ws.receive_json()
        assert exc.value.code == 4404


def test_site_socket_entities(client, app) -> None:
    with client.websocket_connect("/ws/site/CHN-HWY-01") as ws:
        first = ws.receive_json()
        assert first["type"] == "snapshot"
        machines = first["payload"]["entities"]["machines"]
        assert len(machines) == 12 and sum(m["focus"] for m in machines) == 1
        client.portal.call(run_world, app, 10, 6000.0)
        ent = receive_until(ws, "entities")[-1]["payload"]
        assert {"machines", "trucks", "workers", "ts"} <= set(ent)


def test_network_toggle_reaches_the_cab(client) -> None:
    with client.websocket_connect("/ws/cab/EXC001") as ws:
        ws.receive_json()  # snapshot
        client.post("/demo/network", json={"online": False})
        msgs = receive_until(ws, "connectivity")
        assert msgs[-1]["payload"] == {"online": False}
        sync = [m["payload"] for m in msgs if m["type"] == "sync"]  # sent just before
        assert sync and sync[-1]["online"] is False and "outbox_size" in sync[-1]
        client.post("/demo/network", json={"online": True})


# --- outbox sync ----------------------------------------------------------------------------


def _shared_event(app, code: str = "test") -> None:
    c = ctx(app)
    c.site.runtime.record(EventType.SITE_ISSUE, c.site.now, code, {"test": True}, shared=True)


async def test_sync_drains_outbox(app, fleet) -> None:
    c = ctx(app)
    _shared_event(app)
    assert c.sync.outbox_size() > 0
    assert await c.sync.sync_once()
    assert c.sync.outbox_size() == 0
    assert any(e["code"] == "test" for e in fleet.received["events"])
    assert c.sync.last_error is None and c.sync.last_sync is not None


async def test_sync_backs_off_then_recovers(app, fleet) -> None:
    c = ctx(app)
    sync = c.sync
    _shared_event(app, "backoff")
    pending = sync.outbox_size()
    fleet.fail = True
    wall = 10_000.0
    sync.next_attempt = 0.0
    waits = []
    for _ in range(6):
        await sync.tick(wall)
        waits.append(sync.next_attempt - wall)
        wall = sync.next_attempt
    assert waits == [5, 10, 20, 40, 60, 60]  # edge.yaml: interval 5 s, doubling, max 60 s
    assert sync.last_error == "fleet replied 503"
    assert sync.outbox_size() == pending  # nothing is marked synced on failure
    fleet.fail = False
    await sync.tick(wall)
    assert sync.outbox_size() == 0 and sync.failures == 0 and sync.last_error is None
    assert sync.next_attempt - wall == 5


async def test_offline_outbox_grows_and_nothing_is_sent(app, fleet) -> None:
    c = ctx(app)
    await c.sync.sync_once()  # start empty
    c.player.set_network(False)
    before = c.sync.outbox_size()
    _shared_event(app, "while_offline")
    await c.sync.tick(20_000.0)
    assert c.sync.outbox_size() == before + 1 and fleet.posts == 0
    c.player.set_network(True)
    c.sync.next_attempt = 0.0
    await c.sync.tick(20_001.0)
    assert c.sync.outbox_size() == 0
    assert any(e["code"] == "while_offline" for e in fleet.received["events"])


async def test_sync_only_sends_what_privacy_allows(app, fleet) -> None:
    c = ctx(app)
    c.player.advance(20 * 60, wall=0.0, auto=True)  # closes at least one interval record
    _shared_event(app, "privacy")
    assert c.store.outbox_size(["interval"]) > 0
    events_only = SimpleNamespace(
        cfg=SimpleNamespace(
            edge=c.cfg.edge, privacy=SimpleNamespace(fleet_upload=["events_shared"])
        ),
        store=c.store,
        player=c.player,
        feeds=None,
        resources=c.resources,
    )
    worker = SyncWorker(events_only, "http://fleet", c.sync.cache_dir, c.sync.transport)
    assert worker.kinds == ["event", "report"]
    assert await worker.sync_once()
    assert set(fleet.received) <= {"events", "reports"} and fleet.received["events"]
    assert c.store.outbox_size(["interval"]) > 0  # intervals stay on the machine
    await c.sync.sync_once()  # the real worker (intervals allowed) sends them
    assert fleet.received["intervals"]


# --- estimation model download ----------------------------------------------------------------


def _tiny_model(version: str) -> dict[str, bytes]:
    """Three small quantile boosters and a manifest, as the fleet would publish them."""
    rng = np.random.default_rng(0)
    X = pd.DataFrame({"a": rng.random(60)})
    y = rng.random(60)
    files = {}
    for alpha in QUANTILES:
        params = {
            "objective": "quantile",
            "alpha": alpha,
            "min_data_in_leaf": 5,
            "num_threads": 1,
            "verbose": -1,
        }
        booster = lgb.train(params, lgb.Dataset(X, y), num_boost_round=3)
        files[f"q{int(alpha * 100):02d}.txt"] = booster.model_to_string().encode()
    manifest = {"version": version, "features": ["a"], "categorical": {}, "quantiles": QUANTILES}
    files["manifest.json"] = json.dumps(manifest).encode()
    return files


async def test_model_download_swaps_and_failures_keep_the_model(app, fleet, tmp_path) -> None:
    c = ctx(app)
    res = c.resources
    latest_file = c.sync.cache_dir / "estimation" / "LATEST"

    fleet.files["est-test-2"] = _tiny_model("est-test-2")
    fleet.latest = "est-test-2"
    assert await c.sync.check_model() == "est-test-2"
    assert res.estimation.version == "est-test-2" and res.estimation_source == "fleet"
    assert latest_file.read_text(encoding="utf-8") == "est-test-2"
    assert await c.sync.check_model() is None  # already up to date

    # a broken download (unreadable booster) is not used, and LATEST still names the good one
    broken = _tiny_model("est-test-3")
    broken["q50.txt"] = b"not a model"
    fleet.files["est-test-3"] = broken
    fleet.latest = "est-test-3"
    assert await c.sync.check_model() is None
    assert res.estimation.version == "est-test-2"
    assert latest_file.read_text(encoding="utf-8") == "est-test-2"

    # a file the fleet cannot serve, or the fleet being down, changes nothing either
    fleet.files["est-test-4"] = _tiny_model("est-test-4")
    fleet.latest = "est-test-4"
    fleet.unserved = {"q90.txt"}
    assert await c.sync.check_model() is None
    fleet.fail = True
    assert await c.sync.check_model() is None
    assert res.estimation.version == "est-test-2"
    assert latest_file.read_text(encoding="utf-8") == "est-test-2"

    # the next start uses the cached download, even with no fleet and no bundled model
    again = EdgeResources.load(c.cfg, tmp_path / "h", tmp_path / "m", c.sync.cache_dir)
    assert again.estimation.version == "est-test-2" and again.estimation_source == "cache"

    # a cache whose LATEST points at a broken model must not stop the edge from starting
    latest_file.write_text("est-test-3", encoding="utf-8")
    (c.sync.cache_dir / "estimation" / "est-test-3").mkdir(parents=True, exist_ok=True)
    for name, data in broken.items():
        (c.sync.cache_dir / "estimation" / "est-test-3" / name).write_bytes(data)
    started = EdgeResources.load(c.cfg, tmp_path / "h", tmp_path / "m", c.sync.cache_dir)
    assert started.estimation is None
    latest_file.write_text("est-test-2", encoding="utf-8")


def test_sync_status_shows_the_model(client, app) -> None:
    s = client.get("/sync/status").json()
    res = ctx(app).resources
    assert s["estimation_model"] == (res.estimation.version if res.estimation else None)
    assert s["estimation_source"] == res.estimation_source


# --- camera proximity -----------------------------------------------------------------------


def test_fresh_camera_reading_overrides_the_sensor(app) -> None:
    c = ctx(app)
    site = c.site
    rt = site.runtime
    rt.camera_reading(2.5, 0.9, 10.0, wall=500.0)
    site.step(500.4)  # 0.4 s old: the camera wins
    assert rt.last_tick["proximity_source"] == "camera"
    assert rt.last_tick["proximity_m"] == 2.5
    assert rt.telemetry(rt.last_step, rt.last_tick)["proximity_source"] == "camera"
    site.step(501.6)  # 1.6 s old: the machine's own sensor is back
    assert rt.last_tick.get("proximity_source") != "camera"
    rt.camera_reading(2.5, 0.9, 10.0, wall=600.0)
    site.step(0.0)  # fast-forward / seek (wall 0): a real-time camera never counts
    assert rt.last_tick.get("proximity_source") != "camera"
    rt.camera = None


def test_camera_endpoint_feeds_the_runtime(client, app) -> None:
    c = ctx(app)
    r = client.post(
        "/proximity/camera",
        json={"machine_id": "EXC001", "distance_m": 3.1, "confidence": 0.8, "bearing_deg": 0},
    )
    assert r.json()["ok"]
    c.site.step(c.wall())
    assert c.site.runtime.last_tick["proximity_source"] == "camera"
    assert c.site.runtime.last_tick["proximity_m"] == 3.1
    c.site.runtime.camera = None
