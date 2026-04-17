"""Optional access controls for POST /api/image-to-3d (lab vs. exposed deployments)."""

from __future__ import annotations

import asyncio
import hmac
import os
import time
from collections import deque

from fastapi import HTTPException, Request

def _trust_proxy_headers() -> bool:
    return os.environ.get("TRUST_PROXY_HEADERS", "").strip().lower() in {
        "1",
        "true",
        "yes",
    }


# Per-client timestamps (monotonic) inside the sliding window.
_timestamps_by_client: dict[str, deque[float]] = {}
_lock = asyncio.Lock()


def _configured_api_key() -> str | None:
    key = os.environ.get("IMAGE_TO_3D_API_KEY", "").strip()
    return key or None


def _extract_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if not auth:
        return None
    prefix = "Bearer "
    if not auth.startswith(prefix):
        return None
    return auth[len(prefix) :].strip() or None


def _provided_secret(request: Request) -> str | None:
    bearer = _extract_bearer_token(request)
    if bearer is not None:
        return bearer
    header_key = request.headers.get("X-API-Key")
    if header_key is not None and header_key.strip():
        return header_key.strip()
    return None


def _client_identity(request: Request) -> str:
    if _trust_proxy_headers():
        xff = request.headers.get("X-Forwarded-For")
        if xff:
            return xff.split(",")[0].strip() or "unknown"
        xri = request.headers.get("X-Real-IP")
        if xri and xri.strip():
            return xri.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _verify_api_key(request: Request) -> None:
    expected = _configured_api_key()
    if expected is None:
        return
    provided = _provided_secret(request)
    if provided is None:
        raise HTTPException(
            status_code=401,
            detail="需要 API 金鑰（Authorization: Bearer 或 X-API-Key）。",
        )
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="API 金鑰無效。")


async def _enforce_rate_limit(request: Request) -> None:
    window_seconds = float(os.environ.get("IMAGE_TO_3D_RATE_LIMIT_WINDOW_SECONDS", "60"))
    max_per_window = int(os.environ.get("IMAGE_TO_3D_RATE_LIMIT_MAX_REQUESTS", "10"))
    if max_per_window <= 0:
        return
    client_id = _client_identity(request)
    now = time.monotonic()
    async with _lock:
        dq = _timestamps_by_client.setdefault(client_id, deque())
        while dq and now - dq[0] > window_seconds:
            dq.popleft()
        if len(dq) >= max_per_window:
            raise HTTPException(
                status_code=429,
                detail="請求過於頻繁，請稍後再試。",
                headers={"Retry-After": str(int(window_seconds))},
            )
        dq.append(now)


async def enforce_image_to_3d_access(request: Request) -> None:
    """Runs before the route handler: optional Bearer / X-API-Key and per-client rate limit."""
    _verify_api_key(request)
    await _enforce_rate_limit(request)
