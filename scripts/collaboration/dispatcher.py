#!/usr/bin/env python3
"""V3 Multi-Agent Collaboration Dispatcher — Unified Entry Point.

Pipeline: Task → Intent → Roles → Coordinator → Workers → Scratchpad
       → Consensus → Compression → Permission → Memory → Result
"""

import locale
import logging
import os
import tempfile
import time
from typing import Any

from ._version import __version__
from .async_adapter import SyncToAsyncAdapter
from .async_llm_backend import AsyncLLMBackendFactory
from .dispatch_audit import DispatchAuditLogger
from .dispatch_component_factory import ComponentConfig, ComponentFactory
from .dispatch_hooks import DispatchHooks
from .dispatch_models import ROLE_TEMPLATES, DispatchResult
from .dispatch_pre_steps import PreDispatchPipeline
from .dispatch_rbac import DispatchRBAC
from .dispatch_result_assembler import ResultAssembler
from .dispatch_services import MemoryPipelineService, MetricsService, PermissionService, SkillProposalService
from .dispatch_steps import PostDispatchPipeline
from .enterprise_feature import EnterpriseFeature
from .event_bus import EventBus
from .llm_cache_async import AsyncLLMCache
from .permission_guard import PermissionLevel
from .rbac_engine import Permission, PermissionDeniedError
from .usage_tracker import track_usage
from .user_friendly_error import make_user_friendly_error

logger = logging.getLogger(__name__)

# Dispatch step → Lifecycle phase mapping
# Maps the 18-step dispatch pipeline to the 11-phase lifecycle (P1-P11)
DISPATCH_LIFECYCLE_MAPPING = {
    "step0_tenant_setup": "P1_Requirements",
    "step1_language": "P1_Requirements",
    "step2_validation": "P1_Requirements",
    "step3_rules": "P2_Architecture",
    "step4_intent": "P2_Architecture",
    "step5_role_match": "P3_Implementation",
    "step6_security": "P6_Security",
    "step7_preparation": "P3_Implementation",
    "step8_execute": "P3_Implementation",
    "step9_post_exec": "P4_Review",
    "step10_consensus": "P4_Review",
    "step11_permission": "P6_Security",
    "step12_memory": "P5_Integration",
    "step13_skillify": "P8_Optimization",
    "step14_five_axis": "P4_Review",
    "step15_retrospective": "P9_Retrospective",
    "step16_assemble": "P10_Delivery",
    "step17_hooks": "P10_Delivery",
    "step18_feedback": "P11_Monitoring",
    "step19_ue_testing": "P7_TestPlanning",
    "step20_tech_debt": "P9_TestExecution",
}


