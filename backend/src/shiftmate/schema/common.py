"""Small shared API models: health check and the error envelope (TRD §9)."""

from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Answer of `GET /health` on the edge gateway and the fleet service."""

    service: Literal["edge", "fleet"]
    status: Literal["ok"]
    version: str
    sim_clock: str | None = None  # ISO 8601; filled once the world clock exists (milestone 7)
    network_online: bool | None = None  # edge only; the simulated network toggle


class ErrorBody(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    """Every API error uses this envelope: `{"error": {"code", "message"}}`."""

    error: ErrorBody
