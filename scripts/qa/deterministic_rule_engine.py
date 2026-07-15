"""DeterministicRuleEngine — 46 deterministic UI/UX rules (no LLM).

Inspired by Paul Bakaus/impeccable's 46 deterministic detector rules.
Rules are organized by 7 design pillars (from impeccable):
  1. Typography (8 rules)
  2. Color (8 rules)
  3. Spatial design (6 rules)
  4. Responsiveness (6 rules)
  5. Interactions (8 rules)
  6. Motion (5 rules)
  7. UX writing (5 rules)

Each rule's check_fn receives (probes, dials, context) and returns list[UIUXIssue].
Rules gracefully degrade when probe data is missing (return empty list).

Integrates with TasteDials for threshold adjustment:
  - dials.adjust_threshold(rule_id, base_threshold) scales thresholds
  - a11y rules (color_contrast, aria_label) are NEVER adjusted

V4.1.0 (UI-P0-1): Initial implementation — 46 rules.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from .models import UIUXIssue
from .taste_dials import TasteDials

# ── 7 Design Pillars (from impeccable) ────────────────────────────────────────

SEVEN_PILLARS: tuple[str, ...] = (
    "typography",
    "color",
    "spatial",
    "responsiveness",
    "interactions",
    "motion",
    "ux_writing",
)

# Map 7 pillars to DevSquad's 4 existing categories (backward compat)
PILLAR_TO_CATEGORY: dict[str, str] = {
    "typography": "a11y",
    "color": "a11y",
    "spatial": "layout",
    "responsiveness": "layout",
    "interactions": "interaction",
    "motion": "interaction",
    "ux_writing": "ux_antipattern",
}

# Severity levels
SEVERITY_ERROR = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


# ── Data Structures ───────────────────────────────────────────────────────────

CheckFn = Callable[[dict[str, Any], TasteDials, dict[str, Any]], list[UIUXIssue]]


@dataclass
class DesignRule:
    """A single deterministic UI/UX rule.

    Attributes:
        rule_id: Unique identifier (e.g. "typography_line_height").
        pillar: One of SEVEN_PILLARS.
        severity: "critical" | "warning" | "info".
        check_fn: Function (probes, dials, context) -> list[UIUXIssue].
        fix_hint: Human-readable fix suggestion.
    """

    rule_id: str
    pillar: str
    severity: str
    check_fn: CheckFn
    fix_hint: str


# ── Helper: safe probe access ─────────────────────────────────────────────────


def _safe_get(probes: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict, returning default if any key is missing."""
    current: Any = probes
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is None:
            return default
    return current


# ── Typography Rules (8) ──────────────────────────────────────────────────────


def _check_typography_line_height(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check line-height is within 1.4-1.8 range."""
    elements = _safe_get(probes, "typography", "text_styles", default=[])
    if not elements:
        return []
    base_min = 1.4
    adjusted_min = dials.adjust_threshold("typography_line_height", base_min)
    issues = []
    for el in elements:
        lh = el.get("line_height", 0)
        if lh and lh < adjusted_min:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="a11y",
                rule="typography_line_height",
                element=el.get("tag", "unknown"),
                message=f"line-height {lh:.2f} below minimum {adjusted_min:.2f}",
                fix="Increase line-height to at least 1.4 for readability.",
                metric={"line_height": lh, "min_required": adjusted_min},
            ))
    return issues


def _check_typography_font_size_min(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check minimum font size is 14px."""
    elements = _safe_get(probes, "typography", "text_styles", default=[])
    if not elements:
        return []
    base_min = 14.0
    adjusted_min = dials.adjust_threshold("typography_font_size", base_min)
    issues = []
    for el in elements:
        size = el.get("font_size_px", 0)
        if size and size < adjusted_min:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="a11y",
                rule="typography_font_size_min",
                element=el.get("tag", "unknown"),
                message=f"font-size {size}px below minimum {adjusted_min:.0f}px",
                fix="Increase font-size to at least 14px.",
                metric={"font_size": size, "min_required": adjusted_min},
            ))
    return issues


def _check_typography_heading_hierarchy(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check heading levels don't skip (h1→h3 is bad)."""
    headings = _safe_get(probes, "typography", "headings", default=[])
    if not headings:
        return []
    issues = []
    prev_level = 0
    for h in headings:
        level = h.get("level", 0)
        if prev_level > 0 and level > prev_level + 1:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="a11y",
                rule="typography_heading_hierarchy",
                element=f"h{level}",
                message=f"Heading level skipped: h{prev_level} → h{level}",
                fix="Don't skip heading levels (e.g. h1→h2, not h1→h3).",
                metric={"prev": prev_level, "current": level},
            ))
        prev_level = level
    return issues


def _check_typography_banned_fonts(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check for banned fonts (Inter, Roboto, DM Sans per DESIGN.md)."""
    elements = _safe_get(probes, "typography", "text_styles", default=[])
    if not elements:
        return []
    banned = {"inter", "roboto", "dm sans", "arial", "helvetica"}
    issues = []
    for el in elements:
        family = el.get("font_family", "").lower()
        if any(b in family for b in banned):
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="a11y",
                rule="typography_font_family_banned",
                element=el.get("tag", "unknown"),
                message=f"Banned font family: {el.get('font_family', '')}",
                fix="Use a distinctive font, not overused Inter/Roboto/Arial.",
                metric={"font_family": el.get("font_family", "")},
            ))
    return issues


def _check_typography_max_line_length(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check max line length is ≤80 characters."""
    elements = _safe_get(probes, "typography", "text_styles", default=[])
    if not elements:
        return []
    base_max = 80.0
    adjusted_max = dials.adjust_threshold("layout_density", base_max)
    issues = []
    for el in elements:
        width = el.get("line_length_ch", 0)
        if width and width > adjusted_max:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="a11y",
                rule="typography_max_line_length",
                element=el.get("tag", "unknown"),
                message=f"Line length {width}ch exceeds max {adjusted_max:.0f}ch",
                fix="Limit line length to ~80 characters for readability.",
                metric={"line_length": width, "max_recommended": adjusted_max},
            ))
    return issues


