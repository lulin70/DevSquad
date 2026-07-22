#!/usr/bin/env python3
"""
Tests for TwoStageReviewGate (V3.8 #2) — Two-Stage Code Review Gate.

Coverage:
  - ReviewStage / StageResult enums
  - ReviewFinding dataclass (is_critical, to_dict)
  - TwoStageReviewResult dataclass (overall_passed, blocking_findings, to_dict)
  - Stage 1: spec compliance (planned files, planned functions, plan completion, roles, criteria)
  - Stage 2: code quality (security, error handling, test coverage, anti-patterns, oversized)
  - Critical findings block progression (StageResult.FAIL)
  - Warnings produce StageResult.WARN (non-blocking)
  - Missing files / functions detection
  - Security issue detection (hardcoded secrets, SQL injection)
  - Bare except detection
  - Missing test detection
  - Report formatting (Markdown)
  - Integration with spec dict format
  - run_two_stage_review convenience function
  - enable_two_stage_review=False disables the gate
  - strict_mode downgrades
  - Legacy calling convention (plan/worker_results/spec_requirements)
"""

from __future__ import annotations

import os
import sys
import unittest
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.two_stage_review_gate import (
    ReviewFinding,
    ReviewIssue,
    ReviewStage,
    StageResult,
    TwoStageReviewGate,
    TwoStageReviewResult,
    run_two_stage_review,
)


@dataclass
class FakePlan:
    """Minimal plan object mimicking the real plan interface (legacy compat)."""

    total_tasks: int = 3
    completed_tasks: int = 3
    failed_tasks: int = 0


class TestReviewStageEnum(unittest.TestCase):
    """Verify ReviewStage enum values."""

    def test_review_stage_values(self) -> None:
        self.assertEqual(ReviewStage.SPEC_COMPLIANCE.value, "spec_compliance")
        self.assertEqual(ReviewStage.CODE_QUALITY.value, "code_quality")


class TestStageResultEnum(unittest.TestCase):
    """Verify StageResult enum values."""

    def test_stage_result_values(self) -> None:
        self.assertEqual(StageResult.PASS.value, "pass")
        self.assertEqual(StageResult.WARN.value, "warn")
        self.assertEqual(StageResult.FAIL.value, "fail")


class TestReviewFinding(unittest.TestCase):
    """Verify ReviewFinding dataclass."""

    def test_is_critical_true_for_critical(self) -> None:
        finding = ReviewFinding(ReviewStage.SPEC_COMPLIANCE, "critical", "cat", "desc")
        self.assertTrue(finding.is_critical())

    def test_is_critical_false_for_warning(self) -> None:
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "warning", "cat", "desc")
        self.assertFalse(finding.is_critical())
        self.assertTrue(finding.is_warning())

    def test_to_dict_round_trip(self) -> None:
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY,
            "warning",
            "cat",
            "desc",
            file_path="src/foo.py",
            line_range="10-20",
            suggestion="Fix it",
        )
        d = finding.to_dict()
        self.assertEqual(d["stage"], "code_quality")
        self.assertEqual(d["severity"], "warning")
        self.assertEqual(d["file_path"], "src/foo.py")
        self.assertEqual(d["line_range"], "10-20")
        self.assertEqual(d["suggestion"], "Fix it")

    def test_review_issue_is_alias_for_review_finding(self) -> None:
        # Backward-compatibility alias
        self.assertIs(ReviewIssue, ReviewFinding)


class TestTwoStageReviewResult(unittest.TestCase):
    """Verify TwoStageReviewResult dataclass."""

    def test_overall_passed_when_both_stages_pass(self) -> None:
        result = TwoStageReviewResult(
            stage1_result=StageResult.PASS,
            stage2_result=StageResult.PASS,
            overall_passed=True,
        )
        self.assertTrue(result.overall_passed)
        self.assertTrue(result.passed)  # backward-compat alias

    def test_not_passed_when_stage1_fails(self) -> None:
        result = TwoStageReviewResult(
            stage1_result=StageResult.FAIL,
            stage2_result=StageResult.PASS,
            overall_passed=False,
        )
        self.assertFalse(result.overall_passed)
        self.assertFalse(result.stage1_passed)
        self.assertTrue(result.stage2_passed)

    def test_not_passed_when_stage2_fails(self) -> None:
        result = TwoStageReviewResult(
            stage1_result=StageResult.PASS,
            stage2_result=StageResult.FAIL,
            overall_passed=False,
        )
        self.assertFalse(result.overall_passed)
        self.assertFalse(result.stage2_passed)

    def test_to_dict_includes_all_fields(self) -> None:
        finding = ReviewFinding(ReviewStage.SPEC_COMPLIANCE, "critical", "c", "d")
        result = TwoStageReviewResult(
            stage1_result=StageResult.FAIL,
            stage2_result=StageResult.PASS,
            findings=[finding],
            overall_passed=False,
            blocking_findings=[finding],
            summary="test",
        )
        d = result.to_dict()
        self.assertIn("overall_passed", d)
        self.assertIn("stage1_result", d)
        self.assertIn("stage2_result", d)
        self.assertIn("findings", d)
        self.assertIn("blocking_findings", d)
        self.assertIn("summary", d)
        self.assertEqual(d["stage1_result"], "fail")
        self.assertEqual(d["blocking_count"], 1)
        self.assertFalse(d["overall_passed"])


