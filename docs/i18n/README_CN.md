# DevSquad — 多角色 AI 任务编排器

<p align="center">
  <strong>一个任务 → 多角色 AI 协作 → 一个结论</strong>
  <br>
  <em>生产就绪 | V3.6.1</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-1561%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.6.1-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
</p>

<p align="center">
  <img alt="Architecture" src="https://img.shields.io/badge/Architecture-Plan_C_Layered-blueviolet" />
  <img alt="API" src="https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi" />
  <img alt="Dashboard" src="https://img.shields.io/badge/Dashboard-Streamlit-red?logo=streamlit" />
  <img alt="Auth" src="https://img.shields.io/badge/Auth-RBAC-green" />
  <img alt="Alerts" src="https://img.shields.io/badge/Alerts-Multi_Channel-orange" />
</p>

---

## 🚀 V3.6.1: 控制论增强版本

**DevSquad V3.6.1** 引入 FeedbackControlLoop 控制论反馈闭环、ExecutionGuard 实时执行守护、PerformanceFingerprint 统一执行指纹、SimilarTaskRecommender 历史任务推荐、AdaptiveRoleSelector 自适应角色选择 — 让多智能体协作更智能、更自愈、更可观测。

### 🔄 V3.6.1 控制论增强详情

#### 1️⃣ FeedbackControlLoop（反馈闭环控制器）
**中文名称**：反馈闭环控制器
**核心能力**：
- 闭环反馈控制，实时监控调度质量指标
- 自动调整角色权重和策略参数
- 基于历史表现的动态优化

```python
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop

loop = FeedbackControlLoop()
result = loop.run(dispatch_result)
print(f"Quality score: {result.quality_score}")
print(f"Adjustments made: {result.adjustments}")
# 自动分析调度结果并生成改进建议
```

#### 2️⃣ ExecutionGuard（执行守护者）
**中文名称**：执行守护者
**核心能力**：
- 实时执行监控和安全检查
- 异常检测与自动回滚机制
- 执行超时和资源限制管理

```python
from scripts.collaboration.execution_guard import ExecutionGuard

guard = ExecutionGuard()
guarded_result = guard.execute_with_protection(
    task="设计认证系统",
    roles=["architect", "security"],
    timeout=300,
    auto_rollback=True
)
print(f"Execution status: {guarded_result.status}")
print(f"Safety checks passed: {guarded_result.safety_passed}")
```

#### 3️⃣ PerformanceFingerprint（性能指纹）
**中文名称**：性能指纹系统
**核心能力**：
- 统一的性能基线跟踪和对比
- 多维度性能指标采集（延迟、吞吐量、资源消耗）
- 历史趋势分析和异常检测

```python
from scripts.collaboration.performance_fingerprint import PerformanceFingerprint

fingerprint = PerformanceFingerprint()
fp = fingerprint.capture(dispatch_result)
print(f"Response time: {fp.response_time_ms}ms")
print(f"Token usage: {fp.tokens_used}")
print(f"Memory peak: {fp.memory_peak_mb}MB")
# 与历史基线对比
comparison = fingerprint.compare_with_baseline(fp)
print(f"Performance regression: {comparison.has_regression}")
```

#### 4️⃣ SimilarTaskRecommender（相似任务推荐器）
**中文名称**：相似任务推荐器
**核心能力**：
- 基于 TF-IDF 的任务相似度搜索
- 历史成功案例推荐
- 复用已验证的角色组合和策略

```python
from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender

recommender = SimilarTaskRecommender()
recommendations = recommender.find_similar_tasks("设计用户认证系统")
for rec in recommendations:
    print(f"Task: {rec.task_description}")
    print(f"Similarity: {rec.similarity_score:.2%}")
    print(f"Suggested roles: {rec.recommended_roles}")
    print(f"Success rate: {rec.historical_success_rate:.2%}")
    print("---")
```

#### 5️⃣ AdaptiveRoleSelector（自适应角色选择器）
**中文名称**：自适应角色选择器
**核心能力**：
- 基于任务特征智能选择最优角色组合
- 动态调整角色权重和优先级
- 考虑历史表现和任务复杂度

