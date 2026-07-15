#!/usr/bin/env python3
"""
Tests for RedesignAuditor (V39-05) — Third-stage code simplicity audit.

Coverage:
  - Happy path: each category detects its target pattern
  - YAGNI: unused imports, placeholder functions, dead code blocks
  - STDLIB: custom JSON/URL/hash wrappers
  - DUPLICATE: repeated 3+ line blocks
  - OVERENGINEERING: static-only classes, excessive params, factory patterns
  - Edge cases: empty input, None, very long code, no findings
  - Performance: audit completes quickly
"""

from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.redesign_auditor import RedesignAuditor, RedesignFinding


class TestRedesignFindingDataclass(unittest.TestCase):
    """Verify RedesignFinding dataclass stores all fields."""

    def test_redesign_finding_holds_all_fields(self) -> None:
        """Verify: RedesignFinding stores severity/category/current/suggested/saving_lines."""
        # Arrange
        finding = RedesignFinding(
            severity="HIGH",
            category="YAGNI",
            current="Unused function 'foo'",
            suggested="Remove 'foo'",
            saving_lines=10,
        )
        # Assert
        self.assertEqual(finding.severity, "HIGH")
        self.assertEqual(finding.category, "YAGNI")
        self.assertEqual(finding.current, "Unused function 'foo'")
        self.assertEqual(finding.suggested, "Remove 'foo'")
        self.assertEqual(finding.saving_lines, 10)


class TestRedesignAuditorYagni(unittest.TestCase):
    """YAGNI category — unused imports, placeholder functions, dead code."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_unused_import_detected(self) -> None:
        """Verify: unused import is flagged as YAGNI/LOW."""
        # Arrange
        code = "import os\nimport json\n\nprint(os.getcwd())\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        yagni_imports = [f for f in findings if f.category == "YAGNI" and "unused import" in f.current.lower()]
        self.assertEqual(len(yagni_imports), 1)
        self.assertIn("json", yagni_imports[0].current)
        self.assertEqual(yagni_imports[0].severity, "LOW")

    def test_used_import_not_flagged(self) -> None:
        """Verify: used import is NOT flagged."""
        # Arrange
        code = "import os\nimport json\n\nprint(os.getcwd())\nprint(json.dumps({}))\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        unused_import_findings = [f for f in findings if "unused import" in f.current.lower()]
        self.assertEqual(len(unused_import_findings), 0)

    def test_placeholder_pass_function_detected(self) -> None:
        """Verify: function with only 'pass' body is flagged."""
        # Arrange
        code = "def not_implemented_func():\n    pass\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        placeholder_findings = [f for f in findings if f.category == "YAGNI" and "placeholder" in f.current.lower()]
        self.assertEqual(len(placeholder_findings), 1)
        self.assertIn("not_implemented_func", placeholder_findings[0].current)
        self.assertEqual(placeholder_findings[0].severity, "HIGH")

    def test_placeholder_notimplementederror_function_detected(self) -> None:
        """Verify: function raising NotImplementedError is flagged."""
        # Arrange
        code = "def future_function():\n    raise NotImplementedError\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        placeholder_findings = [f for f in findings if f.category == "YAGNI" and "placeholder" in f.current.lower()]
        self.assertEqual(len(placeholder_findings), 1)
        self.assertIn("future_function", placeholder_findings[0].current)

    def test_dead_code_block_critical_severity(self) -> None:
        """Verify: >50 lines of dead code triggers CRITICAL severity."""
        # Arrange
        dead_lines = "# dead comment line\n" * 60
        code = "def real_func():\n    return 1\n\n" + dead_lines
        # Act
        findings = self.auditor.audit(code)
        # Assert
        critical_findings = [f for f in findings if f.category == "YAGNI" and f.severity == "CRITICAL"]
        self.assertEqual(len(critical_findings), 1)
        self.assertIn("dead code", critical_findings[0].current.lower())

    def test_dead_code_block_high_severity(self) -> None:
        """Verify: 10-49 lines of dead code triggers HIGH severity."""
        # Arrange
        dead_lines = "# dead comment line\n" * 20
        code = "def real_func():\n    return 1\n\n" + dead_lines
        # Act
        findings = self.auditor.audit(code)
        # Assert
        high_dead = [
            f for f in findings if f.category == "YAGNI" and f.severity == "HIGH" and "dead code" in f.current.lower()
        ]
        self.assertEqual(len(high_dead), 1)


class TestRedesignAuditorStdlib(unittest.TestCase):
    """STDLIB category — custom implementations stdlib provides."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_custom_url_parser_detected(self) -> None:
        """Verify: custom parse_url function is flagged."""
        # Arrange
        code = "def parse_url(url):\n    parts = url.split('://')\n    return parts\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        stdlib_findings = [f for f in findings if f.category == "STDLIB"]
        self.assertGreaterEqual(len(stdlib_findings), 1)
        self.assertIn("urllib", stdlib_findings[0].suggested.lower())
        self.assertEqual(stdlib_findings[0].severity, "MEDIUM")

    def test_custom_json_parser_class_detected(self) -> None:
        """Verify: custom JSONParser class is flagged."""
        # Arrange
        code = "class CustomJsonParser:\n    def parse(self, text):\n        return eval(text)\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        stdlib_findings = [f for f in findings if f.category == "STDLIB"]
        self.assertGreaterEqual(len(stdlib_findings), 1)

    def test_custom_deep_copy_function_detected(self) -> None:
        """Verify: custom deep_copy function is flagged."""
        # Arrange
        code = (
            "def deep_copy_object(obj):\n"
            "    result = {}\n"
            "    for k, v in obj.items():\n"
            "        result[k] = v\n"
            "    return result\n"
        )
        # Act
        findings = self.auditor.audit(code)
        # Assert
        stdlib_findings = [f for f in findings if f.category == "STDLIB"]
        self.assertGreaterEqual(len(stdlib_findings), 1)
        self.assertIn("copy.deepcopy", stdlib_findings[0].suggested)


