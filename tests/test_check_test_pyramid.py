#!/usr/bin/env python3
"""Tests for check_test_pyramid.py (V4.2.1 P2-21) — Test Pyramid Analyzer.

Coverage dimensions (per DevSquad Iron Rule 3):
  - Happy Path: categorize files by subdir, count test functions via AST
  - Error Case: missing dir, empty dir, syntax-error file
  - Boundary: root-level test_*.py default to unit, *_e2e.py override
  - Health Assessment: ratio below/above healthy range → warning
  - Integration: main() CLI with --json / --strict flags
  - Format: format_report() output structure
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.check_test_pyramid import (
    DEFAULT_TESTS_DIR,
    HEALTHY_RANGES,
    LAYER_ORDER,
    LayerStats,
    PyramidReport,
    TestPyramidAnalyzer,
    format_report,
    main,
)


def _make_test_file(path: Path, test_names: tuple[str, ...] = ("test_a",)) -> None:
    """Create a minimal test file with the given test function names."""
    funcs = "\n".join(
        f"def {name}():\n    pass\n" for name in test_names
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(funcs, encoding="utf-8")


class T1_LayerStatsDataclass(unittest.TestCase):
    """T1: LayerStats dataclass fields and defaults."""

    def test_01_creation_with_required_fields(self) -> None:
        """Verify: LayerStats requires layer, file_count, test_count."""
        s = LayerStats(layer="unit", file_count=10, test_count=100)
        self.assertEqual(s.layer, "unit")
        self.assertEqual(s.file_count, 10)
        self.assertEqual(s.test_count, 100)
        self.assertEqual(s.ratio, 0.0)  # default

    def test_02_ratio_can_be_set(self) -> None:
        """Verify: ratio field is mutable."""
        s = LayerStats(layer="e2e", file_count=2, test_count=20, ratio=0.1)
        self.assertAlmostEqual(s.ratio, 0.1)


class T2_PyramidReportDataclass(unittest.TestCase):
    """T2: PyramidReport dataclass fields and defaults."""

    def test_01_defaults(self) -> None:
        """Verify: PyramidReport defaults (healthy assessment, empty lists)."""
        r = PyramidReport(total_tests=0, total_files=0)
        self.assertEqual(r.total_tests, 0)
        self.assertEqual(r.assessment, "healthy")
        self.assertEqual(r.layers, [])
        self.assertEqual(r.issues, [])

    def test_02_can_populate_layers_and_issues(self) -> None:
        """Verify: layers and issues lists are mutable."""
        r = PyramidReport(total_tests=10, total_files=2)
        r.layers.append(LayerStats(layer="unit", file_count=1, test_count=8, ratio=0.8))
        r.issues.append("test issue")
        self.assertEqual(len(r.layers), 1)
        self.assertEqual(len(r.issues), 1)


class T3_HealthyRanges(unittest.TestCase):
    """T3: HEALTHY_RANGES constants."""

    def test_01_all_layers_have_ranges(self) -> None:
        """Verify: Every layer in LAYER_ORDER has a healthy range."""
        for layer in LAYER_ORDER:
            self.assertIn(layer, HEALTHY_RANGES, f"Missing range for layer: {layer}")

    def test_02_unit_range_lower_bound_60_percent(self) -> None:
        """Verify: unit layer lower bound is 0.60 (>=60%)."""
        self.assertEqual(HEALTHY_RANGES["unit"][0], 0.60)

    def test_03_e2e_range_upper_bound_10_percent(self) -> None:
        """Verify: e2e layer upper bound is 0.10 (<=10%)."""
        self.assertEqual(HEALTHY_RANGES["e2e"][1], 0.10)


class T4_CategorizeFile(unittest.TestCase):
    """T4: _categorize_file() layer assignment logic."""

    def setUp(self) -> None:
        self.analyzer = TestPyramidAnalyzer()

    def test_01_unit_subdir(self) -> None:
        """Verify: tests/unit/test_foo.py → unit."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "unit" / "test_foo.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "unit")

    def test_02_integration_subdir(self) -> None:
        """Verify: tests/integration/test_bar.py → integration."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "integration" / "test_bar.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "integration")

    def test_03_e2e_subdir(self) -> None:
        """Verify: tests/e2e/test_baz.py → e2e."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "e2e" / "test_baz.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "e2e")

    def test_04_root_level_default_unit(self) -> None:
        """Verify: tests/test_foo.py (root) → unit (default)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "test_foo.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "unit")

    def test_05_root_level_e2e_filename_override(self) -> None:
        """Verify: tests/foo_e2e.py (root) → e2e (filename override)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "foo_e2e.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "e2e")

    def test_06_root_level_e2e_test_filename_override(self) -> None:
        """Verify: tests/foo_e2e_test.py (root) → e2e."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "foo_e2e_test.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "e2e")

    def test_07_unknown_subdir_defaults_unit(self) -> None:
        """Verify: tests/unknown/test.py → unit (fallback)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            f = tests_dir / "unknown" / "test.py"
            _make_test_file(f)
            self.assertEqual(self.analyzer._categorize_file(f, tests_dir), "unit")


