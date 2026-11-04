---
name: devsquad
slug: devsquad
version: 5.1.0
description: |
  DevSquad V5.1.0 — 多角色 AI 任务编排技能
  不是单一功能工具：编排 7 个可用角色 + 8 个原子子技能
  (dispatch/intent/review/security/test/retrospective/prototype/teach)。
  一个任务 → 任务匹配的多角色协作 → 共识结论。
  
  V5.1.0 核心特性：ImplementationCompletenessGate (S1 Gate) 防止 AI 实现捷径
  通过检测生产代码中的 mock、缺失设计元素、不完整测试、未保护 I/O 和缺失安全功能。
  渐进式发布：Shadow 模式（0-6 天）→ Soft 模式（7-13 天）→ Full 模式（14 天起）。
  
  219 个公共核心模块；7 种调用方式：TRAE Skill + MCP + CLI + Python API + REST API + Dashboard + start.sh。
  默认 Mock 模式（无需 API 密钥）；通过 OpenAI/Anthropic/MOKA AI 接入真实 LLM。
  
  📚 完整版本历史 → docs/reference/VERSION_HISTORY.md
---

# DevSquad V5.1.0 — Multi-Role AI Task Orchestrator

## 🎯 一句话理解（3 秒）

**DevSquad = 把「单个 AI 助手」升级成「7 人 AI 专业团队」**

```
传统 AI:  你 ──→ ChatGPT ──→ 一个回答（可能不全面）
DevSquad:  你 ──→ DevSquad ──→ [架构师+安全+测试+开发...] ──→ 多维度共识结论
```

## ⚡ 核心工作流（30 秒）

### Core Positioning

This Skill upgrades Trae from a "single AI assistant" to a "multi-AI team". When a task is submitted, it is no longer handled by a single role:

```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [Sync/Async Worker Execution] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

### 对比：单 AI vs DevSquad

| 维度 | 单个 AI (ChatGPT/Claude) | DevSquad |
|------|---------------------------|----------|
| 视角 | 一个角色回答 | **按任务匹配多个专业角色** |
| 质量 | 可能遗漏安全/测试 | **多维度交叉验证** |
| 可追溯 | 无 | **完整审计链 (SHA256)** |
| 适用场景 | 简单问答 | **复杂工程任务** |

### 最快上手（5 分钟）

```bash
# 安装
pip install devsquad

# 运行 - 让 AI 团队帮你设计认证系统
devsquad run "设计一个安全的用户认证系统" --roles architect security tester coder

