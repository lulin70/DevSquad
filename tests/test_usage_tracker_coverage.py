#!/usr/bin/env python3
"""Coverage-focused tests for UsageTracker.

Targets the previously uncovered lines reported by pytest-cov:
  - get_stats (with/without feature_name)
  - get_top_features, get_unused_features, get_error_prone_features
  - generate_report (all branches: top features, components, error-prone, freq buckets)
  - save (success + failure), _load_stats (happy + corrupted), clear, export_json
  - module-level convenience functions
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest

from scripts.collaboration import usage_tracker as ut_module
from scripts.collaboration.usage_tracker import (
    UsageTracker,
    generate_usage_report,
    get_tracker,
    get_usage_stats,
    save_usage_stats,
    track_usage,
)


class TestUsageTrackerGetStats(unittest.TestCase):
    """get_stats() coverage (lines 84-87)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.persist = os.path.join(self.tmpdir, "stats.json")
        self.tracker = UsageTracker(persist_file=self.persist)

    def test_get_stats_for_specific_feature(self) -> None:
        self.tracker.track("feat.a")
        result = self.tracker.get_stats("feat.a")
        self.assertEqual(result["count"], 1)
        self.assertIn("first_used", result)
        self.assertIn("last_used", result)

    def test_get_stats_for_missing_feature_returns_empty(self) -> None:
        result = self.tracker.get_stats("nonexistent")
        self.assertEqual(result, {})

    def test_get_stats_all_features(self) -> None:
        self.tracker.track("feat.a")
        self.tracker.track("feat.b")
        result = self.tracker.get_stats()
        self.assertIn("feat.a", result)
        self.assertIn("feat.b", result)
        self.assertEqual(result["feat.a"]["count"], 1)

    def test_get_stats_all_empty(self) -> None:
        result = self.tracker.get_stats()
        self.assertEqual(result, {})


class TestUsageTrackerTopAndUnused(unittest.TestCase):
    """get_top_features / get_unused_features (lines 98-113)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.persist = os.path.join(self.tmpdir, "stats.json")
        self.tracker = UsageTracker(persist_file=self.persist)

    def test_get_top_features_sorted_by_count(self) -> None:
        for _ in range(5):
            self.tracker.track("popular")
        for _ in range(2):
            self.tracker.track("medium")
        self.tracker.track("rare")
        top = self.tracker.get_top_features(limit=3)
        self.assertEqual(top[0], ("popular", 5))
        self.assertEqual(top[1], ("medium", 2))
        self.assertEqual(top[2], ("rare", 1))

    def test_get_top_features_limit_smaller_than_total(self) -> None:
        for _ in range(3):
            self.tracker.track("a")
        for _ in range(2):
            self.tracker.track("b")
        top = self.tracker.get_top_features(limit=1)
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0], ("a", 3))

    def test_get_top_features_empty(self) -> None:
        self.assertEqual(self.tracker.get_top_features(), [])

    def test_get_unused_features(self) -> None:
        self.tracker.track("used.a")
        self.tracker.track("used.b")
        unused = self.tracker.get_unused_features(["used.a", "used.b", "unused.c", "unused.d"])
        self.assertEqual(sorted(unused), ["unused.c", "unused.d"])

    def test_get_unused_features_all_used(self) -> None:
        self.tracker.track("a")
        self.tracker.track("b")
        self.assertEqual(self.tracker.get_unused_features(["a", "b"]), [])

    def test_get_unused_features_empty_input(self) -> None:
        self.assertEqual(self.tracker.get_unused_features([]), [])


class TestUsageTrackerErrorProne(unittest.TestCase):
    """get_error_prone_features() coverage (lines 125-132)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.persist = os.path.join(self.tmpdir, "stats.json")
        self.tracker = UsageTracker(persist_file=self.persist)

    def test_error_prone_features_detected(self) -> None:
        # feature "buggy": 10 calls, 5 errors = 50% error rate
        for _ in range(5):
            self.tracker.track("buggy", success=True)
        for _ in range(5):
            self.tracker.track("buggy", success=False)
        # feature "stable": 10 calls, 0 errors
        for _ in range(10):
            self.tracker.track("stable", success=True)
        result = self.tracker.get_error_prone_features(min_calls=5, error_threshold=0.1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0][0], "buggy")
        self.assertAlmostEqual(result[0][1], 0.5)

    def test_error_prone_below_min_calls_excluded(self) -> None:
        # Only 2 calls (below min_calls=5)
        self.tracker.track("rare", success=False)
        self.tracker.track("rare", success=False)
        result = self.tracker.get_error_prone_features(min_calls=5)
        self.assertEqual(result, [])

    def test_error_prone_below_threshold_excluded(self) -> None:
        for _ in range(9):
            self.tracker.track("good", success=True)
        self.tracker.track("good", success=False)  # 10% error rate, threshold 0.1
        # 1/10 = 0.1, which is >= 0.1 threshold
        result = self.tracker.get_error_prone_features(min_calls=5, error_threshold=0.2)
        self.assertEqual(result, [])

    def test_error_prone_sorted_descending(self) -> None:
        for _ in range(8):
            self.tracker.track("a", success=True)
        for _ in range(2):
            self.tracker.track("a", success=False)  # 20%
        for _ in range(5):
            self.tracker.track("b", success=True)
        for _ in range(5):
            self.tracker.track("b", success=False)  # 50%
        result = self.tracker.get_error_prone_features(min_calls=5, error_threshold=0.1)
        self.assertEqual(result[0][0], "b")
        self.assertGreater(result[0][1], result[1][1])

    def test_error_prone_empty_stats(self) -> None:
        self.assertEqual(self.tracker.get_error_prone_features(), [])


