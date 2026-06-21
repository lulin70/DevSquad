#!/usr/bin/env python3
"""
MicroTaskPlanner — V3.8 #7: Micro-Task Granularity.

Decomposes a task into 2-5 minute micro-tasks with:

  - Precise file paths (no ambiguity)
  - Verification commands (executable, deterministic)
  - Dependency graph (which tasks must complete first)

Inspired by Superpowers' micro-task discipline.

Rules
-----
  - Each micro-task: 2-5 minutes estimated
  - Max 20 micro-tasks per plan (split further if needed)
  - Each micro-task has a verification command
  - Dependencies form a DAG (no cycles)

Integration
-----------
The planner is usable standalone via :meth:`MicroTaskPlanner.plan`.
:class:`MultiAgentDispatcher` accepts an optional ``micro_task_planner``
parameter; when provided, dispatched tasks can be decomposed for more
granular execution tracking.

Usage::

    from scripts.collaboration.micro_task_planner import MicroTaskPlanner

    planner = MicroTaskPlanner()
    plan = planner.plan(
        "Add user login endpoint",
        spec={
            "files": ["src/auth.py", "tests/test_auth.py"],
            "functions": ["login", "logout"],
        },
    )
    print(planner.format_plan(plan))
    # Execute micro-tasks in topological order:
    while True:
        ready = planner.get_next_ready(plan)
        if not ready:
            break
        for mt in ready:
            # ... execute mt ...
            planner.mark_completed(plan, mt.id, result="done")
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class MicroTaskStatus(Enum):
    """Lifecycle status of a micro-task."""

    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class MicroTask:
    """A single micro-task (2-5 minutes of work).

    Attributes
    ----------
    id:
        Unique identifier (auto-generated when not provided).
    title:
        Short, action-oriented title.
    description:
        What to do, one paragraph.
    file_paths:
        Exact files to modify/create.
    verification_cmd:
        Command to verify completion (e.g. ``python -m pytest tests/test_foo.py``).
    estimated_minutes:
        Estimated duration (2-5 minutes target).
    dependencies:
        IDs of tasks that must complete first.
    status:
        Current :class:`MicroTaskStatus`.
    result:
        Result string (set on completion).
    started_at / completed_at:
        ISO timestamps (set by the executor, not the planner).
    """

    id: str
    title: str
    description: str
    file_paths: list[str] = field(default_factory=list)
    verification_cmd: str = ""
    estimated_minutes: int = 3
    dependencies: list[str] = field(default_factory=list)
    status: MicroTaskStatus = MicroTaskStatus.PLANNED
    result: str = ""
    started_at: str = ""
    completed_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "file_paths": list(self.file_paths),
            "verification_cmd": self.verification_cmd,
            "estimated_minutes": self.estimated_minutes,
            "dependencies": list(self.dependencies),
            "status": self.status.value,
            "result": self.result,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


@dataclass
class MicroTaskPlan:
    """A plan containing a list of micro-tasks for a parent task.

    Attributes
    ----------
    task_id:
        Parent task ID (auto-generated when not provided).
    micro_tasks:
        The list of :class:`MicroTask` objects.
    total_estimated_minutes:
        Sum of all micro-task estimates.
    max_micro_tasks:
        Hard limit on micro-tasks per plan (default 20).
    summary:
        Human-readable summary.
    """

    task_id: str
    micro_tasks: list[MicroTask] = field(default_factory=list)
    total_estimated_minutes: int = 0
    max_micro_tasks: int = 20
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "micro_tasks": [t.to_dict() for t in self.micro_tasks],
            "total_estimated_minutes": self.total_estimated_minutes,
            "max_micro_tasks": self.max_micro_tasks,
            "summary": self.summary,
        }


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


class MicroTaskPlanner:
    """Micro-task planner inspired by Superpowers.

    Decomposes a task into 2-5 minute micro-tasks with precise file
    paths, verification commands, and a dependency DAG.

    Rules:
      - Each micro-task: 2-5 minutes estimated
      - Max 20 micro-tasks per plan (split further if needed)
      - Each micro-task has a verification command
      - Dependencies form a DAG (no cycles)

    Parameters
    ----------
    max_micro_tasks:
        Hard limit on micro-tasks per plan. Default 20.
    min_duration_minutes:
        Minimum estimated duration per micro-task. Default 2.
    max_duration_minutes:
        Maximum estimated duration per micro-task. Default 5.
    """

    # Default verification command templates by file type.
    _VERIFICATION_TEMPLATES: dict[str, str] = {
        "python": "python -m pytest {test_file} -v",
        "javascript": "npm test -- {test_file}",
        "typescript": "npm test -- {test_file}",
        "go": "go test {test_file}",
        "rust": "cargo test {test_file}",
        "shell": "bash {test_file}",
    }

    def __init__(
        self,
        max_micro_tasks: int = 20,
        min_duration_minutes: int = 2,
        max_duration_minutes: int = 5,
    ) -> None:
        self.max_micro_tasks = max_micro_tasks
        self.min_duration_minutes = min_duration_minutes
        self.max_duration_minutes = max_duration_minutes

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def plan(
        self,
        task_description: str,
        spec: dict[str, Any] | None = None,
    ) -> MicroTaskPlan:
        """Main entry — decompose a task into micro-tasks.

        Parameters
        ----------
        task_description:
            Natural-language description of the task.
        spec:
            Optional spec dict. Recognized keys:
              - ``files``: list of file paths to create/modify
              - ``functions``: list of function/class names to implement
              - ``tests``: list of test file paths
              - ``acceptance_criteria``: list of criteria
              - ``task_id``: parent task ID (auto-generated when missing)

        Returns
        -------
        MicroTaskPlan
        """
        spec = spec or {}
        task_id = str(spec.get("task_id") or uuid.uuid4())

        if not task_description or not task_description.strip():
            # Empty task — return an empty plan.
            return MicroTaskPlan(
                task_id=task_id,
                micro_tasks=[],
                total_estimated_minutes=0,
                max_micro_tasks=self.max_micro_tasks,
                summary="MicroTaskPlanner: empty task description, no micro-tasks.",
            )

        micro_tasks = self._decompose(task_description, spec)

        # Enforce max micro-tasks (truncate with a warning).
        if len(micro_tasks) > self.max_micro_tasks:
            logger.warning(
                "MicroTaskPlanner: task produced %d micro-tasks, truncating to %d. "
                "Consider splitting the parent task.",
                len(micro_tasks),
                self.max_micro_tasks,
            )
            micro_tasks = micro_tasks[: self.max_micro_tasks]

        # Validate the plan.
        errors = self._validate_plan_detailed(
            MicroTaskPlan(task_id=task_id, micro_tasks=micro_tasks)
        )
        for err in errors:
            logger.warning("MicroTaskPlanner: %s", err)

        # Topological sort by dependencies.
        micro_tasks = self._topological_sort(micro_tasks)

        total = sum(t.estimated_minutes for t in micro_tasks)
        summary = self._build_summary(task_description, micro_tasks, total)

        return MicroTaskPlan(
            task_id=task_id,
            micro_tasks=micro_tasks,
            total_estimated_minutes=total,
            max_micro_tasks=self.max_micro_tasks,
            summary=summary,
        )

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------

    def _decompose(
        self,
        task_description: str,
        spec: dict[str, Any],
    ) -> list[MicroTask]:
        """Decompose a task into micro-tasks.

        Strategy:
          1. If the spec lists explicit files, create one micro-task
             per file (plus a test micro-task if tests are listed).
          2. If the spec lists functions/classes, create one micro-task
             per function (chained by dependency).
          3. Otherwise, heuristically split the task description by
             sentences or action verbs.
        """
        files = list(spec.get("files") or [])
        functions = list(spec.get("functions") or [])
        tests = list(spec.get("tests") or [])
        criteria = list(spec.get("acceptance_criteria") or [])

        micro_tasks: list[MicroTask] = []

        # Strategy 1: file-based decomposition.
        if files:
            prev_id: str | None = None
            for path in files:
                mt_id = str(uuid.uuid4())
                title = self._title_for_file(path)
                desc = self._description_for_file(path, task_description)
                verification = self._verification_for_file(path, tests)
                deps = [prev_id] if prev_id else []
                micro_tasks.append(
                    MicroTask(
                        id=mt_id,
                        title=title,
                        description=desc,
                        file_paths=[path],
                        verification_cmd=verification,
                        estimated_minutes=self._estimate_duration(
                            MicroTask(
                                id=mt_id, title=title, description=desc,
                                file_paths=[path], verification_cmd=verification,
                            )
                        ),
                        dependencies=deps,
                    )
                )
                prev_id = mt_id

            # Add a test micro-task if tests are listed separately.
            if tests:
                test_id = str(uuid.uuid4())
                micro_tasks.append(
                    MicroTask(
                        id=test_id,
                        title="Run verification tests",
                        description=(
                            f"Run the following test files to verify the "
                            f"implementation: {', '.join(tests)}"
                        ),
                        file_paths=list(tests),
                        verification_cmd=self._verification_for_tests(tests),
                        estimated_minutes=3,
                        dependencies=[mt.id for mt in micro_tasks],
                    )
                )

            # Add an acceptance-criteria micro-task if criteria are listed.
            if criteria:
                crit_id = str(uuid.uuid4())
                micro_tasks.append(
                    MicroTask(
                        id=crit_id,
                        title="Verify acceptance criteria",
                        description=(
                            "Verify each acceptance criterion is met: "
                            + "; ".join(criteria)
                        ),
                        file_paths=[],
                        verification_cmd="echo 'Manually verify acceptance criteria'",
                        estimated_minutes=2,
                        dependencies=[mt.id for mt in micro_tasks if mt.id != crit_id],
                    )
                )

            return micro_tasks

        # Strategy 2: function-based decomposition.
        if functions:
            prev_id = None
            for fn in functions:
                mt_id = str(uuid.uuid4())
                title = f"Implement {fn}"
                desc = (
                    f"Implement the `{fn}` function/class as required by "
                    f"the task: {task_description[:120]}"
                )
                verification = (
                    "python -c \"import ast; ast.parse(open('{file}').read())\""
                )
                deps = [prev_id] if prev_id else []
                micro_tasks.append(
                    MicroTask(
                        id=mt_id,
                        title=title,
                        description=desc,
                        file_paths=[],  # No explicit file paths in this strategy.
                        verification_cmd=verification,
                        estimated_minutes=3,
                        dependencies=deps,
                    )
                )
                prev_id = mt_id
            return micro_tasks

        # Strategy 3: heuristic sentence-based decomposition.
        sentences = self._split_sentences(task_description)
        if not sentences:
            # Single micro-task fallback.
            mt_id = str(uuid.uuid4())
            micro_tasks.append(
                MicroTask(
                    id=mt_id,
                    title=task_description[:60],
                    description=task_description,
                    file_paths=[],
                    verification_cmd="echo 'Manual verification required'",
                    estimated_minutes=3,
                    dependencies=[],
                )
            )
            return micro_tasks

        prev_id = None
        for sentence in sentences[: self.max_micro_tasks]:
            mt_id = str(uuid.uuid4())
            title = self._title_from_sentence(sentence)
            desc = sentence.strip()
            deps = [prev_id] if prev_id else []
            micro_tasks.append(
                MicroTask(
                    id=mt_id,
                    title=title,
                    description=desc,
                    file_paths=[],
                    verification_cmd="echo 'Manual verification required'",
                    estimated_minutes=self.min_duration_minutes,
                    dependencies=deps,
                )
            )
            prev_id = mt_id

        return micro_tasks

    def _title_for_file(self, path: str) -> str:
        """Generate a short title for a file-based micro-task."""
        basename = path.rsplit("/", 1)[-1]
        if basename.endswith(".py"):
            name = basename[:-3]
            return f"Implement {name}"
        if basename.endswith((".js", ".ts")):
            name = basename.rsplit(".", 1)[0]
            return f"Implement {name}"
        if basename.endswith(".md"):
            return f"Document {basename}"
        if "test" in basename.lower():
            return f"Write tests in {basename}"
        return f"Create {basename}"

    def _description_for_file(self, path: str, task: str) -> str:
        """Generate a description for a file-based micro-task."""
        return (
            f"Create or modify `{path}` as required by the task: "
            f"{task[:160]}"
        )

    def _verification_for_file(
        self, path: str, tests: list[str]
    ) -> str:
        """Generate a verification command for a file-based micro-task."""
        # If there's a matching test file, use it.
        basename = path.rsplit("/", 1)[-1]
        module_name = basename.rsplit(".", 1)[0] if "." in basename else basename
        for test in tests:
            if module_name in test:
                return f"python -m pytest {test} -v"
        # Otherwise, syntax-check the file (Python only).
        if path.endswith(".py"):
            return f"python -c \"import ast; ast.parse(open('{path}').read())\""
        # Fallback: echo (manual verification).
        return f"echo 'Verify {path} manually'"

    def _verification_for_tests(self, tests: list[str]) -> str:
        """Generate a verification command for running tests."""
        if not tests:
            return "echo 'No tests to run'"
        return " && ".join(f"python -m pytest {t} -v" for t in tests)

    @staticmethod
    def _split_sentences(text: str) -> list[str]:
        """Split a task description into sentences / action items."""
        # Split on sentence-ending punctuation or newlines.
        parts = re.split(r"(?<=[.!?])\s+|\n+", text)
        return [p.strip() for p in parts if p and p.strip()]

    @staticmethod
    def _title_from_sentence(sentence: str) -> str:
        """Generate a short title from a sentence."""
        # Take the first few words.
        words = sentence.split()[:6]
        title = " ".join(words)
        if len(title) > 60:
            title = title[:57] + "..."
        return title

    # ------------------------------------------------------------------
    # Duration estimation
    # ------------------------------------------------------------------

    def _estimate_duration(self, micro_task: MicroTask) -> int:
        """Estimate 2-5 minutes for a micro-task.

        Heuristic:
          - 1 file → 2 minutes
          - 2-3 files → 3 minutes
          - 4+ files → 5 minutes
          - No files → 2 minutes (documentation / verification)
        Clamped to [min_duration_minutes, max_duration_minutes].
        """
        n_files = len(micro_task.file_paths)
        if n_files <= 1:
            estimate = 2
        elif n_files <= 3:
            estimate = 3
        else:
            estimate = 5
        return max(
            self.min_duration_minutes,
            min(self.max_duration_minutes, estimate),
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def _validate_plan(self, plan: MicroTaskPlan) -> list[str]:
        """Validate: no cycles, ≤20 tasks, all have verification.

        Returns a list of error strings (empty if valid).
        """
        return self._validate_plan_detailed(plan)

    def _validate_plan_detailed(self, plan: MicroTaskPlan) -> list[str]:
        """Detailed validation with specific error messages."""
        errors: list[str] = []
        # Check max micro-tasks.
        if len(plan.micro_tasks) > self.max_micro_tasks:
            errors.append(
                f"Plan has {len(plan.micro_tasks)} micro-tasks, exceeding "
                f"the limit of {self.max_micro_tasks}."
            )
        # Check all micro-tasks have a verification command.
        for mt in plan.micro_tasks:
            if not mt.verification_cmd:
                errors.append(
                    f"Micro-task '{mt.title}' (id={mt.id}) has no verification_cmd."
                )
        # Check for cycles.
        cycle = self._detect_cycle(plan.micro_tasks)
        if cycle:
            errors.append(
                f"Dependency cycle detected: {' -> '.join(cycle)}"
            )
        # Check all dependencies reference existing micro-task IDs.
        ids = {mt.id for mt in plan.micro_tasks}
        for mt in plan.micro_tasks:
            for dep in mt.dependencies:
                if dep not in ids:
                    errors.append(
                        f"Micro-task '{mt.title}' (id={mt.id}) depends on "
                        f"non-existent task id={dep}."
                    )
        return errors

    @staticmethod
    def _detect_cycle(micro_tasks: list[MicroTask]) -> list[str] | None:
        """Detect a cycle in the dependency graph.

        Returns the cycle as a list of IDs (or None if no cycle).
        Uses DFS with three colors (white/gray/black).
        """
        # Build adjacency list.
        graph: dict[str, list[str]] = {mt.id: list(mt.dependencies) for mt in micro_tasks}
        # Note: dependencies point FROM the dependent TO the dependency.
        # A cycle exists if following dependency edges leads back to start.
        WHITE, GRAY, BLACK = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(graph, WHITE)
        path: list[str] = []

        def dfs(node: str) -> list[str] | None:
            color[node] = GRAY
            path.append(node)
            for neighbor in graph.get(node, []):
                if neighbor not in color:
                    continue  # Non-existent node — handled elsewhere.
                if color[neighbor] == GRAY:
                    # Found a cycle — return the cycle path.
                    cycle_start = path.index(neighbor)
                    return path[cycle_start:] + [neighbor]
                if color[neighbor] == WHITE:
                    result = dfs(neighbor)
                    if result is not None:
                        return result
            path.pop()
            color[node] = BLACK
            return None

        for node in graph:
            if color[node] == WHITE:
                result = dfs(node)
                if result is not None:
                    return result
        return None

    # ------------------------------------------------------------------
    # Topological sort
    # ------------------------------------------------------------------

    def _topological_sort(
        self, micro_tasks: list[MicroTask]
    ) -> list[MicroTask]:
        """Sort micro-tasks by dependencies (Kahn's algorithm).

        Tasks with no dependencies come first. The sort is stable
        (preserves input order among tasks with the same dependency
        level).
        """
        # Build adjacency: deps_pointing_to[dep] = [tasks that depend on dep]
        # And in_degree[task] = number of unsatisfied dependencies.
        by_id = {mt.id: mt for mt in micro_tasks}
        in_degree: dict[str, int] = {mt.id: 0 for mt in micro_tasks}
        dependents: dict[str, list[str]] = {mt.id: [] for mt in micro_tasks}

        for mt in micro_tasks:
            for dep in mt.dependencies:
                if dep in by_id:  # Only count existing deps.
                    in_degree[mt.id] += 1
                    dependents[dep].append(mt.id)

        # Kahn's algorithm with stable ordering (preserve input order).
        result: list[MicroTask] = []
        # Use the original order to break ties.
        order = [mt.id for mt in micro_tasks]
        # Initialize queue with all zero-in-degree nodes (in original order).
        queue = [nid for nid in order if in_degree[nid] == 0]

        while queue:
            # Take the first node (stable).
            node_id = queue.pop(0)
            result.append(by_id[node_id])
            # Decrement in-degree of dependents.
            for dep_id in dependents[node_id]:
                in_degree[dep_id] -= 1
                if in_degree[dep_id] == 0:
                    # Insert in original order position.
                    # Find the right place to insert to maintain stability.
                    insert_pos = len(queue)
                    for i, qid in enumerate(queue):
                        if order.index(dep_id) < order.index(qid):
                            insert_pos = i
                            break
                    queue.insert(insert_pos, dep_id)

        # If there's a cycle, result will be shorter than input.
        # Append the remaining tasks (best-effort).
        if len(result) < len(micro_tasks):
            remaining = [mt for mt in micro_tasks if mt not in result]
            result.extend(remaining)

        return result

    # ------------------------------------------------------------------
    # Execution helpers
    # ------------------------------------------------------------------

    def get_next_ready(self, plan: MicroTaskPlan) -> list[MicroTask]:
        """Get tasks ready to execute (all deps completed).

        Returns micro-tasks whose status is PLANNED and all
        dependencies are COMPLETED.
        """
        completed_ids = {
            mt.id for mt in plan.micro_tasks
            if mt.status == MicroTaskStatus.COMPLETED
        }
        ready: list[MicroTask] = []
        for mt in plan.micro_tasks:
            if mt.status != MicroTaskStatus.PLANNED:
                continue
            if all(dep in completed_ids for dep in mt.dependencies):
                ready.append(mt)
        return ready

    def mark_completed(
        self,
        plan: MicroTaskPlan,
        task_id: str,
        result: str,
    ) -> bool:
        """Mark a micro-task as completed.

        Returns True if the task was found and updated, False otherwise.
        """
        for mt in plan.micro_tasks:
            if mt.id == task_id:
                mt.status = MicroTaskStatus.COMPLETED
                mt.result = result
                return True
        return False

    def mark_failed(
        self,
        plan: MicroTaskPlan,
        task_id: str,
        error: str,
    ) -> bool:
        """Mark a micro-task as failed.

        Returns True if the task was found and updated, False otherwise.
        """
        for mt in plan.micro_tasks:
            if mt.id == task_id:
                mt.status = MicroTaskStatus.FAILED
                mt.result = error
                return True
        return False

    # ------------------------------------------------------------------
    # Formatting
    # ------------------------------------------------------------------

    def format_plan(self, plan: MicroTaskPlan) -> str:
        """Format a plan as a Markdown table of all micro-tasks."""
        lines: list[str] = []
        lines.append(f"# Micro-Task Plan (task_id={plan.task_id})")
        lines.append("")
        lines.append(
            f"**Total micro-tasks:** {len(plan.micro_tasks)} | "
            f"**Estimated:** {plan.total_estimated_minutes} min | "
            f"**Max:** {plan.max_micro_tasks}"
        )
        lines.append("")
        lines.append(
            "| # | ID (short) | Title | Files | Est (min) | Deps | Status | Verification |"
        )
        lines.append(
            "|---|------------|-------|-------|-----------|------|--------|--------------|"
        )
        for i, mt in enumerate(plan.micro_tasks, 1):
            short_id = mt.id[:8]
            files = ", ".join(mt.file_paths) if mt.file_paths else "—"
            deps = ", ".join(d[:8] for d in mt.dependencies) if mt.dependencies else "—"
            # Escape pipes in verification command for Markdown table.
            verification = mt.verification_cmd.replace("|", "\\|")
            lines.append(
                f"| {i} | `{short_id}` | {mt.title} | {files} | "
                f"{mt.estimated_minutes} | {deps} | {mt.status.value} | "
                f"`{verification}` |"
            )
        lines.append("")
        if plan.summary:
            lines.append("## Summary")
            lines.append("")
            lines.append(plan.summary)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        task: str,
        micro_tasks: list[MicroTask],
        total_minutes: int,
    ) -> str:
        """Build a human-readable summary string."""
        return (
            f"MicroTaskPlanner: decomposed '{task[:60]}' into "
            f"{len(micro_tasks)} micro-tasks "
            f"(total est. {total_minutes} min, max {self.max_micro_tasks})."
        )


__all__ = [
    "MicroTask",
    "MicroTaskPlan",
    "MicroTaskPlanner",
    "MicroTaskStatus",
]
