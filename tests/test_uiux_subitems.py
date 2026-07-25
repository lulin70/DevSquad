"""V4.3.0 P1-5 — UIUXAnalyzer sub-item audit tests.

Coverage focus (per task requirements):
- Sub-item audit for each of the 4 dimensions (a11y/interaction/layout/ux_antipattern)
- Missing sub-item auto-added with NOT_IMPLEMENTED
- Existing sub-item preserved (idempotent)
- OKLCH color audit + 4pt grid audit
- 46 deterministic rules coverage
- Audit report generation
- Edge/error/boundary: unknown dimension, status mapping, severity mapping,
  non-matching issues, registry functions, report formatting
"""

from __future__ import annotations

from scripts.qa.deterministic_rule_engine import DeterministicRuleEngine
from scripts.qa.models import UIUXIssue
from scripts.qa.uiux_analyzer import UIUXAnalyzer
from scripts.qa.uiux_subitems import (
    SubItemAuditResult,
    SubItemDef,
    format_subitem_report,
    get_all_subitems,
    get_dimensions,
    get_subitems_for_dimension,
)

# ============================================================
# 1. Sub-item audit for each of the 4 dimensions
# ============================================================


class TestSubItemAuditPerDimension:
    def test_audit_a11y_dimension(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("a11y")
        assert len(results) == 5
        names = {r.name for r in results}
        assert "color_contrast_ratio" in names
        assert "image_alt_text" in names
        assert all(r.dimension == "a11y" for r in results)

    def test_audit_interaction_dimension(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("interaction")
        assert len(results) == 5
        assert all(r.dimension == "interaction" for r in results)
        names = {r.name for r in results}
        assert "click_target_size" in names
        assert "form_validation_feedback" in names

    def test_audit_layout_dimension(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("layout")
        assert len(results) == 5
        assert any(r.name == "4pt_grid_spacing_compliance" for r in results)
        assert all(r.dimension == "layout" for r in results)

    def test_audit_ux_antipattern_dimension(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("ux_antipattern")
        assert len(results) == 5
        assert any(r.name == "oklch_color_space_compliance" for r in results)
        assert all(r.dimension == "ux_antipattern" for r in results)


# ============================================================
# 2. Missing sub-item auto-added + existing preserved
# ============================================================


class TestMissingAndPreserved:
    def test_missing_subitem_auto_added(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("a11y")
        not_impl = [r for r in results if r.status == "NOT_IMPLEMENTED"]
        assert len(not_impl) >= 1
        assert any(r.name == "keyboard_navigation_support" for r in not_impl)

    def test_existing_subitem_preserved(self):
        analyzer = UIUXAnalyzer()
        r1 = analyzer.audit_subitems("a11y")
        r2 = analyzer.audit_subitems("a11y")
        assert len(r1) == len(r2)
        assert {r.name for r in r1} == {r.name for r in r2}
        assert [r.status for r in r1] == [r.status for r in r2]


# ============================================================
# 3. Special sub-items: OKLCH, 4pt grid, 46 rules
# ============================================================


class TestSpecialSubItems:
    def test_oklch_color_subitem(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("ux_antipattern")
        oklch = [r for r in results if r.name == "oklch_color_space_compliance"][0]
        assert oklch.status == "PASS"
        assert "OKLCH" in oklch.detail or "oklch" in oklch.detail.lower()

    def test_4pt_grid_subitem(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("layout")
        grid = [r for r in results if r.name == "4pt_grid_spacing_compliance"][0]
        assert grid.status == "PASS"
        assert "4pt" in grid.detail or "grid" in grid.detail.lower()

    def test_46_rules_coverage(self):
        engine = DeterministicRuleEngine()
        assert engine.rule_count >= 46


# ============================================================
# 4. Audit report generation
# ============================================================


class TestAuditReportGeneration:
    def test_audit_report_generation(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("a11y")
        report = format_subitem_report(results)
        assert "UIUX Sub-Item Audit Report" in report
        assert "a11y" in report
        assert "Summary:" in report
        assert "PASS" in report
        assert "NOT_IMPLEMENTED" in report


# ============================================================
# 5. Edge / error / boundary tests
# ============================================================


class TestEdgeAndBoundary:
    def test_unknown_dimension_returns_empty(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("nonexistent")
        assert results == []

    def test_pass_status_when_no_issues(self):
        analyzer = UIUXAnalyzer()
        results = analyzer.audit_subitems("a11y")
        passed = [r for r in results if r.status == "PASS"]
        assert len(passed) >= 1

    def test_warn_status_with_warning_issues(self):
        analyzer = UIUXAnalyzer()
        issues = [
            UIUXIssue(
                severity="warning",
                category="a11y",
                rule="wcag_contrast",
                element="text",
                message="low contrast",
                fix="increase contrast",
            )
        ]
        results = analyzer.audit_subitems("a11y", issues=issues)
        contrast = [r for r in results if r.name == "color_contrast_ratio"][0]
        assert contrast.status == "WARN"

    def test_fail_status_with_critical_issues(self):
        analyzer = UIUXAnalyzer()
        issues = [
            UIUXIssue(
                severity="critical",
                category="a11y",
                rule="img_missing_alt",
                element="img",
                message="missing alt",
                fix="add alt",
            )
        ]
        results = analyzer.audit_subitems("a11y", issues=issues)
        alt = [r for r in results if r.name == "image_alt_text"][0]
        assert alt.status == "FAIL"

    def test_info_severity_gives_warn(self):
        analyzer = UIUXAnalyzer()
        issues = [
            UIUXIssue(
                severity="info",
                category="a11y",
                rule="hsv_harsh_combination",
                element="text",
                message="harsh",
                fix="adjust",
            )
        ]
        results = analyzer.audit_subitems("a11y", issues=issues)
        contrast = [r for r in results if r.name == "color_contrast_ratio"][0]
        assert contrast.status == "WARN"

    def test_all_four_status_values_present(self):
        analyzer = UIUXAnalyzer()
        issues = [
            UIUXIssue("critical", "a11y", "img_missing_alt", "e", "m", "f"),
            UIUXIssue("warning", "a11y", "wcag_contrast", "e", "m", "f"),
        ]
        results = analyzer.audit_subitems("a11y", issues=issues)
        statuses = {r.status for r in results}
        assert "PASS" in statuses
        assert "WARN" in statuses
        assert "FAIL" in statuses
        assert "NOT_IMPLEMENTED" in statuses

    def test_issues_not_matching_any_subitem_have_no_effect(self):
        analyzer = UIUXAnalyzer()
        issues = [
            UIUXIssue(
                severity="critical",
                category="a11y",
                rule="unknown_rule_xyz",
                element="e",
                message="m",
                fix="f",
            )
        ]
        results = analyzer.audit_subitems("a11y", issues=issues)
        assert not any(r.status == "FAIL" for r in results)

    def test_error_severity_treated_as_fail(self):
        """The gradient_text rule uses severity='error' — must map to FAIL."""
        analyzer = UIUXAnalyzer()
        issues = [
            UIUXIssue(
                severity="error",
                category="ux_antipattern",
                rule="form_no_validation",
                element="form",
                message="no validation",
                fix="add validation",
            )
        ]
        results = analyzer.audit_subitems("interaction", issues=issues)
        form = [r for r in results if r.name == "form_validation_feedback"][0]
        assert form.status == "FAIL"

    def test_get_subitems_for_dimension(self):
        items = get_subitems_for_dimension("layout")
        assert len(items) == 5
        assert all(isinstance(i, SubItemDef) for i in items)

    def test_get_subitems_unknown_dimension(self):
        items = get_subitems_for_dimension("nope")
        assert items == []

    def test_get_all_subitems(self):
        all_items = get_all_subitems()
        assert len(all_items) == 20  # 4 dimensions × 5 sub-items

    def test_get_dimensions(self):
        dims = get_dimensions()
        assert dims == ("a11y", "interaction", "layout", "ux_antipattern")

    def test_format_report_empty(self):
        report = format_subitem_report([])
        assert "No sub-items" in report

    def test_subitem_result_fields(self):
        result = SubItemAuditResult(
            name="test",
            dimension="a11y",
            status="PASS",
            detail="ok",
            fix_suggestion="none",
        )
        assert result.name == "test"
        assert result.status == "PASS"
        assert result.fix_suggestion == "none"

    def test_audit_idempotent(self):
        analyzer = UIUXAnalyzer()
        r1 = analyzer.audit_subitems("interaction")
        r2 = analyzer.audit_subitems("interaction")
        assert [r.status for r in r1] == [r.status for r in r2]
        assert [r.name for r in r1] == [r.name for r in r2]

    def test_each_dimension_has_five_subitems(self):
        analyzer = UIUXAnalyzer()
        for dim in get_dimensions():
            results = analyzer.audit_subitems(dim)
            assert len(results) == 5, f"{dim} should have 5 sub-items"
