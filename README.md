# DevSquad — Multi-Role AI Task Orchestrator

<p align="center">
  <strong>🎯 把「单个 AI 助手」升级成「7 人 AI 专业团队」</strong>
  <br>
  <em>One task → Multi-role AI collaboration → One conclusion | V4.5.10 (HostLLMBridge v2 production wiring + --async CLI: v2 protocol hardening + factory v2 default + v1/v2 isolation) | V4.5.9 (Unified Gather Execution Core + Native Async Worker: 执行层统一 gather 化 + Worker 原生异步) | V4.5.8 (FileRiskStore persistence + risks add/assess/mitigate/close + exposure filters) | V4.5.7 (Coeffect Async + Risk Register UX CLI) | V4.5.6 (Module Fiber + Coeffect: 6-state FSM + topological activation + modules CLI) | V4.5.3 (Artifacts + Effect — ArtifactStore + DispatchEffect + EffectRegistry + Audit CLI) | V4.5.2 (Experience polish: MOKA + Metrics + GitLab + Doctor + BackendConfig) | V4.5.0 (cross-session continuity + protocol-native skills)</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-8996%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V4.5.12-success" />
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

📚 **想深入了解？** → [完整快速入门指南](QUICKSTART.md) | [193 模块详细参考](SKILL.md)

---

<details>
<summary>🔍 点击展开：完整功能介绍与架构详解</summary>

## 🚀 V4.5.2: Approval Gate + Connector Framework + Anti-Ghost E2E

**DevSquad V4.5.2** (PATCH release, SemVer compliant) introduces 2 new modules and completes 3 ROADMAP items (V451-1, V451-2, V451-7/8/9). All new modules default to safe, backward-compatible behavior — no API breaking changes. See [docs/release_notes/V4.5.2_RELEASE_NOTES.md](docs/release_notes/V4.5.2_RELEASE_NOTES.md) for full release notes.

### V4.5.2 — 2 New Modules + 3 ROADMAP Items
- **ApprovalGate**: User-level approval mechanism for external operations. Fail-closed on callback exceptions. Auto-approve fallback when no callback configured (backward compatible).
- **ConnectorFramework**: Protocol-based interface for external system integration (GitHub first). `Connector` Protocol + `GitHubConnector` (api/cli/simulation modes). `simulation=True` enforced by default in dispatch pipeline.
- **V451-7 Dashboard browser-level E2E**: 11 AppTest cases (Streamlit AppTest replaces Playwright — avoids heavy browser deps while still being browser-level DOM simulation)
- **V451-8 REST API end-to-end user journey E2E**: 190 E2E tests covering dispatch→history→roles→quick dispatch→error handling→lifecycle→cross-entry
- **V451-9 Connector Framework anti-ghost E2E**: 12 E2E tests (AG-1 through AG-8) proving pipeline activation

### V4.5.0 — Cross-Session Continuity + Protocol-Native Skills + Action-First Reports

**DevSquad V4.5.0** (merging V4.4.3 + V4.4.4 + V4.5.0 changes) delivers 10 new features for cross-session continuity, protocol-native skill architecture, and action-first reporting. The 7-role AI team orchestrates complex engineering tasks with full audit trails and consensus mechanisms. See [docs/VISION.md](docs/VISION.md) for the project vision.

### V4.5.0 — 10 New Features
- **ScratchpadHistoryStore**: SQLite-backed cross-session Scratchpad search
- **AgentIdentity**: Deterministic agent ID for cross-session tracking
- **WorkflowTrace**: Transparent workflow trace in dispatch reports
- **GitContext**: Git branch/commit context injection into dispatch
- **SkillProvider Protocol**: Protocol-native skill architecture (Builtin + MCP providers)
- **OutputStyle**: Action-first report format (from i-have-adhd insights)
- **SessionResume CLI**: `devsquad sessions list` + `dispatch --resume`
- **FileBundler**: Deterministic file bundling for review mode (from open-code-review)
- **SKILL.md Modular Split**: 1216→282 lines + 3 reference docs (MODULE_REFERENCE / SUB_SKILLS / VERSION_HISTORY)
- **VISION Documents**: docs/VISION.md + VISION_ORCHESTRATION.md + VISION_AGENT_COLLABORATION.md

