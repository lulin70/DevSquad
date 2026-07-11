"""Tests for scripts.collaboration.dispatch_performance.

Covers DispatchPerformanceMonitor: record, threshold checking, statistics,
regression detection, export, and clear.
"""

from __future__ import annotations

import json
import os

import pytest

from scripts.collaboration.dispatch_models import PerformanceMetric, PerformanceThresholds
from scripts.collaboration.dispatch_performance import DispatchPerformanceMonitor


def _make_metric(
    duration: float = 10.0,
    success: bool = True,
    errors: int = 0,
    roles: int = 3,
    step_timings: dict[str, float] | None = None,
    task: str = "Test task",
) -> PerformanceMetric:
    return PerformanceMetric(
        timestamp="2026-01-01T12:00:00",
        task_description=task,
        total_duration=duration,
        step_timings=step_timings or {"execute": 8.0, "collect": 1.0},
        success=success,
        error_count=errors,
        role_count=roles,
    )


# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------


class TestInit:
    def test_defaults(self):
        mon = DispatchPerformanceMonitor()
        assert mon.window_size == 100
        assert mon.thresholds is not None
        assert len(mon._metrics) == 0

    def test_custom_window_size(self):
        mon = DispatchPerformanceMonitor(window_size=50)
        assert mon.window_size == 50

    def test_custom_thresholds(self):
        th = PerformanceThresholds(total_duration_warning=15.0)
        mon = DispatchPerformanceMonitor(thresholds=th)
        assert mon.thresholds is th

    def test_window_size_enforced(self):
        mon = DispatchPerformanceMonitor(window_size=3)
        for i in range(5):
            mon.record(_make_metric(task=f"Task {i}"))
        assert len(mon._metrics) == 3


# ---------------------------------------------------------------------------
# record
# ---------------------------------------------------------------------------


class TestRecord:
    def test_record_single_metric(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric())
        assert len(mon._metrics) == 1

    def test_record_multiple_metrics(self):
        mon = DispatchPerformanceMonitor()
        for i in range(5):
            mon.record(_make_metric(task=f"Task {i}"))
        assert len(mon._metrics) == 5

    def test_record_triggers_threshold_check_no_alerts(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(duration=10.0))
        assert len(mon._metrics) == 1

    def test_record_triggers_warning(self, caplog):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(duration=35.0))
        assert any("PERFORMANCE WARNING" in r.message for r in caplog.records)

    def test_record_triggers_critical(self, caplog):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(duration=65.0))
        assert any("PERFORMANCE CRITICAL" in r.message for r in caplog.records)

    def test_record_step_warning(self, caplog):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(step_timings={"execute": 25.0}))
        assert any("PERFORMANCE WARNING" in r.message for r in caplog.records)

    def test_record_step_critical(self, caplog):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(step_timings={"execute": 55.0}))
        assert any("PERFORMANCE CRITICAL" in r.message for r in caplog.records)


# ---------------------------------------------------------------------------
# _check_thresholds
# ---------------------------------------------------------------------------


class TestCheckThresholds:
    def test_no_violations(self):
        mon = DispatchPerformanceMonitor()
        warnings, criticals = mon._check_thresholds(_make_metric(duration=10.0))
        assert warnings == []
        assert criticals == []

    def test_total_duration_warning(self):
        mon = DispatchPerformanceMonitor()
        warnings, criticals = mon._check_thresholds(_make_metric(duration=35.0))
        assert len(warnings) >= 1
        assert any(w["type"] == "total_duration" for w in warnings)
        assert criticals == []

    def test_total_duration_critical(self):
        mon = DispatchPerformanceMonitor()
        warnings, criticals = mon._check_thresholds(_make_metric(duration=65.0))
        assert len(criticals) >= 1
        assert any(c["type"] == "total_duration" for c in criticals)

    def test_step_warning(self):
        mon = DispatchPerformanceMonitor()
        warnings, criticals = mon._check_thresholds(
            _make_metric(step_timings={"analyze": 2.5})
        )
        assert len(warnings) >= 1
        assert any("step_analyze" in w["type"] for w in warnings)

    def test_step_critical(self):
        mon = DispatchPerformanceMonitor()
        warnings, criticals = mon._check_thresholds(
            _make_metric(step_timings={"analyze": 10.0})
        )
        assert len(criticals) >= 1
        assert any("step_analyze" in c["type"] for c in criticals)

    def test_step_no_threshold_no_violation(self):
        mon = DispatchPerformanceMonitor()
        warnings, criticals = mon._check_thresholds(
            _make_metric(step_timings={"unknown_step": 100.0})
        )
        assert all("unknown_step" not in w["type"] for w in warnings)
        assert all("unknown_step" not in c["type"] for c in criticals)


# ---------------------------------------------------------------------------
# get_statistics
# ---------------------------------------------------------------------------


