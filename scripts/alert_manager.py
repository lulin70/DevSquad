#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
DevSquad Alert Manager

Notification system for critical events and alerts.

Features:
  - Multiple notification channels (Slack, Email, Console)
  - Alert severity levels (INFO, WARNING, ERROR, CRITICAL)
  - Rate limiting to prevent alert spam
  - Alert history and deduplication
  - Configurable via config/alerts.yaml

Usage:
    from scripts.alert_manager import AlertManager, AlertSeverity
    
    alerts = AlertManager()
    alerts.send_alert(
        severity=AlertSeverity.ERROR,
        title="Gate Check Failed",
        message="Build gate failed for project X",
        channel="slack"
    )
"""

import logging
import smtplib
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from enum import Enum
from typing import Any, Dict, List, Optional

import os
import yaml

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class AlertChannel(Enum):
    """Notification channels."""
    CONSOLE = "console"
    SLACK = "slack"
    EMAIL = "email"
    WEBHOOK = "webhook"
    ALL = "all"


@dataclass
class Alert:
    """Alert data structure."""
    id: str
    severity: AlertSeverity
    title: str
    message: str
    source: str
    timestamp: datetime
    channel: AlertChannel
    acknowledged: bool = False
    resolved_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "channel": self.channel.value,
            "acknowledged": self.acknowledged,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }


class AlertManager:
    """
    Centralized alert management system.
    
    Handles sending notifications through multiple channels
    with rate limiting and deduplication.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize AlertManager.
        
        Args:
            config_path: Path to alerts configuration file.
                        Defaults to config/alerts.yaml
        """
        self.config_path = config_path or os.path.join(
            os.path.dirname(__file__),
            "..",
            "config",
            "alerts.yaml"
        )
        
        self.config = self._load_config()
        self.alert_history: List[Alert] = []
        self.recent_alerts: Dict[str, datetime] = {}  # For deduplication
        
        # Rate limiting settings
        self.rate_limit_window = self.config.get("rate_limit", {}).get("window_seconds", 60)
        self.max_alerts_per_window = self.config.get("rate_limit", {}).get("max_alerts", 10)
        self._alert_count_in_window = 0
        self._window_start = datetime.now()
        
        logger.info(f"AlertManager initialized")
    
    def _load_config(self) -> Dict[str, Any]:
        """Load alert configuration."""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return yaml.safe_load(f) or {}
            return {}
        except Exception as e:
            logger.error(f"Failed to load alert config: {e}")
            return {}
    
    def _generate_alert_id(self) -> str:
        """Generate unique alert ID."""
        import hashlib
        timestamp = datetime.now().isoformat()
        return hashlib.md5(timestamp.encode()).hexdigest()[:12]
    
    def _check_rate_limit(self) -> bool:
        """
        Check if we're within rate limits.
        
        Returns:
            True if allowed to send, False if rate limited
        """
        now = datetime.now()
        
        # Reset window if expired
        if now - self._window_start > timedelta(seconds=self.rate_limit_window):
            self._window_start = now
            self._alert_count_in_window = 0
        
        if self._alert_count_in_window >= self.max_alerts_per_window:
            logger.warning("Rate limit exceeded for alerts")
            return False
        
        self._alert_count_in_window += 1
        return True
    
    def _deduplicate(self, title: str, message: str, window_minutes: int = 5) -> bool:
        """
        Check for duplicate alerts within time window.
        
        Args:
            title: Alert title
            message: Alert message
            window_minutes: Deduplication window in minutes
            
        Returns:
            True if duplicate (should skip), False if unique
        """
        key = f"{title}:{message[:50]}"
        now = datetime.now()
        
        if key in self.recent_alerts:
            last_sent = self.recent_alerts[key]
            if now - last_sent < timedelta(minutes=window_minutes):
                logger.debug(f"Duplicate alert suppressed: {title}")
                return True
        
        self.recent_alerts[key] = now
        return False
    
    def send_alert(
        self,
        severity: AlertSeverity,
        title: str,
        message: str,
        source: str = "devsquad",
        channel: Optional[str] = None,
        deduplicate: bool = True
    ) -> Optional[Alert]:
        """
        Send an alert notification.
        
        Args:
            severity: Alert severity level
            title: Short alert title
            message: Detailed alert message
            source: Alert source identifier
            channel: Specific channel or None for default
            deduplicate: Whether to check for duplicates
            
        Returns:
            Alert object if sent, None if suppressed
        """
        # Check rate limit
        if not self._check_rate_limit():
            return None
        
        # Check for duplicates
        if deduplicate and self._deduplicate(title, message):
            return None
        
        # Determine target channels
        target_channel = AlertChannel(channel) if channel else self._get_default_channel(severity)
        
        # Create alert object
        alert = Alert(
            id=self._generate_alert_id(),
            severity=severity,
            title=title,
            message=message,
            source=source,
            timestamp=datetime.now(),
            channel=target_channel
        )
        
        # Send to appropriate channel(s)
        try:
            if target_channel == AlertChannel.ALL:
                self._send_to_console(alert)
                self._send_to_slack(alert)
                self._send_to_email(alert)
            elif target_channel == AlertChannel.SLACK:
                self._send_to_slack(alert)
                self._send_to_console(alert)  # Also log to console
            elif target_channel == AlertChannel.EMAIL:
                self._send_to_email(alert)
                self._send_to_console(alert)
            else:
                self._send_to_console(alert)
            
            # Store in history
            self.alert_history.append(alert)
            
            # Trim history if too large (keep last 1000)
            if len(self.alert_history) > 1000:
                self.alert_history = self.alert_history[-1000:]
            
            logger.info(f"Alert sent: [{severity.value.upper()}] {title}")
            return alert
            
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return None
    
    def _get_default_channel(self, severity: AlertSeverity) -> AlertChannel:
        """Get default channel based on severity."""
        defaults = self.config.get("defaults", {})
        channel_map = defaults.get("channels_by_severity", {
            "critical": ["slack", "email"],
            "error": ["slack", "console"],
            "warning": ["console"],
            "info": ["console"]
        })
        
        channels = channel_map.get(severity.value, ["console"])
        if len(channels) > 1:
            return AlertChannel.ALL
        return AlertChannel(channels[0])
    
    def _send_to_console(self, alert: Alert):
        """Send alert to console/log."""
        emoji_map = {
            AlertSeverity.INFO: "ℹ️",
            AlertSeverity.WARNING: "⚠️",
            AlertSeverity.ERROR: "❌",
            AlertSeverity.CRITICAL: "🚨"
        }
        
        emoji = emoji_map.get(alert.severity, "📢")
        
        log_method = {
            AlertSeverity.INFO: logger.info,
            AlertSeverity.WARNING: logger.warning,
            AlertSeverity.ERROR: logger.error,
            AlertSeverity.CRITICAL: logger.critical
        }.get(alert.severity, logger.info)
        
        log_method(
            f"{emoji} [{alert.severity.value.upper()}] {alert.title}\n"
            f"   Source: {alert.source}\n"
            f"   Message: {alert.message}\n"
            f"   ID: {alert.id}"
        )
    
    def _send_to_slack(self, alert: Alert):
        """Send alert to Slack webhook."""
        slack_config = self.config.get("channels", {}).get("slack", {})
        webhook_url = slack_config.get("webhook_url")
        
        if not webhook_url:
            logger.debug("Slack webhook URL not configured")
            return
        
        try:
            import urllib.request
            import json
            
            color_map = {
                AlertSeverity.INFO: "#36a64f",
                AlertSeverity.WARNING: "#ff9800",
                AlertSeverity.ERROR: "#f44336",
                AlertSeverity.CRITICAL: "#9c27b0"
            }
            
            payload = {
                "attachments": [{
                    "color": color_map.get(alert.severity, "#808080"),
                    "title": f"[{alert.severity.value.upper()}] {alert.title}",
                    "text": alert.message,
                    "fields": [
                        {"title": "Source", "value": alert.source, "short": True},
                        {"title": "Severity", "value": alert.severity.value.upper(), "short": True},
                        {"title": "Alert ID", "value": alert.id, "short": True},
                        {"title": "Time", "value": alert.timestamp.strftime("%Y-%m-%d %H:%M:%S"), "short": True}
                    ],
                    "footer": "DevSquad Alert System",
                    "ts": int(alert.timestamp.timestamp())
                }]
            }
            
            data = json.dumps(payload).encode('utf-8')
            req = urllib.request.Request(
                webhook_url,
                data=data,
                headers={'Content-Type': 'application/json'}
            )
            
            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    logger.info(f"Slack alert sent successfully: {alert.id}")
                    
        except ImportError:
            logger.warning("urllib not available for Slack integration")
        except Exception as e:
            logger.error(f"Failed to send Slack alert: {e}")
    
    def _send_to_email(self, alert: Alert):
        """Send alert via email."""
        email_config = self.config.get("channels", {}).get("email", {})
        
        smtp_server = email_config.get("smtp_server")
        smtp_port = email_config.get("smtp_port", 587)
        sender = email_config.get("sender")
        recipients = email_config.get("recipients", [])
        username = email_config.get("username")
        password = email_config.get("password")
        
        if not all([smtp_server, sender, recipients]):
            logger.debug("Email configuration incomplete")
            return
        
        try:
            msg = MIMEMultipart()
            msg['From'] = sender
            msg['To'] = ', '.join(recipients)
            msg['Subject'] = f"[DevSquad-{alert.severity.value.upper()}] {alert.title}"
            
            body = f"""