# 输出结构化报告：
# ✅ 架构师建议：采用 JWT + Refresh Token 方案...
# ✅ 安全专家审查：需防范 CSRF、XSS、SQL 注入...
# ✅ 测试策略：单元测试覆盖率达 90%+...
# ✅ 开发实现：提供完整代码框架...
# 📊 共识结论：方案可行，风险可控...
```

📚 **完整快速入门指南** → [QUICKSTART.md](QUICKSTART.md)

## Reference Documentation

> SKILL.md is the concise entry-point overview. Detailed reference material has been split into modular docs (PRD §10.2). All information is preserved — nothing was deleted, only moved.

| Reference Doc | Content | Target Audience |
|---------------|---------|-----------------|
| [docs/reference/MODULE_REFERENCE.md](docs/reference/MODULE_REFERENCE.md) | Full 218+ module table, test coverage matrix, advanced features guide, cybernetics enhancement, dispatch modes, system status, error handling | Contributors / module developers |
| [docs/reference/SUB_SKILLS.md](docs/reference/SUB_SKILLS.md) | 8 atomic sub-skills (dispatch/intent/review/security/test/retrospective/prototype/teach), complete dispatch workflow, 11-phase project lifecycle, testing iron rules, meta iron rule, delivery workflow iron rules | Skill users / test engineers |
| [docs/reference/DEFECT_LEDGER.md](docs/reference/DEFECT_LEDGER.md) | Defect ledger contract (V4.9.0): JSON schema + closed state machine (open/fixed/closed) + two hazard guards + `signal_ref` resolution + mandatory-signal mapping + registration-gate three-state tracking + `devsquad defect add/update/close/reopen/list/audit` CLI | Run operators / defect filers |
| [docs/reference/VERSION_HISTORY.md](docs/reference/VERSION_HISTORY.md) | Version History + per-version changelog (v1.0 → v4.9.0) | Release tracking / auditors |

## ⚠️ Honest Disclosure (V4.5.6 G6 Complete)

DevSquad is a **hybrid AI orchestration skill** with explicit capability boundaries. We disclose these honestly (weiransoft v2.8.4 G6 complete):

### 1. Prompt-layer AI is delegated to the host LLM

When you invoke DevSquad inside an AI IDE (TRAE / Cursor / Claude Desktop), the prompt composition + 7-role orchestration are executed by the **host LLM** of that IDE (Claude / GPT / Gemini / Moka). DevSquad itself does not embed an LLM — it constructs structured multi-role prompts and relies on the host's chat completion to generate role-specific responses.

### 2. Script-layer deterministic tooling (Python CLI / API / MCP)

The 218+ core modules are deterministic Python code:
- `MultiAgentDispatcher` matches the required roles and executes them through the current sync/async worker paths
- `ScratchpadHistoryStore` persists cross-role state via atomic writes
- `ApprovalGate` enforces human-in-the-loop decisions
- `AntiGhostChecker` ensures modules are activated (not just present)
- `TestQualityGuard` enforces test rigor (no anti-patterns like status-code-only)

These run identically regardless of host LLM, with reproducible outputs.

### 3. Real-LLM backend (OpenAI / Anthropic / Moka) — opt-in only

When invoked from CLI / REST API with a configured `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` / `MOKA_API_KEY`, DevSquad routes through real LLM backends. Without keys, the `MockBackend` is used. Since V4.5.24, Moka credentials may also come from a gitignored repo-root `moka_ai.json` (`{"url", "model", "key"}`) — the lowest-priority source: env vars and caller kwargs always win.

**V4.5.6 W4 enhancement**: Real-LLM smoke tests now auto-skip when the configured API key returns 401 (`DEVSQUAD_SKIP_INVALID_LLM_KEY=1` default). To surface key-rotation issues in CI, set `DEVSQUAD_SKIP_INVALID_LLM_KEY=0`.

### 4. Offline / no-network degradation (V4.5.0+)

When the host LLM is unreachable (no network, IDE in airplane mode, B-path timeout), DevSquad gracefully degrades:

- **TF-IDF fallback**: `IntentMapper` falls back to TF-IDF + cosine similarity (deterministic, no LLM)
- **Hashing fallback**: For pure routing decisions, `HashingVectorizer` (V4.4.0) provides sub-millisecond intent matching
- **Mock response**: For role responses, `MockBackend` returns deterministic placeholder text
- **Degraded dispatch**: `B-path` (real LLM, 600s timeout) → `A-path` (cached/template, <1s) → `C-path` (mock, instant)

### 5. Outside the TRAE IDE: behavior changes

If you invoke DevSquad from a **non-AI IDE shell** (e.g., bare `python3 scripts/cli.py dispatch` in a terminal without LLM):
- `MultiAgentDispatcher.dispatch()` returns the assembled prompt structure but **does NOT execute role calls**
- You get a structured markdown plan, not actual role output
- For real role responses, you must be inside an AI chat session (TRAE IDE / Claude Desktop) where the host LLM completes the role prompts

**Bottom line**: DevSquad is a **prompt-orchestration framework**, not a standalone AI model. Its value is in:
1. **Structured multi-role collaboration** (deterministic prompts, consistent format)
2. **Cross-session continuity** (Scratchpad + AgentIdentity + WorkflowTrace)
3. **Anti-ghost guarantees** (modules activated, not just present)
4. **Tested dispatch pipeline** (current quality gates report findings without claiming unverified totals)

The actual "intelligence" comes from the host LLM, which is honest and explicit.

## 📜 Deterministic-Layer Contract (V4.5.20 W1-0)

The script layer above is deterministic — but only if you know what it promises.
Three commitments decide which mode you should use; read them before choosing:

1. **Delegation requires no API key.** Delegated mode (`host`) reads **no** API-key
   environment variable — it works with `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` and
   `MOKA_API_KEY` all unset. DevSquad supplies the deterministic scaffolding, the
   host Agent supplies the LLM, and the output quality is the host Agent's.
   *This is a boundary, not a free model*: no key does not mean DevSquad generates
   real LLM output itself. Protocol violations raise rather than silently falling
   back to the mock backend.
2. **Incomplete coverage exits non-zero.** If part of the requested code was never
   examined, DevSquad does **not** return `0` with a partial report — the build must
   not pass while code went unread. Interactive callers who want the partial result
   should read it as data and ignore the exit code. Every failed role is named
   individually, because *which* role failed decides what you do next.
3. **`review --preview` makes zero LLM calls.** It prints the plan — what will be
   reviewed and what was dropped, by which gate — so you can price a review without
   paying for it. Sensitive paths are redacted or reduced to counts; output is
   summary-first, with `--verbose` for per-path detail.

The full contract — the eight named filter gates, the four-layer rule chain and its
first-match semantics, and the delegation protocol boundary — is in
[docs/reference/DETERMINISTIC_CONTRACT.md](docs/reference/DETERMINISTIC_CONTRACT.md).
Each clause there carries an `Effective` wave, so nothing is promised ahead of the
code that ships it.

> **Status honesty (V4.5.20 W1 + C9/C10)**: this section was written ahead of the
> implementation, by design, and is now synchronized with the shipped waves.
> Shipped: commitment 1; commitment 2 (C9/C10 incomplete-coverage enforcement and
> named failure attribution); commitment 3 (`review --preview`); the rule-chain + gate
> detail (W1-1 … W1-4); W1-5/C18 (review input contract); W1-6/C16-C17
> (host delegation selection, observable degradation, strict fail-closed protocol
> handling, and no silent Mock fallback); and W1-7 (unified role-candidate
> fields, deterministic deduplication/order, and production Dispatch/CLI
> visibility). `Effective` in the contract doc is authoritative for what is live
> today. Drift is checked by `scripts/check_skill_contract.py`, which verifies
> *presence*, not behaviour.

**Quick navigation:**
- Looking for a module's file/responsibility? → [MODULE_REFERENCE.md](docs/reference/MODULE_REFERENCE.md)
- Looking for sub-skill usage or test iron rules? → [SUB_SKILLS.md](docs/reference/SUB_SKILLS.md)
- Looking for what changed in a version? → [VERSION_HISTORY.md](docs/reference/VERSION_HISTORY.md)
- Looking for the deterministic-layer contract? → [DETERMINISTIC_CONTRACT.md](docs/reference/DETERMINISTIC_CONTRACT.md)

---

## Quick Start (Must Follow)

### Installation

```bash
# Install from PyPI (recommended)
pip install devsquad

