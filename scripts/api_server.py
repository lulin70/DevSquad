#!/usr/bin/env python3
"""
DevSquad REST API Server (FastAPI)

Production-ready REST API for DevSquad lifecycle management.

Features:
  - FastAPI with automatic OpenAPI/Swagger documentation
  - Lifecycle phase management endpoints
  - Metrics and monitoring APIs
  - Gate status checking
  - Health check endpoint
  - CORS support
  - Request logging

Usage:
    # Start API server
    uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

    # Access Swagger UI
    http://localhost:8000/docs

    # Access ReDoc documentation
    http://localhost:8000/redoc

Requirements:
    fastapi>=0.100.0
    uvicorn[standard]>=0.23.0
"""

import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional, cast

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

if TYPE_CHECKING:
    from scripts.auth import AuthManager

from scripts.api.rate_limit import (
    https_redirect_middleware,
    rate_limit_middleware,
)
from scripts.api.routes.dispatch import router as dispatch_router

# Import routes
from scripts.api.routes.lifecycle import router as lifecycle_router
from scripts.api.routes.metrics import router as prometheus_router
from scripts.api.routes.metrics_gates import router as metrics_router
from scripts.collaboration._version import __version__ as DEVSQUAD_VERSION

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)

# Readiness flag — set True on startup, False on shutdown.
# /ready returns 503 when False, allowing load balancers to drain traffic
# before uvicorn completes the shutdown sequence.
_app_ready: bool = False

# Create FastAPI application
app = FastAPI(
    title="DevSquad API",
    description=f"""
    ## DevSquad V{DEVSQUAD_VERSION} REST API

    Production-ready API for DevSquad multi-agent collaboration.

    ### 核心功能 / Core Features

    * **Task Dispatch**: Multi-agent task orchestration (任务调度)
    * **Lifecycle Management**: Query and control 11-phase lifecycle (生命周期管理)
    * **Metrics & Monitoring**: Real-time performance metrics (实时监控)
    * **Gate Status**: Check and monitor quality gates (质量门禁)
    * **Health Checks**: Service health monitoring (健康检查)

    ### Authentication / 认证

    API supports optional authentication via AuthManager.
    Configure in config/deployment.yaml or disable for development.

    ### Rate Limiting / 限流

    Default: 60 requests/minute per IP address.

    ---

    **Version**: {DEVSQUAD_VERSION}
    **Base URL**: `/api/v1`
    """,
    version=DEVSQUAD_VERSION,
    docs_url="/docs",  # Swagger UI
    redoc_url="/redoc",  # ReDoc
    openapi_url="/openapi.json",  # OpenAPI spec
    contact={
        "name": "DevSquad Team",
        "url": "https://github.com/devsquad",
        "email": "devsquad@example.com",
    },
    license_info={
        "name": "MIT License",
        "url": "https://opensource.org/licenses/MIT",
    },
)

# Add CORS middleware
# ⚠️  Do NOT use wildcard "*" with allow_credentials=True (CORS spec violation)
# Configure allowed origins explicitly; use env var DEVSQUAD_CORS_ORIGINS in production

_cors_origins_str = os.environ.get("DEVSQUAD_CORS_ORIGINS", "")
if _cors_origins_str:
    allowed_origins = [o.strip() for o in _cors_origins_str.split(",") if o.strip()]
else:
    # Development defaults only - no wildcard with credentials
    allowed_origins = [
        "http://localhost:8501",  # DevSquad Dashboard
        "http://localhost:8000",  # API Server
        "http://localhost:3000",  # Frontend dev server
    ]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
)


# Request timing middleware
@app.middleware("http")
async def add_process_time_header(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    """Add processing time header to responses."""
    start_time = time.time()

    # Log request
    logger.info("Request: %s %s", request.method, request.url.path)

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.3f}"

    # Log response
    logger.info("Response: %s (took %.3fs)", response.status_code, process_time)

    return response


