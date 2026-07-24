#!/usr/bin/env python3
"""PromptAssembler + AntiRationalizationEngine + LearnedRuleStore +
PonytailRuleInjector + PromptDials Integration Tests.

End-to-end integration tests for the dynamic prompt-assembly pipeline.
Verifies CROSS-MODULE interactions among:

    scripts/collaboration/prompt_assembler.py        — PromptAssembler facade
        orchestrating complexity detection → template selection → assembly.
    scripts/collaboration/anti_rationalization.py    — AntiRationalizationEngine
        per-role excuse→reality tables injected into structured prompts.
    scripts/collaboration/learned_rule_store.py      — LearnedRuleStore two-tier
        persistence (tier1 YAML auto-inject, tier2 JSON candidate pool).
    scripts/collaboration/ponytail_rule_injector.py  — PonytailRuleInjector
        lazy-senior-developer manifesto appended when QC enabled.
    scripts/collaboration/prompt_dials.py             — PromptDials three-dimension
        tuning (verbosity/creativity/risk_tolerance) with variant compat.

Flow:
    PromptAssembler.assemble(task_description, dials=..., variant=...)
      → detect_complexity() → select_template() → _build_instruction()
      → injects ponytail + learned_rules + anti_rationalization + grilling

Test categories:
    T1: PromptDials — defaults, variant mapping, clamping, prompt fragment
    T2: AntiRationalizationEngine — universal + role tables, formatting, limits
    T3: PonytailRuleInjector — enabled/disabled, markers config
    T4: LearnedRuleStore — tier classification, round-trip, promote, dedup
    T5: PromptAssembler integration — assemble with dials/variant/hints/compression
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import unittest
from typing import Any

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.anti_rationalization import AntiRationalizationEngine
from scripts.collaboration.learned_rule_store import LearnedRuleStore
from scripts.collaboration.models_base import LearnedRule
from scripts.collaboration.ponytail_rule_injector import PonytailRuleInjector
from scripts.collaboration.prompt_assembler import PromptAssembler, TaskComplexity
from scripts.collaboration.prompt_dials import PromptDials

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_prompt_assembler_cache() -> None:
    """Reset the module-level config cache in prompt_assembler_mixins.

    ``_load_config`` caches the last-loaded config by resolved path. Resetting
    it between tests guarantees each test reads its own tmp config file
    instead of receiving a stale cached entry from a prior test.
    """
    import scripts.collaboration.prompt_assembler_mixins as pa_mod

    pa_mod._config_cache = {}
    pa_mod._config_cache_path = None


def _reset_ar_singleton() -> None:
    """Reset the shared AntiRationalizationEngine singleton."""
    import scripts.collaboration.anti_rationalization as ar_mod

    ar_mod._shared_engine_instance = None


def _write_config(tmp_dir: str, config: dict[str, Any]) -> str:
    """Write a YAML config file into ``tmp_dir`` and return its path."""
    path = os.path.join(tmp_dir, ".devsquad.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return path


def _make_qc_config(
    *,
    enabled: bool = True,
    minimal_implementation: bool = False,
    learned_rules: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a quality_control config dict for PromptAssembler tests."""
    qc: dict[str, Any] = {"enabled": enabled}
    if minimal_implementation:
        qc["minimal_implementation"] = True
    if learned_rules is not None:
        qc["learned_rules"] = learned_rules
    return {"quality_control": qc}


# ---------------------------------------------------------------------------
# T1: PromptDials — defaults, variant mapping, clamping, fragment generation
# ---------------------------------------------------------------------------


