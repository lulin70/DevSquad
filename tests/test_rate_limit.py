#!/usr/bin/env python3
"""Tests for P3-2 Rate Limiting and HTTPS Redirect middleware.

Validates:
  - RateLimitMiddleware: per-IP sliding window, exempt paths, 429 + Retry-After
  - HTTPSRedirectMiddleware: disabled by default, 308 on X-Forwarded-Proto: http
  - Env var configuration (DEVSQUAD_RATE_LIMIT_DISABLED, _PER_MINUTE,
    DEVSQUAD_HTTPS_REDIRECT_ENABLED)
  - Singleton reset helper for test isolation

Design doc: docs/_archive/assessments/IMPROVEMENT_PLAN_V3.9.2.md (P3-2)
"""

from __future__ import annotations

import asyncio
import os
import sys
import time

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.api.rate_limit import (
    DEFAULT_RATE_LIMIT_PER_MINUTE,
    RATE_LIMIT_EXEMPT_PATHS,
    RateLimiter,
    _get_client_ip,
    _get_rate_limit_per_minute,
    _is_https_redirect_enabled,
    _is_rate_limit_enabled,
    _SlidingWindow,
    https_redirect_middleware,
    rate_limit_middleware,
    reset_rate_limiter,
)

# ---------------------------------------------------------------------------
# Test app fixture
# ---------------------------------------------------------------------------


def _build_test_app() -> FastAPI:
    """Build a minimal FastAPI app with rate_limit + https_redirect middleware."""
    app = FastAPI()

    @app.middleware("http")
    async def _rl(request: Request, call_next):
        return await rate_limit_middleware(request, call_next)

    @app.middleware("http")
    async def _hr(request: Request, call_next):
        return await https_redirect_middleware(request, call_next)

    @app.get("/")
    async def root():
        return {"hello": "world"}

    @app.get("/api/v1/health")
    async def health():
        return {"status": "ok"}

    @app.get("/api/v1/tasks")
    async def tasks():
        return {"tasks": []}

    @app.post("/api/v1/tasks/dispatch")
    async def dispatch():
        return {"dispatched": True}

    return app


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    """Reset rate limiter singleton + clear env vars before each test."""
    # Clear all rate_limit-related env vars
    for var in ("DEVSQUAD_RATE_LIMIT_DISABLED", "DEVSQUAD_RATE_LIMIT_PER_MINUTE", "DEVSQUAD_HTTPS_REDIRECT_ENABLED"):
        monkeypatch.delenv(var, raising=False)
    reset_rate_limiter()
    yield
    reset_rate_limiter()


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


