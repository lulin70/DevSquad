#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
        # Your function
        return response
    
    # Get metrics
    from scripts.collaboration.performance_monitor import get_monitor
    stats = get_monitor().get_stats()
"""

import time
import psutil
import logging
from typing import Callable, Dict, Any, List, Optional
from functools import wraps
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict, deque


logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """性能指标"""
    name: str
    start_time: float
    end_time: float
    duration: float
    cpu_percent: float
    memory_mb: float
    success: bool
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "duration_ms": self.duration * 1000,
            "cpu_percent": self.cpu_percent,
            "memory_mb": self.memory_mb,
            "success": self.success,
            "error": self.error,
            "timestamp": datetime.fromtimestamp(self.start_time).isoformat()
        }


@dataclass
class FunctionStats:
    """函数统计信息"""
    name: str
    call_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    total_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    recent_metrics: deque = field(default_factory=lambda: deque(maxlen=100))
    
    def add_metric(self, metric: PerformanceMetric):
        """添加性能指标"""
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
        """平均执行时间"""
        return self.total_duration / self.call_count if self.call_count > 0 else 0.0
    
    @property
    def success_rate(self) -> float:
        """成功率"""
        return self.success_count / self.call_count if self.call_count > 0 else 0.0
    
    @property
    def p95_duration(self) -> float:
        """P95 响应时间"""
        if not self.recent_metrics:
            return 0.0
        durations = sorted([m.duration for m in self.recent_metrics])
        idx = int(len(durations) * 0.95)
        return durations[idx] if idx < len(durations) else durations[-1]
    
    @property
    def p99_duration(self) -> float:
        """P99 响应时间"""
        if not self.recent_metrics:
            return 0.0
        durations = sorted([m.duration for m in self.recent_metrics])
        idx = int(len(durations) * 0.99)
        return durations[idx] if idx < len(durations) else durations[-1]


class PerformanceMonitor:
    """
    性能监控器
      Features:
    - 自动追踪函数执行时间
    - 监控 CPU 和内存使用
    - 计算 P95/P99 响应时间
    - 检测性能瓶颈
    - 生成性能报告
    """
    
    def __init__(self, max_history: int = 1000):
        """
        初始化监控器
        
        Args:
            max_history: 保留的历史记录数量
        """
        self.function_stats: Dict[str, FunctionStats] = defaultdict(
            lambda: FunctionStats(name="")
        )
        self.all_metrics: deque = deque(maxlen=max_history)
        self.process = psutil.Process()
        self.start_time = time.time()
    
    def record_metric(self, metric: PerformanceMetric):
        """记录性能指标"""
        self.all_metrics.append(metric)
        
        if metric.name not in self.function_stats:
            self.function_stats[metric.name] = FunctionStats(name=metric.name)
        
        self.function_stats[metric.name].add_metric(metric)
    
    def monitor(self, name: str):
        """
        装饰器：监控函数性能
        
        Args:
            name: 函数名称标识
        """
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs):
                # 记录开始状态
                start_time = time.time()
                start_cpu = self.process.cpu_percent()
                start_memory = self.process.memory_info().rss / 1024 / 1024  # MB
                
                success = True
                error = None
                result = None
                
                try:
                    result = func(*args, **kwargs)
                    return result
                except Exception as e:
                    success = False
                    error = str(e)
                    raise
                finally:
                    # 记录结束状态
                    end_time = time.time()
                    end_cpu = self.process.cpu_percent()
                    end_memory = self.process.memory_info().rss / 1024 / 1024
                    
                    metric = PerformanceMetric(
                        name=name,
                        start_time=start_time,
                        end_time=end_time,
                        duration=end_time - start_time,
                        cpu_percent=(start_cpu + end_cpu) / 2,
                        memory_mb=(start_memory + end_memory) / 2,
                        success=success,
                        error=error
                    )
                    
                    self.record_metric(metric)
            
            return wrapper
        return decorator
    
    def get_stats(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """
        获取统计信息
        
        Args:
            function_name: 如果指定，只返回该函数的统计
        
        Returns:
            统计信息字典
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
        
        # 返回所有函数的统计
        return {
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
            }
        }
    
    def get_slowest_functions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最慢的函数"""
        sorted_funcs = sorted(
            self.function_stats.values(),
            key=lambda s: s.avg_duration,
            reverse=True
        )[:limit]
        
        return [
            {
                "name": stats.name,
                "avg_duration_ms": stats.avg_duration * 1000,
                "call_count": stats.call_count,
                "p95_duration_ms": stats.p95_duration * 1000,
            }
            for stats in sorted_funcs
        ]
    
    def get_bottlenecks(self, threshold_ms: float = 1000) -> List[Dict[str, Any]]:
        """
        检测性能瓶颈
        
        Args:
            threshold_ms: 阈值（毫秒），超过此值视为瓶颈
        
        Returns:
            瓶颈列表
        """
        bottlenecks = []
        
        for name, stats in self.function_stats.items():
            if stats.avg_duration * 1000 > threshold_ms:
                bottlenecks.append({
                    "name": name,
                    "avg_duration_ms": stats.avg_duration * 1000,
                    "p95_duration_ms": stats.p95_duration * 1000,
                    "call_count": stats.call_count,
                    "severity": "high" if stats.avg_duration * 1000 > threshold_ms * 2 else "medium"
                })
        
        return sorted(bottlenecks, key=lambda x: x["avg_duration_ms"], reverse=True)
    
    def get_recent_errors(self, limit: int = 10) -> List[Dict[str, Any]]:
        """获取最近的错误"""
        errors = [m for m in self.all_metrics if not m.success]
        return [m.to_dict() for m in list(errors)[-limit:]]
    
    def export_report(self) -> str:
        """导出性能报告（Markdown 格式）"""
        stats = self.get_stats()
        slowest = self.get_slowest_functions(5)
        bottlenecks = self.get_bottlenecks()
        errors = self.get_recent_errors(5)
        
        report = f"""# Performance Monitoring Report

**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Uptime**: {stats['uptime_seconds']:.0f} seconds
**Total Metrics**: {stats['total_metrics']}

## Overall Statistics

| Function | Calls | Success Rate | Avg Duration | P95 Duration |
|----------|-------|--------------|--------------|--------------|
"""
        
        for name, func_stats in stats['functions'].items():
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


# 全局实例
_monitor_instance: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """获取全局监控器实例"""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PerformanceMonitor()
    return _monitor_instance


def monitor_performance(name: str):
    """
    装饰器：监控函数性能
    
    Args:
        name: 函数名称标识
    
    Example:
        @monitor_performance("llm_call")
        def call_llm(prompt: str):
            return response
    """
    monitor = get_monitor()
    return monitor.monitor(name)


def reset_monitor():
    """重置全局监控器（主要用于测试）"""
    global _monitor_instance
    _monitor_instance = None
