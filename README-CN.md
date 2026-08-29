# DevSquad — 多角色 AI 任务编排器

<p align="center">
  <strong>🎯 把「单个 AI 助手」升级成「7 人 AI 专业团队」</strong>
  <br>
  <em>一个任务 → 多角色 AI 协作 → 一个结论 | V4.5.9 (执行层统一 gather 化 + Worker 原生异步) | V4.5.8 (FileRiskStore 持久化 + risks add/assess/mitigate/close + exposure 过滤) | V4.5.7 (Coeffect 异步化 + Risk Register UX CLI) | V4.5.6 (Module Fiber + Coeffect: 6 状态 FSM + 拓扑激活 + modules CLI) | V4.5.3 (Artifacts + Effect — ArtifactStore + DispatchEffect + EffectRegistry + Audit CLI) | V4.5.2 (体验打磨: MOKA + Metrics + GitLab + Doctor + BackendConfig) | V4.5.0 (跨会话连续性 + 协议原生 Skill)</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-8600%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V4.5.9-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

## 📖 太长不看？先看这个（30 秒）

### DevSquad 是什么？

**DevSquad** 是一个多角色 AI 任务编排器。当你提交一个任务时，它不再是单个 AI 回答，而是让 **7 个专业角色**（架构师、安全专家、测试员、开发者等）**并行协作**，最后给出经过多方审核的结论。

```
传统 AI:  你 ──→ ChatGPT ──→ 一个回答（可能不全面）
DevSquad:  你 ──→ DevSquad ──→ [架构师+安全+测试+开发...] ──→ 多维度共识结论
```

### 核心优势（对比单 AI）

| 痛点 | 传统单 AI | DevSquad |
|------|----------|----------|
| **视角单一** | 只有通用视角 | 7 个专业角色并行审视 ✅ |
| **质量不可控** | 可能遗漏安全问题 | 多维度交叉验证 + 共识机制 ✅ |
| **无审计追踪** | 不知道回答依据什么 | 完整审计链 + SHA256 完整性校验 ✅ |
| **复杂任务崩溃** | 长任务容易丢失上下文 | Checkpoint 断点续传 + 工作流引擎 ✅ |

### 最快上手（5 分钟）

```bash
# 安装
pip install devsquad

# 运行 - 让 AI 团队帮你设计认证系统
devsquad run "设计一个安全的用户认证系统" --roles architect,security,tester,coder

# 输出结构化报告：
# ✅ 架构师建议：采用 JWT + Refresh Token 方案...
# ✅ 安全专家审查：需防范 CSRF、XSS、SQL 注入...
# ✅ 测试策略：单元测试覆盖率达 90%+...
# ✅ 开发实现：提供完整代码框架...
# 📊 共识结论：方案可行，风险可控...
```

### 什么时候用 DevSquad？

| 你的需求 | 推荐方案 |
|---------|---------|
| 简单问答（"Python 怎么写 for 循环？"） | 直接用 ChatGPT/Claude ✅ |
| 代码片段审查 | DevSquad 单角色模式 ✅ |
| 复杂系统设计（需要多视角） | **DevSquad 多角色协作** 🎯 |
| 生产环境自动化流程 | **DevSquad + REST API + Dashboard** 🎯 |

📚 **想深入了解？** → [完整快速入门指南](QUICKSTART.md) | [187+ 模块详细参考](SKILL.md)

---

<details>
<summary>🔍 点击展开：完整功能介绍与架构详解</summary>

## 🚀 V4.5.2: Approval Gate + Connector Framework + 反幽灵 E2E

**DevSquad V4.5.2**（PATCH 发布，符合 SemVer）引入 2 个新模块并完成 3 个 ROADMAP 项（V451-1、V451-2、V451-7/8/9）。所有新模块默认采用安全、向后兼容的行为——无 API 破坏性变更。详见 [docs/release_notes/V4.5.2_RELEASE_NOTES.md](docs/release_notes/V4.5.2_RELEASE_NOTES.md) 完整发布说明。

