---
name: devsquad
slug: devsquad
description: |
  V3.6.0-Prod DevSquad — 生产就绪多角色 AI 任务编排器。
  一个任务输入，多角色 AI 协作，一个结论输出。
  7个核心角色（架构师/产品经理/安全专家/测试员/开发人员/运维/UI设计师），
  真实 LLM 后端（OpenAI/Anthropic），CLI + REST API + Dashboard + MCP + Python API。
  777+ 测试全部通过 (99.34%)。
  V3.6.0 新增: 认证系统(RBAC)、FastAPI REST服务器、告警通知、
  历史数据存储(SQLite)、带登录功能的Streamlit仪表板。
  ThreadPoolExecutor 并行、CheckpointManager、WorkflowEngine、流式输出、Docker、CI。
---

# DevSquad V3.6.0-Prod — 多角色 AI 任务编排器（生产就绪）

## 核心定位

本 Skill 将 Trae 从「单AI助手」升级为「多AI团队」。当用户提出任务时，不再由单一角色处理，而是：

```
用户任务 → [输入验证] → [角色匹配] → [Coordinator编排]
        → [ThreadPoolExecutor并行Worker] → [Scratchpad实时共享]
        → [ConsensusEngine共识] → [报告格式化] → [结构化报告]
```

## 架构总览（45大模块）

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | 统一调度入口，一键完成全流程协作（集成所有模块） |
| 1 | **Coordinator** | `coordinator.py` | 全局编排者，分解任务、分配Worker、收集结果、解决冲突 |
| 2 | **Scratchpad** | `scratchpad.py` | 共享黑板，Worker间实时交换发现/决策/冲突 |
| 3 | **Worker** | `worker.py` | 工作者，每个角色一个实例，独立执行并写入Scratchpad（支持流式输出） |
| 4 | **ConsensusEngine** | `consensus.py` | 共识引擎，权重投票+否决权+升级人工机制 |
| 5 | **BatchScheduler** | `batch_scheduler.py` | 并行/串行混合调度，自动判断并发安全性 |
| 6 | **ContextCompressor** | `context_compressor.py` | 4级上下文压缩(NONE/SNIP/SESSION_MEMORY/FULL_COMPACT) |
| 7 | **PermissionGuard** | `permission_guard.py` | 4级权限守卫(PLAN/DEFAULT/AUTO/BYPASS) |
| 8 | **Skillifier** | `skillifier.py` | 从成功操作模式中自动生成新Skill |
| 9 | **WarmupManager** | `warmup_manager.py` | 3层启动预热(EAGER/ASYNC/LAZY) + 进程级缓存 |
| 10 | **MemoryBridge** | `memory_bridge.py` | 7类型记忆桥接 + 倒排索引 + TF-IDF + 遗忘曲线 + MCE+Claw集成 |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | 测试质量审计(API校验/反模式检测/维度覆盖) |
| 12 | **PromptAssembler** | `prompt_assembler.py` | 动态提示词组装(复杂度检测/3级变体/5种风格/压缩感知/QC配置注入) |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | Skillify闭环反哺(模式→变体/A/B测试/自动晋升淘汰) |
| 14 | **MCEAdapter** | `mce_adapter.py` | CarryMem集成适配器(懒加载/优雅降级/线程安全/类型映射) |
| 15 | **WorkBuddyClawSource** | `memory_bridge.py` (class) | WorkBuddy Claw只读桥接(索引检索/日更记忆/AI新闻流) |
| 16 | **RoleMatcher** | `role_matcher.py` | 基于关键词的角色匹配+别名解析（从Dispatcher提取） |
| 17 | **ReportFormatter** | `report_formatter.py` | 结构化/紧凑/详细报告生成（从Dispatcher提取） |
| 18 | **InputValidator** | `input_validator.py` | 安全验证 + 21+种Prompt注入模式检测 |
| 19 | **RuleCollector** | `rule_collector.py` | 自然语言规则收集（意图检测/规则提取/安全清洗/CarryMem+JSON存储/Prompt注入防护） |
| 20 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM驱动的语义角色匹配 + 中英双语关键词回退 |
| 21 | **CheckpointManager** | `checkpoint_manager.py` | SHA256完整性校验、交接文档、自动清理 |
| 22 | **WorkflowEngine** | `workflow_engine.py` | 任务→工作流自动拆分、步骤执行、断点恢复、11阶段生命周期模板、需求变更管理 |
| 23 | **TaskCompletionChecker** | `task_completion_checker.py` | DispatchResult/ScheduleResult完成度跟踪 |
| 24 | **CodeMapGenerator** | `code_map_generator.py` | Python AST代码结构分析 + 依赖图 |
| 25 | **DualLayerContext** | `dual_layer_context.py` | 项目级+任务级上下文管理（带TTL） |
| 26 | **SkillRegistry** | `skill_registry.py` | 可复用技能注册+发现+持久化 |
| 27 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic + 流式输出 + 120s超时 |
| 28 | **ConfigManager** | `config_loader.py` | YAML配置 + 环境变量覆盖（16个参数） |
| 29 | **Protocols** | `protocols.py` | Protocol接口(CacheProvider/RetryProvider/MonitorProvider/MemoryProvider) + 异常层级 |
| 30 | **NullProviders** | `null_providers.py` | 所有Protocol接口的空实现(降级 + 测试Mock) |
| 31 | **EnhancedWorker** | `enhanced_worker.py` | 基于Protocol的Provider注入Worker(缓存/重试/监控/简报) |
| 32 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99响应时间/CPU/内存追踪/瓶颈检测/Markdown报告 |
| 33 | **AgentBriefing** | `agent_briefing.py` | 上下文感知简报生成 + 优先级过滤 + 持久化 |
| 34 | **ConfidenceScorer** | `confidence_score.py` | 5因子置信度评分(完整性/确定性/具体性/一致性/模型质量) |
| 35 | **RoleTemplateMarket** | `role_template_market.py` | 角色模板市场(发布/搜索/安装/评分/导出/导入) |
| 36 | **LLMCache** | `llm_cache.py` | TTL LRU缓存+磁盘持久化（节省60-80%成本） |
| 37 | **LLMRetry** | `llm_retry.py` | 指数退避+熔断器+多后端回退 |
| 38 | **UsageTracker** | `usage_tracker.py` | Token/成本使用追踪和报告 |
| 39 | **Models** | `models.py` | 共享数据模型和类型定义 |
| 40 | **ConfigManager (YAML)** | `config_manager.py` | 项目级YAML配置管理 |
| 41 | **LLMCacheAsync** | `llm_cache_async.py` | 异步LLM缓存 |
| 42 | **LLMRetryAsync** | `llm_retry_async.py` | 异步LLM重试+退避 |
| 43 | **IntegrationExample** | `integration_example.py` | DevSquad集成示例代码 |
| 44 | **AsyncIntegrationExample** | `async_integration_example.py` | 异步DevSquad集成示例 |

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

