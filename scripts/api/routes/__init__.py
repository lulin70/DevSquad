# API Routes Package

"""
DevSquad API Routes Package

Provides REST API endpoints for:
- Task Dispatch: Multi-agent task orchestration
- Lifecycle Management: 11-phase lifecycle control
- Metrics & Gates: Performance monitoring and quality gates
"""

from scripts.api.routes.dispatch import router as dispatch_router
from scripts.api.routes.lifecycle import router as lifecycle_router
from scripts.api.routes.metrics_gates import router as metrics_router

__all__ = [
    "lifecycle_router",
    "metrics_router",
    "dispatch_router",
]
