#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for OperationClassifier (P1-2: PermissionGuard Three-Tier Extension).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.2
"""

import pytest
from scripts.collaboration.operation_classifier import (
    OperationCategory,
    OperationClassifier,
    ClassifiedOperation,
    OPERATION_CLASSIFICATION,
    create_default_classifier,
    create_strict_classifier,
)


class TestOperationCategoryEnum:
    """Test the three-tier category enum."""

    def test_three_categories_exist(self):
        assert hasattr(OperationCategory, 'ALWAYS_SAFE')
        assert hasattr(OperationCategory, 'NEEDS_REVIEW')
        assert hasattr(OperationCategory, 'FORBIDDEN')

    def test_category_values(self):
        assert OperationCategory.ALWAYS_SAFE.value == "always_safe"
        assert OperationCategory.NEEDS_REVIEW.value == "needs_review"
        assert OperationCategory.FORBIDDEN.value == "forbidden"


class TestDefaultClassifications:
    """Test default operation classification mapping."""

    def test_read_operations_are_always_safe(self):
        safe_ops = ["read_config", "read_file", "read_scratchpad", "list_directory"]
        for op in safe_ops:
            assert OPERATION_CLASSIFICATION[op] == OperationCategory.ALWAYS_SAFE

    def test_write_operations_need_review(self):
        review_ops = ["write_file", "write_scratchpad", "call_llm", "git_operation"]
        for op in review_ops:
            assert OPERATION_CLASSIFICATION[op] == OperationCategory.NEEDS_REVIEW

    def test_dangerous_operations_are_forbidden(self):
        forbidden_ops = [
            "delete_file",
            "execute_shell",
            "access_secrets",
            "eval_code",
            "spawn_process",
        ]
        for op in forbidden_ops:
            assert OPERATION_CLASSIFICATION[op] == OperationCategory.FORBIDDEN

    def test_classification_count(self):
        assert len(OPERATION_CLASSIFICATION) >= 20


class TestOperationClassifier:
    """Test core classification functionality."""

    def setup_method(self):
        self.classifier = create_default_classifier()

    def test_classify_safe_operation(self):
        result = self.classifier.classify("read_config")
        assert result.category == OperationCategory.ALWAYS_SAFE
        assert result.requires_confirmation is False
        assert result.override_allowed is True

    def test_classify_review_required_operation(self):
        result = self.classifier.classify("call_llm")
        assert result.category == OperationCategory.NEEDS_REVIEW
        assert result.requires_confirmation is True
        assert result.override_allowed is True

    def test_classify_forbidden_operation(self):
        result = self.classifier.classify("delete_file")
        assert result.category == OperationCategory.FORBIDDEN
        assert result.requires_confirmation is True
        assert result.override_allowed is False

    def test_classify_unknown_operation_non_strict(self):
        result = self.classifier.classify("unknown_op")
        assert result.category == OperationCategory.NEEDS_REVIEW  # Default non-strict

    def test_classify_unknown_operation_strict(self):
        strict = create_strict_classifier()
        result = strict.classify("unknown_op")
        assert result.category == OperationCategory.FORBIDDEN  # Strict mode

    def test_classified_operation_has_required_fields(self):
        result = self.classifier.classify("write_file")
        assert isinstance(result, ClassifiedOperation)
        assert result.operation_id == "write_file"
        assert len(result.description) > 0
        assert isinstance(result.risk_factors, list)

    def test_classify_with_target_context(self):
        result = self.classifier.classify(
            "delete_file",
            target="/etc/passwd",
        )
        assert "sensitive" in str(result.risk_factors).lower() or len(result.risk_factors) > 0


class TestIsAllowedMethod:
    """Test quick permission check."""

    def setup_method(self):
        self.classifier = create_default_classifier()

    def test_safe_op_allowed_at_default(self):
        allowed, reason = self.classifier.is_allowed("read_config", "DEFAULT")
        assert allowed is True

    def test_forbidden_op_blocked_at_default(self):
        allowed, reason = self.classifier.is_allowed("delete_file", "DEFAULT")
        assert allowed is False
        assert "forbidden" in reason.lower()

    def test_forbidden_op_allowed_at_bypass(self):
        allowed, reason = self.classifier.is_allowed("delete_file", "BYPASS")
        assert allowed is True

    def test_review_op_allowed_at_auto(self):
        allowed, reason = self.classifier.is_allowed("call_llm", "AUTO")
        assert allowed is True

    def test_write_op_blocked_in_plan_mode(self):
        allowed, reason = self.classifier.is_allowed("write_file", "PLAN")
        assert allowed is False
        assert "plan" in reason.lower()


class TestBatchClassification:
    """Test batch operation classification."""

    def test_batch_classify_multiple(self):
        classifier = create_default_classifier()
        operations = [
            {"operation_id": "read_config"},
            {"operation_id": "write_file"},
            {"operation_id": "delete_file"},
        ]
        results = classifier.batch_classify(operations)
        assert len(results) == 3
        assert results[0].category == OperationCategory.ALWAYS_SAFE
        assert results[1].category == OperationCategory.NEEDS_REVIEW
        assert results[2].category == OperationCategory.FORBIDDEN

    def test_batch_with_targets(self):
        classifier = create_default_classifier()
        operations = [
            {"operation_id": "delete_file", "target": "/tmp/test.txt"},
            {"operation_id": "read_file", "target": "/etc/config"},
        ]
        results = classifier.batch_classify(operations)
        assert results[0].category == OperationCategory.FORBIDDEN
        assert results[1].category == OperationCategory.ALWAYS_SAFE


class TestCustomClassifications:
    """Test custom classification overrides."""

    def test_add_custom_safe_operation(self):
        classifier = create_default_classifier()
        classifier.add_custom_classification("custom_read", OperationCategory.ALWAYS_SAFE)
        result = classifier.classify("custom_read")
        assert result.category == OperationCategory.ALWAYS_SAFE

    def test_custom_override_existing(self):
        classifier = create_default_classifier()
        # Override delete_file to be review-required instead of forbidden
        classifier.add_custom_classification("delete_file", OperationCategory.NEEDS_REVIEW)
        result = classifier.classify("delete_file")
        assert result.category == OperationCategory.NEEDS_REVIEW
        assert result.override_allowed is True

    def test_init_with_custom_classifications(self):
        custom = {
            "dangerous_thing": OperationCategory.FORBIDDEN,
            "safe_thing": OperationCategory.ALWAYS_SAFE,
        }
        classifier = OperationClassifier(custom_classifications=custom)
        assert classifier.classify("dangerous_thing").category == OperationCategory.FORBIDDEN
        assert classifier.classify("safe_thing").category == OperationCategory.ALWAYS_SAFE


class TestUtilityMethods:
    """Test utility and query methods."""

    def test_get_forbidden_operations(self):
        classifier = create_default_classifier()
        forbidden = classifier.get_forbidden_operations()
        assert len(forbidden) >= 5
        assert "delete_file" in forbidden
        assert "execute_shell" in forbidden

    def test_get_review_required_operations(self):
        classifier = create_default_classifier()
        review = classifier.get_review_required_operations()
        assert len(review) >= 5
        assert "call_llm" in review
        assert "write_file" in review

    def test_to_dict_serialization(self):
        classifier = create_default_classifier()
        result = classifier.classify("read_config")
        d = result.to_dict()
        assert "operation_id" in d
        assert "category" in d
        assert "requires_confirmation" in d
        assert d["category"] == "always_safe"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_operation_id(self):
        classifier = create_default_classifier()
        result = classifier.classify("")
        assert result.category == OperationCategory.NEEDS_REVIEW  # Non-strict default

    def test_case_insensitive_lookup(self):
        classifications = dict(OPERATION_CLASSIFICATION)
        assert "READ_CONFIG" not in classifications  # Case-sensitive by design

    def test_risk_factors_with_sensitive_target(self):
        classifier = create_default_classifier()
        result = classifier.classify(
            "write_file",
            target="/home/user/.env",
            context={"source_role_id": "solo-coder"},
        )
        factors = result.risk_factors
        assert isinstance(factors, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
