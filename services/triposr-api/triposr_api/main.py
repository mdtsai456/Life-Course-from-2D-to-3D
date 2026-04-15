"""FastAPI sidecar for TripoSR inference."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from triposr_api.engine import (
    EmptyMeshError,
    EngineNotReadyError,
    InferenceFailedError,
    InvalidImageError,
    build_engine,
)
from triposr_api.validation import (
    ALLOWED_IMAGE_MIME_TYPES,
    detect_image_type,
    read_and_validate_upload,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    engine = build_engine()
    app.state.engine = engine
    try:
        engine.load()
    except Exception:
        logger.exception("Failed to initialize TripoSR engine")
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    report = request.app.state.engine.health()
    content: dict[str, str | bool] = {
        "status": "ok" if report.ready else "degraded",
        "triposr_ok": report.ready,
    }
    if report.detail:
        content["detail"] = report.detail
    return JSONResponse(status_code=200, content=content)


@app.post("/infer")
async def infer(file: UploadFile, request: Request) -> Response:
    allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
    contents, _ = await read_and_validate_upload(
        file,
        detect_type=detect_image_type,
        allowed_types=ALLOWED_IMAGE_MIME_TYPES,
        type_error_detail=f"檔案內容不是有效的格式。允許：{allowed}。",
    )

    loop = asyncio.get_running_loop()
    try:
        glb = await loop.run_in_executor(
            None,
            request.app.state.engine.infer_glb,
            contents,
        )
    except EngineNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except InvalidImageError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from None
    except EmptyMeshError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except InferenceFailedError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None

    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="model.glb"'},
    )
