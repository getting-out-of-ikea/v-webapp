import io

import pytest
from fastapi.testclient import TestClient
from google.cloud import vision
from PIL import Image

from tagger import main as main_module


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color=(120, 30, 200)).save(buf, format="PNG")
    return buf.getvalue()


class _FakeVision:
    def __init__(self, response: vision.AnnotateImageResponse) -> None:
        self._response = response
        self.calls = 0

    def start(self) -> None: ...
    def close(self) -> None: ...
    def credentials_ok(self) -> bool:
        return True

    async def annotate(self, request):  # noqa: ANN001
        self.calls += 1
        return self._response


@pytest.fixture
def client(monkeypatch):
    response = vision.AnnotateImageResponse(
        label_annotations=[
            vision.EntityAnnotation(description="cane", topicality=0.91),
            vision.EntityAnnotation(description="prato", topicality=0.43),
            vision.EntityAnnotation(description="palla", topicality=0.38),
        ]
    )
    fake = _FakeVision(response)
    monkeypatch.setattr(main_module, "VisionClient", lambda settings: fake)
    with TestClient(main_module.app) as c:
        yield c, fake


def test_health(client):
    c, _ = client
    r = c.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "labels" in body["features"]


def test_tag_labels_mode(client):
    c, fake = client
    r = c.post(
        "/tag",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={"mode": "labels", "top_k": "2", "threshold": "0.4"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["provider"] == "google-cloud-vision"
    assert body["features"] == ["labels"]
    assert [t["tag"] for t in body["tags"]] == ["cane", "prato"]
    assert fake.calls == 1


def test_tag_rejects_unknown_mode(client):
    c, _ = client
    r = c.post(
        "/tag",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={"mode": "nope"},
    )
    assert r.status_code == 400


def test_tag_rejects_objects_when_disabled(client):
    c, _ = client
    r = c.post(
        "/tag",
        files={"image": ("x.png", _png_bytes(), "image/png")},
        data={"mode": "objects"},
    )
    assert r.status_code == 400


def test_tag_rejects_bad_image(client):
    c, _ = client
    r = c.post(
        "/tag",
        files={"image": ("x.png", b"not-an-image", "image/png")},
        data={"mode": "labels"},
    )
    assert r.status_code == 400