class T1_PromptDials(unittest.TestCase):
    """T1: PromptDials three-dimension tuning and variant compatibility."""

    def test_01_default_dials_is_default(self) -> None:
        """Verify: Default PromptDials() is (3, 3, 3) and is_default True."""
        dials = PromptDials()
        self.assertEqual(dials.verbosity, 3)
        self.assertEqual(dials.creativity, 3)
        self.assertEqual(dials.risk_tolerance, 3)
        self.assertTrue(dials.is_default)

    def test_02_from_variant_mappings(self) -> None:
        """Verify: from_variant converts legacy strings to dial tuples."""
        self.assertEqual(
            PromptDials.from_variant("concise"),
            PromptDials(verbosity=1, creativity=3, risk_tolerance=3),
        )
        self.assertEqual(
            PromptDials.from_variant("balanced"),
            PromptDials(verbosity=3, creativity=3, risk_tolerance=3),
        )
        self.assertEqual(
            PromptDials.from_variant("detailed"),
            PromptDials(verbosity=5, creativity=3, risk_tolerance=3),
        )

    def test_03_to_variant_roundtrip(self) -> None:
        """Verify: variant → dials → variant round-trips for known variants."""
        for variant in ("concise", "balanced", "detailed"):
            dials = PromptDials.from_variant(variant)
            self.assertEqual(dials.to_variant(), variant)

    def test_04_to_variant_non_default_creativity_maps_balanced(self) -> None:
        """Verify: non-default creativity/risk always maps to 'balanced'."""
        dials = PromptDials(verbosity=1, creativity=5, risk_tolerance=3)
        self.assertEqual(dials.to_variant(), "balanced")
        dials2 = PromptDials(verbosity=5, creativity=3, risk_tolerance=5)
        self.assertEqual(dials2.to_variant(), "balanced")

    def test_05_clamping_below_one(self) -> None:
        """Verify: values below 1 are clamped to 1."""
        dials = PromptDials(verbosity=0, creativity=-5, risk_tolerance=-100)
        self.assertEqual(dials.verbosity, 1)
        self.assertEqual(dials.creativity, 1)
        self.assertEqual(dials.risk_tolerance, 1)

    def test_06_clamping_above_five(self) -> None:
        """Verify: values above 5 are clamped to 5."""
        dials = PromptDials(verbosity=99, creativity=10, risk_tolerance=1000)
        self.assertEqual(dials.verbosity, 5)
        self.assertEqual(dials.creativity, 5)
        self.assertEqual(dials.risk_tolerance, 5)

    def test_07_default_fragment_is_empty(self) -> None:
        """Verify: default dials produce empty prompt fragment."""
        self.assertEqual(PromptDials().to_prompt_fragment(), "")

    def test_08_non_default_fragment_has_verbosity(self) -> None:
        """Verify: terse dials produce a 'Be terse' fragment."""
        dials = PromptDials(verbosity=1, creativity=3, risk_tolerance=3)
        fragment = dials.to_prompt_fragment()
        self.assertIn("terse", fragment.lower())

    def test_09_apply_to_prompt_prepends_fragment(self) -> None:
        """Verify: apply_to_prompt prepends non-empty fragment to prompt."""
        dials = PromptDials(verbosity=5)
        original = "Design the auth module."
        result = dials.apply_to_prompt(original)
        self.assertTrue(result.startswith(dials.to_prompt_fragment()))
        self.assertIn(original, result)

    def test_10_apply_to_prompt_unchanged_when_default(self) -> None:
        """Verify: apply_to_prompt returns prompt unchanged for default dials."""
        original = "Do the thing."
        self.assertEqual(PromptDials().apply_to_prompt(original), original)


# ---------------------------------------------------------------------------
# T2: AntiRationalizationEngine — universal + role tables, formatting, limits
# ---------------------------------------------------------------------------