### V4.4.0 — P0-P3 Enhancement Modules (5 new modules)
- **P0-1 RiskRegister**: PMP risk management with 7-role weighted assessment (probability × impact) + 4 response strategies (avoid/transfer/mitigate/accept) + `GateType.RISK_CHECK` gate (exposure ≥ 0.36 blocks)
- **P0-2 ViewpointRegistry**: TOGAF architecture viewpoints with 7-role bound formal viewpoints + `is_orthogonal()` orthogonality check + `check_consistency()` conflict detection
- **P1-1 ErrorBudgetTracker**: SRE error budget with SLO 99.9% default + `GateType.ERROR_BUDGET` P10 gate (budget exhaustion blocks deployment) + `burn_rate()` consumption rate
- **P1-2 GapAnalyzer**: TOGAF gap analysis with `analyze(current, target)` + `prioritize()` + `generate_roadmap()` + `suggest_scheduler_decision()` driving LoopScheduler
- **P2-1 DoraMetricsCollector**: DORA metrics (Deployment Frequency / Lead Time / Change Failure Rate / MTTR) + `GateType.DORA_CHECK` P11 gate (CFR > 15% triggers architecture review) + Elite/High/Medium/Low rating

### V4.4.1 — External Docs Restructure
- Archived orphan i18n docs (docs/i18n/ → docs/_archive/i18n/)
- Retired CHANGELOG-CN.md (CHANGELOG.md is now SSOT for all languages)
- Consolidated admin credentials to INSTALL.md only (single source of truth)
- Renumbered INSTALL.md methods to continuous 1-7
- Synced version numbers across all external docs (README/SKILL/INSTALL/CLAUDE)

### V4.4.2 — Multilingual + Dashboard Enhancement
- Multilingual role prompts (EN/CN/JP) for all 7 roles
- Dashboard 6-tab visibility (Overview/Dispatch/Lifecycle/Metrics/Audit/Settings)
- P2 Kanban evaluation (work-in-progress limits + cycle time tracking)
- P3 ITSM evaluation (incident management + change advisory board simulation)
- 13 E2E tests xpass + anti-ghost counters

### Anti-Ghost Feature Guarantee
Every new module includes `_call_counter` mechanism + E2E anti_ghost test + CI `check_module_activation.py` verification. Modules must be truly integrated into dispatch pipeline (not just instantiated), with Markdown report sections user-visible. V4.5.2 extends this pattern from V4.4.0 (RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector) to V4.5.2 (ApprovalGate / ConnectorFramework).

### Test Pyramid Achieved
- **Contract tests**: 5.2% (target ≥5% ✅)
- **Integration tests**: 15.1% (target ≥15% ✅)
- **Total tests**: 8392+ (CI authoritative)
- **E2E coverage**: 107 e2e + 1244 integration + 13 V4.4.0 anti-ghost + 12 V4.5.2 anti-ghost

### Historical Features (V4.0.0-V4.3.3)
- **V4.3.3**: P0-P3 enhancement E2E skeletons (xfail TDD for V4.4.0)
- **V4.3.2**: LLM vs Mock quality gap measurement (calibration gate + thin-slice probe)
- **V4.3.0 Phase 3**: Quality hardening + user simulation E2E (NPS 9/10)
- **V4.3.0 Phase 2**: OutputValidator full integration (LLM output safety detection)
- **V4.3.0 Phase 1**: DependencyHallucinationChecker (anti-slopsquatting supply chain attack)
- **V4.3.0 Phase 0**: DeploymentComplianceChecker (anti-violation deployment backstop)
- **V4.0.0 P1-1 Loop Engineering**: Discovery → Handoff → Verification → Persistence → Scheduling
- **V4.0.0 P1-2 UI/UX Patrol**: 4-dimension audit + PIL pixel diff visual regression
- **V4.0.0 P2-1 Adversarial Verification**: red team attack + blue team defense + judge arbitration
- **V4.0.0 P2-2 DAG Visualization**: Mermaid / JSON / DOT three formats
- **V4.0.0 P3-1 Autonomous**: plan → dev → verify → fix 4-stage autonomous iteration
- **V4.0.0 P3-2 Plugin Hot-Loading**: 3 loading paths + path traversal 3-layer protection + reload rollback

