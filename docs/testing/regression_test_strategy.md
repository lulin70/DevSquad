# 回归测试策略

> ⚠️ **已过时 (HISTORICAL)** — 本文档停留在 V3.6 时代 (2026-05-17)，声称 1662 测试/92% 覆盖率。
> 当前实际: 4603+ 测试 / 80%+ 覆盖率 (V4.0.11)。当前测试计划请参阅:
> [PROJECT_STATUS.md](../PROJECT_STATUS.md) 第 3 节 + [V3.9_Test_Plan.md](../prd/V3.9_Test_Plan.md) + [P2_4_TEST_PLAN.md](../P2_4_TEST_PLAN.md)

> **文档类型**：测试计划文档
>
> **版本**：v1.1 — **历史版本，已过时**
>
> **创建日期**：2026-05-01
>
> **最后更新**：2026-05-17
>
> **负责人**：QA Engineer
>
> **状态**：已批准

---

## 一、概述

本文档定义 DevSquad v3.6.0 的回归测试策略，确保新功能（Authentication、REST API、Alerts、Historical Data Storage）不破坏 v3.5 的现有功能。

**测试目标**：
- **向后兼容性**：v3.5 代码在 v3.6.0 环境中正常运行
- **功能完整性**：v3.5 的所有功能在 v3.6.0 中保持不变
- **性能稳定性**：v3.6.0 不引入性能退化
- **模块完整性**：48个核心模块全部正常工作
- **测试覆盖**：1662+ 测试全部通过

---

## 二、回归测试范围

### 2.1 核心功能回归

| 功能模块 | v3.5 功能 | v3.6.0 变更 | 测试优先级 |
|----------|-----------|-------------|-----------|
| Auth Manager | 无 | 新增 RBAC 认证系统 | P0 |
| API Server | 无 | 新增 FastAPI REST API | P0 |
| Alert Manager | 无 | 新增多渠道告警 | P0 |
| History Manager | 无 | 新增 SQLite 时序存储 | P0 |
| Lifecycle Protocol | 11阶段工作流 | 增强门禁引擎 | P0 |
| AgentBriefing | 上下文感知简报 | 优化生成逻辑 | P1 |
| ConfidenceScore | 置信度评分 | 新增趋势分析 | P1 |
| EnhancedWorker | 增强Worker | 集成QA流程 | P1 |
| Dashboard | Streamlit仪表板 | 集成认证功能 | P1 |

### 2.2 兼容性测试矩阵

| 测试场景 | v3.4 代码 | v3.5 环境 | 预期结果 |
|----------|-----------|-----------|----------|
| 使用 LLMCache（旧 API） | ✅ | ✅ | 正常运行 |
| 使用 LLMRetry（旧 API） | ✅ | ✅ | 正常运行 |
| 使用 PerformanceMonitor（旧 API） | ✅ | ✅ | 正常运行 |
| Agent 不传 Provider 参数 | ✅ | ✅ | 自动使用 Null Provider |
| 编排器使用完整历史模式 | ✅ | ✅ | 正常运行 |

---

## 三、回归测试套件

### 3.1 单元测试回归

**目标**：确保所有 v3.4 的单元测试在 v3.5 中通过。

**测试清单**：
- [ ] `tests/test_llm_cache.py`：所有测试通过
- [ ] `tests/test_llm_retry.py`：所有测试通过
- [ ] `tests/test_performance_monitor.py`：所有测试通过
- [ ] `tests/test_agent_base.py`：所有测试通过
- [ ] `tests/test_orchestrator.py`：所有测试通过

**执行命令**：
```bash
pytest tests/ -v --cov=scripts --cov-report=html
```

**验收标准**：
- 所有测试通过（100%）
- 测试覆盖率 ≥ 92%（v3.4 基线）

---

### 3.2 集成测试回归

**目标**：确保多模块协作功能正常。

**测试场景**：

#### T1：完整工作流测试
```python
def test_full_workflow_v34_compatibility():
    """测试 v3.4 风格的完整工作流"""
    # 使用 v3.4 API
    cache = LLMCache()
    retry = LLMRetry()
    monitor = PerformanceMonitor()
    
    # 创建 Agent（v3.4 风格）
    architect = ArchitectAgent(cache=cache, retry=retry, monitor=monitor)
    pm = PMAgent(cache=cache, retry=retry, monitor=monitor)
    
    # 执行工作流
    orchestrator = Orchestrator([architect, pm])
    result = orchestrator.execute("Design REST API")
    
    # 验证
    assert result.status == "COMPLETED"
    assert len(result.agent_results) == 2
```

