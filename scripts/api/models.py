#!/usr/bin/env python3
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
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


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
                "artifacts_out": "Requirements Document",
            }
        }
    )

    phase_id: str = Field(..., description="Unique phase identifier (e.g., P1, P2)")
    name: str = Field(..., description="Human-readable phase name")
    description: str = Field(..., description="Detailed phase description")
    role_id: str = Field(..., description="Role responsible for this phase")
    order: int = Field(..., description="Execution order")
    status: PhaseStatus = Field(default=PhaseStatus.PENDING, description="Current phase status")
    dependencies: list[str] = Field(default_factory=list, description="List of dependent phase IDs")
    artifacts_in: str | None = Field(None, description="Input artifacts for this phase")
    artifacts_out: str | None = Field(None, description="Output artifacts from this phase")


class GateCheckRequest(BaseModel):
    """Gate check request model."""

    model_config = ConfigDict(json_schema_extra={"example": {"command": "build", "strict_mode": False}})

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
                "checked_at": "2026-05-03T12:00:00",
            }
        }
    )

    passed: bool = Field(..., description="Whether the gate check passed")
    verdict: str = Field(..., description="Gate verdict (APPROVE/CONDITIONAL/REJECT)")
    red_flags_count: int = Field(default=0, description="Number of red flags found")
    missing_evidence_count: int = Field(default=0, description="Number of missing evidence items")
    gap_report: str | None = Field(None, description="Detailed gap analysis report")
    checked_at: datetime = Field(default_factory=datetime.now, description="When the check was performed")


class CommandMapping(BaseModel):
    """CLI command to phases mapping model."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"command": "build", "phases": ["P8"], "mode": "full", "gate": "quality_gate"}}
    )

    command: str = Field(..., description="CLI command name")
    phases: list[str] = Field(..., description="List of mapped phase IDs")
    mode: str = Field(..., description="Lifecycle mode (shortcut/full/custom)")
    gate: str | None = Field(None, description="Required gate for this command")


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
                "memory_usage_percent": 62.8,
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
        json_schema_extra={"example": {"phase_id": "P8", "action": "advance", "force": False, "reason": None}}
    )

    phase_id: str = Field(..., description="Target phase ID")
    action: str = Field(..., description="Action to perform (advance/complete/reset/skip)")
    force: bool = Field(default=False, description="Force action even if dependencies not met")
    reason: str | None = Field(None, description="Reason for forced action")


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
                "performed_at": "2026-05-03T12:00:00",
            }
        }
    )

    success: bool = Field(..., description="Whether the action was successful")
    phase_id: str = Field(..., description="Target phase ID")
    action: str = Field(..., description="Action that was performed")
    message: str = Field(..., description="Human-readable result message")
    previous_status: PhaseStatus | None = Field(None, description="Status before action")
    new_status: PhaseStatus | None = Field(None, description="Status after action")
    performed_at: datetime = Field(default_factory=datetime.now, description="When action was performed")


class APIError(BaseModel):
    """Standard API error response model."""

    error: str = Field(..., description="Error type identifier")
    message: str = Field(..., description="Human-readable error message")
    detail: str | None = Field(None, description="Detailed error information")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.now, description="When error occurred")
    path: str | None = Field(None, description="Request path that caused error")


class APISuccess(BaseModel):
    """Standard API success response model."""

    success: bool = Field(default=True, description="Always true for success responses")
    message: str = Field(..., description="Success message")
    data: Any | None = Field(None, description="Response payload")
    timestamp: datetime = Field(default_factory=datetime.now, description="When response was generated")


class PaginatedResponse(BaseModel):
    """Paginated response wrapper model."""

    items: list[Any] = Field(..., description="List of items in current page")
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
    components: dict[str, str] = Field(default_factory=dict, description="Component health statuses")
    timestamp: datetime = Field(default_factory=datetime.now, description="When health was checked")


class TaskDispatchRequest(BaseModel):
    """Task dispatch request model / 任务调度请求模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Design a user authentication system with JWT tokens",
                "roles": ["architect", "security", "tester"],
                "mode": "auto",
                "backend": "mock",
                "lang": "zh",
            }
        }
    )

    task: str = Field(..., description="任务描述 / Task description", min_length=1, max_length=10000)
    roles: list[str] | None = Field(
        default=None, description="指定角色列表 / Specific role list (e.g., ['architect', 'tester'])"
    )
    mode: str = Field(default="auto", description="执行模式 / Execution mode (auto/parallel/sequential/consensus)")
    backend: str | None = Field(default=None, description="LLM后端 / LLM backend (openai/anthropic/mock)")
    lang: str = Field(default="auto", description="输出语言 / Output language (zh/en/ja/auto)")
    dry_run: bool = Field(default=False, description="仅模拟执行 / Dry run only")