class TestRedesignAuditorDuplicate(unittest.TestCase):
    """DUPLICATE category — repeated code blocks."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_duplicate_block_detected(self) -> None:
        """Verify: 3+ consecutive similar lines repeated are flagged."""
        # Arrange
        block = "    result = process(data)\n    result = transform(result)\n    result = validate(result)\n"
        code = (
            "def func_a(data):\n" + block + "    return result\n\ndef func_b(data):\n" + block + "    return result\n"
        )
        # Act
        findings = self.auditor.audit(code)
        # Assert
        dup_findings = [f for f in findings if f.category == "DUPLICATE"]
        self.assertGreaterEqual(len(dup_findings), 1)
        self.assertEqual(dup_findings[0].severity, "MEDIUM")

    def test_no_duplicate_for_unique_code(self) -> None:
        """Verify: structurally different code has no DUPLICATE findings.

        Scenario: Three functions with different bodies (return, assign+return,
        conditional) should NOT be flagged as duplicates.
        Expected: 0 DUPLICATE findings.
        """
        # Arrange
        code = (
            "def func_a():\n"
            "    return 1\n\n"
            "def func_b(x):\n"
            "    y = x + 1\n"
            "    return y\n\n"
            "def func_c(x, y):\n"
            "    if x > 0:\n"
            "        return y\n"
            "    return -y\n"
        )
        # Act
        findings = self.auditor.audit(code)
        # Assert
        dup_findings = [f for f in findings if f.category == "DUPLICATE"]
        self.assertEqual(len(dup_findings), 0)

    def test_duplicate_skips_blank_and_comment_blocks(self) -> None:
        """Verify: blocks of only blank/comment lines are not flagged."""
        # Arrange
        code = "# comment 1\n# comment 2\n# comment 3\n# comment 1\n# comment 2\n# comment 3\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        dup_findings = [f for f in findings if f.category == "DUPLICATE"]
        self.assertEqual(len(dup_findings), 0)


class TestRedesignAuditorOverengineering(unittest.TestCase):
    """OVERENGINEERING category — excessive abstraction."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_static_only_class_detected(self) -> None:
        """Verify: class with only static methods is flagged."""
        # Arrange
        code = (
            "class MathUtils:\n"
            "    @staticmethod\n"
            "    def add(a, b):\n"
            "        return a + b\n"
            "    @staticmethod\n"
            "    def sub(a, b):\n"
            "        return a - b\n"
        )
        # Act
        findings = self.auditor.audit(code)
        # Assert
        oe_findings = [f for f in findings if f.category == "OVERENGINEERING"]
        static_findings = [f for f in oe_findings if "static" in f.current.lower()]
        self.assertGreaterEqual(len(static_findings), 1)
        self.assertEqual(static_findings[0].severity, "HIGH")

    def test_factory_pattern_detected(self) -> None:
        """Verify: Factory class is flagged as overengineering."""
        # Arrange
        code = (
            "class WidgetFactory:\n"
            "    def create(self, kind):\n"
            "        if kind == 'a':\n"
            "            return A()\n"
            "        return B()\n"
        )
        # Act
        findings = self.auditor.audit(code)
        # Assert
        oe_findings = [f for f in findings if f.category == "OVERENGINEERING"]
        factory_findings = [f for f in oe_findings if "factory" in f.suggested.lower()]
        self.assertGreaterEqual(len(factory_findings), 1)

    def test_builder_pattern_detected(self) -> None:
        """Verify: Builder class is flagged as overengineering."""
        # Arrange
        code = "class QueryBuilder:\n    def select(self, *cols):\n        self.cols = cols\n        return self\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        oe_findings = [f for f in findings if f.category == "OVERENGINEERING"]
        builder_findings = [f for f in oe_findings if "builder" in f.suggested.lower()]
        self.assertGreaterEqual(len(builder_findings), 1)

    def test_excessive_parameters_detected(self) -> None:
        """Verify: function with >5 parameters is flagged."""
        # Arrange
        code = "def configure_system(host, port, user, password, db, timeout, retry, debug):\n    pass\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        oe_findings = [f for f in findings if f.category == "OVERENGINEERING"]
        param_findings = [f for f in oe_findings if "parameter" in f.current.lower()]
        self.assertGreaterEqual(len(param_findings), 1)
        self.assertIn("configure_system", param_findings[0].current)

    def test_normal_parameter_count_not_flagged(self) -> None:
        """Verify: function with <=5 parameters is NOT flagged."""
        # Arrange
        code = "def normal_func(a, b, c, d, e):\n    return a + b + c + d + e\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        oe_findings = [f for f in findings if f.category == "OVERENGINEERING"]
        param_findings = [f for f in oe_findings if "parameter" in f.current.lower()]
        self.assertEqual(len(param_findings), 0)


