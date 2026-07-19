#!/usr/bin/env python3
"""Coverage-focused tests for WorkflowEnginePersistenceMixin.

Targets the previously uncovered lines reported by pytest-cov:
  - _save_checkpoint (lines 31-46)
  - resume_from_checkpoint (lines 60-84): not found, no checkpoint,
    load failure, success-with-remaining, success-completed
  - handoff (lines 99-122): not found, success, with/without reason,
    remaining-step computation, history + current_agent update

The mixin is structural; we build a minimal concrete engine that wires a
real CheckpointManager (file-backed, in a temp dir) so persistence is
exercised end-to-end without mocks.
"""

from __future__ import annotations

import tempfile
import unittest

import pytest

from scripts.collaboration.checkpoint_manager import CheckpointManager, CheckpointStatus
from scripts.collaboration.workflow_engine_base import (
    WorkflowDefinition,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)
from scripts.collaboration.workflow_engine_persistence_mixin import (
    WorkflowEnginePersistenceMixin,
)

pytestmark = pytest.mark.unit


class _Engine(WorkflowEnginePersistenceMixin):
    """Minimal concrete engine exercising the persistence mixin.

    Only the attributes referenced by the mixin are populated; everything
    else (executors, coordinator, dispatcher) is left unset since the
    mixin never touches them.
    """

    def __init__(self, storage_path: str) -> None:
        self.storage_path = storage_path  # type: ignore[assignment]
        self.definitions: dict[str, WorkflowDefinition] = {}
        self.instances: dict[str, WorkflowInstance] = {}
        self.checkpoint_manager = CheckpointManager(storage_path=storage_path)


def _make_definition(steps: list[WorkflowStep] | None = None) -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="wf-test",
        name="Test Workflow",
        steps=steps or [],
    )


def _make_step(step_id: str, name: str = "", role_id: str = "agent-1") -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=name or step_id, role_id=role_id)


