"""Configuration helpers for the backend application."""

from __future__ import annotations

import os
from pathlib import Path

_BASE_DIR = Path(__file__).resolve().parent.parent  # backend/


def get_storage_root() -> Path:
    return Path(os.getenv("STORAGE_ROOT") or str(_BASE_DIR / "storage")).resolve()
