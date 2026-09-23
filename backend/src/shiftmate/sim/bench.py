"""Runtime benchmark: many full MachineRuntimes on live 1 s ticks (TRD §7.6).

`shiftmate bench runtime --machines 200 --sim-minutes 30`

Every site of the history fleet runs as a live world (1 s ticks) from the start of its shift.
Each world tick is fed to the machine's runtime — the same `MachineRuntime` the Edge Gateway runs
(state, safety, risk, alerts, idle reasons, intervals, anomaly scoring, lessons) — and, to reach
`--machines`, several independent runtimes are fed the ticks of the same simulated machine.

Measured, on this computer:
- CPU time of `MachineRuntime.step` per machine per tick (mean and p95), without the world;
- memory per runtime (Python allocations traced while the runtimes are built and run their
  first minute — approximate);
- what the runtimes queue for upload (intervals and shared events): bytes and records per
  machine per hour — the per-machine footprint the 1.6 M projection uses.

Ticks go to the runtime only; the world's ground truth is dropped here (golden rule 5).
"""

from __future__ import annotations

import time
import tracemalloc
from datetime import UTC, date, datetime
from pathlib import Path

import numpy as np

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.edge.resources import EdgeResources
from shiftmate.edge.runtime import MachineRuntime
from shiftmate.edge.store import EdgeStore
from shiftmate.engines.dispatch_view import DispatchLogEntry, DispatchView
from shiftmate.engines.pipeline import TaskInfo
from shiftmate.schema.fleet import BenchResult
from shiftmate.sim.history import build_history_fleet
from shiftmate.sim.site import SiteWorld

BENCH_DAY = date(2026, 9, 24)  # the demo day; any day works
MEMORY_TICKS = 60  # memory is traced over the first minute only (tracing slows everything)
UPLOAD_KINDS = ["interval", "event"]


class _World:
    def __init__(self, cfg: ShiftMateConfig, site_id: str, index: int, fleet, seed: int, day_index):
        self.site = cfg.sites[site_id]
        self.world = SiteWorld(cfg, self.site, fleet, index, seed)
        self.state = self.world.begin_day(day_index, BENCH_DAY, 1.0)
        self.dispatch = DispatchView(cfg.idle_rules.params.dispatch_presence_timeout_min)
        self.cursor = 0
        start = datetime.combine(BENCH_DAY, self.site.shift.start, tzinfo=self.world.tz)
        while self.state.now < start:  # the world runs alone up to the shift start
            self.step()

    def step(self) -> dict[str, dict]:
        results = self.world.step()
        log = self.state.dispatcher.log
        if self.cursor < len(log):
            self.dispatch.add(
                [DispatchLogEntry(e.ts, e.zone_id, e.truck_id, e.event) for e in log[self.cursor :]]
            )
            self.cursor = len(log)
        return {str(tick["machine_id"]): tick for tick, _truth in results}


def bench_runtime(
    cfg: ShiftMateConfig,
    history_dir: Path,
    models_dir: Path,
    machines: int = 200,
    sim_minutes: int = 30,
    seed: int = 7,
    progress=None,
) -> BenchResult:
    fleet = build_history_fleet(cfg, 7)
    resources = EdgeResources.load(cfg, history_dir, models_dir)
    store = EdgeStore(None)
    day_index = max(resources.history_days, 0) + 1
    worlds = [
        _World(cfg, sid, i, fleet, seed, day_index) for i, sid in enumerate(sorted(cfg.sites))
    ]
    slots = [(w, mid) for w in worlds for mid in w.world.agents]

    tracemalloc.start()
    before = tracemalloc.get_traced_memory()[0]
    runtimes: list[tuple[_World, str, MachineRuntime]] = []
    for j in range(machines):
        w, mid = slots[j % len(slots)]
        agent = w.world.agents[mid]
        tasks = {
            pt.task.task_id: TaskInfo(pt.task.task_id, pt.task.task_type, pt.task.zone_id)
            for pt in (agent.plan.tasks if agent.plan else [])
        }
        rt = MachineRuntime(
            cfg, agent.machine, w.site, tasks, w.dispatch, store, resources, seed + j
        )
        runtimes.append((w, mid, rt))

    samples: list[float] = []
    memory = 0
    ticks = sim_minutes * 60
    for k in range(ticks):
        current = {id(w): w.step() for w in worlds}
        for w, mid, rt in runtimes:
            tick = current[id(w)][mid]
            t = time.perf_counter()
            rt.step(tick, 1.0, 0.0)
            if k >= MEMORY_TICKS:  # time only once tracing is off
                samples.append((time.perf_counter() - t) * 1000)
            for _ in rt.drain():  # the cab would take these; don't let buffers grow
                pass
            rt.drain_site()
        if k + 1 == MEMORY_TICKS:
            memory = tracemalloc.get_traced_memory()[0] - before
            tracemalloc.stop()
        if progress and (k + 1) % 60 == 0:
            progress(k + 1, ticks)
    if tracemalloc.is_tracing():
        memory = tracemalloc.get_traced_memory()[0] - before
        tracemalloc.stop()

    records, size = store.outbox_bytes(UPLOAD_KINDS)
    hours = sim_minutes / 60
    return BenchResult(
        machines=machines,
        sim_minutes=sim_minutes,
        ticks=ticks * machines,
        cpu_ms_per_tick_mean=round(float(np.mean(samples)), 4) if samples else 0.0,
        cpu_ms_per_tick_p95=round(float(np.percentile(samples, 95)), 4) if samples else 0.0,
        memory_mb_per_machine=round(memory / machines / 1e6, 3),
        upload_bytes_per_machine_per_hour=round(size / machines / hours, 1),
        records_per_machine_per_hour=round(records / machines / hours, 2),
        finished_at=datetime.now(UTC),
    )
