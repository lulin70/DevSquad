#!/usr/bin/env python3
"""
DevSquad Null Providers

Provides no-op implementations for all Protocol interfaces, used for:
- Degradation: auto-switch when real Provider is unavailable
- Test mocking: quick tests without real dependencies
- Development: skip certain modules to focus on core logic

Characteristics:
- All methods succeed silently, never raise exceptions
- is_available() returns False (marks as degraded implementation)
- No actual operations performed (no side effects)

Version: v1.0
Created: 2026-05-01
"""

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class NullCacheProvider:
    """
    No-op cache implementation.

    Behavior:
    - get() always returns None (cache miss)
    - set() succeeds silently, no actual storage
    - clear() succeeds silently
    - is_available() returns False
    """

    def __init__(self) -> None:
        self._call_count = 0
        logger.info("NullCacheProvider initialized (degraded mode)")

    def get(self, prompt: str, backend: str, model: str) -> str | None:  # noqa: ARG002
        """Retrieve cached response (always returns None)."""
        self._call_count += 1
        logger.debug("NullCacheProvider.get() called (miss) - call #%d", self._call_count)
        return None

    def set(self, prompt: str, response: str, backend: str, model: str, ttl: int | None = None) -> None:  # noqa: ARG002
        """Store response in cache (no-op)."""
        self._call_count += 1
        logger.debug("NullCacheProvider.set() called (no-op) - call #%d", self._call_count)

    def clear(self) -> None:
        """Clear cache (no-op)."""
        logger.debug("NullCacheProvider.clear() called (no-op)")

    def is_available(self) -> bool:
        """Check if cache is available. Returns False (degraded)."""
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return empty cache statistics."""
        return {
            "hit_count": 0,
            "miss_count": self._call_count,
            "hit_rate": 0.0,
            "total_size": 0,
            "entry_count": 0,
            "provider_type": "null",
            "degraded": True,
        }


class NullRetryProvider:
    """
    No-op retry implementation.

    Behavior:
    - retry_with_fallback() executes function directly, no retry
    - On failure, calls fallback if provided
    - is_available() returns False
    """

    def __init__(self) -> None:
        self._call_count = 0
        self._success_count = 0
        self._failure_count = 0
        self._fallback_count = 0
        logger.info("NullRetryProvider initialized (degraded mode)")

    def retry_with_fallback(
        self, func: Callable[[], Any], max_attempts: int = 3, fallback: Callable[[], Any] | None = None  # noqa: ARG002
    ) -> Any:
        """Execute function without retry. Falls back on failure."""
        self._call_count += 1

        try:
            result = func()
            self._success_count += 1
            logger.debug("NullRetryProvider: function succeeded (no retry) - call #%d", self._call_count)
            return result
        except Exception as e:
            self._failure_count += 1
            logger.debug("NullRetryProvider: function failed (no retry) - call #%d: %s", self._call_count, e)

            if fallback:
                self._fallback_count += 1
                logger.debug("NullRetryProvider: calling fallback - call #%d", self._call_count)
                return fallback()
            else:
                raise

    def is_available(self) -> bool:
        """Check if retry mechanism is available. Returns False (degraded)."""
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return retry statistics."""
        return {
            "total_attempts": self._call_count,
            "success_count": self._success_count,
            "failure_count": self._failure_count,
            "fallback_count": self._fallback_count,
            "avg_attempts": 1.0,
            "provider_type": "null",
            "degraded": True,
        }