### V4.5.2 — 2 个新模块 + 3 个 ROADMAP 项
- **ApprovalGate**：外部操作的用户级审批机制。回调异常时 fail-closed。未配置回调时自动批准（向后兼容）。
- **ConnectorFramework**：外部系统集成的协议接口（GitHub 优先）。`Connector` Protocol + `GitHubConnector`（api/cli/simulation 三种模式）。调度管线默认强制 `simulation=True`。
- **V451-7 Dashboard 浏览器级 E2E**：11 个 AppTest 用例（Streamlit AppTest 替代 Playwright——避免重浏览器依赖，仍是浏览器级 DOM 仿真）
- **V451-8 REST API 端到端用户旅程 E2E**：190 个 E2E 测试覆盖 dispatch→history→roles→quick dispatch→error handling→lifecycle→cross-entry
- **V451-9 Connector Framework 反幽灵 E2E**：12 个 E2E 测试（AG-1 到 AG-8）证明管线激活

### V4.5.0: 跨会话连续性 + 协议原生 Skill 架构 + 行动优先报告

**DevSquad V4.5.0**（合并 V4.4.3 + V4.4.4 + V4.5.0 变更一次性发布）交付 10 项新特性，覆盖跨会话连续性、协议原生 Skill 架构和行动优先报告。7 角色 AI 团队编排复杂工程任务，提供完整审计链和共识机制。详见 [docs/VISION.md](docs/VISION.md) 项目愿景。

### V4.5.0 — 10 项新特性
- **ScratchpadHistoryStore**: SQLite 跨会话 Scratchpad 搜索
- **AgentIdentity**: 确定性 agent ID，用于跨会话追踪
- **WorkflowTrace**: dispatch 报告中透明工作流追踪
- **GitContext**: Git 分支/commit 上下文注入 dispatch
- **SkillProvider Protocol**: 协议原生 Skill 架构（Builtin + MCP providers）
- **OutputStyle**: 行动优先报告格式（源自 i-have-adhd 洞察）
- **SessionResume CLI**: `devsquad sessions list` + `dispatch --resume`
- **FileBundler**: review 模式确定性文件打包（源自 open-code-review）
- **SKILL.md 模块化拆分**: 1216→282 行 + 3 参考文档（MODULE_REFERENCE / SUB_SKILLS / VERSION_HISTORY）
- **VISION 文档**: docs/VISION.md + VISION_ORCHESTRATION.md + VISION_AGENT_COLLABORATION.md

### V4.4.0 — P0-P3 增强模块（5 个新模块）
- **P0-1 RiskRegister**: PMP 风险管理；7 角色加权评估（probability × impact）+ 4 种响应策略（规避/转移/减轻/接受）+ `GateType.RISK_CHECK` 门禁（exposure ≥ 0.36 阻断）
- **P0-2 ViewpointRegistry**: TOGAF 架构视点；7 角色绑定正式视点 + `is_orthogonal()` 正交性判断 + `check_consistency()` 矛盾检测
- **P1-1 ErrorBudgetTracker**: SRE 错误预算；SLO 99.9% 默认 + `GateType.ERROR_BUDGET` P10 门禁（预算耗尽阻断功能部署）+ `burn_rate()` 消耗速率
- **P1-2 GapAnalyzer**: TOGAF 差距分析；`analyze(current, target)` + `prioritize()` + `generate_roadmap()` + `suggest_scheduler_decision()` 驱动 LoopScheduler
- **P2-1 DoraMetricsCollector**: DORA 指标（部署频率 / Lead Time / 变更失败率 / MTTR）+ `GateType.DORA_CHECK` P11 门禁（CFR > 15% 触发架构评审）+ Elite/High/Medium/Low 评级

### V4.4.1 — 外部文档重构
- 归档孤儿 i18n 文档（docs/i18n/ → docs/_archive/i18n/）
- 退休 CHANGELOG-CN.md（CHANGELOG.md 成为所有语言的 SSOT）
- 合并管理员凭证到 INSTALL.md（单一信息源）
- 重新编号 INSTALL.md 方法为连续 1-7
- 同步所有外部文档版本号（README/SKILL/INSTALL/CLAUDE）

### V4.4.2 — 多语言 + Dashboard 增强
- 多语言角色 prompt（EN/CN/JP）覆盖全部 7 角色
- Dashboard 6-Tab 可见性（Overview/Dispatch/Lifecycle/Metrics/Audit/Settings）
- P2 Kanban 评估（在制品限制 + 周期时间追踪）
- P3 ITSM 评估（事件管理 + 变更顾问委员会模拟）
- 13 个 E2E 测试 xpass + 防幽灵计数器

### 防幽灵功能保证
每个新模块包含 `_call_counter` 机制 + E2E anti_ghost 测试 + CI `check_module_activation.py` 验证。模块必须真正接入 dispatch pipeline（不仅实例化），且 Markdown 报告章节用户可见。V4.5.2 将此模式从 V4.4.0（RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector）扩展到 V4.5.2（ApprovalGate / ConnectorFramework）。

