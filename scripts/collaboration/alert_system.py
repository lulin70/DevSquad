# DevSquad - Simplicity Role - AlertSystem Implementation
# PagerDuty + Slack integration for real-time alerts

"""
AlertSystem: Multi-channel alert notification system

Features:
- PagerDuty Events API v2 integration
- Slack webhook integration
- 5-minute aggregation window (deduplication)
- Alert severities: P1 (bypass), P2 (threshold violation, false positive)
- Local history persistence
- Graceful degradation (missing credentials → log-only mode)

Environment Variables:
- PAGERDUTY_ROUTING_KEY: PagerDuty integration key (optional)
- SLACK_WEBHOOK_URL: Slack incoming webhook URL (optional)
"""

import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import requests
except ImportError:
    requests = None  # Graceful degradation


logger = logging.getLogger(__name__)


@dataclass
class Alert:
    """Alert notification data"""
    alert_id: str
    severity: str  # P1, P2, P3
    title: str
    description: str
    timestamp: float
    source: str = "DevSquad-Simplicity"
    metadata: dict | None = None


class AlertSystem:
    """
    Multi-channel alert notification system
    
    Integrations:
    - PagerDuty Events API v2
    - Slack Incoming Webhooks
    
    Features:
    - 5-minute aggregation window (deduplicate alerts)
    - Local history persistence
    - Graceful degradation (missing credentials)
    """
    
    AGGREGATION_WINDOW = 300  # 5 minutes in seconds
    HISTORY_FILE = Path.home() / ".devsquad" / ".alert_history.jsonl"
    
    def __init__(self) -> None:
        """Initialize AlertSystem (reads environment variables)"""
        self.pagerduty_key = os.getenv("PAGERDUTY_ROUTING_KEY", "")
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL", "")
        
        # Alert history for aggregation (in-memory cache)
        self._alert_cache: dict[str, float] = {}  # {alert_id: last_sent_timestamp}
        
        # Ensure history directory exists
        self.HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
        
        # Load history from disk
        self._load_history()
    
    def _load_history(self) -> None:
        """Load alert history from disk"""
        if not self.HISTORY_FILE.exists():
            return
        
        try:
            with open(self.HISTORY_FILE, 'r') as f:
                for line in f:
                    try:
                        record = json.loads(line.strip())
                        alert_id = record.get("alert_id", "")
                        timestamp = record.get("timestamp", 0.0)
                        self._alert_cache[alert_id] = timestamp
                    except json.JSONDecodeError:
                        continue
        except Exception as e:
            logger.warning(f"Failed to load alert history: {e}")
    
    def _save_to_history(self, alert: Alert) -> None:
        """Append alert to local history (JSONL format)"""
        try:
            with open(self.HISTORY_FILE, 'a') as f:
                f.write(json.dumps(asdict(alert)) + "\n")
        except Exception as e:
            logger.error(f"Failed to save alert history: {e}")
    
    def _should_send_alert(self, alert: Alert) -> bool:
        """
        Check if alert should be sent (aggregation window logic)
        
        Returns:
            True if alert should be sent (not in aggregation window)
        """
        last_sent = self._alert_cache.get(alert.alert_id, None)
        
        # If alert was never sent before, always send it
        if last_sent is None:
            return True
        
        time_since_last = alert.timestamp - last_sent
        
        if time_since_last < self.AGGREGATION_WINDOW:
            logger.info(
                f"Alert {alert.alert_id} skipped (within {self.AGGREGATION_WINDOW}s window)"
            )
            return False
        
        return True
    
    def _send_to_pagerduty(self, alert: Alert) -> bool:
        """
        Send alert to PagerDuty Events API v2
        
        Returns:
            True if successful, False otherwise
        """
        if not self.pagerduty_key:
            logger.warning("PagerDuty routing key not configured, skipping")
            return False
        
        if requests is None:
            logger.error("requests library not available, cannot send to PagerDuty")
            return False
        
        # PagerDuty Events API v2 endpoint
        url = "https://events.pagerduty.com/v2/enqueue"
        
        # Construct payload
        payload = {
            "routing_key": self.pagerduty_key,
            "event_action": "trigger",
            "payload": {
                "summary": alert.title,
                "severity": alert.severity.lower(),
                "source": alert.source,
                "timestamp": datetime.fromtimestamp(alert.timestamp).isoformat(),
                "custom_details": {
                    "description": alert.description,
                    "alert_id": alert.alert_id,
                    **(alert.metadata or {})
                }
            }
        }
        
        try:
            response = requests.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 202:
                logger.info(f"PagerDuty alert sent successfully: {alert.alert_id}")
                return True
            else:
                logger.error(
                    f"PagerDuty API error: {response.status_code} - {response.text}"
                )
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"PagerDuty network error: {e}")
            return False
        except Exception as e:
            logger.error(f"PagerDuty unexpected error: {e}")
            return False
    
    def _send_to_slack(self, alert: Alert) -> bool:
        """
        Send alert to Slack Incoming Webhook
        
        Returns:
            True if successful, False otherwise
        """
        if not self.slack_webhook:
            logger.warning("Slack webhook URL not configured, skipping")
            return False
        
        if requests is None:
            logger.error("requests library not available, cannot send to Slack")
            return False
        
        # Construct Slack message (Block Kit format)
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"🚨 {alert.title}"
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Severity:* {alert.severity}"},
                        {"type": "mrkdwn", "text": f"*Source:* {alert.source}"},
                        {"type": "mrkdwn", "text": f"*Alert ID:* `{alert.alert_id}`"},
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:* {datetime.fromtimestamp(alert.timestamp).strftime('%Y-%m-%d %H:%M:%S')}"
                        }
                    ]
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Description:*\n{alert.description}"
                    }
                }
            ]
        }
        
        # Add metadata if present
        if alert.metadata:
            metadata_text = "\n".join(
                f"• *{k}:* {v}" for k, v in alert.metadata.items()
            )
            payload["blocks"].append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Metadata:*\n{metadata_text}"
                }
            })
        
        try:
            response = requests.post(
                self.slack_webhook,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=5
            )
            
            if response.status_code == 200:
                logger.info(f"Slack alert sent successfully: {alert.alert_id}")
                return True
            else:
                logger.error(
                    f"Slack API error: {response.status_code} - {response.text}"
                )
                return False
        
        except requests.exceptions.RequestException as e:
            logger.error(f"Slack network error: {e}")
            return False
        except Exception as e:
            logger.error(f"Slack unexpected error: {e}")
            return False
    
    def send_alert(self, alert: Alert) -> bool:
        """
        Send alert to all configured channels
        
        Args:
            alert: Alert object
        
        Returns:
            True if at least one channel succeeded, False if all failed
        """
        # Check aggregation window
        if not self._should_send_alert(alert):
            return False
        
        # Send to both channels
        pagerduty_success = self._send_to_pagerduty(alert)
        slack_success = self._send_to_slack(alert)
        
        # Update cache if at least one succeeded
        if pagerduty_success or slack_success:
            self._alert_cache[alert.alert_id] = alert.timestamp
            self._save_to_history(alert)
            return True
        
        # Both failed, save to history anyway
        self._save_to_history(alert)
        return False
    
    def send_bypass_alert(
        self,
        reason: str,
        approver: str,
        phase: str
    ) -> bool:
        """
        Send bypass alert (P1 severity)
        
        Args:
            reason: Bypass reason
            approver: Approver name/ID
            phase: Workflow phase (e.g., "P8")
        
        Returns:
            True if sent successfully
        """
        alert_id = hashlib.sha256(
            f"bypass-{phase}-{reason}-{approver}".encode()
        ).hexdigest()[:16]
        
        alert = Alert(
            alert_id=alert_id,
            severity="P1",
            title="Simplicity Gate Bypass Activated",
            description=f"Reason: {reason}\nApprover: {approver}\nPhase: {phase}",
            timestamp=time.time(),
            metadata={
                "reason": reason,
                "approver": approver,
                "phase": phase
            }
        )
        
        return self.send_alert(alert)
    
    def send_threshold_violation_alert(
        self,
        violation_type: str,
        value: float,
        threshold: float,
        file_path: str
    ) -> bool:
        """
        Send threshold violation alert (P2 severity)
        
        Args:
            violation_type: "CRAP" or "Duplication"
            value: Actual value
            threshold: Threshold value
            file_path: File path
        
        Returns:
            True if sent successfully
        """
        alert_id = hashlib.sha256(
            f"threshold-{violation_type}-{file_path}".encode()
        ).hexdigest()[:16]
        
        alert = Alert(
            alert_id=alert_id,
            severity="P2",
            title=f"Simplicity Gate Violation: {violation_type}",
            description=(
                f"File: {file_path}\n"
                f"Value: {value:.2f}\n"
                f"Threshold: {threshold:.2f}\n"
                f"Violation Type: {violation_type}"
            ),
            timestamp=time.time(),
            metadata={
                "violation_type": violation_type,
                "value": value,
                "threshold": threshold,
                "file_path": file_path
            }
        )
        
        return self.send_alert(alert)
    
    def send_false_positive_alert(
        self,
        false_positive_rate: float
    ) -> bool:
        """
        Send false positive rate alert (P2 severity)
        
        Args:
            false_positive_rate: Current false positive rate (0.0-1.0)
        
        Returns:
            True if sent successfully
        """
        alert_id = hashlib.sha256(
            f"false-positive-{false_positive_rate:.3f}".encode()
        ).hexdigest()[:16]
        
        alert = Alert(
            alert_id=alert_id,
            severity="P2",
            title="Simplicity Gate High False Positive Rate",
            description=(
                f"False positive rate: {false_positive_rate * 100:.1f}%\n"
                f"Threshold: 10%\n"
                f"Action: Consider downgrading enforcement mode"
            ),
            timestamp=time.time(),
            metadata={
                "false_positive_rate": false_positive_rate,
                "threshold": 0.1
            }
        )
        
        return self.send_alert(alert)
