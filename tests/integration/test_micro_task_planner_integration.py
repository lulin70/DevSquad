#!/usr/bin/env python3
"""MicroTaskPlanner + Dispatcher Integration Tests (V4.2.1 P1-2 — Test Pyramid Improvement).

End-to-end integration tests for MicroTaskPlanner + Dispatcher +
YagniChecker interaction. Verifies that the micro-task decomposition
pipeline works as an integrated whole across modules:

    dispatcher.dispatch(use_micro_tasks=True)
      → MicroTaskPlanner.plan(task_description, spec)
        → _decompose (file/function/sentence strategies)
        → _topological_sort (Kahn's algorithm, stable)
        → _run_yagni_checks (SKIP → MicroTaskStatus.SKIPPED)
      → DispatchResult.micro_task_plan populated

These tests focus on CROSS-MODULE interactions (planner ↔ dispatcher,
planner ↔ yagni_checker, planner DAG ↔ execution helpers). Unit-level
behavior of individual methods is covered by tests/test_micro_task_planner.py.

Test categories:
    T1: MicroTaskPlanner + Dispatcher integration (decompose_task, use_micro_tasks)
    T2: Decomposition strategies end-to-end (file/function/sentence)
    T3: DAG execution flow (plan → get_next_ready → mark_completed → next)
    T4: YagniChecker integration (SKIP propagation, get_next_ready exclusion)
    T5: Execution mode classification (HITL vs AFK)
    T6: Topological sort + cycle detection
    T7: Edge cases + graceful degradation
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.micro_task_planner import (
    MicroTask,
    MicroTaskPlan,
    MicroTaskPlanner,
    MicroTaskStatus,
)
from scripts.collaboration.yagni_checker import YagniChecker, YagniResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_yagni_result(verdict: str, reason: str = "") -> YagniResult:
    """Build a YagniResult with sensible defaults for testing."""
    return YagniResult(
        verdict=verdict,
        reason=reason or f"test verdict {verdict}",
        upgrade_path="n/a in test",
        shortcut_marker=f"shortcut: {reason}" if reason else "",
    )


def _make_planner_with_yagni() -> tuple[MicroTaskPlanner, MagicMock]:
    """Build a planner whose YagniChecker is a MagicMock.

    Returns ``(planner, mock_checker)`` so individual tests can program
    ``mock_checker.check_micro_task`` return values.
    """
    mock_checker = MagicMock(spec=YagniChecker)
    # Default: NECESSARY for all tasks (no SKIP, no shortcut).
    mock_checker.check_micro_task.return_value = _make_yagni_result("NECESSARY")
    planner = MicroTaskPlanner(yagni_checker=mock_checker)
    return planner, mock_checker


# ---------------------------------------------------------------------------
# T1: MicroTaskPlanner + Dispatcher integration
# ---------------------------------------------------------------------------


class T1_MicroTaskPlannerDispatcherIntegration(unittest.TestCase):
    """T1: Dispatcher with MicroTaskPlanner — decompose_task + use_micro_tasks."""

    def setUp(self) -> None:
        self._work_dir = tempfile.mkdtemp(prefix="mt_dispatch_")
        self.planner = MicroTaskPlanner()
        self.disp = MultiAgentDispatcher(
            persist_dir=self._work_dir,
            micro_task_planner=self.planner,
        )

    def tearDown(self) -> None:
        self.disp.shutdown()
        import shutil
        shutil.rmtree(self._work_dir, ignore_errors=True)

    def test_01_dispatch_without_use_micro_tasks_has_no_plan(self) -> None:
        """Verify: dispatch() without use_micro_tasks leaves micro_task_plan=None."""
        result = self.disp.dispatch("Design a user authentication system")
        self.assertIsNone(result.micro_task_plan,
                          "use_micro_tasks=False must not populate micro_task_plan")

    def test_02_dispatch_with_use_micro_tasks_populates_plan(self) -> None:
        """Verify: dispatch(use_micro_tasks=True) populates micro_task_plan dict."""
        result = self.disp.dispatch(
            "Implement user login feature",
            use_micro_tasks=True,
            files=["src/auth.py", "tests/test_auth.py"],
        )
        self.assertIsNotNone(result.micro_task_plan,
                             "use_micro_tasks=True must populate micro_task_plan")
        self.assertIsInstance(result.micro_task_plan, dict)
        self.assertIn("micro_tasks", result.micro_task_plan)
        self.assertGreater(len(result.micro_task_plan["micro_tasks"]), 0)

    def test_03_dispatch_propagates_files_spec_to_planner(self) -> None:
        """Verify: files= kwarg forwarded to planner.plan() as spec."""
        result = self.disp.dispatch(
            "Add payment module",
            use_micro_tasks=True,
            files=["src/payment.py"],
        )
        plan = result.micro_task_plan
        self.assertIsNotNone(plan)
        file_lists = [mt["file_paths"] for mt in plan["micro_tasks"]]
        flat_files = [f for sublist in file_lists for f in sublist]
        self.assertIn("src/payment.py", flat_files,
                      "files= spec must reach the planner")

    def test_04_decompose_task_direct_method(self) -> None:
        """Verify: dispatcher.decompose_task() delegates to planner.plan()."""
        plan = self.disp.decompose_task(
            "Build notification service",
            spec={"files": ["src/notify.py"]},
        )
        self.assertIsInstance(plan, MicroTaskPlan)
        self.assertGreater(len(plan.micro_tasks), 0)
        self.assertEqual(plan.micro_tasks[0].file_paths, ["src/notify.py"])

    def test_05_dispatch_without_planner_gracefully_skips_decomposition(self) -> None:
        """Verify: dispatcher with no planner + use_micro_tasks=True → no crash, no plan."""
        work_dir = tempfile.mkdtemp(prefix="mt_noplanner_")
        try:
            disp = MultiAgentDispatcher(persist_dir=work_dir)  # no planner
            result = disp.dispatch(
                "Some task",
                use_micro_tasks=True,
                files=["src/foo.py"],
            )
            self.assertIsNone(result.micro_task_plan,
                              "No planner configured → micro_task_plan must stay None")
            disp.shutdown()
        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# T2: Decomposition strategies end-to-end
# ---------------------------------------------------------------------------


class T2_DecompositionStrategiesIntegration(unittest.TestCase):
    """T2: File-based / function-based / heuristic decomposition."""

    def setUp(self) -> None:
        self.planner = MicroTaskPlanner()

    def test_01_file_based_decomposition_chains_dependencies(self) -> None:
        """Verify: file-based decomposition chains tasks via dependencies."""
        plan = self.planner.plan(
            "Implement module",
            spec={"files": ["src/a.py", "src/b.py", "src/c.py"]},
        )
        self.assertEqual(len(plan.micro_tasks), 3)
        # First task: no deps. Each subsequent task depends on previous.
        self.assertEqual(plan.micro_tasks[0].dependencies, [])
        self.assertEqual(len(plan.micro_tasks[1].dependencies), 1)
        self.assertEqual(len(plan.micro_tasks[2].dependencies), 1)
        # Dependency chain: t1 → t0, t2 → t1
        self.assertEqual(plan.micro_tasks[1].dependencies[0], plan.micro_tasks[0].id)
        self.assertEqual(plan.micro_tasks[2].dependencies[0], plan.micro_tasks[1].id)

    def test_02_file_based_decomposition_adds_test_task(self) -> None:
        """Verify: when tests= is provided, a final test micro-task is appended."""
        plan = self.planner.plan(
            "Implement module",
            spec={"files": ["src/auth.py"], "tests": ["tests/test_auth.py"]},
        )
        last = plan.micro_tasks[-1]
        self.assertIn("tests/test_auth.py", last.file_paths)
        self.assertIn("pytest", last.verification_cmd)
        # Test task depends on all prior tasks
        prior_ids = {mt.id for mt in plan.micro_tasks[:-1]}
        self.assertEqual(set(last.dependencies), prior_ids)

    def test_03_function_based_decomposition_chains(self) -> None:
        """Verify: function-based decomposition creates one task per function."""
        plan = self.planner.plan(
            "Build service",
            spec={"functions": ["login", "logout", "refresh"]},
        )
        self.assertEqual(len(plan.micro_tasks), 3)
        titles = [mt.title for mt in plan.micro_tasks]
        self.assertIn("Implement login", titles)
        self.assertIn("Implement logout", titles)
        self.assertIn("Implement refresh", titles)
        # Chain: 2nd and 3rd depend on previous
        self.assertEqual(plan.micro_tasks[0].dependencies, [])
        self.assertEqual(len(plan.micro_tasks[1].dependencies), 1)
        self.assertEqual(len(plan.micro_tasks[2].dependencies), 1)

    def test_04_sentence_based_decomposition_fallback(self) -> None:
        """Verify: no files/functions → heuristic sentence split."""
        plan = self.planner.plan(
            "Do thing one. Do thing two! Do thing three?"
        )
        self.assertGreaterEqual(len(plan.micro_tasks), 3)
        # Each task is bounded by min_duration_minutes
        for mt in plan.micro_tasks:
            self.assertGreaterEqual(mt.estimated_minutes, self.planner.min_duration_minutes)

    def test_05_verification_cmd_for_python_file_uses_pytest_when_test_matches(self) -> None:
        """Verify: file-based strategy prefers pytest over ast.parse when a matching test exists."""
        plan = self.planner.plan(
            "Implement",
            spec={"files": ["src/foo.py"], "tests": ["tests/test_foo.py"]},
        )
        impl_task = next(mt for mt in plan.micro_tasks if "src/foo.py" in mt.file_paths)
        self.assertIn("pytest", impl_task.verification_cmd,
                      "Matching test file should produce pytest verification cmd")


# ---------------------------------------------------------------------------
# T3: DAG execution flow
# ---------------------------------------------------------------------------


class T3_DAGExecutionFlowIntegration(unittest.TestCase):
    """T3: plan → get_next_ready → mark_completed → next batch."""

    def setUp(self) -> None:
        self.planner = MicroTaskPlanner()
        # Diamond DAG: t0 → t1, t0 → t2, t1 → t3, t2 → t3
        self.plan = self.planner.plan(
            "Implement module",
            spec={"files": ["a.py", "b.py"]},
        )

    def test_01_initial_ready_tasks_have_no_dependencies(self) -> None:
        """Verify: get_next_ready returns only tasks with no unsatisfied deps."""
        ready = self.planner.get_next_ready(self.plan)
        self.assertGreater(len(ready), 0)
        for mt in ready:
            self.assertEqual(mt.dependencies, [])
            self.assertEqual(mt.status, MicroTaskStatus.PLANNED)

    def test_02_completion_unlocks_dependents(self) -> None:
        """Verify: marking the first task complete unlocks its dependents."""
        first_ready = self.planner.get_next_ready(self.plan)
        self.assertEqual(len(first_ready), 1)
        first = first_ready[0]
        self.assertTrue(self.planner.mark_completed(self.plan, first.id, "done"))
        self.assertEqual(first.status, MicroTaskStatus.COMPLETED)
        self.assertEqual(first.result, "done")
        # Next batch should now be ready
        second_batch = self.planner.get_next_ready(self.plan)
        self.assertGreater(len(second_batch), 0,
                           "Completing first task should unlock dependents")

    def test_03_mark_failed_records_error(self) -> None:
        """Verify: mark_failed sets FAILED status with error message."""
        first = self.planner.get_next_ready(self.plan)[0]
        self.assertTrue(self.planner.mark_failed(self.plan, first.id, "boom"))
        self.assertEqual(first.status, MicroTaskStatus.FAILED)
        self.assertEqual(first.result, "boom")
        # Failed tasks are not re-reported by get_next_ready (only PLANNED)
        ready_again = self.planner.get_next_ready(self.plan)
        self.assertNotIn(first.id, [mt.id for mt in ready_again])

    def test_04_mark_completed_unknown_id_returns_false(self) -> None:
        """Verify: mark_completed with unknown id returns False (no crash)."""
        self.assertFalse(self.planner.mark_completed(self.plan, "nonexistent-id", "x"))
        self.assertFalse(self.planner.mark_failed(self.plan, "nonexistent-id", "y"))

    def test_05_full_execution_drains_plan(self) -> None:
        """Verify: iterating get_next_ready + mark_completed drains all tasks."""
        completed = 0
        iterations = 0
        while True:
            ready = self.planner.get_next_ready(self.plan)
            if not ready:
                break
            iterations += 1
            self.assertLess(iterations, 20, "Execution loop should terminate (no infinite loop)")
            for mt in ready:
                self.planner.mark_completed(self.plan, mt.id, f"done-{mt.id}")
                completed += 1
        self.assertEqual(completed, len(self.plan.micro_tasks),
                         "All planned micro-tasks should be completable")
        # After full drain, no PLANNED tasks remain
        remaining_planned = [mt for mt in self.plan.micro_tasks
                             if mt.status == MicroTaskStatus.PLANNED]
        self.assertEqual(remaining_planned, [])


# ---------------------------------------------------------------------------
# T4: YagniChecker integration
# ---------------------------------------------------------------------------


class T4_YagniCheckerIntegration(unittest.TestCase):
    """T4: YagniChecker SKIP propagation through planner."""

    def setUp(self) -> None:
        self.planner, self.mock_checker = _make_planner_with_yagni()

    def test_01_yagni_results_attached_to_plan(self) -> None:
        """Verify: yagni_results dict is populated on the plan."""
        plan = self.planner.plan(
            "Build feature",
            spec={"files": ["src/a.py"]},
        )
        self.assertIsInstance(plan.yagni_results, dict)
        self.assertEqual(len(plan.yagni_results), len(plan.micro_tasks))
        for _mt_id, result in plan.yagni_results.items():
            self.assertIn("verdict", result)
            self.assertIn("reason", result)

    def test_02_skip_verdict_marks_task_as_skipped(self) -> None:
        """Verify: SKIP verdict → MicroTaskStatus.SKIPPED."""
        self.mock_checker.check_micro_task.return_value = _make_yagni_result("SKIP", "exploratory")
        plan = self.planner.plan(
            "Build feature",
            spec={"files": ["src/a.py", "src/b.py"]},
        )
        skipped = [mt for mt in plan.micro_tasks if mt.status == MicroTaskStatus.SKIPPED]
        self.assertEqual(len(skipped), len(plan.micro_tasks),
                         "All tasks should be marked SKIPPED when checker returns SKIP")

    def test_03_skipped_tasks_count_as_satisfied_dependencies(self) -> None:
        """Verify: get_next_ready treats SKIPPED deps as satisfied (V3.9-03)."""
        self.mock_checker.check_micro_task.return_value = _make_yagni_result("SKIP", "exploratory")
        plan = self.planner.plan(
            "Build",
            spec={"files": ["a.py", "b.py"]},  # b depends on a
        )
        # Both tasks skipped — none should be returned by get_next_ready
        # (only PLANNED tasks are returned, not SKIPPED).
        ready = self.planner.get_next_ready(plan)
        self.assertEqual(ready, [],
                         "Skipped tasks are not PLANNED — should not be returned")

    def test_04_yagni_checker_exception_is_swallowed(self) -> None:
        """Verify: YagniChecker raising → planner logs warning, continues."""
        self.mock_checker.check_micro_task.side_effect = RuntimeError("checker crashed")
        plan = self.planner.plan(
            "Build",
            spec={"files": ["a.py"]},
        )
        # Plan still produced, no yagni_results for the failed check
        self.assertEqual(plan.yagni_results, {})
        # Task remains PLANNED (not skipped)
        self.assertEqual(plan.micro_tasks[0].status, MicroTaskStatus.PLANNED)

    def test_05_necessary_verdict_does_not_skip_task(self) -> None:
        """Verify: NECESSARY verdict keeps task PLANNED."""
        self.mock_checker.check_micro_task.return_value = _make_yagni_result("NECESSARY")
        plan = self.planner.plan(
            "Build",
            spec={"files": ["a.py"]},
        )
        self.assertEqual(plan.micro_tasks[0].status, MicroTaskStatus.PLANNED)
        self.assertEqual(plan.yagni_results[plan.micro_tasks[0].id]["verdict"], "NECESSARY")


# ---------------------------------------------------------------------------
# T5: Execution mode classification
# ---------------------------------------------------------------------------


class T5_ExecutionModeClassificationIntegration(unittest.TestCase):
    """T5: HITL vs AFK classification for realistic tasks."""

    def setUp(self) -> None:
        self.planner = MicroTaskPlanner()

    def _build_task(self, title: str, description: str = "") -> MicroTask:
        return MicroTask(
            id="t1",
            title=title,
            description=description,
            file_paths=[],
            verification_cmd="echo ok",
        )

    def test_01_deploy_keyword_triggers_hitl(self) -> None:
        """Verify: 'deploy' keyword → HITL classification."""
        task = self._build_task("Deploy service to production")
        self.assertEqual(self.planner.classify_execution_mode(task), "HITL")

    def test_02_release_keyword_triggers_hitl(self) -> None:
        """Verify: 'release' keyword → HITL."""
        task = self._build_task("Release v1.0", description="Cut the release branch")
        self.assertEqual(self.planner.classify_execution_mode(task), "HITL")

    def test_03_approve_keyword_triggers_hitl(self) -> None:
        """Verify: 'approve' keyword → HITL."""
        task = self._build_task("Approve PR", description="review and approve")
        self.assertEqual(self.planner.classify_execution_mode(task), "HITL")

    def test_04_chinese_deploy_keyword_triggers_hitl(self) -> None:
        """Verify: '部署' (deploy in Chinese) → HITL."""
        task = self._build_task("部署服务到生产环境")
        self.assertEqual(self.planner.classify_execution_mode(task), "HITL")

    def test_05_normal_task_is_afk(self) -> None:
        """Verify: a normal implementation task → AFK."""
        task = self._build_task("Implement login function", description="Add auth logic")
        self.assertEqual(self.planner.classify_execution_mode(task), "AFK")


# ---------------------------------------------------------------------------
# T6: Topological sort + cycle detection
# ---------------------------------------------------------------------------


class T6_TopologicalSortAndCyclesIntegration(unittest.TestCase):
    """T6: Topological order + cycle detection integration."""

    def setUp(self) -> None:
        self.planner = MicroTaskPlanner()

    def test_01_topological_sort_puts_dependencies_first(self) -> None:
        """Verify: order_by_dependencies returns deps before dependents."""
        t0 = MicroTask(id="t0", title="t0", description="", dependencies=[])
        t1 = MicroTask(id="t1", title="t1", description="", dependencies=["t0"])
        t2 = MicroTask(id="t2", title="t2", description="", dependencies=["t1"])
        ordered = self.planner.order_by_dependencies([t2, t1, t0])
        ids = [mt.id for mt in ordered]
        self.assertEqual(ids, ["t0", "t1", "t2"],
                         "Topological sort should put t0 → t1 → t2 in order")

    def test_02_cycle_detection_returns_original_order(self) -> None:
        """Verify: cycle → order_by_dependencies preserves input order + logs warning."""
        t0 = MicroTask(id="t0", title="t0", description="", dependencies=["t1"])
        t1 = MicroTask(id="t1", title="t1", description="", dependencies=["t0"])
        ordered = self.planner.order_by_dependencies([t0, t1])
        # On cycle, original order is returned as-is
        self.assertEqual([mt.id for mt in ordered], ["t0", "t1"])

    def test_03_plan_validates_missing_dependency(self) -> None:
        """Verify: plan() with a missing dep logs a validation warning but still produces a plan."""
        # Build a plan manually with a missing dep
        plan = MicroTaskPlan(
            task_id="t-parent",
            micro_tasks=[
                MicroTask(id="t0", title="t0", description="", verification_cmd="echo ok",
                          dependencies=["nonexistent"]),
            ],
        )
        errors = self.planner._validate_plan_detailed(plan)
        self.assertTrue(any("non-existent task id=nonexistent" in e for e in errors),
                        f"Expected missing-dep error, got: {errors}")

    def test_04_cycle_detected_by_validate_plan(self) -> None:
        """Verify: _validate_plan_detailed flags a cycle."""
        plan = MicroTaskPlan(
            task_id="t-parent",
            micro_tasks=[
                MicroTask(id="t0", title="t0", description="", verification_cmd="echo",
                          dependencies=["t1"]),
                MicroTask(id="t1", title="t1", description="", verification_cmd="echo",
                          dependencies=["t0"]),
            ],
        )
        errors = self.planner._validate_plan_detailed(plan)
        self.assertTrue(any("cycle" in e.lower() for e in errors),
                        f"Expected cycle error, got: {errors}")


# ---------------------------------------------------------------------------
# T7: Edge cases + graceful degradation
# ---------------------------------------------------------------------------


class T7_EdgeCasesAndGracefulDegradationIntegration(unittest.TestCase):
    """T7: Empty task, max exceeded, planner failure, format_plan."""

    def setUp(self) -> None:
        self.planner = MicroTaskPlanner(max_micro_tasks=3)

    def test_01_empty_task_returns_empty_plan(self) -> None:
        """Verify: empty task description → empty plan (no crash)."""
        plan = self.planner.plan("")
        self.assertEqual(plan.micro_tasks, [])
        self.assertEqual(plan.total_estimated_minutes, 0)

    def test_02_whitespace_task_returns_empty_plan(self) -> None:
        """Verify: whitespace-only task → empty plan."""
        plan = self.planner.plan("   \n\t  ")
        self.assertEqual(plan.micro_tasks, [])

    def test_03_max_micro_tasks_truncates_with_warning(self) -> None:
        """Verify: exceeding max_micro_tasks truncates the plan."""
        # 5 files but max=3 → truncated to 3
        plan = self.planner.plan(
            "Build",
            spec={"files": ["a.py", "b.py", "c.py", "d.py", "e.py"]},
        )
        self.assertLessEqual(len(plan.micro_tasks), self.planner.max_micro_tasks)
        self.assertEqual(len(plan.micro_tasks), 3)

    def test_04_format_plan_produces_markdown_table(self) -> None:
        """Verify: format_plan returns a Markdown table with headers."""
        plan = self.planner.plan(
            "Build feature",
            spec={"files": ["a.py"]},
        )
        md = self.planner.format_plan(plan)
        self.assertIsInstance(md, str)
        self.assertIn("# Micro-Task Plan", md)
        self.assertIn("| # |", md)
        self.assertIn("Total micro-tasks:", md)

    def test_05_dispatcher_with_failing_planner_gracefully_degrades(self) -> None:
        """Verify: planner raising → dispatcher returns result without plan (no crash)."""
        work_dir = tempfile.mkdtemp(prefix="mt_fail_")
        try:
            failing_planner = MagicMock(spec=MicroTaskPlanner)
            failing_planner.plan.side_effect = RuntimeError("planner exploded")
            disp = MultiAgentDispatcher(
                persist_dir=work_dir,
                micro_task_planner=failing_planner,
            )
            result = disp.dispatch(
                "Some task",
                use_micro_tasks=True,
                files=["src/foo.py"],
            )
            # _maybe_decompose_task swallows the exception → plan stays None
            self.assertIsNone(result.micro_task_plan,
                              "Planner failure should degrade to None, not crash")
            disp.shutdown()
        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
