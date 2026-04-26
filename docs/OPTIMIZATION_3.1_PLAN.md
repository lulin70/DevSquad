# 优化 3.1: 功能使用监控实施计划

**创建日期**: 2026-04-26  
**负责人**: Arch  
**优先级**: 🟠 P1  
**预计工时**: 4小时  
**状态**: 📋 计划中

---

## 目标

实现轻量级的功能使用统计系统，为后续优化决策提供数据支持。避免误删有用功能，确保优化工作基于真实使用数据。

---

## 背景

当前 DevSquad 项目包含多个组件和功能，但缺乏使用数据：
- 不清楚哪些功能被频繁使用
- 不清楚哪些功能从未被使用
- 优化决策缺乏数据支持
- 可能误删有用功能

**解决方案**: 实现简单的使用统计追踪系统

---

## 设计方案

### 1. UsageTracker 类设计

```python
# scripts/collaboration/usage_tracker.py

import json
import threading
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional
from collections import defaultdict


class UsageTracker:
    """轻量级功能使用追踪器"""
    
    def __init__(self, persist_file: Optional[str] = None):
        self.stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            "count": 0,
            "first_used": None,
            "last_used": None,
            "errors": 0,
        })
        self.persist_file = persist_file or ".usage_stats.json"
        self._lock = threading.RLock()
        self._load_stats()
    
    def track(self, feature_name: str, success: bool = True, metadata: Optional[Dict] = None):
        """追踪功能使用"""
        with self._lock:
            stat = self.stats[feature_name]
            stat["count"] += 1
            
            now = datetime.now().isoformat()
            if stat["first_used"] is None:
                stat["first_used"] = now
            stat["last_used"] = now
            
            if not success:
                stat["errors"] += 1
            
            if metadata:
                if "metadata" not in stat:
                    stat["metadata"] = []
                stat["metadata"].append(metadata)
                # 只保留最近 10 条
                stat["metadata"] = stat["metadata"][-10:]
    
    def get_stats(self, feature_name: Optional[str] = None) -> Dict:
        """获取统计数据"""
        with self._lock:
            if feature_name:
                return dict(self.stats.get(feature_name, {}))
            return {k: dict(v) for k, v in self.stats.items()}
    
    def get_top_features(self, limit: int = 10) -> list:
        """获取使用最多的功能"""
        with self._lock:
            sorted_features = sorted(
                self.stats.items(),
                key=lambda x: x[1]["count"],
                reverse=True
            )
            return [(name, stats["count"]) for name, stats in sorted_features[:limit]]
    
    def get_unused_features(self, all_features: list) -> list:
        """获取从未使用的功能"""
        with self._lock:
            used = set(self.stats.keys())
            return [f for f in all_features if f not in used]
    
    def generate_report(self) -> str:
        """生成使用报告"""
        with self._lock:
            total_calls = sum(s["count"] for s in self.stats.values())
            total_errors = sum(s["errors"] for s in self.stats.values())
            
            lines = [
                "# DevSquad 功能使用报告",
                f"\n**生成时间**: {datetime.now().isoformat()}",
                f"**追踪功能数**: {len(self.stats)}",
                f"**总调用次数**: {total_calls}",
                f"**总错误次数**: {total_errors}",
                f"**错误率**: {(total_errors/max(1,total_calls)*100):.2f}%",
                "\n## Top 10 最常用功能\n",
            ]
            
            for name, count in self.get_top_features(10):
                stat = self.stats[name]
                error_rate = (stat["errors"] / max(1, stat["count"])) * 100
                lines.append(f"- **{name}**: {count} 次调用, 错误率 {error_rate:.1f}%")
            
            # 按类别分组
            lines.append("\n## 按组件分类\n")
            by_component = defaultdict(int)
            for name, stat in self.stats.items():
                component = name.split(".")[0] if "." in name else "other"
                by_component[component] += stat["count"]
            
            for component, count in sorted(by_component.items(), key=lambda x: x[1], reverse=True):
                lines.append(f"- **{component}**: {count} 次调用")
            
            return "\n".join(lines)
    
    def save(self):
        """保存统计数据到文件"""
        with self._lock:
            try:
                with open(self.persist_file, 'w', encoding='utf-8') as f:
                    json.dump(dict(self.stats), f, indent=2, ensure_ascii=False)
            except Exception as e:
                print(f"Failed to save usage stats: {e}")
    
    def _load_stats(self):
        """从文件加载统计数据"""
        try:
            if Path(self.persist_file).exists():
                with open(self.persist_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    self.stats.update(loaded)
        except Exception as e:
            print(f"Failed to load usage stats: {e}")


# 全局单例
_global_tracker: Optional[UsageTracker] = None


def get_tracker() -> UsageTracker:
    """获取全局追踪器实例"""
    global _global_tracker
    if _global_tracker is None:
        _global_tracker = UsageTracker()
    return _global_tracker


def track_usage(feature_name: str, success: bool = True, metadata: Optional[Dict] = None):
    """便捷函数：追踪功能使用"""
    get_tracker().track(feature_name, success, metadata)
```

