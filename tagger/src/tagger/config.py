"""Application settings loaded from environment variables."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration for the tagger service.

    All values can be overridden via environment variables (or a local
    ``.env`` file). See ``.env.example`` for the documented set.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Google Cloud Vision
    google_cloud_project: str | None = None
    google_application_credentials: str | None = None
    vision_timeout_ms: int = 10_000
    vision_max_results: int = 30
    vision_enable_objects: bool = False
    vision_enable_web: bool = False

    # Upload limits
    max_image_size: int = 10 * 1024 * 1024  # 10 MB
    max_image_dimension: int = 1600

    # Local assets
    tag_alias_path: Path = Path("app/data/tag_aliases.json")

    # CORS
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    # Defaults for the /tag endpoint
    default_top_k: int = 10
    default_threshold: float = 0.0
    default_lang: str = "it"


@lru_cache
def get_settings() -> Settings:
    """Return a cached ``Settings`` instance.

    Also propagates ``GOOGLE_APPLICATION_CREDENTIALS`` to ``os.environ`` so that
    ``google.auth.default()`` (used by the Vision client) can find the service
    account file even when it was only provided via ``.env``.
    """
    settings = Settings()
    if settings.google_application_credentials:
        os.environ.setdefault(
            "GOOGLE_APPLICATION_CREDENTIALS",
            settings.google_application_credentials,
        )
    if settings.google_cloud_project:
        os.environ.setdefault("GOOGLE_CLOUD_PROJECT", settings.google_cloud_project)
    return settings