class MultiAgentDispatcher:
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
        # V3.8 #2: Two-stage code review gate
        enable_two_stage_review: bool = True,
        # V3.9-02: Stage 3 — Redesign audit (code simplicity check)
        enable_redesign_audit: bool = True,
        # V3.8 #3: Severity router + auto-fix loop
        enable_severity_router: bool = True,
        # V3.8 #7: Micro-task planner (optional; when provided, dispatched
        # tasks can be decomposed into 2-5 minute micro-tasks for more
        # granular execution tracking).
        micro_task_planner: Any = None,
        development_mode: bool = True,
        max_fix_iterations: int = 3,
        severity_router: Any = None,
        # V3.8 #4: Judge agent for finding consolidation (optional; when
        # provided, runs after the severity router to dedup/consolidate
        # findings before reporting).
        judge_agent: Any = None,
        # V3.8 #9: ContentCache wrapper for the LLM call path (optional;
        # when provided, checked before LLM API calls and populated after
        # responses — adds SHA-256 key hashing + secret filtering).
        content_cache: Any = None,
        # V3.9-02: CodeKnowledgeGraph for code-structure queries (optional;
        # when provided, workers query the graph before LLM calls to reduce
        # redundant Read/Grep tool usage).
        code_graph: Any = None,
        # V3.9-02: DispatchRBAC for dispatch-level permission checks
        # (optional; when provided, checked at dispatch start — denied
        # requests are logged and returned as failed DispatchResult).
        rbac: DispatchRBAC | None = None,
        # V3.9-02: DispatchAuditLogger for tamper-evident audit trail
        # (optional; when provided, logs dispatch_start/dispatch_end/
        # permission_denied/error events with SHA-256 chain hash).
        audit_logger: DispatchAuditLogger | None = None,
        redis_url: str | None = None,
        compression_threshold: int = 100000,
        memory_dir: str | None = None,
        permission_level: PermissionLevel = PermissionLevel.DEFAULT,
        mce_adapter: Any = None,
        llm_backend: Any = None,
        stream: bool = False,
        lang: str = "auto",
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
        # V3.8 feature flags
        self.enable_two_stage_review = enable_two_stage_review
        self.enable_redesign_audit = enable_redesign_audit
        self.enable_severity_router = enable_severity_router
        self.development_mode = development_mode
        self.max_fix_iterations = max_fix_iterations
        self._injected_severity_router = severity_router
        # V3.8 #7: Optional micro-task planner for granular task decomposition.
        self.micro_task_planner = micro_task_planner
        # V3.8 #4: Optional judge agent for finding consolidation.
        self.judge_agent = judge_agent
        # V3.8 #9: Optional ContentCache wrapper for the LLM call path.
        self.content_cache = content_cache
        # V3.9-02: Optional CodeKnowledgeGraph for code-structure queries.
        self._code_graph = code_graph
        # V3.9-02: Optional DispatchRBAC for dispatch-level permission checks.
        self._rbac = rbac
        # V3.9-02: Optional DispatchAuditLogger for tamper-evident audit trail.
        self._audit_logger = audit_logger
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

        os.makedirs(self.persist_dir, exist_ok=True)
        os.makedirs(self.memory_dir, exist_ok=True)

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
            # V3.8 #2: Two-stage review gate
            enable_two_stage_review=self.enable_two_stage_review,
            # V3.9-02: Stage 3 — Redesign audit
            enable_redesign_audit=self.enable_redesign_audit,
            # V3.8 #3: Severity router + auto-fix loop
            enable_severity_router=self.enable_severity_router,
            development_mode=self.development_mode,
            max_fix_iterations=self.max_fix_iterations,
            severity_router=self._injected_severity_router,
            # V3.8 #4: Judge agent for finding consolidation
            judge_agent=self.judge_agent,
            compressor=self.compressor,
            usage_tracker=self.usage_tracker,
            retrospective_engine=self.retrospective_engine,
            anchor_checker=self.anchor_checker,
            llm_backend=self.llm_backend,
            persist_dir=self.persist_dir,
            dispatcher=self,
            event_bus=self.event_bus,
            result_assembler=self._result_assembler,
        )

        # V3.8 #9: Attach ContentCache to the coordinator so workers can
        # check it before LLM API calls. The coordinator exposes it to
        # workers via spawn_workers().
        if self.content_cache is not None:
            self.coordinator.content_cache = self.content_cache

        # V3.9-02: Attach CodeKnowledgeGraph to the coordinator so workers
        # can query the graph before LLM calls (reduces Read/Grep usage).
        # The coordinator exposes it to workers via spawn_workers().
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

    def analyze_task(self, task_description: str) -> list[dict[str, str]]:
        """Analyze task and match appropriate roles."""
        track_usage("dispatcher.analyze_task")
        return self.role_matcher.analyze_task(task_description)  # type: ignore[no-any-return]

    def decompose_task(
        self,
        task_description: str,
        spec: dict[str, Any] | None = None,
    ) -> Any:
        """Decompose a task into micro-tasks using the configured planner.

        V3.8 #7: When a :class:`MicroTaskPlanner` is configured via
        the ``micro_task_planner`` parameter, this method delegates to
        ``planner.plan(task_description, spec)`` and returns the
        resulting :class:`MicroTaskPlan`. When no planner is
        configured, returns ``None``.

        Parameters
        ----------
        task_description:
            Natural-language task description.
        spec:
            Optional spec dict (files, functions, tests, etc.).

        Returns
        -------
        MicroTaskPlan or None
        """
        if self.micro_task_planner is None:
            return None
        return self.micro_task_planner.plan(task_description, spec=spec)

    def _maybe_decompose_task(
        self,
        task_description: str,
        use_micro_tasks: bool,
        kwargs: dict[str, Any],
    ) -> Any:
        """V3.8 #7: Optionally decompose the task into micro-tasks.

        Runs only when ``use_micro_tasks=True`` and a
        :class:`MicroTaskPlanner` is configured. Returns the
        :class:`MicroTaskPlan` (or ``None`` when decomposition is
        disabled or fails — graceful degradation).
        """
        if not use_micro_tasks or self.micro_task_planner is None:
            return None
        try:
            # Build a spec from kwargs when relevant keys are present.
            spec: dict[str, Any] = {}
            for key in ("files", "functions", "tests", "acceptance_criteria"):
                if key in kwargs:
                    spec[key] = kwargs[key]
            plan = self.decompose_task(task_description, spec=spec or None)
            if plan is not None:
                logger.info(
                    "MicroTaskPlanner decomposed task into %d micro-tasks "
                    "(est. %d min)",
                    len(plan.micro_tasks),
                    plan.total_estimated_minutes,
                )
                if self.usage_tracker:
                    self.usage_tracker.tick("micro_task_planner")
            return plan
        except (ValueError, AttributeError, TypeError, RuntimeError) as exc:
            logger.warning("Micro-task decomposition failed: %s", exc)
            return None

    def dispatch(
        self, task_description: str, roles: list[str] | None = None, mode: str = "auto", dry_run: bool = False, use_micro_tasks: bool = False, **kwargs: Any
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
                # Determine the roles to check — use requested roles or
                # fall back to a wildcard list (any role).
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
                    # V3.9-02: Log permission denial to audit logger.
                    if self._audit_logger is not None:
                        try:
                            self._audit_logger.log_permission_denied(
                                user_id=user_id,
                                reason=perm.reason,
                            )
                        except (ValueError, RuntimeError, OSError) as audit_err:
                            logger.warning("Audit log_permission_denied failed: %s", audit_err)
                    # Return a failed DispatchResult immediately.
                    self.metrics_service.safe_record(lambda m: (
                        m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
                    ))
                    denied_result = DispatchResult(
                        success=False,
                        task_description=task_description,
                        errors=[f"Permission denied: {perm.reason}"],
                        permission_result=permission_result_dict,
                    )
                    # V3.9-02: Attach audit entries (including the
                    # permission_denied event that was just logged).
                    self._attach_audit_entries(denied_result)
                    return denied_result
            except (ValueError, AttributeError, TypeError, RuntimeError) as rbac_err:
                logger.warning("RBAC check failed (allowing dispatch): %s", rbac_err)
                # Fail-open: log the error but continue dispatch (do not
                # block on RBAC infrastructure failures).

        self.metrics_service.safe_record(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("dispatch")

        # V3.9-02: Log dispatch_start to audit logger.
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
            # V3.9-02: Log dispatch_end for early return.
            self._log_dispatch_end_audit(user_id, False, time.time() - start_time)
            early_result = pre_result.early_return
            if permission_result_dict is not None:
                early_result.permission_result = permission_result_dict
            self._attach_audit_entries(early_result)
            return early_result

        tenant_ctx = pre_result.tenant_ctx

        # V3.8 #7: Micro-task decomposition (after task analysis, before
        # role assignment / worker execution). Runs only when explicitly
        # requested via use_micro_tasks=True and a planner is configured.
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
            result = self.post_dispatch.execute(
                pre_result=pre_result,
                exec_result=exec_result,
                worker_results=worker_results,
                exec_errors=exec_errors,
                exec_timing=exec_timing,
                start_time=start_time,
                phase=phase,
                **kwargs,
            )

            # Attach the micro-task plan to the result (if decomposed).
            if micro_task_plan is not None:
                result.micro_task_plan = micro_task_plan.to_dict()
                result.details["micro_task_plan"] = micro_task_plan.to_dict()

            # V3.9-02: Attach RBAC permission result and audit entries.
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

    async def async_dispatch(
        self,
        task_description: str,
        roles: list[str] | None = None,
        mode: str = "auto",
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DispatchResult:
        """Async version of dispatch() using AsyncCoordinator. Falls back to sync on failure."""
        track_usage("dispatcher.async_dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()
        phase = "async_dispatch"

        self.metrics_service.safe_record(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("async_dispatch")

        # Pre-dispatch steps (shared with dispatch)
        pre_result = self.pre_dispatch.execute(task_description, roles, mode, dry_run, start_time, phase, **kwargs)
        if pre_result.early_return:
            self.metrics_service.safe_record(lambda m: m.tasks_in_progress_gauge.labels(phase=phase).dec())
            return pre_result.early_return

        tenant_ctx = pre_result.tenant_ctx

        try:
            # Step 8: Execute workers asynchronously via AsyncCoordinator
            matched_roles = pre_result.matched_roles
            self.metrics_service.safe_record(lambda m: m.workers_active_gauge.labels(worker_type="agent").inc(len(matched_roles)))

            exec_result, worker_results, exec_errors, exec_timing = await self._execute_async_workers(
                pre_result.plan, task_description, matched_roles, kwargs
            )

            self.metrics_service.safe_record(lambda m: m.workers_active_gauge.labels(worker_type="agent").dec(len(matched_roles)))

            # Post-dispatch steps (shared with dispatch)
            return self.post_dispatch.execute(
                pre_result=pre_result,
                exec_result=exec_result,
                worker_results=worker_results,
                exec_errors=exec_errors,
                exec_timing=exec_timing,
                start_time=start_time,
                phase=phase,
                **kwargs,
            )

        except (ValueError, TypeError, AttributeError) as dispatch_err:
            return self._handle_dispatch_error(dispatch_err, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)
        except (ImportError, ModuleNotFoundError) as import_err:
            return self._handle_dispatch_error(import_err, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)
        except (RuntimeError, OSError, ConnectionError, TimeoutError) as e:
            return self._handle_dispatch_error(e, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)

    async def _execute_async_workers(
        self, plan: Any, task_description: str, matched_roles: list[dict[str, Any]], kwargs: dict[str, Any]
    ) -> tuple[Any, list[dict[str, Any]], list[str], dict[str, float]]:
        """Execute workers asynchronously, falling back to sync on failure."""
        # Async backend selection
        if kwargs.get('use_async_backend', False) or os.environ.get('DEVSQUAD_USE_ASYNC', '').lower() in ('1', 'true'):
            try:
                AsyncLLMBackendFactory.create(self.llm_backend.__class__.__name__)
            except (ImportError, AttributeError, RuntimeError):
                SyncToAsyncAdapter(self.llm_backend)
        else:
            SyncToAsyncAdapter(self.llm_backend)

        # Async cache
        if kwargs.get('use_async_cache', False):
            try:
                AsyncLLMCache(cache_dir=self.persist_dir or "data/llm_cache")
            except (ImportError, AttributeError, OSError) as e:
                logger.debug("Async cache init failed: %s", e)

        try:
            from .async_coordinator import AsyncCoordinator

            async_coordinator = AsyncCoordinator(
                scratchpad=self.scratchpad,
                persist_dir=self.persist_dir,
                enable_compression=self.enable_compression,
                compression_threshold=self.compression_threshold,
                llm_backend=self.llm_backend,
                stream=self.stream,
                memory_provider=self.memory_bridge if self.enable_memory else None,
                task_timeout=kwargs.get("task_timeout", 300),
                max_concurrency=kwargs.get("max_concurrency", 10),
                execution_guard=self.execution_guard,
            )

            async_plan = async_coordinator.plan_task(
                task_description=task_description,
                available_roles=[
                    {
                        "role_id": r["role_id"],
                        "role_prompt": str(ROLE_TEMPLATES.get(r["role_id"], {}).get("prompt", "")),
                        "confidence": r.get("confidence", 0.5),
                    }
                    for r in matched_roles
                ],
            )
            async_coordinator.spawn_workers(async_plan)
            exec_result = await async_coordinator.execute_plan(async_plan)

            worker_results, step6_time, step7_time = self.post_dispatch._collect_worker_results(exec_result)
            exec_errors = list(exec_result.errors) if exec_result.errors else []
            return exec_result, worker_results, exec_errors, {"step6_time": step6_time, "step7_time": step7_time}

        except (ImportError, RuntimeError, AttributeError, OSError) as async_err:
            logger.warning("Async dispatch failed, falling back to sync: %s", async_err)
            return self._execute_workers(plan, task_description)

    # ------------------------------------------------------------------
    # Private step methods
    # ------------------------------------------------------------------

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
        """Handle dispatch errors uniformly for sync and async paths."""
        prefix = "Async " if is_async else ""
        if isinstance(error, (ValueError, TypeError, AttributeError)):
            logger.error(
                "%sdispatch validation error for task '%s': %s - %s",
                prefix, task_description[:50], type(error).__name__, error, exc_info=True,
            )
            error_key, metrics_label = "dispatch_failed", "validation"
        elif isinstance(error, (ImportError, ModuleNotFoundError)):
            logger.error(
                "Missing dependency during %sdispatch of task '%s': %s",
                prefix.lower(), task_description[:50], error, exc_info=True,
            )
            error_key, metrics_label = "backend_unavailable", "dependency"
        else:
            logger.critical(
                "UNEXPECTED ERROR in %sdispatch task '%s': %s - %s",
                prefix.lower(), task_description[:50], type(error).__name__, error, exc_info=True,
            )
            error_key, metrics_label = "dispatch_failed", "unknown"

        self.enterprise.clear_tenant_context(tenant_ctx)
        self.metrics_service.safe_record(lambda m: (
            m.record_error(metrics_label, "dispatcher"),
            m.tasks_in_progress_gauge.labels(phase=phase).dec(),
        ))
        friendly = make_user_friendly_error(error_key, original_error=error)
        return DispatchResult(
            success=False,
            task_description=task_description,
            matched_roles=[],
            summary=friendly.message,
            errors=[friendly.format()],
            duration_seconds=time.time() - start_time,
            lang=lang,
        )

    # ------------------------------------------------------------------
    # V3.9-02: Audit logging helpers
    # ------------------------------------------------------------------

    def _log_dispatch_end_audit(
        self, user_id: str, success: bool, duration: float
    ) -> None:
        """Log dispatch_end event to the audit logger (if configured)."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_dispatch_end(
                user_id=user_id,
                success=success,
                duration=duration,
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_dispatch_end failed: %s", audit_err)

    def _log_dispatch_error_audit(
        self, user_id: str, error: Exception
    ) -> None:
        """Log an error event to the audit logger (if configured)."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_error(
                user_id=user_id,
                error_type=type(error).__name__,
                context={"message": str(error)[:200]},
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_error failed: %s", audit_err)

    def _attach_audit_entries(self, result: DispatchResult) -> None:
        """Attach recent audit entries to the dispatch result."""
        if self._audit_logger is None:
            return
        try:
            entries = self._audit_logger.get_entries(limit=50)
            result.audit_entries = [
                {
                    "event_type": e.event_type,
                    "user_id": e.user_id,
                    "timestamp": e.timestamp,
                    "details": e.details,
                    "entry_hash": e.entry_hash,
                }
                for e in entries
            ]
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit get_entries failed: %s", audit_err)

    def _resolve_language(self, lang: str) -> str:
        """Resolve language from 'auto' to a specific language code."""
        if lang != "auto":
            return lang

        try:
            try:
                loc = locale.getlocale()[0] or ""
            except (ValueError, TypeError):
                loc = ""
            if loc.startswith("ja"):
                return "ja"
            elif loc.startswith("zh"):
                return "zh"
            else:
                return "zh"
        except (ValueError, TypeError, OSError) as e:
            logger.debug("Locale detection failed, using default language: %s", e)
            return "zh"

    def _execute_workers(
        self, plan: Any, _task_description: str
    ) -> tuple[Any, list[dict[str, Any]], list[str], dict[str, float]]:
        """Execute workers via Coordinator. Returns (exec_result, worker_results, errors, timing)."""
        exec_result = self.coordinator.execute_plan(plan)
        worker_results, step6_time, step7_time = self.post_dispatch._collect_worker_results(exec_result)
        exec_errors = list(exec_result.errors) if exec_result.errors else []
        return exec_result, worker_results, exec_errors, {
            "step6_time": step6_time,
            "step7_time": step7_time,
        }

    def _get_current_tenant_id(self) -> str:
        """Get current tenant_id for data isolation, defaults to 'default'."""
        if self.enterprise.enable_multi_tenant and self.enterprise.tenant_manager:
            current_tenant = self.enterprise.tenant_manager.get_current_tenant()
            if current_tenant:
                return current_tenant.tenant_id
        return "default"

    def quick_dispatch(
        self,
        task: str,
        output_format: str = "structured",
        include_action_items: bool = True,
        include_timing: bool = False,
    ) -> DispatchResult:
        """Quick dispatch returning DispatchResult with formatted report.

        Args:
            task: Task description
            output_format: "structured" (default), "compact", or "detailed"
            include_action_items: Include action items in report
            include_timing: Include step timing analysis
        """
        result = self.dispatch(task)

        if output_format == "structured":
            result.summary = self.report_formatter.format_structured_report(
                result, include_action_items, include_timing
            )
        elif output_format == "compact":
            result.summary = self.report_formatter.format_compact_report(result)
        else:
            result.summary = result.to_markdown()

        return result

    def _format_structured_report(
        self, result: DispatchResult, include_action_items: bool = True, include_timing: bool = False
    ) -> str:
        return self.report_formatter.format_structured_report(result, include_action_items, include_timing)  # type: ignore[no-any-return]

    def _format_compact_report(self, result: DispatchResult) -> str:
        return self.report_formatter.format_compact_report(result)  # type: ignore[no-any-return]

    def _extract_findings(self, scratchpad_summary: str) -> list[str]:
        return self.report_formatter.extract_findings(scratchpad_summary)  # type: ignore[no-any-return]

    def _generate_action_items(self, result: DispatchResult) -> list[dict[str, str]]:
        return self.report_formatter.generate_action_items(result)  # type: ignore[no-any-return]

    def get_status(self) -> dict[str, Any]:
        """获取系统状态"""
        status = {
            "version": __version__,
            "persist_dir": self.persist_dir,
            "components": {
                "coordinator": self.coordinator is not None,
                "scratchpad": self.scratchpad is not None,
                "batch_scheduler": self.batch_scheduler is not None,
                "consensus": self.consensus_engine is not None,
                "compressor": self.compressor is not None,
                "permission_guard": self.permission_guard is not None,
                "warmup_manager": self.warmup_manager is not None,
                "memory_bridge": self.memory_bridge is not None,
                "skillifier": self.skillifier is not None,
                "quality_guard": self.quality_guard is not None,
                "performance_monitor": True,
                "execution_guard": self.execution_guard is not None,
            },
            "dispatch_count": len(self._dispatch_history),
            "scratchpad_stats": self.scratchpad.get_stats() if self.scratchpad else {},
        }
        self._append_perf_status(status)
        self._append_warmup_status(status)
        self._append_memory_status(status)
        return status

    def _append_perf_status(self, status: dict) -> None:
        """Append performance stats to status dict."""
        try:
            perf_stats = self._perf_monitor.get_statistics()
            status["performance"] = perf_stats
            regression = self._perf_monitor.detect_regression()
            if regression:
                status["regression_detected"] = regression
        except (ValueError, AttributeError, RuntimeError) as e:
            logger.debug("Performance stats collection failed: %s", e)

    def _append_warmup_status(self, status: dict) -> None:
        """Append warmup metrics to status dict."""
        if not self.warmup_manager:
            return
        try:
            metrics = self.warmup_manager.get_metrics()
            status["warmup_metrics"] = {
                "cache_size": metrics.cache_size,
                "hit_rate": round(metrics.cache_hit_rate, 3) if metrics.cache_hit_rate else 0,
                "tasks_completed": metrics.tasks_completed,
                "eager_duration_ms": round(metrics.eager_duration_ms, 2),
            }
        except (AttributeError, ValueError, RuntimeError):
            status["warmup_metrics"] = None

    def _append_memory_status(self, status: dict) -> None:
        """Append memory stats to status dict."""
        if not self.memory_bridge:
            return
        try:
            mem_stats = self.memory_bridge.get_statistics()
            status["memory_stats"] = {
                "total_memories": mem_stats.total_memories,
                "by_type_counts": mem_stats.by_type_counts,
                "index_built": mem_stats.index_built,
            }
        except (AttributeError, ValueError, OSError):
            status["memory_stats"] = None

    def get_history(self, limit: int = 10, **kwargs: Any) -> list[dict[str, Any]]:
        """Get dispatch history."""
        if self.enterprise.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.enterprise.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return []
        return [r.to_dict() for r in self._dispatch_history[-limit:]]

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return self._perf_monitor.get_statistics()  # type: ignore[no-any-return]

    def check_performance_regression(self) -> dict[str, Any] | None:
        """Check for performance regression."""
        return self._perf_monitor.detect_regression()  # type: ignore[no-any-return]

    def shutdown(self) -> None:
        """Gracefully shut down all components."""
        self._shutdown_component(
            self.warmup_manager, "shutdown",
            (RuntimeError, OSError, AttributeError), "Warmup shutdown failed")
        self._shutdown_component(
            self.memory_bridge, "cleanup_expired_memories",
            (OSError, AttributeError, RuntimeError), "Memory cleanup failed")
        self._shutdown_component(
            self.usage_tracker, "persist",
            (OSError, ValueError, AttributeError), "Usage tracker persist failed")
        self._shutdown_component(
            self.enterprise.audit_logger, "force_flush",
            (OSError, AttributeError, RuntimeError), "Audit flush failed")
        self._shutdown_component(
            self.enterprise.tenant_manager, "clear_context",
            (AttributeError, RuntimeError, OSError), "Tenant cleanup failed")

    def _shutdown_component(self, component: Any, method: str, exc_types: tuple, msg: str) -> None:
        """Safely call a shutdown method on a component."""
        if not component:
            return
        try:
            getattr(component, method)()
        except exc_types as e:
            logger.debug("%s: %s", msg, e)


def create_dispatcher(**kwargs: Any) -> MultiAgentDispatcher:
    """Factory function to create and initialize dispatcher."""
    return MultiAgentDispatcher(**kwargs)


def quick_collaborate(task: str, **kwargs: Any) -> DispatchResult:
    """Convenience function: single-call collaboration."""
    disp = create_dispatcher(**kwargs)
    result = disp.dispatch(task)
    disp.shutdown()
    return result


async def async_quick_collaborate(task: str, roles: list[str] | None = None, **kwargs: Any) -> DispatchResult:
    """Async version of quick_collaborate()."""
    disp = create_dispatcher(**kwargs)
    result = await disp.async_dispatch(task, roles=roles, **kwargs)
    disp.shutdown()
    return result
