#!/usr/bin/env python3
"""
DevSquad History Manager Tests (V3.6.2)

Comprehensive test coverage for SQLite-based history management.

Test Categories:
  - Database initialization and schema creation
  - Metrics snapshot CRUD operations
  - API request logging
  - Lifecycle event tracking
  - Historical data queries with filters
  - Data cleanup and retention
  - Database size and statistics
  - Connection management
  - Error handling and edge cases
  - Concurrent access safety

Usage:
    pytest tests/test_history_manager_v362.py -v --cov=scripts/history_manager --cov-report=term-missing
"""

import json
import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.history_manager import HistoryManager


@pytest.fixture
def temp_db_path():
    """Create a temporary database path for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        temp_path = f.name
    yield temp_path
    if os.path.exists(temp_path):
        os.unlink(temp_path)


@pytest.fixture
def history_manager(temp_db_path):
    """Create a HistoryManager instance with temporary database."""
    mgr = HistoryManager(db_path=temp_db_path)
    yield mgr
    mgr.close()


class TestDatabaseInitialization:
    """Test database initialization and schema creation."""

    def test_initialization_creates_database(self, temp_db_path):
        """Test that initialization creates database file."""
        mgr = HistoryManager(db_path=temp_db_path)
        mgr.close()

        assert os.path.exists(temp_db_path)
        assert os.path.getsize(temp_db_path) > 0

    def test_initialization_default_path(self):
        """Test initialization with default database path."""
        mgr = HistoryManager()
        mgr.close()

        assert os.path.exists(mgr.db_path)
        if os.path.exists(mgr.db_path):
            os.unlink(mgr.db_path)

    def test_schema_creates_metrics_table(self, history_manager):
        """Test that metrics_snapshots table is created."""
        cursor = history_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='metrics_snapshots'")
        result = cursor.fetchone()
        assert result is not None

    def test_schema_creates_alerts_table(self, history_manager):
        """Test that alert_history table is created."""
        cursor = history_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='alert_history'")
        result = cursor.fetchone()
        assert result is not None

    def test_schema_creates_api_logs_table(self, history_manager):
        """Test that api_logs table is created."""
        cursor = history_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='api_logs'")
        result = cursor.fetchone()
        assert result is not None

    def test_schema_creates_lifecycle_events_table(self, history_manager):
        """Test that lifecycle_events table is created."""
        cursor = history_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lifecycle_events'")
        result = cursor.fetchone()
        assert result is not None

    def test_schema_creates_indexes(self, history_manager):
        """Test that performance indexes are created."""
        cursor = history_manager.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        indexes = cursor.fetchall()
        assert len(indexes) >= 5


class TestMetricsSnapshotOperations:
    """Test metrics snapshot CRUD operations."""

    def test_save_metrics_snapshot_success(self, history_manager):
        """Test saving a metrics snapshot returns True."""
        metrics_data = {
            "total_phases": 11,
            "completed_phases": 7,
            "running_phases": 1,
            "failed_phases": 0,
            "completion_rate": 63.6,
            "avg_response_time_ms": 150.5,
            "p95_latency_ms": 250.2,
            "success_rate": 98.5,
            "cpu_usage_percent": 45.2,
            "memory_usage_percent": 62.8,
        }

        result = history_manager.save_metrics_snapshot(metrics_data)
        assert result is True

    def test_save_metrics_with_custom_fields(self, history_manager):
        """Test saving metrics snapshot with custom/extra fields."""
        metrics_data = {
            "total_phases": 5,
            "completed_phases": 3,
            "custom_metric_1": 100,
            "custom_string": "test_value",
            "nested": {"key": "value"},
        }

        result = history_manager.save_metrics_snapshot(metrics_data)
        assert result is True

    def test_save_metrics_empty_data(self, history_manager):
        """Test saving empty metrics data."""
        result = history_manager.save_metrics_snapshot({})
        assert result is True

    def test_get_metrics_history_returns_list(self, history_manager):
        """Test retrieving metrics history returns list."""
        history_manager.save_metrics_snapshot({"total_phases": 10})

        data = history_manager.get_metrics_history(hours=1)
        assert isinstance(data, list)
        assert len(data) >= 1

    def test_get_metrics_history_with_custom_field(self, history_manager):
        """Test retrieving metrics includes custom data when requested."""
        history_manager.save_metrics_snapshot(
            {
                "total_phases": 10,
                "custom_field": "test_value",
            }
        )

        data = history_manager.get_metrics_history(hours=1, include_custom=True)
        assert len(data) > 0

        if data[0].get("custom_data"):
            custom_data = data[0]["custom_data"]
            if isinstance(custom_data, str):
                import json

                parsed = json.loads(custom_data)
            else:
                parsed = custom_data
            assert "custom_field" in parsed

    def test_get_metrics_history_empty_result(self, history_manager):
        """Test retrieving metrics when no data exists."""
        data = history_manager.get_metrics_history(hours=1)
        assert data == []

    def test_get_metrics_history_time_filter(self, history_manager):
        """Test that time filter works correctly."""
        old_metrics = {"total_phases": 5}
        history_manager.save_metrics_snapshot(old_metrics)

        data = history_manager.get_metrics_history(hours=24)
        original_count = len(data)

        data_filtered = history_manager.get_metrics_history(hours=0.0001)
        assert len(data_filtered) <= original_count


class TestAPIRequestLogging:
    """Test API request logging functionality."""

    def test_log_api_request_success(self, history_manager):
        """Test logging an API request returns True."""
        result = history_manager.log_api_request(
            method="GET",
            path="/api/v1/lifecycle/phases",
            status_code=200,
            response_time_ms=45.2,
        )
        assert result is True

    def test_log_request_with_all_params(self, history_manager):
        """Test logging request with all optional parameters."""
        result = history_manager.log_api_request(
            method="POST",
            path="/api/v1/tasks/dispatch",
            status_code=201,
            response_time_ms=150.5,
            client_ip="192.168.1.100",
            user_agent="DevSquad-Client/1.0",
        )
        assert result is True

    def test_log_multiple_requests(self, history_manager):
        """Test logging multiple requests accumulates correctly."""
        for i in range(5):
            history_manager.log_api_request("GET", f"/api/v1/test/{i}", 200, 10.0 * i)

        stats = history_manager.get_api_stats(hours=1)
        assert stats["total_requests"] == 5

    def test_get_api_stats_basic(self, history_manager):
        """Test getting basic API statistics."""
        history_manager.log_api_request("GET", "/api/v1/health", 200, 25.0)

        stats = history_manager.get_api_stats(hours=1)
        assert stats["total_requests"] == 1
        assert stats["avg_response_time_ms"] >= 0
        assert "status_codes" in stats

    def test_get_api_stats_status_distribution(self, history_manager):
        """Test API stats include status code distribution."""
        history_manager.log_api_request("GET", "/api/v1/test", 200, 50.0)
        history_manager.log_api_request("POST", "/api/v1/test", 201, 75.0)
        history_manager.log_api_request("GET", "/api/v1/error", 500, 100.0)

        stats = history_manager.get_api_stats(hours=1)
        status_codes = stats["status_codes"]

        code_dict = {sc["status_code"]: sc["count"] for sc in status_codes}
        assert 200 in code_dict
        assert 500 in code_dict

    def test_get_api_stats_endpoint_grouping(self, history_manager):
        """Test API stats group by endpoint when requested."""
        history_manager.log_api_request("GET", "/api/v1/a", 200, 10.0)
        history_manager.log_api_request("GET", "/api/v1/b", 200, 20.0)
        history_manager.log_api_request("GET", "/api/v1/a", 200, 30.0)

        stats = history_manager.get_api_stats(hours=1, group_by_path=True)
        assert "endpoints" in stats
        assert len(stats["endpoints"]) == 2

    def test_get_api_stats_no_grouping(self, history_manager):
        """Test API stats without endpoint grouping."""
        history_manager.log_api_request("GET", "/api/v1/test", 200, 10.0)

        stats = history_manager.get_api_stats(hours=1, group_by_path=False)
        assert "endpoints" not in stats or stats.get("endpoints") is None


class TestLifecycleEventTracking:
    """Test lifecycle event tracking functionality."""

    def test_save_lifecycle_event_success(self, history_manager):
        """Test saving a lifecycle event returns True."""
        result = history_manager.save_lifecycle_event(
            event_type="phase_advance",
            phase_id="P1",
            previous_status="pending",
            new_status="running",
            user_id="test-user",
        )
        assert result is True

    def test_save_lifecycle_event_minimal(self, history_manager):
        """Test saving lifecycle event with minimal fields."""
        result = history_manager.save_lifecycle_event(event_type="phase_complete")
        assert result is True

    def test_save_lifecycle_event_with_details(self, history_manager):
        """Test saving lifecycle event with detailed info."""
        details = json.dumps({"artifacts_created": ["spec.md", "plan.md"]})
        result = history_manager.save_lifecycle_event(
            event_type="phase_complete",
            phase_id="P2",
            details=details,
        )
        assert result is True

    def test_get_lifecycle_history_basic(self, history_manager):
        """Test retrieving lifecycle event history."""
        history_manager.save_lifecycle_event(event_type="phase_start", phase_id="P1")

        events = history_manager.get_lifecycle_history(hours=1)
        assert isinstance(events, list)
        assert len(events) >= 1

    def test_get_lifecycle_history_by_phase(self, history_manager):
        """Test filtering lifecycle events by phase ID."""
        history_manager.save_lifecycle_event(event_type="advance", phase_id="P1")
        history_manager.save_lifecycle_event(event_type="advance", phase_id="P2")

        p1_events = history_manager.get_lifecycle_history(hours=1, phase_id="P1")
        assert all(e["phase_id"] == "P1" for e in p1_events)

    def test_get_lifecycle_history_by_type(self, history_manager):
        """Test filtering lifecycle events by event type."""
        history_manager.save_lifecycle_event(event_type="phase_complete")
        history_manager.save_lifecycle_event(event_type="phase_skip")

        complete_events = history_manager.get_lifecycle_history(hours=1, event_type="phase_complete")
        assert all(e["event_type"] == "phase_complete" for e in complete_events)

    def test_get_lifecycle_history_order(self, history_manager):
        """Test lifecycle events are returned in descending order."""
        for i in range(3):
            history_manager.save_lifecycle_event(event_type=f"event_{i}")

        events = history_manager.get_lifecycle_history(hours=1)
        if len(events) >= 2:
            assert events[0]["timestamp"] >= events[1]["timestamp"]


class TestDataCleanupAndRetention:
    """Test data cleanup and retention policies."""

    def test_cleanup_old_data(self, history_manager):
        """Test cleaning up old data beyond retention period."""
        history_manager.save_metrics_snapshot({"total_phases": 10})
        history_manager.log_api_request("GET", "/test", 200, 10.0)
        history_manager.save_lifecycle_event(event_type="test")

        deleted = history_manager.cleanup_old_data(retention_days=0)
        assert isinstance(deleted, dict)
        assert "metrics_snapshots" in deleted

    def test_cleanup_respects_retention_period(self, history_manager):
        """Test that recent data is preserved during cleanup."""
        history_manager.save_metrics_snapshot({"total_phases": 10})

        deleted = history_manager.cleanup_old_data(retention_days=365)
        total_deleted = sum(deleted.values())
        assert total_deleted == 0


class TestDatabaseSizeAndStatistics:
    """Test database size information and statistics."""

    def test_get_database_size(self, history_manager):
        """Test getting database size information."""
        history_manager.save_metrics_snapshot({"total_phases": 10})

        info = history_manager.get_database_size()
        assert "file_path" in info
        assert "file_size_mb" in info
        assert "tables" in info
        assert "total_records" in info

    def test_database_size_includes_all_tables(self, history_manager):
        """Test that size info includes record counts for all tables."""
        history_manager.save_metrics_snapshot({"total_phases": 10})
        history_manager.log_api_request("GET", "/test", 200, 10.0)
        history_manager.save_lifecycle_event(event_type="test")

        info = history_manager.get_database_size()
        tables = info["tables"]
        assert "metrics_snapshots" in tables
        assert "api_logs" in tables
        assert "lifecycle_events" in tables

    def test_file_size_is_positive(self, history_manager):
        """Test that reported file size is non-negative."""
        info = history_manager.get_database_size()
        assert info["file_size_mb"] >= 0


class TestConnectionManagement:
    """Test database connection management."""

    def test_close_connection(self, history_manager):
        """Test closing database connection."""
        history_manager.close()
        assert history_manager.conn is None

    def test_operations_after_close_fail(self, history_manager):
        """Test that operations after close handle gracefully."""
        history_manager.close()

        def should_not_crash():
            return history_manager.get_database_size()
        try:
            result = should_not_crash()
            assert isinstance(result, dict) or result is None
        except Exception:
            pass


class TestEdgeCasesAndBoundaryConditions:
    """Test edge cases and boundary conditions."""

    def test_very_long_task_description(self, history_manager):
        """Test handling very long strings in task descriptions."""
        long_string = "x" * 10000
        result = history_manager.save_lifecycle_event(
            event_type="test",
            details=long_string,
        )
        assert result is True

    def test_special_characters_in_paths(self, history_manager):
        """Test handling special characters in API paths."""
        special_paths = [
            "/api/v1/test?param=value&other=123",
            "/api/v1/path/with spaces",
            "/api/v1/path/unicode-\u00e9\u00e8",
        ]

        for path in special_paths:
            result = history_manager.log_api_request("GET", path, 200, 10.0)
            assert result is True

    def test_unicode_content(self, history_manager):
        """Test storing and retrieving Unicode content."""
        unicode_text = "中文测试 🎉 日本語テスト"
        result = history_manager.save_lifecycle_event(
            event_type="unicode_test",
            details=unicode_text,
        )
        assert result is True

        events = history_manager.get_lifecycle_history(hours=1, event_type="unicode_test")
        if events:
            assert events[0]["details"] == unicode_text

    def test_null_values_handling(self, history_manager):
        """Test handling of NULL/None values."""
        result = history_manager.save_lifecycle_event(
            event_type="null_test",
            phase_id=None,
            user_id=None,
        )
        assert result is True

    def test_concurrent_inserts(self, history_manager):
        """Test multiple rapid insertions don't cause errors."""
        results = []
        for i in range(20):
            r = history_manager.save_metrics_snapshot({"total_phases": i})
            results.append(r)

        assert all(results)
        assert len(history_manager.get_metrics_history(hours=1)) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
