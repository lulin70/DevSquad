#!/usr/bin/env python3
"""WorkflowEngine + CheckpointManager + IntentWorkflowMapper +
TaskCompletionChecker Integration Tests.

End-to-end integration tests for the workflow execution pipeline.
Verifies CROSS-MODULE interactions among:

    scripts/collaboration/workflow_engine.py         — WorkflowEngine facade
        (task→workflow splitting, step execution, lifecycle templates).
    scripts/collaboration/checkpoint_manager.py      — CheckpointManager
        (state persistence, SHA256 integrity, handoff docs, lifecycle state).
    scripts/collaboration/intent_workflow_mapper.py  — IntentWorkflowMapper
        (intent→workflow-chain mapping, flow vs standalone, zh/en/ja).
    scripts/collaboration/task_completion_checker.py — TaskCompletionChecker
        (dispatch result checking, completion tracking, progress reports).

Flow:
    IntentWorkflowMapper.detect_intent(task) → IntentMatch
    WorkflowEngine.create_workflow_from_task(task) → WorkflowDefinition
    WorkflowEngine.start_workflow() → execute_step() → _save_checkpoint()
    CheckpointManager.save/load_checkpoint() → resume_from_checkpoint()
    TaskCompletionChecker.check_dispatch_result() → TaskCompletionResult

Test categories:
    T1: IntentWorkflowMapper — intent detection, flow classification, i18n
    T2: CheckpointManager — save/load, integrity hash, handoff, lifecycle
    T3: WorkflowEngine — task splitting, lifecycle, start/execute, classify
    T4: TaskCompletionChecker — dispatch result, completion tracking, summary
    T5: Integration — intent→workflow→checkpoint→resume→completion end-to-end
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import unittest
from types import SimpleNamespace
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.checkpoint_manager import (
    Checkpoint,
    CheckpointManager,
    CheckpointStatus,
    HandoffDocument,
)
from scripts.collaboration.intent_workflow_mapper import IntentWorkflowMapper
from scripts.collaboration.task_completion_checker import TaskCompletionChecker
from scripts.collaboration.workflow_engine import (
    LIFECYCLE_TEMPLATES,
    WorkflowEngine,
    WorkflowStatus,
    WorkflowStep,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_dispatch_result(
    task_description: str = "test task",
    worker_results: list[dict[str, Any]] | None = None,
) -> SimpleNamespace:
    """Build a duck-typed DispatchResult for TaskCompletionChecker."""
    return SimpleNamespace(
        task_description=task_description,
        worker_results=worker_results or [],
    )


def _make_worker_result(
    role: str = "solo-coder",
    success: bool = True,
    output: str = "done",
    error: str | None = None,
) -> dict[str, Any]:
    """Build a worker-result dict accepted by TaskCompletionChecker."""
    return {
        "role_id": role,
        "role_name": role,
        "success": success,
        "output": output,
        "error": error,
    }


# ---------------------------------------------------------------------------
# T1: IntentWorkflowMapper — intent detection, flow classification, i18n
# ---------------------------------------------------------------------------


class T1_IntentWorkflowMapper(unittest.TestCase):
    """T1: IntentWorkflowMapper multi-language intent detection."""

    def setUp(self) -> None:
        self.mapper = IntentWorkflowMapper()

    def test_01_detect_bug_fix_intent_zh(self) -> None:
        """Verify: Chinese bug-fix keywords trigger bug_fix intent."""
        match = self.mapper.detect_intent("修复登录bug", lang="zh")
        self.assertIsNotNone(match)
        assert match is not None  # for type checker
        self.assertEqual(match.intent_type, "bug_fix")
        self.assertIn("solo-coder", match.required_roles)
        self.assertEqual(match.gate, "prove_it_pattern")

    def test_02_detect_new_feature_intent_en(self) -> None:
        """Verify: English new-feature keywords trigger new_feature intent."""
        match = self.mapper.detect_intent("implement a new user authentication feature", lang="en")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.intent_type, "new_feature")
        self.assertIn("architect", match.required_roles)
        self.assertEqual(match.gate, "spec_first")

    def test_03_detect_security_review_intent(self) -> None:
        """Verify: security keywords trigger security_review intent."""
        match = self.mapper.detect_intent("审查安全漏洞和SQL注入风险", lang="zh")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.intent_type, "security_review")
        self.assertIn("security", match.required_roles)

    def test_04_classify_flow_vs_standalone_zh(self) -> None:
        """Verify: Chinese continuity keywords classify as flow."""
        self.assertEqual(self.mapper.classify_flow_vs_standalone("然后实现下一步"), "flow")
        self.assertEqual(self.mapper.classify_flow_vs_standalone("写一个排序函数"), "standalone")

    def test_05_classify_flow_vs_standalone_en(self) -> None:
        """Verify: English continuity keywords classify as flow (word-boundary)."""
        self.assertEqual(self.mapper.classify_flow_vs_standalone("then deploy the service"), "flow")
        # 'then' inside 'authentication' must NOT trigger flow (word-boundary).
        self.assertEqual(self.mapper.classify_flow_vs_standalone("implement authentication"), "standalone")

    def test_06_get_available_intents_sorted(self) -> None:
        """Verify: get_available_intents returns sorted intent types."""
        intents = self.mapper.get_available_intents()
        self.assertEqual(intents, sorted(intents))
        self.assertIn("bug_fix", intents)
        self.assertIn("new_feature", intents)
        self.assertIn("deployment", intents)

    def test_07_no_match_returns_none(self) -> None:
        """Verify: unrelated text produces no intent match."""
        match = self.mapper.detect_intent("hello world random text", lang="en")
        self.assertIsNone(match)


# ---------------------------------------------------------------------------
# T2: CheckpointManager — save/load, integrity hash, handoff, lifecycle
# ---------------------------------------------------------------------------


class T2_CheckpointManager(unittest.TestCase):
    """T2: CheckpointManager persistence, integrity, and handoff."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="devsquad_cm_")
        self.manager = CheckpointManager(storage_path=self._tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_01_save_and_load_checkpoint_roundtrip(self) -> None:
        """Verify: save_checkpoint then load_checkpoint returns same data."""
        cp = Checkpoint(
            task_id="task-001",
            step_name="Implementation",
            agent_id="solo-coder",
            completed_steps=["P1", "P2"],
            remaining_steps=["P3", "P4"],
            progress_percentage=0.5,
            context_snapshot={"key": "value"},
        )
        self.assertTrue(self.manager.save_checkpoint(cp))
        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.task_id, "task-001")
        self.assertEqual(loaded.completed_steps, ["P1", "P2"])
        self.assertEqual(loaded.progress_percentage, 0.5)

    def test_02_checkpoint_integrity_hash_tamper_detected(self) -> None:
        """Verify: hash mismatch on tampered file returns None."""
        cp = Checkpoint(task_id="task-002", step_name="Test", completed_steps=["A"])
        self.manager.save_checkpoint(cp)
        # Tamper: rewrite the checkpoint file with a wrong hash.
        cp_path = self.manager.checkpoints_dir / f"{cp.checkpoint_id}.json"
        with open(cp_path, encoding="utf-8") as f:
            data = json.load(f)
        data["checkpoint_hash"] = "tampered_hash"
        with open(cp_path, "w", encoding="utf-8") as f:
            json.dump(data, f)
        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        self.assertIsNone(loaded)

    def test_03_create_checkpoint_from_dispatch_computes_progress(self) -> None:
        """Verify: create_checkpoint_from_dispatch computes progress percentage."""
        cp = self.manager.create_checkpoint_from_dispatch(
            task_id="task-003",
            step_name="Deployment",
            agent_id="devops",
            completed_steps=["s1", "s2", "s3"],
            remaining_steps=["s4"],
            context={"phase": "deploy"},
        )
        self.assertEqual(cp.progress_percentage, 0.75)
        self.assertEqual(cp.agent_id, "devops")
        self.assertEqual(cp.status, CheckpointStatus.ACTIVE)

    def test_04_save_and_load_handoff_roundtrip(self) -> None:
        """Verify: save_handoff then load_handoff returns same document."""
        handoff = HandoffDocument(
            task_id="task-004",
            from_agent="architect",
            to_agent="solo-coder",
            completed_work=["Designed API"],
            current_state={"design": "approved"},
            next_steps=["Implement API"],
            handoff_reason="design_complete",
        )
        self.assertTrue(self.manager.save_handoff(handoff))
        loaded = self.manager.load_handoff(handoff.handoff_id)
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded.from_agent, "architect")
        self.assertEqual(loaded.to_agent, "solo-coder")
        self.assertEqual(loaded.next_steps, ["Implement API"])

    def test_05_handoff_to_markdown_renders_sections(self) -> None:
        """Verify: to_markdown produces readable sections."""
        handoff = HandoffDocument(
            task_id="task-005",
            from_agent="tester",
            to_agent="devops",
            completed_work=["Ran tests"],
            current_state={"coverage": "85%"},
            next_steps=["Deploy"],
        )
        md = handoff.to_markdown()
        self.assertIn("# Task Handoff Document", md)
        self.assertIn("Completed Work", md)
        self.assertIn("Ran tests", md)
        self.assertIn("Next Steps", md)

    def test_06_save_and_load_lifecycle_state(self) -> None:
        """Verify: save_lifecycle_state then load_lifecycle_state round-trips."""
        self.manager.save_lifecycle_state(
            task_id="task-006",
            current_phase="P8",
            phase_states={"P1": "completed", "P8": "running"},
            completed_phases=["P1", "P2", "P3"],
            mode="full",
        )
        loaded = self.manager.load_lifecycle_state("task-006")
        self.assertIsNotNone(loaded)
        assert loaded is not None
        self.assertEqual(loaded["current_phase"], "P8")
        self.assertEqual(loaded["mode"], "full")
        self.assertEqual(len(loaded["completed_phases"]), 3)

    def test_07_list_checkpoints_filtered_by_task(self) -> None:
        """Verify: list_checkpoints filters by task_id."""
        self.manager.create_checkpoint_from_dispatch(
            task_id="task-A", step_name="S1", agent_id="a",
            completed_steps=["x"], remaining_steps=["y"],
        )
        self.manager.create_checkpoint_from_dispatch(
            task_id="task-B", step_name="S1", agent_id="b",
            completed_steps=["x"], remaining_steps=["y"],
        )
        task_a_cps = self.manager.list_checkpoints(task_id="task-A")
        self.assertEqual(len(task_a_cps), 1)
        self.assertEqual(task_a_cps[0].task_id, "task-A")