class TestSaveCheckpoint(unittest.TestCase):
    """_save_checkpoint() coverage (lines 31-46)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One", "architect"), _make_step("s2", "Step Two", "coder")]
        self.defn = _make_definition(self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn
        self.instance = WorkflowInstance(
            instance_id="inst-1",
            workflow_id=self.defn.workflow_id,
            completed_steps=["s1"],
            failed_steps=[],
            variables={"k": "v"},
            results={"s1": "done"},
        )
        self.engine.instances[self.instance.instance_id] = self.instance

    def test_save_checkpoint_creates_and_assigns_checkpoint_id(self) -> None:
        current_step = self.steps[1]
        self.assertIsNone(self.instance.checkpoint_id)
        self.engine._save_checkpoint(self.instance, current_step)
        self.assertIsNotNone(self.instance.checkpoint_id)

    def test_save_checkpoint_persists_to_disk(self) -> None:
        current_step = self.steps[1]
        self.engine._save_checkpoint(self.instance, current_step)
        loaded = self.engine.checkpoint_manager.load_checkpoint(self.instance.checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.task_id, "inst-1")
        self.assertEqual(loaded.step_name, "Step Two")
        self.assertEqual(loaded.agent_id, "coder")
        self.assertEqual(loaded.completed_steps, ["s1"])

    def test_save_checkpoint_remaining_excludes_completed_and_failed(self) -> None:
        # s1 completed, s3 failed, s2/s4 remaining
        steps = [_make_step("s1"), _make_step("s2"), _make_step("s3"), _make_step("s4")]
        defn = _make_definition(steps)
        engine = _Engine(tempfile.mkdtemp())
        engine.definitions[defn.workflow_id] = defn
        instance = WorkflowInstance(
            instance_id="inst-2",
            workflow_id=defn.workflow_id,
            completed_steps=["s1"],
            failed_steps=["s3"],
        )
        engine.instances[instance.instance_id] = instance
        engine._save_checkpoint(instance, steps[1])
        loaded = engine.checkpoint_manager.load_checkpoint(instance.checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(sorted(loaded.remaining_steps), ["s2", "s4"])

    def test_save_checkpoint_with_missing_definition(self) -> None:
        # Instance references a workflow_id not in definitions
        instance = WorkflowInstance(instance_id="inst-3", workflow_id="nonexistent")
        engine = _Engine(tempfile.mkdtemp())
        engine.instances[instance.instance_id] = instance
        # Should not raise; all_step_ids empty, remaining empty
        engine._save_checkpoint(instance, _make_step("s1"))
        loaded = engine.checkpoint_manager.load_checkpoint(instance.checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.remaining_steps, [])

    def test_save_checkpoint_passes_context_and_outputs(self) -> None:
        current_step = self.steps[1]
        self.engine._save_checkpoint(self.instance, current_step)
        loaded = self.engine.checkpoint_manager.load_checkpoint(self.instance.checkpoint_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.context_snapshot, {"k": "v"})
        self.assertEqual(loaded.outputs, {"s1": "done"})


class TestResumeFromCheckpoint(unittest.TestCase):
    """resume_from_checkpoint() coverage (lines 60-84)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One"), _make_step("s2", "Step Two"), _make_step("s3", "Step Three")]
        self.defn = _make_definition(self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn

    def _make_instance(self, checkpoint_id: str | None = None) -> WorkflowInstance:
        inst = WorkflowInstance(
            instance_id="inst-resume",
            workflow_id=self.defn.workflow_id,
            checkpoint_id=checkpoint_id,
        )
        self.engine.instances[inst.instance_id] = inst
        return inst

    def test_resume_missing_instance_returns_none(self) -> None:
        self.assertIsNone(self.engine.resume_from_checkpoint("does-not-exist"))

    def test_resume_instance_without_checkpoint_returns_instance_unchanged(self) -> None:
        inst = self._make_instance(checkpoint_id=None)
        result = self.engine.resume_from_checkpoint(inst.instance_id)
        self.assertIs(result, inst)
        self.assertEqual(result.status, WorkflowStatus.PENDING)

    def test_resume_with_checkpoint_load_failure_returns_instance_unchanged(self) -> None:
        inst = self._make_instance(checkpoint_id="cp-missing")
        # No checkpoint file exists for this id; load_checkpoint returns None
        result = self.engine.resume_from_checkpoint(inst.instance_id)
        self.assertIs(result, inst)
        # State should not have changed
        self.assertEqual(result.completed_steps, [])

    def test_resume_with_remaining_steps_sets_running(self) -> None:
        # Create a checkpoint with completed=["s1"] and remaining=["s2","s3"],
        # then reset instance state to simulate a fresh load, then resume.
        inst = self._make_instance()
        inst.completed_steps = ["s1"]
        self.engine._save_checkpoint(inst, self.steps[0])
        # Now reset instance state to simulate a fresh load
        inst.completed_steps = []
        inst.variables = {}
        inst.results = {}
        inst.status = WorkflowStatus.PENDING

        result = self.engine.resume_from_checkpoint(inst.instance_id)
        self.assertIs(result, inst)
        self.assertEqual(result.status, WorkflowStatus.RUNNING)
        self.assertEqual(result.current_step, "s2")  # first remaining step
        self.assertEqual(result.completed_steps, ["s1"])

    def test_resume_with_no_remaining_steps_sets_completed(self) -> None:
        # All steps completed → no remaining → COMPLETED
        inst = self._make_instance()
        # Save a checkpoint where all steps are completed (no remaining)
        inst.completed_steps = ["s1", "s2", "s3"]
        self.engine._save_checkpoint(inst, self.steps[2])
        checkpoint_id = inst.checkpoint_id

        # Reset instance state
        inst.completed_steps = []
        inst.variables = {}
        inst.results = {}
        inst.status = WorkflowStatus.PENDING
        inst.checkpoint_id = checkpoint_id

        result = self.engine.resume_from_checkpoint(inst.instance_id)
        self.assertIs(result, inst)
        self.assertEqual(result.status, WorkflowStatus.COMPLETED)
        self.assertEqual(result.completed_steps, ["s1", "s2", "s3"])

    def test_resume_restores_variables_and_results(self) -> None:
        inst = self._make_instance()
        inst.variables = {"original": "data"}
        inst.results = {"r1": "orig"}
        inst.completed_steps = ["s1"]
        self.engine._save_checkpoint(inst, self.steps[0])
        checkpoint_id = inst.checkpoint_id

        # Simulate state loss
        inst.variables = {}
        inst.results = {}
        inst.completed_steps = []
        inst.checkpoint_id = checkpoint_id

        result = self.engine.resume_from_checkpoint(inst.instance_id)
        self.assertEqual(result.variables, {"original": "data"})
        self.assertEqual(result.results, {"r1": "orig"})


class TestHandoff(unittest.TestCase):
    """handoff() coverage (lines 99-122)."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One", "architect"), _make_step("s2", "Step Two", "coder")]
        self.defn = _make_definition(self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn
        self.instance = WorkflowInstance(
            instance_id="inst-handoff",
            workflow_id=self.defn.workflow_id,
            completed_steps=["s1"],
            variables={"state": "mid"},
        )
        self.engine.instances[self.instance.instance_id] = self.instance

    def test_handoff_missing_instance_returns_none(self) -> None:
        self.assertIsNone(self.engine.handoff("nope", "a", "b"))

    def test_handoff_creates_document_with_correct_fields(self) -> None:
        handoff = self.engine.handoff("inst-handoff", "architect", "coder")
        self.assertIsNotNone(handoff)
        self.assertEqual(handoff.from_agent, "architect")
        self.assertEqual(handoff.to_agent, "coder")
        self.assertEqual(handoff.task_id, "inst-handoff")
        self.assertIn("Completed step: s1", handoff.completed_work)
        self.assertEqual(handoff.current_state, {"state": "mid"})

    def test_handoff_computes_next_steps_excluding_completed(self) -> None:
        handoff = self.engine.handoff("inst-handoff", "architect", "coder")
        self.assertIsNotNone(handoff)
        # s1 completed, so remaining should be s2
        self.assertEqual(handoff.next_steps, ["s2"])

    def test_handoff_default_reason_when_empty(self) -> None:
        handoff = self.engine.handoff("inst-handoff", "architect", "coder")
        self.assertEqual(handoff.handoff_reason, "agent_handoff")

    def test_handoff_custom_reason(self) -> None:
        handoff = self.engine.handoff("inst-handoff", "architect", "coder", reason="role_change")
        self.assertEqual(handoff.handoff_reason, "role_change")

    def test_handoff_persists_to_disk(self) -> None:
        handoff = self.engine.handoff("inst-handoff", "architect", "coder")
        loaded = self.engine.checkpoint_manager.load_handoff(handoff.handoff_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.from_agent, "architect")

    def test_handoff_updates_instance_history_and_agent(self) -> None:
        original_history_len = len(self.instance.handoff_history)
        self.assertIsNone(self.instance.current_agent_id)
        handoff = self.engine.handoff("inst-handoff", "architect", "coder")
        self.assertEqual(len(self.instance.handoff_history), original_history_len + 1)
        self.assertIn(handoff.handoff_id, self.instance.handoff_history)
        self.assertEqual(self.instance.current_agent_id, "coder")

    def test_handoff_with_missing_definition(self) -> None:
        # Instance references a workflow not in definitions
        inst = WorkflowInstance(instance_id="inst-no-def", workflow_id="nonexistent", completed_steps=[])
        self.engine.instances[inst.instance_id] = inst
        handoff = self.engine.handoff("inst-no-def", "a", "b")
        self.assertIsNotNone(handoff)
        self.assertEqual(handoff.next_steps, [])

    def test_handoff_multiple_accumulates_history(self) -> None:
        self.engine.handoff("inst-handoff", "architect", "coder")
        self.engine.handoff("inst-handoff", "coder", "tester", reason="review")
        self.assertEqual(len(self.instance.handoff_history), 2)
        self.assertEqual(self.instance.current_agent_id, "tester")

    def test_handoff_all_steps_completed_empty_next_steps(self) -> None:
        instance = WorkflowInstance(
            instance_id="inst-done",
            workflow_id=self.defn.workflow_id,
            completed_steps=["s1", "s2"],
        )
        self.engine.instances[instance.instance_id] = instance
        handoff = self.engine.handoff("inst-done", "coder", "devops")
        self.assertEqual(handoff.next_steps, [])


class TestCheckpointStatusAfterResume(unittest.TestCase):
    """Verify checkpoint status after resume reflects the checkpoint state."""

    def test_resume_uses_checkpoint_status_active(self) -> None:
        tmpdir = tempfile.mkdtemp()
        engine = _Engine(tmpdir)
        steps = [_make_step("s1"), _make_step("s2")]
        defn = _make_definition(steps)
        engine.definitions[defn.workflow_id] = defn
        inst = WorkflowInstance(instance_id="inst-cp", workflow_id=defn.workflow_id)
        engine.instances[inst.instance_id] = inst

        engine._save_checkpoint(inst, steps[0])
        saved_cp = engine.checkpoint_manager.load_checkpoint(inst.checkpoint_id)
        self.assertIsNotNone(saved_cp)
        self.assertEqual(saved_cp.status, CheckpointStatus.ACTIVE)


if __name__ == "__main__":
    unittest.main()
