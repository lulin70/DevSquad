"""P1-2 UI/UX 巡检与视觉回归单元测试。"""

from __future__ import annotations

import pytest

from scripts.qa import (
    ChangedRegion,
    DiffResult,
    UIUXAnalyzer,
    UIUXAuditReport,
    UIUXIssue,
    VisualRegressionChecker,
)

# ============================================================
# UIUXAnalyzer 测试
# ============================================================

class TestUIUXIssueModel:
    def test_issue_creation(self):
        issue = UIUXIssue(
            severity="critical",
            category="a11y",
            rule="img_missing_alt",
            element="img",
            message="missing alt",
            fix="add alt",
        )
        assert issue.severity == "critical"
        assert issue.metric == {}


class TestUIUXAuditReport:
    def test_report_counts(self):
        issues = [
            UIUXIssue("critical", "a11y", "r1", "e1", "m1", "f1"),
            UIUXIssue("warning", "layout", "r2", "e2", "m2", "f2"),
            UIUXIssue("warning", "interaction", "r3", "e3", "m3", "f3"),
            UIUXIssue("info", "ux_antipattern", "r4", "e4", "m4", "f4"),
        ]
        report = UIUXAuditReport(url="http://test", issues=issues)
        assert report.total_count == 4
        assert report.critical_count == 1
        assert report.warning_count == 2
        assert report.info_count == 1
        assert report.passed is False

    def test_report_passed_when_no_critical(self):
        issues = [
            UIUXIssue("warning", "layout", "r1", "e1", "m1", "f1"),
            UIUXIssue("info", "ux_antipattern", "r2", "e2", "m2", "f2"),
        ]
        report = UIUXAuditReport(url="http://test", issues=issues)
        assert report.passed is True

    def test_report_audited_at_default(self):
        report = UIUXAuditReport(url="http://test", issues=[])
        assert report.audited_at  # ISO timestamp generated


