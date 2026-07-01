#!/usr/bin/env python3
"""Tests for V3.8 #6: WorkflowStep node_type (Deterministic vs LLM separation)."""

from scripts.collaboration.workflow_engine import (
    NodeType,
    WorkflowEngine,
    WorkflowStep,
)


class TestNodeTypeEnum:
    """Verify NodeType enum values."""

    def test_node_type_has_three_values(self):
        """Verify: NodeType has DETERMINISTIC, LLM, HYBRID values."""
        assert NodeType.DETERMINISTIC.value == "deterministic"
        assert NodeType.LLM.value == "llm"
        assert NodeType.HYBRID.value == "hybrid"

    def test_node_type_count(self):
        """Verify: Exactly 3 NodeType values exist."""
        assert len(list(NodeType)) == 3


class TestWorkflowStepNodeType:
    """Verify WorkflowStep node_type field behavior."""

    def test_default_node_type_is_hybrid(self):
        """Verify: Default node_type is HYBRID for backward compatibility."""
        step = WorkflowStep(name="test")
        assert step.node_type == NodeType.HYBRID

    def test_explicit_deterministic(self):
        """Verify: Can set node_type to DETERMINISTIC."""
        step = WorkflowStep(name="parse", node_type=NodeType.DETERMINISTIC)
        assert step.node_type == NodeType.DETERMINISTIC

    def test_explicit_llm(self):
        """Verify: Can set node_type to LLM."""
        step = WorkflowStep(name="generate", node_type=NodeType.LLM)
        assert step.node_type == NodeType.LLM

    def test_is_deterministic_method(self):
        """Verify: is_deterministic() returns True only for DETERMINISTIC."""
        assert WorkflowStep(node_type=NodeType.DETERMINISTIC).is_deterministic() is True
        assert WorkflowStep(node_type=NodeType.LLM).is_deterministic() is False
        assert WorkflowStep(node_type=NodeType.HYBRID).is_deterministic() is False

    def test_requires_llm_property(self):
        """Verify: requires_llm returns True for LLM and HYBRID."""
        assert WorkflowStep(node_type=NodeType.LLM).requires_llm is True
        assert WorkflowStep(node_type=NodeType.HYBRID).requires_llm is True
        assert WorkflowStep(node_type=NodeType.DETERMINISTIC).requires_llm is False


class TestWorkflowStepSerialization:
    """Verify node_type survives serialization round-trip."""

    def test_to_dict_includes_node_type(self):
        """Verify: to_dict includes node_type as string."""
        step = WorkflowStep(name="test", node_type=NodeType.LLM)
        d = step.to_dict()
        assert "node_type" in d
        assert d["node_type"] == "llm"

    def test_from_dict_restores_node_type(self):
        """Verify: from_dict restores node_type enum."""
        data = {"name": "test", "node_type": "deterministic"}
        step = WorkflowStep.from_dict(data)
        assert step.node_type == NodeType.DETERMINISTIC

    def test_from_dict_invalid_node_type_falls_back(self):
        """Verify: Invalid node_type string falls back to HYBRID."""
        data = {"name": "test", "node_type": "invalid_value"}
        step = WorkflowStep.from_dict(data)
        assert step.node_type == NodeType.HYBRID

    def test_from_dict_missing_node_type_defaults(self):
        """Verify: Missing node_type defaults to HYBRID."""
        data = {"name": "test"}
        step = WorkflowStep.from_dict(data)
        assert step.node_type == NodeType.HYBRID

    def test_round_trip_preserves_all_types(self):
        """Verify: All three node_types survive round-trip."""
        for nt in NodeType:
            step = WorkflowStep(name="test", node_type=nt)
            d = step.to_dict()
            restored = WorkflowStep.from_dict(d)
            assert restored.node_type == nt


class TestWorkflowEngineStepSummary:
    """Verify WorkflowEngine step summary and classification."""

    def test_classify_steps_returns_counts(self):
        """Verify: classify_steps returns correct counts by node_type."""
        engine = WorkflowEngine()
        # Create a workflow definition with steps
        from scripts.collaboration.workflow_engine import WorkflowDefinition

        steps = [
            WorkflowStep(name="s1", node_type=NodeType.DETERMINISTIC),
            WorkflowStep(name="s2", node_type=NodeType.DETERMINISTIC),
            WorkflowStep(name="s3", node_type=NodeType.LLM),
            WorkflowStep(name="s4", node_type=NodeType.HYBRID),
        ]
        definition = WorkflowDefinition(workflow_id="test-wf", name="test", steps=steps)
        engine.definitions["test-wf"] = definition
        result = engine.classify_steps("test-wf")
        assert result["deterministic"] == 2
        assert result["llm"] == 1
        assert result["hybrid"] == 1
        assert result["total"] == 4

    def test_classify_steps_empty(self):
        """Verify: Empty workflow returns all zeros."""
        engine = WorkflowEngine()
        result = engine.classify_steps()
        assert result["deterministic"] == 0
        assert result["llm"] == 0
        assert result["hybrid"] == 0
        assert result["total"] == 0

    def test_get_step_summary_detail(self):
        """Verify: classify_steps returns per-step detail."""
        engine = WorkflowEngine()
        from scripts.collaboration.workflow_engine import WorkflowDefinition

        steps = [
            WorkflowStep(step_id="s1", name="parse_file", node_type=NodeType.DETERMINISTIC),
            WorkflowStep(step_id="s2", name="generate", node_type=NodeType.LLM),
        ]
        definition = WorkflowDefinition(workflow_id="test-wf", name="test", steps=steps)
        engine.definitions["test-wf"] = definition
        detail = engine.classify_steps("test-wf")
        assert "by_step" in detail
        assert len(detail["by_step"]) == 2
        assert detail["by_step"][0]["node_type"] == "deterministic"
        assert detail["by_step"][1]["node_type"] == "llm"
        assert detail["summary"]["total"] == 2 if "summary" in detail else detail["total"] == 2