### 测试金字塔达标
- **Contract 测试**: 5.2%（目标 ≥5% ✅）
- **Integration 测试**: 15.1%（目标 ≥15% ✅）
- **总测试数**: 8392+（CI 权威）
- **E2E 覆盖**: 107 e2e + 1244 integration + 13 V4.4.0 anti-ghost + 12 V4.5.2 anti-ghost

### 历史特性（V4.0.0-V4.3.3）
- **V4.3.3**: P0-P3 增强 E2E 骨架（xfail TDD for V4.4.0）
- **V4.3.2**: LLM vs Mock 质量差距衡量（校准门 + 薄切片探针）
- **V4.3.0 Phase 3**: 质量补强 + 用户模拟 E2E（NPS 9/10）
- **V4.3.0 Phase 2**: OutputValidator 完整集成（LLM 输出安全检测）
- **V4.3.0 Phase 1**: DependencyHallucinationChecker（防 Slopsquatting 供应链攻击）
- **V4.3.0 Phase 0**: DeploymentComplianceChecker（防违规部署兜底）
- **V4.0.0 P1-1 Loop Engineering**: Discovery → Handoff → Verification → Persistence → Scheduling 五步闭环
- **V4.0.0 P1-2 UI/UX 巡检**: 4 维度审计 + PIL 像素 diff 视觉回归
- **V4.0.0 P2-1 Adversarial 验证**: 红队攻击 + 蓝队防御 + 裁判仲裁
- **V4.0.0 P2-2 DAG 可视化**: Mermaid / JSON / DOT 三格式
- **V4.0.0 P3-1 Autonomous**: plan → dev → verify → fix 4 阶段自主迭代
- **V4.0.0 P3-2 插件热加载**: 3 加载路径 + 路径穿越三层防护 + reload 回滚

8996+ tests passing（CI 权威）。

---

## ⚡ 快速开始（7 种调用方式）

### 方式 1: TRAE Skill（推荐 — 您已经在使用）

DevSquad 已注册为 TRAE Skill。在 TRAE IDE 对话中直接描述任务，7 角色团队将自动协作。无需 CLI 或 API 配置。

### 方式 2: CLI（推荐终端用户）

```bash
# 交互式设置向导（1-2 分钟）
python scripts/cli.py init

# 然后开始协作！
devsquad dispatch -t "你的任务描述"
```

### 方式 3: MCP Server（用于 IDE / 工具集成）

```bash
# 启动 MCP 服务器（stdio 传输，用于 IDE 集成）
python3 scripts/mcp_server.py

# 或 SSE 传输（用于远程访问）
python3 scripts/mcp_server.py --port 8080
```

### 方式 4: Web Dashboard（推荐团队）

```bash
# 启动带认证的 Streamlit dashboard
streamlit run scripts/dashboard.py

# 打开 http://localhost:8501
# 使用默认 dev 凭证登录（详见 INSTALL.md "Default credentials" 章节）
# 生产环境请修改所有默认配置
```

### 方式 5: REST API（推荐集成场景）

```bash
# 安装依赖
pip install fastapi uvicorn

# 启动 API 服务器
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# 访问 Swagger UI: http://localhost:8000/docs
# 访问 ReDoc:      http://localhost:8000/redoc
```

### 方式 6: Python API（推荐开发者）

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
result = dispatcher.dispatch(
    task="优化数据库查询性能",
    roles=["architect", "security", "tester"],
)
print(result.report)
print(result.consensus)
```

### 方式 7: 一键启动脚本（V3.9.2+）

```bash
# 一键启动 — 4 阶段：环境检查 → 数据库初始化 → 前端构建 → 服务启动
./scripts/start.sh

# 启动 Streamlit dashboard 替代 API 服务器
./scripts/start.sh --dashboard

