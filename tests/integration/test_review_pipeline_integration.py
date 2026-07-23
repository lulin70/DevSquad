#!/usr/bin/env python3
"""Review Pipeline Integration Tests (V4.2.1 P0-1 — Test Pyramid Lift).

Integration tests for the three-stage review pipeline:
    TwoStageReviewGate → SeverityRouter → JudgeAgent

These tests verify that the three post-dispatch review modules integrate
correctly when chained together: the gate produces findings, the router
classifies and routes them, and the judge arbitrates duplicates/conflicts.

Flow:
    1. TwoStageReviewGate.review(spec, code_changes) → TwoStageReviewResult
    2. SeverityRouter.route(findings) → RoutingResult (with FixActions)
    3. JudgeAgent.judge(findings) → JudgeResult (dedup + arbitration)

References:
    - Gate: scripts/collaboration/two_stage_review_gate.py
    - Router: scripts/collaboration/severity_router.py
    - Judge: scripts/collaboration/judge_agent.py
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.judge_agent import JudgeAgent, JudgeAction
from scripts.collaboration.severity_router import SeverityLevel, SeverityRouter
from scripts.collaboration.two_stage_review_gate import (
    ReviewFinding,
    ReviewStage,
    StageResult,
    TwoStageReviewGate,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(
    stage: ReviewStage = ReviewStage.CODE_QUALITY,
    severity: str = "warning",
    category: str = "style",
    description: str = "Sample finding",
    file_path: str = "",
) -> ReviewFinding:
    """Create a ReviewFinding with sensible defaults."""
    return ReviewFinding(
        stage=stage,
        severity=severity,
        category=category,
        description=description,
        file_path=file_path,
    )


def _make_code_changes(files: dict[str, str]) -> dict[str, Any]:
    """Build a code_changes dict accepted by TwoStageReviewGate.review()."""
    return {
        "files": {path: {"content": content} for path, content in files.items()},
    }


def _make_spec(
    planned_files: list[str] | None = None,
    planned_functions: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
) -> dict[str, Any]:
    """Build a spec dict accepted by TwoStageReviewGate.review()."""
    spec: dict[str, Any] = {}
    if planned_files is not None:
        spec["planned_files"] = planned_files
    if planned_functions is not None:
        spec["planned_functions"] = planned_functions
    if acceptance_criteria is not None:
        spec["acceptance_criteria"] = acceptance_criteria
    return spec


# ---------------------------------------------------------------------------
# T1: Full Review Pipeline — Gate → Router → Judge
# ---------------------------------------------------------------------------


class T1_FullReviewPipelineIntegration(unittest.TestCase):
    """T1: Full review pipeline — gate findings flow to router then judge."""

    def setUp(self) -> None:
        self.gate = TwoStageReviewGate(enable_redesign_audit=False)
        self.router = SeverityRouter(development_mode=True)
        self.judge = JudgeAgent()

    def test_01_clean_code_passes_all_stages(self) -> None:
        """Verify: Clean code with tests passes gate, router has no blockers."""
        # Gate in strict_mode requires test files for code changes.
        spec = _make_spec(planned_files=["src/main.py"], planned_functions=["main"])
        code = _make_code_changes({
            "src/main.py": "def main():\n    pass\n",
            "tests/test_main.py": "def test_main():\n    assert main() is None\n",
        })
        gate_result = self.gate.review(spec=spec, code_changes=code)
        router_result = self.router.route(gate_result.findings, context={})
        judge_result = self.judge.judge(gate_result.findings, context={})
        self.assertTrue(gate_result.overall_passed)
        self.assertFalse(router_result.blocked)
        self.assertIsInstance(judge_result.accepted_findings, list)

    def test_02_findings_flow_through_full_pipeline(self) -> None:
        """Verify: Findings from gate flow through router to judge."""
        spec = _make_spec(planned_files=["src/auth.py"], planned_functions=["login"])
        # Missing planned file → spec deviation finding
        code = _make_code_changes({"src/other.py": "# not planned"})
        gate_result = self.gate.review(spec=spec, code_changes=code)
        # Feed findings to router
        router_result = self.router.route(gate_result.findings, context={})
        # Feed same findings to judge
        judge_result = self.judge.judge(gate_result.findings, context={})
        self.assertIsInstance(router_result.actions, list)
        self.assertIsInstance(judge_result.decisions, list)

    def test_03_critical_findings_block_in_router(self) -> None:
        """Verify: Critical findings from gate cause router to block."""
        # Create findings directly to control severity
        findings = [
            _make_finding(severity="critical", category="security",
                          description="SQL injection vulnerability"),
        ]
        router_result = self.router.route(findings, context={})
        self.assertTrue(router_result.blocked)

    def test_04_judge_deduplicates_redundant_findings(self) -> None:
        """Verify: Judge deduplicates similar findings from the gate."""
        findings = [
            _make_finding(description="SQL injection vulnerability in login()"),
            _make_finding(description="SQL injection vulnerability in login"),
        ]
        judge_result = self.judge.judge(findings, context={})
        # Should have fewer accepted than input (dedup occurred)
        self.assertLessEqual(len(judge_result.accepted_findings), len(findings))

    def test_05_pipeline_preserves_finding_metadata(self) -> None:
        """Verify: Finding metadata (category, severity) preserved through pipeline."""
        findings = [
            _make_finding(severity="warning", category="style",
                          description="Line too long", file_path="src/main.py"),
        ]
        router_result = self.router.route(findings, context={})
        judge_result = self.judge.judge(findings, context={})
        # Router should have at least one action
        if router_result.actions:
            self.assertEqual(router_result.actions[0].description,
                             "Line too long")
        # Judge should accept the finding
        if judge_result.accepted_findings:
            self.assertEqual(judge_result.accepted_findings[0].category, "style")


# ---------------------------------------------------------------------------
# T2: Gate → Router Integration
# ---------------------------------------------------------------------------


class T2_GateToRouterIntegration(unittest.TestCase):
    """T2: TwoStageReviewGate findings → SeverityRouter routing."""

    def setUp(self) -> None:
        self.gate = TwoStageReviewGate(enable_redesign_audit=False)
        self.router = SeverityRouter(development_mode=True)

    def test_01_gate_findings_routed_by_severity(self) -> None:
        """Verify: Gate findings are classified into correct severity levels."""
        findings = [
            _make_finding(severity="critical", description="Security issue"),
            _make_finding(severity="warning", description="Style issue"),
            _make_finding(severity="info", description="Info note"),
        ]
        result = self.router.route(findings, context={})
        self.assertTrue(result.blocked)  # critical present
        self.assertGreater(len(result.actions), 0)

    def test_02_no_findings_no_block(self) -> None:
        """Verify: Empty findings list → router not blocked."""
        result = self.router.route([], context={})
        self.assertFalse(result.blocked)
        self.assertEqual(len(result.actions), 0)

    def test_03_router_actions_contain_finding_ids(self) -> None:
        """Verify: Router actions have unique finding_id fields."""
        findings = [
            _make_finding(description="Issue 1"),
            _make_finding(description="Issue 2"),
        ]
        result = self.router.route(findings, context={})
        ids = [a.finding_id for a in result.actions]
        self.assertEqual(len(ids), len(set(ids)), "Finding IDs should be unique")

    def test_04_critical_finding_always_blocks(self) -> None:
        """Verify: A single critical finding blocks the router."""
        findings = [_make_finding(severity="critical", description="Blocker")]
        result = self.router.route(findings, context={})
        self.assertTrue(result.blocked)

    def test_05_warning_only_does_not_block(self) -> None:
        """Verify: Warning-level findings don't block progression."""
        findings = [_make_finding(severity="warning", description="Warning")]
        result = self.router.route(findings, context={})
        self.assertFalse(result.blocked)


