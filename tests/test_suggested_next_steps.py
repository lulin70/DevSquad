#!/usr/bin/env python3
"""Tests for suggested_next_steps feature — V3.7.0."""

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.intent_workflow_mapper import IntentWorkflowMapper


class TestWorkflowChainDefNextSteps:
    """Tests for suggested_next_steps in WorkflowChainDef."""

    def test_all_intents_have_next_steps(self):
        mapper = IntentWorkflowMapper()
        for intent_type, chain_def in mapper.WORKFLOW_CHAINS.items():
            assert len(chain_def.suggested_next_steps) >= 1, f"Intent '{intent_type}' missing suggested_next_steps"

    def test_next_steps_are_strings(self):
        mapper = IntentWorkflowMapper()
        for intent_type, chain_def in mapper.WORKFLOW_CHAINS.items():
            for step in chain_def.suggested_next_steps:
                assert isinstance(step, str), f"Non-string step in {intent_type}"
                assert len(step) > 5, f"Too short step in {intent_type}: {step}"


class TestIntentMatchNextSteps:
    """Tests for suggested_next_steps in IntentMatch."""

    def test_detect_intent_includes_next_steps(self):
        mapper = IntentWorkflowMapper()
        match = mapper.detect_intent("fix the login bug", lang="en")
        assert match is not None
        assert len(match.suggested_next_steps) >= 1

    def test_detect_intent_new_feature(self):
        mapper = IntentWorkflowMapper()
        match = mapper.detect_intent("implement user authentication", lang="en")
        assert match is not None
        assert "Write user stories" in match.suggested_next_steps[0] or len(match.suggested_next_steps) >= 1

    def test_no_intent_returns_default(self):
        mapper = IntentWorkflowMapper()
        steps = mapper.get_suggested_next_steps("nonexistent_intent")
        assert len(steps) >= 1  # Default suggestion


class TestGetSuggestedNextSteps:
    """Tests for IntentWorkflowMapper.get_suggested_next_steps."""

    def test_known_intent(self):
        mapper = IntentWorkflowMapper()
        steps = mapper.get_suggested_next_steps("bug_fix")
        assert len(steps) >= 1
        assert all(isinstance(s, str) for s in steps)

    def test_unknown_intent_returns_default(self):
        mapper = IntentWorkflowMapper()
        steps = mapper.get_suggested_next_steps("unknown_type")
        assert len(steps) >= 1

    def test_returns_copy(self):
        mapper = IntentWorkflowMapper()
        steps1 = mapper.get_suggested_next_steps("bug_fix")
        steps1.append("extra step")
        steps2 = mapper.get_suggested_next_steps("bug_fix")
        assert "extra step" not in steps2


class TestDispatchResultNextSteps:
    """Tests for suggested_next_steps in DispatchResult."""

    def test_default_empty(self):
        result = DispatchResult(success=True, task_description="test")
        assert result.suggested_next_steps == []

    def test_with_next_steps(self):
        result = DispatchResult(
            success=True,
            task_description="test",
            suggested_next_steps=["Step 1", "Step 2"],
        )
        assert len(result.suggested_next_steps) == 2

    def test_to_markdown_includes_next_steps(self):
        result = DispatchResult(
            success=True,
            task_description="fix login bug",
            suggested_next_steps=["Run security review", "Add regression tests"],
            lang="en",
        )
        md = result.to_markdown()
        assert "Suggested Next Steps" in md or "建议下一步" in md

    def test_to_markdown_no_next_steps(self):
        result = DispatchResult(success=True, task_description="test", lang="en")
        md = result.to_markdown()
        # Should not have next steps section if empty
        assert "Next Steps" not in md or "建议下一步" not in md