class TestGetStatistics:
    def test_empty_returns_count_zero(self):
        mon = DispatchPerformanceMonitor()
        stats = mon.get_statistics()
        assert stats == {"count": 0}

    def test_count(self):
        mon = DispatchPerformanceMonitor()
        for _ in range(3):
            mon.record(_make_metric())
        stats = mon.get_statistics()
        assert stats["count"] == 3

    def test_success_rate(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(success=True))
        mon.record(_make_metric(success=True))
        mon.record(_make_metric(success=False))
        stats = mon.get_statistics()
        assert stats["success_rate"] == pytest.approx(2 / 3)

    def test_duration_stats(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(duration=10.0))
        mon.record(_make_metric(duration=20.0))
        stats = mon.get_statistics()
        assert stats["duration"]["min"] == 10.0
        assert stats["duration"]["max"] == 20.0
        assert stats["duration"]["avg"] == 15.0

    def test_duration_p50(self):
        mon = DispatchPerformanceMonitor()
        for d in [10.0, 20.0, 30.0, 40.0, 50.0]:
            mon.record(_make_metric(duration=d))
        stats = mon.get_statistics()
        assert stats["duration"]["p50"] == 30.0

    def test_errors_per_dispatch_avg(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(errors=0))
        mon.record(_make_metric(errors=3))
        stats = mon.get_statistics()
        assert stats["errors_per_dispatch_avg"] == 1.5

    def test_roles_per_dispatch_avg(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(roles=2))
        mon.record(_make_metric(roles=4))
        stats = mon.get_statistics()
        assert stats["roles_per_dispatch_avg"] == 3.0

    def test_step_stats(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(step_timings={"execute": 10.0, "collect": 1.0}))
        mon.record(_make_metric(step_timings={"execute": 20.0, "collect": 2.0}))
        stats = mon.get_statistics()
        assert "execute" in stats["steps"]
        assert stats["steps"]["execute"]["avg"] == 15.0
        assert stats["steps"]["execute"]["max"] == 20.0

    def test_step_stats_missing_step(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(step_timings={"execute": 10.0}))
        mon.record(_make_metric(step_timings={"collect": 1.0}))
        stats = mon.get_statistics()
        assert "execute" in stats["steps"]
        assert "collect" in stats["steps"]


# ---------------------------------------------------------------------------
# detect_regression
# ---------------------------------------------------------------------------


class TestDetectRegression:
    def test_insufficient_data_returns_none(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric(duration=10.0))
        assert mon.detect_regression() is None

    def test_no_regression_returns_none(self):
        mon = DispatchPerformanceMonitor()
        for _ in range(20):
            mon.record(_make_metric(duration=10.0))
        assert mon.detect_regression() is None

    def test_regression_detected(self):
        mon = DispatchPerformanceMonitor()
        for _ in range(10):
            mon.record(_make_metric(duration=10.0))
        for _ in range(10):
            mon.record(_make_metric(duration=20.0))
        result = mon.detect_regression()
        assert result is not None
        assert result["detected"] is True
        assert result["regression_ratio"] > 0.2

    def test_regression_severity_high(self):
        mon = DispatchPerformanceMonitor()
        for _ in range(10):
            mon.record(_make_metric(duration=10.0))
        for _ in range(10):
            mon.record(_make_metric(duration=20.0))
        result = mon.detect_regression()
        assert result is not None
        assert result["severity"] in ("medium", "high")

    def test_regression_with_custom_baseline(self):
        mon = DispatchPerformanceMonitor()
        for _ in range(6):
            mon.record(_make_metric(duration=10.0))
        for _ in range(6):
            mon.record(_make_metric(duration=15.0))
        result = mon.detect_regression(baseline_count=5)
        assert result is not None
        assert result["detected"] is True


# ---------------------------------------------------------------------------
# export_metrics
# ---------------------------------------------------------------------------


class TestExportMetrics:
    def test_export_creates_file(self, tmp_path):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric())
        output = str(tmp_path / "metrics.json")
        mon.export_metrics(output, allowed_base_dir=str(tmp_path))
        assert os.path.exists(output)
        with open(output) as f:
            data = json.load(f)
        assert len(data) == 1
        assert data[0]["task_description"] == "Test task"

    def test_export_empty_metrics(self, tmp_path):
        mon = DispatchPerformanceMonitor()
        output = str(tmp_path / "empty.json")
        mon.export_metrics(output, allowed_base_dir=str(tmp_path))
        assert os.path.exists(output)
        with open(output) as f:
            data = json.load(f)
        assert data == []

    def test_export_multiple_metrics(self, tmp_path):
        mon = DispatchPerformanceMonitor()
        for i in range(3):
            mon.record(_make_metric(task=f"Task {i}"))
        output = str(tmp_path / "multi.json")
        mon.export_metrics(output, allowed_base_dir=str(tmp_path))
        with open(output) as f:
            data = json.load(f)
        assert len(data) == 3

    def test_export_path_outside_allowed_dir(self, tmp_path, monkeypatch):
        allowed_dir = tmp_path / "allowed"
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric())
        output = str(tmp_path / "metrics.json")
        monkeypatch.setattr("tempfile.gettempdir", lambda: "/nonexistent_temp_root")
        mon.export_metrics(output, allowed_base_dir=str(allowed_dir))
        redirected = allowed_dir / "metrics.json"
        assert redirected.exists()
        with open(redirected) as f:
            data = json.load(f)
        assert len(data) == 1


# ---------------------------------------------------------------------------
# clear
# ---------------------------------------------------------------------------


class TestClear:
    def test_clear_removes_all_metrics(self):
        mon = DispatchPerformanceMonitor()
        for _ in range(5):
            mon.record(_make_metric())
        assert len(mon._metrics) == 5
        mon.clear()
        assert len(mon._metrics) == 0

    def test_clear_empty_noop(self):
        mon = DispatchPerformanceMonitor()
        mon.clear()
        assert len(mon._metrics) == 0

    def test_clear_then_record(self):
        mon = DispatchPerformanceMonitor()
        mon.record(_make_metric())
        mon.clear()
        mon.record(_make_metric())
        assert len(mon._metrics) == 1
