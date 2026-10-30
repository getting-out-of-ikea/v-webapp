"""Operational endpoints."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Request
from pydantic import BaseModel

from tagger import __version__
from tagger.config import Settings
from tagger.credentials import CredentialProbe

router = APIRouter(tags=["ops"])


class CredentialsHealth(BaseModel):
    reachable: bool
    project: str | None = None
    error: str | None = None


class FeaturesHealth(BaseModel):
    labels: bool
    objects: bool
    web: bool


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    service: str = "tagger"
    version: str
    features: FeaturesHealth
    credentials: CredentialsHealth


@router.get("/health", response_model=HealthResponse, summary="Service and credentials health")
async def read_health(request: Request) -> HealthResponse:
    """Report service liveness, credential reachability and enabled features.

    Always answers ``200`` while the process can serve requests; a degraded
    body tells humans and monitoring that the Google credentials are not
    usable without letting a transient token-refresh failure kill the
    container through a failing liveness probe.
    """
    settings: Settings = request.app.state.settings
    probe: CredentialProbe = request.app.state.credentials
    credentials = await probe.status()

    return HealthResponse(
        status="ok" if credentials.reachable else "degraded",
        version=__version__,
        features=FeaturesHealth(
            labels=True,
            objects=settings.vision_enable_objects,
            web=settings.vision_enable_web,
        ),
        credentials=CredentialsHealth(
            reachable=credentials.reachable,
            project=credentials.project,
            error=credentials.error,
        ),
    )
