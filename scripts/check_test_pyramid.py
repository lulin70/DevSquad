#!/usr/bin/env python3
"""Test Pyramid Distribution Analyzer (V4.2.1 P2-21).

Analyzes the test suite composition (unit / integration / e2e / contract /
smoke / external) and reports distribution ratios against healthy pyramid
ranges. A top-heavy pyramid (too many e2e, too few unit) indicates a slow
test suite and brittle tests.

Usage:
    python scripts/check_test_pyramid.py
    python scripts/check_test_pyramid.py tests/ --json
    python scripts/check_test_pyramid.py tests/ --strict  # fail on warnings

Exit codes:
    0 = all layers within healthy ranges
    1 = one or more layers outside healthy range (warning)
    2 = script error (could not read tests directory)

Categorization rules (applied in priority order):
    1. Path-based: tests/unit/ → unit, tests/integration/ → integration, etc.
    2. Filename-based: *_e2e.py / *_e2e_test.py → e2e (override root default)
    3. Root default: tests/test_*.py (no subdir) → unit (per convention)

Test function counting uses AST parsing to count ``test_*`` functions and
``Test*`` class methods, avoiding import side effects.
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TESTS_DIR = REPO_ROOT / "tests"


@dataclass
class LayerStats:
    """Statistics for a single test pyramid layer."""

    layer: str          # "unit", "integration", etc.
    file_count: int     # Number of test files
    test_count: int     # Number of test functions/methods
    ratio: float = 0.0  # Percentage of total (0.0-1.0)


@dataclass
class PyramidReport:
    """Full test pyramid analysis report."""

    total_tests: int
    total_files: int
    layers: list[LayerStats] = field(default_factory=list)
    assessment: str = "healthy"  # "healthy" / "warning"
    issues: list[str] = field(default_factory=list)


# Healthy ratio ranges per test pyramid layer (lower, upper).
# Reference: https://martinfowler.com/bliki/TestPyramid.html
HEALTHY_RANGES: dict[str, tuple[float, float]] = {
    "unit": (0.60, 1.00),         # >=60% (numerous, fast, isolated)
    "integration": (0.15, 0.25),  # 15-25% (module interaction)
    "e2e": (0.00, 0.10),          # <=10% (slow, brittle, few)
    "contract": (0.05, 0.10),     # 5-10% (interface verification)
    "smoke": (0.00, 0.05),        # <=5% (deployment verification)
    "external": (0.00, 0.05),     # <=5% (external API tests)
}

# Display order for reports.
LAYER_ORDER: list[str] = ["unit", "integration", "e2e", "contract", "smoke", "external"]

# Filename patterns that override root-level default categorization.
E2E_FILENAME_PATTERNS: tuple[str, ...] = ("_e2e.py", "_e2e_test.py")


class TestPyramidAnalyzer:
    """Analyzes test directory structure and reports pyramid distribution."""

    # pytest collection guard: class name starts with "Test" but this is NOT
    # a test class. __test__ = False tells pytest to skip collection.
    __test__ = False

    def __init__(self, healthy_ranges: dict[str, tuple[float, float]] | None = None) -> None:
        """Initialize analyzer with optional custom healthy ranges.

        Args:
            healthy_ranges: Custom (lower, upper) ratio bounds per layer.
                Defaults to :data:`HEALTHY_RANGES`.
        """
        self.healthy_ranges = healthy_ranges if healthy_ranges is not None else HEALTHY_RANGES

    def analyze(self, tests_dir: Path) -> PyramidReport:
        """Analyze test directory and return pyramid report.

        Args:
            tests_dir: Path to the tests/ directory.

        Returns:
            :class:`PyramidReport` with per-layer stats and health assessment.
        """
        if not tests_dir.exists():
            return PyramidReport(total_tests=0, total_files=0, assessment="warning",
                                 issues=[f"tests directory not found: {tests_dir}"])

        # Categorize files by layer.
        layer_files: dict[str, list[Path]] = {layer: [] for layer in LAYER_ORDER}
        for py_file in self._find_test_files(tests_dir):
            layer = self._categorize_file(py_file, tests_dir)
            layer_files[layer].append(py_file)

        # Count tests per layer (AST-based, no imports).
        layer_stats: list[LayerStats] = []
        total_tests = 0
        total_files = 0
        for layer in LAYER_ORDER:
            files = layer_files[layer]
            test_count = sum(self._count_tests(f) for f in files)
            layer_stats.append(LayerStats(
                layer=layer,
                file_count=len(files),
                test_count=test_count,
            ))
            total_tests += test_count
            total_files += len(files)

        # Compute ratios.
        for stat in layer_stats:
            stat.ratio = (stat.test_count / total_tests) if total_tests > 0 else 0.0

        # Assess health.
        issues: list[str] = []
        for stat in layer_stats:
            lower, upper = self.healthy_ranges.get(stat.layer, (0.0, 1.0))
            if stat.test_count == 0:
                # Empty layers are informational, not warnings (project may
                # not use contract/smoke/external layers).
                continue
            if stat.ratio < lower:
                issues.append(
                    f"{stat.layer} ratio {stat.ratio:.1%} below {lower:.0%} target "
                    f"({stat.test_count}/{total_tests} tests) — consider adding "
                    f"{stat.layer} tests."
                )
            elif stat.ratio > upper:
                issues.append(
                    f"{stat.layer} ratio {stat.ratio:.1%} exceeds {upper:.0%} target "
                    f"({stat.test_count}/{total_tests} tests) — too many slow tests."
                )

        assessment = "healthy" if not issues else "warning"
        return PyramidReport(
            total_tests=total_tests,
            total_files=total_files,
            layers=layer_stats,
            assessment=assessment,
            issues=issues,
        )

    def _find_test_files(self, tests_dir: Path) -> list[Path]:
        """Find all Python test files in tests_dir (recursive).

        Args:
            tests_dir: Root tests/ directory.

        Returns:
            Sorted list of .py file paths matching test file conventions.
        """
        files: list[Path] = []
        for py_file in tests_dir.rglob("*.py"):
            # Skip __init__.py, conftest.py, and non-test files.
            if py_file.name in ("__init__.py", "conftest.py"):
                continue
            # Include files starting with "test_" or ending with "_test.py".
            if py_file.name.startswith("test_") or py_file.name.endswith("_test.py"):
                files.append(py_file)
        return sorted(files)

    def _categorize_file(self, path: Path, tests_dir: Path) -> str:
        """Categorize a test file into a pyramid layer.

        Priority:
            1. Subdirectory name (tests/unit/, tests/e2e/, etc.)
            2. Filename override (*_e2e.py → e2e)
            3. Root default (tests/test_*.py → unit)

        Args:
            path: Test file path.
            tests_dir: Root tests/ directory (for relative path calc).

        Returns:
            Layer name (e.g., "unit", "integration", "e2e").
        """
        try:
            rel_path = path.relative_to(tests_dir)
        except ValueError:
            return "unit"  # fallback

        parts = rel_path.parts
        # If file is in a subdirectory, use subdir name as layer.
        if len(parts) > 1:
            subdir = parts[0].lower()
            if subdir in LAYER_ORDER:
                return subdir
            # Unknown subdir defaults to unit.
            return "unit"

        # Root-level file: check filename overrides first.
        name_lower = path.name.lower()
        for pattern in E2E_FILENAME_PATTERNS:
            if name_lower.endswith(pattern):
                return "e2e"

        # Default: root-level test_*.py → unit.
        return "unit"

    def _count_tests(self, path: Path) -> int:
        """Count test functions and methods in a file using AST.

        Counts:
            - Top-level functions starting with "test_"
            - Methods in Test* classes starting with "test_"

        Args:
            path: Python test file.

        Returns:
            Number of test functions/methods. Returns 0 on parse error.
        """
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return 0
        try:
            tree = ast.parse(content, filename=str(path))
        except SyntaxError:
            return 0

        count = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test_") or isinstance(node, ast.AsyncFunctionDef) and node.name.startswith("test_"):
                count += 1
        return count


def format_report(report: PyramidReport) -> str:
    """Format a :class:`PyramidReport` as a human-readable string.

    Args:
        report: The pyramid report to format.

    Returns:
        Multi-line string with table and assessment.
    """
    lines: list[str] = []
    lines.append("Test Pyramid Report (V4.2.1 P2-21)")
    lines.append(f"  Total: {report.total_tests} tests across {report.total_files} files")
    lines.append("")
    lines.append(f"  {'Layer':<14} {'Files':>6} {'Tests':>7} {'Ratio':>8}   Status")
    lines.append(f"  {'-' * 50}")
    for stat in report.layers:
        lower, upper = HEALTHY_RANGES.get(stat.layer, (0.0, 1.0))
        if stat.test_count == 0:
            status = "—"
        elif stat.ratio < lower or stat.ratio > upper:
            status = "WARNING"
        else:
            status = "OK"
        lines.append(
            f"  {stat.layer:<14} {stat.file_count:>6} {stat.test_count:>7} "
            f"{stat.ratio:>7.1%}   {status}"
        )
    lines.append(f"  {'-' * 50}")
    lines.append("")
    if report.issues:
        lines.append(f"  Assessment: {report.assessment}")
        for issue in report.issues:
            lines.append(f"    - {issue}")
    else:
        lines.append(f"  Assessment: {report.assessment} (all layers within target ranges)")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Analyze test pyramid distribution (unit/integration/e2e/contract/smoke/external)."
    )
    parser.add_argument(
        "tests_dir",
        nargs="?",
        default=str(DEFAULT_TESTS_DIR),
        help=f"Path to tests/ directory (default: {DEFAULT_TESTS_DIR})",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON instead of text")
    parser.add_argument("--strict", action="store_true", help="fail on warnings (exit 1)")
    args = parser.parse_args()

    tests_dir = Path(args.tests_dir)
    if not tests_dir.exists():
        print(f"ERROR: tests directory not found: {tests_dir}")
        return 2

    analyzer = TestPyramidAnalyzer()
    report = analyzer.analyze(tests_dir)

    if args.json:
        data = {
            "total_tests": report.total_tests,
            "total_files": report.total_files,
            "assessment": report.assessment,
            "issues": report.issues,
            "layers": [asdict(s) for s in report.layers],
        }
        print(json.dumps(data, indent=2))
    else:
        print(format_report(report))

    if report.issues and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
