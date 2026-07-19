#!/usr/bin/env python3
"""Unit tests for workflow_engine_transition_mixin.py.

Covers start_workflow, execute_step (10+ scenarios), _default_step_executor,
and _get_next_step.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from scripts.collaboration.checkpoint_manager import CheckpointManager
from scripts.collaboration.workflow_engine_base import (
    StepStatus,
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
    """Minimal concrete engine for transition mixin tests."""

    def __init__(self, storage_path: str, dispatcher: object | None = None) -> None:
        self.storage_path = Path(storage_path)
        self.definitions: dict[str, WorkflowDefinition] = {}
        self.instances: dict[str, WorkflowInstance] = {}
        self.executors: dict[str, object] = {}
        self.checkpoint_manager = CheckpointManager(storage_path=storage_path)
        self.checkpoint_interval = 2
        self.coordinator = None
        self.dispatcher = dispatcher


def _make_step(
    step_id: str,
    name: str = "",
    role_id: str = "agent-1",
    action: str = "execute",
    description: str = "",
) -> WorkflowStep:
    return WorkflowStep(
        step_id=step_id,
        name=name or step_id,
        role_id=role_id,
        action=action,
        description=description,
    )


class TestStartWorkflow(unittest.TestCase):
    """start_workflow() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One"), _make_step("s2", "Step Two")]
        self.defn = WorkflowDefinition(workflow_id="wf-test", name="Test", steps=self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn

    def test_definition_not_found_returns_none(self) -> None:
        self.assertIsNone(self.engine.start_workflow("nonexistent"))

    def test_creates_running_instance(self) -> None:
        inst = self.engine.start_workflow("wf-test")
        assert inst is not None
        self.assertEqual(inst.status, WorkflowStatus.RUNNING)
        self.assertIsNotNone(inst.started_at)

    def test_sets_current_step_to_first(self) -> None:
        inst = self.engine.start_workflow("wf-test")
        assert inst is not None
        self.assertEqual(inst.current_step, "s1")

    def test_no_steps_current_step_none(self) -> None:
        defn = WorkflowDefinition(workflow_id="wf-empty", name="Empty", steps=[])
        self.engine.definitions[defn.workflow_id] = defn
        inst = self.engine.start_workflow("wf-empty")
        assert inst is not None
        self.assertIsNone(inst.current_step)

    def test_variables_passed_through(self) -> None:
        inst = self.engine.start_workflow("wf-test", variables={"k": "v"})
        assert inst is not None
        self.assertEqual(inst.variables, {"k": "v"})

    def test_variables_default_empty(self) -> None:
        inst = self.engine.start_workflow("wf-test")
        assert inst is not None
        self.assertEqual(inst.variables, {})

    def test_instance_registered(self) -> None:
        inst = self.engine.start_workflow("wf-test")
        assert inst is not None
        self.assertIn(inst.instance_id, self.engine.instances)

    def test_instance_id_generated(self) -> None:
        inst = self.engine.start_workflow("wf-test")
        assert inst is not None
        self.assertTrue(inst.instance_id.startswith("inst-"))

    def test_workflow_id_set(self) -> None:
        inst = self.engine.start_workflow("wf-test")
        assert inst is not None
        self.assertEqual(inst.workflow_id, "wf-test")


class TestExecuteStep(unittest.TestCase):
    """execute_step() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One"), _make_step("s2", "Step Two"), _make_step("s3", "Step Three")]
        self.defn = WorkflowDefinition(workflow_id="wf-test", name="Test", steps=self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn

    def _make_instance(self, current_step: str | None = "s1") -> WorkflowInstance:
        inst = WorkflowInstance(
            instance_id="inst-1",
            workflow_id=self.defn.workflow_id,
            status=WorkflowStatus.RUNNING,
            current_step=current_step,
        )
        self.engine.instances[inst.instance_id] = inst
        return inst

    def test_instance_not_found_returns_none(self) -> None:
        self.assertIsNone(self.engine.execute_step("nonexistent"))

    def test_definition_not_found_returns_none(self) -> None:
        inst = WorkflowInstance(instance_id="inst-no-def", workflow_id="nonexistent", current_step="s1")
        self.engine.instances[inst.instance_id] = inst
        self.assertIsNone(self.engine.execute_step("inst-no-def"))

    def test_current_step_not_found_returns_none(self) -> None:
        inst = WorkflowInstance(
            instance_id="inst-bad-step",
            workflow_id=self.defn.workflow_id,
            current_step="nonexistent_step",
        )
        self.engine.instances[inst.instance_id] = inst
        self.assertIsNone(self.engine.execute_step("inst-bad-step"))

    def test_current_step_none_returns_none(self) -> None:
        self._make_instance(current_step=None)
        self.assertIsNone(self.engine.execute_step("inst-1"))

    def test_success_with_step_executor(self) -> None:
        self._make_instance(current_step="s1")

        def executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            return "custom_result"

        step = self.engine.execute_step("inst-1", step_executor=executor)
        assert step is not None
        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertEqual(step.result, "custom_result")

    def test_success_with_registered_executor(self) -> None:
        self._make_instance(current_step="s1")

        def executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            return "registered_result"

        self.engine.register_executor("execute", executor)
        step = self.engine.execute_step("inst-1")
        assert step is not None
        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertEqual(step.result, "registered_result")

    def test_success_with_default_executor_no_dispatcher(self) -> None:
        self._make_instance(current_step="s1")
        step = self.engine.execute_step("inst-1")
        assert step is not None
        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertEqual(step.result, {"action": "execute", "role": "agent-1", "status": "mock_completed"})

    def test_success_with_default_executor_dispatcher(self) -> None:
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.summary = "dispatch summary"
        mock_dispatcher.dispatch.return_value = mock_result

        engine = _Engine(self.tmpdir, dispatcher=mock_dispatcher)
        engine.definitions[self.defn.workflow_id] = self.defn
        inst = WorkflowInstance(
            instance_id="inst-disp",
            workflow_id=self.defn.workflow_id,
            status=WorkflowStatus.RUNNING,
            current_step="s1",
        )
        engine.instances[inst.instance_id] = inst

        step = engine.execute_step("inst-disp")
        assert step is not None
        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertEqual(step.result, {"dispatch_success": True, "summary": "dispatch summary"})
        mock_dispatcher.dispatch.assert_called_once_with(task_description="", roles=["agent-1"])

    def test_checkpoint_interval_trigger(self) -> None:
        inst = self._make_instance(current_step="s1")
        # checkpoint_interval = 2, so checkpoint on every 2nd completed step
        # First step: completed_steps = ["s1"], len=1, 1 % 2 != 0 → no checkpoint
        self.engine.execute_step("inst-1")
        self.assertIsNone(inst.checkpoint_id)

        # Second step: completed_steps = ["s1", "s2"], len=2, 2 % 2 == 0 → checkpoint
        self.engine.execute_step("inst-1")
        self.assertIsNotNone(inst.checkpoint_id)

    def test_checkpoint_interval_1(self) -> None:
        engine = _Engine(self.tmpdir)
        engine.definitions[self.defn.workflow_id] = self.defn
        engine.checkpoint_interval = 1
        inst = WorkflowInstance(
            instance_id="inst-cp1",
            workflow_id=self.defn.workflow_id,
            status=WorkflowStatus.RUNNING,
            current_step="s1",
        )
        engine.instances[inst.instance_id] = inst

        engine.execute_step("inst-cp1")
        self.assertIsNotNone(inst.checkpoint_id)

    def test_completion_no_next_step(self) -> None:
        inst = self._make_instance(current_step="s3")
        self.engine.execute_step("inst-1")
        self.assertEqual(inst.status, WorkflowStatus.COMPLETED)
        self.assertIsNotNone(inst.completed_at)

    def test_failure_runtime_error(self) -> None:
        self._make_instance(current_step="s1")

        def failing_executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            raise RuntimeError("execution failed")

        step = self.engine.execute_step("inst-1", step_executor=failing_executor)
        assert step is not None
        self.assertEqual(step.status, StepStatus.FAILED)
        self.assertIn("execution failed", step.error)
        inst = self.engine.instances["inst-1"]
        self.assertIn("s1", inst.failed_steps)
        self.assertEqual(inst.error, "execution failed")

    def test_failure_value_error(self) -> None:
        self._make_instance(current_step="s1")

        def failing_executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            raise ValueError("bad value")

        step = self.engine.execute_step("inst-1", step_executor=failing_executor)
        assert step is not None
        self.assertEqual(step.status, StepStatus.FAILED)

    def test_failure_attribute_error(self) -> None:
        self._make_instance(current_step="s1")

        def failing_executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            raise AttributeError("missing attr")

        step = self.engine.execute_step("inst-1", step_executor=failing_executor)
        assert step is not None
        self.assertEqual(step.status, StepStatus.FAILED)

    def test_failure_type_error(self) -> None:
        self._make_instance(current_step="s1")

        def failing_executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            raise TypeError("wrong type")

        step = self.engine.execute_step("inst-1", step_executor=failing_executor)
        assert step is not None
        self.assertEqual(step.status, StepStatus.FAILED)

    def test_step_marked_completed(self) -> None:
        self._make_instance(current_step="s1")
        step = self.engine.execute_step("inst-1")
        assert step is not None
        self.assertEqual(step.status, StepStatus.COMPLETED)

    def test_advances_to_next_step(self) -> None:
        inst = self._make_instance(current_step="s1")
        self.engine.execute_step("inst-1")
        self.assertEqual(inst.current_step, "s2")
        self.assertIn("s1", inst.completed_steps)

    def test_result_stored_in_step(self) -> None:
        self._make_instance(current_step="s1")

        def executor(step: WorkflowStep, variables: dict[str, object]) -> dict[str, str]:
            return {"output": "data"}

        step = self.engine.execute_step("inst-1", step_executor=executor)
        assert step is not None
        self.assertEqual(step.result, {"output": "data"})

    def test_results_stored_in_instance(self) -> None:
        inst = self._make_instance(current_step="s1")

        def executor(step: WorkflowStep, variables: dict[str, object]) -> str:
            return "result_data"

        self.engine.execute_step("inst-1", step_executor=executor)
        # Instance doesn't store results in execute_step directly, but completed_steps should be updated
        self.assertIn("s1", inst.completed_steps)


class TestDefaultStepExecutor(unittest.TestCase):
    """_default_step_executor() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.step = _make_step("s1", "Step One", "architect", "design", "Design the system")

    def test_with_dispatcher(self) -> None:
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.summary = "Dispatch completed successfully"
        mock_dispatcher.dispatch.return_value = mock_result

        engine = _Engine(self.tmpdir, dispatcher=mock_dispatcher)
        result = engine._default_step_executor(self.step, {})
        self.assertEqual(result, {"dispatch_success": True, "summary": "Dispatch completed successfully"})
        mock_dispatcher.dispatch.assert_called_once_with(
            task_description="Design the system",
            roles=["architect"],
        )

    def test_without_dispatcher(self) -> None:
        engine = _Engine(self.tmpdir)
        result = engine._default_step_executor(self.step, {})
        self.assertEqual(result, {"action": "design", "role": "architect", "status": "mock_completed"})

    def test_dispatcher_result_summary_truncated(self) -> None:
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.summary = "x" * 300
        mock_dispatcher.dispatch.return_value = mock_result

        engine = _Engine(self.tmpdir, dispatcher=mock_dispatcher)
        result = engine._default_step_executor(self.step, {})
        self.assertEqual(len(result["summary"]), 200)

    def test_dispatcher_result_no_summary_attr(self) -> None:
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        # Remove summary attribute to test getattr fallback
        del mock_result.summary
        mock_dispatcher.dispatch.return_value = mock_result

        engine = _Engine(self.tmpdir, dispatcher=mock_dispatcher)
        result = engine._default_step_executor(self.step, {})
        self.assertEqual(result["dispatch_success"], False)
        self.assertEqual(result["summary"], "")

    def test_dispatcher_failed_dispatch(self) -> None:
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.summary = "Dispatch failed"
        mock_dispatcher.dispatch.return_value = mock_result

        engine = _Engine(self.tmpdir, dispatcher=mock_dispatcher)
        result = engine._default_step_executor(self.step, {})
        self.assertEqual(result["dispatch_success"], False)
        self.assertEqual(result["summary"], "Dispatch failed")


class TestGetNextStep(unittest.TestCase):
    """_get_next_step() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One"), _make_step("s2", "Step Two"), _make_step("s3", "Step Three")]
        self.defn = WorkflowDefinition(workflow_id="wf-test", name="Test", steps=self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn

    def test_returns_next_step(self) -> None:
        result = self.engine._get_next_step(self.defn, self.steps[0])
        assert result is not None
        self.assertEqual(result.step_id, "s2")

    def test_returns_step_after_middle(self) -> None:
        result = self.engine._get_next_step(self.defn, self.steps[1])
        assert result is not None
        self.assertEqual(result.step_id, "s3")

    def test_current_is_last_returns_none(self) -> None:
        result = self.engine._get_next_step(self.defn, self.steps[2])
        self.assertIsNone(result)

    def test_current_not_in_definition_returns_none(self) -> None:
        foreign_step = _make_step("foreign", "Foreign Step")
        result = self.engine._get_next_step(self.defn, foreign_step)
        self.assertIsNone(result)

    def test_empty_steps_returns_none(self) -> None:
        defn = WorkflowDefinition(workflow_id="wf-empty", name="Empty", steps=[])
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine._get_next_step(defn, _make_step("s1"))
        self.assertIsNone(result)

    def test_single_step_returns_none(self) -> None:
        steps = [_make_step("s1", "Only Step")]
        defn = WorkflowDefinition(workflow_id="wf-single", name="Single", steps=steps)
        self.engine.definitions[defn.workflow_id] = defn
        result = self.engine._get_next_step(defn, steps[0])
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
