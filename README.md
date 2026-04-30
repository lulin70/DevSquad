# DevSquad — Multi-Role AI Task Orchestrator

<p align="center">
  <strong>One task → Multi-role AI collaboration → One conclusion</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-129%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.3.0-2026--04--27-orange" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
</p>

---

## What is DevSquad?

DevSquad transforms a **single AI task into a multi-role AI collaboration**. It automatically dispatches your task to the right combination of expert roles — architect, product manager, coder, tester, security reviewer, DevOps — orchestrates their parallel collaboration through a shared workspace, resolves conflicts via weighted consensus voting, and delivers a unified structured report.

```
You: "Design a microservices e-commerce backend"
         │
         ▼
┌─────────────────┐
│  InputValidator   ──→ Security check (XSS, SQL injection, prompt injection)
└────────┬────────┘
         ▼
┌─────────────────┐
│  RoleMatcher     ──→ Auto-match: architect + devops + security
└────────┬────────┘
         ▼
┌──────────┬──────────┬──────────┐
│ Architect │  DevOps   │ Security │   ← ThreadPoolExecutor parallel execution
│(Design)   │(Infra)   │(Threat)  │
└────┬──────┴────┬─────┴────┬────┘
     └────────────┼───────────┘
                  ▼
      ┌──────────────────┐
      │    Scratchpad     │ ← Shared blackboard (real-time sync)
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │ Consensus Engine  │ ← Weighted vote + veto + escalation
      └────────┬─────────┘
               ▼
      ┌──────────────────┐
      │ Structured Report │ ← Findings + Action Items (H/M/L)
      └──────────────────┘
```

## Quick Start

### Install

```bash
git clone https://github.com/lulin70/DevSquad.git
cd DevSquad

# Option A: Run directly (no install needed)
python3 scripts/cli.py dispatch -t "Design user authentication system"

# Option B: pip install
pip install -e .
devsquad dispatch -t "Design user authentication system"
```

### 3 Ways to Use

**1. CLI (Recommended)**

```bash
# Mock mode (default) — no API key needed
python3 scripts/cli.py dispatch -t "Design user authentication system"

# Real AI output — set environment variables first
export OPENAI_API_KEY="sk-..."
export OPENAI_BASE_URL="https://api.openai.com/v1"   # optional
export OPENAI_MODEL="gpt-4"                            # optional
python3 scripts/cli.py dispatch -t "Design auth system" --backend openai

# Specify roles (short IDs: arch/pm/test/coder/ui/infra/sec)
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec --backend openai

# Stream output in real-time
python3 scripts/cli.py dispatch -t "Design auth system" -r arch --backend openai --stream

# Other commands
python3 scripts/cli.py status          # System status
python3 scripts/cli.py roles           # List available roles
python3 scripts/cli.py --version       # Show version (3.3.0)
```

**2. Python API**

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock mode (default)
disp = MultiAgentDispatcher()
result = disp.dispatch("Design REST API for user management")
print(result.to_markdown())
disp.shutdown()

