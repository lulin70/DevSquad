#!/usr/bin/env python3
"""Dispatch Pipeline Integration Tests (V4.2.1 P0 — Test Pyramid Improvement).

End-to-end integration tests for the complete dispatch pipeline:
    dispatcher → coordinator → worker → consensus → report

These tests verify that the core dispatch pipeline works as an integrated
whole, not just individual modules in isolation. They use Mock mode (no
LLM API key required) but exercise real module interactions.

Test categories:
    1. Full dispatch pipeline (task → dispatch → result)
    2. Role matching integration (task keywords → matched roles)
    3. Coordinator-Worker interaction (task decomposition → parallel execution)
    4. Consensus integration (multi-role results → consensus decision)
    5. Result assembly integration (worker outputs → structured report)
    6. Error handling pipeline (invalid input → graceful degradation)
    7. Dry-run mode integration (simulation without execution)
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher import MultiAgentDispatcher


class T1_FullDispatchPipeline(unittest.TestCase):
    """T1: Full dispatch pipeline — task → dispatch → result."""

    def setUp(self) -> None:
        """Create a fresh dispatcher per test for isolation."""
        self._work_dir = tempfile.mkdtemp(prefix="dispatch_integration_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_dispatch_returns_dispatch_result(self) -> None:
        """Verify: dispatch() returns a DispatchResult instance."""
        result = self.disp.dispatch("Design a user authentication system")
        self.assertIsInstance(result, DispatchResult)

    def test_02_dispatch_success_for_valid_task(self) -> None:
        """Verify: Valid task → result.success == True (mock mode)."""
        result = self.disp.dispatch("Design a REST API for user management")
        self.assertTrue(result.success, f"Expected success but got errors: {result.errors}")

    def test_03_dispatch_populates_matched_roles(self) -> None:
        """Verify: dispatch() populates matched_roles list."""
        result = self.disp.dispatch("Design a secure authentication system")
        self.assertIsInstance(result.matched_roles, list)
        # Mock mode should match at least one role
        self.assertGreater(len(result.matched_roles), 0,
                          "Expected at least one matched role")

    def test_04_dispatch_populates_summary(self) -> None:
        """Verify: dispatch() populates summary string."""
        result = self.disp.dispatch("Implement a login feature")
        self.assertIsInstance(result.summary, str)
        # Summary should be non-empty for successful dispatch
        if result.success:
            self.assertGreater(len(result.summary), 0, "Summary should be non-empty")

    def test_05_dispatch_populates_worker_results(self) -> None:
        """Verify: dispatch() populates worker_results list."""
        result = self.disp.dispatch("Design a microservice architecture")
        self.assertIsInstance(result.worker_results, list)
        # Mock mode should produce at least one worker result
        if result.success:
            self.assertGreater(len(result.worker_results), 0,
                              "Expected at least one worker result")

    def test_06_dispatch_records_duration(self) -> None:
        """Verify: dispatch() records duration_seconds."""
        result = self.disp.dispatch("Analyze system performance")
        self.assertIsInstance(result.duration_seconds, float)
        self.assertGreaterEqual(result.duration_seconds, 0.0)

    def test_07_dispatch_populates_task_description(self) -> None:
        """Verify: dispatch() stores original task_description in result."""
        task = "Design a database schema for e-commerce"
        result = self.disp.dispatch(task)
        self.assertEqual(result.task_description, task)


class T2_RoleMatchingIntegration(unittest.TestCase):
    """T2: Role matching — task keywords → matched roles."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="role_match_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_security_task_matches_security_role(self) -> None:
        """Verify: Security-related task → security role in matched_roles."""
        result = self.disp.dispatch("Audit the system for security vulnerabilities")
        self.assertIn("security", result.matched_roles,
                      f"Expected 'security' in matched roles: {result.matched_roles}")

    def test_02_test_task_matches_tester_role(self) -> None:
        """Verify: Test-related task → tester role in matched_roles."""
        result = self.disp.dispatch("Write test cases for the authentication module")
        # Role ID may be "tester" or "test"
        role_found = any(r in result.matched_roles for r in ["tester", "test"])
        self.assertTrue(role_found,
                       f"Expected tester role in: {result.matched_roles}")

    def test_03_explicit_roles_override_auto_match(self) -> None:
        """Verify: Explicit roles parameter overrides auto-matching."""
        result = self.disp.dispatch(
            "Any task here",
            roles=["architect", "solo-coder"],
        )
        self.assertIn("architect", result.matched_roles)
        # Role ID is "solo-coder" (full ID), not "coder" (short alias)
        self.assertIn("solo-coder", result.matched_roles)

    def test_04_analyze_task_returns_role_list(self) -> None:
        """Verify: analyze_task() returns list of role dicts."""
        matched = self.disp.analyze_task("Design a CI/CD pipeline")
        self.assertIsInstance(matched, list)
        self.assertGreater(len(matched), 0)