## 角色系统（7个核心角色）

| Role ID | 名称 | 触发关键词 | 核心职责 |
|---------|------|-----------|---------|
| `architect` | 架构师 | 架构、设计、选型、性能、模块、接口、数据架构 | 系统架构设计、技术选型、性能/安全/数据架构 |
| `product-manager` | 产品经理 | 需求、PRD、用户故事、竞品、验收 | 需求分析、PRD编写、产品规划 |
| `security` | 安全专家 | 安全、漏洞、审计、威胁、加密、OWASP | 威胁建模、漏洞审计、合规评估、安全审查 |
| `tester` | 测试专家 | 测试、质量、验收、自动化、缺陷 | 测试策略、用例设计、质量保障 |
| `solo-coder` | 开发者 | 实现、开发、代码、修复、优化、重构 | 功能开发、代码审查、性能优化、重构 |
| `devops` | DevOps工程师 | CI/CD、部署、监控、Docker、K8s、基础设施 | CI/CD流水线、容器化、监控、基础设施 |
| `ui-designer` | UI设计师 | UI、界面、前端、视觉、原型、无障碍 | UI设计、交互设计、原型制作、无障碍 |

**CLI短ID**: `arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`

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

## 项目全生命周期：11阶段模型（V3.5）

> **定义文档**: `docs/prd/lifecycle_phases_definition.md`（权威）
> **评审报告**: `docs/prd/lifecycle_phases_review.md`（7角色评审，9条建议采纳）

### 阶段概览

