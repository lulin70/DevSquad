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
from unittest.mock import Mock, patch
from .performance_monitor import (
    PerformanceMetric,
    PerformanceMonitor,
    get_monitor,
    monitor_performance
)


class TestPerformanceMetric:
    """Test performance metric data class"""
    
    def test_metric_creation(self):
        """Test creating a performance metric"""
        metric = PerformanceMetric(
            function_name="test_func",
            duration_ms=100.5,
            cpu_percent=25.0,
            memory_mb=50.0
        )
        
        assert metric.function_name == "test_func"
        assert metric.duration_ms == 100.5
        assert metric.cpu_percent == 25.0
        assert metric.memory_mb == 50.0
        assert metric.timestamp is not None


class TestPerformanceMonitor:
    """Test performance monitor"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.monitor = PerformanceMonitor()
    
    def test_initialization(self):
        """Test monitor initialization"""
        assert len(self.monitor.metrics) == 0
        assert self.monitor.max_history == 10000
    
    def test_record_metric(self):
        """Test recording a single metric"""
        self.monitor.record(
            function_name="test_func",
            duration_ms=100.0,
            cpu_percent=20.0,
            memory_mb=30.0
        )
        
        assert "test_func" in self.monitor.metrics
        assert len(self.monitor.metrics["test_func"]) == 1
        
        metric = self.monitor.metrics["test_func"][0]
        assert metric.duration_ms == 100.0
        assert metric.cpu_percent == 20.0
        assert metric.memory_mb == 30.0
    
    def test_record_multiple_metrics(self):
        """Test recording multiple metrics for same function"""
        for i in range(5):
            self.monitor.record(
                function_name="test_func",
                duration_ms=100.0 + i * 10,
                cpu_percent=20.0,
                memory_mb=30.0
            )
        
        assert len(self.monitor.metrics["test_func"]) == 5
    
    def tetory_limit(self):
        """Test max history limit enforcement"""
        monitor = PerformanceMonitor(max_history=10)
        
        # Record more than max_history
        for i in range(15):
            monitor.record("test_func", duration_ms=float(i))
        
        # Should keep only last 10
        assert len(monitor.metrics["test_func"]) == 10
        
        # Should keep the most recent ones
        durations = [m.duration_ms for m in monitor.metrics["test_func"]]
        assert durations == [5.0, 6.0, 7.0, 8.0, 9.0, 10.0, 11.0, 12.0, 13.0, 14.0]
    
    def test_get_stats_empty(self):
        """Test getting stats for non-existent function"""
        stats = self.monitor.get_stats("nonexistent")
        assert stats is None
    
    def test_get_stats_single_metric(self):
        """Test statistics with single metric"""
        self.monitor.record("test_func", duration_ms=100.0, cpu_percent=20.0, memory_mb=30.0)
        
        stats = self.monitor.get_stats("test_func")
        assert stats["call_count"] == 1
        assert stats["avg_duration_ms"] == 100.0
        assert stats["min_duration_ms"] == 100.0
        assert stats["max_duration_ms"] == 100.0
        assert stats["p95_duration_ms"] == 100.0
        assert stats["p99_duration_ms"] == 100.0
    
    def test_get_stats_multiple_metrics(self):
        """Test statistics with multiple metrics"""
        durations = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
        
        for d in durations:
            self.monitor.record("test_func", duration_ms=d, cpu_percent=20.0, memory_mb=30.0)
        
        stats = self.monitor.get_stats("test_func")
        assert stats["call_count"] == 10
        assert stats["avg_duration_ms"] == 55.0
        assert stats["min_duration_ms"] == 10.0
        assert stats["max_duration_ms"] == 100.0
        
        # P95 should be around 95th percentile
        assert 90.0 <= stats["p95_duration_ms"] <= 100.0
        
        # P99 should be around 99th percentile
        assert 95.0 <= stats["p99_duration_ms"] <= 100.0
    
    def test_percentile_calculation(self):
        """Test percentile calculation accuracy"""
        # Create 100 metrics with known distribution
        for i in range(100):
            self.monitor.record("test_func", duration_ms=float(i + 1))
        
        stats = self.monitor.get_stats("test_func")
        
        # P95 should be around 95
        assert 94.0 <= stats["p95_duration_ms"] <= 96.0
        
        # P99 should be around 99
        assert 98.0 <= stats["p99_duration_ms"] <= 100.0
    
    def test_get_all_stats(self):
        """Test getting stats for all functions"""
        self.monitor.record("func1", duration_ms=100.0)
        self.monitor.record("func2", duration_ms=200.0)
        self.monitor.record("func1", duration_ms=150.0)
        
        all_stats = self.monitor.get_all_stats()
        
        assert "func1" in all_stats
        assert "func2" in all_stats
        assert all_stats["func1"]["call_count"] == 2
        assert all_stats["func2"]["call_count"] == 1
    
    def test_detect_bottlenecks(self):
        """Test bottleneck detection"""
        # Add fast function
        for i in range(10):
            self.monitor.record("fast_func", duration_ms=10.0)
        
        # Add slow function (bottleneck)
        for i in range(10):
            self.monitor.record("slow_func", duration_ms=2000.0)
        
        bottlenecks = self.monitor.detect_bottlenecks(threshold_ms=1000.0)
        
        assert len(bottlenecks) == 1
        assert bottlenecks[0]["function_name"] == "slow_func"
        assert bottlenecks[0]["avg_duration_ms"] == 2000.0
    
    def test_detect_bottlenecks_empty(self):
        """Test bottleneck detection with no bottlenecks"""
        for i in range(10):
            self.monitor.record("fast_func", duration_ms=10.0)
        
        bottlenecks = self.monitor.detect_bottlenecks(threshold_ms=1000.0)
        assert len(bottlenecks) == 0
    
    def test_clear_metrics(self):
        """Test clearing metrics for a function"""
        self.monitor.record("test_func", duration_ms=100.0)
        self.monitor.record("other_func", duration_ms=200.0)
        
        self.monitor.clear("test_func")
        
        assert "test_func" not in self.monitor.metrics
        assert "other_func" in self.monitor.metrics
    
    def test_clear_all_metrics(self):
        """Test clearing all metrics"""
        self.monitor.record("func1", duration_ms=100.0)
        self.monitor.record("func2", duration_ms=200.0)
        
        self.monitor.clear_all()
        
        assert len(self.monitor.metrics) == 0
    
    def test_export_report(self):
        """Test exporting markdown report"""
        self.monitor.record("func1", duration_ms=100.0, cpu_percent=20.0, memory_mb=30.0)
        self.monitor.record("func2", duration_ms=200.0, cpu_percent=40.0, memory_mb=60.0)
        
        report = self.monitor.export_report()
        
        assert "# Performance Report" in report
        assert "func1" in report
        assert "func2" in report
        assert "100.0" in report
        assert "200.0" in report
    
    def test_export_report_with_bottlenecks(self):
        """Test report includes bottleneck section"""
        # Add slow function
        for i in range(5):
            self.monitor.record("slow_func", duration_ms=2000.0)
        
        report = self.monitor.export_report(bottleneck_threshold_ms=1000.0)
        
        assert "## Bottlenecks" in report
        assert "slow_func" in report


class TestMonitorDecorator:
    """Test monitor_performance decorator"""
    
    def setup_method(self):
        """Setup test fixtures"""
        # Reset global monitor
        from performance_monitor import _global_monitor
        if _global_monitor[0] is not None:
            _global_monitor[0].clear_all()
 
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
        
        assert stats is not None
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
        
        assert stats is not None
        assert stats["call_count"] == 1
    
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
    
    def test_singleton(self):
        """Test global monitor is singleton"""
        monitor1 = get_monitor()
        monitor2 = get_monitor()
        
        assert monitor1 is monitor2
    
    def test_shared_state(self):
        """Test global monitor shares state"""
        monitor1 = get_monitor()
        monitor1.record("test_func", duration_ms=100.0)
        
        monitor2 = get_monitor()
        stats = monitor2.get_stats("test_func")
        
        assert stats is not None
        assert stats["call_count"] == 1
    
    def test_reset_monitor(self):
        """Test resetting global monitor"""
        from performance_monitor import reset_monitor
        
        monitor = get_monitor()
        monitor.record("test_func", duration_ms=100.0)
        
        reset_monitor()
        
        # Get new monitor instance
        new_monitor = get_monitor()
        assert len(new_monitor.metrics) == 0


class TestIntegration:
    """Integration tests"""
    
    def test_real_world_scenario(self):
        """Test realistic usage scenario"""
        monitor = PerformanceMonitor()
        
        # Simulate multiple function calls with varying performance
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
