"""Responsiveness rule checks (6).

Viewport overflow, touch target size, image max-width, text overflow,
breakpoint coverage and grid adaptation detectors.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, _safe_get


def _check_responsive_viewport_overflow(
    probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]
) -> list[UIUXIssue]:
    """Check no horizontal scroll (viewport overflow)."""
    overflow = _safe_get(probes, "layout", "viewport_overflow")
    if overflow:
        return [
            UIUXIssue(
                severity=SEVERITY_ERROR,
                category="layout",
                rule="responsive_viewport_overflow",
                element="body",
                message="Horizontal scroll detected (viewport overflow)",
                fix="Prevent content from exceeding viewport width.",
                metric={"viewport_overflow": True},
            )
        ]
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="responsive_touch_target",
                    element=btn.get("text", "")[:20],
                    message=f"Touch target {w}×{h}px below {adjusted_min:.0f}px",
                    fix="Increase touch target to at least 44×44px.",
                    metric={"width": w, "height": h, "min_required": adjusted_min},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="layout",
                    rule="responsive_image_max_width",
                    element=img.get("src", "")[:30],
                    message="Image missing max-width: 100%",
                    fix="Add max-width: 100% to images for responsive layout.",
                    metric={"has_max_width": False},
                )
            )
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
        issues.append(
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="layout",
                rule="responsive_text_overflow",
                element=el.get("tag", "unknown"),
                message="Text truncation detected",
                fix="Avoid truncating important text on smaller screens.",
                metric={"truncated": True},
            )
        )
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
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="layout",
                rule="responsive_breakpoint_coverage",
                element="breakpoints",
                message=f"Missing breakpoints: {missing}",
                fix="Add responsive breakpoints for sm/md/lg/xl.",
                metric={"missing": list(missing)},
            )
        ]
    return []


def _check_responsive_grid_adapt(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check grid layout adapts to viewport."""
    grids = _safe_get(probes, "responsiveness", "grid_layouts", default=[])
    if not grids:
        return []
    issues = []
    for grid in grids:
        if not grid.get("has_media_query"):
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="layout",
                    rule="responsive_grid_adapt",
                    element="grid",
                    message="Grid layout missing media query adaptation",
                    fix="Add media queries to adapt grid columns.",
                    metric={"has_media_query": False},
                )
            )
    return issues
