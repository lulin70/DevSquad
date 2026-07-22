"""Tests for V4.2.1 P1-17 Test Quality CI Gate script.

Tests the check_test_quality.py CLI script that scans test files for
weak assertions and anti-patterns using AntiPatternDetector.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "scripts" / "check_test_quality.py"


def _run_script(*args: str) -> tuple[int, str, str]:
    """Run check_test_quality.py with given args and return (exit_code, stdout, stderr).

    Args:
        *args: Command-line arguments to pass to the script.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    cmd = [sys.executable, str(SCRIPT_PATH), *args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    return result.returncode, result.stdout, result.stderr


class TestScanTestFile:
    """Test the scan_test_file function directly."""

    def test_scan_finds_bare_except(self, tmp_path: Path) -> None:
        """Verify: scan_test_file detects bare except in a test file.

        Scenario: A test file containing a bare except clause.
        Expected: AntiPatternDetector returns at least one MAJOR issue.
        """
        from scripts.check_test_quality import scan_test_file
        from scripts.collaboration.test_quality_guard import AntiPatternDetector

        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            "def test_foo():\n"
            "    try:\n"
            "        x = 1\n"
            "    except:\n"  # noqa: test-quality — bare except fixture string, not real code
            "        pass\n"
        )
        detector = AntiPatternDetector()
        issues = scan_test_file(detector, test_file)
        major_issues = [i for i in issues if i.severity.value == "major"]
        assert len(major_issues) >= 1, f"Expected at least 1 MAJOR issue, got {len(major_issues)}"

    def test_scan_finds_loose_assert(self, tmp_path: Path) -> None:
        """Verify: scan_test_file detects assertTrue as MINOR.

        Scenario: A test file using assertTrue instead of assertEqual.
        Expected: AntiPatternDetector returns at least one MINOR issue.
        """
        from scripts.check_test_quality import scan_test_file
        from scripts.collaboration.test_quality_guard import AntiPatternDetector

        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            "def test_foo():\n"
            "    result = True\n"
            "    self.assertTrue(result)\n"
        )
        detector = AntiPatternDetector()
        issues = scan_test_file(detector, test_file)
        minor_issues = [i for i in issues if i.severity.value == "minor"]
        assert len(minor_issues) >= 1, f"Expected at least 1 MINOR issue, got {len(minor_issues)}"

    def test_scan_noqa_suppression(self, tmp_path: Path) -> None:
        """Verify: lines with # noqa: test-quality are skipped.

        Scenario: A test file with bare except in a string literal
        marked with # noqa: test-quality.
        Expected: No MAJOR issues returned (suppressed).
        """
        from scripts.check_test_quality import scan_test_file
        from scripts.collaboration.test_quality_guard import AntiPatternDetector

        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            'def test_foo():\n'
            '    code = "except:"  # noqa: test-quality\n'
            '    pass\n'
        )
        detector = AntiPatternDetector()
        issues = scan_test_file(detector, test_file)
        major_issues = [i for i in issues if i.severity.value == "major"]
        assert len(major_issues) == 0, f"Expected 0 MAJOR issues with noqa, got {len(major_issues)}"

    def test_scan_clean_file_no_issues(self, tmp_path: Path) -> None:
        """Verify: a clean test file returns no issues.

        Scenario: A test file with no anti-patterns.
        Expected: Empty issue list.
        """
        from scripts.check_test_quality import scan_test_file
        from scripts.collaboration.test_quality_guard import AntiPatternDetector

        test_file = tmp_path / "test_example.py"
        test_file.write_text(
            "def test_foo():\n"
            "    result = 42\n"
            "    assert result == 42\n"
        )
        detector = AntiPatternDetector()
        issues = scan_test_file(detector, test_file)
        assert len(issues) == 0, f"Expected 0 issues for clean file, got {len(issues)}"

    def test_scan_unreadable_file_returns_empty(self, tmp_path: Path) -> None:
        """Verify: scan_test_file handles unreadable files gracefully.

        Scenario: A file that cannot be read (permission denied).
        Expected: Empty list returned, no exception raised.
        """
        from scripts.check_test_quality import scan_test_file
        from scripts.collaboration.test_quality_guard import AntiPatternDetector

        test_file = tmp_path / "nonexistent.py"
        # File doesn't exist — scan_test_file should handle OSError.
        detector = AntiPatternDetector()
        issues = scan_test_file(detector, test_file)
        assert issues == []


