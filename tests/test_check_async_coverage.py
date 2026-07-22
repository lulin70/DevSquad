"""Tests for V4.2.0 P0-20 Async Coverage Detector."""

import textwrap
from pathlib import Path

from scripts.check_async_coverage import (
    AsyncFunction,
    CoverageReport,
    check_async_coverage,
    extract_async_functions,
    extract_tested_names,
)


class TestExtractAsyncFunctions:
    """Test async function extraction from source code."""

    def test_extracts_async_def(self, tmp_path: Path):
        """async def functions are extracted."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                async def fetch_data():
                    pass

                def sync_func():
                    pass

                async def process_async():
                    pass
            """)
        )
        funcs = extract_async_functions(tmp_path)
        names = [f.name for f in funcs]
        assert "fetch_data" in names
        assert "process_async" in names
        assert "sync_func" not in names

    def test_skips_dunder_methods(self, tmp_path: Path):
        """__dunder__ methods are skipped."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                class Foo:
                    async def __aenter__(self):
                        pass
                    async def __aexit__(self, *args):
                        pass
                    async def public_method(self):
                        pass
            """)
        )
        funcs = extract_async_functions(tmp_path)
        names = [f.name for f in funcs]
        assert "public_method" in names
        assert "__aenter__" not in names
        assert "__aexit__" not in names

    def test_marks_private_functions(self, tmp_path: Path):
        """_underscore functions are marked as private."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                async def public_func():
                    pass

                async def _private_func():
                    pass
            """)
        )
        funcs = extract_async_functions(tmp_path)
        private = [f for f in funcs if f.is_private]
        public = [f for f in funcs if not f.is_private]
        assert any(f.name == "_private_func" for f in private)
        assert any(f.name == "public_func" for f in public)

    def test_records_file_and_line(self, tmp_path: Path):
        """File path and line number are recorded."""
        src = tmp_path / "mod.py"
        src.write_text(
            textwrap.dedent("""
                # line 2
                # line 3
                async def func():
                    pass
            """)
        )
        funcs = extract_async_functions(tmp_path)
        assert funcs[0].file == src
        assert funcs[0].line == 4

    def test_handles_syntax_error_gracefully(self, tmp_path: Path):
        """Syntax errors are skipped, not crashed."""
        src = tmp_path / "bad.py"
        src.write_text("def broken(:\n    pass\n")
        # Should not raise
        funcs = extract_async_functions(tmp_path)
        assert funcs == []


class TestExtractTestedNames:
    """Test tested name extraction from test files."""

    def test_extracts_direct_calls(self, tmp_path: Path):
        """Direct function calls are extracted."""
        test_file = tmp_path / "test_mod.py"
        test_file.write_text(
            textwrap.dedent("""
                async def test_fetch():
                    await fetch_data()
            """)
        )
        names = extract_tested_names(tmp_path)
        assert "fetch_data" in names

    def test_extracts_attribute_calls(self, tmp_path: Path):
        """Attribute access calls are extracted."""
        test_file = tmp_path / "test_mod.py"
        test_file.write_text(
            textwrap.dedent("""
                def test_engine():
                    engine.reach_consensus(prop)
            """)
        )
        names = extract_tested_names(tmp_path)
        assert "reach_consensus" in names

    def test_extracts_from_test_names(self, tmp_path: Path):
        """Function names are extracted from test_<name> patterns."""
        test_file = tmp_path / "test_mod.py"
        test_file.write_text(
            textwrap.dedent("""
                def test_reach_consensus_approved():
                    pass
            """)
        )
        names = extract_tested_names(tmp_path)
        assert "reach_consensus" in names
        assert "reach" in names  # prefix matching

    def test_extracts_async_test_names(self, tmp_path: Path):
        """Async test function names are extracted."""
        test_file = tmp_path / "test_mod.py"
        test_file.write_text(
            textwrap.dedent("""
                async def test_dispatch_async():
                    pass
            """)
        )
        names = extract_tested_names(tmp_path)
        assert "dispatch" in names
        assert "dispatch_async" in names


class TestCheckAsyncCoverage:
    """Test coverage checking."""

    def test_full_coverage(self, tmp_path: Path):
        """All async functions covered → 100%."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("async def fetch():\n    pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_mod.py").write_text(
            "async def test_fetch():\n    await fetch()\n"
        )

        report = check_async_coverage(src, tests)
        assert report.total == 1
        assert len(report.covered) == 1
        assert len(report.uncovered) == 0
        assert report.coverage_percent == 100.0

    def test_zero_coverage(self, tmp_path: Path):
        """No async functions covered → 0%."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("async def fetch():\n    pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_mod.py").write_text("def test_other():\n    pass\n")

        report = check_async_coverage(src, tests)
        assert report.total == 1
        assert len(report.covered) == 0
        assert len(report.uncovered) == 1
        assert report.coverage_percent == 0.0

    def test_partial_coverage(self, tmp_path: Path):
        """Some async functions covered."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "async def fetch():\n    pass\n\nasync def process():\n    pass\n"
        )

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_mod.py").write_text(
            "async def test_fetch():\n    await fetch()\n"
        )

        report = check_async_coverage(src, tests)
        assert report.total == 2
        assert len(report.covered) == 1
        assert len(report.uncovered) == 1
        assert report.coverage_percent == 50.0

    def test_exclude_private_by_default(self, tmp_path: Path):
        """Private functions excluded by default."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "async def public_func():\n    pass\n\nasync def _private_func():\n    pass\n"
        )

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_mod.py").write_text("def test_other():\n    pass\n")

        report = check_async_coverage(src, tests)
        assert report.total == 1  # only public_func
        assert report.uncovered[0].name == "public_func"

    def test_include_private_when_requested(self, tmp_path: Path):
        """Private functions included when flag set."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text(
            "async def public_func():\n    pass\n\nasync def _private_func():\n    pass\n"
        )

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_mod.py").write_text("def test_other():\n    pass\n")

        report = check_async_coverage(src, tests, include_private=True)
        assert report.total == 2

    def test_empty_source(self, tmp_path: Path):
        """No async functions → 0 total, 0% coverage."""
        src = tmp_path / "src"
        src.mkdir()
        (src / "mod.py").write_text("def sync_only():\n    pass\n")

        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_mod.py").write_text("def test_sync():\n    pass\n")

        report = check_async_coverage(src, tests)
        assert report.total == 0
        assert report.coverage_percent == 0.0

    def test_to_dict(self, tmp_path: Path):
        """to_dict returns correct structure."""
        report = CoverageReport(
            total=3,
            covered=["func_a", "func_b"],
            uncovered=[AsyncFunction(name="func_c", file=Path("mod.py"), line=10)],
        )
        report.coverage_percent = 66.67
        d = report.to_dict()
        assert d["total_async_functions"] == 3
        assert d["covered_count"] == 2
        assert d["uncovered_count"] == 1
        assert d["coverage_percent"] == 66.7
        assert d["uncovered"][0]["name"] == "func_c"