class TestUIUXAnalyzerA11y:
    def test_img_missing_alt(self):
        data = {
            "a11y": {
                "images": [
                    {"src": "logo.png", "has_alt": False, "alt_value": ""},
                    {"src": "icon.png", "has_alt": True, "alt_value": "icon"},
                ],
                "inputs": [],
                "div_buttons": [],
                "text_contrast": [],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert report.total_count == 1
        assert report.issues[0].rule == "img_missing_alt"
        assert report.issues[0].severity == "critical"

    def test_input_missing_label(self):
        data = {
            "a11y": {
                "images": [],
                "inputs": [
                    {"type": "text", "has_label": False, "id": "name"},
                    {"type": "email", "has_label": True, "id": "email"},
                ],
                "div_buttons": [],
                "text_contrast": [],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert report.total_count == 1
        assert report.issues[0].rule == "input_missing_label"

    def test_div_with_button_role(self):
        data = {
            "a11y": {
                "images": [],
                "inputs": [],
                "div_buttons": [{"text": "Click me", "tag": "div"}],
                "text_contrast": [],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert report.total_count == 1
        assert report.issues[0].rule == "div_with_button_role"
        assert report.issues[0].severity == "warning"

    def test_low_contrast_detected(self):
        data = {
            "a11y": {
                "images": [],
                "inputs": [],
                "div_buttons": [],
                "text_contrast": [
                    {"text": "faint", "color": "rgb(150, 150, 150)", "background": "rgb(200, 200, 200)"},
                ],
            }
        }
        analyzer = UIUXAnalyzer(contrast_threshold=4.5)
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "wcag_contrast" for i in report.issues)

    def test_high_contrast_no_issue(self):
        data = {
            "a11y": {
                "images": [],
                "inputs": [],
                "div_buttons": [],
                "text_contrast": [
                    {"text": "clear", "color": "rgb(0, 0, 0)", "background": "rgb(255, 255, 255)"},
                ],
            }
        }
        analyzer = UIUXAnalyzer(contrast_threshold=4.5)
        report = analyzer.audit_dom_data(data, url="http://test")
        assert not any(i.rule == "wcag_contrast" for i in report.issues)


class TestUIUXAnalyzerInteraction:
    def test_button_too_small(self):
        data = {
            "interaction": {
                "buttons": [
                    {"text": "OK", "width": 30, "height": 20, "too_small": True},
                    {"text": "Big", "width": 60, "height": 50, "too_small": False},
                ],
                "focus_styles": [],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert report.total_count == 1
        assert report.issues[0].rule == "button_too_small"
        assert report.issues[0].severity == "warning"

    def test_focus_outline_removed(self):
        data = {
            "interaction": {
                "buttons": [],
                "focus_styles": [{"outline_removed": True}],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "focus_outline_removed" for i in report.issues)


class TestUIUXAnalyzerLayout:
    def test_element_overlap(self):
        data = {
            "layout": {
                "overlapping": [{"a": "button", "b": "input"}],
                "truncated": [],
                "viewport_overflow": False,
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "element_overlap" and i.severity == "critical" for i in report.issues)

    def test_viewport_overflow(self):
        data = {
            "layout": {
                "overlapping": [],
                "truncated": [],
                "viewport_overflow": True,
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "viewport_overflow" for i in report.issues)

    def test_text_truncation_info(self):
        data = {
            "layout": {
                "overlapping": [],
                "truncated": [{"tag": "div", "text": "long text..."}],
                "viewport_overflow": False,
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "text_truncation" and i.severity == "info" for i in report.issues)


class TestUIUXAnalyzerUXAntipattern:
    def test_form_no_validation(self):
        data = {
            "ux": {
                "forms": [
                    {"action": "/submit", "input_count": 3, "required_count": 0, "no_validation": True},
                ],
                "destructive_without_confirm": [],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "form_no_validation" for i in report.issues)

    def test_destructive_no_confirm(self):
        data = {
            "ux": {
                "forms": [],
                "destructive_without_confirm": [
                    {"text": "delete", "tag": "button"},
                ],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")
        assert any(i.rule == "destructive_no_confirm" and i.severity == "critical" for i in report.issues)


class TestUIUXAnalyzerFailureSafety:
    def test_empty_data_no_crash(self):
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data({}, url="http://test")
        assert report.total_count == 0
        assert report.passed is True

    def test_probe_exception_returns_empty(self):
        class BadPage:
            def evaluate(self, _script):
                raise RuntimeError("page gone")

        analyzer = UIUXAnalyzer()
        report = analyzer.audit(BadPage(), url="http://test")
        assert report.total_count == 0

    def test_malformed_data_no_crash(self):
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data({"a11y": "not a dict"}, url="http://test")
        assert report.total_count == 0


class TestUIUXAnalyzerColorParsing:
    def test_parse_rgb_color(self):
        rgb = UIUXAnalyzer._parse_color("rgb(255, 0, 0)")
        assert rgb == (255, 0, 0)

    def test_parse_hex_color(self):
        rgb = UIUXAnalyzer._parse_color("#ff0000")
        assert rgb == (255, 0, 0)

    def test_parse_invalid_color(self):
        assert UIUXAnalyzer._parse_color("red") is None
        assert UIUXAnalyzer._parse_color("") is None

    def test_contrast_ratio_black_white(self):
        ratio = UIUXAnalyzer._compute_contrast_ratio("rgb(0, 0, 0)", "rgb(255, 255, 255)")
        assert ratio is not None
        assert 20 < ratio < 22  # WCAG max ratio is 21

    def test_contrast_ratio_same_color(self):
        ratio = UIUXAnalyzer._compute_contrast_ratio("rgb(128, 128, 128)", "rgb(128, 128, 128)")
        assert ratio == 1.0


class TestUIUXAnalyzerWithMockPage:
    """模拟 Playwright Page 测试完整 audit 流程。"""

    def test_audit_with_mock_page(self):
        class MockPage:
            def __init__(self, data):
                self._data = data

            def evaluate(self, _script):
                return self._data

        data = {
            "a11y": {
                "images": [{"src": "a.png", "has_alt": False, "alt_value": ""}],
                "inputs": [],
                "div_buttons": [],
                "text_contrast": [],
            },
            "interaction": {"buttons": [], "focus_styles": []},
            "layout": {"overlapping": [], "truncated": [], "viewport_overflow": False},
            "ux": {"forms": [], "destructive_without_confirm": []},
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit(MockPage(data), url="http://localhost:8501")
        assert report.url == "http://localhost:8501"
        assert report.critical_count == 1
        assert report.passed is False


# ============================================================
# VisualRegressionChecker 测试
# ============================================================

class TestVisualRegressionModels:
    def test_changed_region(self):
        region = ChangedRegion(x=10, y=20, width=50, height=60, diff_ratio=0.5)
        assert region.x == 10
        assert region.diff_ratio == 0.5

    def test_diff_result(self):
        result = DiffResult(
            pixel_diff_ratio=0.05,
            changed_regions=[],
            has_display_error=False,
            baseline_size=(800, 600),
            current_size=(800, 600),
        )
        assert result.pixel_diff_ratio == 0.05
        assert result.baseline_size == (800, 600)


class TestVisualRegressionChecker:
    def test_identical_images(self, tmp_path):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img.save(baseline)
        img.save(current)

        checker = VisualRegressionChecker()
        result = checker.compare(baseline, current)
        assert result.pixel_diff_ratio == 0.0
        assert result.has_display_error is False
        assert result.changed_regions == []
        assert checker.is_regression(result) is False

    def test_different_images(self, tmp_path):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img_b = Image.new("RGB", (100, 100), color=(0, 0, 0))
        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img_a.save(baseline)
        img_b.save(current)

        checker = VisualRegressionChecker()
        result = checker.compare(baseline, current)
        assert result.pixel_diff_ratio > 0.9
        assert result.has_display_error is True
        assert checker.is_regression(result) is True

    def test_small_change_not_regression(self, tmp_path):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (200, 200), color=(255, 255, 255))
        img_b = img_a.copy()
        draw = ImageDraw.Draw(img_b)
        draw.rectangle((0, 0, 5, 5), fill=(0, 0, 0))  # tiny change

        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img_a.save(baseline)
        img_b.save(current)

        checker = VisualRegressionChecker(pixel_diff_threshold=0.01)
        result = checker.compare(baseline, current)
        assert result.pixel_diff_ratio < 0.01
        assert checker.is_regression(result) is False

    def test_size_mismatch(self, tmp_path):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img_b = Image.new("RGB", (200, 200), color=(255, 255, 255))
        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img_a.save(baseline)
        img_b.save(current)

        checker = VisualRegressionChecker()
        result = checker.compare(baseline, current)
        assert result.baseline_size == (100, 100)
        assert result.current_size == (200, 200)
        assert result.has_display_error is True

    def test_baseline_not_found(self, tmp_path):
        checker = VisualRegressionChecker()
        with pytest.raises(FileNotFoundError, match="Baseline"):
            checker.compare(tmp_path / "missing.png", tmp_path / "also_missing.png")

    def test_current_not_found(self, tmp_path):
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img = Image.new("RGB", (100, 100), color=(255, 255, 255))
        baseline = tmp_path / "baseline.png"
        img.save(baseline)

        checker = VisualRegressionChecker()
        with pytest.raises(FileNotFoundError, match="Current"):
            checker.compare(baseline, tmp_path / "missing.png")

    def test_regions_detected_on_partial_change(self, tmp_path):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (200, 200), color=(255, 255, 255))
        img_b = img_a.copy()
        draw = ImageDraw.Draw(img_b)
        draw.rectangle((0, 0, 100, 100), fill=(0, 0, 0))  # big change in top-left

        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img_a.save(baseline)
        img_b.save(current)

        checker = VisualRegressionChecker(region_grid_size=4)
        result = checker.compare(baseline, current)
        assert len(result.changed_regions) > 0
        # Top-left region should be detected
        top_left = [r for r in result.changed_regions if r.x == 0 and r.y == 0]
        assert len(top_left) > 0


class TestVisualRegressionCheckerThresholds:
    def test_custom_threshold(self, tmp_path):
        try:
            from PIL import Image, ImageDraw
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (100, 100), color=(255, 255, 255))
        img_b = img_a.copy()
        draw = ImageDraw.Draw(img_b)
        draw.rectangle((0, 0, 10, 10), fill=(0, 0, 0))  # 1% change

        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img_a.save(baseline)
        img_b.save(current)

        # Strict threshold: 0.005 → regression
        strict = VisualRegressionChecker(pixel_diff_threshold=0.005)
        result = strict.compare(baseline, current)
        assert strict.is_regression(result) is True

        # Loose threshold: 0.05 → not regression
        loose = VisualRegressionChecker(pixel_diff_threshold=0.05)
        result = loose.compare(baseline, current)
        assert loose.is_regression(result) is False
