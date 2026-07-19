#!/usr/bin/env python3
"""Unit tests for workflow_engine_state_mixin.py.

Covers get_workflow_status, register_executor, classify_steps, and
get_step_summary.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import pytest

from scripts.collaboration.checkpoint_manager import CheckpointManager
from scripts.collaboration.workflow_engine_base import (
    NodeType,
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from scripts.collaboration.workflow_engine_lifecycle_mixin import (
    WorkflowEngineLifecycleMixin,
)
from scripts.collaboration.workflow_engine_persistence_mixin import (
    WorkflowEnginePersistenceMixin,
)
from scripts.collaboration.workflow_engine_state_mixin import WorkflowEngineStateMixin
from scripts.collaboration.workflow_engine_transition_mixin import (
    WorkflowEngineTransitionMixin,
)

pytestmark = pytest.mark.unit



class _Engine(
    WorkflowEngineLifecycleMixin,
    WorkflowEngineTransitionMixin,
    WorkflowEnginePersistenceMixin,
    WorkflowEngineStateMixin,
):
    """Minimal concrete engine for state mixin tests."""

    def __init__(self, storage_path: str) -> None:
        self.storage_path = Path(storage_path)
        self.definitions: dict[str, WorkflowDefinition] = {}
        self.instances: dict[str, WorkflowInstance] = {}
        self.executors: dict[str, object] = {}
        self.checkpoint_manager = CheckpointManager(storage_path=storage_path)
        self.checkpoint_interval = 2
        self.coordinator = None
        self.dispatcher = None


def _make_step(
    step_id: str,
    name: str = "",
    role_id: str = "agent-1",
    node_type: NodeType = NodeType.HYBRID,
) -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=name or step_id, role_id=role_id, node_type=node_type)


class TestGetWorkflowStatus(unittest.TestCase):
    """get_workflow_status() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One"), _make_step("s2", "Step Two"), _make_step("s3", "Step Three")]
        self.defn = WorkflowDefinition(workflow_id="wf-test", name="Test", steps=self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn

    def test_instance_not_found_returns_none(self) -> None:
        self.assertIsNone(self.engine.get_workflow_status("nonexistent"))

    def test_with_definition(self) -> None:
        inst = WorkflowInstance(
            instance_id="inst-1",
            workflow_id=self.defn.workflow_id,
            status=WorkflowStatus.RUNNING,
            completed_steps=["s1"],
            current_step="s2",
        )
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-1")
        assert status is not None
        self.assertEqual(status["instance_id"], "inst-1")
        self.assertEqual(status["workflow_id"], "wf-test")
        self.assertEqual(status["status"], "running")
        self.assertEqual(status["progress"], "1/3")
        self.assertAlmostEqual(status["completion_rate"], 33.33333333333333)
        self.assertEqual(status["current_step"], "s2")
        self.assertFalse(status["has_checkpoint"])

    def test_without_definition(self) -> None:
        inst = WorkflowInstance(instance_id="inst-1", workflow_id="nonexistent", completed_steps=["s1"])
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-1")
        assert status is not None
        self.assertEqual(status["progress"], "1/0")
        self.assertEqual(status["completion_rate"], 0)

    def test_zero_steps_completion_rate_zero(self) -> None:
        defn = WorkflowDefinition(workflow_id="wf-empty", name="Empty", steps=[])
        self.engine.definitions[defn.workflow_id] = defn
        inst = WorkflowInstance(instance_id="inst-empty", workflow_id="wf-empty")
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-empty")
        assert status is not None
        self.assertEqual(status["completion_rate"], 0)
        self.assertEqual(status["progress"], "0/0")

    def test_has_checkpoint_flag_true(self) -> None:
        inst = WorkflowInstance(
            instance_id="inst-cp",
            workflow_id=self.defn.workflow_id,
            checkpoint_id="cp-1",
        )
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-cp")
        assert status is not None
        self.assertTrue(status["has_checkpoint"])

    def test_has_checkpoint_flag_false(self) -> None:
        inst = WorkflowInstance(instance_id="inst-nocp", workflow_id=self.defn.workflow_id)
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-nocp")
        assert status is not None
        self.assertFalse(status["has_checkpoint"])

    def test_failed_steps_included(self) -> None:
        inst = WorkflowInstance(
            instance_id="inst-failed",
            workflow_id=self.defn.workflow_id,
            completed_steps=["s1"],
            failed_steps=["s2"],
        )
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-failed")
        assert status is not None
        self.assertEqual(status["failed_steps"], ["s2"])

    def test_full_completion(self) -> None:
        inst = WorkflowInstance(
            instance_id="inst-done",
            workflow_id=self.defn.workflow_id,
            status=WorkflowStatus.COMPLETED,
            completed_steps=["s1", "s2", "s3"],
        )
        self.engine.instances[inst.instance_id] = inst
        status = self.engine.get_workflow_status("inst-done")
        assert status is not None
        self.assertEqual(status["completion_rate"], 100.0)
        self.assertEqual(status["progress"], "3/3")


class TestRegisterExecutor(unittest.TestCase):
    """register_executor() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)

    def test_register_and_use(self) -> None:
        called: list[str] = []

        def executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            called.append(step.step_id)
            return "executed"

        self.engine.register_executor("analyze", executor)
        self.assertIn("analyze", self.engine.executors)

        step = WorkflowStep(step_id="s1", action="analyze")
        result = self.engine.executors["analyze"](step, {})  # type: ignore[operator]
        self.assertEqual(result, "executed")
        self.assertEqual(called, ["s1"])

    def test_overwrite_executor(self) -> None:
        def first(step: WorkflowStep, variables: dict[str, object]) -> str:
            return "first"

        def second(step: WorkflowStep, variables: dict[str, object]) -> str:
            return "second"

        self.engine.register_executor("action", first)
        self.engine.register_executor("action", second)
        self.assertEqual(self.engine.executors["action"](WorkflowStep(), {}), "second")  # type: ignore[operator]


class TestClassifySteps(unittest.TestCase):
    """classify_steps() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)

    def test_none_workflow_id_empty_definitions(self) -> None:
        result = self.engine.classify_steps(None)
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["deterministic"], 0)
        self.assertEqual(result["llm"], 0)
        self.assertEqual(result["hybrid"], 0)
        self.assertEqual(result["by_step"], [])

    def test_none_workflow_id_uses_latest(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.LLM),
            _make_step("s2", node_type=NodeType.DETERMINISTIC),
        ]
        defn = WorkflowDefinition(workflow_id="wf-latest", name="Latest", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps(None)
        self.assertEqual(result["total"], 2)
        self.assertEqual(result["llm"], 1)
        self.assertEqual(result["deterministic"], 1)

    def test_workflow_id_not_found(self) -> None:
        result = self.engine.classify_steps("nonexistent")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["by_step"], [])

    def test_mixed_node_types(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.DETERMINISTIC),
            _make_step("s2", node_type=NodeType.LLM),
            _make_step("s3", node_type=NodeType.HYBRID),
            _make_step("s4", node_type=NodeType.LLM),
        ]
        defn = WorkflowDefinition(workflow_id="wf-mixed", name="Mixed", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-mixed")
        self.assertEqual(result["total"], 4)
        self.assertEqual(result["deterministic"], 1)
        self.assertEqual(result["llm"], 2)
        self.assertEqual(result["hybrid"], 1)
        self.assertEqual(result["deterministic_pct"], 25.0)
        self.assertEqual(result["llm_pct"], 50.0)
        self.assertEqual(result["hybrid_pct"], 25.0)

    def test_all_deterministic(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.DETERMINISTIC),
            _make_step("s2", node_type=NodeType.DETERMINISTIC),
        ]
        defn = WorkflowDefinition(workflow_id="wf-det", name="Det", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-det")
        self.assertEqual(result["deterministic"], 2)
        self.assertEqual(result["llm"], 0)
        self.assertEqual(result["hybrid"], 0)
        self.assertEqual(result["deterministic_pct"], 100.0)

    def test_all_llm(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.LLM),
            _make_step("s2", node_type=NodeType.LLM),
        ]
        defn = WorkflowDefinition(workflow_id="wf-llm", name="LLM", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-llm")
        self.assertEqual(result["llm"], 2)
        self.assertEqual(result["deterministic"], 0)
        self.assertEqual(result["hybrid"], 0)
        self.assertEqual(result["llm_pct"], 100.0)

    def test_all_hybrid(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.HYBRID),
            _make_step("s2", node_type=NodeType.HYBRID),
        ]
        defn = WorkflowDefinition(workflow_id="wf-hyb", name="Hyb", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-hyb")
        self.assertEqual(result["hybrid"], 2)
        self.assertEqual(result["deterministic"], 0)
        self.assertEqual(result["llm"], 0)
        self.assertEqual(result["hybrid_pct"], 100.0)

    def test_empty_steps(self) -> None:
        defn = WorkflowDefinition(workflow_id="wf-empty", name="Empty", steps=[])
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-empty")
        self.assertEqual(result["total"], 0)
        self.assertEqual(result["by_step"], [])

    def test_by_step_list_structure(self) -> None:
        steps = [
            _make_step("s1", name="First", node_type=NodeType.LLM),
            _make_step("s2", name="Second", node_type=NodeType.DETERMINISTIC),
        ]
        defn = WorkflowDefinition(workflow_id="wf-by", name="ByStep", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-by")
        by_step = result["by_step"]
        self.assertEqual(len(by_step), 2)
        self.assertEqual(by_step[0], {"step_id": "s1", "name": "First", "node_type": "llm"})
        self.assertEqual(by_step[1], {"step_id": "s2", "name": "Second", "node_type": "deterministic"})

    def test_percentages_sum_100(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.DETERMINISTIC),
            _make_step("s2", node_type=NodeType.LLM),
            _make_step("s3", node_type=NodeType.HYBRID),
            _make_step("s4", node_type=NodeType.LLM),
        ]
        defn = WorkflowDefinition(workflow_id="wf-pct", name="Pct", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine.classify_steps("wf-pct")
        total_pct = result["deterministic_pct"] + result["llm_pct"] + result["hybrid_pct"]
        self.assertAlmostEqual(total_pct, 100.0, places=2)

    def test_none_workflow_id_multiple_definitions_uses_last_inserted(self) -> None:
        defn1 = WorkflowDefinition(workflow_id="wf-1", steps=[_make_step("a", node_type=NodeType.LLM)])
        defn2 = WorkflowDefinition(workflow_id="wf-2", steps=[_make_step("b", node_type=NodeType.DETERMINISTIC)])
        self.engine.definitions[defn1.workflow_id] = defn1
        self.engine.definitions[defn2.workflow_id] = defn2
        result = self.engine.classify_steps(None)
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["deterministic"], 1)


class TestGetStepSummary(unittest.TestCase):
    """get_step_summary() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)

    def test_summary_delegates_to_classify(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.DETERMINISTIC),
            _make_step("s2", node_type=NodeType.LLM),
            _make_step("s3", node_type=NodeType.HYBRID),
        ]
        defn = WorkflowDefinition(workflow_id="wf-sum", name="Summary", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        summary = self.engine.get_step_summary("wf-sum")
        self.assertEqual(summary["deterministic"], 1)
        self.assertEqual(summary["llm"], 1)
        self.assertEqual(summary["hybrid"], 1)
        self.assertEqual(summary["total"], 3)

    def test_summary_counts(self) -> None:
        steps = [
            _make_step("s1", node_type=NodeType.LLM),
            _make_step("s2", node_type=NodeType.LLM),
            _make_step("s3", node_type=NodeType.LLM),
        ]
        defn = WorkflowDefinition(workflow_id="wf-llm-sum", name="LLM Sum", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        summary = self.engine.get_step_summary("wf-llm-sum")
        self.assertEqual(summary["llm"], 3)
        self.assertEqual(summary["deterministic"], 0)
        self.assertEqual(summary["hybrid"], 0)
        self.assertEqual(summary["total"], 3)

    def test_summary_empty_workflow(self) -> None:
        summary = self.engine.get_step_summary("nonexistent")
        self.assertEqual(summary["total"], 0)
        self.assertEqual(summary["deterministic"], 0)
        self.assertEqual(summary["llm"], 0)
        self.assertEqual(summary["hybrid"], 0)

    def test_summary_none_workflow_id(self) -> None:
        summary = self.engine.get_step_summary(None)
        self.assertEqual(summary["total"], 0)


if __name__ == "__main__":
    unittest.main()
