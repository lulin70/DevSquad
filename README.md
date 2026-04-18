# DevSquad — Multi-Agent Software Development Team

<p align="center">
  <strong>Assemble an AI-powered software development squad on demand.</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-41%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.3-2026--04--17-orange" />
</p>

---

## What is DevSquad?

DevSquad transforms a **single AI coding assistant into a specialized multi-role development team**. Instead of one AI handling your entire task, it automatically dispatches to the right combination of expert roles — architect, product manager, coder, tester, security reviewer, and more — then orchestrates their parallel collaboration through a shared workspace, resolves conflicts via consensus voting, and delivers a unified structured report.

**Think of it as assembling a virtual dev team on demand, powered by AI agents that collaborate like real engineers.**

```
You: "Design a microservices e-commerce backend"
         │
         ▼
┌─────────────────┐
│  Intent Analysis  ──→ Auto-match: architect + devops + security
└────────┬────────┘
         ▼
┌──────────┬──────────┬──────────┐
│ Architect │  DevOps   │ Security │
│(Design)   │(Infra)   │(Threat)  │
└────┬──────┴────┬─────┴────┬────┘
     └────────────┼───────────┘
                  ▼
      ┌──────────────────┐
      │    Scratchpad     │ ← Shared blackboard
      │ (Real-time sync) │
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │ Consensus Engine  │ ← Weighted vote + veto
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │ Structured Report │ ← Findings + Action Items (H/M/L)
      └──────────────────┘
```

## Quick Start

### Prerequisites

- **Python 3.9+** (pure Python, no compiled dependencies)
- **OS**: macOS / Linux / **Windows 10+**
- No external dependencies required (all integrations use graceful degradation)

See [**INSTALL.md**](INSTALL.md) for detailed setup instructions including Windows.

### 3 Ways to Use

**Method 1: CLI (Recommended)**

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

python3 scripts/cli.py dispatch -t "Design user authentication system"
python3 scripts/cli.py status
python3 scripts/cli.py roles
```

**Method 2: Python API**

```python
import sys
sys.path.insert(0, '/path/to/DevSquad')
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design REST API for user management")
print(result.to_markdown())
disp.shutdown()
```

**Method 3: Quick Dispatch (3 output formats)**

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()

# Structured report (default table format)
result = disp.quick_dispatch(task, output_format="structured")

# Compact (one-line per role)
result = disp.quick_dispatch(task, output_format="compact")

# Detailed (full findings + action items)
result = disp.quick_dispatch(task, output_format="detailed",
                              include_action_items=True)

disp.shutdown()
```

## 10 Built-in Roles

| Role | Best For |
|------|----------|
| `architect` | System design, tech stack, API design |
| `pm` | Requirements, user stories, acceptance criteria |
| `coder` | Implementation, code generation, refactoring |
| `tester` | Test strategy, edge cases, coverage gaps |
| `ui` | UX flow, interaction design, accessibility |
| `devops` | CI/CD pipeline, deployment, monitoring |
| `security` | Threat modeling, vulnerability audit |
| `data` | Data modeling, analytics, migrations |
| `reviewer` | Code review, best practices |
| `optimizer` | Performance optimization, caching |

**Auto-match**: If no roles specified, the dispatcher automatically matches based on task intent.

## 16 Core Modules

| Module | Purpose |
|--------|---------|
| **MultiAgentDispatcher** | Unified entry point — one call does everything |
| **Coordinator** | Global orchestration: decompose → assign → collect → resolve |
| **Scratchpad** | Shared blackboard for inter-worker real-time communication |
| **Worker** | Role executor — independent instance per role |
| **ConsensusEngine** | Weighted voting + veto power + human escalation |
| **BatchScheduler** | Parallel/sequential hybrid with auto safety detection |
| **ContextCompressor** | 4-level compression prevents context overflow |
| **PermissionGuard** | 4-level safety gate (PLAN → DEFAULT → AUTO → BYPASS) |
| **Skillifier** | Learns from successful patterns, auto-generates new skills |
| **WarmupManager** | 3-layer startup preloading (cold-start < 300ms) |
| **MemoryBridge** | Cross-session memory (7 types, TF-IDF, forgetting curve) |
| **MCEAdapter** | Memory Classification Engine integration (v0.4, tenant-aware) |
| **WorkBuddyClawSource** | External knowledge bridge (INDEX search, AI news feed) |
| **PromptAssembler** | Dynamic prompt construction (3 variants × 5 styles) |
| **PromptVariantGenerator** | Closed-loop A/B testing for prompt optimization |
| **TestQualityGuard** | Automated test quality audit (API validation, coverage) |

## Cross-Platform Compatibility

DevSquad works natively across multiple AI coding environments:

| Platform | Integration Method | Status |
|----------|-------------------|--------|
| **Trae IDE** | `skill-manifest.yaml` native skill | ✅ Primary |
| **Claude Code** | `CLAUDE.md` + `.claude/skills/` custom skill | ✅ Supported |
| **OpenClaw** | MCP Server (`scripts/mcp_server.py`, 6 tools) | ✅ Supported |
| **Terminal / Any IDE** | CLI (`scripts/cli.py`) or Python import | ✅ Universal |

