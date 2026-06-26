"""Shared base class for MultiAgentDispatcher and its mixins.

This module declares the common attributes and method signatures used across
split dispatcher implementation so that mypy can type-check mixins without
requiring heavy casts or ``# type: ignore`` comments.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from .dispatch_models import DispatchResult

if TYPE_CHECKING:
    from .dispatch_pre_steps import PreDispatchPipeline
    from .dispatch_steps import PostDispatchPipeline


class DispatcherBase:
    """Structural base for dispatcher mixins.

    Attributes are declared as class-level annotations; concrete values are
    assigned by ``MultiAgentDispatcher.__init__`` or by
    ``ComponentFactory.create_all``.
    """

    # Components
    coordinator: Any
    scratchpad: Any
    batch_scheduler: Any
    consensus_engine: Any
    compressor: Any
    permission_guard: Any
    warmup_manager: Any
    memory_bridge: Any
    skillifier: Any
    quality_guard: Any
    anchor_checker: Any
    retrospective_engine: Any
    usage_tracker: Any
    report_formatter: Any
    role_matcher: Any
    semantic_matcher: Any
    intent_mapper: Any
    context_manager: Any
    operation_classifier: Any
    skill_registry: Any
    execution_guard: Any
    output_slicer: Any
    ci_feedback: Any
    _perf_monitor: Any
    _concern_loader: Any
    _validator: Any
    _dispatch_history: list[Any]
    _max_history: int
    _result_assembler: Any
    _audit_logger: Any

    # Configuration / state
    persist_dir: str
    memory_dir: str
    llm_backend: Any
    stream: bool
    lang: str
    micro_task_planner: Any
    content_cache: Any
    _code_graph: Any
    enable_memory: bool
    enable_skillify: bool
    enable_compression: bool
    enable_permission: bool
    enable_quality_guard: bool
    enable_execution_guard: bool
    enable_feedback_loop: bool | str
    enable_two_stage_review: bool
    enable_redesign_audit: bool
    enable_severity_router: bool
    development_mode: bool
    max_fix_iterations: int
    _injected_severity_router: Any
    judge_agent: Any
    compression_threshold: int
    permission_level: Any
    _mce_adapter: Any
    redis_url: str | None

    # Pipelines and services
    pre_dispatch: PreDispatchPipeline
    post_dispatch: PostDispatchPipeline
    metrics_service: Any
    permission_service: Any
    memory_pipeline_service: Any
    skill_service: Any
    enterprise: Any
    event_bus: Any
    hooks: Any

    # Shared methods used by mixins
    def dispatch(
        self, task_description: str, roles: list[str] | None = None, mode: str = "auto", dry_run: bool = False, use_micro_tasks: bool = False, **kwargs: Any
    ) -> DispatchResult:
        raise NotImplementedError

    def _execute_workers(
        self, plan: Any, _task_description: str
    ) -> tuple[Any, list[dict[str, Any]], list[str], dict[str, float]]:
        raise NotImplementedError

    def _handle_dispatch_error(
        self,
        error: Exception,
        task_description: str,
        tenant_ctx: Any,
        phase: str,
        start_time: float,
        lang: str,
        is_async: bool = False,
    ) -> DispatchResult:
        raise NotImplementedError

    def _log_dispatch_end_audit(self, user_id: str, success: bool, duration: float) -> None:
        raise NotImplementedError

    def _log_dispatch_error_audit(self, user_id: str, error: Exception) -> None:
        raise NotImplementedError

    def _attach_audit_entries(self, result: DispatchResult) -> None:
        raise NotImplementedError
