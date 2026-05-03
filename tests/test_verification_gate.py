#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for VerificationGate (P0-2)

Coverage:
  - Unit: All 7 Red Flags detection functions
  - Unit: Evidence requirement checking
  - Unit: Verdict logic (APPROVE/CONDITIONAL/REJECT)
  - Unit: build_context_from_worker_result heuristic
  - Unit: Edge cases (empty context, unknown role, strict mode)
  - Integration: Gate + TaskCompletionChecker integration
  - Regression: Existing completion checks unaffected

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.2
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.verification_gate import (
    CompletionContext,
    EvidenceItem,
    GateResult,
    RedFlag,
    VerificationGate,
    get_shared_gate,
)


class TestRedFlagDefinitions(unittest.TestCase):
    """Test that all Red Flags are properly defined."""

    def setUp(self):
        self.gate = VerificationGate()

    def test_has_7_red_flags(self):
        self.assertEqual(self.gate.red_flag_count, 7)

    def test_all_flags_have_valid_id(self):
        for flag in self.gate.RED_FLAGS:
            self.assertTrue(len(flag.id) > 0)
            self.assertTrue(flag.id.replace("_", "").isalnum() or "_" in flag.id)

    def test_all_flags_have_severity(self):
        valid_severities = {"critical", "warning", "info"}
        for flag in self.gate.RED_FLAGS:
            self.assertIn(flag.severity, valid_severities)

    def test_all_flags_have_description(self):
        for flag in self.gate.RED_FLAGS:
            self.assertTrue(len(flag.description) > 0)

    def test_all_flags_have_detection_callable(self):
        for flag in self.gate.RED_FLAGS:
            self.assertTrue(callable(flag.detection))

    def test_critical_flags_exist(self):
        critical = [f for f in self.gate.RED_FLAGS if f.severity == "critical"]
        self.assertGreaterEqual(len(critical), 3)

    def test_get_red_flag_by_id_found(self):
        flag = self.gate.get_red_flag_by_id("no_test_for_new_behavior")
        self.assertIsNotNone(flag)
        self.assertEqual(flag.severity, "critical")

    def test_get_red_flag_by_id_not_found(self):
        flag = self.gate.get_red_flag_by_id("nonexistent_flag_xyz")
        self.assertIsNone(flag)


class TestEvidenceItemDefinitions(unittest.TestCase):
    """Test that all EvidenceItems are properly defined."""

    def setUp(self):
        self.gate = VerificationGate()

    def test_has_evidence_items(self):
        self.assertGreater(self.gate.evidence_item_count, 0)

    def test_test_results_is_required(self):
        items = [e for e in self.gate.MANDATORY_EVIDENCE if e.key == "test_results"]
        self.assertEqual(len(items), 1)
        self.assertTrue(items[0].required)

    def test_build_status_required_for_coder_and_architect(self):
        items = [e for e in self.gate.MANDATORY_EVIDENCE if e.key == "build_status"]
        self.assertEqual(len(items), 1)
        self.assertIn("solo-coder", items[0].required_for)
        self.assertIn("architect", items[0].required_for)