class TestTwoStageReviewGateDisabled(unittest.TestCase):
    """Verify the gate can be disabled."""

    def test_disabled_gate_returns_passing_result(self) -> None:
        gate = TwoStageReviewGate(enable_two_stage_review=False)
        result = gate.review(spec={}, code_changes={})
        self.assertTrue(result.overall_passed)
        self.assertEqual(result.blocking_findings, [])

    def test_disabled_gate_ignores_all_issues(self) -> None:
        gate = TwoStageReviewGate(enable_two_stage_review=False)
        result = gate.review(
            spec={"planned_files": ["missing.py"], "total_tasks": 5, "completed_tasks": 1},
            code_changes={},
        )
        self.assertTrue(result.overall_passed)


class TestStage1SpecCompliance(unittest.TestCase):
    """Verify Stage 1: spec compliance checks."""

    def setUp(self) -> None:
        self.gate = TwoStageReviewGate()

    def test_missing_planned_file_blocks(self) -> None:
        """Missing files detection — planned file not in code_changes."""
        spec = {"planned_files": ["src/auth.py", "src/utils.py"]}
        code_changes = {"files": {"src/auth.py": {"content": "code"}}}
        result = self.gate.review(spec=spec, code_changes=code_changes)
        self.assertFalse(result.overall_passed)
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        self.assertTrue(
            any(f.category == "missing_file" and f.file_path == "src/utils.py" for f in result.blocking_findings)
        )

    def test_all_planned_files_present_passes_stage1(self) -> None:
        spec = {"planned_files": ["src/auth.py"]}
        code_changes = {"files": {"src/auth.py": {"content": "code"}}}
        result = self.gate.review(spec=spec, code_changes=code_changes)
        self.assertEqual(result.stage1_result, StageResult.PASS)

    def test_missing_planned_function_blocks(self) -> None:
        """Missing functions detection — planned function not in code."""
        spec = {"planned_functions": ["login", "logout"]}
        code_changes = {"files": {"src/auth.py": {"content": "def login():\n    pass\n"}}}
        result = self.gate.review(spec=spec, code_changes=code_changes)
        self.assertFalse(result.overall_passed)
        self.assertTrue(
            any(f.category == "missing_function" and "logout" in f.description for f in result.blocking_findings)
        )

    def test_all_planned_functions_present_passes_stage1(self) -> None:
        spec = {"planned_functions": ["login", "logout"]}
        code_changes = {"files": {"src/auth.py": {"content": "def login():\n    pass\ndef logout():\n    pass\n"}}}
        result = self.gate.review(spec=spec, code_changes=code_changes)
        self.assertEqual(result.stage1_result, StageResult.PASS)

    def test_incomplete_plan_blocks(self) -> None:
        spec = {"total_tasks": 5, "completed_tasks": 3, "failed_tasks": 0}
        result = self.gate.review(spec=spec, code_changes={})
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "incomplete_plan" for f in result.blocking_findings))

    def test_failed_tasks_block(self) -> None:
        spec = {"total_tasks": 3, "completed_tasks": 3, "failed_tasks": 1}
        result = self.gate.review(spec=spec, code_changes={})
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "failed_tasks" for f in result.blocking_findings))

    def test_strict_mode_false_downgrades_missing_file(self) -> None:
        gate = TwoStageReviewGate(strict_mode=False)
        spec = {"planned_files": ["missing.py"]}
        result = gate.review(spec=spec, code_changes={})
        # In non-strict mode, missing_file is a warning, not blocking
        self.assertEqual(result.stage1_result, StageResult.WARN)
        self.assertTrue(any(f.category == "missing_file" for f in result.warnings))
        self.assertTrue(result.overall_passed)

    def test_acceptance_criteria_not_evident_is_warning(self) -> None:
        spec = {"acceptance_criteria": ["user authentication"]}
        code_changes = {"files": {"src/foo.py": {"content": "print('hello')"}}}
        result = self.gate.review(spec=spec, code_changes=code_changes)
        # acceptance_criteria_not_evident is a warning (heuristic)
        self.assertTrue(any(f.category == "acceptance_criteria_not_evident" for f in result.warnings))


