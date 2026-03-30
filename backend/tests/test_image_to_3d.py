"""Tests for /api/image-to-3d endpoint and _make_mock_glb helper."""

from __future__ import annotations

import json
import struct

from tests.conftest import PNG_HEADER


class TestMakeMockGlb:
    def test_glb_magic_and_version(self, client):
        from app.main import _make_mock_glb

        glb = _make_mock_glb()
        magic, version, length = struct.unpack_from("<III", glb, 0)
        assert magic == 0x46546C67  # "glTF"
        assert version == 2
        assert length == len(glb)

    def test_json_chunk_is_valid(self, client):
        from app.main import _make_mock_glb

        glb = _make_mock_glb()
        chunk_len, chunk_type = struct.unpack_from("<II", glb, 12)
        assert chunk_type == 0x4E4F534A  # "JSON"
        json_bytes = glb[20 : 20 + chunk_len]
        data = json.loads(json_bytes)
        assert data["asset"]["version"] == "2.0"
        assert "scenes" in data


class TestImageTo3dValidation:
    def test_accept_mismatched_mime_with_valid_magic(self, client):
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.jpg", PNG_HEADER, "image/jpeg")},
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

    def test_success_returns_glb(self, client):
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "model/gltf-binary"
        assert resp.headers["content-disposition"] == 'attachment; filename="model.glb"'
        magic = struct.unpack_from("<I", resp.content, 0)[0]
        assert magic == 0x46546C67

    def test_security_headers(self, client):
        resp = client.post(
            "/api/image-to-3d",
            files={"file": ("model.png", PNG_HEADER, "image/png")},
        )
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"
