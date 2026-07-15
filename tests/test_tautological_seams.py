#!/usr/bin/env python3
"""Module 5 (Matt P0-1): Tautological test detection + seams-up-front analysis.

Tests for TautologicalTestDetector and SeamAnalyzer classes added to
test_quality_guard.py as part of V4.1.0 Matt Pocock skills fusion.

Acceptance criteria (PRD §3.1 P0-1): ≥15 tests covering tautological
detection + seams confirmation.
"""

import ast
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.test_quality_guard import (
    SeamAnalyzer,
    Severity,
    TautologicalTestDetector,
    TestQualityGuard,
)


def _parse(source: str) -> ast.Module:
    """Helper: parse Python source into AST module."""
    return ast.parse(source)


class TestTautologicalTestDetector(unittest.TestCase):
    """T1: TautologicalTestDetector — detect trivially-true assertions."""

    def setUp(self) -> None:
        self.detector = TautologicalTestDetector()
        self.file = "test_sample.py"

    def test_constant_true_assert_detected(self) -> None:
        """Verify: ``assert True`` is flagged as tautological constant."""
        tree = _parse("def test_x():\n    assert True\n")
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].id, "taut-constant-assert")
        self.assertEqual(issues[0].severity, Severity.MAJOR)
        self.assertEqual(issues[0].category, "同义反复")

    def test_constant_one_assert_detected(self) -> None:
        """Verify: ``assert 1`` is flagged (truthy constant)."""
        tree = _parse("def test_x():\n    assert 1\n")
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 1)
        self.assertIn("恒真", issues[0].message)

    def test_constant_string_assert_detected(self) -> None:
        """Verify: ``assert "hello"`` is flagged (truthy string constant)."""
        tree = _parse('def test_x():\n    assert "hello"\n')
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 1)

    def test_false_constant_not_flagged(self) -> None:
        """Verify: ``assert False`` is NOT flagged (always-fails, not tautological)."""
        tree = _parse("def test_x():\n    assert False\n")
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 0)

    def test_self_comparison_detected(self) -> None:
        """Verify: ``assert x == x`` is flagged as self-comparison."""
        tree = _parse("def test_x():\n    x = 5\n    assert x == x\n")
        issues = self.detector.detect_in_ast(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("taut-self-compare", ids)

    def test_same_call_both_sides_detected(self) -> None:
        """Verify: ``assert f(x) == f(x)`` is flagged (same Call both sides)."""
        source = "def test_x():\n    assert f(x) == f(x)\n"
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("taut-self-compare", ids)

    def test_self_assert_equal_detected(self) -> None:
        """Verify: ``self.assertEqual(x, x)`` is flagged as self-comparison."""
        source = "class TestT(unittest.TestCase):\n    def test_x(self):\n        self.assertEqual(x, x)\n"
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("taut-self-assert-equal", ids)

    def test_recompute_impl_pattern_detected(self) -> None:
        """Verify: ``assert add(a, b) == a + b`` is flagged as recompute."""
        source = "def test_x():\n    assert add(a, b) == a + b\n"
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("taut-recompute-impl", ids)

    def test_recompute_reverse_direction(self) -> None:
        """Verify: ``assert a + b == add(a, b)`` also flagged (reverse direction)."""
        source = "def test_x():\n    assert a + b == add(a, b)\n"
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("taut-recompute-impl", ids)

    def test_recompute_assert_equal_detected(self) -> None:
        """Verify: ``self.assertEqual(add(a, b), a + b)`` is flagged."""
        source = (
            "class TestT(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        self.assertEqual(add(a, b), a + b)\n"
        )
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("taut-recompute-assert-equal", ids)

    def test_normal_assert_not_flagged(self) -> None:
        """Verify: ``assert add(2, 3) == 5`` is NOT flagged (real verification)."""
        source = "def test_x():\n    assert add(2, 3) == 5\n"
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 0)

    def test_assert_equal_different_args_not_flagged(self) -> None:
        """Verify: ``self.assertEqual(result, 42)`` is NOT flagged."""
        source = (
            "class TestT(unittest.TestCase):\n"
            "    def test_x(self):\n"
            "        self.assertEqual(result, 42)\n"
        )
        tree = _parse(source)
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 0)

    def test_empty_source_no_issues(self) -> None:
        """Verify: empty test file produces no issues (boundary case)."""
        tree = _parse("")
        issues = self.detector.detect_in_ast(tree, self.file)
        self.assertEqual(len(issues), 0)


