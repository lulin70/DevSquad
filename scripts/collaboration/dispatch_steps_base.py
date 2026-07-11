"""Structural base class for PostDispatchPipeline and its mixins.

Declares shared attributes so that split post-dispatch modules can be
type-checked by mypy without heavy casts.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .dispatcher_base import ReportFormatterProtocol

if TYPE_CHECKING:
    from .dispatch_result_assembler import ResultAssembler
    from .dispatch_services import MemoryPipelineService, PermissionService, SkillProposalService
    from .event_bus import EventBus
    from .severity_router import SeverityRouter
    from .two_stage_review_gate import TwoStageReviewGate
    from .ue_test_framework import UETestFramework


class PostDispatchBase:
    """Attribute declarations shared across PostDispatchPipeline mixins."""

    # Core components
    coordinator: Any
    report_formatter: ReportFormatterProtocol
    enterprise: Any

    # Service instances
    metrics_service: Any
    permission_service: PermissionService
    memory_pipeline: MemoryPipelineService
    skill_service: SkillProposalService

    # Feature flags
    enable_compression: bool
    enable_permission: bool
    enable_feedback_loop: bool | str
    enable_two_stage_review: bool
    enable_redesign_audit: bool
    enable_severity_router: bool
    development_mode: bool
    max_fix_iterations: int

    # Routers / frameworks
    severity_router: SeverityRouter
    two_stage_review_gate: TwoStageReviewGate
    judge_agent: Any
    _ue_framework: UETestFramework | None
    _debt_manager: Any

    # Optional components
    compressor: Any
    usage_tracker: Any
    retrospective_engine: Any
    learned_rule_store: Any
    anchor_checker: Any
    llm_backend: Any

    # Context / plumbing
    persist_dir: str
    dispatcher: Any
    event_bus: EventBus
    result_assembler: ResultAssembler | None
