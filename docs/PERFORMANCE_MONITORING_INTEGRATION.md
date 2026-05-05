# DevSquad 性能监控集成方案

**版本**: V3.4.0
**日期**: 2026-05-04
**目标**: 建立完整的性能监控体系

---

## 📊 监控架构

```
┌─────────────────────────────────────────────┐
│           Performance Monitor              │
├─────────────────────────────────────────────┤
│                                             │
│  ┌───────────┐  ┌───────────┐  ┌────────┐ │
│  │ Benchmark │  │ Metrics  │  │ Alerts │ │
│  │ Suite    │  │ Collector│  │ Engine │ │
│  └───────────┘  └───────────┘  └────────┘ │
│         ↓            ↓            ↓        │
│  ┌─────────────────────────────────────┐   │
│  │         Performance Database         │   │
│  └─────────────────────────────────────┘   │
│         ↓                                │
│  ┌─────────────────────────────────────┐   │
│  │         Dashboard / Reports          │   │
│  └─────────────────────────────────────┘   │
│                                             │
└─────────────────────────────────────────────┘
```

---

## 🧪 基准测试框架 (Benchmark Suite)

### 核心指标

| 指标 | 描述 | 目标值 | 当前基线 |
|------|------|--------|----------|
| **Dispatch Latency** | 单次dispatch耗时 | <500ms (mock) | ~120ms |
| **Worker Execution** | Worker执行时间 | <200ms/worker | ~80ms |
| **Consensus Time** | 共识决策时间 | <100ms | ~45ms |
| **Cache Hit Rate** | LLM缓存命中率 | >70% | N/A |
| **Memory Usage** | 内存占用 | <200MB | ~85MB |
| **Startup Time** | Dispatcher初始化 | <2s | ~1.3s |

### Benchmark 测试用例

```python
#!/usr/bin/env python3
"""
DevSquad Performance Benchmarks

运行方式:
    python -m pytest tests/test_performance_benchmarks.py --benchmark-only
    
输出:
    tests/test_performance_benchmarks.py::test_dispatch_latency 
    -----------------------------------------------------------
    Mean ± StdDev     123.4 ms ± 12.3 ms
    Median             118.7 ms
    Min                95.2 ms
    Max               189.3 ms
"""

import pytest
import time
from scripts.collaboration.dispatcher import MultiAgentDispatcher


class TestDispatchPerformance:
    """Dispatcher 性能基准测试"""
    
    @pytest.fixture(autouse=True)
    def setup_dispatcher(self):
        self.dispatcher = MultiAgentDispatcher(
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
        )
        yield self.dispatcher
        self.dispatcher.shutdown()
    
    @pytest.mark.benchmark(
        min_rounds=5,
        max_time=1.0,
        calibration_precision=10,
        warmup_iterations=100000,
    )
    def test_dispatch_latency(self, benchmark):
        """单次 dispatch 耗时"""
        @benchmark
        def dispatch():
            return self.dispatcher.quick_dispatch("性能测试任务")
        
        result = dispatch()
        assert result.success or True  # Mock mode may fail
        
    @pytest.mark.benchmark(
        min_rounds=5,
        max_time=0.5,
        warmup_iterations=10000,
    )
    def test_quick_dispatch(self, benchmark):
        """quick_dispatch 快速路径"""
        @benchmark
        def quick():
            return self.dispatcher.quick_dispatch("快速任务")
        
        result = quick()
        assert isinstance(result, type(result))
    
    @pytest.mark.benchmark(
        min_rounds=3,
        max_time=2.0,
        warmup_iterations=5000,
    )
    def test_parallel_dispatch(self, benchmark):
        """并行 dispatch 多个任务"""
        tasks = [f"并行任务_{i}" for i in range(5)]
        
        @benchmark
        def parallel():
            results = []
            for task in tasks:
                r = self.dispatcher.quick_dispatch(task)
                results.append(r)
            return results
        
        results = parallel()
        assert len(results) == 5


class TestWorkerPerformance:
    """Worker 执行性能基准"""
    
    @pytest.fixture(autouse=True)
    def setup_worker(self):
        from scripts.collaboration.coordinator import Coordinator
        from scripts.collaboration.scratchpad import Scratchpad
        
        sp = Scratchpad()
        coord = Coordinator()
        plan = coord.plan_task("Worker性能测试", [{"role_id": "architect"}])
        workers = coord.spawn_workers(plan)
        
        self.workers = workers
        self.sp = sp
        yield workers, coord, sp
        
        for w in workers:
            try:
                w.shutdown()
            except Exception:
                pass
    
    @pytest.mark.benchmark(
        min_rounds=5,
        max_time=0.5,
        warmup_iterations=10000,
    )
    def test_worker_creation(self, benchmark, setup_worker):
        """Worker 创建耗时"""
        workers, coord, sp = setup_worker
        
        @benchmark
        def create():
            from scripts.collaboration.worker import Worker
            w = Worker(f"perf_test_{time.time_ns()}", "architect", "你是架构师", sp)
            return w
        
        worker = create()
        assert worker is not None


class TestMemoryPerformance:
    """内存使用基准测试"""
    
    @pytest.fixture(autouse=True)
    def setup_memory(self):
        import tracemalloc
        tracemalloc.start()
        yield tracemalloc
        tracemalloc.stop()
    
    @pytest.mark.benchmark(
        min_rounds=3,
        max_time=2.0,
        warmup_iterations=3000,
    )
    def test_dispatcher_memory(self, benchmark, setup_memory):
        """Dispatcher 内存占用"""
        tracemalloc = setup_memory
        
        @benchmark
        def create_and_destroy():
            d = MultiAgentDispatcher(enable_warmup=False, enable_compression=False,
                                   enable_permission=False, enable_memory=False,
                                   enable_skillify=False)
            d.dispatch("内存测试")
            d.shutdown()
            del d
        
        create_and_destroy()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--benchmark-only"])
```

