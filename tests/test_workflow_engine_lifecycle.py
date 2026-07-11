#!/usr/bin/env python3
"""Unit tests for workflow_engine_lifecycle_mixin.py.

Covers create_workflow_from_task, _split_task_into_steps (all keyword
combinations), create_lifecycle (5 templates + invalid), and
submit_change_request (instance not found, wrong status, sanitization).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.collaboration.checkpoint_manager import CheckpointManager
from scripts.collaboration.workflow_engine_base import (
    LIFECYCLE_TEMPLATES,
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


class _Engine(
    WorkflowEngineLifecycleMixin,
    WorkflowEngineTransitionMixin,
    WorkflowEnginePersistenceMixin,
    WorkflowEngineStateMixin,
):
    """Minimal concrete engine for lifecycle mixin tests."""

    def __init__(self, storage_path: str) -> None:
        self.storage_path = Path(storage_path)
        self.definitions: dict[str, WorkflowDefinition] = {}
        self.instances: dict[str, WorkflowInstance] = {}
        self.executors: dict[str, object] = {}
        self.checkpoint_manager = CheckpointManager(storage_path=storage_path)
        self.checkpoint_interval = 2
        self.coordinator = None
        self.dispatcher = None


def _make_step(step_id: str, name: str = "", role_id: str = "agent-1") -> WorkflowStep:
    return WorkflowStep(step_id=step_id, name=name or step_id, role_id=role_id)


class TestCreateWorkflowFromTask(unittest.TestCase):
    """create_workflow_from_task() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)

    def test_creates_definition_with_metadata(self) -> None:
        defn = self.engine.create_workflow_from_task("Test Task", "Description")
        self.assertIsInstance(defn, WorkflowDefinition)
        self.assertEqual(defn.name, "Test Task")
        self.assertEqual(defn.description, "Description")
        self.assertEqual(defn.metadata["created_by"], "WorkflowEngine")

    def test_registers_in_definitions(self) -> None:
        defn = self.engine.create_workflow_from_task("Test Task")
        self.assertIn(defn.workflow_id, self.engine.definitions)

    def test_empty_description(self) -> None:
        defn = self.engine.create_workflow_from_task("Test Task")
        self.assertEqual(defn.description, "")

    def test_with_target_agent(self) -> None:
        defn = self.engine.create_workflow_from_task("Test Task", target_agent="architect")
        self.assertEqual(defn.metadata["target_agent"], "architect")

    def test_target_agent_none(self) -> None:
        defn = self.engine.create_workflow_from_task("Test Task")
        self.assertIsNone(defn.metadata["target_agent"])


