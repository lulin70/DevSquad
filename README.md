# DevSquad — Multi-Role AI Task Orchestrator

<p align="center">
  <strong>🎯 把「单个 AI 助手」升级成「7 人 AI 专业团队」</strong>
  <br>
  <em>One task → Multi-role AI collaboration → One conclusion | V3.7.2 Enterprise Ready</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-2115%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.7.2-success" />
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

📚 **想深入了解？** → [完整快速入门指南](QUICKSTART.md) | [70+ 模块详细参考](SKILL.md)

---

<details>
<summary>🔍 点击展开：完整功能介绍与架构详解</summary>

## 🚀 V3.7.2: EventBus + Dispatcher Split + Tech Debt Cleanup

**DevSquad V3.7.2** introduces EventBus event-driven decoupling, splits dispatcher.py from 1660→706 lines (-57%), converts all 3 Mixins to Composition pattern, eliminates 166 f-string logger calls, fixes EnhancedWorker type mismatch bug, removes config_loader dead code, refactors skillifier parasitic coupling, narrows 29 broad except scopes, with 2115 tests passing.

---

## ⚡ Quick Start (4 Ways to Use DevSquad)

### 方式 1：命令行（推荐新手）

```bash
# Interactive setup wizard (1-2 minutes)
python scripts/cli.py init

# Then start collaborating!
devsquad dispatch -t "your task description"
```

### 方式 2：Web Dashboard（推荐团队）

```bash
# Start Streamlit dashboard with authentication
streamlit run scripts/dashboard.py

# Open http://localhost:8501
# Login with default account, then change password immediately.
# Username: admin   Password: <your-secure-password>
```

### 方式 3：REST API（推荐集成）

```bash
# Install dependencies
pip install fastapi uvicorn

# Start API server
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Access Swagger UI: http://localhost:8000/docs
# Access ReDoc:      http://localhost:8000/redoc
```

### 方式 4：Python API（推荐开发者）

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

DevSquad's 70+ modules are organized into **5 capability domains**, each solving a specific problem:

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
| **GitHub Actions CI** | Python 3.9-3.12 matrix testing | CI/CD pipelines |

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

> DevSquad provides **6 atomic sub-skills** that can be used independently or together.
> Each sub-skill is a thin wrapper (~50 lines) importing existing core modules — no duplicated logic.

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7-role orchestration)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6 intents × 3 languages)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5-axis code review)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + test strategy generation
└── retrospective/  → RetroSkill    — RetrospectiveEngine + pattern extraction
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
- **Python 3.9+** (3.9, 3.10, 3.11, 3.12 supported)
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
git clone https://github.com/weiransoft/devsquad.git
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
# Expected: devsquad 3.7.2

# Run tests
pytest tests/ -v --tb=short
# Expected: 1500+ passed
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
  backend: openai
  base_url: ""  # Set via DEVSQUAD_OPENAI_BASE_URL env var
  model: ""     # Set via DEVSQUAD_OPENAI_MODEL env var
  timeout: 120
```

Or use environment variables (higher priority):

```bash
export DEVSQUAD_LLM_BACKEND=openai
export DEVSQUAD_OPENAI_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_OPENAI_MODEL=gpt-4
export DEVSQUAD_OPENAI_API_KEY=sk-...
```

**Environment Variables Reference:**

| Variable | Purpose | Default |
|----------|---------|---------|
| `DEVSQUAD_LLM_BACKEND` | Default backend type (mock\|trae\|openai\|anthropic\|fallback) | `mock` |
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
python3 scripts/cli.py --version       # Expected: DevSquad 3.7.2
python3 scripts/cli.py status          # Expected: System ready
python3 scripts/cli.py roles           # Expected: 7 core roles listed
```

### Full Test Suite
```bash
# Run all tests (2115+ tests passing)
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

**Total: 2115+ tests**

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
| [SKILL.md](SKILL.md) | 完整技能手册 + 70+ 模块参考 | EN/CN/JP |
| [GUIDE.md](GUIDE.md) | 完全用户指南 | 中文 |
| [INSTALL.md](INSTALL.md) | 安装指南 (Unix + Windows) | EN/CN |
| [EXAMPLES.md](EXAMPLES.md) | 实际使用示例 | EN |
| [CHANGELOG.md](CHANGELOG.md) | 版本历史记录 | EN |
| [docs/i18n/README_CN.md](docs/i18n/README_CN.md) | 中文说明 | 中文 |
| [docs/i18n/README_JP.md](docs/i18n/README_JP.md) | 日本語説明 | 日本語 |
| [docs/PRD.md](docs/PRD.md) | 产品需求文档 | 中文 |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 技术架构文档 | 中文 |

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

*Last updated: 2026-06-16 | Version: V3.7.2*

</details>
