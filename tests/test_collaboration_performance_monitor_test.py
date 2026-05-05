#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for Performance Monitor

Tests cover:
- Performance metric recording
- Statistics calculation (avg, min, max, P95, P99)
- Decorator functionality
- Bottleneck detection
- Report generation
- Global monitor singleton
"""

import pytest
import time
from scripts.collaboration.performance_monitor import (
    PerformanceMetric,
    PerformanceMonitor,
    FunctionStats,
    get_monitor,
    monitor_performance,
    reset_monitor
)


class TestPerformanceMetric:
    """Test performance metric data class"""

    def test_metric_creation(self):
        """Test creating a performance metric"""
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1005,
            cpu_percent=25.0,
            memory_mb=50.0,
            success=True
        )

        assert metric.name == "test_func"
        assert metric.duration == 0.1005
        assert metric.cpu_percent == 25.0
        assert metric.memory_mb == 50.0
        assert metric.success is True

    def test_metric_to_dict(self):
        """Test metric conversion to dictionary"""
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )

        metric_dict = metric.to_dict()

        assert "name" in metric_dict
        assert "duration_ms" in metric_dict
        assert metric_dict["duration_ms"] == 100.0  # Converted to ms
        assert metric_dict["success"] is True


class TestFunctionStats:
    """Test function statistics data class"""

    def test_stats_creation(self):
        """Test creating function stats"""
        stats = FunctionStats(name="test_func")

        assert stats.name == "test_func"
        assert stats.call_count == 0
        assert stats.avg_duration == 0.0

    def test_add_metric(self):
        """Test adding metrics to stats"""
        stats = FunctionStats(name="test_func")

        metric1 = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        stats.add_metric(metric1)

        assert stats.call_count == 1
        assert stats.success_count == 1
        assert stats.avg_duration == 0.1

    def test_add_multiple_metrics(self):
        """Test statistics with multiple metrics"""
        stats = FunctionStats(name="test_func")

        for i in range(5):
            metric = PerformanceMetric(
                name="test_func",
                start_time=time.time() - 0.1,
                end_time=time.time(),
                duration=0.1 + i * 0.01,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            stats.add_metric(metric)

        assert stats.call_count == 5
        assert 0.1 <= stats.avg_duration <= 0.15


class TestPerformanceMonitor:
    """Test performance monitor"""

    def setup_method(self):
        """Setup test fixtures"""
        self.monitor = PerformanceMonitor(max_history=100)

    def test_initialization(self):
        """Test monitor initialization"""
        assert len(self.monitor.function_stats) == 0
        assert len(self.monitor.all_metrics) == 0

    def test_record_metric(self):
        """Test recording a single metric"""
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )

        self.monitor.record_metric(metric)

        assert "test_func" in self.monitor.function_stats
        assert self.monitor.function_stats["test_func"].call_count == 1
        assert len(self.monitor.all_metrics) == 1

    def test_record_multiple_metrics(self):
        """Test recording multiple metrics for same function"""
        for i in range(5):
            metric = PerformanceMetric(
                name="test_func",
                start_time=time.time() - 0.1,
                end_time=time.time(),
                duration=0.1 + i * 0.01,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            self.monitor.record_metric(metric)

        assert self.monitor.function_stats["test_func"].call_count == 5
        assert len(self.monitor.all_metrics) == 5

    def test_max_history_limit(self):
        """Test max history limit enforcement"""
        monitor = PerformanceMonitor(max_history=10)

        for i in range(15):
            metric = PerformanceMetric(
                name="test_func",
                start_time=time.time() - 0.1,
                end_time=time.time(),
                duration=float(i) * 0.01,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            monitor.record_metric(metric)

        # Should keep only last 10 in all_metrics
        assert len(monitor.all_metrics) <= 10
        # But function_stats should still have all calls tracked
        assert monitor.function_stats["test_func"].call_count == 15

    def test_get_stats_nonexistent(self):
        """Test getting stats for non-existent function"""
        stats = self.monitor.get_stats("nonexistent")
        assert stats == {}

    def test_get_stats_single_metric(self):
        """Test statistics with single metric"""
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        self.monitor.record_metric(metric)

        stats = self.monitor.get_stats("test_func")
        assert stats["call_count"] == 1
        assert stats["avg_duration_ms"] == 100.0
        assert stats["min_duration_ms"] == 100.0
        assert stats["max_duration_ms"] == 100.0
        assert stats["p95_duration_ms"] == 100.0
        assert stats["p99_duration_ms"] == 100.0

    def test_get_stats_multiple_metrics(self):
        """Test statistics with multiple metrics"""
        durations = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.10]

        for d in durations:
            metric = PerformanceMetric(
                name="test_func",
                start_time=time.time() - d,
                end_time=time.time(),
                duration=d,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            self.monitor.record_metric(metric)

        stats = self.monitor.get_stats("test_func")
        assert stats["call_count"] == 10
        assert stats["min_duration_ms"] == 10.0
        assert stats["max_duration_ms"] == 100.0

    def test_get_all_stats(self):
        """Test getting stats for all functions"""
        metric1 = PerformanceMetric(
            name="func1",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        self.monitor.record_metric(metric1)

        metric2 = PerformanceMetric(
            name="func2",
            start_time=time.time() - 0.2,
            end_time=time.time(),
            duration=0.2,
            cpu_percent=40.0,
            memory_mb=60.0,
            success=True
        )
        self.monitor.record_metric(metric2)

        metric3 = PerformanceMetric(
            name="func1",
            start_time=time.time() - 0.15,
            end_time=time.time(),
            duration=0.15,
            cpu_percent=25.0,
            memory_mb=35.0,
            success=True
        )
        self.monitor.record_metric(metric3)

        all_stats = self.monitor.get_stats()

        assert "functions" in all_stats
        assert "func1" in all_stats["functions"]
        assert "func2" in all_stats["functions"]
        assert all_stats["functions"]["func1"]["call_count"] == 2
        assert all_stats["functions"]["func2"]["call_count"] == 1

    def test_detect_bottlenecks(self):
        """Test bottleneck detection"""
        for i in range(10):
            fast_metric = PerformanceMetric(
                name="fast_func",
                start_time=time.time() - 0.01,
                end_time=time.time(),
                duration=0.01,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            self.monitor.record_metric(fast_metric)

        for i in range(10):
            slow_metric = PerformanceMetric(
                name="slow_func",
                start_time=time.time() - 2.0,
                end_time=time.time(),
                duration=2.0,
                cpu_percent=40.0,
                memory_mb=60.0,
                success=True
            )
            self.monitor.record_metric(slow_metric)

        bottlenecks = self.monitor.get_bottlenecks(threshold_ms=1000.0)

        assert len(bottlenecks) == 1
        assert bottlenecks[0]["name"] == "slow_func"
        assert bottlenecks[0]["avg_duration_ms"] == 2000.0

    def test_detect_bottlenecks_empty(self):
        """Test bottleneck detection with no bottlenecks"""
        for i in range(10):
            metric = PerformanceMetric(
                name="fast_func",
                start_time=time.time() - 0.01,
                end_time=time.time(),
                duration=0.01,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            self.monitor.record_metric(metric)

        bottlenecks = self.monitor.get_bottlenecks(threshold_ms=1000.0)
        assert len(bottlenecks) == 0

    def test_export_report(self):
        """Test exporting markdown report"""
        metric1 = PerformanceMetric(
            name="func1",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        self.monitor.record_metric(metric1)

        metric2 = PerformanceMetric(
            name="func2",
            start_time=time.time() - 0.2,
            end_time=time.time(),
            duration=0.2,
            cpu_percent=40.0,
            memory_mb=60.0,
            success=True
        )
        self.monitor.record_metric(metric2)

        report = self.monitor.export_report()

        assert "# Performance Monitoring Report" in report
        assert "func1" in report
        assert "func2" in report

    def test_export_report_with_bottlenecks(self):
        """Test report includes bottleneck section"""
        for i in range(5):
            metric = PerformanceMetric(
                name="slow_func",
                start_time=time.time() - 2.0,
                end_time=time.time(),
                duration=2.0,
                cpu_percent=40.0,
                memory_mb=60.0,
                success=True
            )
            self.monitor.record_metric(metric)

        report = self.monitor.export_report()

        assert "Performance Bottlenecks" in report
        assert "slow_func" in report

    def test_get_slowest_functions(self):
        """Test getting slowest functions"""
        for i in range(5):
            fast_metric = PerformanceMetric(
                name="fast_func",
                start_time=time.time() - 0.01,
                end_time=time.time(),
                duration=0.01,
                cpu_percent=20.0,
                memory_mb=30.0,
                success=True
            )
            self.monitor.record_metric(fast_metric)

        for i in range(5):
            slow_metric = PerformanceMetric(
                name="slow_func",
                start_time=time.time() - 2.0,
                end_time=time.time(),
                duration=2.0,
                cpu_percent=40.0,
                memory_mb=60.0,
                success=True
            )
            self.monitor.record_metric(slow_metric)

        slowest = self.monitor.get_slowest_functions(limit=5)

        assert len(slowest) >= 2
        assert slowest[0]["name"] == "slow_func"
        assert slowest[0]["avg_duration_ms"] > slowest[1]["avg_duration_ms"]

    def test_record_llm_call(self):
        """Test recording LLM API call"""
        self.monitor.record_llm_call(
            backend="openai",
            model="gpt-4",
            duration=1.5,
            token_count=1000,
            success=True
        )

        stats = self.monitor.get_stats("llm_call:openai:gpt-4")
        assert stats["call_count"] == 1
        assert stats["avg_duration_ms"] == 1500.0

    def test_record_agent_execution(self):
        """Test recording agent execution"""
        self.monitor.record_agent_execution(
            agent_role="architect",
            task="design system",
            duration=2.0,
            success=True
        )

        stats = self.monitor.get_stats("agent:architect")
        assert stats["call_count"] == 1
        assert stats["avg_duration_ms"] == 2000.0

    def test_generate_report_to_file(self, tmp_path):
        """Test generating report to file"""
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        self.monitor.record_metric(metric)

        output_file = tmp_path / "report.md"
        self.monitor.generate_report(str(output_file))

        assert output_file.exists()
        content = output_file.read_text()
        assert "# Performance Monitoring Report" in content


class TestMonitorDecorator:
    """Test monitor_performance decorator"""

    def setup_method(self):
        """Setup test fixtures - reset global monitor"""
        reset_monitor()

    def test_decorator_basic(self):
        """Test basic decorator usage"""
        @monitor_performance("test_func")
        def test_func():
            time.sleep(0.01)
            return "result"

        result = test_func()

        assert result == "result"

        monitor = get_monitor()
        stats = monitor.get_stats("test_func")

        assert stats["call_count"] == 1
        assert stats["avg_duration_ms"] >= 10.0  # At least 10ms due to sleep

    def test_decorator_calls(self):
        """Test decorator with multiple calls"""
        @monitor_performance("test_func")
        def test_func(x):
            return x * 2

        for i in range(5):
            test_func(i)

        monitor = get_monitor()
        stats = monitor.get_stats("test_func")

        assert stats["call_count"] == 5

    def test_decorator_with_exception(self):
        """Test decorator handles exceptions"""
        @monitor_performance("test_func")
        def test_func():
            raise ValueError("Test error")

        with pytest.raises(ValueError):
            test_func()

        # Should still record the metric
        monitor = get_monitor()
        stats = monitor.get_stats("test_func")

        assert stats["call_count"] == 1
        assert stats["failure_count"] == 1

    def test_decorator_preserves_function_metadata(self):
        """Test decorator preserves function name and docstring"""
        @monitor_performance("test_func")
        def my_function():
            """This is my function"""
            pass

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "This is my function"

    def test_decorator_with_args_and_kwargs(self):
        """Test decorator works with function arguments"""
        @monitor_performance("test_func")
        def test_func(a, b, c=3):
            return a + b + c

        result = test_func(1, 2, c=4)

        assert result == 7

        monitor = get_monitor()
        stats = monitor.get_stats("test_func")
        assert stats["call_count"] == 1


class TestGlobalMonitor:
    """Test global monitor singleton"""

    def setup_method(self):
        """Reset global monitor before each test"""
        reset_monitor()

    def test_singleton(self):
        """Test global monitor is singleton"""
        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2

    def test_shared_state(self):
        """Test global monitor shares state"""
        monitor1 = get_monitor()
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        monitor1.record_metric(metric)

        monitor2 = get_monitor()
        stats = monitor2.get_stats("test_func")

        assert stats["call_count"] == 1

    def test_reset_monitor(self):
        """Test resetting global monitor"""
        monitor = get_monitor()
        metric = PerformanceMetric(
            name="test_func",
            start_time=time.time() - 0.1,
            end_time=time.time(),
            duration=0.1,
            cpu_percent=20.0,
            memory_mb=30.0,
            success=True
        )
        monitor.record_metric(metric)

        reset_monitor()

        new_monitor = get_monitor()
        assert len(new_monitor.function_stats) == 0
        assert len(new_monitor.all_metrics) == 0


class TestIntegration:
    """Integration tests"""

    def setup_method(self):
        """Reset global monitor before integration tests"""
        reset_monitor()

    def test_real_world_scenario(self):
        """Test realistic usage scenario"""
        @monitor_performance("api_call")
        def api_call():
            time.sleep(0.01)
            return "data"

        @monitor_performance("process_data")
        def process_data():
            time.sleep(0.005)
            return "processed"

        @monitor_performance("save_data")
        def save_data():
            time.sleep(0.002)
            return "saved"

        # Execute workflow multiple times
        for i in range(10):
            api_call()
            process_data()
            save_data()

        # Check statistics
        api_stats = get_monitor().get_stats("api_call")
        process_stats = get_monitor().get_stats("process_data")
        save_stats = get_monitor().get_stats("save_data")

        assert api_stats["call_count"] == 10
        assert process_stats["call_count"] == 10
        assert save_stats["call_count"] == 10

        # API call should be slowest
        assert api_stats["avg_duration_ms"] > process_stats["avg_duration_ms"]
        assert process_stats["avg_duration_ms"] > save_stats["avg_duration_ms"]

        # Generate report
        report = get_monitor().export_report()
        assert "api_call" in report
        assert "process_data" in report
        assert "save_data" in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
