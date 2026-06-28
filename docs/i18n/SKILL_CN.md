---
name: devsquad
slug: devsquad
description: |
  V3.9.2 DevSquad — Enterprise 多角色 AI 任务编排器。
  一个任务输入，多角色 AI 协作，一个结论输出。
  7 个核心角色（架构师/产品经理/安全专家/测试专家/开发工程师/DevOps/UI 设计师），
  真实 LLM 后端（OpenAI/Anthropic/MOKA AI），CLI + MCP + Python API + REST API + Web Dashboard。
  ThreadPoolExecutor 并行、CheckpointManager、WorkflowEngine、流式输出、Docker、CI。
  V3.9.2: 自动 LLM 后端回退 + Dashboard 拆分 + SQLite 审计持久化 + P3 清理,
  118 核心模块, 2703+ 测试通过 (CI 权威).
---

# DevSquad V3.9.2 — 多角色 AI 任务编排器（企业级就绪）

## 🎯 一句话理解（3 秒）

**DevSquad = 把「单个 AI 助手」升级成「7 人 AI 专业团队」**

```
传统 AI:  你 ──→ ChatGPT ──→ 一个回答（可能不全面）
DevSquad:  你 ──→ DevSquad ──→ [架构师+安全+测试+开发...] ──→ 多维度共识结论
```

## 核心定位

本技能将 Trae 从"单一 AI 助手"升级为"多 AI 团队"。当任务提交后，不再由单一角色处理：

```
用户任务 → [InputValidator 输入验证] → [RoleMatcher 角色匹配] → [Coordinator 编排协调]
         → [ThreadPoolExecutor 并行 Worker] → [Scratchpad 实时共享]
         → [ConsensusEngine 共识决策] → [ReportFormatter 报告生成] → [结构化报告]
```

