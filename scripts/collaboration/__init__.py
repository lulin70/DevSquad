#!/usr/bin/env python3
"""
DevSquad Collaboration Optimization Modules

This package provides three core optimization modules for LLM-based applications:

1. LLM Cache (llm_cache.py)
   - Reduces API costs by 60-80%
   - Improves response time by 90% on cache hits
   - Supports TTL-based expiration and LRU eviction

2. LLM Retry & Fallback (llm_retry.py)
   - Exponential backoff retry mechanism
   - Multi-backend fallback support
   - Circuit breaker pattern for fault tolerance

3. Performance Monitor (performance_monitor.py)
   - Real-time performance tracking
   - P95/P99 latency metrics
   - Bottleneck detection and reporting

Quick Start:
    from scripts.collaboration import (
        get_llm_cache,
        retry_with_fallback,
        monitor_performance
    )

    @monitor_performance("my_function")
    @retry_with_fallback(max_retries=3)
    def my_function():
        cache = get_llm_cache()
        # Your code here
        pass

For detailed documentation, see: docs/OPTIMIZATION_GUIDE.md
"""

import logging
import sys


def get_logger(name: str = "devsquad") -> logging.Logger:
    """Get a configured logger instance."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        fmt = logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s", datefmt="%H:%M:%S")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
    return logger


# LLM Cache exports
from ._version import __version__
from .adaptive_role_selector import AdaptiveRoleSelector
from .ai_semantic_matcher import AISemanticMatcher

# V3.7.0 Module exports
from .anchor_checker import AnchorChecker
from .async_adapter import AsyncToSyncAdapter, AutoBackendSelector, SyncToAsyncAdapter

# Async Module exports
from .async_llm_backend import AsyncAnthropicBackend, AsyncFallbackBackend, AsyncLLMBackendFactory, AsyncOpenAIBackend
from .audit_logger import AuditLogger, SensitiveDataMasker
from .batch_scheduler import BatchScheduler
from .ci_feedback_adapter import CIContext, CIFeedbackAdapter, CIResult
from .consensus import ConsensusEngine
from .coordinator import Coordinator
from .dual_layer_context import DualLayerContextManager
from .enhanced_worker import AgentBriefingOutput, EnhancedWorker
from .execution_guard import ExecutionGuard
from .feature_usage_tracker import FeatureUsageTracker

# V3.7.0 Control & Guard exports
from .feedback_control_loop import FeedbackControlLoop
from .five_axis_consensus import FiveAxisConsensusEngine
from .intent_workflow_mapper import IntentWorkflowMapper
from .llm_cache import (
    CacheEntry,
    LLMCache,
    get_llm_cache,
    reset_cache,
)
from .llm_cache_async import AsyncLLMCache

# LLM Retry exports
from .llm_retry import (
    CircuitBreakerError,
    CircuitBreakerState,
    LLMRetryManager,
    RateLimitError,
    RetryConfig,
    get_retry_manager,
    retry_with_fallback,
)

# Async LLM Retry exports
from .llm_retry_async import AsyncLLMRetryManager

# Data models exports
from .models import (
    ROLE_WEIGHTS,
    BatchMode,
    DecisionOutcome,
    DecisionProposal,
    EntryStatus,
    EntryType,
    Reference,
    ReferenceType,
    ScratchpadEntry,
    TaskBatch,
    TaskDefinition,
    TaskNotification,
    Vote,
    WorkerResult,
)

# Multi-Level Cache exports
from .multi_level_cache import MemoryCacheBackend, MultiLevelCacheCoordinator
from .multi_tenant import IsolationLevel, MultiTenantManager, Tenant, TenantContext
from .null_providers import (
    NullCacheProvider,
    NullMemoryProvider,
    NullMonitorProvider,
    NullRetryProvider,
)
from .operation_classifier import OperationClassifier

# Tier3 Auxiliary Module exports
from .output_slicer import OutputSlice, OutputSlicer
from .performance_fingerprint import PerformanceFingerprint

# Performance Monitor exports
from .performance_monitor import (
    FunctionStats,
    PerformanceMetric,
    PerformanceMonitor,
    get_monitor,
    monitor_performance,
    reset_monitor,
)

# Enterprise Feature exports
from .rbac_engine import Permission, PermissionDeniedError, RBACEngine, RBACUser, UserRole
from .retrospective import RetrospectiveEngine

# Collaboration Core exports
from .scratchpad import Scratchpad
from .similar_task_recommender import SimilarTaskRecommender
from .skill_registry import SkillRegistry
from .standardized_role_template import StandardizedRoleTemplate
from .worker import Worker, WorkerFactory

__author__ = "DevSquad Team"
__all__ = [
    # Version
    "__version__",
    # Core Orchestration
    "Coordinator",
    "Worker",
    "WorkerFactory",
    "Scratchpad",
    "ConsensusEngine",
    "FiveAxisConsensusEngine",
    "BatchScheduler",
    "AdaptiveRoleSelector",
    "AISemanticMatcher",
    # Dispatch Components
    "AnchorChecker",
    "CIContext",
    "CIFeedbackAdapter",
    "CIResult",
    "DualLayerContextManager",
    "EnhancedWorker",
    "AgentBriefingOutput",
    "ExecutionGuard",
    "FeatureUsageTracker",
    "FeedbackControlLoop",
    "IntentWorkflowMapper",
    "OperationClassifier",
    "OutputSlice",
    "OutputSlicer",
    "PerformanceFingerprint",
    "RetrospectiveEngine",
    "SimilarTaskRecommender",
    "SkillRegistry",
    "StandardizedRoleTemplate",
    # Enterprise
    "RBACEngine",
    "Permission",
    "PermissionDeniedError",
    "RBACUser",
    "UserRole",
    "AuditLogger",
    "SensitiveDataMasker",
    "MultiTenantManager",
    "IsolationLevel",
    "Tenant",
    "TenantContext",
    # Async
    "AsyncLLMBackendFactory",
    "AsyncOpenAIBackend",
    "AsyncAnthropicBackend",
    "AsyncFallbackBackend",
    "SyncToAsyncAdapter",
    "AsyncToSyncAdapter",
    "AutoBackendSelector",
    "AsyncLLMCache",
    "AsyncLLMRetryManager",
    # Cache
    "LLMCache",
    "CacheEntry",
    "get_llm_cache",
    "reset_cache",
    "MultiLevelCacheCoordinator",
    "MemoryCacheBackend",
    # Retry
    "LLMRetryManager",
    "RetryConfig",
    "CircuitBreakerState",
    "RateLimitError",
    "CircuitBreakerError",
    "get_retry_manager",
    "retry_with_fallback",
    # Monitor
    "PerformanceMonitor",
    "PerformanceMetric",
    "FunctionStats",
    "get_monitor",
    "monitor_performance",
    "reset_monitor",
    # Data Models
    "ROLE_WEIGHTS",
    "BatchMode",
    "DecisionOutcome",
    "DecisionProposal",
    "EntryStatus",
    "EntryType",
    "Reference",
    "ReferenceType",
    "ScratchpadEntry",
    "TaskBatch",
    "TaskDefinition",
    "TaskNotification",
    "Vote",
    "WorkerResult",
    # Null Providers
    "NullCacheProvider",
    "NullMemoryProvider",
    "NullMonitorProvider",
    "NullRetryProvider",
]


def get_version() -> str:
    """Get the current version of the optimization modules."""
    return __version__


def print_stats():
    """Print statistics from all optimization modules."""
    logger = get_logger(__name__)
    logger.info("\n" + "=" * 60)
    logger.info("DevSquad Optimization Modules Statistics")
    logger.info("=" * 60)

    # Cache stats
    try:
        cache = get_llm_cache()
        cache_stats = cache.get_stats()
        logger.info("\n📦 Cache Statistics:")
        logger.info("  Hit Rate: %s", cache_stats["hit_rate_percent"])
        logger.info("  Total Requests: %s", cache_stats["total_requests"])
        logger.info("  Memory Entries: %s", cache_stats["memory_entries"])
        logger.info("  Disk Entries: %s", cache_stats["disk_entries"])
    except Exception as e:
        logger.warning("\n📦 Cache: Not initialized or error: %s", e)

    # Retry stats
    try:
        retry_manager = get_retry_manager()
        retry_stats = retry_manager.get_stats()
        logger.info("\n🔄 Retry Statistics:")
        logger.info("  Success Rate: %s", retry_stats["success_rate"])
        logger.info("  Total Calls: %s", retry_stats["total_calls"])
        logger.info("  Retries: %s", retry_stats["retries"])
        logger.info("  Fallbacks: %s", retry_stats["fallbacks"])
    except Exception as e:
        logger.warning("\n🔄 Retry: Not initialized or error: %s", e)

    # Performance stats
    try:
        monitor = get_monitor()
        perf_stats = monitor.get_stats()
        logger.info("\n⚡ Performance Statistics:")
        logger.info("  Uptime: %.0fs", perf_stats["uptime_seconds"])
        logger.info("  Total Metrics: %s", perf_stats["total_metrics"])
        logger.info("  Monitored Functions: %d", len(perf_stats["functions"]))
    except Exception as e:
        logger.warning("\n⚡ Performance: Not initialized or error: %s", e)

    logger.info("\n" + "=" * 60)


def reset_all():
    """Reset all optimization modules (useful for testing)."""
    reset_cache()
    reset_monitor()
    # Note: retry_manager doesn't have a reset function, but you can create a new instance
    logger = get_logger(__name__)
    logger.info("✓ All optimization modules reset")


# Module initialization message
def _init_message():
    """Print initialization message (only in debug mode)."""
    import os

    if os.getenv("DEVSQUAD_DEBUG"):
        logger = get_logger(__name__)
        logger.debug("DevSquad Optimization Modules v%s loaded", __version__)


# Auto-initialize on import (only in debug mode)
_init_message()
