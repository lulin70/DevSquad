"""Unit tests for BenchmarkRegressionChecker (V4.3.1 Phase 1 P1-1).

Verifies the P11 lifecycle gate benchmark regression detector:
- BenchmarkMetric / BenchmarkSnapshot / BenchmarkReport dataclasses
- BenchmarkRegressionChecker.compare() and run_live_benchmark()
- lifecycle_gate_check() module-level entry point
- BenchmarkReport.to_markdown() output

7-dimension coverage: Happy / Error / Boundary / Performance / Config /
Integration / Security.

All tests are self-contained (no external files, no real benchmark runs).
"""

from __future__ import annotations

import os
import sys
import time
import unittest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration._version import __version__  # noqa: E402
from scripts.collaboration.benchmark_regression_checker import (  # noqa: E402
    BenchmarkMetric,
    BenchmarkRegressionChecker,
    BenchmarkReport,
    BenchmarkSnapshot,
    lifecycle_gate_check,
)


def _snapshot(version: str, metrics: list[BenchmarkMetric]) -> BenchmarkSnapshot:
    """Build a snapshot with timestamp=0.0 for deterministic tests."""
    return BenchmarkSnapshot(version=version, timestamp=0.0, metrics=metrics)


class TestBenchmarkMetric(unittest.TestCase):
    """Tests for BenchmarkMetric dataclass (Happy)."""

    def test_01_metric_creation_and_attributes(self) -> None:
        """Happy: a metric exposes name/value/unit after construction."""
        metric = BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")
        self.assertEqual(metric.name, "dispatch_p95_ms")
        self.assertEqual(metric.value, 100.0)
        self.assertEqual(metric.unit, "ms")