## 架构概览（118+ 核心模块）

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | 统一调度入口点（集成所有模块） |
| 1 | **Coordinator** | `coordinator.py` | 全局编排器：分解任务、分配 Worker、收集结果、解决冲突 |
| 2 | **Scratchpad** | `scratchpad.py` | 共享黑板，Worker 间实时信息交换 |
| 3 | **Worker** | `worker.py` | 执行者：每个角色一个实例，独立执行并写入 Scratchpad |
| 4 | **ConsensusEngine** | `consensus.py` | 共识引擎：加权投票 + 否决权 + 升级机制 |
| 5 | **BatchScheduler** | `batch_scheduler.py` | 并行/顺序混合调度，自动安全检查 |
| 6 | **ContextCompressor** | `context_compressor.py` | 4 级上下文压缩（NONE/SNIP/SESSION_MEMORY/FULL_COMPACT） |
| 7 | **PermissionGuard** | `permission_guard.py` | 4 级权限守卫（PLAN/DEFAULT/AUTO/BYPASS） |
| 8 | **Skillifier** | `skillifier.py` | 从成功操作模式自动生成新技能 |
| 9 | **WarmupManager** | `warmup_manager.py` | 3 层启动预热（EAGER/ASYNC/LAZY）+ 进程级缓存 |
| 10 | **MemoryBridge** | `memory_bridge.py` | 7 类记忆桥接 + 倒排索引 + TF-IDF + 遗忘曲线 + MCE+Claw 集成 |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | 测试质量审计（API 验证 / 反模式检测 / 维度覆盖） |
| 12 | **PromptAssembler** | `prompt_assembler.py` | 动态 Prompt 组装（复杂度检测 / 3 种变体 / 5 种风格 / 压缩感知 / QC 配置注入 / 用户规则注入） |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | Skillify 闭环反馈（模式→变体 / A-B 测试 / 自动升降级） *(已移除)* |
| 14 | **MCEAdapter** | `mce_adapter.py` | CarryMem 集成适配器（优先 DevSquadAdapter，懒加载 / 优雅降级 / 线程安全 / match_rules + format_rules_as_prompt + add_rule） |
| 15 | **WorkBuddyClawSource** | `memory_bridge.py` (类) | WorkBuddy Claw 只读桥接（INDEX 搜索 / 日志 / AI 资讯流） |
| 16 | **RoleMatcher** | `role_matcher.py` | 基于关键词的角色匹配，支持别名解析（从 Dispatcher 提取） |
| 17 | **ReportFormatter** | `report_formatter.py` | 结构化/紧凑/详细报告生成（从 Dispatcher 提取） |
| 18 | **InputValidator** | `input_validator.py` | 安全验证 + 40种检测模式 |
| 19 | **RuleCollector** | `rule_collector.py` | 自然语言规则收集（意图检测 / 规则提取 / 清洗 / CarryMem+JSON 存储 / Prompt 注入防护） |
| 20 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM 驱动的语义角色匹配，双语关键词兜底 |
| 21 | **CheckpointManager** | `checkpoint_manager.py` | SHA256 完整性校验、交接文档、自动清理、调度集成 |
| 22 | **WorkflowEngine** | `workflow_engine.py` | 任务→工作流自动拆分、步骤执行、检查点恢复、Agent 交接、11 阶段生命周期模板 |
| 23 | **TaskCompletionChecker** | `task_completion_checker.py` | DispatchResult/ScheduleResult 完成追踪 + 进度持久化 |
| 24 | **CodeMapGenerator** | `code_map_generator.py` | 基于 Python AST 的代码结构分析 + 依赖图 |
| 25 | **DualLayerContextManager** | `dual_layer_context.py` | 项目级 + 任务级上下文管理，带 TTL |
| 26 | **SkillRegistry** | `skill_registry.py` | 可复用技能注册 + 发现 + 持久化 |
| 27 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic，支持流式输出 + 120s 超时 |
| 28 | **ConfigManager** | `config_loader.py` | *(V3.7.2 已移除)* 死代码 — 零引用 |
| 29 | **Protocols** | `protocols.py` | Protocol 接口（CacheProvider/RetryProvider/MonitorProvider/MemoryProvider + match_rules/format_rules_as_prompt）+ 异常层级 |
| 30 | **NullProviders** | `null_providers.py` | 所有 Protocol 接口的空操作实现（含 match_rules/format_rules_as_prompt，降级 + 测试模拟） |
| 31 | **EnhancedWorker** | `enhanced_worker.py` | 支持 Protocol 注入的 Worker（缓存/重试/监控/简报/记忆）+ 规则注入流水线 |
| 32 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99 响应时间、CPU/内存追踪、瓶颈检测、Markdown 报告 |
| 33 | **AgentBriefing** | `agent_briefing.py` | 上下文感知简报生成，带优先级过滤 + 持久化 |
| 34 | **ConfidenceScorer** | `confidence_score.py` | 5 因子置信度评分（完整性/确定性/具体性/一致性/模型质量） |
| 35 | **RoleTemplateMarket** | `role_template_market.py` | *(已移除)* 幽灵功能 — 生产环境从未使用 |
| 36 | **LLMCache** | `llm_cache.py` | 基于 TTL 的 LRU 缓存，磁盘持久化（降低 60-80% 成本） |
| 37 | **LLMRetry** | `llm_retry.py` | 指数退避 + 断路器 + 多后端降级 |
| 38 | **UsageTracker** | `usage_tracker.py` | Token/成本使用量追踪与报告 |
| 39 | **Models** | `models.py` | 共享数据模型和类型定义 |
| 40 | **ConfigManager (YAML)** | `config_manager.py` | 项目级 YAML 配置管理 |
| 41 | **LLMCacheAsync** | `llm_cache_async.py` | 异步 LLM 缓存，用于并发负载 |
| 42 | **LLMRetryAsync** | `llm_retry_async.py` | 异步 LLM 重试，带退避策略 |
| 43 | **IntegrationExample** | `integration_example.py` | DevSquad 集成示例代码 |
| 44 | **AsyncIntegrationExample** | `async_integration_example.py` | 异步 DevSquad 集成示例 |
| 45 | **AntiRationalizationEngine** | `anti_rationalization.py` | 按角色的借口→反驳表（8 条通用 + 6-7 条角色专属），通过 PromptAssembler 注入以防止质量偷工减料 |
| 46 | **VerificationGate** | `verification_gate.py` | 强制证据要求 + 7 个红旗检测 + Prove-It 模式（完成声明验证） |
| 47 | **IntentWorkflowMapper** | `intent_workflow_mapper.py` | 用户意图→工作流链映射（6 种意图 × 3 种语言），带门控要求和防跳过提示 |
| 48 | **CLI Lifecycle Commands** | `cli.py` | 6 个生命周期快捷命令（spec/plan/build/test/review/ship），预设角色/模式/门控，灵感来自 Agent Skills |
| 49 | **StandardizedRoleTemplate** | `standardized_role_template.py` | V2 模板格式，含 SKILL.md 解剖：概述、适用场景、流程步骤、合理化借口、红旗、验证要求 |
| 50 | **OperationClassifier** | `operation_classifier.py` | 三层操作分类（ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN），20+ 预定义操作 + 自定义覆盖 |
| 51 | **OutputSlicer** | `output_slicer.py` | 大响应增量输出切片：可配置切片大小、头部信息、Scratchpad 集成 |
| 52 | **FiveAxisConsensusEngine** | `five_axis_consensus.py` | 五轴评审共识（正确性/可读性/架构/安全性/性能），加权投票和严格模式 |
| 53 | **CIFeedbackAdapter** | `ci_feedback_adapter.py` | CI 结果解析器（pytest/coverage/lint/build）+ 上下文生成器 + 调度流水线 Prompt 注入 |
| 54 | **LifecycleProtocol** | `lifecycle_protocol.py` | 统一生命周期管理的抽象接口（SHORTCUT/FULL/CUSTOM 模式），支持 11 阶段 |
| 55 | **UnifiedGateEngine** | `unified_gate_engine.py` | 统一门控引擎，集成 VerificationGate + LifecycleProtocol 门控，可插拔检查器 |
| 56 | **CheckpointManager (Enhanced)** | `checkpoint_manager.py` | 扩展生命周期状态持久化：跨会话保存/恢复/列表/删除生命周期状态 |
| 57 | **ShortcutLifecycleAdapter** | `lifecycle_protocol.py` (类) | Plan C 适配器，使用 CLI 6 命令快捷方式实现 LifecycleProtocol，自动状态持久化 |
| 58 | **AuthManager** | `auth.py` | 认证与授权：多用户 RBAC、SHA-256 密码哈希、Streamlit 登录界面、OAuth2 支持 |
| 59 | **APIServer** | `api_server.py` | FastAPI REST API 服务器：OpenAPI/Swagger 文档、CORS 中间件、请求计时、10+ 端点 |
| 60 | **APIDataModels** | `api/models.py` | Pydantic 验证模型：LifecyclePhase、GateResult、MetricsSnapshot、PhaseActionRequest/Result |
| 61 | **LifecycleAPIRoutes** | `api/routes/lifecycle.py` | REST API 端点：阶段列表/详情、状态、动作执行、命令映射 |
| 62 | **MetricsGatesAPIRoutes** | `api/routes/metrics_gates.py` | API 端点：当前/历史指标、门控状态/检查、健康检查 |
| 63 | **AlertManager** | `alert_manager.py` | *(V3.7.0 已移除)* 多渠道告警模块因未使用已被移除 |
| 64 | **DispatchModels** | `dispatch_models.py` | DispatchResult + I18N + ROLE_TEMPLATES（从 dispatcher 提取） |
| 65 | **DispatchPerformance** | `dispatch_performance.py` | 调度流水线 PerformanceMonitor（从 dispatcher 提取） |
| 66 | **MultiLevelCache** | `multi_level_cache.py` | 多级缓存协调器（内存→磁盘→Redis） |
| 67 | **HistoryManager** | `history_manager.py` | SQLite 时序存储：指标快照、告警历史、API 日志、生命周期事件 |
| 68 | **StreamlitDashboard** | `dashboard.py` | 交互式 Web 仪表盘，带认证、实时监控、阶段可视化 |
| 69 | **FeedbackControlLoop** | `feedback_control_loop.py` | Sense→Decide→Act→Feedback 闭环迭代，持续改进 |
| 70 | **ExecutionGuard** | `execution_guard.py` | 实时中止守卫（超时/输出/关键词），保障安全执行 |
| 71 | **PerformanceFingerprint** | `performance_fingerprint.py` | 统一性能指纹，TF-IDF 相似度搜索用于任务匹配 |
| 72 | **SimilarTaskRecommender** | `similar_task_recommender.py` | 基于历史的任务配置推荐，使用性能数据 |
| 73 | **AdaptiveRoleSelector** | `adaptive_role_selector.py` | 成功率驱动的自适应角色选择，优化团队组合 |