# 覆盖 API 端口
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# 显示帮助
./scripts/start.sh --help
```

`start.sh` 是 V3.9.2（P0-2）引入的统一入口脚本，一条命令完成环境校验、数据库初始化、前端构建和服务启动。配合 `requirements.lock` 可实现可复现构建（`pip install -r requirements.lock`）。V4.1.0 新增 Loop Engineering、UI/UX 巡检、Adversarial 验证、DAG 可视化、Autonomous 和插件热加载。

---

## 👥 7 个核心角色

| 角色 | CLI ID | 别名 | 权重 | 最适用于 |
|------|--------|------|------|----------|
| 🏗️ **Architect** | `arch` | `architect` | 1.5 | 系统设计、技术栈、性能/安全架构 |
| 📋 **Product Manager** | `pm` | `product-manager` | 1.2 | 需求、用户故事、验收标准 |
| 🛡️ **Security Expert** | `sec` | `security` | 1.1 | 威胁建模、漏洞审计、合规 |
| 🧪 **Tester** | `test` | `tester`, `qa` | 1.0 | 测试策略、质量保证、边界用例 |
| 💻 **Coder** | `coder` | `solo-coder`, `dev` | 1.0 | 实现、代码审查、性能优化 |
| 🔧 **DevOps** | `infra` | `devops` | 1.0 | CI/CD、容器化、监控、基础设施 |
| 🎨 **UI Designer** | `ui` | `ui-designer` | 0.9 | UX 流程、交互设计、可访问性 |

**自动匹配**: 若未指定角色，dispatcher 会根据任务关键词自动匹配。

---

## 🏗️ 五大能力域（架构概览）

DevSquad 的 235 个模块组织为 **5 大能力域**，各域解决特定问题：

### 🎯 能力域 1: 任务编排引擎（核心）

> **让 7 个角色高效协作的「指挥中心」**

| 模块 | 用途 | 何时使用 |
|------|------|----------|
| **MultiAgentDispatcher** | 统一 dispatch 入口 | 所有任务自动调用 |
| **Coordinator** | 任务分解 + 角色分配 | 需要拆解的复杂任务 |
| **Scratchpad** | 实时信息交换的共享黑板 | 角色间协作 |
| **ConsensusEngine** | 加权投票 + 否决 + 升级机制 | 安全/架构争议 |
| **BatchScheduler** | 并行/串行混合调度 | 资源受限环境 |

**核心工作流:**
```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [ThreadPoolExecutor Parallel Workers] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

### 🛡️ 能力域 2: 质量保障体系

> **防止 AI 「偷懒」或「幻觉」**

| 模块 | 用途 | 何时使用 |
|------|------|----------|
| **InputValidator** | 安全校验 + 40 种模式检测（14 禁止 + 21 提示词注入 + 5 可疑） | 生产环境 |
| **VerificationGate** | 强制证据要求 + 7 Red Flags 检测 | 关键决策场景 |
| **AntiRationalizationEngine** | 按角色的借口→反驳表，防止质量偷工减料 | 高质量要求场景 |
| **TestQualityGuard** | 测试质量审计（API 校验 / 反模式检测 / 维度覆盖） | 发布前验证 |
| **PermissionGuard** | 4 级安全门（PLAN/DEFAULT/AUTO/BYPASS） | 安全敏感任务 |

### ⚡ 能力域 3: 性能与可靠性

> **让系统更快、更稳定、更省钱**

| 模块 | 用途 | 何时使用 |
|------|------|----------|
| **LLMCache** | 基于 TTL 的 LRU 缓存，支持磁盘持久化（降低 60-80% 成本） | 高频使用场景 |
| **LLMRetry** | 指数退避 + 熔断器 + 多后端 fallback | 网络不稳定场景 |
| **FeedbackControlLoop** | 闭环反馈控制，自动迭代直至达到质量阈值 | 追求高质量输出 |
| **ExecutionGuard** | 实时中止守护（超时/输出/关键词），保障安全执行 | 长时间运行任务 |
| **FallbackBackend** | 带 health 监控的自动后端 failover | 高可用要求场景 |

### 📊 能力域 4: 可观测性与治理

> **知道系统在做什么、做得怎么样**

| 模块 | 用途 | 何时使用 |
|------|------|----------|
| **PerformanceMonitor** | P95/P99 响应时间、CPU/内存跟踪、瓶颈检测 | 性能调优 |
| **UsageTracker** | Token/成本使用量跟踪与报告 | 成本控制 |
| **AuditLogger** | SHA256 完整性操作日志，支持 CSV/JSON 导出（Preview） | 合规审计 |
| **RBAC Engine** | 15+ 细粒度权限，5 角色（SUPER_ADMIN/ADMIN/OPERATOR/ANALYST/VIEWER）（Preview） | 企业级访问控制 |
| **Multi-Tenancy Manager** | 3 级隔离（strict/moderate/shared），租户级资源隔离（Preview） | 多租户 SaaS |
| **Sensitive Data Masker** | PII 检测与脱敏（邮箱/手机/身份证/信用卡），可配置规则（Preview） | 数据合规 |
| **HistoryManager** | SQLite 时序存储：指标快照、告警历史、API 日志 | 复盘分析 |

