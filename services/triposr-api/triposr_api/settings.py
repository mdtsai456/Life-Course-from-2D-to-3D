"""Configuration helpers for the TripoSR sidecar."""

from __future__ import annotations

import os
from dataclasses import dataclass


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
        chunk_size=int(os.environ.get("TRIPOSR_CHUNK_SIZE", "8192")),
        mc_resolution=int(os.environ.get("TRIPOSR_MC_RESOLUTION", "256")),
        foreground_ratio=float(os.environ.get("TRIPOSR_FOREGROUND_RATIO", "0.85")),
        max_image_edge=int(os.environ.get("TRIPOSR_MAX_IMAGE_EDGE", "2048")),
    )
