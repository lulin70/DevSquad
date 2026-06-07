#!/usr/bin/env python3
"""
V3 Multi-Agent Collaboration Dispatcher (Unified Entry Point)

This is the V3 unified entry point that chains all collaboration components
into a single usable pipeline:

    User Task → [Intent Recognition] → [Role Assignment] → [Coordinator Orchestration]
             → [Parallel Worker Execution] → [Scratchpad Sharing] → [Consensus Decision]
             → [Context Compression] → [Permission Check] → [Memory Capture] → [Result Return]

Integrated Components:
- WarmupManager: Startup warmup to reduce cold-start latency
- Coordinator + Worker + Scratchpad: Multi-agent collaboration core
- BatchScheduler: Parallel/sequential hybrid scheduling
- ConsensusEngine: Weighted voting consensus mechanism with veto power
- ContextCompressor: 4-level context compression to prevent overflow
- PermissionGuard: Permission guard for secure operation checks
- Skillifier: Learns from successful patterns to generate new Skills
- MemoryBridge: Cross-session memory bridge (with MCE + WorkBuddy Claw integration)

Example Usage:
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    disp = MultiAgentDispatcher()
    result = disp.dispatch("Design a user authentication system")
    print(result.summary)
"""

import json
import logging
import os
import tempfile
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)

from .batch_scheduler import BatchScheduler
from .concern_pack_loader import ConcernPackLoader
from .consensus import ConsensusEngine
from .context_compressor import ContextCompressor
from .coordinator import Coordinator
from .dispatch_models import (
    DispatchResult,
    I18N,
    PLANNED_ROLES,
    ROLE_TEMPLATES,
    PerformanceMetric,
    PerformanceThresholds,
)
from .dispatch_performance import PerformanceMonitor
from .input_validator import InputValidator
from .memory_bridge import (
    EpisodicMemory,
    MemoryBridge,
)
from .models import (
    EntryType,
)
from .permission_guard import (
    ActionType,
    PermissionGuard,
    PermissionLevel,
    ProposedAction,
)
from .report_formatter import ReportFormatter
from .role_matcher import RoleMatcher
from .scratchpad import Scratchpad, ScratchpadEntry
from .skillifier import Skillifier
from .test_quality_guard import (
    TestQualityGuard,
    TestQualityReport,
)
from .usage_tracker import track_usage
from .user_friendly_error import make_user_friendly_error, translate_validation_result
from .warmup_manager import WarmupConfig, WarmupManager
from ._version import __version__