# HTTPS redirect middleware (P3-2, disabled by default; enable in production)
# Must be registered BEFORE rate_limit so http requests are redirected before
# consuming rate limit budget.
@app.middleware("http")
async def _https_redirect(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    return cast(Response, await https_redirect_middleware(request, call_next))


# Rate limit middleware (P3-2, default 60 rpm per IP)
@app.middleware("http")
async def _rate_limit(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    return cast(Response, await rate_limit_middleware(request, call_next))


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with custom error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Handle unhandled exceptions."""
    logger.error("Unhandled exception: %s", exc, exc_info=True)

    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": str(exc) if app.debug else None,
            "status_code": 500,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path,
        },
    )


# Include routers
app.include_router(lifecycle_router)
app.include_router(metrics_router)
app.include_router(dispatch_router)
app.include_router(prometheus_router)


# Auth dependency injection (optional, based on AuthManager)
def get_auth_manager() -> Optional["AuthManager"]:
    """Get AuthManager instance for dependency injection."""
    try:
        from scripts.auth import AuthManager

        return AuthManager()
    except (ImportError, RuntimeError, ValueError, OSError):
        return None


async def get_auth_dependency() -> Optional["AuthManager"]:
    """
    Optional auth dependency - can be used by endpoints that need authentication.
    Returns AuthManager if enabled, None otherwise.
    """
    return get_auth_manager()


# Root endpoint
@app.get("/", tags=["Root"])
async def root() -> dict[str, Any]:
    """
    Root endpoint - API information.

    Returns basic API information and available endpoints.

    根端点 - API信息。返回基本API信息和可用端点。
    """
    return {
        "name": "DevSquad API",
        "version": DEVSQUAD_VERSION,
        "description": "Production REST API for DevSquad multi-agent collaboration",
        "documentation": {"swagger_ui": "/docs", "redoc": "/redoc", "openapi_spec": "/openapi.json"},
        "endpoints": {
            "task_dispatch": "/api/v1/tasks/",
            "quick_dispatch": "/api/v1/tasks/quick",
            "dispatch_history": "/api/v1/tasks/history",
            "roles": "/api/v1/roles",
            "lifecycle": "/api/v1/lifecycle/",
            "metrics": "/api/v1/metrics/",
            "gates": "/api/v1/gates/",
            "health": "/api/v1/health",
            "ready": "/api/v1/ready",
            "prometheus": "/metrics",
        },
        "features": {
            "task_dispatch": "Multi-Agent task orchestration with 7 roles",
            "lifecycle_management": "11-phase lifecycle control",
            "real_time_metrics": "CPU/Memory/Response time monitoring",
            "quality_gates": "Gate status checking for CI/CD",
            "auth_integration": "Optional AuthManager integration",
            "prometheus_metrics": "Prometheus /metrics endpoint for scraping",
        },
        "status": "operational",
        "timestamp": datetime.now().isoformat(),
    }


# Readiness probe — separated from /health (liveness) for K8s/load-balancer traffic management.
# /health reports component status; /ready reports traffic-readiness (503 during startup/shutdown).
@app.get("/api/v1/ready", tags=["Health"])
async def readiness_check() -> dict[str, Any]:
    """Readiness probe — returns 503 when not ready (startup/shutdown).

    Use for K8s/load-balancer readiness checks. Returns 200 only when the
    application has completed startup and is accepting traffic.
    """
    if not _app_ready:
        raise HTTPException(status_code=503, detail="Service not ready")
    return {
        "ready": True,
        "version": DEVSQUAD_VERSION,
        "timestamp": datetime.now().isoformat(),
    }


# Startup event
@app.on_event("startup")
async def startup_event() -> None:
    """
    Execute on application startup.

    Initialize components and log startup message.
    """
    # Import security status for startup logging
    try:
        from scripts.api.security import get_security_status

        sec_status = get_security_status()
    except (ImportError, RuntimeError, OSError):
        sec_status = {
            "auth_enabled": False,
            "api_keys_configured": False,
            "audit_logger_available": False,
            "rbac_engine_available": False,
        }

    logger.info("=" * 60)
    logger.info("🚀 DevSquad API Server Starting...")
    logger.info("=" * 60)
    logger.info("Version: %s", DEVSQUAD_VERSION)
    logger.info("Time: %s", datetime.now().isoformat())
    logger.info("Components:")
    logger.info("  ✅ FastAPI initialized")
    logger.info("  ✅ Lifecycle routes registered")
    logger.info("  ✅ Metrics routes registered")
    logger.info("  ✅ Task Dispatch routes registered (NEW)")
    logger.info("  ✅ Prometheus /metrics endpoint registered (NEW)")
    if _cors_origins_str:
        logger.info(
            "  ✅ CORS middleware enabled (explicit: %d origins from DEVSQUAD_CORS_ORIGINS)", len(allowed_origins)
        )
    else:
        logger.info("  ✅ CORS middleware enabled (dev defaults: %d localhost origins)", len(allowed_origins))
    logger.info("  ⏱️  Request timing enabled")
    logger.info("Security:")
    if sec_status.get("auth_enabled"):
        logger.info("  🔐 API Key authentication: ENABLED")
        logger.info("  🔑 API keys configured: %s", sec_status.get("api_key_count", 0))
    else:
        logger.info("  ⚠️  API Key authentication: DISABLED (set DEVSQUAD_API_AUTH_DISABLED=0 to enable)")
    logger.info("  📋 RBAC engine: %s", "ready" if sec_status.get("rbac_engine_available") else "unavailable")
    logger.info("  📝 Audit logger: %s", "ready" if sec_status.get("audit_logger_available") else "unavailable")
    # P3-2 middlewares
    from scripts.api.rate_limit import (
        _get_rate_limit_per_minute,
        _is_https_redirect_enabled,
        _is_rate_limit_enabled,
    )

    if _is_rate_limit_enabled():
        logger.info("  🚦 Rate limit: ENABLED (%d req/min per IP)", _get_rate_limit_per_minute())
    else:
        logger.info("  ⚠️  Rate limit: DISABLED (DEVSQUAD_RATE_LIMIT_DISABLED=1)")
    if _is_https_redirect_enabled():
        logger.info("  🔒 HTTPS redirect: ENABLED (308 on X-Forwarded-Proto: http)")
    else:
        logger.info("  ⚠️  HTTPS redirect: DISABLED (set DEVSQUAD_HTTPS_REDIRECT_ENABLED=1 in production)")
    logger.info("=" * 60)
    logger.info("Available Endpoints:")
    logger.info("  POST /api/v1/tasks/dispatch   - Full task dispatch (TASK_EXECUTE)")
    logger.info("  POST /api/v1/tasks/quick      - Quick dispatch (TASK_EXECUTE)")
    logger.info("  GET  /api/v1/tasks/history     - Dispatch history (TASK_READ)")
    logger.info("  GET  /api/v1/roles             - List roles (TASK_READ)")
    logger.info("  GET  /api/v1/lifecycle/*       - Lifecycle mgmt (TASK_READ/TASK_UPDATE)")
    logger.info("  GET  /api/v1/metrics/*         - Metrics (AUDIT_READ)")
    logger.info("  GET  /api/v1/gates/*           - Gates (AUDIT_READ)")
    logger.info("  GET  /api/v1/health            - Health check (PUBLIC)")
    logger.info("  GET  /api/v1/ready             - Readiness probe (PUBLIC)")
    logger.info("  GET  /metrics                  - Prometheus metrics (AUDIT_READ)")
    global _app_ready
    _app_ready = True
    logger.info("Ready to accept requests!")
    logger.info("Swagger UI: http://localhost:8000/docs")
    logger.info("=" * 60)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event() -> None:
    """Execute on application shutdown — drain traffic then clean up."""
    global _app_ready
    _app_ready = False
    logger.info("=" * 60)
    logger.info("🛑 DevSquad API Server Shutting Down...")
    logger.info("Time: %s", datetime.now().isoformat())
    logger.info("Draining traffic (ready=False)...")
    logger.info("Cleaning up resources...")
    logger.info("Goodbye! 👋")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn

    print(f"""
╔══════════════════════════════════════════════════════╗
║          🚀 DevSquad API Server v{DEVSQUAD_VERSION}           ║
╠══════════════════════════════════════════════════════╣
║  Starting server...                                   ║
║                                                       ║
║  Swagger UI:  http://localhost:8000/docs               ║
║  ReDoc:       http://localhost:8000/redoc             ║
║  Health:      http://localhost:8000/api/v1/health     ║
║                                                       ║
║  Press CTRL+C to stop                                 ║
╚══════════════════════════════════════════════════════╝
    """)

    uvicorn.run(
        "scripts.api_server:app",
        host="0.0.0.0",  # nosec B104
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info",
    )