8996+ tests passing (CI authoritative).

---

## ⚡ Quick Start (7 Ways to Invoke DevSquad)

### Method 1: TRAE Skill (Recommended — you're already here)

DevSquad is registered as a TRAE Skill. Simply describe your task in the TRAE IDE chat, and the 7-role team will collaborate automatically. No CLI or API setup needed.

### Method 2: CLI (Recommended for Terminal Users)

```bash
# Interactive setup wizard (1-2 minutes)
python scripts/cli.py init

# Then start collaborating!
devsquad dispatch -t "your task description"
```

### Method 3: MCP Server (For IDE / Tool Integration)

```bash
# Start MCP server with stdio transport (for IDE integration)
python3 scripts/mcp_server.py

# Or SSE transport (for remote access)
python3 scripts/mcp_server.py --port 8080
```

### Method 4: Web Dashboard (Recommended for Teams)

```bash
# Start Streamlit dashboard with authentication
streamlit run scripts/dashboard.py

# Open http://localhost:8501
# Login with default dev credentials (see INSTALL.md "Default credentials" section).
# Change all defaults in production.
```

### Method 5: REST API (Recommended for Integration)

```bash
# Install dependencies
pip install fastapi uvicorn

# Start API server
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Access Swagger UI: http://localhost:8000/docs
# Access ReDoc:      http://localhost:8000/redoc
```

### Method 6: Python API (Recommended for Developers)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

dispatcher = MultiAgentDispatcher()
result = dispatcher.dispatch(
    task="Optimize database query performance",
    roles=["architect", "security", "tester"],
)
print(result.report)
print(result.consensus)
```

### Method 7: One-Click Startup Script (V3.9.2+)

```bash
# One-click startup — 4 phases: env check → DB init → frontend build → service start
./scripts/start.sh

# Launch Streamlit dashboard instead of API server
./scripts/start.sh --dashboard

# Override API port
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# Show help
./scripts/start.sh --help
```

`start.sh` is the unified entry point introduced in V3.9.2 (P0-2). It validates the environment, initializes the database, builds the frontend, and starts the service in one command. Use `requirements.lock` alongside it for reproducible builds (`pip install -r requirements.lock`). V4.1.0 adds Loop Engineering, UI/UX 巡检, Adversarial 验证, DAG 可视化, Autonomous, and 插件热加载.

---

## 👥 7 Core Roles

| Role | CLI ID | Aliases | Weight | Best For |
|------|--------|---------|--------|----------|
| 🏗️ **Architect** | `arch` | `architect` | 1.5 | System design, tech stack, performance/security architecture |
| 📋 **Product Manager** | `pm` | `product-manager` | 1.2 | Requirements, user stories, acceptance criteria |
| 🛡️ **Security Expert** | `sec` | `security` | 1.1 | Threat modeling, vulnerability audit, compliance |
| 🧪 **Tester** | `test` | `tester`, `qa` | 1.0 | Test strategy, quality assurance, edge cases |
| 💻 **Coder** | `coder` | `solo-coder`, `dev` | 1.0 | Implementation, code review, performance optimization |
| 🔧 **DevOps** | `infra` | `devops` | 1.0 | CI/CD, containerization, monitoring, infrastructure |
| 🎨 **UI Designer** | `ui` | `ui-designer` | 0.9 | UX flow, interaction design, accessibility |

**Auto-match**: If no roles specified, the dispatcher automatically matches based on task keywords.

---

## 🏗️ Five Capability Domains (Architecture Overview)

DevSquad's 235 modules are organized into **5 capability domains**, each solving a specific problem:

### 🎯 Domain 1: Task Orchestration Engine (Core)

> **让 7 个角色高效协作的「指挥中心」**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **MultiAgentDispatcher** | Unified dispatch entry point | All tasks automatically |
| **Coordinator** | Task decomposition + role assignment | Complex tasks needing breakdown |
| **Scratchpad** | Shared blackboard for real-time info exchange | Inter-role collaboration |
| **ConsensusEngine** | Weighted voting + veto + escalation mechanism | Security/architecture disputes |
| **BatchScheduler** | Parallel/sequential hybrid scheduling | Resource-constrained environments |

**Core Workflow:**
```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [ThreadPoolExecutor Parallel Workers] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

