"""Test Case 002: Mock Exemption for Test Files

Tests that MockDetector allows mocks in test files (test_*.py).
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from scripts.collaboration.gates.completeness_gate.detectors.mock_detector import MockDetector


class TestMockExemption:
    """Test mock exemption rules."""
    
    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)
    
    @pytest.fixture
    def detector(self):
        return MockDetector()
    
    def test_allow_mock_in_test_file(self, detector, temp_dir):
        """Test that test_*.py files can use mocks."""
        test_file = temp_dir / "test_user_service.py"
        test_file.write_text("""
from unittest.mock import Mock

def test_get_user():
    mock_db = Mock()
    mock_db.query.return_value = {"id": 1}
    assert get_user(mock_db) is not None
""")
        
        result = detector.check([test_file])
        
        assert result["has_violations"] is False
        assert len(result["violations"]) == 0
    
    def test_allow_mock_in_tests_directory(self, detector, temp_dir):
        """Test that tests/**/*.py files can use mocks."""
        tests_dir = temp_dir / "tests"
        tests_dir.mkdir()
        test_file = tests_dir / "integration_test.py"
        test_file.write_text("""
from unittest.mock import MagicMock

def test_api_call():
    mock_http = MagicMock()
    assert call_api(mock_http) == 200
""")
        
        result = detector.check([test_file])
        
        assert result["has_violations"] is False
    
    def test_allow_mock_with_pattern_star_test_py(self, detector, temp_dir):
        """Test that *_test.py files can use mocks."""
        test_file = temp_dir / "user_service_test.py"
        test_file.write_text("""
from unittest.mock import patch

@patch('requests.get')
def test_fetch_user(mock_get):
    mock_get.return_value.json.return_value = {"id": 1}
    assert fetch_user() == {"id": 1}
""")
        
        result = detector.check([test_file])
        
        assert result["has_violations"] is False
