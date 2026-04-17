"""FastAPI application for the single-step image-to-3D flow."""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
import uuid

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_storage_root
from app.image_to_3d_guards import enforce_image_to_3d_access
from app.storage_paths import ensure_job_dirs
from app.validation import (
    ALLOWED_IMAGE_MIME_TYPES,
    detect_image_type,
    read_and_validate_upload,
)

logger = logging.getLogger(__name__)

TRIPOSR_API_URL = os.environ.get("TRIPOSR_API_URL", "http://localhost:8001").rstrip("/")
TRIPOSR_API_TIMEOUT_SECONDS = float(os.environ.get("TRIPOSR_API_TIMEOUT_SECONDS", "120"))
IMAGE_EXTENSION_BY_MIME_TYPE = {
    "image/png": "png",
    "image/jpeg": "jpg",
}


class TriposrProxyError(Exception):
    """Raised when the downstream TripoSR service cannot satisfy a request."""

    def __init__(self, status_code: int, detail: str):
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in os.environ.get(
            "CORS_ALLOWED_ORIGINS", "http://localhost:5173"
        ).split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id", "Authorization", "X-API-Key"],
)


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "")


def _with_request_id(detail: str, request: Request) -> str:
    request_id = _request_id(request)
    if not request_id:
        return detail
    return f"{detail}（錯誤 ID: {request_id}）"


def _extract_error_detail(response: httpx.Response, fallback: str) -> str:
    try:
        data = response.json()
    except ValueError:
        return fallback

    detail = data.get("detail")
    if isinstance(detail, str) and detail:
        return detail
    return fallback