| # | 阶段 | 主导 | 评审人 | 可选 | 门禁 |
|---|------|------|--------|------|------|
| P1 | 需求分析 | pm | arch+test+sec+ui | ❌ | 验收标准可量化 |
| P2 | 架构设计 | arch | pm+sec+infra | ❌ | 加权共识≥70% |
| P3 | 技术设计 | arch+coder | coder+test | ❌ | API规范无歧义 |
| P4 | 数据设计 | arch+coder | arch+sec | ✅ | 3NF或反范式有据 |
| P5 | 交互设计 | ui | pm+test+sec | ✅ | 核心流程可用性验证通过 |
| P6 | 安全评审 | sec | arch+infra | ✅ | 无P0/P1漏洞、合规全绿 |
| P7 | 测试计划 | test | arch+sec+infra+pm | ❌ | 测试计划评审通过 |
| P8 | 开发实现 | coder | arch+sec+test+coder | ❌ | 代码审查通过、无P0缺陷 |
| P9 | 测试执行 | test | arch+pm+sec+infra | ❌ | 覆盖率≥80%+P7计划100%执行 |
| P10 | 部署发布 | infra | arch+sec+test | ❌ | 部署演练通过 |
| P11 | 运维保障 | infra+sec | arch+infra | ✅ | P99<目标值、告警100% |

### 依赖图

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

### 生命周期模板

| 模板 | 阶段 | 适用场景 |
|------|------|---------|
| `full` | P1-P11全部 | 完整项目 |
| `backend` | 无P5 | 后端服务 |
| `frontend` | 无P4,P6 | 前端应用 |
| `internal_tool` | 无P4,P5,P6,P11 | 内部工具 |
| `minimal` | P1,P3,P7,P8,P9 | 最小集 |

### 门禁机制

- **强制执行**：每个阶段门禁必须检查
- **不达标不阻塞**：生成差距报告（差距项+原因分析），由用户决定是否推进
- **留痕**：所有门禁结果记录到检查点

### 需求变更流程

```
变更发起(pm/user) → 影响分析(arch+sec+test) → 变更评审(全角色) → 批准/驳回(pm+arch) → 回退到受影响阶段
```

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
#   "version": "3.4.0",
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

## 交付工作流铁律（⚠️ 每次推进后必须执行）

> 本节定义「推进→测试→走读→注释→文档→Git」的标准闭环流程。**违反任何一步都是严重错误。**

### 铁律：推进后的必做闭环

```
推进实现 → 测试验证(全量回归) → 代码走读 → 注释补全 → 文档更新 → Git推送
```

**每一步的强制要求**：

| 步骤 | 强制动作 | 验证标准 |
|------|---------|---------|
| **1. 推进实现** | 按 Plan/Spec 编写/修改代码 | 功能完整，无 TODO 占位 |
| **2. 测试验证** | 新增测试 + 全量回归 | 0 failure, 0 error, 100% pass |
| **3. 代码走读** | 逐文件阅读新增/修改的每一行 | 理解每个方法的输入输出和边界行为 |
| **4. 注释补全** | 公共方法 docstring (Args/Returns) + 关键逻辑行内注释 | 无"裸方法"(无docstring的public method) |
| **5. 文档更新** | **全量相关文档同步**（见下方「文档覆盖清单」） | 所有文档版本号/模块数/测试数一致，无过时内容 |
| **6. 清理收尾** | 删除过程文档/临时文档/临时代码 | 无残留的 `_tmp`/`_draft`/`_old` 文件 |
| **7. Git 推送** | commit message 含版本号+变更摘要+测试数 | push 成功，remote 可见 |

### 铁律：文档覆盖清单（⚠️ 步骤 5 必须检查以下全部类别）

> **原则：与变更相关的需求/设计/测试/API/安装依赖/SKILL 各类文档，只要相关都要更新。**

| 文档类别 | 检查项 | 本次变更是否涉及 |
|----------|--------|-----------------|
| **需求文档** | `docs/spec/*.md` — 规格说明书状态更新 (待评审→实现中→已实现) | ✅ 必查 |
| **设计文档** | `docs/architecture/*.md` — 架构演进记录、Phase 追加 | ✅ 必查 |
| **规划文档** | `docs/planning/*.md` — 共识决议 action items 勾选、扩展说明 | ✅ 必查 |
| **SKILL 文档** | `SKILL.md` — 模块表、测试表、版本历史、规则 | ✅ 必查 |
| **项目概览** | `README.md` (EN) / `README-CN.md` (中文) / `README-JP.md` (日本語) — 版本号、模块表、时间线 | ✅ 必查 |
| **变更日志** | `CHANGELOG.md` — 新版本条目 (Added/Changed/Fixed) | ✅ 必查 |
| **状态文档** | `IMPLEMENTATION_STATUS.md` — 当前版本、模块清单、测试汇总 | ✅ 必查 |
| **配置文档** | `CONFIGURATION.md` — 新增外部集成配置选项 | 🔍 有集成时必更 |
| **API 文档** | 如有 API 变更则更新对应接口文档 | 🔍 有 API 变更时必更 |
| **安装依赖** | `INSTALL.md` / `requirements.txt` — 有新依赖时更新 | 🔍 有新依赖时必更 |
| **测试计划** | 测试用例文档反映新增测试覆盖范围 | 🔍 大幅变更时建议更新 |

