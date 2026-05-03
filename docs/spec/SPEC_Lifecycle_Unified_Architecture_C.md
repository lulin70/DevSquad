# DevSquad V3.5 Lifecycle Unified Architecture (方案C)

> **状态**: 设计阶段 — 待评审
> **日期**: 2026-05-03
> **背景**: CLI 6命令与11阶段生命周期存在实质性冲突，需通过分层架构统一
> **决策**: 采用方案C — CLI作为11阶段的视图层(View Layer)

---

## 一、设计目标

### 1.1 核心问题
- **问题A**: 两套独立的生命周期定义（CLI 6命令 vs 11阶段），无明确关系
- **问题B**: 双重入口操作同一底层系统，状态分裂
- **问题C**: 扩展时需同步修改多处，维护成本高

### 1.2 设计原则

| # | 原则 | 说明 |
|---|------|------|
| 1 | **单一真相源** | 11阶段 PHASE_TEMPLATES 是唯一完整定义 |
| 2 | **视图层模式** | CLI 6命令是11阶段的简化视图(View)，非独立系统 |
| 3 | **协议抽象** | 通过 LifecycleProtocol 接口解耦 |
| 4 | **模式可切换** | 支持 SHORTCUT / FULL / CUSTOM 三种模式 |
| 5 | **向后兼容** | 现有CLI命令保持可用，内部实现改为调用11阶段 |

---

## 二、架构设计

### 2.1 分层架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                    用户交互层 (User Interface)                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────────────┐    ┌───────────────────────────────────┐  │
│  │  CLI 6 Commands   │    │  WorkflowEngine (Full Mode)       │  │
│  │  (View Layer)     │    │  (11 Phases)                     │  │
│  │                   │    │                                   │  │
│  │  spec → P1+P2     │    │  P1 → P2 → P3 → ... → P11       │  │
│  │  plan → P7        │    │                                   │  │
│  │  build → P8       │    │  完整的阶段流转、门禁、依赖管理     │  │
│  │  test → P9        │    │                                   │  │
│  │  review → P8内嵌   │    │                                   │  │
│  │  ship → P10        │    │                                   │  │
│  └────────┬───────────┘    └──────────────┬────────────────┘  │
│           │                               │                  │
│           ▼                               ▼                  │
│  ┌──────────────────────────────────────────────────┐         │
│  │          LifecycleProtocol (Interface)            │         │
│  │                                                  │         │
│  │  + get_phases() → List[PhaseDef]                 │         │
│  │  + get_current_phase() → PhaseDef                │         │
│  │  + advance_phase(phase_id) → PhaseResult         │         │
│  │  + check_gate(phase_id) → GateResult             │         │
│  │  + get_status() → LifecycleStatus               │         │
│  └──────────────────────┬───────────────────────────┘         │
│                         │                                     │
│                         ▼                                     │
│  ┌──────────────────────────────────────────────────┐         │
│  │           Core Engine Layer                      │         │
│  │                                                  │         │
│  │  PHASE_TEMPLATES (11 phases, single source)      │         │
│  │  VerificationGate (unified gate engine)           │         │
│  │  CheckpointManager (unified state)               │         │
│  │  MultiAgentDispatcher (execution)                │         │
│  └──────────────────────────────────────────────────┘         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 核心组件

#### Component 1: LifecycleMode 枚举
```python
class LifecycleMode(Enum):
    SHORTCUT = "shortcut"  # CLI 6命令模式（简化视图）
    FULL = "full"         # 11阶段完整模式
    CUSTOM = "custom"     # 自定义流程模式
```

#### Component 2: LifecycleProtocol 接口
```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class LifecycleProtocol(ABC):
    """Abstract interface for lifecycle management."""

    @abstractmethod
    def get_mode(self) -> LifecycleMode:
        """Return current lifecycle mode."""
        ...

    @abstractmethod
    def get_all_phases(self) -> List[PhaseDefinition]:
        """Return all available phases in current mode."""
        ...

    @abstractmethod
    def get_active_phases(self) -> List[PhaseDefinition]:
        """Return phases active for current task."""
        ...

    @abstractmethod
    def get_current_phase(self) -> Optional[PhaseDefinition]:
        """Return current phase or None if not started."""
        ...

    @abstractmethod
    def advance_to_phase(self, phase_id: str) -> PhaseResult:
        """Advance to specified phase, running gate checks."""
        ...

    @abstractmethod
    def check_gate(self, phase_id: str = None) -> GateResult:
        """Check gate conditions for phase (default: current)."""
        ...

    @abstractmethod
    def get_status(self) -> LifecycleStatus:
        """Return overall lifecycle status."""
        ...
```

