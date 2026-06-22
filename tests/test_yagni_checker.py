#!/usr/bin/env python3
"""
Tests for YagniChecker (V39-03) — YAGNI ladder check for micro-tasks.

Coverage:
  - Happy path: various task types → correct verdicts
  - NEVER_SKIP: security/error/test/a11y tasks always return NECESSARY
  - STDLIB detection: json parsing, url parsing, regex, etc.
  - DEPENDENCY detection: http requests, html parsing, etc.
  - SKIP detection: exploratory tasks without output
  - ONE_LINER detection: simple config/call tasks
  - MINIMAL: necessary tasks with no shortcut
  - Edge cases: empty string, None, very long description
  - Integration: MicroTaskPlanner integration
"""

from __future__ import annotations

import os
import sys
import time
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.yagni_checker import YagniChecker, YagniResult


class TestYagniResultDataclass(unittest.TestCase):
    """Verify YagniResult dataclass."""

    def test_yagni_result_holds_all_fields(self) -> None:
        """Verify: YagniResult stores verdict/reason/upgrade_path/shortcut_marker."""
        # Arrange
        result = YagniResult(
            verdict="SKIP",
            reason="Exploratory",
            upgrade_path="Skip it",
            shortcut_marker="shortcut: exploratory task skipped",
        )
        # Assert
        self.assertEqual(result.verdict, "SKIP")
        self.assertEqual(result.reason, "Exploratory")
        self.assertEqual(result.upgrade_path, "Skip it")
        self.assertEqual(result.shortcut_marker, "shortcut: exploratory task skipped")


class TestYagniCheckerHappyPath(unittest.TestCase):
    """Happy-path tests — various task types return correct verdicts."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_minimal_verdict_for_general_implementation_task(self) -> None:
        """Verify: a general implementation task returns MINIMAL.

        Scenario: Task is concrete, no stdlib/dependency match, not one-liner,
        and does NOT match any never-skip pattern (avoid words like
        'auth'/'validate'/'test'/'error' which trigger NECESSARY).
        Expected: verdict == MINIMAL.
        """
        # Act
        result = self.checker.check("Implement the report generation module with PDF export")
        # Assert
        self.assertEqual(result.verdict, "MINIMAL")
        self.assertFalse(result.shortcut_marker)

    def test_use_stdlib_for_json_parsing(self) -> None:
        """Verify: 'parse JSON' task returns USE_STDLIB."""
        # Act
        result = self.checker.check("Parse JSON response from the API")
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")
        self.assertIn("json.loads", result.reason)
        self.assertIn("shortcut: use stdlib", result.shortcut_marker)

    def test_use_stdlib_for_url_parsing(self) -> None:
        """Verify: 'parse URL' task returns USE_STDLIB."""
        # Act
        result = self.checker.check("Parse URL to extract query parameters")
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")
        self.assertIn("urllib.parse", result.reason)

    def test_use_stdlib_for_regex_matching(self) -> None:
        """Verify: 'regex' task returns USE_STDLIB."""
        # Act
        result = self.checker.check("Apply regex pattern match on user input")
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")
        self.assertIn("re module", result.reason)

    def test_use_stdlib_for_uuid_generation(self) -> None:
        """Verify: 'uuid' task returns USE_STDLIB."""
        # Act
        result = self.checker.check("Generate UUID for the new record")
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")
        self.assertIn("uuid.uuid4", result.reason)

    def test_use_stdlib_for_hashing(self) -> None:
        """Verify: 'hash' task returns USE_STDLIB."""
        # Act
        result = self.checker.check("Compute SHA256 hash of the file contents")
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")
        self.assertIn("hashlib", result.reason)

    def test_use_dependency_for_http_request(self) -> None:
        """Verify: 'http request' task returns USE_DEPENDENCY."""
        # Act
        result = self.checker.check("Make HTTP request to the external API endpoint")
        # Assert
        self.assertEqual(result.verdict, "USE_DEPENDENCY")
        self.assertIn("requests", result.reason)

    def test_use_dependency_for_html_parsing(self) -> None:
        """Verify: 'parse HTML' task returns USE_DEPENDENCY."""
        # Act
        result = self.checker.check("Parse HTML from the scraped page")
        # Assert
        self.assertEqual(result.verdict, "USE_DEPENDENCY")
        self.assertIn("BeautifulSoup", result.reason)


class TestYagniCheckerNeverSkip(unittest.TestCase):
    """NEVER_SKIP patterns — security/error/test/a11y tasks return NECESSARY."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_validate_task_is_necessary(self) -> None:
        """Verify: validation task returns NECESSARY."""
        # Act
        result = self.checker.check("Validate user input before saving to database")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")
        self.assertFalse(result.shortcut_marker)

    def test_error_handling_task_is_necessary(self) -> None:
        """Verify: error-handling task returns NECESSARY."""
        # Act
        result = self.checker.check("Add error handling for the network call")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")

    def test_permission_check_task_is_necessary(self) -> None:
        """Verify: permission/auth task returns NECESSARY."""
        # Act
        result = self.checker.check("Check user permission before accessing resource")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")

    def test_backup_task_is_necessary(self) -> None:
        """Verify: backup/persist task returns NECESSARY."""
        # Act
        result = self.checker.check("Backup database before migration")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")

    def test_test_writing_task_is_necessary(self) -> None:
        """Verify: test-writing task returns NECESSARY."""
        # Act
        result = self.checker.check("Write unit tests for the auth module")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")

    def test_accessibility_task_is_necessary(self) -> None:
        """Verify: accessibility (a11y) task returns NECESSARY."""
        # Act
        result = self.checker.check("Add accessibility labels to the form")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")

    def test_security_task_overrides_stdlib_pattern(self) -> None:
        """Verify: even if 'validate' appears with a stdlib keyword, NECESSARY wins.

        Scenario: 'validate JSON' would match stdlib pattern, but 'validate'
        is in NEVER_SKIP_PATTERNS, so NECESSARY must win.
        Expected: verdict == NECESSARY (never-skip is checked first).
        """
        # Act
        result = self.checker.check("Validate JSON schema before processing")
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")


