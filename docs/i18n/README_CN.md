# DevSquad — 多角色 AI 任务编排器

<p align="center">
  <strong>一个任务 → 多角色 AI 协作 → 一个结论</strong>
  <br>
  <em>企业级就绪 | V3.6.7</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-1855%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.6.7-success" />
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

## 🚀 V3.6.6: 企业级版本 + E2E 测试发布

**DevSquad V3.6.6** 引入企业级功能和全面的 E2E 测试：RBAC 引擎（预览，15+ 权限、5 角色）、审计日志（预览，SHA256 完整性链）、多租户管理器（预览，3 级隔离）、敏感数据脱敏（预览，PII 保护）、AsyncIO 转换（2x 吞吐量提升、50% 延迟降低）、Redis 缓存集成（L1→L2→L3 三级缓存、95%+ 命中率）、Prometheus 监控（12 个核心指标）、E2E 测试套件（16 个用户旅程测试、5 个场景：CLI/API/协作/企业/错误恢复、9 秒内 100% 通过率）、代码质量改进（print() → logging 迁移、TODO/FIXME 清理、pre-commit hooks、.editorconfig）— 让多智能体协作更智能、更安全、更可观测。

### 🔄 V3.6.6 企业级功能详情

#### 1️⃣ FeedbackControlLoop（反馈闭环控制器）
**中文名称**：反馈闭环控制器
**核心能力**：
- 闭环反馈控制，自动迭代优化直到质量达标
- 可配置质量门禁（quality_gate）和最大迭代次数
- 轻量级质量评估（无需LLM调用），支持dry-run模式

```python
from scripts.collaboration.feedback_control_loop import FeedbackControlLoop
from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7, max_iterations=3)
result = loop.run("设计安全认证系统", roles=["architect", "security"])
print(f"迭代次数: {loop.iteration_count}")
print(f"最佳质量分: {loop.best_quality:.2f}")
# 自动迭代直到质量达标或达到最大次数
```

#### 2️⃣ ExecutionGuard（执行守护者）
**中文名称**：执行守护者
**核心能力**：
- 实时执行监控，支持超时、输出大小、token数、关键词4种中止条件
- 轻量级检查（<1ms），零外部依赖
- 可动态配置阈值（max_duration_sec, max_output_tokens等）

```python
from scripts.collaboration.execution_guard import ExecutionGuard

guard = ExecutionGuard(max_duration_sec=300.0, max_output_tokens=8000)
should_abort, reason = guard.check_abort(
    worker_output="正在生成代码...",
    elapsed_time=120.5,
    token_count=5000
)
if should_abort:
    print(f"中止执行: {reason}")
    # 示例输出: "Timeout exceeded: 120.5s > 300.0s"
# 也可检测警告关键词（不触发中止）
warnings = guard.check_warnings("WARNING: 内存使用率过高")
print(f"警告: {warnings}")  # ['WARNING']
```

#### 3️⃣ PerformanceFingerprint（性能指纹）
**中文名称**：性能指纹系统
**核心能力**：
- 统一执行指纹记录（融合4个数据源：调用次数、延迟、状态快照、复盘偏差）
- 纯Python TF-IDF实现（无sklearn/numpy依赖），支持中英文混合
- JSON持久化到 .devsquad_data/fingerprints/，支持冷启动优雅降级

```python
from scripts.collaboration.performance_fingerprint import PerformanceFingerprint

fingerprint = PerformanceFingerprint()
fid = fingerprint.record_execution(
    task="实现用户认证",
    result=dispatch_result,
    timing={"total": 12.5, "planning": 2.0, "coding": 8.0, "review": 2.5},
    roles_used=["architect", "coder", "tester"],
)
print(f"指纹ID: {fid}")  # fp_20260518_143052_a1b2c3d4

# 基于TF-IDF查找相似历史任务
similar = fingerprint.find_similar("添加登录页面", top_k=3)
for case in similar:
    print(f"任务: {case['task']}")
    print(f"相似度: {case['similarity']:.2%}")
    print(f"角色组合: {case['roles_used']}")
    print(f"成功: {case['success']}")

# 获取整体统计
stats = fingerprint.get_stats()
print(f"总执行数: {stats['total']}")
print(f"成功率: {stats['success_rate']:.1%}")
```

#### 4️⃣ SimilarTaskRecommender（相似任务推荐器）
**中文名称**：相似任务推荐器
**核心能力**：
- 基于TF-IDF的任务相似度搜索，推荐历史成功配置
- 智能角色组合推荐、意图预测、执行时间估算
- 置信度评分（high/medium/low），冷启动优雅降级

