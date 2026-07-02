#!/usr/bin/env python3
"""Tests for the ponytail + SMART compression benchmark framework.

Verifies that the benchmark script:
  - Defines 15 tasks (5 simple + 5 medium + 5 complex)
  - run_ponytail_benchmark produces metrics for all tasks
  - run_smart_compression_benchmark produces metrics for all 6 samples
  - Summary aggregation computes correct averages
  - Metrics have expected fields and sane values

Spec reference: docs/spec/v3.10.0_spec.md §7 (Phase 1+2 收尾项)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.benchmark_ponytail_smart import (  # noqa: E402
    BENCHMARK_TASKS,
    PonytailMetric,
    SmartCompressionMetric,
    compute_ponytail_summary,
    compute_smart_summary,
    run_ponytail_benchmark,
    run_smart_compression_benchmark,
)


class TestBenchmarkTasks(unittest.TestCase):
    """Benchmark task definitions."""

    def test_total_15_tasks(self):
        self.assertEqual(len(BENCHMARK_TASKS), 15)

    def test_5_tasks_per_tier(self):
        for tier in ["simple", "medium", "complex"]:
            tier_tasks = [t for t in BENCHMARK_TASKS if t["complexity"] == tier]
            self.assertEqual(len(tier_tasks), 5, f"Tier {tier} should have 5 tasks")

    def test_each_task_has_required_fields(self):
        for task in BENCHMARK_TASKS:
            self.assertIn("id", task)
            self.assertIn("complexity", task)
            self.assertIn("description", task)
            self.assertTrue(len(task["description"]) > 10, "Task description should be meaningful")

    def test_task_ids_unique(self):
        ids = [t["id"] for t in BENCHMARK_TASKS]
        self.assertEqual(len(ids), len(set(ids)), "Task IDs should be unique")


class TestPonytailBenchmark(unittest.TestCase):
    """Ponytail injection A/B benchmark."""

    def setUp(self):
        self.metrics = run_ponytail_benchmark(BENCHMARK_TASKS)

    def test_returns_metric_for_each_task(self):
        self.assertEqual(len(self.metrics), len(BENCHMARK_TASKS))

    def test_metrics_are_ponytail_metric_instances(self):
        for m in self.metrics:
            self.assertIsInstance(m, PonytailMetric)

    def test_injection_overhead_is_positive(self):
        """Ponytail injection should add tokens (positive overhead)."""
        for m in self.metrics:
            self.assertGreater(m.injection_overhead_tokens, 0, f"Task {m.task_id} should have positive overhead")
            self.assertGreater(m.injection_overhead_pct, 0.0, f"Task {m.task_id} should have positive overhead %")

    def test_tokens_with_greater_than_without(self):
        for m in self.metrics:
            self.assertGreaterEqual(m.prompt_tokens_with, m.prompt_tokens_without)

    def test_all_complexity_tiers_present(self):
        tiers = {m.complexity for m in self.metrics}
        self.assertEqual(tiers, {"simple", "medium", "complex"})


class TestSmartCompressionBenchmark(unittest.TestCase):
    """SMART compression A/B benchmark."""

    def setUp(self):
        self.metrics = run_smart_compression_benchmark()

    def test_returns_6_samples(self):
        self.assertEqual(len(self.metrics), 6)

    def test_metrics_are_smart_compression_metric_instances(self):
        for m in self.metrics:
            self.assertIsInstance(m, SmartCompressionMetric)

    def test_json_samples_have_high_reduction(self):
        """JSON samples should have >80% SMART reduction."""
        json_metrics = [m for m in self.metrics if m.content_type == "json"]
        for m in json_metrics:
            self.assertGreater(m.smart_reduction_pct, 80.0, f"JSON sample {m.sample_id} should have >80% SMART reduction")

    def test_log_samples_have_high_reduction(self):
        """Log samples should have >70% SMART reduction."""
        log_metrics = [m for m in self.metrics if m.content_type == "log"]
        for m in log_metrics:
            self.assertGreater(m.smart_reduction_pct, 70.0, f"Log sample {m.sample_id} should have >70% SMART reduction")

    def test_smart_preserves_all_messages(self):
        """SMART compression must preserve all messages (no deletion)."""
        for m in self.metrics:
            self.assertEqual(m.smart_messages_preserved, 1, f"Sample {m.sample_id} should preserve 1 message")

    def test_smart_correctness_is_high(self):
        """SMART should preserve structured content markers (correctness >= 0.8)."""
        for m in self.metrics:
            self.assertGreaterEqual(m.smart_correctness_score, 0.8, f"Sample {m.sample_id} correctness should be >= 0.8")

    def test_all_content_types_present(self):
        types = {m.content_type for m in self.metrics}
        self.assertEqual(types, {"json", "log", "code", "plain"})


class TestSummaryAggregation(unittest.TestCase):
    """Summary computation."""

    def test_ponytail_summary_has_all_tiers(self):
        metrics = run_ponytail_benchmark(BENCHMARK_TASKS)
        summary = compute_ponytail_summary(metrics)
        self.assertIn("simple", summary)
        self.assertIn("medium", summary)
        self.assertIn("complex", summary)
        self.assertIn("overall_avg_overhead_pct", summary)
        for tier in ["simple", "medium", "complex"]:
            self.assertEqual(summary[tier]["count"], 5)
            self.assertGreater(summary[tier]["avg_overhead_pct"], 0.0)

    def test_smart_summary_has_all_types(self):
        metrics = run_smart_compression_benchmark()
        summary = compute_smart_summary(metrics)
        self.assertIn("json", summary)
        self.assertIn("log", summary)
        self.assertIn("code", summary)
        self.assertIn("plain", summary)
        self.assertIn("overall_avg_smart_reduction_pct", summary)
        self.assertIn("overall_avg_snip_reduction_pct", summary)

    def test_smart_summary_json_all_preserved(self):
        metrics = run_smart_compression_benchmark()
        summary = compute_smart_summary(metrics)
        self.assertTrue(summary["json"]["all_messages_preserved"])
        self.assertTrue(summary["log"]["all_messages_preserved"])

    def test_empty_metrics_summary(self):
        """Empty metrics list should produce zero-valued summary."""
        ponytail_summary = compute_ponytail_summary([])
        self.assertEqual(ponytail_summary["total_tasks"], 0)
        self.assertEqual(ponytail_summary["overall_avg_overhead_pct"], 0.0)

        smart_summary = compute_smart_summary([])
        self.assertEqual(smart_summary["total_samples"], 0)
        self.assertEqual(smart_summary["overall_avg_smart_reduction_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
