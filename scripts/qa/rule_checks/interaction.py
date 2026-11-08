"""Interaction rule checks (8).

Button size, focus visibility, hover/active/disabled states, loading
feedback, destructive confirmation and form validation detectors.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_ERROR, SEVERITY_INFO, SEVERITY_WARNING, _safe_get


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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="interaction_button_min_size",
                    element=btn.get("text", "")[:20],
                    message=f"Button {btn.get('width', 0)}×{btn.get('height', 0)}px too small",
                    fix=f"Increase button size to at least {adjusted_min:.0f}×{adjusted_min:.0f}px.",
                    metric={"width": btn.get("width"), "height": btn.get("height")},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_ERROR,
                    category="interaction",
                    rule="interaction_focus_visible",
                    element=":focus",
                    message="Focus outline removed — keyboard accessibility violation",
                    fix="Don't remove focus outlines; style them instead.",
                    metric={"outline_removed": True},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="interaction",
                    rule="interaction_hover_feedback",
                    element=el.get("tag", "unknown"),
                    message="Interactive element missing hover state",
                    fix="Add :hover state for interactive elements.",
                    metric={"has_hover": False},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_INFO,
                    category="interaction",
                    rule="interaction_active_state",
                    element=el.get("tag", "unknown"),
                    message="Interactive element missing :active state",
                    fix="Add :active state for tactile feedback.",
                    metric={"has_active": False},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="interaction_disabled_state",
                    element=el.get("tag", "unknown"),
                    message="Disabled element lacks visual distinction",
                    fix="Style :disabled state with reduced opacity/cursor.",
                    metric={"has_disabled_style": False},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="interaction_loading_feedback",
                    element=op.get("action", "unknown"),
                    message="Async operation missing loading feedback",
                    fix="Show loading spinner/skeleton for async operations.",
                    metric={"has_loading_state": False},
                )
            )
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
        issues.append(
            UIUXIssue(
                severity=SEVERITY_ERROR,
                category="ux_antipattern",
                rule="interaction_destructive_confirm",
                element=el.get("text", "")[:20],
                message="Destructive action without confirmation dialog",
                fix="Add confirmation dialog for destructive actions.",
                metric={"has_confirm": False},
            )
        )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="ux_antipattern",
                    rule="interaction_form_validation",
                    element=form.get("action", "")[:20],
                    message="Form has inputs but no required fields/validation",
                    fix="Add form validation (required fields, type checks).",
                    metric={"input_count": form.get("input_count"), "required_count": form.get("required_count")},
                )
            )
    return issues
