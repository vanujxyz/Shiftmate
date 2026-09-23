"""Write the combined JSON Schema for all exported models (`shiftmate schema export`).

All models go into one file with a shared `$defs` section, so a model used by several others
(for example `ErrorBody`) becomes exactly one TypeScript type in `packages/contracts`.
"""

import json
from pathlib import Path

from pydantic.json_schema import models_json_schema

from shiftmate.schema import EXPORTED_MODELS

SCHEMA_FILENAME = "contracts.schema.json"


def build_combined_schema() -> dict:
    _, top = models_json_schema(
        [(model, "validation") for model in EXPORTED_MODELS],
        ref_template="#/$defs/{model}",
    )
    defs = dict(sorted(top.get("$defs", {}).items()))
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "ShiftMateContracts",
        "type": "object",
        "additionalProperties": False,
        "$defs": defs,
    }


def export_schemas(out_dir: Path) -> Path:
    """Write the combined schema to `out_dir/contracts.schema.json` and return its path."""
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / SCHEMA_FILENAME
    text = json.dumps(build_combined_schema(), indent=2, ensure_ascii=False) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")
    return path