#### T2：缓存功能测试
```python
def test_cache_backward_compatibility():
    """测试缓存向后兼容性"""
    cache = LLMCache()
    
    # v3.4 API
    cache.set("key1", "value1")
    assert cache.get("key1") == "value1"
    
    # v3.5 API（应该也能工作）
    assert cache.is_available() == True
    assert cache.version() == "1.0.0"
```

#### T3：重试功能测试
```python
def test_retry_backward_compatibility():
    """测试重试向后兼容性"""
    retry = LLMRetry()
    
    # v3.4 API
    def flaky_function():
        if random.random() < 0.5:
            raise TimeoutError()
        return "success"
    
    result = retry.retry_with_fallback(flaky_function)
    assert result == "success"
```

---

### 3.3 性能回归测试

**目标**：确保 v3.5 不引入性能退化。

**基准测试**（v3.4）：

| 指标 | v3.4 基线 | v3.5 目标 | 容忍度 |
|------|-----------|-----------|--------|
| Agent 执行时间 | 2.5s | ≤ 2.75s | +10% |
| 缓存读取延迟 | 5ms | ≤ 5.5ms | +10% |
| 缓存写入延迟 | 10ms | ≤ 11ms | +10% |
| 内存占用 | 150MB | ≤ 165MB | +10% |
| 测试套件执行时间 | 60s | ≤ 66s | +10% |

**测试脚本**：
```python
import time
import psutil
import pytest

def test_agent_execution_performance():
    """测试 Agent 执行性能"""
    agent = ArchitectAgent()
    
    start = time.time()
    result = agent.execute("Simple task")
    duration = time.time() - start
    
    # 不应超过 v3.4 基线的 110%
    assert duration <= 2.75, f"Performance regression: {duration}s > 2.75s"

def test_cache_read_performance():
    """测试缓存读取性能"""
    cache = LLMCache()
    cache.set("key", "value")
    
    start = time.time()
    for _ in range(1000):
        cache.get("key")
    duration = (time.time() - start) / 1000
    
    assert duration <= 0.0055, f"Cache read regression: {duration*1000}ms > 5.5ms"

def test_memory_usage():
    """测试内存占用"""
    process = psutil.Process()
    baseline = process.memory_info().rss / 1024 / 1024  # MB
    
    # 执行典型工作负载
    orchestrator = Orchestrator([...])
    orchestrator.execute("Complex task")
    
    current = process.memory_info().rss / 1024 / 1024
    increase = current - baseline
    
    assert increase <= 165, f"Memory regression: {increase}MB > 165MB"
```

---

## 四、兼容性测试

### 4.1 API 兼容性测试

**目标**：确保 v3.4 的 API 在 v3.5 中仍然可用。

**测试清单**：

#### LLMCache API
```python
def test_llm_cache_api_compatibility():
    """测试 LLMCache API 兼容性"""
    cache = LLMCache()
    
    # v3.4 API（必须保留）
    assert hasattr(cache, 'get')
    assert hasattr(cache, 'set')
    assert hasattr(cache, 'clear')
    
    # v3.5 新增 API（可选）
    assert hasattr(cache, 'version')
    assert hasattr(cache, 'is_available')
```

#### LLMRetry API
```python
def test_llm_retry_api_compatibility():
    """测试 LLMRetry API 兼容性"""
    retry = LLMRetry()
    
    # v3.4 API
    assert hasattr(retry, 'retry_with_fallback')
    assert hasattr(retry, 'get_stats')
    
    # v3.5 新增 API
    assert hasattr(retry, 'version')
    assert hasattr(cache, 'is_available')
```

### 4.2 配置兼容性测试

**目标**：确保 v3.4 的配置文件在 v3.5 中仍然有效。

**测试场景**：
```python
def test_config_backward_compatibility():
    """测试配置文件向后兼容性"""
    # 加载 v3.4 配置文件
    config = load_config("config/v3.4_config.yaml")
    
    # 应该能正常解析
    assert config['llm']['model'] == 'gpt-4'
    assert config['cache']['enabled'] == True
    
    # v3.5 新增字段应该有默认值
    assert config.get('providers', {}).get('cache', {}).get('type') == 'memory'
```

---

## 五、测试执行计划

### 5.1 测试阶段

| 阶段 | 时间 | 测试内容 | 负责人 |
|------|------|----------|--------|
| Phase 1 | Week 1-2 | 单元测试回归 | QA |
| Phase 2 | Week 3-4 | 集成测试回归 | QA |
| Phase 3 | Week 5-6 | 性能回归测试 | QA |
| Phase 4 | Week 7-8 | 兼容性测试 | QA |

