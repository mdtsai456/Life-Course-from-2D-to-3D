"""Shared fixtures for backend tests.

Uses sys.modules patching to mock rembg before app.main is imported.
"""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

PNG_HEADER = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100


def _cleanup_modules():
    """Remove cached app modules so the next import gets a fresh copy."""
    for mod in ["app.main"]:
        sys.modules.pop(mod, None)


@pytest.fixture()
def client():
    """Yield a TestClient with rembg mocked out."""
    mock_session = MagicMock(name="rembg_session")
    mock_rembg = MagicMock()
    mock_rembg.new_session = MagicMock(return_value=mock_session)
    mock_rembg.remove = MagicMock()

    with patch.dict(sys.modules, {"rembg": mock_rembg}):
        _cleanup_modules()

        from app.main import app

        with TestClient(app) as c:
            yield c

        _cleanup_modules()