```python
from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector

selector = AdaptiveRoleSelector()
selection = selector.select_roles(
    task="构建高并发微服务架构",
    complexity="high",
    domain="backend",
    consider_history=True
)
print(f"Selected roles: {selection.roles}")
print(f"Confidence: {selection.confidence_score:.2%}")
print(f"Rationale: {selection.rationale}")
# 输出类似：
# Selected roles: ['architect', 'devops', 'security', 'tester']
# Confidence: 94.5%
# Rationale: 高复杂度后端任务需要架构设计+运维+安全+测试全覆盖
```

**集成示例**：五个模块可独立使用，也可组合形成完整的控制论闭环：

```python
from scripts.collaboration import (
    FeedbackControlLoop,
    ExecutionGuard,
    PerformanceFingerprint,
    SimilarTaskRecommender,
    AdaptiveRoleSelector,
)

# 完整的控制论工作流
recommender = SimilarTaskRecommender()
selector = AdaptiveRoleSelector()
guard = ExecutionGuard()
fingerprint = PerformanceFingerprint()
loop = FeedbackControlLoop()

task = "设计分布式缓存系统"

# 步骤 1: 查找相似任务
similar = recommender.find_similar_tasks(task)

# 步骤 2: 智能选择角色
roles = selector.select_roles(task, consider_history=True)

# 步骤 3: 安全执行
result = guard.execute_with_protection(task, roles.roles)

# 步骤 4: 性能指纹采集
fp = fingerprint.capture(result)

# 步骤 5: 反馈闭环优化
improvement = loop.run(result)
print(f"Next iteration suggestions: {improvement.suggestions}")
```

## DevSquad 是什么？

DevSquad 将**单个 AI 任务转化为多角色 AI 协作**。自动将你的任务分派到最合适的专家角色组合——架构师、产品经理、编码员、测试工程师、安全审查员、运维工程师——通过共享工作区编排并行协作，通过加权共识投票解决冲突，最终交付统一的结构化报告。

```
你: "设计一个微服务电商后端"
         │
         ▼
┌─────────────────┐
│  输入验证  ──→ 安全检查 (XSS, SQL注入, Prompt注入)
└────────┬────────┘
         ▼
┌─────────────────┐
│  角色匹配  ──→ 自动匹配: 架构师 + 运维 + 安全
└────────┬────────┘
         ▼
┌──────────┬──────────┬──────────┐
│  架构师   │  运维     │  安全     │   ← ThreadPoolExecutor 并行执行
│ (设计)    │ (基础设施)│ (威胁)    │
└────┬──────┴────┬─────┴────┬────┘
     └────────────┼───────────┘
                  ▼
      ┌──────────────────┐
      │    共享工作区      │ ← 实时同步的协作黑板
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │   共识引擎         │ ← 加权投票 + 否决权 + 升级
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │   结构化报告       │ ← 发现 + 行动项 (高/中/低)
      └──────────────────┘
```

## 快速开始

### 安装

```bash
# 方式一：PyPI 直接安装（推荐）
pip install devsquad

# 带可选依赖
pip install "devsquad[api]"   # 包含 FastAPI + Streamlit
pip install "devsquad[all]"   # 包含所有可选依赖

git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 方式 A: 直接运行（无需安装）
# 零依赖，开箱即用，配置文件功能降级
python3 scripts/cli.py dispatch -t "设计用户认证系统"

# 方式 B: pip 开发安装（推荐用于本地开发）
# 完整功能，含配置文件支持（pyyaml 自动安装）
pip install -e .
devsquad dispatch -t "设计用户认证系统"
```

> **选哪种？** 方式 A 适合快速体验——无需任何依赖，但无法加载 `~/.devsquad.yaml` 配置文件。方式 B 将 DevSquad 安装为完整包，启用所有功能，包括 YAML 配置、`devsquad` 命令行工具和可选集成（CarryMem、OpenAI、Anthropic）。

### 3 种使用方式

**1. CLI（推荐）**

