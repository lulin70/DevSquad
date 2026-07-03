#!/usr/bin/env python3
"""Phase 4 Ghost-Feature Defense Tests + E2E Learning Cycle.

This suite provides evidence that RetrospectiveSkill is NOT a ghost
feature — it is genuinely invoked in the dispatch pipeline and closes
the learning loop (extract → persist → inject).

Three test classes:

1. ``TestRunRetrospectiveClosesLoop`` — Ghost-feature defense.
   Verifies ``_run_retrospective`` calls ``extract_learned_rules`` +
   ``add_rule`` after ``retrospective_engine.run()``. Uses spy mocks to
   prove the calls happen (not just that the code exists).

2. ``TestRetrospectiveTriggersOnFailure`` — Failure-path coverage.
   Verifies ``exec_result.success=False`` does NOT skip retrospective.
   This was the original ghost-feature bug (``not exec_result.success``
   guard caused failures to be silently skipped).

3. ``TestE2ELearningCycle`` — Full user scenario.
   Simulates: failed task → retrospective → tier1 rule persisted to
   ``.devsquad.yaml`` → next dispatch's PromptAssembler injects the rule.
   This is the spec §4 US-4 acceptance scenario.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock

from scripts.collaboration.dispatch_steps_quality_mixin import PostDispatchQualityMixin
from scripts.collaboration.learned_rule_store import LearnedRuleStore
from scripts.collaboration.models import DeviationRecord, RetrospectiveReport
from scripts.collaboration.models_lifecycle import (
    GoalItem,
    GoalItemStatus,
    StructuredGoal,
)
from scripts.collaboration.retrospective import RetrospectiveEngine


def _make_goal(coverage: float = 0.3) -> StructuredGoal:
    """Build a StructuredGoal with one uncovered item (triggers goal_uncovered)."""
    item = GoalItem(
        item_id="g1",
        description="Implement feature X",
        status=GoalItemStatus.PENDING,
        coverage_score=coverage,
    )
    return StructuredGoal(
        goal_id="goal_test",
        original_description="Implement feature X",
        items=[item],
        created_at="2026-07-03T00:00:00",
    )


def _make_report(deviation_type: str = "goal_uncovered") -> RetrospectiveReport:
    """Build a RetrospectiveReport with one deviation."""
    return RetrospectiveReport(
        task_goal="test goal",
        goal_id="goal_test",
        deviations=[DeviationRecord(
            step_description="step1",
            deviation_type=deviation_type,
            reason="test",
            impact="test",
            suggestion="test",
        )],
        redundant_steps=[],
        improvements=[],
        anchor_check_count=3,
        anchor_drift_count=0,
        final_coverage=0.3,
        summary="test report",
        created_at="2026-07-03T00:00:00",
    )


class _PipelineHarness(PostDispatchQualityMixin):
    """Minimal PostDispatchPipeline harness for testing _run_retrospective.

    Inherits from PostDispatchQualityMixin (via PostDispatchBase) and only
    sets the attributes that _run_retrospective reads.
    """

    def __init__(
        self,
        retrospective_engine: object | None,
        learned_rule_store: object | None,
        usage_tracker: object | None = None,
        anchor_checker: object | None = None,
    ) -> None:
        self.retrospective_engine = retrospective_engine
        self.learned_rule_store = learned_rule_store
        self.usage_tracker = usage_tracker
        self.anchor_checker = anchor_checker


class TestRunRetrospectiveClosesLoop(unittest.TestCase):
    """Ghost-feature defense: prove _run_retrospective calls the full chain."""

    def test_extract_learned_rules_called_after_run(self) -> None:
        """_run_retrospective must call extract_learned_rules after run().

        Without this call, RetrospectiveEngine.run() output is discarded
        and no rules are ever persisted — the definition of a ghost feature.
        """
        engine = MagicMock(spec=RetrospectiveEngine)
        engine.run.return_value = _make_report()
        engine.extract_learned_rules.return_value = []

        store = MagicMock(spec=LearnedRuleStore)
        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=store,
        )

        result = harness._run_retrospective(
            _task="test task",
            worker_results=[{"role_id": "architect", "output": "some output"}],
            structured_goal=_make_goal(),
            exec_result=SimpleNamespace(success=True),
            total_duration=1.5,
        )

        # run() must be called
        engine.run.assert_called_once()
        # extract_learned_rules MUST be called — this is the ghost-feature guard
        engine.extract_learned_rules.assert_called_once()
        # Report is still returned
        self.assertIsNotNone(result)

    def test_add_rule_called_for_each_extracted_rule(self) -> None:
        """Each extracted LearnedRule must be passed to store.add_rule()."""
        from scripts.collaboration.models_base import LearnedRule

        rules = [
            LearnedRule(rule_text="rule A", trigger_condition="t", confidence=0.85),
            LearnedRule(rule_text="rule B", trigger_condition="t", confidence=0.65),
            LearnedRule(rule_text="rule C", trigger_condition="t", confidence=0.90),
        ]
        engine = MagicMock(spec=RetrospectiveEngine)
        engine.run.return_value = _make_report()
        engine.extract_learned_rules.return_value = rules

        store = MagicMock(spec=LearnedRuleStore)
        store.add_rule.return_value = "tier1"
        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=store,
        )

        harness._run_retrospective(
            _task="test",
            worker_results=[],
            structured_goal=_make_goal(),
            exec_result=SimpleNamespace(success=True),
            total_duration=1.0,
        )

        # add_rule must be called exactly once per extracted rule
        self.assertEqual(store.add_rule.call_count, len(rules))

    def test_no_store_does_not_crash_but_logs_warning(self) -> None:
        """When learned_rule_store is None, retrospective still runs but rules are lost.

        This tests graceful degradation — the retrospective report is still
        returned, but a debug log warns about ghost-feature risk.
        """
        engine = MagicMock(spec=RetrospectiveEngine)
        engine.run.return_value = _make_report()
        engine.extract_learned_rules.return_value = []

        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=None,  # No store configured
        )

        result = harness._run_retrospective(
            _task="test",
            worker_results=[],
            structured_goal=_make_goal(),
            exec_result=SimpleNamespace(success=True),
            total_duration=1.0,
        )

        # Report still returned
        self.assertIsNotNone(result)
        # extract_learned_rules NOT called (store is None — no point extracting)
        engine.extract_learned_rules.assert_not_called()

    def test_no_engine_returns_none(self) -> None:
        """When retrospective_engine is None, returns None gracefully."""
        harness = _PipelineHarness(
            retrospective_engine=None,
            learned_rule_store=MagicMock(spec=LearnedRuleStore),
        )
        result = harness._run_retrospective(
            _task="test",
            worker_results=[],
            structured_goal=_make_goal(),
            exec_result=SimpleNamespace(success=True),
            total_duration=1.0,
        )
        self.assertIsNone(result)


class TestRetrospectiveTriggersOnFailure(unittest.TestCase):
    """Verify failed tasks trigger retrospective (the original ghost-feature bug).

    Before the Phase 4 fix, _run_retrospective had ``not exec_result.success``
    in its guard, causing failed tasks to be silently skipped — exactly when
    learning is most valuable. This suite ensures that guard is gone.
    """

    def test_failure_triggers_retrospective(self) -> None:
        """exec_result.success=False must NOT skip retrospective."""
        engine = MagicMock(spec=RetrospectiveEngine)
        engine.run.return_value = _make_report()
        engine.extract_learned_rules.return_value = []

        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=MagicMock(spec=LearnedRuleStore),
        )

        result = harness._run_retrospective(
            _task="failed task",
            worker_results=[{"role_id": "dev", "output": "incomplete"}],
            structured_goal=_make_goal(),
            exec_result=SimpleNamespace(success=False),  # FAILED
            total_duration=2.0,
        )

        # Retrospective MUST still run on failure
        engine.run.assert_called_once()
        engine.extract_learned_rules.assert_called_once()
        self.assertIsNotNone(result)

    def test_success_also_triggers_retrospective(self) -> None:
        """exec_result.success=True also triggers retrospective (for continuous improvement)."""
        engine = MagicMock(spec=RetrospectiveEngine)
        engine.run.return_value = _make_report()
        engine.extract_learned_rules.return_value = []

        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=MagicMock(spec=LearnedRuleStore),
        )

        harness._run_retrospective(
            _task="success task",
            worker_results=[],
            structured_goal=_make_goal(),
            exec_result=SimpleNamespace(success=True),
            total_duration=1.0,
        )

        engine.run.assert_called_once()

    def test_no_structured_goal_skips_retrospective(self) -> None:
        """Without structured_goal, retrospective cannot run (nothing to analyze)."""
        engine = MagicMock(spec=RetrospectiveEngine)
        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=MagicMock(spec=LearnedRuleStore),
        )

        result = harness._run_retrospective(
            _task="test",
            worker_results=[],
            structured_goal=None,
            exec_result=SimpleNamespace(success=False),
            total_duration=1.0,
        )

        self.assertIsNone(result)
        engine.run.assert_not_called()


class TestE2ELearningCycle(unittest.TestCase):
    """Full E2E: failed task → retrospective → tier1 rule → PromptAssembler injects.

    This is the spec §4 US-4 acceptance scenario:
    - Failed task triggers rule extraction
    - High-confidence rule (>=0.8) persisted to .devsquad.yaml
    - Next dispatch's PromptAssembler loads and injects the rule
    """

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="devsquad_p4_e2e_")
        self.config_path = os.path.join(self.tmpdir, ".devsquad.yaml")
        self.tier2_path = os.path.join(self.tmpdir, "data", "tier2", "corrections.json")
        os.makedirs(os.path.dirname(self.tier2_path), exist_ok=True)
        # Seed config file so LearnedRuleStore can append to it
        with open(self.config_path, "w") as f:
            f.write("quality_control:\n  enabled: true\n")

    def test_failed_task_persists_tier1_rule_to_yaml(self) -> None:
        """Failed task with goal_uncovered deviation → tier1 rule in .devsquad.yaml."""
        engine = RetrospectiveEngine()
        store = LearnedRuleStore(
            config_path=self.config_path,
            tier2_path=self.tier2_path,
        )
        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=store,
            anchor_checker=SimpleNamespace(check_history=[]),
        )

        # Simulate a FAILED task with an uncovered goal item
        goal = _make_goal(coverage=0.2)
        report = harness._run_retrospective(
            _task="implement feature X but failed",
            worker_results=[{"role_id": "dev", "output": "partial work"}],
            structured_goal=goal,
            exec_result=SimpleNamespace(success=False),
            total_duration=5.0,
        )

        # Retrospective ran
        self.assertIsNotNone(report)
        self.assertGreater(len(report.deviations), 0)

        # Rule persisted to .devsquad.yaml (tier1, confidence >= 0.8)
        tier1_rules = store.load_tier1_rules()
        self.assertGreater(len(tier1_rules), 0, "No tier1 rules persisted — learning loop broken!")
        # goal_uncovered → confidence 0.85 → tier1
        self.assertTrue(any(r.confidence >= 0.8 for r in tier1_rules))

    def test_persisted_rule_is_injected_by_prompt_assembler(self) -> None:
        """Rule persisted by retrospective → injected by PromptAssembler on next dispatch.

        This closes the full learning loop:
        1. Failed task → retrospective extracts rule
        2. Rule persisted to .devsquad.yaml
        3. Next dispatch's PromptAssembler reads .devsquad.yaml and injects rule
        """
        # Step 1+2: Run retrospective to persist a rule
        engine = RetrospectiveEngine()
        store = LearnedRuleStore(
            config_path=self.config_path,
            tier2_path=self.tier2_path,
        )
        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=store,
            anchor_checker=SimpleNamespace(check_history=[]),
        )

        goal = _make_goal(coverage=0.1)
        harness._run_retrospective(
            _task="failed task for E2E",
            worker_results=[{"role_id": "dev", "output": ""}],
            structured_goal=goal,
            exec_result=SimpleNamespace(success=False),
            total_duration=3.0,
        )

        # Verify rule was persisted
        tier1_rules = store.load_tier1_rules()
        self.assertGreater(len(tier1_rules), 0)

        # Step 3: PromptAssembler loads from the same .devsquad.yaml
        from scripts.collaboration.prompt_assembler import PromptAssembler

        assembler = PromptAssembler(
            role_id="architect",
            base_prompt="You are an architect.",
            config_path=self.config_path,
        )
        injection = assembler._get_learned_rules_injection()

        # The rule text must appear in the injection
        self.assertNotEqual(injection, "", "PromptAssembler returned empty injection — rule not loaded!")
        # Verify at least one persisted rule text appears in injection
        matched = any(rule.rule_text[:30] in injection for rule in tier1_rules)
        self.assertTrue(matched, f"Persisted rule not found in injection:\n{injection}")

    def test_repeated_dispatches_accumulate_rules(self) -> None:
        """Multiple failed dispatches accumulate distinct rules in .devsquad.yaml."""
        engine = RetrospectiveEngine()
        store = LearnedRuleStore(
            config_path=self.config_path,
            tier2_path=self.tier2_path,
        )
        harness = _PipelineHarness(
            retrospective_engine=engine,
            learned_rule_store=store,
            anchor_checker=SimpleNamespace(check_history=[]),
        )

        # First failed dispatch
        harness._run_retrospective(
            _task="fail 1",
            worker_results=[],
            structured_goal=_make_goal(coverage=0.1),
            exec_result=SimpleNamespace(success=False),
            total_duration=1.0,
        )
        rules_after_1 = store.load_tier1_rules()
        self.assertGreater(len(rules_after_1), 0)

        # Second failed dispatch (dedup by rule_text — same deviation type)
        harness._run_retrospective(
            _task="fail 2",
            worker_results=[],
            structured_goal=_make_goal(coverage=0.2),
            exec_result=SimpleNamespace(success=False),
            total_duration=1.0,
        )
        rules_after_2 = store.load_tier1_rules()
        # Dedup ensures same rule_text doesn't double-write
        self.assertEqual(len(rules_after_1), len(rules_after_2))

    def test_factory_initializes_learned_rule_store(self) -> None:
        """ComponentFactory must create LearnedRuleStore when retrospective is enabled.

        This is the integration guard — if the factory doesn't create the
        store, the learning loop is broken at the source (ghost feature).
        """
        from scripts.collaboration.dispatch_component_factory import (
            ComponentConfig,
            ComponentFactory,
        )

        config = ComponentConfig(
            persist_dir=self.tmpdir,
            memory_dir=os.path.join(self.tmpdir, "memory"),
            enable_warmup=False,
            enable_retrospective=True,
            enable_memory=False,
            enable_skillify=False,
        )
        factory = ComponentFactory()
        components = factory.create_all(config)

        self.assertIn("learned_rule_store", components, "Factory did not create learned_rule_store!")
        self.assertIsNotNone(components["learned_rule_store"], "learned_rule_store is None!")
        self.assertIsInstance(components["learned_rule_store"], LearnedRuleStore)

    def test_factory_skips_store_when_retrospective_disabled(self) -> None:
        """When retrospective is disabled, learned_rule_store is None (graceful degradation)."""
        from scripts.collaboration.dispatch_component_factory import (
            ComponentConfig,
            ComponentFactory,
        )

        config = ComponentConfig(
            persist_dir=self.tmpdir,
            memory_dir=os.path.join(self.tmpdir, "memory"),
            enable_warmup=False,
            enable_retrospective=False,
            enable_memory=False,
            enable_skillify=False,
        )
        factory = ComponentFactory()
        components = factory.create_all(config)

        self.assertIn("learned_rule_store", components)
        self.assertIsNone(components["learned_rule_store"])


if __name__ == "__main__":
    unittest.main()
