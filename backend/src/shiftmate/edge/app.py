"""Edge Gateway FastAPI app (TRD §9.1). Milestone 1: health check only."""

from fastapi import FastAPI

from shiftmate import __version__
from shiftmate.schema import HealthResponse
from shiftmate.util.api import install_common


def create_app() -> FastAPI:
    app = FastAPI(title="ShiftMate Edge Gateway", version=__version__)
    install_common(app)

    @app.get("/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        return HealthResponse(service="edge", status="ok", version=__version__, network_online=True)

    return app
