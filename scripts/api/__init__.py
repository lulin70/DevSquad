# API Package

"""
DevSquad REST API Package

Provides FastAPI-based REST API for DevSquad multi-agent collaboration system.

Modules:
- models: Pydantic request/response models
- routes: API endpoint routers (lifecycle, metrics_gates, dispatch)
"""

from scripts.api.models import *

__all__ = [
    # Lifecycle models
    "LifecyclePhase",
    "PhaseStatus",
    "PhaseActionRequest",
    "PhaseActionResult",
    "CommandMapping",
    # Metrics & Gates models
    "GateCheckRequest",
    "GateResult",
    "MetricsSnapshot",
    "HealthCheck",
    # Task Dispatch models (NEW in V3.6.0)
    "TaskDispatchRequest",
    "QuickDispatchRequest",
    "DispatchResponse",
    "WorkerResultItem",
    "IntentMatchInfo",
    "FiveAxisResult",
    "AnchorResult",
    "RoleInfo",
    "RolesListResponse",
    "DispatchHistoryResponse",
    # Common models
    "UserRole",
    "APIError",
    "APISuccess",
    "PaginatedResponse",
]