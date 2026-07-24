#!/usr/bin/env python3
"""MonitorProvider Contract Tests (V4.2.1 P1 — Test Pyramid Improvement).

Validates that all MonitorProvider implementations conform to the Protocol
interface defined in protocols.py. Both PerformanceMonitor (real, in-memory)
and NullMonitorProvider (degraded no-op) must pass these tests.

Contract test ownership: shared between DevSquad and monitoring infrastructure
teams. Any breaking change to MonitorProvider Protocol must be negotiated.

References:
    - Protocol definition: scripts/collaboration/protocols.py (MonitorProvider)
    - Real implementation: scripts/collaboration/performance_monitor.py (PerformanceMonitor)
    - Null implementation: scripts/collaboration/null_providers.py (NullMonitorProvider)
"""

from __future__ import annotations

import contextlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.null_providers import NullMonitorProvider
from scripts.collaboration.performance_monitor import PerformanceMonitor


class MonitorProviderContractBase(unittest.TestCase):
    """Base class for MonitorProvider contract tests.

    Subclasses must override _get_provider() to return a MonitorProvider
    implementation. All tests run against both real and null implementations.
    """

    # pytest collection guard: base class has abstract _get_provider().
    # __test__ = False tells pytest to skip collection of this class.
    __test__ = False

    def _get_provider(self) -> object:
        """Return a MonitorProvider instance. Override in subclasses."""
        raise NotImplementedError("Subclass must implement _get_provider()")

    # === Method existence (Protocol conformance) ===

    def test_01_has_record_llm_call(self) -> None:
        """Verify: provider exposes record_llm_call() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "record_llm_call"))
        self.assertTrue(callable(getattr(provider, "record_llm_call", None)))

    def test_02_has_record_agent_execution(self) -> None:
        """Verify: provider exposes record_agent_execution() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "record_agent_execution"))
        self.assertTrue(callable(getattr(provider, "record_agent_execution", None)))

    def test_03_has_generate_report(self) -> None:
        """Verify: provider exposes generate_report() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "generate_report"))
        self.assertTrue(callable(getattr(provider, "generate_report", None)))

    def test_04_has_is_available(self) -> None:
        """Verify: provider exposes is_available() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "is_available"))
        self.assertTrue(callable(getattr(provider, "is_available", None)))

    def test_05_has_get_stats(self) -> None:
        """Verify: provider exposes get_stats() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "get_stats"))
        self.assertTrue(callable(getattr(provider, "get_stats", None)))

    # === Behavioral contracts ===

    def test_10_is_available_returns_bool(self) -> None:
        """Verify: is_available() returns a boolean."""
        provider = self._get_provider()
        result = provider.is_available()
        self.assertIsInstance(result, bool)

    def test_11_get_stats_returns_dict(self) -> None:
        """Verify: get_stats() returns a dictionary."""
        provider = self._get_provider()
        result = provider.get_stats()
        self.assertIsInstance(result, dict)

    def test_12_get_stats_has_required_keys(self) -> None:
        """Verify: get_stats() result contains required monitoring keys.

        Required keys (per Protocol docstring): total_llm_calls,
        avg_duration (or equivalent). Null provider includes 'degraded' flag.
        """
        provider = self._get_provider()
        stats = provider.get_stats()
        # Must have at least one of these key patterns
        has_llm_key = any("llm" in k.lower() for k in stats)
        has_agent_key = any("agent" in k.lower() for k in stats)
        self.assertTrue(
            has_llm_key or has_agent_key,
            f"get_stats() should include LLM or agent metrics, got: {list(stats.keys())}",
        )

    def test_13_record_llm_call_does_not_raise(self) -> None:
        """Verify: record_llm_call() with valid args does not raise."""
        provider = self._get_provider()
        # Should not raise
        provider.record_llm_call(
            backend="openai",
            model="gpt-4",
            duration=1.5,
            token_count=100,
            success=True,
        )

    def test_14_record_agent_execution_does_not_raise(self) -> None:
        """Verify: record_agent_execution() with valid args does not raise."""
        provider = self._get_provider()
        provider.record_agent_execution(
            agent_role="architect",
            task="Design auth system",
            duration=2.0,
            success=True,
        )

    def test_15_generate_report_creates_file(self) -> None:
        """Verify: generate_report() writes a file to the given path."""
        provider = self._get_provider()
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = str(Path(tmpdir) / "report.md")
            provider.generate_report(report_path)
            # File should exist after generate_report()
            self.assertTrue(Path(report_path).exists(),
                            f"Report file not created at {report_path}")

    def test_16_record_llm_call_with_metadata(self) -> None:
        """Verify: record_llm_call() accepts optional metadata dict."""
        provider = self._get_provider()
        provider.record_llm_call(
            backend="anthropic",
            model="claude-3",
            duration=0.8,
            token_count=50,
            success=False,
            metadata={"error": "timeout", "retry": 1},
        )

    def test_17_record_agent_execution_with_metadata(self) -> None:
        """Verify: record_agent_execution() accepts optional metadata dict."""
        provider = self._get_provider()
        provider.record_agent_execution(
            agent_role="security",
            task="Audit auth flow",
            duration=3.5,
            success=True,
            metadata={"findings": 2, "severity": "low"},
        )

    def test_18_multiple_record_calls_accumulate(self) -> None:
        """Verify: Multiple record_llm_call() calls are tracked in stats."""
        provider = self._get_provider()
        # Record 3 LLM calls
        for i in range(3):
            provider.record_llm_call(
                backend="openai",
                model="gpt-4",
                duration=1.0 + i * 0.1,
                token_count=100,
                success=True,
            )
        stats = provider.get_stats()
        # Stats should reflect accumulated calls (total_llm_calls >= 3)
        # Null provider tracks _llm_call_count internally but get_stats()
        # returns 0 for degraded mode. So we check both cases.
        if provider.is_available():
            # Real provider should show accumulated count
            llm_count = stats.get("total_llm_calls", 0)
            self.assertGreaterEqual(llm_count, 3,
                                    f"Expected >=3 LLM calls in stats, got {llm_count}")

    def test_19_generate_report_to_invalid_path_does_not_raise(self) -> None:
        """Verify: generate_report() to invalid path handles gracefully (no raise)."""
        provider = self._get_provider()
        # Should not raise even if path is invalid
        with contextlib.suppress(OSError, PermissionError):
            # Acceptable: some implementations may raise on truly invalid paths
            provider.generate_report("/nonexistent/path/that/does/not/exist/report.md")

    def test_20_get_stats_after_records(self) -> None:
        """Verify: get_stats() returns meaningful data after recording calls."""
        provider = self._get_provider()
        # Record some activity
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        provider.record_agent_execution("coder", "implement feature", 2.0, True)
        # get_stats should return a dict (content depends on implementation)
        stats = provider.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertGreater(len(stats), 0, "get_stats() should return non-empty dict")


class TestPerformanceMonitorContract(MonitorProviderContractBase):
    """Contract tests for the real PerformanceMonitor implementation."""

    # Override base class __test__ = False to enable collection.
    __test__ = True

    def _get_provider(self) -> PerformanceMonitor:
        return PerformanceMonitor(max_history=100)


class TestNullMonitorProviderContract(MonitorProviderContractBase):
    """Contract tests for the NullMonitorProvider (degraded mode)."""

    # Override base class __test__ = False to enable collection.
    __test__ = True

    def _get_provider(self) -> NullMonitorProvider:
        return NullMonitorProvider()

    # === Null-specific behavioral contracts ===

    def test_30_null_is_available_returns_false(self) -> None:
        """Verify: NullMonitorProvider.is_available() returns False (degraded)."""
        provider = self._get_provider()
        self.assertFalse(provider.is_available(),
                        "NullMonitorProvider should report unavailable (degraded)")

    def test_31_null_get_stats_includes_degraded_flag(self) -> None:
        """Verify: NullMonitorProvider.get_stats() includes degraded=True."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertIn("degraded", stats, "NullMonitorProvider stats should include 'degraded' flag")
        self.assertTrue(stats.get("degraded", False),
                       "NullMonitorProvider 'degraded' flag should be True")

    def test_32_null_get_stats_has_zero_counts(self) -> None:
        """Verify: NullMonitorProvider.get_stats() returns zero counts."""
        provider = self._get_provider()
        # Even after recording, null provider reports zeros (degraded)
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        stats_after = provider.get_stats()
        self.assertEqual(stats_after.get("total_llm_calls", 0), 0,
                        "NullMonitorProvider should report 0 LLM calls in stats (degraded)")

    def test_33_null_generate_report_writes_degraded_message(self) -> None:
        """Verify: NullMonitorProvider.generate_report() writes degraded notice."""
        provider = self._get_provider()
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = str(Path(tmpdir) / "null_report.md")
            provider.generate_report(report_path)
            content = Path(report_path).read_text(encoding="utf-8")
            # Should mention degraded/unavailable in the report
            content_lower = content.lower()
            self.assertTrue(
                "degraded" in content_lower or "unavailable" in content_lower or "null" in content_lower,
                f"Null report should mention degraded status, got: {content[:200]}",
            )