### 🔌 能力域 5: 集成与扩展

> **融入你的现有工具链**

| 模块 | 用途 | 何时使用 |
|------|------|----------|
| **CLI** | 带 lifecycle 命令的命令行界面 | 开发者日常使用 |
| **REST API (FastAPI)** | 10+ 端点，含 OpenAPI/Swagger 文档 | 微服务集成 |
| **Dashboard (Streamlit)** | 带认证的交互式 Web dashboard | 运营团队可视化 |
| **MCP Protocol** | 集成 TRAE/Claude Code/Cursor | AI Agent 生态 |
| **Docker Support** | 多阶段构建用于生产部署 | 容器化环境 |
| **GitHub Actions CI** | Python 3.10-3.11 矩阵测试 | CI/CD 流水线 |

---

## 🔬 控制论增强模块（V3.6.1）

> **非侵入式包装设计 — 可选开关，零修改现有核心逻辑**

5 个控制论模块可独立或组合工作，无需修改现有核心逻辑：

```
User Task
    ↓
[SimilarTaskRecommender] ← 可选：从历史推荐角色
    ↓
[AdaptiveRoleSelector]   ← 可选：优化角色选择
    ↓
[MultiAgentDispatcher]
    ↓
[FeedbackControlLoop]     ← 包装 dispatcher 实现自动迭代
    ↓ [每个 worker 步骤]
[ExecutionGuard]          ← 守护每个 worker 执行
    ↓
[PerformanceFingerprint]  ← dispatch 完成后记录
```

### 1️⃣ FeedbackControlLoop（反馈闭环控制器）
- 闭环反馈控制，自动迭代直至达到质量阈值
- 可配置质量门（`quality_gate`）和最大迭代次数
- 轻量级质量评估（无 LLM 调用），支持 dry-run 模式

### 2️⃣ ExecutionGuard（执行守护者）
- 实时执行监控，4 种中止条件：超时、输出大小、Token 数、关键关键词
- 轻量级检查（<1ms），零外部依赖
- 阈值可动态配置

### 3️⃣ PerformanceFingerprint（性能指纹系统）
- 统一执行指纹记录（融合 4 种数据源）
- 纯 Python TF-IDF 实现（不依赖 sklearn/numpy），支持中英文混合内容
- JSON 持久化到 `.devsquad_data/fingerprints/`，支持冷启动优雅降级

### 4️⃣ SimilarTaskRecommender（相似任务推荐器）
- 基于 TF-IDF 的任务相似度搜索，提供历史成功配置推荐
- 智能角色组合推荐、意图预测、执行时间估算
- 置信度评分（high/medium/low），支持冷启动优雅降级

### 5️⃣ AdaptiveRoleSelector（自适应角色选择器）
- 基于历史成功率的三层选择策略
- 可配置最小成功率和最大角色数
- 支持手动统计更新和完整的角色效能报告

**推荐用法**（渐进式采用）：
```python
from scripts.collaboration import (
    MultiAgentDispatcher, FeedbackControlLoop,
    ExecutionGuard, PerformanceFingerprint
)

dispatcher = MultiAgentDispatcher()
guard = ExecutionGuard()
fingerprint = PerformanceFingerprint()

# 方式 1: 完整控制论栈
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("Your task here")

# 方式 2: 仅守护（最小采用）
result = dispatcher.dispatch("Your task")
for w in result.worker_results:
    abort, reason = guard.check_abort(w.output, w.duration)
    if abort:
        print(f"Aborted: {reason}")

# 方式 3: 仅学习
fingerprint.record_execution("task", result, result.timing, result.matched_roles)
similar = fingerprint.find_similar("new task", top_k=3)
```

所有模块均为**可选开关** — 不启用也能完美运行 DevSquad。

---

## 🏗️ 架构概览（分层设计）

