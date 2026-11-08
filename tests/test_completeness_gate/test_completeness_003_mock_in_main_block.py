"""Test Case 003: Mock in __main__ Block

Tests that MockDetector allows mocks in __main__ blocks (CLI testing).
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate.detectors.mock_detector import MockDetector


class TestMockInMainBlock:
    """Test mock exemption in __main__ blocks."""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def detector(self):
        return MockDetector()

    def test_allow_mock_in_main_block(self, detector, temp_dir):
        """Test that mocks in __main__ block are allowed."""
        code_file = temp_dir / "cli.py"
        code_file.write_text("""
import sys

def run_app(config):
    print(f"Running with config: {config}")
    return 0

if __name__ == "__main__":
    from unittest.mock import Mock
    mock_config = Mock()
    sys.exit(run_app(mock_config))
""")

        result = detector.check([code_file])

        assert result["has_violations"] is False
        assert len(result["violations"]) == 0

    def test_reject_mock_outside_main_block(self, detector, temp_dir):
        """Test that mocks outside __main__ are still rejected."""
        code_file = temp_dir / "hybrid.py"
        code_file.write_text("""
from unittest.mock import Mock  # ❌ Should be rejected

def get_data():
    return Mock(id=1)  # Production code with mock

if __name__ == "__main__":
    print("Demo mode")
""")

        result = detector.check([code_file])

        assert result["has_violations"] is True
        violations = result["violations"]
        assert len(violations) >= 1
        assert violations[0]["line"] == 2  # Top-level import