def _check_typography_letter_spacing(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check letter-spacing is within normal range (-0.05em to 0.1em)."""
    elements = _safe_get(probes, "typography", "text_styles", default=[])
    if not elements:
        return []
    issues = []
    for el in elements:
        ls = el.get("letter_spacing_em")
        if ls is not None and (ls < -0.05 or ls > 0.1):
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="a11y",
                rule="typography_letter_spacing",
                element=el.get("tag", "unknown"),
                message=f"letter-spacing {ls}em outside normal range",
                fix="Keep letter-spacing between -0.05em and 0.1em.",
                metric={"letter_spacing": ls},
            ))
    return issues


def _check_typography_font_weight_contrast(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check heading vs body font-weight has sufficient contrast (≥200 diff)."""
    headings = _safe_get(probes, "typography", "headings", default=[])
    body = _safe_get(probes, "typography", "body_style", default={})
    if not headings or not body:
        return []
    body_weight = body.get("font_weight", 400)
    issues = []
    for h in headings:
        hw = h.get("font_weight", 400)
        if abs(hw - body_weight) < 200:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="a11y",
                rule="typography_font_weight_contrast",
                element=f"h{h.get('level', '?')}",
                message=f"Heading weight {hw} too close to body {body_weight}",
                fix="Increase heading font-weight contrast (≥200 difference).",
                metric={"heading_weight": hw, "body_weight": body_weight},
            ))
    return issues


def _check_typography_text_alignment(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check body text is not justified."""
    elements = _safe_get(probes, "typography", "text_styles", default=[])
    if not elements:
        return []
    issues = []
    for el in elements:
        align = el.get("text_align", "")
        if align == "justify":
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="a11y",
                rule="typography_text_alignment",
                element=el.get("tag", "unknown"),
                message="Body text is justified, causing irregular spacing",
                fix="Use left-align for body text instead of justify.",
                metric={"text_align": align},
            ))
    return issues


# ── Color Rules (8) ───────────────────────────────────────────────────────────


def _check_color_contrast_normal(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check WCAG AA contrast ratio for normal text (≥4.5:1). a11y — never adjusted."""
    items = _safe_get(probes, "a11y", "text_contrast", default=[])
    if not items:
        return []
    # a11y rules are NEVER adjusted by TasteDials
    min_ratio = 4.5
    issues = []
    for item in items:
        ratio = item.get("contrast_ratio", 0)
        if ratio and ratio < min_ratio:
            issues.append(UIUXIssue(
                severity=SEVERITY_ERROR, category="a11y",
                rule="color_contrast_ratio_normal",
                element=item.get("text", "")[:30],
                message=f"Contrast ratio {ratio:.1f} below WCAG AA 4.5:1",
                fix="Increase color contrast to at least 4.5:1.",
                metric={"ratio": ratio, "min_required": min_ratio},
            ))
    return issues


def _check_color_contrast_large(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check WCAG AA contrast for large text (≥3:1). a11y — never adjusted."""
    items = _safe_get(probes, "color", "large_text_contrast", default=[])
    if not items:
        return []
    min_ratio = 3.0
    issues = []
    for item in items:
        ratio = item.get("contrast_ratio", 0)
        if ratio and ratio < min_ratio:
            issues.append(UIUXIssue(
                severity=SEVERITY_ERROR, category="a11y",
                rule="color_contrast_ratio_large",
                element=item.get("text", "")[:30],
                message=f"Large text contrast {ratio:.1f} below 3:1",
                fix="Increase contrast to at least 3:1 for large text.",
                metric={"ratio": ratio, "min_required": min_ratio},
            ))
    return issues


def _check_color_contrast_ui(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check WCAG AA contrast for UI components (≥3:1). a11y — never adjusted."""
    items = _safe_get(probes, "color", "ui_component_contrast", default=[])
    if not items:
        return []
    min_ratio = 3.0
    issues = []
    for item in items:
        ratio = item.get("contrast_ratio", 0)
        if ratio and ratio < min_ratio:
            issues.append(UIUXIssue(
                severity=SEVERITY_ERROR, category="a11y",
                rule="color_contrast_ratio_ui",
                element=item.get("element", "ui-component"),
                message=f"UI contrast {ratio:.1f} below 3:1",
                fix="Increase UI component contrast to at least 3:1.",
                metric={"ratio": ratio, "min_required": min_ratio},
            ))
    return issues


def _check_color_harsh_saturation(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check HSV saturation is < 0.6 (Morandi color palette)."""
    colors = _safe_get(probes, "color", "palette", default=[])
    if not colors:
        return []
    base_max = 0.6
    adjusted_max = dials.adjust_threshold("variance_consistency", base_max)
    issues = []
    for c in colors:
        sat = c.get("hsv_saturation", 0)
        if sat > adjusted_max:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="a11y",
                rule="color_harsh_saturation",
                element=c.get("hex", "#unknown"),
                message=f"HSV saturation {sat:.2f} exceeds {adjusted_max:.2f}",
                fix="Use softer (Morandi-style) colors with lower saturation.",
                metric={"saturation": sat, "max_recommended": adjusted_max},
            ))
    return issues


def _check_color_palette_count(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check color palette has ≤5 distinct colors."""
    colors = _safe_get(probes, "color", "palette", default=[])
    if not colors:
        return []
    base_max = 5.0
    adjusted_max = dials.adjust_threshold("layout_density", base_max)
    count = len(colors)
    if count > adjusted_max:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="a11y",
            rule="color_palette_count",
            element="color-palette",
            message=f"Palette has {count} colors, max {adjusted_max:.0f} recommended",
            fix="Limit palette to 5 distinct colors.",
            metric={"count": count, "max_recommended": adjusted_max},
        )]
    return []


def _check_color_oklch_usage(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check if OKLCH color space is used (recommended)."""
    colors = _safe_get(probes, "color", "palette", default=[])
    if not colors:
        return []
    has_oklch = any(c.get("color_space") == "oklch" for c in colors)
    if not has_oklch:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="a11y",
            rule="color_oklch_usage",
            element="color-palette",
            message="No OKLCH colors detected",
            fix="Consider using OKLCH color space for perceptual uniformity.",
            metric={"has_oklch": False},
        )]
    return []


def _check_color_grayscale_secondary(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check grayscale is used for secondary text."""
    text_styles = _safe_get(probes, "typography", "text_styles", default=[])
    if not text_styles:
        return []
    has_grayscale = any(
        "gray" in str(t.get("color", "")).lower() or "#666" in str(t.get("color", ""))
        or "#999" in str(t.get("color", ""))
        for t in text_styles
    )
    if not has_grayscale:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="a11y",
            rule="color_grayscale_secondary",
            element="secondary-text",
            message="No grayscale detected for secondary text",
            fix="Use grayscale tones for secondary/supporting text.",
            metric={"has_grayscale": False},
        )]
    return []


