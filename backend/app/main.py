"""FastAPI application for the single-step image-to-3D flow."""

from __future__ import annotations

import logging
import os
import shutil
import uuid

import httpx
from fastapi import FastAPI, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_storage_root
from app.storage_paths import ensure_job_dirs
from app.validation import (
    ALLOWED_IMAGE_MIME_TYPES,
    detect_image_type,
    read_and_validate_upload,
)

logger = logging.getLogger(__name__)

TRIPOSR_API_URL = os.environ.get("TRIPOSR_API_URL", "http://localhost:8001").rstrip("/")
TRIPOSR_API_TIMEOUT_SECONDS = float(os.environ.get("TRIPOSR_API_TIMEOUT_SECONDS", "60"))
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
    allow_origins=os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-Id"],
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
    files: dict[str, tuple[str, bytes, str]] | None = None,
) -> httpx.Response:
    headers = {"X-Request-Id": str(uuid.uuid4())}
    async with httpx.AsyncClient(timeout=TRIPOSR_API_TIMEOUT_SECONDS) as client:
        return await client.request(
            method,
            f"{TRIPOSR_API_URL}{path}",
            files=files,
            headers=headers,
        )


async def _probe_triposr() -> tuple[bool, str | None]:
    try:
        response = await _triposr_request("GET", "/health")
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


async def _infer_glb(contents: bytes, filename: str, content_type: str) -> bytes:
    try:
        response = await _triposr_request(
            "POST",
            "/infer",
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


def _persist_job_artifacts(
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


@app.get("/health")
async def health() -> JSONResponse:
    ok, detail = await _probe_triposr()
    content: dict[str, str | bool] = {
        "status": "ok" if ok else "degraded",
        "triposr_ok": ok,
    }
    if detail:
        content["detail"] = detail
    return JSONResponse(status_code=200, content=content)


@app.post("/api/image-to-3d")
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
        )
    except TriposrProxyError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail=_with_request_id(exc.detail, request),
        ) from None

    job_id = str(uuid.uuid4())
    try:
        _persist_job_artifacts(job_id, detected_type, contents, glb)
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
