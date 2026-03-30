"""Shared constants and upload validation helpers."""

from __future__ import annotations

from collections.abc import Set as AbstractSet
from typing import Callable

from fastapi import HTTPException, UploadFile

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
JPEG_MAGIC = b"\xff\xd8\xff"
WEBP_MAGIC_RIFF = b"RIFF"
WEBP_MAGIC_TAG = b"WEBP"

FILE_TOO_LARGE_DETAIL = f"檔案過大，最大允許 {MAX_FILE_SIZE // (1024 * 1024)} MB。"

ALLOWED_IMAGE_MIME_TYPES: frozenset[str] = frozenset(
    {"image/png", "image/jpeg", "image/webp"}
)
ALLOWED_3D_MIME_TYPES: frozenset[str] = frozenset({"image/png"})


def detect_image_type(contents: bytes) -> str | None:
    """Detect image type from magic bytes."""
    if contents.startswith(PNG_MAGIC):
        return "image/png"
    if contents.startswith(JPEG_MAGIC):
        return "image/jpeg"
    if len(contents) >= 12 and contents[:4] == WEBP_MAGIC_RIFF and contents[8:12] == WEBP_MAGIC_TAG:
        return "image/webp"
    return None


def detect_png(contents: bytes) -> str | None:
    """Return 'image/png' if contents start with the PNG magic bytes."""
    if contents.startswith(PNG_MAGIC):
        return "image/png"
    return None


async def read_and_validate_upload(
    file: UploadFile,
    *,
    max_size: int = MAX_FILE_SIZE,
    detect_type: Callable[[bytes], str | None] | None = None,
    allowed_types: AbstractSet[str] | None = None,
    type_error_detail: str = "不支援的檔案類型。",
) -> tuple[bytes, str | None]:
    """Read an upload file with size and optional type validation.

    Returns (contents, detected_type).
    Raises HTTPException 413 if too large, 415 if wrong type.
    """
    if allowed_types is not None and detect_type is None:
        raise ValueError(
            "allowed_types requires a detect_type callback to perform type validation"
        )

    if file.size is not None and file.size > max_size:
        raise HTTPException(status_code=413, detail=FILE_TOO_LARGE_DETAIL)

    contents = await file.read(max_size + 1)
    if len(contents) > max_size:
        raise HTTPException(status_code=413, detail=FILE_TOO_LARGE_DETAIL)

    detected = None
    if detect_type is not None:
        detected = detect_type(contents)
        if allowed_types is not None and detected not in allowed_types:
            raise HTTPException(status_code=415, detail=type_error_detail)

    return contents, detected