---

## 分层子技能架构（V3.6.0）

> DevSquad 提供 **6 个原子级子技能**，可独立使用或组合使用。
> 每个子技能是一个轻量封装（约 50 行），导入已有核心模块 — 无重复逻辑。

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher（7 角色编排）
├── intent/         → IntentSkill   — IntentWorkflowMapper（6 种意图 × 3 种语言）
├── review/         → ReviewSkill   — FiveAxisConsensusEngine（5 轴代码评审）
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + 测试策略生成
└── retrospective/  → RetroSkill    — RetrospectiveEngine + 模式提取
```

### 子技能速查表

| 技能 | 类 | 核心方法 | 封装 |
|------|-----|---------|------|
| `dispatch` | `DispatchSkill` | `run(task, roles, mode)` | MultiAgentDispatcher |
| `intent` | `IntentSkill` | `detect(text, lang)` | IntentWorkflowMapper |
| `review` | `ReviewSkill` | `review(code, axes)` | FiveAxisConsensusEngine |
| `security` | `SecuritySkill` | `scan_input(text)` | InputValidator + OpClassifier |
| `test` | `TestSkill` | `generate_strategy(module)` | TestQualityGuard |
| `retrospective` | `RetrospectiveSkill` | `run_retrospective(results)` | RetrospectiveEngine |

#### Mock Mode 行为

全部 6 个子技能在 Mock 模式下 **无需任何 API Key** 即可运行：

| 技能 | Mock 返回值 | 保真度 | 说明 |
|------|------------|--------|------|
| **DispatchSkill** | 预构建 Markdown 报告，含模拟 Worker 结果 | 高 | 模拟全部 7 个角色，内容逼真 |
| **IntentSkill** | 检测到的意图 + 置信度评分 + 工作流建议 | 高 | 基于规则的关键词匹配，确定性输出 |
| **ReviewSkill** | 五轴评审分数 + 通过/警告/不通过判定 | 中 | 分数围绕 0.75 呈高斯分布 |
| **SecuritySkill** | 扫描结果：安全/警告/危险 + 匹配到的模式 | 高 | 模式数据库为真实数据（40种检测模式） |
| **TestSkill** | 测试策略 + 质量评分 + 改进建议 | 中 | 从任务关键词生成 |
| **RetrospectiveSkill** | 调度后分析 + 模式提取 | 低～中 | 首次运行时历史为空，随时间积累 |

**Mock 模式的核心保证：**
- ✅ 无网络调用 — 完全离线
- ✅ 相同输入产生确定输出（RetrospectiveSkill 除外）
- ✅ 与真实模式相同的数据结构（`DispatchResult`、`ReviewResult` 等）
- ⚠️ 内容基于模板 — 非 LLM 生成
- ⚠️ RetrospectiveSkill 需要 ≥ 1 次真实调度后才显示模式

**切换到真实模式：**
```python
# Mock 模式（默认，无需配置）
result = skill.run("your task")

# 真实模式（需要 API Key）
import os
result = skill.run("your task", backend="openai",
                    api_key=os.environ["OPENAI_API_KEY"])
```

### 使用示例

```python
# 方法 A：直接导入（推荐单技能使用场景）
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("修复登录漏洞", roles=["coder", "tester"])
print(result["success"])  # True

# 方法 B：通过注册表（推荐动态/发现式使用）
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']

skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
print(result["risk_level"])  # "critical"

# 方法 C：快速一行调用
from skills.intent.handler import IntentSkill
intent = IntentSkill().detect("修复登录漏洞", lang="zh")
print(intent["intent"])  # "bug_fix"
```

### 注册表 API

```python
from skills import discover_all
all_skills = discover_all()  # {"dispatch": <DispatchSkill>, ...}
for name, skill in all_skills.items():
    print(f"{name}: {skill.info()['description']}")