DevSquad Alert Notification
============================

Severity: {alert.severity.value.upper()}
Title: {alert.title}
Source: {alert.source}
Time: {alert.timestamp.strftime("%Y-%m-%d %H:%M:%S")}
Alert ID: {alert.id}

Message:
{alert.message}

---
This is an automated message from DevSquad Alert System.
"""
            
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                if username and password:
                    server.login(username, password)
                server.sendmail(sender, recipients, msg.as_string())
            
            logger.info(f"Email alert sent successfully: {alert.id}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def get_alert_history(
        self,
        severity: Optional[AlertSeverity] = None,
        hours: int = 24,
        limit: int = 50
    ) -> List[Dict]:
        """
        Get alert history.
        
        Args:
            severity: Filter by severity (optional)
            hours: Look back period in hours
            limit: Maximum number of alerts to return
            
        Returns:
            List of alert dictionaries
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        
        filtered = [
            alert.to_dict()
            for alert in self.alert_history
            if alert.timestamp >= cutoff
            and (severity is None or alert.severity == severity)
        ]
        
        # Sort by timestamp descending
        filtered.sort(key=lambda x: x["timestamp"], reverse=True)
        
        return filtered[:limit]
    
    def get_alert_stats(self, hours: int = 24) -> Dict[str, Any]:
        """
        Get alert statistics.
        
        Args:
            hours: Statistics period in hours
            
        Returns:
            Dictionary with alert statistics
        """
        cutoff = datetime.now() - timedelta(hours=hours)
        recent_alerts = [a for a in self.alert_history if a.timestamp >= cutoff]
        
        stats = {
            "total": len(recent_alerts),
            "by_severity": {},
            "by_source": {},
            "period_hours": hours
        }
        
        for alert in recent_alerts:
            sev = alert.severity.value
            stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
            
            src = alert.source
            stats["by_source"][src] = stats["by_source"].get(src, 0) + 1
        
        return stats


