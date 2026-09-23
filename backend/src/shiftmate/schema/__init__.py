"""Pydantic models for every piece of data that crosses a module or network boundary (TRD §5).

`EXPORTED_MODELS` lists the models that `shiftmate schema export` turns into JSON Schema, from
which `frontend/packages/contracts` generates TypeScript types.
"""

from pydantic import BaseModel

from shiftmate.schema.common import ErrorBody, ErrorResponse, HealthResponse

EXPORTED_MODELS: list[type[BaseModel]] = [HealthResponse, ErrorResponse, ErrorBody]

__all__ = ["EXPORTED_MODELS", "ErrorBody", "ErrorResponse", "HealthResponse"]
