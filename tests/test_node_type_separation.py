#!/usr/bin/env python3
"""
Tests for V3.8 #6: Deterministic vs LLM Step Separation.

Coverage:
  - NodeType enum values
  - WorkflowStep.node_type field default (HYBRID, backward compat)
  - to_dict / from_dict round-trip with node_type
  - is_deterministic() / is_llm() helper methods
  - WorkflowEngine.classify_steps() statistics
  - Lifecycle templates annotated with node_type
  - Backward compatibility: legacy dicts without node_type deserialize
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.workflow_engine import (
    PHASE_TEMPLATES,
    NodeType,
    StepStatus,
    WorkflowEngine,
    WorkflowStep,
)


class TestNodeTypeEnum(unittest.TestCase):
    """Verify NodeType enum definition."""

    def test_node_type_values(self) -> None:
        self.assertEqual(NodeType.DETERMINISTIC.value, "deterministic")
        self.assertEqual(NodeType.LLM.value, "llm")
        self.assertEqual(NodeType.HYBRID.value, "hybrid")

    def test_node_type_has_three_members(self) -> None:
        self.assertEqual(len(list(NodeType)), 3)


class TestWorkflowStepNodeType(unittest.TestCase):
    """Verify WorkflowStep.node_type field and helpers."""

    def test_default_node_type_is_hybrid(self) -> None:
        step = WorkflowStep(name="test")
        self.assertEqual(step.node_type, NodeType.HYBRID)

    def test_is_deterministic_helper(self) -> None:
        step = WorkflowStep(name="test", node_type=NodeType.DETERMINISTIC)
        self.assertTrue(step.is_deterministic())
        self.assertFalse(step.is_llm())

    def test_is_llm_helper(self) -> None:
        step = WorkflowStep(name="test", node_type=NodeType.LLM)
        self.assertTrue(step.is_llm())
        self.assertFalse(step.is_deterministic())

    def test_hybrid_neither_deterministic_nor_llm(self) -> None:
        step = WorkflowStep(name="test", node_type=NodeType.HYBRID)
        self.assertFalse(step.is_deterministic())
        self.assertFalse(step.is_llm())


class TestWorkflowStepSerialization(unittest.TestCase):
    """Verify to_dict / from_dict include node_type."""

    def test_to_dict_includes_node_type(self) -> None:
        step = WorkflowStep(name="test", node_type=NodeType.LLM)
        d = step.to_dict()
        self.assertIn("node_type", d)
        self.assertEqual(d["node_type"], "llm")

    def test_from_dict_restores_node_type(self) -> None:
        d = {"name": "test", "node_type": "deterministic"}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.node_type, NodeType.DETERMINISTIC)

    def test_round_trip_preserves_node_type(self) -> None:
        step = WorkflowStep(name="test", node_type=NodeType.LLM)
        d = step.to_dict()
        restored = WorkflowStep.from_dict(d)
        self.assertEqual(restored.node_type, NodeType.LLM)

    def test_from_dict_invalid_node_type_falls_back_to_hybrid(self) -> None:
        d = {"name": "test", "node_type": "invalid_mode"}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.node_type, NodeType.HYBRID)

    def test_from_dict_missing_node_type_falls_back_to_hybrid(self) -> None:
        # Backward compatibility: legacy dicts without node_type
        d = {"name": "test", "step_id": "s1"}
        step = WorkflowStep.from_dict(d)
        self.assertEqual(step.node_type, NodeType.HYBRID)

    def test_to_dict_node_type_as_string(self) -> None:
        step = WorkflowStep(name="test", node_type=NodeType.DETERMINISTIC)
        d = step.to_dict()
        self.assertIsInstance(d["node_type"], str)
        self.assertEqual(d["node_type"], "deterministic")


class TestWorkflowEngineClassifySteps(unittest.TestCase):
    """Verify WorkflowEngine.classify_steps() statistics."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.TemporaryDirectory()
        self.engine = WorkflowEngine(storage_path=self._tmpdir.name)

    def tearDown(self) -> None:
        self._tmpdir.cleanup()

    def test_classify_steps_empty_definitions(self) -> None:
        stats = self.engine.classify_steps()
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["deterministic"], 0)
        self.assertEqual(stats["llm"], 0)
        self.assertEqual(stats["hybrid"], 0)

    def test_classify_steps_mixed_node_types(self) -> None:
        definition = self.engine.create_workflow_from_task(
            "develop and test the feature",
            "implement code and run tests",
        )
        # Add explicit node_type annotations for the test
        for step in definition.steps:
            if step.name == "Development":
                step.node_type = NodeType.HYBRID
            elif step.name == "Test Execution":
                step.node_type = NodeType.DETERMINISTIC
            elif step.name == "Test Design":
                step.node_type = NodeType.LLM
        stats = self.engine.classify_steps()
        self.assertEqual(stats["total"], len(definition.steps))
        self.assertGreaterEqual(stats["deterministic"], 1)
        self.assertGreaterEqual(stats["llm"], 1)
        self.assertGreaterEqual(stats["hybrid"], 1)
        # Percentages sum to 100
        total_pct = stats["deterministic_pct"] + stats["llm_pct"] + stats["hybrid_pct"]
        self.assertAlmostEqual(total_pct, 100.0, places=1)

    def test_classify_steps_by_step_list(self) -> None:
        definition = self.engine.create_workflow_from_task("develop feature")
        stats = self.engine.classify_steps()
        self.assertEqual(len(stats["by_step"]), len(definition.steps))
        for entry in stats["by_step"]:
            self.assertIn("step_id", entry)
            self.assertIn("name", entry)
            self.assertIn("node_type", entry)
            self.assertIn(entry["node_type"], {"deterministic", "llm", "hybrid"})

    def test_classify_steps_unknown_workflow_id(self) -> None:
        stats = self.engine.classify_steps("nonexistent-wf-id")
        self.assertEqual(stats["total"], 0)
        self.assertEqual(stats["by_step"], [])


