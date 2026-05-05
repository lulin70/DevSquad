#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad API Data Models

Pydantic models for REST API request/response validation.

Models:
  - LifecyclePhase: Phase information
  - GateResult: Gate check result
  - MetricsSnapshot: Performance metrics
  - APIResponse: Standard API response wrapper
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, ConfigDict


class PhaseStatus(str, Enum):
    """Lifecycle phase status enumeration."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class UserRole(str, Enum):
    """User role enumeration."""
    ADMIN = "admin"
    OPERATOR = "operator"
    VIEWER = "viewer"


class LifecyclePhase(BaseModel):
    """Lifecycle phase information model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phase_id": "P1",
                "name": "Requirements Analysis",
                "description": "Gather and analyze project requirements",
                "role_id": "product-manager",
                "order": 1,
                "status": "completed",
                "dependencies": [],
                "artifacts_in": None,
                "artifacts_out": "Requirements Document"
            }
        }
    )
    
    phase_id: str = Field(..., description="Unique phase identifier (e.g., P1, P2)")
    name: str = Field(..., description="Human-readable phase name")
    description: str = Field(..., description="Detailed phase description")
    role_id: str = Field(..., description="Role responsible for this phase")
    order: int = Field(..., description="Execution order")
    status: PhaseStatus = Field(default=PhaseStatus.PENDING, description="Current phase status")
    dependencies: List[str] = Field(default_factory=list, description="List of dependent phase IDs")
    artifacts_in: Optional[str] = Field(None, description="Input artifacts for this phase")
    artifacts_out: Optional[str] = Field(None, description="Output artifacts from this phase")


class GateCheckRequest(BaseModel):
    """Gate check request model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "command": "build",
                "strict_mode": False
            }
        }
    )
    
    command: str = Field(..., description="CLI command to check gate for (e.g., 'build', 'test')")
    strict_mode: bool = Field(default=False, description="Enable strict gate checking")


class GateResult(BaseModel):
    """Gate check result model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "passed": True,
                "verdict": "APPROVE",
                "red_flags_count": 0,
                "missing_evidence_count": 0,
                "gap_report": None,
                "checked_at": "2026-05-03T12:00:00"
            }
        }
    )
    
    passed: bool = Field(..., description="Whether the gate check passed")
    verdict: str = Field(..., description="Gate verdict (APPROVE/CONDITIONAL/REJECT)")
    red_flags_count: int = Field(default=0, description="Number of red flags found")
    missing_evidence_count: int = Field(default=0, description="Number of missing evidence items")
    gap_report: Optional[str] = Field(None, description="Detailed gap analysis report")
    checked_at: datetime = Field(default_factory=datetime.now, description="When the check was performed")


class CommandMapping(BaseModel):
    """CLI command to phases mapping model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "command": "build",
                "phases": ["P8"],
                "mode": "full",
                "gate": "quality_gate"
            }
        }
    )
    
    command: str = Field(..., description="CLI command name")
    phases: List[str] = Field(..., description="List of mapped phase IDs")
    mode: str = Field(..., description="Lifecycle mode (shortcut/full/custom)")
    gate: Optional[str] = Field(None, description="Required gate for this command")


class MetricsSnapshot(BaseModel):
    """Performance metrics snapshot model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2026-05-03T12:00:00",
                "total_phases": 11,
                "completed_phases": 7,
                "running_phases": 1,
                "failed_phases": 0,
                "completion_rate": 63.6,
                "avg_response_time_ms": 150.5,
                "p95_latency_ms": 450.2,
                "success_rate": 99.5,
                "cpu_usage_percent": 45.2,
                "memory_usage_percent": 62.8
            }
        }
    )
    
    timestamp: datetime = Field(default_factory=datetime.now, description="When metrics were captured")
    total_phases: int = Field(..., description="Total number of lifecycle phases")
    completed_phases: int = Field(default=0, description="Number of completed phases")
    running_phases: int = Field(default=0, description="Number of currently running phases")
    failed_phases: int = Field(default=0, description="Number of failed phases")
    completion_rate: float = Field(default=0.0, description="Completion percentage (0-100)")
    
    # Response time metrics
    avg_response_time_ms: float = Field(default=0.0, description="Average API response time in ms")
    p95_latency_ms: float = Field(default=0.0, description="95th percentile latency in ms")
    success_rate: float = Field(default=100.0, description="Request success rate percentage")
    
    # Resource utilization
    cpu_usage_percent: float = Field(default=0.0, description="CPU usage percentage")
    memory_usage_percent: float = Field(default=0.0, description="Memory usage percentage")


class PhaseActionRequest(BaseModel):
    """Phase execution action request model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "phase_id": "P8",
                "action": "advance",
                "force": False,
                "reason": None
            }
        }
    )
    
    phase_id: str = Field(..., description="Target phase ID")
    action: str = Field(..., description="Action to perform (advance/complete/reset/skip)")
    force: bool = Field(default=False, description="Force action even if dependencies not met")
    reason: Optional[str] = Field(None, description="Reason for forced action")


class PhaseActionResult(BaseModel):
    """Phase action result model."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "phase_id": "P8",
                "action": "advance",
                "message": "Successfully advanced to phase P8",
                "previous_status": "pending",
                "new_status": "running",
                "performed_at": "2026-05-03T12:00:00"
            }
        }
    )
    
    success: bool = Field(..., description="Whether the action was successful")
    phase_id: str = Field(..., description="Target phase ID")
    action: str = Field(..., description="Action that was performed")
    message: str = Field(..., description="Human-readable result message")
    previous_status: Optional[PhaseStatus] = Field(None, description="Status before action")
    new_status: Optional[PhaseStatus] = Field(None, description="Status after action")
    performed_at: datetime = Field(default_factory=datetime.now, description="When action was performed")


class APIError(BaseModel):
    """Standard API error response model."""
    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.now, description="When error occurred")
    path: Optional[str] = Field(None, description="Request path that caused error")


class APISuccess(BaseModel):
    """Standard API success response model."""
    success: bool = Field(default=True, description="Always true for success responses")
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Response payload")
    timestamp: datetime = Field(default_factory=datetime.now, description="When response was generated")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper model."""
    items: List[Any] = Field(..., description="List of items in current page")
    total: int = Field(..., description="Total number of items across all pages")
    page: int = Field(1, description="Current page number (1-indexed)")
    page_size: int = Field(20, description="Number of items per page")
    total_pages: int = Field(..., description="Total number of pages")
    has_next: bool = Field(False, description="Whether there is a next page")
    has_prev: bool = Field(False, description="Whether there is a previous page")


class HealthCheck(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status (healthy/degraded/unhealthy)")
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="How long the service has been running")
    components: Dict[str, str] = Field(default_factory=dict, description="Component health statuses")
    timestamp: datetime = Field(default_factory=datetime.now, description="When health was checked")