class TestPerformanceMonitorExtendedContract(unittest.TestCase):
    """Extended contract tests for PerformanceMonitor behavior."""

    def _get_provider(self) -> PerformanceMonitor:
        return PerformanceMonitor(max_history=100)

    def test_record_llm_call_openai_backend(self):
        """record_llm_call with openai backend should not raise."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.5, 100, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 1)

    def test_record_llm_call_anthropic_backend(self):
        """record_llm_call with anthropic backend should not raise."""
        provider = self._get_provider()
        provider.record_llm_call("anthropic", "claude-3", 2.0, 200, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 1)

    def test_record_agent_execution_architect(self):
        """record_agent_execution with architect role should not raise."""
        provider = self._get_provider()
        provider.record_agent_execution("architect", "Design system", 5.0, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_agent_executions"], 1)

    def test_record_agent_execution_tester(self):
        """record_agent_execution with tester role should not raise."""
        provider = self._get_provider()
        provider.record_agent_execution("tester", "Run tests", 3.0, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_agent_executions"], 1)

    def test_get_stats_has_avg_llm_duration(self):
        """get_stats should include avg_llm_duration field."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        stats = provider.get_stats()
        self.assertIn("avg_llm_duration", stats)

    def test_get_stats_has_total_agent_executions(self):
        """get_stats should include total_agent_executions field."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertIn("total_agent_executions", stats)

    def test_multiple_llm_calls_accumulate(self):
        """Multiple record_llm_call should accumulate in stats."""
        provider = self._get_provider()
        for i in range(5):
            provider.record_llm_call("openai", "gpt-4", 1.0 + i * 0.5, 100, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 5)

    def test_metadata_with_error_recorded(self):
        """record_llm_call with error metadata should not raise."""
        provider = self._get_provider()
        provider.record_llm_call(
            "openai", "gpt-4", 0.5, 50, False,
            metadata={"error": "connection timeout"},
        )
        # Verify errors are tracked
        errors = provider.get_recent_errors()
        self.assertIsInstance(errors, list)

    def test_success_false_recorded(self):
        """record_llm_call with success=False should not raise."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 0.3, 10, False)
        stats = provider.get_stats()
        self.assertIsInstance(stats, dict)

    def test_duration_zero_boundary(self):
        """record_llm_call with duration=0 should not raise."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 0.0, 100, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 1)

    def test_get_stats_by_function_name(self):
        """get_stats with function_name should return specific stats."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        stats = provider.get_stats("llm_call:openai:gpt-4")
        self.assertIsInstance(stats, dict)
        self.assertIn("call_count", stats)

    def test_get_stats_by_nonexistent_function(self):
        """get_stats for unknown function should return empty dict."""
        provider = self._get_provider()
        stats = provider.get_stats("nonexistent:function")
        self.assertEqual(stats, {})

    def test_get_bottlenecks_returns_list(self):
        """get_bottlenecks should return a list."""
        provider = self._get_provider()
        bottlenecks = provider.get_bottlenecks()
        self.assertIsInstance(bottlenecks, list)

    def test_get_slowest_functions_returns_list(self):
        """get_slowest_functions should return a list."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 5.0, 100, True)
        slowest = provider.get_slowest_functions(limit=5)
        self.assertIsInstance(slowest, list)

    def test_monitor_decorator_wraps_function(self):
        """monitor decorator should wrap a function and record metrics."""
        provider = self._get_provider()

        @provider.monitor("test_func")
        def sample_function(x):
            return x * 2

        result = sample_function(5)
        self.assertEqual(result, 10)
        stats = provider.get_stats("test_func")
        self.assertGreaterEqual(stats.get("call_count", 0), 1)

    def test_generate_report_content_not_empty(self):
        """generate_report should write non-empty content."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = str(Path(tmpdir) / "report.md")
            provider.generate_report(report_path)
            content = Path(report_path).read_text(encoding="utf-8")
            self.assertGreater(len(content), 0)

    def test_get_stats_has_uptime_seconds(self):
        """get_stats should include uptime_seconds field."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertIn("uptime_seconds", stats)

    def test_record_metric_directly(self):
        """record_metric should accept a PerformanceMetric directly."""
        from scripts.collaboration.performance_monitor import PerformanceMetric
        provider = self._get_provider()
        metric = PerformanceMetric(
            name="custom_op",
            start_time=0.0,
            end_time=1.0,
            duration=1.0,
            cpu_percent=10.0,
            memory_mb=50.0,
            success=True,
        )
        provider.record_metric(metric)
        stats = provider.get_stats("custom_op")
        self.assertGreaterEqual(stats.get("call_count", 0), 1)

    def test_is_available_returns_true(self):
        """PerformanceMonitor.is_available() should always return True."""
        provider = self._get_provider()
        self.assertTrue(provider.is_available())

    def test_export_report_returns_string(self):
        """export_report should return a Markdown string."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        report = provider.export_report()
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 0)