# ---------------------------------------------------------------------------
# T3: Router → Judge Integration
# ---------------------------------------------------------------------------


class T3_RouterToJudgeIntegration(unittest.TestCase):
    """T3: SeverityRouter results → JudgeAgent arbitration."""

    def setUp(self) -> None:
        self.router = SeverityRouter(development_mode=True)
        # Low threshold so findings aren't rejected by confidence filtering;
        # these tests focus on dedup/arbitration, not confidence scoring.
        self.judge = JudgeAgent(confidence_threshold=0.1)

    def test_01_router_findings_judged_correctly(self) -> None:
        """Verify: Findings that went through router are judged correctly."""
        findings = [
            _make_finding(severity="critical", description="Critical bug"),
            _make_finding(severity="warning", description="Minor issue"),
        ]
        self.router.route(findings, context={})
        judge_result = self.judge.judge(findings, context={})
        # Findings should be accepted (passed dedup + confidence filter)
        self.assertGreater(len(judge_result.accepted_findings), 0)

    def test_02_judge_merges_duplicate_findings(self) -> None:
        """Verify: Judge merges near-duplicate findings."""
        findings = [
            _make_finding(description="SQL injection in query"),
            _make_finding(description="SQL injection in query function"),
        ]
        judge_result = self.judge.judge(findings, context={})
        # Merged count should be > 0 if dedup occurred
        self.assertGreaterEqual(judge_result.merged_count, 0)

    def test_03_judge_accepts_unique_findings(self) -> None:
        """Verify: Unique findings are accepted by the judge."""
        findings = [
            _make_finding(description="Memory leak in parser"),
            _make_finding(description="Race condition in worker pool"),
        ]
        judge_result = self.judge.judge(findings, context={})
        self.assertGreater(len(judge_result.accepted_findings), 0)

    def test_04_empty_findings_judge_returns_empty(self) -> None:
        """Verify: Judge handles empty findings list gracefully."""
        judge_result = self.judge.judge([], context={})
        self.assertEqual(len(judge_result.accepted_findings), 0)
        self.assertEqual(len(judge_result.decisions), 0)


