"""Tests for the health endpoint and the credential probe cache."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tagger.credentials import CredentialProbe, CredentialStatus
from tagger.main import create_app


class FakeProbe:
    """Stand-in for CredentialProbe: returns a fixed status, never uses the network."""

    def __init__(self, status: CredentialStatus) -> None:
        self._status = status

    async def status(self) -> CredentialStatus:
        return self._status


@pytest.fixture
def client() -> TestClient:
    with TestClient(create_app()) as test_client:
        yield test_client


def test_health_reports_ok_when_credentials_work(client: TestClient) -> None:
    client.app.state.credentials = FakeProbe(CredentialStatus(True, "demo-project"))

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["features"]["labels"] is True
    assert body["credentials"] == {
        "reachable": True,
        "project": "demo-project",
        "error": None,
    }


def test_health_degrades_without_credentials(client: TestClient) -> None:
    client.app.state.credentials = FakeProbe(
        CredentialStatus(False, None, "credentials not found")
    )

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "degraded"
    assert body["credentials"]["reachable"] is False
    assert body["credentials"]["error"] == "credentials not found"


async def test_probe_caches_the_result(monkeypatch: pytest.MonkeyPatch) -> None:
    probe = CredentialProbe(ttl_seconds=60)
    calls = 0

    def fake_probe() -> CredentialStatus:
        nonlocal calls
        calls += 1
        return CredentialStatus(True, "demo-project")

    monkeypatch.setattr(probe, "_probe", fake_probe)

    assert (await probe.status()).reachable is True
    assert (await probe.status()).reachable is True
    assert calls == 1


async def test_probe_names_a_missing_key_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A path that points nowhere is reported as such, not as "no credentials"."""
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(tmp_path / "missing.json"))
    probe = CredentialProbe(project_hint="demo-project")

    status = await probe.status()

    assert status.reachable is False
    assert status.error == "credentials file not found"
    assert status.project == "demo-project"


async def test_probe_rejects_a_json_file_that_is_not_a_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An OAuth client secret is valid JSON but not a credential google-auth loads."""
    secret = tmp_path / "client_secret.json"
    secret.write_text('{"installed": {"client_id": "x"}}', encoding="utf-8")
    monkeypatch.setenv("GOOGLE_APPLICATION_CREDENTIALS", str(secret))
    probe = CredentialProbe()

    status = await probe.status()

    assert status.reachable is False
    assert status.error == "credentials file is not a Google key"
