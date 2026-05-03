#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for IntentWorkflowMapper - Intent detection and workflow mapping.

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.3 (P0-3)
Test plan: P6(TestPlan) for IntentWorkflowMapper module.
"""

import pytest
from scripts.collaboration.intent_workflow_mapper import (
    IntentWorkflowMapper,
    IntentMatch,
    WorkflowChainDef,
    get_shared_mapper,
)


class TestIntentDetectionChinese:
    """Test intent detection with Chinese keywords."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper(confidence_threshold=0.05)

    def test_detect_bug_fix_chinese(self):
        result = self.mapper.detect_intent("修复登录页面的bug", lang="zh")
        assert result is not None
        assert result.intent_type == "bug_fix"
        assert "solo-coder" in result.required_roles
        assert "tester" in result.required_roles

    def test_detect_bug_fix_with_error_keyword(self):
        result = self.mapper.detect_intent("用户注册报错了，请修复", lang="zh")
        assert result is not None
        assert result.intent_type == "bug_fix"

    def test_detect_new_feature_chinese(self):
        result = self.mapper.detect_intent("实现一个新的用户认证功能", lang="zh")
        assert result is not None
        assert result.intent_type == "new_feature"
        assert "architect" in result.required_roles
        assert len(result.workflow_chain) >= 3

    def test_detect_security_review_chinese(self):
        result = self.mapper.detect_intent("检查SQL注入漏洞并加固", lang="zh")
        assert result is not None
        assert result.intent_type == "security_review"
        assert "security" in result.required_roles

    def test_detect_code_review_chinese(self):
        result = self.mapper.detect_intent("审查这段代码的质量", lang="zh")
        assert result is not None
        assert result.intent_type == "code_review"

    def test_detect_performance_optimization_chinese(self):
        result = self.mapper.detect_intent("优化接口响应速度太慢了", lang="zh")
        assert result is not None
        assert result.intent_type == "performance_optimization"

    def test_detect_deployment_chinese(self):
        result = self.mapper.detect_intent("部署到生产环境", lang="zh")
        assert result is not None
        assert result.intent_type == "deployment"

    def test_no_match_returns_none(self):
        result = self.mapper.detect_intent("今天天气不错", lang="zh")
        assert result is None


class TestIntentDetectionEnglish:
    """Test intent detection with English keywords."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper(confidence_threshold=0.05)

    def test_detect_bug_fix_english(self):
        result = self.mapper.detect_intent(
            "Fix the login page bug that causes crash", lang="en"
        )
        assert result is not None
        assert result.intent_type == "bug_fix"

    def test_detect_new_feature_english(self):
        result = self.mapper.detect_intent(
            "Implement a new user authentication feature", lang="en"
        )
        assert result is not None
        assert result.intent_type == "new_feature"
        assert "architect" in result.required_roles

    def test_detect_security_review_english(self):
        result = self.mapper.detect_intent(
            "Check for SQL injection vulnerabilities and harden", lang="en"
        )
        assert result is not None
        assert result.intent_type == "security_review"
        assert result.gate == "owasp_checklist"

    def test_detect_code_review_english(self):
        result = self.mapper.detect_intent(
            "Review this code for quality issues", lang="en"
        )
        assert result is not None
        assert result.intent_type == "code_review"

    def test_detect_performance_english(self):
        result = self.mapper.detect_intent(
            "Optimize API response time, it's too slow", lang="en"
        )
        assert result is not None
        assert result.intent_type == "performance_optimization"
        assert result.gate == "measure_first"

    def test_detect_deployment_english(self):
        result = self.mapper.detect_intent(
            "Deploy to production with CI/CD pipeline", lang="en"
        )
        assert result is not None
        assert result.intent_type == "deployment"


class TestIntentDetectionJapanese:
    """Test intent detection with Japanese keywords."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper(confidence_threshold=0.05)

    def test_detect_bug_fix_japanese(self):
        result = self.mapper.detect_intent(
            "ログインページのバグを修正してください", lang="ja"
        )
        assert result is not None
        assert result.intent_type == "bug_fix"

    def test_detect_new_feature_japanese(self):
        result = self.mapper.detect_intent(
            "新しいユーザー認証機能を実装する", lang="ja"
        )
        assert result is not None
        assert result.intent_type == "new_feature"

    def test_detect_security_review_japanese(self):
        result = self.mapper.detect_intent(
            "SQLインジェクションの脆弱性をチェックして強化", lang="ja"
        )
        assert result is not None
        assert result.intent_type == "security_review"

    def test_detect_performance_japanese(self):
        result = self.mapper.detect_intent(
            "APIレスポンスが遅い、パフォーマンスを改善", lang="ja"
        )
        assert result is not None
        assert result.intent_type == "performance_optimization"

    def test_detect_deployment_japanese(self):
        result = self.mapper.detect_intent(
            "本番環境にデプロイ", lang="ja"
        )
        assert result is not None
        assert result.intent_type == "deployment"