class T2_AntiRationalizationEngine(unittest.TestCase):
    """T2: AntiRationalizationEngine universal + role-specific tables."""

    def setUp(self) -> None:
        _reset_ar_singleton()

    def test_01_universal_table_count(self) -> None:
        """Verify: universal table has 8 entries."""
        engine = AntiRationalizationEngine()
        self.assertEqual(engine.universal_count, 8)
        self.assertGreaterEqual(engine.total_entries, 8)

    def test_02_role_specific_combined_with_universal(self) -> None:
        """Verify: get_table returns universal + role-specific entries."""
        engine = AntiRationalizationEngine()
        architect_table = engine.get_table("architect")
        # 8 universal + 6 architect-specific = 14
        self.assertEqual(engine.get_table_size("architect"), 8 + 6)
        self.assertGreater(len(architect_table), engine.universal_count)

    def test_03_unknown_role_falls_back_to_universal(self) -> None:
        """Verify: unknown role still gets universal table."""
        engine = AntiRationalizationEngine()
        unknown_table = engine.get_table("nonexistent-role")
        self.assertEqual(len(unknown_table), engine.universal_count)

    def test_04_format_for_prompt_has_table_header(self) -> None:
        """Verify: format_for_prompt produces markdown table with header."""
        engine = AntiRationalizationEngine()
        text = engine.format_for_prompt("architect")
        self.assertIn("Quality Guardrails", text)
        self.assertIn("| Excuse (DO NOT think this) |", text)
        self.assertIn("|---|---|", text)

    def test_05_max_entries_per_role_limit(self) -> None:
        """Verify: max_entries_per_role truncates the combined table."""
        engine = AntiRationalizationEngine(max_entries_per_role=3)
        self.assertEqual(engine.get_table_size("architect"), 3)

    def test_06_list_all_roles_sorted(self) -> None:
        """Verify: list_all_roles returns sorted role identifiers."""
        engine = AntiRationalizationEngine()
        roles = engine.list_all_roles()
        self.assertEqual(roles, sorted(roles))
        self.assertIn("architect", roles)
        self.assertIn("solo-coder", roles)
        self.assertIn("tester", roles)

    def test_07_format_caches_repeated_calls(self) -> None:
        """Verify: format_for_prompt returns identical cached text per role."""
        engine = AntiRationalizationEngine()
        first = engine.format_for_prompt("tester")
        second = engine.format_for_prompt("tester")
        self.assertEqual(first, second)
        self.assertIn("Quality Guardrails", first)


# ---------------------------------------------------------------------------
# T3: PonytailRuleInjector — enabled/disabled, markers config
# ---------------------------------------------------------------------------


class T3_PonytailRuleInjector(unittest.TestCase):
    """T3: PonytailRuleInjector static behavior-rule injection."""

    def test_01_disabled_returns_empty(self) -> None:
        """Verify: disabled injector returns empty string."""
        injector = PonytailRuleInjector({"quality_control": {"minimal_implementation": False}})
        self.assertFalse(injector.enabled)
        self.assertEqual(injector.build_injection(), "")

    def test_02_disabled_when_no_config(self) -> None:
        """Verify: None config defaults to disabled."""
        injector = PonytailRuleInjector(None)
        self.assertFalse(injector.enabled)
        self.assertEqual(injector.build_injection(), "")

    def test_03_enabled_returns_full_rules(self) -> None:
        """Verify: enabled injector returns the ponytail rules manifesto."""
        injector = PonytailRuleInjector({"quality_control": {"minimal_implementation": True}})
        self.assertTrue(injector.enabled)
        text = injector.build_injection()
        self.assertIn("Minimal Implementation Rules", text)
        self.assertIn("lazy senior developer", text)

    def test_04_markers_enabled_by_default(self) -> None:
        """Verify: ponytail_markers defaults to True when enabled."""
        injector = PonytailRuleInjector({"quality_control": {"minimal_implementation": True}})
        self.assertTrue(injector.markers_enabled)
        # No marker-disable note appended.
        self.assertNotIn("markers are disabled", injector.build_injection())

    def test_05_markers_disabled_adds_note(self) -> None:
        """Verify: markers disabled adds an explicit note to the injection."""
        injector = PonytailRuleInjector(
            {"quality_control": {"minimal_implementation": True, "ponytail_markers": False}}
        )
        self.assertFalse(injector.markers_enabled)
        text = injector.build_injection()
        self.assertIn("markers are disabled", text)

    def test_06_is_enabled_alias_matches_property(self) -> None:
        """Verify: is_enabled() method matches enabled property."""
        enabled_inj = PonytailRuleInjector({"quality_control": {"minimal_implementation": True}})
        disabled_inj = PonytailRuleInjector({})
        self.assertEqual(enabled_inj.is_enabled(), enabled_inj.enabled)
        self.assertEqual(disabled_inj.is_enabled(), disabled_inj.enabled)


# ---------------------------------------------------------------------------
# T4: LearnedRuleStore — tier classification, round-trip, promote, dedup
# ---------------------------------------------------------------------------


