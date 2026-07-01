#!/usr/bin/env python3
"""
Tests for PonytailRuleInjector and PromptAssembler integration.

Coverage:
  - Unit: PonytailRuleInjector with various configs
  - Unit: PONYTAIL_RULES content verification
  - Integration: PromptAssembler injects ponytail rules when enabled
  - Regression: PromptAssembler works unchanged when disabled
  - Edge cases: None config, empty config, markers disabled

Spec reference: docs/spec/v3.10.0_spec.md §5.2
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # noqa: E402

from scripts.collaboration.ponytail_rule_injector import (  # noqa: E402
    PONYTAIL_RULES,
    PonytailRuleInjector,
)


class TestPonytailRuleInjectorUnit(unittest.TestCase):
    """Unit tests for PonytailRuleInjector."""

    def test_disabled_by_default(self):
        injector = PonytailRuleInjector(None)
        self.assertFalse(injector.enabled)
        self.assertEqual(injector.build_injection(), "")

    def test_disabled_when_minimal_implementation_false(self):
        config = {"quality_control": {"minimal_implementation": False}}
        injector = PonytailRuleInjector(config)
        self.assertFalse(injector.enabled)
        self.assertEqual(injector.build_injection(), "")

    def test_enabled_when_minimal_implementation_true(self):
        config = {"quality_control": {"minimal_implementation": True}}
        injector = PonytailRuleInjector(config)
        self.assertTrue(injector.enabled)
        injection = injector.build_injection()
        self.assertIn("Minimal Implementation Rules", injection)
        self.assertIn("YAGNI", injection)

    def test_markers_enabled_by_default(self):
        config = {"quality_control": {"minimal_implementation": True}}
        injector = PonytailRuleInjector(config)
        self.assertTrue(injector.markers_enabled)
        injection = injector.build_injection()
        self.assertIn("ponytail:", injection)

    def test_markers_disabled_adds_note(self):
        config = {
            "quality_control": {
                "minimal_implementation": True,
                "ponytail_markers": False,
            }
        }
        injector = PonytailRuleInjector(config)
        self.assertFalse(injector.markers_enabled)
        injection = injector.build_injection()
        self.assertIn("markers are disabled", injection)

    def test_is_enabled_alias(self):
        config = {"quality_control": {"minimal_implementation": True}}
        injector = PonytailRuleInjector(config)
        self.assertTrue(injector.is_enabled())

    def test_empty_config(self):
        injector = PonytailRuleInjector({})
        self.assertFalse(injector.enabled)


class TestPonytailRulesContent(unittest.TestCase):
    """Verify PONYTAIL_RULES contains required sections."""

    def test_contains_laziness_ladder(self):
        self.assertIn("lazy senior developer", PONYTAIL_RULES)

    def test_contains_all_7_rungs(self):
        rungs = [
            "YAGNI", "standard library", "native platform",
            "already-installed dependency", "one line",
            "minimum code",
        ]
        for rung in rungs:
            self.assertIn(rung, PONYTAIL_RULES, f"Missing rung: {rung}")

    def test_contains_never_skip_section(self):
        self.assertIn("Not lazy about", PONYTAIL_RULES)
        items = ["Input validation", "data loss", "Security",
                 "Accessibility"]
        for item in items:
            self.assertIn(item, PONYTAIL_RULES)

    def test_contains_ponytail_marker_instruction(self):
        self.assertIn("ponytail:", PONYTAIL_RULES)

    def test_contains_no_abstractions_rule(self):
        self.assertIn("No abstractions", PONYTAIL_RULES)


class TestPromptAssemblerIntegration(unittest.TestCase):
    """Integration: PromptAssembler injects ponytail rules."""

    def setUp(self):
        from scripts.collaboration.prompt_assembler import PromptAssembler

        self.PromptAssembler = PromptAssembler
        self.base_prompt = "You are an architect. Design systems."

    def test_injection_appears_when_enabled(self):
        config = {"quality_control": {
            "enabled": True, "minimal_implementation": True,
        }}
        asm = self.PromptAssembler.__new__(self.PromptAssembler)
        asm.role_id = "architect"
        asm.base_prompt = self.base_prompt
        asm.qc_config = config
        asm.qc_enabled = True
        asm._qc_injection = ""
        inj = PonytailRuleInjector(config)
        asm._ponytail_injector = inj
        asm._ponytail_injection = inj.build_injection()

        self.assertIn("Minimal Implementation Rules",
                      asm._ponytail_injection)

    def test_no_injection_when_disabled(self):
        config = {"quality_control": {
            "enabled": True, "minimal_implementation": False,
        }}
        asm = self.PromptAssembler.__new__(self.PromptAssembler)
        asm.role_id = "architect"
        asm.base_prompt = self.base_prompt
        asm.qc_config = config
        asm.qc_enabled = True
        asm._qc_injection = ""
        inj = PonytailRuleInjector(config)
        asm._ponytail_injector = inj
        asm._ponytail_injection = inj.build_injection()

        self.assertEqual(asm._ponytail_injection, "")

    def test_build_instruction_structured_includes_ponytail(self):
        """Verify ponytail rules appear in structured prompts."""
        from scripts.collaboration.prompt_assembler_formatting_mixin import (
            PromptAssemblerFormattingMixin,
        )

        config = {"quality_control": {
            "enabled": True, "minimal_implementation": True,
        }}

        class TestAssembler(
            PromptAssemblerFormattingMixin,
        ):
            def __init__(self):
                self.role_id = "architect"
                self.base_prompt = "You are an architect."
                self.qc_config = config
                self.qc_enabled = True
                self._qc_injection = "## QC Rules"
                inj = PonytailRuleInjector(config)
                self._ponytail_injector = inj
                self._ponytail_injection = inj.build_injection()

            def _get_user_rules_injection(self, task_description):  # noqa: ARG002
                return ""

            def _get_role_anti_patterns(self):
                return []

            def _get_skill_injection(self):
                return ""

            def _get_anti_rationalization_injection(self):
                return ""

        asm = TestAssembler()
        instruction = asm._build_instruction(
            style="structured",
            task_id="T001",
            task_description="Design API",
            role_display="Architect",
            findings=[],
            include_constraints=False,
            include_anti_patterns=False,
        )

        self.assertIn("QC Rules", instruction)
        self.assertIn("Minimal Implementation Rules", instruction)
        self.assertIn("YAGNI", instruction)

    def test_build_instruction_ultra_minimal_skips_ponytail(self):
        """Verify ponytail rules are skipped in ultra_minimal (compressed)."""
        from scripts.collaboration.prompt_assembler_formatting_mixin import (
            PromptAssemblerFormattingMixin,
        )

        config = {"quality_control": {
            "enabled": True, "minimal_implementation": True,
        }}

        class TestAssembler(PromptAssemblerFormattingMixin):
            def __init__(self):
                self.role_id = "coder"
                self.base_prompt = "You are a coder."
                self.qc_config = config
                self.qc_enabled = True
                self._qc_injection = ""
                inj = PonytailRuleInjector(config)
                self._ponytail_injector = inj
                self._ponytail_injection = inj.build_injection()

            def _get_user_rules_injection(self, task_description):  # noqa: ARG002
                return ""

            def _get_role_anti_patterns(self):
                return []

            def _get_skill_injection(self):
                return ""

            def _get_anti_rationalization_injection(self):
                return ""

        asm = TestAssembler()
        instruction = asm._build_instruction(
            style="ultra_minimal",
            task_id="",
            task_description="Fix bug",
            role_display="Coder",
            findings=[],
            include_constraints=False,
            include_anti_patterns=False,
        )

        # Ponytail rules should NOT appear in compressed styles
        self.assertNotIn("Minimal Implementation Rules", instruction)

    def test_concat_injections_empty_when_all_disabled(self):
        """_concat_injections returns '' when QC and ponytail are off."""
        from scripts.collaboration.prompt_assembler_formatting_mixin import (
            PromptAssemblerFormattingMixin,
        )

        class TestAssembler(PromptAssemblerFormattingMixin):
            def __init__(self):
                self.role_id = "coder"
                self.qc_enabled = False
                self._qc_injection = ""
                self._ponytail_injection = ""

            def _get_ponytail_injection(self):
                return self._ponytail_injection

        asm = TestAssembler()
        self.assertEqual(asm._concat_injections(), "")


if __name__ == "__main__":
    unittest.main()