# With optional dependencies
pip install "devsquad[api]"    # Includes FastAPI + Streamlit dashboard
pip install "devsquad[all]"    # All optional dependencies

# Or install in development mode (for contributors)
pip install -e .
pip install -e ".[api]"       # With API/dashboard dependencies
```

### Method 1: Python API — One-Click Collaboration (Recommended)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock mode (default) — returns assembled prompts, no API key needed
disp = MultiAgentDispatcher()
result = disp.dispatch("User's described task")
print(result.to_markdown())
disp.shutdown()
```

### Method 1b: Real AI Output (with LLM Backend)

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
result = disp.dispatch("Design user authentication system", roles=["architect", "security"])
print(result.to_markdown())
disp.shutdown()
```

**When to use Method 1**:
- User requests like "Design XX", "Implement XX", "Analyze XX"
- Need quick multi-role collaboration results
- No need for fine-grained role control

### Method 2: CLI (Command Line Interface)

```bash
# Basic dispatch (mock mode, no API key needed)
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec

# Real AI output with LLM backend
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec --backend openai

# V4.5.0: List recent dispatch sessions
python3 scripts/cli.py sessions list

# V4.5.0: Show details of a specific session
python3 scripts/cli.py sessions show <session-id>

# V4.5.0: Resume an interrupted dispatch
python3 scripts/cli.py dispatch --resume <session-id>

