"""Pydantic models for the public API."""

from __future__ import annotations

from pydantic import BaseModel, Field


class TagOut(BaseModel):
    tag: str
    score: float
    source: str


class TimingOut(BaseModel):
    preprocess: float = 0.0
    upstream: float = 0.0
    scoring: float = 0.0


class TagResponse(BaseModel):
    provider: str = "google-cloud-vision"
    features: list[str]
    tags: list[TagOut]
    timing_ms: TimingOut


class HealthResponse(BaseModel):
    status: str
    credentials_ok: bool
    project: str | None = None
    features: list[str] = Field(default_factory=list)
