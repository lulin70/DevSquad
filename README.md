# TraeMultiAgentSkill v3

基于 Claude Code Coordinator 模式的 **多 Agent 协作平台**，从单分发工具演进为有记忆的学习型协作系统。

## v3 核心架构总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                    TraeMultiAgentSkill v3                          │
│                                                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────┐ │
│  │Coordinator│←→│Compressor│←→│   Guard  │←→│ Skillify │←→│Warmup │ │
│  │ 协调器    │  │ 压缩器    │  │ 权限守卫  │  │ 技能生成  │  │预热   │ │
│  └────┬─────┘  └──────────┘  └──────────┘  └────┬─────┘  └───┬───┘ │
│       │                                      │            │       │
│       ▼                                      ▼            ▼       │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                  MemoryBridge (记忆桥接)                      │   │
│  │  recall() ← capture() ← persist() ← search()             │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │              PromptRegistry (提示词注册表)                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

## v3 模块一览

| Phase | 模块 | 文件 | 测试数 | 功能 |
|-------|------|------|--------|------|
| Entry | **MultiAgentDispatcher** | dispatcher.py | **54** | 统一调度入口，一键完成全流程协作 |
| P1 | **Coordinator** | coordinator.py | (E2E) | 多Agent协调、任务规划、执行、报告 |
| P1 | **Scratchpad** | scratchpad.py | (E2E) | 共享黑板、Worker间信息交换 |
| P1 | **Worker** | worker.py | (E2E) | 工作者执行具体任务 |
| P1 | **ConsensusEngine** | consensus.py | (E2E) | 共识机制、投票决策 |
| P1 | **BatchScheduler** | batch_scheduler.py | (E2E) | 并行/串行混合调度 |
| P1-b | **ContextCompressor** | context_compressor.py | **72** | 3级上下文压缩(L1/L2/L3) |
| P2-a | **PermissionGuard** | permission_guard.py | **105** | 4级权限模型+AI分类器+审计日志 |
| P2-b | **Skillifier** | skillifier.py | **96** | 执行记录→模式提取→技能自动生成 |
| P3 | **WarmupManager** | warmup_manager.py | **103** | L1同步+L2异步+LAZY懒加载+进程缓存 |
| P4 | **MemoryBridge** | memory_bridge.py | **96** | 记忆召回/捕获/反馈闭环/模式持久化 |
| QA | **TestQualityGuard** | test_quality_guard.py | **42** | API签名校验+反模式检测+维度覆盖审计 |
| **合计** | — | — | **~710** | — |

## 快速开始

### 基础导入

```python
from scripts.collaboration import (
    # 核心协作组件
    Coordinator, Scratchpad, Worker,
    ConsensusEngine, BatchScheduler,

    # Phase 1-b: 上下文压缩
    ContextCompressor, CompressionLevel,

    # Phase 2-a: 权限守卫
    PermissionGuard, ProposedAction, PermissionLevel,

    # Phase 2-b: 技能生成
    Skillifier, ExecutionRecord, SuccessPattern,

    # Phase 3: 启动优化
    WarmupManager, WarmupConfig,

    # Phase 4: 记忆桥接
    MemoryBridge, MemoryConfig as MemCfg, MemoryType,
)

# 创建协作系统
scratchpad = Scratchpad()
coordinator = Coordinator(scratchpad=scratchpad)

# 规划任务（多角色）
plan = coordinator.plan_task(
    "设计用户认证系统",
    [{"role_id": "architect"}, {"role_id": "product-manager"}]
)
print(f"任务数: {plan.total_tasks}")

# 启动预热（加速后续操作）
wm = WarmupManager.instance(WarmupConfig.default())
report = wm.warmup()
print(f"预热完成: {report.completed}/{report.total_tasks} 任务")

# 权限检查
guard = PermissionGuard()
action = ProposedAction(
    action_type=ActionType.FILE_WRITE,
    target="/etc/config",
    description="修改系统配置"
)
decision = guard.check(action)
print(f"权限决定: {decision.outcome}")

# 技能学习
skillifier = Skillifier()
record = ExecutionRecord(
    task_description="实现CRUD接口",
    success=True,
    worker_id="dev-worker",
    steps=[],
)
skillifier.record_execution(record)
patterns = skillifier.analyze_history()
print(f"发现模式: {len(patterns)} 个")

# 记忆桥接
bridge = MemoryBridge()
result = bridge.recall(MemoryQuery(query_text="微服务架构"))
print(f"召回记忆: {result.total_found} 条")
```

### 环境变量配置

```bash
# WarmupManager 预热模式
export WARMUP_MODE=FAST        # 最小预热 (~20ms)
export WARMUP_MODE=FULL        # 全量预热
export WARMUP_MODE=DISABLED     # 禁用预热
```