class TestNoqaSuppression:
    """Test the _is_noqa_suppressed helper function."""

    def test_noqa_present(self) -> None:
        """Verify: _is_noqa_suppressed returns True when comment present."""
        from scripts.check_test_quality import _is_noqa_suppressed

        source = 'code = "except:"  # noqa: test-quality\n'
        assert _is_noqa_suppressed(source, 1) is True

    def test_noqa_absent(self) -> None:
        """Verify: _is_noqa_suppressed returns False when comment absent."""
        from scripts.check_test_quality import _is_noqa_suppressed

        source = 'code = "except:"\n'  # noqa: test-quality — fixture string, not real code
        assert _is_noqa_suppressed(source, 1) is False

    def test_noqa_wrong_line(self) -> None:
        """Verify: _is_noqa_suppressed only checks the specified line."""
        from scripts.check_test_quality import _is_noqa_suppressed

        source = 'code = "except:"\nother = "except:"  # noqa: test-quality\n'
        assert _is_noqa_suppressed(source, 1) is False
        assert _is_noqa_suppressed(source, 2) is True

    def test_noqa_line_out_of_range(self) -> None:
        """Verify: _is_noqa_suppressed handles out-of-range line numbers."""
        from scripts.check_test_quality import _is_noqa_suppressed

        source = "line1\nline2\n"
        assert _is_noqa_suppressed(source, 0) is False
        assert _is_noqa_suppressed(source, 99) is False


class TestScriptCLI:
    """Test the script's CLI behavior via subprocess."""

    def test_script_runs_on_tests_directory(self) -> None:
        """Verify: script runs successfully on the tests/ directory.

        Scenario: Running the script against the real tests/ directory.
        Expected: Exit code 0 (no MAJOR issues after noqa suppressions).
        """
        exit_code, stdout, _ = _run_script("--source", str(REPO_ROOT / "tests"))
        assert exit_code == 0, f"Expected exit 0, got {exit_code}\nstdout: {stdout}"
        assert "Test Quality Report" in stdout

    def test_script_empty_directory_exits_zero(self, tmp_path: Path) -> None:
        """Verify: script exits 0 when no test files found.

        Scenario: An empty directory with no test files.
        Expected: Exit code 0 with "no test files found" message.
        """
        exit_code, stdout, _ = _run_script("--source", str(tmp_path))
        assert exit_code == 0
        assert "no test files" in stdout

    def test_script_nonexistent_directory_exits_two(self, tmp_path: Path) -> None:
        """Verify: script exits 2 when source directory doesn't exist.

        Scenario: A path that doesn't exist.
        Expected: Exit code 2 with error message.
        """
        bogus = tmp_path / "nonexistent"
        exit_code, stdout, _ = _run_script("--source", str(bogus))
        assert exit_code == 2
        assert "not found" in stdout

    def test_script_fails_on_major(self, tmp_path: Path) -> None:
        """Verify: script exits 1 when MAJOR issues are found.

        Scenario: A directory with a test file containing bare except.
        Expected: Exit code 1 (MAJOR severity, default --fail-on major).
        """
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_bad.py").write_text(
            "def test_foo():\n"
            "    try:\n"
            "        x = 1\n"
            "    except:\n"  # noqa: test-quality — test fixture, not real code
            "        pass\n"
        )
        exit_code, stdout, _ = _run_script("--source", str(test_dir))
        assert exit_code == 1
        assert "MAJOR" in stdout
        assert "FAIL" in stdout

    def test_script_passes_with_only_minor(self, tmp_path: Path) -> None:
        """Verify: script exits 0 when only MINOR issues exist.

        Scenario: A test file with assertTrue but no bare except.
        Expected: Exit code 0 (MINOR doesn't meet MAJOR threshold).
        """
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_minor.py").write_text(
            "def test_foo():\n"
            "    result = True\n"
            "    self.assertTrue(result)\n"
        )
        exit_code, stdout, _ = _run_script("--source", str(test_dir))
        assert exit_code == 0
        assert "MINOR" in stdout

    def test_script_fail_on_minor(self, tmp_path: Path) -> None:
        """Verify: --fail-on minor causes exit 1 for MINOR issues.

        Scenario: A test file with assertTrue, using --fail-on minor.
        Expected: Exit code 1 (MINOR meets the minor threshold).
        """
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_minor.py").write_text(
            "def test_foo():\n"
            "    result = True\n"
            "    self.assertTrue(result)\n"
        )
        exit_code, _, _ = _run_script("--source", str(test_dir), "--fail-on", "minor")
        assert exit_code == 1

    def test_script_noqa_suppresses_major(self, tmp_path: Path) -> None:
        """Verify: # noqa: test-quality suppresses MAJOR false positives.

        Scenario: A test file with bare except in a string literal
        marked with # noqa: test-quality.
        Expected: Exit code 0 (MAJOR suppressed).
        """
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        (test_dir / "test_suppressed.py").write_text(
            'def test_foo():\n'
            '    code = "except:"  # noqa: test-quality\n'
            '    pass\n'
        )
        exit_code, stdout, _ = _run_script("--source", str(test_dir))
        assert exit_code == 0
        # The MAJOR issue should not appear in output.
        assert "MAJOR" not in stdout or "0 MAJOR" in stdout
