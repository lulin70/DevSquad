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
    ## DevSquad V3.4.0-Prod REST API
    
    Production-ready API for DevSquad lifecycle management.
    
    ### Features
    
    * **Lifecycle Management**: Query and control 11-phase lifecycle
    * **Metrics & Monitoring**: Real-time performance metrics
    * **Gate Status**: Check and monitor quality gates
    * **Health Checks**: Service health monitoring
    
    ### Authentication
    
    API supports basic authentication (configure in config/deployment.yaml).
    
    ### Rate Limiting
    
    Default: 60 requests/minute per IP address.
    
    ---
    
    **Version**: 3.4.0-Prod  
    **Base URL**: `/api/v1`
    """,
    version="3.4.0-Prod",
    docs_url="/docs",           # Swagger UI
    redoc_url="/redoc",         # ReDoc
    openapi_url="/openapi.json" # OpenAPI spec
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """
    Root endpoint - API information.
    
    Returns basic API information and available endpoints.
    """
    return {
        "name": "DevSquad API",
        "version": "3.4.0-Prod",
        "description": "Production REST API for DevSquad lifecycle management",
        "documentation": {
            "swagger_ui": "/docs",
            "redoc": "/redoc",
            "openapi_spec": "/openapi.json"
        },
        "endpoints": {
            "lifecycle": "/api/v1/lifecycle/",
            "metrics": "/api/v1/metrics/",
            "gates": "/api/v1/gates/",
            "health": "/api/v1/health"
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
    logger.info(f"Version: 3.4.0-Prod")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("Components:")
    logger.info("  ✅ FastAPI initialized")
    logger.info("  ✅ Lifecycle routes registered")
    logger.info("  ✅ Metrics routes registered")
    logger.info("  ✅ CORS middleware enabled")
    logger.info("  ⏱️  Request timing enabled")
    logger.info("=" * 60)
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
║          🚀 DevSquad API Server v3.4.0-Prod           ║
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
