# DevSquad — Multi-Role AI Task Orchestrator

<p align="center">
  <strong>🎯 Upgrade "Single AI Assistant" to "Multi-Role AI Professional Team"</strong>
  <br>
  <em>One task → Multi-role AI collaboration → One conclusion | V5.1.0 (ImplementationCompletenessGate (S1 Gate) MINOR: Prevents AI implementation shortcuts by detecting mocks in production code (20% weight), missing classes/functions from P3 design docs (25%), missing test cases from P7 test plans (25%), unprotected I/O operations (15%), and missing security features (15%). Integrated into SimplicityRole before S2 gates (CRAP/Duplication). Weighted scoring with thresholds: ≥0.95 PASS, 0.90-0.95 WARNING, <0.90 REJECT. Progressive rollout: Shadow mode (Day 0-6), Soft mode (Day 7-13), Full mode (Day 14+). 91 tests (100% pass), test pyramid: 74% unit, 20% integration, 6% E2E. Anti-ghost verification via activation counters, production integration in SimplicityRole, user-visible Markdown output. P9 enhancements: concurrent file access (AC-007), large-scale PR performance 1000+ files <30s (AC-009), internationalization Unicode/CJK/emoji paths (AC-008). PRD: docs/prd/DevSquad-V5.1-ImplementationCompletenessGate-P2-PRD.md, Technical Design: P3, Test Plan: P7, Implementation Summary: P8. SemVer MINOR (new feature, backward compatible)) | V4.9.0 (defect-ledger MINOR: W1 defect ledger core — SQLite closed state machine open|fixed|closed with atomic writes and fail-closed load, signal_ref resolution contract, `defect` CLI six subcommands; W2 signal write-side — log_dispatch_end findings/failure_class extension, terminal-state wiring, Step 24 C19 recompute, PRD §4.2 mapping table; W3 registration gate — fail-closed mandatory-signal three-state tracking (tracked/unregistered/regressed), advisory unfiled-signal report, `.devsquad.yaml` switch; W4 feature gate — SHA256-anchored acceptance checklist, live pass/fail/waived coverage matrix, tamper detection, default off with zero trace; PRs #71/#76/#77/#80/#81/#83/#84) | V4.8.2 (gate-fix PATCH: print_debug false positives on the CLI command family found by dogfooding the gate on PR #71 — a print statement to stdout is the product interface of scripts/cli*.py, not debug residue; the diff scanner now exempts the CLI output layer for print_debug only, while secrets/eval/SQL-injection families stay fully covered in those files; PR #72) | V4.8.1 (gate-fix PATCH: F-D1 found by dogfooding the gate on this repo — diff pattern findings now honor the deterministic path gates: include/exclude and default excludes bind the diff scan, trailing /** restores gitignore directory semantics, secrets stay checked in all retained paths while code smells are limited to source-kind files; PR #62) | V4.8.0 (workflow-entry MINOR: QUICKSTART rewritten as three persona channels — IDE/MCP zero-key, CLI init branching with backend detection, maintainer wrapper workflow; doc_command gate keeps all 36 documented CLI commands true to the argparse registry; MCP integration guide as single source of truth; dogfooding quarterly report generator; TD-076 mcp>=1,<2 constraint; E1 consumer audit adjudicated — live-browser removed, impeccable vocabulary wired into `doctor --command`) | V4.7.2 (hygiene PATCH: six stale version strings removed from user-visible surfaces, negative stale-string gate scan, PROJECT_STATUS refreshed to release reality, api perf baseline measured) | V4.7.1 (release-integrity PATCH: PyPI devsquad entry point fixed — the scripts/cli/ package that shadowed cli.py removed, defusedxml dependency declared, release-gate e2e marker restored) | V4.7.0 (W1 delivered deterministic BREAK/VULN ten-category review taxonomy, C20, reverse gate, real review-gate subprocess E2E, and simulated real-user validation; MINOR; released as tag v4.7.0) | V4.6.0 (E2E-inspired testing infrastructure MINOR: LLM replay cache for PR CI — first real call records, later PRs replay near-zero cost; failure taxonomy product_failed/environment_blocked with exit 2; independent judge semantic assertions; e2e failure auto-comment on PRs) | V4.5.24 (CI-gate PATCH: dispatcher size baseline gate now also runs in PR CI) | V4.5.23 (Governance + root-cause PATCH: CI lint tools read from requirements-dev.lock at run time — fourth Dependabot-blind version copy eliminated; 8 GitHub Actions SHA-pinned + `.github/CODEOWNERS`; `:memory:` repo-root directory root-caused to `LLMCache(":memory:")` mkdir and fixed per SQLite convention in LLMCache/AsyncLLMCache) | V4.5.22 (Backend-config PATCH: gitignored `moka_ai.json` feeds the auto chain's Moka candidate as lowest-priority source — kwargs > env > file — restoring design order Moka → OpenAI(DeepSeek) → Anthropic; conftest autouse fixture isolates maintainer-local credentials from tests; `_build_api_backends` decomposed into per-provider builders after radon cc flagged D) | V4.5.21 (Security + toolchain PATCH: Dependabot vuln closure, branch-protection bypass tightening, CI least-privilege; ruff 0.16.10/mypy 2.4.0 aligned across lock + pre-commit + CI pins; flaky hardening — min-of-3 latency sampling, host-bridge fuse E2E warm-up; `enable_anchor_check=False` factory fix) | V4.5.20 (Version-SSOT truth + deterministic review bundling MINOR: `--mode review --changeset` wired to real bundling, sub-skill manifest gate closed, anti-ghost production probe) | V4.5.19 (Flaky-test cleanup: dashboard latency gate → 5-run median + pytest-rerunfailures) | V4.5.18 (Perf-extension: SQLite PRAGMA to ccr_store/history_manager + SkillRegistry thread-safety hotfix) | V4.5.17 (V4.6.1-cleanup: PR #9 CI repair + e2e portability + release-readiness) | V4.5.16 (Housekeeping + Digital Truth PATCH: 18-file SSOT sync, badge 9400+/211+, date 2026-09-03) | V4.5.15 (Skill registration gate + Prometheus E2E + 3-level TRAE cache sync) | V4.5.10 (HostLLMBridge v2 production wiring + --async CLI: v2 protocol hardening + factory v2 default + v1/v2 isolation) | V4.5.9 (Unified Gather Execution Core + Native Async Worker: 执行层统一 gather 化 + Worker 原生异步) | V4.5.8 (FileRiskStore persistence + risks add/assess/mitigate/close + exposure filters) | V4.5.7 (Coeffect Async + Risk Register UX CLI) | V4.5.6 (Module Fiber + Coeffect: 6-state FSM + topological activation + modules CLI) | V4.5.3 (Artifacts + Effect — ArtifactStore + DispatchEffect + EffectRegistry + Audit CLI) | V4.5.2 (Experience polish: MOKA + Metrics + GitLab + Doctor + BackendConfig) | V4.5.0 (cross-session continuity + protocol-native skills)</em>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Test quality" src="https://img.shields.io/badge/Test%20quality-0%20MAJOR-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V5.1.0-success" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Quality" src="https://img.shields.io/badge/Code%20Quality-4.3%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%86-blue" />
  <img alt="Security" src="https://img.shields.io/badge/Security-5%2F5%20%E2%98%85%E2%98%85%E2%98%85%E2%98%85%E2%98%85-success" />
</p>

---

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

### When to Use DevSquad?

| Your Need | Recommended Solution |
|---------|---------|
| Simple Q&A ("How to write for loop in Python?") | Use ChatGPT/Claude directly ✅ |
| Code snippet review | DevSquad single-role mode ✅ |
| Complex system design (needs multiple perspectives) | **DevSquad multi-role collaboration** 🎯 |
| Production automation workflow | **DevSquad + REST API + Dashboard** 🎯 |

📚 **Want to dive deeper?** → [Complete Quick Start Guide](QUICKSTART.md) | [218+ Module Reference](SKILL.md)

---

<details>
<summary>🔍 Click to expand: Complete feature introduction and architecture details</summary>

## Historical release details: V4.5.2 and earlier

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
- **FileBundler**: Deterministic file bundling for review mode (from open-code-review). Invoked via `dispatch --mode review --changeset <files...>`; more than 5 files engage bundling, grouped by directory + imports (bundle count follows the grouping, not the file count)
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
- **Discovered tests**: 9794 across 403 files in the current local scan
- **Integration tests**: 14.9% (target ≥15%; warning remains)
- **Unclassified tests**: 0
- **E2E coverage**: present in `tests/e2e/`; final pass count requires the current CI run

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

9800+ tests collected (current local scan; pass counts are CI-authoritative).

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
# Expected: DevSquad 5.1.0

# Run tests
pytest tests/ -v --tb=short
# Expected: 9800+ collected (pass counts are CI-authoritative)
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
python3 scripts/cli.py --version       # Expected: DevSquad 5.1.0
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

*Last updated: 2026-10-27 | Version: V4.9.0 (defect-ledger MINOR: W1 defect ledger core — SQLite closed state machine open|fixed|closed with atomic writes and fail-closed load, signal_ref resolution contract, `defect` CLI six subcommands; W2 signal write-side — log_dispatch_end findings/failure_class extension, terminal-state wiring, Step 24 C19 recompute, PRD §4.2 mapping table; W3 registration gate — fail-closed mandatory-signal three-state tracking (tracked/unregistered/regressed), advisory unfiled-signal report, `.devsquad.yaml` switch; W4 feature gate — SHA256-anchored acceptance checklist, live pass/fail/waived coverage matrix, tamper detection, default off with zero trace; PRs #71/#76/#77/#80/#81/#83/#84) | V4.8.2 (gate-fix PATCH: print_debug false positives on the CLI command family found by dogfooding the gate on PR #71 — a print statement to stdout is the product interface of scripts/cli*.py, not debug residue; the diff scanner now exempts the CLI output layer for print_debug only, while secrets/eval/SQL-injection families stay fully covered in those files; PR #72) | V4.8.1 (gate-fix PATCH: F-D1 found by dogfooding the gate on this repo — diff pattern findings now honor the deterministic path gates: include/exclude and default excludes bind the diff scan, trailing /** restores gitignore directory semantics, secrets stay checked in all retained paths while code smells are limited to source-kind files; PR #62) | V4.8.0 (workflow-entry MINOR: QUICKSTART three persona channels — IDE/MCP zero-key, CLI init branching, maintainer wrapper; doc_command gate keeps all 36 documented CLI commands true to the argparse registry; MCP integration guide as single source of truth; dogfooding quarterly report generator; TD-076 mcp>=1,<2 constraint; E1 consumer audit adjudicated — live-browser removed, impeccable vocabulary wired into `doctor --command`) | V4.7.2 (hygiene PATCH: six stale version strings removed from user-visible surfaces, negative stale-string gate scan, PROJECT_STATUS refreshed to release reality, api perf baseline measured) | V4.7.1 (release-integrity PATCH: PyPI devsquad entry point fixed — the scripts/cli/ package that shadowed cli.py removed, defusedxml dependency declared, release-gate e2e marker restored) | V4.7.0 (W1 delivered deterministic BREAK/VULN ten-category review taxonomy, C20, reverse gate, real review-gate subprocess E2E, and simulated real-user validation; MINOR; released as tag v4.7.0) | V4.6.0 (E2E-inspired testing infrastructure MINOR: LLM replay cache for PR CI — first real call records, later PRs replay near-zero cost; failure taxonomy product_failed/environment_blocked with exit 2; independent judge semantic assertions; e2e failure auto-comment on PRs) | V4.5.24 (CI-gate PATCH: dispatcher size baseline gate now also runs in PR CI) | V4.5.23 (Governance + root-cause PATCH: CI lint tools read from requirements-dev.lock at run time — fourth Dependabot-blind version copy eliminated; 8 GitHub Actions SHA-pinned + `.github/CODEOWNERS`; `:memory:` repo-root directory root-caused to `LLMCache(":memory:")` mkdir and fixed per SQLite convention in LLMCache/AsyncLLMCache) | V4.5.22 (Backend-config PATCH: gitignored `moka_ai.json` feeds the auto chain's Moka candidate as lowest-priority source — kwargs > env > file — restoring design order Moka → OpenAI(DeepSeek) → Anthropic; conftest autouse fixture isolates maintainer-local credentials from tests; `_build_api_backends` decomposed into per-provider builders after radon cc flagged D) | V4.5.21 (Security + toolchain PATCH: Dependabot vuln closure, branch-protection bypass tightening, CI least-privilege; ruff 0.16.10/mypy 2.4.0 aligned across lock + pre-commit + CI pins; flaky hardening — min-of-3 latency sampling, host-bridge fuse E2E warm-up; `enable_anchor_check=False` factory fix) | V4.5.20 (Version-SSOT truth + deterministic review bundling: `--mode review --changeset` wired to real bundling, sub-skill manifest version gate, anti-ghost production probe — MINOR) | V4.5.19 (Flaky-test cleanup: dashboard latency gate → 5-run median + pytest-rerunfailures) | V4.5.18 (Perf-extension: SQLite PRAGMA to ccr_store/history_manager + SkillRegistry thread-safety hotfix) | V4.5.17 (V4.6.1-cleanup: PR #9 CI repair + e2e portability + release-readiness) | V4.5.16 (Housekeeping + Digital Truth PATCH: 18-file SSOT sync, badges 9400+/204+, date 2026-09-03) | V4.5.15 (Skill registration gate + Prometheus E2E + 3-level TRAE cache sync) | V4.5.10 (HostLLMBridge v2 production wiring + --async CLI) | V4.5.9 (Unified Gather Execution Core + Native Async Worker) | V4.5.8 (FileRiskStore persistence + risks add/assess/mitigate/close + exposure filters) | V4.5.7 (Coeffect Async + Risk Register UX CLI) | V4.5.6 (Module Fiber + Coeffect: 6-state FSM + topological activation + modules CLI) | V4.5.3 (Artifacts + Effect — ArtifactStore + DispatchEffect + EffectRegistry + Audit CLI) | V4.5.2 (Experience polish: MOKA + Metrics + GitLab + Doctor + BackendConfig) | V4.5.0 (cross-session continuity + protocol-native skills) | V4.4.0 (5 new enhancement modules: RiskRegister / ViewpointRegistry / ErrorBudgetTracker / GapAnalyzer / DoraMetricsCollector — see [CHANGELOG.md](CHANGELOG.md))*

</details>
