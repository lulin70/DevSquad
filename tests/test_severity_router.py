#!/usr/bin/env python3
"""
Tests for SeverityRouter (V3.8 #3) — Severity Router + Auto-Fix Loop.

Coverage:
  - SeverityLevel enum (values, from_string, aliases)
  - FixAction dataclass (is_blocking, to_dict)
  - RoutingResult dataclass (all_fixed, status, to_dict)
  - Severity classification (critical/warning/info → CRITICAL/HIGH/INFO)
  - CRITICAL blocks progression
  - HIGH triggers auto-fix (when auto_fixable)
  - MEDIUM/LOW/INFO non-blocking
  - Auto-fix loop: success on round 1
  - Auto-fix loop: success on round 2
  - Auto-fix loop: failure after max_rounds → escalate
  - FixAction tracking (fix_applied, fix_verified)
  - RoutingResult summary
  - Integration with TwoStageReviewGate
  - _should_escalate logic
  - Production mode (no auto-fix)
  - Backward-compat: collect_findings, run_auto_fix_loop
"""

from __future__ import annotations

import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.event_bus import EventBus
from scripts.collaboration.severity_router import (
    AutoFixResult,
    Finding,
    FixAction,
    RoutingResult,
    Severity,
    SeverityLevel,
    SeverityRouter,
)
from scripts.collaboration.two_stage_review_gate import (
    ReviewFinding,
    ReviewStage,
    StageResult,
    TwoStageReviewGate,
    TwoStageReviewResult,
)


class TestSeverityLevelEnum(unittest.TestCase):
    """Verify SeverityLevel enum and parsing."""

    def test_severity_values(self) -> None:
        self.assertEqual(SeverityLevel.CRITICAL.value, "critical")
        self.assertEqual(SeverityLevel.HIGH.value, "high")
        self.assertEqual(SeverityLevel.MEDIUM.value, "medium")
        self.assertEqual(SeverityLevel.LOW.value, "low")
        self.assertEqual(SeverityLevel.INFO.value, "info")

    def test_from_string_known_values(self) -> None:
        self.assertEqual(SeverityLevel.from_string("critical"), SeverityLevel.CRITICAL)
        self.assertEqual(SeverityLevel.from_string("high"), SeverityLevel.HIGH)
        self.assertEqual(SeverityLevel.from_string("medium"), SeverityLevel.MEDIUM)
        self.assertEqual(SeverityLevel.from_string("low"), SeverityLevel.LOW)
        self.assertEqual(SeverityLevel.from_string("info"), SeverityLevel.INFO)

    def test_from_string_case_insensitive_and_aliases(self) -> None:
        self.assertEqual(SeverityLevel.from_string("CRITICAL"), SeverityLevel.CRITICAL)
        self.assertEqual(SeverityLevel.from_string("p0"), SeverityLevel.CRITICAL)
        self.assertEqual(SeverityLevel.from_string("blocker"), SeverityLevel.CRITICAL)
        self.assertEqual(SeverityLevel.from_string("warning"), SeverityLevel.HIGH)
        self.assertEqual(SeverityLevel.from_string("major"), SeverityLevel.HIGH)
        self.assertEqual(SeverityLevel.from_string("minor"), SeverityLevel.LOW)

    def test_from_string_unknown_defaults_to_medium(self) -> None:
        self.assertEqual(SeverityLevel.from_string("unknown"), SeverityLevel.MEDIUM)
        self.assertEqual(SeverityLevel.from_string(""), SeverityLevel.MEDIUM)

    def test_severity_is_alias_for_severity_level(self) -> None:
        # Backward-compatibility alias
        self.assertIs(Severity, SeverityLevel)


class TestFixAction(unittest.TestCase):
    """Verify FixAction dataclass."""

    def test_is_blocking_for_critical_and_high(self) -> None:
        self.assertTrue(
            FixAction("id1", SeverityLevel.CRITICAL, "desc").is_blocking()
        )
        self.assertTrue(
            FixAction("id2", SeverityLevel.HIGH, "desc").is_blocking()
        )

    def test_is_not_blocking_for_medium_low_info(self) -> None:
        self.assertFalse(FixAction("id", SeverityLevel.MEDIUM, "d").is_blocking())
        self.assertFalse(FixAction("id", SeverityLevel.LOW, "d").is_blocking())
        self.assertFalse(FixAction("id", SeverityLevel.INFO, "d").is_blocking())

    def test_to_dict_round_trip(self) -> None:
        action = FixAction(
            finding_id="f1",
            severity=SeverityLevel.HIGH,
            description="SQL injection",
            file_path="src/db.py",
            suggested_fix="Use parameterized queries",
            auto_fixable=True,
            fix_applied=True,
            fix_verified=True,
        )
        d = action.to_dict()
        self.assertEqual(d["finding_id"], "f1")
        self.assertEqual(d["severity"], "high")
        self.assertEqual(d["file_path"], "src/db.py")
        self.assertTrue(d["auto_fixable"])
        self.assertTrue(d["fix_applied"])
        self.assertTrue(d["fix_verified"])

    def test_finding_is_alias_for_fix_action(self) -> None:
        # Backward-compatibility alias
        self.assertIs(Finding, FixAction)


