"""FastAPI application for the tagger service."""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from tagger import __version__
from tagger.config import Settings, get_settings
from tagger.credentials import CredentialProbe, apply_credentials_env
from tagger.health import router as health_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Create process-wide resources; the Vision client joins here in M2."""
    settings: Settings = get_settings()
    apply_credentials_env(settings.google_application_credentials)
    app.state.settings = settings
    app.state.credentials = CredentialProbe(
        project_hint=settings.google_cloud_project,
        ttl_seconds=settings.health_cache_ttl_s,
    )
    logger.info(
        "tagger %s ready (objects=%s, web=%s)",
        __version__,
        settings.vision_enable_objects,
        settings.vision_enable_web,
    )
    yield


def create_app() -> FastAPI:
    """Build the ASGI application."""
    settings = get_settings()
    app = FastAPI(title="tagger", version=__version__, lifespan=lifespan)

    if origins := settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    app.include_router(health_router)
    return app


app = create_app()


def run() -> None:
    """Console entry point (``uv run tagger``); Cloud Run provides ``PORT``."""
    logging.basicConfig(level=logging.INFO)
    uvicorn.run(
        "tagger.main:app",
        host=os.environ.get("HOST", "0.0.0.0"),
        port=int(os.environ.get("PORT", "8000")),
    )