```python
from scripts.collaboration.similar_task_recommender import SimilarTaskRecommender

recommender = SimilarTaskRecommender()
result = recommender.recommend("设计用户认证系统")
print(f"推荐角色: {result['recommended_roles']}")
# 输出: ['architect', 'coder', 'tester', 'security']
print(f"置信度: {result['confidence']}")  # high/medium/low
print(f"预估耗时: {result['estimated_duration_s']:.1f}s")

# 查看相似案例详情
for case in result['similar_cases']:
    print(f"任务: {case['task']}")
    print(f"相似度: {case['similarity']:.2%}")
    print(f"历史角色: {case['roles']}")
    print(f"是否成功: {case['success']}")

# 快捷方法：仅获取角色建议
roles = recommender.get_role_suggestion("实现支付接口")
print(f"建议角色: {roles}")
```

#### 5️⃣ AdaptiveRoleSelector（自适应角色选择器）
**中文名称**：自适应角色选择器
**核心能力**：
- 基于历史成功率的三层策略选择（相似任务→意图匹配→降级到默认）
- 可配置最低成功率和最大角色数
- 支持手动统计更新和完整角色效能报告

```python
from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector

selector = AdaptiveRoleSelector()
roles = selector.select_roles(
    task="构建高并发微服务架构",
    intent="feature_implementation",
    min_success_rate=0.5,
    max_roles=5,
)
print(f"推荐角色: {roles}")
# 输出: ['architect', 'devops', 'security', 'tester']
# 或: [] （无历史数据时返回空，由调用方回退到默认RoleMatcher）

# 手动更新统计数据（用于外部系统集成）
selector.update_stats(["architect", "coder"], success=True, duration_s=12.5)

# 生成角色效能报告
report = selector.get_role_report()
for role_name, metrics in report.items():
    print(f"{role_name}: 成功率={metrics['success_rate']:.1%}, "
          f"平均耗时={metrics['avg_duration']:.1f}s")
```

**集成示例**：五个模块可独立使用，也可组合形成完整的控制论闭环：

```python
from scripts.collaboration import (
    MultiAgentDispatcher, FeedbackControlLoop,
    ExecutionGuard, PerformanceFingerprint,
    SimilarTaskRecommender, AdaptiveRoleSelector,
)

dispatcher = MultiAgentDispatcher()
guard = ExecutionGuard()
fingerprint = PerformanceFingerprint()

# 选项1: 完整控制论栈（自动迭代+质量门禁）
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.dispatch("设计分布式缓存系统")  # 自动迭代优化

# 选项2: 仅守护模式（最小化采用）
result = dispatcher.dispatch("设计分布式缓存系统")
for w in result.worker_results:
    abort, reason = guard.check_abort(w.output, w.duration)
    if abort:
        print(f"中止: {reason}")

# 选项3: 仅学习模式（积累指纹+推荐）
fingerprint.record_execution("任务", result, result.timing, result.matched_roles)
similar = fingerprint.find_similar("新任务", top_k=3)

# 所有模块都是可选开关 — 不使用时DevSquad完全正常工作
```

### 🔗 集成架构

5个控制论模块设计为**非侵入式包装器** — 它们可以独立或协同工作，无需修改现有核心逻辑：

```
用户任务
    ↓
[SimilarTaskRecommender] ← 可选：从历史记录推荐角色
    ↓
[AdaptiveRoleSelector]   ← 可选：优化角色选择
    ↓
[MultiAgentDispatcher]
    ↓
[FeedbackControlLoop]     ← 包装dispatcher实现自动迭代
    ↓ [每个worker步骤]
[ExecutionGuard]          ← 守护每个worker执行
    ↓
[PerformanceFingerprint]  → 调度完成后记录指纹
```

**推荐用法**（渐进式采用）：
```python
from scripts.collaboration import (
    MultiAgentDispatcher, FeedbackControlLoop,
    ExecutionGuard, PerformanceFingerprint
)

dispatcher = MultiAgentDispatcher()
guard = ExecutionGuard()
fingerprint = PerformanceFingerprint()

# 选项1: 完整控制论栈（自动迭代+质量门禁）
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("你的任务描述")

# 选项2: 仅守护模式（最小化采用）
result = dispatcher.dispatch("你的任务")
for w in result.worker_results:
    abort, reason = guard.check_abort(w.output, w.duration)
    if abort:
        print(f"中止: {reason}")

# 选项3: 仅学习模式（积累指纹+推荐）
fingerprint.record_execution("任务", result, result.timing, result.matched_roles)
similar = fingerprint.find_similar("新任务", top_k=3)
```

