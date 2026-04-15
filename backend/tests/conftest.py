"""Shared fixtures for backend tests."""

from __future__ import annotations

import sys

import pytest
from fastapi.testclient import TestClient

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
JPEG_HEADER = b"\xff\xd8\xff" + b"\x00" * 100
WEBP_HEADER = b"RIFF" + b"\x00" * 4 + b"WEBP" + b"\x00" * 100


def _cleanup_modules():
    """Remove cached app modules so the next import gets a fresh copy."""
    for mod in ["app.main", "app.config", "app.storage_paths"]:
        sys.modules.pop(mod, None)


@pytest.fixture()
def client():
    _cleanup_modules()

    from app.main import app

    with TestClient(app) as c:
        yield c

    _cleanup_modules()