class TestYagniCheckerSkip(unittest.TestCase):
    """SKIP detection — exploratory tasks without concrete output."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_explore_task_is_skipped(self) -> None:
        """Verify: 'explore' task returns SKIP."""
        # Act
        result = self.checker.check("Explore the codebase structure")
        # Assert
        self.assertEqual(result.verdict, "SKIP")
        self.assertIn("shortcut: exploratory", result.shortcut_marker)

    def test_investigate_task_is_skipped(self) -> None:
        """Verify: 'investigate' task returns SKIP."""
        # Act
        result = self.checker.check("Investigate the root cause of the bug")
        # Assert
        self.assertEqual(result.verdict, "SKIP")

    def test_research_task_is_skipped(self) -> None:
        """Verify: 'research' task returns SKIP."""
        # Act
        result = self.checker.check("Research the available options for caching")
        # Assert
        self.assertEqual(result.verdict, "SKIP")

    def test_concrete_task_with_explore_word_is_not_skipped(self) -> None:
        """Verify: a task with 'explore' but also a concrete verb is NOT skipped.

        Scenario: 'Explore and implement the auth flow' has both 'explore'
        and 'implement'. Concrete verb wins → not exploratory.
        Expected: verdict != SKIP (likely MINIMAL).
        """
        # Act
        result = self.checker.check("Explore and implement the auth flow")
        # Assert
        self.assertNotEqual(result.verdict, "SKIP")


class TestYagniCheckerOneLiner(unittest.TestCase):
    """ONE_LINER detection — simple config/call tasks."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_set_config_is_one_liner(self) -> None:
        """Verify: 'set X = Y' task returns ONE_LINER."""
        # Act
        result = self.checker.check("Set DEBUG = True in config")
        # Assert
        self.assertEqual(result.verdict, "ONE_LINER")
        self.assertIn("shortcut: one-liner", result.shortcut_marker)

    def test_print_statement_is_one_liner(self) -> None:
        """Verify: 'print(...)' task returns ONE_LINER."""
        # Act
        result = self.checker.check("print('hello world')")
        # Assert
        self.assertEqual(result.verdict, "ONE_LINER")

    def test_import_statement_is_one_liner(self) -> None:
        """Verify: 'import X' task returns ONE_LINER."""
        # Act
        result = self.checker.check("import os")
        # Assert
        self.assertEqual(result.verdict, "ONE_LINER")


