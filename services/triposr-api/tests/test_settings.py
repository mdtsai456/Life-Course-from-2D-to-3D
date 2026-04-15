from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from triposr_api.settings import ConfigurationError, get_settings


def test_get_settings_empty_numeric_env_uses_defaults():
    with patch.dict(
        os.environ,
        {
            "TRIPOSR_CHUNK_SIZE": "",
            "TRIPOSR_MC_RESOLUTION": "   ",
            "TRIPOSR_FOREGROUND_RATIO": "",
            "TRIPOSR_MAX_IMAGE_EDGE": "",
        },
        clear=False,
    ):
        s = get_settings()
    assert s.chunk_size == 8192
    assert s.mc_resolution == 256
    assert s.foreground_ratio == 0.85
    assert s.max_image_edge == 2048


def test_get_settings_invalid_chunk_size():
    with patch.dict(os.environ, {"TRIPOSR_CHUNK_SIZE": "not-int"}, clear=False):
        with pytest.raises(ConfigurationError) as excinfo:
            get_settings()
    assert "TRIPOSR_CHUNK_SIZE" in str(excinfo.value)


def test_get_settings_invalid_foreground_ratio():
    with patch.dict(os.environ, {"TRIPOSR_FOREGROUND_RATIO": "x"}, clear=False):
        with pytest.raises(ConfigurationError) as excinfo:
            get_settings()
    assert "TRIPOSR_FOREGROUND_RATIO" in str(excinfo.value)
