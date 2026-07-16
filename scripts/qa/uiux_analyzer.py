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

V4.1.0 extensions:
- P1-UI-1: 6 anti-pattern bans (taste-skill) — see check_css_antipatterns()
- P1-UI-3: OKLCH color space parsing & conversion
- P2-UI-4: 4pt grid spacing detection
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

from .models import UIUXAuditReport, UIUXIssue

logger = logging.getLogger(__name__)


# V4.1.0 P1-UI-1: Banned font families (taste-skill Anti-pattern Bans)
_BANNED_FONT_FAMILIES: tuple[str, ...] = (
    "inter",
    "roboto",
    "dm sans",
)

# V4.1.0 P2-UI-4: 4pt grid — multiples of 4 are valid (0 included as no-spacing)
_4PT_GRID_UNIT = 4


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

        # V4.1.0 P1-UI-1: taste-skill Anti-pattern Bans (6 CSS rules)
        css_text = ux.get("css_text", "") or ux.get("css", "")
        if isinstance(css_text, str) and css_text:
            issues.extend(self.check_css_antipatterns(css_text))

        return issues

    # ── V4.1.0 P1-UI-1: Anti-pattern Bans (taste-skill) ────────────────────────

    def check_css_antipatterns(self, css_text: str) -> list[UIUXIssue]:
        """Run all 6 taste-skill Anti-pattern Bans against CSS text.

        Args:
            css_text: Raw CSS source to scan.

        Returns:
            List of UIUXIssue detected by the 6 anti-pattern rules.
        """
        issues: list[UIUXIssue] = []
        for checker in (
            self._check_border_left_accent,
            self._check_gradient_text,
            self._check_glassmorphism_overuse,
            self._check_overused_fonts,
            self._check_purple_blue_gradient,
            self._check_nested_cards,
        ):
            try:
                issues.extend(checker(css_text))
            except Exception as exc:  # noqa: BLE001
                logger.warning("Anti-pattern checker %s failed: %s", checker.__name__, exc)
        return issues

    def _check_border_left_accent(self, css_text: str) -> list[UIUXIssue]:
        """Detect `border-left: Npx solid <color>` accent stripes.

        The left-accent stripe is an overused AI pattern for callout boxes.
        """
        issues: list[UIUXIssue] = []
        pattern = re.compile(
            r"border-left\s*:\s*(\d+)px\s+solid\s+([#\w][^;}]*)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(css_text):
            width = int(match.group(1))
            if width >= 2:  # only flag visible accent stripes (>=2px)
                issues.append(UIUXIssue(
                    severity="warning",
                    category="ux_antipattern",
                    rule="border_left_accent_stripes",
                    element=f"border-left:{width}px solid {match.group(2).strip()}",
                    message=(
                        "border-left accent stripe is an overused AI pattern; "
                        "use a dedicated callout component instead"
                    ),
                    fix="Replace left-accent stripe with a structured callout/banner component",
                    metric={"width": width, "color": match.group(2).strip()},
                ))
        return issues

    def _check_gradient_text(self, css_text: str) -> list[UIUXIssue]:
        """Detect `background-clip: text` combined with `linear-gradient`/`radial-gradient`."""
        issues: list[UIUXIssue] = []
        # Split CSS into rule blocks so we can correlate background-clip with gradient
        # within the same selector block.
        block_pattern = re.compile(r"([^{}]*?)\{([^{}]*)\}", re.DOTALL)
        for selector, body in block_pattern.findall(css_text):
            has_clip_text = "background-clip" in body and "text" in body
            has_gradient = "gradient(" in body.lower()
            if has_clip_text and has_gradient:
                # Extract the gradient for the metric
                grad_match = re.search(r"(linear|radial|conic)-gradient\([^)]*\)", body, re.IGNORECASE)
                gradient_value = grad_match.group(0) if grad_match else "gradient"
                issues.append(UIUXIssue(
                    severity="error",
                    category="ux_antipattern",
                    rule="gradient_text",
                    element=selector.strip()[:60] or "selector",
                    message=(
                        "Gradient text (background-clip: text + gradient) is banned; "
                        "reduces readability and accessibility"
                    ),
                    fix="Use a solid color or a subtle text-shadow instead of gradient text",
                    metric={"gradient": gradient_value[:80]},
                ))
        return issues

    def _check_glassmorphism_overuse(self, css_text: str) -> list[UIUXIssue]:
        """Detect `backdrop-filter: blur()` usage exceeding 2 instances."""
        issues: list[UIUXIssue] = []
        matches = re.findall(r"backdrop-filter\s*:\s*blur\(", css_text, re.IGNORECASE)
        count = len(matches)
        if count > 2:
            issues.append(UIUXIssue(
                severity="warning",
                category="ux_antipattern",
                rule="glassmorphism_overuse",
                element="backdrop-filter",
                message=(
                    f"Glassmorphism used {count} times, max 2 recommended; "
                    "overuse hurts readability and performance"
                ),
                fix="Limit backdrop-filter: blur() to at most 2 instances per page",
                metric={"count": count, "max_recommended": 2},
            ))
        return issues

    def _check_overused_fonts(self, css_text: str) -> list[UIUXIssue]:
        """Detect banned font-family declarations (Inter / Roboto / DM Sans)."""
        issues: list[UIUXIssue] = []
        pattern = re.compile(r"font-family\s*:\s*([^;}]+)", re.IGNORECASE)
        for match in pattern.finditer(css_text):
            family_decl = match.group(1).strip().strip('"').strip("'").lower()
            for banned in _BANNED_FONT_FAMILIES:
                if banned in family_decl:
                    issues.append(UIUXIssue(
                        severity="warning",
                        category="ux_antipattern",
                        rule="overused_fonts",
                        element=f"font-family: {match.group(1).strip()[:60]}",
                        message=(
                            f"Overused font '{banned}' detected; "
                            "these fonts signal generic AI-generated UI"
                        ),
                        fix="Choose a more distinctive font family that matches the brand",
                        metric={"font": banned, "declaration": match.group(1).strip()[:80]},
                    ))
                    break  # one banned font per declaration is enough
        return issues

    def _check_purple_blue_gradient(self, css_text: str) -> list[UIUXIssue]:
        """Detect purple/blue gradient backgrounds (signature AI pattern).

        Parses hex colors and rgb() inside the gradient stops and converts
        each to HSV. A stop is considered purple when its hue is in
        240-300°, and blue when its hue is in 180-240°. Named color keywords
        (purple/violet/indigo/blue) are also accepted as a fallback when the
        color value cannot be parsed.
        """
        issues: list[UIUXIssue] = []
        gradient_pattern = re.compile(
            r"(linear|radial|conic)-gradient\s*\(([^)]*)\)",
            re.IGNORECASE,
        )
        purple_keywords = ("purple", "violet", "indigo")
        blue_keywords = ("blue", "navy", "royalblue")
        for grad_type, grad_body in gradient_pattern.findall(css_text):
            body_lower = grad_body.lower()
            has_purple = any(kw in body_lower for kw in purple_keywords)
            has_blue = any(kw in body_lower for kw in blue_keywords)
            # Also parse hex colors and rgb() for HSV-based detection
            hex_colors = re.findall(r"#[0-9a-fA-F]{6}\b", grad_body)
            rgb_colors = re.findall(r"rgb\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*\)", grad_body, re.IGNORECASE)
            for hex_str in hex_colors:
                rgb = UIUXAnalyzer._parse_color(hex_str)
                if rgb is None:
                    continue
                hue, _sat, _val = UIUXAnalyzer._rgb_to_hsv(rgb)
                if 240 <= hue <= 300:
                    has_purple = True
                elif 180 <= hue < 240:
                    has_blue = True
            for rgb_str in rgb_colors:
                rgb = UIUXAnalyzer._parse_color(rgb_str)
                if rgb is None:
                    continue
                hue, _sat, _val = UIUXAnalyzer._rgb_to_hsv(rgb)
                if 240 <= hue <= 300:
                    has_purple = True
                elif 180 <= hue < 240:
                    has_blue = True
            if has_purple and has_blue:
                full_gradient = f"{grad_type}-gradient({grad_body})"[:80]
                issues.append(UIUXIssue(
                    severity="warning",
                    category="ux_antipattern",
                    rule="purple_blue_gradient",
                    element=full_gradient,
                    message=(
                        "Purple-blue gradient is the signature AI-generated UI pattern; "
                        "use a more intentional palette"
                    ),
                    fix="Replace purple-blue gradient with a brand-aligned color pair",
                    metric={"gradient": full_gradient},
                ))
        return issues

    def _check_nested_cards(self, css_text: str) -> list[UIUXIssue]:
        """Detect `.card .card` nested selectors (visual hierarchy anti-pattern)."""
        issues: list[UIUXIssue] = []
        # Match selectors like ".card .card", ".card .card .card", etc.
        pattern = re.compile(r"(^|[^.\w-])(\.card(?:\s+\.card)+)", re.MULTILINE)
        for match in pattern.finditer(css_text):
            selector = match.group(2)
            nesting_level = selector.count(".card")
            issues.append(UIUXIssue(
                severity="warning",
                category="ux_antipattern",
                rule="nested_cards",
                element=selector,
                message=(
                    f"Nested .card selector (depth {nesting_level}) detected; "
                    "card-in-card layout breaks visual hierarchy"
                ),
                fix="Use distinct component types (e.g. .card > .panel) instead of nested cards",
                metric={"nesting_level": nesting_level, "selector": selector},
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
        """解析 CSS 颜色为 (r, g, b)。支持 rgb() / #hex / oklch()。"""
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
        # V4.1.0 P1-UI-3: OKLCH color space support
        if color.lower().startswith("oklch"):
            oklch = UIUXAnalyzer._parse_oklch_color(color)
            if oklch is None:
                return None
            return UIUXAnalyzer._oklch_to_rgb(*oklch)
        return None

    # ── V4.1.0 P1-UI-3: OKLCH color space ───────────────────────────────────────

    @staticmethod
    def _parse_oklch_color(color_str: str) -> tuple[float, float, float] | None:
        """Parse an `oklch(L C H)` CSS color string into (L, C, H).

        Args:
            color_str: CSS color string, e.g. `oklch(0.7 0.15 250)`.

        Returns:
            Tuple (L: 0-1, C: 0-0.4+, H: 0-360) or None when the format
            is invalid.
        """
        if not color_str:
            return None
        text = color_str.strip()
        if not text.lower().startswith("oklch"):
            return None
        try:
            inner = text[text.index("(") + 1:text.rindex(")")]
        except ValueError:
            return None
        parts = [p.strip() for p in inner.split() if p.strip()]
        if len(parts) != 3:
            return None
        try:
            l_raw = float(parts[0])
            c_raw = float(parts[1])
            h_raw = float(parts[2])
        except ValueError:
            return None
        # Reject NaN/inf — they parse as floats but are not valid colors.
        if not (0.0 <= l_raw <= 1.0):
            return None
        if c_raw < 0.0:
            return None
        if not (0.0 <= h_raw <= 360.0):
            return None
        return (l_raw, c_raw, h_raw)

    @staticmethod
    def _oklch_to_rgb(
        lightness: float, chroma: float, h_deg: float
    ) -> tuple[int, int, int]:
        """Convert OKLCH (L, C, H) to 8-bit sRGB (r, g, b).

        Pipeline: OKLCH → OKLab → l'ms' (cube roots) → LMS (cube) → linear
        sRGB → sRGB. The implementation is a simplified approximation
        (sufficient for taste-skill detection), not a color-management-grade
        conversion.
        """
        h_rad = math.radians(h_deg)
        # OKLab from OKLCH
        lab_l = lightness
        lab_a = chroma * math.cos(h_rad)
        lab_b = chroma * math.sin(h_rad)

        # OKLab → l'ms' (cube roots of LMS)
        l_prime = lab_l + 0.3963377774 * lab_a + 0.2158037573 * lab_b
        m_prime = lab_l - 0.1055613458 * lab_a - 0.0638541728 * lab_b
        s_prime = lab_l - 0.0894841775 * lab_a - 1.2914855480 * lab_b

        # Cube l'ms' to get LMS
        l_cubed = l_prime ** 3
        m_cubed = m_prime ** 3
        s_cubed = s_prime ** 3

        # LMS → linear sRGB
        lin_r = +4.0767416621 * l_cubed - 3.3077115913 * m_cubed + 0.2309699292 * s_cubed
        lin_g = -1.2684380046 * l_cubed + 2.6097573513 * m_cubed - 0.3413193965 * s_cubed
        lin_b = -0.0041960863 * l_cubed - 0.7034186147 * m_cubed + 1.7076147010 * s_cubed

        def to_srgb_channel(linear: float) -> float:
            linear = max(0.0, min(1.0, linear))
            return linear if linear <= 0.0031308 else 1.055 * (linear ** (1.0 / 2.4)) - 0.055

        r = to_srgb_channel(lin_r)
        g = to_srgb_channel(lin_g)
        b = to_srgb_channel(lin_b)
        return (
            max(0, min(255, round(r * 255))),
            max(0, min(255, round(g * 255))),
            max(0, min(255, round(b * 255))),
        )

    @staticmethod
    def _rgb_to_oklch(
        r: int, g: int, b: int
    ) -> tuple[float, float, float]:
        """Convert 8-bit sRGB (r, g, b) to OKLCH (L, C, H).

        Pipeline: sRGB → linear sRGB → OKLab → OKLCH. The reverse of
        :meth:`_oklch_to_rgb`. Simplified approximation.
        """
        def to_linear(channel_8bit: int) -> float:
            s = channel_8bit / 255.0
            return s / 12.92 if s <= 0.04045 else ((s + 0.055) / 1.055) ** 2.4

        lin_r = to_linear(r)
        lin_g = to_linear(g)
        lin_b = to_linear(b)

        l_ = 0.4122214708 * lin_r + 0.5363325363 * lin_g + 0.0514459929 * lin_b
        m_ = 0.2119034982 * lin_r + 0.6806995451 * lin_g + 0.1073969566 * lin_b
        s_ = 0.0883024619 * lin_r + 0.2817188376 * lin_g + 0.6299787005 * lin_b

        l_ = l_ ** (1.0 / 3.0) if l_ > 0 else 0.0
        m_ = m_ ** (1.0 / 3.0) if m_ > 0 else 0.0
        s_ = s_ ** (1.0 / 3.0) if s_ > 0 else 0.0

        lab_l = 0.2104542553 * l_ + 0.7936177850 * m_ - 0.0040720468 * s_
        lab_a = 1.9779984951 * l_ - 2.4285922050 * m_ + 0.4505937099 * s_
        lab_b = 0.0259040371 * l_ + 0.7827717662 * m_ - 0.8086757660 * s_

        chroma = math.sqrt(lab_a * lab_a + lab_b * lab_b)
        hue = math.degrees(math.atan2(lab_b, lab_a))
        if hue < 0:
            hue += 360.0
        return (lab_l, chroma, hue)

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

    # ── V4.1.0 P2-UI-4: 4pt grid spacing ────────────────────────────────────────

    def check_4pt_grid(self, css_text: str) -> list[UIUXIssue]:
        """Run the 4pt-grid spacing check against CSS text.

        Args:
            css_text: Raw CSS source to scan.

        Returns:
            List of UIUXIssue for each spacing value that is not on the
            4pt grid (4/8/12/16/20/24/...).
        """
        return self._check_4pt_grid(css_text)

    def _check_4pt_grid(self, css_text: str) -> list[UIUXIssue]:
        """Detect spacing values that are not multiples of 4 (4pt grid).

        Scans `margin`, `padding`, and `gap` declarations. Supports `px`,
        `rem` (1rem = 16px), and `em` (uses parent font-size 16px by
        convention). `0` is always valid.
        """
        issues: list[UIUXIssue] = []
        if not css_text:
            return issues
        # Match spacing properties with px/rem/em values
        # Example: margin: 8px 12px 4px; padding-top: 7rem; gap: 13em;
        pattern = re.compile(
            r"(margin(?:-top|-right|-bottom|-left)?|"
            r"padding(?:-top|-right|-bottom|-left)?|"
            r"gap|row-gap|column-gap)\s*:\s*([^;{}]+)",
            re.IGNORECASE,
        )
        for match in pattern.finditer(css_text):
            prop = match.group(1).strip().lower()
            value_part = match.group(2)
            # Split shorthand (e.g. "8px 12px 4px 16px")
            for token in value_part.split():
                token = token.strip().rstrip(",")
                if not token:
                    continue
                px_value = self._spacing_token_to_px(token)
                if px_value is None:
                    continue  # unsupported unit (e.g. "%", "vw"), skip
                # 0 is always valid (no spacing)
                if px_value == 0:
                    continue
                if px_value % _4PT_GRID_UNIT != 0:
                    issues.append(UIUXIssue(
                        severity="warning",
                        category="layout",
                        rule="spacing_4pt_grid",
                        element=f"{prop}: {token}",
                        message=(
                            f"Spacing {token} ({px_value}px) is not on the "
                            "4pt grid (use multiples of 4)"
                        ),
                        fix="Use 4pt grid values: 4, 8, 12, 16, 20, 24, 28, 32, ...",
                        metric={
                            "property": prop,
                            "token": token,
                            "px": px_value,
                            "grid_unit": _4PT_GRID_UNIT,
                        },
                    ))
        return issues

    @staticmethod
    def _spacing_token_to_px(token: str) -> float | None:
        """Convert a CSS spacing token to a pixel value.

        Supports `px`, `rem` (1rem = 16px), `em` (1em = 16px default).
        Returns None when the unit is unsupported or the value is invalid.
        """
        token = token.strip().lower()
        if not token:
            return None
        try:
            if token.endswith("px"):
                return float(token[:-2])
            if token.endswith("rem"):
                return float(token[:-3]) * 16.0
            if token.endswith("em"):
                return float(token[:-2]) * 16.0
            # bare number — assume px
            return float(token)
        except ValueError:
            return None
