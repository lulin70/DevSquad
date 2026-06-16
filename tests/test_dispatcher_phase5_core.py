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

from scripts.collaboration.dispatch_models import PerformanceThresholds
from scripts.collaboration.dispatcher import (
    MultiAgentDispatcher,
    DispatchResult,
)
from scripts.collaboration.performance_monitor import (
    PerformanceMonitor,
    PerformanceMetric,
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
        monitor = PerformanceMonitor(max_history=10)
        metric = PerformanceMetric(
            name="test_task",
            start_time=0.0,
            end_time=1.5,
            duration=1.5,
            cpu_percent=10.0,
            memory_mb=100.0,
            success=True,
        )
        monitor.record_metric(metric)
        stats = monitor.get_stats()
        assert stats["total_metrics"] == 1

    def test_record_metric_warning_threshold(self):
        """Test recording a slow metric."""
        monitor = PerformanceMonitor(max_history=10)
        metric = PerformanceMetric(
            name="slow_task",
            start_time=0.0,
            end_time=2.0,
            duration=2.0,
            cpu_percent=50.0,
            memory_mb=200.0,
            success=True,
        )
        monitor.record_metric(metric)
        stats = monitor.get_stats()
        assert stats["total_metrics"] == 1

    def test_record_metric_critical_threshold(self):
        """Test recording a failed metric."""
        monitor = PerformanceMonitor(max_history=10)
        metric = PerformanceMetric(
            name="critical_task",
            start_time=0.0,
            end_time=10.0,
            duration=10.0,
            cpu_percent=90.0,
            memory_mb=500.0,
            success=False,
            error="timeout",
        )
        monitor.record_metric(metric)
        stats = monitor.get_stats()
        assert stats["total_metrics"] == 1

    def test_get_stats_empty(self):
        """Test statistics with no metrics recorded."""
        monitor = PerformanceMonitor(max_history=10)
        stats = monitor.get_stats()
        assert stats["total_metrics"] == 0

    def test_get_stats_multiple_metrics(self):
        """Test statistics aggregation with multiple metrics."""
        monitor = PerformanceMonitor(max_history=10)
        for i in range(5):
            metric = PerformanceMetric(
                name=f"task_{i}",
                start_time=float(i),
                end_time=float(i + 1),
                duration=1.0,
                cpu_percent=10.0,
                memory_mb=100.0,
                success=i % 2 == 0,
            )
            monitor.record_metric(metric)

        stats = monitor.get_stats()
        assert stats["total_metrics"] == 5

    def test_max_history_limits_stored_metrics(self):
        """Test that max_history limits stored metrics."""
        monitor = PerformanceMonitor(max_history=3)
        for i in range(5):
            metric = PerformanceMetric(
                name=f"task_{i}",
                start_time=float(i),
                end_time=float(i + 1),
                duration=1.0,
                cpu_percent=10.0,
                memory_mb=100.0,
                success=True,
            )
            monitor.record_metric(metric)

        assert len(monitor.all_metrics) == 3

    def test_function_stats_tracking(self):
        """Test per-function statistics tracking."""
        monitor = PerformanceMonitor(max_history=10)
        for _ in range(3):
            metric = PerformanceMetric(
                name="my_func",
                start_time=0.0,
                end_time=1.0,
                duration=1.0,
                cpu_percent=10.0,
                memory_mb=100.0,
                success=True,
            )
            monitor.record_metric(metric)

        func_stats = monitor.get_stats(function_name="my_func")
        assert func_stats["call_count"] == 3
        assert func_stats["success_rate"] == "100.0%"


class TestPerformanceMetricDataclass:
    """PerformanceMetric 数据类测试"""

    def test_metric_creation(self):
        """Test basic metric creation with actual fields."""
        metric = PerformanceMetric(
            name="test_task",
            start_time=0.0,
            end_time=1.0,
            duration=1.0,
            cpu_percent=10.0,
            memory_mb=100.0,
            success=True,
        )
        assert metric.name == "test_task"
        assert metric.duration == 1.0
        assert metric.success is True
        assert metric.error is None

    def test_metric_with_error(self):
        """Test metric creation with error."""
        metric = PerformanceMetric(
            name="failed_task",
            start_time=0.0,
            end_time=1.0,
            duration=1.0,
            cpu_percent=10.0,
            memory_mb=100.0,
            success=False,
            error="timeout",
        )
        assert metric.success is False
        assert metric.error == "timeout"

    def test_metric_to_dict(self):
        """Test metric serialization."""
        metric = PerformanceMetric(
            name="test_task",
            start_time=0.0,
            end_time=1.0,
            duration=1.0,
            cpu_percent=10.0,
            memory_mb=100.0,
            success=True,
        )
        d = metric.to_dict()
        assert "name" in d
        assert "duration_ms" in d
        assert "success" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