### 2. 集成点

需要在以下组件中集成使用追踪：

#### 2.1 Dispatcher
```python
# scripts/collaboration/dispatcher.py

from .usage_tracker import track_usage

class MultiAgentDispatcher:
    def dispatch(self, task: str, **kwargs):
        track_usage("dispatcher.dispatch")
        # ... 原有代码
        
    def analyze_task(self, task: str):
        track_usage("dispatcher.analyze_task")
        # ... 原有代码
```

#### 2.2 Coordinator
```python
# scripts/collaboration/coordinator.py

from .usage_tracker import track_usage

class Coordinator:
    def coordinate(self, task: str, roles: list):
        track_usage("coordinator.coordinate", metadata={"roles": roles})
        # ... 原有代码
```

#### 2.3 Worker
```python
# scripts/collaboration/worker.py

from .usage_tracker import track_usage

class Worker:
    def execute(self, task: str):
        track_usage(f"worker.{self.role}.execute")
        try:
            # ... 原有代码
            track_usage(f"worker.{self.role}.execute", success=True)
        except Exception as e:
            track_usage(f"worker.{self.role}.execute", success=False)
            raise
```

#### 2.4 可选组件
```python
# 各个可选组件

# WarmupManager
track_usage("warmup.execute")

# ContextCompressor
track_usage(f"compressor.level{level}")

# PermissionGuard
track_usage("permission.check")

# MemoryBridge
track_usage("memory.store")
track_usage("memory.retrieve")

# Skillifier
track_usage("skillify.propose")
```

### 3. 报告生成脚本

```python
# scripts/generate_usage_report.py

#!/usr/bin/env python3
"""生成功能使用报告"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.collaboration.usage_tracker import get_tracker


def main():
    tracker = get_tracker()
    
    # 生成报告
    report = tracker.generate_report()
    
    # 保存到文件
    output_file = "docs/USAGE_REPORT.md"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"✅ 使用报告已生成: {output_file}")
    print(f"\n{report}")
    
    # 保存统计数据
    tracker.save()


if __name__ == "__main__":
    main()
```

---

## 实施步骤

### Phase 1: 实现 UsageTracker (1h)

1. 创建 `scripts/collaboration/usage_tracker.py`
2. 实现 UsageTracker 类
3. 编写单元测试
4. 验证基本功能

**验收标准**:
- UsageTracker 类功能完整
- 单元测试通过
- 可以追踪、查询、生成报告

### Phase 2: 集成到核心组件 (2h)

1. 在 Dispatcher 中集成
2. 在 Coordinator 中集成
3. 在 Worker 中集成
4. 在 Scratchpad 中集成

**验收标准**:
- 所有核心组件都有使用追踪
- 不影响原有功能
- 所有测试通过

### Phase 3: 集成到可选组件 (0.5h)

1. WarmupManager
2. ContextCompressor
3. PermissionGuard
4. MemoryBridge
5. Skillifier

**验收标准**:
- 可选组件都有使用追踪
- 追踪代码不影响性能

### Phase 4: 报告生成和文档 (0.5h)

1. 创建报告生成脚本
2. 编写使用文档
3. 更新 README

**验收标准**:
- 可以生成清晰的使用报告
- 文档完整

---

## 追踪的功能列表

### 核心功能
- `dispatcher.dispatch`
- `dispatcher.analyze_task`
- `dispatcher.match_roles`
- `coordinator.coordinate`
- `coordinator.consensus`
- `worker.{role}.execute`
- `scratchpad.update`
- `scratchpad.query`

### 可选功能
- `warmup.execute`
- `compressor.level1` (SNIP)
- `compressor.level2` (SessionMemory)
- `compressor.level3` (FullCompact)
- `permission.check`
- `memory.store`
- `memory.retrieve`
- `skillify.propose`
- `quality_guard.check`

---

## 性能考虑

### 1. 最小化开销
- 使用简单的字典计数
- 异步持久化（可选）
- 不影响主流程性能

