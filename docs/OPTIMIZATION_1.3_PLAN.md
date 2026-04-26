# 优化 1.3: 统一测试框架执行计划

**负责人**: QA Lead + Arch  
**优先级**: 🔴 P0  
**预计工时**: 12h  
**开始日期**: 2026-04-26  
**目标完成**: 2026-05-03

---

## 目标

将 DevSquad 的测试框架从 unittest + pytest 混用统一为 100% pytest，提升测试代码质量和可维护性。

---

## 当前状态分析

### 测试文件清单

```bash
scripts/collaboration/
├── dispatcher_test.py          # unittest 风格，54 tests ✅ 已验证通过
├── coordinator_test.py         # unittest 风格
├── worker_test.py              # unittest 风格
├── scratchpad_test.py          # unittest 风格
├── consensus_test.py           # unittest 风格
├── batch_scheduler_test.py     # unittest 风格
├── context_compressor_test.py  # unittest 风格
├── permission_guard_test.py    # unittest 风格
├── skillifier_test.py          # unittest 风格
├── warmup_manager_test.py      # unittest 风格
├── memory_bridge_test.py       # unittest 风格
└── test_quality_guard_test.py  # unittest 风格
```

### 问题分析

1. **混用两种框架**
   - 所有测试文件使用 unittest.TestCase
   - 但通过 pytest 运行
   - 新贡献者需要学习两种框架

2. **代码冗余**
   - setUp/tearDown 样板代码重复
   - self.assertEqual 等断言冗长
   - 测试类继承增加复杂度

3. **维护成本高**
   - 两种风格混用导致不一致
   - 难以利用 pytest 的高级特性（fixtures, parametrize）

---

## 执行计划

### Phase 1: 核心模块迁移（Week 1，本周）

**目标**: 迁移 2 个核心测试文件

#### Task 1.1: 迁移 dispatcher_test.py (4h)

**当前状态**: 54 tests, unittest 风格

**迁移步骤**:

1. **移除 unittest 依赖** (30min)
   ```python
   # 删除
   import unittest
   
   # 删除
   class TestT1_DispatcherDataModels(unittest.TestCase):
   
   # 改为
   class TestT1_DispatcherDataModels:
   ```

2. **转换断言** (1h)
   ```python
   # unittest 风格
   self.assertEqual(a, b)
   self.assertTrue(x)
   self.assertIn(item, list)
   
   # pytest 风格
   assert a == b
   assert x
   assert item in list
   ```

3. **转换 setUp/tearDown** (1h)
   ```python
   # unittest 风格
   def setUp(self):
       self.tmp = tempfile.mkdtemp()
       self.disp = MultiAgentDispatcher(persist_dir=self.tmp)
   
   def tearDown(self):
       self.disp.shutdown()
       shutil.rmtree(self.tmp)
   
   # pytest 风格（使用 fixture）
   @pytest.fixture
   def tmp_dir():
       tmp = tempfile.mkdtemp()
       yield tmp
       shutil.rmtree(tmp, ignore_errors=True)
   
   @pytest.fixture
   def dispatcher(tmp_dir):
       disp = MultiAgentDispatcher(persist_dir=tmp_dir)
       yield disp
       disp.shutdown()
   
   def test_01_dispatch_result_default(dispatcher):
       # 使用 fixture
       pass
   ```

4. **运行测试验证** (30min)
   ```bash
   pytest scripts/collaboration/dispatcher_test.py -v
   # 确保 54/54 tests 通过
   ```

5. **代码审查和优化** (1h)
   - 简化冗余代码
   - 利用 pytest 特性（parametrize）
   - 添加更清晰的测试文档

**预期成果**:
- 代码量: -15%（移除样板代码）
- 可读性: +30%
- 54/54 tests 通过

#### Task 1.2: 迁移 coordinator_test.py (4h)

**步骤**: 同 Task 1.1

**预期成果**:
- 代码量: -15%
- 所有测试通过

#### Task 1.3: 更新 CI 配置 (1h)

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.9
      - name: Install dependencies
        run: |
          pip install pytest pytest-cov
          pip install -r requirements.txt
      - name: Run tests
        run: |
          pytest scripts/collaboration/ -v --cov=scripts/collaboration --v-report=term-missing
