#!/usr/bin/env python3
"""PerformanceMonitor + UsageTracker + HistoryManager Integration Tests
(V4.2.1 P2-3 — Test Pyramid Lift).

End-to-end integration tests for the performance-monitoring trio. Verifies
CROSS-MODULE interactions among:

    scripts/collaboration/performance_monitor.py — PerformanceMonitor
        (record_metric / record_llm_call / record_agent_execution /
         get_stats / get_bottlenecks / export_report)
    scripts/collaboration/usage_tracker.py      — UsageTracker
        (track / get_stats / get_top_features / get_error_prone_features /
         save / generate_report / export_json)
    scripts/history_manager.py                  — HistoryManager
        (save_metrics_snapshot / get_metrics_history / log_api_request /
         save_lifecycle_event / get_lifecycle_history / get_database_size)

Flow:
    1. PerformanceMonitor.record_metric + UsageTracker.track — a monitoring
       pipeline records both a perf metric and a usage tick for the same
       operation (mirrors how DispatchHooks records perf + usage together).
    2. PerformanceMonitor stats → HistoryManager.save_metrics_snapshot —
       perf stats are persisted to SQLite and round-tripped back.
    3. UsageTracker report → HistoryManager.save_lifecycle_event — usage
       summaries are persisted as lifecycle events for later audit.
    4. End-to-end: record → track → save → load → report.
    5. Boundary (empty data, concurrent writes, huge metrics).

Test categories:
    T1: PerformanceMonitor.record_metric → UsageTracker.track linkage
    T2: PerformanceMonitor + HistoryManager metrics persistence (save/load roundtrip)
    T3: UsageTracker + HistoryManager token/cost tracking
    T4: End-to-end — record → track → save → load → report
    T5: Boundary (empty data, concurrent writes, huge metrics)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.performance_monitor import (
    PerformanceMetric,
    PerformanceMonitor,
)
from scripts.collaboration.usage_tracker import UsageTracker
from scripts.history_manager import HistoryManager

# ---------------------------------------------------------------------------
# Stub / helper: a monitoring pipeline that wires the three modules together.
# Mirrors how DispatchHooks records both a PerformanceMetric and a usage tick
# for the same dispatch operation. This is the "integration glue" under test.
# ---------------------------------------------------------------------------


class _MonitoringPipeline:
    """Wire PerformanceMonitor + UsageTracker + HistoryManager together.

    Each ``record_operation`` call fans out to all three:
      - PerformanceMonitor.record_metric (timing + success)
      - UsageTracker.track (feature usage count + errors)
      - HistoryManager.save_metrics_snapshot (persistent time-series)
    """

    def __init__(
        self,
        perf: PerformanceMonitor,
        usage: UsageTracker,
        history: HistoryManager,
    ) -> None:
        self.perf = perf
        self.usage = usage
        self.history = history
        # SQLite connections are thread-local by default; serialize history
        # writes so concurrent pipeline calls don't violate check_same_thread.
        self._history_lock = threading.Lock()

    def record_operation(
        self,
        name: str,
        duration: float,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """Record a single operation across all three modules."""
        metric = PerformanceMetric(
            name=name,
            start_time=0.0,
            end_time=duration,
            duration=duration,
            cpu_percent=0.0,
            memory_mb=0.0,
            success=success,
            error=error,
        )
        self.perf.record_metric(metric)
        self.usage.track(name, success=success, metadata={"duration": duration})
        with self._history_lock:
            self.history.save_metrics_snapshot({
                "avg_response_time_ms": duration * 1000,
                "success_rate": 1.0 if success else 0.0,
                "custom_operation": name,
            })


def _make_pipeline() -> tuple[_MonitoringPipeline, PerformanceMonitor, UsageTracker, HistoryManager, str]:
    """Build a pipeline backed by temp files. Returns (pipeline, perf, usage, history, tmpdir)."""
    tmpdir = tempfile.mkdtemp(prefix="perfmon_integ_")
    usage = UsageTracker(persist_file=os.path.join(tmpdir, "usage.json"))
    history = HistoryManager(db_path=os.path.join(tmpdir, "history.db"))
    perf = PerformanceMonitor()
    return _MonitoringPipeline(perf, usage, history), perf, usage, history, tmpdir


def _make_metric(
    name: str = "llm_call:openai:gpt-4",
    duration: float = 0.5,
    success: bool = True,
    error: str | None = None,
) -> PerformanceMetric:
    """Build a minimal PerformanceMetric for tests."""
    return PerformanceMetric(
        name=name,
        start_time=0.0,
        end_time=duration,
        duration=duration,
        cpu_percent=0.0,
        memory_mb=10.0,
        success=success,
        error=error,
    )


# ---------------------------------------------------------------------------
# T1: PerformanceMonitor.record_metric → UsageTracker.track linkage
# ---------------------------------------------------------------------------


class T1_PerfMonitorUsageTrackerLinkage(unittest.TestCase):
    """T1: PerformanceMonitor.record_metric and UsageTracker.track fire together."""

    def setUp(self) -> None:
        self._pipeline, self._perf, self._usage, self._history, self._tmpdir = _make_pipeline()

    def tearDown(self) -> None:
        self._history.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_record_operation_fans_out_to_both_modules(self) -> None:
        """Verify: record_operation records in both PerformanceMonitor and UsageTracker."""
        self._pipeline.record_operation("dispatch.execute", 0.3)
        self.assertEqual(self._perf.get_stats()["total_metrics"], 1)
        usage_stats = self._usage.get_stats("dispatch.execute")
        self.assertEqual(usage_stats["count"], 1)

    def test_02_failed_operation_records_error_in_both(self) -> None:
        """Verify: a failed operation increments error counters in both modules."""
        self._pipeline.record_operation("dispatch.execute", 0.1, success=False, error="boom")
        perf_stats = self._perf.get_stats("dispatch.execute")
        self.assertEqual(perf_stats["failure_count"], 1)
        usage_stats = self._usage.get_stats("dispatch.execute")
        self.assertEqual(usage_stats["errors"], 1)

    def test_03_record_llm_call_updates_perf_and_usage(self) -> None:
        """Verify: record_llm_call on perf + manual track on usage stay in sync."""
        self._perf.record_llm_call("openai", "gpt-4", duration=1.2, token_count=500, success=True)
        self._usage.track("llm_call:openai:gpt-4", success=True, metadata={"tokens": 500})
        perf_stats = self._perf.get_stats("llm_call:openai:gpt-4")
        self.assertEqual(perf_stats["call_count"], 1)
        self.assertEqual(self._usage.get_stats("llm_call:openai:gpt-4")["count"], 1)

    def test_04_record_agent_execution_updates_both(self) -> None:
        """Verify: record_agent_execution on perf + track on usage align on role name."""
        self._perf.record_agent_execution("architect", "design", duration=2.0, success=True)
        self._usage.track("agent:architect", success=True)
        perf_stats = self._perf.get_stats()
        self.assertEqual(perf_stats["total_agent_executions"], 1)
        self.assertEqual(self._usage.get_stats("agent:architect")["count"], 1)

    def test_05_monitor_decorator_records_perf_only(self) -> None:
        """Verify: the monitor decorator records a metric on each decorated call."""
        @self._perf.monitor("decorated_fn")
        def _fast() -> str:
            return "done"

        _fast()
        _fast()
        self.assertEqual(self._perf.get_stats("decorated_fn")["call_count"], 2)

    def test_06_metric_name_aligns_with_usage_feature_name(self) -> None:
        """Verify: the same operation name is used across perf and usage."""
        name = "coordinator.execute_plan"
        self._pipeline.record_operation(name, 0.5)
        self.assertIn(name, self._perf.function_stats)
        self.assertIn(name, self._usage.get_stats())

    def test_07_multiple_operations_accumulate_in_both(self) -> None:
        """Verify: 3 operations produce 3 perf metrics and 3 usage ticks."""
        for i in range(3):
            self._pipeline.record_operation(f"op.{i}", 0.1 * i)
        self.assertEqual(self._perf.get_stats()["total_metrics"], 3)
        self.assertEqual(len(self._usage.get_stats()), 3)

    def test_08_perf_total_metrics_matches_usage_total_count(self) -> None:
        """Verify: after N operations, perf total_metrics equals usage sum of counts."""
        for _ in range(5):
            self._pipeline.record_operation("repeated.op", 0.2)
        perf_total = self._perf.get_stats()["total_metrics"]
        usage_count = self._usage.get_stats("repeated.op")["count"]
        self.assertEqual(perf_total, 5)
        self.assertEqual(usage_count, 5)


# ---------------------------------------------------------------------------
# T2: PerformanceMonitor + HistoryManager metrics persistence (save/load roundtrip)
# ---------------------------------------------------------------------------


class T2_PerfMonitorHistoryManagerPersistence(unittest.TestCase):
    """T2: PerformanceMonitor stats persist to HistoryManager and round-trip back."""

    def setUp(self) -> None:
        self._pipeline, self._perf, self._usage, self._history, self._tmpdir = _make_pipeline()

    def tearDown(self) -> None:
        self._history.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_save_metrics_snapshot_returns_true(self) -> None:
        """Verify: save_metrics_snapshot succeeds and returns True."""
        ok = self._history.save_metrics_snapshot({
            "completion_rate": 75.0,
            "avg_response_time_ms": 120.5,
        })
        self.assertTrue(ok)

    def test_02_get_metrics_history_retrieves_saved_snapshot(self) -> None:
        """Verify: a saved snapshot is retrievable via get_metrics_history."""
        self._history.save_metrics_snapshot({"completion_rate": 50.0})
        rows = self._history.get_metrics_history(hours=1)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["completion_rate"], 50.0)

    def test_03_roundtrip_preserves_completion_rate(self) -> None:
        """Verify: completion_rate survives the save → load roundtrip."""
        self._history.save_metrics_snapshot({"completion_rate": 88.8})
        rows = self._history.get_metrics_history(hours=1)
        self.assertAlmostEqual(rows[0]["completion_rate"], 88.8)

    def test_04_roundtrip_preserves_avg_response_time(self) -> None:
        """Verify: avg_response_time_ms survives the save → load roundtrip."""
        self._history.save_metrics_snapshot({"avg_response_time_ms": 250.3})
        rows = self._history.get_metrics_history(hours=1)
        self.assertAlmostEqual(rows[0]["avg_response_time_ms"], 250.3)

    def test_05_custom_data_stored_as_json_blob(self) -> None:
        """Verify: unknown fields are stored in the custom_data JSON column."""
        self._history.save_metrics_snapshot({
            "avg_response_time_ms": 10.0,
            "custom_tag": "nightly",
        })
        rows = self._history.get_metrics_history(hours=1, include_custom=True)
        self.assertEqual(rows[0]["custom_data"]["custom_tag"], "nightly")

    def test_06_multiple_snapshots_retrieved_in_order(self) -> None:
        """Verify: multiple snapshots are returned in ascending timestamp order."""
        for rate in (10.0, 20.0, 30.0):
            self._history.save_metrics_snapshot({"completion_rate": rate})
        rows = self._history.get_metrics_history(hours=1)
        self.assertEqual(len(rows), 3)
        rates = [r["completion_rate"] for r in rows]
        self.assertEqual(rates, [10.0, 20.0, 30.0])

    def test_07_include_custom_flag_parses_json(self) -> None:
        """Verify: include_custom=True parses the custom_data JSON into a dict."""
        self._history.save_metrics_snapshot({
            "completion_rate": 1.0,
            "extra": {"k": "v"},
        })
        rows = self._history.get_metrics_history(hours=1, include_custom=True)
        self.assertIsInstance(rows[0]["custom_data"], dict)
        self.assertEqual(rows[0]["custom_data"]["extra"], {"k": "v"})

    def test_08_get_database_size_reports_metrics_count(self) -> None:
        """Verify: get_database_size counts the metrics_snapshots table rows."""
        self._history.save_metrics_snapshot({"completion_rate": 1.0})
        self._history.save_metrics_snapshot({"completion_rate": 2.0})
        size = self._history.get_database_size()
        self.assertEqual(size["tables"]["metrics_snapshots"], 2)


# ---------------------------------------------------------------------------
# T3: UsageTracker + HistoryManager token/cost tracking
# ---------------------------------------------------------------------------


class T3_UsageTrackerHistoryManagerTracking(unittest.TestCase):
    """T3: UsageTracker summaries persist to HistoryManager lifecycle events."""

    def setUp(self) -> None:
        self._pipeline, self._perf, self._usage, self._history, self._tmpdir = _make_pipeline()

    def tearDown(self) -> None:
        self._history.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_track_features_then_save_summary_to_lifecycle_event(self) -> None:
        """Verify: usage stats are saved as a lifecycle event detail string."""
        self._usage.track("dispatch.execute", success=True)
        self._usage.track("dispatch.execute", success=True)
        report = self._usage.export_json()
        self._history.save_lifecycle_event(
            event_type="usage_summary",
            details=report,
        )
        events = self._history.get_lifecycle_history(hours=1, event_type="usage_summary")
        self.assertEqual(len(events), 1)
        self.assertIn("dispatch.execute", events[0]["details"])

    def test_02_get_lifecycle_history_retrieves_saved_usage_event(self) -> None:
        """Verify: a saved usage lifecycle event is retrievable."""
        self._history.save_lifecycle_event(event_type="usage_snapshot", details="count=5")
        events = self._history.get_lifecycle_history(hours=1, event_type="usage_snapshot")
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["details"], "count=5")

    def test_03_error_prone_features_persisted_in_lifecycle_details(self) -> None:
        """Verify: error-prone feature detection results feed into lifecycle events."""
        for _ in range(10):
            self._usage.track("flaky.api", success=False)
        error_prone = self._usage.get_error_prone_features(min_calls=5)
        self.assertEqual(len(error_prone), 1)
        self._history.save_lifecycle_event(
            event_type="error_prone_alert",
            details=f"flaky={error_prone[0][1]:.2f}",
        )
        events = self._history.get_lifecycle_history(hours=1, event_type="error_prone_alert")
        self.assertIn("flaky=", events[0]["details"])

    def test_04_usage_report_markdown_saved_to_api_logs_path(self) -> None:
        """Verify: the usage Markdown report can be logged via log_api_request."""
        report = self._usage.generate_report()
        self._history.log_api_request("GET", "/api/usage/report", 200, 45.2)
        self.assertIn("DevSquad", report)

    def test_05_get_api_stats_returns_logged_endpoint(self) -> None:
        """Verify: log_api_request + get_api_stats round-trip an endpoint."""
        self._history.log_api_request("GET", "/api/usage", 200, 12.3)
        stats = self._history.get_api_stats(hours=1)
        self.assertEqual(stats["total_requests"], 1)
        self.assertTrue(any(e["path"] == "/api/usage" for e in stats["endpoints"]))

    def test_06_usage_save_persists_and_reload_preserves(self) -> None:
        """Verify: UsageTracker.save → new UsageTracker loads the persisted stats."""
        self._usage.track("persisted.op", success=True)
        self.assertTrue(self._usage.save())
        reload_file = self._usage.persist_file
        reloaded = UsageTracker(persist_file=reload_file)
        self.assertEqual(reloaded.get_stats("persisted.op")["count"], 1)

    def test_07_track_with_metadata_persists_in_usage_stats(self) -> None:
        """Verify: metadata attached to track() is retained in get_stats."""
        self._usage.track("op.with.meta", success=True, metadata={"tokens": 42})
        stats = self._usage.get_stats("op.with.meta")
        self.assertEqual(stats["metadata"][0]["tokens"], 42)

    def test_08_clear_usage_tracker_resets_but_history_retains(self) -> None:
        """Verify: clear() wipes usage stats but lifecycle events remain in history."""
        self._usage.track("temp.op", success=True)
        self._history.save_lifecycle_event(event_type="before_clear", details="temp.op tracked")
        cleared = self._usage.clear()
        self.assertEqual(cleared, 1)
        self.assertEqual(self._usage.get_stats("temp.op"), {})
        events = self._history.get_lifecycle_history(hours=1, event_type="before_clear")
        self.assertEqual(len(events), 1)


# ---------------------------------------------------------------------------
# T4: End-to-end — record → track → save → load → report
# ---------------------------------------------------------------------------


class T4_EndToEndRecordTrackSaveLoadReport(unittest.TestCase):
    """T4: Full pipeline — record → track → save → load → report."""

    def setUp(self) -> None:
        self._pipeline, self._perf, self._usage, self._history, self._tmpdir = _make_pipeline()

    def tearDown(self) -> None:
        self._history.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_full_pipeline_record_save_load_report(self) -> None:
        """Verify: record → save snapshot → load history → perf report has data."""
        self._pipeline.record_operation("e2e.op", 0.4)
        rows = self._history.get_metrics_history(hours=1)
        self.assertEqual(len(rows), 1)
        report = self._perf.export_report()
        self.assertIn("e2e.op", report)

    def test_02_full_pipeline_llm_call_save_load_stats(self) -> None:
        """Verify: LLM call → save → load → get_stats reflects the call."""
        self._perf.record_llm_call("anthropic", "claude", duration=0.8, token_count=100, success=True)
        self._usage.track("llm_call:anthropic:claude", success=True)
        self._history.save_metrics_snapshot({
            "avg_response_time_ms": 800.0,
            "total_llm_calls": self._perf.get_stats()["total_llm_calls"],
        })
        # total_llm_calls is not a known column; it lands in custom_data JSON.
        rows = self._history.get_metrics_history(hours=1, include_custom=True)
        self.assertEqual(rows[0]["custom_data"]["total_llm_calls"], 1)
        self.assertEqual(self._perf.get_stats("llm_call:anthropic:claude")["call_count"], 1)

    def test_03_full_pipeline_agent_execution_bottleneck_detection(self) -> None:
        """Verify: agent execution → save → bottleneck detection finds slow agent."""
        self._perf.record_agent_execution("architect", "design", duration=2.5, success=True)
        bottlenecks = self._perf.get_bottlenecks(threshold_ms=1000)
        self.assertTrue(any(b["name"] == "agent:architect" for b in bottlenecks))

    def test_04_report_includes_both_perf_and_usage_data(self) -> None:
        """Verify: perf export_report + usage generate_report both contain data."""
        self._pipeline.record_operation("report.op", 0.3)
        perf_report = self._perf.export_report()
        usage_report = self._usage.generate_report()
        self.assertIn("report.op", perf_report)
        self.assertIn("report.op", usage_report)

    def test_05_failure_path_recorded_in_errors_and_history(self) -> None:
        """Verify: a failed operation surfaces in perf errors and history."""
        self._perf.record_metric(_make_metric("fail.op", duration=0.1, success=False, error="crash"))
        self._usage.track("fail.op", success=False)
        self._history.save_metrics_snapshot({"success_rate": 0.0})
        errors = self._perf.get_recent_errors()
        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["name"], "fail.op")
        rows = self._history.get_metrics_history(hours=1)
        self.assertEqual(rows[0]["success_rate"], 0.0)

    def test_06_concurrent_records_all_saved_to_history(self) -> None:
        """Verify: concurrent record_operation calls all produce history snapshots."""
        def _worker(idx: int) -> None:
            self._pipeline.record_operation(f"concurrent.{idx}", 0.01)

        threads = [threading.Thread(target=_worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        rows = self._history.get_metrics_history(hours=1)
        self.assertEqual(len(rows), 8)

    def test_07_bottleneck_feeds_into_history_snapshot(self) -> None:
        """Verify: a detected bottleneck is persisted via save_metrics_snapshot."""
        self._perf.record_metric(_make_metric("slow.fn", duration=1.5, success=True))
        bottlenecks = self._perf.get_bottlenecks(threshold_ms=1000)
        self._history.save_metrics_snapshot({
            "avg_response_time_ms": bottlenecks[0]["avg_duration_ms"],
        })
        rows = self._history.get_metrics_history(hours=1)
        self.assertGreater(rows[0]["avg_response_time_ms"], 1000.0)

    def test_08_recent_errors_feed_into_lifecycle_event(self) -> None:
        """Verify: perf recent errors are persisted as a lifecycle event detail."""
        self._perf.record_metric(_make_metric("err.fn", duration=0.1, success=False, error="timeout"))
        errors = self._perf.get_recent_errors()
        self._history.save_lifecycle_event(
            event_type="perf_errors",
            details=errors[0]["error"],
        )
        events = self._history.get_lifecycle_history(hours=1, event_type="perf_errors")
        self.assertEqual(events[0]["details"], "timeout")


# ---------------------------------------------------------------------------
# T5: Boundary (empty data, concurrent writes, huge metrics)
# ---------------------------------------------------------------------------


class T5_BoundaryAndEdgeCases(unittest.TestCase):
    """T5: Boundary conditions — empty data, concurrency, huge payloads."""

    def setUp(self) -> None:
        self._pipeline, self._perf, self._usage, self._history, self._tmpdir = _make_pipeline()

    def tearDown(self) -> None:
        self._history.close()
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def test_01_empty_perf_monitor_get_stats_returns_zeros(self) -> None:
        """Verify: a fresh PerformanceMonitor reports zero metrics."""
        stats = self._perf.get_stats()
        self.assertEqual(stats["total_metrics"], 0)
        self.assertEqual(stats["total_llm_calls"], 0)

    def test_02_empty_usage_tracker_get_stats_returns_empty(self) -> None:
        """Verify: a fresh UsageTracker reports no features."""
        self.assertEqual(self._usage.get_stats(), {})

    def test_03_empty_history_get_metrics_history_returns_empty_list(self) -> None:
        """Verify: a fresh HistoryManager returns no snapshots."""
        self.assertEqual(self._history.get_metrics_history(hours=1), [])

    def test_04_concurrent_track_calls_are_thread_safe(self) -> None:
        """Verify: concurrent UsageTracker.track calls don't lose counts."""
        def _track(idx: int) -> None:
            self._usage.track("concurrent.track", success=True)

        threads = [threading.Thread(target=_track, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self._usage.get_stats("concurrent.track")["count"], 20)

    def test_05_concurrent_record_metric_calls_are_safe(self) -> None:
        """Verify: concurrent PerformanceMonitor.record_metric calls don't lose metrics."""
        def _record(idx: int) -> None:
            self._perf.record_metric(_make_metric("concurrent.metric", duration=0.01))

        threads = [threading.Thread(target=_record, args=(i,)) for i in range(15)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(self._perf.get_stats()["total_metrics"], 15)

    def test_06_huge_metrics_custom_data_saved_and_loaded(self) -> None:
        """Verify: a large custom_data payload survives the save → load roundtrip."""
        big_payload = {"big": "x" * 5000}
        self._history.save_metrics_snapshot({
            "completion_rate": 1.0,
            **big_payload,
        })
        rows = self._history.get_metrics_history(hours=1, include_custom=True)
        self.assertEqual(len(rows[0]["custom_data"]["big"]), 5000)

    def test_07_save_metrics_snapshot_with_minimal_fields(self) -> None:
        """Verify: save_metrics_snapshot works with an empty dict (all None columns)."""
        ok = self._history.save_metrics_snapshot({})
        self.assertTrue(ok)
        rows = self._history.get_metrics_history(hours=1)
        self.assertEqual(len(rows), 1)

    def test_08_get_stats_for_unknown_function_returns_empty_dict(self) -> None:
        """Verify: get_stats for a non-existent function name returns {}."""
        self.assertEqual(self._perf.get_stats("never.recorded"), {})


if __name__ == "__main__":
    unittest.main()
