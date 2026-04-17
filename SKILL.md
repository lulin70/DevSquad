---
name: multi-agent-team-v3
slug: multi-agent-team-v3
description: |
  V3.2 多智能体协作平台 — 基于 Coordinator/Worker/Scratchpad 模式的完整多Agent协作系统。
  集成15大核心模块：Coordinator协调器 + Scratchpad共享黑板 + Worker执行者 + Consensus共识引擎 +
  BatchScheduler并行调度 + ContextCompressor上下文压缩 + PermissionGuard权限守卫 +
  Skillifier技能学习 + WarmupManager启动预热 + MemoryBridge记忆桥接 +
  PromptAssembler提示词组装 + PromptVariantGenerator变体生成 + MCEAdapter记忆分类适配器。
  ~795个测试全通过。支持中英文双语。
---

# Multi-Agent Team V3.2 — 多智能体协作平台

## 核心定位

本 Skill 将 Trae 从「单AI助手」升级为「多AI团队」。当用户提出任务时，不再由单一角色处理，而是：

```
用户任务 → [意图分析] → [角色匹配] → [Coordinator编排]
        → [多个Worker并行执行] → [Scratchpad实时共享]
        → [Consensus共识决策] → [MCE分类增强] → [结果汇总返回]
```

## 架构总览（15大模块）

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | 统一调度入口，一键完成全流程协作（集成所有模块） |
| 1 | **Coordinator** | `coordinator.py` | 全局编排者，分解任务、分配Worker、收集结果、解决冲突 |
| 2 | **Scratchpad** | `scratchpad.py` | 共享黑板，Worker间实时交换发现/决策/冲突 |
| 3 | **Worker** | `worker.py` | 工作者，每个角色一个实例，独立执行并写入Scratchpad |
| 4 | **ConsensusEngine** | `consensus.py` | 共识引擎，权重投票+否决权+升级人工机制 |
| 5 | **BatchScheduler** | `batch_scheduler.py` | 并行/串行混合调度，自动判断并发安全性 |
| 6 | **ContextCompressor** | `context_compressor.py` | 4级上下文压缩(NONE/SNIP/SESSION_MEMORY/FULL_COMPACT) |
| 7 | **PermissionGuard** | `permission_guard.py` | 4级权限守卫(PLAN/DEFAULT/AUTO/BYPASS) |
| 8 | **Skillifier** | `skillifier.py` | 从成功操作模式中自动生成新Skill |
| 9 | **WarmupManager** | `warmup_manager.py` | 3层启动预热(EAGER/ASYNC/LAZY) + 进程级缓存 |
| 10 | **MemoryBridge** | `memory_bridge.py` | 7类型记忆桥接 + 倒排索引 + TF-IDF + 遗忘曲线 + MCE集成 |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | 测试质量审计(API校验/反模式检测/维度覆盖) |
| 12 | **PromptAssembler** | `prompt_assembler.py` | 动态提示词组装(复杂度检测/3级变体/5种风格/压缩感知) |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | Skillify闭环反哺(模式→变体/A/B测试/自动晋升淘汰) |
| 14 | **MCEAdapter** | `mce_adapter.py` | MCE记忆分类引擎适配器(懒加载/优雅降级/线程安全) |

---

## 快速使用（必须遵循）

### 方式一：一键协作（推荐用于大多数场景）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("用户描述的任务")
print(result.to_markdown())
disp.shutdown()
```

**何时使用方式一**：
- 用户要求"设计XX"、"实现XX"、"分析XX"等单一指令任务
- 需要快速得到多角色协作结果
- 不需要精细控制参与角色

### 方式二：指定角色协作

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("设计用户认证系统", roles=["architect", "tester"])
print(result.to_markdown())
disp.shutdown()
```

### 方式三：Dry-Run 模拟（仅分析不执行）

```python
disp = MultiAgentDispatcher()
result = disp.dispatch("测试任务", dry_run=True)
print(result.summary)
disp.shutdown()
```

### 方式四：便捷函数（单行调用）

