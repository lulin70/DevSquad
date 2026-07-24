#!/usr/bin/env python3
"""TwoStageReviewGate + SeverityRouter + JudgeAgent Integration Tests
(Test Pyramid Lift — integration layer coverage gap fill).

End-to-end integration tests for the three-stage code review pipeline.
Verifies CROSS-MODULE interactions among the three review collaborators:

    scripts/collaboration/two_stage_review_gate.py — TwoStageReviewGate
        (Stage 1: spec compliance; Stage 2: code quality; Stage 3:
        redesign audit. Critical findings block progression.)
    scripts/collaboration/severity_router.py — SeverityRouter
        (Classifies findings by severity; CRITICAL blocks, HIGH
        triggers auto-fix loop (up to max_rounds), MEDIUM/LOW/INFO
        are tracked non-blocking.)
    scripts/collaboration/judge_agent.py — JudgeAgent
        (Arbitrates findings: deduplication by text similarity,
        conflict resolution by severity upgrade, confidence
        filtering, and optional historical learning.)

Pipeline flow:
    1. TwoStageReviewGate.review(spec, code_changes) → TwoStageReviewResult
       (produces findings with stage + severity + category metadata)
    2. SeverityRouter.route(findings) → RoutingResult
       (classifies into CRITICAL/HIGH/MEDIUM/LOW/INFO; blocks on
       CRITICAL; auto-fixes HIGH+auto_fixable in development mode)
    3. JudgeAgent.judge(findings) → JudgeResult
       (deduplicates near-identical findings, resolves severity
       conflicts, filters low-confidence findings, optionally
       applies historical learning)

Test categories:
    T1: TwoStageReviewGate basic two-stage flow (spec → quality)
    T2: SeverityRouter severity routing + auto-fix loop
    T3: JudgeAgent arbitration (dedup / conflict / confidence / history)
    T4: Three-module end-to-end pipeline integration
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.judge_agent import (
    HistoryRecord,
    JudgeAction,
    JudgeAgent,
    JudgeDecision,
)
from scripts.collaboration.severity_router import (
    FixAction,
    SeverityLevel,
    SeverityRouter,
)
from scripts.collaboration.two_stage_review_gate import (
    ReviewFinding,
    ReviewStage,
    StageResult,
    TwoStageReviewGate,
)

# ---------------------------------------------------------------------------
# Stub collaborators (isolate external dependencies: auto-fix callable,
# event bus, history storage). These honor the exact signatures the real
# modules call, so the integration logic is tested in isolation).
# ---------------------------------------------------------------------------


class _StubAutoFixCallable:
    """Stub for the auto_fix_callable parameter of SeverityRouter.

    Records every call and returns a configurable success value so
    tests can assert on the auto-fix loop's behavior without depending
    on a real code-rewriting backend.
    """

    def __init__(self, *, succeed: bool = True) -> None:
        self._succeed = succeed
        self.calls: list[tuple[FixAction, dict[str, Any]]] = []

    def __call__(self, action: FixAction, context: dict[str, Any]) -> bool:
        self.calls.append((action, context))
        return self._succeed


def _make_finding(
    stage: ReviewStage = ReviewStage.CODE_QUALITY,
    severity: str = "warning",
    category: str = "style",
    description: str = "Sample finding",
    file_path: str = "src/main.py",
    suggestion: str = "",
) -> ReviewFinding:
    """Build a ReviewFinding with sensible test defaults."""
    return ReviewFinding(
        stage=stage,
        severity=severity,
        category=category,
        description=description,
        file_path=file_path,
        suggestion=suggestion,
    )


def _make_spec(
    planned_files: list[str] | None = None,
    planned_functions: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    total_tasks: int | None = None,
    completed_tasks: int | None = None,
) -> dict[str, Any]:
    """Build a spec dict accepted by TwoStageReviewGate.review()."""
    spec: dict[str, Any] = {}
    if planned_files is not None:
        spec["planned_files"] = planned_files
    if planned_functions is not None:
        spec["planned_functions"] = planned_functions
    if acceptance_criteria is not None:
        spec["acceptance_criteria"] = acceptance_criteria
    if total_tasks is not None:
        spec["total_tasks"] = total_tasks
    if completed_tasks is not None:
        spec["completed_tasks"] = completed_tasks
    return spec


def _make_code_changes(files: dict[str, str]) -> dict[str, Any]:
    """Build a code_changes dict accepted by TwoStageReviewGate.review()."""
    return {
        "files": {path: {"content": content} for path, content in files.items()},
    }


def _make_gate(
    *,
    enable_two_stage_review: bool = True,
    strict_mode: bool = True,
    enable_redesign_audit: bool = False,
) -> TwoStageReviewGate:
    """Build a TwoStageReviewGate with Stage 3 disabled by default.

    Stage 3 (redesign audit) is disabled so T1 tests can focus on the
    spec-compliance → code-quality two-stage flow without the redesign
    auditor's heuristic noise.
    """
    return TwoStageReviewGate(
        enable_two_stage_review=enable_two_stage_review,
        strict_mode=strict_mode,
        enable_redesign_audit=enable_redesign_audit,
    )


# ---------------------------------------------------------------------------
# T1: TwoStageReviewGate basic two-stage flow (spec → quality)
# ---------------------------------------------------------------------------


class T1_TwoStageReviewGateBasics(unittest.TestCase):
    """T1: TwoStageReviewGate spec-compliance → code-quality flow."""

    def test_01_clean_code_passes_both_stages(self) -> None:
        """Verify: code matching the spec with tests passes all stages."""
        gate = _make_gate()
        spec = _make_spec(planned_files=["src/main.py"], planned_functions=["main"])
        code = _make_code_changes({
            "src/main.py": "def main():\n    return None\n",
            "tests/test_main.py": "def test_main():\n    assert main() is None\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertTrue(result.overall_passed)
        self.assertEqual(result.stage1_result, StageResult.PASS)
        self.assertEqual(result.stage2_result, StageResult.PASS)
        self.assertEqual(len(result.blocking_findings), 0)

    def test_02_critical_security_finding_blocks_stage2(self) -> None:
        """Verify: a SQL injection pattern produces a critical Stage 2 FAIL."""
        gate = _make_gate()
        spec = _make_spec(planned_files=["src/db.py"], planned_functions=["query"])
        code = _make_code_changes({
            "src/db.py": (
                "def query(user_input):\n"
                "    cursor.execute(f\"SELECT * FROM users WHERE id={user_input}\")\n"
            ),
            "tests/test_db.py": "def test_query():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertFalse(result.overall_passed)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertTrue(any(f.is_critical() for f in result.blocking_findings))

    def test_03_no_findings_yields_pass_summary(self) -> None:
        """Verify: an empty finding set produces a PASS summary string."""
        gate = _make_gate()
        spec = _make_spec(planned_files=["src/x.py"], planned_functions=["x"])
        code = _make_code_changes({
            "src/x.py": "def x():\n    pass\n",
            "tests/test_x.py": "def test_x():\n    assert x() is None\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertIn("PASSED", result.summary)
        self.assertEqual(len(result.findings), 0)

    def test_04_spec_pass_but_quality_warn(self) -> None:
        """Verify: spec compliance passes while code quality emits warnings.

        A bare ``except:`` clause is a warning (not critical), so Stage 1
        passes and Stage 2 returns WARN — the overall result still passes.
        """
        gate = _make_gate()
        spec = _make_spec(planned_files=["src/h.py"], planned_functions=["handle"])
        code = _make_code_changes({
            "src/h.py": (
                "def handle():\n"
                "    try:\n"
                "        do_thing()\n"
                "    except:\n"
                "        pass\n"
            ),
            "tests/test_h.py": "def test_handle():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertEqual(result.stage1_result, StageResult.PASS)
        self.assertEqual(result.stage2_result, StageResult.WARN)
        self.assertTrue(result.overall_passed)
        self.assertTrue(any(f.severity == "warning" for f in result.findings))

    def test_05_missing_planned_file_blocks_stage1(self) -> None:
        """Verify: a missing planned file yields a critical Stage 1 finding."""
        gate = _make_gate(strict_mode=True)
        spec = _make_spec(planned_files=["src/missing.py", "src/present.py"])
        code = _make_code_changes({"src/present.py": "# present\n"})
        result = gate.review(spec=spec, code_changes=code)
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        self.assertFalse(result.overall_passed)
        missing = [f for f in result.blocking_findings if "missing.py" in f.description]
        self.assertEqual(len(missing), 1)

    def test_06_missing_planned_function_blocks_stage1(self) -> None:
        """Verify: a missing planned function yields a critical Stage 1 finding."""
        gate = _make_gate(strict_mode=True)
        spec = _make_spec(planned_files=["src/svc.py"], planned_functions=["login"])
        code = _make_code_changes({
            "src/svc.py": "def logout():\n    pass\n",
            "tests/test_svc.py": "def test_logout():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        fn_findings = [f for f in result.findings if f.category == "missing_function"]
        self.assertEqual(len(fn_findings), 1)

    def test_07_multi_file_review_aggregates_findings(self) -> None:
        """Verify: findings from multiple files are aggregated into one result."""
        gate = _make_gate()
        spec = _make_spec(
            planned_files=["src/a.py", "src/b.py"],
            planned_functions=["a_func", "b_func"],
        )
        code = _make_code_changes({
            "src/a.py": "def a_func():\n    pass\n",
            "src/b.py": "def b_func():\n    pass\n",
            "tests/test_a.py": "def test_a():\n    assert True\n",
            "tests/test_b.py": "def test_b():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertTrue(result.overall_passed)
        self.assertEqual(result.stage1_result, StageResult.PASS)

    def test_08_eval_usage_is_critical_and_blocks(self) -> None:
        """Verify: ``eval()`` usage is flagged critical and blocks Stage 2."""
        gate = _make_gate()
        spec = _make_spec(planned_files=["src/calc.py"], planned_functions=["compute"])
        code = _make_code_changes({
            "src/calc.py": "def compute(expr):\n    return eval(expr)\n",
            "tests/test_calc.py": "def test_compute():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        eval_findings = [f for f in result.findings if "eval" in f.category]
        self.assertEqual(len(eval_findings), 1)
        self.assertTrue(eval_findings[0].is_critical())

    def test_09_incomplete_plan_blocks_stage1(self) -> None:
        """Verify: incomplete plan (completed < total) blocks Stage 1."""
        gate = _make_gate(strict_mode=True)
        spec = _make_spec(
            planned_files=["src/t.py"],
            planned_functions=["t"],
            total_tasks=5,
            completed_tasks=3,
        )
        code = _make_code_changes({
            "src/t.py": "def t():\n    pass\n",
            "tests/test_t.py": "def test_t():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        incomplete = [f for f in result.findings if f.category == "incomplete_plan"]
        self.assertEqual(len(incomplete), 1)

    def test_10_format_report_produces_markdown(self) -> None:
        """Verify: format_report renders a Markdown document for any result."""
        gate = _make_gate()
        spec = _make_spec(planned_files=["src/r.py"], planned_functions=["r"])
        code = _make_code_changes({
            "src/r.py": "def r():\n    pass\n",
            "tests/test_r.py": "def test_r():\n    assert True\n",
        })
        result = gate.review(spec=spec, code_changes=code)
        report = gate.format_report(result)
        self.assertIn("# Two-Stage Code Review Report", report)
        self.assertIn("Stage 1: Spec Compliance", report)
        self.assertIn("Stage 2: Code Quality", report)


# ---------------------------------------------------------------------------
# T2: SeverityRouter severity routing + auto-fix loop
# ---------------------------------------------------------------------------


class T2_SeverityRouterRouting(unittest.TestCase):
    """T2: SeverityRouter classification, routing, and auto-fix loop."""

    def test_01_critical_finding_blocks_router(self) -> None:
        """Verify: a critical finding sets blocked=True on the RoutingResult."""
        router = SeverityRouter(development_mode=True)
        findings = [_make_finding(severity="critical", description="SQL injection")]
        result = router.route(findings, context={})
        self.assertTrue(result.blocked)
        self.assertEqual(result.actions[0].severity, SeverityLevel.CRITICAL)

    def test_02_warning_finding_classified_as_high(self) -> None:
        """Verify: a warning-severity finding is classified HIGH by the router."""
        router = SeverityRouter(development_mode=True)
        findings = [_make_finding(severity="warning", description="Long line")]
        result = router.route(findings, context={})
        self.assertFalse(result.blocked)
        self.assertEqual(result.actions[0].severity, SeverityLevel.HIGH)

    def test_03_info_finding_classified_as_info(self) -> None:
        """Verify: an info-severity finding is classified INFO (non-blocking)."""
        router = SeverityRouter(development_mode=True)
        findings = [_make_finding(severity="info", description="FYI note")]
        result = router.route(findings, context={})
        self.assertFalse(result.blocked)
        self.assertEqual(result.actions[0].severity, SeverityLevel.INFO)

    def test_04_mixed_severity_findings_route_correctly(self) -> None:
        """Verify: a mix of critical/warning/info findings routes each correctly."""
        router = SeverityRouter(development_mode=True)
        findings = [
            _make_finding(severity="critical", description="Blocker"),
            _make_finding(severity="warning", description="Warning"),
            _make_finding(severity="info", description="Info"),
        ]
        result = router.route(findings, context={})
        self.assertTrue(result.blocked)
        self.assertEqual(len(result.actions), 3)
        severities = {a.severity for a in result.actions}
        self.assertEqual(severities, {
            SeverityLevel.CRITICAL, SeverityLevel.HIGH, SeverityLevel.INFO,
        })

    def test_05_bare_except_triggers_auto_fix_in_dev_mode(self) -> None:
        """Verify: a HIGH+auto_fixable bare_except finding triggers auto-fix."""
        fixer = _StubAutoFixCallable(succeed=True)
        router = SeverityRouter(
            development_mode=True,
            auto_fix_callable=fixer,
        )
        findings = [_make_finding(
            severity="warning", category="bare_except",
            description="Bare except clause detected",
        )]
        result = router.route(findings, context={"task": "fix"})
        self.assertTrue(result.auto_fix_triggered)
        self.assertEqual(len(fixer.calls), 1)
        self.assertTrue(fixer.calls[0][0].fix_applied)

    def test_06_auto_fix_loop_respects_max_rounds(self) -> None:
        """Verify: the fix loop stops after max_rounds iterations."""
        fixer = _StubAutoFixCallable(succeed=False)
        router = SeverityRouter(
            development_mode=True,
            max_rounds=2,
            auto_fix_callable=fixer,
        )
        findings = [_make_finding(
            severity="warning", category="bare_except",
            description="Bare except in handler",
        )]
        result = router.run_fix_loop(findings, context={})
        self.assertLessEqual(result.fix_round, router.max_rounds)
        self.assertFalse(result.all_fixed)

    def test_07_auto_fix_success_marks_action_fixed(self) -> None:
        """Verify: a successful auto-fix marks the action fix_applied+verified."""
        fixer = _StubAutoFixCallable(succeed=True)
        router = SeverityRouter(
            development_mode=True,
            max_rounds=3,
            auto_fix_callable=fixer,
        )
        findings = [_make_finding(
            severity="warning", category="bare_except",
            description="Bare except in main",
        )]
        result = router.run_fix_loop(findings, context={})
        self.assertTrue(result.actions[0].fix_applied)
        self.assertTrue(result.actions[0].fix_verified)
        self.assertEqual(result.status, "success")

    def test_08_production_mode_skips_auto_fix(self) -> None:
        """Verify: in production mode (development_mode=False) no auto-fix runs."""
        fixer = _StubAutoFixCallable(succeed=True)
        router = SeverityRouter(
            development_mode=False,
            auto_fix_callable=fixer,
        )
        findings = [_make_finding(
            severity="warning", category="bare_except",
            description="Bare except in prod",
        )]
        result = router.run_fix_loop(findings, context={})
        self.assertFalse(result.auto_fix_triggered)
        self.assertEqual(len(fixer.calls), 0)
        self.assertIn("production mode", result.summary)

    def test_09_collect_findings_from_worker_results(self) -> None:
        """Verify: collect_findings extracts FixActions from worker output dicts."""
        router = SeverityRouter(development_mode=True)
        worker_results = [
            {
                "role_id": "security",
                "findings": [
                    {"severity": "critical", "description": "SQL injection",
                     "file_path": "db.py"},
                    {"severity": "warning", "description": "Long line"},
                ],
            },
        ]
        findings = router.collect_findings(worker_results)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].severity, SeverityLevel.CRITICAL)
        self.assertEqual(findings[1].severity, SeverityLevel.HIGH)

    def test_10_event_bus_subscription_collects_findings(self) -> None:
        """Verify: a subscribed router collects findings emitted on the bus."""
        router = SeverityRouter(development_mode=True)
        router.subscribe()
        try:
            router.event_bus.emit(
                "review.finding",
                severity="critical",
                description="Bus-reported critical",
                file_path="src/x.py",
            )
            collected = router.get_collected_findings()
            self.assertEqual(len(collected), 1)
            self.assertEqual(collected[0].severity, SeverityLevel.CRITICAL)
        finally:
            router.unsubscribe()
            router.clear()


# ---------------------------------------------------------------------------
# T3: JudgeAgent arbitration (dedup / conflict / confidence / history)
# ---------------------------------------------------------------------------


class T3_JudgeAgentArbitration(unittest.TestCase):
    """T3: JudgeAgent deduplication, conflict resolution, and filtering."""

    def test_01_exact_duplicates_same_position_merged(self) -> None:
        """Verify: two findings with identical description+severity are merged."""
        judge = JudgeAgent(confidence_threshold=0.1, similarity_threshold=0.85)
        findings = [
            _make_finding(severity="warning", category="style",
                          description="Line too long at src/main.py:10",
                          file_path="src/main.py"),
            _make_finding(severity="warning", category="style",
                          description="Line too long at src/main.py:10",
                          file_path="src/main.py"),
        ]
        result = judge.judge(findings, context={})
        self.assertGreaterEqual(result.merged_count, 1)
        self.assertLessEqual(len(result.accepted_findings), 1)

    def test_02_conflict_resolution_upgrades_severity(self) -> None:
        """Verify: same issue with conflicting severity is upgraded to critical."""
        judge = JudgeAgent(confidence_threshold=0.1, similarity_threshold=0.80)
        findings = [
            _make_finding(severity="warning", category="security",
                          description="SQL injection in login function"),
            _make_finding(severity="critical", category="security",
                          description="SQL injection in login function"),
        ]
        result = judge.judge(findings, context={})
        upgrade_decisions = [
            d for d in result.decisions if d.action == JudgeAction.UPGRADE
        ]
        self.assertGreaterEqual(len(upgrade_decisions), 1)
        accepted = result.accepted_findings
        self.assertTrue(all(f.severity == "critical" for f in accepted))

    def test_03_low_confidence_findings_rejected(self) -> None:
        """Verify: findings below the confidence threshold are rejected.

        A warning finding with no suggestion and no file_path has
        heuristic confidence 0.5, below the default 0.7 threshold.
        """
        judge = JudgeAgent(confidence_threshold=0.7)
        findings = [
            ReviewFinding(
                stage=ReviewStage.CODE_QUALITY,
                severity="warning",
                category="misc",
                description="Vague issue",
                file_path="",
                suggestion="",
            ),
        ]
        result = judge.judge(findings, context={})
        self.assertEqual(len(result.accepted_findings), 0)
        self.assertGreaterEqual(result.rejected_count, 1)

    def test_04_critical_findings_always_high_confidence(self) -> None:
        """Verify: critical findings are always kept (confidence 1.0)."""
        judge = JudgeAgent(confidence_threshold=0.9)
        findings = [
            _make_finding(severity="critical", category="security",
                          description="SQL injection"),
        ]
        result = judge.judge(findings, context={})
        self.assertEqual(len(result.accepted_findings), 1)
        self.assertEqual(result.rejected_count, 0)

    def test_05_history_learning_defers_similar_rejected(self) -> None:
        """Verify: a finding similar to a past REJECT is deferred to human."""
        judge = JudgeAgent(
            confidence_threshold=0.1,
            similarity_threshold=0.70,
            enable_history=True,
        )
        judge._history.append(HistoryRecord(
            finding_text="SQL injection in login function",
            category="security",
            severity="critical",
            action=JudgeAction.REJECT.value,
        ))
        findings = [_make_finding(
            severity="critical", category="security",
            description="SQL injection in login function",
        )]
        result = judge.judge(findings, context={})
        self.assertTrue(result.history_used)
        defer_decisions = [
            d for d in result.decisions if d.action == JudgeAction.DEFER
        ]
        self.assertGreaterEqual(len(defer_decisions), 1)

    def test_06_empty_input_returns_empty_result(self) -> None:
        """Verify: judge with no findings returns an empty JudgeResult."""
        judge = JudgeAgent()
        result = judge.judge([], context={})
        self.assertEqual(len(result.accepted_findings), 0)
        self.assertEqual(len(result.decisions), 0)
        self.assertIn("no findings", result.summary)

    def test_07_all_low_confidence_all_rejected(self) -> None:
        """Verify: when every finding is low-confidence, all are rejected."""
        judge = JudgeAgent(confidence_threshold=0.9)
        findings = [
            ReviewFinding(
                stage=ReviewStage.CODE_QUALITY, severity="warning",
                category="misc", description="Vague issue A",
                file_path="", suggestion="",
            ),
            ReviewFinding(
                stage=ReviewStage.CODE_QUALITY, severity="warning",
                category="misc", description="Vague issue B",
                file_path="", suggestion="",
            ),
        ]
        result = judge.judge(findings, context={})
        self.assertEqual(len(result.accepted_findings), 0)
        self.assertGreaterEqual(result.rejected_count, 2)

    def test_08_unique_findings_all_accepted(self) -> None:
        """Verify: genuinely different findings are all accepted."""
        judge = JudgeAgent(confidence_threshold=0.5)
        findings = [
            _make_finding(severity="critical", category="security",
                          description="SQL injection in db.py",
                          file_path="db.py"),
            _make_finding(severity="warning", category="style",
                          description="Function too complex",
                          file_path="svc.py", suggestion="Refactor"),
        ]
        result = judge.judge(findings, context={})
        self.assertEqual(len(result.accepted_findings), 2)

    def test_09_record_decision_persists_to_disk(self) -> None:
        """Verify: record_decision writes a HistoryRecord to the JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            judge = JudgeAgent(enable_history=False)
            judge.enable_history_learning(path)
            decision = JudgeDecision(
                action=JudgeAction.ACCEPT,
                finding_ids=["fid-1"],
                rationale="Accepted critical finding",
                confidence=0.95,
                merged_finding=_make_finding(
                    severity="critical", description="SQL injection",
                ),
            )
            judge.record_decision(decision, human_override=False)
            stats = judge.get_history_stats()
            self.assertEqual(stats["total"], 1)
            self.assertIn("accept", stats["by_action"])
            self.assertTrue(os.path.exists(path))

    def test_10_mixed_decisions_produce_correct_counts(self) -> None:
        """Verify: a mix of accept/reject/merge produces correct counts."""
        judge = JudgeAgent(confidence_threshold=0.5, similarity_threshold=0.85)
        findings = [
            _make_finding(severity="critical", category="security",
                          description="SQL injection in login", file_path="a.py"),
            _make_finding(severity="critical", category="security",
                          description="SQL injection in login", file_path="a.py"),
            _make_finding(severity="warning", category="style",
                          description="Long line", file_path="b.py",
                          suggestion="Split"),
        ]
        result = judge.judge(findings, context={})
        self.assertGreaterEqual(result.merged_count, 1)
        self.assertGreaterEqual(result.rejected_count, 1)
        self.assertGreaterEqual(len(result.accepted_findings), 1)


