"""Thin async wrapper around the synchronous Google Cloud Vision client."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from google.cloud import vision

from .config import Settings

logger = logging.getLogger(__name__)


class VisionClient:
    """Owns a single ``ImageAnnotatorClient`` for the process lifetime."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: vision.ImageAnnotatorClient | None = None
        self._init_error: Exception | None = None

    def start(self) -> None:
        """Try to create the underlying client.

        The client is created lazily so that a missing/invalid ADC setup does
        not prevent the app from booting: ``/health`` can then report the
        problem instead of the whole process failing at startup.
        """
        try:
            self._ensure_client()
        except Exception as exc:  # pragma: no cover - depends on environment
            self._init_error = exc
            logger.warning("Vision client not initialised: %s", exc)

    def close(self) -> None:
        """Release the underlying gRPC channel."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Vision client closed")

    def _ensure_client(self) -> vision.ImageAnnotatorClient:
        if self._client is None:
            self._client = vision.ImageAnnotatorClient()
            self._init_error = None
            logger.info("Vision client initialised")
        return self._client

    @property
    def client(self) -> vision.ImageAnnotatorClient:
        return self._ensure_client()

    async def annotate(self, request: vision.AnnotateImageRequest) -> vision.AnnotateImageResponse:
        """Run a single annotate call off the event loop."""
        return await asyncio.to_thread(self.client.annotate_image, request=request)

    def credentials_ok(self) -> bool:
        """Best-effort check that credentials can be resolved.

        Uses the cached credentials on the client, so this does not hit the
        network on every probe. Returns ``False`` (instead of raising) when the
        client cannot be created, e.g. because ADC is not configured.
        """
        try:
            creds: Any = self._ensure_client().transport._credentials  # type: ignore[attr-defined]
            return creds is not None
        except Exception:  # pragma: no cover - defensive
            return False
