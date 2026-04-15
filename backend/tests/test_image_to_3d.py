"""Tests for /api/image-to-3d and /health."""

from __future__ import annotations

from tests.conftest import JPEG_HEADER, PNG_HEADER, WEBP_HEADER

FAKE_GLB = b"glb-bytes"


class TestHealth:
    def test_reports_ok_when_triposr_probe_succeeds(self, client, monkeypatch):
        async def fake_probe():
            return True, None

        monkeypatch.setattr("app.main._probe_triposr", fake_probe)

        resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "triposr_ok": True}

    def test_reports_degraded_when_triposr_probe_fails(self, client, monkeypatch):
        async def fake_probe():
            return False, "3D 推理服務尚未就緒。"

        monkeypatch.setattr("app.main._probe_triposr", fake_probe)

        resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json() == {
            "status": "degraded",
            "triposr_ok": False,
            "detail": "3D 推理服務尚未就緒。",
        }


class TestImageTo3dValidation:
    def test_accept_mismatched_mime_with_valid_magic(self, client, monkeypatch, tmp_path):
        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            assert filename == "model.jpg"
            assert content_type == "image/png"
            return FAKE_GLB

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.jpg", PNG_HEADER, "image/jpeg")},
        )

        assert resp.status_code == 200

    def test_accept_valid_jpeg(self, client, monkeypatch, tmp_path):
        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            assert content_type == "image/jpeg"
            return FAKE_GLB

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.jpg", JPEG_HEADER, "image/jpeg")},
        )

        assert resp.status_code == 200

    def test_reject_oversized_file(self, client):
        big = PNG_HEADER + b"\x00" * (10 * 1024 * 1024)
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("big.png", big, "image/png")},
        )
        assert resp.status_code == 413

    def test_reject_bad_magic_bytes(self, client):
        fake = b"\x00" * 200
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", fake, "image/png")},
        )
        assert resp.status_code == 415

    def test_reject_webp(self, client):
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.webp", WEBP_HEADER, "image/webp")},
        )
        assert resp.status_code == 415

    def test_success_returns_glb(self, client, monkeypatch, tmp_path):
        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            return FAKE_GLB

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )

        assert resp.status_code == 200
        assert resp.headers["content-type"] == "model/gltf-binary"
        assert resp.headers["content-disposition"] == 'attachment; filename="model.glb"'
        assert resp.headers["x-request-id"]
        assert resp.headers["x-job-id"]
        assert resp.content == FAKE_GLB

    def test_surfaces_downstream_errors_with_request_id(self, client, monkeypatch):
        from app.main import TriposrProxyError

        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            raise TriposrProxyError(503, "3D 推理服務暫時不可用。")

        monkeypatch.setattr("app.main._infer_glb", fake_infer)

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )

        assert resp.status_code == 503
        assert "錯誤 ID:" in resp.json()["detail"]

    def test_persists_successful_input_and_output(self, client, monkeypatch, tmp_path):
        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            return FAKE_GLB

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.jpg", JPEG_HEADER, "image/jpeg")},
        )

        job_id = resp.headers["x-job-id"]

        assert resp.status_code == 200
        assert (tmp_path / "input" / job_id / "original.jpg").read_bytes() == JPEG_HEADER
        assert (tmp_path / "output" / job_id / "model.glb").read_bytes() == FAKE_GLB

    def test_does_not_persist_files_when_inference_fails(self, client, monkeypatch, tmp_path):
        from app.main import TriposrProxyError

        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            raise TriposrProxyError(503, "3D 推理服務暫時不可用。")

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )

        assert resp.status_code == 503
        assert not (tmp_path / "input").exists()
        assert not (tmp_path / "output").exists()

    def test_security_headers(self, client, monkeypatch, tmp_path):
        async def fake_infer(contents: bytes, filename: str, content_type: str) -> bytes:
            return FAKE_GLB

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
