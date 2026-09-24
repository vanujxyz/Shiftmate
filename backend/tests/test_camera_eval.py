"""Camera protocol (TRD §12): sessions recorded by the cab, reported by `shiftmate eval camera`."""

import json

from fastapi.testclient import TestClient

from shiftmate.edge.app import create_app
from shiftmate.eval.camera import evaluate_camera


def test_no_sessions_says_not_measured(tmp_path) -> None:
    metrics, md = evaluate_camera(tmp_path / "none.jsonl")
    assert metrics == {"sessions": 0} and "Not measured yet" in md


def test_error_by_distance_from_recorded_sessions(tmp_path) -> None:
    path = tmp_path / "camera_protocol.jsonl"
    rows = [
        {
            "calibrated": True,
            "readings": [{"true_m": 2, "estimate_m": 2.4}, {"true_m": 2, "estimate_m": 1.8}],
        },
        {"calibrated": False, "readings": [{"true_m": 6, "estimate_m": 7.5}]},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    metrics, md = evaluate_camera(path)
    assert metrics["sessions"] == 2 and metrics["readings"] == 3
    assert (
        abs(metrics["by_distance"][2.0] - 0.3) < 1e-9
        and abs(metrics["by_distance"][6.0] - 1.5) < 1e-9
    )
    assert abs(metrics["mae_m"] - 0.7) < 1e-9
    assert "| 2 m | 2 | 0.30 m | 0.40 m |" in md and "1 with a calibrated camera" in md


def test_the_gateway_stores_protocol_sessions(tmp_path) -> None:
    app = create_app(
        history_dir=tmp_path / "h",
        models_dir=tmp_path / "m",
        db_path=tmp_path / "edge.db",
        autorun=False,
    )
    body = {"calibrated": True, "readings": [{"true_m": 3, "estimate_m": 3.2}]}
    with TestClient(app) as client:
        assert client.post("/eval/camera-protocol", json=body).json() == {"saved": 1}
        assert (
            client.post(
                "/eval/camera-protocol", json={"calibrated": True, "readings": []}
            ).status_code
            == 422
        )
    saved = (tmp_path / "eval" / "camera_protocol.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(saved) == 1 and json.loads(saved[0])["readings"][0]["estimate_m"] == 3.2
