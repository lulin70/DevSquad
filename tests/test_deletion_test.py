#!/usr/bin/env python3
"""Module 6 (Matt P0-3): Deletion test + HTML report.

Tests for ``RedesignAuditor.deletion_test()``, ``_is_pass_through()``,
and ``to_html_report()`` methods added as part of V4.1.0 Matt Pocock
skills fusion.

Acceptance criteria (PRD §3.3 P0-3): ≥10 tests covering deletion test
detection (pass-through / dead code / single-use) + HTML report
generation + integration with ``audit()``.
"""

from __future__ import annotations

import ast
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.redesign_auditor import RedesignAuditor
from scripts.collaboration.redesign_checkers import RedesignFinding

# ======================================================================
# Module 6 — Matt Pocock Deletion Test
# ======================================================================


class TestDeletionTestPassThrough(unittest.TestCase):
    """T1: Pass-through function detection (body just delegates)."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_return_call_is_pass_through(self) -> None:
        """Verify: function whose body is ``return other_func(...)`` is flagged MEDIUM."""
        code = "def wrapper(x):\n    return list(x)\n"
        findings = self.auditor.deletion_test(code)
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 1)
        self.assertEqual(pass_through[0].severity, "MEDIUM")
        self.assertEqual(pass_through[0].category, "DELETION_TEST")
        self.assertIn("wrapper", pass_through[0].current)

    def test_return_attribute_call_is_pass_through(self) -> None:
        """Verify: ``return obj.method()`` (attribute call) is pass-through.

        Note: ``deletion_test`` only checks top-level definitions (module
        scope). Methods inside classes are part of the class's internal
        implementation and are not individually checked.
        """
        code = "def wrapper(obj):\n    return obj.process()\n"
        findings = self.auditor.deletion_test(code)
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 1)
        self.assertIn("wrapper", pass_through[0].current)

    def test_docstring_plus_return_call_is_pass_through(self) -> None:
        """Verify: docstring followed by ``return call()`` is still pass-through."""
        code = (
            "def wrapper():\n"
            '    """Doc."""\n'
            "    return int('42')\n"
        )
        findings = self.auditor.deletion_test(code)
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 1)

    def test_pass_only_function_is_pass_through(self) -> None:
        """Verify: function with only ``pass`` body is flagged as pass-through."""
        code = "def empty():\n    pass\n"
        findings = self.auditor.deletion_test(code)
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 1)

    def test_multi_statement_function_not_pass_through(self) -> None:
        """Verify: function with multiple statements is NOT pass-through."""
        code = (
            "def real_work(x):\n"
            "    y = x + 1\n"
            "    return y * 2\n"
        )
        findings = self.auditor.deletion_test(code)
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 0)


class TestDeletionTestDeadCode(unittest.TestCase):
    """T2: Dead code detection (defined but never referenced)."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_unused_function_flagged_high(self) -> None:
        """Verify: function never called is flagged HIGH (dead code)."""
        code = "def unused():\n    return 42\n"
        findings = self.auditor.deletion_test(code)
        dead = [f for f in findings if "never referenced" in f.current]
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].severity, "HIGH")
        self.assertIn("unused", dead[0].current)

    def test_unused_class_flagged_high(self) -> None:
        """Verify: class never instantiated is flagged HIGH."""
        code = "class UnusedClass:\n    pass\n"
        findings = self.auditor.deletion_test(code)
        dead = [f for f in findings if "never referenced" in f.current]
        self.assertEqual(len(dead), 1)
        self.assertEqual(dead[0].severity, "HIGH")

    def test_dunder_methods_not_flagged(self) -> None:
        """Verify: dunder methods (__init__, __str__) are skipped."""
        code = (
            "class Foo:\n"
            "    def __init__(self):\n"
            "        pass\n"
            "    def __str__(self):\n"
            "        return 'Foo'\n"
        )
        findings = self.auditor.deletion_test(code)
        dunder_findings = [f for f in findings if "__" in f.current]
        self.assertEqual(len(dunder_findings), 0)