### 5.2 测试环境

| 环境 | Python 版本 | 依赖版本 | 用途 |
|------|-------------|----------|------|
| v3.4 基线 | 3.9, 3.10, 3.11 | requirements.txt (v3.4) | 基准测试 |
| v3.5 测试 | 3.9, 3.10, 3.11 | requirements.txt (v3.5) | 回归测试 |

---

## 六、缺陷管理

### 6.1 缺陷分类

| 严重程度 | 定义 | 处理策略 |
|----------|------|----------|
| P0 - 阻塞 | v3.4 功能完全不可用 | 立即修复，阻塞发布 |
| P1 - 严重 | v3.4 功能部分不可用 | 1 周内修复 |
| P2 - 一般 | 性能退化 > 10% | 2 周内修复 |
| P3 - 轻微 | 文档不一致 | 发布前修复 |

### 6.2 缺陷跟踪

**缺陷报告模板**：
```markdown
## 缺陷描述
[简要描述问题]

## 复现步骤
1. [步骤 1]
2. [步骤 2]
3. [步骤 3]

## 预期行为
[v3.4 的行为]

## 实际行为
[v3.5 的行为]

## 环境信息
- Python 版本：3.10
- DevSquad 版本：v3.5
- 操作系统：macOS

## 严重程度
P0 / P1 / P2 / P3
```

---

## 七、CI/CD 集成

### 7.1 自动化回归测试

**GitHub Actions 配置**：
```yaml
name: Regression Tests

on:
  pull_request:
    branches: [main, develop]
  push:
    branches: [main]

jobs:
  regression:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: [3.9, "3.10", "3.11"]
    
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          pip install -r requirements-dev.txt
      
      - name: Run regression tests
        run: |
          pytest tests/ -v --cov=scripts --cov-report=xml
      
      - name: Check coverage
        run: |
          coverage report --fail-under=92
      
      - name: Performance regression check
        run: |
          python scripts/test_performance_regression.py
```

### 7.2 性能回归检测

**自动化脚本**：
```python
#!/usr/bin/env python3
"""性能回归检测脚本"""

import json
import sys

def check_performance_regression():
    """检查性能回归"""
    # 加载 v3.4 基线
    with open("benchmarks/v3.4_baseline.json") as f:
        baseline = json.load(f)
    
    # 运行 v3.5 性能测试
    current = run_performance_tests()
    
    # 对比
    regressions = []
    for metric, baseline_value in baseline.items():
        current_value = current[metric]
        increase = (current_value - baseline_value) / baseline_value
        
        if increase > 0.1:  # 超过 10%
            regressions.append({
                "metric": metric,
                "baseline": baseline_value,
                "current": current_value,
                "increase": f"{increase:.1%}"
            })
    
    if regressions:
        print("❌ Performance regressions detected:")
        for r in regressions:
            print(f"  - {r['metric']}: {r['baseline']} → {r['current']} (+{r['increase']})")
        sys.exit(1)
    else:
        print("✅ No performance regressions detected")
        sys.exit(0)

if __name__ == "__main__":
    check_performance_regression()
```

---

## 八、验收标准

### 8.1 回归测试通过标准

- ✅ 所有单元测试通过（100%）
- ✅ 所有集成测试通过（100%）
- ✅ 测试覆盖率 ≥ 92%
- ✅ 性能退化 ≤ 10%
- ✅ 无 P0/P1 缺陷
- ✅ v3.4 配置文件兼容

### 8.2 发布检查清单

- [ ] 单元测试回归通过
- [ ] 集成测试回归通过
- [ ] 性能回归测试通过
- [ ] API 兼容性测试通过
- [ ] 配置兼容性测试通过
- [ ] 所有 P0/P1 缺陷已修复
- [ ] 回归测试报告已生成
- [ ] 迁移指南已更新

---

## 九、附录

### 9.1 测试工具

- **pytest**：单元测试和集成测试
- **pytest-cov**：测试覆盖率
- **pytest-benchmark**：性能基准测试
- **psutil**：内存和 CPU 监控

### 9.2 参考文档

- PRD：`docs/prd/protocol_interface_system_prd.md`
- Protocol 接口规范：`docs/architecture/protocol_interfaces_spec.md`
- v3.4 测试报告：`docs/testing/v3.4_test_report.md`

---

**文档生成时间**：2026-05-01
**作者**：QA Engineer
**版本**：v1.0