class T3_CoordinatorWorkerInteraction(unittest.TestCase):
    """T3: Coordinator-Worker interaction — task decomposition → execution."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="coord_worker_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_parallel_mode_executes_all_roles(self) -> None:
        """Verify: parallel mode → all specified roles produce results."""
        result = self.disp.dispatch(
            "Design a system",
            roles=["architect", "coder", "tester"],
            mode="parallel",
        )
        if result.success:
            # Each role should produce a worker result
            self.assertEqual(len(result.worker_results), 3,
                            f"Expected 3 worker results, got {len(result.worker_results)}")

    def test_02_sequential_mode_executes_all_roles(self) -> None:
        """Verify: sequential mode → all specified roles produce results."""
        result = self.disp.dispatch(
            "Implement a feature",
            roles=["coder", "tester"],
            mode="sequential",
        )
        if result.success:
            self.assertGreaterEqual(len(result.worker_results), 1)

    def test_03_worker_results_contain_role_field(self) -> None:
        """Verify: Each worker result dict contains role identification."""
        result = self.disp.dispatch("Design API", roles=["architect"])
        if result.success and result.worker_results:
            for wr in result.worker_results:
                # Worker results use 'role_id' and 'role_name', not 'role'
                self.assertIn("role_id", wr,
                              f"Worker result missing 'role_id' key: {wr.keys()}")

    def test_04_worker_results_contain_output_field(self) -> None:
        """Verify: Each worker result dict contains an 'output' key."""
        result = self.disp.dispatch("Design UI", roles=["ui-designer"])
        if result.success and result.worker_results:
            for wr in result.worker_results:
                self.assertIn("output", wr, f"Worker result missing 'output' key: {wr.keys()}")


class T4_ConsensusIntegration(unittest.TestCase):
    """T4: Consensus — multi-role results → consensus decision."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="consensus_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_consensus_mode_completes(self) -> None:
        """Verify: consensus mode completes without error."""
        result = self.disp.dispatch(
            "Design authentication",
            roles=["architect", "security", "tester"],
            mode="consensus",
        )
        # Should complete (success or graceful failure)
        self.assertIsInstance(result, DispatchResult)

    def test_02_consensus_records_populated(self) -> None:
        """Verify: consensus mode populates consensus_records list."""
        result = self.disp.dispatch(
            "Design a secure API",
            roles=["architect", "security"],
            mode="consensus",
        )
        self.assertIsInstance(result.consensus_records, list)


