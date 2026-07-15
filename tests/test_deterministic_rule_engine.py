#!/usr/bin/env python3
"""Tests for DeterministicRuleEngine (V4.1.0 UI-P0-1) — 46 deterministic UI/UX rules.

Coverage:
  - Structure: rule count = 46, pillar counts, unique rule_ids
  - Typography (8): line_height, font_size, heading_hierarchy, banned_fonts
  - Color (8): contrast (a11y never adjusted), saturation, palette_count, oklch
  - Spatial (6): 4pt_grid, element_density, padding_min, whitespace_ratio
  - Responsiveness (6): viewport_overflow, touch_target, breakpoint_coverage
  - Interactions (8): button_min_size, focus_visible, destructive_confirm, form_validation
  - Motion (5): duration_max, bounce_easing, width_height_anim, reduced_motion
  - UX writing (5): button_text_clarity, error_message, link_text, heading_descriptive
  - TasteDials integration: non-a11y adjusted, a11y NOT adjusted
  - Graceful degradation: missing probes → empty list
  - Fail-safe: exception in one rule doesn't stop others
  - Severity sorting: critical > warning > info
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.qa.deterministic_rule_engine import (
    PILLAR_TO_CATEGORY,
    SEVEN_PILLARS,
    SEVERITY_ERROR,
    SEVERITY_INFO,
    SEVERITY_WARNING,
    DeterministicRuleEngine,
)
from scripts.qa.taste_dials import TasteDials


class TestRuleEngineStructure(unittest.TestCase):
    """Verify rule library structure and counts."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_total_rule_count_is_46(self) -> None:
        """Verify: engine has exactly 46 rules (8+8+6+6+8+5+5)."""
        self.assertEqual(self.engine.rule_count, 46)

    def test_seven_pillars_defined(self) -> None:
        """Verify: SEVEN_PILLARS contains 7 pillar names."""
        self.assertEqual(len(SEVEN_PILLARS), 7)
        for pillar in SEVEN_PILLARS:
            self.assertIn(pillar, PILLAR_TO_CATEGORY)

    def test_pillar_counts_match_spec(self) -> None:
        """Verify: pillar counts match architecture spec (8/8/6/6/8/5/5)."""
        counts = self.engine.get_pillar_counts()
        self.assertEqual(counts["typography"], 8)
        self.assertEqual(counts["color"], 8)
        self.assertEqual(counts["spatial"], 6)
        self.assertEqual(counts["responsiveness"], 6)
        self.assertEqual(counts["interactions"], 8)
        self.assertEqual(counts["motion"], 5)
        self.assertEqual(counts["ux_writing"], 5)

    def test_all_rule_ids_are_unique(self) -> None:
        """Verify: all 46 rule_ids are unique."""
        rule_ids = [r.rule_id for r in self.engine.rules]
        self.assertEqual(len(rule_ids), len(set(rule_ids)))

    def test_all_pillars_have_rules(self) -> None:
        """Verify: every pillar in SEVEN_PILLARS has at least 1 rule."""
        for pillar in SEVEN_PILLARS:
            rules = self.engine.get_rules_by_pillar(pillar)
            self.assertGreater(len(rules), 0, f"Pillar '{pillar}' has no rules")

    def test_every_rule_has_check_fn(self) -> None:
        """Verify: every rule has a callable check_fn."""
        for rule in self.engine.rules:
            self.assertTrue(callable(rule.check_fn), f"{rule.rule_id} check_fn not callable")

    def test_every_rule_has_fix_hint(self) -> None:
        """Verify: every rule has a non-empty fix_hint."""
        for rule in self.engine.rules:
            self.assertTrue(rule.fix_hint, f"{rule.rule_id} has empty fix_hint")

    def test_every_rule_has_valid_severity(self) -> None:
        """Verify: every rule severity is one of critical/warning/info."""
        valid = {SEVERITY_ERROR, SEVERITY_WARNING, SEVERITY_INFO}
        for rule in self.engine.rules:
            self.assertIn(rule.severity, valid, f"{rule.rule_id} has invalid severity")

    def test_rules_property_returns_copy(self) -> None:
        """Verify: rules property returns a copy (not internal list)."""
        rules1 = self.engine.rules
        rules2 = self.engine.rules
        self.assertIsNot(rules1, rules2)


