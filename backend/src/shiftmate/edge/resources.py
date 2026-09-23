"""Data the Edge Gateway loads once: roster, models, baselines and recent history.

On a real machine these arrive from the fleet service and are cached on the tablet; here they
are read from `data/history` and `models/`. The estimation model is the one piece the edge keeps
up to date on its own: `edge/sync.py` downloads newer versions from the fleet into the edge
cache (`data/edge/models`); at start the cache is used first, then the bundled `models/`.
Everything is optional: if history or models have not been generated yet, the features that
need them say so instead of failing (golden rule 6).
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from shiftmate.config_loader import ShiftMateConfig
from shiftmate.engines.estimation import EstimationModels, expected_minutes

log = logging.getLogger(__name__)


@dataclass
class EdgeResources:
    cfg: ShiftMateConfig
    history_dir: Path
    models_dir: Path
    machines: pd.DataFrame = field(default_factory=pd.DataFrame)
    operators: pd.DataFrame = field(default_factory=pd.DataFrame)
    tasks: pd.DataFrame = field(default_factory=pd.DataFrame)
    history_events: pd.DataFrame = field(default_factory=pd.DataFrame)
    history_intervals: pd.DataFrame = field(default_factory=pd.DataFrame)
    baselines: pd.DataFrame = field(default_factory=pd.DataFrame)
    anomaly_models: dict[str, dict[str, Any]] = field(default_factory=dict)
    estimation: EstimationModels | None = None
    estimation_manifest: dict[str, Any] | None = None
    estimation_source: str | None = None  # "fleet" (downloaded), "cache" or "bundled"
    manifest: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def load(
        cls,
        cfg: ShiftMateConfig,
        history_dir: Path,
        models_dir: Path,
        cache_dir: Path | None = None,
    ) -> EdgeResources:
        r = cls(cfg, history_dir, models_dir)
        h = history_dir
        if (h / "manifest.json").exists():
            r.manifest = json.loads((h / "manifest.json").read_text(encoding="utf-8"))
        for name in ("machines", "operators", "tasks"):
            if (h / f"{name}.parquet").exists():
                setattr(r, name, pd.read_parquet(h / f"{name}.parquet"))
        if r.operators.empty or r.machines.empty:
            # No history yet: the roster is the same deterministic fleet the history would use.
            from shiftmate.sim.history import build_history_fleet

            fleet = build_history_fleet(cfg, 7)
            r.machines = pd.DataFrame([m.model_dump(mode="json") for m in fleet.machines])
            r.operators = pd.DataFrame(
                [
                    {**o.model_dump(mode="json"), "certifications": ",".join(o.certifications)}
                    for o in fleet.operators
                ]
            )
        if (h / "events.parquet").exists():
            ev = pd.read_parquet(
                h / "events.parquet",
                columns=["ts", "operator_id", "machine_id", "type", "code", "priority"],
            )
            r.history_events = ev[ev.type.isin(["alert", "idle_segment"])]
        if (h / "intervals.parquet").exists():
            r.history_intervals = pd.read_parquet(h / "intervals.parquet")
        a = models_dir / "anomaly"
        if (a / "baselines_latest.parquet").exists():
            r.baselines = pd.read_parquet(a / "baselines_latest.parquet")
        for path in sorted(a.glob("*.joblib")) if a.exists() else []:
            r.anomaly_models[path.stem] = joblib.load(path)
        for directory, source in ((cache_dir, "cache"), (models_dir, "bundled")):
            if directory is None:
                continue
            try:
                r.use_estimation_from(directory, source)
                break
            except (FileNotFoundError, OSError) as exc:
                log.info("no estimation model in %s: %s", directory, exc)
        if r.estimation is None:
            log.warning("no estimation model yet: estimates are off until one is trained")
        return r

    def use_estimation_from(self, directory: Path, source: str) -> None:
        """Load the LATEST estimation model under `directory/estimation` and use it."""
        from shiftmate.fleet.training import load_estimation_models

        self.estimation, self.estimation_manifest = load_estimation_models(directory)
        self.estimation_source = source

    # --- helpers used by the runtime -------------------------------------------------------------
    @property
    def history_days(self) -> int:
        return int(self.manifest.get("days", 0))

    def operator_row(self, operator_id: str) -> dict[str, Any] | None:
        if self.operators.empty:
            return None
        rows = self.operators[self.operators.operator_id == operator_id]
        return rows.iloc[0].to_dict() if len(rows) else None

    def last_engine_hours(self, machine_id: str) -> float | None:
        iv = self.history_intervals
        if iv.empty:
            return None
        rows = iv[iv.machine_id == machine_id]
        return float(rows["engine_hours"].iloc[-1]) if len(rows) else None

    def skill_index(self, operator_id: str, task_type: str, window_days: int) -> tuple[float, int]:
        """Median actual ÷ expected for this operator and task type (and how many days of data)."""
        t = self.tasks
        if t.empty:
            return 1.0, 0
        last = int(t["day_index"].max())
        rows = t[
            (t.operator_id == operator_id)
            & (t.task_type == task_type)
            & (t.status == "done")
            & (t.day_index > last - window_days)
        ]
        if rows.empty:
            return 1.0, 0
        machine_type = self.machines.set_index("machine_id").loc[
            rows.machine_id.iloc[0], "machine_type"
        ]
        rate = self.cfg.profiles[machine_type].tasks[task_type].base_rate_per_h
        ratios = rows["actual_duration_min"] / rows["planned_quantity"].map(
            lambda q: expected_minutes(q, rate)
        )
        return float(ratios.median()), int(rows["day_index"].nunique())

    def baseline_for(
        self, operator_id: str | None, machine_type: str, task_type: str | None, site_id: str
    ) -> dict[str, tuple[float, float]]:
        """feature → (median, MAD) from the latest baselines: personal, else site group."""
        b = self.baselines
        if b.empty:
            return {}
        personal = b[
            (b.level == "personal")
            & (b.operator_id == operator_id)
            & (b.machine_type == machine_type)
            & (b.task_type == task_type)
        ]
        use = (
            personal
            if len(personal)
            else b[
                (b.level == "group")
                & (b.machine_type == machine_type)
                & (b.task_type == task_type)
                & (b.site_id == site_id)
            ]
        )
        return {r.feature: (r.median, r.mad) for r in use.itertuples()}