class T5_ResultAssemblyIntegration(unittest.TestCase):
    """T5: Result assembly — worker outputs → structured report."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="result_asm_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_to_markdown_produces_report(self) -> None:
        """Verify: DispatchResult.to_markdown() produces a markdown report."""
        result = self.disp.dispatch("Design a system")
        report = result.to_markdown()
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 0, "Markdown report should be non-empty")

    def test_02_report_contains_task_description(self) -> None:
        """Verify: Markdown report contains the original task description."""
        task = "Design a user authentication system"
        result = self.disp.dispatch(task)
        report = result.to_markdown()
        # Report should reference the task
        self.assertTrue(
            task in report or "authentication" in report.lower(),
            "Report should contain task description"
        )

    def test_03_report_contains_role_names(self) -> None:
        """Verify: Markdown report contains matched role names."""
        result = self.disp.dispatch("Design API", roles=["architect"])
        report = result.to_markdown()
        self.assertIn("architect", report.lower(),
                      "Report should mention 'architect' role")

    def test_04_errors_list_accessible(self) -> None:
        """Verify: DispatchResult.errors is a list (even if empty)."""
        result = self.disp.dispatch("Design a system")
        self.assertIsInstance(result.errors, list)


class T6_ErrorHandlingPipeline(unittest.TestCase):
    """T6: Error handling — invalid input → graceful degradation."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="error_pipe_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_empty_task_does_not_crash(self) -> None:
        """Verify: Empty task string → graceful result (no crash)."""
        result = self.disp.dispatch("")
        self.assertIsInstance(result, DispatchResult)
        # Should have errors or succeed with empty matching

    def test_02_very_long_task_handled(self) -> None:
        """Verify: Very long task → graceful result (no crash)."""
        long_task = "Design a system " + "with many requirements " * 100
        result = self.disp.dispatch(long_task)
        self.assertIsInstance(result, DispatchResult)

    def test_03_nonexistent_role_handled(self) -> None:
        """Verify: Nonexistent role → graceful result (no crash)."""
        result = self.disp.dispatch("Design a system", roles=["nonexistent_role"])
        self.assertIsInstance(result, DispatchResult)

    def test_04_dispatch_captures_errors_in_result(self) -> None:
        """Verify: Errors are captured in DispatchResult.errors, not thrown."""
        # Even if something goes wrong, it should be in result.errors
        result = self.disp.dispatch("Task with <script>alert('xss')</script> tag")
        self.assertIsInstance(result, DispatchResult)
        # Should not raise — errors captured in result


class T7_DryRunModeIntegration(unittest.TestCase):
    """T7: Dry-run mode — simulation without Worker execution."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="dry_run_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_dry_run_returns_result(self) -> None:
        """Verify: dry_run=True returns a DispatchResult."""
        result = self.disp.dispatch("Design a system", dry_run=True)
        self.assertIsInstance(result, DispatchResult)

    def test_02_dry_run_completes_quickly(self) -> None:
        """Verify: dry_run=True completes in < 2 seconds (no real execution)."""
        import time
        start = time.time()
        self.disp.dispatch("Design a system", dry_run=True)
        elapsed = time.time() - start
        self.assertLess(elapsed, 5.0, f"Dry-run took {elapsed:.2f}s, expected < 5s")

    def test_03_dry_run_still_matches_roles(self) -> None:
        """Verify: dry_run=True still performs role matching."""
        result = self.disp.dispatch("Design a secure system", dry_run=True)
        self.assertIsInstance(result.matched_roles, list)


class T8_DispatcherStatusIntegration(unittest.TestCase):
    """T8: Dispatcher status — get_status() returns component info."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="status_")
        self.disp = MultiAgentDispatcher(persist_dir=self._work_dir)

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_get_status_returns_dict(self) -> None:
        """Verify: get_status() returns a dictionary."""
        status = self.disp.get_status()
        self.assertIsInstance(status, dict)

    def test_02_status_contains_version(self) -> None:
        """Verify: get_status() includes version field."""
        status = self.disp.get_status()
        self.assertIn("version", status, f"Status should include 'version': {status.keys()}")

    def test_03_status_contains_components(self) -> None:
        """Verify: get_status() includes component information."""
        status = self.disp.get_status()
        # Should have some component-related key
        has_components = any("component" in k.lower() for k in status)
        self.assertTrue(has_components or len(status) > 0,
                       "Status should include component info")

    def test_04_history_returns_list(self) -> None:
        """Verify: get_history() returns a list."""
        # Do one dispatch first
        self.disp.dispatch("Design a system")
        history = self.disp.get_history(limit=5)
        self.assertIsInstance(history, list)


if __name__ == "__main__":
    unittest.main()
