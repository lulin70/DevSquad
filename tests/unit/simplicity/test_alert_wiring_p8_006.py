"""P8-006: AlertSystem wiring integration tests (TD-078 / W3).

Verifies the bypass path is never silent:

- DEVSQUAD_SKIP_SIMPLICITY=1 triggers send_bypass_alert (P1)
- approver comes from DEVSQUAD_SKIP_SIMPLICITY_APPROVER
- alert delivery failure never blocks the bypass itself
- without PagerDuty/Slack credentials the alert still lands in the
  local JSONL history (graceful degradation contract)
"""

from __future__ import annotations

import json
import os
from unittest.mock import Mock, patch

import pytest


@pytest.fixture
def mock_workflow_trace():
    trace = Mock()
    trace.record = Mock()
    return trace


@pytest.fixture
def mock_engine():
    return Mock()


@pytest.fixture
def bypass_plan():
    plan = Mock()
    plan.phase = "P8"
    return plan


class TestAlertSystemWiring:
    """P8-006 integration: bypass events raise a P1 alert."""

    def test_bypass_sends_p1_alert(self, mock_workflow_trace, mock_engine, bypass_plan) -> None:
        """Bypass path calls send_bypass_alert with phase and approver."""
        from scripts.collaboration.alert_system import AlertSystem
        from scripts.collaboration.simplicity_role import SimplicityRole

        role = SimplicityRole(mock_workflow_trace, mock_engine)
        with (
            patch.dict(
                os.environ,
                {"DEVSQUAD_SKIP_SIMPLICITY": "1", "DEVSQUAD_SKIP_SIMPLICITY_APPROVER": "ops-oncall"},
            ),
            patch.object(AlertSystem, "send_bypass_alert", return_value=True) as mock_send,
        ):
            result = role.activate(bypass_plan, [])

        assert result is None
        mock_send.assert_called_once_with(reason="Emergency bypass enabled", approver="ops-oncall", phase="P8")
        mock_workflow_trace.record.assert_called()

    def test_bypass_alert_failure_is_non_blocking(self, mock_workflow_trace, mock_engine, bypass_plan) -> None:
        """AlertSystem blowing up must not break the bypass path."""
        from scripts.collaboration.alert_system import AlertSystem
        from scripts.collaboration.simplicity_role import SimplicityRole

        role = SimplicityRole(mock_workflow_trace, mock_engine)
        with (
            patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": "1"}),
            patch.object(AlertSystem, "send_bypass_alert", side_effect=RuntimeError("network down")),
        ):
            result = role.activate(bypass_plan, [])

        assert result is None
        mock_workflow_trace.record.assert_called()

    def test_no_credentials_still_records_history(
        self, mock_workflow_trace, mock_engine, bypass_plan, tmp_path
    ) -> None:
        """Graceful degradation: no PagerDuty/Slack keys -> local history only."""
        from scripts.collaboration.alert_system import AlertSystem
        from scripts.collaboration.simplicity_role import SimplicityRole

        history_file = tmp_path / ".alert_history.jsonl"
        role = SimplicityRole(mock_workflow_trace, mock_engine)
        with (
            patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": "1"}),
            patch.object(AlertSystem, "HISTORY_FILE", history_file),
        ):
            alert_system = AlertSystem()
            assert alert_system.pagerduty_key == ""
            assert alert_system.slack_webhook == ""

            role.activate(bypass_plan, [])

        assert history_file.exists(), "bypass alert must be persisted even without credentials"
        records = [json.loads(line) for line in history_file.read_text().splitlines() if line.strip()]
        assert len(records) == 1
        assert records[0]["title"] == "Simplicity Gate Bypass Activated"
        assert records[0]["severity"] == "P1"