class TestRoutingResult(unittest.TestCase):
    """Verify RoutingResult dataclass."""

    def test_all_fixed_true_when_no_blocking(self) -> None:
        result = RoutingResult(
            actions=[FixAction("id", SeverityLevel.LOW, "d")],
            blocked=False,
        )
        self.assertTrue(result.all_fixed)

    def test_all_fixed_true_when_blocking_fixed(self) -> None:
        action = FixAction("id", SeverityLevel.HIGH, "d", auto_fixable=True,
                           fix_applied=True, fix_verified=True)
        result = RoutingResult(actions=[action], blocked=False,
                               auto_fix_triggered=True)
        self.assertTrue(result.all_fixed)

    def test_all_fixed_false_when_blocking_unfixed(self) -> None:
        action = FixAction("id", SeverityLevel.HIGH, "d")
        result = RoutingResult(actions=[action])
        self.assertFalse(result.all_fixed)

    def test_status_success_when_no_blocking(self) -> None:
        result = RoutingResult(
            actions=[FixAction("id", SeverityLevel.MEDIUM, "d")]
        )
        self.assertEqual(result.status, "success")

    def test_status_failed_when_blocking_unfixed(self) -> None:
        action = FixAction("id", SeverityLevel.HIGH, "d")
        result = RoutingResult(actions=[action])
        self.assertEqual(result.status, "failed")

    def test_status_partial_when_some_fixed(self) -> None:
        a1 = FixAction("id1", SeverityLevel.HIGH, "d1", fix_applied=True)
        a2 = FixAction("id2", SeverityLevel.HIGH, "d2")
        result = RoutingResult(actions=[a1, a2])
        self.assertEqual(result.status, "partial")

    def test_to_dict_includes_all_fields(self) -> None:
        action = FixAction("id", SeverityLevel.CRITICAL, "d")
        result = RoutingResult(
            actions=[action], blocked=True, auto_fix_triggered=False,
            fix_round=0, max_rounds=3, summary="test"
        )
        d = result.to_dict()
        self.assertIn("actions", d)
        self.assertIn("blocked", d)
        self.assertIn("auto_fix_triggered", d)
        self.assertIn("fix_round", d)
        self.assertIn("max_rounds", d)
        self.assertIn("summary", d)
        self.assertTrue(d["blocked"])

    def test_auto_fix_result_is_alias_for_routing_result(self) -> None:
        # Backward-compatibility alias
        self.assertIs(AutoFixResult, RoutingResult)


class TestSeverityClassification(unittest.TestCase):
    """Verify _classify_severity mapping."""

    def test_critical_finding_maps_to_critical(self) -> None:
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "xss")
        self.assertEqual(
            SeverityRouter._classify_severity(finding), SeverityLevel.CRITICAL
        )

    def test_warning_finding_maps_to_high(self) -> None:
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "style", "long line")
        self.assertEqual(
            SeverityRouter._classify_severity(finding), SeverityLevel.HIGH
        )

    def test_info_finding_maps_to_info(self) -> None:
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "info", "note", "FYI")
        self.assertEqual(
            SeverityRouter._classify_severity(finding), SeverityLevel.INFO
        )

    def test_missing_docstring_downgraded_to_low(self) -> None:
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "missing_docstring", "d")
        self.assertEqual(
            SeverityRouter._classify_severity(finding), SeverityLevel.LOW
        )

    def test_oversized_output_downgraded_to_low(self) -> None:
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "oversized_output", "d")
        self.assertEqual(
            SeverityRouter._classify_severity(finding), SeverityLevel.LOW
        )

    def test_acceptance_criteria_downgraded_to_medium(self) -> None:
        finding = ReviewFinding(
            ReviewStage.SPEC_COMPLIANCE, "warning",
            "acceptance_criteria_not_evident", "d"
        )
        self.assertEqual(
            SeverityRouter._classify_severity(finding), SeverityLevel.MEDIUM
        )

    def test_classify_static_method(self) -> None:
        self.assertEqual(SeverityRouter.classify("critical"), SeverityLevel.CRITICAL)
        self.assertEqual(SeverityRouter.classify(SeverityLevel.HIGH), SeverityLevel.HIGH)

    def test_should_auto_fix(self) -> None:
        self.assertTrue(
            SeverityRouter.should_auto_fix(
                ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "c", "d")
            )
        )
        self.assertTrue(
            SeverityRouter.should_auto_fix(
                ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "c", "d")
            )
        )
        self.assertFalse(
            SeverityRouter.should_auto_fix(
                ReviewFinding(ReviewStage.CODE_QUALITY, "info", "c", "d")
            )
        )