class TestSplitTaskIntoSteps(unittest.TestCase):
    """_split_task_into_steps() keyword detection tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)

    def _get_step_names(self, title: str, description: str = "") -> list[str]:
        steps = self.engine._split_task_into_steps(title, description)
        return [s.name for s in steps]

    def test_product_keywords(self) -> None:
        names = self._get_step_names("requirement analysis for user product")
        self.assertIn("Requirements Analysis", names)

    def test_architecture_keywords(self) -> None:
        names = self._get_step_names("design system architecture")
        self.assertIn("Architecture Design", names)

    def test_security_keywords(self) -> None:
        names = self._get_step_names("security review and auth")
        self.assertIn("Security Review", names)

    def test_ui_keywords(self) -> None:
        names = self._get_step_names("design UI interface for frontend")
        self.assertIn("UI Design", names)

    def test_testing_keywords(self) -> None:
        names = self._get_step_names("test and verify quality")
        self.assertIn("Test Design", names)

    def test_development_keywords(self) -> None:
        names = self._get_step_names("develop and implement code")
        self.assertIn("Development", names)

    def test_testing_and_development_adds_test_execution(self) -> None:
        names = self._get_step_names("develop code and test it")
        self.assertIn("Development", names)
        self.assertIn("Test Design", names)
        self.assertIn("Test Execution", names)

    def test_deployment_keywords(self) -> None:
        names = self._get_step_names("deploy and release to production")
        self.assertIn("Deployment", names)

    def test_chinese_keywords(self) -> None:
        names = self._get_step_names("需求分析 架构设计 开发实现 测试验证 部署发布")
        self.assertIn("Requirements Analysis", names)
        self.assertIn("Architecture Design", names)
        self.assertIn("Development", names)
        self.assertIn("Test Design", names)
        self.assertIn("Deployment", names)

    def test_chinese_security_keyword(self) -> None:
        names = self._get_step_names("安全认证审查")
        self.assertIn("Security Review", names)

    def test_chinese_ui_keyword(self) -> None:
        names = self._get_step_names("界面交互设计")
        self.assertIn("UI Design", names)

    def test_no_keywords_fallback(self) -> None:
        names = self._get_step_names("random task with no keywords")
        self.assertEqual(len(names), 1)
        self.assertEqual(names[0], "Task Execution")

    def test_no_keywords_fallback_uses_target_agent(self) -> None:
        steps = self.engine._split_task_into_steps("random task", "", target_agent="custom-agent")
        self.assertEqual(steps[0].role_id, "custom-agent")

    def test_no_keywords_fallback_default_agent(self) -> None:
        steps = self.engine._split_task_into_steps("random task", "")
        self.assertEqual(steps[0].role_id, "solo-coder")

    def test_step_ids_sequential(self) -> None:
        steps = self.engine._split_task_into_steps("design architecture develop code test", "")
        ids = [s.step_id for s in steps]
        self.assertEqual(ids, ["step_1", "step_2", "step_3", "step_4", "step_5"])

    def test_full_workflow_all_steps(self) -> None:
        names = self._get_step_names("requirement architecture security ui testing development deploy")
        expected = [
            "Requirements Analysis",
            "Architecture Design",
            "Security Review",
            "UI Design",
            "Test Design",
            "Development",
            "Test Execution",
            "Deployment",
        ]
        self.assertEqual(names, expected)

    def test_description_contributes_keywords(self) -> None:
        names = self._get_step_names("Task", "develop the code")
        self.assertIn("Development", names)


class TestCreateLifecycle(unittest.TestCase):
    """create_lifecycle() template tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)

    def test_full_template(self) -> None:
        defn = self.engine.create_lifecycle("full")
        self.assertEqual(len(defn.steps), 11)
        step_ids = [s.step_id for s in defn.steps]
        self.assertEqual(step_ids, ["P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10", "P11"])

    def test_backend_template(self) -> None:
        defn = self.engine.create_lifecycle("backend")
        self.assertEqual(len(defn.steps), 10)
        self.assertNotIn("P5", [s.step_id for s in defn.steps])

    def test_frontend_template(self) -> None:
        defn = self.engine.create_lifecycle("frontend")
        self.assertEqual(len(defn.steps), 9)
        self.assertNotIn("P4", [s.step_id for s in defn.steps])

    def test_internal_tool_template(self) -> None:
        defn = self.engine.create_lifecycle("internal_tool")
        self.assertEqual(len(defn.steps), 7)
        for pid in ["P4", "P5", "P6"]:
            self.assertNotIn(pid, [s.step_id for s in defn.steps])

    def test_minimal_template(self) -> None:
        defn = self.engine.create_lifecycle("minimal")
        self.assertEqual(len(defn.steps), 5)
        step_ids = [s.step_id for s in defn.steps]
        self.assertEqual(step_ids, ["P1", "P3", "P7", "P8", "P9"])

    def test_invalid_template_raises_value_error(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            self.engine.create_lifecycle("nonexistent")
        self.assertIn("Unknown template", str(ctx.exception))
        self.assertIn("nonexistent", str(ctx.exception))

    def test_default_template_is_full(self) -> None:
        defn = self.engine.create_lifecycle()
        self.assertEqual(len(defn.steps), 11)

    def test_node_type_propagation(self) -> None:
        defn = self.engine.create_lifecycle("full")
        p9 = next(s for s in defn.steps if s.step_id == "P9")
        self.assertEqual(p9.node_type, NodeType.DETERMINISTIC)

        p1 = next(s for s in defn.steps if s.step_id == "P1")
        self.assertEqual(p1.node_type, NodeType.LLM)

        p4 = next(s for s in defn.steps if s.step_id == "P4")
        self.assertEqual(p4.node_type, NodeType.HYBRID)

    def test_definition_registered(self) -> None:
        defn = self.engine.create_lifecycle("minimal")
        self.assertIn(defn.workflow_id, self.engine.definitions)

    def test_definition_metadata(self) -> None:
        defn = self.engine.create_lifecycle("full")
        self.assertEqual(defn.metadata["template"], "full")
        self.assertEqual(defn.metadata["lifecycle_version"], "3.8.0")

    def test_step_fields_from_template(self) -> None:
        defn = self.engine.create_lifecycle("full")
        p1 = next(s for s in defn.steps if s.step_id == "P1")
        self.assertEqual(p1.name, "Requirements Analysis")
        self.assertEqual(p1.role_id, "product-manager")
        self.assertEqual(p1.action, "analyze_requirements")
        self.assertEqual(p1.dependencies, [])
        self.assertFalse(p1.optional)

    def test_all_templates_match_lifecycle_templates_constant(self) -> None:
        for template_name in LIFECYCLE_TEMPLATES:
            defn = self.engine.create_lifecycle(template_name)
            expected_count = len(LIFECYCLE_TEMPLATES[template_name])
            self.assertEqual(len(defn.steps), expected_count, f"Template {template_name} step count mismatch")


class TestSubmitChangeRequest(unittest.TestCase):
    """submit_change_request() tests."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.engine = _Engine(self.tmpdir)
        self.steps = [_make_step("s1", "Step One"), _make_step("s2", "Step Two"), _make_step("s3", "Step Three")]
        self.defn = WorkflowDefinition(workflow_id="wf-test", name="Test", steps=self.steps)
        self.engine.definitions[self.defn.workflow_id] = self.defn

    def _make_instance(
        self,
        status: WorkflowStatus = WorkflowStatus.RUNNING,
        completed_steps: list[str] | None = None,
    ) -> WorkflowInstance:
        inst = WorkflowInstance(
            instance_id="inst-1",
            workflow_id=self.defn.workflow_id,
            status=status,
            completed_steps=completed_steps or [],
        )
        self.engine.instances[inst.instance_id] = inst
        return inst

    def test_instance_not_found_returns_none(self) -> None:
        result = self.engine.submit_change_request("nonexistent", "desc", "reason")
        self.assertIsNone(result)

    def test_wrong_status_completed_returns_none(self) -> None:
        self._make_instance(status=WorkflowStatus.COMPLETED)
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        self.assertIsNone(result)

    def test_wrong_status_failed_returns_none(self) -> None:
        self._make_instance(status=WorkflowStatus.FAILED)
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        self.assertIsNone(result)

    def test_wrong_status_pending_returns_none(self) -> None:
        self._make_instance(status=WorkflowStatus.PENDING)
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        self.assertIsNone(result)

    def test_wrong_status_waiting_handover_returns_none(self) -> None:
        self._make_instance(status=WorkflowStatus.WAITING_HANDOVER)
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        self.assertIsNone(result)

    def test_running_status_allows(self) -> None:
        self._make_instance(status=WorkflowStatus.RUNNING)
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        self.assertIsNotNone(result)

    def test_paused_status_allows(self) -> None:
        self._make_instance(status=WorkflowStatus.PAUSED)
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        self.assertIsNotNone(result)

    def test_no_definition_returns_none(self) -> None:
        inst = WorkflowInstance(instance_id="inst-no-def", workflow_id="nonexistent", status=WorkflowStatus.RUNNING)
        self.engine.instances[inst.instance_id] = inst
        result = self.engine.submit_change_request("inst-no-def", "desc", "reason")
        self.assertIsNone(result)

    def test_affected_phases_excludes_completed(self) -> None:
        self._make_instance(completed_steps=["s1"])
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        assert result is not None
        self.assertEqual(result.affected_phases, ["s2", "s3"])

    def test_affected_phases_all_when_none_completed(self) -> None:
        self._make_instance(completed_steps=[])
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        assert result is not None
        self.assertEqual(result.affected_phases, ["s1", "s2", "s3"])

    def test_rollback_to_is_earliest_uncompleted(self) -> None:
        self._make_instance(completed_steps=["s1"])
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        assert result is not None
        self.assertEqual(result.rollback_to, "s2")

    def test_rollback_to_empty_when_all_completed(self) -> None:
        self._make_instance(completed_steps=["s1", "s2", "s3"])
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        assert result is not None
        self.assertEqual(result.rollback_to, "")

    def test_description_sanitized_truncated(self) -> None:
        self._make_instance()
        long_desc = "x" * 600
        result = self.engine.submit_change_request("inst-1", long_desc, "reason")
        assert result is not None
        self.assertEqual(len(result.description), 500)

    def test_reason_sanitized_truncated(self) -> None:
        self._make_instance()
        long_reason = "y" * 600
        result = self.engine.submit_change_request("inst-1", "desc", long_reason)
        assert result is not None
        self.assertEqual(len(result.reason), 500)

    def test_requested_by_sanitized_truncated(self) -> None:
        self._make_instance()
        long_by = "z" * 200
        result = self.engine.submit_change_request("inst-1", "desc", "reason", requested_by=long_by)
        assert result is not None
        self.assertEqual(len(result.requested_by), 100)

    def test_default_requested_by(self) -> None:
        self._make_instance()
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        assert result is not None
        self.assertEqual(result.requested_by, "user")

    def test_change_id_generated(self) -> None:
        self._make_instance()
        result = self.engine.submit_change_request("inst-1", "desc", "reason")
        assert result is not None
        self.assertTrue(result.change_id.startswith("cr-"))


if __name__ == "__main__":
    unittest.main()
