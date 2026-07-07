"""P1-2 QA 集成测试：验证 UIUXAnalyzer/VisualRegressionChecker 接入 dispatcher。

确保无幽灵功能：组件可在 qa_enabled=True 时通过 dispatcher 访问和使用。
"""

from __future__ import annotations

import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher


class TestQAIntegration:
    """验证 QA 组件接入 dispatch pipeline。"""

    def test_qa_disabled_by_default(self):
        """默认 qa_enabled=False，组件不存在。"""
        d = MultiAgentDispatcher(enable_warmup=False, enable_memory=False, enable_skillify=False)
        assert d.qa_enabled is False
        assert not hasattr(d, "uiux_analyzer") or d.uiux_analyzer is None
        assert not hasattr(d, "visual_regression_checker") or d.visual_regression_checker is None

    def test_qa_enabled_creates_components(self):
        """qa_enabled=True 时，UIUXAnalyzer 和 VisualRegressionChecker 被创建。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            qa_enabled=True,
        )
        assert d.qa_enabled is True
        assert d.uiux_analyzer is not None
        assert d.visual_regression_checker is not None

    def test_qa_audit_url_without_analyzer_raises(self):
        """qa_enabled=False 时调用 qa_audit_url 抛 RuntimeError。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )
        with pytest.raises(RuntimeError, match="UIUXAnalyzer not enabled"):
            d.qa_audit_url("http://localhost:8501")

    def test_qa_visual_regression_without_checker_raises(self):
        """qa_enabled=False 时调用 qa_visual_regression 抛 RuntimeError。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
        )
        with pytest.raises(RuntimeError, match="VisualRegressionChecker not enabled"):
            d.qa_visual_regression("a.png", "b.png")

    def test_qa_visual_regression_works_when_enabled(self, tmp_path):
        """qa_enabled=True 时 qa_visual_regression 可成功调用。"""
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        img_a = Image.new("RGB", (50, 50), color=(255, 255, 255))
        img_b = Image.new("RGB", (50, 50), color=(255, 255, 255))
        baseline = tmp_path / "baseline.png"
        current = tmp_path / "current.png"
        img_a.save(baseline)
        img_b.save(current)

        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            qa_enabled=True,
        )
        result = d.qa_visual_regression(str(baseline), str(current))
        assert result.pixel_diff_ratio == 0.0
        assert result.has_display_error is False

    def test_qa_analyzer_audit_dom_data_via_dispatcher(self):
        """通过 dispatcher 访问 uiux_analyzer.audit_dom_data。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            qa_enabled=True,
        )
        data = {
            "a11y": {
                "images": [{"src": "logo.png", "has_alt": False, "alt_value": ""}],
                "inputs": [],
                "div_buttons": [],
                "text_contrast": [],
            },
            "interaction": {"buttons": [], "focus_styles": []},
            "layout": {"overlapping": [], "truncated": [], "viewport_overflow": False},
            "ux": {"forms": [], "destructive_without_confirm": []},
        }
        report = d.uiux_analyzer.audit_dom_data(data, url="http://test")
        assert report.critical_count == 1
        assert report.passed is False

    def test_qa_pixel_diff_threshold_configurable(self):
        """qa_pixel_diff_threshold 可配置。"""
        d = MultiAgentDispatcher(
            enable_warmup=False,
            enable_memory=False,
            enable_skillify=False,
            qa_enabled=True,
            qa_pixel_diff_threshold=0.05,
        )
        assert d.visual_regression_checker._pixel_diff_threshold == 0.05