### 🛡️ Domain 2: Quality Assurance System

> **防止 AI 「偷懒」或「幻觉」**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **InputValidator** | Security validation + 40-pattern detection (14 forbidden + 21 prompt injection + 5 suspicious) | Production environments |
| **VerificationGate** | Mandatory evidence requirements + 7 Red Flags detection | Critical decision scenarios |
| **AntiRationalizationEngine** | Per-role excuse→rebuttal tables to prevent quality shortcuts | High quality requirements |
| **TestQualityGuard** | Test quality audit (API validation / anti-pattern detection / dimension coverage) | Pre-release verification |
| **PermissionGuard** | 4-level safety gate (PLAN/DEFAULT/AUTO/BYPASS) | Security-sensitive tasks |

### ⚡ Domain 3: Performance & Reliability

> **让系统更快、更稳定、更省钱**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **LLMCache** | TTL-based LRU cache with disk persistence (60-80% cost reduction) | High-frequency usage |
| **LLMRetry** | Exponential backoff + circuit breaker + multi-backend fallback | Unstable networks |
| **FeedbackControlLoop** | Closed-loop feedback control with automatic iteration until quality threshold met | High quality output pursuit |
| **ExecutionGuard** | Real-time abort guard (timeout/output/keywords) for safe execution | Long-running tasks |
| **FallbackBackend** | Automatic backend failover with health monitoring | High availability requirements |

### 📊 Domain 4: Observability & Governance

> **知道系统在做什么、做得怎么样**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **PerformanceMonitor** | P95/P99 response time, CPU/memory tracking, bottleneck detection | Performance tuning |
| **UsageTracker** | Token/cost usage tracking and reporting | Cost control |
| **AuditLogger** | SHA256 integrity operation logs with CSV/JSON export (Preview) | Compliance auditing |
| **RBAC Engine** | 15+ fine-grained permissions, 5 roles (SUPER_ADMIN/ADMIN/OPERATOR/ANALYST/VIEWER) (Preview) | Enterprise access control |
| **Multi-Tenancy Manager** | 3 isolation levels (strict/moderate/shared), tenant-scoped resources (Preview) | Multi-tenant SaaS |
| **Sensitive Data Masker** | PII detection and masking (email/phone/ID card/credit card), configurable rules (Preview) | Data compliance |
| **HistoryManager** | SQLite time-series storage: metrics snapshots, alert history, API logs | Retrospective analysis |

### 🔌 Domain 5: Integration & Extension

> **融入你的现有工具链**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **CLI** | Command-line interface with lifecycle commands | Daily developer usage |
| **REST API (FastAPI)** | 10+ endpoints with OpenAPI/Swagger docs | Microservice integration |
| **Dashboard (Streamlit)** | Interactive web dashboard with authentication | Operations team visualization |
| **MCP Protocol** | Integration with TRAE/Claude Code/Cursor | AI Agent ecosystem |
| **Docker Support** | Multi-stage build for production deployment | Containerized environments |
| **GitHub Actions CI** | Python 3.10-3.11 matrix testing | CI/CD pipelines |

---

## 🔬 Cybernetics Enhancement Modules (V3.6.1)

