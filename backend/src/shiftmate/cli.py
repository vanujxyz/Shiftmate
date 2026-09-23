"""The `shiftmate` command-line tool (CLAUDE.md §2).

Commands that belong to later milestones are registered now so the command tree is stable;
they exit with code 2 and say which milestone builds them.
"""

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

app.add_typer(sim_app, name="sim")
app.add_typer(bench_app, name="bench")
app.add_typer(ml_app, name="ml")
app.add_typer(assistant_app, name="assistant")
app.add_typer(eval_app, name="eval")
app.add_typer(schema_app, name="schema")
app.add_typer(config_app, name="config")


def _not_yet(what: str, milestone: int) -> None:
    typer.echo(f"'{what}' is not built yet. It arrives in milestone {milestone}.", err=True)
    raise typer.Exit(code=2)


# --- servers -------------------------------------------------------------------------------


@app.command()
def edge(host: str = "127.0.0.1", port: int | None = None) -> None:
    """Run the Edge Gateway (default port 8100)."""
    port = port or get_settings().edge_port
    uvicorn.run("shiftmate.edge.app:create_app", factory=True, host=host, port=port)


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
    _not_yet("config validate", 2)


@sim_app.command("generate")
def sim_generate(days: int = 42, seed: int = 7) -> None:
    """Generate fleet history (Parquet + DuckDB)."""
    _not_yet("sim generate", 3)


@sim_app.command("scale")
def sim_scale(machines: int = 10000, sim_minutes: int = 60, speed: str = "max") -> None:
    """Stream synthetic summaries from many machines to the Fleet Service."""
    _not_yet("sim scale", 9)


@bench_app.command("runtime")
def bench_runtime(machines: int = 200, sim_minutes: int = 30) -> None:
    """Benchmark full MachineRuntimes."""
    _not_yet("bench runtime", 9)


@ml_app.command("train")
def ml_train() -> None:
    """Train anomaly and estimation models."""
    _not_yet("ml train", 6)


@assistant_app.command("index")
def assistant_index() -> None:
    """Build the assistant retrieval index."""
    _not_yet("assistant index", 14)


@eval_app.command("all")
def eval_all() -> None:
    """Run every evaluation and rewrite docs/EVAL.md."""
    _not_yet("eval all", 6)


@eval_app.command("idle")
def eval_idle() -> None:
    _not_yet("eval idle", 6)


@eval_app.command("anomaly")
def eval_anomaly() -> None:
    _not_yet("eval anomaly", 6)


@eval_app.command("estimation")
def eval_estimation() -> None:
    _not_yet("eval estimation", 6)


@eval_app.command("assistant")
def eval_assistant() -> None:
    _not_yet("eval assistant", 14)


if __name__ == "__main__":
    app()
