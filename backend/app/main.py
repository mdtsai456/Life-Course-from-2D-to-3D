"""FastAPI application for background removal and image-to-3D conversion."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import struct
import time
from contextlib import asynccontextmanager
from functools import partial

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from rembg import new_session, remove

from app.validation import (
    ALLOWED_3D_MIME_TYPES,
    ALLOWED_IMAGE_MIME_TYPES,
    detect_image_type,
    detect_png,
    read_and_validate_upload,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    start = time.monotonic()
    try:
        app.state.rembg_session = new_session()
        app.state.rembg_error = None
        logger.info("rembg model loaded in %.1fs", time.monotonic() - start)
    except Exception:
        logger.exception("Failed to load rembg model")
        app.state.rembg_session = None
        app.state.rembg_error = "rembg model failed to load"
    yield
    if getattr(app.state, "rembg_session", None) is not None:
        del app.state.rembg_session
    logger.info("Models unloaded")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next) -> Response:
    response: Response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> JSONResponse:
    ok = getattr(app.state, "rembg_session", None) is not None
    rembg_error = getattr(app.state, "rembg_error", None)
    status = "ok" if ok else "degraded"
    content: dict[str, str] = {"status": status}
    if rembg_error:
        content["rembg_error"] = rembg_error
    return JSONResponse(status_code=200, content=content)


@app.post("/api/remove-background")
async def remove_background(file: UploadFile, request: Request) -> Response:
    allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
    contents, _ = await read_and_validate_upload(
        file,
        detect_type=detect_image_type,
        allowed_types=ALLOWED_IMAGE_MIME_TYPES,
        type_error_detail=f"不支援的檔案類型。允許：{allowed}。",
    )

    session = getattr(request.app.state, "rembg_session", None)
    if session is None:
        raise HTTPException(status_code=503, detail="服務尚未就緒。")

    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(
            None, partial(remove, contents, session=session)
        )
    except Exception:
        logger.exception("Background removal failed")
        raise HTTPException(status_code=500, detail="圖片處理失敗，請重試。") from None

    if result is None or len(result) == 0:
        raise HTTPException(status_code=500, detail="圖片處理失敗，請重試。")

    return Response(
        content=result,
        media_type="image/png",
        headers={"Content-Disposition": 'attachment; filename="output.png"'},
    )


def _make_mock_glb() -> bytes:
    """Return a minimal valid GLB (empty glTF scene) for development."""
    gltf = {
        "asset": {"version": "2.0"},
        "scene": 0,
        "scenes": [{"nodes": []}],
    }
    json_bytes = json.dumps(gltf).encode()
    padding = (4 - len(json_bytes) % 4) % 4
    json_chunk_data = json_bytes + b" " * padding

    json_chunk_len = len(json_chunk_data)
    total_len = 12 + 8 + json_chunk_len

    file_header = struct.pack("<III", 0x46546C67, 2, total_len)
    chunk_header = struct.pack("<II", json_chunk_len, 0x4E4F534A)

    return file_header + chunk_header + json_chunk_data


@app.post("/api/image-to-3d")
async def image_to_3d(file: UploadFile) -> Response:
    allowed = ", ".join(sorted(ALLOWED_3D_MIME_TYPES))
    contents, _ = await read_and_validate_upload(
        file,
        detect_type=detect_png,
        allowed_types=ALLOWED_3D_MIME_TYPES,
        type_error_detail=f"檔案內容不是有效的格式。允許：{allowed}。",
    )

    # TODO: 替換成真實 2D→3D 模型推理（TripoSR、Meshy 等）
    logger.info("Returning mock GLB (input size: %d bytes)", len(contents))
    glb = _make_mock_glb()

    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="model.glb"'},
    )
