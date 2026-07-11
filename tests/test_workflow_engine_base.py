#!/usr/bin/env python3
"""Unit tests for workflow_engine_base.py.

Covers enums, dataclass serialization/deserialization, lifecycle template
constants integrity, and WorkflowEngineBase structural stubs.
"""

from __future__ import annotations

import unittest

from scripts.collaboration.workflow_engine_base import (
    LIFECYCLE_TEMPLATES,
    PHASE_TEMPLATES,
    NodeType,
    RequirementChange,
    StepStatus,
    WorkflowDefinition,
    WorkflowEngineBase,
    WorkflowInstance,
    WorkflowStatus,
    WorkflowStep,
)


class TestWorkflowStatusEnum(unittest.TestCase):
    """WorkflowStatus enum values."""

    def test_all_statuses_exist(self) -> None:
        expected = {"pending", "running", "completed", "failed", "paused", "waiting_handover"}
        actual = {s.value for s in WorkflowStatus}
        self.assertEqual(actual, expected)

    def test_status_count(self) -> None:
        self.assertEqual(len(list(WorkflowStatus)), 6)


class TestStepStatusEnum(unittest.TestCase):
    """StepStatus enum values."""

    def test_all_statuses_exist(self) -> None:
        expected = {"pending", "running", "completed", "failed", "skipped"}
        actual = {s.value for s in StepStatus}
        self.assertEqual(actual, expected)

    def test_status_count(self) -> None:
        self.assertEqual(len(list(StepStatus)), 5)


class TestNodeTypeEnum(unittest.TestCase):
    """NodeType enum values."""

    def test_all_types_exist(self) -> None:
        expected = {"deterministic", "llm", "hybrid"}
        actual = {t.value for t in NodeType}
        self.assertEqual(actual, expected)

    def test_type_count(self) -> None:
        self.assertEqual(len(list(NodeType)), 3)


class TestWorkflowStepSerialization(unittest.TestCase):
    """WorkflowStep to_dict / from_dict round-trip and edge cases."""

    def test_to_dict_round_trip(self) -> None:
        step = WorkflowStep(
            step_id="s1",
            name="Design",
            description="Design phase",
            role_id="architect",
            action="design",
            inputs={"k": "v"},
            outputs={"r": "result"},
            conditions={"c": True},
            timeout=1800,
            retry_count=5,
            status=StepStatus.COMPLETED,
            result="done",
            error="",
            dependencies=["s0"],
            artifacts_in="req",
            artifacts_out="spec",
            gate_condition="passed",
            reviewers=["tester"],
            optional=False,
            skip_reason="",
            node_type=NodeType.LLM,
        )
        d = step.to_dict()
        restored = WorkflowStep.from_dict(d)
        self.assertEqual(restored.step_id, "s1")
        self.assertEqual(restored.name, "Design")
        self.assertEqual(restored.description, "Design phase")
        self.assertEqual(restored.role_id, "architect")
        self.assertEqual(restored.action, "design")
        self.assertEqual(restored.inputs, {"k": "v"})
        self.assertEqual(restored.outputs, {"r": "result"})
        self.assertEqual(restored.conditions, {"c": True})
        self.assertEqual(restored.timeout, 1800)
        self.assertEqual(restored.retry_count, 5)
        self.assertEqual(restored.status, StepStatus.COMPLETED)
        self.assertEqual(restored.result, "done")
        self.assertEqual(restored.error, "")
        self.assertEqual(restored.dependencies, ["s0"])
        self.assertEqual(restored.artifacts_in, "req")
        self.assertEqual(restored.artifacts_out, "spec")
        self.assertEqual(restored.gate_condition, "passed")
        self.assertEqual(restored.reviewers, ["tester"])
        self.assertEqual(restored.optional, False)
        self.assertEqual(restored.skip_reason, "")
        self.assertEqual(restored.node_type, NodeType.LLM)

    def test_to_dict_status_enum_to_string(self) -> None:
        step = WorkflowStep(step_id="s1", status=StepStatus.RUNNING)
        d = step.to_dict()
        self.assertEqual(d["status"], "running")

    def test_to_dict_node_type_enum_to_string(self) -> None:
        step = WorkflowStep(step_id="s1", node_type=NodeType.DETERMINISTIC)
        d = step.to_dict()
        self.assertEqual(d["node_type"], "deterministic")

    def test_to_dict_status_already_string(self) -> None:
        step = WorkflowStep(step_id="s1")
        step.status = "custom_status"  # type: ignore[assignment]
        d = step.to_dict()
        self.assertEqual(d["status"], "custom_status")

    def test_to_dict_node_type_already_string(self) -> None:
        step = WorkflowStep(step_id="s1")
        step.node_type = "custom_type"  # type: ignore[assignment]
        d = step.to_dict()
        self.assertEqual(d["node_type"], "custom_type")

    def test_from_dict_invalid_status_falls_back_to_pending(self) -> None:
        d = {"step_id": "s1", "status": "invalid_status"}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.status, StepStatus.PENDING)

    def test_from_dict_invalid_node_type_falls_back_to_hybrid(self) -> None:
        d = {"step_id": "s1", "node_type": "invalid_type"}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.node_type, NodeType.HYBRID)

    def test_from_dict_missing_node_type_defaults_hybrid(self) -> None:
        d = {"step_id": "s1"}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.node_type, NodeType.HYBRID)

    def test_from_dict_status_already_enum(self) -> None:
        d = {"step_id": "s1", "status": StepStatus.COMPLETED}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.status, StepStatus.COMPLETED)

    def test_from_dict_node_type_already_enum(self) -> None:
        d = {"step_id": "s1", "node_type": NodeType.LLM}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.node_type, NodeType.LLM)

    def test_from_dict_empty_dict_uses_defaults(self) -> None:
        step = WorkflowStep.from_dict({})
        self.assertEqual(step.status, StepStatus.PENDING)
        self.assertEqual(step.node_type, NodeType.HYBRID)
        self.assertEqual(step.timeout, 3600)
        self.assertEqual(step.retry_count, 3)