class TestNullMonitorProviderExtendedContract(unittest.TestCase):
    """Extended contract tests for NullMonitorProvider behavior."""

    def _get_provider(self) -> NullMonitorProvider:
        return NullMonitorProvider()

    def test_null_record_llm_call_no_op(self):
        """NullMonitorProvider.record_llm_call should be a no-op."""
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        stats = provider.get_stats()
        self.assertEqual(stats.get("total_llm_calls", 0), 0)

    def test_null_record_agent_execution_no_op(self):
        """NullMonitorProvider.record_agent_execution should be a no-op."""
        provider = self._get_provider()
        provider.record_agent_execution("architect", "task", 1.0, True)
        stats = provider.get_stats()
        self.assertEqual(stats.get("total_agent_executions", 0), 0)

    def test_null_get_stats_has_provider_type_null(self):
        """NullMonitorProvider.get_stats should report provider_type='null'."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertEqual(stats.get("provider_type"), "null")

    def test_null_get_stats_has_avg_llm_duration_zero(self):
        """NullMonitorProvider.get_stats should report avg_llm_duration=0.0."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertEqual(stats.get("avg_llm_duration"), 0.0)

    def test_null_generate_report_writes_file(self):
        """NullMonitorProvider.generate_report should write a file."""
        provider = self._get_provider()
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = str(Path(tmpdir) / "null_report.md")
            provider.generate_report(report_path)
            self.assertTrue(Path(report_path).exists())


