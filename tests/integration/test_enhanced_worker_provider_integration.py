#!/usr/bin/env python3
"""EnhancedWorker Provider Injection Integration Tests (V4.2.1 P0-2 — Test Pyramid Lift).

Integration tests for EnhancedWorker with Protocol provider injection:
    cache_provider, retry_provider, monitor_provider, memory_provider

Verifies that providers are correctly injected, called during execute(),
and that NullProviders provide graceful degradation.
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.enhanced_worker import EnhancedWorker
from scripts.collaboration.models_base import TaskDefinition, WorkerResult
from scripts.collaboration.null_providers import (
    NullCacheProvider,
    NullMemoryProvider,
    NullMonitorProvider,
    NullRetryProvider,
)
from scripts.collaboration.scratchpad import Scratchpad


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_mock_llm_backend() -> Any:
    """Create a Mock LLM backend whose generate() returns 'Mock LLM output'."""
    backend = mock.MagicMock()
    backend.generate.return_value = "Mock LLM output"
    backend.model = "mock-model"
    return backend


def _make_task(**kwargs: Any) -> TaskDefinition:
    """Create a minimal TaskDefinition for testing."""
    defaults: dict[str, Any] = {
        "description": "Design a simple API endpoint",
        "role_id": "architect",
    }
    defaults.update(kwargs)
    return TaskDefinition(**defaults)


class _ProviderTestBase(unittest.TestCase):
    """Base class with shared setUp for EnhancedWorker integration tests.

    Patches the global LLM cache so each test calls the mock LLM backend
    directly (prevents cross-test cache hits from short-circuiting the
    backend.generate() call).
    """

    def setUp(self) -> None:
        self.scratchpad = Scratchpad()
        self.llm_backend = _make_mock_llm_backend()
        self.task = _make_task()
        # Patch global LLM cache to always miss — ensures backend.generate()
        # is invoked every time (avoids cache hits masking provider calls).
        cache_patcher = mock.patch("scripts.collaboration.llm_cache.get_llm_cache")
        mock_cache_fn = cache_patcher.start()
        mock_cache_fn.return_value.get.return_value = None
        self.addCleanup(cache_patcher.stop)

    def _make_worker(self, **kwargs: Any) -> EnhancedWorker:
        """Build an EnhancedWorker with sensible defaults; callers override providers."""
        defaults: dict[str, Any] = {
            "worker_id": "w1",
            "role_id": "architect",
            "scratchpad": self.scratchpad,
            "llm_backend": self.llm_backend,
        }
        defaults.update(kwargs)
        return EnhancedWorker(**defaults)


# ---------------------------------------------------------------------------
# T1: Provider Injection Basics
# ---------------------------------------------------------------------------


class T1_ProviderInjectionBasics(_ProviderTestBase):
    """Verify providers are stored as instance attributes after injection."""

    def test_cache_provider_stored(self) -> None:
        """Verify: cache_provider is stored as self.cache_provider."""
        cache = mock.MagicMock()
        worker = self._make_worker(cache_provider=cache)
        self.assertIs(worker.cache_provider, cache)

    def test_retry_provider_stored(self) -> None:
        """Verify: retry_provider is stored as self.retry_provider."""
        retry = mock.MagicMock()
        worker = self._make_worker(retry_provider=retry)
        self.assertIs(worker.retry_provider, retry)

    def test_monitor_provider_stored(self) -> None:
        """Verify: monitor_provider is stored as self.monitor_provider."""
        monitor = mock.MagicMock()
        worker = self._make_worker(monitor_provider=monitor)
        self.assertIs(worker.monitor_provider, monitor)

    def test_memory_provider_stored(self) -> None:
        """Verify: memory_provider is stored as self.memory_provider."""
        memory = mock.MagicMock()
        worker = self._make_worker(memory_provider=memory)
        self.assertIs(worker.memory_provider, memory)

    def test_all_providers_stored_together(self) -> None:
        """Verify: all four providers are stored simultaneously."""
        cache, retry, monitor, memory = (
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        )
        worker = self._make_worker(
            cache_provider=cache,
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        self.assertIs(worker.cache_provider, cache)
        self.assertIs(worker.retry_provider, retry)
        self.assertIs(worker.monitor_provider, monitor)
        self.assertIs(worker.memory_provider, memory)


# ---------------------------------------------------------------------------
# T2: NullProviders Graceful Degradation
# ---------------------------------------------------------------------------


class T2_NullProvidersGracefulDegrade(_ProviderTestBase):
    """Verify NullProviders provide graceful degradation during execute()."""

    def test_null_cache_does_not_crash(self) -> None:
        """Verify: execute() does not crash with NullCacheProvider."""
        worker = self._make_worker(cache_provider=NullCacheProvider())
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)

    def test_null_retry_does_not_crash(self) -> None:
        """Verify: execute() does not crash with NullRetryProvider."""
        worker = self._make_worker(retry_provider=NullRetryProvider())
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)

    def test_null_monitor_does_not_crash(self) -> None:
        """Verify: execute() does not crash with NullMonitorProvider."""
        worker = self._make_worker(monitor_provider=NullMonitorProvider())
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)

    def test_null_memory_does_not_crash(self) -> None:
        """Verify: execute() does not crash with NullMemoryProvider."""
        worker = self._make_worker(memory_provider=NullMemoryProvider())
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)

    def test_all_null_providers_execute_succeeds(self) -> None:
        """Verify: execute() succeeds with all NullProviders injected."""
        worker = self._make_worker(
            cache_provider=NullCacheProvider(),
            retry_provider=NullRetryProvider(),
            monitor_provider=NullMonitorProvider(),
            memory_provider=NullMemoryProvider(),
        )
        result = worker.execute(self.task)
        self.assertTrue(result.success)


# ---------------------------------------------------------------------------
# T3: RetryProvider Integration
# ---------------------------------------------------------------------------


class T3_RetryProviderIntegration(_ProviderTestBase):
    """Verify retry_provider is consulted during execute()."""

    def test_retry_with_fallback_called_when_available(self) -> None:
        """Verify: retry_with_fallback is called when is_available() returns True."""
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        retry.retry_with_fallback.side_effect = lambda func, **_: func()
        worker = self._make_worker(retry_provider=retry)
        worker.execute(self.task)
        retry.retry_with_fallback.assert_called_once()

    def test_retry_not_called_when_unavailable(self) -> None:
        """Verify: retry_with_fallback is NOT called when is_available() returns False."""
        retry = mock.MagicMock()
        retry.is_available.return_value = False
        worker = self._make_worker(retry_provider=retry)
        worker.execute(self.task)
        retry.retry_with_fallback.assert_not_called()

    def test_retry_fallback_invoked_on_failure(self) -> None:
        """Verify: retry_with_fallback is called even when the primary func raises."""
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        retry.retry_with_fallback.side_effect = lambda func, **_: func()
        # Force _do_work_with_briefing to fail by making LLM raise
        self.llm_backend.generate.side_effect = RuntimeError("LLM down")
        worker = self._make_worker(retry_provider=retry)
        result = worker.execute(self.task)
        retry.retry_with_fallback.assert_called_once()
        # Fallback path (_do_work_simple) returns a failed WorkerResult
        self.assertIsInstance(result, WorkerResult)
        self.assertFalse(result.success)

    def test_retry_max_attempts_passed(self) -> None:
        """Verify: max_attempts=3 is forwarded to retry_with_fallback."""
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        retry.retry_with_fallback.side_effect = lambda func, **_: func()
        worker = self._make_worker(retry_provider=retry)
        worker.execute(self.task)
        _, kwargs = retry.retry_with_fallback.call_args
        self.assertEqual(kwargs.get("max_attempts"), 3)

    def test_retry_returns_worker_result(self) -> None:
        """Verify: execute() returns a WorkerResult when retry is active."""
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        retry.retry_with_fallback.side_effect = lambda func, **_: func()
        worker = self._make_worker(retry_provider=retry)
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)


# ---------------------------------------------------------------------------
# T4: MonitorProvider Integration
# ---------------------------------------------------------------------------


class T4_MonitorProviderIntegration(_ProviderTestBase):
    """Verify monitor_provider records agent executions during execute()."""

    def test_record_called_on_success(self) -> None:
        """Verify: record_agent_execution is called with success=True on success."""
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        worker = self._make_worker(monitor_provider=monitor)
        worker.execute(self.task)
        monitor.record_agent_execution.assert_called_once()
        _, kwargs = monitor.record_agent_execution.call_args
        self.assertTrue(kwargs.get("success"))

    def test_record_not_called_when_unavailable(self) -> None:
        """Verify: record_agent_execution is NOT called when is_available() is False."""
        monitor = mock.MagicMock()
        monitor.is_available.return_value = False
        worker = self._make_worker(monitor_provider=monitor)
        worker.execute(self.task)
        monitor.record_agent_execution.assert_not_called()

    def test_record_called_on_failure(self) -> None:
        """Verify: record_agent_execution is called with success=False on failure."""
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        # Use a unique task description to avoid cache interference
        task = _make_task(description="Trigger monitor failure path unique xyz")
        self.llm_backend.generate.side_effect = RuntimeError("LLM exploded")
        worker = self._make_worker(monitor_provider=monitor)
        try:
            worker.execute(task)
        except Exception:
            pass
        monitor.record_agent_execution.assert_called_once()
        _, kwargs = monitor.record_agent_execution.call_args
        self.assertFalse(kwargs.get("success"))

    def test_record_args_contain_role(self) -> None:
        """Verify: record_agent_execution receives agent_role matching worker's role_id."""
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        worker = self._make_worker(role_id="architect", monitor_provider=monitor)
        worker.execute(self.task)
        _, kwargs = monitor.record_agent_execution.call_args
        self.assertEqual(kwargs.get("agent_role"), "architect")

    def test_record_args_contain_task_description(self) -> None:
        """Verify: record_agent_execution receives task description (truncated to 100)."""
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        long_desc = "X" * 200
        task = _make_task(description=long_desc)
        worker = self._make_worker(monitor_provider=monitor)
        worker.execute(task)
        _, kwargs = monitor.record_agent_execution.call_args
        self.assertEqual(kwargs.get("task"), long_desc[:100])


