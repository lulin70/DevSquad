"""Test Anti-Ghost Counter Verification

Ensures S1 Gate activation counters work correctly.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate


class TestAntiGhostCounters:
    """Test anti-ghost verification counters."""
    
    @pytest.fixture
    def temp_dir(self):
        tmpdir = tempfile.mkdtemp()
        yield Path(tmpdir)
        shutil.rmtree(tmpdir)
    
    @pytest.fixture
    def gate(self):
        return ImplementationCompletenessGate()
    
    @pytest.fixture
    def sample_file(self, temp_dir):
        code_file = temp_dir / "sample.py"
        code_file.write_text("def hello(): return 'world'")
        return code_file
    
    def test_activation_counter_increments(self, gate, sample_file):
        """Test _activation_counter increments on each check() call."""
        initial_stats = gate.get_activation_stats()
        assert initial_stats["activation_counter"] == 0
        
        gate.check([sample_file])
        stats_1 = gate.get_activation_stats()
        assert stats_1["activation_counter"] == 1
        
        gate.check([sample_file])
        stats_2 = gate.get_activation_stats()
        assert stats_2["activation_counter"] == 2
    
    def test_trigger_counter_increments(self, gate, sample_file):
        """Test _trigger_counter increments when check is actually executed."""
        gate.check([sample_file])
        stats = gate.get_activation_stats()
        
        # Should equal activation_counter (no skips)
        assert stats["trigger_counter"] == stats["activation_counter"]
        assert stats["trigger_counter"] > 0
    
    def test_skip_counter_remains_zero(self, gate, sample_file):
        """Test _skip_counter remains 0 when no conditions skip execution."""
        gate.check([sample_file])
        gate.check([sample_file])
        stats = gate.get_activation_stats()
        
        # No skips in current implementation
        assert stats["skip_counter"] == 0
    
    def test_counters_persist_across_calls(self, gate, sample_file):
        """Test counters accumulate across multiple check() calls."""
        for i in range(5):
            gate.check([sample_file])
        
        stats = gate.get_activation_stats()
        assert stats["activation_counter"] == 5
        assert stats["trigger_counter"] == 5
        assert stats["skip_counter"] == 0
