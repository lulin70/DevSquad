"""V4.3.0 P1-5: UI/UX sub-item audit registry.

Defines the sub-item catalog for each of the 4 UIUX dimensions
(a11y / interaction / layout / ux_antipattern). Each dimension exposes
identifiable sub-items that UIUXAnalyzer.audit_subitems() can audit
individually. Missing sub-items are auto-added with NOT_IMPLEMENTED
status; existing sub-items are preserved (no coverage regression).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

SubItemStatus = Literal["PASS", "WARN", "FAIL", "NOT_IMPLEMENTED"]

_DIMENSIONS: tuple[str, ...] = ("a11y", "interaction", "layout", "ux_antipattern")


@dataclass(frozen=True)
class SubItemDef:
    """Static definition of a sub-item within a UIUX dimension."""

    name: str
    dimension: str
    description: str
    fix_suggestion: str
    implemented: bool = False
    rules: tuple[str, ...] = ()


@dataclass
class SubItemAuditResult:
    """Result of auditing a single sub-item."""

    name: str
    dimension: str
    status: SubItemStatus
    detail: str
    fix_suggestion: str


# ── Sub-item registry (V4.3.0 P1-5) ──────────────────────────────────────────
# Each entry maps a sub-item to its implementation status and the
# UIUXAnalyzer rule IDs that cover it. implemented=False means the
# analyzer has no corresponding rule yet (auto-added as NOT_IMPLEMENTED).
_REGISTRY: dict[str, list[SubItemDef]] = {
    "a11y": [
        SubItemDef("color_contrast_ratio", "a11y", "WCAG AA contrast ratio check", "Ensure text/background contrast >= 4.5:1", True, ("wcag_contrast", "hsv_harsh_combination")),
        SubItemDef("aria_labels_presence", "a11y", "ARIA labels on form inputs", "Add aria-label or <label for> to inputs", True, ("input_missing_label",)),
        SubItemDef("keyboard_navigation_support", "a11y", "Keyboard navigation support", "Ensure all interactive elements are keyboard reachable", False),
        SubItemDef("focus_visibility", "a11y", "Focus indicator visibility", "Provide visible :focus outline", True, ("focus_outline_removed",)),
        SubItemDef("image_alt_text", "a11y", "Image alt text presence", "Add descriptive alt attributes", True, ("img_missing_alt",)),
    ],
    "interaction": [
        SubItemDef("click_target_size", "interaction", "Click target >= 44px", "Increase touch target to >= 44x44px", True, ("button_too_small",)),
        SubItemDef("hover_focus_feedback", "interaction", "Hover/focus visual feedback", "Add :hover and :focus styles", False),
        SubItemDef("form_validation_feedback", "interaction", "Form validation feedback", "Add required attrs and validation messages", True, ("form_no_validation",)),
        SubItemDef("loading_state_indication", "interaction", "Loading state indication", "Show spinner or skeleton during async ops", False),
        SubItemDef("error_recovery_path", "interaction", "Error recovery path", "Provide retry/undo on failure", False),
    ],
    "layout": [
        SubItemDef("4pt_grid_spacing_compliance", "layout", "4pt grid spacing (V4.1.0 P2-UI-4)", "Use multiples of 4 for spacing", True, ("spacing_4pt_grid",)),
        SubItemDef("responsive_breakpoint_coverage", "layout", "Responsive breakpoint coverage", "Add media queries for common breakpoints", False),
        SubItemDef("container_overflow_check", "layout", "Container overflow check", "Prevent horizontal viewport overflow", True, ("viewport_overflow", "element_overlap")),
        SubItemDef("text_truncation_detection", "layout", "Text truncation detection", "Add tooltips for truncated text", True, ("text_truncation",)),
        SubItemDef("z_index_stacking_order", "layout", "Z-index stacking order", "Document and constrain z-index layers", False),
    ],
    "ux_antipattern": [
        SubItemDef("oklch_color_space_compliance", "ux_antipattern", "OKLCH color space support (V4.1.0 P1-UI-3)", "Use oklch() for perceptual color mixing", True),
        SubItemDef("dark_mode_support", "ux_antipattern", "Dark mode support", "Add prefers-color-scheme media query", False),
        SubItemDef("empty_state_design", "ux_antipattern", "Empty state design", "Design helpful empty states", False),
        SubItemDef("error_message_clarity", "ux_antipattern", "Error message clarity", "Write actionable error messages", False),
        SubItemDef("progressive_disclosure", "ux_antipattern", "Progressive disclosure", "Reveal advanced options progressively", False),
    ],
}


def get_subitems_for_dimension(dimension: str) -> list[SubItemDef]:
    """Return the sub-item definitions for a UIUX dimension.

    Args:
        dimension: One of "a11y", "interaction", "layout", "ux_antipattern".

    Returns:
        List of SubItemDef for the dimension; empty for unknown dimensions.
    """
    return list(_REGISTRY.get(dimension, []))


def get_all_subitems() -> list[SubItemDef]:
    """Return all sub-item definitions across all 4 dimensions."""
    return [item for dim in _DIMENSIONS for item in _REGISTRY[dim]]


def get_dimensions() -> tuple[str, ...]:
    """Return the 4 supported UIUX dimensions."""
    return _DIMENSIONS


def format_subitem_report(results: list[SubItemAuditResult]) -> str:
    """Format sub-item audit results as a human-readable text report.

    Args:
        results: List of SubItemAuditResult (typically from one dimension).

    Returns:
        Multi-line text report with per-sub-item status and summary counts.
    """
    if not results:
        return "No sub-items audited."
    dimension = results[0].dimension
    counts: dict[str, int] = {"PASS": 0, "WARN": 0, "FAIL": 0, "NOT_IMPLEMENTED": 0}
    lines = [f"UIUX Sub-Item Audit Report — {dimension}", "=" * 50]
    for r in results:
        counts[r.status] = counts.get(r.status, 0) + 1
        lines.append(f"  [{r.status:16s}] {r.name}: {r.detail}")
    lines.append("=" * 50)
    lines.append(
        f"Summary: {counts['PASS']} PASS, {counts['WARN']} WARN, "
        f"{counts['FAIL']} FAIL, {counts['NOT_IMPLEMENTED']} NOT_IMPLEMENTED"
    )
    return "\n".join(lines)