class TestSeamAnalyzer(unittest.TestCase):
    """T2: SeamAnalyzer — detect missing seams-up-front declarations."""

    def setUp(self) -> None:
        self.analyzer = SeamAnalyzer()
        self.file = "test_sample.py"

    def test_missing_setup_detected(self) -> None:
        """Verify: class with 3+ tests, no setUp, repeated instantiation → issue."""
        source = (
            "class TestCalc(unittest.TestCase):\n"
            "    def test_01(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.add(1, 2), 3)\n"
            "    def test_02(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.sub(5, 3), 2)\n"
            "    def test_03(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.mul(2, 4), 8)\n"
        )
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("seam-missing-setup", ids)

    def test_inline_mock_detected(self) -> None:
        """Verify: test function with inline Mock() → seam-inline-mock issue."""
        source = (
            "def test_something():\n"
            "    mock = Mock()\n"
            "    result = mock.method()\n"
            "    mock.method.assert_called_once()\n"
        )
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("seam-inline-mock", ids)

    def test_inline_magic_mock_detected(self) -> None:
        """Verify: MagicMock inline also detected."""
        source = "def test_x():\n    m = MagicMock()\n    m.foo()\n"
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        ids = [i.id for i in issues]
        self.assertIn("seam-inline-mock", ids)

    def test_with_setup_not_flagged(self) -> None:
        """Verify: class with setUp() → no seam-missing-setup issue."""
        source = (
            "class TestCalc(unittest.TestCase):\n"
            "    def setUp(self):\n"
            "        self.calc = Calculator()\n"
            "    def test_01(self):\n"
            "        self.assertEqual(self.calc.add(1, 2), 3)\n"
            "    def test_02(self):\n"
            "        self.assertEqual(self.calc.sub(5, 3), 2)\n"
            "    def test_03(self):\n"
            "        self.assertEqual(self.calc.mul(2, 4), 8)\n"
        )
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        setup_issues = [i for i in issues if i.id == "seam-missing-setup"]
        self.assertEqual(len(setup_issues), 0)

    def test_with_fixture_not_flagged(self) -> None:
        """Verify: class with @pytest.fixture → no seam-missing-setup issue."""
        source = (
            "import pytest\n"
            "class TestCalc:\n"
            "    @pytest.fixture\n"
            "    def calc(self):\n"
            "        return Calculator()\n"
            "    def test_01(self, calc):\n"
            "        assert calc.add(1, 2) == 3\n"
            "    def test_02(self, calc):\n"
            "        assert calc.sub(5, 3) == 2\n"
            "    def test_03(self, calc):\n"
            "        assert calc.mul(2, 4) == 8\n"
        )
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        setup_issues = [i for i in issues if i.id == "seam-missing-setup"]
        self.assertEqual(len(setup_issues), 0)

    def test_class_under_threshold_not_flagged(self) -> None:
        """Verify: class with only 2 tests → no seam-missing-setup (boundary)."""
        source = (
            "class TestSmall(unittest.TestCase):\n"
            "    def test_01(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.add(1, 2), 3)\n"
            "    def test_02(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.sub(5, 3), 2)\n"
        )
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        setup_issues = [i for i in issues if i.id == "seam-missing-setup"]
        self.assertEqual(len(setup_issues), 0)

    def test_no_repeated_instantiation_not_flagged(self) -> None:
        """Verify: 3+ tests, no setUp, but each uses different class → no issue."""
        source = (
            "class TestMixed(unittest.TestCase):\n"
            "    def test_01(self):\n"
            "        a = Alpha()\n"
            "        self.assertTrue(a.run())\n"
            "    def test_02(self):\n"
            "        b = Beta()\n"
            "        self.assertTrue(b.run())\n"
            "    def test_03(self):\n"
            "        c = Gamma()\n"
            "        self.assertTrue(c.run())\n"
        )
        tree = _parse(source)
        issues = self.analyzer.analyze(tree, self.file)
        setup_issues = [i for i in issues if i.id == "seam-missing-setup"]
        self.assertEqual(len(setup_issues), 0)


