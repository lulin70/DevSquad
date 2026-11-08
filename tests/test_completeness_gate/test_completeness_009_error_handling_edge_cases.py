"""Test Case 009: ErrorHandlingChecker Edge Cases

Tests edge cases and error handling for ErrorHandlingChecker.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.error_handling_checker import ErrorHandlingChecker


class TestErrorHandlingEdgeCases:
    """Test error handling checker edge cases."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def checker(self):
        """Create ErrorHandlingChecker instance."""
        return ErrorHandlingChecker()

    def test_nested_try_blocks(self, checker, temp_dir):
        """Test nested try-except blocks."""
        code_file = temp_dir / "nested.py"
        code_file.write_text("""
def complex_operation():
    try:
        with open('outer.txt') as f:
            try:
                data = f.read()
            except IOError:
                data = ""
    except FileNotFoundError:
        data = None
""")

        result = checker.check([code_file])

        assert result["error_handling_score"] == 1.0

    def test_context_manager_protection(self, checker, temp_dir):
        """Test that with statement counts as protection."""
        code_file = temp_dir / "context.py"
        code_file.write_text("""
def use_context():
    try:
        with open('file.txt') as f:
            content = f.read()
    except:
        content = ""
""")

        result = checker.check([code_file])

        assert result["error_handling_score"] == 1.0

    def test_syntax_error_in_file(self, checker, temp_dir):
        """Test handling of syntax errors."""
        code_file = temp_dir / "broken.py"
        code_file.write_text("""
def bad_function(
    # Missing closing paren
""")

        # Should not raise exception
        result = checker.check([code_file])

        assert "error_handling_score" in result

    def test_finally_block(self, checker, temp_dir):
        """Test detection with finally blocks."""
        code_file = temp_dir / "finally_test.py"
        code_file.write_text("""
def with_finally():
    try:
        with open('file.txt') as f:
            return f.read()
    except FileNotFoundError:
        return ""
    finally:
        print("cleanup")
""")

        result = checker.check([code_file])

        assert result["error_handling_score"] == 1.0

    def test_empty_except(self, checker, temp_dir):
        """Test that bare except still counts as protection."""
        code_file = temp_dir / "bare_except.py"
        code_file.write_text("""
def catch_all():
    try:
        with open('file.txt') as f:
            return f.read()
    except:
        return ""
""")

        result = checker.check([code_file])

        assert result["error_handling_score"] == 1.0

    def test_requests_variations(self, checker, temp_dir):
        """Test various requests call patterns."""
        code_file = temp_dir / "requests_test.py"
        code_file.write_text("""
import requests

# Unprotected variations
def test1():
    requests.get("url")

def test2():
    requests.post("url", json={})

def test3():
    requests.put("url", data="test")

def test4():
    requests.delete("url")
""")

        result = checker.check([code_file])

        # All 4 are unprotected
        assert len(result["unprotected_operations"]) == 4

    def test_subprocess_variations(self, checker, temp_dir):
        """Test various subprocess patterns."""
        code_file = temp_dir / "subprocess_test.py"
        code_file.write_text("""
import subprocess

def test1():
    subprocess.run(["ls"])

def test2():
    subprocess.call(["echo", "hello"])

def test3():
    subprocess.check_output(["pwd"])
""")

        result = checker.check([code_file])

        # All 3 are unprotected
        assert len(result["unprotected_operations"]) >= 3

    def test_nonexistent_file(self, checker, temp_dir):
        """Test handling of non-existent files."""
        nonexistent = temp_dir / "does_not_exist.py"

        result = checker.check([nonexistent])

        # Should handle gracefully
        assert "error_handling_score" in result
        assert result["error_handling_score"] == 1.0  # No operations found

    def test_empty_file(self, checker, temp_dir):
        """Test handling of empty files."""
        code_file = temp_dir / "empty.py"
        code_file.write_text("")

        result = checker.check([code_file])

        assert result["error_handling_score"] == 1.0
