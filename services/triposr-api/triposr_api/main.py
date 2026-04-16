"""FastAPI sidecar for TripoSR inference."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.responses import JSONResponse

from triposr_api.engine import (
    DegradedEngine,
    EmptyMeshError,
    EngineHealth,
    EngineNotReadyError,
    InferenceFailedError,
    InvalidImageError,
    build_engine,
)
from triposr_api.settings import INFER_TIMEOUT_SECONDS_DEFAULT
from triposr_api.validation import (
    ALLOWED_IMAGE_MIME_TYPES,
    detect_image_type,
    read_and_validate_upload,
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_task: asyncio.Task[None] | None = None
    try:
        engine = build_engine()
    except Exception as exc:
        logger.exception("Failed to build TripoSR engine")
        app.state.engine = DegradedEngine(str(exc))
        app.state.settings = None
        yield
        return

    app.state.engine = engine
    app.state.settings = getattr(engine, "settings", None)

    async def _load_in_thread() -> None:
        try:
            await asyncio.to_thread(engine.load)
        except Exception:
            logger.exception("Failed to initialize TripoSR engine")

    load_task = asyncio.create_task(_load_in_thread())
    try:
        yield
    finally:
        if load_task is not None and not load_task.done():
            load_task.cancel()
            try:
                await load_task
            except asyncio.CancelledError:
                pass


app = FastAPI(lifespan=lifespan)


def _health_json(report: EngineHealth) -> dict[str, str | bool]:
    content: dict[str, str | bool] = {
        "status": "ok" if report.ready else "degraded",
        "triposr_ok": report.ready,
    }
    if report.detail:
        content["detail"] = report.detail
    return content


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    report = request.app.state.engine.health()
    return JSONResponse(status_code=200, content=_health_json(report))


@app.get("/health/ready")
async def health_ready(request: Request) -> JSONResponse:
    """就緒探測：供 Docker Compose `curl -f` 使用；未就緒為 503。JSON 與 GET /health 相同。"""
    report = request.app.state.engine.health()
    body = _health_json(report)
    status_code = 200 if report.ready else 503
    return JSONResponse(status_code=status_code, content=body)


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
    settings = getattr(request.app.state, "settings", None)
    timeout = (
        settings.infer_timeout_seconds
        if settings is not None
        else INFER_TIMEOUT_SECONDS_DEFAULT
    )
    infer_future = loop.run_in_executor(
        None,
        request.app.state.engine.infer_glb,
        contents,
    )
    try:
        glb = await asyncio.wait_for(infer_future, timeout=timeout)
    except asyncio.TimeoutError:
        logger.warning("TripoSR inference exceeded %.1f s limit.", timeout)
        if not infer_future.done():
            infer_future.cancel()
        raise HTTPException(
            status_code=504,
            detail="3D 推理逾時。",
        ) from None
    except EngineNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None
    except InvalidImageError as exc:
        raise HTTPException(status_code=415, detail=str(exc)) from None
    except EmptyMeshError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from None
    except InferenceFailedError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from None
    except Exception:
        logger.exception("POST /infer 發生未預期錯誤")
        raise HTTPException(
            status_code=500,
            detail="3D 推理發生內部錯誤。",
        ) from None

    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={"Content-Disposition": 'attachment; filename="model.glb"'},
    )