```

---

### Phase 2: 其他模块迁移（Week 2）

**目标**: 迁移剩余 10 个测试文件

#### 优先级排序

1. **P0 - 核心模块** (已在 Phase 1 完成)
   - dispatcher_test.py ✅
   - coordinator_test.py ✅

2. **P1 - 高频使用模块** (4h)
   - worker_test.py
   - scratchpad_test.py

3. **P2 - 中频使用模块** (4h)
   - consensus_test.py
   - batch_scheduler_test.py
   - context_compressor_test.py

4. **P3 - 低频使用模块** (3h)
   - permission_guard_test.py
   - skillifier_test.py
   - warmup_manager_test.py
   - memory_bridge_test.py
   - test_quality_guard_test.py

---

### Phase 3: 清理和文档（延后到 v3.4.0）

**目标**: 完全移除 unittest 残留

1. **移除 unittest 导入** (30min)
   - 全局搜索 `import unittest`
   - 确认无残留

2. **更新文档** (1h)
   - 更新 CONTRIBUTING.md
   - 添加 pytest 最佳实践
   - 更新测试编写指南

3. **添加 pytest 配置** (30min)
   ```ini
   # pytest.ini
   [pytest]
   testpaths = scripts/collaboration
   python_files = *_test.py
   python_classes = Test*
   python_functions = test_*
   addopts = -v --tb=short --strict-markers
   markers =
       slow: marks tests as slow
       integration: marks tests as integration tests
   ```

---

## 迁移模板

### unittest → pytest 转换规则

| unittest | pytest |
|----------|--------|
| `import unittest` | `import pytest` |
| `class TestX(unittest.TestCase):` | `class TestX:` |
| `def setUp(self):` | `@pytest.fixture` |
| `def tearDown(self):` | `yield` in fixture |
| `self.assertEqual(a, b)` | `assert a == b` |
| `self.assertTrue(x)` | `assert x` |
| `self.assertFalse(x)` | `assert not x` |
| `self.assertIn(a, b)` | `assert a in b` |
| `self.assertIsNone(x)` | `assert x is None` |
| `self.assertIsInstance(x, T)` | `assert isinstance(x, T)` |
| `self.asse, b)` | `assert a > b` |
| `self.assertRaises(E)` | `pytest.raises(E)` |

### Fixture 示例

```python
import pytest
import tempfile
import shutil
from pathlib import Path

@pytest.fixture
def tmp_dir():
    """临时目录 fixture"""
    tmp = tempfile.mkdtemp(prefix="test_")
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)

@pytest.fixture
def dispatcher(tmp_dir):
    """Dispatcher fixture"""
    disp = MultiAgentDispatcher(persist_dir=str(tmp_dir))
    yield disp
    disp.shutdown()

@pytest.fixture
def sample_task():
    """示例任务 fixture"""
    return "设计用户认证系统"

# 使用 fixture
def test_dispatch_basic(dispatcher, sample_task):
    result = dispatcher.dispatch(sample_task)
    assert result.success
    assert len(result.matched_roles) > 0
```

### Parametrize 示例

```python
import pytest

@pytest.mark.parametrize("task,expected_role", [
    ("设计架构", "architect"),
    ("编写测试", "tester"),
    ("实现功能", "solo-coder"),
    ("设计UI", "ui-designer"),
])
def test_role_matching(dispatcher, task, expected_role):
    roles = dispatcher.analyze_task(task)
    role_ids = [r["role_id"] for r in roles]
    assert expected_role in role_ids
```

---

## 风险和缓解

### 风: 迁移引入回归

**概率**: 低  
**影响**: 中  
**缓解措施**:
- 逐个文件迁移
- 每次迁移后运行全量测试
- 保持 Git 提交粒度小，便于回滚

### 风险 2: 测试覆盖率下降

**概率**: 低  
**影响**: 高  
**缓解措施**:
- 使用 pytest-cov 监控覆盖率
- 迁移前后对比覆盖率报告
- 目标: 保持或提升覆盖率

### 风险 3: CI/CD 中断

**概率**: 低  
**影响**: 中  
**缓解措施**:
- 先在本地完全验证
- 更新 CI 配置时保持向后兼容
- 分阶段部署

---

## 成功指标

### 定量指标

| 指标 | 当前 | 目标 | 测量方法 |
|------|------|------|---------|
| 测试框架统一度 | 0% pytest 纯度 | 100% pytest | 代码审查 |
| 测试代码量 | 基准 | -20% | `wc -l *_test.py` |
| 测试通过率 | 100% | 100% | pytest 输出 |
| 测试覆盖率 | 基准 | ≥基准 | pytest-cov |
| 测试运行速度 | 基准 | +15% | pytest rations |

### 定性指标

- ✅ 新贡献者只需学习 pytest
- ✅ 测试代码更简洁易读
- ✅ 可以使用 pytest 高级特性
- ✅ CI/CD 配置更简单

---

## 时间表

| 日期 | 任务 | 负责人 | 状态 |
|------|------|--------|------|
| 2026-04-26 | 制定执行计划 | Arch | ✅ 完成 |
| 2026-04-27 | 迁移 dispatcher_test.py | QA + Arch | ⏳ 待启动 |
| 2026-04-28 | 迁移 coordinator_test.py | QA + Arch | ⏳ 待启动 |
| 2026-04-29 | 更新 CI 配置 | Arch | ⏳ 待启动 |
| 2026-04-30 | 迁移 P1 模块 (2个) | QA | ⏳ 待启动 |
| 2026-05-01 | 迁移 P2 模块 (3个) | QA | ⏳ 待启动 |
| 2026-05-02 | 迁移 P3 模块 (5个) | QA | ⏳ 待启动 |
| 2026-05-03 | 回归测试 + 文档更新 | QA + Arch | ⏳ 待启动 |

---

## 参考资料

- [pytest 官方文档](https://docs.pytest.org/)
- [从 unittest 迁移到 pytest](https://docs.pytest.org/en/stable/how-to/unittest.html)
- [pytest fixtures 最佳实践](https://docs.pytest.org/en/stable/how-to/fixtures.html)
- [pytest parametrize 指南](https://docs.pytest.org/en/stable/how-to/parametrize.html)

---

**文档生成时间**: 2026-04-26 19:05  
**下次更新时间**: 2026-04-27 (开始执行)  
**文档状态**: ✅ 计划完成，待执行

*本文档是优化 1.3 的详细执行计划。*