#### Component 3: PhaseViewMapping (CLI → 11阶段映射)
```python
PHASE_VIEW_MAPPING: Dict[str, ViewMapping] = {
    # CLI command → 11阶段映射
    "spec": ViewMapping(
        phases=["P1", "P2"],              # 覆盖的11阶段
        mode=LifecycleMode.SHORTCUT,
        description="需求分析 + 架构设计",
        required_roles=["architect", "product-manager"],
        gate="spec_first",
    ),
    "plan": ViewMapping(
        phases=["P7"],
        mode=LifecycleMode.SHORTCUT,
        description="测试计划 + 任务分解",
        required_roles=["architect", "product-manager"],
        gate="task_breakdown_complete",
    ),
    "build": ViewMapping(
        phases=["P8"],
        mode=LifecycleMode.SHORTCUT,
        description="开发实现 (TDD)",
        required_roles=["architect", "solo-coder", "tester"],
        gate="incremental_verification",
    ),
    "test": ViewMapping(
        phases=["P9"],
        mode=LifecycleMode.SHORTCUT,
        description="测试执行 + 验证",
        required_roles=["tester", "solo-coder"],
        gate="evidence_required",
    ),
    "review": ViewMapping(
        phases=["P8_review", "P6_partial"],  # P8内嵌审查 + 部分P6
        mode=LifecycleMode.SHORTCUT,
        description="代码审查 + 安全检查",
        required_roles=["solo-coder", "security", "tester", "architect"],
        gate="change_size_limit",
    ),
    "ship": ViewMapping(
        phases=["P10"],
        mode=LifecycleMode.SHORTCUT,
        description="部署发布",
        required_roles=["devops", "security", "architect"],
        gate="pre_launch_checklist",
    ),
}
```

---

## 三、CLI 重构方案

### 3.1 当前实现（重构前）
```python
# cli.py - cmd_lifecycle() 直接使用 LIFECYCLE_PRESETS
def cmd_lifecycle(args):
    preset = LIFECYCLE_PRESETS[args.lifecycle_command]
    result = dispatch(task, roles=preset["required_roles"])
```

### 3.2 目标实现（重构后）
```python
# cli.py - cmd_lifecycle() 通过 LifecycleProtocol 调用
def cmd_lifecycle(args):
    protocol = get_lifecycle_protocol(mode=LifecycleMode.SHORTCUT)
    view_mapping = PHASE_VIEW_MAPPING[args.lifecycle_command]

    # 获取该视图对应的11阶段
    phases = [protocol.get_phase(pid) for pid in view_mapping.phases]

    # 检查前置条件
    for phase in phases:
        gate_result = protocol.check_gate(phase.id)
        if not gate_result.passed:
            print(f"⚠️ Gate {phase.id} not met: {gate_result.reason}")

    # 执行调度（底层走11阶段逻辑）
    result = dispatch(
        task=args.task,
        roles=view_mapping.required_roles,
        lifecycle_context={
            "mode": "shortcut",
            "view_command": args.lifecycle_command,
            "target_phases": view_mapping.phases,
        }
    )
```

### 3.3 新增 CLI 命令
```bash
# 显示当前生命周期状态
devsquad lifecycle status
# Output:
# Mode: SHORTCUT (spec/plan/build/test/review/ship)
# Full Mode Available: Yes (11 phases)
# Current Phase: P8 (Implementation) - running
# Completed: [P1, P2, P3, P7]
# Next: P9 (Test Execution)

# 切换到完整模式
devsquad lifecycle --mode full
# Now shows all 11 phases with full detail

# 显示某个命令对应的11阶段详情
devsquad spec --show-phases
# Output:
# Command 'spec' maps to phases: [P1, P2]
# P1 Requirements Analysis (pm) → User stories, acceptance criteria
# P2 Architecture Design (arch) → Architecture proposal, tech selection
```

---

## 四、状态管理统一