class TestIntegrationWithAudit(unittest.TestCase):
    """T3: Integration — TestQualityGuard.audit() detects tautological + seams."""

    def _write_temp_files(
        self, source_code: str, test_code: str
    ) -> tuple[Path, Path]:
        """Create temp source and test files, return their paths."""
        tmpdir = Path(tempfile.mkdtemp(prefix="taut_test_"))
        src_path = tmpdir / "sample.py"
        test_path = tmpdir / "test_sample.py"
        src_path.write_text(source_code, encoding="utf-8")
        test_path.write_text(test_code, encoding="utf-8")
        return src_path, test_path

    def test_audit_detects_tautological_patterns(self) -> None:
        """Verify: audit() flags tautological assertions in test file."""
        source = "def add(a, b):\n    return a + b\n"
        test_code = (
            '"""Tests."""\n'
            "from sample import add\n"
            "import unittest\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_tautological(self):\n"
            "        self.assertEqual(add(1, 2), 1 + 2)\n"
            "    def test_self_compare(self):\n"
            "        x = 5\n"
            "        self.assertEqual(x, x)\n"
        )
        src_path, test_path = self._write_temp_files(source, test_code)
        guard = TestQualityGuard(str(src_path), str(test_path))
        report = guard.audit()
        taut_issues = [i for i in report.issues if i.category == "同义反复"]
        self.assertGreaterEqual(len(taut_issues), 2)

    def test_audit_detects_missing_seams(self) -> None:
        """Verify: audit() flags missing seam declarations."""
        source = "class Calculator:\n    def add(self, a, b):\n        return a + b\n"
        test_code = (
            '"""Tests."""\n'
            "from sample import Calculator\n"
            "import unittest\n"
            "class TestCalc(unittest.TestCase):\n"
            "    def test_01(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.add(1, 2), 3)\n"
            "    def test_02(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.add(3, 4), 7)\n"
            "    def test_03(self):\n"
            "        calc = Calculator()\n"
            "        self.assertEqual(calc.add(0, 0), 0)\n"
        )
        src_path, test_path = self._write_temp_files(source, test_code)
        guard = TestQualityGuard(str(src_path), str(test_path))
        report = guard.audit()
        seam_issues = [i for i in report.issues if i.category == "缺失seam声明"]
        self.assertGreaterEqual(len(seam_issues), 1)

    def test_tautological_affects_anti_pattern_score(self) -> None:
        """Verify: tautological issues decrease anti_pattern_free score."""
        source = "def add(a, b):\n    return a + b\n"
        taut_test = (
            '"""Tautological tests."""\n'
            "from sample import add\n"
            "import unittest\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_taut(self):\n"
            "        self.assertEqual(add(1, 2), 1 + 2)\n"
        )
        clean_test = (
            '"""Clean tests."""\n'
            "from sample import add\n"
            "import unittest\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_clean(self):\n"
            "        self.assertEqual(add(1, 2), 3)\n"
        )
        src_taut, test_taut = self._write_temp_files(source, taut_test)
        src_clean, test_clean = self._write_temp_files(source, clean_test)
        taut_report = TestQualityGuard(str(src_taut), str(test_taut)).audit()
        clean_report = TestQualityGuard(str(src_clean), str(test_clean)).audit()
        self.assertLess(
            taut_report.score.anti_pattern_free,
            clean_report.score.anti_pattern_free,
        )

    def test_clean_test_produces_no_tautological_issues(self) -> None:
        """Verify: well-written test file produces zero tautological issues."""
        source = "def add(a, b):\n    return a + b\n"
        clean_test = (
            '"""Clean tests with real expected values."""\n'
            "from sample import add\n"
            "import unittest\n"
            "class TestAdd(unittest.TestCase):\n"
            "    def test_add_positive(self):\n"
            "        self.assertEqual(add(2, 3), 5)\n"
            "    def test_add_negative(self):\n"
            "        self.assertEqual(add(-1, -1), -2)\n"
            "    def test_add_zero(self):\n"
            "        self.assertEqual(add(0, 5), 5)\n"
        )
        src_path, test_path = self._write_temp_files(source, clean_test)
        guard = TestQualityGuard(str(src_path), str(test_path))
        report = guard.audit()
        taut_issues = [i for i in report.issues if i.category == "同义反复"]
        self.assertEqual(len(taut_issues), 0)


if __name__ == "__main__":
    unittest.main()
