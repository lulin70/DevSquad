# DevSquad — Multi-Role AI Task Orchestrator

<p align="center">
  <strong>One task → Multi-role AI collaboration → One conclusion</strong>
</p>

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.9+-blue?logo=python&logoColor=white" />
  <img alt="License" src="https://img.shields.io/badge/License-MIT-green" />
  <img alt="Tests" src="https://img.shields.io/badge/Tests-700%2B%20passing-brightgreen" />
  <img alt="Version" src="https://img.shields.io/badge/V3.5.0--C-2026--05--03-orange" />
  <img alt="CI" src="https://img.shields.io/badge/CI-GitHub_Actions-blue?logo=githubactions" />
  <img alt="Architecture" src="https://img.shields.io/badge/Architecture-Plan_C_Layered-blueviolet" />
</p>

---

## 🎯 What's New in V3.5.0-C (Plan C Layered Architecture)

**Unified Lifecycle Architecture** - Resolves CLI 6 commands vs 11-phase lifecycle conflict:

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

**Key Components:**
- ✅ **LifecycleProtocol** - Abstract interface for unified lifecycle management
- ✅ **UnifiedGateEngine** - Integrates VerificationGate + Phase transition gates
- ✅ **ShortcutLifecycleAdapter** - Maps CLI commands to 11-phase segments
- ✅ **Enhanced CheckpointManager** - Auto save/restore lifecycle state across sessions
- ✅ **27 new tests** - All passing (Plan C architecture validation)

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
# Zero dependencies, ready to use, config file features degraded
python3 scripts/cli.py dispatch -t "Design user authentication system"

# Option B: pip install (Recommended)
# Full functionality, including config file support (pyyaml auto-installed)
pip install -e .
devsquad dispatch -t "Design user authentication system"
```

> **Which option?** Option A is for quick trials — no dependencies needed, but `~/.devsquad.yaml` config files won't be loaded. Option B installs DevSquad as a package with all features enabled, including YAML config, `devsquad` CLI command, and optional integrations (CarryMem, OpenAI, Anthropic).

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
python3 scripts/cli.py --version       # Show version (3.4.0)
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

## Architecture Overview (45 Core Modules)

DevSquad is built on a layered architecture with clear separation of concerns:

```
┌─────────────────────────────────────────────────┐
│                    CLI / MCP / API               │  Entry Points
├─────────────────────────────────────────────────┤
│              MultiAgentDispatcher                │  Orchestration
│  ┌────────────┬──────────────┬────────────────┐ │
│  │RoleMatcher │ReportFormatter│InputValidator  │ │  Extracted Components
│  └────────────┴──────────────┴────────────────┘ │
│  ┌────────────────────────────────────────────┐ │
│  │ RuleCollector (NL Rule Intercept)          │ │  Rule Collection
│  └────────────────────────────────────────────┘ │
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

## What's New in V3.4.0 🆕

### AgentBriefing System
Context-aware task briefing that helps agents understand project history and make informed decisions:

```python
from scripts.collaboration.agent_briefing import get_agent_briefing

# Create briefing for agent
briefing = get_agent_briefing("architect")
briefing.update_briefing("capabilities", "System design")
briefing.update_briefing("constraints", "Must use Python 3.8+")

# Generate briefing for task
content = briefing.generate_briefing(
    task="Design authentication system",
    context={"priority": "high"}
)
```

**Features**:
- Historical pattern recognition
- Priority-based information filtering
- JSON persistence
- Multi-section management

### ConfidenceScore System
Automatic response quality assessment with 5-factor analysis:

```python
from scripts.collaboration.confidence_score import get_confidence_scorer

scorer = get_confidence_scorer()
score = scorer.calculate_confidence(
    prompt="Design a REST API",
    response=llm_response,
    metadata={"model": "gpt-4", "temperature": 0.7}
)

print(f"Confidence: {score.overall_score:.2f}")  # 0.89
print(f"Level: {score.level.value}")             # "high"
```