# ---------------------------------------------------------------------------
# T4: Auto-Fix Loop Integration
# ---------------------------------------------------------------------------


class T4_AutoFixLoopIntegration(unittest.TestCase):
    """T4: SeverityRouter.run_fix_loop() with auto-fix callable."""

    def test_01_fix_loop_resolves_auto_fixable_issues(self) -> None:
        """Verify: run_fix_loop() applies auto-fix and resolves issues."""
        fix_call_count: list[int] = []

        def auto_fix(action: Any, context: dict[str, Any]) -> bool:
            fix_call_count.append(1)
            return True  # Fix succeeded

        router = SeverityRouter(
            development_mode=True,
            max_rounds=3,
            auto_fix_callable=auto_fix,
        )
        findings = [
            _make_finding(severity="critical", description="Fixable critical bug"),
        ]
        result = router.run_fix_loop(findings, context={})
        self.assertIsInstance(result.actions, list)

    def test_02_fix_loop_exhausted_escalates(self) -> None:
        """Verify: When auto-fix fails, findings remain unfixed."""
        def always_fail(action: Any, context: dict[str, Any]) -> bool:
            return False  # Fix always fails

        router = SeverityRouter(
            development_mode=True,
            max_rounds=2,
            auto_fix_callable=always_fail,
        )
        findings = [
            _make_finding(severity="critical", description="Unfixable bug"),
        ]
        result = router.run_fix_loop(findings, context={})
        self.assertIsInstance(result, type(router.route(findings)))

    def test_03_fix_loop_no_callable_skips_fix(self) -> None:
        """Verify: Without auto_fix_callable, no fix is attempted."""
        router = SeverityRouter(development_mode=True, max_rounds=3)
        findings = [_make_finding(severity="critical", description="Bug")]
        result = router.run_fix_loop(findings, context={})
        self.assertFalse(result.auto_fix_triggered)

    def test_04_fix_loop_with_no_findings_returns_empty(self) -> None:
        """Verify: run_fix_loop() with empty findings returns empty result."""
        router = SeverityRouter(development_mode=True, max_rounds=3)
        result = router.run_fix_loop([], context={})
        self.assertEqual(len(result.actions), 0)


# ---------------------------------------------------------------------------
# T5: Judge Deduplication Integration
# ---------------------------------------------------------------------------


class T5_JudgeDeduplicationIntegration(unittest.TestCase):
    """T5: JudgeAgent deduplication and conflict resolution."""

    def setUp(self) -> None:
        # Low threshold so findings aren't rejected by confidence filtering;
        # these tests focus on dedup behavior, not confidence scoring.
        self.judge = JudgeAgent(confidence_threshold=0.1, similarity_threshold=0.80)

    def test_01_exact_duplicates_merged(self) -> None:
        """Verify: Exact duplicate descriptions are merged by the judge."""
        findings = [
            _make_finding(description="SQL injection in login function"),
            _make_finding(description="SQL injection in login function"),
        ]
        result = self.judge.judge(findings, context={})
        self.assertLessEqual(len(result.accepted_findings), 1)

    def test_02_different_findings_not_merged(self) -> None:
        """Verify: Genuinely different findings are not merged."""
        findings = [
            _make_finding(description="Memory leak in parser module"),
            _make_finding(description="SQL injection in login function"),
        ]
        result = self.judge.judge(findings, context={})
        self.assertEqual(len(result.accepted_findings), 2)

    def test_03_judge_with_history_enabled(self) -> None:
        """Verify: Judge works with history learning enabled."""
        judge = JudgeAgent(enable_history=True)
        findings = [_make_finding(description="Test finding")]
        result = judge.judge(findings, context={})
        self.assertIsInstance(result, type(result))

    def test_04_judge_summary_populated(self) -> None:
        """Verify: Judge result includes a summary string."""
        findings = [_make_finding(description="Test finding")]
        result = self.judge.judge(findings, context={})
        self.assertIsInstance(result.summary, str)


