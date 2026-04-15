"""Configuration helpers for the TripoSR sidecar."""

from __future__ import annotations

import os
from dataclasses import dataclass


class ConfigurationError(ValueError):
    """Raised when a required environment value cannot be parsed."""


def _parse_int(name: str, raw: str | None, default: int) -> int:
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"環境變數 {name} 必須為整數，目前值為 {raw!r}。"
        ) from exc


def _parse_float(name: str, raw: str | None, default: float) -> float:
    if raw is None or raw.strip() == "":
        return default
    try:
        return float(raw)
    except ValueError as exc:
        raise ConfigurationError(
            f"環境變數 {name} 必須為數字，目前值為 {raw!r}。"
        ) from exc


@dataclass(frozen=True)
class Settings:
    source_dir: str
    pretrained_model_name_or_path: str
    device: str
    chunk_size: int
    mc_resolution: int
    foreground_ratio: float
    max_image_edge: int


def get_settings() -> Settings:
    return Settings(
        source_dir=os.environ.get("TRIPOSR_SOURCE_DIR", "/opt/triposr"),
        pretrained_model_name_or_path=os.environ.get(
            "TRIPOSR_MODEL_SOURCE",
            "stabilityai/TripoSR",
        ),
        device=os.environ.get("TRIPOSR_DEVICE", "cuda:0"),
        chunk_size=_parse_int(
            "TRIPOSR_CHUNK_SIZE", os.environ.get("TRIPOSR_CHUNK_SIZE"), 8192
        ),
        mc_resolution=_parse_int(
            "TRIPOSR_MC_RESOLUTION", os.environ.get("TRIPOSR_MC_RESOLUTION"), 256
        ),
        foreground_ratio=_parse_float(
            "TRIPOSR_FOREGROUND_RATIO",
            os.environ.get("TRIPOSR_FOREGROUND_RATIO"),
            0.85,
        ),
        max_image_edge=_parse_int(
            "TRIPOSR_MAX_IMAGE_EDGE", os.environ.get("TRIPOSR_MAX_IMAGE_EDGE"), 2048
        ),
    )
