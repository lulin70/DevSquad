#!/usr/bin/env python3
"""Tests for check_version_consistency.py (V4.2.1 P2-11) — PRD linkage.

Covers the P2-11 enhancement: ``_check_prd_files()`` scans ``docs/prd/*.md``
and verifies that each PRD's filename version (e.g., ``V3.9`` → ``3.9``)
appears in the file content. Mismatches are non-blocking WARN-level.

Coverage dimensions (per DevSquad Iron Rule 3):
  - Happy Path: PRD with matching version in content → PASS
  - Error Case: PRD with mismatched version → WARN (non-blocking)
  - Boundary: empty PRD dir, non-versioned filename, missing PRD dir
  - Configuration: --strict mode promotes WARN to FAIL
  - Integration: main() incorporates PRD results into totals
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.check_version_consistency import (
    PRD_DIR,
    PRD_FILENAME_VERSION_RE,
    _check_prd_files,
    main,
)


class T1_FilenameVersionRegex(unittest.TestCase):
    """T1: PRD_FILENAME_VERSION_RE extracts version from filename."""

    def test_01_matches_v3_9_format(self) -> None:
        """Verify: V3.9_PRD_Code_Intelligence.md → '3.9'."""
        m = PRD_FILENAME_VERSION_RE.match("V3.9_PRD_Code_Intelligence.md")
        self.assertIsNotNone(m)
        assert m is not None  # for mypy
        self.assertEqual(m.group(1), "3.9")

    def test_02_matches_v4_1_0_format(self) -> None:
        """Verify: V4.1.0_PRD_Consensus_Record.md → '4.1.0'."""
        m = PRD_FILENAME_VERSION_RE.match("V4.1.0_PRD_Consensus_Record.md")
        self.assertIsNotNone(m)
        assert m is not None
        self.assertEqual(m.group(1), "4.1.0")

    def test_03_rejects_non_versioned_filename(self) -> None:
        """Verify: README.md (no V prefix) → no match."""
        self.assertIsNone(PRD_FILENAME_VERSION_RE.match("README.md"))

    def test_04_rejects_lowercase_v(self) -> None:
        """Verify: lowercase 'v' prefix is rejected (spec requires uppercase V)."""
        # PRD convention is uppercase V; lowercase should not match to avoid
        # false positives on files like "version_notes.md".
        self.assertIsNone(PRD_FILENAME_VERSION_RE.match("v3.9_notes.md"))


class T2_CheckPrdFiles_HappyPath(unittest.TestCase):
    """T2: _check_prd_files() with matching version in content."""

    def test_01_returns_pass_when_version_in_content(self) -> None:
        """Verify: PRD with filename version in content → PASS result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD_Test.md"
            prd_file.write_text("# V3.9 PRD\n\nContent referencing V3.9.", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].passed)
            self.assertEqual(results[0].expected, "3.9")
            self.assertEqual(results[0].found, "3.9")
            self.assertNotIn("WARN", results[0].detail)

    def test_02_handles_multiple_prd_files(self) -> None:
        """Verify: Multiple PRD files each produce a result."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            (tmp_prd_dir / "V3.9_A.md").write_text("Version V3.9 here.", encoding="utf-8")
            (tmp_prd_dir / "V4.1.0_B.md").write_text("Version V4.1.0 here.", encoding="utf-8")
            (tmp_prd_dir / "V4.2.1_C.md").write_text("Version V4.2.1 here.", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 3)

    def test_03_v_prefixed_version_matches(self) -> None:
        """Verify: 'V3.9' in content satisfies check for filename 'V3.9'."""
        # This is the core P2-11 bug fix: \b fails between V and 3 (both \w),
        # so the scanner must use (?<!\d) lookbehind instead.
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD_Test.md"
            # Content only has "V3.9" (not bare "3.9")
            prd_file.write_text("# DevSquad V3.9 PRD\n\nTarget version V3.9.0", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].passed, f"Should PASS but got: {results[0].detail}")


class T3_CheckPrdFiles_WarnCases(unittest.TestCase):
    """T3: _check_prd_files() warns on filename/content drift."""

    def test_01_returns_warn_when_version_missing_from_content(self) -> None:
        """Verify: PRD content without filename version → WARN (non-blocking)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD_Test.md"
            # Content references V4.2 but filename says V3.9 → drift
            prd_file.write_text("# PRD\n\nUpdated to V4.2.1 content.", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            # WARN is non-blocking: passed=True but detail starts with "WARN"
            self.assertTrue(results[0].passed, "WARN should be non-blocking (passed=True)")
            self.assertTrue(results[0].detail.startswith("WARN"))
            self.assertIsNone(results[0].found)

    def test_02_warn_does_not_fail_ci(self) -> None:
        """Verify: WARN result has passed=True so it doesn't count as failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            (tmp_prd_dir / "V3.9_Drift.md").write_text("No version here.", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            # All results pass (WARN is non-blocking)
            self.assertTrue(all(r.passed for r in results))


class T4_CheckPrdFiles_Boundary(unittest.TestCase):
    """T4: _check_prd_files() boundary conditions."""

    def test_01_empty_prd_directory(self) -> None:
        """Verify: Empty docs/prd/ → empty results list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(results, [])

    def test_02_nonexistent_prd_directory(self) -> None:
        """Verify: Missing docs/prd/ → empty results list (no crash)."""
        with mock.patch.object(
            __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
            "PRD_DIR",
            Path("/nonexistent/path/that/does/not/exist"),
        ):
            results = _check_prd_files()
        self.assertEqual(results, [])

    def test_03_skips_non_versioned_files(self) -> None:
        """Verify: Files without V-prefix version are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            # Non-versioned files should be skipped
            (tmp_prd_dir / "README.md").write_text("some content", encoding="utf-8")
            (tmp_prd_dir / "notes.txt").write_text("notes", encoding="utf-8")
            # Only this one should be checked
            (tmp_prd_dir / "V3.9_PRD.md").write_text("V3.9 content", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertIn("V3.9_PRD.md", results[0].file)

    def test_04_only_md_files_processed(self) -> None:
        """Verify: Non-.md files in docs/prd/ are skipped."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            (tmp_prd_dir / "V3.9_PRD.md").write_text("V3.9 content", encoding="utf-8")
            (tmp_prd_dir / "V3.9_notes.txt").write_text("V3.9 content", encoding="utf-8")
            (tmp_prd_dir / "V3.9_data.json").write_text('{"v": "3.9"}', encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)

    def test_05_unreadable_file_returns_skip(self) -> None:
        """Verify: Unreadable PRD file → SKIP result (non-blocking)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD.md"
            prd_file.write_text("V3.9 content", encoding="utf-8")
            # Mock read_text to raise OSError
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ), mock.patch.object(
                Path, "read_text", side_effect=OSError("permission denied")
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].passed)  # SKIP is non-blocking
            self.assertTrue(results[0].detail.startswith("SKIP"))


class T5_CheckPrdFiles_DigitBoundary(unittest.TestCase):
    """T5: Digit boundary regex prevents false positives."""

    def test_01_rejects_version_in_larger_number(self) -> None:
        """Verify: '3.9' in '13.9' should NOT match (digit prefix)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD.md"
            # '13.9' contains '3.9' but should not match (digit prefix)
            prd_file.write_text("Measurement: 13.9 units", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].detail.startswith("WARN"),
                            f"Should WARN on 13.9 false positive but got: {results[0].detail}")

    def test_02_rejects_version_with_trailing_digit(self) -> None:
        """Verify: '3.9' in '3.91' should NOT match (digit suffix)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD.md"
            prd_file.write_text("Build 3.91 was released", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].detail.startswith("WARN"))

    def test_03_accepts_version_with_trailing_dot(self) -> None:
        """Verify: '3.9' in 'V3.9.0' should match (dot is not a digit)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            prd_file = tmp_prd_dir / "V3.9_PRD.md"
            prd_file.write_text("Target: V3.9.0", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ):
                results = _check_prd_files()
            self.assertEqual(len(results), 1)
            self.assertTrue(results[0].passed, f"Should PASS but got: {results[0].detail}")