```bash
# Mock 模式（默认）— 无需 API Key
python3 scripts/cli.py dispatch -t "设计用户认证系统"

# 真实 AI 输出 — 先设置环境变量
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "设计认证系统" --backend openai

# 指定角色（短 ID: arch/pm/test/coder/ui/infra/sec）
python3 scripts/cli.py dispatch -t "设计认证系统" -r arch sec --backend openai

# 实时流式输出
python3 scripts/cli.py dispatch -t "设计认证系统" -r arch --backend openai --stream

# 其他命令
python3 scripts/cli.py status          # 系统状态
python3 scripts/cli.py roles           # 列出可用角色
python3 scripts/cli.py --version       # 显示版本 (3.6.1)
```

**2. Python API**

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock 模式（默认）
disp = MultiAgentDispatcher()
result = disp.dispatch("设计 REST API 用户管理系统")
print(result.to_markdown())
disp.shutdown()

# 使用 LLM 后端
from scripts.collaboration.llm_backend import create_backend
backend = create_backend("openai", api_key="sk-...", base_url="https://api.openai.com/v1")
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("设计认证系统", roles=["architect", "security"])
print(result.summary)
disp.shutdown()
```

**3. MCP 服务器（用于 Cursor / 任何 MCP 客户端）**

```bash
pip install mcp
python3 scripts/mcp_server.py              # stdio 模式
python3 scripts/mcp_server.py --port 8080  # SSE 模式
```

**4. 子Skill（轻量独立）**

```python
# 单独使用任意子Skill，无需启动完整 DevSquad
from skills.security.handler import SecuritySkill
SecuritySkill().scan_input("DROP TABLE users;")  # Mock 模式零依赖

from skills.review.handler import ReviewSkill
ReviewSkill().review("def foo(): pass")
```

## 7 个核心角色

| 角色 | CLI ID | 别名 | 权重 | 最适合 |
|------|--------|------|------|--------|
| 架构师 | `arch` | `architect` | 1.5 | 系统设计、技术选型、性能/安全架构 |
| 产品经理 | `pm` | `product-manager` | 1.2 | 需求分析、用户故事、验收标准 |
| 安全专家 | `sec` | `security` | 1.1 | 威胁建模、漏洞审计、合规检查 |
| 测试专家 | `test` | `tester`, `qa` | 1.0 | 测试策略、质量保证、边界用例 |
| 编码员 | `coder` | `solo-coder`, `dev` | 1.0 | 功能实现、代码审查、性能优化 |
| 运维工程师 | `infra` | `devops` | 1.0 | CI/CD、容器化、监控、基础设施 |
| UI 设计师 | `ui` | `ui-designer` | 0.9 | UX 流程、交互设计、无障碍 |

**自动匹配**：如果不指定角色，调度器会根据任务关键词自动匹配。

## 🧩 分层子Skill架构 (V3.6.1 新增)

> DevSquad 提供 **6 个原子化子Skill**，可独立使用也可组合使用。
> 每个子Skill 是约 **50 行的薄封装层**，导入现有核心模块——无重复逻辑。

```
skills/
├── dispatch/       → DispatchSkill — 多Agent调度（7角色编排）
├── intent/         → IntentSkill   — 意图检测（6种意图 × 3语言）
├── review/         → ReviewSkill   — 五维代码审查
├── security/       → SecuritySkill — 安全扫描 + 操作分类
├── test/           → TestSkill     — 测试策略 + 质量审计
└── retrospective/  → RetroSkill    — 调度后复盘 + 模式提取
```

### 子Skill速查

| Skill | 核心方法 | 封装模块 | Mock模式 |
|-------|---------|---------|:-------:|
| `dispatch` | `run(task, roles)` | MultiAgentDispatcher | ✅ |
| `intent` | `detect(text, lang)` | IntentWorkflowMapper | ✅ |
| `review` | `review(code)` | FiveAxisConsensusEngine | ✅ |
| `security` | `scan_input(text)` | InputValidator + OpClassifier | ✅ |
| `test` | `generate_strategy(module)` | TestQualityGuard | ✅ |
| `retrospective` | `run_retrospective(results)` | RetrospectiveEngine | ✅ |

### 使用示例

```python
# 直接导入（推荐用于单Skill场景）
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("修复登录漏洞", roles=["coder", "tester"])

