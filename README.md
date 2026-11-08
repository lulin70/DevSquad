# DevSquad — Multi-Role AI Task Orchestrator

<p align="center">
  <strong>🎯 Upgrade "Single AI Assistant" to "Multi-Role AI Professional Team"</strong>
  <br>
  <em>7 roles · 12 phases · 10,656 tests<br>V4.10.0 — see <a href="#-release-history">Release History</a></em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Test quality" src="https://img.shields.io/badge/Test%20quality-0%20MAJOR-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V4.10.0-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

## 📑 Contents

- [📖 TL;DR? Start Here (30 Seconds)](#-tldr-start-here-30-seconds)
- [🚀 Install](#-install)
- [▶️ Quick Start: Run Your First Task](#️-quick-start-run-your-first-task)
- [⚙️ Configuration](#️-configuration)
- [👥 Features: 7 Core Roles](#-features-7-core-roles)
- [🏗️ Features: Five Capability Domains](#️-features-five-capability-domains)
- [🔬 Cybernetics Enhancement Modules (V3.6.1)](#-cybernetics-enhancement-modules-v361)
- [🏗️ Architecture Overview (Layered Design)](#️-architecture-overview-layered-design)
- [🧩 Layered Sub-Skill Architecture (V3.6.0)](#-layered-sub-skill-architecture-v360)
- [📋 Plan C Architecture (Core Engine)](#-plan-c-architecture-core-engine)
- [🧪 Testing](#-testing)
- [📚 Documentation](#-documentation)
- [📜 Release History](#-release-history)
- [🗺️ Roadmap](#️-roadmap)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)

## 📖 TL;DR? Start Here (30 Seconds)

### What is DevSquad?

**DevSquad** is a multi-role AI task orchestrator. When you submit a task, instead of getting a single AI response, it matches multiple specialized roles to collaborate and delivers a conclusion reviewed by multiple perspectives.

```
Traditional AI:  You ──→ ChatGPT ──→ One answer (may be incomplete)
DevSquad:        You ──→ DevSquad ──→ [Architect+Security+Test+Dev...] ──→ Multi-dimensional consensus
```

### Core Advantages (vs. Single AI)

| Pain Point | Traditional Single AI | DevSquad |
|------|----------|----------|
| **Single Perspective** | Generic viewpoint only | Task-matched multi-role collaboration ✅ |
| **Uncontrolled Quality** | May miss security issues | Multi-dimensional cross-validation + consensus ✅ |
| **No Audit Trail** | Unknown answer basis | Complete audit chain + SHA256 integrity ✅ |
| **Complex Task Failure** | Long tasks lose context | Checkpoint resume + workflow engine ✅ |

### Quickest Start (5 Minutes)

```bash
# Install
pip install devsquad

# Run - Let AI team design authentication system
devsquad run "Design a secure user authentication system" --roles architect security tester coder

# Output structured report:
# ✅ Architect recommendation: Adopt JWT + Refresh Token approach...
# ✅ Security expert review: Guard against CSRF, XSS, SQL injection...
# ✅ Test strategy: Unit test coverage 90%+...
# ✅ Development implementation: Complete code framework provided...
# ✅ Consensus conclusion: Approach viable, risks controlled...
```

> **Next step** → [Install](#-install) · [7 ways to run your first task](#️-quick-start-run-your-first-task) · [Configuration](#️-configuration)

### When to Use DevSquad?

| Your Need | Recommended Solution |
|---------|---------|
| Simple Q&A ("How to write for loop in Python?") | Use ChatGPT/Claude directly ✅ |
| Code snippet review | DevSquad single-role mode ✅ |
| Complex system design (needs multiple perspectives) | **DevSquad multi-role collaboration** 🎯 |
| Production automation workflow | **DevSquad + REST API + Dashboard** 🎯 |

📚 **Want to dive deeper?** → [Complete Quick Start Guide](QUICKSTART.md) | [218+ Module Reference](SKILL.md)

---

## 🚀 Install

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
# Expected: DevSquad 4.10.0

# Run tests
pytest tests/ -v --tb=short
# Expected: 9800+ collected (pass counts are CI-authoritative)
```

---

## ▶️ Quick Start: Run Your First Task

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
python3 -m scripts.mcp_server

# Or SSE transport (for remote access)
python3 -m scripts.mcp_server --port 8080
```

Full integration guide — install (`pip install "devsquad[mcp]" "mcp<2"`), client config JSON (Cursor / Claude Desktop), the 9-tool catalog, and RBAC / fail-closed behavior: [docs/integrations/MCP.md](docs/integrations/MCP.md).

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

# Launch the API and Streamlit dashboard together
./scripts/start.sh --dashboard

# Override API port
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# Show help
./scripts/start.sh --help
```

`start.sh` is the unified entry point introduced in V3.9.2 (P0-2). It validates the environment, initializes the database, builds the frontend, and starts the service in one command. Use `requirements.lock` alongside it for reproducible builds (`pip install -r requirements.lock`). V4.1.0 adds Loop Engineering, UI/UX inspection, Adversarial validation, DAG visualization, Autonomous mode, and plugin hot-reloading.

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
| `MOKA_TIMEOUT` | Moka LLM request timeout (seconds, V4.10.0+) | `90.0` |
| `DEVSQUAD_LOG_LEVEL` | Logging level | `WARNING` |

**Moka LLM Configuration**: For local Moka service tuning (timeout, retries), see [Moka Tuning Guide](docs/MOKA_TUNING_GUIDE.md).

---

## 👥 Features: 7 Core Roles

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

## 🏗️ Features: Five Capability Domains

DevSquad's 218+ modules are organized into **5 capability domains**, each solving a specific problem:

### 🎯 Domain 1: Task Orchestration Engine (Core)

> **Command center for efficient multi-role collaboration**

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
           → [Sync/Async Worker Execution] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

### 🛡️ Domain 2: Quality Assurance System

> **Prevents AI from "cutting corners" or "hallucinating"**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **InputValidator** | Security validation + 40-pattern detection (14 forbidden + 21 prompt injection + 5 suspicious) | Production environments |
| **VerificationGate** | Mandatory evidence requirements + 7 Red Flags detection | Critical decision scenarios |
| **AntiRationalizationEngine** | Per-role excuse→rebuttal tables to prevent quality shortcuts | High quality requirements |
| **TestQualityGuard** | Test quality audit (API validation / anti-pattern detection / dimension coverage) | Pre-release verification |
| **PermissionGuard** | 4-level safety gate (PLAN/DEFAULT/AUTO/BYPASS) | Security-sensitive tasks |

### ⚡ Domain 3: Performance & Reliability

> **Makes the system faster, more stable, and more cost-efficient**

| Module | Purpose | When to Use |
|--------|---------|------------|
| **LLMCache** | TTL-based LRU cache with disk persistence (60-80% cost reduction) | High-frequency usage |
| **LLMRetry** | Exponential backoff + circuit breaker + multi-backend fallback | Unstable networks |
| **FeedbackControlLoop** | Closed-loop feedback control with automatic iteration until quality threshold met | High quality output pursuit |
| **ExecutionGuard** | Real-time abort guard (timeout/output/keywords) for safe execution | Long-running tasks |
| **FallbackBackend** | Automatic backend failover with health monitoring | High availability requirements |

### 📊 Domain 4: Observability & Governance

> **Know what the system is doing and how well it's performing**

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

> **Integrates with your existing toolchain**

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

> **Non-invasive wrapper design — Optional switches, zero modifications to existing core logic**

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

### 1️⃣ FeedbackControlLoop (Feedback Control Loop)
- Closed-loop feedback control with automatic iteration until quality threshold met
- Configurable quality gate (`quality_gate`) and maximum iterations
- Lightweight quality assessment (no LLM calls), supports dry-run mode

### 2️⃣ ExecutionGuard (Execution Guardian)
- Real-time execution monitoring with 4 abort conditions: timeout, output size, token count, critical keywords
- Lightweight checks (<1ms), zero external dependencies
- Dynamically configurable thresholds

### 3️⃣ PerformanceFingerprint (Performance Fingerprint System)
- Unified execution fingerprint recording (fuses 4 data sources)
- Pure Python TF-IDF implementation (no sklearn/numpy), supports English/Chinese mixed content
- JSON persistence to `.devsquad_data/fingerprints/`, graceful cold-start degradation

### 4️⃣ SimilarTaskRecommender (Similar Task Recommender)
- TF-IDF-based task similarity search with historical success configuration recommendations
- Intelligent role combination recommendation, intent prediction, execution time estimation
- Confidence scoring (high/medium/low), graceful cold-start degradation

### 5️⃣ AdaptiveRoleSelector (Adaptive Role Selector)
- Three-tier selection strategy based on historical success rates
- Configurable minimum success rate and maximum role count
- Supports manual statistics updates and comprehensive role effectiveness reporting

**Recommended usage** (progressive adoption):
```python
from scripts.collaboration import MultiAgentDispatcher, FeedbackControlLoop, ExecutionGuard, PerformanceFingerprint

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

**Unified Lifecycle Architecture** - Resolves CLI 6 commands vs 12-phase lifecycle (P0-P11):

```
CLI View Layer (6 commands)          Core Engine (12 phases)
┌─────────────────────┐            ┌──────────────────────────┐
│ spec → P1, P2       │───View ──→│ P0: Discovery (optional) │
│ plan → P7           │   Mapping │ P1: Requirements         │
│ build → P8          │            │ P2: Architecture         │
│ test → P9           │            │ P3: Technical Design     │
│ review → P8,P6      │            │ ...                      │
│ ship → P10          │            │ P11: Operations          │
└─────────────────────┘            └──────────────────────────┘
        ↓                                    ↓
  UnifiedGateEngine                   CheckpointManager
  (Phase + Worker gates)              (Lifecycle state persistence)
```

**Core Components:**
- ✅ **LifecycleProtocol** - Abstract interface for unified lifecycle management
- ✅ **UnifiedGateEngine** - Integrates VerificationGate + Phase transition gates
- ✅ **FullLifecycleAdapter** - Complete 12-phase lifecycle with dependency resolution
- ✅ **Enhanced CheckpointManager** - Auto save/restore lifecycle state across sessions

---

## 🧪 Testing

### Quick Smoke Test (< 30 seconds)
```bash
python3 scripts/cli.py --version       # Expected: DevSquad 4.10.0
python3 scripts/cli.py status          # Expected: System ready
python3 scripts/cli.py roles           # Expected: 7 core roles listed
```

### Full Test Suite
```bash
# Run all tests (9800+ collected)
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

**Total: 9800+ collected tests / 492 e2e (current local scan)**

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
| [**QUICKSTART.md**](QUICKSTART.md) | **⭐ 30-second quick start guide (recommended for new users)** | Chinese |
| [SKILL.md](SKILL.md) | Complete skill manual + 218+ module reference | EN/CN/JP |
| [GUIDE.md](GUIDE.md) | Complete user guide | Chinese |
| [INSTALL.md](INSTALL.md) | Installation guide (Unix + Windows) | EN/CN |
| [EXAMPLES.md](EXAMPLES.md) | Real-world usage examples | EN |
| [CHANGELOG.md](CHANGELOG.md) | Version history | EN |
| [README-CN.md](README-CN.md) | Chinese documentation | Chinese |
| [README-JP.md](README-JP.md) | Japanese documentation | Japanese |
| [docs/prd/V4.6.1_cleanup_PRD.md](docs/prd/V4.6.1_cleanup_PRD.md) | Product requirements document | Chinese |
| [docs/architecture/ARCHITECTURE_V4.md](docs/architecture/ARCHITECTURE_V4.md) | Technical architecture document | Chinese |
| [docs/planning/V43_ROADMAP_PROPOSAL.md](docs/planning/V43_ROADMAP_PROPOSAL.md) | V4.3 unified roadmap v1.2 (7-Role consensus) | Chinese |
| [docs/prd/V4.3.0_PRD.md](docs/prd/V4.3.0_PRD.md) | V4.3.0 PRD (requirements/user stories/acceptance criteria) | Chinese |
| [docs/architecture/V4.3.0_ARCHITECTURE.md](docs/architecture/V4.3.0_ARCHITECTURE.md) | V4.3.0 architecture design (module boundaries/interface contracts/dependency graph) | Chinese |
| [docs/testing/V4.3.0_TEST_PLAN.md](docs/testing/V4.3.0_TEST_PLAN.md) | V4.3.0 test plan (test pyramid/E2E/real user simulation) | Chinese |

---

## 📜 Release History

### V4.10.0 — 2026-11-05
- Lifecycle definition is single-source: `PHASE_TEMPLATES` is the only definition.
- P0 (Discovery & Feasibility) added as an optional phase.
- Gate conditions added: dependency/supply-chain scan, NFR targets with UAT sign-off, data migration with reconciliation.
- P11 roles corrected: DevOps leads; architect and security review.
- Role participation is enforced after recording.

### V4.9.0 — 2026-10-27
- W1 defect ledger: atomic JSON state machine, fail-closed load, `devsquad defect` CLI.
- W2 signal write-side: `findings` and `failure_class` on `log_dispatch_end`.
- W3 registration gate: fail-closed mandatory-signal tracking.
- W4 feature gate: SHA256-anchored checklist with tamper detection.

Older releases (V4.8.2 and earlier) are in [CHANGELOG.md](CHANGELOG.md).


## 🗺️ Roadmap

### V4.3.0 (In Progress — 7-Role Consensus Reached, Documentation First)

**Release Strategy**: V4.3.0 pre-release (complete code + documentation + E2E validation) → user confirmation → V4.3.0 official release

**Integrating three aspects**:
1. Technical debt continuous governance (`todo_drift_monitor` + CI blocking)
2. pickle→JSON migration (dead code removal + fallback security tightening + removal)
3. Upstream TraeMultiAgentSkill v2.6-v2.8 refinement inspiration (Ponytail dual-mode / LoopKernel rollback / UIUX audit / Dashboard visualization)

**V4.3.0 Scope (9 items)**:

| ID | Name | Priority |
|----|------|--------|
| P0-1 | pickle dead code removal + fallback security tightening | P0 |
| P0-2 | `todo_drift_monitor.py` + CI blocking + PR template | P0 |
| P1-1 | Ponytail lite/full dual-mode + DebtCollector + RequirementTracer | P1 |
| P1-4 | LoopKernel RollbackStrategy + independent hard limit | P1 |
| P1-5 | UIUXAnalyzer sub-item audit + on-demand completion | P1 |
| P1-6 | Dashboard state visualization | P1 |
| P2-1 | pickle fallback removal | P2 |
| P2-2 | Autonomous SmartConfirmation documentation completion | P2 |
| P2-4 | V4.3.0 release documentation sync | P2 |

**7-Role Consensus**: 7/7 APPROVE_WITH_CONCERNS, consensus achieved after 10 adjustments. See [V43_ROADMAP_PROPOSAL.md](docs/planning/V43_ROADMAP_PROPOSAL.md) v1.2 for details.

**Project Lifecycle**: Follow 11-Phase model (P1 Requirements → P2 Architecture → P3 Technical Design → P7 Test Plan → P8 Implementation → P9 Test Execution → P10 Deployment Release)

**Test Pyramid Guarantee**: unit ≥60% / integration 15-25% / e2e ≤10% / contract 5-10% / smoke ≤5%

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
  <strong>⭐ If DevSquad helps you, please give it a Star! ⭐</strong>
  <br>
  <em>Let more developers enjoy the power of "AI Team Collaboration"</em>
  <br>
  <br>
  <strong>🙏 Acknowledgments</strong>
  <br>
  Inspired by <a href="https://github.com/weiransoft/TraeMultiAgentSkill">TraeMultiAgentSkill</a> upstream project
  <br>
  Built with ❤️ by the DevSquad team
</p>

---

*Last updated: 2026-11-08 | Version: V4.10.0 — full changelog in [Release History](#-release-history).*
