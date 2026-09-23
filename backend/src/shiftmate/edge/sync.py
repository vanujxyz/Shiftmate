"""Outbox sync and model download: the only parts of the edge that need the network (TRD §9.3).

**Outbox sync.** Every `sync.interval_s` real seconds while the machine is online, the worker
takes up to `batch_size` unsynced outbox rows, groups them by kind and posts each group to the
fleet service:
    interval → POST /ingest/intervals     event  → POST /ingest/events
    report   → POST /ingest/reports       task   → POST /ingest/tasks
Only kinds that `privacy.yaml → fleet_upload` allows are ever sent (raw ticks never are). The
fleet ingests idempotently by record id, so sending a record twice (e.g. after a timeout) is
harmless. On a 2xx the rows are marked synced; on any failure nothing is marked and the next
attempt waits twice as long (5, 10, 20, 40, 60, 60 … seconds), back to normal after a success.
Real seconds, not world seconds: the network does not speed up when the demo does.

**Estimation model download.** Every `sync.model_check_s` while online (and once at start) the
worker asks the fleet for its latest estimation model. If it is newer than the one in use, the
files are downloaded into the edge cache (`data/edge/models/estimation/<version>/`), loaded and
swapped in. If the fleet cannot be reached the edge keeps using the cached model, or the bundled
one from `models/` — estimates never depend on the network.

The "network" is the demo's network toggle (`player.online`): when it is off, nothing is sent,
the outbox grows, and the cab shows that records are waiting.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time as _time
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from shiftmate.edge.app import EdgeContext

log = logging.getLogger(__name__)

ENDPOINTS = {
    "interval": "/ingest/intervals",
    "event": "/ingest/events",
    "report": "/ingest/reports",
    "task": "/ingest/tasks",
}
# privacy.yaml → fleet_upload names what may leave the machine; each outbox kind needs one.
KIND_PERMISSION = {
    "interval": "interval_summaries",
    "task": "task_summaries",
    "event": "events_shared",
    "report": "events_shared",  # a report is something the operator chose to share
}
LOOP_PERIOD_S = 0.5


class SyncWorker:
    def __init__(
        self,
        ctx: EdgeContext,
        base_url: str,
        cache_dir: Path,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.ctx = ctx
        self.cfg = ctx.cfg.edge.sync
        self.base_url = base_url
        self.cache_dir = cache_dir
        self.transport = transport
        allowed = set(ctx.cfg.privacy.fleet_upload)
        self.kinds = [k for k, perm in KIND_PERMISSION.items() if perm in allowed]
        self.last_sync: datetime | None = None
        self.last_error: str | None = None
        self.failures = 0
        self.next_attempt = 0.0  # wall clock
        self.next_model_check = 0.0
        self.synced_total = 0
        self._last_published: tuple[Any, ...] | None = None

    # --- status ----------------------------------------------------------------------------------
    def outbox_size(self) -> int:
        return self.ctx.store.outbox_size(self.kinds)

    def status_payload(self, synced_now: int = 0) -> dict[str, Any]:
        return {
            "online": self.ctx.player.online,
            "outbox_size": self.outbox_size(),
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "last_error": self.last_error,
            "synced_now": synced_now,
        }

    def publish_status(self, synced_now: int = 0, force: bool = False) -> None:
        """Tell the cab about the outbox when something changed (size, network, error)."""
        payload = self.status_payload(synced_now)
        key = (payload["online"], payload["outbox_size"], payload["last_error"])
        if force or synced_now or key != self._last_published:
            self._last_published = key
            if self.ctx.feeds is not None:
                self.ctx.feeds.publish_sync(payload)

    def backoff_s(self) -> float:
        return min(self.cfg.interval_s * (2 ** max(self.failures - 1, 0)), self.cfg.backoff_max_s)

    # --- the loop --------------------------------------------------------------------------------
    async def run(self) -> None:
        while True:
            await asyncio.sleep(LOOP_PERIOD_S)
            try:
                await self.tick(_time.monotonic())
            except Exception:  # never let the sync loop die; the cab shows last_error
                log.exception("sync tick failed")

    async def tick(self, wall: float) -> None:
        if not self.ctx.player.online:
            self.publish_status()
            return
        if wall >= self.next_model_check:
            self.next_model_check = wall + self.cfg.model_check_s
            await self.check_model()
        if wall < self.next_attempt:
            self.publish_status()
            return
        ok = await self.sync_once()
        self.next_attempt = wall + (self.cfg.interval_s if ok else self.backoff_s())

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url, timeout=self.cfg.timeout_s, transport=self.transport
        )

    def _sim_now(self) -> datetime:
        site = self.ctx.player.site
        return site.now if site is not None else datetime.now(UTC)

    async def sync_once(self) -> bool:
        """Post one batch per kind. True if everything pending in this round was accepted."""
        rows = self.ctx.store.outbox_pending(self.cfg.batch_size, self.kinds)
        if not rows:
            self.failures = 0
            self.last_error = None
            self.publish_status()
            return True
        groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for r in rows:
            groups[r["kind"]].append(r)
        synced = 0
        try:
            async with self._client() as client:
                for kind, items in groups.items():
                    body = {
                        "source": self.ctx.player.site.focus_id if self.ctx.player.site else None,
                        "records": [json.loads(r["payload"]) for r in items],
                    }
                    resp = await client.post(ENDPOINTS[kind], json=body)
                    resp.raise_for_status()
                    self.ctx.store.mark_synced([r["id"] for r in items], self._sim_now())
                    synced += len(items)
        except (httpx.HTTPError, OSError) as exc:
            self.failures += 1
            self.last_error = _short_error(exc)
            log.info("sync failed (%s); retry in %.0f s", self.last_error, self.backoff_s())
            self.publish_status(synced)
            return False
        self.failures = 0
        self.last_error = None
        self.last_sync = self._sim_now()
        self.synced_total += synced
        self.publish_status(synced)
        return True

    # --- estimation model ----------------------------------------------------------------------
    async def check_model(self) -> str | None:
        """Download a newer estimation model from the fleet. Returns the new version, if any."""
        res = self.ctx.resources
        current = res.estimation.version if res.estimation else None
        try:
            async with self._client() as client:
                resp = await client.get("/models/estimation/latest")
                resp.raise_for_status()
                manifest = resp.json()
                version = manifest["version"]
                if version == current:
                    return None
                target = self.cache_dir / "estimation" / version
                target.mkdir(parents=True, exist_ok=True)
                for name in manifest["files"]:
                    if "/" in name or "\\" in name or name.startswith("."):
                        raise ValueError(f"unsafe model file name {name!r}")
                    f = await client.get(f"/models/estimation/{version}/files/{name}")
                    f.raise_for_status()
                    (target / name).write_bytes(f.content)
        except (httpx.HTTPError, OSError, KeyError, ValueError) as exc:
            log.info("model check failed (%s); keeping %s", _short_error(exc), current)
            return None
        (self.cache_dir / "estimation" / "LATEST").write_text(version, encoding="utf-8")
        try:
            res.use_estimation_from(self.cache_dir, "fleet")
        except Exception:  # a broken download must never take estimates away
            log.exception("downloaded model %s failed to load; keeping %s", version, current)
            return None
        log.info("estimation model updated %s → %s", current, version)
        return version


def _short_error(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"fleet replied {exc.response.status_code}"
    if isinstance(exc, httpx.ConnectError | httpx.TimeoutException | OSError):
        return "fleet not reachable"
    return type(exc).__name__