# 通过注册表动态发现
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']
skill = get_skill("security")
result = skill.scan_input("DROP TABLE users;")
```

所有子Skill **无需任何 API Key** 即可在 Mock 模式下运行。

## 核心特性

### 安全
- **输入验证器**：XSS、SQL 注入、命令注入、HTML 注入检测
- **Prompt 注入防护**：21+ 种注入模式（忽略先前指令、越狱、DAN 模式、系统提示提取等）
- **API Key 安全**：仅使用环境变量，绝不通过命令行参数或日志泄露
- **权限守卫**：4 级安全门（PLAN → DEFAULT → AUTO → BYPASS）

### 性能
- **ThreadPoolExecutor**：多角色分派的真实并行执行
- **LLM 缓存**：基于 TTL 的 LRU 缓存 + 磁盘持久化（60-80% 成本降低）
- **LLM 重试**：指数退避 + 熔断器 + 多后端降级
- **流式输出**：通过 `--stream` 实时逐块输出 LLM 响应

### 可靠性
- **检查点管理器**：SHA256 完整性校验、交接文档、自动清理
- **工作流引擎**：任务→工作流自动拆分、步骤执行、断点恢复、**11阶段生命周期模板**（full/backend/frontend/internal_tool/minimal）、需求变更管理
- **任务完成检查器**：DispatchResult/ScheduleResult 完成度跟踪
- **共识引擎**：加权投票 + 否决权 + 人工升级

### ⚓ AnchorChecker 锚点检查系统
里程碑锚点验证，确保关键检查点在继续之前被正确验证：

```python
from scripts.collaboration.anchor_checker import AnchorChecker

checker = AnchorChecker()
checker.define_anchor("architecture_complete", criteria=["API spec defined", "tech stack selected"])
result = checker.check_anchor("architecture_complete", phase_output)
print(f"Anchor passed: {result.passed}")
print(f"Drift detected: {result.drift_score}")
```

**特性**:
- 跨阶段一致性验证
- 带严重性评分的漂移检测
- 自动恢复建议
- 锚点持久化

### 🔄 RetrospectiveEngine 独立复盘引擎
独立复盘机制，持续改进每次调度：

```python
from scripts.collaboration.retrospective_engine import RetrospectiveEngine

engine = RetrospectiveEngine()
report = engine.run_retrospective(dispatch_result)
print(f"Patterns found: {len(report.patterns)}")
print(f"Anti-patterns: {len(report.anti_patterns)}")
print(f"Improvement suggestions: {report.suggestions}")
```

**特性**:
- 调度后质量分析
- 模式与反模式提取
- 指标趋势跟踪
- 可操作的改进建议

### 🎯 StructuredGoal 结构化目标
结构化目标管理，层次化分解：

```python
from scripts.collaboration.structured_goal import StructuredGoal

goal = StructuredGoal("构建电商平台")
goal.add_sub_goal("用户认证", criteria=["OAuth2支持", "2FA就绪"])
goal.add_sub_goal("商品目录", criteria=["搜索", "筛选", "分页"])
progress = goal.get_progress()
print(f"Overall: {progress.completion_pct}%")
```

**特性**:
- 层次化目标分解
- 子目标间依赖映射
- 实时进度跟踪
- 自动完成验证

### 🔀 FallbackBackend 自动故障转移
自动LLM后端故障转移，确保高可用：

```python
from scripts.collaboration.llm_backend import FallbackBackend

backend = FallbackBackend(
    primary="openai",
    fallbacks=["anthropic", "mock"],
    health_check_interval=30,
)
result = backend.generate("设计认证系统")
# 主后端不可用时自动切换
```

**特性**:
- 持续后端健康监控
- 无缝自动故障转移
- 优先级路由配置
- 自动主后端恢复检测

### 自然语言规则收集

自动从用户自然语言输入中检测并存储规则，无需手动编辑配置文件：

```python
# 用户说："记住规则：写代码时必须加注释"
# DevSquad 自动：
# 1. 检测规则存储意图
# 2. 提取：trigger="写代码时", action="必须加注释", type="always"
# 3. 安全清洗（移除危险模式 + prompt注入防护）
# 4. 存储（CarryMem优先 + 本地JSON备）

