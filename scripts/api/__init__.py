# API Package

"""
DevSquad REST API Package

Provides FastAPI-based REST API for DevSquad multi-agent collaboration system.

Modules:
- models: Pydantic request/response models
- routes: API endpoint routers (lifecycle, metrics_gates, dispatch)
"""

from scripts.api.models import (
    AnchorResult,
    APIError,
    APISuccess,
    CommandMapping,
    DispatchHistoryResponse,
    DispatchResponse,
    FiveAxisResult,
    GateCheckRequest,
    GateResult,
    HealthCheck,
    IntentMatchInfo,
    LifecyclePhase,
    MetricsSnapshot,
    PaginatedResponse,
    PhaseActionRequest,
    PhaseActionResult,
    PhaseStatus,
    QuickDispatchRequest,
    RoleInfo,
    RolesListResponse,
    TaskDispatchRequest,
    UserRole,
    WorkerResultItem,
)

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
    # Task Dispatch models (NEW in V3.7.0)
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