class TestTypographyRules(unittest.TestCase):
    """Verify typography pillar rules (8 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_line_height_below_minimum_detected(self) -> None:
        """Verify: line-height < 1.4 is flagged."""
        probes = {"typography": {"text_styles": [
            {"tag": "p", "line_height": 1.2},
        ]}}
        issues = self.engine.check(probes)
        lh_issues = [i for i in issues if i.rule == "typography_line_height"]
        self.assertEqual(len(lh_issues), 1)
        self.assertEqual(lh_issues[0].severity, SEVERITY_WARNING)

    def test_line_height_ok_no_issue(self) -> None:
        """Verify: line-height >= 1.4 produces no issue."""
        probes = {"typography": {"text_styles": [
            {"tag": "p", "line_height": 1.5},
        ]}}
        issues = self.engine.check(probes)
        lh_issues = [i for i in issues if i.rule == "typography_line_height"]
        self.assertEqual(len(lh_issues), 0)

    def test_font_size_below_minimum_detected(self) -> None:
        """Verify: font-size < 14px is flagged."""
        probes = {"typography": {"text_styles": [
            {"tag": "span", "font_size_px": 11},
        ]}}
        issues = self.engine.check(probes)
        fs_issues = [i for i in issues if i.rule == "typography_font_size_min"]
        self.assertEqual(len(fs_issues), 1)

    def test_heading_hierarchy_skip_detected(self) -> None:
        """Verify: h1→h3 skip is flagged."""
        probes = {"typography": {"headings": [
            {"level": 1, "text": "Title"},
            {"level": 3, "text": "Section"},
        ]}}
        issues = self.engine.check(probes)
        hh_issues = [i for i in issues if i.rule == "typography_heading_hierarchy"]
        self.assertEqual(len(hh_issues), 1)
        self.assertIn("h1", hh_issues[0].message)
        self.assertIn("h3", hh_issues[0].message)

    def test_banned_font_detected(self) -> None:
        """Verify: Inter/Roboto/Arial fonts are flagged."""
        probes = {"typography": {"text_styles": [
            {"tag": "body", "font_family": "Inter, sans-serif"},
        ]}}
        issues = self.engine.check(probes)
        font_issues = [i for i in issues if i.rule == "typography_font_family_banned"]
        self.assertEqual(len(font_issues), 1)
        self.assertEqual(font_issues[0].severity, SEVERITY_INFO)

    def test_text_alignment_justified_detected(self) -> None:
        """Verify: text-align: justify is flagged."""
        probes = {"typography": {"text_styles": [
            {"tag": "p", "text_align": "justify"},
        ]}}
        issues = self.engine.check(probes)
        align_issues = [i for i in issues if i.rule == "typography_text_alignment"]
        self.assertEqual(len(align_issues), 1)


class TestColorRules(unittest.TestCase):
    """Verify color pillar rules (8 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_contrast_normal_below_wcag_aa_detected(self) -> None:
        """Verify: contrast ratio < 4.5 is flagged as critical."""
        probes = {"a11y": {"text_contrast": [
            {"text": "Hello", "contrast_ratio": 3.0},
        ]}}
        issues = self.engine.check(probes)
        c_issues = [i for i in issues if i.rule == "color_contrast_ratio_normal"]
        self.assertEqual(len(c_issues), 1)
        self.assertEqual(c_issues[0].severity, SEVERITY_ERROR)

    def test_contrast_normal_ok_no_issue(self) -> None:
        """Verify: contrast ratio >= 4.5 produces no issue."""
        probes = {"a11y": {"text_contrast": [
            {"text": "Hello", "contrast_ratio": 7.0},
        ]}}
        issues = self.engine.check(probes)
        c_issues = [i for i in issues if i.rule == "color_contrast_ratio_normal"]
        self.assertEqual(len(c_issues), 0)

    def test_harsh_saturation_detected(self) -> None:
        """Verify: HSV saturation > 0.6 is flagged."""
        probes = {"color": {"palette": [
            {"hex": "#FF0000", "hsv_saturation": 0.9},
        ]}}
        issues = self.engine.check(probes)
        sat_issues = [i for i in issues if i.rule == "color_harsh_saturation"]
        self.assertEqual(len(sat_issues), 1)
        self.assertEqual(sat_issues[0].severity, SEVERITY_WARNING)

    def test_palette_count_exceeded_detected(self) -> None:
        """Verify: palette with >5 colors is flagged."""
        probes = {"color": {"palette": [
            {"hex": f"#00000{i}"} for i in range(7)
        ]}}
        issues = self.engine.check(probes)
        pc_issues = [i for i in issues if i.rule == "color_palette_count"]
        self.assertEqual(len(pc_issues), 1)

    def test_oklch_not_used_detected(self) -> None:
        """Verify: no OKLCH colors is flagged as info."""
        probes = {"color": {"palette": [
            {"hex": "#333333", "color_space": "hex"},
        ]}}
        issues = self.engine.check(probes)
        oklch_issues = [i for i in issues if i.rule == "color_oklch_usage"]
        self.assertEqual(len(oklch_issues), 1)
        self.assertEqual(oklch_issues[0].severity, SEVERITY_INFO)

    def test_oklch_used_no_issue(self) -> None:
        """Verify: OKLCH colors present produces no issue."""
        probes = {"color": {"palette": [
            {"hex": "#333333", "color_space": "oklch"},
        ]}}
        issues = self.engine.check(probes)
        oklch_issues = [i for i in issues if i.rule == "color_oklch_usage"]
        self.assertEqual(len(oklch_issues), 0)


class TestSpatialRules(unittest.TestCase):
    """Verify spatial design pillar rules (6 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_non_4pt_grid_spacing_detected(self) -> None:
        """Verify: spacing value not on 4pt grid is flagged."""
        probes = {"spatial": {"spacing_values": [
            {"property": "margin", "value": 7},
        ]}}
        issues = self.engine.check(probes)
        grid_issues = [i for i in issues if i.rule == "spatial_4pt_grid"]
        self.assertEqual(len(grid_issues), 1)

    def test_4pt_grid_spacing_ok_no_issue(self) -> None:
        """Verify: 4pt grid value produces no issue."""
        probes = {"spatial": {"spacing_values": [
            {"property": "margin", "value": 16},
        ]}}
        issues = self.engine.check(probes)
        grid_issues = [i for i in issues if i.rule == "spatial_4pt_grid"]
        self.assertEqual(len(grid_issues), 0)

    def test_element_density_exceeded_detected(self) -> None:
        """Verify: element count > 50 is flagged."""
        probes = {"layout": {"element_count": 75}}
        issues = self.engine.check(probes)
        density_issues = [i for i in issues if i.rule == "spatial_element_density"]
        self.assertEqual(len(density_issues), 1)
        self.assertEqual(density_issues[0].severity, SEVERITY_WARNING)

    def test_padding_below_min_detected(self) -> None:
        """Verify: padding < 8px is flagged."""
        probes = {"spatial": {"padding_values": [
            {"tag": "div", "padding": 4},
        ]}}
        issues = self.engine.check(probes)
        pad_issues = [i for i in issues if i.rule == "spatial_padding_min"]
        self.assertEqual(len(pad_issues), 1)


class TestResponsivenessRules(unittest.TestCase):
    """Verify responsiveness pillar rules (6 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_viewport_overflow_detected(self) -> None:
        """Verify: viewport overflow is flagged as critical."""
        probes = {"layout": {"viewport_overflow": True}}
        issues = self.engine.check(probes)
        overflow_issues = [i for i in issues if i.rule == "responsive_viewport_overflow"]
        self.assertEqual(len(overflow_issues), 1)
        self.assertEqual(overflow_issues[0].severity, SEVERITY_ERROR)

    def test_touch_target_too_small_detected(self) -> None:
        """Verify: touch target < 44px is flagged."""
        probes = {"interaction": {"buttons": [
            {"text": "OK", "width": 30, "height": 30},
        ]}}
        issues = self.engine.check(probes)
        touch_issues = [i for i in issues if i.rule == "responsive_touch_target"]
        self.assertEqual(len(touch_issues), 1)

    def test_missing_breakpoints_detected(self) -> None:
        """Verify: missing sm/md/lg/xl breakpoints are flagged."""
        probes = {"responsiveness": {"breakpoints": ["sm", "md"]}}
        issues = self.engine.check(probes)
        bp_issues = [i for i in issues if i.rule == "responsive_breakpoint_coverage"]
        self.assertEqual(len(bp_issues), 1)
        self.assertIn("lg", bp_issues[0].metric["missing"])
        self.assertIn("xl", bp_issues[0].metric["missing"])

    def test_all_breakpoints_present_no_issue(self) -> None:
        """Verify: all 4 breakpoints present produces no issue."""
        probes = {"responsiveness": {"breakpoints": ["sm", "md", "lg", "xl"]}}
        issues = self.engine.check(probes)
        bp_issues = [i for i in issues if i.rule == "responsive_breakpoint_coverage"]
        self.assertEqual(len(bp_issues), 0)


class TestInteractionRules(unittest.TestCase):
    """Verify interactions pillar rules (8 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_button_too_small_detected(self) -> None:
        """Verify: button with too_small=True is flagged."""
        probes = {"interaction": {"buttons": [
            {"text": "Submit", "width": 30, "height": 20, "too_small": True},
        ]}}
        issues = self.engine.check(probes)
        btn_issues = [i for i in issues if i.rule == "interaction_button_min_size"]
        self.assertEqual(len(btn_issues), 1)

    def test_focus_outline_removed_detected(self) -> None:
        """Verify: removed focus outline is flagged as critical."""
        probes = {"interaction": {"focus_styles": [
            {"outline_removed": True},
        ]}}
        issues = self.engine.check(probes)
        focus_issues = [i for i in issues if i.rule == "interaction_focus_visible"]
        self.assertEqual(len(focus_issues), 1)
        self.assertEqual(focus_issues[0].severity, SEVERITY_ERROR)

    def test_destructive_without_confirm_detected(self) -> None:
        """Verify: destructive action without confirm is flagged as critical."""
        probes = {"ux": {"destructive_without_confirm": [
            {"text": "Delete Account", "tag": "button"},
        ]}}
        issues = self.engine.check(probes)
        dest_issues = [i for i in issues if i.rule == "interaction_destructive_confirm"]
        self.assertEqual(len(dest_issues), 1)
        self.assertEqual(dest_issues[0].severity, SEVERITY_ERROR)

    def test_form_without_validation_detected(self) -> None:
        """Verify: form with inputs but no required fields is flagged."""
        probes = {"ux": {"forms": [
            {"action": "/submit", "input_count": 3, "required_count": 0, "no_validation": True},
        ]}}
        issues = self.engine.check(probes)
        form_issues = [i for i in issues if i.rule == "interaction_form_validation"]
        self.assertEqual(len(form_issues), 1)


class TestMotionRules(unittest.TestCase):
    """Verify motion pillar rules (5 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_animation_duration_too_long_detected(self) -> None:
        """Verify: animation duration > 1000ms is flagged."""
        probes = {"motion": {"animations": [
            {"property": "opacity", "duration_ms": 2000, "easing": "ease"},
        ]}}
        issues = self.engine.check(probes)
        dur_issues = [i for i in issues if i.rule == "motion_duration_max"]
        self.assertEqual(len(dur_issues), 1)

    def test_bounce_easing_detected(self) -> None:
        """Verify: bounce easing is flagged."""
        probes = {"motion": {"animations": [
            {"property": "transform", "duration_ms": 500, "easing": "cubic-bezier(bounce)"},
        ]}}
        issues = self.engine.check(probes)
        bounce_issues = [i for i in issues if i.rule == "motion_no_bounce_easing"]
        self.assertEqual(len(bounce_issues), 1)

    def test_width_height_animation_detected(self) -> None:
        """Verify: animating width/height is flagged."""
        probes = {"motion": {"animations": [
            {"property": "width", "duration_ms": 300, "easing": "ease-out"},
        ]}}
        issues = self.engine.check(probes)
        wh_issues = [i for i in issues if i.rule == "motion_no_width_height_anim"]
        self.assertEqual(len(wh_issues), 1)
        self.assertIn("width", wh_issues[0].message)

    def test_missing_reduced_motion_query_detected(self) -> None:
        """Verify: animations without prefers-reduced-motion is flagged."""
        probes = {
            "motion": {
                "animations": [{"property": "opacity", "duration_ms": 300, "easing": "ease"}],
                "has_reduced_motion_query": False,
            }
        }
        issues = self.engine.check(probes)
        rm_issues = [i for i in issues if i.rule == "motion_reduced_motion"]
        self.assertEqual(len(rm_issues), 1)

    def test_has_reduced_motion_query_no_issue(self) -> None:
        """Verify: animations with prefers-reduced-motion produces no issue."""
        probes = {
            "motion": {
                "animations": [{"property": "opacity", "duration_ms": 300, "easing": "ease"}],
                "has_reduced_motion_query": True,
            }
        }
        issues = self.engine.check(probes)
        rm_issues = [i for i in issues if i.rule == "motion_reduced_motion"]
        self.assertEqual(len(rm_issues), 0)


class TestUXWritingRules(unittest.TestCase):
    """Verify UX writing pillar rules (5 rules)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_vague_button_text_detected(self) -> None:
        """Verify: vague button text 'Click Here' is flagged."""
        probes = {"interaction": {"buttons": [
            {"text": "Click Here", "width": 100, "height": 44},
        ]}}
        issues = self.engine.check(probes)
        btn_issues = [i for i in issues if i.rule == "ux_button_text_clarity"]
        self.assertEqual(len(btn_issues), 1)

    def test_actionable_button_text_no_issue(self) -> None:
        """Verify: actionable button text produces no issue."""
        probes = {"interaction": {"buttons": [
            {"text": "Save Changes", "width": 100, "height": 44},
        ]}}
        issues = self.engine.check(probes)
        btn_issues = [i for i in issues if i.rule == "ux_button_text_clarity"]
        self.assertEqual(len(btn_issues), 0)

    def test_unhelpful_error_message_detected(self) -> None:
        """Verify: unhelpful error message 'Error' is flagged."""
        probes = {"ux": {"error_messages": [
            {"text": "Error"},
        ]}}
        issues = self.engine.check(probes)
        err_issues = [i for i in issues if i.rule == "ux_error_message_clarity"]
        self.assertEqual(len(err_issues), 1)

    def test_vague_link_text_detected(self) -> None:
        """Verify: vague link text 'Read More' is flagged."""
        probes = {"ux": {"links": [
            {"text": "Read More"},
        ]}}
        issues = self.engine.check(probes)
        link_issues = [i for i in issues if i.rule == "ux_link_text_descriptive"]
        self.assertEqual(len(link_issues), 1)

    def test_vague_heading_detected(self) -> None:
        """Verify: vague heading 'Title' is flagged."""
        probes = {"typography": {"headings": [
            {"level": 1, "text": "Title"},
        ]}}
        issues = self.engine.check(probes)
        h_issues = [i for i in issues if i.rule == "ux_heading_descriptive"]
        self.assertEqual(len(h_issues), 1)


class TestTasteDialsIntegration(unittest.TestCase):
    """Verify TasteDials adjusts non-a11y thresholds but NOT a11y thresholds."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_a11y_contrast_not_adjusted_by_dials(self) -> None:
        """Verify: color contrast (a11y) threshold is NOT adjusted by dials.

        Accessibility rules must not be relaxed by taste dials — this is a
        critical design principle. Even with visual_density=1.0, the contrast
        threshold remains 4.5:1.
        """
        probes = {"a11y": {"text_contrast": [
            {"text": "Hello", "contrast_ratio": 4.0},
        ]}}
        # Default dials — should flag (4.0 < 4.5)
        issues_default = self.engine.check(probes, dials=TasteDials())
        # High density dials — should STILL flag (a11y not adjusted)
        issues_high = self.engine.check(probes, dials=TasteDials(visual_density=1.0))
        # Both should flag the contrast issue
        default_contrast = [i for i in issues_default if i.rule == "color_contrast_ratio_normal"]
        high_contrast = [i for i in issues_high if i.rule == "color_contrast_ratio_normal"]
        self.assertEqual(len(default_contrast), 1)
        self.assertEqual(len(high_contrast), 1)
        # Threshold should be the same (4.5) in both cases
        self.assertEqual(default_contrast[0].metric["min_required"], 4.5)
        self.assertEqual(high_contrast[0].metric["min_required"], 4.5)

    def test_non_a11y_layout_threshold_adjusted_by_dials(self) -> None:
        """Verify: spatial element density threshold IS adjusted by dials.

        With visual_density=1.0 (high), the max element count should be
        relaxed (50 * 1.3 = 65), so 55 elements should NOT be flagged.
        With default dials, 55 elements SHOULD be flagged (55 > 50).
        """
        probes = {"layout": {"element_count": 55}}
        # Default dials — should flag (55 > 50)
        issues_default = self.engine.check(probes, dials=TasteDials())
        # High density dials — should NOT flag (55 < 65)
        issues_high = self.engine.check(probes, dials=TasteDials(visual_density=1.0))
        default_density = [i for i in issues_default if i.rule == "spatial_element_density"]
        high_density = [i for i in issues_high if i.rule == "spatial_element_density"]
        self.assertEqual(len(default_density), 1, "Default dials should flag 55 elements")
        self.assertEqual(len(high_density), 0, "High density dials should not flag 55 elements")

    def test_motion_threshold_adjusted_by_dials(self) -> None:
        """Verify: motion duration threshold IS adjusted by dials.

        With motion_intensity=1.0 (high), the max duration should be
        relaxed (1000ms * 1.3 = 1300ms), so 1100ms should NOT be flagged.
        With default dials, 1100ms SHOULD be flagged (1100 > 1000).
        """
        probes = {"motion": {"animations": [
            {"property": "opacity", "duration_ms": 1100, "easing": "ease"},
        ]}}
        # Default dials — should flag (1100 > 1000)
        issues_default = self.engine.check(probes, dials=TasteDials())
        # High motion dials — should NOT flag (1100 < 1300)
        issues_high = self.engine.check(probes, dials=TasteDials(motion_intensity=1.0))
        default_motion = [i for i in issues_default if i.rule == "motion_duration_max"]
        high_motion = [i for i in issues_high if i.rule == "motion_duration_max"]
        self.assertEqual(len(default_motion), 1)
        self.assertEqual(len(high_motion), 0)

    def test_default_dials_produce_same_result_as_none(self) -> None:
        """Verify: passing dials=None uses default dials (no adjustment)."""
        probes = {"layout": {"element_count": 60}}
        issues_none = self.engine.check(probes, dials=None)
        issues_default = self.engine.check(probes, dials=TasteDials())
        # Both should flag (60 > 50 with default dials)
        none_density = [i for i in issues_none if i.rule == "spatial_element_density"]
        default_density = [i for i in issues_default if i.rule == "spatial_element_density"]
        self.assertEqual(len(none_density), 1)
        self.assertEqual(len(default_density), 1)


class TestGracefulDegradation(unittest.TestCase):
    """Verify rules gracefully handle missing probe data."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_empty_probes_returns_empty_list(self) -> None:
        """Verify: empty probes dict returns no issues."""
        issues = self.engine.check({})
        self.assertEqual(len(issues), 0)

    def test_partial_probes_only_check_available_data(self) -> None:
        """Verify: only rules with matching probe data produce issues."""
        probes = {
            "interaction": {
                "buttons": [{"text": "Save Document", "width": 44, "height": 44}],
                "focus_styles": [{"outline_removed": False}],
            }
            # No typography, color, spatial, motion, ux data
        }
        issues = self.engine.check(probes)
        # Should not crash, and should return 0 issues (all data is clean)
        self.assertEqual(len(issues), 0)

    def test_missing_nested_key_returns_empty(self) -> None:
        """Verify: missing nested key returns empty (not crash)."""
        probes = {"typography": {}}  # No "text_styles" key
        issues = self.engine.check(probes)
        self.assertEqual(len(issues), 0)

    def test_none_values_handled_gracefully(self) -> None:
        """Verify: None values in probe data don't crash rules."""
        probes = {"typography": {"text_styles": None}}
        issues = self.engine.check(probes)
        self.assertEqual(len(issues), 0)


class TestFailSafe(unittest.TestCase):
    """Verify rule exceptions don't stop other rules."""

    def test_rule_exception_does_not_stop_others(self) -> None:
        """Verify: if one rule's check_fn raises, other rules still run.

        This mirrors UIUXAnalyzer's fail-safe philosophy.
        """
        engine = DeterministicRuleEngine()

        # Inject a rule that raises an exception
        def bad_check_fn(probes, dials, context):
            raise ValueError("Simulated rule failure")

        # Replace one rule's check_fn with the bad one
        original_fn = engine._rules[0].check_fn
        engine._rules[0].check_fn = bad_check_fn

        try:
            # Should not raise, should still run other rules
            probes = {"layout": {"viewport_overflow": True}}
            issues = engine.check(probes)
            # The viewport_overflow rule should still have run
            overflow_issues = [i for i in issues if i.rule == "responsive_viewport_overflow"]
            self.assertEqual(len(overflow_issues), 1)
        finally:
            engine._rules[0].check_fn = original_fn


class TestSeveritySorting(unittest.TestCase):
    """Verify issues are sorted by severity (critical > warning > info)."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_issues_sorted_by_severity(self) -> None:
        """Verify: critical issues come before warning, warning before info."""
        probes = {
            "a11y": {"text_contrast": [{"text": "low contrast", "contrast_ratio": 2.0}]},
            "interaction": {"focus_styles": [{"outline_removed": True}]},
            "spatial": {"spacing_values": [{"property": "margin", "value": 7}]},
            "typography": {"text_styles": [{"tag": "span", "font_size_px": 10}]},
        }
        issues = self.engine.check(probes)
        # Should have at least one of each severity
        severities = [i.severity for i in issues]
        self.assertIn(SEVERITY_ERROR, severities)
        self.assertIn(SEVERITY_WARNING, severities)
        self.assertIn(SEVERITY_INFO, severities)
        # Verify sorting: all criticals before warnings before infos
        first_warning_idx = next(
            (i for i, s in enumerate(severities) if s == SEVERITY_WARNING), len(severities)
        )
        first_info_idx = next(
            (i for i, s in enumerate(severities) if s == SEVERITY_INFO), len(severities)
        )
        last_critical_idx = max(
            (i for i, s in enumerate(severities) if s == SEVERITY_ERROR), default=-1
        )
        self.assertLess(last_critical_idx, first_warning_idx,
                        "Critical issues must come before warnings")
        self.assertLess(first_warning_idx, first_info_idx,
                        "Warning issues must come before infos")


class TestPillarToCategoryMapping(unittest.TestCase):
    """Verify pillar-to-category mapping covers all 7 pillars."""

    def test_all_pillars_have_category_mapping(self) -> None:
        """Verify: every pillar in SEVEN_PILLARS has a category mapping."""
        for pillar in SEVEN_PILLARS:
            self.assertIn(pillar, PILLAR_TO_CATEGORY,
                          f"Pillar '{pillar}' missing from PILLAR_TO_CATEGORY")

    def test_all_categories_are_valid(self) -> None:
        """Verify: all mapped categories are valid DevSquad categories."""
        valid_categories = {"a11y", "interaction", "layout", "ux_antipattern"}
        for pillar, category in PILLAR_TO_CATEGORY.items():
            self.assertIn(category, valid_categories,
                          f"Pillar '{pillar}' maps to invalid category '{category}'")


class TestRealWorldScenarios(unittest.TestCase):
    """Integration: realistic probe data from a hypothetical web page."""

    def setUp(self) -> None:
        self.engine = DeterministicRuleEngine()

    def test_clean_page_produces_no_issues(self) -> None:
        """Verify: a clean, well-designed page produces no issues."""
        probes = {
            "a11y": {
                "text_contrast": [{"text": "Hello", "contrast_ratio": 7.0}],
                "inputs": [{"type": "text", "has_label": True, "id": "email",
                            "label_text": "Email Address"}],
            },
            "interaction": {
                "buttons": [{"text": "Save Changes", "width": 120, "height": 44,
                             "too_small": False}],
                "focus_styles": [{"outline_removed": False}],
            },
            "layout": {"viewport_overflow": False, "element_count": 20},
            "ux": {"forms": [{"action": "/save", "input_count": 2,
                              "required_count": 1, "no_validation": False}],
                   "destructive_without_confirm": []},
            "typography": {"text_styles": [
                {"tag": "p", "line_height": 1.6, "font_size_px": 16,
                 "text_align": "left", "color": "#666666"},
            ]},
        }
        issues = self.engine.check(probes)
        self.assertEqual(len(issues), 0,
                         f"Clean page should produce 0 issues, got {len(issues)}: "
                         f"{[i.rule for i in issues]}")

    def test_problematic_page_produces_multiple_issues(self) -> None:
        """Verify: a problematic page produces multiple issues across pillars."""
        probes = {
            "a11y": {
                "text_contrast": [{"text": "low", "contrast_ratio": 2.0}],
                "inputs": [{"type": "text", "has_label": False, "id": "field1",
                            "label_text": "Field 1"}],
            },
            "interaction": {
                "buttons": [{"text": "Click Here", "width": 30, "height": 20,
                             "too_small": True}],
                "focus_styles": [{"outline_removed": True}],
            },
            "layout": {"viewport_overflow": True, "element_count": 80},
            "ux": {"forms": [{"action": "/submit", "input_count": 3,
                              "required_count": 0, "no_validation": True}],
                   "destructive_without_confirm": [
                       {"text": "Delete Account", "tag": "button"}]},
            "motion": {"animations": [
                {"property": "width", "duration_ms": 2000, "easing": "bounce"},
            ]},
        }
        issues = self.engine.check(probes)
        # Should have multiple issues
        self.assertGreater(len(issues), 5,
                           f"Problematic page should produce >5 issues, got {len(issues)}")
        # Should have at least one critical
        self.assertGreater(
            sum(1 for i in issues if i.severity == SEVERITY_ERROR), 0,
            "Should have at least one critical issue"
        )


if __name__ == "__main__":
    unittest.main()