### 4.1 统一状态模型
```python
@dataclass
class UnifiedLifecycleState:
    """Single source of truth for lifecycle state."""

    mode: LifecycleMode
    view_command: Optional[str]  # Which CLI command triggered this (if shortcut mode)

    # 11阶段状态
    phase_states: Dict[str, PhaseState]  # {"P1": COMPLETED, "P2": RUNNING, ...}

    # 元数据
    task_id: str
    started_at: datetime
    updated_at: datetime

    # Checkpoint (for recovery)
    checkpoint: Optional[Checkpoint] = None
```

### 4.2 CheckpointManager 扩展
```python
# 现有: 只支持11阶段状态
checkpoint = CheckpointManager()
checkpoint.save_phase_state("P8", "running", artifacts={...})

# 新增: 支持快捷模式状态
checkpoint.save_view_state(
    mode=LifecycleMode.SHORTCUT,
    view_command="build",
    mapped_phases=["P8"],
    phase_states={"P8": "running"},
)
```

---

## 五、门禁引擎统一

### 5.1 统一门禁检查流
```
User Request (CLI or WorkflowEngine)
        │
        ▼
  LifecycleProtocol.check_gate(phase_id)
        │
        ├──► VerificationGate (P0-2 implementation)
        │     ├── Red Flag detection
        │     ├── Mandatory evidence check
        │     └── Verdict: APPROVE/CONDITIONAL/REJECT
        │
        ├──► Phase-specific gates (from PHASE_TEMPLATES)
        │     ├── P1: Acceptance criteria quantifiable
        │     ├── P8: Code review passed
        │     └── P10: Deployment drill passed
        │
        └──► Return unified GateResult
              ├── passed: bool
              ├── verdict: str
              ├── red_flags: list
              ├── missing_evidence: list
              └── gap_report: str  # If not passed, what's missing?
```

---

## 六、迁移路径

### Phase 1: 接口定义（本次实施）
- [ ] 创建 `lifecycle_protocol.py` (LifecycleProtocol ABC)
- [ ] 创建 `lifecycle_mode.py` (LifecycleMode enum)
- [ ] 创建 `phase_view_mapping.py` (CLI→11阶段映射表)

### Phase 2: CLI 重构（本次实施）
- [ ] 修改 `cmd_lifecycle()` 使用新接口
- [ ] 新增 `lifecycle status/show-phases/--mode` 子命令
- [ ] 保持向后兼容（旧参数仍有效）

### Phase 3: 状态统一（后续优化）
- [ ] 扩展 CheckpointManager 支持双模式
- [ ] 统一状态序列化格式
- [ ] 添加模式切换能力

### Phase 4: 文档更新（本次实施）
- [ ] 更新 SKILL.md 说明分层架构
- [ ] 更新 GUIDE.md 添加使用指南
- [ ] 更新 README.md 示例

---

## 七、测试策略

### 7.1 单元测试
- `test_lifecycle_protocol.py`: 接口契约验证
- `test_phase_view_mapping.py`: 映射正确性验证
- `test_lifecycle_mode.py`: 枚举行为验证

### 7.2 集成测试
- `test_cli_view_layer.py`: CLI命令正确映射到11阶段
- `test_unified_gate.py`: 门禁在两种模式下一致
- `test_mode_switching.py`: SHORTCUT ↔ FULL 切换

### 7.3 回归测试
- 现有所有CLI测试必须通过
- 现有WorkflowEngine测试必须通过
- 无功能退化

---

## 八、风险评估

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|---------|
| 向后兼容性破坏 | 中 | 高 | 保持旧API签名，内部重写 |
| 性能开销增加 | 低 | 中 | 视图层只做映射，不引入额外计算 |
| 测试覆盖不足 | 中 | 高 | 先写测试再重构 |
| 文档同步延迟 | 高 | 中 | 本次一并更新 |

---

## 九、成功标准

| # | 标准 | 验证方法 |
|---|------|---------|
| 1 | CLI 6命令仍可正常使用 | 现有CLI测试全部通过 |
| 2 | CLI命令内部调用11阶段逻辑 | 日志显示正确的phase_id |
| 3 | `lifecycle status` 正确显示状态 | 新增测试验证 |
| 4 | 门禁结果在两种模式下一致 | 对比测试 |
| 5 | 文档明确说明两套系统的关系 | 文档审核通过 |

---

*文档创建时间: 2026-05-03*
*预计工作量: 8小时（含测试和文档）*
*优先级: P0（阻塞v3.4.2发布）*
