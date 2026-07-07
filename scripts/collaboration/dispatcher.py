#!/usr/bin/env python3
"""V3 Multi-Agent Collaboration Dispatcher — Unified Entry Point.

Pipeline: Task → Intent → Roles → Coordinator → Workers → Scratchpad
       → Consensus → Compression → Permission → Memory → Result

Implementation notes:
- The class body intentionally keeps only ``__init__`` and the core
  ``dispatch()`` orchestration method.
- Auxiliary concerns (audit logging, status reporting, async execution,
  error handling, shutdown, utility helpers, factory functions) are split
  into single-responsibility mixins/modules under
  ``scripts/collaboration/dispatcher_*.py``.
"""

import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, cast

from ._version import __version__
from .dispatch_audit import DispatchAuditLogger
from .dispatch_component_factory import ComponentConfig, ComponentFactory
from .dispatch_hooks import DispatchHooks
from .dispatch_lifecycle import DISPATCH_LIFECYCLE_MAPPING
from .dispatch_models import ROLE_TEMPLATES, DispatchResult
from .dispatch_pre_steps import PreDispatchPipeline
from .dispatch_rbac import DispatchRBAC
from .dispatch_result_assembler import ResultAssembler
from .dispatch_services import MemoryPipelineService, MetricsService, PermissionService, SkillProposalService
from .dispatch_steps import PostDispatchPipeline
from .dispatcher_async_mixin import DispatcherAsyncMixin
from .dispatcher_audit_mixin import DispatcherAuditMixin
from .dispatcher_error_mixin import DispatcherErrorMixin
from .dispatcher_factory import async_quick_collaborate, create_dispatcher, quick_collaborate
from .dispatcher_lifecycle_mixin import DispatcherLifecycleMixin
from .dispatcher_status_mixin import DispatcherStatusMixin
from .dispatcher_utils_mixin import DispatcherUtilsMixin
from .enterprise_feature import EnterpriseFeature
from .event_bus import EventBus
from .permission_guard import PermissionLevel
from .usage_tracker import track_usage

logger = logging.getLogger(__name__)