# ---------------------------------------------------------------------------
# T3: WorkflowEngine — task splitting, lifecycle, start/execute, classify
# ---------------------------------------------------------------------------


class T3_WorkflowEngine(unittest.TestCase):
    """T3: WorkflowEngine creation, execution, and state management."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="devsquad_we_")
        self.engine = WorkflowEngine(storage_path=self._tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_01_create_workflow_from_task_splits_steps(self) -> None:
        """Verify: task with development+testing keywords produces multiple steps."""
        wf = self.engine.create_workflow_from_task(
            task_title="Implement user feature with tests",
            task_description="develop authentication and add test coverage",
        )
        # development + testing keywords → Test Design, Development, Test Execution.
        self.assertGreaterEqual(len(wf.steps), 2)
        step_names = [s.name for s in wf.steps]
        self.assertTrue(any("Development" in n for n in step_names))

    def test_02_create_workflow_unknown_task_single_step(self) -> None:
        """Verify: unrecognized task falls back to a single execution step."""
        wf = self.engine.create_workflow_from_task(
            task_title="hello world",
            task_description="random unrelated text",
        )
        self.assertEqual(len(wf.steps), 1)
        self.assertEqual(wf.steps[0].role_id, "solo-coder")

    def test_03_create_lifecycle_full_has_eleven_phases(self) -> None:
        """Verify: create_lifecycle('full') produces all 11 phases P1-P11."""
        wf = self.engine.create_lifecycle("full")
        self.assertEqual(len(wf.steps), 11)
        phase_ids = [s.step_id for s in wf.steps]
        self.assertEqual(phase_ids, LIFECYCLE_TEMPLATES["full"])

    def test_04_start_workflow_sets_running_status(self) -> None:
        """Verify: start_workflow creates a RUNNING instance pointing at step 0."""
        wf = self.engine.create_lifecycle("minimal")
        instance = self.engine.start_workflow(wf.workflow_id)
        self.assertIsNotNone(instance)
        assert instance is not None
        self.assertEqual(instance.status, WorkflowStatus.RUNNING)
        self.assertEqual(instance.current_step, wf.steps[0].step_id)

    def test_05_execute_step_with_custom_executor(self) -> None:
        """Verify: execute_step uses the provided executor and marks COMPLETED."""
        wf = self.engine.create_workflow_from_task("write a utility function")
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None

        def executor(step: WorkflowStep, _vars: dict[str, Any]) -> dict[str, Any]:
            return {"result": f"executed {step.action}"}

        step = self.engine.execute_step(instance.instance_id, step_executor=executor)
        self.assertIsNotNone(step)
        assert step is not None
        from scripts.collaboration.workflow_engine_base import StepStatus

        self.assertEqual(step.status, StepStatus.COMPLETED)
        self.assertIn(step.step_id, instance.completed_steps)

    def test_06_execute_all_steps_completes_workflow(self) -> None:
        """Verify: executing all steps transitions instance to COMPLETED."""
        wf = self.engine.create_workflow_from_task("write a utility function")
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None

        def executor(_step: WorkflowStep, _vars: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        # Execute until workflow completes.
        for _ in range(len(wf.steps)):
            self.engine.execute_step(instance.instance_id, step_executor=executor)

        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)
        self.assertEqual(len(instance.completed_steps), len(wf.steps))

    def test_07_classify_steps_by_node_type(self) -> None:
        """Verify: classify_steps reports deterministic/llm/hybrid counts."""
        wf = self.engine.create_lifecycle("full")
        stats = self.engine.classify_steps(wf.workflow_id)
        self.assertEqual(stats["total"], 11)
        # P9, P10, P11 are deterministic; P1,P2,P3,P5,P7 are llm; P4,P6,P8 are hybrid.
        self.assertGreater(stats["deterministic"], 0)
        self.assertGreater(stats["llm"], 0)
        self.assertGreater(stats["hybrid"], 0)
        self.assertEqual(stats["deterministic"] + stats["llm"] + stats["hybrid"], 11)


# ---------------------------------------------------------------------------
# T4: TaskCompletionChecker — dispatch result, completion tracking, summary
# ---------------------------------------------------------------------------


class T4_TaskCompletionChecker(unittest.TestCase):
    """T4: TaskCompletionChecker dispatch result checking."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="devsquad_tcc_")
        self.checker = TaskCompletionChecker(storage_path=self._tmp_dir)

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_01_check_dispatch_result_all_success(self) -> None:
        """Verify: all workers succeed → is_completed True, rate 100%."""
        dispatch = _make_dispatch_result(
            task_description="build feature",
            worker_results=[
                _make_worker_result("architect", success=True),
                _make_worker_result("solo-coder", success=True),
            ],
        )
        result = self.checker.check_dispatch_result(dispatch)
        self.assertTrue(result.is_completed)
        self.assertEqual(result.completion_rate, 100.0)
        self.assertEqual(result.completed_subtasks, 2)
        self.assertEqual(result.failed_subtasks, 0)

    def test_02_check_dispatch_result_partial_failure(self) -> None:
        """Verify: partial failure → is_completed False, failed counted."""
        dispatch = _make_dispatch_result(
            task_description="partial task",
            worker_results=[
                _make_worker_result("architect", success=True),
                _make_worker_result("solo-coder", success=False, error="timeout"),
            ],
        )
        result = self.checker.check_dispatch_result(dispatch)
        self.assertFalse(result.is_completed)
        self.assertEqual(result.completed_subtasks, 1)
        self.assertEqual(result.failed_subtasks, 1)
        self.assertIn("1/2", result.summary)

    def test_03_check_dispatch_result_empty_workers(self) -> None:
        """Verify: empty worker_results → not completed, rate 0%."""
        dispatch = _make_dispatch_result(task_description="empty task", worker_results=[])
        result = self.checker.check_dispatch_result(dispatch)
        self.assertFalse(result.is_completed)
        self.assertEqual(result.completion_rate, 0.0)
        self.assertEqual(result.total_subtasks, 0)

    def test_04_is_task_completed_tracks_history(self) -> None:
        """Verify: is_task_completed reads from persisted progress."""
        dispatch = _make_dispatch_result(
            task_description="tracked task",
            worker_results=[_make_worker_result("solo-coder", success=True)],
        )
        self.checker.check_dispatch_result(dispatch)
        task_id = "tracked task"  # task_id = task_description[:50]
        self.assertTrue(self.checker.is_task_completed(task_id))

    def test_05_get_completion_summary_markdown(self) -> None:
        """Verify: get_completion_summary produces Markdown with totals."""
        dispatch = _make_dispatch_result(
            task_description="summary task",
            worker_results=[_make_worker_result("solo-coder", success=True)],
        )
        self.checker.check_dispatch_result(dispatch)
        summary = self.checker.get_completion_summary()
        self.assertIn("Task Completion Summary", summary)
        self.assertIn("Total dispatches: 1", summary)