```

---

## 🔄 控制论增强（V3.7.2）

> 灵感源自上游 TraeMultiAgentSkill v2.5 的控制论架构。
> 5 个新模块，为 DevSquad 增加反馈循环、执行守卫和智能能力。

| 模块 | 文件 | 用途 |
|------|------|------|
| FeedbackControlLoop | `feedback_control_loop.py` | Sense→Decide→Act→Feedback 闭环迭代 |
| ExecutionGuard | `execution_guard.py` | 实时中止守卫（超时/输出/关键词） |
| PerformanceFingerprint | `performance_fingerprint.py` | 统一性能指纹 + TF-IDF 相似度搜索 |
| SimilarTaskRecommender | `similar_task_recommender.py` | 基于历史的任务配置推荐 |
| AdaptiveRoleSelector | `adaptive_role_selector.py` | 成功率驱动的自适应角色选择 |

### 快速上手

```python
from scripts.collaboration import (
    FeedbackControlLoop, PerformanceFingerprint,
    SimilarTaskRecommender, AdaptiveRoleSelector, ExecutionGuard
)

# 反馈循环（自动重试直到质量门控通过）
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("设计认证系统", max_iterations=3)

# 性能指纹
fp = PerformanceFingerprint()
fp.record_execution(task, result, timing, roles)
similar = fp.find_similar("添加登录页面")

# 智能推荐
recommender = SimilarTaskRecommender(fp)
rec = recommender.recommend("实现 API")
print(rec["recommended_roles"])  # ["architect", "coder"]

# 自适应角色选择
selector = AdaptiveRoleSelector(fp)
roles = selector.select_roles("修复安全漏洞", intent="bug_fix")
```

---

## 快速上手（必读）

### 安装

```bash
# 从 PyPI 安装（推荐）
pip install devsquad

# 安装可选依赖
pip install "devsquad[api]"    # 包含 FastAPI + Streamlit 仪表盘
pip install "devsquad[all]"    # 所有可选依赖

# 或以开发模式安装（适合贡献者）
pip install -e .
pip install -e ".[api]"       # 含 API/仪表盘依赖
```

### 方法 1：一键协作（推荐大多数场景）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock 模式（默认）— 返回组装好的 Prompt，无需 API Key
disp = MultiAgentDispatcher()
result = disp.dispatch("用户描述的任务")
print(result.to_markdown())
disp.shutdown()
```

### 方法 1b：真实 AI 输出（使用 LLM 后端）

```python
import os
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.llm_backend import create_backend

backend = create_backend(
    "openai",
    api_key=os.environ["OPENAI_API_KEY"],
    base_url=os.environ.get("OPENAI_BASE_URL"),
    model=os.environ.get("OPENAI_MODEL", "gpt-4"),
)
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("设计用户认证系统", roles=["architect", "security"])
print(result.to_markdown())
disp.shutdown()
```

**CLI 等效命令**：
```bash
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "设计认证系统" -r arch sec --backend openai
```

**适用场景（方法 1）**：
- 用户需求如"设计 XX"、"实现 XX"、"分析 XX"
- 需要快速获得多角色协作结果
- 不需要细粒度的角色控制

### 方法 3：交互式 Web 仪表盘（V3.6.0 新增）

```bash
# 启动带认证的 Streamlit 仪表盘
streamlit run scripts/dashboard.py

# 打开 http://localhost:8501
# 使用 admin / admin123 登录
```

**功能特性**：
- 实时生命周期阶段监控
- CLI 命令映射可视化
- 门控状态追踪
- 性能指标展示
- 基于角色的访问控制（管理员/操作员/查看者）

**适用场景（方法 3）**：
- 需要可视化监控和管理
- 团队多人协作
- 非技术干系人需要访问

### 方法 4：REST API 服务器（V3.6.0 新增）

```bash
# 安装 API 依赖
pip install -e ".[api]"

# 启动 FastAPI 服务器
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# 访问 Swagger UI：http://localhost:8000/docs
```

**核心端点**：
```bash
# 生命周期管理
curl http://localhost:8000/api/v1/lifecycle/phases | jq
curl http://localhost:8000/api/v1/lifecycle/status | jq

# 指标与监控
curl http://localhost:8000/api/v1/metrics/current | jq
curl http://localhost:8000/api/v1/gates/status | jq

# 健康检查
curl http://localhost:8000/api/v1/health | jq
```

**适用场景（方法 4）**：
- 与外部系统集成（CI/CD、监控）
- 编程方式访问 DevSquad 能力
- 在 DevSquad 之上构建自定义 UI

### 方法 2：指定角色

```python
disp = MultiAgentDispatcher()
result = disp.dispatch("设计用户认证系统", roles=["architect", "tester"])
print(result.to_markdown())
disp.shutdown()
```

### 方法 3：Dry-Run 模拟（仅分析，不执行）

```python
result = disp.dispatch("测试任务", dry_run=True)
print(result.summary)
disp.shutdown()
```

### 方法 4：便捷函数（一行调用）

```python
from scripts.collaboration.dispatcher import quick_collaborate
result = quick_collaborate("帮我设计微服务架构")
print(result.to_markdown())
```

---

## 角色系统（7 个核心角色）

| 角色 ID | 名称 | 触发关键词 | 核心职责 |
|---------|------|-----------|---------|
| `architect` | 架构师 | architecture, design, selection, performance, module, interface, data architecture | 系统架构、技术选型、性能/安全/数据架构 |
| `product-manager` | 产品经理 | requirements, PRD, user story, competitor, acceptance | 需求分析、PRD 撰写、产品规划 |
| `security` | 安全专家 | security, vulnerability, audit, threat, encryption, OWASP | 威胁建模、漏洞审计、合规审查、安全评审 |
| `tester` | 测试专家 | test, quality, acceptance, automation, defect | 测试策略、用例设计、质量保障 |
| `solo-coder` | 开发工程师 | implementation, development, code, fix, optimize, refactor | 功能开发、代码评审、性能优化、重构 |
| `devops` | DevOps 工程师 | CI/CD, deploy, monitor, Docker, Kubernetes, infrastructure | CI/CD 流水线、容器化、监控、基础设施 |
| `ui-designer` | UI 设计师 | UI, interface, frontend, visual, prototype, accessibility | UI 设计、交互设计、原型制作、无障碍 |

