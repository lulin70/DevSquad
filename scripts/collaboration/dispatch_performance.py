#!/usr/bin/env python3
"""
Dispatch performance monitoring module.

Extracted from dispatcher.py for modularity. Contains:
- PerformanceMonitor: Performance monitoring and alerting system
"""

import json
import logging
import os
import threading
from collections import deque
from typing import Any, Optional

from .dispatch_models import PerformanceMetric, PerformanceThresholds

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """Performance monitoring and alerting system.

    Collects performance metrics from each dispatch call, maintains
    a sliding window of recent metrics, checks against thresholds,
    and generates alerts for performance anomalies.

    Capabilities:
    - Record performance metrics from dispatch calls
    - Detect performance regressions via threshold checking
    - Maintain sliding window statistics (default: 100 entries)
    - Generate performance reports
    - Trigger real-time warnings and critical alerts

    Attributes:
        window_size: Maximum number of metrics to retain in sliding window
        thresholds: PerformanceThresholds configuration instance

    Example:
        >>> monitor = PerformanceMonitor(window_size=50)
        >>> metric = PerformanceMetric(
        ...     timestamp="2024-01-01T12:00:00",
        ...     task_description="Test task",
        ...     total_duration=25.5,
        ...     step_timings={"execute": 20.0, "collect": 1.0},
        ...     success=True,
        ...     error_count=0,
        ...     role_count=3,
        ... )
        >>> monitor.record(metric)
    """

    def __init__(self, window_size: int = 100, thresholds: Optional[PerformanceThresholds] = None):
        """Initialize Performance Monitor.

        Args:
            window_size: Maximum metrics to retain in sliding window (default: 100)
            thresholds: Custom threshold configuration (default: standard thresholds)
        """
        self.window_size = window_size
        self.thresholds = thresholds or PerformanceThresholds()
        self._metrics: deque[PerformanceMetric] = deque(maxlen=window_size)
        self._lock = threading.Lock()

    def record(self, metric: PerformanceMetric) -> None:
        """Record a performance metric entry.

        Adds metric to sliding window and immediately checks against
        configured thresholds. Logs warnings or critical alerts if exceeded.

        Args:
            metric: PerformanceMetric object to record

        Note:
            Automatically triggers threshold checking on insertion.
            Critical alerts logged at CRITICAL level, warnings at WARNING level.
        """
        with self._lock:
            self._metrics.append(metric)

            # 实时检查阈值
            warnings, criticals = self._check_thresholds(metric)
            if criticals:
                logger.critical("PERFORMANCE CRITICAL: %s", json.dumps(criticals, ensure_ascii=False))
            elif warnings:
                logger.warning("PERFORMANCE WARNING: %s", json.dumps(warnings, ensure_ascii=False))

    def _check_thresholds(self, metric: PerformanceMetric) -> tuple[list[dict], list[dict]]:
        """检查指标是否超过阈值"""
        warnings = []
        criticals = []

        # 总耗时检查
        if metric.total_duration > self.thresholds.total_duration_critical:
            criticals.append(
                {
                    "type": "total_duration",
                    "value": metric.total_duration,
                    "threshold": self.thresholds.total_duration_critical,
                    "task": metric.task_description[:50],
                }
            )
        elif metric.total_duration > self.thresholds.total_duration_warning:
            warnings.append(
                {
                    "type": "total_duration",
                    "value": metric.total_duration,
                    "threshold": self.thresholds.total_duration_warning,
                }
            )

        # 各步骤耗时检查
        for step, duration in metric.step_timings.items():
            critical_threshold = self.thresholds.step_criticals.get(step)
            warning_threshold = self.thresholds.step_warnings.get(step)

            if critical_threshold and duration > critical_threshold:
                criticals.append(
                    {
                        "type": f"step_{step}",
                        "value": duration,
                        "threshold": critical_threshold,
                    }
                )
            elif warning_threshold and duration > warning_threshold:
                warnings.append(
                    {
                        "type": f"step_{step}",
                        "value": duration,
                        "threshold": warning_threshold,
                    }
                )

        return warnings, criticals

    def get_statistics(self) -> dict[str, Any]:
        """获取滑动窗口内的统计数据"""
        with self._lock:
            if not self._metrics:
                return {"count": 0}

            metrics_list = list(self._metrics)
            count = len(metrics_list)

            durations = [m.total_duration for m in metrics_list]
            successes = sum(1 for m in metrics_list if m.success)

            stats = {
                "count": count,
                "success_rate": successes / count,
                "duration": {
                    "min": min(durations),
                    "max": max(durations),
                    "avg": sum(durations) / count,
                    "p50": sorted(durations)[int(count * 0.5)],
                    "p95": sorted(durations)[int(count * 0.95)],
                    "p99": sorted(durations)[int(count * 0.99)] if count > 20 else max(durations),
                },
                "errors_per_dispatch_avg": sum(m.error_count for m in metrics_list) / count,
                "roles_per_dispatch_avg": sum(m.role_count for m in metrics_list) / count,
            }

            # 各步骤统计
            step_stats = {}
            all_steps: set = set()
            for m in metrics_list:
                all_steps.update(m.step_timings.keys())

            for step in all_steps:
                step_durations = [m.step_timings.get(step, 0) for m in metrics_list if step in m.step_timings]
                if step_durations:
                    step_stats[step] = {
                        "avg": sum(step_durations) / len(step_durations),
                        "max": max(step_durations),
                        "min": min(step_durations),
                        "p95": sorted(step_durations)[int(len(step_durations) * 0.95)],
                    }

            stats["steps"] = step_stats

            return stats

    def detect_regression(self, baseline_count: int = 10) -> dict[str, Any] | None:
        """
        检测性能回归

        对比最近N次与历史平均，检测显著恶化
        """
        with self._lock:
            if len(self._metrics) < baseline_count * 2:
                return None

            metrics_list = list(self._metrics)
            recent = metrics_list[-baseline_count:]
            baseline = metrics_list[:-baseline_count]

            recent_avg = sum(m.total_duration for m in recent) / len(recent)
            baseline_avg = sum(m.total_duration for m in baseline) / len(baseline)

            regression_ratio = (recent_avg - baseline_avg) / baseline_avg if baseline_avg > 0 else 0

            if regression_ratio > 0.2:  # 超过20%视为回归
                return {
                    "detected": True,
                    "regression_ratio": round(regression_ratio, 3),
                    "baseline_avg": round(baseline_avg, 3),
                    "recent_avg": round(recent_avg, 3),
                    "baseline_samples": len(baseline),
                    "recent_samples": len(recent),
                    "severity": "high" if regression_ratio > 0.5 else "medium",
                }

            return None

    def export_metrics(self, output_file: str, allowed_base_dir: str = "/tmp") -> None:
        """导出性能指标到文件"""
        output_path = os.path.abspath(output_file)
        base_dir = os.path.abspath(allowed_base_dir)
        if not output_path.startswith(base_dir) and not output_path.startswith("/tmp"):
            logger.warning("Export path outside allowed directories: %s", output_path)
            output_path = os.path.join(base_dir, os.path.basename(output_file))

        with self._lock:
            data = [m.__dict__ for m in self._metrics]

            os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
            with open(output_path, "w") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info("Exported %d performance metrics to %s", len(data), output_path)

    def clear(self) -> None:
        """清除历史数据"""
        with self._lock:
            self._metrics.clear()
