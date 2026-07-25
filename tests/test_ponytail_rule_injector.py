#!/usr/bin/env python3
"""
Tests for PonytailRuleInjector and PromptAssembler integration.

Coverage:
  - Unit: PonytailRuleInjector with various configs
  - Unit: PONYTAIL_RULES content verification
  - Integration: PromptAssembler injects ponytail rules when enabled
  - Regression: PromptAssembler works unchanged when disabled
  - Edge cases: None config, empty config, markers disabled
  - V4.3.0 P1-1: lite/full dual-mode + 16 red lines + violation checker

Spec reference: docs/spec/v3.10.0_spec.md §5.2
                docs/prd/V4.3.0_PRD.md §3.2 (P1-1)
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # noqa: E402

from scripts.collaboration.ponytail_rule_injector import (  # noqa: E402
    PONYTAIL_RED_LINES,
    PONYTAIL_RED_LINES_LITE,
    PONYTAIL_RULES,
    PONYTAIL_RULES_LITE,
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


class TestPonytailLiteFullMode(unittest.TestCase):
    """V4.3.0 P1-1: lite/full dual-mode tests."""

    _ENABLED = {"quality_control": {"minimal_implementation": True}}

    def test_default_mode_is_full(self):
        # Default mode must be full (backward compatible with V3.10.0).
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertEqual(injector.mode, "full")

    def test_full_mode_returns_full_rules(self):
        injector = PonytailRuleInjector(self._ENABLED)
        injection = injector.build_injection()
        self.assertIn("Minimal Implementation Rules (Ponytail)", injection)
        # Full mode keeps the "Rules:" section (lite mode drops it).
        self.assertIn("Rules:", injection)

    def test_lite_mode_returns_lite_rules(self):
        injector = PonytailRuleInjector(self._ENABLED, mode="lite")
        injection = injector.build_injection()
        self.assertIn("Ponytail — Lite", injection)
        # Lite mode does not include the "Rules:" section header.
        self.assertNotIn("\nRules:\n", injection)

    def test_lite_mode_from_config(self):
        config = {"quality_control": {
            "minimal_implementation": True, "ponytail_mode": "lite",
        }}
        injector = PonytailRuleInjector(config)
        self.assertEqual(injector.mode, "lite")
        self.assertIn("Lite", injector.build_injection())

    def test_full_mode_from_config(self):
        config = {"quality_control": {
            "minimal_implementation": True, "ponytail_mode": "full",
        }}
        injector = PonytailRuleInjector(config)
        self.assertEqual(injector.mode, "full")

    def test_init_mode_overrides_config(self):
        # Explicit mode param takes precedence over config.
        config = {"quality_control": {
            "minimal_implementation": True, "ponytail_mode": "full",
        }}
        injector = PonytailRuleInjector(config, mode="lite")
        self.assertEqual(injector.mode, "lite")

    def test_build_injection_mode_overrides_init(self):
        injector = PonytailRuleInjector(self._ENABLED, mode="full")
        injection = injector.build_injection(mode="lite")
        self.assertIn("Lite", injection)

    def test_invalid_mode_in_init_raises(self):
        with self.assertRaises(ValueError):
            PonytailRuleInjector(self._ENABLED, mode="ultra")

    def test_invalid_mode_in_build_injection_raises(self):
        injector = PonytailRuleInjector(self._ENABLED)
        with self.assertRaises(ValueError):
            injector.build_injection(mode="ultra")

    def test_no_ultra_mode_supported(self):
        # ultra mode is dead code removed per PRD §3.2 P1-1.
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertNotIn("ultra", injector.mode)

    def test_disabled_returns_empty_even_in_lite_mode(self):
        config = {"quality_control": {
            "minimal_implementation": False, "ponytail_mode": "lite",
        }}
        injector = PonytailRuleInjector(config)
        self.assertEqual(injector.build_injection(), "")

    def test_markers_disabled_note_in_lite_mode(self):
        config = {"quality_control": {
            "minimal_implementation": True,
            "ponytail_mode": "lite",
            "ponytail_markers": False,
        }}
        injector = PonytailRuleInjector(config)
        self.assertIn("markers are disabled", injector.build_injection())


class TestPonytailRedLines(unittest.TestCase):
    """V4.3.0 P1-1: 16 (full) / 8 (lite) red lines tests."""

    def test_full_red_lines_count_is_16(self):
        self.assertEqual(len(PONYTAIL_RED_LINES), 16)

    def test_lite_red_lines_count_is_8(self):
        self.assertEqual(len(PONYTAIL_RED_LINES_LITE), 8)

    def test_full_red_lines_have_stable_ids(self):
        ids = [line.split(":", 1)[0] for line in PONYTAIL_RED_LINES]
        self.assertEqual(ids, [f"RL-{i:02d}" for i in range(1, 17)])

    def test_lite_red_lines_subset_of_full(self):
        full_ids = {line.split(":", 1)[0] for line in PONYTAIL_RED_LINES}
        lite_ids = {line.split(":", 1)[0] for line in PONYTAIL_RED_LINES_LITE}
        self.assertTrue(lite_ids.issubset(full_ids))

    def test_red_lines_property_full(self):
        injector = PonytailRuleInjector(
            {"quality_control": {"minimal_implementation": True}}
        )
        self.assertEqual(len(injector.red_lines), 16)

    def test_red_lines_property_lite(self):
        injector = PonytailRuleInjector(
            {"quality_control": {"minimal_implementation": True}}, mode="lite"
        )
        self.assertEqual(len(injector.red_lines), 8)

    def test_lite_rules_contain_7_rungs(self):
        # Lite mode must still contain all 7 ladder rungs.
        rungs = ["YAGNI", "standard library", "native platform",
                 "already-installed dependency", "one line", "minimum code"]
        for rung in rungs:
            self.assertIn(rung, PONYTAIL_RULES_LITE, f"Missing rung: {rung}")

    def test_full_rules_contain_never_skip_section(self):
        self.assertIn("Not lazy about", PONYTAIL_RULES)


class TestCheckRedLineViolation(unittest.TestCase):
    """V4.3.0 P1-1: check_red_line_violation heuristic tests."""

    _ENABLED = {"quality_control": {"minimal_implementation": True}}

    def test_detects_skip_input_validation(self):
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertIn("RL-12", injector.check_red_line_violation(
            "let's skip input validation here"))

    def test_detects_ignore_security(self):
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertIn("RL-14", injector.check_red_line_violation(
            "ignore security for now"))

    def test_detects_multiple_violations(self):
        injector = PonytailRuleInjector(self._ENABLED)
        violations = injector.check_red_line_violation(
            "skip input validation and ignore security")
        self.assertIn("RL-12", violations)
        self.assertIn("RL-14", violations)

    def test_no_violation_returns_empty(self):
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertEqual(
            injector.check_red_line_violation("normal code with no issues"),
            [],
        )

    def test_empty_content_returns_empty(self):
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertEqual(injector.check_red_line_violation(""), [])

    def test_case_insensitive_detection(self):
        injector = PonytailRuleInjector(self._ENABLED)
        self.assertIn("RL-12", injector.check_red_line_violation(
            "SKIP INPUT VALIDATION"))

    def test_lite_mode_still_detects_rl12(self):
        # RL-12 is in the lite red line set, so it must be detectable.
        injector = PonytailRuleInjector(self._ENABLED, mode="lite")
        self.assertIn("RL-12", injector.check_red_line_violation(
            "skip input validation"))

    def test_lite_mode_skips_full_only_red_lines(self):
        # RL-13 is full-mode-only (not in PONYTAIL_RED_LINES_LITE), so a
        # violation phrase for RL-13 must NOT be reported in lite mode.
        injector = PonytailRuleInjector(self._ENABLED, mode="lite")
        self.assertNotIn("RL-13", injector.check_red_line_violation(
            "swallow exceptions"))

    def test_full_mode_detects_rl13(self):
        injector = PonytailRuleInjector(self._ENABLED, mode="full")
        self.assertIn("RL-13", injector.check_red_line_violation(
            "swallow exceptions"))


class TestPonytailBackwardCompatibility(unittest.TestCase):
    """V4.3.0 P1-1: ensure existing V3.10.0 behavior is preserved."""

    def test_full_mode_default_unchanged(self):
        # The default injection must match V3.10.0 output exactly.
        config = {"quality_control": {"minimal_implementation": True}}
        injector = PonytailRuleInjector(config)
        self.assertEqual(injector.build_injection(), PONYTAIL_RULES)

    def test_full_mode_with_markers_disabled_unchanged(self):
        config = {"quality_control": {
            "minimal_implementation": True, "ponytail_markers": False,
        }}
        injector = PonytailRuleInjector(config)
        expected = PONYTAIL_RULES + "\n" + (
            "(Note: `ponytail:` markers are disabled in config; "
            "do not add them to output.)"
        )
        self.assertEqual(injector.build_injection(), expected)

    def test_disabled_unchanged(self):
        injector = PonytailRuleInjector(None)
        self.assertFalse(injector.enabled)
        self.assertEqual(injector.build_injection(), "")

    def test_init_backward_compat_single_arg(self):
        # Old call signature PonytailRuleInjector(config) must still work.
        config = {"quality_control": {"minimal_implementation": True}}
        injector = PonytailRuleInjector(config)
        self.assertTrue(injector.enabled)
        self.assertEqual(injector.mode, "full")


if __name__ == "__main__":
    unittest.main()
