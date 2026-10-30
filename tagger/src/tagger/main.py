"""FastAPI application exposing the tagger endpoints."""

from __future__ import annotations

import logging
import time
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from google.api_core import exceptions as gexc
from google.cloud import vision

from .config import Settings, get_settings
from .preprocess import ALLOWED_MIME, InvalidImageError, prepare_image
from .schemas import HealthResponse, TagOut, TagResponse, TimingOut
from .scoring import collect_tags, load_aliases, rank_tags
from .vision import VisionClient

logger = logging.getLogger(__name__)

ALLOWED_MODES = {"auto", "labels", "objects"}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    client = VisionClient(settings)
    client.start()
    app.state.settings = settings
    app.state.vision = client
    app.state.aliases = load_aliases(settings.tag_alias_path)
    try:
        yield
    finally:
        client.close()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="tagger", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_allow_origins,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    return app


app = create_app()


def _enabled_features(settings: Settings) -> list[str]:
    features = ["labels"]
    if settings.vision_enable_objects:
        features.append("objects")
    if settings.vision_enable_web:
        features.append("web")
    return features


def _features_for_mode(mode: str, settings: Settings) -> list[str]:
    if mode == "labels":
        return ["labels"]
    if mode == "objects":
        if not settings.vision_enable_objects:
            raise HTTPException(
                status_code=400,
                detail="mode 'objects' is disabled on this server",
            )
        return ["labels", "objects"]
    # auto
    features = ["labels"]
    if settings.vision_enable_objects:
        features.append("objects")
    if settings.vision_enable_web:
        features.append("web")
    return features


def _build_request(
    image_bytes: bytes,
    features: list[str],
    lang: str,
    max_results: int,
) -> vision.AnnotateImageRequest:
    feature_map = {
        "labels": vision.Feature.Type.LABEL_DETECTION,
        "objects": vision.Feature.Type.OBJECT_LOCALIZATION,
        "web": vision.Feature.Type.WEB_DETECTION,
    }
    vision_features = [
        vision.Feature(type_=feature_map[name], max_results=max_results)
        for name in features
    ]
    image = vision.Image(content=image_bytes)
    context = vision.ImageContext(language_hints=[lang]) if lang else None
    return vision.AnnotateImageRequest(
        image=image,
        features=vision_features,
        image_context=context,
    )


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings: Settings = app.state.settings
    vision_client: VisionClient = app.state.vision
    return HealthResponse(
        status="ok",
        credentials_ok=vision_client.credentials_ok(),
        project=settings.google_cloud_project,
        features=_enabled_features(settings),
    )


@app.post("/tag", response_model=TagResponse)
async def tag(
    image: UploadFile = File(...),
    mode: str = Form("auto"),
    top_k: int = Form(10),
    threshold: float = Form(0.0),
    lang: str = Form("it"),
) -> TagResponse:
    settings: Settings = app.state.settings
    vision_client: VisionClient = app.state.vision
    aliases: dict[str, str] = app.state.aliases

    if mode not in ALLOWED_MODES:
        raise HTTPException(status_code=400, detail=f"unknown mode: {mode}")
    if top_k <= 0:
        raise HTTPException(status_code=400, detail="top_k must be positive")
    if not 0.0 <= threshold <= 1.0:
        raise HTTPException(status_code=400, detail="threshold must be in [0, 1]")

    if image.content_type and image.content_type not in ALLOWED_MIME:
        raise HTTPException(status_code=400, detail="unsupported image type")

    raw = await image.read()
    if not raw:
        raise HTTPException(status_code=400, detail="empty upload")
    if len(raw) > settings.max_image_size:
        raise HTTPException(status_code=413, detail="image too large")

    features = _features_for_mode(mode, settings)

    t0 = time.perf_counter()
    try:
        prepared = prepare_image(raw, settings.max_image_dimension)
    except InvalidImageError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    t1 = time.perf_counter()

    request = _build_request(
        prepared.data,
        features,
        lang,
        max_results=max(settings.vision_max_results, top_k),
    )

    try:
        response = await vision_client.annotate(request)
    except gexc.ResourceExhausted as exc:
        raise HTTPException(status_code=429, detail="provider quota exhausted") from exc
    except (gexc.ServiceUnavailable, gexc.DeadlineExceeded) as exc:
        raise HTTPException(status_code=503, detail="provider unavailable") from exc
    except gexc.GoogleAPICallError as exc:
        logger.exception("Vision call failed")
        raise HTTPException(status_code=502, detail="provider error") from exc
    t2 = time.perf_counter()

    if response.error and response.error.message:
        logger.warning("Vision returned error: %s", response.error.message)
        raise HTTPException(status_code=502, detail="invalid provider response")

    tags = collect_tags(response, aliases)
    ranked = rank_tags(tags, threshold=threshold, top_k=top_k)
    t3 = time.perf_counter()

    return TagResponse(
        features=features,
        tags=[TagOut(tag=t.tag, score=t.score, source=t.source) for t in ranked],
        timing_ms=TimingOut(
            preprocess=(t1 - t0) * 1000,
            upstream=(t2 - t1) * 1000,
            scoring=(t3 - t2) * 1000,
        ),
    )
