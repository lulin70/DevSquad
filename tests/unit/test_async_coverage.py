"""Unit tests for scripts/check_async_coverage.py (V4.1.2 Phase 3.1).

Covers the Phase 3.1 API surface:
- ``extract_async_functions`` / ``extract_tested_names`` / ``check_async_coverage``
- ``generate_markdown`` (new in Phase 3.1)
- ``check_with_threshold`` (new in Phase 3.1)

All tests use ``tempfile.TemporaryDirectory`` so they do not depend on the
real project layout. Run with::

    python -m pytest tests/unit/test_async_coverage.py -v
"""

import os
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.check_async_coverage import (  # noqa: E402
    AsyncFunction,
    CoverageReport,
    check_async_coverage,
    check_with_threshold,
    extract_async_functions,
    extract_tested_names,
    generate_markdown,
)


class TestExtractAsyncFunctions(unittest.TestCase):
    """Test async function extraction from source code."""

    def test_01_extracts_async_functions(self) -> None:
        """``async def`` functions are extracted; sync ``def`` are skipped."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "mod.py"
            src.write_text(
                textwrap.dedent(
                    """
                    async def fetch_data():
                        pass

                    def sync_func():
                        pass

                    async def process_async():
                        pass
                    """
                ),
                encoding="utf-8",
            )
            funcs = extract_async_functions(Path(tmp))
            names = [f.name for f in funcs]
            self.assertIn("fetch_data", names)
            self.assertIn("process_async", names)
            self.assertNotIn("sync_func", names)

    def test_02_skips_dunder_methods(self) -> None:
        """``__dunder__`` methods are skipped (called by Python internals)."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "mod.py"
            src.write_text(
                textwrap.dedent(
                    """
                    class Foo:
                        async def __aenter__(self):
                            pass
                        async def __aexit__(self, *args):
                            pass
                        async def public_method(self):
                            pass
                    """
                ),
                encoding="utf-8",
            )
            funcs = extract_async_functions(Path(tmp))
            names = [f.name for f in funcs]
            self.assertIn("public_method", names)
            self.assertNotIn("__aenter__", names)
            self.assertNotIn("__aexit__", names)

    def test_03_marks_private_functions(self) -> None:
        """``_``-prefixed functions are marked ``is_private=True``."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "mod.py"
            src.write_text(
                textwrap.dedent(
                    """
                    async def public_func():
                        pass

                    async def _private_func():
                        pass
                    """
                ),
                encoding="utf-8",
            )
            funcs = extract_async_functions(Path(tmp))
            private = [f for f in funcs if f.is_private]
            public = [f for f in funcs if not f.is_private]
            self.assertTrue(any(f.name == "_private_func" for f in private))
            self.assertTrue(any(f.name == "public_func" for f in public))


class TestExtractTestedNames(unittest.TestCase):
    """Test tested-name extraction from test files."""

    def test_01_extracts_direct_calls(self) -> None:
        """Direct function calls (``await foo()``) are extracted."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "test_mod.py"
            test_file.write_text(
                textwrap.dedent(
                    """
                    async def test_fetch():
                        await fetch_data()
                    """
                ),
                encoding="utf-8",
            )
            names = extract_tested_names(Path(tmp))
            self.assertIn("fetch_data", names)

    def test_02_extracts_attribute_access(self) -> None:
        """Attribute access patterns (``obj.method()``) are extracted."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "test_mod.py"
            test_file.write_text(
                textwrap.dedent(
                    """
                    def test_engine():
                        engine.reach_consensus(prop)
                    """
                ),
                encoding="utf-8",
            )
            names = extract_tested_names(Path(tmp))
            self.assertIn("reach_consensus", names)

    def test_03_extracts_test_function_names(self) -> None:
        """Function names are extracted from ``test_<name>`` patterns."""
        with tempfile.TemporaryDirectory() as tmp:
            test_file = Path(tmp) / "test_mod.py"
            test_file.write_text(
                textwrap.dedent(
                    """
                    def test_reach_consensus_approved():
                        pass
                    """
                ),
                encoding="utf-8",
            )
            names = extract_tested_names(Path(tmp))
            self.assertIn("reach_consensus", names)
            self.assertIn("reach", names)  # prefix matching


class TestCheckAsyncCoverage(unittest.TestCase):
    """Test the headline ``check_async_coverage`` analyzer."""

    def test_01_full_coverage(self) -> None:
        """All async functions covered → 100%."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "mod.py").write_text("async def fetch():\n    pass\n", encoding="utf-8")

            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_mod.py").write_text(
                "async def test_fetch():\n    await fetch()\n",
                encoding="utf-8",
            )

            report = check_async_coverage(src, tests)
            self.assertEqual(report.total, 1)
            self.assertEqual(len(report.covered), 1)
            self.assertEqual(len(report.uncovered), 0)
            self.assertEqual(report.coverage_percent, 100.0)

    def test_02_partial_coverage(self) -> None:
        """Some async functions covered → 50%."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "mod.py").write_text(
                "async def fetch():\n    pass\n\nasync def process():\n    pass\n",
                encoding="utf-8",
            )

            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_mod.py").write_text(
                "async def test_fetch():\n    await fetch()\n",
                encoding="utf-8",
            )

            report = check_async_coverage(src, tests)
            self.assertEqual(report.total, 2)
            self.assertEqual(len(report.covered), 1)
            self.assertEqual(len(report.uncovered), 1)
            self.assertEqual(report.coverage_percent, 50.0)

    def test_03_no_coverage(self) -> None:
        """No async functions covered → 0%."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "mod.py").write_text("async def fetch():\n    pass\n", encoding="utf-8")

            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_mod.py").write_text("def test_other():\n    pass\n", encoding="utf-8")

            report = check_async_coverage(src, tests)
            self.assertEqual(report.total, 1)
            self.assertEqual(len(report.covered), 0)
            self.assertEqual(len(report.uncovered), 1)
            self.assertEqual(report.coverage_percent, 0.0)