class TestBenchmarkSnapshot(unittest.TestCase):
    """Tests for BenchmarkSnapshot dataclass (Happy)."""

    def test_02_snapshot_creation_and_attributes(self) -> None:
        """Happy: a snapshot exposes version/timestamp/metrics."""
        metrics = [
            BenchmarkMetric("dispatch_p95_ms", 100.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ]
        snapshot = BenchmarkSnapshot("4.3.0", 1000.0, metrics)
        self.assertEqual(snapshot.version, "4.3.0")
        self.assertEqual(snapshot.timestamp, 1000.0)
        self.assertEqual(len(snapshot.metrics), 2)
        self.assertEqual(snapshot.metrics[0].name, "dispatch_p95_ms")

    def test_02b_snapshot_default_metrics_is_empty(self) -> None:
        """Happy: omitting metrics yields an empty list (no shared state)."""
        snapshot = BenchmarkSnapshot("4.3.0", 0.0)
        self.assertEqual(snapshot.metrics, [])


class TestBenchmarkReportMarkdown(unittest.TestCase):
    """Tests for BenchmarkReport.to_markdown() (Happy)."""

    def test_03_to_markdown_contains_section_header(self) -> None:
        """Happy: markdown output contains the Benchmark Regression header."""
        report = BenchmarkReport(
            regression_detected=True,
            regression_percent=25.0,
            regressed_metrics=["dispatch_p95_ms"],
            baseline_version="4.2.9",
            current_version="4.3.0",
            threshold_percent=10.0,
        )
        md = report.to_markdown()
        self.assertIn("Benchmark Regression", md)

    def test_16_to_markdown_contains_versions(self) -> None:
        """Happy: markdown output contains baseline and current version strings."""
        report = BenchmarkReport(
            regression_detected=False,
            regression_percent=0.0,
            baseline_version="4.2.9",
            current_version="4.3.1",
            threshold_percent=10.0,
        )
        md = report.to_markdown()
        self.assertIn("4.2.9", md)
        self.assertIn("4.3.1", md)


class TestBenchmarkRegressionCheckerCompare(unittest.TestCase):
    """Tests for BenchmarkRegressionChecker.compare() across 7 dimensions."""

    def test_04_compare_no_regression(self) -> None:
        """Happy: current == baseline -> regression_detected=False."""
        metrics = [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")]
        baseline = _snapshot("4.2.9", metrics)
        current = _snapshot("4.3.0", metrics)
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertFalse(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 0.0)

    def test_05_compare_with_regression(self) -> None:
        """Happy: current 25% slower -> regression_detected=True."""
        baseline = _snapshot("4.2.9", [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")])
        current = _snapshot("4.3.0", [BenchmarkMetric("dispatch_p95_ms", 125.0, "ms")])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertTrue(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 25.0)
        self.assertIn("dispatch_p95_ms", report.regressed_metrics)

    def test_06_compare_speedup(self) -> None:
        """Boundary: current 20% faster -> regression_percent < 0."""
        baseline = _snapshot("4.2.9", [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")])
        current = _snapshot("4.3.0", [BenchmarkMetric("dispatch_p95_ms", 80.0, "ms")])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertFalse(report.regression_detected)
        self.assertLess(report.regression_percent, 0)
        self.assertAlmostEqual(report.regression_percent, -20.0)

    def test_07_compare_threshold_boundary_exact_10_percent(self) -> None:
        """Boundary: regression exactly 10.0% -> not detected (not > threshold)."""
        baseline = _snapshot("4.2.9", [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")])
        current = _snapshot("4.3.0", [BenchmarkMetric("dispatch_p95_ms", 110.0, "ms")])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertFalse(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 10.0)

    def test_08_compare_threshold_boundary_just_above(self) -> None:
        """Boundary: regression 10.01% -> detected (> threshold)."""
        baseline = _snapshot("4.2.9", [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")])
        current = _snapshot("4.3.0", [BenchmarkMetric("dispatch_p95_ms", 110.01, "ms")])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertTrue(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 10.01, places=2)

    def test_09_compare_empty_metrics(self) -> None:
        """Error: both snapshots empty -> no regression, 0.0 percent."""
        baseline = _snapshot("4.2.9", [])
        current = _snapshot("4.3.0", [])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertFalse(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 0.0)

    def test_10_compare_different_metric_names(self) -> None:
        """Config: only same-name metrics are compared."""
        baseline = _snapshot("4.2.9", [BenchmarkMetric("metric_a", 100.0, "x")])
        current = _snapshot("4.3.0", [BenchmarkMetric("metric_b", 200.0, "x")])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertFalse(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 0.0)

    def test_11_compare_multiple_metrics_one_regressed(self) -> None:
        """Integration: 2 metrics, 1 regressed 25%, 1 unchanged."""
        baseline = _snapshot("4.2.9", [
            BenchmarkMetric("dispatch_p95_ms", 100.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ])
        current = _snapshot("4.3.0", [
            BenchmarkMetric("dispatch_p95_ms", 125.0, "ms"),
            BenchmarkMetric("memory_peak_mb", 200.0, "MB"),
        ])
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        report = checker.compare(baseline, current)
        self.assertTrue(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 25.0)
        self.assertEqual(report.regressed_metrics, ["dispatch_p95_ms"])

    def test_17_custom_threshold_percent(self) -> None:
        """Config: threshold=5.0 -> a 10% regression is detected."""
        baseline = _snapshot("4.2.9", [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")])
        current = _snapshot("4.3.0", [BenchmarkMetric("dispatch_p95_ms", 110.0, "ms")])
        checker = BenchmarkRegressionChecker(threshold_percent=5.0)
        report = checker.compare(baseline, current)
        self.assertTrue(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 10.0)

    def test_18_compare_performance_1000_metrics(self) -> None:
        """Performance: comparing 1000 metrics completes in < 100ms."""
        baseline_metrics = [BenchmarkMetric(f"metric_{i}", float(i), "x") for i in range(1000)]
        current_metrics = [
            BenchmarkMetric(f"metric_{i}", float(i) * 1.05, "x") for i in range(1000)
        ]
        baseline = _snapshot("4.2.9", baseline_metrics)
        current = _snapshot("4.3.0", current_metrics)
        checker = BenchmarkRegressionChecker(threshold_percent=10.0)
        start = time.perf_counter()
        report = checker.compare(baseline, current)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        self.assertLess(elapsed_ms, 100.0)
        # All metrics regressed by 5%, which is below the 10% threshold.
        self.assertFalse(report.regression_detected)


class TestLifecycleGateCheck(unittest.TestCase):
    """Tests for lifecycle_gate_check() module-level function."""

    def test_12_lifecycle_gate_check_p11_normal(self) -> None:
        """Happy: phase=P11 with injected snapshots returns a report."""
        baseline = BenchmarkSnapshot(
            "4.2.9", 0.0, [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")]
        )
        current = BenchmarkSnapshot(
            "4.3.0", 0.0, [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")]
        )
        report = lifecycle_gate_check(
            phase="P11",
            baseline_version="4.2.9",
            baseline_snapshot=baseline,
            current_snapshot=current,
        )
        self.assertFalse(report.regression_detected)
        self.assertEqual(report.baseline_version, "4.2.9")

    def test_13_lifecycle_gate_check_invalid_phase_raises(self) -> None:
        """Error: phase != P11 raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            lifecycle_gate_check(phase="P10", baseline_version="4.2.9")
        self.assertIn("P11", str(ctx.exception))

    def test_14_lifecycle_gate_check_injected_snapshots(self) -> None:
        """Config: injected snapshots are used; parameter versions win."""
        baseline = BenchmarkSnapshot(
            "4.0.0", 0.0, [BenchmarkMetric("dispatch_p95_ms", 100.0, "ms")]
        )
        current = BenchmarkSnapshot(
            "4.5.0", 0.0, [BenchmarkMetric("dispatch_p95_ms", 130.0, "ms")]
        )
        report = lifecycle_gate_check(
            phase="P11",
            baseline_version="4.2.9",
            current_version="4.3.1",
            threshold_percent=10.0,
            baseline_snapshot=baseline,
            current_snapshot=current,
        )
        self.assertTrue(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 30.0)
        # Parameter versions take precedence over snapshot-embedded versions.
        self.assertEqual(report.baseline_version, "4.2.9")
        self.assertEqual(report.current_version, "4.3.1")

    def test_15_lifecycle_gate_check_auto_run_benchmark(self) -> None:
        """Integration: current_snapshot=None triggers the live benchmark.

        The default baseline is dispatch_p95_ms=100.0ms and the live
        benchmark returns dispatch_p95_ms=120.0ms (a 20% slowdown),
        which exceeds the default 10% threshold.
        """
        report = lifecycle_gate_check(
            phase="P11",
            baseline_version="4.2.9",
            current_snapshot=None,
        )
        self.assertTrue(report.regression_detected)
        self.assertAlmostEqual(report.regression_percent, 20.0)
        self.assertEqual(report.current_version, __version__)

    def test_19_lifecycle_gate_check_strict_phase_validation(self) -> None:
        """Security: empty and case-variant phases are rejected.

        The P11 gate cannot be bypassed by passing an empty string,
        whitespace, a lowercased variant, or a trailing-space variant.
        """
        for invalid_phase in ("", "  ", "p11", "P11 ", "P10"):
            with self.subTest(phase=invalid_phase), self.assertRaises(ValueError):
                lifecycle_gate_check(phase=invalid_phase, baseline_version="4.2.9")


if __name__ == "__main__":
    unittest.main()