# ---------------------------------------------------------------------------
# T5: MemoryProvider Integration
# ---------------------------------------------------------------------------


class T5_MemoryProviderIntegration(_ProviderTestBase):
    """Verify memory_provider is consulted for rule injection during execute()."""

    def test_match_rules_called_when_available(self) -> None:
        """Verify: match_rules is called when memory_provider.is_available() is True."""
        memory = mock.MagicMock()
        memory.is_available.return_value = True
        memory.match_rules.return_value = []
        worker = self._make_worker(memory_provider=memory)
        worker.execute(self.task)
        memory.match_rules.assert_called_once()

    def test_match_rules_not_called_when_unavailable(self) -> None:
        """Verify: match_rules is NOT called when is_available() returns False."""
        memory = mock.MagicMock()
        memory.is_available.return_value = False
        worker = self._make_worker(memory_provider=memory)
        worker.execute(self.task)
        memory.match_rules.assert_not_called()

    def test_get_rules_called_when_no_match_method(self) -> None:
        """Verify: get_rules is called when match_rules is not present on provider."""
        # Use spec to exclude match_rules from the mock's interface
        memory = mock.MagicMock(
            spec=["is_available", "get_rules", "get_stats", "format_rules_as_prompt"]
        )
        memory.is_available.return_value = True
        memory.get_rules.return_value = ["Use SSL for all connections"]
        worker = self._make_worker(memory_provider=memory)
        worker.execute(self.task)
        memory.get_rules.assert_called_once()

    def test_injected_rules_populated_from_match(self) -> None:
        """Verify: _injected_rules is populated from match_rules return value."""
        memory = mock.MagicMock()
        memory.is_available.return_value = True
        memory.match_rules.return_value = [
            {
                "rule_type": "always",
                "action": "Use SSL for all connections",
                "trigger": "database",
                "rule_id": "r1",
            },
        ]
        worker = self._make_worker(memory_provider=memory)
        worker.execute(self.task)
        self.assertEqual(len(worker._injected_rules), 1)
        self.assertEqual(worker._injected_rules[0]["rule_id"], "r1")

    def test_rules_applied_tracked(self) -> None:
        """Verify: _rules_applied tracks rule_ids from injected rules."""
        memory = mock.MagicMock()
        memory.is_available.return_value = True
        memory.match_rules.return_value = [
            {
                "rule_type": "always",
                "action": "Use SSL for all connections",
                "trigger": "database",
                "rule_id": "r1",
            },
            {
                "rule_type": "forbid",
                "action": "Never log passwords",
                "trigger": "password",
                "rule_id": "r2",
            },
        ]
        worker = self._make_worker(memory_provider=memory)
        worker.execute(self.task)
        self.assertIn("r1", worker._rules_applied)
        self.assertIn("r2", worker._rules_applied)