```
┌─────────────────────────────────────────────────────────────┐
│                    用户访问层                               │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Streamlit    │ │ FastAPI REST │ │ CLI/Notebook │        │
│  │ Dashboard    │ │ API Server   │ │ (现有)       │        │
│  │ (Auth+HTTPS) │ │ (Swagger)    │ │              │        │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘        │
└─────────┼───────────────┼───────────────────────────────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   业务逻辑层                                │
│  ┌─────────────┐ ┌─────────────┐           │
│  │AuthManager  │ │HistoryMgr   │           │
│  │(RBAC Auth)  │ │(SQLite TSDB)│           │
│  └─────────────┘ └─────────────┘           │
│  ┌─────────────────────────────────────────────┐            │
│  │     LifecycleProtocol (11-Phase Engine)       │            │
│  │     UnifiedGateEngine + CheckpointManager     │            │
│  └─────────────────────────────────────────────┘            │
└─────────────────────────┬───────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                    数据持久层                                │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────────┐  │
│  │ SQLite DB  │ │ YAML Config│ │ Checkpoint Files       │  │
│  │ (History)  │ │ (Deploy)   │ │ (Lifecycle State)      │  │
│  └────────────┘ └────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 分层子 Skill 架构（V3.6.0）

> DevSquad 提供 **8 个原子化子 Skill**，可独立使用或组合调用。
> 每个子 Skill 是一个轻量级包装器（约 50 行），导入现有核心模块 — 无重复逻辑。

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7 角色编排)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6 意图 × 3 语言)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5 轴代码审查)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + 测试策略生成
├── retrospective/  → RetroSkill    — RetrospectiveEngine + 模式提取
├── prototype/      → PrototypeSkill — 快速原型脚手架 (V4.5.0)
└── teach/          → TeachSkill     — 知识转移与新人上手 (V4.5.0)
```

### 子 Skill 快速参考

| Skill | 核心方法 | 包装 | Mock 模式 |
|-------|---------|------|:---------:|
| `dispatch` | `run(task, roles, mode)` | MultiAgentDispatcher | ✅ |
| `intent` | `detect(text, lang)` | IntentWorkflowMapper | ✅ |
| `review` | `review(code)` | FiveAxisConsensusEngine | ✅ |
| `security` | `scan_input(text)` | InputValidator + OpClassifier | ✅ |
| `test` | `generate_strategy(module)` | TestQualityGuard | ✅ |
| `retrospective` | `run_retrospective(results)` | RetrospectiveEngine | ✅ |

### 使用示例

```python
# 直接导入（推荐用于单个 skill）
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("修复登录 bug", roles=["coder", "tester"])

# 通过注册表（动态发现）
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']
skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
```

所有子 Skill 在 **无需任何 API Key** 的 Mock 模式下工作。

---

## 📋 Plan C 架构（核心引擎）

**统一 Lifecycle 架构** - 解决 CLI 6 命令 vs 11 阶段 lifecycle 的映射：

```
CLI 视图层 (6 命令)             核心引擎 (11 阶段)
┌─────────────────────┐            ┌──────────────────────────┐
│ spec → P1, P2       │───视图 ──→│ P1: Requirements         │
│ plan → P7           │   映射    │ P2: Architecture         │
│ build → P8          │            │ P3: Technical Design     │
│ test → P9           │            │ ...                      │
│ review → P8,P6      │            │ P10: Deployment          │
│ ship → P10          │            │ P11: Operations          │
└─────────────────────┘            └──────────────────────────┘
        ↓                                    ↓
  UnifiedGateEngine                   CheckpointManager
  (Phase + Worker 门)                 (Lifecycle 状态持久化)
```

**核心组件:**
- ✅ **LifecycleProtocol** - 统一 lifecycle 管理的抽象接口
- ✅ **UnifiedGateEngine** - 集成 VerificationGate + Phase 转换门
- ✅ **FullLifecycleAdapter** - 完整 11 阶段 lifecycle，含依赖解析
- ✅ **Enhanced CheckpointManager** - 跨会话自动保存/恢复 lifecycle 状态

---

## 📦 安装

### 前置条件
- **Python 3.10+**（支持 3.10、3.11，CI 已测试）
- **pip** 或 **pipenv** 包管理

### 选项 A: PyPI 安装（推荐）
```bash
# 从 PyPI 安装 — 零配置，开箱即用
pip install devsquad

# 含可选依赖
pip install "devsquad[api]"    # FastAPI + Streamlit dashboard
pip install "devsquad[all]"    # 所有可选功能
```

### 选项 B: Git Clone + 本地安装
```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# 安装核心包（最小依赖）
pip install -e .

# 即可使用！
devsquad dispatch -t "设计用户认证系统"
```