## 各模块详细用法

### 1. Coordinator 多 Agent 协调

```python
from scripts.collaboration import Coordinator, Scratchpad

scratchpad = Scratchpad()
coord = Coordinator(scratchpad=scratchpad)

# 规划任务
plan = coord.plan_task("开发REST API", [
    {"role_id": "architect"},
    {"role_id": "solo-coder"},
])

# 生成执行计划
workers = coord.spawn_workers(plan)
result = coord.execute_plan(plan)
report = coord.generate_report()
```

### 2. ContextCompressor 上下文压缩

```python
from scripts.collaboration import ContextCompressor, CompressionLevel

compressor = ContextCompressor()

# L1 轻度压缩（去重+摘要）
compressed_l1 = compressor.compress(messages, level=CompressionLevel.L1)

# L2 中度压缩（结构化+关键保留）
compressed_l2 = compressor.compress(messages, level=CompressionLevel.L2)

# L3 深度压缩（语义+核心要点）
compressed_l3 = compressor.compress(messages, level=CompressionLevel.L3)
```

### 3. PermissionGuard 权限守卫

```python
from scripts.collaboration import (
    PermissionGuard, ProposedAction, ActionType, PermissionLevel
)

guard = PermissionGuard()

# 设置权限级别
guard.set_level(PermissionLevel.AUTO)  # PLAN / DEFAULT / AUTO / BYPASS

# 添加自定义规则
from scripts.collaboration import PermissionRule
guard.add_rule(PermissionRule(
    rule_id="allow-test-dir",
    pattern="glob:/tmp/**",
    action_types=[ActionType.FILE_WRITE, ActionType.FILE_READ],
    effect="ALLOW",
))

# 检查操作
action = ProposedAction(
    action_type=ActionType.SHELL_EXECUTE,
    target="rm -rf /important",
    description="危险删除操作"
)
decision = guard.check(action)
print(f"结果: {decision.outcome}, 风险分: {decision.risk_score:.2f}")

# 审计日志
log = guard.get_audit_log()
report = guard.get_security_report()
print(f"安全报告: {report}")
```

### 4. Skillifier 技能自动生成

```python
from scripts.collaboration import Skillifier, ExecutionRecord, ExecutionStep

skillifier = Skillifier()

# 记录成功执行
record = ExecutionRecord(
    task_description="实现用户登录API",
    success=True,
    worker_id="backend-dev",
    role_id="solo-coder",
    steps=[
        ExecutionStep(step_order=1, action_type="design", target="auth/models.py",
                        outcome="completed", duration_ms=500),
        ExecutionStep(step_order=2, action_type="implement", target="auth/views.py",
                        outcome="completed", duration_ms=1200),
        ExecutionStep(step_order=3, action_type="test", target="tests/test_auth.py",
                        outcome="completed", duration_ms=800),
    ],
    artifacts=["models.py", "views.py", "test_auth.py"],
)
skillifier.record_execution(record)

# 分析历史 → 提取模式
patterns = skillifier.analyze_history()
for p in patterns:
    print(f"模式: {p.name}, 置信度: {p.confidence:.2f}, 频率: {p.frequency}")

# 生成技能提案
if patterns:
    proposal = skillifier.generate_skill(patterns[0])
    print(f"技能提案: {proposal.name}, 质量分: {proposal.quality_score}")
    
    # 质量验证
    validation = skillifier.validate_skill(proposal)
    print(f"验证等级: {validation.grade}, 分数: {validation.score:.1f}")
```

### 5. WarmupManager 启动优化

```python
from scripts.collaboration import WarmupManager, WarmupConfig, WarmupLayer

# 三种配置模式
config_fast = WarmupConfig.fast()      # 最小预热
config_default = WarmupConfig.default()  # 平衡模式
config_full = WarmupConfig.full()     # 全量预热

wm = WarmupManager.instance(config_default)

# 分层预热
report = wm.warmup(layers=[WarmupLayer.EAGER])  # 仅 L1 同步 (~15ms)
# 或全量预热
full_report = wm.warmup()                   # L1 + L2 + LAZY

# 缓存操作
wm.set_cache("my_key", {"data": "value"})
value = wm.get("my_key")

# 懒加载
result = wm.get_or_load("expensive_key", lambda: heavy_computation())

# 性能诊断
print(wm.print_diagnostics())
metrics = wm.get_metrics()
print(f"启动耗时: {metrics.startup_time_ms:.1f}ms")

# 基准测试
bench = wm.benchmark(iterations=5)
print(f"P95延迟: {bench['p95_ms']:.1f}ms")
```

### 6. MemoryBridge 记忆桥接

