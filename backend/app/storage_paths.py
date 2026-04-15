"""Storage path helpers for persisted image-to-3D jobs."""

from __future__ import annotations

from pathlib import Path


def job_input_dir(storage_root: Path, job_id: str) -> Path:
    return storage_root / "input" / job_id


def job_output_dir(storage_root: Path, job_id: str) -> Path:
    return storage_root / "output" / job_id


def ensure_job_dirs(storage_root: Path, job_id: str) -> tuple[Path, Path]:
    input_dir = job_input_dir(storage_root, job_id)
    output_dir = job_output_dir(storage_root, job_id)

    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    return input_dir, output_dir
