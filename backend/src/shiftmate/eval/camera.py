"""Camera proximity evaluation (TRD §12): a person stands at 2, 3, 4, 5 and 6 m from the webcam
and the cab records 20 distance estimates at each (its "Test accuracy" panel posts them to the
gateway). Reported: mean absolute error by distance, overall, and whether the camera was
calibrated. Target: mean absolute error ≤ 1.0 m. Nothing is estimated or filled in: with no
recorded session the section says so.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

TARGET_M = 1.0


def load_sessions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def evaluate_camera(path: Path) -> tuple[dict[str, Any], str]:
    sessions = load_sessions(path)
    head = ["## Camera proximity (F-SAFE-03)", ""]
    if not sessions:
        md = head + [
            "Not measured yet. The protocol needs a webcam and a helper: open Safety on the cab, "
            "turn the camera on, calibrate at 3 m, then use **Test accuracy** at 2, 3, 4, 5 and "
            "6 m (20 readings each). The readings go to the gateway and `shiftmate eval camera` "
            "writes this section. Target: mean absolute error ≤ 1.0 m."
        ]
        return {"sessions": 0}, "\n".join(md)
    errors: dict[float, list[float]] = defaultdict(list)
    calibrated = 0
    for s in sessions:
        calibrated += bool(s.get("calibrated"))
        for r in s["readings"]:
            errors[float(r["true_m"])].append(abs(float(r["estimate_m"]) - float(r["true_m"])))
    all_err = [e for v in errors.values() for e in v]
    mae = sum(all_err) / len(all_err)
    lines = head + [
        f"{len(sessions)} recorded session(s), {calibrated} with a calibrated camera; "
        f"{len(all_err)} readings. Overall mean absolute error **{mae:.2f} m** "
        f"(target ≤ {TARGET_M:.1f} m: {'met' if mae <= TARGET_M else 'not met'}).",
        "",
        "| true distance | readings | mean absolute error | max error |",
        "|---|---|---|---|",
    ]
    for d in sorted(errors):
        e = errors[d]
        lines.append(f"| {d:g} m | {len(e)} | {sum(e) / len(e):.2f} m | {max(e):.2f} m |")
    metrics = {
        "sessions": len(sessions),
        "readings": len(all_err),
        "mae_m": mae,
        "by_distance": {d: sum(e) / len(e) for d, e in errors.items()},
    }
    return metrics, "\n".join(lines)