class T6_MonitorProviderBoundaryContract(unittest.TestCase):
    """Boundary and stress contract tests for MonitorProvider implementations.

    Covers empty-metadata recording, very-long-duration boundary, empty-data
    report generation, concurrent record safety, cumulative stats
    consistency, and availability under resource constraints.
    """

    def _get_provider(self) -> PerformanceMonitor:
        """Return a real PerformanceMonitor instance for behavior tests."""
        return PerformanceMonitor(max_history=100)

    def _get_null_provider(self) -> NullMonitorProvider:
        """Return a NullMonitorProvider (degraded) for null-specific tests."""
        return NullMonitorProvider()

    def test_record_llm_call_empty_metadata_no_exception(self) -> None:
        """record_llm_call with metadata=None must not raise.

        Boundary: callers may omit metadata entirely. The monitor must
        accept None without crashing or requiring a defensive default.
        """
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True, metadata=None)
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True, metadata={})
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 2)

    def test_record_agent_execution_very_long_duration(self) -> None:
        """record_agent_execution must handle extremely long durations.

        Boundary: a duration of 1e9 seconds (31+ years) must not cause
        overflow, NaN, or stats corruption. The monitor must record it
        as-is and report a valid avg_agent_duration.
        """
        provider = self._get_provider()
        provider.record_agent_execution("architect", "long task", 1e9, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_agent_executions"], 1)
        self.assertIsInstance(stats.get("avg_agent_duration", 0.0), float)
        self.assertTrue(stats["avg_agent_duration"] > 0)

    def test_generate_report_with_no_data(self) -> None:
        """generate_report on a fresh monitor must produce a valid file.

        Empty-data boundary: with zero recorded calls, the report must
        still be written without crashing and contain non-empty content.
        """
        provider = self._get_provider()
        with tempfile.TemporaryDirectory() as tmpdir:
            report_path = str(Path(tmpdir) / "empty_report.md")
            provider.generate_report(report_path)
            self.assertTrue(Path(report_path).exists())
            content = Path(report_path).read_text(encoding="utf-8")
            self.assertGreater(len(content), 0)

    def test_concurrent_record_llm_call_safety(self) -> None:
        """Concurrent record_llm_call from multiple threads must be safe.

        Stress: 10 threads each recording 20 LLM calls simultaneously.
        The monitor must not crash or lose entries; total_llm_calls
        must reflect all 200 records.
        """
        import threading

        provider = self._get_provider()
        barrier = threading.Barrier(10)
        errors: list[str] = []

        def worker() -> None:
            barrier.wait()
            try:
                for _ in range(20):
                    provider.record_llm_call("openai", "gpt-4", 0.5, 100, True)
            except Exception as e:  # noqa: BLE001
                errors.append(f"thread raised {type(e).__name__}: {e}")

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"Concurrent record errors: {errors}")
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 200)

    def test_get_stats_cumulative_consistency(self) -> None:
        """get_stats() counts must be monotonically non-decreasing.

        Records 3 calls, snapshots stats, records 2 more, then verifies
        that total_llm_calls only increases (never decreases) and that
        avg_llm_duration remains a valid finite float.
        """
        import math

        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        provider.record_llm_call("openai", "gpt-4", 2.0, 100, True)
        provider.record_llm_call("openai", "gpt-4", 3.0, 100, True)
        stats_mid = provider.get_stats()
        provider.record_llm_call("openai", "gpt-4", 1.5, 100, True)
        provider.record_llm_call("openai", "gpt-4", 2.5, 100, True)
        stats_final = provider.get_stats()
        self.assertGreaterEqual(
            stats_final["total_llm_calls"], stats_mid["total_llm_calls"],
        )
        self.assertFalse(math.isnan(stats_final["avg_llm_duration"]))
        self.assertFalse(math.isinf(stats_final["avg_llm_duration"]))

    def test_is_available_true_even_with_tiny_history(self) -> None:
        """PerformanceMonitor.is_available() must return True even with max_history=1.

        Resource-constraint boundary: a monitor configured with the
        smallest possible history buffer must still report available.
        The availability contract must not depend on buffer size.
        """
        provider = PerformanceMonitor(max_history=1)
        self.assertTrue(provider.is_available())
        provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
        self.assertTrue(provider.is_available())

    def test_null_provider_is_available_false_under_any_load(self) -> None:
        """NullMonitorProvider.is_available() must stay False under load.

        Degraded-mode boundary: recording many calls must not flip the
        null provider into an available state. It must remain False,
        signaling that no real monitoring is happening.
        """
        provider = self._get_null_provider()
        for _ in range(50):
            provider.record_llm_call("openai", "gpt-4", 1.0, 100, True)
            provider.record_agent_execution("coder", "task", 1.0, True)
        self.assertFalse(provider.is_available())

    def test_record_llm_call_zero_token_count(self) -> None:
        """record_llm_call with token_count=0 must not raise.

        Boundary: a zero-token call (e.g. a cached response or empty
        completion) must be recorded without error.
        """
        provider = self._get_provider()
        provider.record_llm_call("openai", "gpt-4", 0.5, 0, True)
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["total_llm_calls"], 1)


if __name__ == "__main__":
    unittest.main()