### 验证安装
```bash
# 检查版本
devsquad --version
# 预期: devsquad 4.3.0

# 运行测试
pytest tests/ -v --tb=short
# 预期: 7681 passed
```

---

## ⚙️ 配置

在项目根目录创建 `.devsquad.yaml`：

```yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85

llm:
  backend: auto
  base_url: ""  # 通过 DEVSQUAD_OPENAI_BASE_URL 环境变量设置
  model: ""     # 通过 DEVSQUAD_OPENAI_MODEL 环境变量设置
  timeout: 120
```

或使用环境变量（优先级更高）：

```bash
# 默认: auto 优先尝试真实后端，失败后回退到 mock
export DEVSQUAD_LLM_BACKEND=auto
export DEVSQUAD_OPENAI_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_OPENAI_MODEL=gpt-4
export DEVSQUAD_OPENAI_API_KEY=sk-...
```

**环境变量参考：**

| 变量 | 用途 | 默认值 |
|------|------|--------|
| `DEVSQUAD_LLM_BACKEND` | 默认后端类型（auto\|mock\|trae\|openai\|anthropic\|fallback） | `auto` |
| `DEVSQUAD_OPENAI_API_KEY` | OpenAI/MOKA AI API key | None |
| `DEVSQUAD_OPENAI_BASE_URL` | OpenAI 兼容 base URL | None |
| `DEVSQUAD_OPENAI_MODEL` | OpenAI 模型名 | `gpt-4` |
| `DEVSQUAD_ANTHROPIC_API_KEY` | Anthropic API key | None |
| `DEVSQUAD_ANTHROPIC_BASE_URL` | Anthropic 兼容 base URL | None |
| `DEVSQUAD_ANTHROPIC_MODEL` | Anthropic 模型名 | `claude-sonnet-4-20250514` |
| `DEVSQUAD_LOG_LEVEL` | 日志级别 | `WARNING` |

---

## 🧪 测试

### 快速冒烟测试（< 30 秒）
```bash
python3 scripts/cli.py --version       # 预期: DevSquad 4.1.0
python3 scripts/cli.py status          # 预期: System ready
python3 scripts/cli.py roles           # 预期: 列出 7 个核心角色
```

### 完整测试套件
```bash
# 运行所有测试（7681 tests passing）
python3 -m pytest tests/ -q --tb=line

# 含覆盖率报告
python3 -m pytest tests/ --cov=scripts --cov-report=term-missing
```

### 测试分层策略

| 优先级 | 范围 | 示例 | 数量 |
|--------|------|------|------|
| **P0** | 质量框架核心 | AntiRationalization, VerificationGate, IntentWorkflowMapper, AuthManager | ~200 |
| **P1** | 增强模块 | FiveAxisConsensus, OperationClassifier, OutputSlicer | ~150 |
| **P1+** | 控制论（V3.6.6） | FeedbackControlLoop, ExecutionGuard, PerformanceFingerprint 等 | **110** |
| **P2** | 集成 & E2E | 完整 lifecycle dispatch、跨模块集成 | ~200 |
| **P3** | 模块单元 | 核心 dispatcher、RoleMapping、MCEAdapter、LLM backends | ~400+ |

**总计: 7681 CI 测试 / 266 e2e（收集 7681）**

按优先级运行：
```bash
# 仅 P0（关键路径, < 10s）
python3 -m pytest tests/ -k "anti_ratif or verification or intent_workflow or auth" -q

# P0 + P1（质量 + 增强, < 30s）
python3 -m pytest tests/ -k "anti_ratif or verification or intent or auth or five_axis or operation" -q

# 完整套件
python3 -m pytest tests/ -q --tb=line
```

---

## 📚 文档