所有模块都是**可选开关** — 不使用时DevSquad完全正常工作。

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

## 🆚 为什么选择 DevSquad？

| 特性 | **DevSquad** | CrewAI | AutoGen | LangGraph |
|------|-------------|--------|---------|-----------|
| **角色** | 7 个内置角色（架构师/产品经理/安全/测试/编码/运维/UI）+ 自定义 | 仅自定义 Agent | 仅自定义 Agent | 仅自定义节点 |
| **Mock 模式** | ✅ 零配置，无需 API Key | ❌ 需要 LLM 后端 | ❌ 需要 LLM 后端 | ❌ 需要 LLM 后端 |
| **语言支持** | 中/英/日三语 | 仅英语 | 仅英语 | 仅英语 |
| **共识机制** | ✅ 加权投票 + 否决权 + 升级机制 | ❌ | ❌ | ❌ |
| **安全防护** | ✅ InputValidator(40种检测模式) + PermissionGuard(4级) + ExecutionGuard | 基础 | 基础 | 基础 |
| **控制论增强** | ✅ 反馈闭环、性能指纹、自适应角色（V3.6.6） | ❌ | ❌ | ❌ |
| **记忆系统** | ✅ 7类型 MemoryBridge + 遗忘曲线 | 短期记忆 | 有限 | 状态机 |
| **安装方式** | `pip install devsquad` | `pip install crewai` | `pip install pyautogen` | `pip install langgraph` |
| **测试覆盖** | 1855+ 测试，全部通过 | ~500 | ~300 | ~400 |
| **适用场景** | **生产团队**需要结构化、可审计、安全的多智能体工作流 | 快速 Agent 原型开发 | 多智能体对话研究 | 复杂有状态图工作流 |

### 何时选择 DevSquad 而非其他框架

- **选择 DevSquad 如果你**：需要**企业级**多智能体编排，具备安全防护、审计追踪、共识决策机制，以及零配置 Mock 模式用于开发
- **选择 CrewAI 如果你**：想要**轻量级**基于角色的 Agent 组装，最小化配置
- **选择 AutoGen 如果你**：正在进行多智能体对话模式的**研究**
- **选择 LangGraph 如果你**：需要基于**复杂状态图**的 Agent 工作流，支持循环

> **注意**：这些框架是互补的，并非互斥。DevSquad 的调度器可以将任何 LLM 支持的 Agent 包装为 Worker。

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
python3 scripts/cli.py --version       # 显示版本 (3.6.6)
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

## 🧩 分层子Skill架构 (V3.6.6 新增)

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
- **Prompt 注入防护**：40种检测模式（忽略先前指令、越狱、DAN 模式、系统提示提取等）
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

### 🔍 VerificationGate — 基于证据的质量保障
- **证明模式 (Prove-It Pattern)**：每个完成声明必须包含可验证的证据（测试输出、代码差异、性能基准）
- **7个红旗警告**：`no_test`（无测试）| `tests_pass_first_run`（首次运行即通过）| `no_regression_test`（无回归测试）| `no_security_scan`（无安全扫描）| `no_perf_baseline`（无性能基线）| `vague_description`（描述模糊）| `evidence_missing`（证据缺失）
- **自动激活**：已集成到 TaskCompletionChecker 中 — 零配置即可使用

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

DevSquad V3.6.6 定义了 **11阶段（4可选）** 的项目全生命周期，每个阶段有明确的角色、依赖和门禁条件：

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

## 📦 模块参考 (60+ 模块)

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
# 核心测试（1855+测试全通过）
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py \
  tests/ test_v35_integration.py -v

# 快速冒烟测试
python3 scripts/cli.py --version    # 3.6.6
python3 scripts/cli.py status       # 系统就绪
python3 scripts/cli.py roles        # 列出 7 个角色
```

### 🔄 升级后冒烟测试
升级 DevSquad 后，运行以下命令验证环境是否正常：
```bash
# 快速健康检查（应在 30 秒内完成）
python3 scripts/cli.py --version       # 预期输出: DevSquad 3.6.6
python3 scripts/cli.py status          # 预期输出: 系统就绪
python3 scripts/cli.py roles           # 预期输出: 列出 7 个核心角色