> **非侵入式包装设计 — 可选开关，零修改现有核心逻辑**

The 5 cybernetic modules work independently or together without modifying existing core logic:

```
User Task
    ↓
[SimilarTaskRecommender] ← Optional: suggest roles from history
    ↓
[AdaptiveRoleSelector]   ← Optional: optimize role selection
    ↓
[MultiAgentDispatcher]
    ↓
[FeedbackControlLoop]     ← Wrap dispatcher for auto-iteration
    ↓ [each worker step]
[ExecutionGuard]          ← Guard each worker execution
    ↓
[PerformanceFingerprint]  ← Record after dispatch completes
```

### 1️⃣ FeedbackControlLoop (反馈闭环控制器)
- Closed-loop feedback control with automatic iteration until quality threshold met
- Configurable quality gate (`quality_gate`) and maximum iterations
- Lightweight quality assessment (no LLM calls), supports dry-run mode

### 2️⃣ ExecutionGuard (执行守护者)
- Real-time execution monitoring with 4 abort conditions: timeout, output size, token count, critical keywords
- Lightweight checks (<1ms), zero external dependencies
- Dynamically configurable thresholds

### 3️⃣ PerformanceFingerprint (性能指纹系统)
- Unified execution fingerprint recording (fuses 4 data sources)
- Pure Python TF-IDF implementation (no sklearn/numpy), supports English/Chinese mixed content
- JSON persistence to `.devsquad_data/fingerprints/`, graceful cold-start degradation

### 4️⃣ SimilarTaskRecommender (相似任务推荐器)
- TF-IDF-based task similarity search with historical success configuration recommendations
- Intelligent role combination recommendation, intent prediction, execution time estimation
- Confidence scoring (high/medium/low), graceful cold-start degradation

### 5️⃣ AdaptiveRoleSelector (自适应角色选择器)
- Three-tier selection strategy based on historical success rates
- Configurable minimum success rate and maximum role count
- Supports manual statistics updates and comprehensive role effectiveness reporting

**Recommended usage** (progressive adoption):
```python
from scripts.collaboration import (
    MultiAgentDispatcher, FeedbackControlLoop,
    ExecutionGuard, PerformanceFingerprint
)

dispatcher = MultiAgentDispatcher()
guard = ExecutionGuard()
fingerprint = PerformanceFingerprint()

# Option 1: Full cybernetics stack
loop = FeedbackControlLoop(dispatcher, quality_gate=0.7)
result = loop.run("Your task here")

# Option 2: Guard only (minimal adoption)
result = dispatcher.dispatch("Your task")
for w in result.worker_results:
    abort, reason = guard.check_abort(w.output, w.duration)
    if abort:
        print(f"Aborted: {reason}")

# Option 3: Learning only
fingerprint.record_execution("task", result, result.timing, result.matched_roles)
similar = fingerprint.find_similar("new task", top_k=3)
```

All modules are **optional switches** — DevSquad works perfectly without them.

---

## 🏗️ Architecture Overview (Layered Design)

```
┌─────────────────────────────────────────────────────────────┐
│                    User Access Layer                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐        │
│  │ Streamlit    │ │ FastAPI REST │ │ CLI/Notebook │        │
│  │ Dashboard    │ │ API Server   │ │ (Existing)   │        │
│  │ (Auth+HTTPS) │ │ (Swagger)    │ │              │        │
│  └──────┬───────┘ └──────┬───────┘ └──────────────┘        │
└─────────┼───────────────┼───────────────────────────────────┘
          │               │
          ▼               ▼
┌─────────────────────────────────────────────────────────────┐
│                   Business Logic Layer                      │
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
│                    Data Persistence Layer                    │
│  ┌────────────┐ ┌────────────┐ ┌────────────────────────┐  │
│  │ SQLite DB  │ │ YAML Config│ │ Checkpoint Files       │  │
│  │ (History)  │ │ (Deploy)   │ │ (Lifecycle State)      │  │
│  └────────────┘ └────────────┘ └────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 🧩 Layered Sub-Skill Architecture (V3.6.0)

> DevSquad provides **8 atomic sub-skills** that can be used independently or together.
> Each sub-skill is a thin wrapper (~50 lines) importing existing core modules — no duplicated logic.

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7-role orchestration)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6 intents × 3 languages)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5-axis code review)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + test strategy generation
├── retrospective/  → RetroSkill    — RetrospectiveEngine + pattern extraction
├── prototype/      → PrototypeSkill — Rapid prototype scaffolding (V4.5.0)
└── teach/          → TeachSkill     — Knowledge transfer & onboarding (V4.5.0)
```

