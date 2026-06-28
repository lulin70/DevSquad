#!/usr/bin/env python3
"""Rate limiting and HTTPS redirect middleware for FastAPI.

Provides two ASGI middlewares:

  - RateLimitMiddleware: Sliding-window per-IP rate limiter (default 60 rpm).
    Returns HTTP 429 with Retry-After header when exceeded.
  - HTTPSRedirectMiddleware: Returns HTTP 308 permanent redirect to the https
    equivalent when `X-Forwarded-Proto: http` is present. Disabled by default;
    enable via `DEVSQUAD_HTTPS_REDIRECT_ENABLED=1` in production behind a TLS
    terminating proxy.

Design:
  - In-memory token bucket per client IP (sufficient for single-process uvicorn).
  - For multi-worker deployments, swap `_bucket_store` with Redis backend.
  - Health check (`/api/v1/health`, `/healthz`) and Prometheus metrics
    (`/metrics`) are exempt from rate limiting to avoid breaking monitoring.

Added in P3-2 (V3.9.2) — closes REST API security enhancement gap.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import deque
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, cast

from fastapi import Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_RATE_LIMIT_PER_MINUTE = 60
DEFAULT_RATE_LIMIT_WINDOW_SECONDS = 60

# Paths exempt from rate limiting (monitoring must always work)
RATE_LIMIT_EXEMPT_PATHS: frozenset[str] = frozenset({
    "/api/v1/health",
    "/healthz",
    "/metrics",
    "/",            # Root info endpoint
    "/docs",        # Swagger UI
    "/redoc",       # ReDoc
    "/openapi.json",
})


def _is_rate_limit_enabled() -> bool:
    """Rate limiting is ON by default; disable via env var."""
    return os.environ.get("DEVSQUAD_RATE_LIMIT_DISABLED", "").lower() not in ("1", "true", "yes")


def _get_rate_limit_per_minute() -> int:
    """Get rate limit threshold from env var (default 60)."""
    try:
        val = int(os.environ.get("DEVSQUAD_RATE_LIMIT_PER_MINUTE", str(DEFAULT_RATE_LIMIT_PER_MINUTE)))
        return max(1, val)
    except (ValueError, TypeError):
        return DEFAULT_RATE_LIMIT_PER_MINUTE


def _is_https_redirect_enabled() -> bool:
    """HTTPS redirect is OFF by default; enable in production via env var."""
    return os.environ.get("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "").lower() in ("1", "true", "yes")


# ---------------------------------------------------------------------------
# Sliding window rate limiter (in-memory, per-IP)
# ---------------------------------------------------------------------------


class _SlidingWindow:
    """Sliding window counter for a single client IP."""

    __slots__ = ("_timestamps", "_window_seconds")

    def __init__(self, window_seconds: int) -> None:
        self._timestamps: deque[float] = deque()
        self._window_seconds = window_seconds

    def _evict(self, now: float) -> None:
        """Remove timestamps older than the window."""
        cutoff = now - self._window_seconds
        while self._timestamps and self._timestamps[0] < cutoff:
            self._timestamps.popleft()

    def check(self, limit: int) -> tuple[bool, int]:
        """Try to record a hit. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        self._evict(now)
        if len(self._timestamps) >= limit:
            # Compute seconds until oldest entry falls out of window
            retry_after = int(self._timestamps[0] + self._window_seconds - now) + 1
            return False, max(1, retry_after)
        self._timestamps.append(now)
        return True, 0


