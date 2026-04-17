"""Tests for /api/image-to-3d and /health."""

from __future__ import annotations

from tests.conftest import JPEG_HEADER, PNG_HEADER, WEBP_HEADER

FAKE_GLB = b"glb-bytes"


class TestHealth:
    def test_live_endpoint_ok_without_triposr(self, client):
        resp = client.get("/health/live")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}

    def test_reports_ok_when_triposr_probe_succeeds(self, client, monkeypatch):
        async def fake_probe(request_id: str | None = None):
            return True, None

        monkeypatch.setattr("app.main._probe_triposr", fake_probe)

        resp = client.get("/health")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok", "triposr_ok": True}

    def test_reports_degraded_when_triposr_probe_fails(self, client, monkeypatch):
        async def fake_probe(request_id: str | None = None):
            return False, "3D 推理服務尚未就緒。"

        monkeypatch.setattr("app.main._probe_triposr", fake_probe)

        resp = client.get("/health")

        assert resp.status_code == 503
        assert resp.json() == {
            "status": "degraded",
            "triposr_ok": False,
            "detail": "3D 推理服務尚未就緒。",
        }

    def test_public_health_omits_sensitive_fields_when_ok(self, client, monkeypatch):
        async def fake_probe(request_id: str | None = None):
            return True, None

        monkeypatch.setattr("app.main._probe_triposr", fake_probe)

        resp = client.get("/health/public")

        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}
        assert "triposr_ok" not in resp.json()

    def test_public_health_omits_sensitive_fields_when_degraded(self, client, monkeypatch):
        async def fake_probe(request_id: str | None = None):
            return False, "3D 推理服務尚未就緒。"

        monkeypatch.setattr("app.main._probe_triposr", fake_probe)

        resp = client.get("/health/public")

        assert resp.status_code == 503
        assert resp.json() == {"status": "degraded"}
        assert "detail" not in resp.json()

    def test_health_reuses_triposr_probe_within_ttl(self, client, monkeypatch):
        calls = {"n": 0}

        async def counting_probe(request_id: str | None = None):
            calls["n"] += 1
            return True, None

        monkeypatch.setattr("app.main._probe_triposr", counting_probe)
        monkeypatch.setenv("HEALTH_TRIPOSR_PROBE_TTL_SECONDS", "60")

        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        assert calls["n"] == 1

    def test_health_probes_each_time_when_ttl_disabled(self, client, monkeypatch):
        calls = {"n": 0}

        async def counting_probe(request_id: str | None = None):
            calls["n"] += 1
            return True, None

        monkeypatch.setattr("app.main._probe_triposr", counting_probe)
        monkeypatch.setenv("HEALTH_TRIPOSR_PROBE_TTL_SECONDS", "0")

        assert client.get("/health").status_code == 200
        assert client.get("/health").status_code == 200
        assert calls["n"] == 2


class TestImageTo3dValidation:
    def test_accept_mismatched_mime_with_valid_magic(self, client, monkeypatch, tmp_path):
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
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
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
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
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
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

        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
            raise TriposrProxyError(503, "3D 推理服務暫時不可用。")

        monkeypatch.setattr("app.main._infer_glb", fake_infer)

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )

        assert resp.status_code == 503
        assert "錯誤 ID:" in resp.json()["detail"]

    def test_persists_successful_input_and_output(self, client, monkeypatch, tmp_path):
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
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

        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
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
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
            return FAKE_GLB

        monkeypatch.setattr("app.main._infer_glb", fake_infer)
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"


class TestImageTo3dAccessControl:
    def test_requires_api_key_when_configured(self, monkeypatch, client):
        monkeypatch.setenv("IMAGE_TO_3D_API_KEY", "secret-test-key")

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )

        assert resp.status_code == 401
        assert "金鑰" in resp.json()["detail"]

    def test_rejects_wrong_api_key(self, monkeypatch, client):
        monkeypatch.setenv("IMAGE_TO_3D_API_KEY", "secret-test-key")

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
            headers={"Authorization": "Bearer wrong"},
        )

        assert resp.status_code == 401

    def test_accepts_bearer_when_configured(self, monkeypatch, client, tmp_path):
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
            return FAKE_GLB

        monkeypatch.setenv("IMAGE_TO_3D_API_KEY", "secret-test-key")
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        monkeypatch.setattr("app.main._infer_glb", fake_infer)

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
            headers={"Authorization": "Bearer secret-test-key"},
        )

        assert resp.status_code == 200

    def test_accepts_x_api_key_header(self, monkeypatch, client, tmp_path):
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
            return FAKE_GLB

        monkeypatch.setenv("IMAGE_TO_3D_API_KEY", "secret-test-key")
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        monkeypatch.setattr("app.main._infer_glb", fake_infer)

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
            headers={"X-API-Key": "secret-test-key"},
        )

        assert resp.status_code == 200

    def test_rate_limit_returns_429(self, monkeypatch, client, tmp_path):
        async def fake_infer(
            contents: bytes, filename: str, content_type: str, request_id: str | None = None
        ) -> bytes:
            return FAKE_GLB

        monkeypatch.setenv("IMAGE_TO_3D_RATE_LIMIT_MAX_REQUESTS", "2")
        monkeypatch.setenv("IMAGE_TO_3D_RATE_LIMIT_WINDOW_SECONDS", "300")
        monkeypatch.setenv("STORAGE_ROOT", str(tmp_path))
        monkeypatch.setattr("app.main._infer_glb", fake_infer)

        for _ in range(2):
            ok = client.post(
                "/api/image-to-3d",
                files={"file": ("model.png", PNG_HEADER, "image/png")},
            )
            assert ok.status_code == 200

        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model2.png", PNG_HEADER, "image/png")},
        )

        assert resp.status_code == 429
        assert resp.headers.get("retry-after")
