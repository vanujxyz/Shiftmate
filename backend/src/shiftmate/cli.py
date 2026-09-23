"""The `shiftmate` command-line tool (CLAUDE.md §2).

Commands that belong to later milestones are registered now so the command tree is stable;
they exit with code 2 and say which milestone builds them.
"""

import time
from pathlib import Path

import typer
import uvicorn

from shiftmate.settings import REPO_ROOT, get_settings

app = typer.Typer(help="ShiftMate backend CLI.", no_args_is_help=True)
sim_app = typer.Typer(help="Simulator: history generation and scale runs.", no_args_is_help=True)
bench_app = typer.Typer(help="Benchmarks.", no_args_is_help=True)
ml_app = typer.Typer(help="Model training.", no_args_is_help=True)
assistant_app = typer.Typer(help="Assistant knowledge index.", no_args_is_help=True)
eval_app = typer.Typer(help="Evaluation runners (write docs/EVAL.md).", no_args_is_help=True)
schema_app = typer.Typer(
    help="JSON Schema export for the frontend contracts.", no_args_is_help=True
)
config_app = typer.Typer(help="Configuration checks.", no_args_is_help=True)
edge_app = typer.Typer(
    help="Edge Gateway: run the server (no subcommand) or a headless scenario.",
    invoke_without_command=True,
)

app.add_typer(sim_app, name="sim")
app.add_typer(bench_app, name="bench")
app.add_typer(ml_app, name="ml")
app.add_typer(assistant_app, name="assistant")
app.add_typer(eval_app, name="eval")
app.add_typer(schema_app, name="schema")
app.add_typer(config_app, name="config")
app.add_typer(edge_app, name="edge")


def _not_yet(what: str, milestone: int) -> None:
    typer.echo(f"'{what}' is not built yet. It arrives in milestone {milestone}.", err=True)
    raise typer.Exit(code=2)


# --- servers -------------------------------------------------------------------------------


@edge_app.callback()
def edge(ctx: typer.Context, host: str = "127.0.0.1", port: int | None = None) -> None:
    """Run the Edge Gateway (default port 8100)."""
    if ctx.invoked_subcommand is not None:
        return
    port = port or get_settings().edge_port
    uvicorn.run("shiftmate.edge.app:create_app", factory=True, host=host, port=port)


@edge_app.command("headless")
def edge_headless(scenario: str = "ravi_shift", speed: float = 60.0) -> None:
    """Play a scenario with no browser on a fake clock and print what happened, beat by beat."""
    import asyncio

    from shiftmate.edge.headless import describe, run_headless

    def on_beat(b: dict) -> None:
        typer.echo(f"  … {b['fired']:%H:%M} {b['id']}", err=True)

    result = asyncio.run(run_headless(scenario, speed, on_beat=on_beat))
    for line in describe(result):
        typer.echo(line)


@app.command()
def fleet(host: str = "127.0.0.1", port: int | None = None) -> None:
    """Run the Fleet Service (default port 8200)."""
    port = port or get_settings().fleet_port
    uvicorn.run("shiftmate.fleet.app:create_app", factory=True, host=host, port=port)


# --- schema --------------------------------------------------------------------------------

DEFAULT_SCHEMA_DIR = REPO_ROOT / "frontend" / "packages" / "contracts" / "schema"


@schema_app.command("export")
def schema_export(out: Path = DEFAULT_SCHEMA_DIR) -> None:
    """Write JSON Schema files for all exported pydantic models."""
    from shiftmate.schema.export import export_schemas

    path = export_schemas(out)
    typer.echo(f"Exported combined JSON Schema to {path}")


# --- placeholders for later milestones -----------------------------------------------------


@config_app.command("validate")
def config_validate() -> None:
    """Load and validate every file in config/."""
    from shiftmate.config_loader import ConfigError, load_config

    try:
        cfg = load_config()
    except ConfigError as exc:
        typer.echo(f"Config is NOT valid.\n{exc}", err=True)
        raise typer.Exit(code=1) from exc
    rules_by_priority: dict[str, int] = {}
    for rule in cfg.safety_rules.rules:
        rules_by_priority[rule.priority] = rules_by_priority.get(rule.priority, 0) + 1
    machines = sum(sum(s.fleet.count(t) for t in cfg.profiles) for s in cfg.sites.values())
    typer.echo("Config is valid.")
    typer.echo(f"  machine profiles : {', '.join(sorted(cfg.profiles))}")
    typer.echo(f"  sites            : {', '.join(sorted(cfg.sites))} ({machines} machines)")
    typer.echo(
        f"  safety rules     : {len(cfg.safety_rules.rules)} "
        f"({', '.join(f'{p} {n}' for p, n in sorted(rules_by_priority.items()))})"
    )
    typer.echo(f"  lessons          : {len(cfg.lessons.lessons)}")
    typer.echo(f"  checklist items  : {len(cfg.checklist.items)}")
    typer.echo(f"  voice intents    : {len(cfg.intents.intents)}")