**5 Confidence Factors** (weighted):
1. **Completeness** (25%): Response length, truncation detection
2. **Certainty** (25%): Uncertainty phrases, hedging words
3. **Specificity** (20%): Numbers, code, examples, lists
4. **Consistency** (15%): Contradictions, self-corrections
5. **Model Quality** (15%): Model tier, temperature, token count

### EnhancedWorker
Integrated worker with automatic quality assurance:

```python
from scripts.collaboration.enhanced_worker import create_enhanced_worker

worker = create_enhanced_worker(
    worker_id="arch-001",
    role_id="architect",
    role_prompt="You are a system architect...",
    scratchpad=scratchpad,
    confidence_threshold=0.7,  # Auto-retry if below threshold
    enable_briefing=True,
    enable_confidence=True,
)

result = worker.execute(task)
print(f"Confidence: {result.output['confidence_score']}")
```

**Features**:
- Automatic briefing generation
- Automatic confidence evaluation
- Smart retry mechanism (low confidence)
- Quality gates
- Auto-flagging for review

### Natural Language Rule Collection
Automatically detect and store user rules from natural language input:

```python
# User says: "记住规则：写代码时必须加注释"
# DevSquad automatically:
# 1. Detects rule-storing intent
# 2. Extracts: trigger="写代码时", action="必须加注释", type="always"
# 3. Sanitizes content (removes dangerous patterns)
# 4. Stores via CarryMem or local JSON fallback

# List stored rules
# User says: "列出规则" → Returns all stored rules

# Delete a rule
# User says: "删除规则 RULE-LOCAL-abc123"
```

**Pipeline**: User Input → IntentDetector → RuleExtractor → RuleSanitizer → RuleStorage (CarryMem + local JSON)

**Features**:
- 11 intent patterns (Chinese + English)
- 4 rule types: always / avoid / prefer / forbid
- Prompt injection protection in rule content
- CarryMem primary + local JSON fallback storage
- Automatic rule injection into Worker prompts

See [Integration Guide](docs/guides/agent_briefing_confidence_integration.md) for detailed usage.

---

## Key Features

### Security
- **InputValidator**: XSS, SQL injection, command injection, HTML injection detection
- **Prompt Injection Protection**: 21+ patterns (ignore previous instructions, jailbreak, DAN mode, system prompt extraction, etc.)
- **API Key Safety**: Environment variables only, never CLI arguments or logs
- **PermissionGuard**: 4-level safety gate (PLAN → DEFAULT → AUTO → BYPASS)

### Performance
- **ThreadPoolExecutor**: Real parallel execution for multi-role dispatch
- **LLM Cache**: TTL-based LRU cache with disk persistence (60-80% cost reduction)
- **LLM Retry**: Exponential backoff + circuit breaker + multi-backend fallback
- **Streaming Output**: Real-time chunk-by-chunk LLM output via `--stream`

### Reliability
- **CheckpointManager**: SHA256 integrity, handoff documents, auto-cleanup
- **WorkflowEngine**: Task-to-workflow auto-split, step execution, resume from checkpoint, **11-phase lifecycle templates** (full/backend/frontend/internal_tool/minimal), requirement change management
- **TaskCompletionChecker**: DispatchResult/ScheduleResult completion tracking
- **ConsensusEngine**: Weighted voting with veto power and human escalation

### Project Lifecycle (11-Phase Model)

DevSquad V3.4.0 defines an **11-phase (4 optional)** project lifecycle with clear roles, dependencies, and gate conditions:

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

| Template | Phases | Use Case |
|----------|--------|----------|
| `full` | P1-P11 | Complete project |
| `backend` | No P5 | Backend services |
| `frontend` | No P4,P6 | Frontend applications |
| `internal_tool` | No P4,P5,P6,P11 | Internal tools |
| `minimal` | P1,P3,P7,P8,P9 | Minimum set |

See [GUIDE.md](GUIDE.md) §4 for full lifecycle details with gate conditions and requirement change process.