### Sub-Skill Quick Reference

| Skill | Core Method | Wraps | Mock Mode |
|-------|------------|-------|:---------:|
| `dispatch` | `run(task, roles, mode)` | MultiAgentDispatcher | ✅ |
| `intent` | `detect(text, lang)` | IntentWorkflowMapper | ✅ |
| `review` | `review(code)` | FiveAxisConsensusEngine | ✅ |
| `security` | `scan_input(text)` | InputValidator + OpClassifier | ✅ |
| `test` | `generate_strategy(module)` | TestQualityGuard | ✅ |
| `retrospective` | `run_retrospective(results)` | RetrospectiveEngine | ✅ |

### Usage Examples

```python
# Direct import (recommended for single skill)
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("Fix login bug", roles=["coder", "tester"])

# Via registry (dynamic discovery)
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']
skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
```

All sub-skills work **without any API key** in Mock mode.

---

## 📋 Plan C Architecture (Core Engine)

**Unified Lifecycle Architecture** - Resolves CLI 6 commands vs 11-phase lifecycle:

```
CLI View Layer (6 commands)          Core Engine (11 phases)
┌─────────────────────┐            ┌──────────────────────────┐
│ spec → P1, P2       │───View ──→│ P1: Requirements         │
│ plan → P7           │   Mapping │ P2: Architecture         │
│ build → P8          │            │ P3: Technical Design     │
│ test → P9           │            │ ...                      │
│ review → P8,P6      │            │ P10: Deployment          │
│ ship → P10          │            │ P11: Operations          │
└─────────────────────┘            └──────────────────────────┘
        ↓                                    ↓
  UnifiedGateEngine                   CheckpointManager
  (Phase + Worker gates)              (Lifecycle state persistence)
```

**Core Components:**
- ✅ **LifecycleProtocol** - Abstract interface for unified lifecycle management
- ✅ **UnifiedGateEngine** - Integrates VerificationGate + Phase transition gates
- ✅ **FullLifecycleAdapter** - Complete 11-phase lifecycle with dependency resolution
- ✅ **Enhanced CheckpointManager** - Auto save/restore lifecycle state across sessions

---

## 📦 Installation

### Prerequisites
- **Python 3.10+** (3.10, 3.11 supported, tested in CI)
- **pip** or **pipenv** for package management

### Option A: PyPI Install (Recommended)
```bash
# Install from PyPI — zero setup, ready to use
pip install devsquad

# With optional dependencies
pip install "devsquad[api]"    # FastAPI + Streamlit dashboard
pip install "devsquad[all]"    # All optional features
```

### Option B: Git Clone + Local Install
```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# Install core package (minimal dependencies)
pip install -e .

# Ready to use!
devsquad dispatch -t "Design user authentication system"
```

### Verify Installation
```bash
# Check version
devsquad --version
# Expected: devsquad 4.3.0

# Run tests
pytest tests/ -v --tb=short
# Expected: 7681 passed
```

---

## ⚙️ Configuration

Create `.devsquad.yaml` in your project root:

```yaml
quality_control:
  enabled: true
  strict_mode: true
  min_quality_score: 85

llm:
  backend: auto
  base_url: ""  # Set via DEVSQUAD_OPENAI_BASE_URL env var
  model: ""     # Set via DEVSQUAD_OPENAI_MODEL env var
  timeout: 120
```

