# DevSquad V5.0 - Simplicity Role - SimplicityRole Unit Tests
# P8 Implementation Phase - Test-Driven Development
# Based on P7 Test Plan v1.0

import pytest
import os
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


@pytest.fixture
def mock_workflow_trace():
    """Mock WorkflowTrace"""
    trace = Mock()
    trace.record = Mock()
    return trace


@pytest.fixture
def mock_unified_gate_engine():
    """Mock UnifiedGateEngine"""
    engine = Mock()
    return engine


@pytest.fixture
def mock_execution_plan():
    """Mock ExecutionPlan"""
    plan = Mock()
    plan.phase = "P8"
    plan.target_files = [Path("test_file.py")]
    return plan


@pytest.fixture
def mock_worker_results():
    """Mock WorkerResult list"""
    result = Mock()
    result.role = "coder"
    result.output = "Implementation complete"
    return [result]


class TestSimplicityRoleActivation:
    """Test SimplicityRole activation flow"""
    
    def test_activate_001_bypass_enabled(
        self, 
        mock_workflow_trace, 
        mock_unified_gate_engine,
        mock_execution_plan,
        mock_worker_results
    ):
        """
        test_activate_001: Bypass enabled (DEVSQUAD_SKIP_SIMPLICITY=1)
        
        Given: Environment variable DEVSQUAD_SKIP_SIMPLICITY=1
        When: activate() is called
        Then: Returns None, logs bypass event, sends alert
        """
        from scripts.collaboration.simplicity_role import SimplicityRole
        
        with patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": "1"}):
            role = SimplicityRole(mock_workflow_trace, mock_unified_gate_engine)
            result = role.activate(mock_execution_plan, mock_worker_results)
            
            assert result is None
            mock_workflow_trace.record.assert_called()
            
            # Check anti-ghost counters
            stats = role.get_activation_stats()
            assert stats["activation_counter"] == 1
            assert stats["skip_counter"] == 1
            assert stats["trigger_counter"] == 0
    
    def test_activate_002_wrong_phase(
        self,
        mock_workflow_trace,
        mock_unified_gate_engine,
        mock_execution_plan,
        mock_worker_results
    ):
        """
        test_activate_002: Trigger condition not met (non-P8 phase)
        
        Given: plan.phase = "P7"
        When: activate() is called
        Then: Returns None, skip_counter increments
        """
        from scripts.collaboration.simplicity_role import SimplicityRole
        
        mock_execution_plan.phase = "P7"
        
        role = SimplicityRole(mock_workflow_trace, mock_unified_gate_engine)
        result = role.activate(mock_execution_plan, mock_worker_results)
        
        assert result is None
        stats = role.get_activation_stats()
        assert stats["skip_counter"] == 1
    
    def test_activate_003_crap_pass(
        self,
        mock_workflow_trace,
        mock_unified_gate_engine,
        mock_execution_plan,
        mock_worker_results
    ):
        """
        test_activate_003: CRAP ≤ 10 (PASS)
        
        Given: CRAPGate returns max_crap=8.5
        When: activate() is called
        Then: Returns SimplicityAuditResult(status=PASS)
        """
        from scripts.collaboration.simplicity_role import SimplicityRole
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        mock_crap_result = {
            "status": "PASS",
            "max_crap": 8.5,
            "violations": [],
            "summary": "All functions pass"
        }
        
        with patch.object(CRAPGate, 'check', return_value=mock_crap_result):
            role = SimplicityRole(mock_workflow_trace, mock_unified_gate_engine)
            result = role.activate(mock_execution_plan, mock_worker_results)
            
            assert result is not None
            assert result.status == "PASS"
            assert result.verdict == "PASS"
            assert result.metrics["max_crap"] == 8.5
    
    def test_activate_004_crap_reject_shadow_mode(
        self,
        mock_workflow_trace,
        mock_unified_gate_engine,
        mock_execution_plan,
        mock_worker_results
    ):
        """
        test_activate_004: CRAP > 15 (REJECT) in Shadow mode → ADVISORY
        
        Given: CRAPGate returns REJECT, current mode = "shadow"
        When: activate() is called
        Then: verdict changed to ADVISORY
        """
        from scripts.collaboration.simplicity_role import SimplicityRole
        from scripts.collaboration.gates.crap_gate import CRAPGate
        from scripts.collaboration.simplicity_config import SimplicityConfig
        
        mock_crap_result = {
            "status": "REJECT",
            "max_crap": 18.0,
            "violations": [{"function": "complex_func", "crap": 18.0, "file": "test.py", "line": 10}],
            "summary": "1 violation"
        }
        
        with patch.object(CRAPGate, 'check', return_value=mock_crap_result), \
             patch.object(SimplicityConfig, 'get_current_mode', return_value="shadow"):
            
            role = SimplicityRole(mock_workflow_trace, mock_unified_gate_engine)
            result = role.activate(mock_execution_plan, mock_worker_results)
            
            assert result.status == "REJECT"
            assert result.verdict == "ADVISORY"  # Downgraded in shadow mode
            assert result.mode == "shadow"
    
    def test_activate_005_anti_ghost_counters(
        self,
        mock_workflow_trace,
        mock_unified_gate_engine,
        mock_execution_plan,
        mock_worker_results
    ):
        """
        test_activate_005: Anti-ghost verification (counter correctness)
        
        Given: Multiple activate() calls
        When: get_activation_stats() is called
        Then: Counters match actual invocations
        """
        from scripts.collaboration.simplicity_role import SimplicityRole
        from scripts.collaboration.gates.crap_gate import CRAPGate
        
        mock_crap_result = {"status": "PASS", "max_crap": 5.0, "violations": [], "summary": "OK"}
        
        with patch.object(CRAPGate, 'check', return_value=mock_crap_result):
            role = SimplicityRole(mock_workflow_trace, mock_unified_gate_engine)
            
            # First call: P8 phase (trigger)
            role.activate(mock_execution_plan, mock_worker_results)
            
            # Second call: P7 phase (skip)
            mock_execution_plan.phase = "P7"
            role.activate(mock_execution_plan, mock_worker_results)
            
            # Third call: P8 phase (trigger)
            mock_execution_plan.phase = "P8"
            role.activate(mock_execution_plan, mock_worker_results)
            
            stats = role.get_activation_stats()
            assert stats["activation_counter"] == 3
            assert stats["trigger_counter"] == 2
            assert stats["skip_counter"] == 1
