from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from triposr_api.engine import EmptyMeshError, EngineHealth, EngineNotReadyError
from triposr_api.main import app

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
    ):
        self._health = health or EngineHealth(ready=True)
        self._glb = glb
        self._error = error

    def load(self) -> None:
        return None

    def health(self) -> EngineHealth:
        return self._health

    def infer_glb(self, image_bytes: bytes) -> bytes:
        if self._error is not None:
            raise self._error
        return self._glb


def make_client(engine: FakeEngine) -> TestClient:
    patcher = patch("triposr_api.main.build_engine", return_value=engine)
    patcher.start()
    client = TestClient(app)
    client.__enter__()
    client._build_engine_patcher = patcher
    return client


def close_client(client: TestClient) -> None:
    client.__exit__(None, None, None)
    client._build_engine_patcher.stop()


def test_health_reports_ok():
    client = make_client(FakeEngine(health=EngineHealth(ready=True)))
    try:
        resp = client.get("/health")
    finally:
        close_client(client)

    assert resp.status_code == 200
    assert resp.json() == {"status": "ok", "triposr_ok": True}


def test_health_reports_degraded():
    client = make_client(
        FakeEngine(health=EngineHealth(ready=False, detail="目前沒有可用的 CUDA GPU。"))
    )
    try:
        resp = client.get("/health")
    finally:
        close_client(client)

    assert resp.status_code == 200
    assert resp.json() == {
        "status": "degraded",
        "triposr_ok": False,
        "detail": "目前沒有可用的 CUDA GPU。",
    }


def test_infer_accepts_png():
    client = make_client(FakeEngine())
    try:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )
    finally:
        close_client(client)

    assert resp.status_code == 200
    assert resp.headers["content-type"] == "model/gltf-binary"
    assert resp.content == FAKE_GLB


def test_infer_accepts_jpeg():
    client = make_client(FakeEngine())
    try:
        resp = client.post(
            "/infer",
            files={"file": ("input.jpg", JPEG_HEADER, "image/jpeg")},
        )
    finally:
        close_client(client)

    assert resp.status_code == 200


def test_infer_rejects_invalid_magic_bytes():
    client = make_client(FakeEngine())
    try:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", b"\x00" * 100, "image/png")},
        )
    finally:
        close_client(client)

    assert resp.status_code == 415


def test_infer_surfaces_not_ready():
    client = make_client(FakeEngine(error=EngineNotReadyError("3D 推理服務尚未就緒。")))
    try:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )
    finally:
        close_client(client)

    assert resp.status_code == 503


def test_infer_surfaces_empty_mesh():
    client = make_client(FakeEngine(error=EmptyMeshError("產生的 3D 模型內容不足，請換一張圖片再試。")))
    try:
        resp = client.post(
            "/infer",
            files={"file": ("input.png", PNG_HEADER, "image/png")},
        )
    finally:
        close_client(client)

    assert resp.status_code == 422
