from __future__ import annotations

import os
import time
from contextlib import contextmanager
from dataclasses import replace
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from triposr_api.engine import EmptyMeshError, EngineHealth, EngineNotReadyError
from triposr_api.main import app
from triposr_api.settings import get_settings

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_HEADER = b"\xff\xd8\xff" + b"\x00" * 100
FAKE_GLB = b"glb-bytes"


class FakeEngine:
    def __init__(
        self,
        *,
        health: EngineHealth | None = None,
        glb: bytes = FAKE_GLB,
        error: Exception | None = None,
        settings=None,
    ):
        self._health = health or EngineHealth(ready=True)
        self._glb = glb
        self._error = error
        self.settings = settings

    def load(self) -> None:
        return None

    def health(self) -> EngineHealth:
        return self._health

    def infer_glb(self, image_bytes: bytes) -> bytes:
        if self._error is not None:
            raise self._error
        return self._glb


@pytest.fixture
def fake_client():
    @contextmanager
    def _make(engine: FakeEngine):
        with patch("triposr_api.main.build_engine", return_value=engine):
            with TestClient(app) as client:
                yield client

    return _make


class SlowFakeEngine(FakeEngine):
    def infer_glb(self, image_bytes: bytes) -> bytes:
        time.sleep(0.3)
        return super().infer_glb(image_bytes)


def test_health_reports_ok(fake_client):
    with fake_client(FakeEngine(health=EngineHealth(ready=True))) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "triposr_ok": True}


def test_health_reports_degraded(fake_client):
    with fake_client(
        FakeEngine(health=EngineHealth(ready=False, detail="目前沒有可用的 CUDA GPU。"))
    ) as client:
        resp = client.get("/health")

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "degraded",
        "triposr_ok": False,
        "detail": "目前沒有可用的 CUDA GPU。",
    }


def test_health_ready_reports_ok(fake_client):
    with fake_client(FakeEngine(health=EngineHealth(ready=True))) as client:
        resp = client.get("/health/ready")

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "triposr_ok": True}


def test_health_ready_reports_503_when_degraded(fake_client):
    with fake_client(
        FakeEngine(health=EngineHealth(ready=False, detail="目前沒有可用的 CUDA GPU。"))
    ) as client:
        resp = client.get("/health/ready")

    assert resp.status_code == 503
    assert resp.json() == {
        "status": "degraded",
        "triposr_ok": False,
        "detail": "目前沒有可用的 CUDA GPU。",
    }


def test_infer_accepts_png(fake_client):
    with fake_client(FakeEngine()) as client:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "model/gltf-binary"
    assert resp.content == FAKE_GLB


def test_infer_accepts_jpeg(fake_client):
    with fake_client(FakeEngine()) as client:
        resp = client.post(
            "/infer",
            files={"file": ("input.jpg", JPEG_HEADER, "image/jpeg")},
        )

    assert resp.status_code == 200


def test_infer_rejects_invalid_magic_bytes(fake_client):
    with fake_client(FakeEngine()) as client:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", b"\x00" * 100, "image/png")},
        )

    assert resp.status_code == 415


def test_infer_surfaces_not_ready(fake_client):
    with fake_client(FakeEngine(error=EngineNotReadyError("3D 推理服務尚未就緒。"))) as client:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )

    assert resp.status_code == 503


def test_infer_times_out(fake_client):
    fast_timeout = replace(get_settings(), infer_timeout_seconds=0.05)
    with fake_client(SlowFakeEngine(settings=fast_timeout)) as client:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )

    assert resp.status_code == 504
    assert resp.json()["detail"] == "3D 推理逾時。"


def test_infer_surfaces_empty_mesh(fake_client):
    with fake_client(
        FakeEngine(error=EmptyMeshError("產生的 3D 模型內容不足，請換一張圖片再試。"))
    ) as client:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )

    assert resp.status_code == 422


def test_health_degraded_when_build_engine_fails_from_invalid_env():
    with patch.dict(os.environ, {"TRIPOSR_CHUNK_SIZE": "not-int"}, clear=False):
        with TestClient(app) as client:
            resp = client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["triposr_ok"] is False
    assert "TRIPOSR_CHUNK_SIZE" in body["detail"]