# Convenience functions for quick alerts
def alert_info(title: str, message: str, **kwargs) -> Optional[Alert]:
    """Send INFO level alert."""
    mgr = AlertManager()
    return mgr.send_alert(AlertSeverity.INFO, title, message, **kwargs)

def alert_warning(title: str, message: str, **kwargs) -> Optional[Alert]:
    """Send WARNING level alert."""
    mgr = AlertManager()
    return mgr.send_alert(AlertSeverity.WARNING, title, message, **kwargs)

def alert_error(title: str, message: str, **kwargs) -> Optional[Alert]:
    """Send ERROR level alert."""
    mgr = AlertManager()
    return mgr.send_alert(AlertSeverity.ERROR, title, message, **kwargs)

def alert_critical(title: str, message: str, **kwargs) -> Optional[Alert]:
    """Send CRITICAL level alert."""
    mgr = AlertManager()
    return mgr.send_alert(AlertSeverity.CRITICAL, title, message, **kwargs)


if __name__ == "__main__":
    # Demo: Send test alerts
    print("\n🔔 DevSquad Alert Manager Demo\n")
    print("=" * 50)
    
    alerts = AlertManager()
    
    # Test different severity levels
    alerts.send_alert(AlertSeverity.INFO, "Test Info", "This is an info message")
    alerts.send_alert(AlertSeverity.WARNING, "Test Warning", "This is a warning")
    alerts.send_alert(AlertSeverity.ERROR, "Test Error", "This is an error message")
    alerts.send_alert(AlertSeverity.CRITICAL, "Test Critical", "This is critical!")
    
    # Show statistics
    stats = alerts.get_alert_stats()
    print(f"\n📊 Alert Statistics:")
    print(f"Total alerts: {stats['total']}")
    print(f"By severity: {stats['by_severity']}")
    
    print("\n✅ Demo completed!")
