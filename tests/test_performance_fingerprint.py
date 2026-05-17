#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PerformanceFingerprint - Unit Tests

Tests for execution performance fingerprint aggregation module.
"""

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import dataclass
from typing import Any, Optional

from scripts.collaboration.performance_fingerprint import PerformanceFingerprint


@dataclass
class MockDispatchResult:
    """Mock DispatchResult-like object for testing."""
    success: bool = True
    error_message: Optional[str] = None
    error_type: Optional[str] = None


class TestPerformanceFingerprint(unittest.TestCase):
    """Test suite for PerformanceFingerprint."""

    def setUp(self):
        """Create a temporary directory for each test."""
        self.test_dir = tempfile.mkdtemp(prefix="fp_test_")
        self.fp = PerformanceFingerprint(persist_dir=self.test_dir)

    def tearDown(self):
        """Clean up temporary directory."""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_record_execution(self):
        """Test recording an execution and verifying field completeness."""
        result = MockDispatchResult(success=True)
        timing = {"total": 12.5, "planning": 2.0, "coding": 8.0, "review": 2.5}
        roles = ["architect", "coder", "tester"]

        fid = self.fp.record_execution(
            task="Implement user authentication system",
            result=result,
            timing=timing,
            roles_used=roles,
            intent="feature_implementation",
            mode="auto",
        )

        self.assertTrue(fid.startswith("fp_"))
        self.assertEqual(self.fp.get_fingerprint_count(), 1)

        with self.fp._lock:
            fp_record = self.fp._fingerprints[0]

        self.assertEqual(fp_record["task"], "Implement user authentication system")
        self.assertTrue(fp_record["success"])
        self.assertEqual(fp_record["timing"], timing)
        self.assertEqual(fp_record["total_duration"], 12.5)
        self.assertEqual(fp_record["roles_used"], sorted(roles))
        self.assertEqual(fp_record["role_combo"], ("architect", "coder", "tester"))
        self.assertEqual(fp_record["intent"], "feature_implementation")
        self.assertEqual(fp_record["mode"], "auto")
        self.assertIn("fingerprint_id", fp_record)
        self.assertIn("task_hash", fp_record)
        self.assertIn("created_at", fp_record)
        self.assertIsInstance(fp_record["error_patterns"], list)

    def test_find_similar(self):
        """Test finding similar tasks after recording multiple executions."""
        tasks = [
            "Implement user login page with authentication",
            "Add user registration form validation",
            "Create password reset functionality",
            "Build dashboard analytics charts",
            "Design database schema for users",
        ]

        for task in tasks:
            self.fp.record_execution(
                task=task,
                result=MockDispatchResult(success=True),
                timing={"total": 10.0},
                roles_used=["coder"],
            )

        similar = self.fp.find_similar("Add login authentication feature", top_k=3)

        self.assertLessEqual(len(similar), 3)
        if similar:
            self.assertIn("similarity", similar[0])
            self.assertGreater(similar[0]["similarity"], 0)

            similarities = [s["similarity"] for s in similar]
            self.assertEqual(similarities, sorted(similarities, reverse=True))

    def test_success_pattern(self):
        """Test extracting success patterns for a role combination."""
        role_combo = ("architect", "coder")

        for i in range(8):
            success = i < 6
            self.fp.record_execution(
                task=f"Task {i} description here",
                result=MockDispatchResult(success=success),
                timing={"total": 5.0 + i},
                roles_used=list(role_combo),
                intent="feature_implementation" if success else "bug_fix",
            )

        pattern = self.fp.get_success_pattern(role_combo)

        self.assertEqual(pattern["role_combo"], role_combo)
        self.assertEqual(pattern["count"], 8)
        self.assertAlmostEqual(pattern["success_rate"], 6 / 8, places=2)
        self.assertGreater(pattern["avg_duration"], 0)
        self.assertIsInstance(pattern["common_intents"], list)

    def test_persist_and_load(self):
        """Test persistence and loading cycle."""
        result = MockDispatchResult(success=True)
        self.fp.record_execution(
            task="Persist this task",
            result=result,
            timing={"total": 7.5},
            roles_used=["tester"],
            intent="testing",
        )

        persist_path = os.path.join(self.test_dir, "fingerprints.json")
        self.assertTrue(os.path.exists(persist_path))

        with open(persist_path, "r", encoding="utf-8") as f:
            saved_data = json.load(f)

        self.assertEqual(saved_data["count"], 1)
        self.assertEqual(len(saved_data["fingerprints"]), 1)
        self.assertEqual(saved_data["fingerprints"][0]["task"], "Persist this task")

        new_fp = PerformanceFingerprint(persist_dir=self.test_dir)
        self.assertEqual(new_fp.get_fingerprint_count(), 1)

        with new_fp._lock:
            loaded_task = new_fp._fingerprints[0]["task"]

        self.assertEqual(loaded_task, "Persist this task")

    def test_cold_start(self):
        """Test graceful degradation when no historical data exists."""
        empty_fp = PerformanceFingerprint(persist_dir=self.test_dir)

        similar = empty_fp.find_similar("Any query task")
        self.assertEqual(similar, [])

        stats = empty_fp.get_stats()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["success_rate"], 0.0)
        self.assertEqual(stats["top_roles"], [])

        patterns = empty_fp.get_failure_patterns()
        self.assertEqual(patterns, [])

        pattern = empty_fp.get_success_pattern(("architect",))
        self.assertEqual(pattern["count"], 0)
        self.assertEqual(pattern["success_rate"], 0.0)

    def test_tfidf_accuracy(self):
        """Test TF-IDF similarity calculation correctness."""
        sim_identical = self.fp._tfidf_similarity(
            "Implement user authentication",
            "Implement user authentication",
        )
        self.assertAlmostEqual(sim_identical, 1.0, places=2)

        sim_partial_overlap = self.fp._tfidf_similarity(
            "Implement user authentication",
            "User login page design",
        )
        sim_less_overlap = self.fp._tfidf_similarity(
            "Implement user authentication",
            "Design database schema optimization",
        )
        self.assertGreater(sim_identical, sim_partial_overlap)
        self.assertGreaterEqual(sim_partial_overlap, sim_less_overlap)

        sim_empty_a = self.fp._tfidf_similarity("", "Some text")
        self.assertEqual(sim_empty_a, 0.0)

        sim_empty_b = self.fp._tfidf_similarity("Some text", "")
        self.assertEqual(sim_empty_b, 0.0)

        sim_chinese = self.fp._tfidf_similarity(
            "实现用户登录功能",
            "用户认证系统开发",
        )
        self.assertGreater(sim_chinese, 0)


class TestPerformanceFingerprintErrorPatterns(unittest.TestCase):
    """Test error pattern extraction."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fp_err_test_")
        self.fp = PerformanceFingerprint(persist_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_timeout_error(self):
        """Test timeout error pattern detection."""
        result = MockDispatchResult(
            success=False,
            error_message="Request timed out after 30 seconds",
            error_type="TimeoutError",
        )
        patterns = self.fp._extract_error_patterns(result)
        self.assertIn("timeout", patterns)

    def test_connection_error(self):
        """Test connection error pattern detection."""
        result = MockDispatchResult(
            success=False,
            error_message="Connection refused to database server",
            error_type="ConnectionError",
        )
        patterns = self.fp._extract_error_patterns(result)
        self.assertIn("connection_error", patterns)

    def test_permission_error(self):
        """Test permission error pattern detection."""
        result = MockDispatchResult(
            success=False,
            error_message="Access denied: insufficient permissions",
            error_type="PermissionError",
        )
        patterns = self.fp._extract_error_patterns(result)
        self.assertIn("permission_error", patterns)

    def test_unknown_error(self):
        """Test unknown error fallback pattern."""
        result = MockDispatchResult(
            success=False,
            error_message="Something weird happened xyz123",
            error_type="WeirdError",
        )
        patterns = self.fp._extract_error_patterns(result)
        self.assertIn("unknown_error", patterns)

    def test_null_result(self):
        """Test handling of None result."""
        patterns = self.fp._extract_error_patterns(None)
        self.assertEqual(patterns, [])


class TestPerformanceFingerprintFailurePatterns(unittest.TestCase):
    """Test failure pattern aggregation."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fp_fail_test_")
        self.fp = PerformanceFingerprint(persist_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_failure_aggregation(self):
        """Test aggregating multiple failures into patterns."""
        errors = [
            ("TimeoutError", "Request timed out"),
            ("TimeoutError", "Operation timed out"),
            ("ConnectionError", "Network connection refused"),
            (None, None),
        ]

        for err_type, err_msg in errors:
            result = MockDispatchResult(
                success=False,
                error_message=err_msg,
                error_type=err_type,
            )
            self.fp.record_execution(
                task=f"Failed task {err_type or 'unknown'}",
                result=result,
                timing={"total": 5.0},
                roles_used=["coder"],
            )

        patterns = self.fp.get_failure_patterns()
        self.assertGreater(len(patterns), 0)

        timeout_patterns = [p for p in patterns if p["pattern"] == "timeout"]
        self.assertEqual(len(timeout_patterns), 1)
        self.assertEqual(timeout_patterns[0]["count"], 2)


class TestPerformanceFingerprintThreadSafety(unittest.TestCase):
    """Test thread safety of PerformanceFingerprint."""

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="fp_thread_test_")
        self.fp = PerformanceFingerprint(persist_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_concurrent_writes(self):
        """Test concurrent record_execution calls."""
        import threading

        num_threads = 10
        records_per_thread = 5
        errors = []

        def worker(thread_id):
            try:
                for i in range(records_per_thread):
                    self.fp.record_execution(
                        task=f"Thread {thread_id} task {i}",
                        result=MockDispatchResult(success=True),
                        timing={"total": 1.0},
                        roles_used=["worker"],
                    )
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=worker, args=(tid,))
            for tid in range(num_threads)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0)
        expected_total = num_threads * records_per_thread
        self.assertEqual(self.fp.get_fingerprint_count(), expected_total)


if __name__ == "__main__":
    unittest.main()