class T5_CountTests(unittest.TestCase):
    """T5: _count_tests() AST-based test counting."""

    def setUp(self) -> None:
        self.analyzer = TestPyramidAnalyzer()

    def test_01_counts_test_functions(self) -> None:
        """Verify: Counts top-level test_ functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test_x.py"
            f.write_text(
                "def test_a():\n    pass\n"
                "def test_b():\n    pass\n"
                "def helper():\n    pass\n",
                encoding="utf-8",
            )
            self.assertEqual(self.analyzer._count_tests(f), 2)

    def test_02_counts_async_test_functions(self) -> None:
        """Verify: Counts async test_ functions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test_async.py"
            f.write_text(
                "async def test_async_a():\n    pass\n"
                "async def test_async_b():\n    pass\n",
                encoding="utf-8",
            )
            self.assertEqual(self.analyzer._count_tests(f), 2)

    def test_03_counts_class_methods(self) -> None:
        """Verify: Counts test_ methods inside Test* classes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test_class.py"
            f.write_text(
                "class TestFoo:\n"
                "    def test_method_a(self):\n"
                "        pass\n"
                "    def test_method_b(self):\n"
                "        pass\n"
                "    def helper(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            # ast.walk visits FunctionDef nodes regardless of class nesting
            self.assertEqual(self.analyzer._count_tests(f), 2)

    def test_04_syntax_error_returns_zero(self) -> None:
        """Verify: Syntax error file → 0 (no crash)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test_broken.py"
            f.write_text("def test_a(:\n    pass\n", encoding="utf-8")  # syntax error
            self.assertEqual(self.analyzer._count_tests(f), 0)

    def test_05_unreadable_file_returns_zero(self) -> None:
        """Verify: Unreadable file → 0 (no crash)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test_unreadable.py"
            _make_test_file(f)
            with mock.patch.object(Path, "read_text", side_effect=OSError("denied")):
                self.assertEqual(self.analyzer._count_tests(f), 0)

    def test_06_empty_file_returns_zero(self) -> None:
        """Verify: Empty file → 0."""
        with tempfile.TemporaryDirectory() as tmpdir:
            f = Path(tmpdir) / "test_empty.py"
            f.write_text("", encoding="utf-8")
            self.assertEqual(self.analyzer._count_tests(f), 0)


class T6_FindTestFiles(unittest.TestCase):
    """T6: _find_test_files() file discovery."""

    def setUp(self) -> None:
        self.analyzer = TestPyramidAnalyzer()

    def test_01_includes_test_prefix_files(self) -> None:
        """Verify: test_*.py files are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            _make_test_file(tests_dir / "test_foo.py")
            _make_test_file(tests_dir / "test_bar.py")
            files = self.analyzer._find_test_files(tests_dir)
            self.assertEqual(len(files), 2)

    def test_02_includes_test_suffix_files(self) -> None:
        """Verify: *_test.py files are included."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            _make_test_file(tests_dir / "foo_test.py")
            files = self.analyzer._find_test_files(tests_dir)
            self.assertEqual(len(files), 1)

    def test_03_excludes_init_and_conftest(self) -> None:
        """Verify: __init__.py and conftest.py are excluded."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            _make_test_file(tests_dir / "__init__.py")
            _make_test_file(tests_dir / "conftest.py")
            _make_test_file(tests_dir / "test_real.py")
            files = self.analyzer._find_test_files(tests_dir)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].name, "test_real.py")

    def test_04_recursive_search(self) -> None:
        """Verify: Finds files in subdirectories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            _make_test_file(tests_dir / "test_root.py")
            _make_test_file(tests_dir / "unit" / "test_unit.py")
            _make_test_file(tests_dir / "e2e" / "test_e2e.py")
            files = self.analyzer._find_test_files(tests_dir)
            self.assertEqual(len(files), 3)


class T7_Analyze(unittest.TestCase):
    """T7: analyze() full pipeline."""

    def setUp(self) -> None:
        self.analyzer = TestPyramidAnalyzer()

    def test_01_healthy_distribution(self) -> None:
        """Verify: Distribution within healthy ranges → assessment healthy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            # Create 60 unit tests (60%), 20 integration (20%), 10 e2e (10%),
            # 7 contract (7%), 3 smoke (3%)
            for i in range(60):
                _make_test_file(tests_dir / "unit" / f"test_u{i}.py", (f"test_u{i}",))
            for i in range(20):
                _make_test_file(tests_dir / "integration" / f"test_i{i}.py", (f"test_i{i}",))
            for i in range(10):
                _make_test_file(tests_dir / "e2e" / f"test_e{i}.py", (f"test_e{i}",))
            for i in range(7):
                _make_test_file(tests_dir / "contract" / f"test_c{i}.py", (f"test_c{i}",))
            for i in range(3):
                _make_test_file(tests_dir / "smoke" / f"test_s{i}.py", (f"test_s{i}",))
            report = self.analyzer.analyze(tests_dir)
            self.assertEqual(report.total_tests, 100)
            self.assertEqual(report.assessment, "healthy")
            self.assertEqual(len(report.issues), 0)

    def test_02_warning_on_low_unit_ratio(self) -> None:
        """Verify: Unit ratio below 60% → warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            # 40 unit + 60 e2e → unit 40% (below 60%), e2e 60% (above 10%)
            for i in range(40):
                _make_test_file(tests_dir / "unit" / f"test_u{i}.py", (f"test_u{i}",))
            for i in range(60):
                _make_test_file(tests_dir / "e2e" / f"test_e{i}.py", (f"test_e{i}",))
            report = self.analyzer.analyze(tests_dir)
            self.assertEqual(report.assessment, "warning")
            self.assertGreater(len(report.issues), 0)

    def test_03_empty_directory_returns_zero_totals(self) -> None:
        """Verify: Empty tests dir → 0 tests, 0 files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            report = self.analyzer.analyze(tests_dir)
            self.assertEqual(report.total_tests, 0)
            self.assertEqual(report.total_files, 0)

    def test_04_nonexistent_directory_returns_warning(self) -> None:
        """Verify: Missing tests dir → warning with issue."""
        report = self.analyzer.analyze(Path("/nonexistent/path/xxx"))
        self.assertEqual(report.assessment, "warning")
        self.assertGreater(len(report.issues), 0)

    def test_05_ratio_calculation(self) -> None:
        """Verify: Ratio is correctly computed as test_count/total."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            _make_test_file(tests_dir / "unit" / "test_a.py", ("test_1", "test_2", "test_3"))
            _make_test_file(tests_dir / "e2e" / "test_b.py", ("test_4",))
            report = self.analyzer.analyze(tests_dir)
            self.assertEqual(report.total_tests, 4)
            unit_stat = next(s for s in report.layers if s.layer == "unit")
            e2e_stat = next(s for s in report.layers if s.layer == "e2e")
            self.assertAlmostEqual(unit_stat.ratio, 0.75)
            self.assertAlmostEqual(e2e_stat.ratio, 0.25)


class T8_FormatReport(unittest.TestCase):
    """T8: format_report() output."""

    def test_01_contains_layer_names(self) -> None:
        """Verify: All layer names appear in report."""
        report = PyramidReport(
            total_tests=100,
            total_files=10,
            layers=[LayerStats(layer=layer, file_count=1, test_count=10, ratio=0.1)
                    for layer in LAYER_ORDER],
        )
        text = format_report(report)
        for layer in LAYER_ORDER:
            self.assertIn(layer, text)

    def test_02_contains_totals(self) -> None:
        """Verify: Total tests and files appear in report."""
        report = PyramidReport(total_tests=42, total_files=7, layers=[])
        text = format_report(report)
        self.assertIn("42", text)
        self.assertIn("7", text)

    def test_03_contains_issues_when_warning(self) -> None:
        """Verify: Issues listed when assessment is warning."""
        report = PyramidReport(
            total_tests=10,
            total_files=2,
            assessment="warning",
            issues=["unit ratio too low", "e2e ratio too high"],
        )
        text = format_report(report)
        self.assertIn("unit ratio too low", text)
        self.assertIn("e2e ratio too high", text)


class T9_MainCLI(unittest.TestCase):
    """T9: main() CLI entry point."""

    def test_01_returns_zero_on_healthy(self) -> None:
        """Verify: main() exits 0 on healthy distribution (no --strict)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            # Only unit tests → unit 100% (within range)
            _make_test_file(tests_dir / "unit" / "test_a.py", ("test_1",))
            with mock.patch("sys.argv", ["check_test_pyramid.py", str(tests_dir)]):
                exit_code = main()
            self.assertEqual(exit_code, 0)

    def test_02_returns_zero_on_warning_without_strict(self) -> None:
        """Verify: main() exits 0 on warning (no --strict)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            # Imbalanced: 10 e2e + 0 unit → warnings but exit 0 without --strict
            _make_test_file(tests_dir / "e2e" / "test_e.py", ("test_e",))
            with mock.patch("sys.argv", ["check_test_pyramid.py", str(tests_dir)]):
                exit_code = main()
            self.assertEqual(exit_code, 0)

    def test_03_returns_one_with_strict_on_warning(self) -> None:
        """Verify: --strict mode exits 1 on warning."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            # Imbalanced distribution: all tests in e2e (100% e2e → exceeds 10%)
            # Function names must start with "test_" to be counted by AST.
            _make_test_file(
                tests_dir / "e2e" / "test_e1.py",
                ("test_t1", "test_t2", "test_t3", "test_t4"),
            )
            _make_test_file(
                tests_dir / "e2e" / "test_e2.py",
                ("test_t5", "test_t6", "test_t7", "test_t8"),
            )
            with mock.patch("sys.argv", ["check_test_pyramid.py", str(tests_dir), "--strict"]):
                exit_code = main()
            self.assertEqual(exit_code, 1)

    def test_04_returns_two_on_missing_dir(self) -> None:
        """Verify: main() exits 2 when tests dir doesn't exist."""
        with mock.patch("sys.argv", ["check_test_pyramid.py", "/nonexistent/xxx/yyy"]):
            exit_code = main()
        self.assertEqual(exit_code, 2)

    def test_05_json_output_valid_json(self) -> None:
        """Verify: --json produces valid JSON with expected fields."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tests_dir = Path(tmpdir)
            _make_test_file(tests_dir / "unit" / "test_a.py", ("test_1",))
            with mock.patch("sys.argv", ["check_test_pyramid.py", str(tests_dir), "--json"]):
                import io
                from contextlib import redirect_stdout
                buf = io.StringIO()
                with redirect_stdout(buf):
                    exit_code = main()
            data = json.loads(buf.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertIn("total_tests", data)
            self.assertIn("total_files", data)
            self.assertIn("layers", data)
            self.assertIn("assessment", data)


class T10_RealTestsDir(unittest.TestCase):
    """T10: Integration test against real tests/ directory (if present)."""

    def test_01_real_tests_dir_analyzes_without_crash(self) -> None:
        """Verify: Real tests/ directory analyzes without crashing."""
        if not DEFAULT_TESTS_DIR.exists():
            self.skipTest("tests/ directory does not exist")
        analyzer = TestPyramidAnalyzer()
        report = analyzer.analyze(DEFAULT_TESTS_DIR)
        # Should find at least some tests
        self.assertGreater(report.total_tests, 0, "Expected tests in real tests/ dir")
        self.assertGreater(report.total_files, 0)
        # Should have stats for all layers
        self.assertEqual(len(report.layers), len(LAYER_ORDER))


if __name__ == "__main__":
    unittest.main()