class TestWorkflowStepProperties(unittest.TestCase):
    """WorkflowStep node_type helper methods and properties."""

    def test_is_deterministic(self) -> None:
        step = WorkflowStep(node_type=NodeType.DETERMINISTIC)
        self.assertTrue(step.is_deterministic())

    def test_is_deterministic_false_for_llm(self) -> None:
        step = WorkflowStep(node_type=NodeType.LLM)
        self.assertFalse(step.is_deterministic())

    def test_is_llm(self) -> None:
        step = WorkflowStep(node_type=NodeType.LLM)
        self.assertTrue(step.is_llm())

    def test_is_llm_false_for_deterministic(self) -> None:
        step = WorkflowStep(node_type=NodeType.DETERMINISTIC)
        self.assertFalse(step.is_llm())

    def test_requires_llm_llm(self) -> None:
        step = WorkflowStep(node_type=NodeType.LLM)
        self.assertTrue(step.requires_llm)

    def test_requires_llm_hybrid(self) -> None:
        step = WorkflowStep(node_type=NodeType.HYBRID)
        self.assertTrue(step.requires_llm)

    def test_requires_llm_deterministic(self) -> None:
        step = WorkflowStep(node_type=NodeType.DETERMINISTIC)
        self.assertFalse(step.requires_llm)

    def test_default_node_type_is_hybrid(self) -> None:
        step = WorkflowStep()
        self.assertEqual(step.node_type, NodeType.HYBRID)

    def test_default_step_id_has_prefix(self) -> None:
        step = WorkflowStep()
        self.assertTrue(step.step_id.startswith("step-"))


class TestWorkflowDefinition(unittest.TestCase):
    """WorkflowDefinition serialization and defaults."""

    def test_to_dict_serializes_steps(self) -> None:
        steps = [WorkflowStep(step_id="s1", name="A"), WorkflowStep(step_id="s2", name="B")]
        defn = WorkflowDefinition(workflow_id="wf-1", name="Test", steps=steps)
        d = defn.to_dict()
        self.assertEqual(d["workflow_id"], "wf-1")
        self.assertEqual(d["name"], "Test")
        self.assertEqual(len(d["steps"]), 2)
        self.assertEqual(d["steps"][0]["step_id"], "s1")
        self.assertEqual(d["steps"][1]["step_id"], "s2")

    def test_to_dict_includes_metadata(self) -> None:
        defn = WorkflowDefinition(
            workflow_id="wf-1",
            name="Test",
            description="desc",
            variables={"v": 1},
            metadata={"template": "full"},
        )
        d = defn.to_dict()
        self.assertEqual(d["description"], "desc")
        self.assertEqual(d["variables"], {"v": 1})
        self.assertEqual(d["metadata"], {"template": "full"})
        self.assertIn("created_at", d)

    def test_default_workflow_id_format(self) -> None:
        defn = WorkflowDefinition()
        self.assertTrue(defn.workflow_id.startswith("wf-"))
        self.assertEqual(len(defn.workflow_id), 11)  # wf- + 8 hex chars

    def test_default_created_at_is_iso_string(self) -> None:
        defn = WorkflowDefinition()
        self.assertIsInstance(defn.created_at, str)
        self.assertGreater(len(defn.created_at), 10)