**CLI 简写 ID**：`arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`

**自动匹配规则**：未指定角色时，系统根据任务关键词自动匹配最佳角色组合。

---

## 完整工作流（当本技能被调用时）

### 步骤 1：创建 Dispatcher

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

### 步骤 2：分析任务 & 匹配角色

```python
matched = disp.analyze_task(user_task)
for role in matched:
    print(f"{role['name']} (confidence: {role['confidence']:.0%}) - {role['reason']}")
```

### 步骤 3：执行协作

```python
result = disp.dispatch(
    task_description=user_task,
    roles=None,          # None=自动匹配，或指定 ["architect", "tester"]
    mode="auto",         # auto/parallel/sequential/consensus
    dry_run=False,       # True=仅模拟
)
```

### 步骤 4：检查结果

```python
print(f"Success: {result.success}")
print(f"Roles: {result.matched_roles}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(result.summary)

if result.worker_results:
    for wr in result.worker_results:
        print(f"[{wr['role']}] {wr['output'][:200]}")
```

### 步骤 5：输出 Markdown 报告

```python
report = result.to_markdown()
print(report)
```

### 步骤 6：清理资源

```python
disp.shutdown()
```

---

## 高级功能指南

### 上下文压缩（防止长对话溢出）

当对话过长时，ContextCompressor 自动触发：
- **Level 1 SNIP**：对旧对话进行精细裁剪，保留关键决策和结论
- **Level 2 SessionMemory**：将重要信息提取到记忆中然后清空上下文
- **Level 3 FullCompact**：LLM 生成一页摘要（最激进）

查看压缩状态：
```python
stats = disp.coordinator.get_compression_stats()
memory = disp.coordinator.get_session_memory()
```

### 权限守卫（安全操作哨兵）

PermissionGuard 自动检查危险操作：
- **PLAN 级别**：只允许只读操作
- **DEFAULT 级别**：写操作需要确认
- **AUTO 级别**：AI 分类器自动判断
- **BYPASS 级别**：完全跳过（最高信任）

权限记录存储在 `result.permission_checks` 中。

### 记忆桥接（跨会话记忆）

MemoryBridge 提供 7 类记忆：
- `knowledge` — 知识条目
- `episodic` — 情景记忆（任务执行记录）
- `semantic` — 语义记忆
- `feedback` — 用户反馈
- `pattern` — 成功模式
- `analysis` — 分析案例
- `correction` — 纠正记录

遗忘曲线：7d=1.0, 30d≈0.8, 60d≈0.5, 90d≈0.3

查看记忆状态：
```python
status = disp.get_status()
mem_stats = status.get("memory_stats")
```

### 启动预热（减少冷启动延迟）

WarmupManager 3 层预热机制：
- **EAGER 层**：关键资源同步预加载（~15ms）
- **ASYNC 层**：异步后台预热（~300ms）
- **LAZY 层**：按需加载

查看预热状态：
```python
status = disp.get_status()
warmup = status.get("warmup_metrics")
```

### 技能学习（从成功中进化）

Skillifier 从成功操作序列中自动提取可复用模式：
```python
proposals = result.skill_proposals
for p in proposals:
    print(f"新技能候选: {p['title']} (confidence: {p['confidence']:.0%})")
```

### 共识决策（多角色冲突解决）

当 Worker 产生分歧时，ConsensusEngine 发起投票：
- 加权投票（按角色重要性加权）
- 否决权（关键角色可单独否决）
- 升级给人类（共识无法达成时标记为待人工决策）

共识记录在 `result.consensus_records` 中。

---

## 调度模式对照表

| 模式 | 描述 | 适用场景 |
|------|------|---------|
| `auto` | 自动选择最优模式 | 默认推荐 |
| `parallel` | 所有角色并发执行 | 角色间无依赖关系 |
| `sequential` | 按顺序执行 | 存在依赖链 |
| `consensus` | 执行后强制共识投票 | 需要一致决策 |

---

## 系统状态查询

```python
status = disp.get_status()
# 返回:
# {
#   "version": "3.6.1",
#   "components": {...},        # 组件启用状态
#   "dispatch_count": N,         # 已完成的调度次数
#   "scratchpad_stats": {...}, # 黑板统计
#   "warmup_metrics": {...},    # 预热指标（如已启用）
#   "memory_stats": {...},      # 记忆统计（如已启用）
# }

history = disp.get_history(limit=10)
# 返回最近 N 次调度的完整结果
```

---

## 错误处理

所有异常都被捕获在 `DispatchResult` 内部，不会抛出：

```python
result = disp.dispatch("任意任务")
if not result.success:
    print("错误:", result.errors)
    print("摘要:", result.summary)
```

常见错误及处理方式：
- `FILE_CREATE` / 权限相关 → PermissionGuard 拦截，检查 `result.permission_checks`
- 记忆写入失败 → MemoryBridge 存储问题，检查目录权限
- 压缩失败 → ContextCompressor 问题，通常不影响主流程

---

## 语言规则

- 自动检测用户语言（中文/英文/日文）
- 所有输出使用与用户相同的语言
- 角色名称映射：架构师→Architect, PM→Product Manager 等

---

## 测试铁律（⚠️ AI 编写测试时必须遵守）

> 本节解决 AI 辅助测试开发中的三个顽疾。
> **违反任何一条都是严重错误。**

### 铁则 1：文档先行 — 切勿凭记忆编写 API 调用

```
❌ 错误：凭记忆猜测参数名
   result = obj.method(bad_param="value")  # 参数名是猜的

✅ 正确：先读源码确认签名，再编写测试
   # 1. 使用 AST 提取或直接读取源码确认参数
   # 2. 使用 TestQualityGuard 自动验证
   from scripts.collaboration.test_quality_guard import quick_audit
   report = quick_audit("module.py", "module_test.py")
   print(report.to_markdown())  # 检查 API 参数错误
```