# 查看规则
# 用户说："列出规则" → 返回所有已存储规则

# 删除规则
# 用户说："删除规则 RULE-LOCAL-abc123"
```

**管线**：用户输入 → IntentDetector → RuleExtractor → RuleSanitizer → RuleStorage (CarryMem + 本地JSON)

**特性**：
- 11种意图模式（中英文）
- 4种规则类型：always / avoid / prefer / forbid
- 规则内容prompt注入防护（14种模式）
- CarryMem优先 + 本地JSON备存储
- 规则自动注入到Worker提示词

### 项目全生命周期（11阶段模型）

DevSquad V3.6.1 定义了 **11阶段（4可选）** 的项目全生命周期，每个阶段有明确的角色、依赖和门禁条件：

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

| 模板 | 阶段 | 适用场景 |
|------|------|---------|
| `full` | P1-P11全部 | 完整项目 |
| `backend` | 无P5 | 后端服务 |
| `frontend` | 无P4,P6 | 前端应用 |
| `internal_tool` | 无P4,P5,P6,P11 | 内部工具 |
| `minimal` | P1,P3,P7,P8,P9 | 最小集 |

详见 [GUIDE.md](../../GUIDE.md) §4 获取完整生命周期详情、门禁条件和需求变更流程。

### 开发者体验
- **配置文件**：项目根目录 `.devsquad.yaml` + 环境变量覆盖
- **质量控制注入**：基于 `.devsquad.yaml` 配置，自动将 QC 规则（幻觉预防、过度自信检查、安全守卫、RACI 协议）注入 Worker 提示词
- **Docker 支持**：`docker build -t devsquad .`
- **GitHub Actions CI**：Python 3.9-3.12 矩阵测试
- **pip 可安装**：`pip install -e .` + 可选依赖

## 📦 模块参考 (53 模块)

| # | 模块 | 文件 | 职责 |
|---|------|------|------|
| 1 | **MultiAgentDispatcher** | `dispatcher.py` | 统一入口点 |
| 2 | **Coordinator** | `coordinator.py` | 全局编排：计划 → 分派 → 执行 → 收集 |
| 3 | **Worker** | `worker.py` | 角色执行器，集成 LLM 后端 |
| 4 | **EnhancedWorker** | `enhanced_worker.py` | 增强型 Worker，自动质量保证（简报 + 置信度 + 重试 + 记忆规则） |
| 5 | **Scratchpad** | `scratchpad.py` | 共享黑板，用于 Worker 间通信 |
| 6 | **ConsensusEngine** | `consensus.py` | 加权投票 + 否决权 + 升级机制 |
| 7 | **RoleMatcher** | `role_matcher.py` | 基于关键词的角色匹配，支持别名解析 |
| 8 | **ReportFormatter** | `report_formatter.py` | 结构化/紧凑/详细报告生成 |
| 9 | **InputValidator** | `input_validator.py` | 安全验证 + Prompt 注入检测 |
| 10 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM 驱动的语义角色匹配 |
| 11 | **CheckpointManager** | `checkpoint_manager.py` | 状态持久化 + 交接文档 |
| 12 | **WorkflowEngine** | `workflow_engine.py` | 任务→工作流自动拆分 + 11阶段生命周期模板 + 需求变更管理 |
| 13 | **TaskCompletionChecker** | `task_completion_checker.py` | 完成度跟踪 + 进度报告 |
| 14 | **CodeMapGenerator** | `code_map_generator.py` | 基于 Python AST 的代码结构分析 |
| 15 | **DualLayerContextManager** | `dual_layer_context.py` | 项目级 + 任务级上下文管理 |
| 16 | **SkillRegistry** | `skill_registry.py` | 可复用技能注册与发现 |
| 17 | **IntentWorkflowMapper** | `intent_workflow_mapper.py` | 用户意图 → 工作流链映射（6种意图 × 3语言） |
| 18 | **OperationClassifier** | `operation_classifier.py` | 三级操作分类（ALWAYS_SAFE/NEEDS_REVIEW/FORBIDDEN） |
| 19 | **FiveAxisConsensusEngine** | `five_axis_consensus.py` | 五维审查共识引擎，加权投票 |
| 20 | **FeatureUsageTracker** | `feature_usage_tracker.py` | 功能使用跟踪 + 报告 + 自动持久化 |
| 21 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic 后端，支持流式输出 |
| 22 | **LLMCache** | `llm_cache.py` | 基于 TTL 的 LRU 缓存，支持磁盘持久化 |
| 23 | **LLMRetry** | `llm_retry.py` | 指数退避 + 熔断器 |
| 24 | **ConfigManager** | `config_loader.py` | YAML 配置 + 环境变量覆盖 |
| 25 | **PromptAssembler** | `prompt_assembler.py` | 动态提示词组装 + QC 规则注入 |
| 26 | **AgentBriefing** | `agent_briefing.py` | 上下文感知的任务简报，优先级过滤 |
| 27 | **ConfidenceScorer** | `confidence_score.py` | 五因子响应质量评估 |
| 28 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99 跟踪 + CPU/内存监控 |
| 29 | **MCEAdapter** | `mce_adapter.py` | CarryMem 集成适配器（可选依赖，支持 match_rules + format_rules_as_prompt + add_rule） |
| 30 | **Protocols** | `protocols.py` | 接口定义（CacheProvider, MemoryProvider 等） |
| 31 | **NullProviders** | `null_providers.py` | 优雅降级提供者 |
| 32 | **PermissionGuard** | `permission_guard.py` | 四级安全门控 |
| 33 | **MemoryBridge** | `memory_bridge.py` | 跨会话记忆 |
| 34 | **BatchScheduler** | `batch_scheduler.py` | 批量任务调度 |
| 35 | **ContextCompressor** | `context_compressor.py` | 长任务上下文压缩 |
| 36 | **RoleTemplateMarket** | `role_template_market.py` | 角色模板共享市场 |
| 37 | **Skillifier** | `skillifier.py` | 从任务中自动学习技能 |
| 38 | **UsageTracker** | `usage_tracker.py` | Token/成本跟踪 |
| 39 | **WarmupManager** | `warmup_manager.py` | 启动预热优化 |
| 40 | **TestQualityGuard** | `test_quality_guard.py` | 测试质量强制执行 |
| 41 | **PromptVariantGenerator** | `prompt_variant_generator.py` | A/B 提示词测试 |
| 42 | **ConfigManager (YAML)** | `config_manager.py` | 项目级 YAML 配置 |
| 43 | **WorkBuddyClawSource** | `memory_bridge.py` | WorkBuddy 只读桥接 |
| 44 | **Models** | `models.py` | 共享数据模型和类型定义 |
| 45 | **LLMCacheAsync** | `llm_cache_async.py` | 异步 LLM 缓存，用于并发工作负载 |
| 46 | **LLMRetryAsync** | `llm_retry_async.py` | 异步 LLM 重试，带退避策略 |
| 47 | **IntegrationExample** | `integration_example.py` | DevSquad 集成示例代码 |
| 48 | **AsyncIntegrationExample** | `async_integration_example.py` | 异步 DevSquad 集成示例 |
| 49 | **AnchorChecker** | `anchor_checker.py` | 里程碑锚点验证 + 漂移检测 + 自动恢复 |
| 50 | **RetrospectiveEngine** | `retrospective.py` | 独立调度后复盘 + 模式提取 + 反模式检测 |
| 51 | **FeatureUsageTracker** | `feature_usage_tracker.py` | 功能调用计数器 + 使用报告 + 自动持久化 |
| 52 | **FallbackBackend** | `llm_backend.py` | 自动 LLM 后端故障转移 + 健康监控 |
| 53 | **FeedbackControlLoop** | `feedback_control_loop.py` | 控制论反馈闭环，自适应调整 |

## 配置

创建 `.devsquad.yaml`（放在项目根目录）：

```yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85
  ai_quality_control:
    enabled: true
    hallucination_check:
      enabled: true
      require_traceable_references: true
    overconfidence_check:
      enabled: true
      require_alternatives_min: 2
  ai_security_guard:
    enabled: true
    permission_level: "DEFAULT"
  ai_team_collaboration:
    enabled: true
    raci:
      mode: "strict"

