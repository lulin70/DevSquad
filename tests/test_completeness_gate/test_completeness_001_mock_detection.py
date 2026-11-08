"""Test Case 001: Mock Detection Baseline

Tests that MockDetector identifies unittest.mock usage in production code.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.mock_detector import MockDetector


class TestMockDetection:
    """Test mock detection in production code."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test files."""
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def detector(self):
        """Create MockDetector instance."""
        return MockDetector()

    def test_detect_mock_import(self, detector, temp_dir):
        """Test detection of Mock import in production code."""
        code_file = temp_dir / "production.py"
        code_file.write_text("""
from unittest.mock import Mock

def get_user():
    return Mock(id=1, name="test")
""")

        result = detector.check([code_file])

        assert result["has_violations"] is True
        # Should detect both the import AND the usage (2 violations)
        assert len(result["violations"]) >= 1
        violations = result["violations"]
        # Check that Mock import is detected
        import_violation = next((v for v in violations if v["line"] == 2), None)
        assert import_violation is not None
        assert import_violation["file"] == str(code_file)
        assert "Mock" in import_violation["pattern"]

    def test_detect_magic_mock(self, detector, temp_dir):
        """Test detection of MagicMock usage."""
        code_file = temp_dir / "service.py"
        code_file.write_text("""
from unittest.mock import MagicMock

class UserService:
    def __init__(self):
        self.db = MagicMock()
""")

        result = detector.check([code_file])

        assert result["has_violations"] is True
        assert any("MagicMock" in v["pattern"] for v in result["violations"])

    def test_detect_patch_decorator(self, detector, temp_dir):
        """Test detection of @patch in production code."""
        code_file = temp_dir / "api_client.py"
        code_file.write_text("""
from unittest.mock import patch

@patch('requests.get')
def fetch_data(mock_get):
    return {"data": "test"}
""")

        result = detector.check([code_file])

        assert result["has_violations"] is True
        assert any("patch" in v["pattern"] for v in result["violations"])

    def test_no_mock_in_clean_code(self, detector, temp_dir):
        """Test clean production code returns no violations."""
        code_file = temp_dir / "clean.py"
        code_file.write_text("""
import requests

def fetch_data():
    response = requests.get("https://api.example.com")
    return response.json()
""")

        result = detector.check([code_file])

        assert result["has_violations"] is False
        assert len(result["violations"]) == 0
