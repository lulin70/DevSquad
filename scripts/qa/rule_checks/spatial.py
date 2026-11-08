"""Spatial design rule checks (6).

4pt grid adherence, element density, minimum padding, margin consistency,
whitespace ratio and card spacing detectors.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_INFO, SEVERITY_WARNING, _safe_get


def _check_spatial_4pt_grid(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check spacing follows 4pt grid (4/8/16/24/32/48)."""
    spacings = _safe_get(probes, "spatial", "spacing_values", default=[])
    if not spacings:
        return []
    valid = {4, 8, 12, 16, 20, 24, 32, 40, 48, 64}
    issues = []
    for s in spacings:
        val = s.get("value", 0)
        if val and val not in valid:
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="layout",
                    rule="spatial_4pt_grid",
                    element=s.get("property", "spacing"),
                    message=f"Spacing {val}px not on 4pt grid",
                    fix="Use 4pt grid values: 4, 8, 16, 24, 32, 48.",
                    metric={"value": val},
                )
            )
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
        return [
            UIUXIssue(
                severity=SEVERITY_WARNING,
                category="layout",
                rule="spatial_element_density",
                element="viewport",
                message=f"Element count {count} exceeds max {adjusted_max:.0f}",
                fix="Reduce element count or increase whitespace.",
                metric={"count": count, "max_recommended": adjusted_max},
            )
        ]
    return []


def _check_spatial_padding_min(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="layout",
                    rule="spatial_padding_min",
                    element=el.get("tag", "unknown"),
                    message=f"Padding {pad}px below min {adjusted_min:.0f}px",
                    fix="Increase padding to at least 8px.",
                    metric={"padding": pad, "min_required": adjusted_min},
                )
            )
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
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="layout",
                rule="spatial_margin_consistency",
                element="margins",
                message=f"{len(distinct)} distinct margin values, max {adjusted_max:.0f}",
                fix="Standardize margins to ≤3 distinct values.",
                metric={"distinct_count": len(distinct), "max_recommended": adjusted_max},
            )
        ]
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
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="layout",
                rule="spatial_whitespace_ratio",
                element="viewport",
                message=f"Whitespace ratio {ratio:.0%} below {adjusted_min:.0%}",
                fix="Increase whitespace to at least 30% of viewport.",
                metric={"ratio": ratio, "min_recommended": adjusted_min},
            )
        ]
    return []


def _check_spatial_card_spacing(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check card spacing is consistent."""
    cards = _safe_get(probes, "spatial", "card_spacings", default=[])
    if len(cards) < 2:
        return []
    values = [c.get("spacing", 0) for c in cards]
    if len(set(values)) > 2:
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="layout",
                rule="spatial_card_spacing",
                element="cards",
                message=f"Inconsistent card spacing: {set(values)}",
                fix="Use consistent spacing between cards.",
                metric={"spacings": list(set(values))},
            )
        ]
    return []