# With LLM backend
from scripts.collaboration.llm_backend import create_backend
backend = create_backend("openai", api_key="sk-...", base_url="https://api.openai.com/v1")
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("Design auth system", roles=["architect", "security"])
print(result.summary)
disp.shutdown()
```

**3. MCP Server (for Cursor / any MCP client)**

```bash
pip install mcp
python3 scripts/mcp_server.py              # stdio mode
python3 scripts/mcp_server.py --port 8080  # SSE mode
```

Exposes 6 tools: `multiagent_dispatch`, `multiagent_quick`, `multiagent_roles`,
`multiagent_status`, `multiagent_analyze`, `multiagent_shutdown`.

## 7 Core Roles

| Role | CLI ID | Aliases | Weight | Best For |
|------|--------|---------|--------|----------|
| Architect | `arch` | `architect` | 1.5 | System design, tech stack, performance/security architecture |
| Product Manager | `pm` | `product-manager` | 1.2 | Requirements, user stories, acceptance criteria |
| Security Expert | `sec` | `security` | 1.1 | Threat modeling, vulnerability audit, compliance |
| Tester | `test` | `tester`, `qa` | 1.0 | Test strategy, quality assurance, edge cases |
| Coder | `coder` | `solo-coder`, `dev` | 1.0 | Implementation, code review, performance optimization |
| DevOps | `infra` | `devops` | 1.0 | CI/CD, containerization, monitoring, infrastructure |
| UI Designer | `ui` | `ui-designer` | 0.9 | UX flow, interaction design, accessibility |

**Auto-match**: If no roles specified, the dispatcher automatically matches based on task keywords.

## Architecture

DevSquad is built on a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│                    CLI / MCP / API               │  Entry Points
├─────────────────────────────────────────────────┤
│              MultiAgentDispatcher                │  Orchestration
│  ┌────────────┬──────────────┬────────────────┐ │
│  │RoleMatcher │ReportFormatter│InputValidator  │ │  Extracted Components
│  └────────────┴──────────────┴────────────────┘ │
├─────────────────────────────────────────────────┤
│                 Coordinator                      │  Task Planning
│  ┌──────────┬───────────┬────────────────────┐  │
│  │ Scratchpad│ Consensus │  BatchScheduler    │  │  Collaboration
│  └──────────┴───────────┴────────────────────┘  │
├─────────────────────────────────────────────────┤
│              Worker (per role)                   │  Execution
│  ┌────────────────────────────────────────────┐ │
│  │ PromptAssembler → LLMBackend → Output      │ │
│  └────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────┤
│  LLMBackend: Mock | OpenAI | Anthropic          │  LLM Layer
├─────────────────────────────────────────────────┤
│  CheckpointManager | WorkflowEngine | ...       │  Infrastructure
└─────────────────────────────────────────────────┘
```

## Key Features

### Security
- **InputValidator**: XSS, SQL injection, command injection, HTML injection detection
- **Prompt Injection Protection**: 16 patterns (ignore previous instructions, jailbreak, DAN mode, system prompt extraction, etc.)
- **API Key Safety**: Environment variables only, never CLI arguments or logs
- **PermissionGuard**: 4-level safety gate (PLAN → DEFAULT → AUTO → BYPASS)

### Performance
- **ThreadPoolExecutor**: Real parallel execution for multi-role dispatch
- **LLM Cache**: TTL-based LRU cache with disk persistence (60-80% cost reduction)
- **LLM Retry**: Exponential backoff + circuit breaker + multi-backend fallback
- **Streaming Output**: Real-time chunk-by-chunk LLM output via `--stream`

### Reliability
- **CheckpointManager**: SHA256 integrity, handoff documents, auto-cleanup
- **WorkflowEngine**: Task-to-workflow auto-split, step execution, resume from checkpoint
- **TaskCompletionChecker**: DispatchResult/ScheduleResult completion tracking
- **ConsensusEngine**: Weighted voting with veto power and human escalation

### Developer Experience
- **Configuration File**: `~/.devsquad.yaml` with env var overrides
- **Docker Support**: `docker build -t devsquad . && docker run devsquad dispatch -t "task"`
- **GitHub Actions CI**: Python 3.9-3.12 matrix testing
- **pip installable**: `pip install -e .` with optional dependencies

## Module Reference

| Module | File | Purpose |
|--------|------|---------|
| **MultiAgentDispatcher** | `dispatcher.py` | Unified entry point |
| **Coordinator** | `coordinator.py` | Global orchestration: plan → assign → execute → collect |
| **Worker** | `worker.py` | Role executor with LLM backend integration |
| **Scratchpad** | `scratchpad.py` | Shared blackboard for inter-worker communication |
| **ConsensusEngine** | `consensus.py` | Weighted voting + veto + escalation |
| **RoleMatcher** | `role_matcher.py` | Keyword-based role matching with alias resolution |
| **ReportFormatter** | `report_formatter.py` | Structured/compact/detailed report generation |
| **InputValidator** | `input_validator.py` | Security validation + prompt injection detection |
| **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM-powered semantic role matching |
| **CheckpointManager** | `checkpoint_manager.py` | State persistence + handoff documents |
| **WorkflowEngine** | `workflow_engine.py` | Task-to-workflow auto-split + step execution |
| **TaskCompletionChecker** | `task_completion_checker.py` | Completion tracking + progress reporting |
| **CodeMapGenerator** | `code_map_generator.py` | Python AST-based code structure analysis |
| **DualLayerContext** | `dual_layer_context.py` | Project-level + task-level context management |
| **SkillRegistry** | `skill_registry.py` | Reusable skill registration + discovery |
| **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic with streaming support |
| **ConfigManager** | `config_loader.py` | YAML config + env var overrides |

