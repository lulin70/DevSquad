# DevSquad V3.5.0-C 使用指南 (Plan C Layered Architecture)

## 📖 目录

1. [快速开始](#快速开始)
2. [核心概念](#核心概念)
3. [三种生命周期模式](#三种生命周期模式)
4. [API 参考](#api-参考)
5. [使用场景](#使用场景)
6. [最佳实践](#最佳实践)
7. [故障排除](#故障排除)

---

## 快速开始

### 最简单的用法

```python
from scripts.collaboration.lifecycle_protocol import create_lifecycle_protocol, LifecycleMode

# 创建适配器 (SHORTCUT模式 - 默认)
protocol = create_lifecycle_protocol()

# 查看CLI命令映射到哪些阶段
phases = protocol.resolve_command_to_phases("build")
for p in phases:
    print(f"{p.phase_id}: {p.name}")

# 推进到下一阶段
result = protocol.advance_to_phase("P8")
if result.success:
    protocol.complete_phase("P8")

# 查看进度
status = protocol.get_status()
print(f"Progress: {status.progress_percent:.1f}%")
```

### 完整11阶段流程

```python
from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter

adapter = FullLifecycleAdapter(use_unified_gate=True)
adapter.set_task_id("my-project")

# 自动推进
for _ in range(11):
    result = adapter.auto_advance()
    if result.success:
        adapter.complete_phase(result.phase_id)
        print(f"✅ Completed {result.phase_id}")
    else:
        print(f"⚠️ Stopped: {result.error}")
        break

# 保存状态以便恢复
adapter.save_state()

# ... 之后可以恢复 ...
adapter.restore_state()
```

---

## 核心概念

### 分层架构 (Plan C)

```
┌─────────────────────────────────────┐
│      View Layer (CLI 6 Commands)     │
│  spec │ plan │ build │ test │ review │ ship
└──────────────────┬──────────────────┘
                   │ View Mapping
                   ▼
┌─────────────────────────────────────┐
│     LifecycleProtocol Interface       │
│  SHORTCUT / FULL / CUSTOM modes      │
└──────────────────┬──────────────────┘
                   │
     ┌─────────────┼─────────────┐
     ▼             ▼             ▼
┌─────────┐ ┌──────────┐ ┌──────────────┐
│ Unified │ │ Shortcut │ │CheckpointMgr │
│ GateEngine│Lifecycle │ │(State Persist)│
│         │ │ Adapter  │ │              │
└────┬────┘ └────┬─────┘ └──────┬───────┘
     │           │              │
     ▼           ▼              ▼
 Verification  11-Phase       JSON State
   Gate         Workflow      Files (.json)
```

### 11个阶段

| ID | 名称 | 角色 | 描述 | 必需 |
|----|------|------|------|------|
| P1 | Requirements | PM | 需求分析 | ✅ |
| P2 | Architecture | Architect | 架构设计 | ✅ |
| P3 | Technical Design | Architect | 技术设计 | ✅ |
| P4 | Data Design | Architect | 数据设计 | ⚪ |
| P5 | UI/UX Design | UI Designer | 界面设计 | ⚪ |
| P6 | Security Design | Security Engineer | 安全设计 | ⚪ |
| P7 | Test Planning | Tester | 测试规划 | ✅ |
| P8 | Implementation | Coder | 编码实现 | ✅ |
| P9 | Testing & Validation | Tester | 测试验证 | ✅ |
| P10 | Deployment | DevOps | 部署上线 | ✅ |
| P11 | Operations & Monitoring | DevOps | 运维监控 | ⚪ |

---

## 三种生命周期模式

### 1. SHORTCUT 模式 (默认)

**适用**: 快速任务、简单工作流、CLI用户

```python
from scripts.collaboration.lifecycle_protocol import (
    create_lifecycle_protocol,
    LifecycleMode,
    VIEW_MAPPINGS,
)

adapter = create_lifecycle_protocol(LifecycleMode.SHORTCUT)

# CLI命令 → 11阶段映射
for cmd in ["spec", "build", "test"]:
    phases = adapter.resolve_command_to_phases(cmd)
    print(f"{cmd} → {[p.phase_id for p in phases]}")
```

**特点**:
- ✅ 6个简单命令
- ✅ 自动映射到11阶段子集
- ✅ 快速上手
- ❌ 不能访问所有阶段细节

### 2. FULL 模式

**适用**: 复杂项目、完整生命周期、需要依赖管理

```python
from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter

adapter = FullLifecycleAdapter(
    use_unified_gate=True,  # 启用统一门禁
)

# 完整的11阶段控制
adapter.set_skip_optional(True)  # 跳过可选阶段

# 带依赖检查的阶段推进
result = adapter.advance_to_phase("P8")  # 需要先完成P7
if result.success:
    adapter.complete_phase("P8")

# 详细进度追踪
progress = adapter.get_execution_progress()
print(f"Progress: {progress['progress_percent']:.1f}%")
for phase_info in progress["phases"][:5]:
    print(f"  {phase_info['phase_id']}: {phase_info['state']}")
```

**特点**:
- ✅ 完整11阶段支持
- ✅ 自动依赖解析
- ✅ 可选阶段跳过
- ✅ 详细进度追踪
- ✅ 状态持久化
- ❌ 更复杂

### 3. CUSTOM 模式 (未来)

**适用**: 特殊工作流需求

> **计划中功能** - 允许用户自定义阶段组合和顺序

---

## API 参考

### LifecycleProtocol 接口

#### 核心方法

```python
class LifecycleProtocol(ABC):
    # 模式管理
    def get_mode(self) -> LifecycleMode: ...
    def set_mode(self, mode: LifecycleMode) -> None: ...

    # 阶段查询
    def get_all_phases(self) -> List[PhaseDefinition]: ...
    def get_active_phases(self) -> List[PhaseDefinition]: ...
    def get_phase(self, phase_id: str) -> Optional[PhaseDefinition]: ...
    def get_current_phase(self) -> Optional[PhaseDefinition]: ...

    # 阶段操作
    def advance_to_phase(self, phase_id: str) -> PhaseResult: ...
    def complete_phase(self, phase_id: str) -> None: ...

    # 门禁检查
    def check_gate(self, phase_id: Optional[str] = None) -> GateResult: ...

    # 状态查询
    def get_status(self) -> LifecycleStatus: ...

    # 视图层映射
    def get_view_mapping(self, command: str) -> Optional[ViewMapping]: ...
    def resolve_command_to_phases(self, command: str) -> List[PhaseDefinition]: ...
```

#### FullLifecycleAdapter 特有方法

```python
class FullLifecycleAdapter(LifecycleProtocol):
    # 自动推进
    def get_next_phase(self) -> Optional[str]: ...
    def auto_advance(self) -> PhaseResult: ...

    # 配置
    def set_skip_optional(self, skip: bool) -> None: ...

    # 进度追踪
    def get_execution_progress(self) -> Dict[str, Any]: ...

    # 状态持久化
    def set_task_id(self, task_id: str) -> None: ...
    def enable_checkpoint_integration(self, storage_path: str) -> bool: ...
    def save_state(self) -> bool: ...
    def restore_state(self) -> bool: ...
```

### UnifiedGateEngine API

```python
from scripts.collaboration.unified_gate_engine import (
    UnifiedGateEngine,
    UnifiedGateConfig,
    GateType,
    PhaseGateContext,
    WorkerOutputContext,
)

# 配置引擎
config = UnifiedGateConfig(
    strict_mode=True,          # 严格模式
    allowed_critical_flags=0,  # 允许的关键问题数
    max_output_lines=100,      # 最大输出行数
    min_test_coverage=0.8,     # 最小测试覆盖率
)

engine = UnifiedGateEngine(config=config)

# 检查阶段转换门禁
phase_context = PhaseGateContext(
    phase_id="P8",
    phase_name="Implementation",
    current_state="pending",
    target_state="running",
    dependencies_met=True,
    completed_phases=["P1", "P2", "P7"],
)
result = engine.check(GateType.PHASE_TRANSITION, phase_context)

# 检查工作输出质量门禁
worker_context = WorkerOutputContext(
    role_id="solo-coder",
    task_description="Implement feature X",
    output="# Implementation code...",
    has_code_changes=True,
    has_test_changes=True,
    test_results={"all_passed": True},
)
worker_result = engine.check(GateType.WORKER_OUTPUT, worker_context)
```

---

## 使用场景

### 场景1: CLI快速任务

```bash
# 使用CLI命令
python3 scripts/cli.py lifecycle spec
python3 scripts/cli.py lifecycle build
python3 scripts/cli.py lifecycle test
```

### 场景2: Python脚本自动化完整项目

```python
# examples/full_project_workflow.py
from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter

adapter = FullLifecycleAdapter()
adapter.set_task_id("my-api-project")

# 运行完整11阶段
while True:
    result = adapter.auto_advance()
    if not result.success:
        break
    adapter.complete_phase(result.phase_id)

# 保存状态
adapter.save_state()
```

### 场景3: Web服务集成

```python
from fastapi import FastAPI
from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter

app = FastAPI()
lifecycle = FullLifecycleAdapter()

@app.post("/projects/{project_id}/advance")
async def advance_phase(project_id: str, phase_id: str):
    lifecycle.set_task_id(project_id)
    result = lifecycle.advance_to_phase(phase_id)
    return {"success": result.success, "phase": phase_id}

@app.get("/projects/{project_id}/status")
async def get_status(project_id: str):
    lifecycle.set_task_id(project_id)
    status = lifecycle.get_status()
    return status.to_dict()
```

### 场景4: CI/CD Pipeline集成

```yaml
# .github/workflows/devsquad.yml
name: DevSquad Lifecycle

on: [push, pull_request]

jobs:
  devsquad-lifecycle:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2

      - name: Run DevSquad Lifecycle
        run: |
          python3 -c "
          from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter
          adapter = FullLifecycleAdapter()
          adapter.set_task_id('ci-${{ github.run_id }}')
          adapter.advance_to_phase('P9')  # Test phase
          "
```

---

## 最佳实践

### ✅ DO (推荐做法)

1. **始终使用工厂函数**
   ```python
   # ✅ 好
   adapter = create_lifecycle_protocol(LifecycleMode.FULL)

   # ❌ 差
   from scripts.collaboration.lifecycle_protocol import FullLifecycleAdapter
   adapter = FullLifecycleAdapter()  # 直接实例化也可以，但工厂更灵活
   ```

2. **启用状态持久化**
   ```python
   adapter = FullLifecycleAdapter()
   adapter.set_task_id("my-project")
   adapter.enable_checkpoint_integration("./checkpoints")

   # 每次重要操作后保存
   adapter.save_state()
   ```

3. **检查门禁结果**
   ```python
   gate_result = adapter.check_gate("P8")
   if not gate_result.passed and gate_result.verdict == "REJECT":
       print(f"Blocked: {gate_result.gap_report}")
       # 处理失败情况
   ```

4. **处理异常**
   ```python
   try:
       result = adapter.advance_to_phase("P8")
   except Exception as e:
       logger.error(f"Phase advance failed: {e}")
       # 恢复或重试
   ```

5. **利用自动推进**
   ```python
   # 对于线性流程，使用auto_advance
   for i in range(total_phases):
       result = adapter.auto_advance()
       if result.success:
           adapter.complete_phase(result.phase_id)
       else:
           handle_failure(result)
           break
   ```

### ❌ DON'T (避免的做法)

1. **不要忽略门禁结果**
   ```python
   # ❌ 差
   adapter.advance_to_phase("P8")
   adapter.complete_phase("P8")  # 不检查是否成功

   # ✅ 好
   result = adapter.advance_to_phase("P8")
   if result.success:
       adapter.complete_phase("P8")
   else:
       handle_failure(result)
   ```

2. **不要在循环中不保存状态**
   ```python
   # ❌ 差
   for phase in phases:
       adapter.advance_to_phase(phase)
       adapter.complete_phase(phase)
       # 如果崩溃，丢失所有进度！

   # ✅ 好
   for phase in phases:
       adapter.advance_to_phase(phase)
       adapter.complete_phase(phase)
       adapter.save_state()  # 定期保存
   ```

3. **不要混合模式**
   ```python
   # ❌ 差
   adapter = create_lifecycle_protocol(LifecycleMode.SHORTCUT)
   # ... 然后尝试使用FULL模式特有的方法
   adapter.auto_advance()  # 可能不存在或行为不同
   ```

---

## 故障排除

### 常见问题

#### Q1: 阶段推进失败 - 依赖未满足

**错误信息**: `Unmet dependencies: ['P7']`

**解决方案**:
```python
# 先完成依赖阶段
adapter.advance_to_phase("P7")
adapter.complete_phase("P7")

# 再尝试目标阶段
result = adapter.advance_to_phase("P8")  # 现在应该成功
```

#### Q2: 门禁检查被拒绝

**错误信息**: `Gate rejected: ...`

**解决方案**:
```python
# 查看详细原因
gate_result = adapter.check_gate("P8")
print(gate_result.gap_report)
print([issue["message"] for issue in gate_result.red_flags])

# 根据具体问题修复
```

#### Q3: 状态恢复失败

**错误信息**: `Failed to restore lifecycle state`

**解决方案**:
```python
# 检查checkpoint目录是否存在
import os
assert os.path.exists("./checkpoints/lifecycle"), "Checkpoint dir missing"

# 尝试手动创建
os.makedirs("./checkpoints/lifecycle", exist_ok=True)

# 再次尝试恢复
restored = adapter.restore_state()
```

#### Q4: 性能问题 - 大量阶段时慢

**解决方案**:
```python
# 跳过可选阶段
adapter.set_skip_optional(True)

# 或使用SHORTCUT模式（如果适合）
adapter = create_lifecycle_protocol(LifecycleMode.SHORTCUTDOWN)
```

---

## 🎨 可视化与监控 (V3.5.0-C 新增)

### Streamlit 交互式仪表板

启动Web仪表板进行实时监控：

```bash
# 安装依赖
pip install streamlit

# 启动仪表板
streamlit run scripts/dashboard.py
```

**功能特性**：
- 📊 实时生命周期阶段状态监控
- 🔗 CLI命令到11阶段的映射可视化
- 🚧 Gate状态追踪与显示
- 📈 性能指标展示（响应时间、成功率等）
- 🎮 交互式控制面板

**页面导航**：
1. **Overview** - 系统概览与关键指标
2. **Phases** - 阶段时间线详情
3. **Mapping** - CLI命令映射表
4. **Gates** - 门禁状态监控
5. **Performance** - 性能指标面板

### CLI 增强输出

使用可视化模式获得更丰富的终端体验：

```bash
# 标准模式
python scripts/cli.py lifecycle build

# 可视化模式（推荐）
python scripts/cli.py lifecycle build --visual --verbose
```

**可视化功能**：
- 🎨 彩色进度条和状态图标
- 📋 格式化表格与对齐
- ⏱️ 百分比完成度指示器
- 🔒 Gate状态可视化
- ℹ️ 详细信息框

### Jupyter Notebook 交互式教程

逐步学习DevSquad核心概念：

```bash
# 安装Jupyter
pip install jupyter

# 启动教程
jupyter notebook examples/tutorial.ipynb
```

**教程内容**：
1. 环境准备与导入
2. 核心概念理解（三种生命周期模式）
3. CLI命令映射机制
4. Gate检查机制详解
5. 阶段执行模拟
6. 状态查询与可视化
7. 性能基准测试
8. 实际应用场景
9. 高级特性（自定义工作流、Checkpoint管理）
10. 总结与下一步

### 基准测试报告生成器

生成HTML/JSON格式的性能和质量报告：

```bash
# 生成HTML报告并在浏览器中打开
python scripts/generate_benchmark_report.py --format html --open

# 生成JSON报告供程序使用
python scripts/generate_benchmark_report.py --format json

# 同时生成两种格式
python scripts/generate_benchmark_report.py --format both
```

**输出位置**: `reports/benchmark_YYYYMMDD_HHMMSS.html`

**报告内容**：
- 📊 测试通过率与覆盖率
- ⚡ 性能指标（平均响应时间、P95延迟）
- ✅ 质量门禁评估结果
- 🔍 红旗问题与缺失证据清单
- 📈 趋势分析与改进建议

---

## 示例代码位置

- **快速开始**: [examples/quick_start.py](../examples/quick_start.py)
- **完整项目流程**: [examples/full_project_workflow.py](../examples/full_project_workflow.py)
- **交互式教程**: [examples/tutorial.ipynb](../examples/tutorial.ipynb)
- **测试用例**: [tests/test_full_lifecycle_adapter.py](../tests/test_full_lifecycle_adapter.py)
- **Streamlit仪表板**: [scripts/dashboard.py](../scripts/dashboard.py)
- **CLI可视化模块**: [scripts/cli/cli_visual.py](../scripts/cli/cli_visual.py)
- **基准报告生成器**: [scripts/generate_benchmark_report.py](../scripts/generate_benchmark_report.py)

---

## 版本历史

- **V3.5.0-C** (2026-05-03): Plan C分层架构 + 可视化增强
  - 新增: FullLifecycleAdapter (完整11阶段支持)
  - 新增: UnifiedGateEngine (统一门禁引擎)
  - 新增: Streamlit Dashboard (Web监控仪表板)
  - 新增: Jupyter Notebook Tutorial (交互式教程)
  - 新增: CLI Visualization Module (终端可视化)
  - 新增: Benchmark Report Generator (性能报告生成)
  - 增强: CheckpointManager状态持久化
  - 测试: 755+ 测试用例 (99.34% 通过率)

---

## 获取帮助

- 📧 Issues: [GitHub Issues](https://github.com/your-repo/DevSquad/issues)
- 💬 Discussions: [GitHub Discussions](https://github.com/your-repo/DevSquad/discussions)
- 📚 文档: [docs/](../docs/)

---

**最后更新**: 2026-05-03  
**版本**: V3.5.0-C (Plan C Layered Architecture)  
**作者**: DevSquad Team
