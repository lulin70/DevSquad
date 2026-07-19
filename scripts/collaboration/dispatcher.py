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
    # V4.0.0 P3-1: Autonomous 自主迭代
    autonomous_controller: Any
    # V4.0.0 P3-2: 插件热加载
    plugin_hot_loader: Any

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
        # V4.0.0 P3-1: Autonomous 自主迭代模式
        autonomous_enabled: bool = False,
        autonomous_max_iterations: int = 20,
        # V4.0.0 P3-2: 插件热加载
        plugins_enabled: bool = False,
        plugins_dropin_dir: str | Path | None = None,
        plugins_no_hot_reload: bool = False,
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
        self.autonomous_enabled = autonomous_enabled
        self.autonomous_max_iterations = autonomous_max_iterations
        self.plugins_enabled = plugins_enabled
        self.plugins_dropin_dir = plugins_dropin_dir
        self.plugins_no_hot_reload = plugins_no_hot_reload

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

        # V4.0.0 P3-1: 预初始化为 None，确保属性始终存在（避免 disabled 时 AttributeError）
        self.autonomous_controller = None
        # V4.0.0 P3-2: 同样预初始化 plugin_hot_loader
        self.plugin_hot_loader = None

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
            autonomous_enabled=self.autonomous_enabled,
            autonomous_max_iterations=self.autonomous_max_iterations,
            plugins_enabled=self.plugins_enabled,
            plugins_dropin_dir=self.plugins_dropin_dir,
            plugins_no_hot_reload=self.plugins_no_hot_reload,
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
        permission_result_dict, denied_result = self._check_rbac_permission(
            user_id, roles, mode, task_description
        )
        if denied_result is not None:
            return denied_result

        self.metrics_service.safe_record(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("dispatch")

        self._log_audit_dispatch_start(user_id, task_description, roles)

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

    def _check_rbac_permission(
        self,
        user_id: str,
        roles: list[str] | None,
        mode: str,
        task_description: str,
    ) -> tuple[dict[str, Any] | None, DispatchResult | None]:
        """V3.9-02: Run RBAC permission check before dispatch work begins.

        Returns ``(permission_result_dict, denied_result)``. When
        ``denied_result`` is not None the caller must return it immediately.
        When ``denied_result`` is None, ``permission_result_dict`` may carry
        the allowed-permission metadata to attach to the final result.
        """
        if self._rbac is not None:
            return self._check_rbac_with_provider(user_id, roles, mode, task_description)
        # HC-1: When no RBAC is configured, consult rbac_fail_closed flag.
        # In production (development_mode=False), deny all operations to
        # satisfy hard constraint "禁止 fail-open 直接执行".
        # In dev/test mode (development_mode=True), allow for backward compat.
        if self._rbac_fail_closed and not self.development_mode:
            return self._deny_no_rbac_configured(user_id, roles, mode, task_description)
        return None, None

    def _check_rbac_with_provider(
        self,
        user_id: str,
        roles: list[str] | None,
        mode: str,
        task_description: str,
    ) -> tuple[dict[str, Any] | None, DispatchResult | None]:
        """RBAC check path when an RBAC provider is configured."""
        if self._rbac is None:
            return None, None
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
                self._log_audit_permission_denied(user_id, perm.reason)
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
                return permission_result_dict, denied_result
            return permission_result_dict, None
        except (ValueError, AttributeError, TypeError, RuntimeError) as rbac_err:
            logger.warning("RBAC check failed: %s", rbac_err)
            if self._rbac_fail_closed:
                return self._deny_rbac_infra_error(user_id, task_description, rbac_err)
            return None, None

    def _deny_rbac_infra_error(
        self,
        user_id: str,
        task_description: str,
        rbac_err: Exception,
    ) -> tuple[dict[str, Any], DispatchResult]:
        """Build the fail-closed denial result when RBAC itself errors."""
        self._log_audit_permission_denied(
            user_id, f"RBAC infrastructure error: {rbac_err}"
        )
        permission_result_dict = {
            "allowed": False,
            "reason": str(rbac_err),
            "user_id": user_id,
        }
        denied_result = DispatchResult(
            success=False,
            task_description=task_description,
            errors=[f"RBAC check failed (fail-closed): {rbac_err}"],
            permission_result=permission_result_dict,
        )
        self._attach_audit_entries(denied_result)
        return permission_result_dict, denied_result

    def _deny_no_rbac_configured(
        self,
        user_id: str,
        roles: list[str] | None,
        mode: str,
        task_description: str,
    ) -> tuple[dict[str, Any], DispatchResult]:
        """Build the denial result when no RBAC is configured in production."""
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
        self._log_audit_permission_denied(
            user_id, "No RBAC configured (fail-closed mode denies all)"
        )
        denied_result = DispatchResult(
            success=False,
            task_description=task_description,
            errors=["Permission denied: No RBAC configured (fail-closed mode)"],
            permission_result=permission_result_dict,
        )
        self._attach_audit_entries(denied_result)
        return permission_result_dict, denied_result

    def _log_audit_permission_denied(self, user_id: str, reason: str) -> None:
        """Best-effort audit log for permission-denied events."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_permission_denied(
                user_id=user_id,
                reason=reason,
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_permission_denied failed: %s", audit_err)

    def _log_audit_dispatch_start(
        self,
        user_id: str,
        task_description: str,
        roles: list[str] | None,
    ) -> None:
        """Best-effort audit log for dispatch-start events."""
        if self._audit_logger is None:
            return
        try:
            audit_roles = list(roles) if roles else []
            self._audit_logger.log_dispatch_start(
                user_id=user_id,
                task=task_description,
                roles=audit_roles,
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_dispatch_start failed: %s", audit_err)

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

    # V4.0.0 P3-1: Autonomous 自主迭代模式
    def dispatch_autonomous(
        self,
        objective: str,
        max_iterations: int | None = None,
        auto_resume: bool = False,
        run_id: str | None = None,
    ) -> Any:
        """启动 Autonomous 自主迭代模式。

        4 阶段循环：plan → dev → verify → fix，复用 LoopKernel。
        不绕过 ConsensusEngine 前置共识门（HC-2）。

        Args:
            objective: 迭代目标。
            max_iterations: 最大迭代次数，None 则使用初始化时的配置。
            auto_resume: 是否自动从断点续跑。
            run_id: 可选的运行 ID，用于断点续跑。

        Returns:
            AutonomousRunReport。若 autonomous_controller 未启用，抛出 RuntimeError。

        Raises:
            RuntimeError: autonomous_enabled=False。
        """
        if not self.autonomous_enabled or self.autonomous_controller is None:
            raise RuntimeError(
                "AutonomousLoopController not enabled. "
                "Initialize dispatcher with autonomous_enabled=True."
            )

        from .autonomous.loop_controller import AutonomousConfig, AutonomousLoopController

        # 装配 LLM 投票后端（Task #87 收尾：生产路径装配）
        # 优先级: dispatcher.llm_backend > MOKA_API_KEY env var > None (mock 回退)
        llm_backend = self.llm_backend
        if llm_backend is None:
            llm_backend = self._resolve_moka_backend_from_env()

        # 重新构建 config（objective 是运行时参数，不能在 factory 中固定）
        config = AutonomousConfig(
            objective=objective,
            max_iterations=max_iterations or self.autonomous_max_iterations,
            consensus_engine=self.consensus_engine,
            dispatcher=self,
            auto_resume=auto_resume,
            llm_backend=llm_backend,
        )
        # 复用已初始化的 NotesMemory 目录
        controller = AutonomousLoopController(config=config)
        return controller.run(run_id=run_id)

    def _resolve_moka_backend_from_env(self) -> Any:
        """从 MOKA_API_KEY 环境变量自动创建 OpenAIBackend（用于 autonomous LLM 投票）。

        当 dispatcher 本身没有 llm_backend（如 TRAE skill 模式下
        MultiAgentDispatcher() 无参数创建）时，autonomous 投票仍可使用
        Moka AI。key 仅从环境变量读取，不硬编码到代码中。

        Returns:
            OpenAIBackend 或 None（MOKA_API_KEY 未设置或创建失败时）。
        """
        import os

        api_key = os.environ.get("MOKA_API_KEY")
        if not api_key:
            return None
        try:
            from .llm_backend import OpenAIBackend

            return OpenAIBackend(
                api_key=api_key,
                base_url=os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1"),
                model=os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6"),
            )
        except (ImportError, OSError, ValueError, RuntimeError) as e:
            # P1-3 (V4.1.2): Narrowed from bare Exception. Import/config/runtime
            # errors are expected fallback triggers; unexpected exceptions
            # should propagate so they are not silently swallowed.
            logger.warning("MOKA backend creation failed, falling back to mock: %s", e)
            return None

    # V4.0.0 P3-2: 插件热加载
    def register_plugin(self, name: str, plugin: Any) -> bool:
        """运行时注册插件实例。

        Args:
            name: 插件唯一名。
            plugin: 插件实例。

        Returns:
            True 注册成功，False 注册失败（plugins_enabled=False 或 no_hot_reload=True）。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return bool(self.plugin_hot_loader.hot_register(name, plugin))

    def unregister_plugin(self, name: str) -> bool:
        """运行时注销插件。

        Args:
            name: 插件名。

        Returns:
            True 注销成功，False 插件不存在。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return bool(self.plugin_hot_loader.hot_unregister(name))

    def register_builtin_plugin(self, name: str, plugin: Any) -> bool:
        """静态注册内置插件（不受 no_hot_reload 限制）。

        Args:
            name: 插件名。
            plugin: 插件实例。

        Returns:
            True 注册成功，False 已存在同名插件。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return bool(self.plugin_hot_loader.register_builtin(name, plugin))

    def get_plugin(self, name: str) -> Any | None:
        """获取已注册的插件实例。

        Args:
            name: 插件名。

        Returns:
            插件实例，未找到则返回 None。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return self.plugin_hot_loader.get_plugin(name)

    def list_plugins(self) -> list[str]:
        """列出所有已注册插件名。

        Returns:
            插件名列表。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return list(self.plugin_hot_loader.list_plugins())

    def scan_plugins(self) -> list[Any]:
        """扫描 drop-in 目录，加载新插件。

        Returns:
            新加载的 PluginEntry 列表。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return list(self.plugin_hot_loader.scan_dropin_dir())

    def reload_plugins(self) -> list[str]:
        """检查 mtime 和 checksum，重新加载变更的插件（失败回滚保留旧实例）。

        Returns:
            重载的插件名列表。

        Raises:
            RuntimeError: plugins_enabled=False。
        """
        if not self.plugins_enabled or self.plugin_hot_loader is None:
            raise RuntimeError(
                "PluginHotLoader not enabled. "
                "Initialize dispatcher with plugins_enabled=True."
            )
        return list(self.plugin_hot_loader.reload_if_changed())


__all__ = [
    "DISPATCH_LIFECYCLE_MAPPING",
    "ROLE_TEMPLATES",
    "MultiAgentDispatcher",
    "create_dispatcher",
    "quick_collaborate",
    "async_quick_collaborate",
]