class T4_LearnedRuleStore(unittest.TestCase):
    """T4: LearnedRuleStore two-tier persistence and promotion."""

    def setUp(self) -> None:
        self._tmp_dir = tempfile.mkdtemp(prefix="devsquad_lr_")
        self._config_path = os.path.join(self._tmp_dir, ".devsquad.yaml")
        self._tier2_path = os.path.join(self._tmp_dir, "tier2", "corrections.json")

    def tearDown(self) -> None:
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def test_01_tier1_classification_for_high_confidence(self) -> None:
        """Verify: confidence >= 0.8 classifies as tier1."""
        rule = LearnedRule(
            rule_text="Prefer pathlib over os.path",
            trigger_condition="file_path_manipulation",
            confidence=0.85,
            source_task_id="task_001",
        )
        self.assertEqual(rule.tier, "tier1")

    def test_02_tier2_classification_for_medium_confidence(self) -> None:
        """Verify: confidence 0.5-0.8 classifies as tier2."""
        rule = LearnedRule(
            rule_text="Maybe use dataclasses",
            trigger_condition="model_definition",
            confidence=0.6,
            source_task_id="task_002",
        )
        self.assertEqual(rule.tier, "tier2")

    def test_03_rejected_classification_below_threshold(self) -> None:
        """Verify: confidence < 0.5 is rejected."""
        rule = LearnedRule(
            rule_text="Weak guess rule",
            trigger_condition="guess",
            confidence=0.3,
            source_task_id="task_003",
        )
        self.assertEqual(rule.tier, "rejected")

    def test_04_tier1_roundtrip_persist_and_load(self) -> None:
        """Verify: add_rule(tier1) writes YAML and load_tier1_rules reads it back."""
        store = LearnedRuleStore(config_path=self._config_path, tier2_path=self._tier2_path)
        rule = LearnedRule(
            rule_text="Always validate inputs at trust boundaries",
            trigger_condition="input_validation",
            confidence=0.9,
            source_task_id="task_004",
        )
        outcome = store.add_rule(rule)
        self.assertEqual(outcome, "tier1")

        loaded = store.load_tier1_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].rule_text, rule.rule_text)
        self.assertAlmostEqual(loaded[0].confidence, rule.confidence)

    def test_05_tier2_roundtrip_persist_and_load(self) -> None:
        """Verify: add_rule(tier2) writes JSON and load_tier2_rules reads it back."""
        store = LearnedRuleStore(config_path=self._config_path, tier2_path=self._tier2_path)
        rule = LearnedRule(
            rule_text="Consider using asyncio.gather",
            trigger_condition="parallel_execution",
            confidence=0.65,
            source_task_id="task_005",
        )
        outcome = store.add_rule(rule)
        self.assertEqual(outcome, "tier2")

        loaded = store.load_tier2_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].rule_text, rule.rule_text)

    def test_06_rejected_not_persisted_anywhere(self) -> None:
        """Verify: rejected rules are written to neither tier."""
        store = LearnedRuleStore(config_path=self._config_path, tier2_path=self._tier2_path)
        rule = LearnedRule(
            rule_text="Bad low-confidence rule",
            trigger_condition="noise",
            confidence=0.2,
            source_task_id="task_006",
        )
        outcome = store.add_rule(rule)
        self.assertEqual(outcome, "rejected")
        self.assertEqual(store.load_tier1_rules(), [])
        self.assertEqual(store.load_tier2_rules(), [])

    def test_07_promote_tier2_to_tier1(self) -> None:
        """Verify: promote_tier2_to_tier1 moves rule from tier2 to tier1."""
        store = LearnedRuleStore(config_path=self._config_path, tier2_path=self._tier2_path)
        rule = LearnedRule(
            rule_text="Promote me to tier1",
            trigger_condition="promotion_test",
            confidence=0.55,
            source_task_id="task_007",
        )
        store.add_rule(rule)
        # Sanity: rule is in tier2, not tier1.
        self.assertEqual(len(store.load_tier2_rules()), 1)
        self.assertEqual(len(store.load_tier1_rules()), 0)

        promoted = store.promote_tier2_to_tier1(rule.rule_text)
        self.assertTrue(promoted)
        # Rule moved: tier2 empty, tier1 has one entry.
        self.assertEqual(len(store.load_tier2_rules()), 0)
        self.assertEqual(len(store.load_tier1_rules()), 1)

    def test_08_dedup_by_rule_text_hash(self) -> None:
        """Verify: adding the same rule_text twice does not duplicate."""
        store = LearnedRuleStore(config_path=self._config_path, tier2_path=self._tier2_path)
        rule = LearnedRule(
            rule_text="Dedup candidate rule",
            trigger_condition="dedup",
            confidence=0.9,
            source_task_id="task_008",
        )
        store.add_rule(rule)
        store.add_rule(rule)  # identical rule_text → deduped.
        self.assertEqual(len(store.load_tier1_rules()), 1)