**强制要求**：
- 编写任何测试前，必须 `import` 目标模块并验证实际签名
- 禁止使用不存在的参数名（例如 `id` vs `record_id`）
- 可使用 `TestQualityGuard.quick_audit()` 进行自动检测

### 铁则 2：失败即报告 — 严禁修改断言来"通过"

```
❌ 严重错误：测试失败时修改断言来"通过"
   # 原始: assertEqual(result, expected_value)
   # 改为: assertTrue(result > 0)          ← 这是作弊！
   # 改为: assertGreater(score, 0.0)      ← 0.0 阈值永远通过！

✅ 正确：失败时分析根因，修复实现或修正测试逻辑
   # 1. 确认 API 签名正确（铁则 1）
   # 2. 验证测试数据是否合理
   # 3. 如果实现有真实 Bug → 报告给架构师/开发者
   # 4. 仅在测试逻辑本身有错时才修改断言
```

**禁止的反模式**（由 TestQualityGuard 自动检测）：
| 反模式 | 严重程度 | 描述 |
|--------|---------|------|
| 松散断言 (`assertTrue`) | MINOR | 优先使用 `assertEqual/assertIn` |
| 无效阈值 (`>0.0`) | MINOR | 必须设置有意义的阈值 |
| 裸 `except:` | MAJOR | 必须指定异常类型 |
| 魔术数字 (>999) | MINOR | 提取为命名常量 |

### 铁则 3：维度完整 — 不可只测 Happy Path

每个模块的测试套件 **必须** 覆盖以下维度：

| 维度 | 符号 | 最低占比 | 描述 |
|------|------|---------|------|
| **Happy Path** | ✅ | ≥50% | 正常输入 → 预期输出 |
| **Error Case** | 🔴 | **≥15%** | 非法输入 / 空 / 越界 → 异常或错误返回 |
| **Boundary** | 🟡 | ≥10% | 空字符串、零值、最大值、None |
| **Performance** | ⚡ | **≥5%** | 关键路径耗时基线（如 `<100ms`） |
| **Configuration** | ⚙️ | ≥5% | 不同配置组合 |
| **Integration** | 🔗 | ≥10% | 跨模块协作场景 |
| **Security** | 🔒 | 按需 | 权限 / 注入 / 特权提升（如涉及安全） |

**自动检查工具**：
```python
from scripts.collaboration.test_quality_guard import TestQualityGuard

guard = TestQualityGuard(
    module_path="scripts/collaboration/coordinator.py",
    test_path="scripts/collaboration/coordinator_test.py",
)
report = guard.audit()
print(report.to_markdown())
# 输出：评分 + 问题列表 + 维度覆盖 + 反模式检测
```

### 测试函数模板（必须遵循格式）

```python
def test_<feature>_<scenario>(self):
    """验证: <具体要验证什么，一句话>

    场景: <什么条件会触发此测试>
    预期: <应该发生什么>
    """
    # Arrange - 准备数据和依赖

    # Act - 执行被测操作

    # Assert - 验证结果（使用精确断言，禁止用 assertTrue 绕过）
```

---

## 项目生命周期：11 阶段模型（V3.6.0）

> **定义文档**：`docs/prd/lifecycle_phases_definition.md`（权威版本）
> **评审报告**：`docs/prd/lifecycle_phases_review.md`（7 角色评审，9 条建议已采纳）

### 阶段概览

| # | 阶段 | 主导 | 评审者 | 可选 | 门控 |
|---|------|------|--------|------|------|
| P1 | 需求分析 | pm | arch+test+sec+ui | ❌ | 验收标准可量化 |
| P2 | 架构设计 | arch | pm+sec+infra | ❌ | 加权共识 ≥70% |
| P3 | 技术设计 | arch+coder | coder+test | ❌ | API 规格无歧义 |
| P4 | 数据设计 | arch+coder | arch+sec | ✅ | 3NF 或非正规化有据 |
| P5 | 交互设计 | ui | pm+test+sec | ✅ | 核心流程可用性验证通过 |
| P6 | 安全评审 | sec | arch+infra | ✅ | 无 P0/P1 漏洞，合规全绿 |
| P7 | 测试计划 | test | arch+sec+infra+pm | ❌ | 测试计划评审通过 |
| P8 | 开发实现 | coder | arch+sec+test+coder | ❌ | 代码评审通过，无 P0 缺陷 |
| P9 | 测试执行 | test | arch+pm+sec+infra | ❌ | 覆盖率≥80% + P7 计划 100% 执行 |
| P10 | 部署发布 | infra | arch+sec+test | ❌ | 部署演练通过 |
| P11 | 运维保障 | infra+sec | arch+infra | ✅ | P99<目标值，告警 100% |

