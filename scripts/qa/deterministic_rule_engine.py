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
from .rule_checks import (
    _check_color_background_contrast,
    _check_color_contrast_large,
    _check_color_contrast_normal,
    _check_color_contrast_ui,
    _check_color_grayscale_secondary,
    _check_color_harsh_saturation,
    _check_color_oklch_usage,
    _check_color_palette_count,
    _check_interaction_active_state,
    _check_interaction_button_min_size,
    _check_interaction_destructive_confirm,
    _check_interaction_disabled_state,
    _check_interaction_focus_visible,
    _check_interaction_form_validation,
    _check_interaction_hover_feedback,
    _check_interaction_loading_feedback,
    _check_motion_duration_max,
    _check_motion_no_bounce_easing,
    _check_motion_no_glassmorphism_overuse,
    _check_motion_no_width_height_anim,
    _check_motion_reduced_motion,
    _check_responsive_breakpoint_coverage,
    _check_responsive_grid_adapt,
    _check_responsive_image_max_width,
    _check_responsive_text_overflow,
    _check_responsive_touch_target,
    _check_responsive_viewport_overflow,
    _check_spatial_4pt_grid,
    _check_spatial_card_spacing,
    _check_spatial_element_density,
    _check_spatial_margin_consistency,
    _check_spatial_padding_min,
    _check_spatial_whitespace_ratio,
    _check_typography_banned_fonts,
    _check_typography_font_size_min,
    _check_typography_font_weight_contrast,
    _check_typography_heading_hierarchy,
    _check_typography_letter_spacing,
    _check_typography_line_height,
    _check_typography_max_line_length,
    _check_typography_text_alignment,
    _check_ux_button_text_clarity,
    _check_ux_error_message_clarity,
    _check_ux_form_label_clarity,
    _check_ux_heading_descriptive,
    _check_ux_link_text_descriptive,
)
from .rule_checks.common import (
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
)
from .rule_checks.common import (
    _safe_get as _safe_get,
)
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