# ---------------------------------------------------------------------------
# T6: CacheProvider Integration
# ---------------------------------------------------------------------------


class T6_CacheProviderIntegration(_ProviderTestBase):
    """Verify cache_provider is injected and reported in provider status.

    Note: EnhancedWorker stores cache_provider and exposes it via
    get_provider_status(). The active LLM caching path goes through
    ``content_cache`` (a separate Worker param) and the global llm_cache;
    ``cache_provider`` is reported in status but not actively called during
    execute(). These tests verify the injection and status-reporting
    integration points.
    """

    def test_cache_provider_stored_as_attribute(self) -> None:
        """Verify: cache_provider is stored as an instance attribute."""
        cache = mock.MagicMock()
        worker = self._make_worker(cache_provider=cache)
        self.assertIs(worker.cache_provider, cache)

    def test_cache_available_reflected_in_status(self) -> None:
        """Verify: get_provider_status() reports cache availability from is_available()."""
        cache = mock.MagicMock()
        cache.is_available.return_value = True
        worker = self._make_worker(cache_provider=cache)
        status = worker.get_provider_status()
        self.assertTrue(status["cache"]["available"])

    def test_cache_unavailable_reflected_in_status(self) -> None:
        """Verify: get_provider_status() reports False when cache is_available() is False."""
        cache = mock.MagicMock()
        cache.is_available.return_value = False
        worker = self._make_worker(cache_provider=cache)
        status = worker.get_provider_status()
        self.assertFalse(status["cache"]["available"])

    def test_null_cache_shows_unavailable_in_status(self) -> None:
        """Verify: NullCacheProvider shows unavailable in provider status."""
        worker = self._make_worker(cache_provider=NullCacheProvider())
        status = worker.get_provider_status()
        self.assertFalse(status["cache"]["available"])
        self.assertEqual(status["cache"]["type"], "NullCacheProvider")

    def test_execute_does_not_crash_with_cache_provider(self) -> None:
        """Verify: execute() completes without crashing with a cache_provider injected."""
        cache = mock.MagicMock()
        cache.is_available.return_value = True
        worker = self._make_worker(cache_provider=cache)
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)


