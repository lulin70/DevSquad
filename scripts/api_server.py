#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import sys
import time
from datetime import datetime
from typing import Dict

import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Import routes
from scripts.api.routes.lifecycle import router as lifecycle_router
from scripts.api.routes.metrics_gates import router as metrics_router
from scripts.api.routes.dispatch import router as dispatch_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

# Create FastAPI application
app = FastAPI(
    title="DevSquad API",
    description="""
    ## DevSquad V3.6.0 REST API
    
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
    
    **Version**: 3.6.0  
    **Base URL**: `/api/v1`
    """,
    version="3.6.0",
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
    openapi_url="/openapi.json", # OpenAPI spec
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
# Configure allowed origins - use wildcard for development, restrict in production
allowed_origins = [
    "http://localhost:8501",      # DevSquad Dashboard
    "http://localhost:8000",      # API Server
    "http://localhost:3000",      # Frontend dev server
    "*",                          # Allow all origins (restrict in production)
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
async def add_process_time_header(request: Request, call_next):
    """Add processing time header to responses."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = f"{process_time:.3f}"
    
    # Log response
    logger.info(
        f"Response: {response.status_code} "
        f"(took {process_time:.3f}s)"
    )
    
    return response


# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions with custom error format."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unhandled exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred",
            "detail": str(exc) if app.debug else None,
            "status_code": 500,
            "timestamp": datetime.now().isoformat(),
            "path": request.url.path
        }
    )


# Include routers
app.include_router(lifecycle_router)
app.include_router(metrics_router)
app.include_router(dispatch_router)


# Auth dependency injection (optional, based on AuthManager)
def get_auth_manager():
    """Get AuthManager instance for dependency injection."""
    try:
        from scripts.auth import AuthManager
        return AuthManager()
    except Exception:
        return None


async def get_auth_dependency():
    """
    Optional auth dependency - can be used by endpoints that need authentication.
    Returns AuthManager if enabled, None otherwise.
    """
    return get_auth_manager()


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.
    
    Returns basic API information and available endpoints.
    
    根端点 - API信息。返回基本API信息和可用端点。
    """
    return {
        "name": "DevSquad API",
        "version": "3.6.0",
        "description": "Production REST API for DevSquad multi-agent collaboration",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json"
        },
        "endpoints": {
            "task_dispatch": "/api/v1/tasks/",
            "quick_dispatch": "/api/v1/tasks/quick",
            "dispatch_history": "/api/v1/tasks/history",
            "roles": "/api/v1/roles",
            "lifecycle": "/api/v1/lifecycle/",
            "metrics": "/api/v1/metrics/",
            "gates": "/api/v1/gates/",
            "health": "/api/v1/health"
        },
        "features": {
            "task_dispatch": "Multi-Agent task orchestration with 7 roles",
            "lifecycle_management": "11-phase lifecycle control",
            "real_time_metrics": "CPU/Memory/Response time monitoring",
            "quality_gates": "Gate status checking for CI/CD",
            "auth_integration": "Optional AuthManager integration"
        },
        "status": "operational",
        "timestamp": datetime.now().isoformat()
    }


# Startup event
@app.on_event("startup")
async def startup_event():
    """
    Execute on application startup.
    
    Initialize components and log startup message.
    """
    logger.info("=" * 60)
    logger.info("🚀 DevSquad API Server Starting...")
    logger.info("=" * 60)
    logger.info(f"Version: 3.6.0")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("Components:")
    logger.info("  ✅ FastAPI initialized")
    logger.info("  ✅ Lifecycle routes registered")
    logger.info("  ✅ Metrics routes registered")
    logger.info("  ✅ Task Dispatch routes registered (NEW)")
    logger.info("  ✅ CORS middleware enabled (wildcard)")
    logger.info("  ⏱️  Request timing enabled")
    logger.info("  🔐 Auth dependency injection ready")
    logger.info("=" * 60)
    logger.info("Available Endpoints:")
    logger.info("  POST /api/v1/tasks/dispatch   - Full task dispatch")
    logger.info("  POST /api/v1/tasks/quick      - Quick dispatch")
    logger.info("  GET  /api/v1/tasks/history     - Dispatch history")
    logger.info("  GET  /api/v1/roles             - List roles")
    logger.info("Ready to accept requests!")
    logger.info("Swagger UI: http://localhost:8000/docs")
    logger.info("=" * 60)


# Shutdown event
@app.on_event("shutdown")
async def shutdown_event():
    """
    Execute on application shutdown.
    
    Clean up resources and log shutdown message.
    """
    logger.info("=" * 60)
    logger.info("🛑 DevSquad API Server Shutting Down...")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("Cleaning up resources...")
    logger.info("Goodbye! 👋")
    logger.info("=" * 60)


if __name__ == "__main__":
    import uvicorn
    
    print("""
╔══════════════════════════════════════════════════════╗
║          🚀 DevSquad API Server v3.6.0           ║
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
        host="0.0.0.0",
        port=8000,
        reload=True,  # Enable auto-reload during development
        log_level="info"
    )
