"""Runtime settings, read from environment variables and the repo-root `.env` file (TRD §14).

The backend is started with `uv run --directory backend ...`, so the working directory is
`backend/`. Paths in settings are therefore resolved against the repository root, which we
find by walking up from this file until we see `pnpm-workspace.yaml`.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


def find_repo_root(start: Path | None = None) -> Path:
    """Return the repository root (the folder that holds `pnpm-workspace.yaml`)."""
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "pnpm-workspace.yaml").exists():
            return candidate
    raise FileNotFoundError("Could not find the repository root (pnpm-workspace.yaml).")


REPO_ROOT = find_repo_root()


class Settings(BaseSettings):
    """All environment-driven settings. Names match `.env.example` with the prefix removed."""

    model_config = SettingsConfigDict(
        env_file=REPO_ROOT / ".env",
        env_file_encoding="utf-8",
        env_prefix="SHIFTMATE_",
        extra="ignore",
    )

    llm_provider: str = "gemini"
    llm_model: str = ""
    # read from GEMINI_API_KEY (no prefix); a SecretStr so it never appears in logs or reprs
    gemini_api_key: SecretStr = Field(default=SecretStr(""), validation_alias="GEMINI_API_KEY")
    edge_port: int = 8100
    fleet_port: int = 8200
    fleet_url: str = "http://localhost:8200"
    edge_url: str = "http://localhost:8100"
    data_dir: Path = Path("./data")
    models_dir: Path = Path("./models")
    seed: int = 7
    live_weather: bool = False

    @property
    def config_dir(self) -> Path:
        return REPO_ROOT / "config"

    def resolve(self, path: Path) -> Path:
        """Resolve a possibly relative path against the repository root."""
        return path if path.is_absolute() else (REPO_ROOT / path).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