class TestRouting(unittest.TestCase):
    """Verify the route() method."""

    def test_critical_finding_blocks_progression(self) -> None:
        """CRITICAL blocks progression."""
        router = SeverityRouter(development_mode=True)
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
        ]
        result = router.route(findings, context={})
        self.assertTrue(result.blocked)
        self.assertEqual(len(result.actions), 1)
        self.assertEqual(result.actions[0].severity, SeverityLevel.CRITICAL)

    def test_high_finding_triggers_auto_fix_when_fixable(self) -> None:
        """HIGH triggers auto-fix (when auto_fixable)."""
        # Use an auto-fixable category
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "warning", "anti_pattern_bare_except", "bare except"
        )
        # With a callable that returns True
        def fix_fn(action: FixAction, context: dict) -> bool:
            return True

        router = SeverityRouter(development_mode=True, auto_fix_callable=fix_fn)
        result = router.route([finding], context={})
        self.assertFalse(result.blocked)
        self.assertTrue(result.auto_fix_triggered)
        self.assertTrue(result.actions[0].fix_applied)

    def test_medium_low_info_are_non_blocking(self) -> None:
        """MEDIUM/LOW/INFO non-blocking."""
        router = SeverityRouter(development_mode=True)
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "info", "note", "FYI"),
            ReviewFinding(
                ReviewStage.SPEC_COMPLIANCE, "warning",
                "acceptance_criteria_not_evident", "criterion"
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "missing_docstring", "no doc"
            ),
        ]
        result = router.route(findings, context={})
        self.assertFalse(result.blocked)
        # None should be blocking
        for action in result.actions:
            self.assertFalse(action.is_blocking())

    def test_empty_findings_returns_empty_result(self) -> None:
        router = SeverityRouter()
        result = router.route([], context={})
        self.assertEqual(len(result.actions), 0)
        self.assertFalse(result.blocked)
        self.assertEqual(result.status, "skipped")