### 依赖图

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(依赖 P1+P3) ──↗
```

### 生命周期模板

| 模板 | 阶段 | 适用场景 |
|------|------|---------|
| `full` | P1-P11 | 完整项目 |
| `backend` | 无 P5 | 后端服务 |
| `frontend` | 无 P4,P6 | 前端应用 |
| `internal_tool` | 无 P4,P5,P6,P11 | 内部工具 |
| `minimal` | P1,P3,P7,P8,P9 | 最小集 |

### 门控机制

- **强制性**：每个阶段的门控必须检查
- **失败不阻塞**：生成差距报告 → 用户决定
- **可追溯**：所有门控结果记录到检查点

### 需求变更流程

```
变更请求(pm/用户) → 影响分析(arch+sec+test) → 变更评审(全角色) → 批准/驳回 → 回滚到受影响阶段
```

---

## 元铁则：文档先行，万事留痕（⚠️ 最高法则）

> **文档先行，万事留痕** — 这是统领所有其他规则的最高铁则。
> **违反此规则是使所有工作无效的严重错误。**

### 核心原则

```
编写任何代码之前 → 计划/规格文档必须存在
进行任何变更之前 → 影响分析必须文档化
完成任何工作之后 → 结果必须记录到文档
做出任何决策之后 → 决策依据必须可追溯
```

### 强制要求

| 阶段 | 要求 | 验证方式 |
|------|------|---------|
| **事前** | 无规格/计划文档不得编码 | `docs/spec/` 或 `docs/prd/` 有对应文档 |
| **事中** | 所有决策附带理由记录 | Commit 信息、ADR 或行内注释说明 WHY |
| **事后** | 所有受影响文档同步更新 | 版本/模块数/测试数在所有文档间一致 |
| **始终** | 不得有无文档来源的可追溯孤立代码 | 每个文件的用途至少在一个文档中有记录 |

### "文档先行"的含义

1. **先规格后实现**：如果没有 SPEC 或 PRD，先写一个。哪怕一段规格也比没有好。
2. **先设计后编码**：架构决策在写代码之前记录。
3. **先计划后测试**：先明确测什么、为什么测，再写测试代码。
4. **先日志后合并**：改了什么、为什么改，推送前先写清楚。

### "万事留痕"的含义

1. **每个决策都有原因**：代码注释、Commit 信息、ADR — 至少选一个。
2. **每个文件都有归属/用途**：这个文件为什么存在？记录下来。
3. **每次变更都有痕迹**：Git 历史 + 文档更新 = 完整审计链路。
4. **不允许隐身变更**：没有对应文档更新的 Commit 不得提交。

### 执行保障

- CI 检查：`docs/` 目录必须有与代码变更匹配的更新文件
- 评审门控：PR 审查者检查文档同步状态
- 共识机制：Coordinator 在批准前验证文档完整性
- 补救措施：无前置文档完成的工作必须立即补齐

---

## 交付工作流铁律（⚠️ 每次推送后必须执行）

> 本节定义标准闭环工作流：实现→测试→走查→注解→文档→Git。
> **违反任何一步都是严重错误。**

### 铁则：推送后强制闭环

```
实现 → 测试(全量回归) → 代码走查 → 注解补全 → 文档更新 → 清理 → Git 推送
```

**每步强制动作**：

| 步骤 | 强制动做 | 验证标准 |
|------|---------|---------|
| **1. 实现** | 按 Plan/Spec 编写/修改代码 | 功能完整，无 TODO 占位符 |
| **2. 测试** | 新增测试 + 全量回归 | 0 失败，0 错误，100% 通过 |
| **3. 走查** | 逐行阅读每个文件的新增/修改内容 | 理解每个方法的 I/O 和边界行为 |
| **4. 注解** | 公共方法 docstring（Args/Returns）+ 关键逻辑行内注释 | 不得有"裸方法"（公共方法无 docstring） |
| **5. 文档更新** | **同步所有相关文档**（见下方清单） | 所有文档版本/模块数/测试数一致，无过时内容 |
| **6. 清理** | 删除过程文档 / 临时文档 / 临时代码 | 无残留 `_tmp`/`_draft`/`_old` 文件 |
| **7. Git 推送** | commit message 含版本+变更摘要+测试数 | push 成功，远程可见 |

### 铁则：文档覆盖清单（第 5 步必须检查所有类别）

> **原则：与变更相关的所有文档类型都必须更新 — 需求/设计/测试/API/安装/SKILL 等。**

| 文档类别 | 检查项 | 是否必查 |
|----------|--------|---------|
| **需求** | `docs/spec/*.md` — 规格状态更新（pending→in-progress→implemented） | ✅ 必查 |
| **设计** | `docs/architecture/*.md` — 架构演进记录、阶段新增 | ✅ 必查 |
| **规划** | `docs/planning/*.md` — 共识行动项检查、扩展说明 | ✅ 必查 |
| **SKILL 文档** | `SKILL.md` — 模块表、测试表、版本历史、规则 | ✅ 必查 |
| **项目总览** | `README.md`(EN) / `README-CN.md`(CN) / `README-JP.md`(JP) — 版本、模块、时间线 | ✅ 必查 |
| **变更日志** | `CHANGELOG.md` — 新版本条目（Added/Changed/Fixed） | ✅ 必查 |
| **状态文档** | `docs/PROJECT_STATUS.md` — 当前版本、模块列表、测试摘要 | ✅ 必查 |
| **配置** | `CONFIGURATION.md` — 新增外部集成配置选项 | 🔍 如有集成 |
| **API 文档** | 如 API 变更则更新接口文档 | 🔍 如 API 变更 |
| **安装依赖** | `INSTALL.md` / `requirements.txt` — 如有新依赖则更新 | 🔍 如有新依赖 |
| **测试计划** | 反映新的测试覆盖范围 | 🔍 重大变更时 |

### 铁则：清理规则（第 6 步）

> **原则：过程文档和临时产物不应留在代码库中。**

| 清理类别 | 动作 | 示例 |
|----------|------|------|
| 过程分析脚本 | 有价值的保留，一次性的删除 | `*_review.py`, `*_analysis.py` → 评估后决定 |
| 临时调试文件 | **必须删除** | `test_*.py.tmp`, `debug_*.py`, `*.bak.*` |
| 草稿/废弃文档 | **必须删除** | `*_DRAFT.md`, `*_old.md`, `*_tmp.md` |
| 未使用的占位代码 | **必须删除**或替换为真实实现 | `pass # TODO`, `raise NotImplementedError` |
| 重复/冗余文件 | 合并或删除 | 仅保留同一文档的最新版本 |

### 注解规范（语言分离）

| 类别 | 语言 |
|------|------|
| **文档（SKILL.md / README.md）** | **English** |
| **README-CN.md** | **中文（简体）** |
| **README-JP.md** | **日本語** |
| **代码 docstring** | **English**（Args / Returns / Example） |
| **行内注释** | **English**（解释业务逻辑） |

---

## 测试覆盖率

| 模块 | 测试数 | 状态 |
|------|-------|------|
| Core (Dispatcher+Coordinator+Worker+Scratchpad+Consensus) | 39 | ✅ PASS |
| Role Mapping (RoleMatcher+别名解析+双语关键词) | 25 | ✅ PASS |
| Upstream (Checkpoint+SemanticMatcher+Workflow+CompletionChecker) | 35 | ✅ PASS |
| MCEAdapter (CarryMem 集成+类型映射+优雅降级) | 30 | ✅ PASS |
| Contract Tests (Protocols+NullProviders+Cache+Monitor+Security) | 234 | ✅ PASS |
| V3.5 Integration (Lifecycle+ChangeRequest+Templates) | 7 | ✅ PASS |
| **P0-1 AntiRationalizationEngine** | **39** | **✅ PASS** |
| **P0-2 VerificationGate** | **42** | **✅ PASS** |
| **P0-3 IntentWorkflowMapper** | **58** | **✅ PASS** |
| **P0-4 CLI Lifecycle Commands** | **28** | **✅ PASS** |
| **P1-1 StandardizedRoleTemplate** | **27** | **✅ PASS** |
| **P1-2 OperationClassifier** | **29** | **✅ PASS** |
| **P1-3 OutputSlicer** | **26** | **✅ PASS** |
| **P1-4 FiveAxisConsensusEngine** | **29** | **✅ PASS** |
| **P1-5 CIFeedbackAdapter** | **22** | **✅ PASS** |
| **总计** | **2703+** | **✅ 全部通过** |

---

## 版本历史

- **v3.7.0** (2026-06-13): FeedbackControlLoop 自动模式 + LLM 精炼 + AdaptiveRoleSelector/SimilarTaskRecommender 集成到 RoleMatcher + ExecutionGuard 集成到 EnhancedWorker + 调度流水线生命周期阶段追踪 + get_history/audit_quality/export_metrics/clear_history 的 RBAC 检查 + TestQualityGuard 默认启用 + enable_feedback_loop 默认值 False→"auto" + 移除 AlertManager（未使用）+ 13+ 文件版本同步至 3.7.0 + 修复 except Exception: pass 静默错误吞没 + 修复 assertTrue 测试反模式 + 1940 通过, 11 跳过, 3 预期外通过
- **v3.6.7** (2026-06-07): Redis 缓存 L2 后端 + 异步调度 (asyncio.gather) + Dispatcher 重构 (788→18 步骤方法) + DispatchResult Bug 修复 (5 个缺失字段) + 1855+ 测试通过

- **v3.4.2** (2026-05-03): P1 增强完成 — RoleTemplateMarket V2(27 测试) + OperationClassifier(29 测试) + OutputSlicer(26 测试) + FiveAxisConsensusEngine(29 测试) + CIFeedbackAdapter(22 测试) + 166 个新测试 + 53 个核心模块
- **v3.4.1** (2026-05-03): Agent Skills 质量框架 (P0) — AntiRationalizationEngine(39 测试) + VerificationGate(42 测试) + IntentWorkflowMapper(58 测试) + CLI Lifecycle Commands(28 测试) + 167 个新测试 + Google Agent Skills 集成 + 49 个核心模块
- **v3.5.0** (2026-05-02): 11 阶段项目生命周期（full/backend/frontend/internal_tool/minimal 模板）+ 需求变更管理 + 带差距报告的门控机制 + WorkflowEngine 生命周期支持 + 自然语言规则收集（RuleCollector）+ 748+ 测试通过
- **v3.3** (2026-04-17): WorkBuddy Claw 集成 — WorkBuddyClawSource(只读桥接/INDEX 搜索/日志/AI 资讯) + Dispatcher AI News 自动注入 + 注解规范（EN 文档/docstring/行内）+ 代码注释审计（全 EN）+ MCE v0.4 支持（租户/权限）+ 多语言 README（EN/CN/JP）+ 33 个新测试
- **v3.2** (2026-04-17): MVP 三行并线 — E2E 全流程演示(10 步流程/CLI) + Dispatcher UX 增强(结构化/紧凑/详细 3 格式报告) + MCEAdapter 记忆分类适配器(懒加载/优雅降级) + 交付工作流铁律
- **v3.1** (2026-04-16): Prompt 优化系统 — 动态 Prompt 组装(3 种变体) + Skillify 闭环反馈(A/B 升降级) + 压缩感知适配
- **v3.0.1** (2026-04-16): 全面代码注解（6 个核心模块 100% docstring 覆盖）+ TestQualityGuard 集成
- **v3.0** (2026-04-16): 全面重构为 Coordinator/Worker/Scratchpad 架构，11 个核心模块（含 Dispatcher+TestQualityGuard），~710 测试全部通过
- **v2.5** (2026-04-06): 记忆分类引擎集成
- **v2.4** (2026-04-01~03): Vibe Coding + 核心规则 + 生命周期识别
- **v2.3** (2026-03-28): 多角色代码走查 + 3D 可视化
- **v2.2** (2026-03-21): 长运行 Agent（CheckPoint + 交接）
- **v2.1** (2026-03-17): 双层上下文 + AI 语义匹配
- **v2.0/v1.0** (2026-03-16): 初始发布