def _check_color_background_contrast(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check background has sufficient contrast with page content. a11y — never adjusted."""
    bg = _safe_get(probes, "color", "background", default={})
    if not bg:
        return []
    ratio = bg.get("contrast_ratio", 0)
    min_ratio = 4.5
    if ratio and ratio < min_ratio:
        return [UIUXIssue(
            severity=SEVERITY_ERROR, category="a11y",
            rule="color_background_contrast",
            element="body-background",
            message=f"Background contrast {ratio:.1f} below {min_ratio}:1",
            fix="Increase background-to-content contrast.",
            metric={"ratio": ratio, "min_required": min_ratio},
        )]
    return []


# ── Spatial Design Rules (6) ──────────────────────────────────────────────────


def _check_spatial_4pt_grid(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check spacing follows 4pt grid (4/8/16/24/32/48)."""
    spacings = _safe_get(probes, "spatial", "spacing_values", default=[])
    if not spacings:
        return []
    valid = {4, 8, 12, 16, 20, 24, 32, 40, 48, 64}
    issues = []
    for s in spacings:
        val = s.get("value", 0)
        if val and val not in valid:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="layout",
                rule="spatial_4pt_grid",
                element=s.get("property", "spacing"),
                message=f"Spacing {val}px not on 4pt grid",
                fix="Use 4pt grid values: 4, 8, 16, 24, 32, 48.",
                metric={"value": val},
            ))
    return issues


def _check_spatial_element_density(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check element count per viewport is not excessive."""
    count = _safe_get(probes, "layout", "element_count", default=0)
    if not count:
        return []
    base_max = 50.0
    adjusted_max = dials.adjust_threshold("layout_density", base_max)
    if count > adjusted_max:
        return [UIUXIssue(
            severity=SEVERITY_WARNING, category="layout",
            rule="spatial_element_density",
            element="viewport",
            message=f"Element count {count} exceeds max {adjusted_max:.0f}",
            fix="Reduce element count or increase whitespace.",
            metric={"count": count, "max_recommended": adjusted_max},
        )]
    return []


def _check_spatial_padding_min(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check minimum padding is 8px."""
    elements = _safe_get(probes, "spatial", "padding_values", default=[])
    if not elements:
        return []
    base_min = 8.0
    adjusted_min = dials.adjust_threshold("layout_density", base_min)
    issues = []
    for el in elements:
        pad = el.get("padding", 0)
        if pad and pad < adjusted_min:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="layout",
                rule="spatial_padding_min",
                element=el.get("tag", "unknown"),
                message=f"Padding {pad}px below min {adjusted_min:.0f}px",
                fix="Increase padding to at least 8px.",
                metric={"padding": pad, "min_required": adjusted_min},
            ))
    return issues


def _check_spatial_margin_consistency(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check margins are consistent (≤3 distinct margin values)."""
    margins = _safe_get(probes, "spatial", "margin_values", default=[])
    if not margins:
        return []
    distinct = {m.get("value", 0) for m in margins}
    base_max = 3.0
    adjusted_max = dials.adjust_threshold("variance_consistency", base_max)
    if len(distinct) > adjusted_max:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="layout",
            rule="spatial_margin_consistency",
            element="margins",
            message=f"{len(distinct)} distinct margin values, max {adjusted_max:.0f}",
            fix="Standardize margins to ≤3 distinct values.",
            metric={"distinct_count": len(distinct), "max_recommended": adjusted_max},
        )]
    return []


def _check_spatial_whitespace_ratio(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check whitespace-to-content ratio is balanced (≥30%)."""
    ratio = _safe_get(probes, "spatial", "whitespace_ratio")
    if ratio is None:
        return []
    base_min = 0.3
    adjusted_min = dials.adjust_threshold("layout_spacing", base_min)
    if ratio < adjusted_min:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="layout",
            rule="spatial_whitespace_ratio",
            element="viewport",
            message=f"Whitespace ratio {ratio:.0%} below {adjusted_min:.0%}",
            fix="Increase whitespace to at least 30% of viewport.",
            metric={"ratio": ratio, "min_recommended": adjusted_min},
        )]
    return []


