"""V4.1.0 P1-UI-1 — Anti-pattern Bans (6 taste-skill rules) tests.

Each rule has at least one positive case (the rule fires) and one negative
case (the rule stays silent).
"""

from __future__ import annotations

from scripts.qa.uiux_analyzer import UIUXAnalyzer


class TestBorderLeftAccentStripes:
    def test_detects_border_left_accent_stripe(self):
        css = ".callout { border-left: 4px solid #3b82f6; padding: 8px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_border_left_accent(css)
        assert len(issues) == 1
        assert issues[0].rule == "border_left_accent_stripes"
        assert issues[0].severity == "warning"
        assert issues[0].metric["width"] == 4

    def test_ignores_thin_border_left(self):
        # 1px borders are not accent stripes
        css = ".box { border-left: 1px solid #ccc; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_border_left_accent(css)
        assert issues == []

    def test_no_border_left_returns_empty(self):
        css = ".card { padding: 16px; border: 1px solid #ccc; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_border_left_accent(css)
        assert issues == []


class TestGradientText:
    def test_detects_gradient_text(self):
        css = (
            ".hero { "
            "background: linear-gradient(to right, #667eea, #764ba2); "
            "background-clip: text; "
            "-webkit-background-clip: text; "
            "color: transparent; }"
        )
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_gradient_text(css)
        assert len(issues) == 1
        assert issues[0].rule == "gradient_text"
        assert issues[0].severity == "error"

    def test_ignores_gradient_without_clip_text(self):
        # gradient background without background-clip: text
        css = ".card { background: linear-gradient(to right, #667eea, #764ba2); }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_gradient_text(css)
        assert issues == []

    def test_ignores_clip_text_without_gradient(self):
        css = ".x { background-clip: text; color: black; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_gradient_text(css)
        assert issues == []


class TestGlassmorphismOveruse:
    def test_detects_overuse(self):
        css = (
            ".a { backdrop-filter: blur(10px); }"
            ".b { backdrop-filter: blur(8px); }"
            ".c { backdrop-filter: blur(12px); }"
        )
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_glassmorphism_overuse(css)
        assert len(issues) == 1
        assert issues[0].rule == "glassmorphism_overuse"
        assert issues[0].severity == "warning"
        assert issues[0].metric["count"] == 3

    def test_allows_within_limit(self):
        css = ".a { backdrop-filter: blur(10px); } .b { backdrop-filter: blur(8px); }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_glassmorphism_overuse(css)
        assert issues == []

    def test_no_glassmorphism_returns_empty(self):
        css = ".card { box-shadow: 0 2px 4px rgba(0,0,0,0.1); }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_glassmorphism_overuse(css)
        assert issues == []


class TestOverusedFonts:
    def test_detects_inter_font(self):
        css = "body { font-family: 'Inter', sans-serif; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_overused_fonts(css)
        assert len(issues) == 1
        assert issues[0].rule == "overused_fonts"
        assert issues[0].metric["font"] == "inter"

    def test_detects_roboto_font(self):
        css = "h1 { font-family: Roboto, Arial, sans-serif; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_overused_fonts(css)
        assert len(issues) == 1
        assert issues[0].metric["font"] == "roboto"

    def test_detects_dm_sans_font(self):
        css = ".text { font-family: 'DM Sans', sans-serif; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_overused_fonts(css)
        assert len(issues) == 1
        assert issues[0].metric["font"] == "dm sans"

    def test_allows_distinctive_font(self):
        css = "body { font-family: 'IBM Plex Sans', sans-serif; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_overused_fonts(css)
        assert issues == []


class TestPurpleBlueGradient:
    def test_detects_purple_blue_gradient(self):
        css = (
            ".hero { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); }"
        )
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_purple_blue_gradient(css)
        assert len(issues) == 1
        assert issues[0].rule == "purple_blue_gradient"
        assert issues[0].severity == "warning"

    def test_detects_purple_blue_named_colors(self):
        css = ".x { background: linear-gradient(to right, purple, blue); }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_purple_blue_gradient(css)
        assert len(issues) == 1

    def test_ignores_single_color_gradient(self):
        css = ".x { background: linear-gradient(to right, #fff, #ccc); }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_purple_blue_gradient(css)
        assert issues == []


class TestNestedCards:
    def test_detects_nested_card_selector(self):
        css = ".card .card { padding: 8px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_nested_cards(css)
        assert len(issues) == 1
        assert issues[0].rule == "nested_cards"
        assert issues[0].metric["nesting_level"] == 2

    def test_detects_deeply_nested_card(self):
        css = ".card .card .card { padding: 4px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_nested_cards(css)
        assert len(issues) == 1
        assert issues[0].metric["nesting_level"] == 3

    def test_ignores_single_card(self):
        css = ".card { padding: 16px; }"
        analyzer = UIUXAnalyzer()
        issues = analyzer._check_nested_cards(css)
        assert issues == []


class TestCheckCssAntipatternsAggregator:
    def test_runs_all_six_checkers(self):
        # CSS that triggers all 6 anti-pattern rules
        css = (
            ".callout { border-left: 4px solid #3b82f6; }\n"
            ".hero { background: linear-gradient(to right, purple, blue);"
            " background-clip: text; color: transparent; }\n"
            ".a { backdrop-filter: blur(10px); }"
            ".b { backdrop-filter: blur(10px); }"
            ".c { backdrop-filter: blur(10px); }\n"
            "body { font-family: 'Inter', sans-serif; }\n"
            ".card .card { padding: 8px; }\n"
        )
        analyzer = UIUXAnalyzer()
        issues = analyzer.check_css_antipatterns(css)
        rules = {i.rule for i in issues}
        assert "border_left_accent_stripes" in rules
        assert "gradient_text" in rules
        assert "glassmorphism_overuse" in rules
        assert "overused_fonts" in rules
        assert "purple_blue_gradient" in rules
        assert "nested_cards" in rules

    def test_empty_css_returns_empty(self):
        analyzer = UIUXAnalyzer()
        issues = analyzer.check_css_antipatterns("")
        assert issues == []


class TestAuditDomDataCssIntegration:
    def test_audit_dom_data_runs_css_antipatterns(self):
        # When `css_text` is present in ux section, anti-pattern rules fire
        data = {
            "a11y": {},
            "interaction": {},
            "layout": {},
            "ux": {
                "css_text": ".callout { border-left: 4px solid red; }",
            },
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        rules = {i.rule for i in report.issues}
        assert "border_left_accent_stripes" in rules

    def test_audit_dom_data_without_css_text(self):
        # Without css_text, anti-pattern rules do not fire
        data = {
            "a11y": {},
            "interaction": {},
            "layout": {},
            "ux": {"forms": [], "destructive_without_confirm": []},
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        rules = {i.rule for i in report.issues}
        assert "border_left_accent_stripes" not in rules
