"""Test Case 004: DesignAlignmentChecker Baseline

Tests that DesignAlignmentChecker can parse P3 design documents and compare
with actual code to detect missing/extra implementations.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.design_alignment_checker import DesignAlignmentChecker


class TestDesignAlignmentBaseline:
    """Test design alignment checking baseline functionality."""

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

    def test_perfect_alignment(self, checker, temp_dir):
        """Test code that perfectly matches design."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
# Design Document

## Classes

### UserService
- `create_user(name: str, email: str) -> User`
- `get_user(user_id: int) -> User`

### User
Data class with id, name, email fields.
""")

        code_file = temp_dir / "service.py"
        code_file.write_text("""
class UserService:
    def create_user(self, name: str, email: str):
        return User(id=1, name=name, email=email)

    def get_user(self, user_id: int):
        return User(id=user_id, name="test", email="test@example.com")

class User:
    def __init__(self, id: int, name: str, email: str):
        self.id = id
        self.name = name
        self.email = email
""")

        result = checker.check([code_file], p3_doc=p3_doc)

        assert result["alignment_score"] == 1.0
        assert len(result["missing_elements"]) == 0
        assert len(result["extra_elements"]) == 0

    def test_missing_function(self, checker, temp_dir):
        """Test detection of missing function implementation."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
## API Functions

### fetch_data(url: str) -> dict
Fetches data from remote API.

### process_data(data: dict) -> dict
Processes the fetched data.
""")

        code_file = temp_dir / "api.py"
        code_file.write_text("""
def fetch_data(url: str):
    import requests
    return requests.get(url).json()
""")

        result = checker.check([code_file], p3_doc=p3_doc)

        assert result["alignment_score"] < 1.0
        assert len(result["missing_elements"]) == 1
        assert result["missing_elements"][0]["name"] == "process_data"
        assert result["missing_elements"][0]["type"] == "function"

    def test_extra_implementation(self, checker, temp_dir):
        """Test detection of extra code not in design."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### Calculator
- `add(a: int, b: int) -> int`
""")

        code_file = temp_dir / "calculator.py"
        code_file.write_text("""
class Calculator:
    def add(self, a: int, b: int) -> int:
        return a + b

    def subtract(self, a: int, b: int) -> int:
        return a - b

    def multiply(self, a: int, b: int) -> int:
        return a * b
""")

        result = checker.check([code_file], p3_doc=p3_doc)

        assert result["alignment_score"] == 1.0  # Has required element
        assert len(result["extra_elements"]) == 2  # subtract, multiply
        extra_names = [e["name"] for e in result["extra_elements"]]
        assert "subtract" in extra_names
        assert "multiply" in extra_names

    def test_missing_class(self, checker, temp_dir):
        """Test detection of missing class."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
## Data Models

### Product
Class with name, price, category attributes.

### Order
Class with id, products, total attributes.
""")

        code_file = temp_dir / "models.py"
        code_file.write_text("""
class Product:
    def __init__(self, name, price, category):
        self.name = name
        self.price = price
        self.category = category
""")

        result = checker.check([code_file], p3_doc=p3_doc)

        assert result["alignment_score"] == 0.5  # 1 of 2 classes
        assert len(result["missing_elements"]) == 1
        assert result["missing_elements"][0]["name"] == "Order"
        assert result["missing_elements"][0]["type"] == "class"

    def test_no_p3_doc(self, checker, temp_dir):
        """Test graceful handling when P3 document is missing."""
        code_file = temp_dir / "dummy.py"
        code_file.write_text("def test(): pass")

        result = checker.check([code_file], p3_doc=None)

        # Should return neutral result when no design doc
        assert result["alignment_score"] == 1.0
        assert len(result["missing_elements"]) == 0
        assert "warning" in result or "message" in result

    def test_multiple_files(self, checker, temp_dir):
        """Test checking multiple code files against design."""
        p3_doc = temp_dir / "design.md"
        p3_doc.write_text("""
### UserController
- `create(request) -> Response`

### UserService
- `save(user: User) -> bool`
""")

        controller_file = temp_dir / "controller.py"
        controller_file.write_text("""
class UserController:
    def create(self, request):
        return {"status": "created"}
""")

        service_file = temp_dir / "service.py"
        service_file.write_text("""
class UserService:
    def save(self, user):
        return True
""")

        result = checker.check([controller_file, service_file], p3_doc=p3_doc)

        assert result["alignment_score"] == 1.0
        assert len(result["missing_elements"]) == 0
