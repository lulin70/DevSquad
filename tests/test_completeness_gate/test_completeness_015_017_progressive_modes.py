"""Test Case 015-017: Progressive Release Modes

Tests shadow/soft/full modes for gradual S1 Gate rollout.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from datetime import datetime, timedelta, timezone
from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


class TestProgressiveMode:
    """Test progressive release modes."""
    
    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)
    
    @pytest.fixture
    def gate(self):
        return ImplementationCompletenessGate()
    
    @pytest.fixture
    def bad_code_file(self, temp_dir):
        """Create a file with violations for testing modes."""
        code_file = temp_dir / "bad.py"
        code_file.write_text("""
from unittest.mock import Mock

def get_user():
    return Mock(id=1)
""")
        return code_file
    
    def test_shadow_mode_does_not_block(self, gate, bad_code_file):
        """Test shadow mode: violations detected but not blocking."""
        # Shadow mode: Day 0-6
        deployment_date = datetime.now(timezone.utc) - timedelta(days=3)
        
        result = gate.check(
            target_paths=[bad_code_file],
            plan={"mode": "shadow", "deployment_date": deployment_date.isoformat()}
        )
        
        # Should detect violations
        assert result["completeness_score"] < 0.90
        # But in shadow mode, verdict is overridden to PASS (non-blocking)
        assert result["mode"] == "shadow"
        assert result["original_verdict"] == "REJECT"
        assert result["verdict"] == "PASS"  # Shadow mode doesn't block
    
    def test_soft_mode_warns_but_does_not_block(self, gate, bad_code_file):
        """Test soft mode: violations logged as WARNING, doesn't fail CI."""
        # Soft mode: Day 7-13
        deployment_date = datetime.now(timezone.utc) - timedelta(days=10)
        
        result = gate.check(
            target_paths=[bad_code_file],
            plan={"mode": "soft", "deployment_date": deployment_date.isoformat()}
        )
        
        assert result["mode"] == "soft"
        assert result["original_verdict"] == "REJECT"
        # Soft mode upgrades REJECT to WARNING (CI passes with warning)
        assert result["verdict"] == "WARNING"
    
    def test_full_mode_enforces_reject(self, gate, bad_code_file):
        """Test full mode: violations fail CI."""
        # Full mode: Day 14+
        deployment_date = datetime.now(timezone.utc) - timedelta(days=20)
        
        result = gate.check(
            target_paths=[bad_code_file],
            plan={"mode": "full", "deployment_date": deployment_date.isoformat()}
        )
        
        assert result["mode"] == "full"
        assert result["verdict"] == "REJECT"
        # No override in full mode
        assert "original_verdict" not in result or result["original_verdict"] == result["verdict"]
    
    def test_auto_mode_selection_by_date(self, gate, bad_code_file):
        """Test automatic mode selection based on deployment date."""
        # Day 5 → shadow
        deployment_date_shadow = datetime.now(timezone.utc) - timedelta(days=5)
        result = gate.check(
            target_paths=[bad_code_file],
            plan={"deployment_date": deployment_date_shadow.isoformat()}
        )
        assert result["mode"] == "shadow"
        
        # Day 10 → soft
        deployment_date_soft = datetime.now(timezone.utc) - timedelta(days=10)
        result = gate.check(
            target_paths=[bad_code_file],
            plan={"deployment_date": deployment_date_soft.isoformat()}
        )
        assert result["mode"] == "soft"
        
        # Day 20 → full
        deployment_date_full = datetime.now(timezone.utc) - timedelta(days=20)
        result = gate.check(
            target_paths=[bad_code_file],
            plan={"deployment_date": deployment_date_full.isoformat()}
        )
        assert result["mode"] == "full"