def _check_spatial_card_spacing(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check card spacing is consistent."""
    cards = _safe_get(probes, "spatial", "card_spacings", default=[])
    if len(cards) < 2:
        return []
    values = [c.get("spacing", 0) for c in cards]
    if len(set(values)) > 2:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="layout",
            rule="spatial_card_spacing",
            element="cards",
            message=f"Inconsistent card spacing: {set(values)}",
            fix="Use consistent spacing between cards.",
            metric={"spacings": list(set(values))},
        )]
    return []


# ── Responsiveness Rules (6) ──────────────────────────────────────────────────


def _check_responsive_viewport_overflow(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check no horizontal scroll (viewport overflow)."""
    overflow = _safe_get(probes, "layout", "viewport_overflow")
    if overflow:
        return [UIUXIssue(
            severity=SEVERITY_ERROR, category="layout",
            rule="responsive_viewport_overflow",
            element="body",
            message="Horizontal scroll detected (viewport overflow)",
            fix="Prevent content from exceeding viewport width.",
            metric={"viewport_overflow": True},
        )]
    return []


def _check_responsive_touch_target(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check touch targets are ≥44×44px."""
    buttons = _safe_get(probes, "interaction", "buttons", default=[])
    if not buttons:
        return []
    base_min = 44.0
    adjusted_min = dials.adjust_threshold("layout_density", base_min)
    issues = []
    for btn in buttons:
        w = btn.get("width", 0)
        h = btn.get("height", 0)
        if w < adjusted_min or h < adjusted_min:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="responsive_touch_target",
                element=btn.get("text", "")[:20],
                message=f"Touch target {w}×{h}px below {adjusted_min:.0f}px",
                fix="Increase touch target to at least 44×44px.",
                metric={"width": w, "height": h, "min_required": adjusted_min},
            ))
    return issues


def _check_responsive_image_max_width(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check images have max-width: 100%."""
    images = _safe_get(probes, "responsiveness", "images", default=[])
    if not images:
        return []
    issues = []
    for img in images:
        if not img.get("has_max_width"):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="layout",
                rule="responsive_image_max_width",
                element=img.get("src", "")[:30],
                message="Image missing max-width: 100%",
                fix="Add max-width: 100% to images for responsive layout.",
                metric={"has_max_width": False},
            ))
    return issues


def _check_responsive_text_overflow(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check no text truncation on key content."""
    truncated = _safe_get(probes, "layout", "truncated", default=[])
    if not truncated:
        return []
    issues = []
    for el in truncated:
        issues.append(UIUXIssue(
            severity=SEVERITY_INFO, category="layout",
            rule="responsive_text_overflow",
            element=el.get("tag", "unknown"),
            message="Text truncation detected",
            fix="Avoid truncating important text on smaller screens.",
            metric={"truncated": True},
        ))
    return issues


def _check_responsive_breakpoint_coverage(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check responsive breakpoints cover sm/md/lg/xl."""
    breakpoints = _safe_get(probes, "responsiveness", "breakpoints", default=[])
    if not breakpoints:
        return []
    required = {"sm", "md", "lg", "xl"}
    found = set(breakpoints)
    missing = required - found
    if missing:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="layout",
            rule="responsive_breakpoint_coverage",
            element="breakpoints",
            message=f"Missing breakpoints: {missing}",
            fix="Add responsive breakpoints for sm/md/lg/xl.",
            metric={"missing": list(missing)},
        )]
    return []


def _check_responsive_grid_adapt(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check grid layout adapts to viewport."""
    grids = _safe_get(probes, "responsiveness", "grid_layouts", default=[])
    if not grids:
        return []
    issues = []
    for grid in grids:
        if not grid.get("has_media_query"):
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="layout",
                rule="responsive_grid_adapt",
                element="grid",
                message="Grid layout missing media query adaptation",
                fix="Add media queries to adapt grid columns.",
                metric={"has_media_query": False},
            ))
    return issues


# ── Interactions Rules (8) ────────────────────────────────────────────────────


def _check_interaction_button_min_size(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check buttons meet minimum size 44×44px."""
    buttons = _safe_get(probes, "interaction", "buttons", default=[])
    if not buttons:
        return []
    base_min = 44.0
    adjusted_min = dials.adjust_threshold("layout_density", base_min)
    issues = []
    for btn in buttons:
        if btn.get("too_small"):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="interaction_button_min_size",
                element=btn.get("text", "")[:20],
                message=f"Button {btn.get('width', 0)}×{btn.get('height', 0)}px too small",
                fix=f"Increase button size to at least {adjusted_min:.0f}×{adjusted_min:.0f}px.",
                metric={"width": btn.get("width"), "height": btn.get("height")},
            ))
    return issues


def _check_interaction_focus_visible(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check focus outline is not removed."""
    focus_styles = _safe_get(probes, "interaction", "focus_styles", default=[])
    if not focus_styles:
        return []
    issues = []
    for fs in focus_styles:
        if fs.get("outline_removed"):
            issues.append(UIUXIssue(
                severity=SEVERITY_ERROR, category="interaction",
                rule="interaction_focus_visible",
                element=":focus",
                message="Focus outline removed — keyboard accessibility violation",
                fix="Don't remove focus outlines; style them instead.",
                metric={"outline_removed": True},
            ))
    return issues


def _check_interaction_hover_feedback(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check interactive elements have hover state."""
    elements = _safe_get(probes, "interaction", "interactive_elements", default=[])
    if not elements:
        return []
    issues = []
    for el in elements:
        if not el.get("has_hover"):
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="interaction",
                rule="interaction_hover_feedback",
                element=el.get("tag", "unknown"),
                message="Interactive element missing hover state",
                fix="Add :hover state for interactive elements.",
                metric={"has_hover": False},
            ))
    return issues


def _check_interaction_active_state(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check interactive elements have active state."""
    elements = _safe_get(probes, "interaction", "interactive_elements", default=[])
    if not elements:
        return []
    issues = []
    for el in elements:
        if not el.get("has_active"):
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="interaction",
                rule="interaction_active_state",
                element=el.get("tag", "unknown"),
                message="Interactive element missing :active state",
                fix="Add :active state for tactile feedback.",
                metric={"has_active": False},
            ))
    return issues


def _check_interaction_disabled_state(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check disabled elements are visually distinct."""
    elements = _safe_get(probes, "interaction", "disabled_elements", default=[])
    if not elements:
        return []
    issues = []
    for el in elements:
        if not el.get("has_disabled_style"):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="interaction_disabled_state",
                element=el.get("tag", "unknown"),
                message="Disabled element lacks visual distinction",
                fix="Style :disabled state with reduced opacity/cursor.",
                metric={"has_disabled_style": False},
            ))
    return issues


