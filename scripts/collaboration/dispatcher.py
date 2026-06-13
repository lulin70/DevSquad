#!/usr/bin/env python3
"""V3 Multi-Agent Collaboration Dispatcher — Unified Entry Point.

Pipeline: Task → Intent → Roles → Coordinator → Workers → Scratchpad
       → Consensus → Compression → Permission → Memory → Result
"""

import json
import logging
import os
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

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
}

from .batch_scheduler import BatchScheduler
from .concern_pack_loader import ConcernPackLoader
from .consensus import ConsensusEngine
from .context_compressor import ContextCompressor
from .coordinator import Coordinator
from .dispatch_models import DispatchResult, I18N, PLANNED_ROLES, ROLE_TEMPLATES, PerformanceMetric, PerformanceThresholds
from .dispatch_performance import PerformanceMonitor
from .input_validator import InputValidator
from .memory_bridge import EpisodicMemory, MemoryBridge
from .models import EntryType
from .permission_guard import ActionType, PermissionGuard, PermissionLevel, ProposedAction
from .prometheus_metrics import get_metrics
from .report_formatter import ReportFormatter
from .role_matcher import RoleMatcher
from .scratchpad import Scratchpad, ScratchpadEntry
from .skillifier import Skillifier
from .test_quality_guard import TestQualityGuard, TestQualityReport
from .usage_tracker import track_usage
from .user_friendly_error import make_user_friendly_error, translate_validation_result
from .warmup_manager import WarmupConfig, WarmupManager
from ._version import __version__

# Enterprise feature imports
from .rbac_engine import RBACEngine, Permission, PermissionDeniedError
from .audit_logger import AuditLogger, SensitiveDataMasker
from .multi_tenant import MultiTenantManager, IsolationLevel
from .async_llm_backend import AsyncLLMBackendFactory
from .async_adapter import SyncToAsyncAdapter, AutoBackendSelector
from .llm_cache_async import AsyncLLMCache

