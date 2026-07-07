#!/usr/bin/env python3
"""ComponentFactory — Extracted from MultiAgentDispatcher.

Handles all component initialization logic for the dispatcher pipeline.
The factory creates and wires up core, optional, and utility components
based on the provided configuration.
"""

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ComponentConfig:
    """Configuration for component initialization."""

    persist_dir: str
    memory_dir: str
    enable_warmup: bool = True
    enable_compression: bool = True
    enable_permission: bool = True
    enable_memory: bool = True
    enable_skillify: bool = True
    enable_quality_guard: bool = True
    enable_anchor_check: bool = True
    enable_retrospective: bool = True
    enable_usage_tracker: bool = True
    enable_feedback_loop: bool | str = "auto"
    enable_redis_cache: bool = False
    enable_execution_guard: bool = True
    redis_url: str | None = None
    compression_threshold: int = 100000
    permission_level: Any = None  # PermissionLevel
    mce_adapter: Any = None
    llm_backend: Any = None
    stream: bool = False
    lang: str = "auto"
    # V3.10.0 Phase 2: SMART structure-aware pre-compression (preserves all messages)
    smart_compression: bool = False
    # V3.10.0 Phase 3: reversible compression store + per-dispatch token budget
    ccr_store: Any = None  # CCRStore | None
    token_budget: Any = None  # TokenBudget | None
    # V4.0.0 P1-1: Loop Engineering 五步闭环
    loop_engineering_enabled: bool = False
    loop_config: Any = None  # LoopEngineeringConfig | None
    # V4.0.0 P1-2: UI/UX 巡检与视觉回归
    qa_enabled: bool = False
    qa_pixel_diff_threshold: float = 0.01
    # V4.0.0 P3-1: Autonomous 自主迭代模式
    autonomous_enabled: bool = False
    autonomous_max_iterations: int = 20
    # V4.0.0 P3-2: 插件热加载
    plugins_enabled: bool = False
    plugins_dropin_dir: Any = None  # str | Path | None
    plugins_no_hot_reload: bool = False