def _check_interaction_loading_feedback(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check async operations have loading feedback."""
    async_ops = _safe_get(probes, "interaction", "async_operations", default=[])
    if not async_ops:
        return []
    issues = []
    for op in async_ops:
        if not op.get("has_loading_state"):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="interaction_loading_feedback",
                element=op.get("action", "unknown"),
                message="Async operation missing loading feedback",
                fix="Show loading spinner/skeleton for async operations.",
                metric={"has_loading_state": False},
            ))
    return issues


def _check_interaction_destructive_confirm(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check destructive operations have confirmation."""
    destructive = _safe_get(probes, "ux", "destructive_without_confirm", default=[])
    if not destructive:
        return []
    issues = []
    for el in destructive:
        issues.append(UIUXIssue(
            severity=SEVERITY_ERROR, category="ux_antipattern",
            rule="interaction_destructive_confirm",
            element=el.get("text", "")[:20],
            message="Destructive action without confirmation dialog",
            fix="Add confirmation dialog for destructive actions.",
            metric={"has_confirm": False},
        ))
    return issues


def _check_interaction_form_validation(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check forms have validation."""
    forms = _safe_get(probes, "ux", "forms", default=[])
    if not forms:
        return []
    issues = []
    for form in forms:
        if form.get("no_validation"):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="ux_antipattern",
                rule="interaction_form_validation",
                element=form.get("action", "")[:20],
                message="Form has inputs but no required fields/validation",
                fix="Add form validation (required fields, type checks).",
                metric={"input_count": form.get("input_count"),
                        "required_count": form.get("required_count")},
            ))
    return issues


# ── Motion Rules (5) ──────────────────────────────────────────────────────────


def _check_motion_duration_max(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check animation duration ≤1s."""
    animations = _safe_get(probes, "motion", "animations", default=[])
    if not animations:
        return []
    base_max = 1000.0  # ms
    adjusted_max = dials.adjust_threshold("animation_duration", base_max)
    issues = []
    for anim in animations:
        dur = anim.get("duration_ms", 0)
        if dur and dur > adjusted_max:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="motion_duration_max",
                element=anim.get("property", "animation"),
                message=f"Animation duration {dur}ms exceeds {adjusted_max:.0f}ms",
                fix="Keep animation duration under 1 second.",
                metric={"duration": dur, "max_recommended": adjusted_max},
            ))
    return issues


def _check_motion_no_bounce_easing(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check no bounce easing is used."""
    animations = _safe_get(probes, "motion", "animations", default=[])
    if not animations:
        return []
    bounce_keywords = {"bounce", "elastic", "spring"}
    issues = []
    for anim in animations:
        easing = str(anim.get("easing", "")).lower()
        if any(kw in easing for kw in bounce_keywords):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="motion_no_bounce_easing",
                element=anim.get("property", "animation"),
                message=f"Bounce easing detected: {easing}",
                fix="Avoid bounce/elastic easing; use ease-out instead.",
                metric={"easing": easing},
            ))
    return issues


def _check_motion_no_width_height_anim(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check no width/height animation (use transform instead)."""
    animations = _safe_get(probes, "motion", "animations", default=[])
    if not animations:
        return []
    issues = []
    for anim in animations:
        prop = str(anim.get("property", "")).lower()
        if prop in ("width", "height"):
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="interaction",
                rule="motion_no_width_height_anim",
                element=prop,
                message=f"Animating {prop} causes layout thrashing",
                fix=f"Use transform: scale() instead of animating {prop}.",
                metric={"property": prop},
            ))
    return issues