class TestConfidenceScoring:
    """Test confidence scoring algorithm."""

    def test_high_confidence_multiple_keywords(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.1)
        result = mapper.detect_intent(
            "Fix bug error fail crash exception problem",
            lang="en"
        )
        assert result is not None
        assert result.confidence > 0.5

    def test_low_confidence_single_keyword(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        result = mapper.detect_intent("fix it", lang="en")
        assert result is not None
        assert result.confidence < 0.3

    def test_confidence_below_threshold_returns_none(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.9)
        result = mapper.detect_intent("fix bug", lang="en")
        assert result is None

    def test_confidence_capped_at_one(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.0)
        result = mapper.detect_intent(
            "fix bug error fail crash broken issue defect problem exception",
            lang="en"
        )
        assert result is not None
        assert result.confidence <= 1.0


class TestWorkflowChainMapping:
    """Test correct workflow chain mapping for each intent."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper(confidence_threshold=0.1)

    def test_bug_fix_chain_includes_debugging(self):
        result = self.mapper.detect_intent("fix bug", lang="en")
        assert "debugging_and_error_recovery" in result.workflow_chain
        assert "test_driven_development" in result.workflow_chain

    def test_new_feature_chain_includes_spec(self):
        result = self.mapper.detect_intent("implement feature", lang="en")
        assert "spec_driven_development" in result.workflow_chain
        assert "planning_and_task_breakdown" in result.workflow_chain

    def test_security_chain_includes_hardening(self):
        result = self.mapper.detect_intent("security vulnerability", lang="en")
        assert "security_and_hardening" in result.workflow_chain

    def test_code_review_chain_includes_quality(self):
        result = self.mapper.detect_intent("review code quality", lang="en")
        assert "code_review_and_quality" in result.workflow_chain

    def test_performance_chain_includes_optimization(self):
        result = self.mapper.detect_intent("optimize performance", lang="en")
        assert "performance_optimization" in result.workflow_chain

    def test_deployment_chain_includes_ci_cd(self):
        result = self.mapper.detect_intent("deploy release", lang="en")
        assert "ci_cd_and_automation" in result.workflow_chain
        assert "shipping_and_launch" in result.workflow_chain


class TestRequiredRolesMapping:
    """Test correct role requirements for each intent."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper(confidence_threshold=0.1)

    def test_bug_fix_requires_coder_tester(self):
        result = self.mapper.detect_intent("fix bug", lang="en")
        assert "solo-coder" in result.required_roles
        assert "tester" in result.required_roles
        assert "security" in result.optional_roles

    def test_new_feature_requires_architect_coder_tester(self):
        result = self.mapper.detect_intent("implement feature", lang="en")
        assert "architect" in result.required_roles
        assert "solo-coder" in result.required_roles
        assert "tester" in result.required_roles

    def test_security_requires_security_architect(self):
        result = self.mapper.detect_intent("security audit", lang="en")
        assert "security" in result.required_roles
        assert "architect" in result.required_roles

    def test_code_review_requires_three_roles(self):
        result = self.mapper.detect_intent("code review", lang="en")
        assert len(result.required_roles) == 3
        assert "solo-coder" in result.required_roles
        assert "security" in result.required_roles
        assert "tester" in result.required_roles

    def test_performance_requires_architect_devops(self):
        result = self.mapper.detect_intent("performance optimize", lang="en")
        assert "architect" in result.required_roles
        assert "devops" in result.required_roles

    def test_deployment_requires_devops_security(self):
        result = self.mapper.detect_intent("deploy to production", lang="en")
        assert "devops" in result.required_roles
        assert "security" in result.required_roles


class TestGateRequirements:
    """Test gate requirements and anti-skip messages."""

    def setup_method(self):
        self.mapper = IntentWorkflowMapper(confidence_threshold=0.1)

    def test_bug_fix_has_prove_it_gate(self):
        result = self.mapper.detect_intent("fix bug", lang="en")
        assert result.gate == "prove_it_pattern"
        assert "reproduction test" in result.gate_description.lower()
        assert len(result.anti_skip_message) > 0

    def test_new_feature_has_spec_first_gate(self):
        result = self.mapper.detect_intent("implement feature", lang="en")
        assert result.gate == "spec_first"
        assert "spec" in result.gate_description.lower()

    def test_security_has_owasp_gate(self):
        result = self.mapper.detect_intent("security vulnerability", lang="en")
        assert result.gate == "owasp_checklist"
        assert "OWASP" in result.gate_description

    def test_code_review_has_size_limit_gate(self):
        result = self.mapper.detect_intent("code review", lang="en")
        assert result.gate == "change_size_limit"

    def test_performance_has_measure_first_gate(self):
        result = self.mapper.detect_intent("optimize performance",lang="en")
        assert result.gate == "measure_first"
        assert "measurement" in result.gate_description.lower()

    def test_deployment_has_pre_launch_gate(self):
        result = self.mapper.detect_intent("deploy release", lang="en")
        assert result.gate == "pre_launch_checklist"


class TestCachingMechanism:
    """Test intent detection caching."""

    def test_same_input_returns_cached_result(self):
        mapper = IntentWorkflowMapper()
        result1 = mapper.detect_intent("fix bug", lang="en")
        result2 = mapper.detect_intent("fix bug", lang="en")
        assert result1 is result2

    def test_different_input_not_cached(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        result1 = mapper.detect_intent("fix bug error crash", lang="en")
        result2 = mapper.detect_intent("implement feature create build", lang="en")
        assert result1 is not None
        assert result2 is not None
        assert result1 is not result2
        assert result1.intent_type != result2.intent_type

    def test_cache_key_includes_language(self):
        mapper = IntentWorkflowMapper()
        result_zh = mapper.detect_intent("修复bug", lang="zh")
        result_en = mapper.detect_intent("fix bug", lang="en")
        assert result_zh is not result_en or (
            result_zh is None and result_en is None
        )


class TestUtilityMethods:
    """Test utility methods of IntentWorkflowMapper."""

    def test_get_available_intents_returns_all_six(self):
        mapper = IntentWorkflowMapper()
        intents = mapper.get_available_intents()
        assert len(intents) == 6
        expected = [
            "bug_fix",
            "code_review",
            "deployment",
            "new_feature",
            "performance_optimization",
            "security_review",
        ]
        assert intents == expected

    def test_get_intent_details_valid_type(self):
        mapper = IntentWorkflowMapper()
        details = mapper.get_intent_details("bug_fix")
        assert details is not None
        assert details["intent_type"] == "bug_fix"
        assert "trigger_keywords" in details
        assert "workflow_chain" in details
        assert "required_roles" in details
        assert "gate" in details

    def test_get_intent_details_invalid_type(self):
        mapper = IntentWorkflowMapper()
        details = mapper.get_intent_details("nonexistent_intent")
        assert details is None

    def test_intent_details_contains_all_fields(self):
        mapper = IntentWorkflowMapper()
        details = mapper.get_intent_details("new_feature")
        required_fields = [
            "intent_type",
            "trigger_keywords",
            "workflow_chain",
            "required_roles",
            "optional_roles",
            "gate",
            "gate_description",
            "anti_skip_message",
        ]
        for field in required_fields:
            assert field in details, f"Missing field: {field}"


class TestSingletonPattern:
    """Test get_shared_mapper singleton pattern."""

    def test_returns_same_instance(self):
        instance1 = get_shared_mapper()
        instance2 = get_shared_mapper()
        assert instance1 is instance2

    def test_is_intent_workflow_mapper_instance(self):
        instance = get_shared_mapper()
        assert isinstance(instance, IntentWorkflowMapper)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_returns_none(self):
        mapper = IntentWorkflowMapper()
        result = mapper.detect_intent("", lang="en")
        assert result is None

    def test_whitespace_only_returns_none(self):
        mapper = IntentWorkflowMapper()
        result = mapper.detect_intent("   ", lang="en")
        assert result is None

    def test_case_insensitive_matching(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.1)
        result_lower = mapper.detect_intent("fix bug", lang="en")
        result_upper = mapper.detect_intent("FIX BUG", lang="en")
        assert result_lower is not None
        result_upper is not None
        assert result_lower.intent_type == result_upper.intent_type

    def test_partial_keyword_match(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        result = mapper.detect_intent("this has an error", lang="en")
        assert result is not None
        assert result.intent_type == "bug_fix"

    def test_multi_language_fallback_to_english(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.1)
        result = mapper.detect_intent("fix the bug", lang="ja")
        assert result is not None
        assert result.intent_type == "bug_fix"

    def test_very_long_task_description(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.05)
        long_text = "fix bug " * 100
        result = mapper.detect_intent(long_text, lang="en")
        assert result is not None

    def test_special_characters_in_input(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.1)
        result = mapper.detect_intent(
            "Fix bug! @#$% Error: 404 (not found)", lang="en"
        )
        assert result is not None


class TestIntentMatchDataClass:
    """Test IntentMatch dataclass structure."""

    def test_all_fields_populated_for_bug_fix(self):
        mapper = IntentWorkflowMapper(confidence_threshold=0.1)
        result = mapper.detect_intent("fix bug", lang="en")
        assert isinstance(result, IntentMatch)
        assert result.intent_type == "bug_fix"
        assert isinstance(result.confidence, float)
        assert isinstance(result.workflow_chain, list)
        assert isinstance(result.required_roles, list)
        assert isinstance(result.optional_roles, list)
        assert result.gate is not None
        assert len(result.gate_description) > 0
        assert len(result.anti_skip_message) > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