```python
from scripts.collaboration import (
    MemoryBridge, MemoryConfig, MemoryQuery, MemoryType,
    KnowledgeItem, UserFeedback, EpisodicMemory, ErrorContext
)

bridge = MemoryBridge(config=MemoryConfig.default())

# === 写入 ===

# 1. 写入知识
bridge.writer.write_knowledge(KnowledgeItem(
    id="kw-redis", domain="缓存", title="Redis缓存策略",
    content="缓存穿透：布隆过滤器\n击穿：互斥锁重构\n雪崩：随机过期时间",
    tags=["Redis", "缓存", "分布式"],
))

# 2. 记录执行洞察（从 Scratchpad FINDING 自动捕获）
class FakeFinding:
    entry_type = "FINDING"
    content = "发现N+1查询问题，建议引入缓存层"
    confidence = 0.9

record = type('obj', (object,), {
    'task_description': '性能优化', 'worker_id': 'architect'
})()
bridge.capture_execution(record, [FakeFinding()])

# 3. 记录用户反馈
fb = UserFeedback(id="fb1", feedback_type="suggestion",
                 content="希望增加更多计算类型支持", rating=5)
bridge.record_feedback(fb)

# 4. 从错误中学习
ctx = ErrorContext(error_message="ConnectionTimeoutError: DB连接超时",
                    task_description="批量导入数据")
bridge.learn_from_mistake(ctx)

# 5. 持久化 Skillifier 模式
class GoodPattern:
    name = "CRUD Generator"
    steps_template = [{"step": 1, "action": "analyze"}]
    trigger_keywords = ["CRUD", "增删改查"]
    confidence = 0.88
    quality_score = 90

bridge.persist_pattern(GoodPattern())

# === 读取 ===

# 召回相关记忆
result = bridge.recall(MemoryQuery(
    query_text="微服务架构设计",
    limit=5,
    min_relevance=0.3
))
for mem in result.memories:
    print(f"[{mem.memory_type.value}] {mem.title}: {mem.content[:60]}...")
    print(f"  相关度: {mem.relevance_score:.2f}")

# 关键词搜索知识库
items = bridge.search_knowledge(["Redis", "缓存"])
for item in items:
    print(f"[{item.domain}] {item.title}: {item.content[:50]}...")

# 统计面板
stats = bridge.get_statistics()
print(f"总记忆数: {stats.total_memories}")
print(f"按类型: {stats.by_type_counts}")
print(bridge.print_diagnostics())

# 生命周期管理
print(f"遗忘权重(7天): {bridge.forgetting_weight(new_memory):.2f}")
print(f"遗忘权重(60天): {bridge.forgetting_weight(old_memory):.2f}")

# 清理过期记忆
removed = bridge.cleanup_expired_memories()
print(f"清理了 {removed} 条过期记忆")
```

## 运行测试

```bash
# 全量回归测试 (9套件, ~710 cases)
cd /Users/lin/trae_projects/TraeMultiAgentSkill

# 单套件运行
python3 scripts/collaboration/dispatcher_test.py          # 54 cases
python3 scripts/collaboration/test_quality_guard_test.py  # 42 cases
python3 scripts/collaboration/memory_bridge_test.py       # 96 cases
python3 scripts/collaboration/warmup_manager_test.py       # 103 cases
python3 scripts/collaboration/skillifier_test.py           # 96 cases
python3 scripts/collaboration/permission_guard_test.py     # 105 cases
python3 scripts/collaboration/context_compressor_test.py   # 72 cases
python3 scripts/collaboration/enhanced_e2e_test.py         # 96+46 cases

# 全量一键运行
echo "=== FULL REGRESSION ===" && \
python3 scripts/collaboration/dispatcher_test.py 2>&1 | tail -3 && \
python3 scripts/collaboration/test_quality_guard_test.py 2>&1 | tail -3 && \
python3 scripts/collaboration/memory_bridge_test.py 2>&1 | tail -3 && \
python3 scripts/collaboration/warmup_manager_test.py 2>&1 | tail -3 && \
python3 scripts/collaboration/skillifier_test.py 2>&1 | tail -4 && \
python3 scripts/collaboration/permission_guard_test.py 2>&1 | tail -4 && \
python3 scripts/collaboration/context_compressor_test.py 2>&1 | tail -3 && \
python3 scripts/collaboration/enhanced_e2e_test.py 2>&1 | tail-4
```

**最新测试结果**: `~710/~710 ALL PASSED ✅`