class TestAutoFixLoop(unittest.TestCase):
    """Verify the run_fix_loop auto-fix loop."""

    def test_auto_fix_success_on_round_1(self) -> None:
        """Auto-fix loop: success on round 1."""
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "warning", "anti_pattern_bare_except", "bare except"
        )
        call_count = [0]

        def fix_fn(action: FixAction, context: dict) -> bool:
            call_count[0] += 1
            return True  # fix succeeds

        router = SeverityRouter(
            development_mode=True, max_rounds=3, auto_fix_callable=fix_fn
        )
        result = router.run_fix_loop([finding], context={})
        self.assertEqual(result.status, "success")
        self.assertTrue(result.auto_fix_triggered)
        self.assertEqual(call_count[0], 1)  # fixed on first round

    def test_auto_fix_success_on_round_2(self) -> None:
        """Auto-fix loop: success on round 2."""
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "warning", "anti_pattern_bare_except", "bare except"
        )
        call_count = [0]

        def fix_fn(action: FixAction, context: dict) -> bool:
            call_count[0] += 1
            # First attempt fails, second succeeds
            return call_count[0] >= 2

        router = SeverityRouter(
            development_mode=True, max_rounds=3, auto_fix_callable=fix_fn
        )
        result = router.run_fix_loop([finding], context={})
        self.assertEqual(result.status, "success")
        self.assertEqual(result.fix_round, 2)
        self.assertEqual(call_count[0], 2)

    def test_auto_fix_failure_after_max_rounds_escalates(self) -> None:
        """Auto-fix loop: failure after max_rounds → escalate."""
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "warning", "anti_pattern_bare_except", "bare except"
        )

        def fix_fn(action: FixAction, context: dict) -> bool:
            return False  # always fails

        router = SeverityRouter(
            development_mode=True, max_rounds=2, auto_fix_callable=fix_fn
        )
        result = router.run_fix_loop([finding], context={})
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.fix_round, 2)
        # _should_escalate should return True (max rounds exhausted, unfixed)
        self.assertTrue(router._should_escalate(result))

    def test_critical_findings_block_without_auto_fix(self) -> None:
        """CRITICAL findings block progression — no auto-fix loop."""
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
        )
        call_count = [0]

        def fix_fn(action: FixAction, context: dict) -> bool:
            call_count[0] += 1
            return True

        router = SeverityRouter(
            development_mode=True, max_rounds=3, auto_fix_callable=fix_fn
        )
        result = router.run_fix_loop([finding], context={})
        self.assertTrue(result.blocked)
        self.assertEqual(result.fix_round, 0)  # no rounds run
        self.assertEqual(call_count[0], 0)  # fix never called
        self.assertTrue(router._should_escalate(result))

    def test_no_blocking_findings_returns_success(self) -> None:
        router = SeverityRouter(development_mode=True)
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "info", "note", "FYI"),
        ]
        result = router.run_fix_loop(findings, context={})
        self.assertEqual(result.status, "success")
        self.assertEqual(result.fix_round, 0)

    def test_production_mode_skips_auto_fix(self) -> None:
        """Production mode — no auto-fix."""
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "warning", "anti_pattern_bare_except", "bare except"
        )

        def fix_fn(action: FixAction, context: dict) -> bool:
            self.fail("fix_callable should not be called in production mode")
            return True

        router = SeverityRouter(
            development_mode=False, max_rounds=3, auto_fix_callable=fix_fn
        )
        result = router.run_fix_loop([finding], context={})
        # HIGH finding, production mode → no fix applied
        self.assertFalse(result.auto_fix_triggered)
        self.assertEqual(result.status, "failed")

    def test_fix_action_tracking(self) -> None:
        """FixAction tracking — fix_applied and fix_verified set correctly."""
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "warning", "anti_pattern_bare_except", "bare except"
        )

        def fix_fn(action: FixAction, context: dict) -> bool:
            return True

        router = SeverityRouter(
            development_mode=True, max_rounds=3, auto_fix_callable=fix_fn
        )
        result = router.run_fix_loop([finding], context={})
        action = result.actions[0]
        self.assertTrue(action.fix_applied)
        self.assertTrue(action.fix_verified)

    def test_routing_result_summary_contains_key_info(self) -> None:
        """RoutingResult summary contains key info."""
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
            ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "style", "long line"),
        ]
        router = SeverityRouter(development_mode=True)
        result = router.route(findings, context={})
        self.assertIn("SeverityRouter", result.summary)
        self.assertIn("BLOCKED", result.summary)
        self.assertIn("critical", result.summary)


class TestShouldEscalate(unittest.TestCase):
    """Verify _should_escalate logic."""

    def test_escalate_when_blocked(self) -> None:
        result = RoutingResult(
            actions=[FixAction("id", SeverityLevel.CRITICAL, "d")],
            blocked=True,
        )
        self.assertTrue(SeverityRouter()._should_escalate(result))

    def test_escalate_when_max_rounds_exhausted_with_remaining(self) -> None:
        action = FixAction("id", SeverityLevel.HIGH, "d")
        result = RoutingResult(
            actions=[action], fix_round=3, max_rounds=3
        )
        self.assertTrue(SeverityRouter()._should_escalate(result))

    def test_no_escalate_when_all_fixed(self) -> None:
        action = FixAction("id", SeverityLevel.HIGH, "d",
                           fix_applied=True, fix_verified=True)
        result = RoutingResult(
            actions=[action], fix_round=1, max_rounds=3
        )
        self.assertFalse(SeverityRouter()._should_escalate(result))

    def test_no_escalate_when_rounds_remaining(self) -> None:
        action = FixAction("id", SeverityLevel.HIGH, "d")
        result = RoutingResult(
            actions=[action], fix_round=1, max_rounds=3
        )
        self.assertFalse(SeverityRouter()._should_escalate(result))


class TestEventBusSubscription(unittest.TestCase):
    """Verify EventBus subscription (backward compat)."""

    def test_subscribe_registers_handlers(self) -> None:
        bus = EventBus()
        router = SeverityRouter(event_bus=bus)
        router.subscribe()
        bus.emit("security.finding", severity="critical", category="vuln", description="xss")
        bus.emit("tester.finding", severity="high", category="bug", description="crash")
        bus.emit("review.finding", severity="medium", category="style", description="nit")
        findings = router.get_collected_findings()
        self.assertEqual(len(findings), 3)

    def test_subscribe_is_idempotent(self) -> None:
        bus = EventBus()
        router = SeverityRouter(event_bus=bus)
        router.subscribe()
        router.subscribe()
        bus.emit("security.finding", severity="low", category="c", description="d")
        self.assertEqual(len(router.get_collected_findings()), 1)

    def test_unsubscribe_removes_handlers(self) -> None:
        bus = EventBus()
        router = SeverityRouter(event_bus=bus)
        router.subscribe()
        router.unsubscribe()
        bus.emit("security.finding", severity="low", category="c", description="d")
        self.assertEqual(len(router.get_collected_findings()), 0)