class NullMonitorProvider:
    """
    No-op monitoring implementation.

    Behavior:
    - record_*() succeeds silently, no actual recording
    - generate_report() writes empty report
    - is_available() returns False
    """

    def __init__(self) -> None:
        self._llm_call_count = 0
        self._agent_execution_count = 0
        logger.info("NullMonitorProvider initialized (degraded mode)")

    def record_llm_call(
        self,
        backend: str,  # noqa: ARG002
        model: str,  # noqa: ARG002
        duration: float,  # noqa: ARG002
        token_count: int,  # noqa: ARG002
        success: bool,  # noqa: ARG002
        metadata: dict[str, Any] | None = None,  # noqa: ARG002
    ) -> None:
        """Record LLM call (no-op)."""
        self._llm_call_count += 1
        logger.debug("NullMonitorProvider.record_llm_call() called (no-op) - call #%d", self._llm_call_count)

    def record_agent_execution(
        self, agent_role: str, task: str, duration: float, success: bool, metadata: dict[str, Any] | None = None  # noqa: ARG002
    ) -> None:
        """Record agent execution (no-op)."""
        self._agent_execution_count += 1
        logger.debug(
            "NullMonitorProvider.record_agent_execution() called (no-op) - call #%d", self._agent_execution_count
        )

    def generate_report(self, output_path: str) -> None:
        """Generate empty performance report."""
        logger.debug("NullMonitorProvider.generate_report() called (empty report) - path: %s", output_path)
        try:
            with open(output_path, "w") as f:
                f.write("# Performance Report (Degraded Mode)\n\n")
                f.write("Monitoring is currently unavailable (NullMonitorProvider).\n")
                f.write("No performance data was collected.\n")
        except OSError as e:
            logger.warning("NullMonitorProvider: failed to write empty report: %s", e)

    def is_available(self) -> bool:
        """Check if monitoring is available. Returns False (degraded)."""
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return empty monitoring statistics."""
        return {
            "total_llm_calls": 0,
            "total_agent_executions": 0,
            "avg_llm_duration": 0.0,
            "avg_agent_duration": 0.0,
            "total_tokens": 0,
            "provider_type": "null",
            "degraded": True,
        }


class NullMemoryProvider:
    """
    No-op memory implementation.

    Behavior:
    - get_rules() returns empty list
    - add_rule() / update_rule() / delete_rule() succeed silently
    - is_available() returns False
    """

    def __init__(self) -> None:
        self._call_count = 0
        logger.info("NullMemoryProvider initialized (degraded mode)")

    def get_rules(self, user_id: str, context: dict[str, Any] | None = None) -> list[str]:  # noqa: ARG002
        """Retrieve user rules (always returns empty list)."""
        self._call_count += 1
        logger.debug("NullMemoryProvider.get_rules() called (empty) - user: %s, call #%d", user_id, self._call_count)
        return []

    def add_rule(self, user_id: str, rule: str, metadata: dict[str, Any] | None = None) -> None:  # noqa: ARG002
        """Add user rule (no-op)."""
        self._call_count += 1
        logger.debug("NullMemoryProvider.add_rule() called (no-op) - user: %s, call #%d", user_id, self._call_count)

    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None:  # noqa: ARG002
        """Update user rule (no-op)."""
        self._call_count += 1
        logger.debug(
            "NullMemoryProvider.update_rule() called (no-op) - user: %s, rule: %s, call #%d",
            user_id,
            rule_id,
            self._call_count,
        )

    def delete_rule(self, user_id: str, rule_id: str) -> None:
        """Delete user rule (no-op)."""
        self._call_count += 1
        logger.debug(
            "NullMemoryProvider.delete_rule() called (no-op) - user: %s, rule: %s, call #%d",
            user_id,
            rule_id,
            self._call_count,
        )

    def is_available(self) -> bool:
        """Check if memory system is available. Returns False (degraded)."""
        return False

    def get_stats(self) -> dict[str, Any]:
        """Return empty memory statistics."""
        return {
            "total_users": 0,
            "total_rules": 0,
            "avg_rules_per_user": 0.0,
            "provider_type": "null",
            "degraded": True,
        }

    def match_rules(
        self, task_description: str, user_id: str, role: str | None = None, max_rules: int = 5  # noqa: ARG002
    ) -> list[dict[str, Any]]:
        """Match rules based on task description (always returns empty list)."""
        self._call_count += 1
        logger.debug("NullMemoryProvider.match_rules() called (empty) - user: %s, call #%d", user_id, self._call_count)
        return []

    def format_rules_as_prompt(self, rules: list[dict[str, Any]]) -> str:  # noqa: ARG002
        """Format rules as prompt text (always returns empty string)."""
        self._call_count += 1
        logger.debug("NullMemoryProvider.format_rules_as_prompt() called (empty) - call #%d", self._call_count)
        return ""


class NullUETestProvider:
    """No-op UE test provider for graceful degradation."""

    def generate_ue_test_plan(self, project_description: str) -> None:  # noqa: ARG002
        """Generate a UE test plan (no-op, returns None).

        Args:
            project_description: Description of the project to test.
        """
        return None

    def validate_user_journey(self, journey: Any, actual_results: dict[str, Any]) -> None:  # noqa: ARG002
        """Validate a user journey against actual results (no-op).

        Args:
            journey: The expected user journey definition.
            actual_results: Dictionary of observed results to compare against.
        """
        return None

    def assess_usability(self, interface_description: str) -> None:  # noqa: ARG002
        """Assess the usability of an interface (no-op).

        Args:
            interface_description: Textual description of the interface.
        """
        return None

    def is_available(self) -> bool:
        """Check whether the UE test provider is available.

        Returns:
            Always False, indicating degraded mode.
        """
        return False


class NullTechDebtProvider:
    """No-op tech debt provider for graceful degradation."""

    def identify_debt(self, _source: str, _category: Any, _description: str,
                      _location: str, **_kwargs: Any) -> None:
        """Identify a tech debt item (no-op).

        Args:
            _source: Source of the debt identification.
            _category: Category of the tech debt.
            _description: Human-readable description of the debt.
            _location: File or module location of the debt.
            **_kwargs: Additional keyword arguments (ignored).
        """
        return None

    def scan_codebase_debt(self, project_path: str) -> list[Any]:  # noqa: ARG002
        """Scan the codebase for tech debt (no-op).

        Args:
            project_path: Root path of the project to scan.

        Returns:
            Always an empty list.
        """
        return []

    def prioritize(self) -> list[Any]:
        """Prioritize identified tech debt items (no-op).

        Returns:
            Always an empty list.
        """
        return []

    def get_debt_report(self) -> None:
        """Generate a tech debt report (no-op, returns None)."""
        return None

    def is_available(self) -> bool:
        """Check whether the tech debt provider is available.

        Returns:
            Always False, indicating degraded mode.
        """
        return False


# ============================================================================
# Factory functions
# ============================================================================


def get_null_cache() -> NullCacheProvider:
    """Get a null cache instance."""
    return NullCacheProvider()


def get_null_retry() -> NullRetryProvider:
    """Get a null retry instance."""
    return NullRetryProvider()


def get_null_monitor() -> NullMonitorProvider:
    """Get a null monitor instance."""
    return NullMonitorProvider()


def get_null_memory() -> NullMemoryProvider:
    """Get a null memory instance."""
    return NullMemoryProvider()


def get_null_ue_test() -> NullUETestProvider:
    """Get a null UE test instance."""
    return NullUETestProvider()


def get_null_tech_debt() -> NullTechDebtProvider:
    """Get a null tech debt instance."""
    return NullTechDebtProvider()


__version__ = "1.0.0"
__all__ = [
    "NullCacheProvider",
    "NullRetryProvider",
    "NullMonitorProvider",
    "NullMemoryProvider",
    "NullUETestProvider",
    "NullTechDebtProvider",
    "get_null_cache",
    "get_null_retry",
    "get_null_monitor",
    "get_null_memory",
    "get_null_ue_test",
    "get_null_tech_debt",
]