```python
from scripts.collaboration.dispatcher import quick_collaborate
result = quick_collaborate("帮我设计一个微服务架构")
print(result.to_markdown())
```

---

## 角色系统（5个内置角色）

| Role ID | 名称 | 触发关键词 | 核心职责 |
|---------|------|-----------|---------|
| `architect` | 架构师 | 架构、设计、选型、性能、模块、接口、部署 | 系统架构设计、技术选型、性能优化 |
| `product-manager` | 产品经理 | 需求、PRD、用户故事、竞品、验收 | 需求分析、PRD编写、产品规划 |
| `tester` | 测试专家 | 测试、质量、验收、自动化、缺陷 | 测试策略、用例设计、质量保障 |
| `solo-coder` | 独立开发者 | 实现、开发、代码、修复、优化 | 功能开发、编码实现、单元测试 |
| `ui-designer` | UI设计师 | UI、界面、前端、视觉、原型 | UI设计、交互设计、原型制作 |

**自动匹配规则**：不指定roles时，系统根据任务关键词自动匹配最合适的角色组合。

---

## 完整工作流程（当你被调用时）

当用户触发本 Skill 时，按以下步骤执行：

### Step 1: 创建调度器

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher
import tempfile

work_dir = tempfile.mkdtemp(prefix="mas_v3_")
disp = MultiAgentDispatcher(
    persist_dir=work_dir,
    enable_warmup=True,
    enable_compression=True,
    enable_permission=True,
    enable_memory=True,
    enable_skillify=True,
)
```

### Step 2: 分析任务并匹配角色

```python
matched = disp.analyze_task(user_task)
for role in matched:
    print(f"{role['name']} (置信度: {role['confidence']:.0%}) - {role['reason']}")
```

### Step 3: 执行协作

```python
result = disp.dispatch(
    task_description=user_task,
    roles=None,          # None=自动匹配，或指定如 ["architect", "tester"]
    mode="auto",         # auto/parallel/sequential/consensus
    dry_run=False,       # True=仅模拟
)
```

### Step 4: 检查结果

```python
print(f"成功: {result.success}")
print(f"参与角色: {result.matched_roles}")
print(f"耗时: {result.duration_seconds:.2f}s")
print(result.summary)

if result.worker_results:
    for wr in result.worker_results:
        print(f"[{wr['role']}] {wr['output'][:200]}")
```

### Step 5: 输出 Markdown 报告给用户

```python
report = result.to_markdown()
print(report)
```

### Step 6: 清理资源

```python
disp.shutdown()
```

---

## 高级功能使用指南

### 上下文压缩（长对话防溢出）

当对话过长时，ContextCompressor 自动触发：
- **Level 1 SNIP**: 精细剪裁旧对话，保留关键决策和结论
- **Level 2 SessionMemory**: 提取重要信息到记忆后清空上下文
- **Level 3 FullCompact**: LLM生成一页摘要（最激进）

查看压缩状态：
```python
stats = disp.coordinator.get_compression_stats()
memory = disp.coordinator.get_session_memory()
```

### 权限检查（安全操作守卫）

PermissionGuard 自动检查危险操作：
- **PLAN级别**: 只允许读操作
- **DEFAULT级别**: 写操作需确认
- **AUTO级别**: AI分类器自动判断
- **BYPASS级别**: 完全跳过（最高信任）

权限记录在 `result.permission_checks` 中。

### 记忆桥接（跨会话记忆）

MemoryBridge 提供7种记忆类型：
- `knowledge` — 知识条目
- `episodic` — 情节记忆（任务执行记录）
- `semantic` — 语义记忆
- `feedback` — 用户反馈
- `pattern` — 成功模式
- `analysis` — 分析案例
- `correction` — 纠正记录

遗忘曲线：7天=1.0, 30天≈0.8, 60天≈0.5, 90天≈0.3

查看记忆状态：
```python
status = disp.get_status()
mem_stats = status.get("memory_stats")
```

### 启动预热（减少冷启动延迟）

WarmupManager 三层预热：
- **EAGER层**: 同步预加载关键资源（~15ms）
- **ASYNC层**: 异步后台预热（~300ms）
- **LAZY层**: 按需加载

查看预热状态：
```python
status = disp.get_status()
warmup = status.get("warmup_metrics")
```

### Skill 学习（从成功中进化）

Skillifier 自动从成功操作序列中提取可复用模式：
```python
proposals = result.skill_proposals
for p in proposals:
    print(f"新Skill候选: {p['title']} (置信度: {p['confidence']:.0%})")
