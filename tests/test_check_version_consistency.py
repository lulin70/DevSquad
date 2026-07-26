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
    CONTENT_DIFF_PAIRS,
    PRD_DIR,
    PRD_FILENAME_VERSION_RE,
    ContentDiffSpec,
    _check_prd_files,
    check_content_diff,
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


# =============================================================================
# V4.3.1 enhancement: TRAE cache content diff checks
# =============================================================================


class T8_ContentDiffPairsConfig(unittest.TestCase):
    """T8: CONTENT_DIFF_PAIRS module-level configuration sanity."""

    def test_01_has_six_pairs(self) -> None:
        """Verify: 6 cache pairs (3 layers × 2 files: SKILL.md + skill-manifest.yaml)."""
        self.assertEqual(len(CONTENT_DIFF_PAIRS), 6)

    def test_02_all_pairs_optional(self) -> None:
        """Verify: All pairs optional=True (CI environments lack TRAE caches)."""
        for spec in CONTENT_DIFF_PAIRS:
            self.assertTrue(spec.optional, f"{spec.description} should be optional")

    def test_03_source_paths_are_known(self) -> None:
        """Verify: source_path is either SKILL.md or skill-manifest.yaml."""
        valid = {"SKILL.md", "skill-manifest.yaml"}
        for spec in CONTENT_DIFF_PAIRS:
            self.assertIn(spec.source_path, valid)

    def test_04_cache_paths_distinct(self) -> None:
        """Verify: All cache_path values are distinct (no duplicate checks)."""
        paths = [str(spec.cache_path) for spec in CONTENT_DIFF_PAIRS]
        self.assertEqual(len(paths), len(set(paths)))


