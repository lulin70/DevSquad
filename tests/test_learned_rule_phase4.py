#!/usr/bin/env python3
"""Tests for V3.10.0 Phase 4 — LearnedRule + LearnedRuleStore + RetrospectiveEngine extraction + PromptAssembler injection.

Coverage:
  - LearnedRule dataclass: validation, tier property, serialization round-trip
  - LearnedRuleStore: tier1/tier2 persistence, dedup, promote, load
  - RetrospectiveEngine.extract_learned_rules: deviation → rule mapping
  - PromptAssembler: learned_rules injection from .devsquad.yaml
"""

from __future__ import annotations

import os
import tempfile
import unittest
from datetime import datetime

from scripts.collaboration.learned_rule_store import LearnedRuleStore
from scripts.collaboration.models import DeviationRecord, RetrospectiveReport
from scripts.collaboration.models_base import LearnedRule
from scripts.collaboration.retrospective import RetrospectiveEngine


class TestLearnedRuleDataclass(unittest.TestCase):
    """LearnedRule dataclass validation and serialization."""

    def test_valid_rule_creation(self) -> None:
        rule = LearnedRule(
            rule_text="Always prefer pathlib over os.path",
            trigger_condition="file_path_manipulation",
            confidence=0.85,
        )
        self.assertEqual(rule.tier, "tier1")
        self.assertEqual(rule.trigger_condition, "file_path_manipulation")

    def test_tier2_confidence(self) -> None:
        rule = LearnedRule(rule_text="test", trigger_condition="t", confidence=0.65)
        self.assertEqual(rule.tier, "tier2")

    def test_rejected_confidence(self) -> None:
        rule = LearnedRule(rule_text="test", trigger_condition="t", confidence=0.3)
        self.assertEqual(rule.tier, "rejected")

    def test_invalid_confidence_raises(self) -> None:
        with self.assertRaises(ValueError):
            LearnedRule(rule_text="test", trigger_condition="t", confidence=1.5)
        with self.assertRaises(ValueError):
            LearnedRule(rule_text="test", trigger_condition="t", confidence=-0.1)

    def test_empty_rule_text_raises(self) -> None:
        with self.assertRaises(ValueError):
            LearnedRule(rule_text="", trigger_condition="t", confidence=0.8)

    def test_serialization_roundtrip(self) -> None:
        rule = LearnedRule(
            rule_text="Test rule",
            trigger_condition="test_trigger",
            confidence=0.9,
            source_task_id="task_123",
        )
        d = rule.to_dict()
        restored = LearnedRule.from_dict(d)
        self.assertEqual(restored.rule_text, rule.rule_text)
        self.assertEqual(restored.trigger_condition, rule.trigger_condition)
        self.assertEqual(restored.confidence, rule.confidence)
        self.assertEqual(restored.source_task_id, rule.source_task_id)

    def test_from_dict_backward_compat_keys(self) -> None:
        d = {"rule_text": "Old key", "trigger_condition": "old", "confidence": 0.8}
        rule = LearnedRule.from_dict(d)
        self.assertEqual(rule.rule_text, "Old key")


