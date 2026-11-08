"""Motion rule checks (5).

Animation duration, bounce easing, width/height animation, glassmorphism
overuse and reduced-motion support detectors.
Each check accepts ``(probes, dials, context)`` and returns ``list[UIUXIssue]``.
"""

from __future__ import annotations

from typing import Any

from ..models import UIUXIssue
from ..taste_dials import TasteDials
from .common import SEVERITY_INFO, SEVERITY_WARNING, _safe_get


def _check_motion_duration_max(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="motion_duration_max",
                    element=anim.get("property", "animation"),
                    message=f"Animation duration {dur}ms exceeds {adjusted_max:.0f}ms",
                    fix="Keep animation duration under 1 second.",
                    metric={"duration": dur, "max_recommended": adjusted_max},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="motion_no_bounce_easing",
                    element=anim.get("property", "animation"),
                    message=f"Bounce easing detected: {easing}",
                    fix="Avoid bounce/elastic easing; use ease-out instead.",
                    metric={"easing": easing},
                )
            )
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
            issues.append(
                UIUXIssue(
                    severity=SEVERITY_WARNING,
                    category="interaction",
                    rule="motion_no_width_height_anim",
                    element=prop,
                    message=f"Animating {prop} causes layout thrashing",
                    fix=f"Use transform: scale() instead of animating {prop}.",
                    metric={"property": prop},
                )
            )
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
        return [
            UIUXIssue(
                severity=SEVERITY_INFO,
                category="interaction",
                rule="motion_no_glassmorphism_overuse",
                element="glassmorphism",
                message=f"Glassmorphism used {glass} times, max {adjusted_max:.0f}",
                fix="Limit glassmorphism to ≤2 instances per page.",
                metric={"count": glass, "max_recommended": adjusted_max},
            )
        ]
    return []


def _check_motion_reduced_motion(probes: dict[str, Any], dials: TasteDials, context: dict[str, Any]) -> list[UIUXIssue]:
    """Check prefers-reduced-motion is respected."""
    has_animations = bool(_safe_get(probes, "motion", "animations", default=[]))
    has_reduced = _safe_get(probes, "motion", "has_reduced_motion_query")
    if has_animations and has_reduced is False:
        return [
            UIUXIssue(
                severity=SEVERITY_WARNING,
                category="interaction",
                rule="motion_reduced_motion",
                element="@media",
                message="Animations present but prefers-reduced-motion not handled",
                fix="Add @media (prefers-reduced-motion: reduce) query.",
                metric={"has_reduced_motion_query": False},
            )
        ]
    return []
