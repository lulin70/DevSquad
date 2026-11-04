# DevSquad V5.0 - Simplicity Role - CRAPGate Unit Tests
# P8 Implementation Phase - Test-Driven Development
# Based on P7 Test Plan v1.0

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import json
import subprocess


@pytest.fixture
def mock_radon_output_simple():
    """Mock radon cc output: simple function (CC=2, CRAP=3.0)"""
    return json.dumps({
        "test_file.py": [
            {
                "type": "function",
                "name": "simple_function",
                "lineno": 10,
                "col_offset": 0,
                "endline": 15,
                "closures": [],
                "complexity": 2
            }
        ]
    })


@pytest.fixture
def mock_radon_output_complex():
    """Mock radon cc output: complex function (CC=8, CRAP=16.0)"""
    return json.dumps({
        "complex_file.py": [
            {
                "type": "function",
                "name": "complex_function",
                "lineno": 20,
                "col_offset": 0,
                "endline": 50,
                "closures": [],
                "complexity": 8
            }
        ]
    })


# Test Suite: CRAPGate Unit Tests (P7-001 to P7-007)

class TestCRAPGateCalculation:
    """Test CRAP score calculation logic"""
    
    def test_crap_001_below_threshold_pass(self, mock_radon_output_simple):
        """
        test_crap_001: CRAP ≤ 10 (PASS)
        
        Given: radon reports CC=2 for a simple function
        When: calculate_crap_scores() is called
        Then: CRAP score ≤ 10, status = PASS
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout=mock_radon_output_simple,
                returncode=0
            )
            
            gate = CRAPGate(threshold=10.0)
            result = gate.check(target_paths=[Path("test_file.py")])
            
            assert result["status"] == "PASS"
            assert result["max_crap"] <= 10.0
            assert len(result["violations"]) == 0
    
    def test_crap_002_warning_range(self):
        """
        test_crap_002: 10 < CRAP ≤ 15 (WARNING)
        
        Given: radon reports CC=3 (CRAP = 12.0 without coverage)
        When: check() is called
        Then: status = WARNING
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        mock_output = json.dumps({
            "medium_file.py": [{
                "type": "function",
                "name": "medium_function",
                "complexity": 3
            }]
        })
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stdout=mock_output, returncode=0)
            
            gate = CRAPGate(threshold=10.0)
            result = gate.check(target_paths=[Path("medium_file.py")])
            
            assert result["status"] == "WARNING"
            assert 10.0 < result["max_crap"] <= 15.0
    
    def test_crap_003_above_threshold_reject(self, mock_radon_output_complex):
        """
        test_crap_003: CRAP > 15 (REJECT)
        
        Given: radon reports CC=8 (CRAP ≈ 16.0)
        When: check() is called
        Then: status = REJECT, violations list contains the function
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout=mock_radon_output_complex,
                returncode=0
            )
            
            gate = CRAPGate(threshold=10.0)
            result = gate.check(target_paths=[Path("complex_file.py")])
            
            assert result["status"] == "REJECT"
            assert result["max_crap"] > 15.0
            assert len(result["violations"]) > 0
            assert "complex_function" in result["violations"][0]["function"]
    
    def test_crap_004_coverage_impact(self):
        """
        test_crap_004: Coverage impact on CRAP score
        
        Given: CC=5, Coverage=80%
        When: calculate_crap_scores(coverage_data={"file.py": 0.8})
        Then: CRAP = 5^2 * (1 - 0.8)^3 + 5 = 5.2 (lower than no coverage)
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        mock_output = json.dumps({
            "covered_file.py": [{
                "type": "function",
                "name": "covered_function",
                "complexity": 5
            }]
        })
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(stdout=mock_output, returncode=0)
            
            gate = CRAPGate()
            scores = gate.calculate_crap_scores(
                target_paths=[Path("covered_file.py")],
                coverage_data={"covered_file.py": 0.8}
            )
            
            assert len(scores) > 0
            assert scores[0].crap_score < 10.0  # Should be ~5.2
    
    def test_crap_005_empty_file_pass(self):
        """
        test_crap_005: Empty file (no functions)
        
        Given: radon reports no functions
        When: check() is called
        Then: status = PASS, max_crap = 0
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout=json.dumps({"empty.py": []}),
                returncode=0
            )
            
            gate = CRAPGate()
            result = gate.check(target_paths=[Path("empty.py")])
            
            assert result["status"] == "PASS"
            assert result["max_crap"] == 0.0
    
    def test_crap_006_radon_timeout_handling(self):
        """
        test_crap_006: Radon execution timeout (>30s)
        
        Given: subprocess.run() raises TimeoutExpired
        When: calculate_crap_scores() is called
        Then: Log warning and return empty list
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(
                cmd='radon cc',
                timeout=30
            )
            
            gate = CRAPGate()
            scores = gate.calculate_crap_scores(
                target_paths=[Path("timeout_file.py")]
            )
            
            assert scores == []  # Should handle timeout gracefully
    
    def test_crap_007_radon_json_parse_error(self):
        """
        test_crap_007: Radon JSON parsing error
        
        Given: radon returns invalid JSON
        When: calculate_crap_scores() is called
        Then: Log error and return empty list
        """
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                stdout="Invalid JSON {{{",
                returncode=0
            )
            
            gate = CRAPGate()
            scores = gate.calculate_crap_scores(
                target_paths=[Path("invalid_json.py")]
            )
            
            assert scores == []  # Should handle parse error gracefully