@sim_app.command("generate")
def sim_generate(
    days: int = 42,
    seed: int = 7,
    out: Path | None = None,
    workers: int = 4,
    replay: bool = typer.Option(True, help="Also run the engines over the history (D-015)."),
) -> None:
    """Generate fleet history (Parquet + DuckDB) into data/history."""
    import logging
    import time

    from shiftmate.sim.history import generate_history

    logging.basicConfig(level=logging.WARNING)
    settings = get_settings()
    out_dir = out or settings.resolve(settings.data_dir) / "history"
    started = time.perf_counter()
    manifest = generate_history(days=days, seed=seed, out_dir=out_dir, workers=workers)
    typer.echo(
        f"Generated {manifest['tick_rows']:,} ticks, {manifest['tasks']} tasks "
        f"({manifest['tasks_done']} done) for {manifest['machines']} machines over {days} days "
        f"in {time.perf_counter() - started:.0f} s → {out_dir}"
    )
    if replay:
        from shiftmate.edge.replay import replay_history

        started = time.perf_counter()
        counts = replay_history(out_dir, workers=workers, seed=seed)
        typer.echo(
            f"Replayed through the engines: {counts['intervals']:,} intervals, "
            f"{counts['events']:,} events, {counts['idle_segments']:,} idle segments "
            f"in {time.perf_counter() - started:.0f} s"
        )


@sim_app.command("scale")
def sim_scale(
    machines: int = 10000,
    sim_minutes: int = 60,
    speed: str = "max",
    fleet_url: str | None = None,
    in_process: bool = typer.Option(
        False, help="Run the Fleet Service inside this command instead of posting to one."
    ),
) -> None:
    """Stream synthetic summaries from many machines to the Fleet Service (TRD §7.6)."""
    import contextlib

    import httpx

    from shiftmate.config_loader import load_config
    from shiftmate.sim.scale import Pool, run_scale

    if speed != "max":
        try:
            float(speed)
        except ValueError as exc:
            raise typer.BadParameter("speed is 'max' or a number (e.g. 60)") from exc
    cfg = load_config()
    history_dir, _ = _dirs()
    pool = Pool.from_history(history_dir)

    with contextlib.ExitStack() as stack:
        if in_process:
            from fastapi.testclient import TestClient

            from shiftmate.fleet.app import create_app

            client = stack.enter_context(TestClient(create_app(cfg)))
        else:
            url = fleet_url or get_settings().fleet_url
            client = stack.enter_context(httpx.Client(base_url=url, timeout=60))
            try:
                client.get("/health").raise_for_status()
            except httpx.HTTPError as exc:
                typer.echo(
                    f"The Fleet Service is not reachable at {url} ({type(exc).__name__}). Start it "
                    "with `shiftmate fleet`, or add --in-process.",
                    err=True,
                )
                raise typer.Exit(code=1) from exc

        def progress(step: int, end, records: int) -> None:
            typer.echo(f"  {end:%H:%M} UTC · {records:,} records sent", err=True)

        typer.echo(f"Streaming {machines:,} machines × {sim_minutes} min (speed {speed}) …")
        run = run_scale(cfg, client, pool, machines, sim_minutes, speed, progress=progress)
    typer.echo(
        f"{run.records:,} records ({run.intervals:,} intervals, {run.events:,} events) in "
        f"{run.requests:,} requests · {run.records_per_s:,.0f} records/s ingest · p95 "
        f"{run.request_ms_p95:.0f} ms · {run.bytes_per_machine_per_hour / 1000:.1f} kB per "
        f"machine per hour · {run.seconds:.1f} s"
    )
    _save_scale(cfg, run=run)


@bench_app.command("runtime")
def bench_runtime(machines: int = 200, sim_minutes: int = 30) -> None:
    """Benchmark full MachineRuntimes on live 1 s ticks (TRD §7.6)."""
    from shiftmate.config_loader import load_config
    from shiftmate.sim.bench import bench_runtime as run_bench

    cfg = load_config()
    history_dir, models_dir = _dirs()

    def progress(done: int, total: int) -> None:
        typer.echo(f"  {done // 60}/{total // 60} simulated minutes", err=True)

    started = time.perf_counter()
    result = run_bench(cfg, history_dir, models_dir, machines, sim_minutes, progress=progress)
    typer.echo(
        f"{machines} runtimes × {sim_minutes} min: CPU {result.cpu_ms_per_tick_mean:.3f} ms per "
        f"machine per tick (p95 {result.cpu_ms_per_tick_p95:.3f}) · "
        f"{result.memory_mb_per_machine:.2f} MB per runtime · "
        f"{result.upload_bytes_per_machine_per_hour / 1000:.1f} kB upload per machine per hour · "
        f"{time.perf_counter() - started:.0f} s"
    )
    _save_scale(cfg, bench=result)