class T9_CheckContentDiff_HappyPath(unittest.TestCase):
    """T9: check_content_diff returns PASS when cache is identical to source."""

    def test_01_identical_content_returns_pass(self) -> None:
        """Verify: Byte-identical cache → passed=True, found='identical'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "SKILL.md"
            cache = Path(tmpdir) / "cache_SKILL.md"
            content = "# DevSquad V4.3.1\n\nIdentical body.\n"
            source.write_text(content, encoding="utf-8")
            cache.write_text(content, encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test identical",
            )
            # Patch REPO_ROOT so source resolution uses tmpdir parent
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertTrue(result.passed, f"Expected PASS, got: {result.detail}")
            self.assertEqual(result.found, "identical")
            self.assertIn("identical to source", result.detail)


class T10_CheckContentDiff_Differs(unittest.TestCase):
    """T10: check_content_diff returns FAIL when cache content differs."""

    def test_01_different_content_returns_fail(self) -> None:
        """Verify: Different body → passed=False, found='differs', line info given."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "SKILL.md"
            cache = Path(tmpdir) / "cache_SKILL.md"
            source.write_text("line1\nline2\nline3\n", encoding="utf-8")
            cache.write_text("line1\nDIFFERENT\nline3\n", encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test differs",
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertFalse(result.passed)
            self.assertEqual(result.found, "differs")
            self.assertIn("first diff at line 2", result.detail)
            self.assertIn("source=3L", result.detail)
            self.assertIn("cache=3L", result.detail)

    def test_02_version_field_synced_but_body_differs_still_fails(self) -> None:
        """Verify: Catches V4.3.1 bug — version synced, body stale."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "SKILL.md"
            cache = Path(tmpdir) / "cache_SKILL.md"
            # Both have version: 4.3.1, but body differs (the actual V4.3.1 bug)
            source.write_text(
                "version: 4.3.1\nV4.3.1: BenchmarkRegressionChecker\n8110+ tests\n",
                encoding="utf-8",
            )
            cache.write_text(
                "version: 4.3.1\nV4.3.0: old description\n7660+ tests\n",
                encoding="utf-8",
            )
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test version-synced body-drift",
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertFalse(result.passed, "Body drift must FAIL even if version field is synced")
            self.assertEqual(result.found, "differs")
            self.assertIn("first diff at line 2", result.detail)

    def test_03_different_line_counts_reports_eof(self) -> None:
        """Verify: When cache is shorter, diff reports EOF marker."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "SKILL.md"
            cache = Path(tmpdir) / "cache_SKILL.md"
            source.write_text("line1\nline2\nline3\nline4\n", encoding="utf-8")
            cache.write_text("line1\nline2\n", encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test EOF",
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertFalse(result.passed)
            self.assertIn("first diff at line 3", result.detail)
            self.assertIn("source=4L", result.detail)
            self.assertIn("cache=2L", result.detail)


class T11_CheckContentDiff_MissingFiles(unittest.TestCase):
    """T11: check_content_diff handles missing files per optional flag."""

    def test_01_optional_missing_cache_returns_skip(self) -> None:
        """Verify: optional=True + missing cache → SKIP (passed=True)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "SKILL.md"
            source.write_text("content", encoding="utf-8")
            cache = Path(tmpdir) / "nonexistent_cache.md"
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test optional missing",
                optional=True,
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertTrue(result.passed)
            self.assertTrue(result.detail.startswith("SKIP"))

    def test_02_required_missing_cache_returns_fail(self) -> None:
        """Verify: optional=False + missing cache → FAIL."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "SKILL.md"
            source.write_text("content", encoding="utf-8")
            cache = Path(tmpdir) / "nonexistent_cache.md"
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test required missing",
                optional=False,
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertFalse(result.passed)
            self.assertIn("cache file missing", result.detail)

    def test_03_missing_source_returns_fail(self) -> None:
        """Verify: Missing source file → FAIL (regardless of optional)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent_source = Path(tmpdir) / "nonexistent_source.md"
            cache = Path(tmpdir) / "cache.md"
            cache.write_text("content", encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(nonexistent_source),
                cache_path=cache,
                description="test missing source",
                optional=True,
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertFalse(result.passed)
            self.assertIn("source file missing", result.detail)


class T12_CheckContentDiff_Boundary(unittest.TestCase):
    """T12: Boundary cases — empty files, single-line files."""

    def test_01_both_empty_files_identical(self) -> None:
        """Verify: Two empty files are considered identical."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "empty.md"
            cache = Path(tmpdir) / "empty_cache.md"
            source.write_text("", encoding="utf-8")
            cache.write_text("", encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test empty",
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertTrue(result.passed)
            self.assertEqual(result.found, "identical")

    def test_02_single_line_identical(self) -> None:
        """Verify: Single-line identical content passes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "one.md"
            cache = Path(tmpdir) / "one_cache.md"
            source.write_text("only line", encoding="utf-8")
            cache.write_text("only line", encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test single",
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertTrue(result.passed)

    def test_03_source_empty_cache_not_empty_fails(self) -> None:
        """Verify: Empty source + non-empty cache → FAIL at line 1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            source = Path(tmpdir) / "empty.md"
            cache = Path(tmpdir) / "nonempty_cache.md"
            source.write_text("", encoding="utf-8")
            cache.write_text("cache has content", encoding="utf-8")
            spec = ContentDiffSpec(
                source_path=str(source),
                cache_path=cache,
                description="test empty source",
            )
            import scripts.check_version_consistency as mod
            with mock.patch.object(mod, "REPO_ROOT", Path(tmpdir)):
                result = check_content_diff(spec)
            self.assertFalse(result.passed)
            self.assertIn("first diff at line 1", result.detail)


class T13_MainIntegrationContentDiff(unittest.TestCase):
    """T13: main() integrates content diff checks into the report."""

    def test_01_main_runs_content_diff_by_default(self) -> None:
        """Verify: main() runs content diff checks and includes them in totals."""
        import io
        captured = io.StringIO()
        with mock.patch("sys.stdout", new_callable=lambda: captured), \
             mock.patch("sys.argv", ["prog"]):
            exit_code = main()
        output = captured.getvalue()
        self.assertIn("Content diff checks", output)
        self.assertIn(exit_code, (0, 1))

    def test_02_main_no_content_diff_flag_skips_diff(self) -> None:
        """Verify: --no-content-diff flag skips the diff section entirely."""
        import io
        captured = io.StringIO()
        with mock.patch("sys.stdout", new_callable=lambda: captured), \
             mock.patch("sys.argv", ["prog", "--no-content-diff"]):
            exit_code = main()
        output = captured.getvalue()
        self.assertNotIn("Content diff checks", output)
        self.assertIn(exit_code, (0, 1))

    def test_03_main_includes_content_diff_section_in_output(self) -> None:
        """Verify: Output contains 'Content diff checks' header by default."""
        import io
        captured = io.StringIO()
        with mock.patch("sys.stdout", new_callable=lambda: captured), \
             mock.patch("sys.argv", ["prog"]):
            exit_code = main()
        output = captured.getvalue()
        self.assertIn("Content diff checks", output)
        self.assertIn(exit_code, (0, 1))


if __name__ == "__main__":
    unittest.main()
