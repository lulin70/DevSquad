"""UI/UX 巡检分析器：4 大检测维度。

借鉴 TraeMultiAgentSkill 的 uiux_analyzer.py 理念：
- 单次 Playwright page.evaluate() 收集所有 DOM 探针数据
- Python 侧规则匹配，生成结构化问题报告
- 失败安全：任一探针异常不影响其他探针

4 大维度：
1. 可访问性 (a11y): WCAG AA 对比度、img alt、form label、语义化标签
2. 交互质量 (interaction): 按钮最小尺寸、焦点可见性、加载反馈
3. 布局响应式 (layout): 元素重叠、文字截断、视口溢出
4. UX 反模式 (ux_antipattern): 强制注册、破坏性操作无确认、表单无校验
"""

from __future__ import annotations

import logging
from typing import Any

from .models import UIUXAuditReport, UIUXIssue

logger = logging.getLogger(__name__)


# Playwright 单次综合探针脚本：一次 evaluate 取齐所有 DOM 数据
_PROBE_SCRIPT = """
() => {
  const result = {
    a11y: { images: [], inputs: [], div_buttons: [], text_contrast: [] },
    interaction: { buttons: [], focus_styles: [] },
    layout: { overlapping: [], truncated: [], viewport_overflow: false },
    ux: { forms: [], destructive_without_confirm: [] }
  };

  // 1. A11y: img without alt
  document.querySelectorAll('img').forEach(img => {
    result.a11y.images.push({
      src: img.getAttribute('src') || '',
      has_alt: img.hasAttribute('alt'),
      alt_value: img.getAttribute('alt') || ''
    });
  });

  // 2. A11y: input without associated label
  document.querySelectorAll('input, textarea, select').forEach(input => {
    const id = input.getAttribute('id');
    const has_label = id ? !!document.querySelector(`label[for="${id}"]`) : false;
    const has_aria_label = input.hasAttribute('aria-label') || input.hasAttribute('aria-labelledby');
    const wrapped = input.closest('label');
    result.a11y.inputs.push({
      type: input.getAttribute('type') || input.tagName.toLowerCase(),
      has_label: has_label || has_aria_label || !!wrapped,
      id: id || ''
    });
  });

  // 3. A11y: div with role=button (should use <button>)
  document.querySelectorAll('div[role="button"]').forEach(div => {
    result.a11y.div_buttons.push({
      text: (div.textContent || '').trim().slice(0, 50),
      tag: 'div'
    });
  });

  // 4. A11y: text contrast (simplified — check computed color vs bg)
  const textElems = document.querySelectorAll('p, span, a, button, h1, h2, h3, h4, h5, h6, label');
  textElems.forEach((el, idx) => {
    if (idx >= 50) return;  // sample first 50
    const cs = window.getComputedStyle(el);
    const color = cs.color;
    const bg = cs.backgroundColor;
    if (color && bg && color !== 'rgba(0, 0, 0, 0)') {
      result.a11y.text_contrast.push({
        text: (el.textContent || '').trim().slice(0, 30),
        color: color,
        background: bg
      });
    }
  });

  // 5. Interaction: button min size (>=44x44)
  document.querySelectorAll('button, [role="button"], a.btn, .btn').forEach(btn => {
    const rect = btn.getBoundingClientRect();
    result.interaction.buttons.push({
      text: (btn.textContent || '').trim().slice(0, 30),
      width: Math.round(rect.width),
      height: Math.round(rect.height),
      too_small: rect.width < 44 || rect.height < 44
    });
  });

  // 6. Interaction: focus visibility (stylesheet check)
  const styleSheets = Array.from(document.styleSheets);
  let focus_outline_none = false;
  try {
    for (const sheet of styleSheets) {
      try {
        const rules = sheet.cssRules;
        for (const rule of rules) {
          if (rule.selectorText && rule.selectorText.includes(':focus') && rule.style) {
            const outline = rule.style.outline;
            if (outline === 'none' || outline === '') {
              focus_outline_none = true;
            }
          }
        }
      } catch (e) { /* CORS */ }
    }
  } catch (e) {}
  result.interaction.focus_styles = [{ outline_removed: focus_outline_none }];

  // 7. Layout: overlapping elements (sample buttons and inputs)
  const checkElems = Array.from(document.querySelectorAll('button, input, .card, .panel'));
  for (let i = 0; i < checkElems.length && i < 30; i++) {
    for (let j = i + 1; j < checkElems.length && j < 30; j++) {
      const r1 = checkElems[i].getBoundingClientRect();
      const r2 = checkElems[j].getBoundingClientRect();
      const overlap = !(r1.right < r2.left || r2.right < r1.left || r1.bottom < r2.top || r2.bottom < r1.top);
      if (overlap && r1.width > 10 && r1.height > 10 && r2.width > 10 && r2.height > 10) {
        result.layout.overlapping.push({
          a: (checkElems[i].tagName || '').toLowerCase(),
          b: (checkElems[j].tagName || '').toLowerCase()
        });
      }
    }
  }

  // 8. Layout: text truncation
  document.querySelectorAll('[style*="text-overflow"], .truncate, .text-truncate').forEach(el => {
    result.layout.truncated.push({
      tag: el.tagName.toLowerCase(),
      text: (el.textContent || '').trim().slice(0, 50)
    });
  });

  // 9. Layout: viewport overflow
  result.layout.viewport_overflow = document.body.scrollWidth > document.body.clientWidth;

  // 10. UX: forms without validation
  document.querySelectorAll('form').forEach(form => {
    const inputs = form.querySelectorAll('input, textarea, select');
    const required_count = form.querySelectorAll('[required]').length;
    result.ux.forms.push({
      action: form.getAttribute('action') || '',
      input_count: inputs.length,
      required_count: required_count,
      no_validation: inputs.length > 0 && required_count === 0
    });
  });

  // 11. UX: destructive ops without confirm
  document.querySelectorAll('button, a').forEach(btn => {
    const text = (btn.textContent || '').toLowerCase().trim();
    const onclick = btn.getAttribute('onclick') || '';
    const has_confirm = onclick.includes('confirm') || btn.hasAttribute('data-confirm');
    const is_destructive = ['delete', 'remove', 'destroy', 'drop'].some(kw => text.includes(kw));
    if (is_destructive && !has_confirm) {
      result.ux.destructive_without_confirm.push({
        text: text.slice(0, 30),
        tag: btn.tagName.toLowerCase()
      });
    }
  });

  return result;
}
"""


