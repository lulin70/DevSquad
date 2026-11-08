"""Typography rule checks (8).

Line height, minimum font size, heading hierarchy, banned font families,
line length, letter spacing, weight contrast and alignment detectors.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_INFO, SEVERITY_WARNING, _safe_get


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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="a11y",
                    rule="typography_line_height",
                    element=el.get("tag", "unknown"),
                    message=f"line-height {lh:.2f} below minimum {adjusted_min:.2f}",
                    fix="Increase line-height to at least 1.4 for readability.",
                    metric={"line_height": lh, "min_required": adjusted_min},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="a11y",
                    rule="typography_font_size_min",
                    element=el.get("tag", "unknown"),
                    message=f"font-size {size}px below minimum {adjusted_min:.0f}px",
                    fix="Increase font-size to at least 14px.",
                    metric={"font_size": size, "min_required": adjusted_min},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="a11y",
                    rule="typography_heading_hierarchy",
                    element=f"h{level}",
                    message=f"Heading level skipped: h{prev_level} → h{level}",
                    fix="Don't skip heading levels (e.g. h1→h2, not h1→h3).",
                    metric={"prev": prev_level, "current": level},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="a11y",
                    rule="typography_font_family_banned",
                    element=el.get("tag", "unknown"),
                    message=f"Banned font family: {el.get('font_family', '')}",
                    fix="Use a distinctive font, not overused Inter/Roboto/Arial.",
                    metric={"font_family": el.get("font_family", "")},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="a11y",
                    rule="typography_max_line_length",
                    element=el.get("tag", "unknown"),
                    message=f"Line length {width}ch exceeds max {adjusted_max:.0f}ch",
                    fix="Limit line length to ~80 characters for readability.",
                    metric={"line_length": width, "max_recommended": adjusted_max},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="a11y",
                    rule="typography_letter_spacing",
                    element=el.get("tag", "unknown"),
                    message=f"letter-spacing {ls}em outside normal range",
                    fix="Keep letter-spacing between -0.05em and 0.1em.",
                    metric={"letter_spacing": ls},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="a11y",
                    rule="typography_font_weight_contrast",
                    element=f"h{h.get('level', '?')}",
                    message=f"Heading weight {hw} too close to body {body_weight}",
                    fix="Increase heading font-weight contrast (≥200 difference).",
                    metric={"heading_weight": hw, "body_weight": body_weight},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="a11y",
                    rule="typography_text_alignment",
                    element=el.get("tag", "unknown"),
                    message="Body text is justified, causing irregular spacing",
                    fix="Use left-align for body text instead of justify.",
                    metric={"text_align": align},
                )
            )
    return issues