class TestConfiguration:
    """Test env var driven configuration."""

    def test_rate_limit_enabled_by_default(self):
        assert _is_rate_limit_enabled() is True

    def test_rate_limit_disabled_via_env(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_DISABLED", "1")
        assert _is_rate_limit_enabled() is False

    def test_rate_limit_disabled_via_env_true(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_DISABLED", "true")
        assert _is_rate_limit_enabled() is False

    def test_rate_limit_default_per_minute(self):
        assert _get_rate_limit_per_minute() == DEFAULT_RATE_LIMIT_PER_MINUTE
        assert DEFAULT_RATE_LIMIT_PER_MINUTE == 60

    def test_rate_limit_custom_per_minute(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "100")
        assert _get_rate_limit_per_minute() == 100

    def test_rate_limit_invalid_per_minute_falls_back(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "not-a-number")
        assert _get_rate_limit_per_minute() == DEFAULT_RATE_LIMIT_PER_MINUTE

    def test_rate_limit_zero_per_minute_clamped_to_one(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "0")
        assert _get_rate_limit_per_minute() == 1

    def test_rate_limit_negative_per_minute_clamped_to_one(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "-5")
        assert _get_rate_limit_per_minute() == 1

    def test_https_redirect_disabled_by_default(self):
        assert _is_https_redirect_enabled() is False

    def test_https_redirect_enabled_via_env(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "1")
        assert _is_https_redirect_enabled() is True

    def test_https_redirect_enabled_via_env_true(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "true")
        assert _is_https_redirect_enabled() is True

    def test_exempt_paths_include_health_and_metrics(self):
        assert "/api/v1/health" in RATE_LIMIT_EXEMPT_PATHS
        assert "/healthz" in RATE_LIMIT_EXEMPT_PATHS
        assert "/metrics" in RATE_LIMIT_EXEMPT_PATHS


# ---------------------------------------------------------------------------
# SlidingWindow unit tests
# ---------------------------------------------------------------------------


class TestSlidingWindow:
    """Test the _SlidingWindow primitive directly."""

    def test_allows_up_to_limit(self):
        sw = _SlidingWindow(window_seconds=60)
        for _ in range(5):
            allowed, retry = sw.check(limit=5)
            assert allowed is True
            assert retry == 0

    def test_blocks_when_limit_exceeded(self):
        sw = _SlidingWindow(window_seconds=60)
        for _ in range(3):
            sw.check(limit=3)
        allowed, retry = sw.check(limit=3)
        assert allowed is False
        assert retry >= 1

    def test_retry_after_is_positive_int(self):
        sw = _SlidingWindow(window_seconds=60)
        for _ in range(2):
            sw.check(limit=2)
        _, retry = sw.check(limit=2)
        assert isinstance(retry, int)
        assert retry >= 1
        assert retry <= 60

    def test_window_evicts_old_entries(self):
        sw = _SlidingWindow(window_seconds=1)
        # Fill bucket
        sw.check(limit=2)
        sw.check(limit=2)
        # Wait for window to expire
        time.sleep(1.1)
        allowed, _ = sw.check(limit=2)
        assert allowed is True


# ---------------------------------------------------------------------------
# RateLimiter async tests
# ---------------------------------------------------------------------------


class TestRateLimiter:
    """Test the RateLimiter class (async)."""

    @pytest.mark.asyncio
    async def test_allows_under_limit(self):
        limiter = RateLimiter(limit=5, window_seconds=60)
        for i in range(5):
            allowed, _ = await limiter.check("1.2.3.4")
            assert allowed is True, f"Request {i + 1} should be allowed"

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self):
        limiter = RateLimiter(limit=3, window_seconds=60)
        for _ in range(3):
            await limiter.check("1.2.3.4")
        allowed, retry = await limiter.check("1.2.3.4")
        assert allowed is False
        assert retry >= 1

    @pytest.mark.asyncio
    async def test_separate_ips_have_separate_buckets(self):
        limiter = RateLimiter(limit=2, window_seconds=60)
        # IP A exhausts limit
        await limiter.check("10.0.0.1")
        await limiter.check("10.0.0.1")
        allowed_a, _ = await limiter.check("10.0.0.1")
        assert allowed_a is False
        # IP B still has fresh budget
        allowed_b, _ = await limiter.check("10.0.0.2")
        assert allowed_b is True

    @pytest.mark.asyncio
    async def test_cleanup_removes_idle_buckets(self):
        limiter = RateLimiter(limit=10, window_seconds=1)
        limiter._cleanup_interval = 0  # force cleanup on next check
        # Add a bucket
        await limiter.check("1.1.1.1")
        assert "1.1.1.1" in limiter._buckets
        # Wait for idle
        time.sleep(1.2)
        # Trigger cleanup via check on a different IP
        await limiter.check("2.2.2.2")
        assert "1.1.1.1" not in limiter._buckets

    @pytest.mark.asyncio
    async def test_concurrent_checks_are_serialized(self):
        """Verify asyncio.Lock serializes concurrent checks (no race)."""
        limiter = RateLimiter(limit=10, window_seconds=60)
        # Fire 20 concurrent checks; all should be serialized
        results = await asyncio.gather(*[limiter.check("1.2.3.4") for _ in range(20)])
        allowed_count = sum(1 for r in results if r[0])
        # Exactly 10 should be allowed (the limit), 10 blocked
        assert allowed_count == 10


# ---------------------------------------------------------------------------
# Client IP extraction
# ---------------------------------------------------------------------------


class TestGetClientIp:
    """Test _get_client_ip with various ASGI scopes."""

    def test_uses_x_forwarded_for_first_entry(self):
        scope = {
            "headers": [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")],
            "client": ("127.0.0.1", 8000),
        }
        assert _get_client_ip(scope) == "1.2.3.4"

    def test_falls_back_to_scope_client(self):
        scope = {"headers": [], "client": ("127.0.0.1", 8000)}
        assert _get_client_ip(scope) == "127.0.0.1"

    def test_returns_unknown_when_no_client(self):
        scope = {"headers": []}
        assert _get_client_ip(scope) == "unknown"

    def test_handles_single_ip_in_xff(self):
        scope = {
            "headers": [(b"x-forwarded-for", b"192.168.1.100")],
            "client": ("127.0.0.1", 8000),
        }
        assert _get_client_ip(scope) == "192.168.1.100"

    def test_strips_whitespace_in_xff(self):
        scope = {
            "headers": [(b"x-forwarded-for", b"  1.2.3.4  ,  10.0.0.1")],
            "client": ("127.0.0.1", 8000),
        }
        assert _get_client_ip(scope) == "1.2.3.4"


# ---------------------------------------------------------------------------
# Integration: rate_limit_middleware via TestClient
# ---------------------------------------------------------------------------


class TestRateLimitMiddlewareIntegration:
    """Integration tests using FastAPI TestClient."""

    def test_request_succeeds_under_limit(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "10")
        reset_rate_limiter()
        app = _build_test_app()
        client = TestClient(app)
        r = client.get("/api/v1/tasks")
        assert r.status_code == 200
        assert "X-RateLimit-Limit" in r.headers
        assert r.headers["X-RateLimit-Limit"] == "10"

    def test_exceeding_limit_returns_429(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "3")
        reset_rate_limiter()
        app = _build_test_app()
        client = TestClient(app)
        # Send 3 requests (allowed)
        for _ in range(3):
            r = client.get("/api/v1/tasks")
            assert r.status_code == 200
        # 4th should be 429
        r = client.get("/api/v1/tasks")
        assert r.status_code == 429
        assert r.json()["error"] == "RATE_LIMIT_EXCEEDED"
        assert "Retry-After" in r.headers
        assert int(r.headers["Retry-After"]) >= 1
        assert r.headers["X-RateLimit-Remaining"] == "0"

    def test_exempt_paths_bypass_rate_limit(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "1")
        reset_rate_limiter()
        app = _build_test_app()
        client = TestClient(app)
        # Health check should bypass limit
        for _ in range(5):
            r = client.get("/api/v1/health")
            assert r.status_code == 200
        # Even after 5 health checks, /api/v1/tasks still has 1 request left
        r = client.get("/api/v1/tasks")
        assert r.status_code == 200

    def test_disabled_via_env_allows_unlimited(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_DISABLED", "1")
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "1")
        reset_rate_limiter()
        app = _build_test_app()
        client = TestClient(app)
        for _ in range(20):
            r = client.get("/api/v1/tasks")
            assert r.status_code == 200

    def test_post_request_blocked_when_over_limit(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "2")
        reset_rate_limiter()
        app = _build_test_app()
        client = TestClient(app)
        # 2 POSTs allowed
        for _ in range(2):
            r = client.post("/api/v1/tasks/dispatch")
            assert r.status_code == 200
        # 3rd blocked
        r = client.post("/api/v1/tasks/dispatch")
        assert r.status_code == 429

    def test_rate_limit_is_per_ip(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_RATE_LIMIT_PER_MINUTE", "2")
        reset_rate_limiter()
        app = _build_test_app()
        client = TestClient(app)
        # IP A exhausts limit (TestClient uses 127.0.0.1 by default, simulate via header)
        for _ in range(2):
            r = client.get("/api/v1/tasks", headers={"X-Forwarded-For": "1.1.1.1"})
            assert r.status_code == 200
        # IP A blocked
        r = client.get("/api/v1/tasks", headers={"X-Forwarded-For": "1.1.1.1"})
        assert r.status_code == 429
        # IP B still allowed
        r = client.get("/api/v1/tasks", headers={"X-Forwarded-For": "2.2.2.2"})
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# Integration: https_redirect_middleware via TestClient
# ---------------------------------------------------------------------------


class TestHttpsRedirectMiddlewareIntegration:
    """Integration tests for HTTPS redirect middleware."""

    def test_disabled_by_default_no_redirect(self):
        app = _build_test_app()
        client = TestClient(app)
        # Even with X-Forwarded-Proto: http, no redirect (disabled by default)
        r = client.get("/api/v1/tasks", headers={"X-Forwarded-Proto": "http"})
        assert r.status_code == 200

    def test_enabled_redirects_http_to_https(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "1")
        app = _build_test_app()
        # Disable follow_redirects so we can inspect the 308 response itself
        client = TestClient(app, follow_redirects=False)
        r = client.get("/api/v1/tasks", headers={"X-Forwarded-Proto": "http"})
        assert r.status_code == 308
        assert "Location" in r.headers
        assert r.headers["Location"].startswith("https://")
        assert r.json()["error"] == "HTTPS_REQUIRED"

    def test_enabled_no_redirect_when_already_https(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "1")
        app = _build_test_app()
        client = TestClient(app)
        r = client.get("/api/v1/tasks", headers={"X-Forwarded-Proto": "https"})
        assert r.status_code == 200

    def test_enabled_no_redirect_when_no_header(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "1")
        app = _build_test_app()
        client = TestClient(app)
        r = client.get("/api/v1/tasks")
        assert r.status_code == 200

    def test_redirect_preserves_path_and_query(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_HTTPS_REDIRECT_ENABLED", "1")
        app = _build_test_app()
        client = TestClient(app, follow_redirects=False)
        r = client.get(
            "/api/v1/tasks?role=architect&mode=consensus",
            headers={"X-Forwarded-Proto": "http"},
        )
        assert r.status_code == 308
        location = r.headers["Location"]
        assert location.startswith("https://")
        assert "/api/v1/tasks" in location
        assert "role=architect" in location
        assert "mode=consensus" in location


# ---------------------------------------------------------------------------
# Reset helper
# ---------------------------------------------------------------------------


class TestResetHelper:
    """Test reset_rate_limiter for test isolation."""

    def test_reset_clears_singleton(self):
        # First call creates singleton
        from scripts.api.rate_limit import _get_rate_limiter

        _ = _get_rate_limiter()
        # Reset
        reset_rate_limiter()
        # Module-level singleton should be None now
        import scripts.api.rate_limit as rl

        assert rl._rate_limiter is None