```

### 共识决策（多角色冲突解决）

当Worker间出现分歧时，ConsensusEngine 自动启动投票：
- 权重投票（按角色重要性加权）
- 否决权机制（关键角色一票否决）
- 升级人工（无法达成时标记待人工裁决）

共识记录在 `result.consensus_records` 中。

---

## 调度模式说明

| 模式 | 说明 | 适用场景 |
|------|------|---------|
| `auto` | 自动选择最优模式 | 默认推荐 |
| `parallel` | 所有角色并行执行 | 角色间无依赖 |
| `sequential` | 按顺序串行执行 | 有依赖关系 |
| `consensus` | 执行后强制共识投票 | 需要一致决策 |

---

## 系统状态查询

```python
status = disp.get_status()
# 返回：
# {
#   "version": "3.0",
#   "components": {...},       # 各组件启用状态
#   "dispatch_count": N,        # 已执行调度次数
#   "scratchpad_stats": {...},  # 黑板统计
#   "warmup_metrics": {...},    # 预热指标（如启用）
#   "memory_stats": {...},      # 记忆统计（如启用）
# }

history = disp.get_history(limit=10)
# 返回最近N次调度的完整结果
```

---

## 错误处理

所有异常都被捕获在 `DispatchResult` 中，不会抛出：

```python
result = disp.dispatch("任何任务")
if not result.success:
    print("错误:", result.errors)
    print("摘要:", result.summary)
```

常见错误及处理：
- `FILE_CREATE` / 权限相关 → PermissionGuard拦截，检查 `result.permission_checks`
- 记忆写入失败 → MemoryBridge存储问题，检查目录权限
- 压缩失败 → ContextCompressor问题，通常不影响主流程

---

## 语言规则

- 自动识别用户语言（中文/英文）
- 所有输出使用与用户相同的语言
- 角色名称映射：架构师→Architect, 产品经理→Product Manager, etc.

---

## 测试铁律（⚠️ AI 编写测试时必须遵守）

> 本节解决 AI 辅助开发中测试质量的三大顽疾。**违反任何一条都是严重错误。**

### 铁律 1：文档先行 — 禁止凭空写 API 调用

```
❌ 错误做法: 凭记忆/猜测写参数名
   result = obj.method(bad_param="value")  # 参数名是猜的

✅ 正确做法: 先读源码确认签名，再写测试
   # 1. 用 AST 提取或直接阅读源码确认参数
   # 2. 使用 TestQualityGuard 自动校验
   from scripts.collaboration.test_quality_guard import quick_audit
   report = quick_audit("module.py", "module_test.py")
   print(report.to_markdown())  # 查看是否有 API 参数错误
```

**强制要求**：
- 写任何测试之前，必须先 `import` 目标模块并检查实际签名
- 禁止使用不存在的参数名（如 `id` vs `record_id`, `action` vs `action_type`）
- 可使用 `TestQualityGuard.quick_audit()` 自动检测

### 铁律 2：失败即报告 — 禁止为通过而修改断言

```
❌ 严重错误: 测试失败时修改断言来"通过"
   # 原始: assertEqual(result, expected_value)
   # 改成: assertTrue(result > 0)          ← 这是作弊！
   # 改成: assertGreater(score, 0.0)      ← 0.0 阈值必然通过！

✅ 正确做法: 失败时分析根因，修复实现或修正测试逻辑
   # 1. 先确认 API 签名是否正确（铁律1）
   # 2. 确认测试数据是否合理
   # 3. 如果实现确实有 bug → 报告给架构师/开发者
   # 4. 只有当测试本身逻辑错误时才修改断言