def _save_scale(cfg, run=None, bench=None) -> None:
    """Keep the result for /scale/stats and refresh the EVAL.md scale section."""
    from shiftmate.eval.report import write_section
    from shiftmate.fleet.scale import eval_section, read_scale_file, write_scale_file

    settings = get_settings()
    path = settings.resolve(settings.data_dir) / "fleet" / "scale.json"
    write_scale_file(path, run=run, bench=bench)
    write_section("scale", eval_section(cfg, *read_scale_file(path)))
    typer.echo(f"Saved to {path} and docs/EVAL.md (scale section).")


def _dirs() -> tuple[Path, Path]:
    settings = get_settings()
    return settings.resolve(settings.data_dir) / "history", settings.resolve(settings.models_dir)


@ml_app.command("train")
def ml_train(seed: int = 7) -> None:
    """Train estimation (LightGBM quantiles) and anomaly (IsolationForest) models."""
    import json

    from shiftmate.config_loader import load_config
    from shiftmate.fleet.patterns import fleet_patterns
    from shiftmate.fleet.training import estimation_dataset, train_anomaly, train_estimation

    cfg = load_config()
    history_dir, models_dir = _dirs()
    est = train_estimation(cfg, history_dir, models_dir, seed)
    typer.echo(
        f"Estimation {est['version']}: {est['n_train']} training tasks, "
        f"best iterations {est['best_iterations']}"
    )
    anomaly = train_anomaly(cfg, history_dir, models_dir)
    typer.echo(f"Anomaly: {len(anomaly['groups'])} IsolationForests (machine type × tier)")
    patterns = fleet_patterns(cfg, estimation_dataset(cfg, history_dir))
    (models_dir / "fleet_patterns.json").write_text(json.dumps(patterns, indent=2), "utf-8")
    typer.echo(f"Fleet patterns: {len(patterns)} condition multipliers → {models_dir}")


@assistant_app.command("index")
def assistant_index() -> None:
    """Build the assistant retrieval index."""
    _not_yet("assistant index", 14)


def _data_section(cfg, history_dir: Path) -> str:
    import json

    m = json.loads((history_dir / "manifest.json").read_text(encoding="utf-8"))
    s = cfg.estimation.split_days
    return "\n".join(
        [
            "## Data",
            "",
            f"Simulated history, seed {m['seed']}: {m['days']} days ({m['first_day']} to "
            f"{m['last_day']}), {m['machines']} machines, {m['operators']} operators, "
            f"{m['tick_rows']:,} ticks at {m['tick_seconds']:.0f} s, {m['tasks_done']:,} completed "
            f"tasks. Split by day: train {s.train[0]}–{s.train[1]}, validation "
            f"{s.validation[0]}–{s.validation[1]}, test {s.test[0]}–{s.test[1]}.",
        ]
    )


def _run_eval(which: list[str]) -> None:
    from shiftmate.config_loader import load_config
    from shiftmate.eval.report import EVAL_PATH, write_section

    cfg = load_config()
    history_dir, models_dir = _dirs()
    write_section("data", _data_section(cfg, history_dir))
    for name in which:
        if name == "idle":
            from shiftmate.eval.idle import evaluate_idle

            metrics, md = evaluate_idle(cfg, history_dir)
            typer.echo(f"idle: accuracy {metrics['accuracy']:.3f}, by tier {metrics['by_tier']}")
        elif name == "anomaly":
            from shiftmate.eval.anomaly import evaluate_anomaly

            metrics, md = evaluate_anomaly(cfg, history_dir, models_dir)
            typer.echo(
                f"anomaly: precision {metrics['precision']:.3f}, recall {metrics['recall']:.3f}"
            )
        elif name == "estimation":
            from shiftmate.eval.estimation import evaluate_estimation

            metrics, md = evaluate_estimation(cfg, history_dir, models_dir)
            t = metrics["test"]
            typer.echo(
                f"estimation: median error {t['median_ape']:.3f}, coverage {t['coverage']:.3f}"
            )
        else:
            continue
        write_section(name, md)
    typer.echo(f"Wrote {EVAL_PATH}")


@eval_app.command("all")
def eval_all() -> None:
    """Run every evaluation and rewrite docs/EVAL.md."""
    _run_eval(["idle", "anomaly", "estimation"])


@eval_app.command("idle")
def eval_idle() -> None:
    """Idle-reason accuracy by tier, confusion matrix."""
    _run_eval(["idle"])


@eval_app.command("anomaly")
def eval_anomaly() -> None:
    """Unusual-behaviour precision and recall."""
    _run_eval(["anomaly"])


@eval_app.command("estimation")
def eval_estimation() -> None:
    """Task time estimation error and range coverage."""
    _run_eval(["estimation"])


@eval_app.command("assistant")
def eval_assistant() -> None:
    _not_yet("eval assistant", 14)


if __name__ == "__main__":
    app()