| 套件 | 用例数 |
|------|--------|
| Dispatcher (Entry) | 54 |
| TestQualityGuard (QA) | 42 |
| MemoryBridge (P4) | 96 |
| WarmupManager (P3) | 103 |
| Skillifier (P2-b) | 96 |
| PermissionGuard (P2-a) | 105 |
| ContextCompressor (P1-b) | 72 |
| Enhanced E2E (P1) | ~142 |
| **合计** | **~710** |

## 项目结构

```
TraeMultiAgentSkill/
├── scripts/
│   └── collaboration/           # ★ v3 核心模块
│       ├── __init__.py           # 统一导出 (81+ 公共符号)
│       ├── models.py             # 数据模型 (EntryType/TaskDefinition/...)
│       ├── dispatcher.py         # ★ V3统一调度入口 (MultiAgentDispatcher)
│       ├── scratchpad.py         # 共享黑板
│       ├── worker.py             # 工作者
│       ├── consensus.py          # 共识引擎
│       ├── coordinator.py        # 协调器
│       ├── batch_scheduler.py    # 批处理调度
│       ├── context_compressor.py # 上下文压缩 (P1-b)
│       ├── permission_guard.py   # 权限守卫 (P2-a)
│       ├── skillifier.py         # 技能生成 (P2-b)
│       ├── warmup_manager.py     # 启动预热 (P3)
│       ├── memory_bridge.py      # 记忆桥接 (P4)
│       ├── test_quality_guard.py # 测试质量审计 (QA)
│       │
│       └── *_test.py             # 对应测试文件
│
├── prompts/
│   └── registry.py             # PromptRegistry 提示词注册表
│
├── data/
│   └── memory-bank/            # 持久化记忆存储
│       ├── knowledge_base/     # 领域知识库
│       ├── analysis_cases/     # 分析案例 (5-Why)
│       ├── user_experience/    # 用户反馈
│       ├── prompt_evolution/   # 提示词进化
│       └── persisted_patterns/ # 已持久化的技能模式
│
├── docs/
│   ├── architecture/           # 架构设计文档
│   │   ├── v3-upgrade-proposal.md      # v3 升级路线图
│   │   ├── v3-phase2-permission-design.md   # P2-a 设计
│   │   ├── v3-phase2-skillify-design.md     # P2-b 设计
│   │   ├── v3-phase3-warmup-design.md        # P3 设计
│   │   └── v3-phase4-memorybridge-design.md  # P4 设计
│   │
│   ├── product-manager/        # PM 用户故事
│   │   ├── USER_STORIES_P2.md     # P2 用户故事
│   │   ├── USER_STORIES_P2b.md    # P2-b 用户故事
│   │   ├── USER_STORIES_P3.md     # P3 用户故事
│   │   └── USER_STORIES_P4.md     # P4 用户故事
│   │
│   └── test-expert/            # Tester 测试计划
│       ├── TEST_PLAN_P2.md       # P2 测试计划
│       ├── TEST_PLAN_P2b.md      # P2-b 测试计划
│       ├── TEST_PLAN_P3.md       # P3 测试计划
│       └── TEST_PLAN_P4.md       # P4 测试计划
│
└── README.md                    # 本文件
```

## v3 开发历程

| 时间 | Phase | 模块 | 核心能力 | 测试 |
|------|-------|------|---------|------|
| v3.0 | P1 | Coordinator+基础协作 | 多Agent协调/共识/批调度 | E2E 96 |
| v3.0 | Entry | MultiAgentDispatcher | 统一调度入口/一键协作 | 54 |
| v3.1 | P1-b | ContextCompressor | 3级上下文压缩 | 72 |
| v3.2 | P2-a | PermissionGuard | 4级权限+AI分类+审计 | 105 |
| v3.3 | P2-b | Skillifier | 成功模式提取→技能生成 | 96 |
| v3.4 | P3 | WarmupManager | 分层异步预热+进程缓存 | 103 |
| v3.5 | P4 | MemoryBridge | 记忆召回/捕获/持久化 | 96 |
| v3.6 | QA | TestQualityGuard | API校验/反模式检测/维度审计 | 42 |
| **v3.6** | **Doc** | **注释补全** | **6大核心模块docstring全覆盖** | **—** |
| **v3.6** | **—** | **—** | **~710 全通过** | **~710** |

## 设计原则

本项目遵循 **文档先行** 的开发流程：

1. **需求分析** → 设计文档 (9章架构设计)
2. **PM 角色** → 用户故事 (12~13 故事, 54~68 AC)
3. **Tester 角色** → 测试计划 (~91~108 用例)
4. **达成共识** → 用户审批
5. **实现** → 核心代码 (~480~620 行/模块)
6. **测试** → 测试用例 (~96~105 cases/模块)
7. **集成** → __init__.py + 全量回归
8. **推送** → Git commit + push

## License

MIT License

Copyright (c) 2026 Weiransoft
