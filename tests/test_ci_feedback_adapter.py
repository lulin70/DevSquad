#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for CIFeedbackAdapter (P1-5: CI Results Reading + Context Injection).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.5
"""

import pytest
from scripts.collaboration.ci_feedback_adapter import (
    CIMetric,
    CIResult,
    CIContext,
    PytestParser,
    CoverageParser,
    LintParser,
    BuildParser,
    CIFeedbackAdapter,
    create_default_adapter,
)


class TestPytestParser:
    """Test pytest output parsing."""

    def test_parse_passed_tests(self):
        output = "========================= 42 passed in 3.2s ========================="
        result = PytestParser.parse(output)
        assert result.success is True
        passed = result.get_metric("tests_passed")
        assert passed is not None
        assert passed.value == 42

    def test_parse_failed_tests(self):
        output = "========================= 38 passed, 4 failed in 5.1s ===================="
        result = PytestParser.parse(output)
        assert result.success is False
        failed = result.get_metric("tests_failed")
        assert failed is not None
        assert failed.status == "fail"

    def test_parse_with_errors(self):
        output = "=== 10 passed, 2 failed, 1 error, 3 skipped in 8.0s ==="
        result = PytestParser.parse(output)
        assert result.get_metric("errors").value == 1
        assert result.get_metric("skipped").value == 3


class TestCoverageParser:
    """Test coverage report parsing."""

    def test_parse_good_coverage(self):
        output = "TOTAL      500     50    90%   200     20    90%"
        result = CoverageParser.parse(output)
        cov = result.get_metric("coverage_percentage")
        assert cov is not None
        assert cov.status == "pass"
        assert "90%" in str(cov.value)

    def test_parse_low_coverage(self):
        output = "TOTAL      1000    900   10%   400    380   5%"
        result = CoverageParser.parse(output)
        cov = result.get_metric("coverage_percentage")
        assert cov is not None
        assert cov.status == "fail"


class TestLintParser:
    """Test linter output parsing."""

    def test_parse_clean_output(self):
        output = ""
        result = LintParser.parse(output)
        assert result.success is True
        assert result.get_metric("errors").value == 0

    def test_parse_with_errors(self):
        output = "E302 expected 2 blank lines\nE999 SyntaxError: invalid syntax"
        result = LintParser.parse(output)
        assert result.success is False
        assert result.get_metric("errors").value >= 1


class TestBuildParser:
    """Test build output parsing."""

    def test_parse_successful_build(self):
        output = "Build succeeded in 1.2s"
        result = BuildParser.parse(output)
        assert result.success is True

    def test_parse_failed_build(self):
        output = "Build failed with error: missing dependency"
        result = BuildParser.parse(output)
        assert result.success is False


class TestCIResult:
    """Test CIResult structure."""

    def test_has_failures_detection(self):
        result = CIResult(source="test")
        result.metrics.append(CIMetric("test", "value", "pass"))
        result.metrics.append(CIMetric("fail_test", "value", "fail"))
        assert result.has_failures() is True

    def test_no_failures(self):
        result = CIResult(source="test")
        result.metrics.append(CIMetric("a", "v", "pass"))
        result.metrics.append(CIMetric("b", "v", "warning"))
        assert result.has_failures() is False

    def test_to_summary_format(self):
        result = CIResult(source="pytest", success=True)
        result.duration_seconds = 3.2
        summary = result.to_summary()
        assert "PASS" in summary
        assert "pytest" in summary
        assert "3.2" in summary


class TestCIContext:
    """Test CIContext generation."""

    def test_no_data_context(self):
        adapter = CIFeedbackAdapter()
        context = adapter.generate_context([])
        assert context.overall_status == "no_ci_data"

    def test_all_pass_context(self):
        adapter = CIFeedbackAdapter()
        r1 = CIResult(source="pytest", success=True)
        r2 = CIResult(source="build", success=True)
        context = adapter.generate_context([r1, r2])
        assert context.overall_status == "all_pass"

    def test_has_failures_context(self):
        adapter = CIFeedbackAdapter()
        r1 = CIResult(source="pytest", success=False)
        r1.metrics.append(CIMetric("tests_failed", 3, "fail"))
        context = adapter.generate_context([r1])
        assert context.overall_status == "has_failures"
        assert len(context.actionable_items) > 0

    def test_prompt_injection_format(self):
        adapter = CIFeedbackAdapter()
        r1 = CIResult(source="pytest", success=True)
        context = adapter.generate_context([r1])
        injection = context.to_prompt_injection()
        assert "CI/CD Feedback Context" in injection
        assert "Quality Gates" in injection


class TestCIFeedbackAdapter:
    """Test main adapter functionality."""

    def setup_method(self):
        self.adapter = create_default_adapter()

    def test_parse_known_source_type(self):
        output = "10 passed in 1.0s"
        result = self.adapter.parse_ci_output(output, "pytest")
        assert result is not None
        assert result.source == "pytest"

    def test_parse_unknown_source_returns_none(self):
        result = self.adapter.parse_ci_output("output", "unknown_type")
        assert result is None

    def test_generate_context_from_multiple_results(self):
        results = [
            CIResult(source="pytest", success=True),
            CIResult(source="coverage", success=True),
            CIResult(source="lint", success=True),
            CIResult(source="build", success=True),
        ]
        context = self.adapter.generate_context(results)
        assert context.overall_status == "all_pass"
        assert len(context.quality_gates) > 0

    def test_action_items_sorted_by_severity(self):
        r1 = CIResult(source="pytest", success=False)
        r1.metrics.append(CIMetric("critical_bug", "X", "fail"))
        r1.metrics.append(CIMetric("style_issue", "Y", "warning"))

        context = self.adapter.generate_context([r1])
        if len(context.actionable_items) >= 2:
            assert context.actionable_items[0]["severity"] == "critical"


class TestFactoryFunctions:
    """Test factory functions."""

    def test_default_adapter_not_strict(self):
        adapter = create_default_adapter()
        assert adapter._strict_mode is False

    def test_strict_adapter_is_strict(self):
        from scripts.collaboration.ci_feedback_adapter import create_strict_adapter
        adapter = create_strict_adapter()
        assert adapter._strict_mode is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