class MultiAgentDispatcher:
    """V3 Unified Multi-Agent Collaboration Dispatcher.

    Pipeline: Intent → Roles → Coordinator → Workers → Scratchpad →
    Consensus → Compression → Permission → Memory → Result
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        enable_warmup: bool = True,
        enable_compression: bool = True,
        enable_permission: bool = True,
        enable_memory: bool = True,
        enable_skillify: bool = True,
        enable_quality_guard: bool = True,
        enable_anchor_check: bool = True,
        enable_retrospective: bool = True,
        enable_usage_tracker: bool = True,
        enable_feedback_loop: Union[bool, str] = "auto",
        enable_redis_cache: bool = False,
        enable_execution_guard: bool = True,
        redis_url: Optional[str] = None,
        compression_threshold: int = 100000,
        memory_dir: Optional[str] = None,
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
        self._init_components()
        self._init_enterprise_features(**kwargs)

    def _init_enterprise_features(self, **kwargs: Any) -> None:
        """Initialize enterprise features: RBAC, Audit, Multi-Tenant."""
        self.enable_rbac = kwargs.get('enable_rbac', True)
        self.enable_audit = kwargs.get('enable_audit', True)
        self.enable_data_masking = kwargs.get('enable_data_masking', True)
        self.enable_multi_tenant = kwargs.get('enable_multi_tenant', True)

        self.rbac_engine = None
        self.audit_logger = None
        self.data_masker = None
        self.tenant_manager = None

        if self.enable_rbac:
            try:
                self.rbac_engine = RBACEngine()
                from .rbac_engine import RBACUser, UserRole
                self.rbac_engine.add_user(RBACUser("default", "default_admin", {UserRole.SUPER_ADMIN}))
                logger.info("RBAC Engine enabled")
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning(f"RBAC Engine initialization failed: {e}")

        if self.enable_audit:
            try:
                audit_dir = os.path.join(self.persist_dir, "audit") if self.persist_dir else ".devsquad_data/audit"
                self.audit_logger = AuditLogger(log_dir=audit_dir)
                if self.enable_data_masking:
                    self.data_masker = SensitiveDataMasker()
                logger.info(f"Audit Logger enabled (data_masking={self.enable_data_masking})")
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning(f"Audit Logger initialization failed: {e}")

        if self.enable_multi_tenant:
            try:
                self.tenant_manager = MultiTenantManager()
                from .multi_tenant import Tenant
                self.tenant_manager.create_tenant(Tenant(tenant_id="default", name="Default Tenant"))
                logger.info("Multi-Tenant Manager enabled")
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning(f"Multi-Tenant Manager initialization failed: {e}")

    def _init_components(self) -> None:
        """Initialize all v3 components."""
        self._init_core_components()
        self._init_optional_components()
        self._init_cache_and_monitor()
        self._safe_metrics(lambda m: m.set_build_info(version=__version__))

    def _init_core_components(self) -> None:
        """Initialize core components."""
        self.scratchpad = Scratchpad(persist_dir=self.persist_dir)

        # Initialize ExecutionGuard if enabled (graceful degradation)
        self.execution_guard = None
        if self.enable_execution_guard:
            try:
                from .execution_guard import ExecutionGuard
                self.execution_guard = ExecutionGuard()
                logger.info("ExecutionGuard enabled")
            except (ImportError, ModuleNotFoundError, AttributeError, RuntimeError) as e:
                logger.warning("ExecutionGuard initialization failed: %s", e)

        self.coordinator = Coordinator(
            scratchpad=self.scratchpad,
            persist_dir=self.persist_dir,
            enable_compression=self.enable_compression,
            compression_threshold=self.compression_threshold,
            llm_backend=self.llm_backend,
            stream=self.stream,
            execution_guard=self.execution_guard,
        )

        self.batch_scheduler = BatchScheduler()
        self.consensus_engine = ConsensusEngine()
        self.role_matcher = RoleMatcher()
        self.report_formatter = ReportFormatter(lang=self.lang)

        self.compressor = ContextCompressor(token_threshold=self.compression_threshold) if self.enable_compression else None
        self.permission_guard = PermissionGuard(current_level=self.permission_level) if self.enable_permission else None

        self.warmup_manager = self._init_warmup_manager()
        self.memory_bridge = MemoryBridge(base_dir=self.memory_dir, mce_adapter=self._mce_adapter) if self.enable_memory else None
        self.skillifier = Skillifier() if self.enable_skillify else None
        self.quality_guard = TestQualityGuard("", "") if self.enable_quality_guard else None
        self.anchor_checker = self._try_import_component('anchor_checker', 'AnchorChecker')
        self.retrospective_engine = self._init_retrospective_engine()
        self.usage_tracker = self._init_usage_tracker()

        self._dispatch_history: list[DispatchResult] = []
        self._max_history = 100
        self._validator = InputValidator()

    def _init_warmup_manager(self) -> Optional[WarmupManager]:
        """Init WarmupManager if enabled."""
        if not self.enable_warmup:
            return None
        warmup_cfg = WarmupConfig(
            cache_enabled=True, cache_max_size=50, cache_ttl_seconds=3600, metrics_enabled=True,
        )
        mgr = WarmupManager(config=warmup_cfg)
        try:
            mgr.warmup()
        except (RuntimeError, OSError, ImportError) as e:
            logger.warning("Warmup failed: %s", e)
        return mgr

    def _try_import_component(self, module_name: str, class_name: str) -> Optional[Any]:
        """Try to import and instantiate a component."""
        try:
            import importlib
            mod = importlib.import_module(f".{module_name}", package=__package__)
            return getattr(mod, class_name)()
        except (ImportError, AttributeError, RuntimeError, OSError):
            return None

    def _init_retrospective_engine(self) -> Optional[Any]:
        """Init RetrospectiveEngine if enabled."""
        if not self.enable_retrospective:
            return None
        try:
            from .retrospective import RetrospectiveEngine
            return RetrospectiveEngine(memory_bridge=self.memory_bridge if self.enable_memory else None)
        except (ImportError, AttributeError, RuntimeError):
            return None

    def _init_usage_tracker(self) -> Optional[Any]:
        """Init FeatureUsageTracker if enabled."""
        if not self.enable_usage_tracker:
            return None
        try:
            from .feature_usage_tracker import FeatureUsageTracker
            return FeatureUsageTracker(persist_path=os.path.join(self.persist_dir, "feature_usage.json"))
        except (ImportError, AttributeError, RuntimeError):
            return None

    def _init_optional_components(self) -> None:
        """Init optional components with graceful fallback."""
        self.output_slicer = self._try_import_component('output_slicer', 'OutputSlicer')
        self.ci_feedback = self._try_import_component('ci_feedback_adapter', 'CIFeedbackAdapter')
        self._std_templates: Dict[str, Any] = {}
        self.prompt_variant_gen = self._try_import_component('prompt_variant_generator', 'PromptVariantGenerator')
        self.role_template_market = self._try_import_component('role_template_market', 'RoleTemplateMarket')

    def _init_cache_and_monitor(self) -> None:
        """Initialize cache, monitor, and utility components."""
        if self.enable_redis_cache and self.redis_url:
            from .llm_cache import configure_redis_cache
            configure_redis_cache(enabled=True, url=self.redis_url)

        self._perf_monitor = PerformanceMonitor(window_size=100)
        self._concern_loader = ConcernPackLoader()

        from .dual_layer_context import DualLayerContextManager
        self.context_manager = DualLayerContextManager()

        from .intent_workflow_mapper import IntentWorkflowMapper
        self.intent_mapper = IntentWorkflowMapper()

        from .operation_classifier import OperationClassifier
        self.operation_classifier = OperationClassifier()

        from .skill_registry import SkillRegistry
        self.skill_registry = SkillRegistry(storage_path=os.path.join(self.persist_dir, "skills"))

        from .ai_semantic_matcher import AISemanticMatcher
        self.semantic_matcher = AISemanticMatcher(llm_backend=self.llm_backend)

        from .null_providers import get_null_cache, get_null_memory, get_null_monitor, get_null_retry
        self._null_cache = get_null_cache()
        self._null_retry = get_null_retry()
        self._null_monitor = get_null_monitor()
        self._null_memory = get_null_memory()

    def analyze_task(self, task_description: str) -> list[dict[str, str]]:
        """Analyze task and match appropriate roles."""
        track_usage("dispatcher.analyze_task")
        return self.role_matcher.analyze_task(task_description)

    def dispatch(
        self, task_description: str, roles: Optional[List[str]] = None, mode: str = "auto", dry_run: bool = False, **kwargs: Any
    ) -> DispatchResult:
        """Core dispatch method - complete multi-Agent collaboration in one call.

        Args:
            task_description: User's task in natural language
            roles: Optional role IDs (None=auto match)
            mode: "auto"/"parallel"/"sequential"/"consensus"
            dry_run: Simulate without running Workers
            **kwargs: Additional options (tenant_id, user_id, etc.)
        """
        track_usage("dispatcher.dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()
        phase = "dispatch"

        self._safe_metrics(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("dispatch")

        # Pre-dispatch steps (shared with async_dispatch)
        pre_result = self._pre_dispatch_steps(task_description, roles, mode, dry_run, start_time, phase, **kwargs)
        if pre_result.early_return:
            self._safe_metrics(lambda m: m.tasks_in_progress_gauge.labels(phase=phase).dec())
            return pre_result.early_return

        tenant_ctx = pre_result.tenant_ctx

        try:
            # Step 8: Execute workers (sync path)
            matched_roles = pre_result.matched_roles
            self._safe_metrics(lambda m: m.workers_active_gauge.labels(worker_type="agent").inc(len(matched_roles)))
            exec_result, worker_results, exec_errors, exec_timing = self._execute_workers(pre_result.plan, task_description)
            self._safe_metrics(lambda m: m.workers_active_gauge.labels(worker_type="agent").dec(len(matched_roles)))

            # Post-dispatch steps (shared with async_dispatch)
            return self._post_dispatch_steps(
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
            return self._handle_dispatch_error(dispatch_err, task_description, tenant_ctx, phase, start_time, pre_result.lang)
        except (ImportError, ModuleNotFoundError) as import_err:
            return self._handle_dispatch_error(import_err, task_description, tenant_ctx, phase, start_time, pre_result.lang)
        except Exception as e:
            return self._handle_dispatch_error(e, task_description, tenant_ctx, phase, start_time, pre_result.lang)

    async def async_dispatch(
        self,
        task_description: str,
        roles: Optional[List[str]] = None,
        mode: str = "auto",
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DispatchResult:
        """Async version of dispatch() using AsyncCoordinator. Falls back to sync on failure."""
        track_usage("dispatcher.async_dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()
        phase = "async_dispatch"

        self._safe_metrics(lambda m: (
            m.dispatch_counter.labels(mode=mode, role_count="0").inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).inc(),
        ))

        if self.usage_tracker:
            self.usage_tracker.tick("async_dispatch")

        # Pre-dispatch steps (shared with dispatch)
        pre_result = self._pre_dispatch_steps(task_description, roles, mode, dry_run, start_time, phase, **kwargs)
        if pre_result.early_return:
            self._safe_metrics(lambda m: m.tasks_in_progress_gauge.labels(phase=phase).dec())
            return pre_result.early_return

        tenant_ctx = pre_result.tenant_ctx

        try:
            # Step 8: Execute workers asynchronously via AsyncCoordinator
            matched_roles = pre_result.matched_roles
            self._safe_metrics(lambda m: m.workers_active_gauge.labels(worker_type="agent").inc(len(matched_roles)))

            exec_result, worker_results, exec_errors, exec_timing = await self._execute_async_workers(
                pre_result.plan, task_description, matched_roles, kwargs
            )

            self._safe_metrics(lambda m: m.workers_active_gauge.labels(worker_type="agent").dec(len(matched_roles)))

            # Post-dispatch steps (shared with dispatch)
            return self._post_dispatch_steps(
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
        except Exception as e:
            return self._handle_dispatch_error(e, task_description, tenant_ctx, phase, start_time, pre_result.lang, is_async=True)

    async def _execute_async_workers(
        self, plan: Any, task_description: str, matched_roles: List[Dict[str, Any]], kwargs: Dict[str, Any]
    ) -> Tuple[Any, List[Dict[str, Any]], List[str], Dict[str, float]]:
        """Execute workers asynchronously, falling back to sync on failure."""
        # Async backend selection
        async_backend = None
        if kwargs.get('use_async_backend', False) or os.environ.get('DEVSQUAD_USE_ASYNC', '').lower() in ('1', 'true'):
            try:
                async_backend = AsyncLLMBackendFactory.create(self.llm_backend.__class__.__name__)
            except (ImportError, AttributeError, RuntimeError):
                async_backend = SyncToAsyncAdapter(self.llm_backend)
        else:
            async_backend = SyncToAsyncAdapter(self.llm_backend)

        # Async cache
        async_cache = None
        if kwargs.get('use_async_cache', False):
            try:
                async_cache = AsyncLLMCache(cache_dir=self.persist_dir or "data/llm_cache")
            except (ImportError, AttributeError, OSError) as e:
                logger.debug(f"Async cache init failed: {e}")

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

            worker_results, step6_time, step7_time = self._collect_worker_results(exec_result)
            exec_errors = list(exec_result.errors) if exec_result.errors else []
            return exec_result, worker_results, exec_errors, {"step6_time": step6_time, "step7_time": step7_time}

        except (ImportError, RuntimeError, AttributeError, OSError) as async_err:
            logger.warning("Async dispatch failed, falling back to sync: %s", async_err)
            return self._execute_workers(plan, task_description)

    # ------------------------------------------------------------------
    # Private step methods extracted from dispatch()
    # ------------------------------------------------------------------

    @dataclass
    class _PreDispatchResult:
        """Result container for _pre_dispatch_steps()."""
        task_description: str
        lang: str
        rule_collection: Any
        intent_match: Any
        matched_roles: List[Dict[str, Any]]
        role_ids: List[str]
        concern_packs: Any
        concern_enhancements: Dict[str, Any]
        plan: Any
        structured_goal: Any
        prep_timing: Dict[str, float]
        step1_time: float
        step2_time: float
        tenant_ctx: Any = None
        early_return: Optional[DispatchResult] = None

    def _pre_dispatch_steps(
        self,
        task_description: str,
        roles: Optional[List[str]],
        mode: str,
        dry_run: bool,
        start_time: float,
        phase: str,
        **kwargs: Any,
    ):
        """Steps 0-7: tenant setup, validation, intent, roles, preparation."""
        # Step 0: Multi-tenant context setup
        tenant_ctx = self._setup_tenant_context(kwargs, start_time)
        if isinstance(tenant_ctx, DispatchResult):
            return self._make_early_pre_result(
                task_description, self.lang, None, tenant_ctx,
                step1_time=start_time, step2_time=start_time,
            )

        # Step 1: Resolve language
        lang = self._resolve_language(self.lang)

        # Step 2: Validate input
        task_description, early_return = self._validate_input(task_description, roles, lang)
        if early_return:
            return self._make_early_pre_result(
                task_description, lang, tenant_ctx, early_return,
                step1_time=start_time, step2_time=start_time,
            )

        # RBAC pre-check
        rbac_denied = self._check_rbac_access(kwargs, task_description, lang, start_time)
        if rbac_denied:
            return self._make_early_pre_result(
                task_description, lang, tenant_ctx, rbac_denied,
                step1_time=start_time, step2_time=start_time,
            )

        # Step 3: Collect rules and inject CI context
        task_description, rule_collection, early_return = self._collect_rules(task_description, lang)
        if early_return:
            return self._make_early_pre_result(
                task_description, lang, tenant_ctx, early_return,
                rule_collection=rule_collection,
                step1_time=start_time, step2_time=start_time,
            )

        step1_time = time.time()

        # Step 4: Detect intent
        intent_match = self._detect_intent(task_description, lang)

        # Audit: dispatch start
        if self.audit_logger:
            try:
                self.audit_logger.log(
                    user_id=kwargs.get('user_id', 'system'),
                    action="task:dispatch_start",
                    resource_type="Task",
                    resource_id="unknown",
                    details={"task": task_description[:200]}
                )
            except (OSError, AttributeError, KeyError) as e:
                logger.debug(f"Audit logging failed: {e}")

        # Step 5: Match roles
        matched_roles = self._match_roles(task_description, roles)

        # Step 6: Validate roles and security (concern packs + dry_run)
        role_ids, concern_packs, concern_enhancements, early_return = self._validate_roles_and_security(
            task_description, matched_roles, lang, dry_run, start_time
        )
        if early_return:
            return self._make_early_pre_result(
                task_description, lang, tenant_ctx, early_return,
                rule_collection=rule_collection, intent_match=intent_match,
                matched_roles=matched_roles, role_ids=role_ids,
                concern_packs=concern_packs, concern_enhancements=concern_enhancements,
                step1_time=step1_time, step2_time=time.time(),
            )

        step2_time = time.time()

        # Step 7: Prepare execution (warmup, prompts, plan, spawn, anchor, retrospective load)
        plan, structured_goal, prep_timing = self._prepare_execution(
            task_description, matched_roles, lang, intent_match, rule_collection, concern_enhancements
        )

        return self._PreDispatchResult(
            task_description=task_description,
            lang=lang,
            rule_collection=rule_collection,
            intent_match=intent_match,
            matched_roles=matched_roles,
            role_ids=role_ids,
            concern_packs=concern_packs,
            concern_enhancements=concern_enhancements,
            plan=plan,
            structured_goal=structured_goal,
            prep_timing=prep_timing,
            step1_time=step1_time,
            step2_time=step2_time,
            tenant_ctx=tenant_ctx,
            early_return=None,
        )

    def _post_dispatch_steps(
        self,
        pre_result,
        exec_result,
        worker_results: List[Dict[str, Any]],
        exec_errors: List[str],
        exec_timing: Dict[str, float],
        start_time: float,
        phase: str,
        **kwargs: Any,
    ) -> DispatchResult:
        """Steps 9-18: post-processing, consensus, permissions, memory, assembly."""
        task_description = pre_result.task_description
        lang = pre_result.lang
        matched_roles = pre_result.matched_roles
        role_ids = pre_result.role_ids
        concern_packs = pre_result.concern_packs
        intent_match = pre_result.intent_match
        structured_goal = pre_result.structured_goal
        plan = pre_result.plan
        step1_time = pre_result.step1_time
        step2_time = pre_result.step2_time
        step3_time = pre_result.prep_timing.get("step3_time", step2_time)
        step4_time = pre_result.prep_timing.get("step4_time", step3_time)
        step5_time = pre_result.prep_timing.get("step5_time", step4_time)

        errors: List[str] = list(exec_errors)

        step6_time = exec_timing.get("step6_time", step5_time)
        step7_time = exec_timing.get("step7_time", step6_time)

        # Step 9: Post-execution processing (collect, slice, anchor check)
        scratchpad_summary, anchor_result, collection, post_errors, post_timing = self._post_execution_processing(
            worker_results, structured_goal
        )
        errors.extend(post_errors)
        step8_time = post_timing["step8_time"]

        # Step 10: Resolve consensus
        mode = kwargs.get('mode', 'auto')
        consensus_records, compression_info = self._resolve_consensus(collection, mode)
        step9_time = time.time()

        # Step 11: Check permissions
        permission_checks = self._check_permissions(task_description, worker_results, consensus_records, **kwargs)
        step10_time = time.time()

        # Step 12: Process memory pipeline
        memory_stats, mem_errors = self._process_memory_pipeline(
            task_description, worker_results, lang, scratchpad_summary, role_ids
        )
        errors.extend(mem_errors)
        step11_time = time.time()

        # Step 13: Learn skills
        skill_proposals, skill_errors = self._learn_skills(task_description, worker_results, matched_roles, exec_result)
        errors.extend(skill_errors)
        step12_time = time.time()

        # Step 14: Run five-axis consensus
        five_axis_result = self._run_five_axis_consensus(task_description, worker_results, mode, exec_result)

        # Step 15: Run retrospective
        total_duration = time.time() - start_time
        retrospective_report = self._run_retrospective(
            task_description, worker_results, structured_goal, exec_result, total_duration
        )

        # Step 16: Assemble result
        step_timings = self._build_step_timings(
            step1_time, step2_time, step3_time, step4_time, step5_time,
            step6_time, step7_time, step8_time, step9_time, step10_time,
            step11_time, step12_time,
        )
        result = self._assemble_result(
            task_description=task_description,
            role_ids=role_ids,
            exec_result=exec_result,
            scratchpad_summary=scratchpad_summary,
            consensus_records=consensus_records,
            compression_info=compression_info,
            memory_stats=memory_stats,
            permission_checks=permission_checks,
            skill_proposals=skill_proposals,
            anchor_result=anchor_result,
            retrospective_report=retrospective_report,
            intent_match=intent_match,
            five_axis_result=five_axis_result,
            errors=errors,
            lang=lang,
            concern_packs=concern_packs,
            total_duration=total_duration,
            plan=plan,
            step_timings=step_timings,
            worker_results=worker_results,
        )

        # Lifecycle phase trace
        lifecycle_trace = self._build_lifecycle_trace(step_timings)
        result.details["lifecycle_trace"] = lifecycle_trace

        # Audit: dispatch complete
        if self.audit_logger:
            try:
                self.audit_logger.log(
                    user_id=kwargs.get('user_id', 'system'),
                    action="task:dispatch_complete",
                    resource_type="Task",
                    resource_id="unknown",
                    result="success" if result.success else "failure"
                )
            except (OSError, AttributeError, KeyError) as e:
                logger.debug(f"Audit logging failed: {e}")

        # Step 17: Post-dispatch hooks
        self._post_dispatch_hooks(result, task_description, role_ids, total_duration)

        # Step 18: Feedback loop
        roles = kwargs.get('roles')
        dry_run = kwargs.get('dry_run', False)
        result = self._run_feedback_loop(task_description, result, lang, roles, mode, dry_run, kwargs)

        # Prometheus: record dispatch end (duration + tasks_in_progress)
        self._safe_metrics(lambda m: (
            m.dispatch_histogram.labels(mode=mode).observe(total_duration),
            m.dispatch_counter.labels(mode=mode, role_count=str(len(role_ids))).inc(),
            m.tasks_in_progress_gauge.labels(phase=phase).dec(),
        ))

        # Multi-tenant context cleanup
        self._cleanup_tenant_context(pre_result.tenant_ctx)

        return result

    def _setup_tenant_context(self, kwargs: Dict[str, Any], start_time: float) -> Any:
        """Set up multi-tenant context. Returns context manager or DispatchResult on quota error."""
        if not self.enable_multi_tenant or not self.tenant_manager:
            return None
        tenant_id = kwargs.get('tenant_id', 'default')
        user_id = kwargs.get('user_id', 'default')
        if not tenant_id:
            return None
        try:
            tenant_ctx = self.tenant_manager.context(tenant_id, user_id)
            tenant_ctx.__enter__()
            if not self.tenant_manager.check_quota("tasks"):
                return DispatchResult(
                    success=False, task_description="",
                    error="Quota exceeded", matched_roles=[],
                    summary="Quota exceeded for tenant",
                    errors=["Quota exceeded"],
                    duration_seconds=time.time() - start_time,
                )
            return tenant_ctx
        except (AttributeError, KeyError, RuntimeError, OSError) as e:
            logger.warning(f"Multi-tenant setup failed: {e}")
            return None

    def _check_rbac_access(self, kwargs: Dict[str, Any], task: str, lang: str, start_time: float) -> Optional[DispatchResult]:
        """Check RBAC access. Returns DispatchResult if denied, None if allowed."""
        if not self.enable_rbac or not self.rbac_engine:
            return None
        try:
            user_id = kwargs.get('user_id', 'default')
            self.rbac_engine.enforce(user_id, Permission.TASK_EXECUTE)
            return None
        except PermissionDeniedError as e:
            return DispatchResult(
                success=False, task_description=task,
                error=f"Permission denied: {e}", matched_roles=[],
                summary=f"Permission denied: {e}",
                errors=[f"Permission denied: {e}"],
                duration_seconds=time.time() - start_time, lang=lang,
            )
        except (AttributeError, RuntimeError, KeyError) as e:
            logger.warning(f"RBAC check failed: {e}")
            return None

    def _cleanup_tenant_context(self, tenant_ctx: Any) -> None:
        """Clean up tenant context if active."""
        if tenant_ctx:
            try:
                tenant_ctx.__exit__(None, None, None)
            except (AttributeError, RuntimeError, OSError) as e:
                logger.debug(f"Tenant context cleanup failed: {e}")

    def _safe_metrics(self, fn) -> None:
        """Safely execute Prometheus metrics callback."""
        try:
            fn(get_metrics())
        except Exception as _me:
            logger.debug("Metrics recording failed: %s", _me)

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

        self._cleanup_tenant_context(tenant_ctx)
        self._safe_metrics(lambda m: (
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

    def _make_early_pre_result(
        self,
        task_description: str,
        lang: str,
        tenant_ctx: Any,
        early_return: DispatchResult,
        rule_collection: Any = None,
        intent_match: Any = None,
        matched_roles: Optional[List[Dict[str, Any]]] = None,
        role_ids: Optional[List[str]] = None,
        concern_packs: Any = None,
        concern_enhancements: Optional[Dict[str, Any]] = None,
        step1_time: float = 0.0,
        step2_time: float = 0.0,
    ):
        """Create a _PreDispatchResult with early_return set, filling defaults."""
        return self._PreDispatchResult(
            task_description=task_description,
            lang=lang,
            rule_collection=rule_collection,
            intent_match=intent_match,
            matched_roles=matched_roles or [],
            role_ids=role_ids or [],
            concern_packs=concern_packs,
            concern_enhancements=concern_enhancements or {},
            plan=None,
            structured_goal=None,
            prep_timing={},
            step1_time=step1_time,
            step2_time=step2_time,
            tenant_ctx=tenant_ctx,
            early_return=early_return,
        )

    def _collect_worker_results(self, exec_result: Any) -> Tuple[List[Dict[str, Any]], float, float]:
        """Collect worker results from execution result into standardized dicts."""
        step6_time = time.time()
        worker_results: List[Dict[str, Any]] = []
        for r in exec_result.results:
            role_id = r.worker_id.split("-")[0] if "-" in r.worker_id else r.worker_id
            from .models import ROLE_REGISTRY

            rdef = ROLE_REGISTRY.get(role_id)
            role_name = rdef.name if rdef else role_id
            worker_results.append(
                {
                    "worker_id": r.worker_id,
                    "role_id": role_id,
                    "role_name": role_name,
                    "task_id": r.task_id,
                    "success": r.success,
                    "output": (r.output.get("finding_summary", "") if isinstance(r.output, dict) else str(r.output))
                    if r.output
                    else None,
                    "error": r.error,
                }
            )
        step7_time = time.time()
        return worker_results, step6_time, step7_time

    def _get_current_tenant_id(self) -> str:
        """Get current tenant_id for data isolation, defaults to 'default'."""
        if self.enable_multi_tenant and self.tenant_manager:
            current_tenant = self.tenant_manager.get_current_tenant()
            if current_tenant:
                return current_tenant.tenant_id
        return "default"

    def _resolve_language(self, lang: str) -> str:
        """Resolve language from 'auto' to a specific language code."""
        if lang != "auto":
            return lang
        import locale

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

    def _validate_input(
        self, task: str, roles: Optional[List[str]], lang: str
    ) -> Tuple[str, Optional[DispatchResult]]:
        """Validate task and roles input. Returns (sanitized_task, early_return)."""
        validator = self._validator
        task_result = validator.validate_task(task)
        if not task_result.valid:
            friendly = translate_validation_result(task_result.reason or "")
            return task, DispatchResult(
                success=False,
                task_description=task,
                matched_roles=[],
                worker_results=[],
                summary=friendly.message,
                errors=[friendly.format()],
                lang=lang,
            )
        task = task_result.sanitized_input or task

        try:
            if not hasattr(self, "_std_template_cache"):
                self._std_template_cache: Dict[str, Any] = {}
        except Exception:  # Broad catch: defensive attribute check
            self._std_template_cache = {}

        if roles:
            roles_result = validator.validate_roles(roles)
            if not roles_result.valid:
                friendly = make_user_friendly_error("role_not_found")
                return task, DispatchResult(
                    success=False,
                    task_description=task,
                    matched_roles=[],
                    worker_results=[],
                    summary=friendly.message,
                    errors=[friendly.format()],
                    lang=lang,
                )

        warnings = validator.check_suspicious_patterns(task)
        if warnings:
            logger.warning("Suspicious patterns in task: %s", ", ".join(warnings))

        injection_warnings = validator.check_prompt_injection(task)
        if injection_warnings:
            logger.warning("Prompt injection patterns detected: %s", ", ".join(injection_warnings))

        return task, None

    def _collect_rules(
        self, task: str, lang: str
    ) -> Tuple[str, Any, Optional[DispatchResult]]:
        """Collect rules via RuleCollector and inject CI context. Returns (task, rules, early_return)."""
        rule_collection = None
        try:
            from scripts.collaboration.rule_collector import RuleCollector

            if not hasattr(self, "_rule_collector"):
                self._rule_collector = RuleCollector()
            rule_collection = self._rule_collector.process(task, lang)
            if rule_collection.rule_detected and not rule_collection.remaining_task:
                return task, rule_collection, DispatchResult(
                    success=True,
                    task_description=task,
                    matched_roles=[],
                    worker_results=[],
                    summary=rule_collection.message,
                    errors=[],
                    lang=lang,
                )
            if rule_collection.rule_detected:
                task = rule_collection.remaining_task
        except (ImportError, AttributeError, ValueError, KeyError) as e:
            logger.debug("RuleCollector not available: %s", e)

        if self.ci_feedback:
            self._inject_ci_context(task)

        return task, rule_collection, None

    def _inject_ci_context(self, task: str) -> str:
        """Inject CI feedback context into task description if failures found."""
        try:
            import glob as glob_mod

            ci_files = glob_mod.glob(os.path.join(self.persist_dir, "**/pytest*.txt"), recursive=True)
            ci_files += glob_mod.glob(os.path.join(self.persist_dir, "**/junit*.xml"), recursive=True)
            if ci_files:
                ci_results = []
                for cf in ci_files[:3]:
                    with open(cf, encoding="utf-8", errors="ignore") as f:
                        r = self.ci_feedback.parse_ci_output(f.read(), "pytest")
                        if r:
                            ci_results.append(r)
                if ci_results:
                    ctx = self.ci_feedback.generate_context(ci_results)
                    if ctx and ctx.overall_status == "has_failures":
                        if self.usage_tracker:
                            self.usage_tracker.tick("ci_context_injected")
                        return f"{task}\n\n[CI Context] {ctx.summary}"
        except (OSError, ValueError, AttributeError) as e:
            logger.warning(f"CI context injection failed: {e}")
        return task

    def _detect_intent(self, task: str, lang: str) -> Any:
        """Detect intent via IntentWorkflowMapper. Returns intent match or None."""
        intent_match = None
        try:
            intent_match = self.intent_mapper.detect_intent(task, lang=lang)
            if intent_match and self.usage_tracker:
                self.usage_tracker.tick("intent_detected")
        except (ValueError, AttributeError, RuntimeError, ImportError) as intent_err:
            logger.debug("Intent detection failed: %s", intent_err)

        self.context_manager.clear_task_context()
        self.context_manager.set_task("task_description", task)
        self.context_manager.set_task("lang", lang)
        if intent_match:
            self.context_manager.set_task("intent_type", intent_match.intent_type)
            self.context_manager.set_task("workflow_chain", [s for s in intent_match.workflow_chain])

        return intent_match

    def _match_roles(self, task: str, roles: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Match roles via RoleMatcher, AISemanticMatcher, and enhanced adaptive/similar recommendations."""
        matched_roles = self.analyze_task(task)

        # Enhanced role matching: merge adaptive and similar-task recommendations
        try:
            enhanced_roles = self.role_matcher.analyze_task_enhanced(task)
            if enhanced_roles:
                existing_ids = {r["role_id"] for r in matched_roles}
                for er in enhanced_roles:
                    if er["role_id"] not in existing_ids:
                        matched_roles.append(er)
                        existing_ids.add(er["role_id"])
        except (ValueError, AttributeError, RuntimeError, OSError) as enhanced_err:
            logger.debug("Enhanced role matching failed, using keyword-only results: %s", enhanced_err)

        if self.semantic_matcher and self.llm_backend:
            try:
                semantic_results = self.semantic_matcher.match(task)
                if semantic_results:
                    existing_ids = {r["role_id"] for r in matched_roles}
                    for sr in semantic_results:
                        if sr.role_id not in existing_ids and sr.confidence > 0.5:
                            matched_roles.append(
                                {
                                    "role_id": sr.role_id,
                                    "name": sr.role_name,
                                    "reason": sr.reasoning,
                                    "confidence": str(sr.confidence),
                                }
                            )
                            existing_ids.add(sr.role_id)
                    if self.usage_tracker:
                        self.usage_tracker.tick("semantic_matcher")
            except (ValueError, AttributeError, RuntimeError, ConnectionError) as sem_err:
                logger.debug("Semantic matching failed: %s", sem_err)

        if roles:
            matched_roles = self.role_matcher.resolve_roles(roles, matched_roles)

        return matched_roles

    def _validate_roles_and_security(
        self,
        task: str,
        matched_roles: List[Dict[str, Any]],
        lang: str,
        dry_run: bool,
        start_time: float,
    ) -> Tuple[List[str], Any, Dict[str, Any], Optional[DispatchResult]]:
        """Validate roles and run security scans. Returns (role_ids, concern_packs, enhancements, early_return)."""
        role_ids = [r["role_id"] for r in matched_roles]

        concern_packs = self._concern_loader.match_packs(task)
        concern_enhancements = self._concern_loader.get_all_role_enhancements(concern_packs)

        if concern_packs:
            pack_names = ", ".join(p.name for p in concern_packs)
            logger.info("Concern packs activated: %s", pack_names)

        if dry_run:
            return role_ids, concern_packs, concern_enhancements, DispatchResult(
                success=True,
                task_description=task,
                matched_roles=role_ids,
                summary=f"[DRY RUN] 将调度角色: {', '.join(role_ids)}",
                duration_seconds=time.time() - start_time,
                lang=lang,
            )

        return role_ids, concern_packs, concern_enhancements, None

    def _prepare_execution(
        self,
        task: str,
        matched_roles: List[Dict[str, Any]],
        lang: str,
        intent_match: Any,
        rule_collection: Any,
        concern_enhancements: Dict[str, Any],
    ) -> Tuple[Any, Any, Dict[str, float]]:
        """Prepare execution: warmup, prompt assembly, planning, spawn. Returns (plan, goal, timing)."""
        role_ids = [r["role_id"] for r in matched_roles]

        if self.warmup_manager:
            for rid in role_ids:
                cache_key = f"role-prompt-{rid}"
                if not self.warmup_manager.is_ready(cache_key):
                    template = ROLE_TEMPLATES.get(rid, {})
                    self.warmup_manager.set_cache(
                        cache_key,
                        template.get("prompt", ""),
                        ttl=1800,
                    )

        step3_time = time.time()

        available_roles: List[Dict[str, Any]] = []
        for r in matched_roles:
            template = ROLE_TEMPLATES.get(r["role_id"], {})
            role_prompt: str = str(template.get("prompt", ""))

            role_id = r["role_id"]
            if role_id in concern_enhancements:
                enhancement = concern_enhancements[role_id]
                if enhancement:
                    enhancement_str: str = str(enhancement)
                    role_prompt = role_prompt + "\n\n" + enhancement_str if role_prompt else enhancement_str

            available_roles.append(
                {
                    "role_id": role_id,
                    "role_prompt": role_prompt,
                    "confidence": r.get("confidence", 0.5),
                }
            )

        plan = self.coordinator.plan_task(
            task_description=task,
            available_roles=available_roles,
        )

        step4_time = time.time()

        self.coordinator.spawn_workers(plan)

        step5_time = time.time()

        # V3.6.8: Parse structured goal for anchor checking
        structured_goal = None
        if self.anchor_checker:
            structured_goal = self.anchor_checker.parse_goal(task)
            if self.usage_tracker:
                self.usage_tracker.tick("anchor_check")

        # V3.6.8: Load historical retrospectives into Scratchpad
        self._load_historical_retrospectives(task)

        return plan, structured_goal, {
            "step3_time": step3_time,
            "step4_time": step4_time,
            "step5_time": step5_time,
        }

    def _load_historical_retrospectives(self, task: str) -> None:
        """Load historical retrospectives into Scratchpad."""
        if not self.retrospective_engine or not self.enable_memory:
            return
        try:
            historical = self.retrospective_engine.load_historical(task, limit=3)
            if historical:
                retro_lines = ["[Historical Retrospective Context]"]
                for idx, h in enumerate(historical, 1):
                    if isinstance(h, dict):
                        retro_lines.append(f"  {idx}. {h.get('summary', str(h)[:100])}")
                    else:
                        retro_lines.append(f"  {idx}. {str(h)[:100]}")
                self.scratchpad.write(
                    ScratchpadEntry(
                        worker_id="system",
                        entry_type=EntryType.FINDING,
                        content="\n".join(retro_lines),
                        confidence=0.85,
                        tags=["retrospective", "auto-loaded"],
                    )
                )
        except (OSError, ValueError, AttributeError, KeyError) as retro_load_err:
            logger.debug("Failed to load historical retrospectives: %s", retro_load_err)

    def _execute_workers(
        self, plan: Any, task_description: str
    ) -> Tuple[Any, List[Dict[str, Any]], List[str], Dict[str, float]]:
        """Execute workers via Coordinator. Returns (exec_result, worker_results, errors, timing)."""
        exec_result = self.coordinator.execute_plan(plan)
        worker_results, step6_time, step7_time = self._collect_worker_results(exec_result)
        exec_errors = list(exec_result.errors) if exec_result.errors else []
        return exec_result, worker_results, exec_errors, {
            "step6_time": step6_time,
            "step7_time": step7_time,
        }

    def _post_execution_processing(
        self, worker_results: List[Dict[str, Any]], structured_goal: Any
    ) -> Tuple[str, Any, Any, List[str], Dict[str, float]]:
        """Post-execution: collect, slice, anchor check. Returns (summary, anchor, collection, errors, timing)."""
        errors: List[str] = []
        collection = self.coordinator.collect_results()
        scratchpad_summary = collection.get("scratchpad", "")

        self._slice_outputs(worker_results, errors)
        anchor_result = self._check_anchor_drift(worker_results, structured_goal, scratchpad_summary)

        step8_time = time.time()

        return scratchpad_summary, anchor_result, collection, errors, {
            "step8_time": step8_time,
        }

    def _slice_outputs(self, worker_results: List[Dict[str, Any]], errors: List[str]) -> None:
        """Slice oversized worker outputs."""
        if self.output_slicer and worker_results:
            try:
                for wr in worker_results:
                    if wr.get("output") and len(wr["output"]) > self.output_slicer.max_slice_lines * 50:
                        slices = self.output_slicer.slice_output(wr["output"], role_id=wr.get("role_id", "unknown"))
                        wr["_slices"] = len(slices)
                        wr["_sliced"] = True
                        if self.usage_tracker:
                            self.usage_tracker.tick("output_sliced")
            except (ValueError, AttributeError, TypeError) as e:
                logger.warning(f"OutputSlicer failed: {e}")

    def _check_anchor_drift(self, worker_results: List[Dict[str, Any]], structured_goal: Any, scratchpad_summary: str) -> Any:
        """Check for anchor drift after execution."""
        if not self.anchor_checker or not structured_goal:
            return None
        try:
            combined_output = scratchpad_summary or ""
            for wr in worker_results:
                if wr.get("output"):
                    combined_output += "\n" + wr["output"]
            from .models import AnchorTrigger

            anchor_result = self.anchor_checker.check(
                goal=structured_goal,
                current_output=combined_output,
                trigger=AnchorTrigger.STEP_COMPLETE,
            )
            if not anchor_result.aligned:
                if self.usage_tracker:
                    self.usage_tracker.tick("anchor_drift_detected")
                self.scratchpad.write(
                    ScratchpadEntry(
                        worker_id="system",
                        entry_type=EntryType.WARNING,
                        content=f"[Anchor Drift] {anchor_result.recommendation}",
                        confidence=0.9,
                        tags=["anchor-drift", "v3.6.8"],
                    )
                )
            return anchor_result
        except (ValueError, AttributeError, ImportError, RuntimeError) as anchor_err:
            logger.warning("Anchor check failed: %s", anchor_err)
            return None

    def _resolve_consensus(
        self, collection: Any, mode: str
    ) -> Tuple[List[Dict[str, Any]], Any]:
        """Resolve consensus and get compression info. Returns (consensus_records, compression_info)."""
        consensus_records = []
        conflicts_count = collection.get("conflicts_count", 0)
        if conflicts_count > 0 or mode == "consensus":
            resolutions = self.coordinator.resolve_conflicts()
            for rec in resolutions:
                self._safe_metrics(lambda m: m.record_consensus_round(rec.outcome.value))
                consensus_records.append(
                    {
                        "topic": rec.topic,
                        "outcome": rec.outcome.value,
                        "final_decision": rec.final_decision,
                        "votes_for": rec.votes_for,
                        "votes_against": rec.votes_against,
                        "votes_abstain": rec.votes_abstain,
                    }
                )

        compression_info = None
        if self.enable_compression and self.compressor:
            stats = self.coordinator.get_compression_stats()
            if stats:
                compression_info = stats

        return consensus_records, compression_info

    def _check_permissions(
        self, task: str, worker_results: List[Dict[str, Any]], consensus_records: List[Dict[str, Any]], **kwargs: Any
    ) -> List[Dict[str, Any]]:
        """Check permissions via PermissionGuard and RBAC.

        Returns:
            List of permission check results.
        """
        permission_checks = []
        if self.enable_permission and self.permission_guard:
            permission_checks = self._check_permission_guard(permission_checks)

        # RBAC fine-grained check
        if self.enable_rbac and self.rbac_engine:
            permission_checks = self._check_rbac_permission(permission_checks, **kwargs)

        return permission_checks

    def _check_permission_guard(self, permission_checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run PermissionGuard checks on test actions."""
        test_actions = [
            ProposedAction(
                action_type=ActionType.FILE_CREATE, target="/tmp/test_output.md", description="生成输出文件"
            ),
        ]
        for action in test_actions:
            classified = None
            try:
                classified = self.operation_classifier.classify(
                    operation_id=action.action_type.value, target=action.target,
                )
            except (ValueError, AttributeError, KeyError):
                pass
            decision = self.permission_guard.check(action)
            perm_entry = {
                "action": f"{action.action_type.value}:{action.target}",
                "allowed": decision.outcome.value == "ALLOWED",
                "decision": decision.outcome.value,
                "reason": decision.reason or "",
            }
            gate_result = "pass" if decision.outcome.value == "ALLOWED" else "fail"
            self._safe_metrics(lambda m: m.record_gate_check("permission", gate_result))
            if classified:
                perm_entry["operation_category"] = classified.category.value
            permission_checks.append(perm_entry)
        return permission_checks

    def _check_rbac_permission(self, permission_checks: List[Dict[str, Any]], **kwargs: Any) -> List[Dict[str, Any]]:
        """Run RBAC fine-grained permission check."""
        try:
            user_id = kwargs.get('user_id', 'default')
            self.rbac_engine.enforce(user_id, Permission.TASK_EXECUTE)
            permission_checks.append({"action": "rbac:execute", "allowed": True})
        except PermissionDeniedError as e:
            permission_checks.append({"action": "rbac:execute", "allowed": False, "reason": str(e)})
        except (AttributeError, RuntimeError, KeyError) as e:
            logger.debug(f"RBAC permission check failed: {e}")
        return permission_checks

    def _process_memory_pipeline(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        lang: str,
        scratchpad_summary: str,
        role_ids: List[str],
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """Process memory pipeline: capture + MCE classify + AI news inject."""
        errors: List[str] = []

        memory_stats = self._capture_memory(task, scratchpad_summary, role_ids, errors)
        memory_stats = self._classify_mce(scratchpad_summary, task, memory_stats, errors)
        self._inject_ai_news(task, errors)

        return memory_stats, errors

    def _capture_memory(
        self,
        task: str,
        scratchpad_summary: str,
        role_ids: List[str],
        errors: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Capture episodic memory via MemoryBridge."""
        memory_stats: Optional[Dict[str, Any]] = None

        if self.enable_memory and self.memory_bridge:
            try:
                mem_stats: Any = self.memory_bridge.get_statistics()
                tenant_id = self._get_current_tenant_id()
                memory_stats = {
                    "total_memories": mem_stats.total_memories,
                    "by_type_counts": mem_stats.by_type_counts,
                    "index_built": mem_stats.index_built,
                    "total_captures": mem_stats.total_captures,
                    "tenant_id": tenant_id,
                }

                # Tenant-isolated storage key prefix
                key_prefix = f"[{tenant_id}]" if tenant_id != "default" else ""
                ep = EpisodicMemory(
                    id=f"epi-{tenant_id}-{uuid.uuid4().hex[:8]}" if key_prefix else f"epi-{uuid.uuid4().hex[:8]}",
                    task_description=f"{key_prefix}{task}" if key_prefix else task,
                    finding=scratchpad_summary[:500],
                )
                self.memory_bridge.capture_execution(
                    execution_record={"task": f"{key_prefix}{task}" if key_prefix else task, "roles": role_ids, "tenant_id": tenant_id},
                    scratchpad_entries=[],
                )
            except (ConnectionError, TimeoutError, OSError) as mem_err:
                logger.warning("MemoryBridge connection error: %s", mem_err)
                errors.append(f"MemoryBridge connection error: {type(mem_err).__name__}: {mem_err}")
            except (ValueError, KeyError, AttributeError) as mem_val_err:
                logger.debug("MemoryBridge data error: %s", mem_val_err)
                errors.append(f"MemoryBridge data error: {mem_val_err}")
            except Exception as mem_err:  # Broad catch: unpredictable memory system
                logger.warning("Unexpected MemoryBridge error: %s - %s", type(mem_err).__name__, mem_err)
                errors.append(f"MemoryBridge unexpected error: {type(mem_err).__name__}")

        return memory_stats

    def _classify_mce(
        self,
        scratchpad_summary: str,
        task: str,
        memory_stats: Optional[Dict[str, Any]],
        errors: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Classify memory via MCE adapter. Returns updated memory_stats."""
        # [MCE 集成点 v3.2] Dispatcher → MemoryBridge 调用链
        if self._mce_adapter and self._mce_adapter.is_available and scratchpad_summary:
            try:
                mce_classify_result = self._mce_adapter.classify(
                    scratchpad_summary, context={"task": task}, timeout_ms=500
                )
                if mce_classify_result:
                    memory_stats = memory_stats or {}
                    memory_stats["mce_classification"] = {
                        "type": mce_classify_result.memory_type,
                        "confidence": round(mce_classify_result.confidence, 3),
                        "tier": mce_classify_result.tier,
                    }
            except (ValueError, TypeError, AttributeError) as mce_type_err:
                logger.debug("MCE classification data error: %s", mce_type_err)
                errors.append(f"MCE classify data error: {mce_type_err}")
            except (TimeoutError, ConnectionError) as mce_timeout:
                logger.warning("MCE classify timeout/connection error: %s", mce_timeout)
                errors.append(f"MCE classify timeout error: {mce_timeout}")
            except Exception as mce_err:  # Broad catch: unpredictable MCE system
                logger.warning("Unexpected MCE classify error: %s - %s", type(mce_err).__name__, mce_err)
                errors.append(f"MCE classify unexpected error: {type(mce_err).__name__}")

        return memory_stats

    def _inject_ai_news(
        self,
        task: str,
        errors: List[str],
    ) -> None:
        """Inject AI news into scratchpad when task matches AI-related keywords."""
        if self.memory_bridge and self.enable_memory:
            try:
                ai_news_keywords = [
                    "ai news",
                    "industry trend",
                    "latest progress",
                    "trend",
                    "ai coding",
                    "embodied intelligence",
                    "large model",
                    "llm",
                    "cursor",
                    "claude",
                    "gpt",
                    "deepseek",
                    "anthropic",
                    "\u65b0\u95fb",
                    "\u884c\u4e1a\u52a8\u6001",
                    "\u6700\u65b0\u8fdb\u5c55",
                ]
                task_lower = task.lower()
                should_inject = any(kw in task_lower for kw in ai_news_keywords)
                if should_inject:
                    news_items = self.memory_bridge.get_workbuddy_ai_news(days=3)
                    if news_items:
                        news_summary = "\n".join(f"- [{n.title}] {n.content[:200]}..." for n in news_items[:3])
                        self.scratchpad.write(
                            ScratchpadEntry(
                                worker_id="system",
                                entry_type=EntryType.FINDING,
                                content=f"[WorkBuddy AI News Feed]\n{news_summary}",
                                confidence=0.95,
                                tags=["ai-news", "auto-injected"],
                            )
                        )
            except (AttributeError, OSError, KeyError, ValueError) as inject_err:
                errors.append(f"AI news inject error: {inject_err}")

    def _learn_skills(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        matched_roles: List[Dict[str, Any]],
        exec_result: Any,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Learn skills via Skillifier. Returns (skill_proposals, errors)."""
        errors: List[str] = []
        skill_proposals = []
        patterns = None

        if self.enable_skillify and self.skillifier and exec_result.success:
            try:
                patterns = self.skillifier.analyze_history()
                if patterns:
                    skill_proposals = self._propose_skills_from_patterns(patterns)
            except (ValueError, AttributeError, RuntimeError, ImportError) as skill_err:
                errors.append(f"Skillifier error: {skill_err}")

        if self.prompt_variant_gen and patterns:
            try:
                for pattern in patterns:
                    if pattern.confidence > 0.5:
                        variants = self.prompt_variant_gen.generate_from_pattern(pattern)
                        if variants:
                            if self.usage_tracker:
                                self.usage_tracker.tick("prompt_variant_generated")
            except (ValueError, AttributeError, RuntimeError) as e:
                logger.warning(f"PromptVariantGenerator failed: {e}")

        return skill_proposals, errors

    def _propose_skills_from_patterns(self, patterns: list) -> List[Dict[str, Any]]:
        """Generate skill proposals from analyzed patterns and register them."""
        proposals = []
        for pattern in patterns:
            if pattern.confidence <= 0.3:
                continue
            pattern_title = getattr(pattern, 'title', None) or "新协作模式"
            category = pattern.category.value if hasattr(pattern, "category") and pattern.category else "general"
            proposals.append({"title": pattern_title, "confidence": pattern.confidence, "category": category})
            try:
                self.skill_registry.propose_from_result(
                    name=pattern_title, description=pattern_title,
                    category=category, confidence=pattern.confidence,
                )
            except (ValueError, AttributeError, OSError, KeyError) as e:
                logger.warning(f"SkillRegistry proposal failed: {e}")
        return proposals

    def _run_five_axis_consensus(
        self, task: str, worker_results: List[Dict[str, Any]], mode: str, exec_result: Any
    ) -> Optional[Dict[str, Any]]:
        """Run five-axis consensus review (consensus mode only)."""
        if mode != "consensus" or not exec_result.success:
            return None

        try:
            from .five_axis_consensus import FiveAxisConsensusEngine, ReviewAxis

            fa_engine = FiveAxisConsensusEngine()
            review = fa_engine.create_review("system", "dispatcher")
            for wr in worker_results:
                output_text = wr.get("output") or wr.get("error") or ""
                if output_text:
                    fa_engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.READABILITY, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.ARCHITECTURE, 0.8, 0.7)
                    fa_engine.add_axis_vote(review, ReviewAxis.SECURITY, 0.7, 0.6)
                    fa_engine.add_axis_vote(review, ReviewAxis.PERFORMANCE, 0.7, 0.6)
                    break
            fa_result = fa_engine.compute_consensus([review])
            five_axis_result = {
                "verdict": fa_result.verdict,
                "overall_consensus": fa_result.overall_consensus,
                "axis_consensus": fa_result.axis_consensus,
                "action_items": fa_result.action_items,
            }
            if self.usage_tracker:
                self.usage_tracker.tick("five_axis_consensus")
            return five_axis_result
        except (ImportError, AttributeError, ValueError, RuntimeError) as fa_err:
            logger.debug("Five-axis consensus failed: %s", fa_err)
            return None

    def _run_retrospective(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        structured_goal: Any,
        exec_result: Any,
        total_duration: float,
    ) -> Any:
        """Run RetrospectiveEngine analysis. Returns report or None."""
        if not self.retrospective_engine or not structured_goal or not exec_result.success:
            return None

        try:
            if self.usage_tracker:
                self.usage_tracker.tick("retrospective")
            anchor_history = self.anchor_checker.check_history if self.anchor_checker else []
            retrospective_report = self.retrospective_engine.run(
                goal=structured_goal,
                anchor_history=anchor_history,
                worker_outputs={
                    wr["role_id"]: wr.get("output", "") for wr in worker_results if wr.get("output")
                },
                task_duration_seconds=total_duration,
            )
            return retrospective_report
        except (ValueError, AttributeError, RuntimeError, ImportError) as retro_err:
            logger.warning("Retrospective failed: %s", retro_err)
            return None

    def _assemble_result(
        self,
        task_description: str,
        role_ids: List[str],
        exec_result: Any,
        scratchpad_summary: str,
        consensus_records: List[Dict[str, Any]],
        compression_info: Any,
        memory_stats: Optional[Dict[str, Any]],
        permission_checks: List[Dict[str, Any]],
        skill_proposals: List[Dict[str, Any]],
        anchor_result: Any,
        retrospective_report: Any,
        intent_match: Any,
        five_axis_result: Optional[Dict[str, Any]],
        errors: List[str],
        lang: str,
        concern_packs: Any,
        total_duration: float,
        plan: Any,
        step_timings: Dict[str, float],
        worker_results: List[Dict[str, Any]],
    ) -> DispatchResult:
        """Assemble the final DispatchResult from all step results."""
        report = self.coordinator.generate_report()

        # Data masking
        scratchpad_summary = self._apply_data_masking(scratchpad_summary)

        return DispatchResult(
            success=exec_result.success and len(errors) == 0,
            task_description=task_description,
            matched_roles=role_ids,
            summary=self._build_summary(task_description, role_ids, exec_result, scratchpad_summary),
            details={
                "plan_total_tasks": plan.total_tasks,
                "completed_tasks": exec_result.completed_tasks,
                "failed_tasks": exec_result.failed_tasks,
                "report": report,
                "timing": step_timings,
                "tenant_id": self._get_current_tenant_id() if self.enable_multi_tenant else None,
            },
            scratchpad_summary=scratchpad_summary,
            consensus_records=consensus_records,
            compression_info=compression_info,
            memory_stats=memory_stats,
            permission_checks=permission_checks,
            skill_proposals=skill_proposals,
            duration_seconds=total_duration,
            worker_results=worker_results,
            errors=errors,
            lang=lang,
            concern_packs=self._concern_loader.get_pack_info(concern_packs) if concern_packs else [],
            anchor_result=self._build_anchor_dict(anchor_result),
            retrospective_report=retrospective_report.to_dict() if retrospective_report else None,
            intent_match=self._build_intent_dict(intent_match),
            five_axis_result=five_axis_result,
        )

    def _apply_data_masking(self, text: str) -> str:
        """Apply data masking to text if masker is available."""
        if not self.data_masker or not text:
            return text
        try:
            masked = self.data_masker.mask({"content": text})
            return masked.get("content", text)
        except (ValueError, AttributeError, TypeError, KeyError) as e:
            logger.debug(f"Data masking failed: {e}")
            return text

    def _build_anchor_dict(self, anchor_result: Any) -> Optional[Dict[str, Any]]:
        """Build anchor result dict for DispatchResult."""
        if not anchor_result:
            return None
        return {
            "aligned": anchor_result.aligned,
            "coverage": anchor_result.coverage,
            "drift_score": anchor_result.drift_score,
            "severity": anchor_result.severity.value,
            "recommendation": anchor_result.recommendation,
        }

    def _build_intent_dict(self, intent_match: Any) -> Optional[Dict[str, Any]]:
        """Build intent match dict for DispatchResult."""
        if not intent_match:
            return None
        return {
            "intent_type": intent_match.intent_type,
            "workflow_chain": [s for s in intent_match.workflow_chain],
            "confidence": intent_match.confidence,
        }

    def _build_step_timings(
        self, step1: float, step2: float, step3: float, step4: float, step5: float,
        step6: float, step7: float, step8: float, step9: float, step10: float,
        step11: float, step12: float,
    ) -> Dict[str, float]:
        """Build step timings dict from absolute timestamps."""
        names = ["analyze", "warmup", "plan", "spawn", "execute", "collect",
                 "consensus", "compress", "permission", "memory", "skillify"]
        times = [step1, step2, step3, step4, step5, step6, step7, step8, step9, step10, step11, step12]
        return {name: round(times[i + 1] - times[i], 3) for i, name in enumerate(names)}

    def _build_lifecycle_trace(self, step_timings: Dict[str, float]) -> Dict[str, Any]:
        """Build lifecycle phase trace from step timings.

        Maps dispatch pipeline steps to lifecycle phases (P1-P11),
        aggregating timing per phase for observability.
        """
        step_to_lifecycle = {
            "analyze": "P1_Requirements",
            "warmup": "P2_Architecture",
            "plan": "P3_Implementation",
            "spawn": "P3_Implementation",
            "execute": "P3_Implementation",
            "collect": "P4_Review",
            "consensus": "P4_Review",
            "compress": "P5_Integration",
            "permission": "P6_Security",
            "memory": "P5_Integration",
            "skillify": "P8_Optimization",
        }

        phase_durations: Dict[str, float] = {}
        phase_steps: Dict[str, list[str]] = {}
        for step_name, duration in step_timings.items():
            phase = step_to_lifecycle.get(step_name, "P10_Delivery")
            phase_durations[phase] = phase_durations.get(phase, 0.0) + duration
            phase_steps.setdefault(phase, []).append(step_name)

        return {
            "lifecycle_phases": phase_durations,
            "phase_steps": phase_steps,
            "mapping_version": "1.0",
        }

    def _post_dispatch_hooks(
        self, result: DispatchResult, task: str, role_ids: List[str], total_duration: float
    ) -> None:
        """Post-dispatch hooks: history recording, quality audit, performance recording."""
        self._dispatch_history.append(result)
        if len(self._dispatch_history) > self._max_history:
            self._dispatch_history = self._dispatch_history[-self._max_history :]

        if self.enable_quality_guard and self.quality_guard:
            try:
                qreport = self.audit_quality()
                result.quality_report = qreport.to_markdown()
            except (ValueError, AttributeError, OSError, ImportError) as e:
                logger.warning("Quality audit failed: %s", e)

        perf_metric = PerformanceMetric(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            task_description=task,
            total_duration=total_duration,
            step_timings=result.details.get("timing", {}),
            success=result.success,
            error_count=len(result.errors),
            role_count=len(role_ids),
        )
        self._perf_monitor.record(perf_metric)

    def _run_feedback_loop(
        self,
        task: str,
        result: DispatchResult,
        lang: str,
        roles: Optional[List[str]],
        mode: str,
        dry_run: bool,
        kwargs: Dict[str, Any],
    ) -> DispatchResult:
        """Run FeedbackControlLoop iteration. Returns final (possibly refined) result.

        Modes:
            True:  Always run feedback loop (up to 3 iterations)
            "auto": Only trigger when first-pass quality < 0.5 (critical failure)
            False: Never run feedback loop
        """
        if self.enable_feedback_loop is False or dry_run:
            return result

        # Auto mode: assess first-pass quality, only trigger on critical failure
        if self.enable_feedback_loop == "auto":
            try:
                from .feedback_control_loop import FeedbackControlLoop
                loop = FeedbackControlLoop(dispatcher=self)
                first_quality = loop._assess_quality(result)
                if first_quality >= 0.5:
                    logger.debug(
                        "Feedback loop auto-skip: first-pass quality %.2f >= 0.5 threshold",
                        first_quality,
                    )
                    return result
                logger.info(
                    "Feedback loop auto-triggered: first-pass quality %.2f < 0.5",
                    first_quality,
                )
            except (ImportError, ValueError, AttributeError) as e:
                logger.debug("Feedback loop auto-assessment failed: %s", e)
                return result

        try:
            from .feedback_control_loop import FeedbackControlLoop

            feedback_loop = FeedbackControlLoop(
                dispatcher=self,
                quality_gate=0.7,
                max_iterations=3,
                llm_backend=self.llm_backend,
            )
            result = feedback_loop.run(
                task,
                roles=roles,
                mode=mode,
                **{k: v for k, v in kwargs.items() if k not in ["dry_run"]},
            )
            if self.usage_tracker:
                self.usage_tracker.tick("feedback_loop_executed")
            logger.info(
                "Feedback loop completed: %d iterations, best_quality=%.2f",
                feedback_loop.iteration_count,
                feedback_loop.best_quality,
            )
        except (ImportError, ValueError, AttributeError, RuntimeError) as loop_err:
            logger.warning("Feedback control loop failed: %s", loop_err)

        return result

    def _build_summary(self, task: str, roles: List[str], exec_result: Any, sp_summary: str) -> str:
        """Build execution summary."""
        return self.report_formatter.build_summary(task, roles, exec_result, sp_summary)

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
        return self.report_formatter.format_structured_report(result, include_action_items, include_timing)

    def _format_compact_report(self, result: DispatchResult) -> str:
        return self.report_formatter.format_compact_report(result)

    def _extract_findings(self, scratchpad_summary: str) -> List[str]:
        return self.report_formatter.extract_findings(scratchpad_summary)

    def _generate_action_items(self, result: DispatchResult) -> List[Dict[str, str]]:
        return self.report_formatter.generate_action_items(result)

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
        if self.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return []
        return [r.to_dict() for r in self._dispatch_history[-limit:]]

    def audit_quality(self, module_path: str | None = None, test_path: str | None = None, **kwargs: Any) -> TestQualityReport:
        """Execute test quality audit (P1 integration)."""
        if self.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return TestQualityReport(
                    module_name="rbac_denied",
                    test_file="",
                    source_file="",
                )

        if not self.quality_guard:
            self.quality_guard = TestQualityGuard("", "")

        if module_path and test_path:
            return self.quality_guard.__class__(module_path, test_path).audit()

        collab_dir = os.path.dirname(os.path.abspath(__file__))
        reports = self._audit_collab_modules(collab_dir)

        if len(reports) == 1:
            return reports[0]

        combined = TestQualityReport(
            module_name="project",
            test_file=f"{len(reports)} modules",
            source_file=collab_dir,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        combined.total_tests = sum(r.total_tests for r in reports)
        combined.issues = [i for r in reports for i in r.issues]
        combined.test_functions = [tf for r in reports for tf in r.test_functions]
        if reports:
            scores = [r.score.overall for r in reports]
            combined.score.overall = sum(scores) / len(scores) if scores else 0
        combined.audit_time = sum(r.audit_time for r in reports)
        return combined

    def _audit_collab_modules(self, collab_dir: str) -> list:
        """Audit all collaboration modules that have matching test files."""
        reports = []
        for fname in os.listdir(collab_dir):
            if fname.endswith(".py") and not fname.startswith("_") and "test" not in fname:
                mod_name = fname.replace(".py", "")
                test_name = f"{mod_name}_test.py"
                mod_full = os.path.join(collab_dir, fname)
                test_full = os.path.join(collab_dir, test_name)
                if os.path.exists(test_full):
                    try:
                        r = self.quality_guard.__class__(mod_full, test_full).audit()
                        reports.append(r)
                    except (ValueError, AttributeError, OSError, ImportError) as e:
                        logger.warning("Quality guard audit failed for %s: %s", mod_name, e)
        return reports

    def get_performance_stats(self) -> dict[str, Any]:
        """Get performance statistics."""
        return self._perf_monitor.get_statistics()

    def check_performance_regression(self) -> dict[str, Any] | None:
        """Check for performance regression."""
        return self._perf_monitor.detect_regression()

    def export_performance_metrics(self, output_file: str, **kwargs: Any) -> None:
        """Export performance metrics to file."""
        if self.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return
        self._perf_monitor.export_metrics(output_file, allowed_base_dir=self.persist_dir)

    def clear_performance_history(self, **kwargs: Any) -> None:
        """Clear performance history."""
        if self.rbac_engine:
            try:
                user_id = kwargs.get('user_id', 'default')
                self.rbac_engine.enforce(user_id, Permission.TASK_EXECUTE)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return
        self._perf_monitor.clear()
        logger.info("Performance history cleared")

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
            self.audit_logger, "force_flush",
            (OSError, AttributeError, RuntimeError), "Audit flush failed")
        self._shutdown_component(
            self.tenant_manager, "clear_context",
            (AttributeError, RuntimeError, OSError), "Tenant cleanup failed")

    def _shutdown_component(self, component: Any, method: str, exc_types: tuple, msg: str) -> None:
        """Safely call a shutdown method on a component."""
        if not component:
            return
        try:
            getattr(component, method)()
        except exc_types as e:
            logger.debug(f"{msg}: {e}")


def create_dispatcher(**kwargs: Any) -> MultiAgentDispatcher:
    """Factory function to create and initialize dispatcher."""
    return MultiAgentDispatcher(**kwargs)


def quick_collaborate(task: str, **kwargs: Any) -> DispatchResult:
    """Convenience function: single-call collaboration."""
    disp = create_dispatcher(**kwargs)
    result = disp.dispatch(task)
    disp.shutdown()
    return result


async def async_quick_collaborate(task: str, roles: Optional[List[str]] = None, **kwargs: Any) -> DispatchResult:
    """Async version of quick_collaborate()."""
    disp = create_dispatcher(**kwargs)
    result = await disp.async_dispatch(task, roles=roles, **kwargs)
    disp.shutdown()
    return result