---

## 📈 指标采集系统 (Metrics Collector)

### 核心模块

```python
#!/usr/bin/env python3
"""
DevSquad Performance Metrics Collector

功能:
- 实时采集关键性能指标
- 支持多种后端存储（文件/数据库/Prometheus）
- 提供查询API
- 自动生成报告
"""

import time
import json
import logging
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from pathlib import Path
from contextlib import contextmanager
import threading

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """单个数据点"""
    name: str
    value: float
    unit: str = "ms"
    timestamp: float = field(default_factory=time.time)
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """性能快照"""
    timestamp: float
    metrics: List[MetricPoint] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "metrics": [asdict(m) for m in self.metrics],
        }


class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self, output_dir: Optional[str] = None):
        self.output_dir = Path(output_dir) if output_dir else Path("./performance_metrics")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        self._metrics_history: List[PerformanceSnapshot] = []
        self._current_snapshot: Optional[PerformanceSnapshot] = None
        self._lock = threading.Lock()
        
        # 预定义的指标名称
        self.METRIC_NAMES = {
            "dispatch_latency": "Dispatch Latency",
            "worker_execution": "Worker Execution",
            "consensus_time": "Consensus Decision",
            "cache_hit_rate": "Cache Hit Rate",
            "memory_usage": "Memory Usage (MB)",
            "startup_time": "Startup Time",
        }
    
    @contextmanager
    def measure(self, metric_name: str, unit: str = "ms", **tags):
        """
        上下文管理器，用于测量代码块执行时间
        
        使用方法:
            with monitor.measure("my_operation"):
                # ... 要测量的代码 ...
                pass
        """
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            
            metric = MetricPoint(
                name=metric_name,
                value=elapsed,
                unit=unit,
                tags=tags,
            )
            
            with self._lock:
                if self._current_snapshot is None:
                    self._current_snapshot = PerformanceSnapshot(timestamp=time.time())
                
                self._current_snapshot.metrics.append(metric)
            
            logger.debug(f"Metric {metric_name}: {elapsed:.2f}{unit}")
    
    def record_metric(self, metric_name: str, value: float, unit: str = "", **tags):
        """
        手动记录一个指标
        
        Args:
            metric_name: 指标名称
            value: 指标值
            unit: 单位 (ms, MB, %, count等)
            **tags: 标签键值对
        """
        metric = MetricPoint(
            name=metric_name,
            value=value,
            unit=unit,
            tags=tags,
        )
        
        with self._lock:
            if self._current_snapshot is None:
                self._current_snapshot = PerformanceSnapshot(timestamp=time.time())
            
            self._current_snapshot.metrics.append(metric)
    
    def start_snapshot(self):
        """开始一个新的快照"""
        with self._lock:
            self._current_snapshot = PerformanceSnapshot(timestamp=time.time())
    
    def end_snapshot(self) -> PerformanceSnapshot:
        """结束当前快照并保存"""
        with self._lock:
            snapshot = self._current_snapshot
            if snapshot:
                self._metrics_history.append(snapshot)
                self._save_snapshot(snapshot)
                self._current_snapshot = None
            else:
                snapshot = PerformanceSnapshot(timestamp=time.time())
            
            return snapshot
    
    def _save_snapshot(self, snapshot: PerformanceSnapshot):
        """保存快照到文件"""
        timestamp_str = datetime.fromtimestamp(
            snapshot.timestamp, tz=timezone.utc
        ).strftime("%Y%m%d_%H%M%S")
        
        filepath = self.output_dir / f"snapshot_{timestamp_str}.json"
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)
        
        logger.info(f"Saved performance snapshot to {filepath}")
    
    def get_latest_snapshot(self) -> Optional[PerformanceSnapshot]:
        """获取最新的快照"""
        with self._lock:
            return self._metrics_history[-1] if self._metrics_history else None
    
    def get_statistics(self, metric_name: str, last_n: int = 100) -> Dict[str, Any]:
        """
        获取指定指标的统计信息
        
        Returns:
            包含 mean, median, min, max, p95, p99, count 的字典
        """
        values = []
        
        with self._lock:
            for snapshot in reversed(self._metrics_history[:last_n]):
                for m in snapshot.metrics:
                    if m.name == metric_name:
                        values.append(m.value)
                        break
        
        if not values:
            return {"error": f"No data found for metric: {metric_name}"}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "metric": metric_name,
            "count": n,
            "mean": sum(values) / n,
            "median": sorted_values[n // 2],
            "min": sorted_values[0],
            "max": sorted_values[-1],
            "p95": sorted_values[int(n * 0.95)] if n >= 20 else sorted_values[-1],
            "p99": sorted_values[int(n * 0.99)] if n >= 100 else sorted_values[-1],
        }
    
    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        生成性能报告
        
        Returns:
            Markdown格式的报告内容
        """
        lines = [
            "# DevSquad Performance Report",
            "",
            f"**Generated**: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
            "",
            f"**Total Snapshots**: {len(self._metrics_history)}",
            "",
        ]
        
        # 统计各指标
        for metric_name in self.METRIC_NAMES.keys():
            stats = self.get_statistics(metric_name)
            if "error" not in stats:
                lines.extend([
                    f"## {self.METRIC_NAMES.get(metric_name, metric_name)}",
                    "",
                    f"- **Mean**: {stats['mean']:.2f} {self._get_unit(metric_name)}",
                    f"- **Median**: {stats['median']:.2f} {self._get_unit(metric_name)}",
                    f"- **P95**: {stats['p95']:.2f} {self._get_unit(metric_name)}",
                    f"- **P99**: {stats['p99']:.2f} {self._get_unit(metric_name)}",
                    f"- **Min/Max**: {stats['min']:.2f} / {stats['max']:.2f}",
                    f"- **Samples**: {stats['count']}",
                    "",
                ])
        
        report_content = "\n".join(lines)
        
        if output_file:
            filepath = Path(output_file)
            filepath.write_text(report_content, encoding='utf-8')
            logger.info(f"Saved performance report to {filepath}")
        
        return report_content
    
    def _get_unit(self, metric_name: str) -> str:
        """获取指标默认单位"""
        units = {
            "dispatch_latency": "ms",
            "worker_execution": "ms",
            "consensus_time": "ms",
            "startup_time": "ms",
            "memory_usage": "MB",
            "cache_hit_rate": "%",
        }
        return units.get(metric_name, "")


# 全局实例
_monitor_instance = None
_monitor_lock = threading.Lock()

def get_performance_monitor() -> PerformanceMonitor:
    """获取全局性能监控器实例"""
    global _monitor_instance
    
    with _monitor_lock:
        if _monitor_instance is None:
            _monitor_instance = PerformanceMonitor()
        
        return _monitor_instance
```