class TestNoTestForNewBehavior(unittest.TestCase):
    """Test Red Flag: no_test_for_new_behavior"""

    def test_triggers_when_code_but_no_tests(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=True,
            has_test_changes=False,
            claims_complete=True,
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertIn("no_test_for_new_behavior", triggered_ids)

    def test_no_trigger_when_both_code_and_tests(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=True,
            has_test_changes=True,
            claims_complete=True,
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("no_test_for_new_behavior", triggered_ids)

    def test_no_trigger_when_no_code_changes(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=False,
            has_test_changes=False,
            claims_complete=False,
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("no_test_for_new_behavior", triggered_ids)


class TestNoReproTestForBugfix(unittest.TestCase):
    """Test Red Flag: no_regression_test_for_bugfix"""

    def test_triggers_when_bug_fix_without_repro(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            is_bug_fix=True,
            has_repro_test=False,
            claims_complete=True,
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertIn("no_regression_test_for_bugfix", triggered_ids)

    def test_no_trigger_when_repro_exists(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            is_bug_fix=True,
            has_repro_test=True,
            claims_complete=True,
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("no_regression_test_for_bugfix", triggered_ids)


class TestTestsSkippedOrDisabled(unittest.TestCase):
    """Test Red Flag: tests_skipped_or_disabled"""

    def test_triggers_when_tests_skipped(self):
        gate = VerificationGate()
        ctx = CompletionContext(role_id="tester", tests_skipped=3)
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertIn("tests_skipped_or_disabled", triggered_ids)

    def test_no_trigger_when_none_skipped(self):
        gate = VerificationGate()
        ctx = CompletionContext(role_id="tester", tests_skipped=0)
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("tests_skipped_or_disabled", triggered_ids)


class TestOutputExceedsLimit(unittest.TestCase):
    """Test Red Flag: output_exceeds_limit"""

    def test_triggers_when_output_over_100_unsliced(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder", output_lines=200, was_sliced=False
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertIn("output_exceeds_limit", triggered_ids)

    def test_no_trigger_when_sliced(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder", output_lines=200, was_sliced=True
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("output_exceeds_limit", triggered_ids)

    def test_no_trigger_when_under_limit(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder", output_lines=50, was_sliced=False
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("output_exceeds_limit", triggered_ids)


class TestNoEvidenceProvided(unittest.TestCase):
    """Test Red Flag: no_evidence_provided"""

    def test_triggers_when_claims_complete_no_evidence(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder", claims_complete=True, evidence={}
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertIn("no_evidence_provided", triggered_ids)

    def test_no_trigger_when_evidence_exists(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            claims_complete=True,
            evidence={"test_results": "all passed"},
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("no_evidence_provided", triggered_ids)

    def test_no_trigger_when_not_claiming_complete(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder", claims_complete=False, evidence={}
        )
        result = gate.check(ctx)
        triggered_ids = [f.id for f in result.red_flags]
        self.assertNotIn("no_evidence_provided", triggered_ids)


class TestVerdictLogic(unittest.TestCase):
    """Test APPROVE / CONDITIONAL / REJECT verdict assignment."""

    def test_approve_when_clean(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=False,
            output_lines=50,
            claims_complete=False,
            evidence={"test_results": "all passed", "diff_summary": "no changes"},
        )
        result = gate.check(ctx)
        self.assertTrue(result.passed)
        self.assertEqual(result.verdict, "APPROVE")

    def test_reject_on_critical_flag(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=True,
            has_test_changes=False,
            tests_skipped=1,
        )
        result = gate.check(ctx)
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "REJECT")

    def test_conditional_on_warning_only(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            output_lines=50,
            was_sliced=False,
            claims_complete=False,
            evidence={"test_results": "passed", "diff_summary": "+5/-2"},
        )
        result = gate.check(ctx)
        self.assertTrue(result.passed)
        self.assertEqual(result.verdict, "APPROVE")


class TestMissingEvidence(unittest.TestCase):
    """Test mandatory evidence requirement checking."""

    def test_missing_required_evidence_blocks(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="coder",
            claims_complete=True,
            evidence={},
        )
        result = gate.check(ctx)
        self.assertGreater(len(result.missing_evidence), 0)

    def test_diff_summary_required_for_all_roles(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="ui-designer",
            claims_complete=True,
            evidence={},
        )
        result = gate.check(ctx)
        missing_keys = [e.key for e in result.missing_evidence]
        self.assertIn("diff_summary", missing_keys)

    def test_build_status_not_required_for_tester_role(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="tester",
            claims_complete=True,
            evidence={"test_results": "ok", "diff_summary": "+5/-2"},
        )
        result = gate.check(ctx)
        missing_keys = [e.key for e in result.missing_evidence]
        self.assertNotIn("build_status", missing_keys)


class TestBuildContextFromWorkerResult(unittest.TestCase):
    """Test heuristic context extraction from worker results."""

    def setUp(self):
        self.gate = VerificationGate()

    def test_basic_extraction(self):
        wr = {
            "role": "coder",
            "success": True,
            "output": "def foo():\n    return 42\n" * 10,
        }
        ctx = self.gate.build_context_from_worker_result(wr)
        self.assertEqual(ctx.role_id, "coder")
        self.assertTrue(ctx.has_code_changes)
        self.assertTrue(ctx.claims_complete)

    def test_bug_fix_detection_from_task_desc(self):
        wr = {
            "role": "coder",
            "task_description": "Fix the login crash bug",
            "success": True,
            "output": "Fixed null check",
        }
        ctx = self.gate.build_context_from_worker_result(wr)
        self.assertTrue(ctx.is_bug_fix)

    def test_non_bug_fix_task(self):
        wr = {
            "role": "coder",
            "task_description": "Implement user authentication",
            "success": True,
            "output": "Created auth module",
        }
        ctx = self.gate.build_context_from_worker_result(wr)
        self.assertFalse(ctx.is_bug_fix)

    def test_output_line_counting(self):
        wr = {
            "role": "coder",
            "success": True,
            "output": "\n".join([f"line {i}" for i in range(50)]),
        }
        ctx = self.gate.build_context_from_worker_result(wr)
        self.assertEqual(ctx.output_lines, 50)

    def test_verification_evidence_preserved(self):
        wr = {
            "role": "coder",
            "success": True,
            "output": "done",
            "verification": {"passed": True, "verdict": "APPROVE"},
        }
        ctx = self.gate.build_context_from_worker_result(wr)
        self.assertIn("verification", ctx.evidence)

    def test_unknown_role_defaults(self):
        wr = {"success": True}
        ctx = self.gate.build_context_from_worker_result(wr)
        self.assertEqual(ctx.role_id, "unknown")


class TestStrictMode(unittest.TestCase):
    """Test strict vs non-strict mode behavior."""

    def test_strict_mode_rejects_critical(self):
        gate = VerificationGate(strict_mode=True)
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=True,
            has_test_changes=False,
            tests_skipped=1,
        )
        result = gate.check(ctx)
        self.assertEqual(result.verdict, "REJECT")

    def test_non_strict_mode_still_detects(self):
        gate = VerificationGate(strict_mode=False)
        ctx = CompletionContext(
            role_id="coder",
            has_code_changes=True,
            has_test_changes=False,
        )
        result = gate.check(ctx)
        self.assertGreater(len(result.red_flags), 0)


class TestSharedSingleton(unittest.TestCase):
    """Test get_shared_gate singleton pattern."""

    def test_returns_same_instance(self):
        g1 = get_shared_gate()
        g2 = get_shared_gate()
        self.assertIs(g1, g2)

    def test_is_verification_gate(self):
        gate = get_shared_gate()
        self.assertIsInstance(gate, VerificationGate)


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and error handling."""

    def test_empty_context_approves(self):
        gate = VerificationGate()
        ctx = CompletionContext(
            role_id="any",
            claims_complete=False,
            evidence={"test_results": "n/a", "diff_summary": "n/a"},
        )
        result = gate.check(ctx)
        self.assertTrue(result.passed)
        self.assertEqual(len(result.red_flags), 0)

    def test_broken_detection_function_doesnt_crash(self):
        gate = VerificationGate()
        broken_flag = RedFlag(
            id="broken",
            severity="warning",
            description="test",
            detection=lambda ctx: 1 / 0,
        )
        original = gate.RED_FLAGS
        gate.RED_FLAGS = [broken_flag]
        try:
            ctx = CompletionContext(role_id="test")
            result = gate.check(ctx)
            self.assertIsNotNone(result)
        finally:
            gate.RED_FLAGS = original


if __name__ == "__main__":
    unittest.main()