# Dry-run mode (analyze only, no execution)
python3 scripts/cli.py dispatch -t "Test task" --dry-run
```

**When to use Method 2**:
- Quick terminal-based dispatch without writing Python code
- CI/CD pipeline integration via shell scripts
- Session management (list, inspect, resume)

### Method 3: MCP Server (Model Context Protocol)

```bash
# Start MCP server with stdio transport (default, for IDE integration)
python3 -m scripts.mcp_server

# Start MCP server with SSE transport (for remote access)
python3 -m scripts.mcp_server --port 8080
```

**MCP Tools exposed (9)**:
- `multiagent_dispatch` — full multi-agent collaboration on a task (WRITE)
- `multiagent_quick` — quick dispatch with compact output (WRITE)
- `multiagent_roles` — list all agent roles (READ_ONLY)
- `multiagent_status` — version, backends, capabilities (READ_ONLY)
- `multiagent_analyze` — dry-run task intent analysis (READ_ONLY)
- `multiagent_shutdown` — free dispatcher resources (ADMIN)
- `codegraph_explore` — query the code knowledge graph (READ_ONLY)
- `codegraph_status` — graph build status and stats (READ_ONLY)
- `codegraph_refresh` — incremental/full graph rebuild (WRITE)

Full integration guide — install, client config JSON (Cursor / Claude Desktop), RBAC / fail-closed behavior: [docs/integrations/MCP.md](docs/integrations/MCP.md)

**When to use Method 3**:
- IDE integration (TRAE, Claude Desktop, Cursor) via MCP protocol
- External tool orchestration through standardized MCP interface
- Programmatic access from MCP-compatible clients

### Method 4: Interactive Web Dashboard (V3.6.0+)

```bash
# Start Streamlit dashboard with authentication
streamlit run scripts/dashboard.py

# Open http://localhost:8501
# Login with default dev credentials — see INSTALL.md "Default credentials" section
```

**Features**:
- Real-time lifecycle phase monitoring
- CLI command mapping visualization
- Gate status tracking
- Performance metrics display
- Role-based access control (Admin/Operator/Viewer)

**When to use Method 4**:
- Visual monitoring and management needed
- Team collaboration with multiple users
- Non-technical stakeholders need access

### Method 5: REST API Server (V3.6.0+)

```bash
# Install API dependencies
pip install -e ".[api]"

# Start FastAPI server
uvicorn scripts.api_server:app --host 0.0.0.0 --port 8000 --reload

# Access Swagger UI: http://localhost:8000/docs
```

**Key Endpoints**:
```bash
# Lifecycle management
curl http://localhost:8000/api/v1/lifecycle/phases | jq
curl http://localhost:8000/api/v1/lifecycle/status | jq

# Metrics & monitoring
curl http://localhost:8000/api/v1/metrics/current | jq
curl http://localhost:8000/api/v1/gates/status | jq

# Health check
curl http://localhost:8000/api/v1/health | jq
```

**When to use Method 5**:
- Integration with external systems (CI/CD, monitoring)
- Programmatic access to DevSquad capabilities
- Building custom UIs on top of DevSquad

### Method 6: Python API Variants

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher, quick_collaborate

disp = MultiAgentDispatcher()

# Variant A: Specify Roles
result = disp.dispatch("Design user auth system", roles=["architect", "tester"])
print(result.to_markdown())

# Variant B: Dry-Run Simulation (Analyze only, no execution)
result = disp.dispatch("Test task", dry_run=True)
print(result.summary)

# Variant C: Convenience Function (One-liner)
result = quick_collaborate("Help me design a microservice architecture")
print(result.to_markdown())

disp.shutdown()
```

