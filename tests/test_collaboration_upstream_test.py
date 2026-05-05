#!/usr/bin/env python3
import pytest
import tempfile
import shutil
from pathlib import Path

from scripts.collaboration.checkpoint_manager import (
    CheckpointManager, Checkpoint, CheckpointStatus, HandoffDocument,
)
from scripts.collaboration.ai_semantic_matcher import AISemanticMatcher, SemanticMatchResult
from scripts.collaboration.task_completion_checker import TaskCompletionChecker, TaskCompletionResult
from scripts.collaboration.workflow_engine import (
    WorkflowEngine, WorkflowDefinition, WorkflowStep, WorkflowInstance,
    WorkflowStatus, StepStatus,
)


class TestCheckpointManager:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.manager = CheckpointManager(storage_path=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_save_and_load_checkpoint(self):
        cp = Checkpoint(
            task_id="task-1",
            step_name="Architecture Design",
            agent_id="architect",
            completed_steps=["step_1"],
            remaining_steps=["step_2", "step_3"],
            progress_percentage=0.33,
        )
        assert self.manager.save_checkpoint(cp) is True

        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        assert loaded is not None
        assert loaded.task_id == "task-1"
        assert loaded.step_name == "Architecture Design"
        assert loaded.progress_percentage == 0.33

    def test_checkpoint_integrity(self):
        cp = Checkpoint(task_id="task-2", step_name="Test", agent_id="tester")
        self.manager.save_checkpoint(cp)

        loaded = self.manager.load_checkpoint(cp.checkpoint_id)
        assert loaded is not None
        assert loaded.checkpoint_hash != ""

    def test_get_latest_checkpoint(self):
        cp1 = Checkpoint(task_id="task-3", step_name="Step 1", agent_id="arch")
        self.manager.save_checkpoint(cp1)
        cp2 = Checkpoint(task_id="task-3", step_name="Step 2", agent_id="coder")
        self.manager.save_checkpoint(cp2)

        latest = self.manager.get_latest_checkpoint("task-3")
        assert latest is not None
        assert latest.step_name == "Step 2"

    def test_list_checkpoints(self):
        self.manager.save_checkpoint(Checkpoint(task_id="t1", step_name="S1", agent_id="a"))
        self.manager.save_checkpoint(Checkpoint(task_id="t2", step_name="S2", agent_id="b"))

        all_cps = self.manager.list_checkpoints()
        assert len(all_cps) == 2

        t1_cps = self.manager.list_checkpoints(task_id="t1")
        assert len(t1_cps) == 1

    def test_delete_checkpoint(self):
        cp = Checkpoint(task_id="task-del", step_name="Delete", agent_id="a")
        self.manager.save_checkpoint(cp)
        assert self.manager.delete_checkpoint(cp.checkpoint_id) is True
        assert self.manager.load_checkpoint(cp.checkpoint_id) is None

    def test_save_and_load_handoff(self):
        handoff = HandoffDocument(
            task_id="task-h1",
            from_agent="architect",
            to_agent="solo-coder",
            completed_work=["Architecture designed"],
            next_steps=["Implement code"],
            handoff_reason="architecture_complete",
        )
        assert self.manager.save_handoff(handoff) is True

        loaded = self.manager.load_handoff(handoff.handoff_id)
        assert loaded is not None
        assert loaded.from_agent == "architect"
        assert loaded.to_agent == "solo-coder"

    def test_handoff_markdown(self):
        handoff = HandoffDocument(
            task_id="task-md",
            from_agent="arch",
            to_agent="coder",
            completed_work=["Step 1 done"],
            next_steps=["Step 2"],
        )
        md = handoff.to_markdown()
        assert "arch" in md
        assert "coder" in md
        assert "Step 1 done" in md

    def test_create_checkpoint_from_dispatch(self):
        cp = self.manager.create_checkpoint_from_dispatch(
            task_id="dispatch-1",
            step_name="Analysis",
            agent_id="architect",
            completed_steps=["step_1", "step_2"],
            remaining_steps=["step_3"],
            context={"key": "value"},
        )
        assert cp.progress_percentage == 2/3
        assert cp.task_id == "dispatch-1"

    def test_cleanup_expired_checkpoints(self):
        cp = Checkpoint(task_id="old", step_name="Old", agent_id="a")
        self.manager.save_checkpoint(cp)
        cleaned = self.manager.cleanup_expired_checkpoints(max_age_hours=0)
        assert cleaned >= 0


class TestAISemanticMatcher:
    def setup_method(self):
        self.matcher = AISemanticMatcher(llm_backend=None)

    def test_keyword_match_architecture(self):
        results = self.matcher.match("Design a microservices architecture for e-commerce")
        assert len(results) > 0
        assert results[0].role_id == "architect"
        assert results[0].confidence > 0

    def test_keyword_match_security(self):
        results = self.matcher.match("Review authentication and security vulnerabilities")
        assert len(results) > 0
        top_roles = [r.role_id for r in results[:3]]
        assert "security" in top_roles

    def test_keyword_match_testing(self):
        results = self.matcher.match("Write test cases for the API endpoints")
        assert len(results) > 0
        top_roles = [r.role_id for r in results[:3]]
        assert "tester" in top_roles

    def test_keyword_match_default(self):
        results = self.matcher.match("Random task with no specific keywords")
        assert len(results) > 0
        assert results[0].role_id == "solo-coder"

    def test_match_cache(self):
        results1 = self.matcher.match("Design system architecture", use_cache=True)
        results2 = self.matcher.match("Design system architecture", use_cache=True)
        assert len(results1) > 0
        assert len(results2) > 0

    def test_match_history(self):
        self.matcher.match("Task 1")
        self.matcher.match("Task 2")
        history = self.matcher.get_match_history()
        assert len(history) == 2

    def test_clear_cache(self):
        self.matcher.match("Cache test", use_cache=True)
        self.matcher.clear_cache()
        assert len(self.matcher.match_cache) == 0

    def test_explain_match(self):
        results = self.matcher.match("Design architecture")
        explanation = self.matcher.explain_match(results[0])
        assert results[0].role_name in explanation
        assert "Confidence" in explanation

    def test_semantic_match_result_dataclass(self):
        result = SemanticMatchResult(
            role_id="architect",
            role_name="Architect",
            confidence=0.9,
            reasoning="Strong match",
            matched_capabilities=["system design"],
            relevance_score=0.85,
            explanation="Task requires architecture skills",
        )
        assert result.role_id == "architect"
        assert result.confidence == 0.9


class TestTaskCompletionChecker:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.checker = TaskCompletionChecker(storage_path=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_check_dispatch_result_all_success(self):
        class MockResult:
            task_description = "Design auth system"
            worker_results = [
                {"role_id": "architect", "role_name": "Architect", "success": True, "error": None, "output": "ok"},
                {"role_id": "security", "role_name": "Security", "success": True, "error": None, "output": "ok"},
            ]

        result = self.checker.check_dispatch_result(MockResult())
        assert result.is_completed is True
        assert result.completion_rate == 100.0
        assert result.completed_subtasks == 2

    def test_check_dispatch_result_partial(self):
        class MockResult:
            task_description = "Build feature"
            worker_results = [
                {"role_id": "architect", "success": True, "error": None, "output": "ok"},
                {"role_id": "tester", "success": False, "error": "timeout", "output": None},
            ]

        result = self.checker.check_dispatch_result(MockResult())
        assert result.is_completed is False
        assert result.completion_rate == 50.0
        assert result.failed_subtasks == 1

    def test_check_dispatch_result_empty(self):
        class MockResult:
            task_description = "Empty task"
            worker_results = []

        result = self.checker.check_dispatch_result(MockResult())
        assert result.is_completed is False
        assert result.completion_rate == 0.0

    def test_dispatch_history(self):
        class MockResult:
            task_description = "History test"
            worker_results = [{"role_id": "arch", "success": True, "error": None, "output": "ok"}]

        self.checker.check_dispatch_result(MockResult())
        history = self.checker.get_dispatch_history()
        assert len(history) > 0

    def test_completion_summary(self):
        class MockResult:
            task_description = "Summary test"
            worker_results = [{"role_id": "arch", "success": True, "error": None, "output": "ok"}]

        self.checker.check_dispatch_result(MockResult())
        summary = self.checker.get_completion_summary()
        assert "Summary" in summary or "dispatch" in summary.lower()

    def test_is_task_completed(self):
        class MockResult:
            task_description = "Completion check"
            worker_results = [{"role_id": "arch", "success": True, "error": None, "output": "ok"}]

        self.checker.check_dispatch_result(MockResult())
        task_id = "Completion check"
        assert self.checker.is_task_completed(task_id) is True

    def test_reset_progress(self):
        self.checker.reset_progress()
        assert len(self.checker.get_dispatch_history()) == 0


class TestWorkflowEngine:
    def setup_method(self):
        self.tmpdir = tempfile.mkdtemp()
        self.engine = WorkflowEngine(storage_path=self.tmpdir)

    def teardown_method(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_create_workflow_from_task(self):
        wf = self.engine.create_workflow_from_task(
            "Design and implement auth system",
            "Need secure authentication with JWT tokens",
        )
        assert wf.workflow_id.startswith("wf-")
        assert len(wf.steps) > 0

    def test_create_workflow_architecture(self):
        wf = self.engine.create_workflow_from_task(
            "Design microservices architecture",
        )
        role_ids = [s.role_id for s in wf.steps]
        assert "architect" in role_ids

    def test_create_workflow_security(self):
        wf = self.engine.create_workflow_from_task(
            "Security review of authentication",
        )
        role_ids = [s.role_id for s in wf.steps]
        assert "security" in role_ids

    def test_start_workflow(self):
        wf = self.engine.create_workflow_from_task("Build feature X")
        instance = self.engine.start_workflow(wf.workflow_id)
        assert instance is not None
        assert instance.status == WorkflowStatus.RUNNING
        assert instance.current_step is not None

    def test_execute_step(self):
        wf = self.engine.create_workflow_from_task("Build feature Y")
        instance = self.engine.start_workflow(wf.workflow_id)

        step = self.engine.execute_step(instance.instance_id)
        assert step is not None
        assert step.status == StepStatus.COMPLETED

    def test_execute_step_with_executor(self):
        wf = self.engine.create_workflow_from_task("Build feature Z")
        instance = self.engine.start_workflow(wf.workflow_id)

        def custom_executor(step, variables):
            return {"custom": True, "action": step.action}

        step = self.engine.execute_step(instance.instance_id, step_executor=custom_executor)
        assert step is not None
        assert step.result["custom"] is True

    def test_register_executor(self):
        self.engine.register_executor("test_action", lambda s, v: {"registered": True})
        assert "test_action" in self.engine.executors

    def test_workflow_status(self):
        wf = self.engine.create_workflow_from_task("Status test task")
        instance = self.engine.start_workflow(wf.workflow_id)

        status = self.engine.get_workflow_status(instance.instance_id)
        assert status is not None
        assert status['status'] == 'running'

    def test_handoff(self):
        wf = self.engine.create_workflow_from_task("Handoff test")
        instance = self.engine.start_workflow(wf.workflow_id)
        self.engine.execute_step(instance.instance_id)

        handoff = self.engine.handoff(
            instance.instance_id,
            from_agent="architect",
            to_agent="solo-coder",
            reason="Design complete",
        )
        assert handoff is not None
        assert handoff.from_agent == "architect"
        assert handoff.to_agent == "solo-coder"

    def test_default_step_executor_with_dispatcher(self):
        class MockDispatcher:
            def dispatch(self, task_description, roles=None):
                class R:
                    success = True
                    summary = "Mock dispatch result"
                return R()

        engine = WorkflowEngine(storage_path=self.tmpdir, dispatcher=MockDispatcher())
        wf = engine.create_workflow_from_task("Test dispatch integration")
        instance = engine.start_workflow(wf.workflow_id)
        step = engine.execute_step(instance.instance_id)
        assert step is not None
        assert step.result["dispatch_success"] is True
