"""Tests for the removed /api/remove-background endpoint."""

from __future__ import annotations

from tests.conftest import PNG_HEADER


def test_remove_background_route_is_not_found(client):
    resp = client.post(
        "/api/remove-background",
        files={"file": ("test.png", PNG_HEADER, "image/png")},
    )

    assert resp.status_code == 404
