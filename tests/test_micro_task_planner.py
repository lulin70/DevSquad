#!/usr/bin/env python3
"""
Tests for MicroTaskPlanner (V3.8 #7) — Micro-Task Granularity.

Coverage:
  - MicroTaskStatus enum values
  - MicroTask / MicroTaskPlan dataclasses (to_dict)
  - Plan decomposition (file-based, function-based, heuristic)
  - Micro-task has file_paths
  - Micro-task has verification_cmd
  - Duration estimation 2-5 minutes
  - Max 20 micro-tasks enforced
  - Dependency DAG validation (no cycles)
  - Topological sort
  - get_next_ready returns correct tasks
  - mark_completed updates status
  - Plan formatting (Markdown table)
  - Empty task handling
  - Integration with dispatcher
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.micro_task_planner import (
    MicroTask,
    MicroTaskPlan,
    MicroTaskPlanner,
    MicroTaskStatus,
)


class TestMicroTaskStatusEnum(unittest.TestCase):
    """Verify MicroTaskStatus enum values."""

    def test_status_values(self) -> None:
        self.assertEqual(MicroTaskStatus.PLANNED.value, "planned")
        self.assertEqual(MicroTaskStatus.IN_PROGRESS.value, "in_progress")
        self.assertEqual(MicroTaskStatus.COMPLETED.value, "completed")
        self.assertEqual(MicroTaskStatus.FAILED.value, "failed")
        self.assertEqual(MicroTaskStatus.SKIPPED.value, "skipped")


class TestMicroTaskDataclass(unittest.TestCase):
    """Verify MicroTask dataclass."""

    def test_to_dict_round_trip(self) -> None:
        mt = MicroTask(
            id="mt-1",
            title="Implement login",
            description="Add login function",
            file_paths=["src/auth.py"],
            verification_cmd="python -m pytest tests/test_auth.py",
            estimated_minutes=3,
            dependencies=[],
        )
        d = mt.to_dict()
        self.assertEqual(d["id"], "mt-1")
        self.assertEqual(d["title"], "Implement login")
        self.assertEqual(d["file_paths"], ["src/auth.py"])
        self.assertEqual(d["verification_cmd"], "python -m pytest tests/test_auth.py")
        self.assertEqual(d["estimated_minutes"], 3)
        self.assertEqual(d["status"], "planned")

    def test_default_status_is_planned(self) -> None:
        mt = MicroTask(id="x", title="t", description="d")
        self.assertEqual(mt.status, MicroTaskStatus.PLANNED)


class TestMicroTaskPlanDataclass(unittest.TestCase):
    """Verify MicroTaskPlan dataclass."""

    def test_to_dict_includes_all_fields(self) -> None:
        plan = MicroTaskPlan(
            task_id="task-1",
            micro_tasks=[],
            total_estimated_minutes=10,
            max_micro_tasks=20,
            summary="test",
        )
        d = plan.to_dict()
        self.assertEqual(d["task_id"], "task-1")
        self.assertEqual(d["micro_tasks"], [])
        self.assertEqual(d["total_estimated_minutes"], 10)
        self.assertEqual(d["max_micro_tasks"], 20)
        self.assertEqual(d["summary"], "test")


class TestPlanDecomposition(unittest.TestCase):
    """Verify plan decomposition strategies."""

    def test_file_based_decomposition(self) -> None:
        """Plan decomposition — file-based."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add user login endpoint",
            spec={
                "files": ["src/auth.py", "src/models.py"],
                "tests": ["tests/test_auth.py"],
            },
        )
        # 2 file micro-tasks + 1 test micro-task = 3.
        self.assertEqual(len(plan.micro_tasks), 3)
        # Each file micro-task should have file_paths.
        file_mts = [mt for mt in plan.micro_tasks if any("src/" in p for p in mt.file_paths)]
        self.assertEqual(len(file_mts), 2)

    def test_function_based_decomposition(self) -> None:
        """Plan decomposition — function-based."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Implement auth module",
            spec={
                "functions": ["login", "logout", "refresh_token"],
            },
        )
        self.assertEqual(len(plan.micro_tasks), 3)
        titles = [mt.title for mt in plan.micro_tasks]
        self.assertIn("Implement login", titles)
        self.assertIn("Implement logout", titles)
        self.assertIn("Implement refresh_token", titles)

    def test_heuristic_decomposition_for_plain_text(self) -> None:
        """Plan decomposition — heuristic sentence-based."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "First, create the auth module. Then, add the login function. Finally, write tests for the login function.",
        )
        # Should produce at least 3 micro-tasks (one per sentence).
        self.assertGreaterEqual(len(plan.micro_tasks), 3)

    def test_micro_task_has_file_paths(self) -> None:
        """Micro-task has file_paths — file-based decomposition."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add login",
            spec={"files": ["src/auth.py"]},
        )
        # The first micro-task should have file_paths.
        self.assertTrue(any(mt.file_paths for mt in plan.micro_tasks))
        self.assertEqual(plan.micro_tasks[0].file_paths, ["src/auth.py"])

    def test_micro_task_has_verification_cmd(self) -> None:
        """Micro-task has verification_cmd — always present."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add login",
            spec={"files": ["src/auth.py"], "tests": ["tests/test_auth.py"]},
        )
        for mt in plan.micro_tasks:
            self.assertTrue(mt.verification_cmd, f"Missing verification_cmd for {mt.title}")

    def test_verification_cmd_for_python_file(self) -> None:
        """Python file gets a syntax-check verification command."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add module",
            spec={"files": ["src/foo.py"]},
        )
        # The first micro-task is for src/foo.py.
        mt = plan.micro_tasks[0]
        self.assertIn("python", mt.verification_cmd)

    def test_verification_cmd_uses_matching_test_file(self) -> None:
        """When a matching test file exists, it's used in the verification cmd."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add auth",
            spec={"files": ["src/auth.py"], "tests": ["tests/test_auth.py"]},
        )
        # The first micro-task is for src/auth.py — should reference test_auth.py.
        mt = plan.micro_tasks[0]
        self.assertIn("test_auth.py", mt.verification_cmd)


