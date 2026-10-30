"""Runtime configuration, read from the environment (12-factor style)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Service settings.

    Values come from environment variables (case-insensitive) and, when
    present, from the ``.env`` file in the working directory. Every field has
    a default, so the service starts on a bare shell.

    Secrets are never stored here: the Google credentials are referenced by
    path (local development) or attached to the runtime (production).
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- Google Cloud Vision -------------------------------------------
    google_cloud_project: str | None = None
    google_application_credentials: str | None = None
    vision_timeout_ms: int = Field(default=10_000, gt=0)
    vision_max_results: int = Field(default=30, gt=0, le=100)
    vision_enable_objects: bool = True
    vision_enable_web: bool = False

    # --- HTTP layer ----------------------------------------------------
    max_image_size: int = Field(default=10 * 1024 * 1024, gt=0)
    cors_allow_origins: str = ""
    health_cache_ttl_s: int = Field(default=300, ge=0)

    @property
    def cors_origins(self) -> list[str]:
        """Allowed browser origins, from a comma-separated variable.

        A plain string (``http://localhost:5173,https://app.example``) is used
        instead of a list field so users do not have to write JSON in ``.env``.
        An empty value disables the CORS middleware entirely.
        """
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()