class TestDeletionTestSingleUse(unittest.TestCase):
    """T3: Single-use function detection (inlining candidate)."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_single_call_function_flagged_low(self) -> None:
        """Verify: function called exactly once is flagged LOW (inlining candidate)."""
        code = (
            "def helper():\n"
            "    return 42\n"
            "def caller():\n"
            "    return helper()\n"
        )
        findings = self.auditor.deletion_test(code)
        single_use = [f for f in findings if "called only once" in f.current]
        self.assertEqual(len(single_use), 1)
        self.assertEqual(single_use[0].severity, "LOW")
        self.assertIn("helper", single_use[0].current)

    def test_multi_call_function_not_flagged(self) -> None:
        """Verify: function called 2+ times is NOT flagged for inlining."""
        code = (
            "def helper():\n"
            "    return 42\n"
            "def caller_a():\n"
            "    return helper()\n"
            "def caller_b():\n"
            "    return helper()\n"
        )
        findings = self.auditor.deletion_test(code)
        single_use = [f for f in findings if "called only once" in f.current]
        self.assertEqual(len(single_use), 0)


class TestDeletionTestEdgeCases(unittest.TestCase):
    """T4: Edge cases — empty input, syntax errors, file_path."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_empty_code_returns_empty_list(self) -> None:
        """Verify: empty string returns no findings."""
        self.assertEqual(self.auditor.deletion_test(""), [])
        self.assertEqual(self.auditor.deletion_test("   \n  "), [])

    def test_syntax_error_returns_empty_list(self) -> None:
        """Verify: unparseable code returns no findings (graceful degradation)."""
        self.assertEqual(self.auditor.deletion_test("def broken(:\n  pass"), [])

    def test_file_path_appears_in_finding(self) -> None:
        """Verify: when file_path is provided, pass-through findings mention it."""
        code = "def wrapper(x):\n    return list(x)\n"
        findings = self.auditor.deletion_test(code, file_path="my_module.py")
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 1)
        self.assertIn("my_module.py", pass_through[0].current)

    def test_file_path_omitted_does_not_crash(self) -> None:
        """Verify: default file_path='' produces clean output without 'in '."""
        code = "def wrapper(x):\n    return list(x)\n"
        findings = self.auditor.deletion_test(code)
        pass_through = [f for f in findings if "pass-through" in f.current]
        self.assertEqual(len(pass_through), 1)
        # When file_path is empty, the " in {file_path}" suffix is omitted.
        self.assertNotIn(" in \n", pass_through[0].current)
        self.assertNotIn(" in )", pass_through[0].current)