class TestDurationEstimation(unittest.TestCase):
    """Verify duration estimation 2-5 minutes."""

    def test_single_file_estimates_2_minutes(self) -> None:
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add login",
            spec={"files": ["src/auth.py"]},
        )
        for mt in plan.micro_tasks:
            self.assertGreaterEqual(mt.estimated_minutes, 2)
            self.assertLessEqual(mt.estimated_minutes, 5)

    def test_duration_always_in_2_to_5_range(self) -> None:
        """Duration estimation 2-5 minutes — always in range."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add multiple files",
            spec={"files": ["a.py", "b.py", "c.py", "d.py", "e.py"]},
        )
        for mt in plan.micro_tasks:
            self.assertGreaterEqual(mt.estimated_minutes, 2)
            self.assertLessEqual(mt.estimated_minutes, 5)

    def test_custom_duration_bounds(self) -> None:
        """Custom duration bounds are respected."""
        planner = MicroTaskPlanner(min_duration_minutes=3, max_duration_minutes=4)
        plan = planner.plan(
            "Add file",
            spec={"files": ["src/foo.py"]},
        )
        for mt in plan.micro_tasks:
            self.assertGreaterEqual(mt.estimated_minutes, 3)
            self.assertLessEqual(mt.estimated_minutes, 4)


class TestMaxMicroTasksEnforced(unittest.TestCase):
    """Verify max 20 micro-tasks enforced."""

    def test_default_max_is_20(self) -> None:
        planner = MicroTaskPlanner()
        self.assertEqual(planner.max_micro_tasks, 20)

    def test_plan_truncates_to_max(self) -> None:
        """Max 20 micro-tasks enforced — truncates when exceeded."""
        planner = MicroTaskPlanner(max_micro_tasks=5)
        # Generate 10 files → 10 micro-tasks → truncated to 5.
        files = [f"src/file_{i}.py" for i in range(10)]
        plan = planner.plan("Add many files", spec={"files": files})
        self.assertLessEqual(len(plan.micro_tasks), 5)
        self.assertEqual(plan.max_micro_tasks, 5)

    def test_custom_max_micro_tasks(self) -> None:
        planner = MicroTaskPlanner(max_micro_tasks=3)
        files = [f"src/file_{i}.py" for i in range(5)]
        plan = planner.plan("Add files", spec={"files": files})
        self.assertLessEqual(len(plan.micro_tasks), 3)


class TestDependencyDAGValidation(unittest.TestCase):
    """Verify dependency DAG validation (no cycles)."""

    def test_validate_plan_no_cycles_returns_empty(self) -> None:
        """Dependency DAG validation — no cycles → no errors."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
                MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
                MicroTask(id="c", title="C", description="d", verification_cmd="x", dependencies=["b"]),
            ],
        )
        errors = planner._validate_plan(plan)
        self.assertEqual(errors, [])

    def test_validate_plan_detects_cycle(self) -> None:
        """Dependency DAG validation — cycle detected."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x", dependencies=["c"]),
                MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
                MicroTask(id="c", title="C", description="d", verification_cmd="x", dependencies=["b"]),
            ],
        )
        errors = planner._validate_plan(plan)
        self.assertTrue(any("cycle" in e.lower() for e in errors))

    def test_validate_plan_missing_verification_cmd(self) -> None:
        """Validation — missing verification_cmd is flagged."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd=""),
            ],
        )
        errors = planner._validate_plan(plan)
        self.assertTrue(any("verification_cmd" in e for e in errors))

    def test_validate_plan_non_existent_dependency(self) -> None:
        """Validation — non-existent dependency is flagged."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x", dependencies=["nonexistent"]),
            ],
        )
        errors = planner._validate_plan(plan)
        self.assertTrue(any("non-existent" in e for e in errors))

    def test_detect_cycle_direct_method(self) -> None:
        """The _detect_cycle method returns the cycle path."""
        planner = MicroTaskPlanner()
        micro_tasks = [
            MicroTask(id="a", title="A", description="d", verification_cmd="x", dependencies=["b"]),
            MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
        ]
        cycle = planner._detect_cycle(micro_tasks)
        self.assertIsNotNone(cycle)
        self.assertGreaterEqual(len(cycle), 2)

    def test_detect_cycle_no_cycle_returns_none(self) -> None:
        planner = MicroTaskPlanner()
        micro_tasks = [
            MicroTask(id="a", title="A", description="d", verification_cmd="x"),
            MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
        ]
        cycle = planner._detect_cycle(micro_tasks)
        self.assertIsNone(cycle)


class TestTopologicalSort(unittest.TestCase):
    """Verify topological sort."""

    def test_topological_sort_orders_by_dependencies(self) -> None:
        """Topological sort — dependencies come before dependents."""
        planner = MicroTaskPlanner()
        micro_tasks = [
            MicroTask(id="c", title="C", description="d", verification_cmd="x", dependencies=["b"]),
            MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
            MicroTask(id="a", title="A", description="d", verification_cmd="x"),
        ]
        sorted_tasks = planner._topological_sort(micro_tasks)
        ids = [t.id for t in sorted_tasks]
        # 'a' must come before 'b', 'b' before 'c'.
        self.assertLess(ids.index("a"), ids.index("b"))
        self.assertLess(ids.index("b"), ids.index("c"))

    def test_topological_sort_preserves_input_order_for_independent(self) -> None:
        """Topological sort — independent tasks preserve input order."""
        planner = MicroTaskPlanner()
        micro_tasks = [
            MicroTask(id="x", title="X", description="d", verification_cmd="x"),
            MicroTask(id="y", title="Y", description="d", verification_cmd="x"),
            MicroTask(id="z", title="Z", description="d", verification_cmd="x"),
        ]
        sorted_tasks = planner._topological_sort(micro_tasks)
        ids = [t.id for t in sorted_tasks]
        self.assertEqual(ids, ["x", "y", "z"])

    def test_plan_returns_topologically_sorted_tasks(self) -> None:
        """Plan returns tasks in topological order."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add files",
            spec={"files": ["a.py", "b.py", "c.py"]},
        )
        # File-based decomposition chains dependencies: a → b → c.
        # So the first micro-task should have no deps, the second should
        # depend on the first, etc.
        self.assertEqual(len(plan.micro_tasks), 3)
        # First task has no dependencies.
        self.assertEqual(plan.micro_tasks[0].dependencies, [])
        # Second task depends on the first.
        self.assertIn(plan.micro_tasks[0].id, plan.micro_tasks[1].dependencies)