class TestYagniCheckerEdgeCases(unittest.TestCase):
    """Edge cases — empty/None/very-long inputs."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_empty_string_returns_skip(self) -> None:
        """Verify: empty string returns SKIP."""
        # Act
        result = self.checker.check("")
        # Assert
        self.assertEqual(result.verdict, "SKIP")
        self.assertIn("Empty", result.reason)

    def test_whitespace_only_returns_skip(self) -> None:
        """Verify: whitespace-only string returns SKIP."""
        # Act
        result = self.checker.check("   \n\t  ")
        # Assert
        self.assertEqual(result.verdict, "SKIP")

    def test_none_returns_skip(self) -> None:
        """Verify: None input returns SKIP (not raises)."""
        # Act
        result = self.checker.check(None)  # type: ignore[arg-type]
        # Assert
        self.assertEqual(result.verdict, "SKIP")

    def test_very_long_description_does_not_crash(self) -> None:
        """Verify: a 10000-char description completes without error."""
        # Arrange
        long_desc = "Implement the module " + ("foo bar " * 1200)
        # Act
        result = self.checker.check(long_desc)
        # Assert
        self.assertIn(result.verdict, {"MINIMAL", "USE_STDLIB", "USE_DEPENDENCY",
                                       "ONE_LINER", "SKIP", "NECESSARY"})

    def test_task_details_optional(self) -> None:
        """Verify: task_details parameter is optional and does not crash."""
        # Act
        result = self.checker.check("Implement feature X", task_details=None)
        # Assert
        self.assertEqual(result.verdict, "MINIMAL")

    def test_task_details_with_file_paths(self) -> None:
        """Verify: passing task_details with file_paths works."""
        # Act
        result = self.checker.check(
            "Implement feature X",
            task_details={"file_paths": ["src/foo.py"]},
        )
        # Assert
        self.assertEqual(result.verdict, "MINIMAL")


class TestYagniCheckerVerdictSet(unittest.TestCase):
    """Verify all verdicts are within the documented set."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_all_verdicts_are_valid(self) -> None:
        """Verify: every verdict returned is in the documented set."""
        # Arrange
        valid_verdicts = {"SKIP", "USE_STDLIB", "USE_DEPENDENCY",
                          "ONE_LINER", "MINIMAL", "NECESSARY"}
        tasks = [
            "",  # SKIP
            "Validate input",  # NECESSARY
            "Explore options",  # SKIP
            "Parse JSON",  # USE_STDLIB
            "Make HTTP request",  # USE_DEPENDENCY
            "set DEBUG=True",  # ONE_LINER
            "Implement the auth module",  # MINIMAL
        ]
        # Act + Assert
        for task in tasks:
            result = self.checker.check(task)
            self.assertIn(result.verdict, valid_verdicts,
                          f"Task '{task}' returned invalid verdict: {result.verdict}")


class TestYagniCheckerPerformance(unittest.TestCase):
    """Performance baseline — check() should be fast (< 5ms)."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_check_completes_under_5ms(self) -> None:
        """Verify: a single check() call completes in < 5ms.

        Scenario: YagniChecker uses regex matching, which should be fast.
        Expected: 1000 iterations complete in well under 5s, so each
        call is < 5ms.
        """
        # Arrange
        task = "Implement the user authentication module with OAuth2"
        # Act
        start = time.perf_counter()
        for _ in range(1000):
            self.checker.check(task)
        elapsed = time.perf_counter() - start
        # Assert
        self.assertLess(elapsed, 5.0,
                        f"1000 checks took {elapsed:.3f}s (> 5ms per call)")


class TestYagniCheckerMicroTaskIntegration(unittest.TestCase):
    """Integration with MicroTaskPlanner.MicroTask."""

    def setUp(self) -> None:
        self.checker = YagniChecker()

    def test_check_micro_task_with_real_micro_task(self) -> None:
        """Verify: check_micro_task works with a real MicroTask object.

        Scenario: Create a MicroTask from micro_task_planner and check it.
        Expected: returns a YagniResult with a valid verdict.
        """
        # Arrange — import MicroTask (optional integration).
        try:
            from scripts.collaboration.micro_task_planner import MicroTask
        except ImportError:
            self.skipTest("MicroTask not available")
        mt = MicroTask(
            id="mt-1",
            title="Parse JSON response",
            description="Parse the JSON response from the API endpoint",
        )
        # Act
        result = self.checker.check_micro_task(mt)
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")
        self.assertIn("json.loads", result.reason)

    def test_check_micro_task_with_security_task(self) -> None:
        """Verify: check_micro_task flags security MicroTask as NECESSARY."""
        # Arrange
        try:
            from scripts.collaboration.micro_task_planner import MicroTask
        except ImportError:
            self.skipTest("MicroTask not available")
        mt = MicroTask(
            id="mt-2",
            title="Validate user input",
            description="Validate and sanitize user input before saving",
        )
        # Act
        result = self.checker.check_micro_task(mt)
        # Assert
        self.assertEqual(result.verdict, "NECESSARY")

    def test_check_micro_task_with_duck_typed_object(self) -> None:
        """Verify: check_micro_task works with any object having title/description.

        Scenario: Pass a plain object with title/description attributes
        (duck typing) — should work without importing MicroTask.
        Expected: returns a YagniResult.
        """
        # Arrange
        class FakeMicroTask:
            title = "Parse JSON"
            description = "Parse the JSON payload"
            file_paths = ["src/parser.py"]
        # Act
        result = self.checker.check_micro_task(FakeMicroTask())
        # Assert
        self.assertEqual(result.verdict, "USE_STDLIB")


if __name__ == "__main__":
    unittest.main()
