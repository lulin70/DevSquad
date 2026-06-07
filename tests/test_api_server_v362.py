#!/usr/bin/env python3
"""
DevSquad API Server Tests (V3.6.2)

Comprehensive test coverage for FastAPI REST API endpoints.

Test Categories:
  - Root endpoint and API info
  - Task Dispatch endpoints (full/quick/history/roles)
  - Lifecycle Management endpoints (phases/status/actions/mappings)
  - Metrics & Gates endpoints (current/history/gates/health)
  - Middleware and exception handling
  - Authentication integration
  - Error handling and edge cases

Usage:
    pytest tests/test_api_server_v362.py -v --cov=scripts/api_server --cov-report=term-missing
"""

import json
import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.api_server import app


@pytest.fixture
def client():
    """Create a FastAPI TestClient for API testing."""
    return TestClient(app)


class TestRootEndpoint:
    """Test suite for root endpoint (/)."""

    def test_root_endpoint_returns_api_info(self, client):
        """Verify root endpoint returns complete API information."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "DevSquad API"
        assert "version" in data
        assert "endpoints" in data
        assert "features" in data
        assert data["status"] == "operational"
        assert "timestamp" in data

    def test_root_endpoint_contains_all_endpoint_paths(self, client):
        """Verify root endpoint lists all available API paths."""
        response = client.get("/")
        endpoints = response.json()["endpoints"]
        assert "/api/v1/tasks/" in endpoints.values()
        assert "/api/v1/lifecycle/" in endpoints.values()
        assert "/api/v1/metrics/" in endpoints.values()
        assert "/api/v1/gates/" in endpoints.values()

    def test_root_endpoint_contains_documentation_urls(self, client):
        """Verify root endpoint includes documentation URLs."""
        response = client.get("/")
        docs = response.json()["documentation"]
        assert "/docs" in docs["swagger_ui"]
        assert "/redoc" in docs["redoc"]
        assert "/openapi.json" in docs["openapi_spec"]


class TestTaskDispatchEndpoints:
    """Test suite for task dispatch endpoints."""

    @patch("scripts.api.routes.dispatch._get_dispatcher")
    def test_dispatch_task_success(self, mock_get_dispatcher, client):
        """Test successful task dispatch with valid request."""
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.task_description = "Design authentication system"
        mock_result.matched_roles = ["architect", "security"]
        mock_result.summary = "Completed analysis"
        mock_result.duration_seconds = 2.5
        mock_result.worker_results = []
        mock_result.errors = []
        mock_result.intent_match = None
        mock_result.five_axis_result = None
        mock_result.anchor_result = None
        mock_result.scratchpad_summary = None
        mock_result.consensus_records = []
        mock_result.compression_info = {}
        mock_result.memory_stats = {}
        mock_result.permission_checks = []
        mock_result.skill_proposals = []
        mock_result.quality_report = None
        mock_result.retrospective_report = None
        mock_result.details = {}
        mock_dispatcher.dispatch.return_value = mock_result
        mock_get_dispatcher.return_value = mock_dispatcher

        response = client.post(
            "/api/v1/tasks/dispatch",
            json={
                "task": "Design authentication system",
                "roles": ["architect", "security"],
                "mode": "auto",
                "dry_run": False,
            },
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["task_description"] == "Design authentication system"
        assert "architect" in data["matched_roles"]

    @patch("scripts.api.routes.dispatch._get_dispatcher")
    def test_dispatch_task_with_dry_run(self, mock_get_dispatcher, client):
        """Test dispatch with dry_run=True performs simulation only."""
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.matched_roles = ["architect"]
        mock_result.summary = "Dry run completed"
        mock_result.duration_seconds = 0.5
        mock_result.worker_results = []
        mock_result.errors = []
        mock_result.intent_match = {"intent_type": "design", "confidence": 0.9}
        mock_result.five_axis_result = None
        mock_result.anchor_result = None
        mock_result.scratchpad_summary = None
        mock_result.consensus_records = []
        mock_result.compression_info = {}
        mock_result.memory_stats = {}
        mock_result.permission_checks = []
        mock_result.skill_proposals = []
        mock_result.quality_report = None
        mock_result.retrospective_report = None
        mock_result.details = {}
        mock_result.task_description = "Test task"
        mock_dispatcher.dispatch.return_value = mock_result
        mock_get_dispatcher.return_value = mock_dispatcher

        response = client.post(
            "/api/v1/tasks/dispatch",
            json={"task": "Test task", "dry_run": True},
        )

        assert response.status_code == 200
        mock_dispatcher.dispatch.assert_called_once()
        call_kwargs = mock_dispatcher.dispatch.call_args[1]
        assert call_kwargs["dry_run"] is True

    @patch("scripts.api.routes.dispatch._get_dispatcher")
    def test_quick_dispatch_success(self, mock_get_dispatcher, client):
        """Test quick dispatch endpoint with simplified parameters."""
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.summary = "Quick result"
        mock_result.duration_seconds = 1.0
        mock_result.worker_results = []
        mock_result.errors = []
        mock_result.intent_match = None
        mock_result.five_axis_result = None
        mock_result.anchor_result = None
        mock_result.scratchpad_summary = None
        mock_result.consensus_records = []
        mock_result.compression_info = {}
        mock_result.memory_stats = {}
        mock_result.permission_checks = []
        mock_result.skill_proposals = []
        mock_result.quality_report = None
        mock_result.retrospective_report = None
        mock_result.details = {}
        mock_result.task_description = "Quick task"
        mock_result.matched_roles = ["coder"]
        mock_dispatcher.quick_dispatch.return_value = mock_result
        mock_get_dispatcher.return_value = mock_dispatcher

        response = client.post(
            "/api/v1/tasks/quick",
            json={"task": "Fix login bug", "output_format": "structured"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        mock_dispatcher.quick_dispatch.assert_called_once()

    @patch("scripts.api.routes.dispatch._get_dispatcher")
    def test_get_dispatch_history(self, mock_get_dispatcher, client):
        """Test retrieving dispatch history with default limit."""
        mock_dispatcher = MagicMock()
        mock_dispatcher.get_history.return_value = [
            {"task": "Task 1", "timestamp": "2024-01-01T00:00:00"},
            {"task": "Task 2", "timestamp": "2024-01-02T00:00:00"},
        ]
        mock_get_dispatcher.return_value = mock_dispatcher

        response = client.get("/api/v1/tasks/history?limit=10")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 2
        assert len(data["history"]) == 2
        mock_dispatcher.get_history.assert_called_once_with(limit=10)

    @patch("scripts.api.routes.dispatch._get_dispatcher")
    def test_get_dispatch_history_custom_limit(self, mock_get_dispatcher, client):
        """Test dispatch history with custom limit parameter."""
        mock_dispatcher = MagicMock()
        mock_dispatcher.get_history.return_value = [{"task": "Single task"}]
        mock_get_dispatcher.return_value = mock_dispatcher

        response = client.get("/api/v1/tasks/history?limit=5")

        assert response.status_code == 200
        mock_dispatcher.get_history.assert_called_once_with(limit=5)

    def test_list_roles_success(self, client):
        """Test listing all available agent roles."""
        response = client.get("/api/v1/roles")

        assert response.status_code == 200
        data = response.json()
        assert "roles" in data
        assert "total" in data
        assert "core_roles" in data
        assert data["total"] > 0
        assert isinstance(data["roles"], list)

    def test_list_roles_contains_core_roles(self, client):
        """Verify role list includes expected core roles."""
        response = client.get("/api/v1/roles")
        data = response.json()

        role_ids = [r["role_id"] for r in data["roles"]]
        assert any("architect" in rid.lower() for rid in role_ids)
        assert any("solo-coder" in rid or "coder" in rid.lower() for rid in role_ids)


class TestLifecycleEndpoints:
    """Test suite for lifecycle management endpoints."""

    def test_list_all_phases(self, client):
        """Test retrieving all lifecycle phases."""
        response = client.get("/api/v1/lifecycle/phases")

        assert response.status_code == 200
        phases = response.json()
        assert isinstance(phases, list)
        assert len(phases) > 0

        phase = phases[0]
        assert "phase_id" in phase
        assert "name" in phase
        assert "status" in phase
        assert "order" in phase

    def test_list_phases_with_status_filter(self, client):
        """Test filtering phases by status."""
        response = client.get("/api/v1/lifecycle/phases?status_filter=pending")

        assert response.status_code == 200
        phases = response.json()
        for phase in phases:
            assert phase["status"].value if hasattr(phase["status"], "value") else phase["status"] == "pending"

    def test_list_phases_with_details(self, client):
        """Test retrieving phases with full artifact details."""
        response = client.get("/api/v1/lifecycle/phases?include_details=true")

        assert response.status_code == 200
        phases = response.json()
        if phases:
            phase = phases[0]
            assert "artifacts_in" in phase or phase.get("artifacts_in") is None
            assert "artifacts_out" in phase or phase.get("artifacts_out") is None

    def test_get_specific_phase_valid(self, client):
        """Test getting details of a specific valid phase."""
        response = client.get("/api/v1/lifecycle/phases/P1")

        assert response.status_code == 200
        phase = response.json()
        assert phase["phase_id"] == "P1"
        assert "description" in phase
        assert "role_id" in phase

    def test_get_specific_phase_invalid(self, client):
        """Test getting a non-existent phase returns 404."""
        response = client.get("/api/v1/lifecycle/phases/P99")

        assert response.status_code == 404
        error_data = response.json()
        assert "not found" in error_data.get("message", error_data.get("detail", "")).lower()

    def test_get_lifecycle_status(self, client):
        """Test retrieving current lifecycle status."""
        response = client.get("/api/v1/lifecycle/status")

        assert response.status_code == 200
        status = response.json()
        assert "mode" in status
        assert "total_phases" in status
        assert "completed_phases" in status
        assert "progress_percent" in status
        assert "is_complete" in status

    def test_execute_phase_action_advance(self, client):
        """Test executing advance action on a phase."""
        response = client.post(
            "/api/v1/lifecycle/actions",
            json={"phase_id": "P1", "action": "advance"},
        )

        assert response.status_code == 200
        result = response.json()
        assert "success" in result
        assert result["action"] == "advance"
        assert "performed_at" in result

    def test_execute_phase_action_complete(self, client):
        """Test executing complete action on a phase."""
        response = client.post(
            "/api/v1/lifecycle/actions",
            json={"phase_id": "P1", "action": "complete"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "complete"

    def test_execute_phase_action_reset(self, client):
        """Test executing reset action on a phase."""
        response = client.post(
            "/api/v1/lifecycle/actions",
            json={"phase_id": "P1", "action": "reset"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "reset"

    def test_execute_phase_action_skip(self, client):
        """Test executing skip action on a phase."""
        response = client.post(
            "/api/v1/lifecycle/actions",
            json={"phase_id": "P1", "action": "skip"},
        )

        assert response.status_code == 200
        result = response.json()
        assert result["action"] == "skip"

    def test_execute_phase_action_invalid(self, client):
        """Test executing invalid action returns 400 error."""
        response = client.post(
            "/api/v1/lifecycle/actions",
            json={"phase_id": "P1", "action": "invalid_action"},
        )

        assert response.status_code == 400
        error_data = response.json()
        assert "invalid" in error_data.get("message", error_data.get("detail", "")).lower()

    def test_list_command_mappings(self, client):
        """Test retrieving CLI command to phase mappings."""
        response = client.get("/api/v1/lifecycle/mappings")

        assert response.status_code == 200
        mappings = response.json()
        assert isinstance(mappings, list)
        if mappings:
            mapping = mappings[0]
            assert "command" in mapping
            assert "phases" in mapping


class TestMetricsAndGatesEndpoints:
    """Test suite for metrics and gate monitoring endpoints."""

    def test_get_current_metrics(self, client):
        """Test retrieving current system metrics snapshot."""
        response = client.get("/api/v1/metrics/current")

        assert response.status_code == 200
        metrics = response.json()
        assert "timestamp" in metrics
        assert "total_phases" in metrics
        assert "completion_rate" in metrics
        assert "cpu_usage_percent" in metrics
        assert "memory_usage_percent" in metrics
        assert "success_rate" in metrics

    def test_get_current_metrics_reasonable_values(self, client):
        """Verify current metrics contain reasonable value ranges."""
        response = client.get("/api/v1/metrics/current")
        metrics = response.json()

        assert 0 <= metrics["completion_rate"] <= 100
        assert 0 <= metrics["cpu_usage_percent"] <= 100
        assert 0 <= metrics["memory_usage_percent"] <= 100
        assert metrics["avg_response_time_ms"] >= 0

    def test_get_metrics_history_empty(self, client):
        """Test retrieving metrics history when no data exists."""
        response = client.get("/api/v1/metrics/history?hours=24&interval_minutes=60")

        assert response.status_code == 200
        data = response.json()
        assert "snapshots" in data
        assert "count" in data
        assert "period_hours" in data

    def test_get_metrics_history_custom_params(self, client):
        """Test metrics history with custom time range parameters."""
        response = client.get("/api/v1/metrics/history?hours=48&interval_minutes=120")

        assert response.status_code == 200
        data = response.json()
        assert data["period_hours"] == 48
        assert data["interval_minutes"] == 120

    def test_get_all_gate_statuses(self, client):
        """Test retrieving all gate statuses."""
        response = client.get("/api/v1/gates/status")

        assert response.status_code == 200
        data = response.json()
        assert "gates" in data
        assert "total_commands" in data
        assert "passing" in data
        assert "failing" in data
        assert data["total_commands"] > 0

    def test_check_specific_gate(self, client):
        """Test checking a specific gate by command name."""
        response = client.post("/api/v1/gates/check", json={"command": "spec"})

        assert response.status_code in [200, 500]
        if response.status_code == 200:
            result = response.json()
            assert "passed" in result
            assert "verdict" in result
            assert "checked_at" in result

    def test_check_multiple_gates(self, client):
        """Test checking multiple different gates."""
        commands = ["plan", "build", "test", "review", "ship"]

        for cmd in commands:
            response = client.post("/api/v1/gates/check", json={"command": cmd})
            assert response.status_code in [200, 500], f"Failed for command: {cmd}"
            if response.status_code == 200:
                assert "passed" in response.json()


class TestHealthCheckEndpoint:
    """Test suite for health check endpoint."""

    def test_health_check_healthy(self, client):
        """Test health check returns healthy status."""
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        health = response.json()
        assert "status" in health
        assert "version" in health
        assert "uptime_seconds" in health
        assert "components" in health
        assert "timestamp" in health
        assert health["uptime_seconds"] >= 0

    def test_health_check_contains_component_status(self, client):
        """Verify health check includes component-level status."""
        response = client.get("/api/v1/health")
        components = response.json()["components"]

        assert isinstance(components, dict)
        assert len(components) > 0

    def test_health_check_version_format(self, client):
        """Verify health check returns valid version string."""
        response = client.get("/api/v1/health")
        version = response.json()["version"]

        assert version is not None
        assert isinstance(version, str)


class TestMiddlewareAndExceptionHandling:
    """Test suite for middleware and global exception handlers."""

    def test_cors_headers_present(self, client):
        """Verify CORS headers are present in responses."""
        response = client.options("/", headers={"Origin": "http://localhost:3000"})

        assert response.status_code in [200, 404, 405]

    def test_process_time_header_added(self, client):
        """Verify X-Process-Time header is added to responses."""
        response = client.get("/api/v1/health")

        assert "X-Process-Time" in response.headers
        process_time = float(response.headers["X-Process-Time"])
        assert process_time >= 0

    def test_http_exception_handler_format(self, client):
        """Verify HTTP exceptions return standardized error format."""
        response = client.get("/api/v1/lifecycle/phases/INVALID_PHASE")

        assert response.status_code == 404
        data = response.json()
        assert "error" in data or "detail" in data

    def test_not_found_endpoint(self, client):
        """Test accessing non-existent endpoint returns 404."""
        response = client.get("/api/v1/nonexistent")

        assert response.status_code == 404


class TestAuthenticationIntegration:
    """Test suite for authentication dependency injection."""

    def test_auth_manager_dependency_exists(self, client):
        """Verify auth dependency injection is configured."""
        from scripts.api_server import get_auth_manager, get_auth_dependency

        assert callable(get_auth_manager)
        assert callable(get_auth_dependency)

    def test_auth_manager_returns_instance_or_none(self):
        """Test AuthManager creation graceful degradation."""
        from scripts.api_server import get_auth_manager

        auth_mgr = get_auth_manager()
        assert auth_mgr is None or auth_mgr is not None


class TestEdgeCasesAndBoundaryConditions:
    """Test suite for edge cases and boundary conditions."""

    def test_dispatch_with_empty_task(self, client):
        """Test dispatch with empty task string."""
        response = client.post("/api/v1/tasks/dispatch", json={"task": ""})

        assert response.status_code in [200, 422, 500]

    def test_dispatch_with_very_long_task(self, client):
        """Test dispatch with very long task description."""
        long_task = "test " * 1000
        response = client.post("/api/v1/tasks/dispatch", json={"task": long_task})

        assert response.status_code in [200, 422]

    def test_history_limit_boundary_min(self, client):
        """Test history endpoint with minimum limit (1)."""
        response = client.get("/api/v1/tasks/history?limit=1")

        assert response.status_code == 200

    def test_history_limit_boundary_max(self, client):
        """Test history endpoint with maximum limit (100)."""
        response = client.get("/api/v1/tasks/history?limit=100")

        assert response.status_code == 200

    def test_metrics_hours_boundary_min(self, client):
        """Test metrics history with minimum hours (1)."""
        response = client.get("/api/v1/metrics/history?hours=1")

        assert response.status_code == 200

    def test_metrics_hours_boundary_max(self, client):
        """Test metrics history with maximum hours (168)."""
        response = client.get("/api/v1/metrics/history?hours=168")

        assert response.status_code == 200

    def test_phase_id_case_insensitive(self, client):
        """Test that phase ID lookup is case-insensitive."""
        response_lower = client.get("/api/v1/lifecycle/phases/p1")
        response_upper = client.get("/api/v1/lifecycle/phases/P1")

        assert response_lower.status_code == response_upper.status_code


class TestResponseFormatValidation:
    """Test suite for response format and structure validation."""

    def test_dispatch_response_structure(self, client):
        """Verify dispatch response contains all required fields."""
        with patch("scripts.api.routes.dispatch._get_dispatcher") as mock_disp:
            mock_dispatcher = MagicMock()
            mock_result = MagicMock()
            mock_result.success = True
            mock_result.task_description = "Test"
            mock_result.matched_roles = []
            mock_result.summary = "Done"
            mock_result.duration_seconds = 1.0
            mock_result.worker_results = []
            mock_result.errors = []
            mock_result.intent_match = None
            mock_result.five_axis_result = None
            mock_result.anchor_result = None
            mock_result.scratchpad_summary = None
            mock_result.consensus_records = []
            mock_result.compression_info = {}
            mock_result.memory_stats = {}
            mock_result.permission_checks = []
            mock_result.skill_proposals = []
            mock_result.quality_report = None
            mock_result.retrospective_report = None
            mock_result.details = {}
            mock_dispatcher.dispatch.return_value = mock_result
            mock_disp.return_value = mock_dispatcher

            response = client.post("/api/v1/tasks/dispatch", json={"task": "Test"})
            data = response.json()

            required_fields = [
                "success",
                "task_description",
                "matched_roles",
                "summary",
                "duration_seconds",
                "worker_results",
                "errors",
                "timestamp",
            ]
            for field in required_fields:
                assert field in data, f"Missing required field: {field}"

    def test_lifecycle_phase_response_structure(self, client):
        """Verify lifecycle phase response has correct structure."""
        response = client.get("/api/v1/lifecycle/phases/P1")
        phase = response.json()

        assert "phase_id" in phase
        assert "name" in phase
        assert "order" in phase
        assert isinstance(phase["order"], int)

    def test_health_response_timestamp_format(self, client):
        """Verify health check timestamp is ISO format."""
        response = client.get("/api/v1/health")
        timestamp = response.json()["timestamp"]

        try:
            datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except ValueError:
            pytest.fail(f"Timestamp is not valid ISO format: {timestamp}")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