# ---------------------------------------------------------------------------
# T7: Multiple Providers Combined
# ---------------------------------------------------------------------------


class T7_MultipleProvidersCombined(_ProviderTestBase):
    """Verify combined behavior when multiple providers are injected together."""

    def test_all_providers_stored(self) -> None:
        """Verify: all four mock providers are stored simultaneously."""
        cache, retry, monitor, memory = (
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
            mock.MagicMock(),
        )
        worker = self._make_worker(
            cache_provider=cache,
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        self.assertIs(worker.cache_provider, cache)
        self.assertIs(worker.retry_provider, retry)
        self.assertIs(worker.monitor_provider, monitor)
        self.assertIs(worker.memory_provider, memory)

    def test_all_active_providers_called_during_execute(self) -> None:
        """Verify: retry, monitor, and memory providers are all called during execute()."""
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        retry.retry_with_fallback.side_effect = lambda func, **_: func()
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        memory = mock.MagicMock()
        memory.is_available.return_value = True
        memory.match_rules.return_value = []
        worker = self._make_worker(
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        worker.execute(self.task)
        retry.retry_with_fallback.assert_called_once()
        monitor.record_agent_execution.assert_called_once()
        memory.match_rules.assert_called_once()

    def test_combined_status_report(self) -> None:
        """Verify: get_provider_status() reports all four providers as available."""
        cache = mock.MagicMock()
        cache.is_available.return_value = True
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        memory = mock.MagicMock()
        memory.is_available.return_value = True
        worker = self._make_worker(
            cache_provider=cache,
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        status = worker.get_provider_status()
        self.assertTrue(status["cache"]["available"])
        self.assertTrue(status["retry"]["available"])
        self.assertTrue(status["monitor"]["available"])
        self.assertTrue(status["memory"]["available"])

    def test_mixed_null_and_mock_providers(self) -> None:
        """Verify: a mix of Null and Mock providers coexist without crashing."""
        worker = self._make_worker(
            cache_provider=NullCacheProvider(),
            retry_provider=NullRetryProvider(),
            monitor_provider=mock.MagicMock(),
            memory_provider=mock.MagicMock(),
        )
        result = worker.execute(self.task)
        self.assertIsInstance(result, WorkerResult)

    def test_execute_with_all_mocks_succeeds(self) -> None:
        """Verify: execute() succeeds with all four mock providers injected."""
        retry = mock.MagicMock()
        retry.is_available.return_value = True
        retry.retry_with_fallback.side_effect = lambda func, **_: func()
        monitor = mock.MagicMock()
        monitor.is_available.return_value = True
        memory = mock.MagicMock()
        memory.is_available.return_value = True
        memory.match_rules.return_value = []
        worker = self._make_worker(
            cache_provider=mock.MagicMock(),
            retry_provider=retry,
            monitor_provider=monitor,
            memory_provider=memory,
        )
        result = worker.execute(self.task)
        self.assertTrue(result.success)


if __name__ == "__main__":
    unittest.main()