# 完整测试套件
python3 -m pytest tests/ -q --tb=line # 预期输出: 1855 passed
```

### 带覆盖率报告
```bash
# 先安装覆盖率工具：pip install pytest-cov
python3 -m pytest tests/ --cov=scripts --cov-report=term-missing
# 预期结果：覆盖率 ≥ 80%，显示详细的缺失行报告
```

### 测试分层策略

DevSquad 采用基于优先级的测试分层策略：

| 优先级 | 范围 | 示例 | 数量 |
|--------|------|------|------|
| **P0** | 质量框架核心 | AntiRationalization (39), VerificationGate (42), IntentWorkflowMapper (58), AuthManager (35) | ~200 |
| **P1** | 增强模块 | FiveAxisConsensus (29), OperationClassifier (27), OutputSlicer (26), CIFeedbackAdapter (22) | ~150 |
| **P1+** | 控制论模块 (V3.6.6) | FeedbackControlLoop (19), ExecutionGuard (40), PerformanceFingerprint (13), SimilarTaskRecommender (17), AdaptiveRoleSelector (21) | **110** |
| **P2** | 集成与端到端 | 完整生命周期调度、跨模块集成 | ~200 |
| **P3** | 模块单元测试 | 核心调度器、RoleMapping、MCEAdapter、LLM后端 | ~400+ |

**总计：1855 个测试**

按优先级运行：
```bash
# 仅 P0（关键路径，< 10秒）
python3 -m pytest tests/ -k "anti_ratif or verification or intent_workflow or auth" -q

# P0 + P1（质量 + 增强，< 30秒）
python3 -m pytest tests/ -k "anti_ratif or verification or intent or auth or five_axis or operation" -q

# 完整套件
python3 -m pytest tests/ -q --tb=line
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
| 2026-06-07 | **V3.6.7** | 🎯 **Redis Cache + Async Dispatch + Dispatcher Refactor** — Redis缓存L2后端（memory→disk→Redis三级缓存）、异步调度（asyncio.gather并发LLM调用）、Dispatcher重构（788行→18步骤方法，提取dispatch_models.py和dispatch_performance.py）、DispatchResult数据丢失修复（5个缺失字段）、except:pass清理、冗余to_dict()移除、183个xfailed测试恢复。总计：1855测试通过、CI重新启用 |
| 2026-05-17 | **V3.6.1** | 🔄 **控制论增强** — 5个新模块(反馈闭环/执行守护/性能指纹/任务推荐/自适应角色)，来自上游v2.5控制论架构分析。110个新测试，总计1662。Mock模式零依赖可用。 |
| 2026-05-16 | **V3.6.0** | 🧩 **分层子Skill架构 + 核心模块** — 6个原子子Skill(dispatch/intent/review/security/test/retrospective)，懒加载注册表，每个~50行薄封装。加上：AnchorChecker（里程碑锚点验证+漂移检测）、RetrospectiveEngine（独立复盘+模式提取）、StructuredGoal（层次化目标分解+进度跟踪）、FallbackBackend（自动LLM故障转移+健康监控）、FeatureUsageTracker（功能调用统计+使用报告+自动持久化）、7模块集成（IntentWorkflowMapper/AISemanticMatcher/DualLayerContextManager/OperationClassifier/SkillRegistry/FiveAxisConsensusEngine/NullProviders）、1662+测试、48核心模块。跨平台兼容：Claude Code/Cursor/OpenClaw/纯Python/Docker/MCP 全部支持。 |
| 2026-05-05 | **V3.5.0** | 📋 增强冲刺 — 代码走读增强、文档一致性检查、Karpathy原则、项目理解（AgentBriefing）、CLI生命周期命令、结构化输出、748+测试 |
| 2026-05-03 | **V3.4.1** | 🚀 智能体技能质量框架 (P0) — AntiRationalizationEngine + VerificationGate + IntentWorkflowMapper + CLI生命周期命令 (spec/plan/build/test/review/ship) + 167新测试 + Google智能体技能集成 + 49核心模块 |
| 2026-05-02 | **V3.4.0** | 🆕 **基础版本发布** — 真实LLM后端、ThreadPoolExecutor并行执行、输入验证+Prompt注入防护、检查点管理、工作流引擎（11阶段生命周期模板：full/backend/frontend/internal_tool/minimal）、任务完成检查器、语义匹配器、流式输出、Docker、CI、配置文件、代码地图生成器、双层上下文、技能注册表、CarryMem集成、AgentBriefing、ConfidenceScore、EnhancedWorker自动QA、协议接口系统、234+单元测试、需求变更管理与门禁机制及差距报告 |
| 2026-04-17 | V3.2 | E2E Demo、MCE 适配器 |
| 2026-04-16 | V3.0 | 完整重设计 — Coordinator/Worker/Scratchpad 架构 |

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