class T6_MainIntegration(unittest.TestCase):
    """T6: main() integrates PRD checks into overall results."""

    def test_01_main_returns_zero_with_prd_pass(self) -> None:
        """Verify: main() exits 0 when all PRD files pass."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            (tmp_prd_dir / "V3.9_PRD.md").write_text("V3.9 content", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ), mock.patch("sys.argv", ["check_version_consistency.py"]):
                exit_code = main()
            self.assertEqual(exit_code, 0)

    def test_02_main_returns_zero_with_prd_warn(self) -> None:
        """Verify: main() exits 0 even with PRD WARN (non-blocking)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            # WARN: content doesn't match filename version
            (tmp_prd_dir / "V3.9_Drift.md").write_text("No version here", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ), mock.patch("sys.argv", ["check_version_consistency.py"]):
                exit_code = main()
            # WARN is non-blocking, so exit code should be 0
            self.assertEqual(exit_code, 0)

    def test_03_main_strict_mode_fails_on_warn(self) -> None:
        """Verify: --strict mode promotes WARN to failure (exit 1)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_prd_dir = Path(tmpdir) / "prd"
            tmp_prd_dir.mkdir()
            (tmp_prd_dir / "V3.9_Drift.md").write_text("No version here", encoding="utf-8")
            with mock.patch.object(
                __import__("scripts.check_version_consistency", fromlist=["PRD_DIR"]),
                "PRD_DIR",
                tmp_prd_dir,
            ), mock.patch("sys.argv", ["check_version_consistency.py", "--strict"]):
                exit_code = main()
            self.assertEqual(exit_code, 1)


class T7_RealPrdFiles(unittest.TestCase):
    """T7: Integration test against real docs/prd/ files (if present)."""

    def test_01_real_prd_files_pass_or_warn(self) -> None:
        """Verify: Real PRD files produce only PASS or WARN (no FAIL/crash)."""
        if not PRD_DIR.exists():
            self.skipTest("docs/prd/ does not exist in this environment")
        results = _check_prd_files()
        # Should produce results for V-prefixed files
        self.assertGreater(len(results), 0, "Expected at least one PRD file in docs/prd/")
        # All results should be non-blocking (passed=True)
        for r in results:
            self.assertTrue(r.passed, f"PRD check should not block CI: {r.file} → {r.detail}")


if __name__ == "__main__":
    unittest.main()
