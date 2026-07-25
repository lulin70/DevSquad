#!/usr/bin/env python3
"""V4.2.0 P0-20: Async Coverage Detector.

Scans source directories for ``async def`` functions and checks whether
they have corresponding async tests. Reports uncovered async functions
to prevent "0% async coverage" blind spots — a key risk area since
async code paths are often untested.

V4.1.2 Phase 3.1 enhancements:
- ``CoverageReport.markdown_report`` field (backward-compatible default ``""``)
- ``generate_markdown(report)`` API for Markdown rendering
- ``check_with_threshold(source_dir, test_dir, min_coverage_percent, ignore)``
  returns ``(report, passed)`` and populates ``report.markdown_report``
- CLI ``--min-coverage`` and ``--ignore`` flags

Usage::

    python scripts/check_async_coverage.py
    python scripts/check_async_coverage.py --source scripts/collaboration --tests tests
    python scripts/check_async_coverage.py --json  # machine-readable output
    python scripts/check_async_coverage.py --min-coverage 80 --ignore _private_func

Exit codes:
    0: All async functions covered (or no async functions found)
    1: Some async functions uncovered (warnings only, non-blocking in CI)
    2: Invalid arguments
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class AsyncFunction:
    """An async function found in source code."""

    name: str
    file: Path
    line: int
    is_private: bool = False


@dataclass
class CoverageReport:
    """Result of async coverage analysis.

    Attributes:
        total: Total number of async functions considered.
        covered: Names of async functions referenced in tests.
        uncovered: AsyncFunction objects without test references.
        coverage_percent: Percentage of covered async functions (0.0–100.0).
        source_dir: Source directory string used for Markdown rendering.
        test_dir: Test directory string used for Markdown rendering.
        markdown_report: Cached Markdown report (populated by
            ``check_with_threshold``; empty string by default for backward
            compatibility with callers that only inspect ``to_dict()``).
    """

    total: int = 0
    covered: list[str] = field(default_factory=list)
    uncovered: list[AsyncFunction] = field(default_factory=list)
    coverage_percent: float = 0.0
    source_dir: str = ""
    test_dir: str = ""
    markdown_report: str = ""

    def to_dict(self) -> dict:
        return {
            "total_async_functions": self.total,
            "covered_count": len(self.covered),
            "uncovered_count": len(self.uncovered),
            "coverage_percent": round(self.coverage_percent, 1),
            "uncovered": [
                {"name": f.name, "file": str(f.file), "line": f.line}
                for f in self.uncovered
            ],
        }


def extract_async_functions(source_dir: Path) -> list[AsyncFunction]:
    """Extract all ``async def`` functions from Python files in source_dir.

    Args:
        source_dir: Directory to scan recursively for .py files.

    Returns:
        List of AsyncFunction objects (including private functions).
    """
    functions: list[AsyncFunction] = []
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef)):
                # Only async functions
                if not isinstance(node, ast.AsyncFunctionDef):
                    continue
                # Skip __dunder__ methods (they're called by Python internals)
                if node.name.startswith("__") and node.name.endswith("__"):
                    continue
                functions.append(
                    AsyncFunction(
                        name=node.name,
                        file=py_file,
                        line=node.lineno,
                        is_private=node.name.startswith("_"),
                    )
                )
    return functions


def extract_tested_names(test_dir: Path) -> set[str]:
    """Extract function names referenced in test files.

    Scans for:
    - Direct function calls (e.g., ``await engine.dispatch()``)
    - Attribute access patterns (e.g., ``engine.reach_consensus``)
    - String references in test names (e.g., ``test_reach_consensus``)

    Args:
        test_dir: Directory containing test files.

    Returns:
        Set of function names that appear in test code.
    """
    tested_names: set[str] = set()
    for py_file in sorted(test_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            # Direct function calls: func_name()
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    tested_names.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    tested_names.add(node.func.attr)
            # Test function names: test_<function_name>
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
                    # Extract the function name being tested
                    # e.g., test_reach_consensus → reach_consensus
                    tested_part = node.name[5:]  # strip "test_"
                    tested_names.add(tested_part)
                    # Also handle test_<func>_xxx patterns
                    parts = tested_part.split("_")
                    for i in range(1, len(parts) + 1):
                        tested_names.add("_".join(parts[:i]))
    return tested_names


def check_async_coverage(
    source_dir: Path,
    test_dir: Path,
    include_private: bool = False,
) -> CoverageReport:
    """Check async function coverage.

    Args:
        source_dir: Source directory to scan for async functions.
        test_dir: Test directory to scan for test references.
        include_private: Whether to include private (``_``-prefixed) functions.

    Returns:
        CoverageReport with covered/uncovered lists.
    """
    async_funcs = extract_async_functions(source_dir)
    if not include_private:
        async_funcs = [f for f in async_funcs if not f.is_private]

    tested_names = extract_tested_names(test_dir)

    report = CoverageReport(
        total=len(async_funcs),
        source_dir=str(source_dir),
        test_dir=str(test_dir),
    )
    for func in async_funcs:
        if func.name in tested_names:
            report.covered.append(func.name)
        else:
            report.uncovered.append(func)

    if report.total > 0:
        report.coverage_percent = (len(report.covered) / report.total) * 100

    return report


def generate_markdown(report: CoverageReport) -> str:
    """Render a CoverageReport as Markdown.

    Produces a stable Markdown document with a summary section and, when
    there are uncovered functions, a table listing them. Empty reports
    (no uncovered functions) omit the table section.

    Args:
        report: CoverageReport to render. ``source_dir`` and ``test_dir``
            are echoed in the header; if they were not populated, empty
            backticks are emitted (still valid Markdown).

    Returns:
        Markdown-formatted string ending without a trailing newline.
    """
    lines: list[str] = [
        "# Async Coverage Report",
        "",
        f"**Source**: `{report.source_dir}`",
        f"**Tests**: `{report.test_dir}`",
        "",
        "## Summary",
        "",
        f"- Total async functions: {report.total}",
        f"- Covered: {len(report.covered)}",
        f"- Uncovered: {len(report.uncovered)}",
        f"- Coverage: {report.coverage_percent:.1f}%",
        "",
    ]

    if not report.uncovered:
        lines.append("_No uncovered async functions._")
        return "\n".join(lines)

    lines.extend(
        [
            "## Uncovered Functions",
            "",
            "| Name | File | Line | Visibility |",
            "|------|------|------|-----------|",
        ]
    )
    for func in report.uncovered:
        visibility = "private" if func.is_private else "public"
        lines.append(f"| `{func.name}` | `{func.file}` | {func.line} | {visibility} |")
    return "\n".join(lines)


def check_with_threshold(
    source_dir: Path,
    test_dir: Path,
    min_coverage_percent: float = 80.0,
    ignore: list[str] | None = None,
) -> tuple[CoverageReport, bool]:
    """Check async coverage against a minimum threshold.

    Runs the standard coverage check, then optionally filters out
    functions named in ``ignore`` (removing them from both ``covered``
    and ``uncovered`` and recomputing ``total`` / ``coverage_percent``).
    Always populates ``report.markdown_report`` so callers can render
    the result without a second pass.

    Args:
        source_dir: Source directory to scan for async functions.
        test_dir: Test directory to scan for test references.
        min_coverage_percent: Minimum coverage percent required to pass.
        ignore: Optional list of function names to exclude from the
            check. Ignored functions do not count against coverage.

    Returns:
        Tuple ``(report, passed)`` where ``passed`` is ``True`` when
        ``report.coverage_percent >= min_coverage_percent``.
    """
    report = check_async_coverage(source_dir, test_dir)

    if ignore:
        ignore_set = set(ignore)
        report.covered = [name for name in report.covered if name not in ignore_set]
        report.uncovered = [f for f in report.uncovered if f.name not in ignore_set]
        report.total = len(report.covered) + len(report.uncovered)
        if report.total > 0:
            report.coverage_percent = (len(report.covered) / report.total) * 100
        else:
            # No functions remain after ignoring — vacuously fully covered.
            report.coverage_percent = 100.0

    report.markdown_report = generate_markdown(report)
    passed = report.coverage_percent >= min_coverage_percent
    return report, passed


def main() -> int:
    """CLI entry point.

    Returns:
        0 if all covered, 1 if some uncovered, 2 if invalid args.
    """
    parser = argparse.ArgumentParser(
        description="V4.2.0 P0-20: Detect async functions without test coverage."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("scripts/collaboration"),
        help="Source directory to scan (default: scripts/collaboration)",
    )
    parser.add_argument(
        "--tests",
        type=Path,
        default=Path("tests"),
        help="Test directory to scan (default: tests)",
    )
    parser.add_argument(
        "--include-private",
        action="store_true",
        help="Include _private async functions in coverage check",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )
    parser.add_argument(
        "--fail-on-uncovered",
        action="store_true",
        help="Exit with code 1 if any async function is uncovered",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=0.0,
        help="Minimum coverage percent required (default: 0.0 = no threshold). "
        "When > 0, exits with code 1 if coverage is below the threshold.",
    )
    parser.add_argument(
        "--ignore",
        nargs="*",
        default=None,
        metavar="NAME",
        help="Async function names to exclude from the coverage check "
        "(e.g., --ignore _private_func _internal). Ignored functions do "
        "not count against coverage.",
    )

    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"Error: source directory not found: {args.source}", file=sys.stderr)
        return 2
    if not args.tests.is_dir():
        print(f"Error: test directory not found: {args.tests}", file=sys.stderr)
        return 2

    use_threshold = args.min_coverage > 0 or bool(args.ignore)
    if use_threshold:
        report, passed = check_with_threshold(
            source_dir=args.source,
            test_dir=args.tests,
            min_coverage_percent=args.min_coverage,
            ignore=args.ignore,
        )
    else:
        report = check_async_coverage(
            source_dir=args.source,
            test_dir=args.tests,
            include_private=args.include_private,
        )
        passed = True

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("Async Coverage Report (V4.2.0 P0-20)")
        print("=" * 50)
        print(f"Source: {args.source}")
        print(f"Tests:  {args.tests}")
        print(f"Total async functions: {report.total}")
        print(f"Covered: {len(report.covered)}")
        print(f"Uncovered: {len(report.uncovered)}")
        print(f"Coverage: {report.coverage_percent:.1f}%")
        if report.uncovered:
            print("\nUncovered async functions:")
            for func in report.uncovered:
                visibility = "private" if func.is_private else "public"
                print(f"  - {func.name} ({visibility}) [{func.file}:{func.line}]")

    if args.fail_on_uncovered and report.uncovered:
        return 1
    if use_threshold and not passed:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