### Developer Experience
- **Configuration File**: `.devsquad.yaml` in project root with env var overrides
- **Quality Control Injection**: Auto-inject QC rules (hallucination prevention, overconfidence check, security guard, RACI protocol) into Worker prompts based on `.devsquad.yaml` config
- **Docker Support**: `docker build -t devsquad . && docker run devsquad dispatch -t "task"`
- **GitHub Actions CI**: Python 3.9-3.12 matrix testing
- **pip installable**: `pip install -e .` with optional dependencies

## Module Reference (45 Modules)

| Module | File | Purpose |
|--------|------|---------|
| **MultiAgentDispatcher** | `dispatcher.py` | Unified entry point |
| **Coordinator** | `coordinator.py` | Global orchestration: plan → assign → execute → collect |
| **Worker** | `worker.py` | Role executor with LLM backend integration |
| **EnhancedWorker** | `enhanced_worker.py` | Worker with auto QA (briefing + confidence + retry + memory rules) |
| **Scratchpad** | `scratchpad.py` | Shared blackboard for inter-worker communication |
| **ConsensusEngine** | `consensus.py` | Weighted voting + veto + escalation |
| **RoleMatcher** | `role_matcher.py` | Keyword-based role matching with alias resolution |
| **ReportFormatter** | `report_formatter.py` | Structured/compact/detailed report generation |
| **InputValidator** | `input_validator.py` | Security validation + prompt injection detection |
| **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM-powered semantic role matching |
| **CheckpointManager** | `checkpoint_manager.py` | State persistence + handoff documents |
| **WorkflowEngine** | `workflow_engine.py` | Task-to-workflow auto-split + 11-phase lifecycle templates + requirement change |
| **TaskCompletionChecker** | `task_completion_checker.py` | Completion tracking + progress reporting |
| **CodeMapGenerator** | `code_map_generator.py` | Python AST-based code structure analysis |
| **DualLayerContext** | `dual_layer_context.py` | Project-level + task-level context management |
| **SkillRegistry** | `skill_registry.py` | Reusable skill registration + discovery |
| **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic with streaming support |
| **LLMCache** | `llm_cache.py` | TTL-based LRU cache with disk persistence |
| **LLMRetry** | `llm_retry.py` | Exponential backoff + circuit breaker |
| **ConfigManager** | `config_loader.py` | YAML config + env var overrides |
| **PromptAssembler** | `prompt_assembler.py` | Dynamic prompt assembly + QC rule injection |
| **AgentBriefing** | `agent_briefing.py` | Context-aware task briefing with priority filtering |
| **ConfidenceScorer** | `confidence_score.py` | 5-factor response quality assessment |
| **PerformanceMonitor** | `performance_monitor.py` | P95/P99 tracking + CPU/memory monitoring |
| **MCEAdapter** | `mce_adapter.py` | CarryMem integration adapter (optional dependency, supports match_rules + format_rules_as_prompt + add_rule) |
| **Protocols** | `protocols.py` | Interface definitions (CacheProvider, MemoryProvider, etc.) |
| **NullProviders** | `null_providers.py` | Graceful degradation providers |
| **PermissionGuard** | `permission_guard.py` | 4-level safety gate |
| **MemoryBridge** | `memory_bridge.py` | Cross-session memory |
| **BatchScheduler** | `batch_scheduler.py` | Batch task scheduling |
| **ContextCompressor** | `context_compressor.py` | Context compression for long tasks |
| **RoleTemplateMarket** | `role_template_market.py` | Role template sharing marketplace |
| **Skillifier** | `skillifier.py` | Auto skill learning from tasks |
| **UsageTracker** | `usage_tracker.py` | Token/cost tracking |
| **WarmupManager** | `warmup_manager.py` | Startup warmup optimization |
| **TestQualityGuard** | `test_quality_guard.py` | Test quality enforcement |
| **PromptVariantGenerator** | `prompt_variant_generator.py` | A/B prompt testing |
| **ConfigManager (YAML)** | `config_manager.py` | Project-level YAML config |
| **WorkBuddyClawSource** | `memory_bridge.py` | WorkBuddy read-only bridge |
| **Models** | `models.py` | Shared data models and type definitions |
| **LLMCacheAsync** | `llm_cache_async.py` | Async LLM cache for concurrent workloads |
| **LLMRetryAsync** | `llm_retry_async.py` | Async LLM retry with backoff |
| **IntegrationExample** | `integration_example.py` | DevSquad integration example code |
| **AsyncIntegrationExample** | `async_integration_example.py` | Async DevSquad integration example |

