#!/usr/bin/env python3
"""
Tests for PromptDials (V39-04) — Three-dimension prompt tuning.

Coverage:
  - Happy path: create dials, generate prompt fragments
  - from_variant: concise/balanced/detailed mapping
  - to_variant: reverse mapping back to variant string
  - to_prompt_fragment: different values produce different fragments
  - Edge cases: 0, -1, 6, 100 (should clamp to 1 or 5)
  - is_default: default dials return True, modified return False
  - apply_to_prompt: fragment is prepended correctly
  - Integration: PromptAssembler compatibility (if available)
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.prompt_dials import PromptDials


class TestPromptDialsDefaults(unittest.TestCase):
    """Verify default values and is_default property."""

    def test_default_dials_are_all_three(self) -> None:
        """Verify: default PromptDials has all three dials at 3."""
        # Arrange
        dials = PromptDials()
        # Assert
        self.assertEqual(dials.verbosity, 3)
        self.assertEqual(dials.creativity, 3)
        self.assertEqual(dials.risk_tolerance, 3)

    def test_is_default_true_for_default_dials(self) -> None:
        """Verify: is_default returns True for default (3, 3, 3)."""
        # Arrange
        dials = PromptDials()
        # Assert
        self.assertTrue(dials.is_default)

    def test_is_default_false_when_verbosity_modified(self) -> None:
        """Verify: is_default returns False when verbosity != 3."""
        # Arrange
        dials = PromptDials(verbosity=1)
        # Assert
        self.assertFalse(dials.is_default)

    def test_is_default_false_when_creativity_modified(self) -> None:
        """Verify: is_default returns False when creativity != 3."""
        # Arrange
        dials = PromptDials(creativity=5)
        # Assert
        self.assertFalse(dials.is_default)

    def test_is_default_false_when_risk_modified(self) -> None:
        """Verify: is_default returns False when risk_tolerance != 3."""
        # Arrange
        dials = PromptDials(risk_tolerance=2)
        # Assert
        self.assertFalse(dials.is_default)


class TestPromptDialsClamping(unittest.TestCase):
    """Verify value clamping to [1, 5]."""

    def test_zero_verbosity_clamps_to_one(self) -> None:
        """Verify: verbosity=0 clamps to 1."""
        # Arrange
        dials = PromptDials(verbosity=0)
        # Assert
        self.assertEqual(dials.verbosity, 1)

    def test_negative_verbosity_clamps_to_one(self) -> None:
        """Verify: verbosity=-1 clamps to 1."""
        # Arrange
        dials = PromptDials(verbosity=-1)
        # Assert
        self.assertEqual(dials.verbosity, 1)

    def test_six_verbosity_clamps_to_five(self) -> None:
        """Verify: verbosity=6 clamps to 5."""
        # Arrange
        dials = PromptDials(verbosity=6)
        # Assert
        self.assertEqual(dials.verbosity, 5)

    def test_hundred_creativity_clamps_to_five(self) -> None:
        """Verify: creativity=100 clamps to 5."""
        # Arrange
        dials = PromptDials(creativity=100)
        # Assert
        self.assertEqual(dials.creativity, 5)

    def test_negative_risk_clamps_to_one(self) -> None:
        """Verify: risk_tolerance=-10 clamps to 1."""
        # Arrange
        dials = PromptDials(risk_tolerance=-10)
        # Assert
        self.assertEqual(dials.risk_tolerance, 1)

    def test_all_dials_clamped_independently(self) -> None:
        """Verify: each dial clamps independently."""
        # Arrange
        dials = PromptDials(verbosity=0, creativity=99, risk_tolerance=-5)
        # Assert
        self.assertEqual(dials.verbosity, 1)
        self.assertEqual(dials.creativity, 5)
        self.assertEqual(dials.risk_tolerance, 1)


class TestPromptDialsFromVariant(unittest.TestCase):
    """Verify from_variant backward-compat mapping."""

    def test_concise_maps_to_1_3_3(self) -> None:
        """Verify: 'concise' → (1, 3, 3)."""
        # Act
        dials = PromptDials.from_variant("concise")
        # Assert
        self.assertEqual(dials.verbosity, 1)
        self.assertEqual(dials.creativity, 3)
        self.assertEqual(dials.risk_tolerance, 3)

    def test_balanced_maps_to_3_3_3(self) -> None:
        """Verify: 'balanced' → (3, 3, 3)."""
        # Act
        dials = PromptDials.from_variant("balanced")
        # Assert
        self.assertEqual(dials.verbosity, 3)
        self.assertEqual(dials.creativity, 3)
        self.assertEqual(dials.risk_tolerance, 3)
        self.assertTrue(dials.is_default)

    def test_detailed_maps_to_5_3_3(self) -> None:
        """Verify: 'detailed' → (5, 3, 3)."""
        # Act
        dials = PromptDials.from_variant("detailed")
        # Assert
        self.assertEqual(dials.verbosity, 5)
        self.assertEqual(dials.creativity, 3)
        self.assertEqual(dials.risk_tolerance, 3)

    def test_unknown_variant_defaults_to_balanced(self) -> None:
        """Verify: unknown variant string returns balanced (3, 3, 3)."""
        # Act
        dials = PromptDials.from_variant("nonexistent")
        # Assert
        self.assertEqual(dials.verbosity, 3)
        self.assertEqual(dials.creativity, 3)
        self.assertEqual(dials.risk_tolerance, 3)

    def test_empty_variant_defaults_to_balanced(self) -> None:
        """Verify: empty variant string returns balanced."""
        # Act
        dials = PromptDials.from_variant("")
        # Assert
        self.assertTrue(dials.is_default)


class TestPromptDialsToVariant(unittest.TestCase):
    """Verify to_variant reverse mapping."""

    def test_concise_round_trip(self) -> None:
        """Verify: from_variant('concise').to_variant() == 'concise'."""
        # Act
        dials = PromptDials.from_variant("concise")
        # Assert
        self.assertEqual(dials.to_variant(), "concise")

    def test_balanced_round_trip(self) -> None:
        """Verify: from_variant('balanced').to_variant() == 'balanced'."""
        # Act
        dials = PromptDials.from_variant("balanced")
        # Assert
        self.assertEqual(dials.to_variant(), "balanced")

    def test_detailed_round_trip(self) -> None:
        """Verify: from_variant('detailed').to_variant() == 'detailed'."""
        # Act
        dials = PromptDials.from_variant("detailed")
        # Assert
        self.assertEqual(dials.to_variant(), "detailed")

    def test_non_default_creativity_maps_to_balanced(self) -> None:
        """Verify: when creativity != 3, to_variant returns 'balanced'."""
        # Arrange
        dials = PromptDials(verbosity=1, creativity=5, risk_tolerance=3)
        # Assert
        self.assertEqual(dials.to_variant(), "balanced")

    def test_non_default_risk_maps_to_balanced(self) -> None:
        """Verify: when risk_tolerance != 3, to_variant returns 'balanced'."""
        # Arrange
        dials = PromptDials(verbosity=5, creativity=3, risk_tolerance=1)
        # Assert
        self.assertEqual(dials.to_variant(), "balanced")


class TestPromptDialsFragment(unittest.TestCase):
    """Verify to_prompt_fragment output."""

    def test_default_dials_produce_empty_fragment(self) -> None:
        """Verify: default (3, 3, 3) produces an empty fragment."""
        # Arrange
        dials = PromptDials()
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertEqual(fragment, "")

    def test_terse_verbosity_fragment(self) -> None:
        """Verify: verbosity=1 produces 'terse' instruction."""
        # Arrange
        dials = PromptDials(verbosity=1)
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertIn("terse", fragment.lower())

    def test_exhaustive_verbosity_fragment(self) -> None:
        """Verify: verbosity=5 produces 'exhaustive' instruction."""
        # Arrange
        dials = PromptDials(verbosity=5)
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertIn("exhaustive", fragment.lower())

    def test_conservative_creativity_fragment(self) -> None:
        """Verify: creativity=1 produces 'conventional' instruction."""
        # Arrange
        dials = PromptDials(creativity=1)
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertIn("conventional", fragment.lower())

    def test_innovative_creativity_fragment(self) -> None:
        """Verify: creativity=5 produces 'innovative' instruction."""
        # Arrange
        dials = PromptDials(creativity=5)
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertIn("innovative", fragment.lower())

    def test_safest_risk_fragment(self) -> None:
        """Verify: risk_tolerance=1 produces 'battle-tested' instruction."""
        # Arrange
        dials = PromptDials(risk_tolerance=1)
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertIn("battle-tested", fragment.lower())

    def test_aggressive_risk_fragment(self) -> None:
        """Verify: risk_tolerance=5 produces 'aggressive' instruction."""
        # Arrange
        dials = PromptDials(risk_tolerance=5)
        # Act
        fragment = dials.to_prompt_fragment()
        # Assert
        self.assertIn("aggressive", fragment.lower())

    def test_different_dials_produce_different_fragments(self) -> None:
        """Verify: different dial values produce different fragments."""
        # Arrange
        dials_low = PromptDials(verbosity=1)
        dials_high = PromptDials(verbosity=5)
        # Act
        frag_low = dials_low.to_prompt_fragment()
        frag_high = dials_high.to_prompt_fragment()
        # Assert
        self.assertNotEqual(frag_low, frag_high)


class TestPromptDialsApplyToPrompt(unittest.TestCase):
    """Verify apply_to_prompt behavior."""

    def test_default_dials_leave_prompt_unchanged(self) -> None:
        """Verify: default dials do not modify the prompt."""
        # Arrange
        dials = PromptDials()
        prompt = "Implement the auth module."
        # Act
        result = dials.apply_to_prompt(prompt)
        # Assert
        self.assertEqual(result, prompt)

    def test_non_default_dials_prepend_fragment(self) -> None:
        """Verify: non-default dials prepend the fragment to the prompt."""
        # Arrange
        dials = PromptDials(verbosity=1)
        prompt = "Implement the auth module."
        # Act
        result = dials.apply_to_prompt(prompt)
        # Assert
        self.assertTrue(result.startswith("Be terse"))
        self.assertIn(prompt, result)
        self.assertIn("\n\n", result)

    def test_apply_to_empty_prompt(self) -> None:
        """Verify: apply_to_prompt works with an empty prompt string."""
        # Arrange
        dials = PromptDials(verbosity=5)
        # Act
        result = dials.apply_to_prompt("")
        # Assert
        self.assertTrue(result.startswith("Be exhaustive"))


class TestPromptDialsIntegration(unittest.TestCase):
    """Integration with PromptAssembler (if available)."""

    def test_prompt_assembler_compat_with_dials_fragment(self) -> None:
        """Verify: PromptDials fragment can be prepended to a PromptAssembler prompt.

        Scenario: Build a PromptDials, generate fragment, prepend to a
        typical PromptAssembler instruction. The result should be a
        valid prompt string containing both the fragment and the original.
        Expected: combined string contains both parts.
        """
        # Arrange
        try:
            from scripts.collaboration.prompt_assembler import PromptAssembler
        except ImportError:
            self.skipTest("PromptAssembler not available")
        dials = PromptDials(verbosity=2, creativity=4, risk_tolerance=3)
        assembler = PromptAssembler(role_id="architect", base_prompt="You are an architect.")
        # Act
        assembled = assembler.assemble("Design the auth module")
        combined = dials.apply_to_prompt(assembled.instruction)
        # Assert
        self.assertIn(assembled.instruction, combined)
        self.assertIn("concise", combined.lower())  # verbosity=2 → "concise"


if __name__ == "__main__":
    unittest.main()
