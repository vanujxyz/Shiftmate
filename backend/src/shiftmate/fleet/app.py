"""Fleet Service FastAPI app (TRD §9.2): the cloud side the edges upload to.

- **Ingest** `/ingest/{intervals,events,reports,tasks}` takes `{source, records}` (≤ 500
  records) and stores them idempotently (`fleet/store.py`).
- **Supervisor views** per site and local day: summary, where time is lost, safety, and
  privacy-respecting trends (`fleet/aggregates.py`).
- **Fleet views**: overview across sites and countries, fleet-learned patterns.
- **Model registry**: the latest estimation model and its files, which edges download.
- **Scale**: `/scale/stats` shows totals, the live ingest rate, the last scale run and runtime
  benchmark, and the labelled 1.6 M projection (`fleet/scale.py`).
- **`/ws/fleet`**: live ingest counters (at most `feeds.counters_hz`) and safety-critical site
  events as they arrive.

A new store is seeded with the simulated history (what the edges would have uploaded), so the
supervisor views have weeks of data before the live demo adds today.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import re
import time as _time
from collections.abc import AsyncIterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from fastapi import FastAPI, HTTPException, Query, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from shiftmate import __version__
from shiftmate.config_loader import ShiftMateConfig, load_config
from shiftmate.fleet import aggregates as agg
from shiftmate.fleet.scale import projection, read_scale_file
from shiftmate.fleet.store import FleetStore, local_day
from shiftmate.schema import HealthResponse
from shiftmate.schema.config import Site
from shiftmate.schema.fleet import (
    FleetOverview,
    FleetPattern,
    FleetSite,
    IdleCausesResponse,
    IngestKind,
    IngestRequest,
    IngestResponse,
    LiveIngest,
    ModelRef,
    SafetyResponse,
    ScaleStats,
    SiteInfo,
    SiteSummary,
    TrendsResponse,
)
from shiftmate.settings import get_settings
from shiftmate.util.api import install_common

log = logging.getLogger(__name__)
SAFE_NAME = re.compile(r"^[A-Za-z0-9_.-]+$")
LIVE_WINDOW_S = 60
LIVE_EVENT_TYPES = {"incident", "near_miss", "site_issue"}


class FleetHub:
    """`/ws/fleet` subscribers, with ingest counters sent at most `counters_hz` times a second."""

    def __init__(self, counters_hz: float) -> None:
        self.subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self.seq = 0
        self.period = 1.0 / counters_hz
        self.last_counters = -1e9
        self.pending: dict[str, Any] | None = None

    def publish(self, kind: str, payload: dict[str, Any]) -> None:
        if not self.subscribers:
            return
        self.seq += 1
        msg = {
            "type": kind,
            "seq": self.seq,
            "ts": datetime.now(UTC).isoformat(),
            "payload": payload,
        }
        for q in list(self.subscribers):
            if q.full():
                q.get_nowait()  # a slow client loses the oldest message, never blocks ingest
            q.put_nowait(msg)

    def counters(self, payload: dict[str, Any], wall: float, force: bool = False) -> None:
        self.pending = payload
        if force or wall - self.last_counters >= self.period:
            self.flush(wall)

    def flush(self, wall: float) -> None:
        if self.pending is not None:
            self.publish("ingest", self.pending)
            self.pending = None
            self.last_counters = wall


def create_app(
    cfg: ShiftMateConfig | None = None,
    db_path: Path | None = None,
    history_dir: Path | None = None,
    models_dir: Path | None = None,
    seed: bool | None = None,
    autorun: bool = True,
) -> FastAPI:
    """Build the app. `db_path=None` uses `data/fleet/fleet.duckdb`; pass a temp path in tests."""
    settings = get_settings()
    cfg = cfg or load_config()
    data_dir = settings.resolve(settings.data_dir)
    history_dir = history_dir or data_dir / "history"
    models_dir = models_dir or settings.resolve(settings.models_dir)
    db_path = db_path or data_dir / "fleet" / "fleet.duckdb"
    scale_file = db_path.parent / "scale.json"
    store = FleetStore(db_path)
    _load_roster(cfg, store, history_dir)
    if (cfg.fleet.ingest.seed_from_history if seed is None else seed) and store.is_empty():
        counts = store.seed_from_history(history_dir)
        if counts:
            log.info("fleet store seeded from history: %s", counts)
    hub = FleetHub(cfg.fleet.feeds.counters_hz)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        task = asyncio.create_task(_flush_loop(hub)) if autorun else None
        yield
        if task:
            task.cancel()
        store.close()

    app = FastAPI(title="ShiftMate Fleet Service", version=__version__, lifespan=lifespan)
    app.state.store = store
    app.state.hub = hub
    app.state.cfg = cfg
    install_common(app)
    _routes(app, cfg, store, hub, models_dir, scale_file)
    return app


async def _flush_loop(hub: FleetHub) -> None:
    while True:
        await asyncio.sleep(hub.period)
        hub.flush(_time.monotonic())


def _load_roster(cfg: ShiftMateConfig, store: FleetStore, history_dir: Path) -> None:
    """The fleet owns the roster: from history if generated, else the same deterministic fleet."""
    if (history_dir / "machines.parquet").exists() and (history_dir / "operators.parquet").exists():
        machines = pd.read_parquet(history_dir / "machines.parquet")
        operators = pd.read_parquet(history_dir / "operators.parquet")
    else:
        from shiftmate.sim.history import build_history_fleet

        fleet = build_history_fleet(cfg, 7)
        machines = pd.DataFrame([m.model_dump(mode="json") for m in fleet.machines])
        operators = pd.DataFrame([o.model_dump(mode="json") for o in fleet.operators])
    store.load_roster(machines, operators)


def _routes(
    app: FastAPI,
    cfg: ShiftMateConfig,
    store: FleetStore,
    hub: FleetHub,
    models_dir: Path,
    scale_file: Path,
) -> None:
    def site_or_404(site_id: str) -> Site:
        if site_id not in cfg.sites:
            raise HTTPException(404, f"Unknown site {site_id}.")
        return cfg.sites[site_id]

    def resolve_day(site: Site, day: date | None) -> date:
        """The requested local day, or the latest day with data, or today at the site."""
        if day is not None:
            return day
        last = store.interval_span(site.site_id)[1]
        if last is not None:
            return agg.as_date(last, site.timezone)  # type: ignore[return-value]
        return pd.Timestamp.now(tz=site.timezone).date()

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        return HealthResponse(service="fleet", status="ok", version=__version__)

    # --- ingest ----------------------------------------------------------------------------------
    @app.post("/ingest/{kind}", response_model=IngestResponse)
    async def ingest(kind: IngestKind, body: IngestRequest, request: Request) -> IngestResponse:
        if len(body.records) > cfg.fleet.ingest.max_batch:
            raise HTTPException(413, f"At most {cfg.fleet.ingest.max_batch} records per request.")
        handler = {
            "intervals": store.ingest_intervals,
            "events": store.ingest_events,
            "reports": store.ingest_reports,
            "tasks": store.ingest_tasks,
        }[kind]
        result = handler(body.records, body.source)
        nbytes = int(request.headers.get("content-length") or 0)
        store.log_ingest(kind, body.source, result["received"], result["inserted"], nbytes)
        if kind == "events" and result["inserted"]:
            for r in body.records:
                if r.get("priority") == "P1" or r.get("type") in LIVE_EVENT_TYPES:
                    hub.publish("site_event", _live_event(r))
        hub.counters(
            {
                "kind": kind,
                "source": body.source,
                "received": result["received"],
                "inserted": result["inserted"],
                "totals": store.totals(),
                "records_last_60s": store.recent_ingest(LIVE_WINDOW_S),
            },
            _time.monotonic(),
        )
        return IngestResponse(**result)

    # --- sites -----------------------------------------------------------------------------------
    @app.get("/sites", response_model=list[SiteInfo])
    async def sites() -> list[SiteInfo]:
        out = []
        for site in cfg.sites.values():
            first, last = store.interval_span(site.site_id)
            out.append(
                SiteInfo(
                    site_id=site.site_id,
                    name=site.name,
                    country=site.country,
                    timezone=site.timezone,
                    machines=len(store.machines(site.site_id)),
                    first_date=agg.as_date(first, site.timezone),
                    last_date=agg.as_date(last, site.timezone),
                )
            )
        return out

    @app.get("/sites/{site_id}/summary", response_model=SiteSummary)
    async def site_summary(site_id: str, date: date | None = None) -> SiteSummary:  # noqa: A002
        site = site_or_404(site_id)
        day = resolve_day(site, date)
        start, end = local_day(site.timezone, day)
        base_start = start - timedelta(days=cfg.fleet.summary.baseline_days)
        return agg.site_summary(
            cfg,
            site,
            day,
            store.machines(site_id),
            store.operators(),
            store.tasks(site_id, start, end),
            store.intervals(site_id, start, end),
            agg.baselines(cfg, store.done_tasks(base_start, start)),
        )

    @app.get("/sites/{site_id}/idle-causes", response_model=IdleCausesResponse)
    async def idle_causes(site_id: str, date: date | None = None) -> IdleCausesResponse:  # noqa: A002
        site = site_or_404(site_id)
        day = resolve_day(site, date)
        start, end = local_day(site.timezone, day)
        back, _ = local_day(site.timezone, day - timedelta(days=cfg.fleet.idle_causes.similar_days))
        return agg.idle_causes(
            cfg,
            site,
            day,
            store.intervals(site_id, start, end),
            store.intervals(site_id, back, start),
            store.tasks(site_id, back, end),
        )

    @app.get("/sites/{site_id}/safety", response_model=SafetyResponse)
    async def safety(site_id: str, date: date | None = None) -> SafetyResponse:  # noqa: A002
        site = site_or_404(site_id)
        day = resolve_day(site, date)
        start, end = local_day(site.timezone, day)
        return agg.safety(
            cfg,
            site,
            day,
            store.events(site_id, start, end),
            store.reports(site_id, start, end),
            store.intervals(site_id, start, end),
            store.operators(),
        )

    @app.get("/sites/{site_id}/trends", response_model=TrendsResponse)
    async def trends(site_id: str, days: int | None = Query(None, ge=1)) -> TrendsResponse:
        site = site_or_404(site_id)
        t = cfg.fleet.trends
        n = min(days or t.default_days, t.max_days)
        first, last = agg.day_window(resolve_day(site, None), n)
        start, _ = local_day(site.timezone, first)
        _, end = local_day(site.timezone, last)
        return agg.trends(
            cfg,
            site,
            n,
            store.intervals(site_id, start, end),
            store.events(site_id, start, end),
            store.operators(),
        )

    # --- fleet -----------------------------------------------------------------------------------
    @app.get("/fleet/overview", response_model=FleetOverview)
    async def overview() -> FleetOverview:
        roster = store.machines()
        tiles = []
        for site in cfg.sites.values():
            m = roster[roster.site_id == site.site_id]
            last = store.interval_span(site.site_id)[1]
            latest = agg.as_date(last, site.timezone)
            bands: dict[str, int] = {"green": 0, "amber": 0, "red": 0}
            active, ground, heat = 0, None, None
            if latest is not None:
                start, end = local_day(site.timezone, latest)
                iv = store.intervals(site.site_id, start, end)
                if len(iv):
                    ends = iv.sort_values("timestamp").groupby("machine_id").tail(1)
                    active = int(iv.machine_id.nunique())
                    for s in ends.risk_score_max:
                        band = agg.risk_band(cfg, s)
                        if band:
                            bands[band] += 1
                    newest = iv.sort_values("timestamp").iloc[-1]
                    ground = (
                        newest.ground_condition
                        if isinstance(newest.ground_condition, str)
                        else None
                    )
                    heat = None if pd.isna(newest.heat_index_c) else float(newest.heat_index_c)
            tiles.append(
                FleetSite(
                    site_id=site.site_id,
                    name=site.name,
                    country=site.country,
                    timezone=site.timezone,
                    latest_date=latest,
                    machines_total=len(m),
                    machines_active=active,
                    by_type=m.machine_type.value_counts().to_dict() if len(m) else {},
                    by_tier=m.sensor_tier.value_counts().to_dict() if len(m) else {},
                    risk_bands=bands,
                    ground_condition=ground,
                    heat_index_c=heat,
                    last_ingest=store.last_ingest(site.site_id),
                )
            )
        return FleetOverview(
            sites=tiles,
            machines_total=len(roster),
            by_type=roster.machine_type.value_counts().to_dict() if len(roster) else {},
            by_tier=roster.sensor_tier.value_counts().to_dict() if len(roster) else {},
            records=store.site_totals(),
            scale_machines=store.scale_machines(),
        )

    @app.get("/fleet/patterns", response_model=list[FleetPattern])
    async def patterns() -> list[FleetPattern]:
        path = models_dir / "fleet_patterns.json"
        if not path.exists():
            return []  # not trained yet: the console says so rather than inventing patterns
        return [FleetPattern(**p) for p in json.loads(path.read_text(encoding="utf-8"))]

    # --- model registry --------------------------------------------------------------------------
    def model_dir(version: str) -> Path:
        if not SAFE_NAME.match(version):
            raise HTTPException(404, "Unknown model version.")
        d = models_dir / "estimation" / version
        if not (d / "manifest.json").exists():
            raise HTTPException(404, f"Unknown model version {version}.")
        return d

    @app.get("/models/estimation/latest", response_model=ModelRef)
    async def model_latest() -> ModelRef:
        latest = models_dir / "estimation" / "LATEST"
        if not latest.exists():
            raise HTTPException(404, "No estimation model has been trained yet.")
        version = latest.read_text(encoding="utf-8").strip()
        d = model_dir(version)
        files = sorted(p.name for p in d.iterdir() if p.is_file() and SAFE_NAME.match(p.name))
        manifest = json.loads((d / "manifest.json").read_text(encoding="utf-8"))
        return ModelRef(version=version, files=files, manifest=manifest)

    @app.get("/models/estimation/{version}/files/{name}")
    async def model_file(version: str, name: str) -> FileResponse:
        d = model_dir(version)
        path = d / name
        if not SAFE_NAME.match(name) or not path.is_file():
            raise HTTPException(404, f"No file {name} in {version}.")
        return FileResponse(path)

    # --- scale -----------------------------------------------------------------------------------
    @app.get("/scale/stats", response_model=ScaleStats)
    async def scale_stats() -> ScaleStats:
        run, bench = read_scale_file(scale_file)
        recent = store.recent_ingest(LIVE_WINDOW_S)
        return ScaleStats(
            totals=store.totals(),
            scale_machines=store.scale_machines(),
            live=LiveIngest(
                records_last_60s=recent, records_per_s=round(recent / LIVE_WINDOW_S, 1)
            ),
            run=run,
            bench=bench,
            projection=projection(cfg, run, bench),
        )

    # --- live ------------------------------------------------------------------------------------
    @app.websocket("/ws/fleet")
    async def ws_fleet(ws: WebSocket) -> None:
        await ws.accept()
        q: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=1000)
        hub.subscribers.add(q)
        await ws.send_json(
            {
                "type": "snapshot",
                "seq": hub.seq,
                "ts": datetime.now(UTC).isoformat(),
                "payload": {
                    "totals": store.totals(),
                    "records_last_60s": store.recent_ingest(LIVE_WINDOW_S),
                    "scale_machines": store.scale_machines(),
                },
            }
        )

        async def reader() -> None:
            while True:
                await ws.receive_text()

        read_task = asyncio.create_task(reader())
        try:
            while True:
                get = asyncio.create_task(q.get())
                done, _ = await asyncio.wait({get, read_task}, return_when=asyncio.FIRST_COMPLETED)
                if read_task in done:
                    get.cancel()
                    break
                await ws.send_json(get.result())
        except (WebSocketDisconnect, RuntimeError):
            pass
        finally:
            read_task.cancel()
            hub.subscribers.discard(q)


def _live_event(r: dict[str, Any]) -> dict[str, Any]:
    """What `/ws/fleet` shows for a new safety-critical event (operator only when shared)."""
    return {
        "event_id": r.get("event_id"),
        "ts": r.get("ts"),
        "site_id": r.get("site_id"),
        "machine_id": r.get("machine_id"),
        "type": r.get("type"),
        "priority": r.get("priority"),
        "code": r.get("code"),
    }
