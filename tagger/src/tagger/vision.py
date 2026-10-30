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

    def start(self) -> None:
        """Create the underlying client. Called from the FastAPI lifespan."""
        if self._client is None:
            self._client = vision.ImageAnnotatorClient()
            logger.info("Vision client initialised")

    def close(self) -> None:
        """Release the underlying gRPC channel."""
        if self._client is not None:
            self._client.close()
            self._client = None
            logger.info("Vision client closed")

    @property
    def client(self) -> vision.ImageAnnotatorClient:
        if self._client is None:
            raise RuntimeError("Vision client is not initialised")
        return self._client

    async def annotate(self, request: vision.AnnotateImageRequest) -> vision.AnnotateImageResponse:
        """Run a single annotate call off the event loop."""
        return await asyncio.to_thread(self.client.annotate_image, request=request)

    def credentials_ok(self) -> bool:
        """Best-effort check that credentials can be resolved.

        Uses the cached credentials on the client, so this does not hit the
        network on every probe.
        """
        try:
            creds: Any = self.client.transport._credentials  # type: ignore[attr-defined]
            return creds is not None
        except Exception:  # pragma: no cover - defensive
            return False
