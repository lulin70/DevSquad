#!/usr/bin/env python3
"""Tests for TasteDials (V4.1.0 UI-P0-2) — Visual taste dials for UI/UX audit.

Coverage:
  - Defaults: all dials at 0.5, sensitivity 0.3, is_default True
  - Clamping: -1, 2, 0, 1, very large/small values clamp to [0.0, 1.0]
  - is_default: returns False when any dial is modified
  - adjust_threshold: rule_id keyword matching, multiplier math, unknown rule
  - _get_dial_for_rule: keyword groups (density/layout/spacing/grid,
    motion/animation/transition, variance/consistency/uniform), case insensitive
  - to_prompt_fragment: default empty-ish, high/low per dial, multiple dials
  - to_dict / from_dict: round-trip serialization
  - create_preset: minimalist/balanced/rich, unknown raises KeyError
  - Sensitivity edge cases: 0.0, 1.0, negative, >1.0
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.qa.taste_dials import (
    DEFAULT_DIAL,
    DEFAULT_SENSITIVITY,
    MAX_DIAL,
    MIN_DIAL,
    PRESETS,
    TasteDials,
    create_preset,
)


class TestTasteDialsDefaults(unittest.TestCase):
    """Verify default values and is_default property."""

    def test_default_dials_all_at_half(self) -> None:
        """Verify: default TasteDials has all three dials at 0.5."""
        dials = TasteDials()
        self.assertEqual(dials.design_variance, 0.5)
        self.assertEqual(dials.motion_intensity, 0.5)
        self.assertEqual(dials.visual_density, 0.5)

    def test_default_sensitivity_is_point_three(self) -> None:
        """Verify: default sensitivity is 0.3 (±30% adjustment)."""
        dials = TasteDials()
        self.assertEqual(dials.sensitivity, 0.3)

    def test_is_default_true_for_default_dials(self) -> None:
        """Verify: is_default returns True for default configuration."""
        dials = TasteDials()
        self.assertTrue(dials.is_default)

    def test_constants_have_expected_values(self) -> None:
        """Verify: module-level constants match design spec."""
        self.assertEqual(DEFAULT_DIAL, 0.5)
        self.assertEqual(DEFAULT_SENSITIVITY, 0.3)
        self.assertEqual(MIN_DIAL, 0.0)
        self.assertEqual(MAX_DIAL, 1.0)


class TestTasteDialsClamping(unittest.TestCase):
    """Verify value clamping to [0.0, 1.0]."""

    def test_negative_design_variance_clamps_to_zero(self) -> None:
        """Verify: design_variance=-1 clamps to 0.0."""
        dials = TasteDials(design_variance=-1.0)
        self.assertEqual(dials.design_variance, 0.0)

    def test_excess_motion_intensity_clamps_to_one(self) -> None:
        """Verify: motion_intensity=2.0 clamps to 1.0."""
        dials = TasteDials(motion_intensity=2.0)
        self.assertEqual(dials.motion_intensity, 1.0)

    def test_zero_visual_density_stays_zero(self) -> None:
        """Verify: visual_density=0.0 stays at 0.0 (boundary)."""
        dials = TasteDials(visual_density=0.0)
        self.assertEqual(dials.visual_density, 0.0)

    def test_one_visual_density_stays_one(self) -> None:
        """Verify: visual_density=1.0 stays at 1.0 (boundary)."""
        dials = TasteDials(visual_density=1.0)
        self.assertEqual(dials.visual_density, 1.0)

    def test_very_large_value_clamps_to_one(self) -> None:
        """Verify: design_variance=100.0 clamps to 1.0."""
        dials = TasteDials(design_variance=100.0)
        self.assertEqual(dials.design_variance, 1.0)

    def test_very_small_value_clamps_to_zero(self) -> None:
        """Verify: motion_intensity=-99.0 clamps to 0.0."""
        dials = TasteDials(motion_intensity=-99.0)
        self.assertEqual(dials.motion_intensity, 0.0)

    def test_all_dials_clamped_independently(self) -> None:
        """Verify: each dial clamps independently of the others."""
        dials = TasteDials(
            design_variance=-5.0,
            motion_intensity=99.0,
            visual_density=0.7,
        )
        self.assertEqual(dials.design_variance, 0.0)
        self.assertEqual(dials.motion_intensity, 1.0)
        self.assertEqual(dials.visual_density, 0.7)

    def test_half_value_unchanged(self) -> None:
        """Verify: 0.5 (default midpoint) is preserved, not clamped."""
        dials = TasteDials(design_variance=0.5)
        self.assertEqual(dials.design_variance, 0.5)


class TestTasteDialsIsDefault(unittest.TestCase):
    """Verify is_default returns False when any dial is modified."""

    def test_is_default_false_when_variance_modified(self) -> None:
        """Verify: is_default False when design_variance != 0.5."""
        dials = TasteDials(design_variance=0.6)
        self.assertFalse(dials.is_default)

    def test_is_default_false_when_motion_modified(self) -> None:
        """Verify: is_default False when motion_intensity != 0.5."""
        dials = TasteDials(motion_intensity=0.4)
        self.assertFalse(dials.is_default)

    def test_is_default_false_when_density_modified(self) -> None:
        """Verify: is_default False when visual_density != 0.5."""
        dials = TasteDials(visual_density=0.9)
        self.assertFalse(dials.is_default)

    def test_is_default_true_even_with_custom_sensitivity(self) -> None:
        """Verify: is_default only checks dials, not sensitivity.

        Per spec: is_default reflects whether thresholds will be adjusted,
        which depends on dial values, not on the sensitivity scaling factor.
        """
        dials = TasteDials(sensitivity=0.5)
        self.assertTrue(dials.is_default)


class TestTasteDialsSensitivityClamping(unittest.TestCase):
    """Verify sensitivity clamping to [0.0, 1.0]."""

    def test_negative_sensitivity_clamps_to_zero(self) -> None:
        """Verify: sensitivity=-0.5 clamps to 0.0 (no adjustment)."""
        dials = TasteDials(sensitivity=-0.5)
        self.assertEqual(dials.sensitivity, 0.0)

    def test_excess_sensitivity_clamps_to_one(self) -> None:
        """Verify: sensitivity=2.0 clamps to 1.0 (max adjustment)."""
        dials = TasteDials(sensitivity=2.0)
        self.assertEqual(dials.sensitivity, 1.0)

    def test_zero_sensitivity_means_no_adjustment(self) -> None:
        """Verify: sensitivity=0.0 makes adjust_threshold a no-op."""
        dials = TasteDials(sensitivity=0.0, visual_density=1.0)
        # Even with extreme dial, multiplier = 1 + 0.5 * 2 * 0 = 1.0
        self.assertAlmostEqual(dials.adjust_threshold("layout_grid", 10.0), 10.0)


class TestTasteDialsAdjustThreshold(unittest.TestCase):
    """Verify adjust_threshold math and rule_id routing."""

    def test_default_dials_no_adjustment(self) -> None:
        """Verify: default dials (0.5) leave threshold unchanged."""
        dials = TasteDials()
        self.assertEqual(dials.adjust_threshold("layout_density", 10.0), 10.0)
        self.assertEqual(dials.adjust_threshold("motion_animation", 5.0), 5.0)
        self.assertEqual(dials.adjust_threshold("variance_consistency", 3.0), 3.0)

    def test_max_visual_density_relaxes_layout_threshold(self) -> None:
        """Verify: visual_density=1.0 multiplies layout threshold by 1+sensitivity."""
        dials = TasteDials(visual_density=1.0, sensitivity=0.3)
        # multiplier = 1 + (1.0 - 0.5) * 2 * 0.3 = 1.3
        self.assertAlmostEqual(dials.adjust_threshold("layout_density", 10.0), 13.0)

    def test_min_visual_density_tightens_layout_threshold(self) -> None:
        """Verify: visual_density=0.0 multiplies layout threshold by 1-sensitivity."""
        dials = TasteDials(visual_density=0.0, sensitivity=0.3)
        # multiplier = 1 + (0.0 - 0.5) * 2 * 0.3 = 0.7
        self.assertAlmostEqual(dials.adjust_threshold("layout_density", 10.0), 7.0)

    def test_max_motion_relaxes_animation_threshold(self) -> None:
        """Verify: motion_intensity=1.0 multiplies motion threshold by 1+sensitivity."""
        dials = TasteDials(motion_intensity=1.0, sensitivity=0.3)
        self.assertAlmostEqual(dials.adjust_threshold("animation_duration", 4.0), 5.2)

    def test_min_motion_tightens_animation_threshold(self) -> None:
        """Verify: motion_intensity=0.0 multiplies motion threshold by 1-sensitivity."""
        dials = TasteDials(motion_intensity=0.0, sensitivity=0.3)
        self.assertAlmostEqual(dials.adjust_threshold("animation_duration", 4.0), 2.8)

    def test_max_variance_relaxes_consistency_threshold(self) -> None:
        """Verify: design_variance=1.0 multiplies consistency threshold by 1+sensitivity."""
        dials = TasteDials(design_variance=1.0, sensitivity=0.3)
        self.assertAlmostEqual(dials.adjust_threshold("variance_check", 8.0), 10.4)

    def test_min_variance_tightens_consistency_threshold(self) -> None:
        """Verify: design_variance=0.0 multiplies consistency threshold by 1-sensitivity."""
        dials = TasteDials(design_variance=0.0, sensitivity=0.3)
        self.assertAlmostEqual(dials.adjust_threshold("variance_check", 8.0), 5.6)

    def test_unknown_rule_id_returns_base_threshold(self) -> None:
        """Verify: rule_id with no dial keyword returns base_threshold unchanged."""
        dials = TasteDials(visual_density=1.0, motion_intensity=1.0)
        self.assertEqual(dials.adjust_threshold("color_contrast", 7.0), 7.0)
        self.assertEqual(dials.adjust_threshold("aria_label", 1.0), 1.0)

    def test_custom_sensitivity_scales_adjustment(self) -> None:
        """Verify: higher sensitivity produces larger adjustment."""
        dials_low = TasteDials(visual_density=1.0, sensitivity=0.1)
        dials_high = TasteDials(visual_density=1.0, sensitivity=0.5)
        base = 10.0
        # low: 1 + 0.5*2*0.1 = 1.1 → 11.0
        # high: 1 + 0.5*2*0.5 = 1.5 → 15.0
        self.assertAlmostEqual(dials_low.adjust_threshold("layout", base), 11.0)
        self.assertAlmostEqual(dials_high.adjust_threshold("layout", base), 15.0)

    def test_midpoint_dial_value_no_adjustment(self) -> None:
        """Verify: dial=0.5 produces multiplier=1.0 regardless of sensitivity."""
        dials = TasteDials(visual_density=0.5, sensitivity=0.5)
        self.assertAlmostEqual(dials.adjust_threshold("layout", 10.0), 10.0)


class TestTasteDialsGetDialForRule(unittest.TestCase):
    """Verify _get_dial_for_rule keyword matching."""

    def test_density_keyword_routes_to_visual_density(self) -> None:
        """Verify: rule_id containing 'density' uses visual_density dial."""
        dials = TasteDials(visual_density=1.0)
        self.assertEqual(dials._get_dial_for_rule("element_density"), 1.0)

    def test_layout_keyword_routes_to_visual_density(self) -> None:
        """Verify: rule_id containing 'layout' uses visual_density dial."""
        dials = TasteDials(visual_density=0.8)
        self.assertEqual(dials._get_dial_for_rule("layout_grid"), 0.8)

    def test_spacing_keyword_routes_to_visual_density(self) -> None:
        """Verify: rule_id containing 'spacing' uses visual_density dial."""
        dials = TasteDials(visual_density=0.2)
        self.assertEqual(dials._get_dial_for_rule("spacing_check"), 0.2)

    def test_grid_keyword_routes_to_visual_density(self) -> None:
        """Verify: rule_id containing 'grid' uses visual_density dial."""
        dials = TasteDials(visual_density=0.3)
        self.assertEqual(dials._get_dial_for_rule("grid_alignment"), 0.3)

    def test_motion_keyword_routes_to_motion_intensity(self) -> None:
        """Verify: rule_id containing 'motion' uses motion_intensity dial."""
        dials = TasteDials(motion_intensity=0.9)
        self.assertEqual(dials._get_dial_for_rule("motion_duration"), 0.9)

    def test_animation_keyword_routes_to_motion_intensity(self) -> None:
        """Verify: rule_id containing 'animation' uses motion_intensity dial."""
        dials = TasteDials(motion_intensity=0.7)
        self.assertEqual(dials._get_dial_for_rule("animation_easing"), 0.7)

    def test_transition_keyword_routes_to_motion_intensity(self) -> None:
        """Verify: rule_id containing 'transition' uses motion_intensity dial."""
        dials = TasteDials(motion_intensity=0.4)
        self.assertEqual(dials._get_dial_for_rule("page_transition"), 0.4)

    def test_variance_keyword_routes_to_design_variance(self) -> None:
        """Verify: rule_id containing 'variance' uses design_variance dial."""
        dials = TasteDials(design_variance=0.6)
        self.assertEqual(dials._get_dial_for_rule("variance_score"), 0.6)

    def test_consistency_keyword_routes_to_design_variance(self) -> None:
        """Verify: rule_id containing 'consistency' uses design_variance dial."""
        dials = TasteDials(design_variance=0.1)
        self.assertEqual(dials._get_dial_for_rule("consistency_check"), 0.1)

    def test_uniform_keyword_routes_to_design_variance(self) -> None:
        """Verify: rule_id containing 'uniform' uses design_variance dial.

        Note: rule_id must not contain keywords from other dials (e.g.
        'spacing' belongs to visual_density). Using 'uniform_pattern'
        isolates the 'uniform' keyword to test design_variance routing.
        """
        dials = TasteDials(design_variance=0.9)
        self.assertEqual(dials._get_dial_for_rule("uniform_pattern"), 0.9)

    def test_unknown_keyword_returns_none(self) -> None:
        """Verify: rule_id with no matching keyword returns None."""
        dials = TasteDials()
        self.assertIsNone(dials._get_dial_for_rule("color_palette"))
        self.assertIsNone(dials._get_dial_for_rule("aria_label"))
        self.assertIsNone(dials._get_dial_for_rule("font_family"))

    def test_case_insensitive_matching(self) -> None:
        """Verify: keyword matching is case insensitive."""
        dials = TasteDials(visual_density=0.8, motion_intensity=0.7, design_variance=0.6)
        self.assertEqual(dials._get_dial_for_rule("LAYOUT_DENSITY"), 0.8)
        self.assertEqual(dials._get_dial_for_rule("MOTION_INTENSITY"), 0.7)
        self.assertEqual(dials._get_dial_for_rule("VARIANCE_CHECK"), 0.6)


class TestTasteDialsPromptFragment(unittest.TestCase):
    """Verify to_prompt_fragment output."""

    def test_default_dials_produce_default_fragment(self) -> None:
        """Verify: default dials produce 'Taste Dials: default (no adjustment)'."""
        dials = TasteDials()
        fragment = dials.to_prompt_fragment()
        self.assertEqual(fragment, "Taste Dials: default (no adjustment)")

    def test_high_variance_fragment(self) -> None:
        """Verify: design_variance=1.0 produces 'variance=high(1.00)' in fragment."""
        dials = TasteDials(design_variance=1.0)
        fragment = dials.to_prompt_fragment()
        self.assertIn("variance=high", fragment)
        self.assertIn("1.00", fragment)

    def test_low_motion_fragment(self) -> None:
        """Verify: motion_intensity=0.1 produces 'motion=low(0.10)' in fragment."""
        dials = TasteDials(motion_intensity=0.1)
        fragment = dials.to_prompt_fragment()
        self.assertIn("motion=low", fragment)
        self.assertIn("0.10", fragment)

    def test_high_density_fragment(self) -> None:
        """Verify: visual_density=0.9 produces 'density=high(0.90)' in fragment."""
        dials = TasteDials(visual_density=0.9)
        fragment = dials.to_prompt_fragment()
        self.assertIn("density=high", fragment)
        self.assertIn("0.90", fragment)

    def test_multiple_dials_in_fragment(self) -> None:
        """Verify: multiple modified dials all appear in fragment."""
        dials = TasteDials(
            design_variance=0.8,
            motion_intensity=0.2,
            visual_density=0.9,
        )
        fragment = dials.to_prompt_fragment()
        self.assertIn("variance=high", fragment)
        self.assertIn("motion=low", fragment)
        self.assertIn("density=high", fragment)

    def test_different_dials_produce_different_fragments(self) -> None:
        """Verify: different dial values produce different fragments."""
        dials_low = TasteDials(visual_density=0.1)
        dials_high = TasteDials(visual_density=0.9)
        self.assertNotEqual(
            dials_low.to_prompt_fragment(),
            dials_high.to_prompt_fragment(),
        )


class TestTasteDialsSerialization(unittest.TestCase):
    """Verify to_dict / from_dict round-trip."""

    def test_to_dict_contains_all_fields(self) -> None:
        """Verify: to_dict contains all four fields."""
        dials = TasteDials(design_variance=0.7, motion_intensity=0.4, visual_density=0.8)
        d = dials.to_dict()
        self.assertIn("design_variance", d)
        self.assertIn("motion_intensity", d)
        self.assertIn("visual_density", d)
        self.assertIn("sensitivity", d)

    def test_to_dict_values_match_instance(self) -> None:
        """Verify: to_dict values match the instance attributes."""
        dials = TasteDials(design_variance=0.7, motion_intensity=0.4, visual_density=0.8)
        d = dials.to_dict()
        self.assertEqual(d["design_variance"], 0.7)
        self.assertEqual(d["motion_intensity"], 0.4)
        self.assertEqual(d["visual_density"], 0.8)
        self.assertEqual(d["sensitivity"], 0.3)

    def test_from_dict_round_trip(self) -> None:
        """Verify: from_dict(to_dict()) produces equivalent instance."""
        original = TasteDials(
            design_variance=0.7,
            motion_intensity=0.4,
            visual_density=0.8,
            sensitivity=0.5,
        )
        restored = TasteDials.from_dict(original.to_dict())
        self.assertEqual(restored.design_variance, 0.7)
        self.assertEqual(restored.motion_intensity, 0.4)
        self.assertEqual(restored.visual_density, 0.8)
        self.assertEqual(restored.sensitivity, 0.5)

    def test_from_dict_with_missing_fields_uses_defaults(self) -> None:
        """Verify: from_dict with missing fields falls back to defaults."""
        restored = TasteDials.from_dict({})
        self.assertEqual(restored.design_variance, DEFAULT_DIAL)
        self.assertEqual(restored.motion_intensity, DEFAULT_DIAL)
        self.assertEqual(restored.visual_density, DEFAULT_DIAL)
        self.assertEqual(restored.sensitivity, DEFAULT_SENSITIVITY)

    def test_from_dict_with_partial_data(self) -> None:
        """Verify: from_dict accepts partial data and uses defaults for missing."""
        restored = TasteDials.from_dict({"visual_density": 0.9})
        self.assertEqual(restored.visual_density, 0.9)
        self.assertEqual(restored.design_variance, DEFAULT_DIAL)
        self.assertEqual(restored.motion_intensity, DEFAULT_DIAL)

    def test_from_dict_clamps_invalid_values(self) -> None:
        """Verify: from_dict clamps out-of-range values via __post_init__."""
        restored = TasteDials.from_dict({"visual_density": 99.0, "motion_intensity": -5.0})
        self.assertEqual(restored.visual_density, 1.0)
        self.assertEqual(restored.motion_intensity, 0.0)


class TestTasteDialsPresets(unittest.TestCase):
    """Verify preset configurations."""

    def test_minimalist_preset_has_low_values(self) -> None:
        """Verify: 'minimalist' preset has low variance/motion/density."""
        dials = create_preset("minimalist")
        self.assertEqual(dials.design_variance, 0.2)
        self.assertEqual(dials.motion_intensity, 0.2)
        self.assertEqual(dials.visual_density, 0.3)

    def test_balanced_preset_has_mid_values(self) -> None:
        """Verify: 'balanced' preset has 0.5 for all dials (== default)."""
        dials = create_preset("balanced")
        self.assertEqual(dials.design_variance, 0.5)
        self.assertEqual(dials.motion_intensity, 0.5)
        self.assertEqual(dials.visual_density, 0.5)
        self.assertTrue(dials.is_default)

    def test_rich_preset_has_high_values(self) -> None:
        """Verify: 'rich' preset has high variance/motion/density."""
        dials = create_preset("rich")
        self.assertEqual(dials.design_variance, 0.8)
        self.assertEqual(dials.motion_intensity, 0.7)
        self.assertEqual(dials.visual_density, 0.7)

    def test_unknown_preset_raises_keyerror(self) -> None:
        """Verify: unknown preset name raises KeyError."""
        with self.assertRaises(KeyError) as ctx:
            create_preset("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_preset_sensitivity_uses_default(self) -> None:
        """Verify: presets do not override sensitivity (uses default 0.3)."""
        for name in PRESETS:
            dials = create_preset(name)
            self.assertEqual(dials.sensitivity, DEFAULT_SENSITIVITY)

    def test_presets_dict_contains_three_names(self) -> None:
        """Verify: PRESETS dict contains minimalist/balanced/rich."""
        self.assertIn("minimalist", PRESETS)
        self.assertIn("balanced", PRESETS)
        self.assertIn("rich", PRESETS)
        self.assertEqual(len(PRESETS), 3)

    def test_keyerror_message_lists_available_presets(self) -> None:
        """Verify: KeyError message includes list of available presets."""
        with self.assertRaises(KeyError) as ctx:
            create_preset("typo")
        msg = str(ctx.exception)
        self.assertIn("minimalist", msg)
        self.assertIn("balanced", msg)
        self.assertIn("rich", msg)


class TestTasteDialsIntegration(unittest.TestCase):
    """Integration: TasteDials used with realistic audit rule names."""

    def test_realistic_layout_rule_adjustment(self) -> None:
        """Verify: realistic layout rule name triggers visual_density dial."""
        dials = TasteDials(visual_density=0.8, sensitivity=0.3)
        # multiplier = 1 + (0.8 - 0.5) * 2 * 0.3 = 1.18
        adjusted = dials.adjust_threshold("layout_element_count_max", 50.0)
        self.assertAlmostEqual(adjusted, 59.0)

    def test_realistic_motion_rule_adjustment(self) -> None:
        """Verify: realistic motion rule name triggers motion_intensity dial."""
        dials = TasteDials(motion_intensity=0.2, sensitivity=0.3)
        # multiplier = 1 + (0.2 - 0.5) * 2 * 0.3 = 0.82
        adjusted = dials.adjust_threshold("animation_duration_max_ms", 1000.0)
        self.assertAlmostEqual(adjusted, 820.0)

    def test_realistic_consistency_rule_adjustment(self) -> None:
        """Verify: realistic consistency rule triggers design_variance dial."""
        dials = TasteDials(design_variance=0.9, sensitivity=0.3)
        # multiplier = 1 + (0.9 - 0.5) * 2 * 0.3 = 1.24
        adjusted = dials.adjust_threshold("consistency_color_palette_variance", 5.0)
        self.assertAlmostEqual(adjusted, 6.2)

    def test_a11y_rule_not_adjusted(self) -> None:
        """Verify: accessibility rules (no dial keyword) are not adjusted."""
        dials = TasteDials(visual_density=1.0, motion_intensity=1.0, design_variance=1.0)
        # a11y rules like color_contrast / aria_label / focus_visible
        # should NOT be adjusted — accessibility must not be relaxed by taste dials
        self.assertEqual(dials.adjust_threshold("color_contrast_ratio_min", 4.5), 4.5)
        self.assertEqual(dials.adjust_threshold("aria_label_present", 1.0), 1.0)
        self.assertEqual(dials.adjust_threshold("focus_visible_required", 1.0), 1.0)

    def test_minimalist_preset_tightens_layout_threshold(self) -> None:
        """Verify: minimalist preset tightens layout (lower density allowed)."""
        dials = create_preset("minimalist")
        # visual_density=0.3, multiplier = 1 + (0.3 - 0.5) * 2 * 0.3 = 0.88
        adjusted = dials.adjust_threshold("layout_element_count_max", 50.0)
        self.assertAlmostEqual(adjusted, 44.0)

    def test_rich_preset_relaxes_layout_threshold(self) -> None:
        """Verify: rich preset relaxes layout (higher density allowed)."""
        dials = create_preset("rich")
        # visual_density=0.7, multiplier = 1 + (0.7 - 0.5) * 2 * 0.3 = 1.12
        adjusted = dials.adjust_threshold("layout_element_count_max", 50.0)
        self.assertAlmostEqual(adjusted, 56.0)


if __name__ == "__main__":
    unittest.main()
