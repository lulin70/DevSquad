#!/usr/bin/env python3
"""Unit tests for V4.4.3 check_doc_consistency.py — CI documentation gate.

Iron Rules applied:
  1. Documentation-first: source (scripts/check_doc_consistency.py) read first.
     Documented: scans DOC_FILES for ``NNNN+ tests`` / ``NNN+ modules`` claims,
     returns Violations for any minority claim, ``main()`` exits 1 on violation.
  2. Failure-means-report: real regex engine + real temp files, no Mock.
  3. Dimension-completeness: 6 tests across Happy/Error/Boundary/Config/Side-Effect.
  4. Side-effect-verification: ``main()`` exit code (0 vs 1) verified.
  5. User-journey-first: mirrors the CI gate journey (PR blocked on inconsistency).
  6. e2e-release-gate: this IS the release-gate module under test.

Testing strategy: the check functions read the module-level ``DOC_FILES`` global
(relative doc paths). We point ``DOC_FILES`` at temp files we control so tests
are deterministic and independent of the live repo's doc state (the live repo
must already be consistent for CI to pass — we verify our own crafted states).
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts import check_doc_consistency as cdc_module  # noqa: E402
from scripts.check_doc_consistency import (  # noqa: E402
    check_module_count_consistency,
    check_test_count_consistency,
    main,
)


class TestCheckDocConsistency(unittest.TestCase):
    """V4.4.3 check_doc_consistency unit tests (6 tests)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="devsquad_cdc_")
        self._original_doc_files = cdc_module.DOC_FILES

    def tearDown(self) -> None:
        cdc_module.DOC_FILES = self._original_doc_files
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_doc(self, name: str, content: str) -> str:
        """Write a temp doc file and return its absolute path."""
        path = Path(self._tmpdir) / name
        path.write_text(content, encoding="utf-8")
        return str(path)

    def _set_doc_files(self, *paths: str) -> None:
        cdc_module.DOC_FILES = list(paths)

    # ------------------------------------------------------------------
    # Happy: consistency
    # ------------------------------------------------------------------

    def test_consistent_claims_zero_violations(self) -> None:
        """Happy: all docs agree on test count and module count -> 0 violations."""
        d1 = self._write_doc("README.md", "DevSquad has 8200+ tests and 185+ modules.")
        d2 = self._write_doc("SKILL.md", "Status: 8200+ CI tests passing; 185+ core modules.")
        self._set_doc_files(d1, d2)

        self.assertEqual(check_test_count_consistency(), [])
        self.assertEqual(check_module_count_consistency(), [])

    def test_missing_claim_is_consistent(self) -> None:
        """Boundary: a doc with NO count claim does not cause a violation.

        The V4.4.2 issue was *contradictory* claims, not absent claims — a doc
        that simply doesn't state a count must not trigger the gate.
        """
        d1 = self._write_doc("README.md", "DevSquad has 8200+ tests and 185+ modules.")
        d2 = self._write_doc("INSTALL.md", "Install with pip. No counts mentioned here.")
        d3 = self._write_doc("CHANGELOG.md", "Bug fixes only. Nothing about tests or modules.")
        self._set_doc_files(d1, d2, d3)

        # Only one doc makes each claim -> all_values size 1 -> consistent.
        self.assertEqual(check_test_count_consistency(), [])
        self.assertEqual(check_module_count_consistency(), [])

    # ------------------------------------------------------------------
    # Error: inconsistency
    # ------------------------------------------------------------------

    def test_inconsistent_test_count(self) -> None:
        """Error: two different 'NNNN+ tests' claims produce a Violation."""
        d1 = self._write_doc("README.md", "We have 8200+ tests.\nAlso 8200+ CI tests again.")
        d2 = self._write_doc("SKILL.md", "We have 9000+ tests now.")
        self._set_doc_files(d1, d2)

        violations = check_test_count_consistency()
        self.assertEqual(len(violations), 1)
        v = violations[0]
        self.assertEqual(v.claim, "9000+ tests")
        self.assertEqual(v.expected, "8200+ tests")
        self.assertEqual(v.doc_file, d2)

    def test_inconsistent_module_count(self) -> None:
        """Error: two different 'NNN+ modules' claims produce a Violation."""
        d1 = self._write_doc("README.md", "185+ modules.\n185+ core modules again.")
        d2 = self._write_doc("CLAUDE.md", "Now 200+ modules.")
        self._set_doc_files(d1, d2)

        violations = check_module_count_consistency()
        self.assertEqual(len(violations), 1)
        self.assertEqual(violations[0].claim, "200+ modules")
        self.assertEqual(violations[0].expected, "185+ modules")

    def test_multiple_violations(self) -> None:
        """Error: several minority claims across several docs produce several Violations."""
        d1 = self._write_doc("README.md", "8200+ tests.\n8200+ CI tests.")  # majority (2x)
        d2 = self._write_doc("SKILL.md", "9000+ tests.")  # minority
        d3 = self._write_doc("CLAUDE.md", "7000+ tests.")  # minority
        self._set_doc_files(d1, d2, d3)

        violations = check_test_count_consistency()
        self.assertEqual(len(violations), 2)
        claims = {v.claim for v in violations}
        self.assertEqual(claims, {"9000+ tests", "7000+ tests"})
        # Majority (8200) is never reported as a violation.
        self.assertNotIn("8200+ tests", claims)

    # ------------------------------------------------------------------
    # Config / Side-Effect: CI exit code
    # ------------------------------------------------------------------

    def test_main_exit_code(self) -> None:
        """Config/Side-Effect: main() returns 0 when consistent, 1 when inconsistent."""
        # Consistent state -> exit 0.
        d_ok1 = self._write_doc("README.md", "8200+ tests, 185+ modules.")
        d_ok2 = self._write_doc("SKILL.md", "8200+ CI tests, 185+ core modules.")
        self._set_doc_files(d_ok1, d_ok2)
        self.assertEqual(main(), 0)

        # Inconsistent state -> exit 1 (CI must block).
        d_bad = self._write_doc("CLAUDE.md", "9000+ tests, 200+ modules.")
        self._set_doc_files(d_ok1, d_bad)
        self.assertEqual(main(), 1)


if __name__ == "__main__":
    unittest.main()