Or use environment variables (higher priority):

```bash
# Default: auto tries real backends first, then falls back to mock
export DEVSQUAD_LLM_BACKEND=auto
export DEVSQUAD_OPENAI_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_OPENAI_MODEL=gpt-4
export DEVSQUAD_OPENAI_API_KEY=sk-...
```

**Environment Variables Reference:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `DEVSQUAD_LLM_BACKEND` | Default backend type (auto\|mock\|trae\|openai\|anthropic\|fallback) | `auto` |
| `DEVSQUAD_OPENAI_API_KEY` | OpenAI/MOKA AI API key | None |
| `DEVSQUAD_OPENAI_BASE_URL` | OpenAI-compatible base URL | None |
| `DEVSQUAD_OPENAI_MODEL` | OpenAI model name | `gpt-4` |
| `DEVSQUAD_ANTHROPIC_API_KEY` | Anthropic API key | None |
| `DEVSQUAD_ANTHROPIC_BASE_URL` | Anthropic-compatible base URL | None |
| `DEVSQUAD_ANTHROPIC_MODEL` | Anthropic model name | `claude-sonnet-4-20250514` |
| `DEVSQUAD_LOG_LEVEL` | Logging level | `WARNING` |

---

## 🧪 Testing

### Quick Smoke Test (< 30 seconds)
```bash
python3 scripts/cli.py --version       # Expected: DevSquad 4.1.0
python3 scripts/cli.py status          # Expected: System ready
python3 scripts/cli.py roles           # Expected: 7 core roles listed
```

### Full Test Suite
```bash
# Run all tests (7681 tests passing)
python3 -m pytest tests/ -q --tb=line

# With coverage report
python3 -m pytest tests/ --cov=scripts --cov-report=term-missing
```

### Test Layering Strategy

| Priority | Scope | Examples | Count |
|----------|-------|----------|-------|
| **P0** | Quality Framework Core | AntiRationalization, VerificationGate, IntentWorkflowMapper, AuthManager | ~200 |
| **P1** | Enhancement Modules | FiveAxisConsensus, OperationClassifier, OutputSlicer | ~150 |
| **P1+** | Cybernetics (V3.6.6) | FeedbackControlLoop, ExecutionGuard, PerformanceFingerprint, etc. | **110** |
| **P2** | Integration & E2E | Full lifecycle dispatch, cross-module integration | ~200 |
| **P3** | Unit per Module | Core dispatcher, RoleMapping, MCEAdapter, LLM backends | ~400+ |

**Total: 7681 CI tests / 266 e2e (7681 collected)**

Run by priority:
```bash
# P0 only (critical path, < 10s)
python3 -m pytest tests/ -k "anti_ratif or verification or intent_workflow or auth" -q

# P0 + P1 (quality + enhancement, < 30s)
python3 -m pytest tests/ -k "anti_ratif or verification or intent or auth or five_axis or operation" -q

# Full suite
python3 -m pytest tests/ -q --tb=line
```

---

## 📚 Documentation

| Document | Description | Language |
|----------|-------------|----------|
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

## 🤝 Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  <strong>⭐ 如果 DevSquad 对你有帮助，请给个 Star！⭐</strong>
  <br>
  <em>让更多开发者享受到「AI 团队协作」的力量</em>
  <br>
  <br>
  <strong>🙏 Acknowledgments</strong>
  <br>
  Inspired by <a href="https://github.com/weiransoft/TraeMultiAgentSkill">TraeMultiAgentSkill</a> upstream project
  <br>
  Built with ❤️ by the DevSquad team
</p>

---

*Last updated: 2026-08-05 | Version: V4.5.2 (Approval Gate + Connector Framework + anti-ghost E2E — 2 new modules, 3 ROADMAP items completed) | V4.5.0 (cross-session continuity + protocol-native skills + action-first reports — 10 new features) | V4.4.0 (5 enhancement modules: RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector — see [CHANGELOG.md](CHANGELOG.md))*

</details>