class TestUsageTrackerReport(unittest.TestCase):
    """generate_report() coverage (lines 140-200)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.persist = os.path.join(self.tmpdir, "stats.json")
        self.tracker = UsageTracker(persist_file=self.persist)

    def test_report_empty_stats(self) -> None:
        report = self.tracker.generate_report()
        self.assertIn("DevSquad", report)
        self.assertIn("总调用次数", report)
        self.assertIn("0", report)

    def test_report_includes_top_features(self) -> None:
        for _ in range(3):
            self.tracker.track("dispatcher.dispatch", success=True)
        report = self.tracker.generate_report()
        self.assertIn("dispatcher.dispatch", report)
        self.assertIn("Top 10", report)

    def test_report_includes_component_breakdown(self) -> None:
        for _ in range(3):
            self.tracker.track("dispatcher.dispatch")
        for _ in range(2):
            self.tracker.track("coordinator.run")
        report = self.tracker.generate_report()
        self.assertIn("按组件分类", report)
        self.assertIn("dispatcher", report)
        self.assertIn("coordinator", report)

    def test_report_includes_error_prone_section(self) -> None:
        for _ in range(5):
            self.tracker.track("buggy.feature", success=False)
        for _ in range(5):
            self.tracker.track("buggy.feature", success=True)
        report = self.tracker.generate_report()
        self.assertIn("高错误率", report)
        self.assertIn("buggy.feature", report)

    def test_report_omits_error_prone_section_when_none(self) -> None:
        for _ in range(10):
            self.tracker.track("good.feature", success=True)
        report = self.tracker.generate_report()
        self.assertNotIn("高错误率", report)

    def test_report_includes_frequency_distribution(self) -> None:
        # low freq (1-10)
        self.tracker.track("low.freq")
        # mid freq (10-100)
        for _ in range(15):
            self.tracker.track("mid.freq")
        # high freq (>100)
        for _ in range(105):
            self.tracker.track("high.freq")
        report = self.tracker.generate_report()
        self.assertIn("使用频率分布", report)
        self.assertIn("高频", report)
        self.assertIn("中频", report)
        self.assertIn("低频", report)

    def test_report_with_no_dot_feature_goes_to_other(self) -> None:
        self.tracker.track("standalone")  # no dot → "other" component
        report = self.tracker.generate_report()
        self.assertIn("other", report)

    def test_report_total_calls_and_errors(self) -> None:
        for _ in range(7):
            self.tracker.track("feat.x", success=True)
        for _ in range(3):
            self.tracker.track("feat.x", success=False)
        report = self.tracker.generate_report()
        self.assertIn("10", report)  # total calls
        self.assertIn("3", report)  # total errors


class TestUsageTrackerSaveLoadClearExport(unittest.TestCase):
    """save / _load_stats / clear / export_json (lines 208-245)."""

    def test_save_writes_file(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        tracker.track("feat.a")
        tracker.track("feat.b")
        self.assertTrue(tracker.save())
        self.assertTrue(os.path.exists(persist))
        with open(persist, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIn("feat.a", data)
        self.assertIn("feat.b", data)

    def test_save_returns_true_on_empty_stats(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        self.assertTrue(tracker.save())

    def test_save_failure_returns_false(self) -> None:
        tracker = UsageTracker(persist_file="/nonexistent/dir/stats.json")
        tracker.track("feat.a")
        self.assertFalse(tracker.save())

    def test_load_restores_stats_from_file(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        tracker.track("loaded.feat", success=True)
        tracker.track("loaded.feat", success=False)
        tracker.save()

        # New tracker loads from same file
        tracker2 = UsageTracker(persist_file=persist)
        stats = tracker2.get_stats("loaded.feat")
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["errors"], 1)

    def test_load_corrupted_json_does_not_crash(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        with open(persist, "w", encoding="utf-8") as f:
            f.write("{not valid json")
        tracker = UsageTracker(persist_file=persist)
        self.assertEqual(tracker.get_stats(), {})

    def test_load_nonexistent_file_does_not_crash(self) -> None:
        tracker = UsageTracker(persist_file="/nonexistent/path/stats.json")
        self.assertEqual(tracker.get_stats(), {})

    def test_clear_returns_count_and_empties_stats(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        tracker.track("a")
        tracker.track("b")
        tracker.track("c")
        count = tracker.clear()
        self.assertEqual(count, 3)
        self.assertEqual(tracker.get_stats(), {})

    def test_clear_empty_returns_zero(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        self.assertEqual(tracker.clear(), 0)

    def test_export_json_returns_valid_json(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        tracker.track("feat.a")
        tracker.track("feat.b")
        exported = tracker.export_json()
        data = json.loads(exported)
        self.assertIn("feat.a", data)
        self.assertIn("feat.b", data)

    def test_export_json_empty(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)
        data = json.loads(tracker.export_json())
        self.assertEqual(data, {})


class TestUsageTrackerTrackMetadata(unittest.TestCase):
    """track() with metadata and error tracking (lines 66-73)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.persist = os.path.join(self.tmpdir, "stats.json")
        self.tracker = UsageTracker(persist_file=self.persist)

    def test_track_success_increments_count_no_error(self) -> None:
        self.tracker.track("feat", success=True)
        stats = self.tracker.get_stats("feat")
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["errors"], 0)

    def test_track_failure_increments_error(self) -> None:
        self.tracker.track("feat", success=False)
        stats = self.tracker.get_stats("feat")
        self.assertEqual(stats["count"], 1)
        self.assertEqual(stats["errors"], 1)

    def test_track_with_metadata_stores_it(self) -> None:
        self.tracker.track("feat", metadata={"key": "value"})
        stats = self.tracker.get_stats("feat")
        self.assertIn("metadata", stats)
        self.assertEqual(stats["metadata"], [{"key": "value"}])

    def test_track_metadata_keeps_only_last_10(self) -> None:
        for i in range(15):
            self.tracker.track("feat", metadata={"i": i})
        stats = self.tracker.get_stats("feat")
        self.assertEqual(len(stats["metadata"]), 10)
        # Should keep the last 10 (i=5..14)
        self.assertEqual(stats["metadata"][0], {"i": 5})
        self.assertEqual(stats["metadata"][-1], {"i": 14})

    def test_track_sets_first_and_last_used(self) -> None:
        self.tracker.track("feat")
        stats = self.tracker.get_stats("feat")
        self.assertIsNotNone(stats["first_used"])
        self.assertEqual(stats["first_used"], stats["last_used"])
        self.tracker.track("feat")
        stats = self.tracker.get_stats("feat")
        # first_used stays the same; last_used updates
        self.assertEqual(stats["count"], 2)


