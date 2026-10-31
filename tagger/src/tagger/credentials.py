"""Reachability probe for the Google Cloud credentials."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path

import google.auth
from google.auth.exceptions import (
    DefaultCredentialsError,
    GoogleAuthError,
    RefreshError,
    TransportError,
)
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

    The path is made absolute, because google-auth resolves it against the
    current working directory: a relative entry in ``.env`` would otherwise
    mean different files depending on where the server is started from.
    """
    if path and ENV_CREDENTIALS not in os.environ:
        os.environ[ENV_CREDENTIALS] = str(Path(path).expanduser().resolve())


def _inspect_key_file(path: str | None, project_hint: str | None) -> CredentialStatus | None:
    """Check a configured key file before asking google-auth about it.

    google-auth silently ignores a ``GOOGLE_APPLICATION_CREDENTIALS`` that
    points nowhere (or at something that is not a credential file) and then
    fails as if no credentials were configured at all, which sends people
    looking in the wrong place. ``None`` means "nothing to report".
    """
    if not path:
        return None

    key = Path(path).expanduser()
    if not key.exists():
        logger.warning("The credentials key %s does not exist", key)
        return CredentialStatus(False, project_hint, "credentials file not found")
    if not key.is_file():
        logger.warning("The credentials path %s is not a file", key)
        return CredentialStatus(False, project_hint, "credentials path is not a file")

    try:
        with key.open("rb") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("The credentials key %s cannot be read: %s", key, exc)
        return CredentialStatus(False, project_hint, "credentials file is not valid JSON")

    # Every ADC file google-auth understands carries a "type" discriminator:
    # service_account, authorized_user, external_account, ...
    if not isinstance(payload, dict) or "type" not in payload:
        logger.warning("The file %s is not a Google credential file", key)
        return CredentialStatus(False, project_hint, "credentials file is not a Google key")

    return None


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
        key_path = os.environ.get(ENV_CREDENTIALS)
        if (failure := _inspect_key_file(key_path, self._project_hint)) is not None:
            return failure

        try:
            credentials, project = google.auth.default(scopes=[VISION_SCOPE])
        except DefaultCredentialsError as exc:
            logger.warning("No Google credentials available: %s", exc)
            return CredentialStatus(
                False, self._project_hint, "application default credentials not found"
            )
        except (GoogleAuthError, OSError) as exc:
            logger.warning("Application default credentials are unusable: %s", exc)
            return CredentialStatus(False, self._project_hint, "credentials unusable")

        resolved = project or self._project_hint
        try:
            credentials.refresh(Request())
        except TransportError as exc:
            logger.warning("The Google token endpoint is unreachable: %s", exc)
            return CredentialStatus(False, resolved, "token endpoint unreachable")
        except RefreshError as exc:
            logger.warning("Google refused the token request: %s", exc)
            return CredentialStatus(False, resolved, "token refresh rejected")
        except Exception as exc:  # noqa: BLE001 - any failure means "not usable"
            logger.warning("Google token refresh failed: %s", exc)
            return CredentialStatus(False, resolved, "token refresh failed")

        logger.info("Google credentials verified (project=%s)", resolved or "unknown")
        return CredentialStatus(True, resolved, None)
