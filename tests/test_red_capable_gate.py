#!/usr/bin/env python3
"""Module 7 (Matt P0-4): Red-capable gate + [DEBUG-xxx] tag mechanism.

Tests for:
- ``VerificationGate.verify_debug_loop_ready()`` — Matt Pocock's 4 criteria
- ``RedCapableResult`` dataclass
- Module-level DEBUG tag functions: ``register_debug_tag``,
  ``cleanup_debug_tags``, ``strip_debug_tags``, ``get_registered_debug_tags``,
  ``clear_debug_tags``
- Instance methods: ``ExecutionGuard.find_debug_tags``,
  ``ExecutionGuard.remove_debug_lines``

Acceptance criteria (PRD §3.4 P0-4): ≥12 tests covering red-capable gate +
DEBUG tag mechanism.
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.execution_guard import (
    ExecutionGuard,
    cleanup_debug_tags,
    clear_debug_tags,
    get_registered_debug_tags,
    register_debug_tag,
    strip_debug_tags,
)
from scripts.collaboration.verification_gate import (
    RedCapableResult,
    VerificationGate,
)

# ======================================================================
# Module 7 — Red-capable gate (verification_gate.py)
# ======================================================================


class TestRedCapableGate(unittest.TestCase):
    """T1: ``verify_debug_loop_ready()`` — 4 criteria evaluation."""

    def setUp(self) -> None:
        self.gate = VerificationGate()
        # Ensure tests are isolated from each other.
        clear_debug_tags()

    def test_passes_all_4_criteria(self) -> None:
        """Verify: ``pytest tests/test_foo.py`` passes all 4 criteria."""
        result = self.gate.verify_debug_loop_ready("pytest tests/test_foo.py -v")
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_criteria, [])
        self.assertIn("satisfied", result.reasoning)

    def test_fails_on_empty_command(self) -> None:
        """Verify: empty command fails all 4 criteria."""
        result = self.gate.verify_debug_loop_ready("")
        self.assertFalse(result.passed)
        self.assertEqual(len(result.failed_criteria), 4)

    def test_fails_on_non_red_capable(self) -> None:
        """Verify: assignment-only command fails on-red-capable."""
        result = self.gate.verify_debug_loop_ready("x = 1")
        self.assertFalse(result.passed)
        self.assertIn("on-red-capable", result.failed_criteria)

    def test_fails_on_non_deterministic_random(self) -> None:
        """Verify: command with ``random`` fails on-deterministic."""
        result = self.gate.verify_debug_loop_ready("assert random.randint(1, 10) == 5")
        self.assertFalse(result.passed)
        self.assertIn("on-deterministic", result.failed_criteria)

    def test_fails_on_non_deterministic_network(self) -> None:
        """Verify: command with ``requests.`` fails on-deterministic."""
        result = self.gate.verify_debug_loop_ready("assert requests.get('http://x').status_code == 200")
        self.assertFalse(result.passed)
        self.assertIn("on-deterministic", result.failed_criteria)

    def test_fails_on_slow_sleep(self) -> None:
        """Verify: command with ``time.sleep`` fails on-fast."""
        result = self.gate.verify_debug_loop_ready("import time; time.sleep(10); assert True")
        self.assertFalse(result.passed)
        self.assertIn("on-fast", result.failed_criteria)

    def test_fails_on_slow_infinite_loop(self) -> None:
        """Verify: ``while True`` fails on-fast."""
        result = self.gate.verify_debug_loop_ready("while True:\n    assert True")
        self.assertFalse(result.passed)
        self.assertIn("on-fast", result.failed_criteria)

    def test_fails_on_interactive_input(self) -> None:
        """Verify: ``input()`` fails on-agent-runnable."""
        result = self.gate.verify_debug_loop_ready("x = input('enter: ')\nassert x == 'yes'")
        self.assertFalse(result.passed)
        self.assertIn("on-agent-runnable", result.failed_criteria)

    def test_fails_on_pdb(self) -> None:
        """Verify: ``pdb`` fails on-agent-runnable."""
        result = self.gate.verify_debug_loop_ready("import pdb; pdb.set_trace(); assert True")
        self.assertFalse(result.passed)
        self.assertIn("on-agent-runnable", result.failed_criteria)

    def test_multiple_criteria_failures_reported(self) -> None:
        """Verify: multiple failures are all listed in failed_criteria."""
        result = self.gate.verify_debug_loop_ready("x = input('enter: ')\nimport random\nassert x == random.randint(1, 9)")
        self.assertFalse(result.passed)
        self.assertIn("on-deterministic", result.failed_criteria)
        self.assertIn("on-agent-runnable", result.failed_criteria)

    def test_reasoning_contains_failed_criteria_names(self) -> None:
        """Verify: reasoning string explains which criteria failed."""
        result = self.gate.verify_debug_loop_ready("import time; time.sleep(5); print('done')")
        self.assertFalse(result.passed)
        # ``print('done')`` has no assertion → not red-capable
        self.assertIn("on-red-capable", result.failed_criteria)
        self.assertIn("on-fast", result.failed_criteria)
        # Reasoning uses descriptive text, not criterion names.
        self.assertIn("failing result", result.reasoning)
        self.assertIn("slow", result.reasoning)


class TestRedCapableResultDataclass(unittest.TestCase):
    """T2: ``RedCapableResult`` dataclass structure."""

    def test_default_fields(self) -> None:
        """Verify: RedCapableResult defaults are sensible."""
        result = RedCapableResult(passed=True)
        self.assertTrue(result.passed)
        self.assertEqual(result.failed_criteria, [])
        self.assertEqual(result.reasoning, "")
        self.assertEqual(result.command, "")

    def test_all_fields_populated(self) -> None:
        """Verify: RedCapableResult stores all fields."""
        result = RedCapableResult(
            passed=False,
            failed_criteria=["on-fast"],
            reasoning="command appears slow",
            command="time.sleep(10)",
        )
        self.assertFalse(result.passed)
        self.assertEqual(result.failed_criteria, ["on-fast"])
        self.assertEqual(result.reasoning, "command appears slow")
        self.assertEqual(result.command, "time.sleep(10)")


# ======================================================================
# Module 7 — [DEBUG-xxx] tag mechanism (execution_guard.py)
# ======================================================================


class TestDebugTagRegistration(unittest.TestCase):
    """T3: ``register_debug_tag()`` + ``get_registered_debug_tags()``."""

    def setUp(self) -> None:
        clear_debug_tags()

    def tearDown(self) -> None:
        clear_debug_tags()

    def test_register_simple_tag(self) -> None:
        """Verify: registering ``MY_BUG`` stores it uppercase."""
        register_debug_tag("MY_BUG")
        self.assertIn("MY_BUG", get_registered_debug_tags())

    def test_register_strips_brackets(self) -> None:
        """Verify: ``[DEBUG-MY_BUG]`` is normalized to ``MY_BUG``."""
        register_debug_tag("[DEBUG-MY_BUG]")
        self.assertIn("MY_BUG", get_registered_debug_tags())

    def test_register_lowercase_normalized(self) -> None:
        """Verify: lowercase tag is stored uppercase."""
        register_debug_tag("my_bug")
        self.assertIn("MY_BUG", get_registered_debug_tags())

    def test_register_empty_tag_ignored(self) -> None:
        """Verify: empty tag is not registered."""
        register_debug_tag("")
        register_debug_tag("   ")
        self.assertEqual(len(get_registered_debug_tags()), 0)

    def test_clear_debug_tags(self) -> None:
        """Verify: ``clear_debug_tags()`` empties the registry."""
        register_debug_tag("A")
        register_debug_tag("B")
        self.assertEqual(len(get_registered_debug_tags()), 2)
        clear_debug_tags()
        self.assertEqual(len(get_registered_debug_tags()), 0)


class TestDebugTagCleanup(unittest.TestCase):
    """T4: ``cleanup_debug_tags()`` — find tags in output."""

    def test_find_single_tag(self) -> None:
        """Verify: single ``[DEBUG-XXX]`` in output is found."""
        output = "Running test...\n[DEBUG-OFF_BY_ONE] index=5\nDone."
        tags = cleanup_debug_tags(output)
        self.assertEqual(tags, ["OFF_BY_ONE"])

    def test_find_multiple_tags(self) -> None:
        """Verify: multiple distinct tags are found and sorted."""
        output = (
            "[DEBUG-ZERO_CHECK] value=0\n"
            "[DEBUG-NULL_PTR] ptr=None\n"
            "[DEBUG-OFF_BY_ONE] i=1\n"
        )
        tags = cleanup_debug_tags(output)
        self.assertEqual(tags, ["NULL_PTR", "OFF_BY_ONE", "ZERO_CHECK"])

    def test_find_tags_deduplicated(self) -> None:
        """Verify: duplicate tags are returned only once."""
        output = "[DEBUG-FOO] a=1\n[DEBUG-FOO] b=2\n[DEBUG-FOO] c=3\n"
        tags = cleanup_debug_tags(output)
        self.assertEqual(tags, ["FOO"])

    def test_empty_output_returns_empty(self) -> None:
        """Verify: empty or None output returns no tags."""
        self.assertEqual(cleanup_debug_tags(""), [])
        self.assertEqual(cleanup_debug_tags("no tags here"), [])

    def test_tags_with_numbers_and_underscores(self) -> None:
        """Verify: tags with numbers and underscores are matched."""
        output = "[DEBUG-BUG_123] x=42\n[DEBUG-FIX_V2] y=99"
        tags = cleanup_debug_tags(output)
        self.assertEqual(tags, ["BUG_123", "FIX_V2"])

    def test_lowercase_tags_not_matched(self) -> None:
        """Verify: ``[DEBUG-foo]`` (lowercase) is NOT matched."""
        output = "[DEBUG-foo] this should not match"
        tags = cleanup_debug_tags(output)
        self.assertEqual(tags, [])


class TestDebugTagStrip(unittest.TestCase):
    """T5: ``strip_debug_tags()`` — remove debug lines from output."""

    def test_strip_removes_debug_lines(self) -> None:
        """Verify: lines containing ``[DEBUG-xxx]`` are removed."""
        output = "Line 1\n[DEBUG-FOO] debug info\nLine 3"
        cleaned = strip_debug_tags(output)
        self.assertEqual(cleaned, "Line 1\nLine 3")

    def test_strip_preserves_non_debug_lines(self) -> None:
        """Verify: non-debug lines are preserved intact."""
        output = "Keep this\n[DEBUG-BAR] remove this\nKeep this too"
        cleaned = strip_debug_tags(output)
        self.assertIn("Keep this", cleaned)
        self.assertIn("Keep this too", cleaned)
        self.assertNotIn("[DEBUG-BAR]", cleaned)

    def test_strip_empty_output(self) -> None:
        """Verify: empty output returns empty."""
        self.assertEqual(strip_debug_tags(""), "")


# ======================================================================
# Module 7 — ExecutionGuard instance methods
# ======================================================================


class TestExecutionGuardDebugMethods(unittest.TestCase):
    """T6: ``ExecutionGuard.find_debug_tags()`` + ``remove_debug_lines()``."""

    def setUp(self) -> None:
        self.guard = ExecutionGuard()

    def test_find_debug_tags_via_instance(self) -> None:
        """Verify: instance method delegates to ``cleanup_debug_tags``."""
        output = "[DEBUG-ABC] test\n[DEBUG-XYZ] test2"
        tags = self.guard.find_debug_tags(output)
        self.assertEqual(tags, ["ABC", "XYZ"])

    def test_remove_debug_lines_via_instance(self) -> None:
        """Verify: instance method delegates to ``strip_debug_tags``."""
        output = "hello\n[DEBUG-REMOVE_ME] debug\nworld"
        cleaned = self.guard.remove_debug_lines(output)
        self.assertEqual(cleaned, "hello\nworld")


if __name__ == "__main__":
    unittest.main()
