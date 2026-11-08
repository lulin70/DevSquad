"""Test Case 014: Gate Integration - Threshold REJECT

Tests that scores <90% return REJECT verdict.
"""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


class TestGateThresholdReject:
    """Test gate REJECT threshold (<90%)."""

    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)

    @pytest.fixture
    def gate(self):
        return ImplementationCompletenessGate()

    def test_reject_with_mocks(self, gate, temp_dir):
        """Test REJECT verdict when production code contains mocks."""
        code_file = temp_dir / "bad_module.py"
        code_file.write_text("""
from unittest.mock import Mock

def get_user():
    # ❌ CRITICAL: Mock in production
    return Mock(id=1, name="test")
""")

        result = gate.check(target_paths=[code_file])

        # Mock violation → mock_score=0.0 (20% weight) → overall score drops significantly
        assert result["verdict"] == "REJECT"
        assert result["completeness_score"] < 0.90
        assert result["details"]["mock_score"] == 0.0
        assert len(result["details"]["mock_violations"]) > 0

    def test_reject_with_multiple_violations(self, gate, temp_dir):
        """Test REJECT with multiple detector failures."""
        code_file = temp_dir / "very_bad_module.py"
        code_file.write_text("""
from unittest.mock import Mock

def risky_operation():
    # ❌ No error handling
    import requests
    return requests.get("https://example.com").json()

def mock_factory():
    # ❌ Mock in production
    return Mock()
""")

        result = gate.check(target_paths=[code_file])

        assert result["verdict"] == "REJECT"
        assert result["completeness_score"] < 0.90
        # Multiple issues: mock_score=0.0, error_handling_score likely low
        assert result["details"]["mock_score"] == 0.0