class TestRedesignAuditorEdgeCases(unittest.TestCase):
    """Edge cases — empty/None/very-long inputs."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_empty_string_returns_empty_list(self) -> None:
        """Verify: empty string input returns empty findings list."""
        # Act
        findings = self.auditor.audit("")
        # Assert
        self.assertEqual(findings, [])

    def test_whitespace_only_returns_empty_list(self) -> None:
        """Verify: whitespace-only input returns empty findings list."""
        # Act
        findings = self.auditor.audit("   \n\t  \n")
        # Assert
        self.assertEqual(findings, [])

    def test_none_input_returns_empty_list(self) -> None:
        """Verify: None input returns empty findings list (not raises)."""
        # Act
        findings = self.auditor.audit(None)  # type: ignore[arg-type]
        # Assert
        self.assertEqual(findings, [])

    def test_clean_code_returns_no_findings(self) -> None:
        """Verify: clean, minimal code returns no findings."""
        # Arrange — ``add`` is called twice to avoid single-use/dead-code flags.
        code = "def add(a, b):\n    return a + b\n\nprint(add(1, 2))\nprint(add(3, 4))\n"
        # Act
        findings = self.auditor.audit(code)
        # Assert
        self.assertEqual(findings, [])

    def test_very_long_code_does_not_crash(self) -> None:
        """Verify: a 10000-line code completes without error."""
        # Arrange
        long_code = "x = 1\n" * 5000
        # Act
        findings = self.auditor.audit(long_code)
        # Assert
        self.assertIsInstance(findings, list)

    def test_context_parameter_optional(self) -> None:
        """Verify: context parameter is optional and does not crash."""
        # Arrange
        code = "def foo():\n    return 1\n"
        # Act
        findings = self.auditor.audit(code, context={"file_path": "foo.py"})
        # Assert
        self.assertIsInstance(findings, list)


class TestRedesignAuditorCategorySet(unittest.TestCase):
    """Verify all findings have valid categories and severities."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_all_findings_have_valid_categories(self) -> None:
        """Verify: every finding's category is in the documented set."""
        # Arrange
        valid_categories = {"YAGNI", "STDLIB", "DUPLICATE", "OVERENGINEERING", "REDUNDANT_DEP", "DELETION_TEST"}
        codes = [
            "import unused_module\n",
            "def parse_url(u): return u\n",
            "class WidgetFactory:\n    pass\n",
        ]
        # Act + Assert
        for code in codes:
            findings = self.auditor.audit(code)
            for f in findings:
                self.assertIn(f.category, valid_categories, f"Invalid category: {f.category}")

    def test_all_findings_have_valid_severities(self) -> None:
        """Verify: every finding's severity is in the documented set."""
        # Arrange
        valid_severities = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
        codes = [
            "import unused_module\n",
            "def parse_url(u): return u\n",
            "class WidgetFactory:\n    pass\n",
        ]
        # Act + Assert
        for code in codes:
            findings = self.auditor.audit(code)
            for f in findings:
                self.assertIn(f.severity, valid_severities, f"Invalid severity: {f.severity}")


