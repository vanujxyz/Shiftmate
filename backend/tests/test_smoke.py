"""Milestone 1 smoke tests: both apps answer /health, the CLI loads, schema export works."""

import json

from fastapi.testclient import TestClient
from typer.testing import CliRunner

from shiftmate.cli import app as cli_app
from shiftmate.edge.app import create_app as create_edge
from shiftmate.fleet.app import create_app as create_fleet
from shiftmate.schema.export import export_schemas
from shiftmate.settings import REPO_ROOT


def test_edge_health() -> None:
    body = TestClient(create_edge()).get("/health").json()
    assert body["service"] == "edge"
    assert body["status"] == "ok"


def test_fleet_health(tmp_path) -> None:
    # a temporary store: the real data/fleet/fleet.duckdb may be open in a running fleet service
    app = create_fleet(db_path=tmp_path / "fleet.duckdb", seed=False)
    body = TestClient(app).get("/health").json()
    assert body["service"] == "fleet"
    assert body["status"] == "ok"


def test_unknown_route_uses_error_envelope() -> None:
    response = TestClient(create_edge()).get("/does-not-exist")
    assert response.status_code == 404
    assert set(response.json()["error"]) == {"code", "message"}


def test_cors_allows_only_app_origins() -> None:
    client = TestClient(create_edge())
    ok = client.get("/health", headers={"Origin": "http://localhost:5173"})
    bad = client.get("/health", headers={"Origin": "http://evil.example"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert "access-control-allow-origin" not in bad.headers


def test_cli_help_lists_commands() -> None:
    result = CliRunner().invoke(cli_app, ["--help"])
    assert result.exit_code == 0
    for name in ["edge", "fleet", "sim", "bench", "ml", "assistant", "eval", "schema", "config"]:
        assert name in result.output


def test_schema_export_writes_json(tmp_path) -> None:
    path = export_schemas(tmp_path)
    schema = json.loads(path.read_text(encoding="utf-8"))
    assert {"HealthResponse", "ErrorResponse", "ErrorBody"} <= set(schema["$defs"])


def test_repo_root_found() -> None:
    assert (REPO_ROOT / "CLAUDE.md").exists()