class QuickDispatchRequest(BaseModel):
    """Quick dispatch request model / 快速调度请求模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Implement REST API for user management",
                "output_format": "structured",
                "include_action_items": True,
            }
        }
    )

    task: str = Field(..., description="任务描述 / Task description", min_length=1, max_length=10000)
    output_format: str = Field(
        default="structured", description="输出格式 / Output format (structured/compact/detailed)"
    )
    include_action_items: bool = Field(default=True, description="包含行动项 / Include action items")
    include_timing: bool = Field(default=False, description="包含耗时分析 / Include timing analysis")


class WorkerResultItem(BaseModel):
    """Worker result item model / Worker结果项模型"""

    worker_id: str | None = Field(None, description="Worker ID")
    role_id: str = Field(..., description="角色ID / Role ID")
    role_name: str = Field(..., description="角色名称 / Role name")
    task_id: str | None = Field(None, description="Task ID")
    success: bool = Field(..., description="是否成功 / Whether successful")
    output: str | None = Field(None, description="输出内容 / Output content")
    error: str | None = Field(None, description="错误信息 / Error message")


class IntentMatchInfo(BaseModel):
    """Intent match information model / 意图匹配信息模型"""

    intent_type: str | None = Field(None, description="意图类型 / Intent type")
    workflow_chain: list[str] | None = Field(None, description="工作流链 / Workflow chain")
    confidence: float | None = Field(None, description="置信度 / Confidence score")


class FiveAxisResult(BaseModel):
    """Five-axis consensus result model / 五轴共识结果模型"""

    verdict: str | None = Field(None, description="裁决结果 / Verdict")
    overall_consensus: float | None = Field(None, description="总体共识度 / Overall consensus")
    axis_consensus: dict[str, Any] | None = Field(None, description="各轴共识 / Axis consensus")
    action_items: list[str] | None = Field(None, description="行动项 / Action items")


class AnchorResult(BaseModel):
    """Anchor check result model / 锚点检查结果模型"""

    aligned: bool | None = Field(None, description="是否对齐 / Whether aligned")
    coverage: float | None = Field(None, description="覆盖率 / Coverage")
    drift_score: float | None = Field(None, description="偏离分数 / Drift score")
    severity: str | None = Field(None, description="严重程度 / Severity")
    recommendation: str | None = Field(None, description="建议 / Recommendation")


class DispatchResponse(BaseModel):
    """Task dispatch response model / 任务调度响应模型"""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "task_description": "Design a user authentication system",
                "matched_roles": ["architect", "security"],
                "summary": "Task completed successfully",
                "duration_seconds": 15.5,
                "worker_results": [
                    {
                        "role_id": "architect",
                        "role_name": "Architect",
                        "success": True,
                        "output": "Architecture design...",
                    }
                ],
                "intent_match": {"intent_type": "design", "confidence": 0.85},
                "five_axis_result": {"verdict": "APPROVE", "overall_consensus": 0.82},
            }
        }
    )

    success: bool = Field(..., description="是否成功 / Whether successful")
    task_description: str = Field(..., description="任务描述 / Task description")
    matched_roles: list[str] = Field(default_factory=list, description="匹配的角色 / Matched roles")
    summary: str = Field(default="", description="执行摘要 / Execution summary")
    duration_seconds: float = Field(default=0.0, description="耗时(秒) / Duration in seconds")
    worker_results: list[WorkerResultItem] = Field(default_factory=list, description="Worker结果 / Worker results")
    errors: list[str] = Field(default_factory=list, description="错误列表 / Error list")
    intent_match: IntentMatchInfo | None = Field(None, description="意图匹配 / Intent match")
    five_axis_result: FiveAxisResult | None = Field(None, description="五轴共识 / Five-axis consensus")
    anchor_result: AnchorResult | None = Field(None, description="锚点检查 / Anchor check")
    scratchpad_summary: str | None = Field(None, description="Scratchpad摘要 / Scratchpad summary")
    consensus_records: list[dict[str, Any]] | None = Field(None, description="共识记录 / Consensus records")
    compression_info: dict[str, Any] | None = Field(None, description="压缩信息 / Compression info")
    memory_stats: dict[str, Any] | None = Field(None, description="记忆统计 / Memory stats")
    permission_checks: list[dict[str, Any]] | None = Field(None, description="权限检查 / Permission checks")
    skill_proposals: list[dict[str, Any]] | None = Field(None, description="Skill提案 / Skill proposals")
    quality_report: str | None = Field(None, description="质量报告 / Quality report")
    retrospective_report: dict[str, Any] | None = Field(None, description="回顾报告 / Retrospective report")
    details: dict[str, Any] | None = Field(None, description="详细信息 / Details")
    timestamp: datetime = Field(default_factory=datetime.now, description="响应时间 / Response timestamp")


class RoleInfo(BaseModel):
    """Role information model / 角色信息模型"""

    role_id: str = Field(..., description="角色ID / Role ID")
    name: str = Field(..., description="角色名称 / Role name")
    description: str | None = Field(None, description="角色描述 / Role description")
    keywords: list[str] | None = Field(None, description="关键词 / Keywords")
    status: str | None = Field(None, description="状态 / Status")


class RolesListResponse(BaseModel):
    """Roles list response model / 角色列表响应模型"""

    roles: list[RoleInfo] = Field(..., description="角色列表 / Role list")
    total: int = Field(..., description="总数 / Total count")
    core_roles: list[str] = Field(default_factory=list, description="核心角色 / Core roles")
    planned_roles: list[str] = Field(default_factory=list, description="规划中角色 / Planned roles")


class DispatchHistoryResponse(BaseModel):
    """Dispatch history response model / 调度历史响应模型"""

    history: list[dict[str, Any]] = Field(..., description="调度历史 / Dispatch history")
    total: int = Field(..., description="总数 / Total count")
    limit: int = Field(..., description="查询限制 / Query limit")