class TestMarkdownReport(unittest.TestCase):
    """Test ``generate_markdown`` rendering."""

    def test_01_markdown_format(self) -> None:
        """Markdown contains header, summary, and uncovered-function table."""
        report = CoverageReport(
            total=2,
            covered=["fetch"],
            uncovered=[
                AsyncFunction(
                    name="_private_func",
                    file=Path("scripts/foo.py"),
                    line=42,
                    is_private=True,
                )
            ],
            coverage_percent=50.0,
            source_dir="scripts/collaboration",
            test_dir="tests",
        )
        md = generate_markdown(report)
        self.assertIn("# Async Coverage Report", md)
        self.assertIn("**Source**: `scripts/collaboration`", md)
        self.assertIn("**Tests**: `tests`", md)
        self.assertIn("## Summary", md)
        self.assertIn("- Total async functions: 2", md)
        self.assertIn("- Covered: 1", md)
        self.assertIn("- Uncovered: 1", md)
        self.assertIn("- Coverage: 50.0%", md)
        self.assertIn("## Uncovered Functions", md)
        self.assertIn("| Name | File | Line | Visibility |", md)
        self.assertIn("|------|------|------|-----------|", md)
        self.assertIn("`_private_func`", md)
        self.assertIn("`scripts/foo.py`", md)
        self.assertIn("| 42 |", md)
        self.assertIn("| private |", md)

    def test_02_empty_report(self) -> None:
        """Empty report produces valid markdown without the uncovered table."""
        report = CoverageReport(
            total=0,
            source_dir="scripts/empty",
            test_dir="tests/empty",
        )
        md = generate_markdown(report)
        self.assertIn("# Async Coverage Report", md)
        self.assertIn("## Summary", md)
        self.assertIn("- Total async functions: 0", md)
        self.assertIn("- Coverage: 0.0%", md)
        # No uncovered-functions table when there is nothing uncovered.
        self.assertNotIn("## Uncovered Functions", md)
        self.assertIn("_No uncovered async functions._", md)


class TestThresholdCheck(unittest.TestCase):
    """Test ``check_with_threshold`` threshold + ignore semantics."""

    def test_01_passes_threshold(self) -> None:
        """Coverage above threshold → ``passed=True`` and markdown populated."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "mod.py").write_text("async def fetch():\n    pass\n", encoding="utf-8")

            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_mod.py").write_text(
                "async def test_fetch():\n    await fetch()\n",
                encoding="utf-8",
            )

            report, passed = check_with_threshold(src, tests, min_coverage_percent=80.0)
            self.assertTrue(passed)
            self.assertEqual(report.coverage_percent, 100.0)
            # check_with_threshold always populates markdown_report.
            self.assertTrue(report.markdown_report)
            self.assertIn("# Async Coverage Report", report.markdown_report)

    def test_02_fails_threshold(self) -> None:
        """Coverage below threshold → ``passed=False``."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "mod.py").write_text(
                "async def fetch():\n    pass\n\nasync def process():\n    pass\n",
                encoding="utf-8",
            )

            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_mod.py").write_text(
                "async def test_fetch():\n    await fetch()\n",
                encoding="utf-8",
            )

            report, passed = check_with_threshold(src, tests, min_coverage_percent=80.0)
            self.assertFalse(passed)
            self.assertEqual(report.coverage_percent, 50.0)
            self.assertEqual(len(report.uncovered), 1)
            self.assertTrue(report.markdown_report)

    def test_03_ignore_list_skips_functions(self) -> None:
        """Ignore list excludes functions from total / uncovered / coverage."""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "src"
            src.mkdir()
            (src / "mod.py").write_text(
                "async def fetch():\n    pass\n\nasync def bar():\n    pass\n",
                encoding="utf-8",
            )

            tests = Path(tmp) / "tests"
            tests.mkdir()
            (tests / "test_mod.py").write_text(
                "async def test_fetch():\n    await fetch()\n",
                encoding="utf-8",
            )

            report, passed = check_with_threshold(
                src, tests, min_coverage_percent=80.0, ignore=["bar"]
            )
            self.assertTrue(passed)
            # ``bar`` is excluded → total drops from 2 to 1.
            self.assertEqual(report.total, 1)
            self.assertEqual(len(report.covered), 1)
            self.assertEqual(len(report.uncovered), 0)
            self.assertEqual(report.coverage_percent, 100.0)


if __name__ == "__main__":
    unittest.main()