class TestGetNextReady(unittest.TestCase):
    """Verify get_next_ready returns correct tasks."""

    def test_get_next_ready_returns_tasks_with_no_deps(self) -> None:
        """get_next_ready returns correct tasks — initially, tasks with no deps."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
                MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
            ],
        )
        ready = planner.get_next_ready(plan)
        self.assertEqual(len(ready), 1)
        self.assertEqual(ready[0].id, "a")

    def test_get_next_ready_after_completion(self) -> None:
        """get_next_ready returns dependent tasks after deps complete."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
                MicroTask(id="b", title="B", description="d", verification_cmd="x", dependencies=["a"]),
                MicroTask(id="c", title="C", description="d", verification_cmd="x", dependencies=["a"]),
            ],
        )
        # Initially only 'a' is ready.
        ready = planner.get_next_ready(plan)
        self.assertEqual({t.id for t in ready}, {"a"})
        # Complete 'a' → 'b' and 'c' become ready.
        planner.mark_completed(plan, "a", "done")
        ready = planner.get_next_ready(plan)
        self.assertEqual({t.id for t in ready}, {"b", "c"})

    def test_get_next_ready_empty_when_all_done(self) -> None:
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
            ],
        )
        planner.mark_completed(plan, "a", "done")
        ready = planner.get_next_ready(plan)
        self.assertEqual(ready, [])

    def test_get_next_ready_skips_in_progress(self) -> None:
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
            ],
        )
        plan.micro_tasks[0].status = MicroTaskStatus.IN_PROGRESS
        ready = planner.get_next_ready(plan)
        self.assertEqual(ready, [])