# ---------------------------------------------------------------------------
# T5: PromptAssembler integration — assemble with dials/variant/hints/compression
# ---------------------------------------------------------------------------


class T5_PromptAssemblerIntegration(unittest.TestCase):
    """T5: PromptAssembler end-to-end assembly with all collaborator modules."""

    def setUp(self) -> None:
        _reset_prompt_assembler_cache()
        self._tmp_dir = tempfile.mkdtemp(prefix="devsquad_pa_")

    def tearDown(self) -> None:
        _reset_prompt_assembler_cache()
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _make_assembler(self, config: dict[str, Any] | None = None) -> PromptAssembler:
        """Create a PromptAssembler with an isolated tmp config file.

        When ``config`` is None, a QC-disabled config is written so the
        assembler does NOT pick up the real project ``.devsquad.yaml``
        (which has QC/strict/ponytail enabled and would break isolation).
        """
        if config is None:
            config = _make_qc_config(enabled=False)
        config_path = _write_config(self._tmp_dir, config)
        return PromptAssembler(
            role_id="architect",
            base_prompt="You are an architect. Design systems carefully.",
            config_path=config_path,
        )

    def test_01_assemble_simple_task_uses_compact_variant(self) -> None:
        """Verify: short simple task → SIMPLE complexity → compact variant (direct style)."""
        assembler = self._make_assembler()
        result = assembler.assemble(task_description="Fix the typo")
        self.assertEqual(result.complexity, TaskComplexity.SIMPLE)
        # variant_used = config["name"]; SIMPLE variant is named "compact".
        self.assertEqual(result.variant_used, "compact")
        # Direct style uses "=== Task ===" header (not [role_id] tag).
        self.assertIn("=== Task ===", result.instruction)
        self.assertIn("Fix the typo", result.instruction)

    def test_02_assemble_complex_task_uses_comprehensive_style(self) -> None:
        """Verify: long complex task → COMPLEX complexity → comprehensive style."""
        assembler = self._make_assembler()
        long_desc = (
            "Design a distributed microservice architecture with high availability, "
            "disaster recovery, end-to-end monitoring, and complete CI/CD pipeline. "
            "Include tech selection rationale, service discovery, and load balancing."
        )
        result = assembler.assemble(task_description=long_desc)
        self.assertEqual(result.complexity, TaskComplexity.COMPLEX)
        self.assertIn("enhanced", result.variant_used)
        # Comprehensive style asks for analysis process.
        self.assertIn("analysis process", result.instruction.lower())

    def test_03_assemble_with_explicit_dials(self) -> None:
        """Verify: explicit PromptDials are applied and recorded in metadata."""
        assembler = self._make_assembler()
        dials = PromptDials(verbosity=5, creativity=4, risk_tolerance=2)
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs.",
            dials=dials,
        )
        self.assertTrue(result.metadata.get("dials_applied"))
        self.assertEqual(result.metadata.get("dials_variant"), "balanced")
        self.assertEqual(result.metadata["dials"]["verbosity"], 5)
        # The dial fragment is prepended to the instruction.
        self.assertTrue(result.instruction.startswith(dials.to_prompt_fragment()))

    def test_04_assemble_with_variant_string_converts_to_dials(self) -> None:
        """Verify: legacy variant string is converted to dials when dials=None."""
        assembler = self._make_assembler()
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs.",
            variant="concise",
        )
        self.assertTrue(result.metadata.get("dials_applied"))
        self.assertEqual(result.metadata.get("dials_variant"), "concise")
        self.assertEqual(result.metadata["dials"]["verbosity"], 1)

    def test_05_assemble_with_code_graph_hints(self) -> None:
        """Verify: code_graph_hints injected as Code Context section + metadata."""
        assembler = self._make_assembler()
        hints = [
            {
                "name": "UserService",
                "type": "class",
                "file": "src/services.py",
                "signature": "class UserService(BaseService)",
                "line_start": 10,
                "line_end": 50,
            }
        ]
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs.",
            code_graph_hints=hints,
        )
        self.assertEqual(result.metadata.get("code_graph_hints_count"), 1)
        self.assertIn("Code Context", result.instruction)
        self.assertIn("UserService", result.instruction)

    def test_06_assemble_with_compression_override_full_compact(self) -> None:
        """Verify: FULL_COMPACT compression switches style to ultra_minimal."""
        assembler = self._make_assembler()
        result = assembler.assemble(
            task_description="Design a complex distributed architecture.",
            compression_level="FULL_COMPACT",
        )
        # FULL_COMPACT overrides instruction_style to ultra_minimal.
        self.assertIn("[architect]", result.instruction)
        self.assertTrue(result.metadata.get("compression_applied"))
        self.assertEqual(result.metadata.get("compression_level"), "FULL_COMPACT")

    def test_07_anti_rationalization_injected_for_structured_style(self) -> None:
        """Verify: AR table injected for MEDIUM/COMPLEX (structured) tasks."""
        assembler = self._make_assembler()
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs."
        )
        # Structured style includes the Quality Guardrails header from AR engine.
        self.assertIn("Quality Guardrails", result.instruction)

    def test_08_ponytail_injected_when_qc_enabled(self) -> None:
        """Verify: ponytail manifesto injected when minimal_implementation enabled."""
        config = _make_qc_config(enabled=True, minimal_implementation=True)
        assembler = self._make_assembler(config)
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs."
        )
        self.assertIn("Minimal Implementation Rules", result.instruction)
        self.assertIn("lazy senior developer", result.instruction)

    def test_09_learned_rules_injected_when_configured(self) -> None:
        """Verify: tier1 learned rules from config are injected into prompt."""
        config = _make_qc_config(
            enabled=True,
            learned_rules=[
                {
                    "rule": "Always prefer pathlib over os.path",
                    "trigger": "file_path_manipulation",
                }
            ],
        )
        assembler = self._make_assembler(config)
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs."
        )
        self.assertIn("Learned Rules", result.instruction)
        self.assertIn("prefer pathlib", result.instruction)

    def test_10_assemble_empty_task_description(self) -> None:
        """Verify: empty task description defaults to SIMPLE complexity."""
        assembler = self._make_assembler()
        result = assembler.assemble(task_description="")
        self.assertEqual(result.complexity, TaskComplexity.SIMPLE)
        # Still produces a non-empty instruction.
        self.assertGreater(len(result.instruction), 0)

    def test_11_assemble_related_findings_truncated_by_complexity(self) -> None:
        """Verify: findings list is truncated according to complexity config."""
        assembler = self._make_assembler()
        many_findings = [f"Finding number {i}" for i in range(20)]
        result = assembler.assemble(
            task_description="Fix the typo",
            related_findings=many_findings,
        )
        # SIMPLE variant limits findings to 2.
        self.assertEqual(result.metadata.get("findings_included"), 2)
        self.assertEqual(result.metadata.get("findings_total"), 20)

    def test_12_assemble_metadata_records_token_estimate(self) -> None:
        """Verify: tokens_estimate is roughly len(instruction) // 3."""
        assembler = self._make_assembler()
        result = assembler.assemble(
            task_description="Design a medium-complexity feature with trade-offs."
        )
        expected = len(result.instruction) // 3
        self.assertEqual(result.tokens_estimate, expected)
        self.assertGreater(result.tokens_estimate, 0)


if __name__ == "__main__":
    unittest.main()
