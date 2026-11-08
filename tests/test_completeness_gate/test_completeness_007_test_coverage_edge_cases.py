"""Test Case 007: TestCoverageChecker Edge Cases

Tests edge cases and error handling for TestCoverageChecker.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.test_coverage_checker import TestCoverageChecker


class TestCoverageEdgeCases:
    """Test coverage checker edge cases."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def checker(self):
        """Create TestCoverageChecker instance."""
        return TestCoverageChecker()

    def test_malformed_p7_doc(self, checker, temp_dir):
        """Test handling of malformed P7 document."""
        p7_doc = temp_dir / "bad_plan.md"
        p7_doc.write_text("""
# Broken Test Plan

[[unclosed link
test_something
""")

        test_file = temp_dir / "test_code.py"
        test_file.write_text("def test_something(): pass")

        # Should not raise exception
        result = checker.check([test_file], p7_doc=p7_doc)

        assert "test_coverage" in result
        assert isinstance(result["test_coverage"], (int, float))

    def test_syntax_error_in_test_file(self, checker, temp_dir):
        """Test handling of syntax errors in test files."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("- test_something")

        test_file = temp_dir / "broken_test.py"
        test_file.write_text("""
def test_something(
    # Missing closing paren
""")

        result = checker.check([test_file], p7_doc=p7_doc)

        # Should skip broken file and report missing test
        assert result["test_coverage"] < 1.0

    def test_case_insensitive_matching(self, checker, temp_dir):
        """Test case-insensitive matching of test names."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
- test_CreateUser
- test_DeleteUser
""")

        test_file = temp_dir / "test_users.py"
        test_file.write_text("""
def test_createuser():
    pass

def test_deleteuser():
    pass
""")

        result = checker.check([test_file], p7_doc=p7_doc)

        # Should match case-insensitively
        assert result["test_coverage"] == 1.0

    def test_underscore_normalization(self, checker, temp_dir):
        """Test normalization of underscores in test names."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
- test_user_create_001
""")

        test_file = temp_dir / "test.py"
        test_file.write_text("""
def test_usercreate001():
    pass
""")

        result = checker.check([test_file], p7_doc=p7_doc)

        # Should normalize underscores
        assert result["test_coverage"] == 1.0

    def test_non_test_functions_ignored(self, checker, temp_dir):
        """Test that non-test functions are ignored."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("- test_main")

        test_file = temp_dir / "test_module.py"
        test_file.write_text("""
def test_main():
    pass

def helper_function():
    pass

def setup():
    pass
""")

        result = checker.check([test_file], p7_doc=p7_doc)

        # helper_function and setup should not count as extra tests
        assert result["test_coverage"] == 1.0
        assert "helper_function" not in [str(t) for t in result["extra_tests"]]

    def test_private_test_methods_ignored(self, checker, temp_dir):
        """Test that private methods (starting with _) are ignored."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("- test_public")

        test_file = temp_dir / "test_file.py"
        test_file.write_text("""
class TestClass:
    def test_public(self):
        pass

    def _test_private(self):
        pass
""")

        result = checker.check([test_file], p7_doc=p7_doc)

        # _test_private should not count as extra
        assert result["test_coverage"] == 1.0
        extra_lower = [str(t).lower() for t in result["extra_tests"]]
        assert "_test_private" not in extra_lower

    def test_empty_test_file(self, checker, temp_dir):
        """Test handling of empty test files."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("- test_required")

        test_file = temp_dir / "test_empty.py"
        test_file.write_text("")

        result = checker.check([test_file], p7_doc=p7_doc)

        # Should report missing test
        assert result["test_coverage"] == 0.0
        assert len(result["missing_tests"]) == 1

    def test_nonexistent_test_file(self, checker, temp_dir):
        """Test handling of non-existent test files."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("- test_something")

        nonexistent = temp_dir / "does_not_exist.py"

        result = checker.check([nonexistent], p7_doc=p7_doc)

        # Should handle gracefully
        assert "test_coverage" in result
        assert result["test_coverage"] < 1.0

    def test_async_test_functions(self, checker, temp_dir):
        """Test detection of async test functions."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("- test_async_operation")

        test_file = temp_dir / "test_async.py"
        test_file.write_text("""
import asyncio

async def test_async_operation():
    await asyncio.sleep(0)
""")

        result = checker.check([test_file], p7_doc=p7_doc)

        # Should detect async test functions
        assert result["test_coverage"] == 1.0