llm:
  backend: openai
  base_url: ""  # 通过 LLM_BASE_URL 环境变量设置
  model: ""     # 通过 LLM_MODEL 环境变量设置
  timeout: 120
  log_level: WARNING
```

或使用环境变量（优先级更高）：

```bash
export DEVSQUAD_LLM_BACKEND=openai
export DEVSQUAD_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_MODEL=gpt-4
export OPENAI_API_KEY=sk-...
```

## 运行测试

```bash
# 核心测试（1561+测试全通过）
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py \
  tests/ test_v35_integration.py -v

# 快速冒烟测试
python3 scripts/cli.py --version    # 3.6.1
python3 scripts/cli.py status       # 系统就绪
python3 scripts/cli.py roles        # 列出 7 个角色
```

## 文档

| 文档 | 说明 |
|------|------|
| [GUIDE.md](../../GUIDE.md) | 完整用户指南（中文） |
| [GUIDE_EN.md](GUIDE_EN.md) | 完整用户指南（英文） |
| [GUIDE_JP.md](GUIDE_JP.md) | 完整用户指南（日文） |
| [INSTALL.md](../../INSTALL.md) | 安装指南 |
| [EXAMPLES.md](../../EXAMPLES.md) | 真实使用示例 |
| [SKILL.md](../../SKILL.md) | 技能手册 |
| [SKILL_CN.md](SKILL_CN.md) | 中文技能手册 |
| [SKILL_JP.md](SKILL_JP.md) | 日本語スキルマニュアル |
| [README.md](../../README.md) | English README |
| [README_JP.md](README_JP.md) | 日本語説明 |

## 版本历史

| 日期 | 版本 | 亮点 |
|------|------|------|
| 2026-05-17 | **V3.6.1** | 🔄 **控制论增强** — 5个新模块(反馈闭环/执行守护/性能指纹/任务推荐/自适应角色)，来自上游v2.5控制论架构分析。110个新测试，总计1561。Mock模式零依赖可用。 |
| 2026-05-16 | **V3.6.0** | 🧩 **分层子Skill架构** — 6个原子子Skill(dispatch/intent/review/security/test/retrospective)，懒加载注册表，每个~50行薄封装。跨平台兼容：Claude Code/Cursor/OpenClaw/纯Python/Docker/MCP 全部支持。Mock模式零依赖可用。 |
| 2026-05-13 | **V3.6.0** | ⚓ AnchorChecker（里程碑锚点验证+漂移检测）、RetrospectiveEngine（独立复盘+模式提取）、StructuredGoal（层次化目标分解+进度跟踪）、FallbackBackend（自动LLM故障转移+健康监控）、FeatureUsageTracker（功能调用统计+使用报告+自动持久化）、7模块集成（IntentWorkflowMapper/AISemanticMatcher/DualLayerContextManager/OperationClassifier/SkillRegistry/FiveAxisConsensusEngine/NullProviders）、1548+测试、48核心模块 |
| 2026-05-05 | **V3.5.0** | 📋 增强冲刺 — 代码走读增强、文档一致性检查、Karpathy原则、项目理解（AgentBriefing）、CLI生命周期命令、结构化输出、748+测试 |
| 2026-05-03 | **V3.4.1** | 🚀 智能体技能质量框架 (P0) — AntiRationalizationEngine + VerificationGate + IntentWorkflowMapper + CLI生命周期命令 (spec/plan/build/test/review/ship) + 167新测试 + Google智能体技能集成 + 49核心模块 |
| 2026-05-02 | **V3.4.0** | 🆕 11阶段项目全生命周期（full/backend/frontend/internal_tool/minimal模板）、需求变更管理、门禁机制+差距报告、自然语言规则收集(RuleCollector)、560+测试通过 |
| 2026-04-27 | V3.4.0 | 真实 LLM 后端、ThreadPoolExecutor 并行、输入验证+Prompt注入防护、检查点管理、工作流引擎、流式输出、Docker、CI、配置文件、CarryMem集成 |
| 2026-04-17 | V3.2 | E2E Demo、MCE 适配器 |
| 2026-04-16 | V3.0 | 完整重设计 — Coordinator/Worker/Scratchpad 架构 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
