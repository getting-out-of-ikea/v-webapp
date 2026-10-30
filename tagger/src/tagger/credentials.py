"""Reachability probe for the Google Cloud credentials."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass

import google.auth
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import Request

logger = logging.getLogger(__name__)

VISION_SCOPE = "https://www.googleapis.com/auth/cloud-vision"

ENV_CREDENTIALS = "GOOGLE_APPLICATION_CREDENTIALS"


@dataclass(frozen=True)
class CredentialStatus:
    """Outcome of a credential check.

    ``error`` is a short, non-sensitive category. The detailed exception is
    only written to the logs: messages from google-auth can quote the key file
    path or the service account email and must not reach an HTTP client.
    """

    reachable: bool
    project: str | None = None
    error: str | None = None


def apply_credentials_env(path: str | None) -> None:
    """Point google-auth at the key file configured through settings.

    ``google.auth.default`` only looks at ``os.environ``, while
    pydantic-settings reads ``.env`` without exporting it: this bridges the
    two. An already exported variable wins over the ``.env`` entry.
    """
    if path and ENV_CREDENTIALS not in os.environ:
        os.environ[ENV_CREDENTIALS] = path


class CredentialProbe:
    """Checks that Application Default Credentials can mint a token.

    The check performs a real OAuth round trip, so the outcome is memoised for
    ``ttl_seconds``: probing ``/health`` must not cost one credential call per
    request.
    """

    def __init__(self, *, project_hint: str | None = None, ttl_seconds: int = 300) -> None:
        self._project_hint = project_hint
        self._ttl_seconds = ttl_seconds
        self._lock = asyncio.Lock()
        self._cached: CredentialStatus | None = None
        self._cached_at = 0.0

    async def status(self) -> CredentialStatus:
        """Return the cached status, refreshing it when the entry has expired."""
        async with self._lock:
            if self._cached is not None and time.monotonic() - self._cached_at < self._ttl_seconds:
                return self._cached
            status = await asyncio.to_thread(self._probe)
            self._cached = status
            self._cached_at = time.monotonic()
            return status

    def _probe(self) -> CredentialStatus:
        """Blocking check; always executed off the event loop."""
        try:
            credentials, project = google.auth.default(scopes=[VISION_SCOPE])
        except (GoogleAuthError, OSError) as exc:
            logger.warning("Application default credentials are unusable: %s", exc)
            return CredentialStatus(False, self._project_hint, "credentials not found")
        try:
            credentials.refresh(Request())
        except Exception as exc:  # noqa: BLE001 - any failure means "not usable"
            logger.warning("Google token refresh failed: %s", exc)
            return CredentialStatus(False, project or self._project_hint, "token refresh failed")

        resolved = project or self._project_hint
        logger.info("Google credentials verified (project=%s)", resolved or "unknown")
        return CredentialStatus(True, resolved, None)