class TestUsageTrackerThreadSafety(unittest.TestCase):
    """Verify thread-safe operation under concurrent access."""

    def test_concurrent_track_no_data_loss(self) -> None:
        tmpdir = tempfile.mkdtemp()
        persist = os.path.join(tmpdir, "stats.json")
        tracker = UsageTracker(persist_file=persist)

        def worker():
            for _ in range(50):
                tracker.track("concurrent.feat", success=True)

        threads = [threading.Thread(target=worker) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        stats = tracker.get_stats("concurrent.feat")
        self.assertEqual(stats["count"], 200)


class TestUsageTrackerModuleFunctions(unittest.TestCase):
    """Module-level convenience functions (lines 262-305)."""

    def setUp(self) -> None:
        # Reset the global tracker singleton so tests are isolated
        ut_module._global_tracker = None

    def tearDown(self) -> None:
        ut_module._global_tracker = None
        # Remove the default persist file created by the global tracker
        default_persist = ".usage_stats.json"
        if os.path.exists(default_persist):
            os.remove(default_persist)

    def test_get_tracker_returns_singleton(self) -> None:
        t1 = get_tracker()
        t2 = get_tracker()
        self.assertIs(t1, t2)

    def test_track_usage_via_module_function(self) -> None:
        track_usage("module.feat", success=True)
        stats = get_usage_stats("module.feat")
        self.assertEqual(stats["count"], 1)

    def test_get_usage_stats_all_via_module_function(self) -> None:
        track_usage("module.a")
        track_usage("module.b")
        stats = get_usage_stats()
        self.assertIn("module.a", stats)
        self.assertIn("module.b", stats)

    def test_generate_usage_report_via_module_function(self) -> None:
        track_usage("report.feat")
        report = generate_usage_report()
        self.assertIn("DevSquad", report)
        self.assertIn("report.feat", report)

    def test_save_usage_stats_via_module_function(self) -> None:
        track_usage("save.feat")
        # Default persist file is .usage_stats.json in cwd; save should succeed
        self.assertTrue(save_usage_stats())

    def test_get_tracker_thread_safe_creation(self) -> None:
        results: list[UsageTracker] = []

        def worker():
            results.append(get_tracker())

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        # All threads get the same singleton
        self.assertTrue(all(r is results[0] for r in results))


if __name__ == "__main__":
    unittest.main()