| 文档 | 描述 | 语言 |
|------|------|------|
| [**QUICKSTART.md**](QUICKSTART.md) | **⭐ 30 秒快速入门指南（推荐新用户）** | 中文 |
| [SKILL.md](SKILL.md) | 完整技能手册 + 187+ 模块参考 | EN/CN/JP |
| [GUIDE.md](GUIDE.md) | 完全用户指南 | 中文 |
| [INSTALL.md](INSTALL.md) | 安装指南 (Unix + Windows) | EN/CN |
| [EXAMPLES.md](EXAMPLES.md) | 实际使用示例 | EN |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史记录 | EN |
| [README-CN.md](README-CN.md) | 中文说明 | 中文 |
| [README-JP.md](README-JP.md) | 日本語説明 | 日本語 |
| [docs/PRD.md](docs/PRD.md) | 产品需求文档 | 中文 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 技术架构文档 | 中文 |
| [docs/planning/V43_ROADMAP_PROPOSAL.md](docs/planning/V43_ROADMAP_PROPOSAL.md) | V4.3 统一推进方案 v1.2（7-Role 共识达成） | 中文 |
| [docs/prd/V4.3.0_PRD.md](docs/prd/V4.3.0_PRD.md) | V4.3.0 PRD（需求/用户故事/验收标准） | 中文 |
| [docs/architecture/V4.3.0_ARCHITECTURE.md](docs/architecture/V4.3.0_ARCHITECTURE.md) | V4.3.0 架构设计（模块边界/接口契约/依赖图） | 中文 |
| [docs/testing/V4.3.0_TEST_PLAN.md](docs/testing/V4.3.0_TEST_PLAN.md) | V4.3.0 测试方案（测试金字塔/E2E/真实用户模拟） | 中文 |

---

## 🗺️ Roadmap

### V4.3.0（进行中 — 7-Role 共识达成，文档先行）

**版本策略**: V4.3.0 预发布（全部代码+文档+E2E 验证）→ 用户确认 → V4.3.0 正式版

**整合三方面输入**:
1. 技术债持续治理（`todo_drift_monitor` + CI 阻塞）
2. pickle→JSON 迁移（dead code 删除 + fallback 安全收紧 + 移除）
3. 上游 TraeMultiAgentSkill v2.6-v2.8 精细化启发（Ponytail 双模式 / LoopKernel 回退 / UIUX 审计 / Dashboard 可视化）

**V4.3.0 范围（9 项）**:

| ID | 名称 | 优先级 |
|----|------|--------|
| P0-1 | pickle dead code 删除 + fallback 安全收紧 | P0 |
| P0-2 | `todo_drift_monitor.py` + CI 阻塞 + PR template | P0 |
| P1-1 | Ponytail lite/full 双模式 + DebtCollector + RequirementTracer | P1 |
| P1-4 | LoopKernel RollbackStrategy + 独立硬上限 | P1 |
| P1-5 | UIUXAnalyzer 子项审计 + 按需补全 | P1 |
| P1-6 | Dashboard 状态可视化 | P1 |
| P2-1 | pickle fallback 移除 | P2 |
| P2-2 | Autonomous SmartConfirmation 文档补全 | P2 |
| P2-4 | V4.3.0 发布文档同步 | P2 |

**7-Role 共识**: 7/7 APPROVE_WITH_CONCERNS，按 10 项调整修订后达成共识。详见 [V43_ROADMAP_PROPOSAL.md](docs/planning/V43_ROADMAP_PROPOSAL.md) v1.2。

**项目生命周期**: 按 11-Phase 模型推进（P1 需求 → P2 架构 → P3 技术设计 → P7 测试计划 → P8 实施 → P9 测试执行 → P10 部署发布）

**测试金字塔保障**: unit ≥60% / integration 15-25% / e2e ≤10% / contract 5-10% / smoke ≤5%

---

## 🤝 贡献指南

1. Fork 本仓库
2. 创建特性分支（`git checkout -b feature/amazing-feature`）
3. 提交更改（`git commit -m 'Add amazing feature'`）
4. 推送到分支（`git push origin feature/amazing-feature`）
5. 提交 Pull Request

---

## 📄 许可证

本项目采用 MIT 许证 - 详见 [LICENSE](LICENSE) 文件。

---

<p align="center">
  <strong>⭐ 如果 DevSquad 对你有帮助，请给个 Star！⭐</strong>
  <br>
  <em>让更多开发者享受到「AI 团队协作」的力量</em>
  <br>
  <br>
  <strong>🙏 致谢</strong>
  <br>
  灵感来源于 <a href="https://github.com/weiransoft/TraeMultiAgentSkill">TraeMultiAgentSkill</a> 上游项目
  <br>
  Built with ❤️ by the DevSquad team
</p>

---

*最后更新：2026-08-05 | 版本：V4.5.2 (Approval Gate + Connector Framework + 反幽灵 E2E — 2 个新模块、3 个 ROADMAP 项完成) | V4.5.0 (跨会话连续性 + 协议原生 Skill 架构 + 行动优先报告 — 10 项新特性) | V4.4.0 (5 个新增增强模块：RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector — 详见 [CHANGELOG.md](CHANGELOG.md))*

</details>
