#!/usr/bin/env python3
"""
Performance Monitoring Module

Tracks and analyzes system performance metrics:
- Response time monitoring
- Resource usage tracking
- Performance bottleneck detection
- Real-time metrics dashboard

Usage:
    from scripts.collaboration.performance_monitor import monitor_performance

    @monitor_performance(name="llm_call")
    def call_llm(prompt: str):
        return response

    from scripts.collaboration.performance_monitor import get_monitor
    stats = get_monitor().get_stats()
"""

import logging
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from functools import wraps
from typing import Any

try:
    import psutil

    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Performance metric data structure."""

    name: str
    start_time: float
    end_time: float
    duration: float
    cpu_percent: float
    memory_mb: float
    success: bool
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration * 1000,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "success": self.success,
            "error": self.error,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat(),
        }


@dataclass
class FunctionStats:
    """Function execution statistics."""

    name: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration: float = 0.0
    min_duration: float = float("inf")
    max_duration: float = 0.0
    recent_metrics: deque = field(default_factory=lambda: deque(maxlen=100))

    def add_metric(self, metric: PerformanceMetric):
        """Add a performance metric."""
        self.call_count += 1
        if metric.success:
            self.success_count += 1
        else:
            self.failure_count += 1

        self.total_duration += metric.duration
        self.min_duration = min(self.min_duration, metric.duration)
        self.max_duration = max(self.max_duration, metric.duration)
        self.recent_metrics.append(metric)

    @property
    def avg_duration(self) -> float:
        """Average execution duration."""
        return self.total_duration / self.call_count if self.call_count > 0 else 0.0

    @property
    def success_rate(self) -> float:
        """Success rate."""
        return self.success_count / self.call_count if self.call_count > 0 else 0.0

    @property
    def p95_duration(self) -> float:
        """P95 response time."""
        if not self.recent_metrics:
            return 0.0
        durations = sorted([m.duration for m in self.recent_metrics])
        idx = int(len(durations) * 0.95)
        return durations[idx] if idx < len(durations) else durations[-1]

    @property
    def p99_duration(self) -> float:
        """P99 response time."""
        if not self.recent_metrics:
            return 0.0
        durations = sorted([m.duration for m in self.recent_metrics])
        idx = int(len(durations) * 0.99)
        return durations[idx] if idx < len(durations) else durations[-1]


def _get_cpu_percent() -> float:
    """Safely get CPU percent, returns 0.0 if psutil unavailable."""
    if not _PSUTIL_AVAILABLE:
        return 0.0
    try:
        return psutil.Process().cpu_percent()
    except Exception as e:
        logger.debug("cpu_percent read failed: %s", e)
        return 0.0


def _get_memory_mb() -> float:
    """Safely get memory usage in MB, returns 0.0 if psutil unavailable."""
    if not _PSUTIL_AVAILABLE:
        return 0.0
    try:
        return psutil.Process().memory_info().rss / 1024 / 1024
    except Exception as e:
        logger.debug("memory_info read failed: %s", e)
        return 0.0


class PerformanceMonitor:
    """
    Performance Monitor

    Features:
    - Automatic function execution time tracking
    - CPU and memory usage monitoring
    - P95/P99 response time calculation
    - Performance bottleneck detection
    - Performance report generation
    """

    def __init__(self, max_history: int = 1000):
        """
        Initialize performance monitor.

        Args:
            max_history: Maximum number of historical records to retain
        """
        self.function_stats: dict[str, FunctionStats] = defaultdict(lambda: FunctionStats(name=""))
        self.all_metrics: deque = deque(maxlen=max_history)
        self.start_time = time.time()

    def record_metric(self, metric: PerformanceMetric):
        """Record a performance metric."""
        self.all_metrics.append(metric)

        if metric.name not in self.function_stats:
            self.function_stats[metric.name] = FunctionStats(name=metric.name)

        self.function_stats[metric.name].add_metric(metric)

    def monitor(self, name: str):
        """
        Decorator: monitor function performance.

        Args:
            name: Function name identifier
        """

        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                start_time = time.time()
                start_cpu = _get_cpu_percent()
                start_memory = _get_memory_mb()

                success = True
                error = None

                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    end_time = time.time()
                    end_cpu = _get_cpu_percent()
                    end_memory = _get_memory_mb()

                    metric = PerformanceMetric(
                        name=name,
                        start_time=start_time,
                        end_time=end_time,
                        duration=end_time - start_time,
                        cpu_percent=(start_cpu + end_cpu) / 2,
                        memory_mb=(start_memory + end_memory) / 2,
                        success=success,
                        error=error,
                    )

                    self.record_metric(metric)

            return wrapper

        return decorator

    def get_stats(self, function_name: str | None = None) -> dict[str, Any]:
        """
        Get statistics (compatible with MonitorProvider Protocol).

        Args:
            function_name: If specified, return only that function's stats

        Returns:
            Statistics dictionary
        """
        if function_name:
            if function_name not in self.function_stats:
                return {}

            stats = self.function_stats[function_name]
            return {
                "name": stats.name,
                "call_count": stats.call_count,
                "success_count": stats.success_count,
                "failure_count": stats.failure_count,
                "success_rate": f"{stats.success_rate * 100:.1f}%",
                "avg_duration_ms": stats.avg_duration * 1000,
                "min_duration_ms": stats.min_duration * 1000,
                "max_duration_ms": stats.max_duration * 1000,
                "p95_duration_ms": stats.p95_duration * 1000,
                "p99_duration_ms": stats.p99_duration * 1000,
            }

        llm_calls = [s for name, s in self.function_stats.items() if name.startswith("llm_call:")]
        agent_executions = [s for name, s in self.function_stats.items() if name.startswith("agent:")]

        total_llm_calls = sum(s.call_count for s in llm_calls)
        total_agent_executions = sum(s.call_count for s in agent_executions)

        avg_llm_duration = sum(s.total_duration for s in llm_calls) / total_llm_calls if total_llm_calls > 0 else 0.0

        avg_agent_duration = (
            sum(s.total_duration for s in agent_executions) / total_agent_executions
            if total_agent_executions > 0
            else 0.0
        )

        return {
            "total_llm_calls": total_llm_calls,
            "total_agent_executions": total_agent_executions,
            "avg_llm_duration": avg_llm_duration,
            "avg_agent_duration": avg_agent_duration,
            "total_tokens": 0,
            "uptime_seconds": time.time() - self.start_time,
            "total_metrics": len(self.all_metrics),
            "functions": {
                name: {
                    "call_count": stats.call_count,
                    "success_rate": f"{stats.success_rate * 100:.1f}%",
                    "avg_duration_ms": stats.avg_duration * 1000,
                    "p95_duration_ms": stats.p95_duration * 1000,
                }
                for name, stats in self.function_stats.items()
            },
        }

    def get_slowest_functions(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the slowest functions by average duration."""
        sorted_funcs = sorted(self.function_stats.values(), key=lambda s: s.avg_duration, reverse=True)[:limit]

        return [
            {
                "name": stats.name,
                "avg_duration_ms": stats.avg_duration * 1000,
                "call_count": stats.call_count,
                "p95_duration_ms": stats.p95_duration * 1000,
            }
            for stats in sorted_funcs
        ]

    def get_bottlenecks(self, threshold_ms: float = 1000) -> list[dict[str, Any]]:
        """
        Detect performance bottlenecks.

        Args:
            threshold_ms: Threshold in milliseconds; functions above this are bottlenecks

        Returns:
            List of bottleneck entries
        """
        bottlenecks = []

        for name, stats in self.function_stats.items():
            if stats.avg_duration * 1000 > threshold_ms:
                bottlenecks.append(
                    {
                        "name": name,
                        "avg_duration_ms": stats.avg_duration * 1000,
                        "p95_duration_ms": stats.p95_duration * 1000,
                        "call_count": stats.call_count,
                        "severity": "high" if stats.avg_duration * 1000 > threshold_ms * 2 else "medium",
                    }
                )

        return sorted(bottlenecks, key=lambda x: x["avg_duration_ms"], reverse=True)

    def get_recent_errors(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent error entries."""
        errors = [m for m in self.all_metrics if not m.success]
        return [m.to_dict() for m in list(errors)[-limit:]]

    def record_llm_call(
        self,
        backend: str,
        model: str,
        duration: float,
        token_count: int,  # noqa: ARG002
        success: bool,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Record an LLM API call (implements MonitorProvider Protocol)."""
        metric_name = f"llm_call:{backend}:{model}"

        metric = PerformanceMetric(
            name=metric_name,
            start_time=time.time() - duration,
            end_time=time.time(),
            duration=duration,
            cpu_percent=_get_cpu_percent(),
            memory_mb=_get_memory_mb(),
            success=success,
            error=metadata.get("error") if metadata else None,
        )

        self.record_metric(metric)

    def record_agent_execution(
        self, agent_role: str, task: str, duration: float, success: bool, metadata: dict[str, Any] | None = None  # noqa: ARG002
    ) -> None:
        """Record an agent execution (implements MonitorProvider Protocol)."""
        metric_name = f"agent:{agent_role}"

        metric = PerformanceMetric(
            name=metric_name,
            start_time=time.time() - duration,
            end_time=time.time(),
            duration=duration,
            cpu_percent=_get_cpu_percent(),
            memory_mb=_get_memory_mb(),
            success=success,
            error=metadata.get("error") if metadata else None,
        )

        self.record_metric(metric)

    def generate_report(self, output_path: str) -> None:
        """Generate performance report to file (implements MonitorProvider Protocol)."""
        try:
            report = self.export_report()
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            logger.info("Performance report generated: %s", output_path)
        except Exception as e:
            logger.error("Failed to generate report: %s", e)
            raise OSError(f"Failed to generate report: {e}") from e

    def is_available(self) -> bool:
        """Check if monitoring is available (implements MonitorProvider Protocol)."""
        return True

    def export_report(self) -> str:
        """Export performance report as Markdown string."""
        stats = self.get_stats()
        slowest = self.get_slowest_functions(5)
        bottlenecks = self.get_bottlenecks()
        errors = self.get_recent_errors(5)

        report = f"""# Performance Monitoring Report

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
**Uptime**: {stats["uptime_seconds"]:.0f} seconds
**Total Metrics**: {stats["total_metrics"]}

## Overall Statistics

| Function | Calls | Success Rate | Avg Duration | P95 Duration |
|----------|-------|--------------|--------------|--------------|
"""

        for name, func_stats in stats["functions"].items():
            report += f"| {name} | {func_stats['call_count']} | {func_stats['success_rate']} | {func_stats['avg_duration_ms']:.1f}ms | {func_stats['p95_duration_ms']:.1f}ms |\n"

        if slowest:
            report += "\n## Slowest Functions\n\n"
            for i, func in enumerate(slowest, 1):
                report += f"{i}. **{func['name']}**: {func['avg_duration_ms']:.1f}ms avg ({func['call_count']} calls)\n"

        if bottlenecks:
            report += "\n## Performance Bottlenecks\n\n"
            for bottleneck in bottlenecks:
                report += f"- **{bottleneck['name']}** ({bottleneck['severity']}): {bottleneck['avg_duration_ms']:.1f}ms avg\n"

        if errors:
            report += "\n## Recent Errors\n\n"
            for error in errors:
                report += f"- **{error['name']}** at {error['timestamp']}: {error['error']}\n"

        return report


_monitor_instance: PerformanceMonitor | None = None


def get_monitor() -> PerformanceMonitor:
    """Get or create global monitor instance."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PerformanceMonitor()
    return _monitor_instance


def monitor_performance(name: str):
    """
    Decorator: monitor function performance.

    Args:
        name: Function name identifier

    Example:
        @monitor_performance("llm_call")
        def call_llm(prompt: str):
            return response
    """
    monitor = get_monitor()
    return monitor.monitor(name)


def reset_monitor():
    """Reset global monitor instance (mainly for testing)."""
    global _monitor_instance
    _monitor_instance = None