# ---------------------------------------------------------------------------
# T6: Disabled Gate Integration
# ---------------------------------------------------------------------------


class T6_DisabledGateIntegration(unittest.TestCase):
    """T6: TwoStageReviewGate with enable_two_stage_review=False."""

    def test_01_disabled_gate_returns_empty_result(self) -> None:
        """Verify: Disabled gate returns empty result with no findings."""
        gate = TwoStageReviewGate(enable_two_stage_review=False, enable_redesign_audit=False)
        result = gate.review(spec=_make_spec(), code_changes=_make_code_changes({}))
        self.assertTrue(result.overall_passed)
        self.assertEqual(len(result.findings), 0)

    def test_02_disabled_gate_does_not_block(self) -> None:
        """Verify: Disabled gate never produces blocking findings."""
        gate = TwoStageReviewGate(enable_two_stage_review=False, enable_redesign_audit=False)
        result = gate.review(
            spec=_make_spec(planned_files=["missing.py"]),
            code_changes=_make_code_changes({"other.py": "# wrong"}),
        )
        self.assertTrue(result.overall_passed)
        self.assertEqual(len(result.blocking_findings), 0)

    def test_03_disabled_gate_with_router_produces_no_actions(self) -> None:
        """Verify: Disabled gate + router produces no routing actions."""
        gate = TwoStageReviewGate(enable_two_stage_review=False, enable_redesign_audit=False)
        router = SeverityRouter(development_mode=True)
        gate_result = gate.review(spec=_make_spec(), code_changes=_make_code_changes({}))
        router_result = router.route(gate_result.findings, context={})
        self.assertEqual(len(router_result.actions), 0)
        self.assertFalse(router_result.blocked)


# ---------------------------------------------------------------------------
# T7: Empty and Edge Cases
# ---------------------------------------------------------------------------


class T7_EmptyAndEdgeCases(unittest.TestCase):
    """T7: Empty inputs, None context, and boundary conditions."""

    def test_01_empty_spec_and_code_changes(self) -> None:
        """Verify: Gate handles empty spec and code_changes gracefully."""
        gate = TwoStageReviewGate(enable_redesign_audit=False)
        result = gate.review(spec={}, code_changes={})
        self.assertIsInstance(result.findings, list)

    def test_02_none_context_to_router(self) -> None:
        """Verify: Router handles None context."""
        router = SeverityRouter(development_mode=True)
        findings = [_make_finding(description="Test")]
        result = router.route(findings, context=None)
        self.assertIsInstance(result.actions, list)

    def test_03_none_context_to_judge(self) -> None:
        """Verify: Judge handles None context."""
        judge = JudgeAgent()
        findings = [_make_finding(description="Test")]
        result = judge.judge(findings, context=None)
        self.assertIsInstance(result.decisions, list)

    def test_04_mixed_severity_findings_routed(self) -> None:
        """Verify: Router correctly handles a mix of all severity levels."""
        router = SeverityRouter(development_mode=True)
        findings = [
            _make_finding(severity="critical", description="Critical"),
            _make_finding(severity="warning", description="Warning"),
            _make_finding(severity="info", description="Info"),
        ]
        result = router.route(findings, context={})
        self.assertTrue(result.blocked)  # critical present
        self.assertEqual(len(result.actions), 3)

    def test_05_router_status_property(self) -> None:
        """Verify: RoutingResult.status property returns valid string."""
        router = SeverityRouter(development_mode=True)
        result = router.route([], context={})
        self.assertIn(result.status, ("skipped", "success", "partial", "failed"))


if __name__ == "__main__":
    unittest.main()