### 2. 内存控制
- 只保留最近 10 条 metadata
- 定期清理旧数据
- 文件大小限制

### 3. 线程安全
- 使用 RLock 保护共享数据
- 原子操作

---

## 数据收集计划

### 收集周期
- **Week 1**: 收集基础数据
- **Week 2**: 分析使用模式
- **Week 3**: 生成优化建议

### 数据分析
1. 识别零使用功能（候选删除）
2. 识别低使用功能（候选简化）
3. 识别高使用功能（保持/优化）
4. 识别高错误率功能（需要修复）

---

## 预期成果

### 1. 使用报告示例

```markdown
# DevSquad 功能使用报告

**生成时间**: 2026-05-03T10:00:00
**追踪功能数**: 25
**总调用次数**: 1,234
**总错误次数**: 12
**错误率**: 0.97%

## Top 10 最常用功能

- **dispatcher.dispatch**: 456 次调用, 错误率 0.2%
- **worker.solo-coder.execute**: 234 次调用, 错误率 1.3%
- **coordinator.coordinate**: 123 次调用, 错误率 0.8%
- **scratchpad.update**: 98 次调用, 错误率 0.0%
- **worker.architect.execute**: 87 次调用, 错误率 2.3%
- **compressor.level1**: 45 次调用, 错误率 0.0%
- **memory.store**: 34 次调用, 错误率 0.0%
- **permission.check**: 23 次调用, 错误率 0.0%
- **skillify.propose**: 2 次调用, 错误率 0.0%
- **compressor.level3**: 0 次调用, 错误率 N/A

## 按组件分类

- **dispatcher**: 579 次调用
- **worker**: 321 次调用
- **coordinator**: 123 次调用
- **scratchpad**: 98 次调用
- **compressor**: 45 次调用
- **memory**: 34 次调用
- **permission**: 23 次调用
- **skillify**: 2 次调用
```

### 2. 优化决策依据

基于报告数据：
- **Skillifier**: 使用率 <1% → 候选移除
- **FullCompact**: 使用率 0% → 候选移除
- **Dispatcher**: 使用率 47% → 保持并优化
- **Worker**: 使用率 26% → 保持

---

## 测试计划

### 单元测试

```python
# tests/test_usage_tracker.py

def test_track_usage():
    tracker = UsageTracker(persist_file=":memory:")
    tracker.track("test.feature")
    stats = tracker.get_stats("test.feature")
    assert stats["count"] == 1

def test_track_error():
    tracker = UsageTracker(persist_file=":memory:")
    tracker.track("test.feature", success=False)
    stats = tracker.get_stats("test.feature")
    assert stats["errors"] == 1

def test_get_top_features():
    tracker = UsageTracker(persist_file=":memory:")
    tracker.track("feature1")
    tracker.track("feature1")
    tracker.track("feature2")
    top = tracker.get_top_features(2)
    assert top[0][0] == "feature1"
    assert top[0][1] == 2

def test_generate_report():
    tracker = UsageTracker(persist_file=":memory:")
    tracker.track("test.feature")
    report = tracker.generate_report()
    assert "功能使用报告" in report
    assert "test.feature" in report
```

### 集成测试

```python
# tests/test_usage_integration.py

def test_dispatcher_tracking():
    disp = MultiAgentDispatcher()
    disp.dispatch("测试任务")
    
    tracker = get_tracker()
    stats = tracker.get_stats("dispatcher.dispatch")
    assert stats["count"] >= 1
```

---

## 风险和缓解

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|---------|
| 性能开销 | 中 | 低 | 使用简单计数，异步持久化 |
| 数据不准确 | 中 | 中 | 多点验证，交叉检查 |
| 隐私问题 | 低 | 低 | 不记录敏感数据，只记录功能名 |
| 存储空间 | 低 | 低 | 限制 metadata 数量，定期清理 |

---

## 后续工作

完成优化 3.1 后：
1. 收集 1-2 周的使用数据
2. 分析数据，生成优化建议
3. 启动优化 1.2（移除未使用功能）
4. 基于数据优化高使用功能

---

## 参考资料

- [OPTIMIZATION_PLAN_KARPATHY.md](OPTIMIZATION_PLAN_KARPATHY.md)
- [OPTIMIZATION_PROGRESS.md](OPTIMIZATION_PROGRESS.md)
- Python logging best practices
- Telemetry design patterns

---

**文档版本**: 1.0  
**最后更新**: 2026-04-26  
**状态**: 📋 待审核