# ---------------------------------------------------------------------------
# T5: Integration — intent→workflow→checkpoint→resume→completion end-to-end
# ---------------------------------------------------------------------------


class T5_WorkflowIntegration(unittest.TestCase):
    """T5: End-to-end workflow pipeline integration."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="devsquad_int_")
        self.engine = WorkflowEngine(storage_path=self._tmp_dir)
        self.mapper = IntentWorkflowMapper()

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_01_intent_to_workflow_to_execution(self) -> None:
        """Verify: intent detected → workflow created → steps executed to completion."""
        task = "implement a new authentication module with tests"
        match = self.mapper.detect_intent(task, lang="en")
        self.assertIsNotNone(match)
        assert match is not None
        self.assertEqual(match.intent_type, "new_feature")

        wf = self.engine.create_workflow_from_task(task_title=task, task_description=task)
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None

        def executor(_step: WorkflowStep, _vars: dict[str, Any]) -> dict[str, Any]:
            return {"status": "done"}

        for _ in range(len(wf.steps)):
            self.engine.execute_step(instance.instance_id, step_executor=executor)

        self.assertEqual(instance.status, WorkflowStatus.COMPLETED)

    def test_02_workflow_checkpoint_save_and_resume(self) -> None:
        """Verify: executing steps creates a checkpoint; resume restores state."""
        wf = self.engine.create_lifecycle("minimal")
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None

        def executor(_step: WorkflowStep, _vars: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        # Execute 2 steps (checkpoint_interval=2 → checkpoint saved on 2nd step).
        self.engine.execute_step(instance.instance_id, step_executor=executor)
        self.engine.execute_step(instance.instance_id, step_executor=executor)

        self.assertGreaterEqual(len(instance.completed_steps), 2)
        # A checkpoint should have been saved.
        self.assertIsNotNone(instance.checkpoint_id)

        # Resume from checkpoint restores completed steps.
        resumed = self.engine.resume_from_checkpoint(instance.instance_id)
        self.assertIsNotNone(resumed)
        assert resumed is not None
        self.assertEqual(resumed.completed_steps, instance.completed_steps)

    def test_03_workflow_handoff_between_agents(self) -> None:
        """Verify: handoff creates a persisted document with remaining steps."""
        wf = self.engine.create_lifecycle("minimal")
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None

        def executor(_step: WorkflowStep, _vars: dict[str, Any]) -> dict[str, Any]:
            return {"done": True}

        self.engine.execute_step(instance.instance_id, step_executor=executor)

        handoff = self.engine.handoff(
            instance.instance_id,
            from_agent="product-manager",
            to_agent="architect",
            reason="phase_complete",
        )
        self.assertIsNotNone(handoff)
        assert handoff is not None
        self.assertEqual(handoff.from_agent, "product-manager")
        self.assertEqual(handoff.to_agent, "architect")
        self.assertIn(instance.instance_id, [h.task_id for h in self.engine.checkpoint_manager.get_task_handoffs(instance.instance_id)])

    def test_04_change_request_during_running_workflow(self) -> None:
        """Verify: submit_change_request returns affected (uncompleted) phases."""
        wf = self.engine.create_lifecycle("minimal")
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None

        def executor(_step: WorkflowStep, _vars: dict[str, Any]) -> dict[str, Any]:
            return {"ok": True}

        # Complete the first step.
        self.engine.execute_step(instance.instance_id, step_executor=executor)

        change = self.engine.submit_change_request(
            instance.instance_id,
            description="Change the data model",
            reason="New requirement from stakeholder",
            requested_by="product-manager",
        )
        self.assertIsNotNone(change)
        assert change is not None
        # Affected phases = uncompleted steps.
        self.assertGreater(len(change.affected_phases), 0)
        self.assertNotIn(wf.steps[0].step_id, change.affected_phases)


if __name__ == "__main__":
    unittest.main()