class ComponentFactory:
    """Factory for creating and wiring dispatcher components.

    Usage::

        factory = ComponentFactory()
        components = factory.create_all(config)
        # components is a dict of initialized component instances
    """

    def create_all(self, config: ComponentConfig) -> dict[str, Any]:
        """Create all components and return them as a dict.

        Args:
            config: ComponentConfig with initialization parameters.

        Returns:
            Dict mapping component names to initialized instances.
        """
        components: dict[str, Any] = {}
        self._init_core_components(config, components)
        self._init_optional_components(config, components)
        self._init_cache_and_monitor(config, components)
        return components

    def _init_core_components(self, config: ComponentConfig, components: dict[str, Any]) -> None:
        """Initialize core components."""
        from .batch_scheduler import BatchScheduler
        from .consensus import ConsensusEngine
        from .context_compressor import ContextCompressor
        from .coordinator import Coordinator
        from .input_validator import InputValidator
        from .memory_bridge import MemoryBridge
        from .permission_guard import PermissionGuard
        from .report_formatter import ReportFormatter
        from .role_matcher import RoleMatcher
        from .scratchpad import Scratchpad
        from .skillifier import Skillifier
        from .test_quality_guard import TestQualityGuard

        components["scratchpad"] = Scratchpad(persist_dir=config.persist_dir)

        # Initialize ExecutionGuard if enabled (graceful degradation)
        components["execution_guard"] = None
        if config.enable_execution_guard:
            try:
                from .execution_guard import ExecutionGuard
                components["execution_guard"] = ExecutionGuard()
                logger.info("ExecutionGuard enabled")
            except (ImportError, ModuleNotFoundError, AttributeError, RuntimeError) as e:
                logger.warning("ExecutionGuard initialization failed: %s", e)

        components["coordinator"] = Coordinator(
            scratchpad=components["scratchpad"],
            persist_dir=config.persist_dir,
            enable_compression=config.enable_compression,
            compression_threshold=config.compression_threshold,
            llm_backend=config.llm_backend,
            stream=config.stream,
            execution_guard=components["execution_guard"],
            smart_compression=config.smart_compression,
            token_budget=config.token_budget,
            ccr_store=config.ccr_store,
        )

        components["batch_scheduler"] = BatchScheduler()
        components["consensus_engine"] = ConsensusEngine()
        components["role_matcher"] = RoleMatcher()
        components["report_formatter"] = ReportFormatter(lang=config.lang)

        components["compressor"] = (
            ContextCompressor(token_threshold=config.compression_threshold)
            if config.enable_compression
            else None
        )
        components["permission_guard"] = (
            PermissionGuard(current_level=config.permission_level)
            if config.enable_permission
            else None
        )

        components["warmup_manager"] = self._init_warmup_manager(config)
        components["memory_bridge"] = (
            MemoryBridge(base_dir=config.memory_dir, mce_adapter=config.mce_adapter)
            if config.enable_memory
            else None
        )
        components["skillifier"] = Skillifier() if config.enable_skillify else None
        components["quality_guard"] = TestQualityGuard("", "") if config.enable_quality_guard else None
        components["anchor_checker"] = self._try_import_component("anchor_checker", "AnchorChecker")
        components["retrospective_engine"] = self._init_retrospective_engine(config, components)
        components["learned_rule_store"] = self._init_learned_rule_store(config)
        components["usage_tracker"] = self._init_usage_tracker(config)

        components["_dispatch_history"] = []
        components["_max_history"] = 100
        components["_validator"] = InputValidator()

    def _init_warmup_manager(self, config: ComponentConfig) -> Any | None:
        """Init WarmupManager if enabled."""
        if not config.enable_warmup:
            return None
        from .warmup_manager import WarmupConfig, WarmupManager

        warmup_cfg = WarmupConfig(
            cache_enabled=True, cache_max_size=50, cache_ttl_seconds=3600, metrics_enabled=True,
        )
        mgr = WarmupManager(config=warmup_cfg)
        try:
            mgr.warmup()
        except (RuntimeError, OSError, ImportError) as e:
            logger.warning("Warmup failed: %s", e)
        return mgr

    @staticmethod
    def _try_import_component(module_name: str, class_name: str) -> Any | None:
        """Try to import and instantiate a component."""
        try:
            import importlib

            mod = importlib.import_module(f".{module_name}", package=__package__)
            return getattr(mod, class_name)()
        except (ImportError, AttributeError, RuntimeError, OSError):
            return None

    def _init_retrospective_engine(self, config: ComponentConfig, components: dict[str, Any]) -> Any | None:
        """Init RetrospectiveEngine if enabled."""
        if not config.enable_retrospective:
            return None
        try:
            from .retrospective import RetrospectiveEngine
            return RetrospectiveEngine(
                memory_bridge=components.get("memory_bridge") if config.enable_memory else None
            )
        except (ImportError, AttributeError, RuntimeError):
            return None

    def _init_learned_rule_store(self, config: ComponentConfig) -> Any | None:
        """Init LearnedRuleStore if retrospective is enabled (Phase 4).

        Provides two-tier persistence for LearnedRule entries extracted by
        RetrospectiveEngine.extract_learned_rules(). Without this, the
        learning loop is broken — rules extracted from retrospectives are
        never persisted and never injected into future prompts (ghost feature).
        """
        if not config.enable_retrospective:
            return None
        try:
            from .learned_rule_store import LearnedRuleStore

            config_path = os.path.join(config.persist_dir, ".devsquad.yaml")
            tier2_dir = os.path.join(config.persist_dir, "data", "tier2")
            os.makedirs(tier2_dir, exist_ok=True)
            tier2_path = os.path.join(tier2_dir, "corrections.json")
            return LearnedRuleStore(
                config_path=config_path,
                tier2_path=tier2_path,
            )
        except (ImportError, AttributeError, RuntimeError, OSError) as e:
            logger.warning("LearnedRuleStore initialization failed: %s", e)
            return None

    def _init_usage_tracker(self, config: ComponentConfig) -> Any | None:
        """Init FeatureUsageTracker if enabled."""
        if not config.enable_usage_tracker:
            return None
        try:
            from .feature_usage_tracker import FeatureUsageTracker
            return FeatureUsageTracker(
                persist_path=os.path.join(config.persist_dir, "feature_usage.json")
            )
        except (ImportError, AttributeError, RuntimeError):
            return None

    def _init_optional_components(self, config: ComponentConfig, components: dict[str, Any]) -> None:
        """Init optional components with graceful fallback."""
        components["output_slicer"] = self._try_import_component("output_slicer", "OutputSlicer")
        components["ci_feedback"] = self._try_import_component("ci_feedback_adapter", "CIFeedbackAdapter")
        components["_std_templates"] = {}

        if config.loop_engineering_enabled:
            from .loop_engineering import LoopEngineeringConfig, LoopKernel
            loop_config = config.loop_config or LoopEngineeringConfig()
            components["loop_kernel"] = LoopKernel(config=loop_config)

        # V4.0.0 P1-2: UI/UX 巡检与视觉回归（软依赖策略）
        if config.qa_enabled:
            try:
                from scripts.qa import UIUXAnalyzer, VisualRegressionChecker
                components["uiux_analyzer"] = UIUXAnalyzer()
                components["visual_regression_checker"] = VisualRegressionChecker(
                    pixel_diff_threshold=config.qa_pixel_diff_threshold,
                )
                logger.info("UIUXAnalyzer + VisualRegressionChecker enabled")
            except (ImportError, ModuleNotFoundError) as e:
                logger.warning("QA components initialization failed: %s", e)

        # V4.0.0 P3-1: Autonomous 自主迭代模式
        if config.autonomous_enabled:
            try:
                from .autonomous import AutonomousLoopController
                from .autonomous.loop_controller import AutonomousConfig
                autonomous_config = AutonomousConfig(
                    objective="",  # 运行时由 dispatch_autonomous() 设置
                    max_iterations=config.autonomous_max_iterations,
                )
                components["autonomous_controller"] = AutonomousLoopController(
                    config=autonomous_config,
                )
                logger.info("AutonomousLoopController enabled")
            except (ImportError, ModuleNotFoundError, AttributeError) as e:
                logger.warning("Autonomous components initialization failed: %s", e)

        # V4.0.0 P3-2: 插件热加载
        if config.plugins_enabled:
            try:
                from .plugins import PluginHotLoader

                dropin_dir = config.plugins_dropin_dir or os.path.join(
                    config.persist_dir, "plugins_extra"
                )
                os.makedirs(dropin_dir, exist_ok=True)
                components["plugin_hot_loader"] = PluginHotLoader(
                    dropin_dir=dropin_dir,
                    no_hot_reload=config.plugins_no_hot_reload,
                )
                logger.info(
                    "PluginHotLoader enabled (dropin_dir=%s, no_hot_reload=%s)",
                    dropin_dir,
                    config.plugins_no_hot_reload,
                )
            except (ImportError, ModuleNotFoundError, AttributeError) as e:
                logger.warning("PluginHotLoader initialization failed: %s", e)

    def _init_cache_and_monitor(self, config: ComponentConfig, components: dict[str, Any]) -> None:
        """Initialize cache, monitor, and utility components."""
        if config.enable_redis_cache and config.redis_url:
            from .llm_cache import configure_redis_cache
            configure_redis_cache(enabled=True, url=config.redis_url)

        from .concern_pack_loader import ConcernPackLoader
        from .dispatch_performance import DispatchPerformanceMonitor

        components["_perf_monitor"] = DispatchPerformanceMonitor(window_size=100)
        components["_concern_loader"] = ConcernPackLoader()

        from .dual_layer_context import DualLayerContextManager
        components["context_manager"] = DualLayerContextManager()

        from .intent_workflow_mapper import IntentWorkflowMapper
        components["intent_mapper"] = IntentWorkflowMapper()

        from .operation_classifier import OperationClassifier
        components["operation_classifier"] = OperationClassifier()

        from .skill_registry import SkillRegistry
        components["skill_registry"] = SkillRegistry(
            storage_path=os.path.join(config.persist_dir, "skills")
        )

        from .ai_semantic_matcher import AISemanticMatcher
        components["semantic_matcher"] = AISemanticMatcher(llm_backend=config.llm_backend)

        from .null_providers import get_null_cache, get_null_memory, get_null_monitor, get_null_retry
        components["_null_cache"] = get_null_cache()
        components["_null_retry"] = get_null_retry()
        components["_null_monitor"] = get_null_monitor()
        components["_null_memory"] = get_null_memory()
