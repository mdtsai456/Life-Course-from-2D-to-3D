"""Tests for /api/remove-background endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.conftest import PNG_HEADER

FAKE_RESULT = b"\x89PNG\r\n\x1a\nfake-result"


class TestRemoveBackgroundValidation:
    def test_reject_unsupported_mime_type(self, client):
        resp = client.post(
            "/api/remove-background",
            files={"file": ("test.txt", b"hello", "text/plain")},
        )
        assert resp.status_code == 415

    def test_reject_oversized_file(self, client):
        big = PNG_HEADER + b"\x00" * (10 * 1024 * 1024)
        resp = client.post(
            "/api/remove-background",
            files={"file": ("big.png", big, "image/png")},
        )
        assert resp.status_code == 413

    def test_reject_bad_magic_bytes(self, client):
        resp = client.post(
            "/api/remove-background",
            files={"file": ("test.png", b"\x00" * 100, "image/png")},
        )
        assert resp.status_code == 415

    def test_success_returns_png(self, client):
        with patch("app.main.remove", return_value=FAKE_RESULT):
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == FAKE_RESULT

    def test_returns_503_when_session_missing(self, client):
        saved = client.app.state.rembg_session
        del client.app.state.rembg_session
        try:
            resp = client.post(
                "/api/remove-background",
                files={"file": ("test.png", PNG_HEADER, "image/png")},
            )
            assert resp.status_code == 503
        finally:
            client.app.state.rembg_session = saved
