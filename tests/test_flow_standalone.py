#!/usr/bin/env python3
"""
Tests for P1-1 ask-matt — flow vs standalone classification.

Covers IntentWorkflowMapper.classify_flow_vs_standalone() and the
flow_type field populated on IntentMatch by detect_intent().

Spec reference: V4.1.0 PRD P1-1 (Matt Pocock ask-matt).
"""

import pytest

from scripts.collaboration.intent_workflow_mapper import (
    IntentMatch,
    IntentWorkflowMapper,
)


class TestClassifyFlowVsStandalone:
    """Direct tests for classify_flow_vs_standalone()."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper()

    def test_classify_flow_chinese_ranhou_keyword(self):
        """Chinese '然后' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("先修 bug 然后跑测试")
        assert result == "flow"

    def test_classify_flow_chinese_jiezhe_keyword(self):
        """Chinese '接着' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("接着实现登录功能")
        assert result == "flow"

    def test_classify_flow_chinese_jie_xialai_keyword(self):
        """Chinese '接下来' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("接下来部署到生产环境")
        assert result == "flow"

    def test_classify_flow_english_after_that_keyword(self):
        """English 'after that' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("Fix the bug, after that run tests")
        assert result == "flow"

    def test_classify_flow_english_then_keyword(self):
        """English 'then' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("Implement feature then write tests")
        assert result == "flow"

    def test_classify_flow_english_next_keyword(self):
        """English 'next' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("Next, review the code quality")
        assert result == "flow"

    def test_classify_flow_english_continue_keyword(self):
        """English 'continue' keyword triggers flow classification."""
        result = self.mapper.classify_flow_vs_standalone("continue with the deployment")
        assert result == "flow"

    def test_classify_standalone_independent_question(self):
        """Self-contained question is classified as standalone."""
        result = self.mapper.classify_flow_vs_standalone("修复登录页面的 bug")
        assert result == "standalone"

    def test_classify_standalone_english_independent(self):
        """Independent English task is classified as standalone."""
        result = self.mapper.classify_flow_vs_standalone("Implement a new user authentication feature")
        assert result == "standalone"

    def test_classify_empty_string_returns_standalone(self):
        """Empty string is treated as standalone."""
        result = self.mapper.classify_flow_vs_standalone("")
        assert result == "standalone"

    def test_classify_whitespace_only_returns_standalone(self):
        """Whitespace-only input is treated as standalone."""
        result = self.mapper.classify_flow_vs_standalone("   ")
        assert result == "standalone"

    def test_classify_none_returns_standalone(self):
        """None input is treated as standalone."""
        result = self.mapper.classify_flow_vs_standalone(None)  # type: ignore[arg-type]
        assert result == "standalone"

    def test_classify_mixed_keywords_returns_flow(self):
        """When both flow and standalone markers exist, flow wins."""
        result = self.mapper.classify_flow_vs_standalone(
            "Implement login feature, then deploy to production"
        )
        assert result == "flow"

    def test_classify_case_insensitive(self):
        """Flow detection is case-insensitive."""
        result_upper = self.mapper.classify_flow_vs_standalone("THEN deploy to production")
        result_lower = self.mapper.classify_flow_vs_standalone("then deploy to production")
        assert result_upper == "flow"
        assert result_lower == "flow"

    def test_classify_returns_only_flow_or_standalone(self):
        """Returned value is always one of the two labels."""
        for text in ["", "standalone task", "then do it", "接下来"]:
            result = self.mapper.classify_flow_vs_standalone(text)
            assert result in ("flow", "standalone")

    def test_classify_word_boundary_avoids_false_positive(self):
        """'then' inside 'authentication' must not trigger flow."""
        result = self.mapper.classify_flow_vs_standalone(
            "Implement a new user authentication feature"
        )
        assert result == "standalone"


class TestIntentMatchFlowTypeField:
    """Test the flow_type field on IntentMatch dataclass."""

    def test_intent_match_default_flow_type_is_standalone(self):
        """IntentMatch defaults to standalone when not specified."""
        match = IntentMatch(intent_type="bug_fix", confidence=0.5)
        assert match.flow_type == "standalone"

    def test_intent_match_flow_type_can_be_set_to_flow(self):
        """IntentMatch flow_type can be explicitly set to flow."""
        match = IntentMatch(intent_type="bug_fix", confidence=0.5, flow_type="flow")
        assert match.flow_type == "flow"


class TestDetectIntentIntegration:
    """Integration tests: detect_intent() populates flow_type."""

    def test_detect_intent_flow_type_populated_for_flow_task(self):
        """detect_intent populates flow_type='flow' for continuous tasks."""
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        result = mapper.detect_intent("fix bug, then run tests", lang="en")
        assert result is not None
        assert result.flow_type == "flow"

    def test_detect_intent_flow_type_populated_for_standalone_task(self):
        """detect_intent populates flow_type='standalone' for independent tasks."""
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        result = mapper.detect_intent("fix bug", lang="en")
        assert result is not None
        assert result.flow_type == "standalone"

    def test_detect_intent_flow_type_for_chinese_flow_task(self):
        """detect_intent marks Chinese flow task as flow."""
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        result = mapper.detect_intent("修复 bug，然后部署", lang="zh")
        assert result is not None
        assert result.flow_type == "flow"

    def test_detect_intent_none_result_has_no_flow_type(self):
        """detect_intent returns None when no match, so no flow_type."""
        mapper = IntentWorkflowMapper(confidence_threshold=0.99)
        result = mapper.detect_intent("今天天气不错", lang="zh")
        assert result is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