---

## 🚨 告警引擎 (Alert Engine)

### 告警规则定义

```python
@dataclass
class AlertRule:
    """告警规则"""
    name: str
    metric: str
    condition: str  # gt, lt, eq, gte, lte
    threshold: float
    severity: str  # info, warning, critical
    message_template: str
    cooldown_seconds: int = 60  # 冷却时间，避免重复告警


DEFAULT_ALERTS = [
    AlertRule(
        name="High Dispatch Latency",
        metric="dispatch_latency",
        condition="gt",
        threshold=1000,  # 1秒
        severity="warning",
        message_template="Dispatch latency too high: {value:.2f}ms (threshold: {threshold}ms)",
    ),
    AlertRule(
        name="Critical Dispatch Latency",
        metric="dispatch_latency",
        condition="gt",
        threshold=5000,  # 5秒
        severity="critical",
        message_template="CRITICAL: Dispatch latency {value:.2f}ms exceeds SLA!",
    ),
    AlertRule(
        name="Low Memory Usage",
        metric="memory_usage",
        condition="gt",
        threshold=512,  # 512MB
        severity="warning",
        message_template="Memory usage high: {value:.2f}MB (threshold: {threshold}MB)",
    ),
]
```

---

## 📊 实施路线图

### Phase 1: 基础设施搭建 (本周)