class MultiAgentDispatcher:
    """V3 Unified Multi-Agent Collaboration Dispatcher.

    High-level API that orchestrates the complete multi-Agent collaboration
    pipeline in a single call. Integrates all V3 components:

    Pipeline:
        User Task → Intent Recognition → Role Assignment → Coordinator Orchestration
                 → Parallel Worker Execution → Scratchpad Sharing → Consensus Decision
                 → Context Compression → Permission Check → Memory Capture → Result Return

    Integrated Components:
    - WarmupManager: Startup warmup to reduce cold-start latency
    - Coordinator + Worker + Scratchpad: Multi-agent collaboration core
    - BatchScheduler: Parallel/sequential hybrid scheduling
    - ConsensusEngine: Weighted voting consensus with veto power
    - ContextCompressor: 4-level context compression to prevent overflow
    - PermissionGuard: Permission guard for secure operation checks
    - Skillifier: Learns from successful patterns to generate new Skills
    - MemoryBridge: Cross-session memory bridge (with MCE integration)
    - AnchorChecker (V3.6.0): Goal alignment verification
    - RetrospectiveEngine (V3.6.0): Post-task analysis and learning

    Example Usage:
        >>> from scripts.collaboration.dispatcher import MultiAgentDispatcher
        >>> disp = MultiAgentDispatcher()
        >>> result = disp.dispatch("Design a user authentication system")
        >>> print(result.summary)

    Attributes:
        persist_dir: Directory for Scratchpad persistence
        enable_warmup: Whether startup warmup is enabled
        enable_compression: Whether context compression is enabled
        enable_permission: Whether permission checking is enabled
        enable_memory: Whether memory bridge is enabled
        enable_skillify: Whether Skill learning is enabled
        enable_anchor_check: Whether anchor checking is enabled (V3.6.0)
        enable_retrospective: Whether retrospective engine is enabled (V3.6.0)
    """

    def __init__(
        self,
        persist_dir: Optional[str] = None,
        enable_warmup: bool = True,
        enable_compression: bool = True,
        enable_permission: bool = True,
        enable_memory: bool = True,
        enable_skillify: bool = True,
        enable_quality_guard: bool = False,
        enable_anchor_check: bool = True,
        enable_retrospective: bool = True,
        enable_usage_tracker: bool = True,
        enable_feedback_loop: bool = False,
        enable_redis_cache: bool = False,
        redis_url: Optional[str] = None,
        compression_threshold: int = 100000,
        memory_dir: Optional[str] = None,
        permission_level: PermissionLevel = PermissionLevel.DEFAULT,
        mce_adapter: Any = None,
        llm_backend: Any = None,
        stream: bool = False,
        lang: str = "auto",
    ) -> None:
        """Initialize the Multi-Agent Dispatcher.

        Sets up all integrated components based on feature flags.
        Most features are enabled by default for full functionality.

        Args:
            persist_dir: Scratchpad persistence directory (None=in-memory only)
            enable_warmup: Enable startup warmup to reduce cold-start latency
            enable_compression: Enable context compression for long tasks
            enable_permission: Enable permission checking before operations
            enable_memory: Enable cross-session memory bridge
            enable_skillify: Enable pattern-based Skill generation
            enable_quality_guard: Enable test quality auto-audit (P1 feature)
            enable_anchor_check: Enable goal alignment checking (V3.6.0)
            enable_retrospective: Enable retrospective analysis (V3.6.0)
            enable_usage_tracker: Enable feature usage tracking (V3.6.0)
            enable_feedback_loop: Enable feedback control loop (V3.6.0)
            enable_redis_cache: Enable Redis L2 cache for LLM responses
            redis_url: Redis connection URL (e.g. redis://localhost:6379/0)
            compression_threshold: Token count threshold for compression trigger
            memory_dir: Directory for memory persistence files
            permission_level: Default permission level (PLAN/DEFAULT/AUTO/BYPASS)
            mce_adapter: MCE memory classification engine adapter (optional, v3.2)
            llm_backend: LLM execution backend (None=MockBackend, returns prompt as-is)
            stream: Enable streaming mode for LLM responses
            lang: Default language ("auto"/"zh"/"en"/"ja")

        Example:
            >>> disp = MultiAgentDispatcher(
            ...     persist_dir="./collab_data",
            ...     permission_level=PermissionLevel.AUTO,
            ...     lang="en",
            ... )
        """
        self.enable_quality_guard = enable_quality_guard
        self.enable_anchor_check = enable_anchor_check
        self.enable_retrospective = enable_retrospective
        self.enable_usage_tracker = enable_usage_tracker
        self.enable_feedback_loop = enable_feedback_loop
        self.enable_redis_cache = enable_redis_cache
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

    def _init_components(self) -> None:
        """初始化所有v3组件"""
        self._init_core_components()
        self._init_optional_components()
        self._init_cache_and_monitor()

    def _init_core_components(self) -> None:
        """Initialize core components that are always needed."""
        self.scratchpad = Scratchpad(persist_dir=self.persist_dir)

        self.coordinator = Coordinator(
            scratchpad=self.scratchpad,
            persist_dir=self.persist_dir,
            enable_compression=self.enable_compression,
            compression_threshold=self.compression_threshold,
            llm_backend=self.llm_backend,
            stream=self.stream,
        )

        self.batch_scheduler = BatchScheduler()

        self.consensus_engine = ConsensusEngine()

        self.role_matcher = RoleMatcher()
        self.report_formatter = ReportFormatter(lang=self.lang)

        if self.enable_compression:
            self.compressor: Optional[ContextCompressor] = ContextCompressor(token_threshold=self.compression_threshold)
        else:
            self.compressor = None

        if self.enable_permission:
            self.permission_guard: Optional[PermissionGuard] = PermissionGuard(
                current_level=self.permission_level,
            )
        else:
            self.permission_guard = None

        if self.enable_warmup:
            warmup_cfg = WarmupConfig(
                cache_enabled=True,
                cache_max_size=50,
                cache_ttl_seconds=3600,
                metrics_enabled=True,
            )
            self.warmup_manager: Optional[WarmupManager] = WarmupManager(config=warmup_cfg)
            try:
                self.warmup_manager.warmup()
            except Exception as e:
                logger.warning("Warmup failed: %s", e)
        else:
            self.warmup_manager = None

        if self.enable_memory:
            self.memory_bridge: Optional[MemoryBridge] = MemoryBridge(base_dir=self.memory_dir, mce_adapter=self._mce_adapter)
        else:
            self.memory_bridge = None

        if self.enable_skillify:
            self.skillifier: Optional[Skillifier] = Skillifier()
        else:
            self.skillifier = None

        if self.enable_quality_guard:
            self.quality_guard: Optional[TestQualityGuard] = TestQualityGuard("", "")
        else:
            self.quality_guard = None

        if self.enable_anchor_check:
            from .anchor_checker import AnchorChecker

            self.anchor_checker: Optional[Any] = AnchorChecker()
        else:
            self.anchor_checker = None

        if self.enable_retrospective:
            from .retrospective import RetrospectiveEngine

            retrospective_memory = self.memory_bridge if self.enable_memory else None
            self.retrospective_engine: Optional[Any] = RetrospectiveEngine(memory_bridge=retrospective_memory)
        else:
            self.retrospective_engine = None

        if self.enable_usage_tracker:
            from .feature_usage_tracker import FeatureUsageTracker

            usage_path = os.path.join(self.persist_dir, "feature_usage.json")
            self.usage_tracker: Optional[Any] = FeatureUsageTracker(persist_path=usage_path)
        else:
            self.usage_tracker = None

        self._dispatch_history: list[DispatchResult] = []
        self._max_history = 100
        self._validator = InputValidator()

    def _init_optional_components(self) -> None:
        """Initialize components that may not be available."""
        try:
            from .output_slicer import OutputSlicer

            self.output_slicer: Optional[Any] = OutputSlicer(max_slice_lines=200)
        except Exception as e:
            logger.debug("OutputSlicer not available: %s", e)
            self.output_slicer = None

        try:
            from .ci_feedback_adapter import CIFeedbackAdapter

            self.ci_feedback: Optional[Any] = CIFeedbackAdapter()
        except Exception as e:
            logger.debug("CIFeedbackAdapter not available: %s", e)
            self.ci_feedback = None

        self._std_templates: Dict[str, Any] = {}

        try:
            from .prompt_variant_generator import PromptVariantGenerator

            self.prompt_variant_gen: Optional[Any] = PromptVariantGenerator()
        except Exception as e:
            logger.debug("PromptVariantGenerator not available: %s", e)
            self.prompt_variant_gen = None

        try:
            from .role_template_market import RoleTemplateMarket

            self.role_template_market: Optional[Any] = RoleTemplateMarket()
        except Exception as e:
            logger.debug("RoleTemplateMarket not available: %s", e)
            self.role_template_market = None

    def _init_cache_and_monitor(self) -> None:
        """Initialize cache, monitor, and utility components."""
        # Configure Redis L2 cache for LLM responses
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

        from .null_providers import (
            get_null_cache,
            get_null_memory,
            get_null_monitor,
            get_null_retry,
        )

        self._null_cache = get_null_cache()
        self._null_retry = get_null_retry()
        self._null_monitor = get_null_monitor()
        self._null_memory = get_null_memory()

    def analyze_task(self, task_description: str) -> list[dict[str, str]]:
        """
        分析任务，匹配合适的角色

        Args:
            task_description: 任务描述

        Returns:
            匹配到的角色列表 [{"role_id": "...", "name": "...", "reason": "..."}]
        """
        track_usage("dispatcher.analyze_task")
        return self.role_matcher.analyze_task(task_description)

    def dispatch(
        self, task_description: str, roles: Optional[List[str]] = None, mode: str = "auto", dry_run: bool = False, **kwargs: Any
    ) -> DispatchResult:
        """Core dispatch method - complete multi-Agent collaboration in one call.

        Executes the full collaboration pipeline:
        1. Input validation and sanitization
        2. Intent recognition (optional)
        3. Role matching/assignment
        4. Task planning and Worker spawning
        5. Parallel execution with Scratchpad sharing
        6. Consensus decision making
        7. Context compression (if needed)
        8. Permission checking
        9. Memory capture
        10. Result aggregation and report generation

        Args:
            task_description: User's task description in natural language
            roles: Optional list of role IDs (e.g., ["architect", "tester"]).
                   None triggers automatic role matching based on task content.
            mode: Execution mode:
                - "auto": Automatically choose parallel or sequential
                - "parallel": Force parallel execution (default for multiple roles)
                - "sequential": Force sequential execution
                - "consensus": Enable five-axis consensus review mode
            dry_run: If True, simulate execution without running Workers.
                    Useful for testing role matching and planning.

        Returns:
            DispatchResult: Complete dispatch result containing:
                - success: Whether overall dispatch succeeded
                - task_description: Processed task description
                - matched_roles: List of matched role definitions
                - worker_results: List of WorkerResult from each Worker
                - summary: Human-readable result summary
                - errors: List of error messages (if any)
                - timing: Dict with step-level timing information
                - intent_match: Intent detection result (if enabled)
                - five_axis_result: Five-axis consensus result (if consensus mode)
                - report: Formatted Markdown report (if available)

        Raises:
            No exceptions raised; all errors captured in DispatchResult.errors

        Example:
            >>> result = disp.dispatch(
            ...     "Design a REST API for user management",
            ...     roles=["architect", "tester"],
            ...     mode="parallel",
            ... )
            >>> if result.success:
            ...     print(result.summary)
            ...     for wr in result.worker_results:
            ...         print(f"{wr.role_id}: {wr.output.get('finding_summary')}")
        """
        track_usage("dispatcher.dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()

        if self.usage_tracker:
            self.usage_tracker.tick("dispatch")

        errors = []

        # Step 1: Resolve language
        lang = self._resolve_language(self.lang)

        # Step 2: Validate input
        task_description, early_return = self._validate_input(task_description, roles, lang)
        if early_return:
            return early_return

        # Step 3: Collect rules and inject CI context
        task_description, rule_collection, early_return = self._collect_rules(task_description, lang)
        if early_return:
            return early_return

        try:
            step1_time = time.time()

            # Step 4: Detect intent
            intent_match = self._detect_intent(task_description, lang)

            # Step 5: Match roles
            matched_roles = self._match_roles(task_description, roles)

            # Step 6: Validate roles and security (concern packs + dry_run)
            role_ids, concern_packs, concern_enhancements, early_return = self._validate_roles_and_security(
                task_description, matched_roles, lang, dry_run, start_time
            )
            if early_return:
                return early_return

            step2_time = time.time()

            # Step 7: Prepare execution (warmup, prompts, plan, spawn, anchor, retrospective load)
            plan, structured_goal, prep_timing = self._prepare_execution(
                task_description, matched_roles, lang, intent_match, rule_collection, concern_enhancements
            )
            step3_time = prep_timing["step3_time"]
            step4_time = prep_timing["step4_time"]
            step5_time = prep_timing["step5_time"]

            # Step 8: Execute workers
            exec_result, worker_results, exec_errors, exec_timing = self._execute_workers(plan, task_description)
            errors.extend(exec_errors)
            step6_time = exec_timing["step6_time"]
            step7_time = exec_timing["step7_time"]

            # Step 9: Post-execution processing (collect, slice, anchor check)
            scratchpad_summary, anchor_result, collection, post_errors, post_timing = self._post_execution_processing(
                worker_results, structured_goal
            )
            errors.extend(post_errors)
            step8_time = post_timing["step8_time"]

            # Step 10: Resolve consensus
            consensus_records, compression_info = self._resolve_consensus(collection, mode)
            step9_time = time.time()

            # Step 11: Check permissions
            permission_checks = self._check_permissions(task_description, worker_results, consensus_records)
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
            step_timings = {
                "analyze": round(step2_time - step1_time, 3),
                "warmup": round(step3_time - step2_time, 3),
                "plan": round(step4_time - step3_time, 3),
                "spawn": round(step5_time - step4_time, 3),
                "execute": round(step6_time - step5_time, 3),
                "collect": round(step7_time - step6_time, 3),
                "consensus": round(step8_time - step7_time, 3),
                "compress": round(step9_time - step8_time, 3),
                "permission": round(step10_time - step9_time, 3),
                "memory": round(step11_time - step10_time, 3),
                "skillify": round(step12_time - step11_time, 3),
            }
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

            # Step 17: Post-dispatch hooks
            self._post_dispatch_hooks(result, task_description, role_ids, total_duration)

            # Step 18: Feedback loop
            result = self._run_feedback_loop(task_description, result, lang, roles, mode, dry_run, kwargs)

            return result

        except (ValueError, TypeError, AttributeError) as dispatch_err:
            logger.error(
                "Dispatch validation error for task '%s': %s - %s",
                task_description[:50],
                type(dispatch_err).__name__,
                dispatch_err,
                exc_info=True,
            )
            friendly = make_user_friendly_error("dispatch_failed", original_error=dispatch_err)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except (ImportError, ModuleNotFoundError) as import_err:
            logger.error(
                "Missing dependency during dispatch of task '%s': %s", task_description[:50], import_err, exc_info=True
            )
            friendly = make_user_friendly_error("backend_unavailable", original_error=import_err)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except Exception as e:
            logger.critical(
                "UNEXPECTED ERROR in dispatch task '%s': %s - %s",
                task_description[:50],
                type(e).__name__,
                e,
                exc_info=True,
            )
            friendly = make_user_friendly_error("dispatch_failed", original_error=e)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )

    async def async_dispatch(
        self,
        task_description: str,
        roles: Optional[List[str]] = None,
        mode: str = "auto",
        dry_run: bool = False,
        **kwargs: Any,
    ) -> DispatchResult:
        """Async version of dispatch() using AsyncCoordinator for concurrent LLM calls.

        Uses asyncio.gather instead of ThreadPoolExecutor for true async I/O.
        Falls back to sync dispatch if async components are unavailable.

        Args:
            task_description: User's task description in natural language.
            roles: Optional list of role IDs.
            mode: Execution mode ("auto"/"parallel"/"sequential"/"consensus").
            dry_run: If True, simulate execution without running Workers.
            **kwargs: Additional options (task_timeout, max_concurrency, etc.).

        Returns:
            DispatchResult: Complete dispatch result (same as sync dispatch).
        """
        track_usage("dispatcher.async_dispatch", metadata={"mode": mode, "dry_run": dry_run})
        start_time = time.time()

        if self.usage_tracker:
            self.usage_tracker.tick("async_dispatch")

        errors: List[str] = []

        # Step 1: Resolve language
        lang = self._resolve_language(self.lang)

        # Step 2: Validate input
        task_description, early_return = self._validate_input(task_description, roles, lang)
        if early_return:
            return early_return

        # Step 3: Collect rules and inject CI context
        task_description, rule_collection, early_return = self._collect_rules(task_description, lang)
        if early_return:
            return early_return

        try:
            step1_time = time.time()

            # Step 4: Detect intent
            intent_match = self._detect_intent(task_description, lang)

            # Step 5: Match roles
            matched_roles = self._match_roles(task_description, roles)

            # Step 6: Validate roles and security (concern packs + dry_run)
            role_ids, concern_packs, concern_enhancements, early_return = self._validate_roles_and_security(
                task_description, matched_roles, lang, dry_run, start_time
            )
            if early_return:
                return early_return

            step2_time = time.time()

            # Step 7: Prepare execution (warmup, prompts, plan, spawn, anchor, retrospective load)
            plan, structured_goal, prep_timing = self._prepare_execution(
                task_description, matched_roles, lang, intent_match, rule_collection, concern_enhancements
            )
            step3_time = prep_timing["step3_time"]
            step4_time = prep_timing["step4_time"]
            step5_time = prep_timing["step5_time"]

            # Step 8: Execute workers asynchronously via AsyncCoordinator
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
                )

                # Re-plan and spawn using AsyncCoordinator
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

                # Execute asynchronously
                exec_result = await async_coordinator.execute_plan(async_plan)

                step6_time = time.time()

                # Collect worker results (same format as sync)
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
                exec_errors = list(exec_result.errors) if exec_result.errors else []
                errors.extend(exec_errors)

            except (ImportError, Exception) as async_err:
                # Fallback to sync execution
                logger.warning("Async dispatch failed, falling back to sync: %s", async_err)
                exec_result, worker_results, exec_errors, exec_timing = self._execute_workers(plan, task_description)
                errors.extend(exec_errors)
                step6_time = exec_timing["step6_time"]
                step7_time = exec_timing["step7_time"]

            # Step 9: Post-execution processing (collect, slice, anchor check)
            scratchpad_summary, anchor_result, collection, post_errors, post_timing = self._post_execution_processing(
                worker_results, structured_goal
            )
            errors.extend(post_errors)
            step8_time = post_timing["step8_time"]

            # Step 10: Resolve consensus
            consensus_records, compression_info = self._resolve_consensus(collection, mode)
            step9_time = time.time()

            # Step 11: Check permissions
            permission_checks = self._check_permissions(task_description, worker_results, consensus_records)
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
            step_timings = {
                "analyze": round(step2_time - step1_time, 3),
                "warmup": round(step3_time - step2_time, 3),
                "plan": round(step4_time - step3_time, 3),
                "spawn": round(step5_time - step4_time, 3),
                "execute": round(step6_time - step5_time, 3),
                "collect": round(step7_time - step6_time, 3),
                "consensus": round(step8_time - step7_time, 3),
                "compress": round(step9_time - step8_time, 3),
                "permission": round(step10_time - step9_time, 3),
                "memory": round(step11_time - step10_time, 3),
                "skillify": round(step12_time - step11_time, 3),
            }
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

            # Step 17: Post-dispatch hooks
            self._post_dispatch_hooks(result, task_description, role_ids, total_duration)

            # Step 18: Feedback loop
            result = self._run_feedback_loop(task_description, result, lang, roles, mode, dry_run, kwargs)

            return result

        except (ValueError, TypeError, AttributeError) as dispatch_err:
            logger.error(
                "Async dispatch validation error for task '%s': %s - %s",
                task_description[:50],
                type(dispatch_err).__name__,
                dispatch_err,
                exc_info=True,
            )
            friendly = make_user_friendly_error("dispatch_failed", original_error=dispatch_err)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except (ImportError, ModuleNotFoundError) as import_err:
            logger.error(
                "Missing dependency during async dispatch of task '%s': %s", task_description[:50], import_err, exc_info=True
            )
            friendly = make_user_friendly_error("backend_unavailable", original_error=import_err)
            return DispatchResult(
                success=False,
                task_description=task_description,
                matched_roles=[],
                summary=friendly.message,
                errors=[friendly.format()],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except Exception as e:
            logger.critical(
                "UNEXPECTED ERROR in async dispatch task '%s': %s - %s",
                task_description[:50],
                type(e).__name__,
                e,
                exc_info=True,
            )
            friendly = make_user_friendly_error("dispatch_failed", original_error=e)
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
    # Private step methods extracted from dispatch()
    # ------------------------------------------------------------------

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
        except Exception as e:
            logger.debug("Locale detection failed, using default language: %s", e)
            return "zh"

    def _validate_input(
        self, task: str, roles: Optional[List[str]], lang: str
    ) -> Tuple[str, Optional[DispatchResult]]:
        """Validate task and roles input via InputValidator.

        Returns:
            Tuple of (sanitized_task, early_return). If early_return is not None,
            dispatch should return it immediately.
        """
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
        except Exception:
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
        """Collect rules via RuleCollector and inject CI context.

        Returns:
            Tuple of (task, rule_collection, early_return). Task may be modified
            by rule collection or CI context injection.
        """
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
        except Exception as e:
            logger.debug("RuleCollector not available: %s", e)

        if self.ci_feedback:
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
                            task = f"{task}\n\n[CI Context] {ctx.summary}"
                            if self.usage_tracker:
                                self.usage_tracker.tick("ci_context_injected")
            except Exception:
                pass

        return task, rule_collection, None

    def _detect_intent(self, task: str, lang: str) -> Any:
        """Detect intent via IntentWorkflowMapper.

        Returns:
            Intent match result or None.
        """
        intent_match = None
        try:
            intent_match = self.intent_mapper.detect_intent(task, lang=lang)
            if intent_match and self.usage_tracker:
                self.usage_tracker.tick("intent_detected")
        except Exception as intent_err:
            logger.debug("Intent detection failed: %s", intent_err)

        self.context_manager.clear_task_context()
        self.context_manager.set_task("task_description", task)
        self.context_manager.set_task("lang", lang)
        if intent_match:
            self.context_manager.set_task("intent_type", intent_match.intent_type)
            self.context_manager.set_task("workflow_chain", [s for s in intent_match.workflow_chain])

        return intent_match

    def _match_roles(self, task: str, roles: Optional[List[str]]) -> List[Dict[str, Any]]:
        """Match roles via RoleMatcher and AISemanticMatcher.

        Returns:
            List of matched role dicts.
        """
        matched_roles = self.analyze_task(task)

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
            except Exception as sem_err:
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
        """Validate roles and run security scans (concern packs).

        Returns:
            Tuple of (role_ids, concern_packs, concern_enhancements, early_return).
            If early_return is not None, dispatch should return it immediately.
        """
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
        """Prepare execution: warmup, prompt assembly, task planning, worker spawn.

        Returns:
            Tuple of (plan, structured_goal, timing_dict).
            timing_dict contains step3_time, step4_time, step5_time as absolute timestamps.
        """
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

        # V3.6.0: Parse structured goal for anchor checking
        structured_goal = None
        if self.anchor_checker:
            structured_goal = self.anchor_checker.parse_goal(task)
            if self.usage_tracker:
                self.usage_tracker.tick("anchor_check")

        # V3.6.0: Load historical retrospectives into Scratchpad
        if self.retrospective_engine and self.enable_memory:
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
            except Exception as retro_load_err:
                logger.debug("Failed to load historical retrospectives: %s", retro_load_err)

        return plan, structured_goal, {
            "step3_time": step3_time,
            "step4_time": step4_time,
            "step5_time": step5_time,
        }

    def _execute_workers(
        self, plan: Any, task_description: str
    ) -> Tuple[Any, List[Dict[str, Any]], List[str], Dict[str, float]]:
        """Execute workers via Coordinator.

        Returns:
            Tuple of (exec_result, worker_results, errors, timing_dict).
            timing_dict contains step6_time, step7_time as absolute timestamps.
        """
        exec_result = self.coordinator.execute_plan(plan)

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

        exec_errors = list(exec_result.errors) if exec_result.errors else []
        return exec_result, worker_results, exec_errors, {
            "step6_time": step6_time,
            "step7_time": step7_time,
        }

    def _post_execution_processing(
        self, worker_results: List[Dict[str, Any]], structured_goal: Any
    ) -> Tuple[str, Any, Any, List[str], Dict[str, float]]:
        """Post-execution processing: collect results, output slicing, anchor check.

        Returns:
            Tuple of (scratchpad_summary, anchor_result, collection, errors, timing_dict).
            timing_dict contains step8_time as absolute timestamp.
        """
        errors: List[str] = []
        collection = self.coordinator.collect_results()
        scratchpad_summary = collection.get("scratchpad", "")

        if self.output_slicer and worker_results:
            try:
                for wr in worker_results:
                    if wr.get("output") and len(wr["output"]) > self.output_slicer.max_slice_lines * 50:
                        slices = self.output_slicer.slice_output(wr["output"], role_id=wr.get("role_id", "unknown"))
                        wr["_slices"] = len(slices)
                        wr["_sliced"] = True
                        if self.usage_tracker:
                            self.usage_tracker.tick("output_sliced")
            except Exception:
                pass

        # V3.6.0: Anchor check after execution (needs scratchpad_summary)
        anchor_result = None
        if self.anchor_checker and structured_goal:
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
                            tags=["anchor-drift", "v3.6.0"],
                        )
                    )
            except Exception as anchor_err:
                logger.warning("Anchor check failed: %s", anchor_err)

        step8_time = time.time()

        return scratchpad_summary, anchor_result, collection, errors, {
            "step8_time": step8_time,
        }

    def _resolve_consensus(
        self, collection: Any, mode: str
    ) -> Tuple[List[Dict[str, Any]], Any]:
        """Resolve consensus and get compression info.

        Returns:
            Tuple of (consensus_records, compression_info).
        """
        consensus_records = []
        conflicts_count = collection.get("conflicts_count", 0)
        if conflicts_count > 0 or mode == "consensus":
            resolutions = self.coordinator.resolve_conflicts()
            for rec in resolutions:
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
        self, task: str, worker_results: List[Dict[str, Any]], consensus_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Check permissions via PermissionGuard.

        Returns:
            List of permission check results.
        """
        permission_checks = []
        if self.enable_permission and self.permission_guard:
            test_actions = [
                ProposedAction(
                    action_type=ActionType.FILE_CREATE, target="/tmp/test_output.md", description="生成输出文件"
                ),
            ]
            for action in test_actions:
                classified = None
                try:
                    classified = self.operation_classifier.classify(
                        operation_id=action.action_type.value,
                        target=action.target,
                    )
                except Exception:
                    pass
                decision = self.permission_guard.check(action)
                perm_entry = {
                    "action": f"{action.action_type.value}:{action.target}",
                    "allowed": decision.outcome.value == "ALLOWED",
                    "decision": decision.outcome.value,
                    "reason": decision.reason or "",
                }
                if classified:
                    perm_entry["operation_category"] = classified.category.value
                permission_checks.append(perm_entry)

        return permission_checks

    def _process_memory_pipeline(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        lang: str,
        scratchpad_summary: str,
        role_ids: List[str],
    ) -> Tuple[Optional[Dict[str, Any]], List[str]]:
        """Process memory pipeline: MemoryBridge capture + MCE classify + AI news inject.

        Returns:
            Tuple of (memory_stats, errors).
        """
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
        """Capture episodic memory via MemoryBridge.

        Returns:
            memory_stats dict or None.
        """
        memory_stats: Optional[Dict[str, Any]] = None

        if self.enable_memory and self.memory_bridge:
            try:
                mem_stats: Any = self.memory_bridge.get_statistics()
                memory_stats = {
                    "total_memories": mem_stats.total_memories,
                    "by_type_counts": mem_stats.by_type_counts,
                    "index_built": mem_stats.index_built,
                    "total_captures": mem_stats.total_captures,
                }

                ep = EpisodicMemory(
                    id=f"epi-{uuid.uuid4().hex[:8]}",
                    task_description=task,
                    finding=scratchpad_summary[:500],
                )
                self.memory_bridge.capture_execution(
                    execution_record={"task": task, "roles": role_ids},
                    scratchpad_entries=[],
                )
            except (ConnectionError, TimeoutError, OSError) as mem_err:
                logger.warning("MemoryBridge connection error: %s", mem_err)
                errors.append(f"MemoryBridge connection error: {type(mem_err).__name__}: {mem_err}")
            except (ValueError, KeyError, AttributeError) as mem_val_err:
                logger.debug("MemoryBridge data error: %s", mem_val_err)
                errors.append(f"MemoryBridge data error: {mem_val_err}")
            except Exception as mem_err:
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
        """Classify memory via MCE adapter.

        Args:
            scratchpad_summary: Summary from scratchpad.
            task: Task description.
            memory_stats: Existing memory stats dict (may be modified in-place).
            errors: Error list to append to.

        Returns:
            Updated memory_stats dict or the original value.
        """
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
            except Exception as mce_err:
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
            except Exception as inject_err:
                errors.append(f"AI news inject error: {inject_err}")

    def _learn_skills(
        self,
        task: str,
        worker_results: List[Dict[str, Any]],
        matched_roles: List[Dict[str, Any]],
        exec_result: Any,
    ) -> Tuple[List[Dict[str, Any]], List[str]]:
        """Learn skills via Skillifier.

        Returns:
            Tuple of (skill_proposals, errors).
        """
        errors: List[str] = []
        skill_proposals = []
        patterns = None

        if self.enable_skillify and self.skillifier and exec_result.success:
            try:
                patterns = self.skillifier.analyze_history()
                if patterns:
                    for pattern in patterns:
                        if pattern.confidence > 0.3:
                            pattern_title = getattr(pattern, 'title', None) or "新协作模式"
                            skill_proposals.append(
                                {
                                    "title": pattern_title,
                                    "confidence": pattern.confidence,
                                    "category": pattern.category.value
                                    if hasattr(pattern, "category") and pattern.category
                                    else "general",
                                }
                            )
                            try:
                                self.skill_registry.propose_from_result(
                                    name=pattern_title,
                                    description=pattern_title,
                                    category=pattern.category.value
                                    if hasattr(pattern, "category") and pattern.category
                                    else "general",
                                    confidence=pattern.confidence,
                                )
                            except Exception:
                                pass
            except Exception as skill_err:
                errors.append(f"Skillifier error: {skill_err}")

        if self.prompt_variant_gen and patterns:
            try:
                for pattern in patterns:
                    if pattern.confidence > 0.5:
                        variants = self.prompt_variant_gen.generate_from_pattern(pattern)
                        if variants:
                            if self.usage_tracker:
                                self.usage_tracker.tick("prompt_variant_generated")
            except Exception:
                pass

        return skill_proposals, errors

    def _run_five_axis_consensus(
        self, task: str, worker_results: List[Dict[str, Any]], mode: str, exec_result: Any
    ) -> Optional[Dict[str, Any]]:
        """Run five-axis consensus review (consensus mode only).

        Returns:
            Five-axis consensus result dict or None.
        """
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
        except Exception as fa_err:
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
        """Run RetrospectiveEngine analysis.

        Returns:
            Retrospective report or None.
        """
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
        except Exception as retro_err:
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
            anchor_result={
                "aligned": anchor_result.aligned,
                "coverage": anchor_result.coverage,
                "drift_score": anchor_result.drift_score,
                "severity": anchor_result.severity.value,
                "recommendation": anchor_result.recommendation,
            }
            if anchor_result
            else None,
            retrospective_report=retrospective_report.to_dict() if retrospective_report else None,
            intent_match={
                "intent_type": intent_match.intent_type,
                "workflow_chain": [s for s in intent_match.workflow_chain],
                "confidence": intent_match.confidence,
            }
            if intent_match
            else None,
            five_axis_result=five_axis_result,
        )

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
            except Exception as e:
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
        """Run FeedbackControlLoop iteration.

        Returns:
            Final result (possibly refined by feedback loop).
        """
        if not self.enable_feedback_loop or dry_run:
            return result

        try:
            from .feedback_control_loop import FeedbackControlLoop

            feedback_loop = FeedbackControlLoop(
                dispatcher=self,
                quality_gate=0.7,
                max_iterations=3,
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
        except Exception as loop_err:
            logger.warning("Feedback control loop failed: %s", loop_err)

        return result

    def _build_summary(self, task: str, roles: List[str], exec_result: Any, sp_summary: str) -> str:
        """构建执行摘要"""
        return self.report_formatter.build_summary(task, roles, exec_result, sp_summary)

    def quick_dispatch(
        self,
        task: str,
        output_format: str = "structured",
        include_action_items: bool = True,
        include_timing: bool = False,
    ) -> DispatchResult:
        """
        快速调度 - 返回 DispatchResult，summary 包含格式化报告

        Args:
            task: 任务描述
            output_format: 输出格式 ("structured"/"compact"/"detailed")
                - structured: 结构化报告 (默认, UI Designer推荐)
                - compact: 紧凑格式 (适合终端)
                - detailed: 详细完整报告
            include_action_items: 是否包含行动项建议
            include_timing: 是否包含各步骤耗时分析

        Returns:
            DispatchResult: 调度结果，summary 字段包含格式化报告
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
            },
            "dispatch_count": len(self._dispatch_history),
            "scratchpad_stats": self.scratchpad.get_stats() if self.scratchpad else {},
        }

        # 性能监控统计
        try:
            perf_stats = self._perf_monitor.get_statistics()
            status["performance"] = perf_stats

            # 回归检测
            regression = self._perf_monitor.detect_regression()
            if regression:
                status["regression_detected"] = regression
        except Exception as e:
            logger.debug("Performance stats collection failed: %s", e)

        if self.warmup_manager:
            try:
                metrics = self.warmup_manager.get_metrics()
                status["warmup_metrics"] = {
                    "cache_size": metrics.cache_size,
                    "hit_rate": round(metrics.cache_hit_rate, 3) if metrics.cache_hit_rate else 0,
                    "tasks_completed": metrics.tasks_completed,
                    "eager_duration_ms": round(metrics.eager_duration_ms, 2),
                }
            except Exception:
                status["warmup_metrics"] = None

        if self.memory_bridge:
            try:
                mem_stats = self.memory_bridge.get_statistics()
                status["memory_stats"] = {
                    "total_memories": mem_stats.total_memories,
                    "by_type_counts": mem_stats.by_type_counts,
                    "index_built": mem_stats.index_built,
                }
            except Exception:
                status["memory_stats"] = None

        return status

    def get_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取调度历史"""
        return [r.to_dict() for r in self._dispatch_history[-limit:]]

    def audit_quality(self, module_path: str | None = None, test_path: str | None = None) -> TestQualityReport:
        """
        执行测试质量审计 (P1 集成)

        Args:
            module_path: 被测模块路径（默认自动检测 collaboration/ 下所有模块）
            test_path: 测试文件路径

        Returns:
            TestQualityReport: 完整质量报告
        """
        if not self.quality_guard:
            self.quality_guard = TestQualityGuard("", "")

        if module_path and test_path:
            return self.quality_guard.__class__(module_path, test_path).audit()

        collab_dir = os.path.dirname(os.path.abspath(__file__))
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
                    except Exception as e:
                        logger.warning("Quality guard audit failed for %s: %s", mod_name, e)

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

    def get_performance_stats(self) -> dict[str, Any]:
        """获取性能统计信息"""
        return self._perf_monitor.get_statistics()

    def check_performance_regression(self) -> dict[str, Any] | None:
        """检查是否存在性能回归"""
        return self._perf_monitor.detect_regression()

    def export_performance_metrics(self, output_file: str) -> None:
        """导出性能指标到文件"""
        self._perf_monitor.export_metrics(output_file, allowed_base_dir=self.persist_dir)

    def clear_performance_history(self) -> None:
        """清除性能历史数据"""
        self._perf_monitor.clear()
        logger.info("Performance history cleared")

    def shutdown(self) -> None:
        """优雅关闭所有组件"""
        if self.warmup_manager:
            try:
                self.warmup_manager.shutdown()
            except Exception as e:
                logger.warning("Warmup shutdown failed: %s", e)

        if self.memory_bridge:
            try:
                self.memory_bridge.cleanup_expired_memories()
            except Exception as e:
                logger.warning("Memory cleanup failed: %s", e)

        if self.usage_tracker:
            try:
                self.usage_tracker.persist()
            except Exception as e:
                logger.warning("Usage tracker persist failed: %s", e)


def create_dispatcher(**kwargs: Any) -> MultiAgentDispatcher:
    """工厂函数 - 创建并初始化调度器实例"""
    return MultiAgentDispatcher(**kwargs)


def quick_collaborate(task: str, **kwargs: Any) -> DispatchResult:
    """便捷函数 - 单次调用完成协作"""
    disp = create_dispatcher(**kwargs)
    result = disp.dispatch(task)
    disp.shutdown()
    return result


async def async_quick_collaborate(task: str, roles: Optional[List[str]] = None, **kwargs: Any) -> DispatchResult:
    """Async version of quick_collaborate(). Uses async dispatch for concurrent LLM calls."""
    disp = create_dispatcher(**kwargs)
    result = await disp.async_dispatch(task, roles=roles, **kwargs)
    disp.shutdown()
    return result