class TestIsPassThroughHelper(unittest.TestCase):
    """T5: Direct tests for ``_is_pass_through()`` helper."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def _parse_func(self, source: str) -> ast.FunctionDef:
        """Helper: parse source and return the first FunctionDef."""
        tree = ast.parse(source)
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.FunctionDef):
                return node
        raise AssertionError("No FunctionDef found in source")

    def test_return_call_detected(self) -> None:
        """Verify: ``return func()`` is pass-through."""
        node = self._parse_func("def w():\n    return int('1')\n")
        self.assertTrue(self.auditor._is_pass_through(node))

    def test_pass_detected(self) -> None:
        """Verify: ``pass`` body is pass-through."""
        node = self._parse_func("def w():\n    pass\n")
        self.assertTrue(self.auditor._is_pass_through(node))

    def test_return_literal_not_pass_through(self) -> None:
        """Verify: ``return 42`` (literal, not Call) is NOT pass-through."""
        node = self._parse_func("def w():\n    return 42\n")
        self.assertFalse(self.auditor._is_pass_through(node))

    def test_multi_line_logic_not_pass_through(self) -> None:
        """Verify: function with real logic is NOT pass-through."""
        node = self._parse_func("def w(x):\n    y = x + 1\n    return y\n")
        self.assertFalse(self.auditor._is_pass_through(node))


# ======================================================================
# Module 6 — HTML Report
# ======================================================================


class TestHtmlReport(unittest.TestCase):
    """T6: ``to_html_report()`` — HTML report generation."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()
        self.sample_findings = [
            RedesignFinding(
                severity="LOW",
                category="DELETION_TEST",
                current="Low-severity issue",
                suggested="Inline it",
                saving_lines=2,
            ),
            RedesignFinding(
                severity="CRITICAL",
                category="YAGNI",
                current="<script>alert('xss')</script>",
                suggested="Remove dead code",
                saving_lines=50,
            ),
            RedesignFinding(
                severity="HIGH",
                category="DELETION_TEST",
                current="Unused function 'foo'",
                suggested="Delete 'foo'",
                saving_lines=10,
            ),
        ]

    def test_html_starts_with_doctype(self) -> None:
        """Verify: report begins with ``<!DOCTYPE html>``."""
        html = self.auditor.to_html_report(self.sample_findings)
        self.assertTrue(html.startswith("<!DOCTYPE html>"))

    def test_html_contains_title(self) -> None:
        """Verify: custom title appears in <title> and <h1>."""
        html = self.auditor.to_html_report(self.sample_findings, title="My Audit")
        self.assertIn("<title>My Audit</title>", html)
        self.assertIn("<h1>My Audit</h1>", html)

    def test_findings_sorted_by_severity(self) -> None:
        """Verify: CRITICAL findings appear before LOW in the table."""
        html = self.auditor.to_html_report(self.sample_findings)
        critical_pos = html.find("CRITICAL")
        low_pos = html.find("LOW")
        # Both should be present in the table body.
        self.assertGreater(critical_pos, 0)
        self.assertGreater(low_pos, 0)
        self.assertLess(critical_pos, low_pos)

    def test_xss_content_escaped(self) -> None:
        """Verify: ``<script>`` in finding content is HTML-escaped."""
        html = self.auditor.to_html_report(self.sample_findings)
        self.assertNotIn("<script>alert", html)
        self.assertIn("&lt;script&gt;", html)

    def test_summary_shows_total_findings_and_savings(self) -> None:
        """Verify: summary section shows count and total line savings."""
        html = self.auditor.to_html_report(self.sample_findings)
        # Total findings = 3
        self.assertIn("Total findings:</strong> 3", html)
        # Total savings = 2 + 50 + 10 = 62
        self.assertIn("lines saved:</strong> 62", html)

    def test_category_breakdown_displayed(self) -> None:
        """Verify: per-category counts appear in summary list."""
        html = self.auditor.to_html_report(self.sample_findings)
        # DELETION_TEST: 2, YAGNI: 1
        self.assertIn("DELETION_TEST: 2", html)
        self.assertIn("YAGNI: 1", html)

    def test_empty_findings_html_structure(self) -> None:
        """Verify: empty findings list still produces valid HTML."""
        html = self.auditor.to_html_report([], title="Empty")
        self.assertTrue(html.startswith("<!DOCTYPE html>"))
        self.assertIn("Total findings:</strong> 0", html)
        self.assertIn("lines saved:</strong> 0", html)

    def test_severity_colors_applied(self) -> None:
        """Verify: each severity has its color in the table."""
        html = self.auditor.to_html_report(self.sample_findings)
        self.assertIn("#dc2626", html)  # CRITICAL red
        self.assertIn("#ea580c", html)  # HIGH orange
        self.assertIn("#2563eb", html)  # LOW blue


# ======================================================================
# Module 6 — Integration with audit()
# ======================================================================


class TestAuditIntegration(unittest.TestCase):
    """T7: ``audit()`` pipeline includes deletion_test findings."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_deletion_findings_appear_in_audit(self) -> None:
        """Verify: ``audit()`` returns DELETION_TEST category findings."""
        code = (
            "def wrapper(x):\n"
            "    return list(x)\n"
            "def unused():\n"
            "    return 42\n"
        )
        findings = self.auditor.audit(code)
        deletion = [f for f in findings if f.category == "DELETION_TEST"]
        self.assertGreater(len(deletion), 0)

    def test_deletion_does_not_break_yagni(self) -> None:
        """Verify: YAGNI findings still appear alongside DELETION_TEST."""
        code = "import os\nimport json\n\nprint(os.getcwd())\n"
        findings = self.auditor.audit(code)
        yagni = [f for f in findings if f.category == "YAGNI"]
        self.assertGreater(len(yagni), 0)

    def test_audit_empty_code_returns_empty(self) -> None:
        """Verify: ``audit('')`` returns no findings."""
        self.assertEqual(self.auditor.audit(""), [])


if __name__ == "__main__":
    unittest.main()