**When to use Method 6**:
- Need fine-grained role control (Variant A)
- Analysis-only mode without execution (Variant B)
- Quick one-liner for simple tasks (Variant C)

### Method 7: One-Click Startup Script (V3.9.2+)

```bash
# One-click startup — runs 4 phases: env check → DB init → frontend build → service start
./scripts/start.sh

# Launch the API and Streamlit dashboard together
./scripts/start.sh --dashboard

# Override API port
DEVSQUAD_API_PORT=9000 ./scripts/start.sh

# Show help
./scripts/start.sh --help
```

`start.sh` is the unified entry point introduced in V3.9.2 (P0-2). It validates the environment, initializes the database, builds the frontend, and starts the service in one command. Use `requirements.lock` alongside it for reproducible builds (`pip install -r requirements.lock`).

---

## Role System (7 Core Roles)

| Role ID | Name | Trigger Keywords | Core Responsibility |
|---------|------|------------------|---------------------|
| `architect` | Architect | architecture, design, selection, performance, module, interface, data architecture | System architecture, tech selection, performance/security/data architecture |
| `product-manager` | Product Manager | requirements, PRD, user story, competitor, acceptance | Requirements analysis, PRD writing, product planning |
| `security` | Security Expert | security, vulnerability, audit, threat, encryption, OWASP | Threat modeling, vulnerability audit, compliance, security review |
| `tester` | Test Expert | test, quality, acceptance, automation, defect | Test strategy, case design, quality assurance |
| `solo-coder` | Coder | implementation, development, code, fix, optimize, refactor | Feature dev, code review, performance optimization, refactoring |
| `devops` | DevOps Engineer | CI/CD, deploy, monitor, Docker, Kubernetes, infrastructure | CI/CD pipeline, containerization, monitoring, infrastructure |
| `ui-designer` | UI Designer | UI, interface, frontend, visual, prototype, accessibility | UI design, interaction design, prototyping, accessibility |

**CLI short IDs**: `arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`

**Auto-match rule**: When roles are not specified, the system automatically matches the best role combination based on task keywords.

---

## Anti-Ghost Principle (防幽灵功能保证)

> **Ghost feature** = a module that exists in docs/tests but is never actually activated in the dispatch pipeline. DevSquad treats ghost features as a critical quality defect.

Every module shipped in DevSquad **must** prove it is wired into the real execution path — not just present on disk. The anti-ghost discipline enforces this through four mechanisms:

1. **Call counters** (`_call_counter`): Each enhancement module increments a module-level counter when its public API is invoked. CI runs `check_module_activation.py` to assert `_call_counter > 0` — a module that was never called by the dispatch pipeline fails CI.
2. **Natural dispatch integration**: New modules are activated through existing pipeline hooks (post-worker hooks, gate engines, dispatcher `_activate_v4XX_modules()`), never through bypass paths that would skip real execution.
3. **Three-layer test coverage**: Unit tests + integration tests (asserting pipeline integration) + E2E tests (asserting end-to-end activation) + red-team tests. A module with only unit tests but no integration/E2E evidence is suspect.
4. **User-visible output**: Every activated module must render a section in the Markdown dispatch report (`to_markdown()` / `export_markdown()`). If the user cannot see the module's contribution in the report, it is treated as a ghost.

**Lesson**: "文档有 ≠ 代码有 ≠ 功能可用" — documented ≠ implemented ≠ activated. The anti-ghost principle closes this gap with counters, integration, E2E, and user-visible output.

---

## Language Rules

- Auto-detect user language (Chinese/English/Japanese)
- All output uses same language as user
- Role name mapping: 架构师→Architect, PM→Product Manager, etc.