class TestMarkCompleted(unittest.TestCase):
    """Verify mark_completed updates status."""

    def test_mark_completed_updates_status(self) -> None:
        """mark_completed updates status — sets COMPLETED and result."""
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
            ],
        )
        result = planner.mark_completed(plan, "a", "all good")
        self.assertTrue(result)
        self.assertEqual(plan.micro_tasks[0].status, MicroTaskStatus.COMPLETED)
        self.assertEqual(plan.micro_tasks[0].result, "all good")

    def test_mark_completed_returns_false_for_unknown_id(self) -> None:
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
            ],
        )
        result = planner.mark_completed(plan, "nonexistent", "x")
        self.assertFalse(result)

    def test_mark_failed_updates_status(self) -> None:
        planner = MicroTaskPlanner()
        plan = MicroTaskPlan(
            task_id="t1",
            micro_tasks=[
                MicroTask(id="a", title="A", description="d", verification_cmd="x"),
            ],
        )
        result = planner.mark_failed(plan, "a", "syntax error")
        self.assertTrue(result)
        self.assertEqual(plan.micro_tasks[0].status, MicroTaskStatus.FAILED)
        self.assertEqual(plan.micro_tasks[0].result, "syntax error")


class TestPlanFormatting(unittest.TestCase):
    """Verify plan formatting (Markdown table)."""

    def test_format_plan_includes_table_header(self) -> None:
        """Plan formatting — Markdown table header present."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add login",
            spec={"files": ["src/auth.py"]},
        )
        markdown = planner.format_plan(plan)
        self.assertIn("Micro-Task Plan", markdown)
        self.assertIn("| # |", markdown)
        self.assertIn("Title", markdown)
        self.assertIn("Files", markdown)
        self.assertIn("Verification", markdown)

    def test_format_plan_includes_each_micro_task(self) -> None:
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add files",
            spec={"files": ["a.py", "b.py"]},
        )
        markdown = planner.format_plan(plan)
        # Each micro-task title should appear.
        for mt in plan.micro_tasks:
            self.assertIn(mt.title, markdown)

    def test_format_plan_includes_summary(self) -> None:
        planner = MicroTaskPlanner()
        plan = planner.plan("Add login", spec={"files": ["src/auth.py"]})
        markdown = planner.format_plan(plan)
        self.assertIn("Summary", markdown)
        self.assertIn(plan.summary, markdown)


class TestEmptyTaskHandling(unittest.TestCase):
    """Verify empty task handling."""

    def test_empty_task_description_returns_empty_plan(self) -> None:
        """Empty task handling — empty description → empty plan."""
        planner = MicroTaskPlanner()
        plan = planner.plan("")
        self.assertEqual(len(plan.micro_tasks), 0)
        self.assertEqual(plan.total_estimated_minutes, 0)
        self.assertIn("empty", plan.summary.lower())

    def test_whitespace_only_task_returns_empty_plan(self) -> None:
        planner = MicroTaskPlanner()
        plan = planner.plan("   \n   \t  ")
        self.assertEqual(len(plan.micro_tasks), 0)

    def test_empty_task_with_spec_returns_empty_plan(self) -> None:
        planner = MicroTaskPlanner()
        plan = planner.plan("", spec={"files": ["a.py"]})
        self.assertEqual(len(plan.micro_tasks), 0)


class TestIntegrationWithDispatcher(unittest.TestCase):
    """Verify integration with MultiAgentDispatcher."""

    def test_dispatcher_accepts_micro_task_planner_parameter(self) -> None:
        """Integration with dispatcher — accepts micro_task_planner parameter."""
        import inspect

        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        # We can't easily construct a full dispatcher (too many deps),
        # but we can verify the parameter is accepted by inspecting
        # the __init__ signature.
        sig = inspect.signature(MultiAgentDispatcher.__init__)
        self.assertIn("micro_task_planner", sig.parameters)

    def test_dispatcher_decompose_task_uses_planner(self) -> None:
        """Integration with dispatcher — decompose_task delegates to planner."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        planner = MicroTaskPlanner()
        # Create a minimal mock dispatcher by bypassing __init__.
        # This avoids the heavy dependency setup.
        dispatcher = MultiAgentDispatcher.__new__(MultiAgentDispatcher)
        dispatcher.micro_task_planner = planner
        plan = dispatcher.decompose_task(
            "Add login",
            spec={"files": ["src/auth.py"]},
        )
        self.assertIsNotNone(plan)
        self.assertIsInstance(plan, MicroTaskPlan)
        self.assertEqual(len(plan.micro_tasks), 1)

    def test_dispatcher_decompose_task_returns_none_without_planner(self) -> None:
        """Integration with dispatcher — returns None when no planner configured."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        dispatcher = MultiAgentDispatcher.__new__(MultiAgentDispatcher)
        dispatcher.micro_task_planner = None
        result = dispatcher.decompose_task("Add login")
        self.assertIsNone(result)


class TestPlanSummary(unittest.TestCase):
    """Verify plan summary content."""

    def test_summary_contains_count_and_minutes(self) -> None:
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add login",
            spec={"files": ["src/auth.py"]},
        )
        self.assertIn("MicroTaskPlanner", plan.summary)
        self.assertIn("micro-tasks", plan.summary)
        self.assertIn("min", plan.summary)

    def test_total_estimated_minutes_is_sum(self) -> None:
        """Total estimated minutes is the sum of all micro-task estimates."""
        planner = MicroTaskPlanner()
        plan = planner.plan(
            "Add files",
            spec={"files": ["a.py", "b.py", "c.py"]},
        )
        expected_total = sum(mt.estimated_minutes for mt in plan.micro_tasks)
        self.assertEqual(plan.total_estimated_minutes, expected_total)


if __name__ == "__main__":
    unittest.main()