## Configuration

Create `.devsquad.yaml` in your project root:

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
  base_url: ""  # Set via LLM_BASE_URL env var
  model: ""     # Set via LLM_MODEL env var
  timeout: 120
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
# Core tests (537+ tests all passing)
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py \
  tests/ test_v35_integration.py \
  tests/test_anti_rationalization.py \
  tests/test_verification_gate.py \
  tests/test_intent_workflow_mapper.py \
  tests/test_cli_lifecycle.py -v

# Quick smoke test
python3 scripts/cli.py --version    # 3.4.1
python3 scripts/cli.py status       # System ready
python3 scripts/cli.py roles        # List 7 roles

# Lifecycle commands (NEW in v3.4.1)
python3 scripts/cli.py spec -t "User authentication system"
python3 scripts/cli.py build -t "Implement login API"
python3 scripts/cli.py test -t "Run all unit tests"
python3 scripts/cli.py review -t "Check PR #123"
python3 scripts/cli.py ship -t "Deploy to production"
```

## Documentation

| Document | Description |
|----------|-------------|
| [GUIDE.md](GUIDE.md) | Complete user guide (Chinese) |
| [GUIDE_EN.md](docs/i18n/GUIDE_EN.md) | Complete user guide (English) |
| [GUIDE_JP.md](docs/i18n/GUIDE_JP.md) | Complete user guide (Japanese) |
| [INSTALL.md](INSTALL.md) | Installation guide (Unix + Windows) |
| [EXAMPLES.md](EXAMPLES.md) | Real-world usage examples |
| [SKILL.md](SKILL.md) | Skill manual (EN/CN/JP) |
| [CLAUDE.md](CLAUDE.md) | Claude Code project instructions |
| [CHANGELOG.md](CHANGELOG.md) | Version history |
| [README-CN.md](docs/i18n/README_CN.md) | 中文说明 |
| [README-JP.md](docs/i18n/README_JP.md) | 日本語説明 |

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
| 2026-05-03 | **V3.4.1** | 🚀 Agent Skills Quality Framework (P0) — AntiRationalizationEngine + VerificationGate + IntentWorkflowMapper + CLI Lifecycle Commands (spec/plan/build/test/review/ship) + 167 new tests + Google Agent Skills integration + 49 core modules |
| 2026-05-02 | **V3.4.0** | 🆕 11-Phase Project Lifecycle (full/backend/frontend/internal_tool/minimal templates), requirement change management, gate mechanism with gap reporting, 560+ tests passing, WorkflowEngine lifecycle support |
| 2026-05-01 | V3.4.0 | AgentBriefing (context-aware task briefing), ConfidenceScore (5-factor quality assessment), EnhancedWorker (auto quality assurance with retry + memory_provider rule injection), Protocol interface system (match_rules/format_rules_as_prompt), CarryMem v0.2.8+ integration, comprehensive documentation |
| 2026-04-27 | V3.4.0 | Real LLM backend (OpenAI/Anthropic/Mock), ThreadPoolExecutor parallel execution, InputValidator + prompt injection protection, CheckpointManager, WorkflowEngine, TaskCompletionChecker, AISemanticMatcher, streaming output, Docker, GitHub Actions CI, config file, CodeMapGenerator, DualLayerContext, SkillRegistry, CarryMem integration, 234 unit tests |
| 2026-04-17 | V3.2 | E2E Demo, MCE Adapter, Dispatcher UX |
| 2026-04-16 | V3.0 | Complete redesign — Coordinator/Worker/Scratchpad architecture |

## License

MIT License — see [LICENSE](LICENSE) for details.

## Links

| Link | URL |
|------|-----|
| **GitHub (This Repo)** | https://github.com/lulin70/DevSquad |
| **Original / Upstream** | https://github.com/weiransoft/TraeMultiAgentSkill |