class TestWorkflowInstance(unittest.TestCase):
    """WorkflowInstance default values."""

    def test_default_values(self) -> None:
        inst = WorkflowInstance()
        self.assertTrue(inst.instance_id.startswith("inst-"))
        self.assertEqual(inst.workflow_id, "")
        self.assertEqual(inst.status, WorkflowStatus.PENDING)
        self.assertIsNone(inst.current_step)
        self.assertEqual(inst.completed_steps, [])
        self.assertEqual(inst.failed_steps, [])
        self.assertEqual(inst.variables, {})
        self.assertEqual(inst.results, {})
        self.assertIsNone(inst.started_at)
        self.assertIsNone(inst.completed_at)
        self.assertEqual(inst.error, "")
        self.assertIsNone(inst.checkpoint_id)
        self.assertIsNone(inst.current_agent_id)
        self.assertEqual(inst.handoff_history, [])

    def test_custom_values(self) -> None:
        inst = WorkflowInstance(
            instance_id="inst-custom",
            workflow_id="wf-1",
            status=WorkflowStatus.RUNNING,
            current_step="s2",
            completed_steps=["s1"],
            failed_steps=["s0"],
            variables={"k": "v"},
            results={"s1": "done"},
            started_at="2026-01-01T00:00:00",
            error="",
            checkpoint_id="cp-1",
            current_agent_id="agent-1",
            handoff_history=["h1"],
        )
        self.assertEqual(inst.instance_id, "inst-custom")
        self.assertEqual(inst.workflow_id, "wf-1")
        self.assertEqual(inst.status, WorkflowStatus.RUNNING)
        self.assertEqual(inst.current_step, "s2")
        self.assertEqual(inst.completed_steps, ["s1"])
        self.assertEqual(inst.failed_steps, ["s0"])
        self.assertEqual(inst.variables, {"k": "v"})
        self.assertEqual(inst.results, {"s1": "done"})
        self.assertEqual(inst.started_at, "2026-01-01T00:00:00")
        self.assertEqual(inst.checkpoint_id, "cp-1")
        self.assertEqual(inst.current_agent_id, "agent-1")
        self.assertEqual(inst.handoff_history, ["h1"])


class TestRequirementChange(unittest.TestCase):
    """RequirementChange default values."""

    def test_default_values(self) -> None:
        rc = RequirementChange()
        self.assertTrue(rc.change_id.startswith("cr-"))
        self.assertEqual(rc.description, "")
        self.assertEqual(rc.reason, "")
        self.assertEqual(rc.requested_by, "")
        self.assertEqual(rc.impact_analysis, {})
        self.assertEqual(rc.affected_phases, [])
        self.assertEqual(rc.review_result, "pending")
        self.assertEqual(rc.rollback_to, "")

    def test_custom_values(self) -> None:
        rc = RequirementChange(
            description="Add feature",
            reason="Customer request",
            requested_by="pm",
            impact_analysis={"cost": "high"},
            affected_phases=["P3", "P8"],
            review_result="approved",
            rollback_to="P2",
        )
        self.assertEqual(rc.description, "Add feature")
        self.assertEqual(rc.reason, "Customer request")
        self.assertEqual(rc.requested_by, "pm")
        self.assertEqual(rc.impact_analysis, {"cost": "high"})
        self.assertEqual(rc.affected_phases, ["P3", "P8"])
        self.assertEqual(rc.review_result, "approved")
        self.assertEqual(rc.rollback_to, "P2")