## Configuration

Create `~/.devsquad.yaml`:

```yaml
devsquad:
  backend: openai
  base_url: https://api.openai.com/v1
  model: gpt-4
  timeout: 120
  output_format: structured
  strict_validation: false
  checkpoint_enabled: true
  cache_enabled: true
  log_level: WARNING
```

Or use environment variables (higher priority):

```bash
export DEVSQUAD_LLM_BACKEND=openai
export DEVSQUAD_BASE_URL=https://api.openai.com/v1
export DEVSQUAD_MODEL=gpt-4
export OPENAI_API_KEY=sk-...
```

## Environment Variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `OPENAI_API_KEY` | OpenAI API key | None (required for OpenAI backend) |
| `OPENAI_BASE_URL` | OpenAI-compatible base URL | None |
| `OPENAI_MODEL` | Model name | `gpt-4` |
| `ANTHROPIC_API_KEY` | Anthropic API key | None (required for Anthropic backend) |
| `ANTHROPIC_MODEL` | Model name | `claude-sonnet-4-20250514` |
| `DEVSQUAD_LLM_BACKEND` | Default backend type | `mock` |
| `DEVSQUAD_LOG_LEVEL` | Logging level | `WARNING` |

## Running Tests

```bash
# Core tests (129 tests)
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py -v

# Quick smoke test
python3 scripts/cli.py --version    # 3.3.0
python3 scripts/cli.py status       # System ready
python3 scripts/cli.py roles        # List 7 roles
```

## Documentation

| Document | Description |
|----------|-------------|
| [INSTALL.md](INSTALL.md) | Installation guide (Unix + Windows) |
| [EXAMPLES.md](EXAMPLES.md) | Real-world usage examples |
| [SKILL.md](SKILL.md) | Skill manual (EN/CN/JP) |
| [CLAUDE.md](CLAUDE.md) | Claude Code project instructions |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [README-CN.md](README-CN.md) | 中文说明 |
| [README-JP.md](README-JP.md) | 日本語説明 |

## Cross-Platform Compatibility

| Platform | Integration Method | Status |
|----------|-------------------|--------|
| **Trae IDE** | `skill-manifest.yaml` native skill | ✅ Primary |
| **Claude Code** | `CLAUDE.md` + `.claude/skills/` custom skill | ✅ Supported |
| **Cursor / MCP clients** | MCP Server (`scripts/mcp_server.py`, 6 tools) | ✅ Supported |
| **Terminal / Any IDE** | CLI (`scripts/cli.py`) or Python import | ✅ Universal |
| **Docker** | `docker build -t devsquad .` | ✅ Supported |

## Version History

| Date | Version | Highlights |
|------|---------|-----------|
| 2026-04-27 | **V3.3.0** | Real LLM backend (OpenAI/Anthropic/Mock), ThreadPoolExecutor parallel execution, InputValidator + prompt injection protection, CheckpointManager, WorkflowEngine, TaskCompletionChecker, AISemanticMatcher, streaming output, Docker, GitHub Actions CI, config file, CodeMapGenerator, DualLayerContext, SkillRegistry, CarryMem integration, 129 unit tests |
| 2026-04-17 | V3.2 | E2E Demo, MCE Adapter, Dispatcher UX |
| 2026-04-16 | V3.0 | Complete redesign — Coordinator/Worker/Scratchpad architecture |

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

| Link | URL |
|------|-----|
| **GitHub (This Repo)** | https://github.com/lulin70/DevSquad |
| **Original / Upstream** | https://github.com/weiransoft/TraeMultiAgentSkill |
