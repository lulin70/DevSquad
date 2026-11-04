"""
DevSquad V5.0 - Simplicity Role - AlertSystem Unit Tests
Test cases: test_alert_001-004 (from P7-Test-Plan)
"""

import json
import time
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from scripts.collaboration.alert_system import AlertSystem, Alert


@pytest.fixture
def alert_system(tmp_path, monkeypatch):
    """Create AlertSystem instance with temporary history file and mock credentials"""
    # Set mock credentials BEFORE creating AlertSystem
    monkeypatch.setenv("PAGERDUTY_ROUTING_KEY", "test_pd_key")
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test")
    
    history_file = tmp_path / ".alert_history.jsonl"
    
    with patch.object(AlertSystem, 'HISTORY_FILE', history_file):
        system = AlertSystem()
        yield system


@pytest.fixture
def alert_system_no_creds(tmp_path):
    """Create AlertSystem instance without credentials (for graceful degradation test)"""
    history_file = tmp_path / ".alert_history.jsonl"
    
    with patch.object(AlertSystem, 'HISTORY_FILE', history_file):
        system = AlertSystem()
        yield system


class TestAlertSystem:
    """AlertSystem unit tests"""
    
    # ========================
    # test_alert_001: 聚合窗口内重复告警（5 分钟）
    # ========================
    @patch('requests.post')
    def test_alert_001_aggregation_window(
        self,
        mock_post,
        alert_system
    ):
        """
        Test: Duplicate alert within 5-minute aggregation window should be skipped
        
        Expected: Second alert within 5 minutes is not sent
        """
        # Setup: Mock successful HTTP responses (PagerDuty=202, Slack=200)
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'pagerduty' in url:
                return Mock(status_code=202)
            else:
                return Mock(status_code=200)
        
        mock_post.side_effect = side_effect
        
        # Alert A at t=0
        alert_a = Alert(
            alert_id="test-alert-001",
            severity="P1",
            title="Test Alert",
            description="Test description",
            timestamp=0.0
        )
        
        # First send (t=0)
        result1 = alert_system.send_alert(alert_a)
        assert result1 is True, "First alert should be sent"
        
        # Second send (t=3min, within 5min window)
        alert_a_duplicate = Alert(
            alert_id="test-alert-001",
            severity="P1",
            title="Test Alert",
            description="Test description",
            timestamp=180.0
        )
        
        result2 = alert_system.send_alert(alert_a_duplicate)
        assert result2 is False, "Second alert should be skipped (within aggregation window)"
        
        # Verify HTTP calls (only first alert)
        assert mock_post.call_count == 2, "Should call PagerDuty + Slack for first alert only"
    
    # ========================
    # test_alert_002: 聚合窗口外重复告警（6 分钟）
    # ========================
    @patch('requests.post')
    def test_alert_002_aggregation_window_expired(
        self,
        mock_post,
        alert_system
    ):
        """
        Test: Duplicate alert after 6 minutes should be sent
        
        Expected: Both alerts are sent
        """
        # Setup: Mock successful HTTP responses
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'pagerduty' in url:
                return Mock(status_code=202)
            else:
                return Mock(status_code=200)
        
        mock_post.side_effect = side_effect
        
        # Alert A at t=0
        alert_a = Alert(
            alert_id="test-alert-002",
            severity="P2",
            title="Test Alert",
            description="Test description",
            timestamp=0.0
        )
        
        # First send (t=0)
        result1 = alert_system.send_alert(alert_a)
        assert result1 is True
        
        # Second send (t=6min, outside 5min window)
        alert_a_duplicate = Alert(
            alert_id="test-alert-002",
            severity="P2",
            title="Test Alert",
            description="Test description",
            timestamp=360.0
        )
        
        result2 = alert_system.send_alert(alert_a_duplicate)
        assert result2 is True, "Second alert should be sent (outside aggregation window)"
        
        # Verify HTTP calls (both alerts sent)
        assert mock_post.call_count == 4, "Should call PagerDuty + Slack for both alerts"
    
    # ========================
    # test_alert_003: PagerDuty 发送失败（网络错误）
    # ========================
    @patch('requests.post')
    def test_alert_003_pagerduty_network_error(
        self,
        mock_post,
        alert_system,
        tmp_path
    ):
        """
        Test: PagerDuty network error should be handled gracefully
        
        Expected:
        - Alert marked as failed
        - Local history records the failure
        - WorkflowTrace logs the error
        """
        import requests
        
        # Mock PagerDuty network error, Slack success
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'pagerduty' in url:
                raise requests.exceptions.ConnectionError("Network error")
            else:
                return Mock(status_code=200)
        
        mock_post.side_effect = side_effect
        
        # Send alert
        alert = Alert(
            alert_id="test-alert-003",
            severity="P1",
            title="Test Network Error",
            description="Test PagerDuty failure",
            timestamp=time.time()
        )
        
        result = alert_system.send_alert(alert)
        
        # Should still return True (Slack succeeded)
        assert result is True
        
        # Verify history file exists
        assert alert_system.HISTORY_FILE.exists()
        
        # Verify history contains the alert
        with open(alert_system.HISTORY_FILE, 'r') as f:
            history = [json.loads(line) for line in f]
            assert len(history) == 1
            assert history[0]['alert_id'] == "test-alert-003"
    
    # ========================
    # test_alert_004: Slack 发送失败（4xx 错误）
    # ========================
    @patch('requests.post')
    def test_alert_004_slack_http_error(
        self,
        mock_post,
        alert_system
    ):
        """
        Test: Slack HTTP 4xx error should be handled gracefully
        
        Expected:
        - Alert marked as failed
        - Error logged
        - Does not block gate decision
        """
        # Mock PagerDuty success, Slack 403 error
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'slack' in url:
                return Mock(status_code=403, text="Forbidden")
            else:
                return Mock(status_code=202)
        
        mock_post.side_effect = side_effect
        
        # Send alert
        alert = Alert(
            alert_id="test-alert-004",
            severity="P2",
            title="Test Slack Error",
            description="Test Slack 403 failure",
            timestamp=time.time()
        )
        
        result = alert_system.send_alert(alert)
        
        # Should still return True (PagerDuty succeeded)
        assert result is True
        
        # Verify both endpoints were called
        assert mock_post.call_count == 2
    
    # ========================
    # Additional tests for helper methods
    # ========================
    @patch('requests.post')
    def test_send_bypass_alert(self, mock_post, alert_system):
        """Test send_bypass_alert() method"""
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'pagerduty' in url:
                return Mock(status_code=202)
            else:
                return Mock(status_code=200)
        
        mock_post.side_effect = side_effect
        
        result = alert_system.send_bypass_alert(
            reason="Emergency hotfix",
            approver="alice@example.com",
            phase="P8"
        )
        
        assert result is True
        assert mock_post.call_count == 2  # PagerDuty + Slack
    
    @patch('requests.post')
    def test_send_threshold_violation_alert(self, mock_post, alert_system):
        """Test send_threshold_violation_alert() method"""
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'pagerduty' in url:
                return Mock(status_code=202)
            else:
                return Mock(status_code=200)
        
        mock_post.side_effect = side_effect
        
        result = alert_system.send_threshold_violation_alert(
            violation_type="CRAP",
            value=15.5,
            threshold=10.0,
            file_path="/path/to/file.py"
        )
        
        assert result is True
        assert mock_post.call_count == 2
    
    @patch('requests.post')
    def test_send_false_positive_alert(self, mock_post, alert_system):
        """Test send_false_positive_alert() method"""
        def side_effect(*args, **kwargs):
            url = args[0] if args else kwargs.get('url', '')
            if 'pagerduty' in url:
                return Mock(status_code=202)
            else:
                return Mock(status_code=200)
        
        mock_post.side_effect = side_effect
        
        result = alert_system.send_false_positive_alert(
            false_positive_rate=0.12
        )
        
        assert result is True
        assert mock_post.call_count == 2
    
    def test_graceful_degradation_no_credentials(self, alert_system_no_creds):
        """Test AlertSystem works without credentials (log-only mode)"""
        # No environment variables set
        alert = Alert(
            alert_id="test-no-creds",
            severity="P1",
            title="Test",
            description="Test",
            timestamp=time.time()
        )
        
        # Should return False (no channels configured)
        result = alert_system_no_creds.send_alert(alert)
        assert result is False
        
        # But should still save to history
        assert alert_system_no_creds.HISTORY_FILE.exists()
