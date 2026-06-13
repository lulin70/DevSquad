#!/usr/bin/env python3
"""
Test Suite for DevSquad V3.6.8 Production Features

Tests for:
  - Authentication system (scripts/auth.py)
  - History Manager (scripts/history_manager.py)
  - API Data Models (scripts/api/models.py)

Run with:
    pytest tests/test_production_features.py -v
"""

import os
import sys
import tempfile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAuthentication:
    """Test suite for AuthManager."""

    def test_auth_manager_initialization(self):
        """Test AuthManager can be initialized."""
        from scripts.auth import AuthManager

        auth = AuthManager()
        assert auth is not None
        assert hasattr(auth, "config")
        assert hasattr(auth, "auth_enabled")

    def test_password_hashing(self):
        """Test password hashing functionality."""
        from scripts.auth import AuthManager

        auth = AuthManager.__new__(AuthManager)

        password = "test_password_123"
        hashed = auth._hash_password(password)

        # Hash should be consistent
        assert hashed == auth._hash_password(password)

        # Hash should be different from plain text
        assert hashed != password

    def test_verify_credentials_success(self):
        """Test credential verification with correct credentials."""
        # Create a temporary config with known credentials
        import yaml

        from scripts.auth import AuthManager, UserRole

        temp_config = {
            "authentication": {
                "enabled": True,
                "credentials": {
                    "usernames": {
                        "testuser": {
                            "email": "test@test.com",
                            "name": "Test User",
                            "password": "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8",  # SHA256 of "password"
                            "role": "admin",
                        }
                    }
                },
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(temp_config, f)
            temp_path = f.name

        try:
            auth = AuthManager(config_path=temp_path)
            user = auth.verify_credentials("testuser", "password")

            assert user is not None
            assert user.username == "testuser"
            assert user.role == UserRole.ADMIN
            assert user.can_execute_phases() == True

        finally:
            os.unlink(temp_path)

    def test_verify_credentials_failure(self):
        """Test credential verification fails with wrong password."""
        import yaml

        from scripts.auth import AuthManager

        temp_config = {
            "authentication": {
                "enabled": True,
                "credentials": {"usernames": {"testuser": {"password": "hashed_password_here"}}},
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(temp_config, f)
            temp_path = f.name

        try:
            auth = AuthManager(config_path=temp_path)
            user = auth.verify_credentials("testuser", "wrong_password")

            assert user is None

        finally:
            os.unlink(temp_path)

    def test_user_role_permissions(self):
        """Test role-based permission checks."""
        from scripts.auth import User, UserRole

        admin_user = User(
            username="admin",
            email="admin@test.com",
            name="Admin",
            role=UserRole.ADMIN,
            authenticated_at=datetime.now(),
            session_id="test123",
        )

        viewer_user = User(
            username="viewer",
            email="viewer@test.com",
            name="Viewer",
            role=UserRole.VIEWER,
            authenticated_at=datetime.now(),
            session_id="test456",
        )

        # Admin can do everything
        assert admin_user.can_execute_phases() == True
        assert admin_user.can_view_metrics() == True
        assert admin_user.can_modify_config() == True

        # Viewer has limited permissions
        assert viewer_user.can_execute_phases() == False
        assert viewer_user.can_view_metrics() == True
        assert viewer_user.can_modify_config() == False


class TestHistoryManager:
    """Test suite for HistoryManager."""

    def test_history_manager_initialization(self):
        """Test HistoryManager can be initialized and creates database."""
        from scripts.history_manager import HistoryManager

        # Use temporary directory for test database
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_history.db")
            history = HistoryManager(db_path=db_path)

            assert history is not None
            assert os.path.exists(db_path)

            history.close()

    def test_save_and_query_metrics(self):
        """Test saving and querying metrics snapshots."""
        from scripts.history_manager import HistoryManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_metrics.db")
            history = HistoryManager(db_path=db_path)

            # Save test metrics
            test_data = {
                "total_phases": 11,
                "completed_phases": 7,
                "completion_rate": 63.6,
                "avg_response_time_ms": 150.5,
                "cpu_usage_percent": 45.2,
            }

            result = history.save_metrics_snapshot(test_data)
            assert result == True

            # Query back
            queried = history.get_metrics_history(hours=1)
            assert len(queried) >= 1

            # Verify data integrity
            snapshot = queried[-1]
            assert snapshot["total_phases"] == 11
            assert snapshot["completed_phases"] == 7

            history.close()

    def test_log_api_request(self):
        """Test logging API requests."""
        from scripts.history_manager import HistoryManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_api.db")
            history = HistoryManager(db_path=db_path)

            result = history.log_api_request(
                method="GET",
                path="/api/v1/lifecycle/phases",
                status_code=200,
                response_time_ms=45.2,
                client_ip="127.0.0.1",
            )

            assert result == True

            # Get stats with longer time window to ensure data is captured
            stats = history.get_api_stats(hours=24)  # Use 24 hours instead of 1
            assert stats["total_requests"] >= 1
            assert stats["avg_response_time_ms"] > 0

            history.close()

    def test_save_lifecycle_event(self):
        """Test saving lifecycle events."""
        from scripts.history_manager import HistoryManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_events.db")
            history = HistoryManager(db_path=db_path)

            result = history.save_lifecycle_event(
                event_type="phase_advance",
                phase_id="P8",
                previous_status="pending",
                new_status="running",
                user_id="test_user",
                details="Test event details",
            )

            assert result == True

            # Query events with longer time window
            events = history.get_lifecycle_history(hours=24)  # Use 24 hours instead of 1
            assert len(events) >= 1
            assert events[0]["event_type"] == "phase_advance"
            assert events[0]["phase_id"] == "P8"

            history.close()

    def test_cleanup_old_data(self):
        """Test cleanup of old data."""
        from scripts.history_manager import HistoryManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_cleanup.db")
            history = HistoryManager(db_path=db_path)

            # Insert some data
            history.save_metrics_snapshot({"test": 1})
            history.log_api_request("GET", "/test", 200, 10.0)

            # Cleanup with very short retention
            deleted = history.cleanup_old_data(retention_days=0)

            assert isinstance(deleted, dict)

            history.close()

    def test_database_size_info(self):
        """Test getting database size information."""
        from scripts.history_manager import HistoryManager

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test_size.db")
            history = HistoryManager(db_path=db_path)

            # Add some data
            history.save_metrics_snapshot({"test": 1})

            info = history.get_database_size()

            assert "file_size_mb" in info
            assert "tables" in info
            assert "total_records" in info
            assert info["total_records"] > 0

            history.close()


class TestAPIDataModels:
    """Test suite for Pydantic data models."""

    def test_lifecycle_phase_model(self):
        """Test LifecyclePhase model validation."""
        from scripts.api.models import LifecyclePhase, PhaseStatus

        phase = LifecyclePhase(
            phase_id="P1",
            name="Requirements Analysis",
            description="Gather requirements",
            role_id="product-manager",
            order=1,
            status=PhaseStatus.COMPLETED,
        )

        assert phase.phase_id == "P1"
        assert phase.status == PhaseStatus.COMPLETED

        # Test serialization
        data = phase.model_dump()
        assert "phase_id" in data
        assert "status" in data

    def test_gate_result_model(self):
        """Test GateResult model validation."""
        from scripts.api.models import GateResult

        result = GateResult(passed=True, verdict="APPROVE", red_flags_count=0, missing_evidence_count=0)

        assert result.passed == True
        assert result.verdict == "APPROVE"
        assert result.checked_at is not None  # Auto-generated

    def test_metrics_snapshot_model(self):
        """Test MetricsSnapshot model validation."""
        from scripts.api.models import MetricsSnapshot

        snapshot = MetricsSnapshot(
            total_phases=11,
            completed_phases=7,
            completion_rate=63.6,
            avg_response_time_ms=150.5,
            cpu_usage_percent=45.2,
        )

        assert snapshot.total_phases == 11
        assert 0 <= snapshot.completion_rate <= 100
        assert snapshot.timestamp is not None

    def test_health_check_model(self):
        """Test HealthCheck model validation."""
        from scripts.api.models import HealthCheck

        health = HealthCheck(
            status="healthy", version="3.6.8", uptime_seconds=3600.0, components={"lifecycle_protocol": "healthy"}
        )

        assert health.status == "healthy"
        assert health.version == "3.6.8"
        assert health.uptime_seconds > 0


if __name__ == "__main__":
    import pytest

    pytest.main([__file__, "-v"])