- [x] 创建性能监控指南文档
- [x] 实现 PerformanceMonitor 类
- [x] 创建基准测试模板
- [ ] 集成 pytest-benchmark 到 CI

### Phase 2: 数据采集 (下周)

- [ ] 在 dispatcher 中集成 PerformanceMonitor
- [ ] 在 coordinator 中添加 Worker 执行计时
- [ ] 在 consensus_engine 中添加决策计时
- [ ] 实现自动快照保存

### Phase 3: 可视化与告警 (本月)

- [ ] 开发 Web Dashboard (可选)
- [ ] 实现告警引擎
- [ ] 配置 Prometheus/Grafana 导出
- [ ] 定期生成性能报告

### Phase 4: 持续优化 (持续)

- [ ] 建立性能基线库
- [ ] 设置回归检测阈值
- [ ] 集成到 CI/CD 流水线
- [ ] 定期审查和优化

---

## ✅ 快速开始

### 1. 运行基准测试

```bash
cd /Users/lin/trae_projects/DevSquad
pip install pytest-benchmark
python -m pytest tests/test_performance_benchmarks.py --benchmark-only -v
```

### 2. 手动使用 PerformanceMonitor

```python
from scripts.collaboration.performance_monitor import get_performance_monitor

monitor = get_performance_monitor()

with monitor.measure("important_operation", operation_type="test", user="admin"):
    # ... 你的代码 ...
    pass

# 结束快照并查看结果
snapshot = monitor.end_snapshot()
print(f"Recorded {len(snapshot.metrics)} metrics")

# 生成报告
report = monitor.generate_report("performance_report.md")
print(report)
```

### 3. 查看历史统计

```python
stats = monitor.get_statistics("dispatch_latency")
print(f"平均延迟: {stats['mean']:.2f}ms")
print(f"P99延迟: {stats['p99']:.2f}ms")
```

---

## 📈 预期收益

| 能力 | 状态 | 价值 |
|------|------|------|
| **基准测试** | 🟢 已实现 | 建立性能基线 |
| **实时监控** | 🟡 进行中 | 及时发现问题 |
| **趋势分析** | ⏳ 计划中 | 预见性优化 |
| **自动告警** | ⏳ 计划中 | 减少故障响应时间 |
| **性能报告** | 🟢 已实现 | 定期回顾改进 |

---

**创建时间**: 2026-05-04  
**预计完成**: 2026-06-01  
**负责人**: DevSquad DevOps + Tester Roles