class TestBackwardCompatCollectAndRunAutoFixLoop(unittest.TestCase):
    """Verify backward-compat collect_findings + run_auto_fix_loop."""

    def test_collect_findings_from_worker_results(self) -> None:
        router = SeverityRouter()
        worker_results = [
            {
                "role_id": "security",
                "output": "found issues",
                "findings": [
                    {"severity": "critical", "category": "vuln", "description": "xss"},
                    {"severity": "low", "category": "info", "description": "comment"},
                ],
            }
        ]
        findings = router.collect_findings(worker_results)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, SeverityLevel.CRITICAL)

    def test_collect_findings_from_review_result(self) -> None:
        router = SeverityRouter()
        review = MagicMock()
        review.blocking_findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "vuln", "xss"),
        ]
        review.warnings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "style", "nit"),
        ]
        findings = router.collect_findings([], review_result=review)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, SeverityLevel.CRITICAL)

    def test_run_auto_fix_loop_with_legacy_fix_callable(self) -> None:
        """Legacy fix_callable signature: takes list, returns remaining."""
        router = SeverityRouter(development_mode=True, max_fix_iterations=3)
        findings = [
            FixAction("id1", SeverityLevel.HIGH, "desc1"),
        ]

        def fix_fn(actions: list[FixAction]) -> list[FixAction]:
            return []  # all fixed

        result = router.run_auto_fix_loop(findings, fix_callable=fix_fn)
        self.assertEqual(result.status, "success")
        self.assertTrue(result.actions[0].fix_applied)

    def test_run_auto_fix_loop_no_findings_uses_collected(self) -> None:
        bus = EventBus()
        router = SeverityRouter(event_bus=bus, development_mode=True)
        router.subscribe()
        bus.emit("security.finding", severity="low", category="c", description="d")
        result = router.run_auto_fix_loop()
        # LOW is non-blocking → success
        self.assertEqual(result.status, "success")


class TestIntegrationWithTwoStageReviewGate(unittest.TestCase):
    """Integration with TwoStageReviewGate."""

    def test_full_pipeline_review_then_route(self) -> None:
        """End-to-end: TwoStageReviewGate → SeverityRouter."""
        gate = TwoStageReviewGate()
        spec = {
            "planned_files": ["src/auth.py"],
            "planned_functions": ["login"],
            "total_tasks": 2,
            "completed_tasks": 1,  # incomplete
            "failed_tasks": 1,
        }
        code_changes = {
            "files": {
                "src/bad.py": {
                    "content": 'api_key = "sk-1234567890abcdef1234567890abcdef"\n'
                }
            }
        }
        review_result = gate.review(spec=spec, code_changes=code_changes)
        self.assertFalse(review_result.overall_passed)

        # Route the findings through SeverityRouter
        router = SeverityRouter(development_mode=True)
        routing_result = router.route(review_result.findings, context={})
        # Should have at least one CRITICAL (from security or spec compliance)
        self.assertTrue(routing_result.blocked)
        self.assertGreater(len(routing_result.actions), 0)

    def test_full_pipeline_with_auto_fix_loop(self) -> None:
        """End-to-end: review → route → run_fix_loop."""
        gate = TwoStageReviewGate()
        # Create a spec that produces only HIGH-severity findings (warnings)
        spec = {"acceptance_criteria": ["user authentication"]}
        code_changes = {
            "files": {
                "src/foo.py": {"content": "print('hello')\n"}
            }
        }
        review_result = gate.review(spec=spec, code_changes=code_changes)

        router = SeverityRouter(development_mode=True, max_rounds=2)
        result = router.run_fix_loop(review_result.findings, context={})
        # acceptance_criteria_not_evident → MEDIUM (non-blocking) → success
        self.assertEqual(result.status, "success")

    def test_to_dict_serialization(self) -> None:
        router = SeverityRouter(development_mode=True)
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "vuln", "xss"),
        ]
        result = router.route(findings, context={})
        d = result.to_dict()
        self.assertIn("actions", d)
        self.assertIn("blocked", d)
        self.assertIn("auto_fix_triggered", d)
        self.assertIn("fix_round", d)
        self.assertIn("max_rounds", d)
        self.assertIn("summary", d)
        self.assertEqual(len(d["actions"]), 1)
        self.assertTrue(d["blocked"])


if __name__ == "__main__":
    unittest.main()
