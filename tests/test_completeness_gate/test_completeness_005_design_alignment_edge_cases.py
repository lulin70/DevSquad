"""Test Case 005: DesignAlignmentChecker Edge Cases

Tests edge cases and error handling for DesignAlignmentChecker.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from scripts.collaboration.gates.completeness_gate.detectors.design_alignment_checker import DesignAlignmentChecker


class TestDesignAlignmentEdgeCases:
    """Test design alignment edge cases."""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)
    
    @pytest.fixture
    def checker(self):
        """Create DesignAlignmentChecker instance."""
        return DesignAlignmentChecker()
    
    def test_malformed_markdown(self, checker, temp_dir):
        """Test handling of malformed markdown in P3 doc."""
        p3_doc = temp_dir / "bad_design.md"
        p3_doc.write_text("""
# Incomplete Design

### SomeClass
- method1(
- method2)
[[broken link
""")
        
        code_file = temp_dir / "code.py"
        code_file.write_text("""
class SomeClass:
    def method1(self): pass
""")
        
        # Should not raise exception, should extract what it can
        result = checker.check([code_file], p3_doc=p3_doc)
        
        assert "alignment_score" in result
        assert isinstance(result["alignment_score"], (int, float))
    
    def test_syntax_error_in_code(self, checker, temp_dir):
        """Test handling of syntax errors in code files."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### Calculator
- `add(a, b)`
""")
        
        code_file = temp_dir / "broken.py"
        code_file.write_text("""
def add(a, b
    return a + b  # Missing closing paren
""")
        
        # Should skip files with syntax errors gracefully
        result = checker.check([code_file], p3_doc=p3_doc)
        
        assert "alignment_score" in result
        assert result["alignment_score"] < 1.0  # Missing implementation
    
    def test_empty_design_doc(self, checker, temp_dir):
        """Test handling of empty design document."""
        p3_doc = temp_dir / "empty.md"
        p3_doc.write_text("")
        
        code_file = temp_dir / "code.py"
        code_file.write_text("""
def some_function():
    pass
""")
        
        result = checker.check([code_file], p3_doc=p3_doc)
        
        # Empty design means nothing required, so alignment is perfect
        assert result["alignment_score"] == 1.0
        assert len(result["missing_elements"]) == 0
    
    def test_empty_code_files(self, checker, temp_dir):
        """Test handling of empty code files."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### Processor
- `process(data)`
""")
        
        code_file = temp_dir / "empty.py"
        code_file.write_text("")
        
        result = checker.check([code_file], p3_doc=p3_doc)
        
        # Design requires elements but code is empty
        assert result["alignment_score"] == 0.0
        assert len(result["missing_elements"]) > 0
    
    def test_case_insensitive_matching(self, checker, temp_dir):
        """Test case-insensitive matching of class/function names."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### UserService
- `GetUser(id)`
""")
        
        code_file = temp_dir / "service.py"
        code_file.write_text("""
class UserService:
    def get_user(self, id):
        return {"id": id}
""")
        
        result = checker.check([code_file], p3_doc=p3_doc)
        
        # Should match case-insensitively for common naming conventions
        assert result["alignment_score"] == 1.0
    
    def test_private_methods_not_required(self, checker, temp_dir):
        """Test that private methods (starting with _) are not required in design."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### DataProcessor
- `process(input)`
""")
        
        code_file = temp_dir / "processor.py"
        code_file.write_text("""
class DataProcessor:
    def process(self, input):
        return self._internal_process(input)
    
    def _internal_process(self, input):
        return input.upper()
""")
        
        result = checker.check([code_file], p3_doc=p3_doc)
        
        # _internal_process is private, should not count as extra
        assert result["alignment_score"] == 1.0
        assert len(result["missing_elements"]) == 0
        # Private methods should not be flagged as extra
        extra_names = [e["name"] for e in result["extra_elements"]]
        assert "_internal_process" not in extra_names
    
    def test_nested_classes(self, checker, temp_dir):
        """Test handling of nested classes."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### Container
Outer class.

### Container.Inner
Nested class inside Container.
""")
        
        code_file = temp_dir / "nested.py"
        code_file.write_text("""
class Container:
    class Inner:
        pass
""")
        
        result = checker.check([code_file], p3_doc=p3_doc)
        
        # Should detect both outer and nested classes
        assert result["alignment_score"] >= 0.5  # At least Container found
    
    def test_decorators_ignored(self, checker, temp_dir):
        """Test that decorators don't affect function matching."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### APIEndpoint
- `handle_request(data)`
""")
        
        code_file = temp_dir / "endpoint.py"
        code_file.write_text("""
class APIEndpoint:
    @staticmethod
    @cache_result
    def handle_request(data):
        return {"result": data}
""")
        
        result = checker.check([code_file], p3_doc=p3_doc)
        
        # Decorators should not prevent matching
        assert result["alignment_score"] == 1.0
    
    def test_nonexistent_code_file(self, checker, temp_dir):
        """Test handling of non-existent code files."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### Foo
- `bar()`
""")
        
        nonexistent = temp_dir / "does_not_exist.py"
        
        result = checker.check([nonexistent], p3_doc=p3_doc)
        
        # Should handle gracefully
        assert "alignment_score" in result
        assert result["alignment_score"] < 1.0