class TestStage2CodeQuality(unittest.TestCase):
    """Verify Stage 2: code quality checks."""

    def setUp(self) -> None:
        self.gate = TwoStageReviewGate()

    def test_hardcoded_api_key_is_critical(self) -> None:
        """Security issue detection — hardcoded secrets."""
        content = 'api_key = "sk-1234567890abcdef1234567890abcdef"\n'
        code_changes = {"files": {"src/config.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "security_hardcoded_api_key" for f in result.blocking_findings))

    def test_hardcoded_password_is_critical(self) -> None:
        content = 'password = "supersecretpass"\n'
        code_changes = {"files": {"src/config.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "security_hardcoded_password" for f in result.blocking_findings))

    def test_sql_injection_format_is_critical(self) -> None:
        """Security issue detection — SQL injection patterns."""
        content = 'cursor.execute(f"SELECT * FROM users WHERE id = {user_id}")\n'
        code_changes = {"files": {"src/db.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "security_sql_injection_format" for f in result.blocking_findings))

    def test_bare_except_is_warning(self) -> None:
        """Bare except detection — warning, not critical."""
        content = "try:\n    pass\nexcept:\n    pass\n"  # noqa: test-quality — test fixture string, not real code
        code_changes = {"files": {"src/foo.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertTrue(any(f.category == "bare_except" for f in result.warnings))

    def test_eval_usage_is_critical(self) -> None:
        content = "result = eval(user_input)\n"
        code_changes = {"files": {"src/foo.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "anti_pattern_eval_usage" for f in result.blocking_findings))

    def test_exec_usage_is_critical(self) -> None:
        content = "exec(code_string)\n"
        code_changes = {"files": {"src/foo.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.FAIL)

    def test_missing_test_for_code_blocks(self) -> None:
        """Missing test detection — code without tests."""
        content = "def add(a, b):\n    return a + b\n"
        code_changes = {"files": {"src/math.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertTrue(any(f.category == "missing_test" for f in result.blocking_findings))

    def test_code_with_tests_passes_test_check(self) -> None:
        content = "def add(a, b):\n    return a + b\n"
        test_content = "from src.math import add\ndef test_add():\n    assert add(1,2) == 3\n"
        code_changes = {
            "files": {
                "src/math.py": {"content": content},
                "tests/test_math.py": {"content": test_content},
            }
        }
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertFalse(any(f.category == "missing_test" for f in result.blocking_findings))

    def test_todo_left_is_warning(self) -> None:
        content = "# TODO: implement this later\n"
        code_changes = {"files": {"src/foo.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertTrue(any(f.category == "anti_pattern_todo_left" for f in result.warnings))

    def test_oversized_output_is_warning(self) -> None:
        content = "\n".join(f"line {i}" for i in range(250))
        code_changes = {"files": {"src/big.py": {"content": content}}}
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertTrue(any(f.category == "oversized_output" for f in result.warnings))

    def test_clean_code_passes_stage2(self) -> None:
        content = '"""Module docstring."""\n\ndef add(a, b):\n    """Add two numbers."""\n    return a + b\n'
        test_content = "from src.math import add\ndef test_add():\n    assert add(1, 2) == 3\n"
        code_changes = {
            "files": {
                "src/math.py": {"content": content},
                "tests/test_math.py": {"content": test_content},
            }
        }
        result = self.gate.review(spec={}, code_changes=code_changes)
        self.assertEqual(result.stage2_result, StageResult.PASS)


class TestReportFormatting(unittest.TestCase):
    """Verify Markdown report formatting."""

    def test_format_report_includes_status_and_stages(self) -> None:
        gate = TwoStageReviewGate()
        finding = ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection")
        result = TwoStageReviewResult(
            stage1_result=StageResult.PASS,
            stage2_result=StageResult.FAIL,
            findings=[finding],
            overall_passed=False,
            blocking_findings=[finding],
            summary="test",
        )
        report = gate.format_report(result)
        self.assertIn("Two-Stage Code Review Report", report)
        self.assertIn("FAIL", report)
        self.assertIn("Stage 1: Spec Compliance", report)
        self.assertIn("Stage 2: Code Quality", report)
        self.assertIn("Blocking Findings", report)
        self.assertIn("SQL injection", report)

    def test_format_report_for_passing_result(self) -> None:
        gate = TwoStageReviewGate()
        result = TwoStageReviewResult(
            stage1_result=StageResult.PASS,
            stage2_result=StageResult.PASS,
            overall_passed=True,
            summary="all good",
        )
        report = gate.format_report(result)
        self.assertIn("PASS", report)
        self.assertNotIn("Blocking Findings", report)


class TestRunTwoStageReviewConvenience(unittest.TestCase):
    """Verify the run_two_stage_review convenience function."""

    def test_run_two_stage_review_returns_result(self) -> None:
        spec = {"planned_files": ["src/auth.py"]}
        code_changes = {"files": {"src/auth.py": {"content": "code"}}}
        result = run_two_stage_review(spec, code_changes)
        self.assertIsInstance(result, TwoStageReviewResult)
        self.assertTrue(result.overall_passed)

    def test_run_two_stage_review_with_blocking(self) -> None:
        spec = {"planned_files": ["src/missing.py"]}
        code_changes = {"files": {"src/other.py": {"content": "code"}}}
        result = run_two_stage_review(spec, code_changes)
        self.assertFalse(result.overall_passed)
        self.assertGreater(len(result.blocking_findings), 0)


class TestLegacyCallingConvention(unittest.TestCase):
    """Verify backward compatibility with the legacy calling convention."""

    def test_legacy_plan_worker_results_spec_requirements(self) -> None:
        """Integration with spec dict format — legacy convention."""
        gate = TwoStageReviewGate()
        plan = FakePlan(total_tasks=5, completed_tasks=3, failed_tasks=0)
        worker_results = [{"role_id": "solo-coder", "output": "def foo():\n    pass\n", "success": True}]
        result = gate.review(
            plan=plan,
            worker_results=worker_results,
            spec_requirements={"required_roles": ["tester"]},
        )
        # Stage 1 should fail (incomplete plan + missing tester role)
        self.assertFalse(result.stage1_passed)
        self.assertTrue(any(f.category == "incomplete_plan" for f in result.blocking_findings))
        self.assertTrue(any(f.category == "missing_role_output" for f in result.blocking_findings))

    def test_legacy_with_clean_output_passes(self) -> None:
        gate = TwoStageReviewGate()
        plan = FakePlan(total_tasks=2, completed_tasks=2, failed_tasks=0)
        worker_results = [
            {
                "role_id": "architect",
                "output": "Here is the api_spec document with authentication design.",
                "success": True,
            }
        ]
        result = gate.review(
            plan=plan,
            worker_results=worker_results,
            spec_requirements={"required_artifacts": ["api_spec"]},
        )
        self.assertTrue(result.stage1_passed)


class TestTwoStageReviewGateIntegration(unittest.TestCase):
    """Integration scenarios combining both stages."""

    def test_both_stages_pass_for_clean_dispatch(self) -> None:
        spec = {
            "planned_files": ["src/auth.py"],
            "planned_functions": ["login"],
            "total_tasks": 2,
            "completed_tasks": 2,
            "failed_tasks": 0,
        }
        code_changes = {
            "files": {
                "src/auth.py": {
                    "content": ('"""Auth module."""\n\ndef login():\n    """Login function."""\n    return True\n')
                },
                "tests/test_auth.py": {
                    "content": "from src.auth import login\ndef test_login():\n    assert login()\n"
                },
            }
        }
        gate = TwoStageReviewGate()
        result = gate.review(spec=spec, code_changes=code_changes)
        self.assertTrue(result.overall_passed)
        self.assertEqual(result.blocking_findings, [])

    def test_both_stages_fail(self) -> None:
        spec = {
            "planned_files": ["src/auth.py"],
            "planned_functions": ["login"],
            "total_tasks": 5,
            "completed_tasks": 2,
            "failed_tasks": 3,
        }
        code_changes = {
            "files": {
                "src/bad.py": {
                    "content": "def bad():\n    eval(x)\n"  # no tests, eval
                }
            }
        }
        gate = TwoStageReviewGate()
        result = gate.review(spec=spec, code_changes=code_changes)
        self.assertFalse(result.overall_passed)
        self.assertEqual(result.stage1_result, StageResult.FAIL)
        self.assertEqual(result.stage2_result, StageResult.FAIL)
        self.assertGreater(len(result.blocking_findings), 0)

    def test_to_dict_serialization(self) -> None:
        spec = {"total_tasks": 1, "completed_tasks": 0, "failed_tasks": 1}
        gate = TwoStageReviewGate()
        result = gate.review(spec=spec, code_changes={})
        d = result.to_dict()
        self.assertIn("overall_passed", d)
        self.assertIn("stage1_result", d)
        self.assertIn("stage2_result", d)
        self.assertIn("findings", d)
        self.assertIn("blocking_findings", d)
        self.assertFalse(d["overall_passed"])


if __name__ == "__main__":
    unittest.main()