class UIUXAnalyzer:
    """UI/UX 巡检分析器。

    使用 Playwright 单次综合探针收集 DOM 数据，Python 侧规则匹配。
    失败安全：任一探针异常不影响其他探针。
    """

    def __init__(
        self,
        min_button_size: int = 44,
        contrast_threshold: float = 4.5,
        hsv_harsh_saturation_threshold: float = 0.6,
    ) -> None:
        self._min_button_size = min_button_size
        self._contrast_threshold = contrast_threshold
        self._hsv_harsh_sat_threshold = hsv_harsh_saturation_threshold

    def audit(self, page: Any, url: str = "") -> UIUXAuditReport:
        """对 Playwright Page 执行综合巡检。

        Args:
            page: Playwright Page 对象（同步或异步均可，需支持 evaluate）。
            url: 巡检 URL，用于报告。

        Returns:
            UIUXAuditReport 包含所有发现的问题。
        """
        try:
            data = page.evaluate(_PROBE_SCRIPT)
        except Exception as exc:
            logger.warning("UIUX probe failed: %s", exc)
            return UIUXAuditReport(url=url, issues=[])

        if not isinstance(data, dict):
            logger.warning("UIUX probe returned non-dict: %r", type(data))
            return UIUXAuditReport(url=url, issues=[])

        return self.audit_dom_data(data, url=url)

    def audit_dom_data(self, data: dict[str, Any], url: str = "") -> UIUXAuditReport:
        """对预先采集的 DOM 数据执行巡检（无 Playwright 依赖）。

        用于单元测试或离线分析。失败安全：任一维度异常不影响其他维度。
        """
        issues: list[UIUXIssue] = []
        for section, checker in [
            ("a11y", self._check_a11y),
            ("interaction", self._check_interaction),
            ("layout", self._check_layout),
            ("ux", self._check_ux_antipattern),
        ]:
            try:
                section_data = data.get(section, {})
                if not isinstance(section_data, dict):
                    logger.warning("UIUX section %s returned non-dict: %r", section, type(section_data))
                    continue
                issues.extend(checker(section_data))
            except Exception as exc:
                logger.warning("UIUX check %s failed: %s", section, exc)
        return UIUXAuditReport(url=url, issues=issues)

    def _check_a11y(self, a11y: dict[str, Any]) -> list[UIUXIssue]:
        issues: list[UIUXIssue] = []
        for img in a11y.get("images", []):
            if not img.get("has_alt"):
                issues.append(UIUXIssue(
                    severity="critical",
                    category="a11y",
                    rule="img_missing_alt",
                    element=f"img[src='{img.get('src', '')[:40]}']",
                    message="Image missing alt attribute",
                    fix="Add alt attribute describing the image purpose",
                    metric={"src": img.get("src", "")[:80]},
                ))

        for inp in a11y.get("inputs", []):
            if not inp.get("has_label"):
                issues.append(UIUXIssue(
                    severity="critical",
                    category="a11y",
                    rule="input_missing_label",
                    element=f"input#{inp.get('id', '')}[type={inp.get('type', '')}]",
                    message="Form input missing associated label",
                    fix="Add <label for=...> or aria-label attribute",
                    metric={"type": inp.get("type", "")},
                ))

        for div_btn in a11y.get("div_buttons", []):
            issues.append(UIUXIssue(
                severity="warning",
                category="a11y",
                rule="div_with_button_role",
                element=f"div[role=button]: '{div_btn.get('text', '')}'",
                message="Using <div role=button> instead of semantic <button>",
                fix="Use <button> element for accessibility",
                metric={},
            ))

        for text_item in a11y.get("text_contrast", []):
            ratio = self._compute_contrast_ratio(
                text_item.get("color", ""),
                text_item.get("background", ""),
            )
            if ratio is not None and ratio < self._contrast_threshold:
                issues.append(UIUXIssue(
                    severity="warning",
                    category="a11y",
                    rule="wcag_contrast",
                    element=f"text: '{text_item.get('text', '')}'",
                    message=f"Contrast ratio {ratio:.2f} below WCAG AA {self._contrast_threshold}",
                    fix="Increase color contrast between text and background",
                    metric={"ratio": round(ratio, 2), "required": self._contrast_threshold},
                ))

            hsv_issue = self._check_hsv_harsh_combination(
                text_item.get("color", ""),
                text_item.get("background", ""),
                text_item.get("text", ""),
            )
            if hsv_issue is not None:
                issues.append(hsv_issue)

        return issues

    def _check_hsv_harsh_combination(
        self,
        color_fg: str,
        color_bg: str,
        text: str,
    ) -> UIUXIssue | None:
        """检测 HSV 颜色空间中的刺眼配色（WCAG 补充）。

        WCAG luminance 可能放行高饱和度的互补色组合（如红绿），
        但这类配色在视觉上不舒适。HSV 检测捕获这些情况：
        - 高饱和度红绿组合（色相差 ~180°）
        - 高饱和度蓝黄组合（色相差 ~180°）
        """
        rgb_fg = self._parse_color(color_fg)
        rgb_bg = self._parse_color(color_bg)
        if rgb_fg is None or rgb_bg is None:
            return None

        h_fg, s_fg, _ = self._rgb_to_hsv(rgb_fg)
        h_bg, s_bg, _ = self._rgb_to_hsv(rgb_bg)

        if s_fg < self._hsv_harsh_sat_threshold or s_bg < self._hsv_harsh_sat_threshold:
            return None

        hue_diff = abs(h_fg - h_bg)
        if hue_diff > 180:
            hue_diff = 360 - hue_diff

        harsh_pairs = [
            (0, 120, "red-green"),
            (120, 0, "green-red"),
            (0, 240, "red-blue"),
            (240, 0, "blue-red"),
            (60, 240, "yellow-blue"),
            (240, 60, "blue-yellow"),
        ]

        for h1, h2, label in harsh_pairs:
            d1 = abs(h_fg - h1)
            if d1 > 180:
                d1 = 360 - d1
            d2 = abs(h_bg - h2)
            if d2 > 180:
                d2 = 360 - d2
            if d1 < 30 and d2 < 30 and hue_diff >= 120:
                return UIUXIssue(
                    severity="info",
                    category="a11y",
                    rule="hsv_harsh_combination",
                    element=f"text: '{text}'",
                    message=f"Harsh color combination ({label}) may cause visual discomfort despite passing WCAG",
                    fix="Use less saturated colors or adjust hue to reduce visual harshness",
                    metric={
                        "hue_fg": round(h_fg, 1),
                        "hue_bg": round(h_bg, 1),
                        "sat_fg": round(s_fg, 2),
                        "sat_bg": round(s_bg, 2),
                        "hue_diff": round(hue_diff, 1),
                    },
                )

        return None

    def _check_interaction(self, interaction: dict[str, Any]) -> list[UIUXIssue]:
        issues: list[UIUXIssue] = []
        for btn in interaction.get("buttons", []):
            if btn.get("too_small"):
                issues.append(UIUXIssue(
                    severity="warning",
                    category="interaction",
                    rule="button_too_small",
                    element=f"button: '{btn.get('text', '')}'",
                    message=f"Button size {btn.get('width', 0)}x{btn.get('height', 0)} below {self._min_button_size}px",
                    fix="Increase button size to at least 44x44 pixels for touch targets",
                    metric={
                        "width": btn.get("width", 0),
                        "height": btn.get("height", 0),
                        "required": self._min_button_size,
                    },
                ))

        for focus in interaction.get("focus_styles", []):
            if focus.get("outline_removed"):
                issues.append(UIUXIssue(
                    severity="warning",
                    category="interaction",
                    rule="focus_outline_removed",
                    element=":focus",
                    message="Focus outline removed without replacement",
                    fix="Provide alternative focus indicator (box-shadow, border, etc.)",
                    metric={},
                ))

        return issues

    def _check_layout(self, layout: dict[str, Any]) -> list[UIUXIssue]:
        issues: list[UIUXIssue] = []

        overlap_count = len(layout.get("overlapping", []))
        if overlap_count > 0:
            issues.append(UIUXIssue(
                severity="critical",
                category="layout",
                rule="element_overlap",
                element="multiple",
                message=f"{overlap_count} overlapping element pairs detected",
                fix="Adjust layout to prevent element overlap",
                metric={"overlap_count": overlap_count},
            ))

        for trunc in layout.get("truncated", []):
            issues.append(UIUXIssue(
                severity="info",
                category="layout",
                rule="text_truncation",
                element=f"{trunc.get('tag', '')}: '{trunc.get('text', '')}'",
                message="Text truncation in use — verify content is not hidden",
                fix="Ensure truncated text has tooltip or expandable view",
                metric={},
            ))

        if layout.get("viewport_overflow"):
            issues.append(UIUXIssue(
                severity="critical",
                category="layout",
                rule="viewport_overflow",
                element="body",
                message="Horizontal viewport overflow detected",
                fix="Ensure content fits within viewport or use responsive layout",
                metric={
                    "scroll_width": "overflow",
                    "client_width": "viewport",
                },
            ))

        return issues

    def _check_ux_antipattern(self, ux: dict[str, Any]) -> list[UIUXIssue]:
        issues: list[UIUXIssue] = []

        for form in ux.get("forms", []):
            if form.get("no_validation"):
                issues.append(UIUXIssue(
                    severity="warning",
                    category="ux_antipattern",
                    rule="form_no_validation",
                    element=f"form[action={form.get('action', '')}]",
                    message=f"Form with {form.get('input_count', 0)} inputs has no required fields",
                    fix="Add required attribute or client-side validation",
                    metric={"input_count": form.get("input_count", 0)},
                ))

        for destructive in ux.get("destructive_without_confirm", []):
            issues.append(UIUXIssue(
                severity="critical",
                category="ux_antipattern",
                rule="destructive_no_confirm",
                element=f"{destructive.get('tag', '')}: '{destructive.get('text', '')}'",
                message="Destructive action without confirmation",
                fix="Add confirm dialog or data-confirm attribute",
                metric={},
            ))

        return issues

    @staticmethod
    def _compute_contrast_ratio(color1: str, color2: str) -> float | None:
        """计算两个 CSS 颜色的对比度（WCAG 公式）。

        简化实现：支持 rgb() 和 #hex 格式。复杂颜色返回 None。
        """
        rgb1 = UIUXAnalyzer._parse_color(color1)
        rgb2 = UIUXAnalyzer._parse_color(color2)
        if rgb1 is None or rgb2 is None:
            return None

        l1 = UIUXAnalyzer._relative_luminance(rgb1)
        l2 = UIUXAnalyzer._relative_luminance(rgb2)
        lighter = max(l1, l2)
        darker = min(l1, l2)
        return (lighter + 0.05) / (darker + 0.05)

    @staticmethod
    def _parse_color(color: str) -> tuple[int, int, int] | None:
        """解析 CSS 颜色为 (r, g, b)。支持 rgb() 和 #hex。"""
        if not color:
            return None
        color = color.strip()
        if color.startswith("rgb"):
            try:
                parts = color[color.index("(") + 1:color.rindex(")")].split(",")
                return (int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                return None
        if color.startswith("#") and len(color) == 7:
            try:
                return (int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16))
            except ValueError:
                return None
        return None

    @staticmethod
    def _relative_luminance(rgb: tuple[int, int, int]) -> float:
        """WCAG 相对亮度公式。"""
        def channel(c: int) -> float:
            s = c / 255.0
            return s / 12.92 if s <= 0.03928 else ((s + 0.055) / 1.055) ** 2.4

        r, g, b = rgb
        return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)

    @staticmethod
    def _rgb_to_hsv(rgb: tuple[int, int, int]) -> tuple[float, float, float]:
        """RGB 转 HSV 颜色空间。

        Returns:
            (hue: 0-360, saturation: 0.0-1.0, value: 0.0-1.0)
        """
        r, g, b = rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0
        max_val = max(r, g, b)
        min_val = min(r, g, b)
        diff = max_val - min_val

        if diff == 0:
            hue = 0.0
        elif max_val == r:
            hue = 60.0 * (((g - b) / diff) % 6)
        elif max_val == g:
            hue = 60.0 * (((b - r) / diff) + 2)
        else:
            hue = 60.0 * (((r - g) / diff) + 4)

        if hue < 0:
            hue += 360.0

        saturation = diff / max_val if max_val > 0 else 0.0
        return (hue, saturation, max_val)
