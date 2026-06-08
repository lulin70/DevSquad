#!/usr/bin/env python3
"""
DevSquad Protocol Interface Definitions

Defines abstract interfaces (Protocol) for core DevSquad modules, supporting:
- Multiple implementations (Redis, filesystem, memory, etc.)
- Degradation mechanism (Null Provider)
- Dependency injection and test mocking
- Runtime availability detection

Based on Python 3.8+ typing.Protocol (structural subtyping).

Version: v1.0
Created: 2026-05-01
"""

from collections.abc import Callable
from typing import Any, Protocol

# ============================================================================
# CacheProvider: LLM response cache interface
# ============================================================================

# NOTE: CacheProvider is the high-level LLM cache interface used by the dispatch pipeline.
# CacheBackendInterface (in cache_interface.py) is the low-level storage interface used by
# the multi-level cache coordinator. They serve different layers:
# - CacheProvider: business-level (prompt → response caching)
# - CacheBackendInterface: storage-level (key → value caching)
# Do NOT merge these — they are intentionally separate abstractions.


class CacheProvider(Protocol):
    """
    LLM response cache interface.

    Use cases:
    - Cache LLM API responses to reduce duplicate calls
    - Support multiple backends (filesystem, Redis, memory, etc.)
    - Provide TTL expiration mechanism

    Implementations:
    - LLMCache (filesystem-based)
    - RedisCache (Redis-based)
    - MemoryCache (in-memory)
    - NullCacheProvider (no-op, for degradation)
    """

    def get(self, prompt: str, backend: str, model: str) -> str | None:
        """Retrieve cached response. Returns None on cache miss."""
        ...

    def set(self, prompt: str, response: str, backend: str, model: str, ttl: int | None = None) -> None:
        """Store response in cache. ttl is optional expiration in seconds."""
        ...

    def clear(self) -> None:
        """Clear all cached entries."""
        ...

    def is_available(self) -> bool:
        """Check if cache is available. False triggers degradation."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return cache statistics (hit_count, miss_count, hit_rate, etc.)."""
        ...


# ============================================================================
# RetryProvider: LLM call retry interface
# ============================================================================


class RetryProvider(Protocol):
    """
    LLM call retry interface.

    Use cases:
    - Handle LLM API transient failures (network timeout, rate limiting, etc.)
    - Support exponential backoff strategies
    - Provide fallback mechanism

    Implementations:
    - LLMRetry (tenacity-based)
    - SimpleRetry (simple retry)
    - NullRetryProvider (no-op, for degradation)
    """

    def retry_with_fallback(
        self, func: Callable[[], Any], max_attempts: int = 3, fallback: Callable[[], Any] | None = None
    ) -> Any:
        """Execute function with retry. Falls back to fallback if all attempts fail."""
        ...

    def is_available(self) -> bool:
        """Check if retry mechanism is available."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return retry statistics (total_attempts, success_count, etc.)."""
        ...


# ============================================================================
# MonitorProvider: Performance monitoring interface
# ============================================================================


class MonitorProvider(Protocol):
    """
    Performance monitoring interface.

    Use cases:
    - Record LLM call performance metrics
    - Generate performance reports
    - Support multiple backends (file, database, monitoring system)

    Implementations:
    - PerformanceMonitor (file-based)
    - PrometheusMonitor (Prometheus-based)
    - NullMonitorProvider (no-op, for degradation)
    """

    def record_llm_call(
        self,
        backend: str,
        model: str,
        duration: float,
        token_count: int,
        success: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM API call."""
        ...

    def record_agent_execution(
        self, agent_role: str, task: str, duration: float, success: bool, metadata: dict[str, Any] | None = None
    ) -> None:
        """Record an agent execution."""
        ...

    def generate_report(self, output_path: str) -> None:
        """Generate performance report to output_path."""
        ...

    def is_available(self) -> bool:
        """Check if monitoring is available."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return monitoring statistics (total_llm_calls, avg_duration, etc.)."""
        ...


# ============================================================================
# MemoryProvider: Personalization memory interface
# ============================================================================


class MemoryProvider(Protocol):
    """
    Personalization memory interface.

    Use cases:
    - Store and retrieve user preferences and rules
    - Support external memory systems (e.g., CarryMem)
    - Inject rules into agent prompts

    Implementations:
    - CarryMemAdapter (CarryMem integration)
    - LocalMemory (local file storage)
    - NullMemoryProvider (no-op, for degradation)
    """

    def get_rules(self, user_id: str, context: dict[str, Any] | None = None) -> list[str]:
        """Retrieve user rules. Returns list of rule strings."""
        ...

    def add_rule(self, user_id: str, rule: str, metadata: dict[str, Any] | None = None) -> None:
        """Add a user rule."""
        ...

    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None:
        """Update an existing user rule."""
        ...

    def delete_rule(self, user_id: str, rule_id: str) -> None:
        """Delete a user rule."""
        ...

    def is_available(self) -> bool:
        """Check if memory system is available."""
        ...

    def get_stats(self) -> dict[str, Any]:
        """Return memory statistics (total_users, total_rules, etc.)."""
        ...

    def match_rules(
        self, task_description: str, user_id: str, role: str | None = None, max_rules: int = 5
    ) -> list[dict[str, Any]]:
        """Match rules based on task description and role.

        Returns list of rule dicts with keys:
        - rule_type: str (forbid/avoid/always)
        - trigger: str (condition that activates the rule)
        - action: str (what the rule requires)
        - relevance_score: float (0.0-1.0)
        - rule_id: str (unique identifier)
        - override: bool (whether rule cannot be overridden)
        """
        ...

    def format_rules_as_prompt(self, rules: list[dict[str, Any]]) -> str:
        """Format matched rules as injectable prompt text.

        Args:
            rules: List of rule dicts from match_rules()

        Returns:
            Formatted string ready for prompt injection, or empty string if no rules.
        """
        ...


# ============================================================================
# Exception definitions
# ============================================================================


class ProviderError(Exception):
    """Base exception for all provider errors."""

    pass


class CacheError(ProviderError):
    """Cache operation error."""

    pass


class RetryError(ProviderError):
    """Retry operation error."""

    pass


class MonitorError(ProviderError):
    """Monitor operation error."""

    pass


class MemoryProviderError(ProviderError):
    """Memory provider operation error."""

    pass


# ============================================================================
# Version info
# ============================================================================

__version__ = "1.0.0"
__all__ = [
    "CacheProvider",
    "RetryProvider",
    "MonitorProvider",
    "MemoryProvider",
    "ProviderError",
    "CacheError",
    "RetryError",
    "MonitorError",
    "MemoryProviderError",
]
