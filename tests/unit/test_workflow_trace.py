"""Unit tests for WorkflowTrace (V4.4.4).

5 tests covering the 7-dimension Iron Rules:
1. test_trace_populated — Happy (dispatch → trace has ≥1 step)
2. test_trace_in_report — Side-Effect (report contains "## Workflow Trace")
3. test_empty_workflow — Boundary (dry_run → empty trace, no steps)
4. test_trace_to_markdown — Happy (markdown renders all sections)
5. test_call_counter_er — Anti-Ghost (_call_counter_er increments)

Uses REAL components (MultiAgentDispatcher with default mock backend),
not Mock — per V4.4.4 implementation rules.
"""

from __future__ import annotations

import os
import sys

import pytest

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import scripts.collaboration.models_dispatch as models_dispatch_module  # noqa: E402
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402
from scripts.collaboration.models import WorkflowStep, WorkflowTrace  # noqa: E402

pytestmark = [pytest.mark.unit]


@pytest.fixture
def dispatcher() -> MultiAgentDispatcher:
    """Create a real MultiAgentDispatcher with default mock backend."""
    return MultiAgentDispatcher()


# ---------------------------------------------------------------------------
# Test 1: trace populated (Happy)
# ---------------------------------------------------------------------------


def test_trace_populated(dispatcher: MultiAgentDispatcher) -> None:
    """Happy: dispatch → result.workflow_trace has ≥1 step."""
    result = dispatcher.dispatch("Design a REST API for user management", dry_run=False)
    assert result.workflow_trace is not None, "workflow_trace must be set after dispatch"
    assert len(result.workflow_trace.steps) >= 1, (
        f"expected ≥1 step, got {len(result.workflow_trace.steps)}"
    )
    # Each step should have the required fields populated.
    step = result.workflow_trace.steps[0]
    assert step.step_name, "step_name must be non-empty"
    assert step.role_id, "role_id must be non-empty"
    assert step.status in ("success", "failed", "running"), (
        f"unexpected status: {step.status}"
    )


# ---------------------------------------------------------------------------
# Test 2: trace in report (Side-Effect)
# ---------------------------------------------------------------------------


def test_trace_in_report(dispatcher: MultiAgentDispatcher) -> None:
    """Side-Effect: report contains '## Workflow Trace' section."""
    result = dispatcher.dispatch("Design a simple cache layer", dry_run=False)
    md = result.to_markdown()
    assert "Workflow Trace" in md, "report must contain 'Workflow Trace' section"
    # The trace section header uses the 🔍 emoji prefix.
    assert "## 🔍 Workflow Trace" in md, "report must contain the Workflow Trace header"


# ---------------------------------------------------------------------------
# Test 3: empty workflow (Boundary — dry_run → empty trace)
# ---------------------------------------------------------------------------


def test_empty_workflow(dispatcher: MultiAgentDispatcher) -> None:
    """Boundary: dry_run=True → trace exists but has 0 steps."""
    result = dispatcher.dispatch("Design something", dry_run=True)
    # Trace must still be set (anti-ghost: always present, even if empty).
    assert result.workflow_trace is not None, (
        "workflow_trace must be set even on dry_run (anti-ghost)"
    )
    assert len(result.workflow_trace.steps) == 0, (
        f"dry_run must produce 0 steps, got {len(result.workflow_trace.steps)}"
    )
    # Task description should still be populated.
    assert result.workflow_trace.task_description, "task_description must be set"


# ---------------------------------------------------------------------------
# Test 4: to_markdown renders (Happy)
# ---------------------------------------------------------------------------


def test_trace_to_markdown() -> None:
    """Happy: WorkflowTrace.to_markdown renders all sections."""
    trace = WorkflowTrace(
        task_description="Test task for markdown rendering",
        decomposition_tree=[
            {
                "task": "decompose architecture",
                "roles": ["architect"],
                "subtasks": ["sub-task-A", "sub-task-B"],
            },
        ],
        steps=[
            WorkflowStep(
                step_name="analyze",
                role_id="architect",
                agent_id="agent-architect-abc123def",
                status="success",
                duration_ms=150.5,
                details="Analysis complete",
            ),
            WorkflowStep(
                step_name="implement",
                role_id="solo-coder",
                agent_id="agent-solo-coder-deadbeef",
                status="failed",
                duration_ms=3200.0,
                details="Compilation error",
            ),
        ],
        decision_points=[
            {"topic": "use cache layer", "outcome": "APPROVED"},
            {"topic": "sharding strategy", "outcome": "SPLIT"},
        ],
    )
    md = trace.to_markdown()

    # Header
    assert "## 🔍 Workflow Trace" in md
    assert "**Task**: Test task for markdown rendering" in md

    # Decomposition tree
    assert "### Decomposition Tree" in md
    assert "decompose architecture" in md
    assert "architect" in md
    assert "sub-task-A" in md

    # Steps table
    assert "### Steps" in md
    assert "| Step | Role | Agent | Status | Duration (ms) | Details |" in md
    assert "| analyze | architect |" in md
    assert "agent-architect-abc123def" in md
    assert "150.5" in md
    assert "success" in md
    assert "| implement | solo-coder |" in md
    assert "failed" in md

    # Decision points
    assert "### Decision Points" in md
    assert "use cache layer" in md
    assert "APPROVED" in md
    assert "sharding strategy" in md
    assert "SPLIT" in md


# ---------------------------------------------------------------------------
# Test 5: call_counter (Anti-Ghost)
# ---------------------------------------------------------------------------


def test_call_counter_er() -> None:
    """Anti-Ghost: module-level _call_counter_er increments on construction."""
    before = models_dispatch_module._call_counter_er
    # Construct a WorkflowTrace — should bump the counter.
    WorkflowTrace(task_description="anti-ghost verification")
    after = models_dispatch_module._call_counter_er
    assert after > before, (
        f"_call_counter_er did not increment: before={before}, after={after}"
    )
