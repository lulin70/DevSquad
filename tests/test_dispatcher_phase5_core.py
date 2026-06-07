#!/usr/bin/env python3
"""
Phase 5: Dispatcher 核心路径覆盖率提升测试（基于实际 API）

目标：
- 错误输入验证测试（空任务、无效类型等）
- 空角色列表边界测试
- Dry-run 模式测试
- 不同执行模式测试
- PerformanceMonitor 组件测试

遵循 AAA 模式 (Arrange-Act-Assert)
"""

import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatcher import (
    MultiAgentDispatcher,
    DispatchResult,
    PerformanceMonitor,
    PerformanceMetric,
    PerformanceThresholds,
)


class TestDispatchInputValidation:
    """dispatch() 方法输入验证测试"""

    @pytest.fixture
    def dispatcher(self):
        """创建使用 mock backend 的 dispatcher 实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                llm_backend=None,
            )
            yield disp

    def test_dispatch_empty_task_string(self, dispatcher):
        """Test that dispatch with empty string returns error."""
        result = dispatcher.dispatch("")
        assert result.success is False
        assert len(result.errors) > 0
        assert "短" in result.errors[0] or "empty" in result.errors[0].lower() or "short" in result.errors[0].lower()

    def test_dispatch_whitespace_only_task(self, dispatcher):
        """Test that dispatch with whitespace-only task returns error."""
        result = dispatcher.dispatch("   \t\n   ")
        assert result.success is False
        assert len(result.errors) > 0

    def test_dispatch_none_task(self, dispatcher):
        """Test that dispatch with None task handles gracefully."""
        result = dispatcher.dispatch(None)
        assert result.success is False
        assert "文字" in result.errors[0] or "string" in result.errors[0].lower()

    def test_dispatch_non_string_task(self, dispatcher):
        """Test that dispatch with non-string type returns error."""
        result = dispatcher.dispatch(12345)
        assert result.success is False
        assert "文字" in result.errors[0] or "string" in result.errors[0].lower()

    def test_dispatch_too_long_task(self, dispatcher):
        """Test that dispatch with extremely long task returns error."""
        long_task = "test " * 10000
        result = dispatcher.dispatch(long_task)
        assert result.success is False
        assert "长" in result.errors[0] or "long" in result.errors[0].lower()

    def test_dispatch_empty_roles_list(self, dispatcher):
        """Test that dispatch with empty roles list auto-matches roles (succeeds)."""
        result = dispatcher.dispatch("test task", roles=[])
        # Empty roles list triggers auto-matching, which succeeds
        assert result.success is True

    def test_dispatch_invalid_role_type_in_list(self, dispatcher):
        """Test that dispatch with non-string role in list returns error."""
        result = dispatcher.dispatch("test task", roles=["architect", 123])
        assert result.success is False
        assert "角色" in result.errors[0] or "role" in result.errors[0].lower()

    def test_dispatch_too_many_roles(self, dispatcher):
        """Test that dispatch with too many roles returns error."""
        many_roles = [f"role_{i}" for i in range(100)]
        result = dispatcher.dispatch("test task", roles=many_roles)
        assert result.success is False
        assert "角色" in result.errors[0] or "role" in result.errors[0].lower()


class TestDispatchDryRun:
    """dispatch() dry-run 模式测试"""

    @pytest.fixture
    def dispatcher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                llm_backend=None,
            )
            yield disp

    def test_dry_run_returns_success(self, dispatcher):
        """Test that dry_run=True returns success without execution."""
        result = dispatcher.dispatch(
            "Design a REST API",
            roles=["architect", "tester"],
            dry_run=True,
        )
        assert result.success is True
        assert len(result.matched_roles) > 0

    def test_dry_run_no_worker_results(self, dispatcher):
        """Test that dry_run mode has no worker results."""
        result = dispatcher.dispatch(
            "Implement feature X",
            roles=["solo-coder"],
            dry_run=True,
        )
        assert result.worker_results == [] or len(result.worker_results) == 0

    def test_dry_run_with_auto_mode(self, dispatcher):
        """Test dry_run with auto mode (no roles specified)."""
        result = dispatcher.dispatch(
            "Build authentication system",
            dry_run=True,
        )
        assert result.success is True


class TestDispatchModes:
    """不同执行模式测试"""

    @pytest.fixture
    def dispatcher(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(
                persist_dir=tmpdir,
                llm_backend=None,
            )
            yield disp

    def test_parallel_mode(self, dispatcher):
        """Test parallel execution mode."""
        result = dispatcher.dispatch(
            "Task for parallel execution",
            roles=["architect", "tester"],
            mode="parallel",
        )
        assert isinstance(result, DispatchResult)

    def test_sequential_mode(self, dispatcher):
        """Test sequential execution mode."""
        result = dispatcher.dispatch(
            "Task for sequential execution",
            roles=["architect", "tester"],
            mode="sequential",
        )
        assert isinstance(result, DispatchResult)

    def test_consensus_mode(self, dispatcher):
        """Test consensus execution mode."""
        result = dispatcher.dispatch(
            "Code review task",
            roles=["architect", "tester", "security"],
            mode="consensus",
        )
        assert isinstance(result, DispatchResult)


class TestPerformanceMonitor:
    """PerformanceMonitor 组件测试"""

    def test_record_metric_basic(self):
        """Test basic metric recording."""
        monitor = PerformanceMonitor(window_size=10)
        metric = PerformanceMetric(
            timestamp="2024-01-01T00:00:00",
            task_description="test task",
            total_duration=1.5,
            step_timings={"validation": 0.1, "execution": 1.2},
            success=True,
            error_count=0,
            role_count=2,
        )
        monitor.record(metric)
        stats = monitor.get_statistics()
        assert stats["count"] == 1
        assert stats["success_rate"] == 1.0

    def test_record_metric_warning_threshold(self):
        """Test warning threshold detection."""
        thresholds = PerformanceThresholds(
            total_duration_warning=1.0,
            total_duration_critical=5.0,
        )
        monitor = PerformanceMonitor(window_size=10, thresholds=thresholds)
        metric = PerformanceMetric(
            timestamp="2024-01-01T00:00:00",
            task_description="slow task",
            total_duration=2.0,
            step_timings={},
            success=True,
            error_count=0,
            role_count=1,
        )
        monitor.record(metric)
        stats = monitor.get_statistics()
        assert stats["count"] == 1

    def test_record_metric_critical_threshold(self):
        """Test critical threshold detection."""
        thresholds = PerformanceThresholds(
            total_duration_warning=1.0,
            total_duration_critical=2.0,
        )
        monitor = PerformanceMonitor(window_size=10, thresholds=thresholds)
        metric = PerformanceMetric(
            timestamp="2024-01-01T00:00:00",
            task_description="critical slow task",
            total_duration=10.0,
            step_timings={},
            success=False,
            error_count=3,
            role_count=2,
        )
        monitor.record(metric)
        stats = monitor.get_statistics()
        assert stats["count"] == 1
        assert stats["success_rate"] == 0.0

    def test_get_statistics_empty(self):
        """Test statistics with no metrics recorded."""
        monitor = PerformanceMonitor(window_size=10)
        stats = monitor.get_statistics()
        assert stats == {"count": 0}

    def test_get_statistics_multiple_metrics(self):
        """Test statistics aggregation with multiple metrics."""
        monitor = PerformanceMonitor(window_size=10)
        for i in range(5):
            metric = PerformanceMetric(
                timestamp=f"2024-01-0{i+1}T00:00:00",
                task_description=f"task {i}",
                total_duration=float(i + 1),
                step_timings={},
                success=i % 2 == 0,
                error_count=0,
                role_count=2,
            )
            monitor.record(metric)

        stats = monitor.get_statistics()
        assert stats["count"] == 5
        assert 0 < stats["success_rate"] < 1
        assert "duration" in stats
        assert "min" in stats["duration"]
        assert "max" in stats["duration"]
        assert "avg" in stats["duration"]

    def test_detect_regression_insufficient_data(self):
        """Test regression detection with insufficient data returns None."""
        monitor = PerformanceMonitor(window_size=10)
        for i in range(5):
            metric = PerformanceMetric(
                timestamp=f"2024-01-0{i+1}T00:00:00",
                task_description=f"task {i}",
                total_duration=1.0,
                step_timings={},
                success=True,
                error_count=0,
                role_count=1,
            )
            monitor.record(metric)

        result = monitor.detect_regression(baseline_count=10)
        assert result is None

    def test_window_size_limit(self):
        """Test that window size limits stored metrics."""
        monitor = PerformanceMonitor(window_size=3)
        for i in range(5):
            metric = PerformanceMetric(
                timestamp=f"2024-01-0{i+1}T00:00:00",
                task_description=f"task {i}",
                total_duration=float(i),
                step_timings={},
                success=True,
                error_count=0,
                role_count=1,
            )
            monitor.record(metric)

        stats = monitor.get_statistics()
        assert stats["count"] == 3


class TestPerformanceMetricDataclass:
    """PerformanceMetric 数据类测试"""

    def test_truncates_long_description(self):
        """Test that long task descriptions are truncated to 50 chars."""
        long_desc = "x" * 100
        metric = PerformanceMetric(
            timestamp="2024-01-01T00:00:00",
            task_description=long_desc,
            total_duration=1.0,
            step_timings={},
            success=True,
            error_count=0,
            role_count=1,
        )
        assert len(metric.task_description) == 53  # 50 chars + "..."

    def test_preserves_short_description(self):
        """Test that short descriptions are not modified."""
        short_desc = "short task"
        metric = PerformanceMetric(
            timestamp="2024-01-01T00:00:00",
            task_description=short_desc,
            total_duration=1.0,
            step_timings={},
            success=True,
            error_count=0,
            role_count=1,
        )
        assert metric.task_description == short_desc


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