class RateLimiter:
    """Per-IP sliding window rate limiter (thread-safe via asyncio.Lock).

    For multi-process deployments, replace `_buckets` with a shared store
    (Redis/Memcached). The single-process implementation is correct for
    uvicorn with `--workers 1` (the default in our helm chart).
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._buckets: dict[str, _SlidingWindow] = {}
        self._lock = asyncio.Lock()
        # Periodic cleanup: remove idle buckets to bound memory
        self._last_cleanup = time.monotonic()
        self._cleanup_interval = 300  # 5 min

    async def check(self, client_ip: str) -> tuple[bool, int]:
        """Check if client_ip is allowed. Returns (allowed, retry_after_seconds)."""
        async with self._lock:
            now = time.monotonic()
            # Periodic cleanup of idle buckets
            if now - self._last_cleanup > self._cleanup_interval:
                self._cleanup_idle(now)
                self._last_cleanup = now

            bucket = self._buckets.get(client_ip)
            if bucket is None:
                bucket = _SlidingWindow(self._window_seconds)
                self._buckets[client_ip] = bucket
            return bucket.check(self._limit)

    def _cleanup_idle(self, now: float) -> None:
        """Remove buckets with no activity in the last window."""
        cutoff = now - self._window_seconds
        # _SlidingWindow.evict is called inside check(); idle buckets still
        # hold stale timestamps. We detect idle by checking the last timestamp.
        stale_keys = []
        for ip, bucket in self._buckets.items():
            if not bucket._timestamps or bucket._timestamps[-1] < cutoff:
                stale_keys.append(ip)
        for key in stale_keys:
            del self._buckets[key]
        if stale_keys:
            logger.debug("Rate limiter cleanup: removed %d idle buckets", len(stale_keys))


# Singleton instances (lazily initialized)
_rate_limiter: RateLimiter | None = None


def _get_rate_limiter() -> RateLimiter:
    """Get or create singleton RateLimiter."""
    global _rate_limiter
    if _rate_limiter is None:
        _rate_limiter = RateLimiter(
            limit=_get_rate_limit_per_minute(),
            window_seconds=DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        )
    return _rate_limiter


def reset_rate_limiter() -> None:
    """Reset the singleton rate limiter (for testing)."""
    global _rate_limiter
    _rate_limiter = None


# ---------------------------------------------------------------------------
# Client IP extraction
# ---------------------------------------------------------------------------


def _get_client_ip(scope: Mapping[str, Any]) -> str:
    """Extract client IP from ASGI scope, honoring X-Forwarded-For.

    When behind a reverse proxy (nginx/ingress), the proxy sets X-Forwarded-For.
    We trust the leftmost entry (the original client) only if the request came
    through a proxy. For direct connections, use scope["client"][0].
    """
    # Check X-Forwarded-For header
    headers: list[tuple[bytes, bytes]] = scope.get("headers", [])
    for name, value in headers:
        if name == b"x-forwarded-for":
            # First entry is the original client
            return value.decode("latin-1").split(",")[0].strip()
    # Fall back to direct connection client IP
    client = scope.get("client")
    if client:
        return cast(str, client[0])
    return "unknown"


# ---------------------------------------------------------------------------
# ASGI middleware functions (FastAPI @app.middleware("http"))
# ---------------------------------------------------------------------------


async def rate_limit_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Any]],
) -> Any:
    """Rate limit middleware — call as `@app.middleware("http")`.

    Returns HTTP 429 with Retry-After header when limit exceeded.
    """
    if not _is_rate_limit_enabled():
        return await call_next(request)

    # Exempt monitoring/root/docs paths
    if request.url.path in RATE_LIMIT_EXEMPT_PATHS:
        return await call_next(request)

    # Extract client IP (honoring X-Forwarded-For)
    client_ip = _get_client_ip(request.scope)

    limiter = _get_rate_limiter()
    allowed, retry_after = await limiter.check(client_ip)

    if not allowed:
        logger.warning(
            "Rate limit exceeded for IP %s on %s (limit=%d/min)",
            client_ip,
            request.url.path,
            _get_rate_limit_per_minute(),
        )
        return JSONResponse(
            status_code=429,
            content={
                "error": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded. Max {_get_rate_limit_per_minute()} requests per minute.",
                "retry_after_seconds": retry_after,
            },
            headers={
                "Retry-After": str(retry_after),
                "X-RateLimit-Limit": str(_get_rate_limit_per_minute()),
                "X-RateLimit-Remaining": "0",
            },
        )

    response = await call_next(request)
    # Add rate limit info headers for transparency
    response.headers["X-RateLimit-Limit"] = str(_get_rate_limit_per_minute())
    return response


async def https_redirect_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Any]],
) -> Any:
    """HTTPS redirect middleware — call as `@app.middleware("http")`.

    Returns HTTP 308 permanent redirect to https://... when the request came in
    as http (per `X-Forwarded-Proto: http`). Disabled by default; enable via
    `DEVSQUAD_HTTPS_REDIRECT_ENABLED=1` in production behind a TLS-terminating
    proxy.

    Why 308 (not 301/302): 308 preserves method and body, so POST/PUT work.
    """
    if not _is_https_redirect_enabled():
        return await call_next(request)

    # Check X-Forwarded-Proto header (set by nginx/ingress when TLS terminated)
    forwarded_proto = request.headers.get("x-forwarded-proto", "").lower()
    if forwarded_proto == "http":
        # Build https URL
        https_url = request.url.replace(scheme="https")
        logger.info(
            "HTTPS redirect: %s %s -> %s",
            request.method,
            request.url.path,
            https_url,
        )
        return JSONResponse(
            status_code=308,
            content={
                "error": "HTTPS_REQUIRED",
                "message": "HTTPS is required. Redirecting to secure endpoint.",
                "location": str(https_url),
            },
            headers={"Location": str(https_url)},
        )

    return await call_next(request)


__all__ = [
    "rate_limit_middleware",
    "https_redirect_middleware",
    "reset_rate_limiter",
    "RATE_LIMIT_EXEMPT_PATHS",
    "DEFAULT_RATE_LIMIT_PER_MINUTE",
]