```

**禁止的反模式**（TestQualityGuard 会自动检测）：
| 反模式 | 严重级别 | 说明 |
|--------|---------|------|
| 宽松断言 (`assertTrue`) | MINOR | 应优先用 `assertEqual/assertIn` |
| 无效阈值 (`>0.0`) | MINOR | 必须设置有意义的阈值 |
| 裸 `except:` | MAJOR | 必须指定异常类型 |
| 魔法数字 (>999) | MINOR | 提取为命名常量 |

### 铁律 3：维度完整 — 禁止只测 happy path

每个模块的测试套件**必须**覆盖以下维度：

| 维度 | 符号 | 最低占比 | 说明 |
|------|------|---------|------|
| **Happy Path** | ✅ | ≥50% | 正常输入 → 预期输出 |
| **Error Case** | 🔴 | **≥15%** | 非法输入/空值/越界 → 异常或错误返回 |
| **Boundary** | 🟡 | ≥10% | 空字符串、零值、最大值、None |
| **Performance** | ⚡ | **≥5%** | 关键路径耗时基准（如 `<100ms`） |
| **Configuration** | ⚙️ | ≥5% | 不同配置项组合 |
| **Integration** | 🔗 | ≥10% | 模块间协作场景 |
| **Security** | 🔒 | 按需 | 权限/注入/越权（如有安全相关） |

**自动检查工具**：
```python
from scripts.collaboration.test_quality_guard import TestQualityGuard

guard = TestQualityGuard(
    module_path="scripts/collaboration/coordinator.py",
    test_path="scripts/collaboration/coordinator_test.py",
)
report = guard.audit()
print(report.to_markdown())
# 输出: 评分 + 问题清单 + 各维度覆盖情况 + 反模式检测
```

### 测试函数模板（必须遵循的格式）

```python
def test_<功能>_<场景>(self):
    """验证: <具体要验证什么，一句话说清楚>

    场景说明: <什么条件下触发>
    预期结果: <应该发生什么>
    """
    # Arrange - 准备数据和依赖

    # Act - 执行被测操作

    # Assert - 验证结果（使用精确断言，不用 assertTrue 绕过）
```

---

## 测试覆盖

| 模块 | 测试数 | 质量评分 | 状态 |
|------|--------|---------|------|
| PromptOptimization (提示词优化) | 59 | ✅ | ✅ PASS |
| TestQualityGuard (质量守卫) | 42 | 自身审计通过 | ✅ PASS |
| Dispatcher (统一调度) | 54 | ✅ | ✅ PASS |
| Coordinator + Scratchpad + Worker | 96 | ✅ | ✅ PASS |
| ContextCompressor | 72 | ✅ | ✅ PASS |
| PermissionGuard | 105 | ✅ | ✅ PASS |
| Skillifier | 96 | ✅ | ✅ PASS |
| WarmupManager | 103 | ✅ | ✅ PASS |
| MemoryBridge | 96 | ✅ | ✅ PASS |
| Enhanced E2E | 46 | ✅ | ✅ PASS |
| **总计** | **~782** | **✅ ALL PASS** | |

---

## 版本历史

- **v3.1** (2026-04-16): 提示词优化系统 - 动态Prompt裁剪(3级变体) + Skillify闭环反哺(A/B晋升) + 压缩感知适配
- **v3.0.1** (2026-04-16): 代码注释全面补全(6大核心模块docstring 100%覆盖) + TestQualityGuard测试质量审计系统集成
- **v3.0** (2026-04-16): 完整重构为 Coordinator/Worker/Scratchpad 协作架构，11大模块（含Dispatcher+TestQualityGuard），~710测试全通过
- **v2.5** (2026-04-06): Memory Classification Engine 集成
- **v2.4** (2026-04-01~03): Vibe Coding + 核心规则 + 生命周期识别
- **v2.3** (2026-03-28): 多角色代码走读 + 3D可视化
- **v2.2** (2026-03-21): 长程 Agent (Checkpoint + Handoff)
- **v2.1** (2026-03-17): 双层上下文 + AI语义匹配
- **v2.0/v1.0** (2026-03-16): 初始版本