class MultiAgentDispatcher(
    DispatcherAuditMixin,
    DispatcherAsyncMixin,
    DispatcherErrorMixin,
    DispatcherLifecycleMixin,
    DispatcherStatusMixin,
    DispatcherUtilsMixin,
):
    """V3 Unified Multi-Agent Collaboration Dispatcher.

    Pipeline: Intent → Roles → Coordinator → Workers → Scratchpad →
    Consensus → Compression → Permission → Memory → Result
    """

    # Class-level type annotations for attributes dynamically assigned
    # in _init_components_from_factory() via setattr().
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
    learned_rule_store: Any
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
    _audit_logger: DispatchAuditLogger | None

    def __init__(
        self,
        persist_dir: str | None = None,
        enable_warmup: bool = True,
        enable_compression: bool = True,
        enable_permission: bool = True,
        enable_memory: bool = True,
        enable_skillify: bool = True,
        enable_quality_guard: bool = True,
        enable_anchor_check: bool = True,
        enable_retrospective: bool = True,
        enable_usage_tracker: bool = True,
        enable_feedback_loop: bool | str = "auto",
        enable_redis_cache: bool = False,
        enable_execution_guard: bool = True,
        enable_two_stage_review: bool = True,
        enable_redesign_audit: bool = True,
        enable_severity_router: bool = True,
        micro_task_planner: Any = None,
        development_mode: bool = True,
        max_fix_iterations: int = 3,
        severity_router: Any = None,
        judge_agent: Any = None,
        content_cache: Any = None,
        code_graph: Any = None,
        rbac: DispatchRBAC | None = None,
        audit_logger: DispatchAuditLogger | None = None,
        enable_audit_logger: bool = True,
        audit_db_path: str | Path | None = None,
        rbac_fail_closed: bool = True,  # HC-1: fail-closed by default (硬约束: 禁止 fail-open)
        redis_url: str | None = None,
        compression_threshold: int = 100000,
        memory_dir: str | None = None,
        permission_level: PermissionLevel = PermissionLevel.DEFAULT,
        mce_adapter: Any = None,
        llm_backend: Any = None,
        stream: bool = False,
        lang: str = "auto",
        # V4.0.0 P1-2: UI/UX 巡检与视觉回归
        qa_enabled: bool = False,
        qa_pixel_diff_threshold: float = 0.01,
        **kwargs: Any,
    ) -> None:
        """Initialize the Multi-Agent Dispatcher with feature flags and components."""
        self.enable_quality_guard = enable_quality_guard
        self.enable_anchor_check = enable_anchor_check
        self.enable_retrospective = enable_retrospective
        self.enable_usage_tracker = enable_usage_tracker
        self.enable_feedback_loop = enable_feedback_loop
        self.enable_redis_cache = enable_redis_cache
        self.enable_execution_guard = enable_execution_guard
        self.enable_two_stage_review = enable_two_stage_review
        self.enable_redesign_audit = enable_redesign_audit
        self.enable_severity_router = enable_severity_router
        self.development_mode = development_mode
        self.max_fix_iterations = max_fix_iterations
        self._injected_severity_router = severity_router
        self.micro_task_planner = micro_task_planner
        self.judge_agent = judge_agent
        self.content_cache = content_cache
        self._code_graph = code_graph
        self._rbac = rbac
        self._rbac_fail_closed = rbac_fail_closed
        self.redis_url = redis_url
        self.persist_dir = persist_dir or tempfile.mkdtemp(prefix="mas_v3_")
        self.memory_dir = memory_dir or os.path.join(self.persist_dir, "memory")
        self.enable_warmup = enable_warmup
        self.enable_compression = enable_compression
        self.enable_permission = enable_permission
        self.enable_memory = enable_memory
        self.enable_skillify = enable_skillify
        self.compression_threshold = compression_threshold
        self.permission_level = permission_level
        self.llm_backend = llm_backend
        self.stream = stream
        self.lang = lang
        self.qa_enabled = qa_enabled
        self.qa_pixel_diff_threshold = qa_pixel_diff_threshold

        os.makedirs(self.persist_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)

        if audit_logger is not None:
            self._audit_logger = audit_logger
        elif enable_audit_logger:
            db_path = Path(audit_db_path) if audit_db_path else None
            if db_path is None:
                db_path = Path(self.persist_dir) / "audit" / "dispatch_audit.db"
                db_path.parent.mkdir(parents=True, exist_ok=True)
            self._audit_logger = DispatchAuditLogger(db_path=db_path)
        else:
            self._audit_logger = None

        self._mce_adapter = mce_adapter

        # Composition-based metrics service (must be created before _init_components_from_factory)
        self.metrics_service = MetricsService()

        # Event bus for decoupled pipeline communication
        self.event_bus = EventBus()

        self._init_components_from_factory()
        self.enterprise = EnterpriseFeature(
            persist_dir=self.persist_dir,
            quality_guard=self.quality_guard,
            perf_monitor=self._perf_monitor,
            config=kwargs,
        )

        # Initialize DispatchHooks (post-dispatch hooks + post-execution processing)
        self.hooks = DispatchHooks(
            coordinator=self.coordinator,
            enterprise=self.enterprise,
            quality_guard=self.quality_guard,
            perf_monitor=self._perf_monitor,
            anchor_checker=self.anchor_checker,
            output_slicer=self.output_slicer,
            scratchpad=self.scratchpad,
            usage_tracker=self.usage_tracker,
            dispatch_history=self._dispatch_history,
            max_history=self._max_history,
            enable_quality_guard=self.enable_quality_guard,
        )

        # Register event handlers for post-dispatch hooks
        self.event_bus.on("post_dispatch.hooks", self.hooks.post_dispatch_hooks)

        # Composition-based pre-dispatch pipeline
        self.pre_dispatch = PreDispatchPipeline(
            validator=self._validator,
            ci_feedback=self.ci_feedback,
            persist_dir=self.persist_dir,
            usage_tracker=self.usage_tracker,
            intent_mapper=self.intent_mapper,
            context_manager=self.context_manager,
            role_matcher=self.role_matcher,
            semantic_matcher=self.semantic_matcher,
            llm_backend=self.llm_backend,
            concern_loader=self._concern_loader,
            warmup_manager=self.warmup_manager,
            coordinator=self.coordinator,
            anchor_checker=self.anchor_checker,
            retrospective_engine=self.retrospective_engine,
            enable_memory=self.enable_memory,
            scratchpad=self.scratchpad,
            enterprise=self.enterprise,
            resolve_language_fn=self._resolve_language,
            analyze_task_fn=self.analyze_task,
            lang=self.lang,
        )

        # Composition-based service instances for post-dispatch
        self.permission_service = PermissionService(
            permission_guard=self.permission_guard,
            operation_classifier=self.operation_classifier,
            rbac_engine=self.enterprise.rbac_engine,
            enable_rbac=self.enterprise.enable_rbac,
            metrics_service=self.metrics_service,
        )
        self.memory_pipeline_service = MemoryPipelineService(
            memory_bridge=self.memory_bridge,
            mce_adapter=self._mce_adapter,
            scratchpad=self.scratchpad,
            enable_memory=self.enable_memory,
            enterprise=self.enterprise,
        )
        self.skill_service = SkillProposalService(
            skillifier=self.skillifier,
            enable_skillify=self.enable_skillify,
            skill_registry=self.skill_registry,
        )

        # Composition-based post-dispatch pipeline
        self.post_dispatch = PostDispatchPipeline(
            coordinator=self.coordinator,
            report_formatter=self.report_formatter,
            enterprise=self.enterprise,
            metrics_service=self.metrics_service,
            permission_service=self.permission_service,
            memory_pipeline=self.memory_pipeline_service,
            skill_service=self.skill_service,
            enable_compression=self.enable_compression,
            enable_permission=self.enable_permission,
            enable_feedback_loop=self.enable_feedback_loop,
            enable_two_stage_review=self.enable_two_stage_review,
            enable_redesign_audit=self.enable_redesign_audit,
            enable_severity_router=self.enable_severity_router,
            development_mode=self.development_mode,
            max_fix_iterations=self.max_fix_iterations,
            severity_router=self._injected_severity_router,
            judge_agent=self.judge_agent,
            compressor=self.compressor,
            usage_tracker=self.usage_tracker,
            retrospective_engine=self.retrospective_engine,
            learned_rule_store=self.learned_rule_store,
            anchor_checker=self.anchor_checker,
            llm_backend=self.llm_backend,
            persist_dir=self.persist_dir,
            dispatcher=self,
            event_bus=self.event_bus,
            result_assembler=self._result_assembler,
        )

        # Attach optional cross-cutting concerns to the coordinator
        if self.content_cache is not None:
            self.coordinator.content_cache = self.content_cache
        if self._code_graph is not None:
            self.coordinator.code_graph = self._code_graph

    def _init_components_from_factory(self) -> None:
        """Initialize all components via ComponentFactory."""
        config = ComponentConfig(
            persist_dir=self.persist_dir,
            memory_dir=self.memory_dir,
            enable_warmup=self.enable_warmup,
            enable_compression=self.enable_compression,
            enable_permission=self.enable_permission,
            enable_memory=self.enable_memory,
            enable_skillify=self.enable_skillify,
            enable_quality_guard=self.enable_quality_guard,
            enable_anchor_check=self.enable_anchor_check,
            enable_retrospective=self.enable_retrospective,
            enable_usage_tracker=self.enable_usage_tracker,
            enable_feedback_loop=self.enable_feedback_loop,
            enable_redis_cache=self.enable_redis_cache,
            enable_execution_guard=self.enable_execution_guard,
            redis_url=self.redis_url,
            compression_threshold=self.compression_threshold,
            permission_level=self.permission_level,
            mce_adapter=self._mce_adapter,
            llm_backend=self.llm_backend,
            stream=self.stream,
            lang=self.lang,
            qa_enabled=self.qa_enabled,
            qa_pixel_diff_threshold=self.qa_pixel_diff_threshold,
        )
        factory = ComponentFactory()
        components = factory.create_all(config)

        # Assign all components as instance attributes
        for name, value in components.items():
            setattr(self, name, value)

        # Initialize ResultAssembler
        self._result_assembler = ResultAssembler(
            concern_loader=self._concern_loader,
            report_formatter=self.report_formatter,
        )

        self.metrics_service.safe_record(lambda m: m.set_build_info(version=__version__))

    def dispatch(
        self,
        task_description: str,
        roles: list[str] | None = None,
        mode: str = "auto",
        dry_run: bool = False,
        use_micro_tasks: bool = False,
        **kwargs: Any,
    ) -> DispatchResult:
        """Core dispatch method - complete multi-Agent collaboration in one call.

        Args:
            task_description: User's task in natural language
            roles: Optional role IDs (None=auto match)
            mode: "auto"/"parallel"/"sequential"/"consensus"
            dry_run: Simulate without running Workers
            use_micro_tasks: When True and a MicroTaskPlanner is configured,
                decompose the task into 2-5 minute micro-tasks before role
                assignment. The resulting plan is stored in
                ``DispatchResult.micro_task_plan``.
            **kwargs: Additional options (tenant_id, user_id, etc.)
        """
        track_usage("dispatcher.dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()
        phase = "dispatch"

        # V3.9-02: Extract user_id for RBAC and audit logging.
        user_id = str(kwargs.get("user_id", "anonymous"))

        # V3.9-02: RBAC permission check (before any work begins).
        permission_result_dict: dict[str, Any] | None = None
        if self._rbac is not None:
            try:
                check_roles = list(roles) if roles else []
                perm = self._rbac.check_dispatch_permission(
                    user_id=user_id,
                    roles=check_roles,
                    mode=mode,
                )
                permission_result_dict = {
                    "allowed": perm.allowed,
                    "reason": perm.reason,
                    "user_id": perm.user_id,
                    "requested_roles": perm.requested_roles,
                    "requested_mode": perm.requested_mode,
                }
                if not perm.allowed:
                    if self._audit_logger is not None:
                        try:
                            self._audit_logger.log_permission_denied(
                                user_id=user_id,
                                reason=perm.reason,
                            )
                        except (ValueError, RuntimeError, OSError) as audit_err:
                            logger.warning("Audit log_permission_denied failed: %s", audit_err)
                    self.metrics_service.safe_record(lambda m: (
                        m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
                    ))
                    denied_result = DispatchResult(
                        success=False,
                        task_description=task_description,
                        errors=[f"Permission denied: {perm.reason}"],
                        permission_result=permission_result_dict,
                    )
                    self._attach_audit_entries(denied_result)
                    return denied_result
            except (ValueError, AttributeError, TypeError, RuntimeError) as rbac_err:
                logger.warning("RBAC check failed: %s", rbac_err)
                if self._rbac_fail_closed:
                    if self._audit_logger is not None:
                        try:
                            self._audit_logger.log_permission_denied(
                                user_id=user_id,
                                reason=f"RBAC infrastructure error: {rbac_err}",
                            )
                        except (ValueError, RuntimeError, OSError) as audit_err:
                            logger.warning("Audit log_permission_denied failed: %s", audit_err)
                    denied_result = DispatchResult(
                        success=False,
                        task_description=task_description,
                        errors=[f"RBAC check failed (fail-closed): {rbac_err}"],
                        permission_result={"allowed": False, "reason": str(rbac_err), "user_id": user_id},
                    )
                    self._attach_audit_entries(denied_result)
                    return denied_result
        else:
            # HC-1: When no RBAC is configured, consult rbac_fail_closed flag.
            # In production (development_mode=False), deny all operations to
            # satisfy hard constraint "禁止 fail-open 直接执行".
            # In dev/test mode (development_mode=True), allow for backward compat.
            if self._rbac_fail_closed and not self.development_mode:
                logger.warning(
                    "Dispatch denied: no RBAC configured (fail-closed mode, "
                    "user=%s, production mode)"
                )
                permission_result_dict = {
                    "allowed": False,
                    "reason": "No RBAC configured (fail-closed mode denies all)",
                    "user_id": user_id,
                    "requested_roles": list(roles) if roles else [],
                    "requested_mode": mode,
                }
                if self._audit_logger is not None:
                    try:
                        self._audit_logger.log_permission_denied(
                            user_id=user_id,
                            reason="No RBAC configured (fail-closed mode denies all)",
                        )
                    except (ValueError, RuntimeError, OSError) as audit_err:
                        logger.warning("Audit log_permission_denied failed: %s", audit_err)
                denied_result = DispatchResult(
                    success=False,
                    task_description=task_description,
                    errors=["Permission denied: No RBAC configured (fail-closed mode)"],
                    permission_result=permission_result_dict,
                )
                self._attach_audit_entries(denied_result)
                return denied_result

        self.metrics_service.safe_record(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("dispatch")

        if self._audit_logger is not None:
            try:
                audit_roles = list(roles) if roles else []
                self._audit_logger.log_dispatch_start(
                    user_id=user_id,
                    task=task_description,
                    roles=audit_roles,
                )
            except (ValueError, RuntimeError, OSError) as audit_err:
                logger.warning("Audit log_dispatch_start failed: %s", audit_err)

        # Pre-dispatch steps (shared with async_dispatch)
        pre_result = self.pre_dispatch.execute(task_description, roles, mode, dry_run, start_time, phase, **kwargs)
        if pre_result.early_return:
            self.metrics_service.safe_record(lambda m: m.tasks_in_progress_gauge.labels(phase=phase).dec())
            self._log_dispatch_end_audit(user_id, False, time.time() - start_time)
            early_result = cast(DispatchResult, pre_result.early_return)
            if permission_result_dict is not None:
                early_result.permission_result = permission_result_dict
            self._attach_audit_entries(early_result)
            return early_result

        tenant_ctx = pre_result.tenant_ctx

        # V3.8 #7: Micro-task decomposition (after task analysis, before role assignment)
        micro_task_plan = self._maybe_decompose_task(
            task_description, use_micro_tasks, kwargs
        )

        try:
            # Step 8: Execute workers (sync path)
            matched_roles = pre_result.matched_roles
            self.metrics_service.safe_record(lambda m: m.workers_active_gauge.labels(worker_type="agent").inc(len(matched_roles)))
            exec_result, worker_results, exec_errors, exec_timing = self._execute_workers(pre_result.plan, task_description)
            self.metrics_service.safe_record(lambda m: m.workers_active_gauge.labels(worker_type="agent").dec(len(matched_roles)))

            # Post-dispatch steps (shared with async_dispatch)
            result = cast(
                DispatchResult,
                self.post_dispatch.execute(
                    pre_result=pre_result,
                    exec_result=exec_result,
                    worker_results=worker_results,
                    exec_errors=exec_errors,
                    exec_timing=exec_timing,
                    start_time=start_time,
                    phase=phase,
                    **kwargs,
                ),
            )

            if micro_task_plan is not None:
                result.micro_task_plan = micro_task_plan.to_dict()
                result.details["micro_task_plan"] = micro_task_plan.to_dict()

            if permission_result_dict is not None:
                result.permission_result = permission_result_dict
            self._log_dispatch_end_audit(user_id, result.success, time.time() - start_time)
            self._attach_audit_entries(result)

            return result

        except (ValueError, TypeError, AttributeError) as dispatch_err:
            self._log_dispatch_error_audit(user_id, dispatch_err)
            return self._handle_dispatch_error(dispatch_err, task_description, tenant_ctx, phase, start_time, pre_result.lang)
        except (ImportError, ModuleNotFoundError) as import_err:
            self._log_dispatch_error_audit(user_id, import_err)
            return self._handle_dispatch_error(import_err, task_description, tenant_ctx, phase, start_time, pre_result.lang)
        except (RuntimeError, OSError, ConnectionError, TimeoutError) as e:
            self._log_dispatch_error_audit(user_id, e)
            return self._handle_dispatch_error(e, task_description, tenant_ctx, phase, start_time, pre_result.lang)

    # V4.0.0 P1-1: Loop Engineering 五步闭环
    def dispatch_with_loop(
        self,
        task_description: str,
        loop_type: str = "coding",
        max_iterations: int = 50,
    ) -> Any:
        """使用 Loop Engineering 五步闭环执行任务。

        Args:
            task_description: 任务目标
            loop_type: "design" | "coding" | "testing"
            max_iterations: 最大迭代次数
        """
        from .loop_engineering import (
            HandoffAdapter,
            LoopEngineeringConfig,
            LoopKernel,
            LoopType,
        )

        loop_config = LoopEngineeringConfig(
            loop_type=LoopType(loop_type),
            max_iterations=max_iterations,
        )

        handoff = HandoffAdapter(dispatcher=self)
        kernel = LoopKernel(
            config=loop_config,
            handoff_adapter=handoff,
        )

        return kernel.run(task_description)

    # V4.0.0 P1-2: UI/UX 巡检与视觉回归
    def qa_audit_url(self, url: str, **kwargs: Any) -> Any:
        """对指定 URL 执行 UI/UX 巡检。

        Args:
            url: 巡检目标 URL。
            **kwargs: 传递给 Playwright launch 的额外参数。

        Returns:
            UIUXAuditReport。若 uiux_analyzer 未启用或 Playwright 不可用，抛出 RuntimeError。

        Raises:
            RuntimeError: qa_enabled=False 或 Playwright 未安装。
        """
        if not hasattr(self, "uiux_analyzer") or self.uiux_analyzer is None:
            raise RuntimeError(
                "UIUXAnalyzer not enabled. Initialize dispatcher with qa_enabled=True."
            )
        try:
            from playwright.sync_api import sync_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for qa_audit_url. Install with: pip install playwright && playwright install"
            ) from exc

        with sync_playwright() as p:
            browser = p.chromium.launch(**kwargs)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="networkidle")
                return self.uiux_analyzer.audit(page, url=url)
            finally:
                browser.close()

    def qa_visual_regression(self, baseline: str, current: str) -> Any:
        """对两张图片执行视觉回归检查。

        Args:
            baseline: 基线图片路径。
            current: 当前图片路径。

        Returns:
            DiffResult。若 visual_regression_checker 未启用，抛出 RuntimeError。
        """
        if not hasattr(self, "visual_regression_checker") or self.visual_regression_checker is None:
            raise RuntimeError(
                "VisualRegressionChecker not enabled. Initialize dispatcher with qa_enabled=True."
            )
        return self.visual_regression_checker.compare(baseline, current)


__all__ = [
    "DISPATCH_LIFECYCLE_MAPPING",
    "ROLE_TEMPLATES",
    "MultiAgentDispatcher",
    "create_dispatcher",
    "quick_collaborate",
    "async_quick_collaborate",
]