### 铁律：清理收尾规则（⚠️ 步骤 6）

> **原则：过程文档和临时产物不应留在代码库中。**

| 清理类别 | 处理方式 | 示例 |
|----------|---------|------|
| 过程性分析脚本 | 保留有价值的，删除一次性用途的 | `*_review.py`, `*_analysis.py` → 评估后决定 |
| 临时调试文件 | **必须删除** | `test_*.py.tmp`, `debug_*.py`, `*_bak.*` |
| 草稿/废弃文档 | **必须删除** | `*_DRAFT.md`, `*_old.md`, `*_tmp.md` |
| 未使用的占位代码 | **必须删除** 或替换为真实实现 | `pass # TODO`, `raise NotImplementedError` |
| 重复/冗余文件 | 合并或删除 | 多个版本的同一文档只保留最新版 |

**Annotation Standards (Language Separation)**:
- **Documentation (SKILL.md / README.md)**: Use **English**
- **README-CN.md**: Use **Chinese** (中文简体)
- **README-JP.md**: Use **Japanese** (日本語)
- **Code docstring**: Use **English** (Args / Returns / Example)
- **Inline comments**: Use **English** (explaining business logic)

---

## 测试覆盖

| 模块 | 测试数 | 质量评分 | 状态 |
|------|--------|---------|------|
| Core Tests (Dispatcher+Coordinator+Worker+Scratchpad+Consensus) | 39 | ✅ | ✅ PASS |
| Role Mapping (RoleMatcher+别名解析) | 25 | ✅ | ✅ PASS |
| Upstream (Checkpoint+SemanticMatcher+Workflow+CompletionChecker) | 35 | ✅ | ✅ PASS |
| MCEAdapter (CarryMem集成+类型映射+优雅降级) | 30 | ✅ | ✅ PASS |
| Contract Tests (Protocols+NullProviders+Cache+Monitor+Security) | 234 | ✅ | ✅ PASS |
| V3.5 Integration (Lifecycle+ChangeRequest+Templates) | 7 | ✅ | ✅ PASS |
| **总计** | **560+** | **✅ ALL PASS** | |

---

## Version History

- **v3.4.0** (2026-05-02): 11阶段项目全生命周期（full/backend/frontend/internal_tool/minimal模板）+ 需求变更管理 + 门禁机制+差距报告 + WorkflowEngine生命周期支持 + 自然语言规则收集(RuleCollector) + 560+测试通过
- **v3.3** (2026-04-24): 7核心角色(security+devops提升为核心) + RoleRegistry SSOT + TaskDefinition.role_prompt修复 + 环境变量唯一API key入口 + InputValidator输入验证 + 3个真实场景验证通过
- **v3.3** (2026-04-17): WorkBuddy Claw集成 + MCE v0.4支持 + 注释EN化 + 多语言README
- **v3.2** (2026-04-17): MVP Three Lines - E2E Full Demo(10-step flow/CLI) + Dispatcher UX Enhancement(structured/compact/detailed 3-format report) + MCEAdapter Memory Classification Adapter(lazy-load/graceful-degrade) + Delivery Workflow Iron Rule (walkthrough→annotate→docs→Git loop)
- **v3.1** (2026-04-16): Prompt Optimization System - Dynamic Prompt Assembly(3 variants) + Skillify Closed-loop Feedback(A/B promotion) + Compression-Aware Adaptation
- **v3.0.1** (2026-04-16): 代码注释全面补全(6大核心模块docstring 100%覆盖) + TestQualityGuard测试质量审计系统集成
- **v3.0** (2026-04-16): 完整重构为 Coordinator/Worker/Scratchpad 协作架构，11大模块（含Dispatcher+TestQualityGuard），~710测试全通过
- **v2.5** (2026-04-06): Memory Classification Engine 集成
- **v2.4** (2026-04-01~03): Vibe Coding + 核心规则 + 生命周期识别
- **v2.3** (2026-03-28): 多角色代码走读 + 3D可视化
- **v2.2** (2026-03-21): 长程 Agent (Checkpoint + Handoff)
- **v2.1** (2026-03-17): 双层上下文 + AI语义匹配
- **v2.0/v1.0** (2026-03-16): 初始版本