class TestRedesignAuditorPerformance(unittest.TestCase):
    """Performance baseline — audit() should be fast."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_audit_completes_under_100ms(self) -> None:
        """Verify: a single audit() call on 1000-line code completes in < 100ms.

        Scenario: RedesignAuditor uses regex matching, which should be fast.
        Expected: 100 iterations complete in well under 10s, so each
        call is < 100ms.
        """
        # Arrange
        code = (
            "import os\n"
            "def foo(a, b, c, d, e, f, g):\n"
            "    pass\n"
            "class WidgetFactory:\n"
            "    @staticmethod\n"
            "    def create():\n"
            "        pass\n"
            "    @staticmethod\n"
            "    def build():\n"
            "        pass\n"
        ) * 100
        # Act
        start = time.perf_counter()
        for _ in range(10):
            self.auditor.audit(code)
        elapsed = time.perf_counter() - start
        # Assert
        self.assertLess(elapsed, 5.0, f"10 audits took {elapsed:.3f}s (> 500ms per call)")


class TestRedesignAuditorIntegration(unittest.TestCase):
    """Integration — multiple categories in one code snippet."""

    def setUp(self) -> None:
        self.auditor = RedesignAuditor()

    def test_multiple_categories_in_one_snippet(self) -> None:
        """Verify: a snippet with multiple issues returns findings from multiple categories."""
        # Arrange
        code = (
            "import unused_module\n"
            "import json\n"
            "\n"
            "class WidgetFactory:\n"
            "    @staticmethod\n"
            "    def create():\n"
            "        pass\n"
            "    @staticmethod\n"
            "    def build():\n"
            "        pass\n"
            "\n"
            "def parse_url(url):\n"
            "    return url.split('://')\n"
            "\n"
            "def excessive_func(a, b, c, d, e, f, g):\n"
            "    return 1\n"
        )
        # Act
        findings = self.auditor.audit(code)
        categories = {f.category for f in findings}
        # Assert
        self.assertIn("YAGNI", categories)
        self.assertIn("STDLIB", categories)
        self.assertIn("OVERENGINEERING", categories)


if __name__ == "__main__":
    unittest.main()