### MCP Server (for OpenClaw / Cursor / any MCP client)

```bash
pip install mcp          # optional
python3 scripts/mcp_server.py              # stdio mode
python3 scripts/mcp_server.py --port 8080  # SSE mode
```

Exposes 6 tools: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`,
`multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`.

## External Integrations

| Component | Status | Fallback |
|-----------|--------|----------|
| **MCE v0.4** (Memory Classification Engine) | Optional tenant/permission support | Graceful degrade if unavailable |
| **WorkBuddy Claw** | Read-only bridge to external knowledge base | Skip if path not found |

All integrations are optional — DevSquad works fully standalone.

## Running Tests

```bash
cd /path/to/DevSquad

# Core collaboration tests
python3 -m pytest scripts/collaboration/ -v
# Expected: ~41 test cases, all passing

# Quick status check
python3 scripts/cli.py status
# Expected: {"name": "DevSquad", "status": "ready", ...}

# Dry-run verification
python3 scripts/cli.py dispatch -t "test" --dry-run
```

## Project Structure

```
DevSquad/
├── scripts/
│   ├── cli.py                    # Primary CLI entry point
│   ├── mcp_server.py             # MCP server (OpenClaw/Cursor)
│   ├── trae_agent.py             # Legacy wrapper (/dss command)
│   ├── trae_agent_dispatch_v2.py # Core dispatcher (legacy)
│   └── collaboration/            # ★ 16 core modules
│       ├── dispatcher.py         # MultiAgentDispatcher
│       ├── coordinator.py        # Global orchestrator
│       ├── scratchpad.py         # Shared blackboard
│       ├── worker.py             # Role executor
│       ├── consensus.py          # Weighted voting + veto
│       ├── memory_bridge.py      # Cross-session memory
│       ├── mce_adapter.py        # MCE v0.4 adapter
│       └── *_test.py             # Test suites (~41 cases)
├── SKILL.md                      # English skill manual
├── SKILL-CN.md                   # Chinese skill manual
├── SKILL-JP.md                   # Japanese skill manual
├── CLAUDE.md                     # Claude Code project instructions
├── INSTALL.md                    # Installation guide (Unix + Windows)
├── CHANGELOG.md                  # Complete version history
└── docs/                         # Architecture specs, plans
```

## Philosophy

> **"One AI is a tool. Ten AI collaborators are a team."**

Software development is inherently multi-disciplinary. No single perspective can match the quality of a well-coordinated team with diverse expertise. DevSquad makes that team available on demand, in seconds, for any software task.

## Version History

| Date | Version | Highlights |
|------|---------|-----------|
| 2026-04-17 | **V3.3** | Rebrand → DevSquad, WorkBuddy Claw, cross-platform (CLI/MCP/ClaudeCode), MAS→DSS |
| 2026-04-17 | V3.2 | E2E Demo, MCE Adapter, Dispatcher UX, Delivery Workflow Iron Rule |
| 2026-04-16 | V3.1 | Prompt Optimization System (A/B variant testing) |
| 2026-04-16 | V3.0 | Complete redesign — Coordinator/Worker/Scratchpad architecture |
| Mar 2026 | V2.x | Dual-layer context, Vibe Coding, MCE integration, code map visualization |

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

| Link | URL |
|------|-----|
| **GitHub (This Repo)** | https://github.com/lulin70/DevSquad |
| **Original / Upstream** | https://github.com/weiransoft/DevSquad |
| **Installation** | See [INSTALL.md](INSTALL.md) |
| **Skill Manual** | [SKILL.md](SKILL.md) / [SKILL-CN.md](SKILL-CN.md) / [SKILL-JP.md](SKILL-JP.md) |
| **Chinese Readme** | [README-CN.md](README-CN.md) |
| **Japanese Readme** | [README-JP.md](README-JP.md) |

## Usage Examples

### Scenario 1: Architecture Design Session

```
User: "Design a microservices e-commerce backend"
→ DevSquad auto-matches: architect + devops + security
→ Output: Tech stack recommendation + service boundaries + security model
```

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design a microservices e-commerce backend")
print(result.to_markdown())
# → Structured report with findings, conflicts, and H/M/L action items
disp.shutdown()
```

### Scenario 2: Code Review with Security Focus

```python
# Target specific roles for a focused review
result = disp.quick_dispatch(
    "Review auth.py for security vulnerabilities",
    output_format="detailed",
    include_action_items=True,
)
# → Security findings + test gaps + improvement suggestions
```

### Scenario 3: Full-Stack Analysis

```python
# Auto-match mode — let DevSquad pick the right team
result = disp.dispatch("Analyze our project's production readiness")
# → Multi-role assessment with consensus decision
```

### Scenario 4: Quick Compact Output (for terminal/piping)

```bash
python3 scripts/cli.py quick -t "Optimize database queries" -f compact
# → One-line summary per role, machine-friendly
```

### Scenario 5: JSON Output for Integration

```bash
python3 scripts/cli.py dispatch -t "Analyze API surface" -f json
# → Parsed by downstream tools, CI/CD pipelines, or dashboards
```
