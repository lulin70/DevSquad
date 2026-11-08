"""Color rule checks (8).

WCAG contrast ratios (normal text, large text, UI components), saturation,
palette size, OKLCH usage, grayscale secondary text and background contrast.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, _safe_get


def _check_color_contrast_normal(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_ERROR,
                    category="a11y",
                    rule="color_contrast_ratio_normal",
                    element=item.get("text", "")[:30],
                    message=f"Contrast ratio {ratio:.1f} below WCAG AA 4.5:1",
                    fix="Increase color contrast to at least 4.5:1.",
                    metric={"ratio": ratio, "min_required": min_ratio},
                )
            )
    return issues


def _check_color_contrast_large(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check WCAG AA contrast for large text (≥3:1). a11y — never adjusted."""
    items = _safe_get(probes, "color", "large_text_contrast", default=[])
    if not items:
        return []
    min_ratio = 3.0
    issues = []
    for item in items:
        ratio = item.get("contrast_ratio", 0)
        if ratio and ratio < min_ratio:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_ERROR,
                    category="a11y",
                    rule="color_contrast_ratio_large",
                    element=item.get("text", "")[:30],
                    message=f"Large text contrast {ratio:.1f} below 3:1",
                    fix="Increase contrast to at least 3:1 for large text.",
                    metric={"ratio": ratio, "min_required": min_ratio},
                )
            )
    return issues


def _check_color_contrast_ui(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check WCAG AA contrast for UI components (≥3:1). a11y — never adjusted."""
    items = _safe_get(probes, "color", "ui_component_contrast", default=[])
    if not items:
        return []
    min_ratio = 3.0
    issues = []
    for item in items:
        ratio = item.get("contrast_ratio", 0)
        if ratio and ratio < min_ratio:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_ERROR,
                    category="a11y",
                    rule="color_contrast_ratio_ui",
                    element=item.get("element", "ui-component"),
                    message=f"UI contrast {ratio:.1f} below 3:1",
                    fix="Increase UI component contrast to at least 3:1.",
                    metric={"ratio": ratio, "min_required": min_ratio},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="a11y",
                    rule="color_harsh_saturation",
                    element=c.get("hex", "#unknown"),
                    message=f"HSV saturation {sat:.2f} exceeds {adjusted_max:.2f}",
                    fix="Use softer (Morandi-style) colors with lower saturation.",
                    metric={"saturation": sat, "max_recommended": adjusted_max},
                )
            )
    return issues


def _check_color_palette_count(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check color palette has ≤5 distinct colors."""
    colors = _safe_get(probes, "color", "palette", default=[])
    if not colors:
        return []
    base_max = 5.0
    adjusted_max = dials.adjust_threshold("layout_density", base_max)
    count = len(colors)
    if count > adjusted_max:
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="a11y",
                rule="color_palette_count",
                element="color-palette",
                message=f"Palette has {count} colors, max {adjusted_max:.0f} recommended",
                fix="Limit palette to 5 distinct colors.",
                metric={"count": count, "max_recommended": adjusted_max},
            )
        ]
    return []


def _check_color_oklch_usage(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check if OKLCH color space is used (recommended)."""
    colors = _safe_get(probes, "color", "palette", default=[])
    if not colors:
        return []
    has_oklch = any(c.get("color_space") == "oklch" for c in colors)
    if not has_oklch:
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="a11y",
                rule="color_oklch_usage",
                element="color-palette",
                message="No OKLCH colors detected",
                fix="Consider using OKLCH color space for perceptual uniformity.",
                metric={"has_oklch": False},
            )
        ]
    return []


def _check_color_grayscale_secondary(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check grayscale is used for secondary text."""
    text_styles = _safe_get(probes, "typography", "text_styles", default=[])
    if not text_styles:
        return []
    has_grayscale = any(
        "gray" in str(t.get("color", "")).lower()
        or "#666" in str(t.get("color", ""))
        or "#999" in str(t.get("color", ""))
        for t in text_styles
    )
    if not has_grayscale:
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="a11y",
                rule="color_grayscale_secondary",
                element="secondary-text",
                message="No grayscale detected for secondary text",
                fix="Use grayscale tones for secondary/supporting text.",
                metric={"has_grayscale": False},
            )
        ]
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
        return [
            UIUXIssue(
                severity=SEVERITY_ERROR,
                category="a11y",
                rule="color_background_contrast",
                element="body-background",
                message=f"Background contrast {ratio:.1f} below {min_ratio}:1",
                fix="Increase background-to-content contrast.",
                metric={"ratio": ratio, "min_required": min_ratio},
            )
        ]
    return []