class TestLearnedRuleStore(unittest.TestCase):
    """LearnedRuleStore two-tier persistence."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, ".devsquad.yaml")
        self.tier2_path = os.path.join(self.tmpdir, "corrections.json")
        with open(self.config_path, "w") as f:
            f.write("quality_control:\n  enabled: true\n")
        self.store = LearnedRuleStore(config_path=self.config_path, tier2_path=self.tier2_path)

    def test_tier1_write_and_load(self) -> None:
        rule = LearnedRule(rule_text="Tier1 rule", trigger_condition="t", confidence=0.85)
        result = self.store.add_rule(rule)
        self.assertEqual(result, "tier1")
        loaded = self.store.load_tier1_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].rule_text, "Tier1 rule")

    def test_tier2_write_and_load(self) -> None:
        rule = LearnedRule(rule_text="Tier2 rule", trigger_condition="t", confidence=0.65)
        result = self.store.add_rule(rule)
        self.assertEqual(result, "tier2")
        loaded = self.store.load_tier2_rules()
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0].rule_text, "Tier2 rule")

    def test_rejected_rule_not_stored(self) -> None:
        rule = LearnedRule(rule_text="Bad rule", trigger_condition="t", confidence=0.3)
        result = self.store.add_rule(rule)
        self.assertEqual(result, "rejected")
        self.assertEqual(len(self.store.load_tier1_rules()), 0)
        self.assertEqual(len(self.store.load_tier2_rules()), 0)

    def test_dedup_tier1(self) -> None:
        rule = LearnedRule(rule_text="Dedup rule", trigger_condition="t", confidence=0.85)
        self.store.add_rule(rule)
        self.store.add_rule(rule)
        self.assertEqual(len(self.store.load_tier1_rules()), 1)

    def test_dedup_tier2(self) -> None:
        rule = LearnedRule(rule_text="Dedup tier2", trigger_condition="t", confidence=0.65)
        self.store.add_rule(rule)
        self.store.add_rule(rule)
        self.assertEqual(len(self.store.load_tier2_rules()), 1)

    def test_promote_tier2_to_tier1(self) -> None:
        rule = LearnedRule(rule_text="Promote me", trigger_condition="t", confidence=0.65)
        self.store.add_rule(rule)
        self.assertEqual(len(self.store.load_tier2_rules()), 1)
        self.assertEqual(len(self.store.load_tier1_rules()), 0)
        success = self.store.promote_tier2_to_tier1("Promote me")
        self.assertTrue(success)
        self.assertEqual(len(self.store.load_tier2_rules()), 0)
        tier1 = self.store.load_tier1_rules()
        self.assertEqual(len(tier1), 1)
        self.assertGreaterEqual(tier1[0].confidence, 0.8)

    def test_promote_nonexistent_returns_false(self) -> None:
        success = self.store.promote_tier2_to_tier1("does not exist")
        self.assertFalse(success)

    def test_load_tier1_no_config_file(self) -> None:
        store = LearnedRuleStore(config_path="/nonexistent/path.yaml", tier2_path="/nonexistent/tier2.json")
        self.assertEqual(store.load_tier1_rules(), [])
        self.assertEqual(store.load_tier2_rules(), [])


class TestRetrospectiveExtractLearnedRules(unittest.TestCase):
    """RetrospectiveEngine.extract_learned_rules deviation → rule mapping."""

    def setUp(self) -> None:
        self.engine = RetrospectiveEngine()

    def _make_report(
        self,
        deviations: list[DeviationRecord],
        anchor_drift_count: int = 0,
        final_coverage: float = 0.8,
        improvements: list[str] | None = None,
    ) -> RetrospectiveReport:
        return RetrospectiveReport(
            task_goal="test goal",
            goal_id="goal_1",
            deviations=deviations,
            redundant_steps=[],
            improvements=improvements or [],
            anchor_check_count=5,
            anchor_drift_count=anchor_drift_count,
            final_coverage=final_coverage,
            summary="test",
            created_at=datetime.now().isoformat(),
        )

    def test_goal_uncovered_produces_high_confidence_rule(self) -> None:
        dev = DeviationRecord(
            step_description="test",
            deviation_type="goal_uncovered",
            reason="test",
            impact="test",
            suggestion="test",
        )
        report = self._make_report([dev])
        rules = self.engine.extract_learned_rules(report, task_id="t1")
        self.assertTrue(any(r.confidence >= 0.8 and r.trigger_condition == "task_decomposition" for r in rules))

    def test_sustained_drift_produces_09_confidence_rule(self) -> None:
        dev = DeviationRecord(
            step_description="test",
            deviation_type="sustained_drift",
            reason="test",
            impact="test",
            suggestion="test",
        )
        report = self._make_report([dev])
        rules = self.engine.extract_learned_rules(report, task_id="t1")
        self.assertTrue(any(r.confidence >= 0.9 for r in rules))

    def test_no_deviations_produces_no_rules(self) -> None:
        report = self._make_report([])
        rules = self.engine.extract_learned_rules(report, task_id="t1")
        self.assertEqual(len(rules), 0)

    def test_low_coverage_produces_tier2_rule(self) -> None:
        dev = DeviationRecord(
            step_description="test",
            deviation_type="goal_uncovered",
            reason="test",
            impact="test",
            suggestion="test",
        )
        report = self._make_report([dev], final_coverage=0.3)
        rules = self.engine.extract_learned_rules(report, task_id="t1")
        self.assertTrue(any(r.tier == "tier2" and r.trigger_condition == "low_coverage_detection" for r in rules))

    def test_source_task_id_propagated(self) -> None:
        dev = DeviationRecord(
            step_description="test",
            deviation_type="goal_drift",
            reason="test",
            impact="test",
            suggestion="test",
        )
        report = self._make_report([dev])
        rules = self.engine.extract_learned_rules(report, task_id="my_task_42")
        self.assertTrue(all(r.source_task_id == "my_task_42" for r in rules))


class TestPromptAssemblerLearnedRulesInjection(unittest.TestCase):
    """PromptAssembler loads and injects learned_rules from .devsquad.yaml."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp()
        self.config_path = os.path.join(self.tmpdir, ".devsquad.yaml")
        with open(self.config_path, "w") as f:
            f.write(
                "quality_control:\n"
                "  enabled: true\n"
                "  learned_rules:\n"
                "    - rule: 'Always use pathlib for file paths'\n"
                "      trigger: 'file_manipulation'\n"
                "      confidence: 0.85\n"
                "    - rule: 'Validate inputs at boundaries'\n"
                "      trigger: 'input_validation'\n"
                "      confidence: 0.90\n"
            )

    def test_injection_contains_rules(self) -> None:
        from scripts.collaboration.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(
            role_id="architect",
            base_prompt="You are an architect.",
            config_path=self.config_path,
        )
        injection = assembler._get_learned_rules_injection()
        self.assertIn("pathlib", injection)
        self.assertIn("Validate inputs", injection)
        self.assertIn("Learned Rules", injection)

    def test_no_rules_returns_empty(self) -> None:
        from scripts.collaboration.prompt_assembler import PromptAssembler

        empty_config = os.path.join(self.tmpdir, "empty.yaml")
        with open(empty_config, "w") as f:
            f.write("quality_control:\n  enabled: true\n")
        assembler = PromptAssembler(
            role_id="architect",
            base_prompt="You are an architect.",
            config_path=empty_config,
        )
        self.assertEqual(assembler._get_learned_rules_injection(), "")

    def test_injection_appears_in_assembled_instruction(self) -> None:
        from scripts.collaboration.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(
            role_id="architect",
            base_prompt="You are an architect.",
            config_path=self.config_path,
        )
        result = assembler.assemble(task_description="Design a system")
        self.assertIn("pathlib", result.instruction)


if __name__ == "__main__":
    unittest.main()