class TestPhaseTemplates(unittest.TestCase):
    """PHASE_TEMPLATES constant integrity."""

    REQUIRED_KEYS = {
        "name",
        "description",
        "role_id",
        "action",
        "dependencies",
        "artifacts_in",
        "artifacts_out",
        "gate_condition",
        "reviewers",
        "optional",
        "node_type",
    }

    def test_all_phases_have_required_keys(self) -> None:
        for phase_id, template in PHASE_TEMPLATES.items():
            missing = self.REQUIRED_KEYS - set(template.keys())
            self.assertEqual(missing, set(), f"Phase {phase_id} missing keys: {missing}")

    def test_phase_ids_sequential(self) -> None:
        for i in range(1, 12):
            self.assertIn(f"P{i}", PHASE_TEMPLATES, f"Phase P{i} missing")

    def test_phase_count(self) -> None:
        self.assertEqual(len(PHASE_TEMPLATES), 11)

    def test_dependencies_reference_valid_phases(self) -> None:
        valid_phases = set(PHASE_TEMPLATES.keys())
        for phase_id, template in PHASE_TEMPLATES.items():
            for dep in template["dependencies"]:
                self.assertIn(dep, valid_phases, f"Phase {phase_id} depends on unknown phase {dep}")

    def test_node_type_values_valid(self) -> None:
        valid_types = {"deterministic", "llm", "hybrid"}
        for phase_id, template in PHASE_TEMPLATES.items():
            self.assertIn(
                template["node_type"],
                valid_types,
                f"Phase {phase_id} has invalid node_type: {template['node_type']}",
            )

    def test_reviewers_are_lists(self) -> None:
        for phase_id, template in PHASE_TEMPLATES.items():
            self.assertIsInstance(
                template["reviewers"],
                list,
                f"Phase {phase_id} reviewers should be a list",
            )

    def test_dependencies_are_lists(self) -> None:
        for phase_id, template in PHASE_TEMPLATES.items():
            self.assertIsInstance(
                template["dependencies"],
                list,
                f"Phase {phase_id} dependencies should be a list",
            )

    def test_optional_is_bool(self) -> None:
        for phase_id, template in PHASE_TEMPLATES.items():
            self.assertIsInstance(
                template["optional"],
                bool,
                f"Phase {phase_id} optional should be bool",
            )


class TestLifecycleTemplates(unittest.TestCase):
    """LIFECYCLE_TEMPLATES constant integrity."""

    def test_all_templates_reference_valid_phases(self) -> None:
        valid_phases = set(PHASE_TEMPLATES.keys())
        for template_name, phase_ids in LIFECYCLE_TEMPLATES.items():
            for pid in phase_ids:
                self.assertIn(
                    pid,
                    valid_phases,
                    f"Template {template_name} references unknown phase {pid}",
                )

    def test_template_names(self) -> None:
        expected = {"full", "backend", "frontend", "internal_tool", "minimal"}
        self.assertEqual(set(LIFECYCLE_TEMPLATES.keys()), expected)

    def test_full_template_has_all_11_phases(self) -> None:
        self.assertEqual(len(LIFECYCLE_TEMPLATES["full"]), 11)

    def test_minimal_template_has_5_phases(self) -> None:
        self.assertEqual(len(LIFECYCLE_TEMPLATES["minimal"]), 5)

    def test_backend_template_excludes_p5(self) -> None:
        self.assertNotIn("P5", LIFECYCLE_TEMPLATES["backend"])

    def test_frontend_template_excludes_p4(self) -> None:
        self.assertNotIn("P4", LIFECYCLE_TEMPLATES["frontend"])

    def test_internal_tool_excludes_p4_p5_p6(self) -> None:
        for pid in ["P4", "P5", "P6"]:
            self.assertNotIn(pid, LIFECYCLE_TEMPLATES["internal_tool"])

    def test_all_templates_are_non_empty(self) -> None:
        for name, phases in LIFECYCLE_TEMPLATES.items():
            self.assertGreater(len(phases), 0, f"Template {name} is empty")


class TestWorkflowEngineBase(unittest.TestCase):
    """WorkflowEngineBase structural stubs."""

    def test_save_checkpoint_raises_not_implemented(self) -> None:
        base = WorkflowEngineBase()
        with self.assertRaises(NotImplementedError):
            base._save_checkpoint(WorkflowInstance(), WorkflowStep())  # type: ignore[arg-type]

    def test_classify_steps_raises_not_implemented(self) -> None:
        base = WorkflowEngineBase()
        with self.assertRaises(NotImplementedError):
            base.classify_steps()

    def test_base_has_class_level_annotations(self) -> None:
        annotations = WorkflowEngineBase.__annotations__
        expected_attrs = {
            "storage_path",
            "definitions",
            "instances",
            "executors",
            "coordinator",
            "dispatcher",
            "checkpoint_manager",
            "checkpoint_interval",
        }
        self.assertTrue(expected_attrs.issubset(set(annotations.keys())))


if __name__ == "__main__":
    unittest.main()