class TestLifecycleTemplatesNodeType(unittest.TestCase):
    """Verify lifecycle templates are annotated with node_type."""

    def test_all_phase_templates_have_node_type(self) -> None:
        for phase_id, template in PHASE_TEMPLATES.items():
            self.assertIn(
                "node_type",
                template,
                f"Phase {phase_id} missing node_type annotation",
            )
            self.assertIn(
                template["node_type"],
                {"deterministic", "llm", "hybrid"},
                f"Phase {phase_id} has invalid node_type: {template['node_type']}",
            )

    def test_create_lifecycle_propagates_node_type(self) -> None:
        engine = WorkflowEngine(storage_path=tempfile.mkdtemp())
        definition = engine.create_lifecycle("full")
        # P1 is annotated as "llm"
        p1 = next(s for s in definition.steps if s.step_id == "P1")
        self.assertEqual(p1.node_type, NodeType.LLM)
        # P9 is annotated as "deterministic"
        p9 = next(s for s in definition.steps if s.step_id == "P9")
        self.assertEqual(p9.node_type, NodeType.DETERMINISTIC)
        # P8 is annotated as "hybrid"
        p8 = next(s for s in definition.steps if s.step_id == "P8")
        self.assertEqual(p8.node_type, NodeType.HYBRID)

    def test_classify_steps_on_lifecycle(self) -> None:
        engine = WorkflowEngine(storage_path=tempfile.mkdtemp())
        engine.create_lifecycle("full")
        stats = engine.classify_steps()
        # Full lifecycle has 11 phases with mixed node_types
        self.assertEqual(stats["total"], 11)
        self.assertGreater(stats["llm"], 0)
        self.assertGreater(stats["deterministic"], 0)
        self.assertGreater(stats["hybrid"], 0)


class TestBackwardCompatibility(unittest.TestCase):
    """Verify legacy code without node_type still works."""

    def test_workflow_step_created_without_node_type_works(self) -> None:
        # Simulate legacy code that doesn't pass node_type
        step = WorkflowStep(
            step_id="legacy-1",
            name="Legacy Step",
            description="Created before V3.8",
            role_id="architect",
            action="legacy_action",
        )
        self.assertEqual(step.node_type, NodeType.HYBRID)
        self.assertFalse(step.is_deterministic())
        self.assertFalse(step.is_llm())

    def test_legacy_dict_without_node_type_deserializes(self) -> None:
        legacy_dict = {
            "step_id": "legacy-2",
            "name": "Legacy",
            "role_id": "tester",
            "action": "test",
            "status": "pending",
        }
        step = WorkflowStep.from_dict(legacy_dict)
        self.assertEqual(step.node_type, NodeType.HYBRID)
        self.assertEqual(step.status, StepStatus.PENDING)


if __name__ == "__main__":
    unittest.main()