def _check_motion_no_glassmorphism_overuse(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check glassmorphism is not overused (≤2 instances)."""
    glass = _safe_get(probes, "motion", "glassmorphism_count", default=0)
    if not glass:
        return []
    base_max = 2.0
    adjusted_max = dials.adjust_threshold("layout_density", base_max)
    if glass > adjusted_max:
        return [UIUXIssue(
            severity=SEVERITY_INFO, category="interaction",
            rule="motion_no_glassmorphism_overuse",
            element="glassmorphism",
            message=f"Glassmorphism used {glass} times, max {adjusted_max:.0f}",
            fix="Limit glassmorphism to ≤2 instances per page.",
            metric={"count": glass, "max_recommended": adjusted_max},
        )]
    return []


def _check_motion_reduced_motion(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check prefers-reduced-motion is respected."""
    has_animations = bool(_safe_get(probes, "motion", "animations", default=[]))
    has_reduced = _safe_get(probes, "motion", "has_reduced_motion_query")
    if has_animations and has_reduced is False:
        return [UIUXIssue(
            severity=SEVERITY_WARNING, category="interaction",
            rule="motion_reduced_motion",
            element="@media",
            message="Animations present but prefers-reduced-motion not handled",
            fix="Add @media (prefers-reduced-motion: reduce) query.",
            metric={"has_reduced_motion_query": False},
        )]
    return []


# ── UX Writing Rules (5) ──────────────────────────────────────────────────────


def _check_ux_button_text_clarity(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check button text is actionable (not 'Click Here' / 'Submit')."""
    buttons = _safe_get(probes, "interaction", "buttons", default=[])
    if not buttons:
        return []
    vague = {"click here", "submit", "ok", "click", "here", "tap", "go"}
    issues = []
    for btn in buttons:
        text = str(btn.get("text", "")).lower().strip()
        if text in vague:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="ux_antipattern",
                rule="ux_button_text_clarity",
                element=btn.get("text", "")[:20],
                message=f"Vague button text: '{text}'",
                fix="Use action-oriented text (e.g. 'Save Changes', 'Delete Account').",
                metric={"text": text},
            ))
    return issues


def _check_ux_error_message_clarity(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check error messages are helpful (not just 'Error')."""
    errors = _safe_get(probes, "ux", "error_messages", default=[])
    if not errors:
        return []
    unhelpful = {"error", "failed", "invalid", "wrong", "error!", "oops"}
    issues = []
    for err in errors:
        text = str(err.get("text", "")).lower().strip()
        if text in unhelpful:
            issues.append(UIUXIssue(
                severity=SEVERITY_WARNING, category="ux_antipattern",
                rule="ux_error_message_clarity",
                element=err.get("text", "")[:20],
                message=f"Unhelpful error message: '{text}'",
                fix="Explain what went wrong and how to fix it.",
                metric={"text": text},
            ))
    return issues


def _check_ux_form_label_clarity(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check form labels are clear (not just 'Field 1')."""
    inputs = _safe_get(probes, "a11y", "inputs", default=[])
    if not inputs:
        return []
    issues = []
    for inp in inputs:
        label = str(inp.get("label_text", "")).lower().strip()
        if label.startswith("field ") or label in {"input", "text", "value"}:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="ux_antipattern",
                rule="ux_form_label_clarity",
                element=inp.get("id", "input"),
                message=f"Unclear form label: '{label}'",
                fix="Use descriptive labels (e.g. 'Email Address', not 'Field 1').",
                metric={"label": label},
            ))
    return issues


def _check_ux_link_text_descriptive(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check link text is descriptive (not 'click here' / 'read more')."""
    links = _safe_get(probes, "ux", "links", default=[])
    if not links:
        return []
    vague = {"click here", "read more", "more", "here", "link", "learn more"}
    issues = []
    for link in links:
        text = str(link.get("text", "")).lower().strip()
        if text in vague:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="ux_antipattern",
                rule="ux_link_text_descriptive",
                element=link.get("text", "")[:20],
                message=f"Vague link text: '{text}'",
                fix="Use descriptive link text (e.g. 'Read API Guide').",
                metric={"text": text},
            ))
    return issues


def _check_ux_heading_descriptive(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check headings are descriptive (not just 'Heading' or 'Title')."""
    headings = _safe_get(probes, "typography", "headings", default=[])
    if not headings:
        return []
    vague = {"heading", "title", "section", "block", "untitled", ""}
    issues = []
    for h in headings:
        text = str(h.get("text", "")).lower().strip()
        if text in vague:
            issues.append(UIUXIssue(
                severity=SEVERITY_INFO, category="ux_antipattern",
                rule="ux_heading_descriptive",
                element=f"h{h.get('level', '?')}",
                message=f"Vague heading: '{text}'",
                fix="Use descriptive headings that convey content meaning.",
                metric={"text": text},
            ))
    return issues


# ── DeterministicRuleEngine ───────────────────────────────────────────────────


class DeterministicRuleEngine:
    """46+ deterministic UI/UX rules, no LLM needed.

    Inspired by impeccable's 46 deterministic detector rules.
    Rules organized by 7 design pillars:
      - Typography (8 rules)
      - Color (8 rules)
      - Spatial design (6 rules)
      - Responsiveness (6 rules)
      - Interactions (8 rules)
      - Motion (5 rules)
      - UX writing (5 rules)

    Each rule's check_fn receives (probes, dials, context) and returns
    list[UIUXIssue]. Rules gracefully degrade when probe data is missing.

    TasteDials integration:
      - Non-a11y rules have thresholds adjusted by dials.adjust_threshold()
      - a11y rules (contrast, aria) are NEVER adjusted — accessibility is not
        a matter of taste
    """

    def __init__(self) -> None:
        self._rules: list[DesignRule] = self._build_rule_library()

    @property
    def rules(self) -> list[DesignRule]:
        """Read-only access to the rule library."""
        return list(self._rules)

    @property
    def rule_count(self) -> int:
        """Total number of rules in the library."""
        return len(self._rules)

    def get_rules_by_pillar(self, pillar: str) -> list[DesignRule]:
        """Filter rules by design pillar.

        Args:
            pillar: One of SEVEN_PILLARS.

        Returns:
            List of rules belonging to the specified pillar.
        """
        return [r for r in self._rules if r.pillar == pillar]

    def get_pillar_counts(self) -> dict[str, int]:
        """Get rule count per pillar.

        Returns:
            Dict mapping pillar name to rule count.
        """
        counts: dict[str, int] = dict.fromkeys(SEVEN_PILLARS, 0)
        for rule in self._rules:
            counts[rule.pillar] = counts.get(rule.pillar, 0) + 1
        return counts

    def check(
        self,
        probes: dict[str, Any],
        dials: TasteDials | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[UIUXIssue]:
        """Run all rules against collected DOM probes.

        Args:
            probes: DOM probe data (from Playwright page.evaluate or test mock).
            dials: TasteDials for threshold adjustment. Defaults to default dials.
            context: Additional context (e.g. viewport size, device type).

        Returns:
            List of all UIUXIssue found by all rules, sorted by severity.
        """
        if dials is None:
            dials = TasteDials()
        if context is None:
            context = {}

        all_issues: list[UIUXIssue] = []
        for rule in self._rules:
            try:
                issues = rule.check_fn(probes, dials, context)
                all_issues.extend(issues)
            except Exception:  # noqa: BLE001
                # Fail-safe: a single rule error doesn't stop other rules
                # (mirrors UIUXAnalyzer's fail-safe philosophy)
                continue

        # Sort by severity: critical > warning > info
        severity_order = {SEVERITY_ERROR: 0, SEVERITY_WARNING: 1, SEVERITY_INFO: 2}
        all_issues.sort(key=lambda i: severity_order.get(i.severity, 99))
        return all_issues

    def _build_rule_library(self) -> list[DesignRule]:
        """Build the 46-rule library.

        Returns:
            List of DesignRule instances organized by 7 pillars.
        """
        return [
            # ── Typography (8) ──
            DesignRule(
                rule_id="typography_line_height",
                pillar="typography",
                severity=SEVERITY_WARNING,
                check_fn=_check_typography_line_height,
                fix_hint="Increase line-height to at least 1.4 for readability.",
            ),
            DesignRule(
                rule_id="typography_font_size_min",
                pillar="typography",
                severity=SEVERITY_WARNING,
                check_fn=_check_typography_font_size_min,
                fix_hint="Increase font-size to at least 14px.",
            ),
            DesignRule(
                rule_id="typography_heading_hierarchy",
                pillar="typography",
                severity=SEVERITY_WARNING,
                check_fn=_check_typography_heading_hierarchy,
                fix_hint="Don't skip heading levels (h1→h2, not h1→h3).",
            ),
            DesignRule(
                rule_id="typography_font_family_banned",
                pillar="typography",
                severity=SEVERITY_INFO,
                check_fn=_check_typography_banned_fonts,
                fix_hint="Use a distinctive font, not overused Inter/Roboto/Arial.",
            ),
            DesignRule(
                rule_id="typography_max_line_length",
                pillar="typography",
                severity=SEVERITY_INFO,
                check_fn=_check_typography_max_line_length,
                fix_hint="Limit line length to ~80 characters for readability.",
            ),
            DesignRule(
                rule_id="typography_letter_spacing",
                pillar="typography",
                severity=SEVERITY_INFO,
                check_fn=_check_typography_letter_spacing,
                fix_hint="Keep letter-spacing between -0.05em and 0.1em.",
            ),
            DesignRule(
                rule_id="typography_font_weight_contrast",
                pillar="typography",
                severity=SEVERITY_INFO,
                check_fn=_check_typography_font_weight_contrast,
                fix_hint="Increase heading font-weight contrast (≥200 difference).",
            ),
            DesignRule(
                rule_id="typography_text_alignment",
                pillar="typography",
                severity=SEVERITY_INFO,
                check_fn=_check_typography_text_alignment,
                fix_hint="Use left-align for body text instead of justify.",
            ),

            # ── Color (8) ──
            DesignRule(
                rule_id="color_contrast_ratio_normal",
                pillar="color",
                severity=SEVERITY_ERROR,
                check_fn=_check_color_contrast_normal,
                fix_hint="Increase color contrast to at least 4.5:1.",
            ),
            DesignRule(
                rule_id="color_contrast_ratio_large",
                pillar="color",
                severity=SEVERITY_ERROR,
                check_fn=_check_color_contrast_large,
                fix_hint="Increase contrast to at least 3:1 for large text.",
            ),
            DesignRule(
                rule_id="color_contrast_ratio_ui",
                pillar="color",
                severity=SEVERITY_ERROR,
                check_fn=_check_color_contrast_ui,
                fix_hint="Increase UI component contrast to at least 3:1.",
            ),
            DesignRule(
                rule_id="color_harsh_saturation",
                pillar="color",
                severity=SEVERITY_WARNING,
                check_fn=_check_color_harsh_saturation,
                fix_hint="Use softer (Morandi-style) colors with lower saturation.",
            ),
            DesignRule(
                rule_id="color_palette_count",
                pillar="color",
                severity=SEVERITY_INFO,
                check_fn=_check_color_palette_count,
                fix_hint="Limit palette to 5 distinct colors.",
            ),
            DesignRule(
                rule_id="color_oklch_usage",
                pillar="color",
                severity=SEVERITY_INFO,
                check_fn=_check_color_oklch_usage,
                fix_hint="Consider using OKLCH color space for perceptual uniformity.",
            ),
            DesignRule(
                rule_id="color_grayscale_secondary",
                pillar="color",
                severity=SEVERITY_INFO,
                check_fn=_check_color_grayscale_secondary,
                fix_hint="Use grayscale tones for secondary/supporting text.",
            ),
            DesignRule(
                rule_id="color_background_contrast",
                pillar="color",
                severity=SEVERITY_ERROR,
                check_fn=_check_color_background_contrast,
                fix_hint="Increase background-to-content contrast.",
            ),

            # ── Spatial Design (6) ──
            DesignRule(
                rule_id="spatial_4pt_grid",
                pillar="spatial",
                severity=SEVERITY_INFO,
                check_fn=_check_spatial_4pt_grid,
                fix_hint="Use 4pt grid values: 4, 8, 16, 24, 32, 48.",
            ),
            DesignRule(
                rule_id="spatial_element_density",
                pillar="spatial",
                severity=SEVERITY_WARNING,
                check_fn=_check_spatial_element_density,
                fix_hint="Reduce element count or increase whitespace.",
            ),
            DesignRule(
                rule_id="spatial_padding_min",
                pillar="spatial",
                severity=SEVERITY_WARNING,
                check_fn=_check_spatial_padding_min,
                fix_hint="Increase padding to at least 8px.",
            ),
            DesignRule(
                rule_id="spatial_margin_consistency",
                pillar="spatial",
                severity=SEVERITY_INFO,
                check_fn=_check_spatial_margin_consistency,
                fix_hint="Standardize margins to ≤3 distinct values.",
            ),
            DesignRule(
                rule_id="spatial_whitespace_ratio",
                pillar="spatial",
                severity=SEVERITY_INFO,
                check_fn=_check_spatial_whitespace_ratio,
                fix_hint="Increase whitespace to at least 30% of viewport.",
            ),
            DesignRule(
                rule_id="spatial_card_spacing",
                pillar="spatial",
                severity=SEVERITY_INFO,
                check_fn=_check_spatial_card_spacing,
                fix_hint="Use consistent spacing between cards.",
            ),

            # ── Responsiveness (6) ──
            DesignRule(
                rule_id="responsive_viewport_overflow",
                pillar="responsiveness",
                severity=SEVERITY_ERROR,
                check_fn=_check_responsive_viewport_overflow,
                fix_hint="Prevent content from exceeding viewport width.",
            ),
            DesignRule(
                rule_id="responsive_touch_target",
                pillar="responsiveness",
                severity=SEVERITY_WARNING,
                check_fn=_check_responsive_touch_target,
                fix_hint="Increase touch target to at least 44×44px.",
            ),
            DesignRule(
                rule_id="responsive_image_max_width",
                pillar="responsiveness",
                severity=SEVERITY_WARNING,
                check_fn=_check_responsive_image_max_width,
                fix_hint="Add max-width: 100% to images for responsive layout.",
            ),
            DesignRule(
                rule_id="responsive_text_overflow",
                pillar="responsiveness",
                severity=SEVERITY_INFO,
                check_fn=_check_responsive_text_overflow,
                fix_hint="Avoid truncating important text on smaller screens.",
            ),
            DesignRule(
                rule_id="responsive_breakpoint_coverage",
                pillar="responsiveness",
                severity=SEVERITY_INFO,
                check_fn=_check_responsive_breakpoint_coverage,
                fix_hint="Add responsive breakpoints for sm/md/lg/xl.",
            ),
            DesignRule(
                rule_id="responsive_grid_adapt",
                pillar="responsiveness",
                severity=SEVERITY_INFO,
                check_fn=_check_responsive_grid_adapt,
                fix_hint="Add media queries to adapt grid columns.",
            ),

            # ── Interactions (8) ──
            DesignRule(
                rule_id="interaction_button_min_size",
                pillar="interactions",
                severity=SEVERITY_WARNING,
                check_fn=_check_interaction_button_min_size,
                fix_hint="Increase button size to at least 44×44px.",
            ),
            DesignRule(
                rule_id="interaction_focus_visible",
                pillar="interactions",
                severity=SEVERITY_ERROR,
                check_fn=_check_interaction_focus_visible,
                fix_hint="Don't remove focus outlines; style them instead.",
            ),
            DesignRule(
                rule_id="interaction_hover_feedback",
                pillar="interactions",
                severity=SEVERITY_INFO,
                check_fn=_check_interaction_hover_feedback,
                fix_hint="Add :hover state for interactive elements.",
            ),
            DesignRule(
                rule_id="interaction_active_state",
                pillar="interactions",
                severity=SEVERITY_INFO,
                check_fn=_check_interaction_active_state,
                fix_hint="Add :active state for tactile feedback.",
            ),
            DesignRule(
                rule_id="interaction_disabled_state",
                pillar="interactions",
                severity=SEVERITY_WARNING,
                check_fn=_check_interaction_disabled_state,
                fix_hint="Style :disabled state with reduced opacity/cursor.",
            ),
            DesignRule(
                rule_id="interaction_loading_feedback",
                pillar="interactions",
                severity=SEVERITY_WARNING,
                check_fn=_check_interaction_loading_feedback,
                fix_hint="Show loading spinner/skeleton for async operations.",
            ),
            DesignRule(
                rule_id="interaction_destructive_confirm",
                pillar="interactions",
                severity=SEVERITY_ERROR,
                check_fn=_check_interaction_destructive_confirm,
                fix_hint="Add confirmation dialog for destructive actions.",
            ),
            DesignRule(
                rule_id="interaction_form_validation",
                pillar="interactions",
                severity=SEVERITY_WARNING,
                check_fn=_check_interaction_form_validation,
                fix_hint="Add form validation (required fields, type checks).",
            ),

            # ── Motion (5) ──
            DesignRule(
                rule_id="motion_duration_max",
                pillar="motion",
                severity=SEVERITY_WARNING,
                check_fn=_check_motion_duration_max,
                fix_hint="Keep animation duration under 1 second.",
            ),
            DesignRule(
                rule_id="motion_no_bounce_easing",
                pillar="motion",
                severity=SEVERITY_WARNING,
                check_fn=_check_motion_no_bounce_easing,
                fix_hint="Avoid bounce/elastic easing; use ease-out instead.",
            ),
            DesignRule(
                rule_id="motion_no_width_height_anim",
                pillar="motion",
                severity=SEVERITY_WARNING,
                check_fn=_check_motion_no_width_height_anim,
                fix_hint="Use transform: scale() instead of animating width/height.",
            ),
            DesignRule(
                rule_id="motion_no_glassmorphism_overuse",
                pillar="motion",
                severity=SEVERITY_INFO,
                check_fn=_check_motion_no_glassmorphism_overuse,
                fix_hint="Limit glassmorphism to ≤2 instances per page.",
            ),
            DesignRule(
                rule_id="motion_reduced_motion",
                pillar="motion",
                severity=SEVERITY_WARNING,
                check_fn=_check_motion_reduced_motion,
                fix_hint="Add @media (prefers-reduced-motion: reduce) query.",
            ),

            # ── UX Writing (5) ──
            DesignRule(
                rule_id="ux_button_text_clarity",
                pillar="ux_writing",
                severity=SEVERITY_INFO,
                check_fn=_check_ux_button_text_clarity,
                fix_hint="Use action-oriented button text (e.g. 'Save Changes').",
            ),
            DesignRule(
                rule_id="ux_error_message_clarity",
                pillar="ux_writing",
                severity=SEVERITY_WARNING,
                check_fn=_check_ux_error_message_clarity,
                fix_hint="Explain what went wrong and how to fix it.",
            ),
            DesignRule(
                rule_id="ux_form_label_clarity",
                pillar="ux_writing",
                severity=SEVERITY_INFO,
                check_fn=_check_ux_form_label_clarity,
                fix_hint="Use descriptive form labels (e.g. 'Email Address').",
            ),
            DesignRule(
                rule_id="ux_link_text_descriptive",
                pillar="ux_writing",
                severity=SEVERITY_INFO,
                check_fn=_check_ux_link_text_descriptive,
                fix_hint="Use descriptive link text (e.g. 'Read API Guide').",
            ),
            DesignRule(
                rule_id="ux_heading_descriptive",
                pillar="ux_writing",
                severity=SEVERITY_INFO,
                check_fn=_check_ux_heading_descriptive,
                fix_hint="Use descriptive headings that convey content meaning.",
            ),
        ]
