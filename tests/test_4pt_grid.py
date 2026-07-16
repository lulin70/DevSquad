"""V4.1.0 P2-UI-4 — 4pt grid spacing detection tests."""

from __future__ import annotations

from scripts.qa.uiux_analyzer import UIUXAnalyzer


class Test4ptGridValidValues:
    def test_valid_4pt_values_pass(self):
        css = (
            ".a { margin: 4px; padding: 8px; gap: 16px; }"
            ".b { margin: 24px; padding: 32px; }"
        )
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []

    def test_zero_passes(self):
        # 0 is always valid (no spacing)
        css = ".a { margin: 0; padding: 0px; gap: 0px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []

    def test_large_4pt_multiples_pass(self):
        css = ".a { margin: 64px; padding: 128px; gap: 48px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []

    def test_rem_values_on_grid_pass(self):
        # 1rem = 16px, so 1rem and 2rem are on grid
        css = ".a { margin: 1rem; padding: 2rem; gap: 0.5rem; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []


class Test4ptGridInvalidValues:
    def test_detects_non_4pt_margin(self):
        css = ".a { margin: 5px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1
        assert issues[0].rule == "spacing_4pt_grid"
        assert issues[0].severity == "warning"
        assert issues[0].metric["px"] == 5.0
        assert issues[0].metric["property"] == "margin"

    def test_detects_non_4pt_padding(self):
        css = ".a { padding: 13px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1
        assert issues[0].metric["property"] == "padding"

    def test_detects_non_4pt_gap(self):
        css = ".a { gap: 7px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1
        assert issues[0].metric["property"] == "gap"

    def test_detects_15px_as_invalid(self):
        css = ".a { margin: 15px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1
        assert issues[0].metric["px"] == 15.0

    def test_detects_non_4pt_rem_value(self):
        # 0.3rem = 4.8px → not on grid
        css = ".a { margin: 0.3rem; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1
        assert abs(issues[0].metric["px"] - 4.8) < 0.01


class Test4ptGridShorthandAndMultiple:
    def test_shorthand_with_one_invalid(self):
        # 4px (ok), 5px (bad), 8px (ok), 16px (ok)
        css = ".a { margin: 4px 5px 8px 16px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1
        assert issues[0].metric["px"] == 5.0

    def test_multiple_violations(self):
        css = ".a { margin: 5px; padding: 7px; gap: 13px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 3
        properties = {i.metric["property"] for i in issues}
        assert properties == {"margin", "padding", "gap"}

    def test_multiple_selectors(self):
        css = (
            ".a { margin: 5px; }"
            ".b { padding: 9px; }"
            ".c { gap: 11px; }"
        )
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 3


class Test4ptGridEdgeCases:
    def test_empty_string_returns_empty(self):
        analyzer = UIUXAnalyzer()
        assert analyzer._check_4pt_grid("") == []

    def test_no_spacing_properties_returns_empty(self):
        css = ".a { color: red; font-size: 16px; border: 1px solid black; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []

    def test_sided_properties_detected(self):
        # margin-top, padding-left, etc.
        css = ".a { margin-top: 5px; padding-left: 13px; row-gap: 7px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 3

    def test_em_unit_treated_as_16px(self):
        # 1em = 16px (default parent font-size)
        css = ".a { margin: 1em; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []  # 16 is on grid

    def test_em_unit_off_grid_detected(self):
        # 0.3em = 4.8px → not on grid
        css = ".a { padding: 0.3em; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert len(issues) == 1

    def test_unsupported_unit_skipped(self):
        # %, vw, vh are not checked (return None from token→px)
        css = ".a { margin: 5%; padding: 2vw; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_4pt_grid(css)
        assert issues == []


class TestCheck4ptGridPublicMethod:
    def test_public_method_matches_private(self):
        css = ".a { margin: 5px; padding: 8px; }"
        analyzer = UIUXAnalyzer()
        public_issues = analyzer.check_4pt_grid(css)
        private_issues = analyzer._check_4pt_grid(css)
        assert len(public_issues) == len(private_issues)
        assert public_issues[0].rule == private_issues[0].rule