async def _triposr_request(
    method: str,
    path: str,
    *,
    request_id: str | None = None,
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> httpx.Response:
    rid = request_id if request_id else str(uuid.uuid4())
    headers = {"X-Request-Id": rid}
    async with httpx.AsyncClient(timeout=TRIPOSR_API_TIMEOUT_SECONDS) as client:
        return await client.request(
            method,
            f"{TRIPOSR_API_URL}{path}",
            files=files,
            headers=headers,
        )


async def _probe_triposr(request_id: str | None = None) -> tuple[bool, str | None]:
    try:
        response = await _triposr_request("GET", "/health", request_id=request_id)
    except httpx.RequestError:
        logger.exception("TripoSR health probe failed")
        return False, "無法連線至 3D 推理服務。"

    if response.status_code != 200:
        return False, "3D 推理服務健康檢查失敗。"

    try:
        payload = response.json()
    except ValueError:
        return False, "3D 推理服務健康回應無效。"

    if payload.get("triposr_ok") is True:
        return True, None

    return False, payload.get("detail") or "3D 推理服務尚未就緒。"


_triposr_health_cache: tuple[bool, str | None, float] | None = None
_triposr_health_lock = asyncio.Lock()


async def _probe_triposr_cached() -> tuple[bool, str | None]:
    """對 TripoSR 做就緒探測並以 TTL 去重，避免 /health 與 /health/public 高頻呼叫放大成下游 DoS。"""
    global _triposr_health_cache
    ttl = float(os.environ.get("HEALTH_TRIPOSR_PROBE_TTL_SECONDS", "15"))
    if ttl <= 0:
        return await _probe_triposr(request_id=None)

    now = time.monotonic()
    cached = _triposr_health_cache
    if cached is not None:
        ok, detail, cached_at = cached
        if now - cached_at < ttl:
            return ok, detail

    async with _triposr_health_lock:
        now = time.monotonic()
        cached = _triposr_health_cache
        if cached is not None:
            ok, detail, cached_at = cached
            if now - cached_at < ttl:
                return ok, detail
        ok, detail = await _probe_triposr(request_id=None)
        _triposr_health_cache = (ok, detail, time.monotonic())
        return ok, detail


async def _readiness_full() -> tuple[int, dict[str, str | bool]]:
    ok, detail = await _probe_triposr_cached()
    body: dict[str, str | bool] = {
        "status": "ok" if ok else "degraded",
        "triposr_ok": ok,
    }
    if detail:
        body["detail"] = detail
    return (200 if ok else 503), body


async def _infer_glb(
    contents: bytes,
    filename: str,
    content_type: str,
    *,
    request_id: str | None = None,
) -> bytes:
    try:
        response = await _triposr_request(
            "POST",
            "/infer",
            request_id=request_id,
            files={"file": (filename, contents, content_type)},
        )
    except httpx.TimeoutException as exc:
        raise TriposrProxyError(503, "3D 轉換逾時，請稍後再試。") from exc
    except httpx.RequestError as exc:
        raise TriposrProxyError(503, "3D 推理服務暫時不可用。") from exc

    if response.status_code == 200:
        if not response.content:
            raise TriposrProxyError(502, "3D 推理服務回應為空。")
        return response.content

    if response.status_code in {413, 415, 422, 503}:
        raise TriposrProxyError(
            response.status_code,
            _extract_error_detail(response, "3D 轉換失敗。"),
        )

    raise TriposrProxyError(
        502,
        _extract_error_detail(response, "3D 推理服務暫時不可用。"),
    )


def _persist_job_artifacts_sync(
    job_id: str,
    detected_type: str | None,
    contents: bytes,
    glb: bytes,
) -> None:
    storage_root = get_storage_root()
    input_dir, output_dir = ensure_job_dirs(storage_root, job_id)

    try:
        ext = IMAGE_EXTENSION_BY_MIME_TYPE.get(detected_type or "", "bin")
        (input_dir / f"original.{ext}").write_bytes(contents)
        (output_dir / "model.glb").write_bytes(glb)
    except Exception:
        shutil.rmtree(input_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)
        raise


async def _persist_job_artifacts(
    job_id: str,
    detected_type: str | None,
    contents: bytes,
    glb: bytes,
) -> None:
    loop = asyncio.get_running_loop()
    await loop.run_in_executor(
        None,
        _persist_job_artifacts_sync,
        job_id,
        detected_type,
        contents,
        glb,
    )


@app.middleware("http")
async def add_response_headers(request: Request, call_next) -> Response:
    request.state.request_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    response: Response = await call_next(request)
    response.headers["X-Request-Id"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none'"
    return response


@app.get("/health/live")
async def health_live() -> JSONResponse:
    """Process liveness for orchestration probes; does not call TripoSR."""
    return JSONResponse(status_code=200, content={"status": "ok"})


@app.get("/health/public")
async def health_public() -> JSONResponse:
    """就緒狀態之最小 JSON（供 nginx 對外）；不含 triposr_ok／detail 以降低偵察面。完整欄位請 GET /health（須能直連 backend）。"""
    status_code, body = await _readiness_full()
    return JSONResponse(
        status_code=status_code,
        content={"status": body["status"]},
    )


@app.get("/health")
async def health(request: Request) -> JSONResponse:
    """Readiness: 503 when TripoSR 未就緒，供僅看 HTTP 狀態的探針使用；純存活請用 /health/live。

    對下游探測結果會快取 HEALTH_TRIPOSR_PROBE_TTL_SECONDS 秒（預設 15），設為 0 則每次即時探測。
    經 nginx 對外同源 /health 僅轉至此服務之 /health/public（不含下游細節）。
    """
    status_code, body = await _readiness_full()
    return JSONResponse(status_code=status_code, content=body)


@app.post(
    "/api/image-to-3d",
    dependencies=[Depends(enforce_image_to_3d_access)],
)
async def image_to_3d(file: UploadFile, request: Request) -> Response:
    allowed = ", ".join(sorted(ALLOWED_IMAGE_MIME_TYPES))
    contents, detected_type = await read_and_validate_upload(
        file,
        detect_type=detect_image_type,
        allowed_types=ALLOWED_IMAGE_MIME_TYPES,
        type_error_detail=f"檔案內容不是有效的格式。允許：{allowed}。",
    )

    try:
        glb = await _infer_glb(
            contents,
            file.filename or "upload-image",
            detected_type or "application/octet-stream",
            request_id=_request_id(request) or None,
        )
    except TriposrProxyError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=_with_request_id(exc.detail, request),
        ) from None

    job_id = str(uuid.uuid4())
    try:
        await _persist_job_artifacts(job_id, detected_type, contents, glb)
    except Exception:
        logger.exception("Failed to persist image-to-3d artifacts for job_id=%s", job_id)
        raise HTTPException(
            status_code=500,
            detail=_with_request_id("3D 檔案儲存失敗，請重試。", request),
        ) from None

    logger.info("Returned TripoSR GLB (input size: %d bytes)", len(contents))
    return Response(
        content=glb,
        media_type="model/gltf-binary",
        headers={
            "Content-Disposition": 'attachment; filename="model.glb"',
            "X-Job-Id": job_id,
        },
    )