# ---------------------------------------------------------------------------
# T4: Three-module end-to-end pipeline integration
# ---------------------------------------------------------------------------


class T4_ThreeModuleEndToEnd(unittest.TestCase):
    """T4: ReviewGate → SeverityRouter → JudgeAgent full chain."""

    def test_01_clean_code_passes_full_pipeline(self) -> None:
        """Verify: clean code passes gate, router, and judge with no blockers."""
        gate = _make_gate()
        router = SeverityRouter(development_mode=True)
        judge = JudgeAgent()
        spec = _make_spec(planned_files=["src/main.py"], planned_functions=["main"])
        code = _make_code_changes({
            "src/main.py": "def main():\n    return None\n",
            "tests/test_main.py": "def test_main():\n    assert main() is None\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.route(gate_result.findings, context={})
        judge_result = judge.judge(gate_result.findings, context={})
        self.assertTrue(gate_result.overall_passed)
        self.assertFalse(router_result.blocked)
        self.assertEqual(len(judge_result.accepted_findings),
                         len(gate_result.findings))

    def test_02_critical_finding_blocks_at_router(self) -> None:
        """Verify: a critical finding from the gate blocks at the router.

        Critical findings always block — the auto-fix loop does not run
        for CRITICAL severity (manual escalation required).
        """
        gate = _make_gate()
        router = SeverityRouter(development_mode=True)
        spec = _make_spec(planned_files=["src/db.py"], planned_functions=["query"])
        code = _make_code_changes({
            "src/db.py": (
                "def query(uid):\n"
                "    cursor.execute(f\"SELECT * FROM t WHERE id={uid}\")\n"
            ),
            "tests/test_db.py": "def test_query():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.route(gate_result.findings, context={})
        self.assertFalse(gate_result.overall_passed)
        self.assertTrue(router_result.blocked)
        self.assertEqual(router_result.status, "failed")

    def test_03_auto_fixable_finding_resolved_by_loop(self) -> None:
        """Verify: a HIGH+auto_fixable finding is resolved by the fix loop.

        A bare ``except:`` produces a HIGH-severity auto-fixable action.
        With a succeeding auto_fix_callable, run_fix_loop resolves it.
        """
        gate = _make_gate()
        fixer = _StubAutoFixCallable(succeed=True)
        router = SeverityRouter(
            development_mode=True,
            max_rounds=3,
            auto_fix_callable=fixer,
        )
        spec = _make_spec(planned_files=["src/h.py"], planned_functions=["handle"])
        code = _make_code_changes({
            "src/h.py": (
                "def handle():\n"
                "    try:\n"
                "        do_thing()\n"
                "    except:\n"
                "        pass\n"
            ),
            "tests/test_h.py": "def test_handle():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.run_fix_loop(gate_result.findings, context={})
        self.assertTrue(router_result.auto_fix_triggered)
        self.assertEqual(router_result.status, "success")

    def test_04_auto_fix_failure_exhausts_rounds(self) -> None:
        """Verify: a failing auto-fix exhausts rounds without resolving."""
        gate = _make_gate()
        fixer = _StubAutoFixCallable(succeed=False)
        router = SeverityRouter(
            development_mode=True,
            max_rounds=2,
            auto_fix_callable=fixer,
        )
        spec = _make_spec(planned_files=["src/h.py"], planned_functions=["handle"])
        code = _make_code_changes({
            "src/h.py": (
                "def handle():\n"
                "    try:\n"
                "        do_thing()\n"
                "    except:\n"
                "        pass\n"
            ),
            "tests/test_h.py": "def test_handle():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.run_fix_loop(gate_result.findings, context={})
        self.assertFalse(router_result.all_fixed)
        self.assertGreaterEqual(router_result.fix_round, 1)

    def test_05_judge_deduplicates_gate_findings(self) -> None:
        """Verify: the judge deduplicates near-identical findings from the gate."""
        gate = _make_gate()
        judge = JudgeAgent(confidence_threshold=0.1, similarity_threshold=0.80)
        spec = _make_spec(
            planned_files=["src/a.py", "src/b.py"],
            planned_functions=["a", "b"],
        )
        code = _make_code_changes({
            "src/a.py": "def a():\n    pass\n",
            "src/b.py": "def b():\n    pass\n",
            "tests/test_a.py": "def test_a():\n    assert True\n",
            "tests/test_b.py": "def test_b():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        judge_result = judge.judge(gate_result.findings, context={})
        self.assertLessEqual(
            len(judge_result.accepted_findings), len(gate_result.findings)
        )

    def test_06_full_pipeline_preserves_finding_metadata(self) -> None:
        """Verify: finding category/severity survive the full pipeline."""
        gate = _make_gate()
        router = SeverityRouter(development_mode=True)
        judge = JudgeAgent(confidence_threshold=0.1)
        spec = _make_spec(planned_files=["src/db.py"], planned_functions=["query"])
        code = _make_code_changes({
            "src/db.py": (
                "def query(uid):\n"
                "    cursor.execute(f\"SELECT * FROM t WHERE id={uid}\")\n"
            ),
            "tests/test_db.py": "def test_query():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.route(gate_result.findings, context={})
        judge_result = judge.judge(gate_result.findings, context={})
        critical_actions = [
            a for a in router_result.actions
            if a.severity == SeverityLevel.CRITICAL
        ]
        self.assertGreater(len(critical_actions), 0)
        accepted_critical = [
            f for f in judge_result.accepted_findings if f.is_critical()
        ]
        self.assertGreater(len(accepted_critical), 0)

    def test_07_router_actions_match_gate_findings_count(self) -> None:
        """Verify: the router produces one action per gate finding."""
        gate = _make_gate()
        router = SeverityRouter(development_mode=True)
        spec = _make_spec(
            planned_files=["src/a.py", "src/b.py"],
            planned_functions=["a", "b"],
        )
        code = _make_code_changes({
            "src/a.py": "def a():\n    pass\n",
            "src/b.py": "def b():\n    pass\n",
            "tests/test_a.py": "def test_a():\n    assert True\n",
            "tests/test_b.py": "def test_b():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.route(gate_result.findings, context={})
        self.assertEqual(len(router_result.actions), len(gate_result.findings))

    def test_08_judge_summary_reflects_pipeline_state(self) -> None:
        """Verify: the judge summary reports accepted/rejected/merged counts."""
        gate = _make_gate()
        judge = JudgeAgent(confidence_threshold=0.1, similarity_threshold=0.80)
        spec = _make_spec(planned_files=["src/db.py"], planned_functions=["query"])
        code = _make_code_changes({
            "src/db.py": (
                "def query(uid):\n"
                "    cursor.execute(f\"SELECT * FROM t WHERE id={uid}\")\n"
            ),
            "tests/test_db.py": "def test_query():\n    assert True\n",
        })
        gate_result = gate.review(spec=spec, code_changes=code)
        judge_result = judge.judge(gate_result.findings, context={})
        self.assertIn("accepted", judge_result.summary)
        self.assertIn("Rejected", judge_result.summary)

    def test_09_pipeline_with_history_learning_enabled(self) -> None:
        """Verify: the full pipeline works with judge history learning on."""
        gate = _make_gate()
        router = SeverityRouter(development_mode=True)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "judge_history.json")
            judge = JudgeAgent(
                confidence_threshold=0.1,
                similarity_threshold=0.80,
                enable_history=True,
            )
            judge.enable_history_learning(path)
            spec = _make_spec(
                planned_files=["src/main.py"], planned_functions=["main"],
            )
            code = _make_code_changes({
                "src/main.py": "def main():\n    return None\n",
                "tests/test_main.py": "def test_main():\n    assert True\n",
            })
            gate_result = gate.review(spec=spec, code_changes=code)
            router_result = router.route(gate_result.findings, context={})
            judge_result = judge.judge(gate_result.findings, context={})
            self.assertIsInstance(judge_result.history_used, bool)
            self.assertFalse(router_result.blocked)

    def test_10_gate_blocking_findings_become_router_critical(self) -> None:
        """Verify: gate blocking_findings map to CRITICAL actions in the router.

        The gate's blocking_findings are critical-severity; the router
        classifies them as SeverityLevel.CRITICAL and sets blocked=True.
        """
        gate = _make_gate()
        router = SeverityRouter(development_mode=True)
        spec = _make_spec(planned_files=["src/missing.py"])
        code = _make_code_changes({"src/other.py": "# not planned\n"})
        gate_result = gate.review(spec=spec, code_changes=code)
        router_result = router.route(gate_result.blocking_findings, context={})
        self.assertTrue(router_result.blocked)
        for action in router_result.actions:
            self.assertEqual(action.severity, SeverityLevel.CRITICAL)


if __name__ == "__main__":
    unittest.main()
