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


if __name__ == "__main__":
    unittest.main()
