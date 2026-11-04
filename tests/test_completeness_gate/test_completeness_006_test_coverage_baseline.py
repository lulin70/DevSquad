"""Test Case 006: TestCoverageChecker Baseline

Tests that TestCoverageChecker can parse P7 test plan documents and compare
with actual test files to detect missing/extra tests.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from scripts.collaboration.gates.completeness_gate.detectors.test_coverage_checker import TestCoverageChecker


class TestCoverageBaseline:
    """Test coverage checking baseline functionality."""
    
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
    
    def test_perfect_coverage(self, checker, temp_dir):
        """Test when all planned tests are implemented."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
# Test Plan

## Test Cases

- test_user_001: Create user
- test_user_002: Update user
- test_user_003: Delete user
""")
        
        test_file = temp_dir / "test_user.py"
        test_file.write_text("""
def test_user_001():
    assert True

def test_user_002():
    assert True

def test_user_003():
    assert True
""")
        
        result = checker.check([test_file], p7_doc=p7_doc)
        
        assert result["test_coverage"] == 1.0
        assert len(result["missing_tests"]) == 0
        assert len(result["extra_tests"]) == 0
    
    def test_missing_tests(self, checker, temp_dir):
        """Test detection of missing test implementations."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
## Planned Tests

- test_login_001: Valid credentials
- test_login_002: Invalid password
- test_login_003: Account locked
""")
        
        test_file = temp_dir / "test_auth.py"
        test_file.write_text("""
def test_login_001():
    pass
""")
        
        result = checker.check([test_file], p7_doc=p7_doc)
        
        assert result["test_coverage"] < 1.0
        assert result["test_coverage"] == pytest.approx(1/3, abs=0.01)
        assert len(result["missing_tests"]) == 2
        missing_names = [t for t in result["missing_tests"]]
        assert "test_login_002" in missing_names or "test_login_002".lower() in [m.lower() for m in missing_names]
    
    def test_extra_tests(self, checker, temp_dir):
        """Test detection of extra tests not in plan."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
## Test Coverage

- test_api_001: GET endpoint
""")
        
        test_file = temp_dir / "test_api.py"
        test_file.write_text("""
def test_api_001():
    pass

def test_api_002():
    pass

def test_api_edge_case():
    pass
""")
        
        result = checker.check([test_file], p7_doc=p7_doc)
        
        assert result["test_coverage"] == 1.0  # Required test is present
        assert len(result["extra_tests"]) == 2
    
    def test_no_p7_doc(self, checker, temp_dir):
        """Test graceful handling when P7 document is missing."""
        test_file = temp_dir / "test_dummy.py"
        test_file.write_text("def test_something(): pass")
        
        result = checker.check([test_file], p7_doc=None)
        
        # Should return neutral result
        assert result["test_coverage"] == 1.0
        assert "message" in result or "warning" in result
    
    def test_empty_p7_doc(self, checker, temp_dir):
        """Test handling of empty P7 document."""
        p7_doc = temp_dir / "empty_plan.md"
        p7_doc.write_text("")
        
        test_file = temp_dir / "test_code.py"
        test_file.write_text("def test_something(): pass")
        
        result = checker.check([test_file], p7_doc=p7_doc)
        
        # Empty plan means nothing required
        assert result["test_coverage"] == 1.0
        assert len(result["missing_tests"]) == 0
    
    def test_multiple_test_files(self, checker, temp_dir):
        """Test checking multiple test files."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
- test_model_001: User model
- test_view_001: User view
""")
        
        test_model = temp_dir / "test_models.py"
        test_model.write_text("""
def test_model_001():
    pass
""")
        
        test_view = temp_dir / "test_views.py"
        test_view.write_text("""
def test_view_001():
    pass
""")
        
        result = checker.check([test_model, test_view], p7_doc=p7_doc)
        
        assert result["test_coverage"] == 1.0
        assert len(result["missing_tests"]) == 0
    
    def test_test_class_methods(self, checker, temp_dir):
        """Test detection of test methods in test classes."""
        p7_doc = temp_dir / "test_plan.md"
        p7_doc.write_text("""
- test_create
- test_update
""")
        
        test_file = temp_dir / "test_crud.py"
        test_file.write_text("""
class TestCRUD:
    def test_create(self):
        pass
    
    def test_update(self):
        pass
""")
        
        result = checker.check([test_file], p7_doc=p7_doc)
        
        assert result["test_coverage"] == 1.0
