#!/usr/bin/env python3
"""V4.2.1 P1-17: Test Quality CI Gate.

Scans all test files for weak assertions and anti-patterns using
AntiPatternDetector from TestQualityGuard. Fails CI on MAJOR severity
issues (bare except, missing error tests). Reports MINOR/INFO as warnings.

Usage:
    python scripts/check_test_quality.py [--source tests/] [--fail-on major]

Exit codes:
    0 = no MAJOR issues found (MINOR/INFO warnings may exist)
    1 = one or more MAJOR issues found
    2 = script error
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Import from the collaboration module.
sys.path.insert(0, str(REPO_ROOT / "scripts"))
from collaboration.test_quality_guard import (  # noqa: E402
    AntiPatternDetector,
    QualityIssue,
    Severity,
)


def scan_test_file(detector: AntiPatternDetector, test_file: Path) -> list[QualityIssue]:
    """Scan a single test file and return anti-pattern issues.

    Lines containing ``# noqa: test-quality`` are skipped (false positive
    suppression, e.g., string literals that contain anti-pattern text as
    test fixtures for the detector itself).

    Args:
        detector: AntiPatternDetector instance.
        test_file: Path to the test file to scan.

    Returns:
        List of QualityIssue found in the file.
    """
    try:
        source = test_file.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  WARN: cannot read {test_file}: {exc}", file=sys.stderr)
        return []
    issues = detector.detect_in_source(source, str(test_file))
    # Filter out noqa-suppressed issues.
    return [i for i in issues if not _is_noqa_suppressed(source, i.line)]


def _is_noqa_suppressed(source: str, line_no: int) -> bool:
    """Check if a line has a ``# noqa: test-quality`` suppression comment.

    Args:
        source: Full source code text.
        line_no: 1-based line number to check.

    Returns:
        True if the line contains the suppression comment.
    """
    lines = source.split("\n")
    if 1 <= line_no <= len(lines):
        return "# noqa: test-quality" in lines[line_no - 1]
    return False


def format_issue(issue: QualityIssue) -> str:
    """Format a single issue for display.

    Args:
        issue: QualityIssue to format.

    Returns:
        Human-readable string with severity, file, line, and message.
    """
    return (
        f"  [{issue.severity.value.upper():6s}] {issue.file}:{issue.line} "
        f"[{issue.id}] {issue.message}"
    )


def _report_issues(
    major: list[QualityIssue],
    minor: list[QualityIssue],
    info: list[QualityIssue],
    test_count: int,
    source_dir: Path,
    fail_threshold: int,
) -> None:
    """Print the test quality report to stdout.

    Args:
        major: MAJOR severity issues.
        minor: MINOR severity issues.
        info: INFO severity issues.
        test_count: Number of test files scanned.
        source_dir: Directory that was scanned.
        fail_threshold: Severity rank threshold for CI blocking.
    """
    print("Test Quality Report (V4.2.1 P1-17)")
    print(f"  Scanned: {test_count} test files in {source_dir}")
    print(f"  Issues:  {len(major)} MAJOR / {len(minor)} MINOR / {len(info)} INFO")
    print("-" * 70)

    if major:
        print("\nMAJOR issues (CI-blocking):")
        for issue in major:
            print(format_issue(issue))

    if minor:
        label = "CI-blocking" if fail_threshold <= 1 else "warnings"
        print(f"\nMINOR issues ({label}):")
        for issue in minor:
            print(format_issue(issue))

    if info:
        label = "CI-blocking" if fail_threshold <= 0 else "warnings"
        print(f"\nINFO issues ({label}):")
        for issue in info:
            print(format_issue(issue))

    print("-" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test quality CI gate — detects weak assertions and anti-patterns."
    )
    parser.add_argument(
        "--source",
        default=str(REPO_ROOT / "tests"),
        help="Directory containing test files (default: tests/)",
    )
    parser.add_argument(
        "--fail-on",
        choices=["major", "minor", "info"],
        default="major",
        help="Minimum severity to fail CI (default: major)",
    )
    args = parser.parse_args()

    source_dir = Path(args.source)
    if not source_dir.is_dir():
        print(f"ERROR: source directory not found: {source_dir}")
        return 2

    test_files = sorted(source_dir.glob("test_*.py"))
    if not test_files:
        print(f"OK: no test files found in {source_dir}")
        return 0

    detector = AntiPatternDetector()
    fail_rank = {"info": 0, "minor": 1, "major": 2}
    fail_threshold = fail_rank[args.fail_on]

    all_issues: list[QualityIssue] = []
    for test_file in test_files:
        all_issues.extend(scan_test_file(detector, test_file))

    major = [i for i in all_issues if i.severity == Severity.MAJOR]
    minor = [i for i in all_issues if i.severity == Severity.MINOR]
    info = [i for i in all_issues if i.severity == Severity.INFO]

    _report_issues(major, minor, info, len(test_files), source_dir, fail_threshold)

    blocking = [i for i in all_issues if fail_rank.get(i.severity.value, 0) >= fail_threshold]
    if blocking:
        print(f"\nFAIL: {len(blocking)} issue(s) at or above {args.fail_on.upper()} severity")
        return 1

    print(f"\nOK: no issues at or above {args.fail_on.upper()} severity")
    return 0


if __name__ == "__main__":
    sys.exit(main())
