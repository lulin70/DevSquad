"""Test Case 012: Gate Integration - Threshold PASS

Tests that completeness gate correctly calculates overall score and returns PASS verdict.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


class TestGateThresholdPass:
    """Test gate integration and PASS threshold."""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def gate(self):
        return ImplementationCompletenessGate()

    def test_perfect_score_pass(self, gate, temp_dir):
        """Test perfect implementation scores PASS (100%)."""
        # Clean production code
        code_file = temp_dir / "clean_module.py"
        code_file.write_text("""
def fetch_data():
    try:
        import requests
        response = requests.get("https://api.example.com", timeout=5)
        return response.json()
    except requests.RequestException as e:
        print(f"Error: {e}")
        return None
""")

        # No P3/P7 docs → design alignment and test coverage default to 1.0
        result = gate.check(target_paths=[code_file])

        assert result["verdict"] == "PASS"
        assert result["completeness_score"] >= 0.95  # ≥95% → PASS
        assert result["details"]["mock_score"] == 1.0  # No mocks

    def test_high_score_pass(self, gate, temp_dir):
        """Test score ≥95% returns PASS."""
        code_file = temp_dir / "module.py"
        code_file.write_text("""
def process():
    return "ok"
""")

        result = gate.check(target_paths=[code_file])

        assert result["verdict"] == "PASS"
        assert result["completeness_score"] >= 0.95
        assert "timestamp" in result
