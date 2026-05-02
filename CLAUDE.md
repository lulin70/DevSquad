# DevSquad — Project Instructions for AI Coding Assistants

## Project Overview

**DevSquad** is a **V3.4.0 Multi-Role AI Task Orchestrator**. It transforms a single AI task into multi-role AI collaboration with 7 core roles. Based on the Coordinator/Worker/Scratchpad pattern with ThreadPoolExecutor parallel execution.

**44 Core Modules**: MultiAgentDispatcher, Coordinator, Scratchpad, Worker, EnhancedWorker, ConsensusEngine, BatchScheduler, ContextCompressor, PermissionGuard, Skillifier, WarmupManager, MemoryBridge, TestQualityGuard, PromptAssembler, PromptVariantGenerator, MCEAdapter, WorkBuddyClawSource, RoleMatcher, ReportFormatter, InputValidator, AISemanticMatcher, CheckpointManager, WorkflowEngine, TaskCompletionChecker, CodeMapGenerator, DualLayerContext, SkillRegistry, LLMBackend, LLMCache, LLMRetry, ConfigManager, Protocols, NullProviders, PerformanceMonitor, AgentBriefing, ConfidenceScorer, RoleTemplateMarket, UsageTracker, Models, ConfigManager(YAML), LLMCacheAsync, LLMRetryAsync, IntegrationExample, AsyncIntegrationExample.

**Test Coverage**: 370 tests (129 unit + 234 contract + 7 integration), all passing.
**Cross-Platform**: Trae IDE / Claude Code / Cursor / Any MCP client / CLI / Docker.

## Architecture

```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [ThreadPoolExecutor Parallel Workers] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

## Key Entry Points

### Primary API (Python)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

# Mock mode (default)
disp = MultiAgentDispatcher()
result = disp.dispatch("Design user authentication system")
print(result.to_markdown())
disp.shutdown()

# With LLM backend
from scripts.collaboration.llm_backend import create_backend
backend = create_backend("openai", api_key="sk-...", base_url="https://api.openai.com/v1")
disp = MultiAgentDispatcher(llm_backend=backend)
result = disp.dispatch("Design auth system", roles=["architect", "security"])
disp.shutdown()
```

### CLI Entry Point

```bash
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec
python3 scripts/cli.py dispatch -t "Design auth system" --backend openai --stream
python3 scripts/cli.py status
python3 scripts/cli.py roles
python3 scripts/cli.py --version  # 3.4.0
```

### Quick Dispatch

```python
result = disp.quick_dispatch(task, output_format="structured")  # structured / compact / detailed
result = disp.quick_dispatch(task, include_action_items=True)   # auto-generate H/M/L action items
```

## Directory Structure

```
DevSquad/
├── scripts/
│   ├── collaboration/          # ★ Core V3.5 modules (44 files)
│   │   ├── _version.py         # Version SSOT (3.4.0)
│   │   ├── dispatcher.py       # MultiAgentDispatcher — unified entry point
│   │   ├── coordinator.py      # Global orchestrator
│   │   ├── scratchpad.py       # Shared blackboard
│   │   ├── worker.py           # Role executor (with streaming)
│   │   ├── enhanced_worker.py  # Worker with provider injection (cache/retry/monitor/briefing/memory) + rule injection
│   │   ├── consensus.py        # Weighted voting + veto
│   │   ├── llm_backend.py      # Mock/OpenAI/Anthropic + streaming
│   │   ├── llm_cache.py        # TTL LRU cache + disk persistence
│   │   ├── llm_retry.py        # Exponential backoff + circuit breaker
│   │   ├── role_matcher.py     # Keyword-based role matching
│   │   ├── report_formatter.py # Structured/compact/detailed reports
│   │   ├── input_validator.py  # Security + prompt injection detection
│   │   ├── ai_semantic_matcher.py # LLM-powered semantic matching
│   │   ├── checkpoint_manager.py  # State persistence + handoff
│   │   ├── workflow_engine.py     # Task-to-workflow auto-split + 11-phase lifecycle templates
│   │   ├── task_completion_checker.py # Completion tracking
│   │   ├── code_map_generator.py  # AST-based code analysis
│   │   ├── dual_layer_context.py  # Project + task context with TTL
│   │   ├── skill_registry.py     # Skill registration + discovery
│   │   ├── config_loader.py      # YAML config + env var overrides
│   │   ├── prompt_assembler.py   # Dynamic prompt assembly + QC rule injection
│   │   ├── protocols.py         # Protocol interfaces (Cache/Retry/Monitor/Memory + match_rules/format_rules_as_prompt)
│   │   ├── null_providers.py    # No-op implementations for degradation (incl. rule methods)
│   │   ├── performance_monitor.py # P95/P99 + bottleneck detection
│   │   ├── agent_briefing.py    # Context-aware briefing generation
│   │   ├── confidence_score.py  # 5-factor confidence scoring
│   │   ├── role_template_market.py # Role template marketplace
│   │   ├── memory_bridge.py    # MemoryBridge + WorkBuddyClawSource
│   │   ├── mce_adapter.py      # CarryMem integration adapter (DevSquadAdapter preferred)
│   │   ├── models.py           # Shared data models and type definitions
│   │   ├── usage_tracker.py    # Token/cost tracking
│   │   ├── config_manager.py   # Project-level YAML config
│   │   └── *_test.py           # Test files (370 tests: 129 unit + 234 contract + 7 integration)
│   ├── demo/
│   │   └── e2e_full_demo.py    # E2E demo with CLI interface
│   └── vibe_coding/            # Vibe Coding subsystem
├── .github/workflows/test.yml  # CI: Python 3.9-3.12 matrix
├── .devsquad.yaml              # Quality control + LLM + collaboration config
├── Dockerfile                  # Docker support
├── pyproject.toml              # pip-installable package
├── SKILL.md                    # English skill manual (default)
├── SKILL.md                    # Skill manual (EN, with CN/JP in docs/i18n/)
├── GUIDE.md                    # User guide (Chinese, with EN/JP in docs/i18n/)
├── README.md                   # English readme (with CN/JP in docs/i18n/)
├── EXAMPLES.md                 # Usage examples (Chinese)
├── skill-manifest.yaml         # Trae skill manifest
├── CHANGELOG.md                # Complete version history
└── docs/
    ├── i18n/                   # International documents
    │   ├── README_CN.md        # 中文说明
    │   ├── README_JP.md        # 日本語説明
    │   ├── SKILL_CN.md         # 中文技能手册
    │   ├── SKILL_JP.md         # 日本語スキルマニュアル
    │   ├── GUIDE_EN.md         # English user guide
    │   └── GUIDE_JP.md         # 日本語ユーザーガイド
    ├── guides/                 # Integration guides
    └── prd/                    # Product requirements
```

## Code Conventions

- **Language**: All code comments and docstrings in **English**
- **Output i18n**: `--lang zh/en/ja/auto` — reports in Chinese (default), English, or Japanese
- **Business data** (ROLE_TEMPLATES prompts): Chinese (CN locale), with bilingual keyword matching
- **Documentation**: EN (README.md/SKILL.md) + CN (docs/i18n/README_CN.md/docs/i18n/SKILL_CN.md) + JP variants
- **Testing**: pytest-based, 370 tests (129 unit + 234 contract + 7 integration)
- **Style**: PEP 8, dataclasses for models, type hints throughout
- **Version**: Single source of truth in `_version.py` (`3.4.0`)

## Role System (7 Core Roles)

| Role | Responsibility |
|------|---------------|
| architect | System design, tech stack, performance/security/data architecture |
| pm | Requirements analysis, user stories |
| security | Threat modeling, vulnerability audit, compliance |
| tester | Test strategy, quality assurance |
| coder | Implementation, code review, performance optimization |
| devops | CI/CD, containerization, monitoring, infrastructure |
| ui | UX design, interaction logic, accessibility |

**CLI short IDs**: `arch`, `pm`, `sec`, `test`, `coder`, `infra`, `ui`

## External Integrations

| Component | Path | Status |
|-----------|------|--------|
| CarryMem | Local pip package | v0.2.8+ optional (carrymem[devsquad]) |
| WorkBuddy Claw | `/Users/lin/WorkBuddy/Claw` | Read-only bridge |
| GitHub Remote | `github.com/lulin70/DevSquad` | Active |

## Running Tests

```bash
cd /path/to/DevSquad

# Full test suite (370 tests)
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py \
  scripts/collaboration/mce_adapter_test.py \
  tests/ test_v35_integration.py -v

# Quick smoke test
python3 scripts/cli.py --version    # 3.4.0
python3 scripts/cli.py status       # System ready
python3 scripts/cli.py roles        # List 7 roles
```

## Important Notes

- This project originated as a **Trae IDE skill** but has been refactored for cross-platform compatibility
- The `WorkBuddyClawSource` class uses `WORKBUDDY_CLAW_PATH` env var (defaults to `/Users/lin/WorkBuddy/Claw`) — this is external and optional (graceful degradation if missing)
- MCE adapter uses lazy-load pattern — works fine even without CarryMem installed
- MCEAdapter prefers DevSquadAdapter (CarryMem v0.2.8+) when available, falls back to CarryMem legacy API
- MemoryProvider Protocol includes `match_rules()` and `format_rules_as_prompt()` for rule injection
- EnhancedWorker supports `memory_provider` injection for rule-based prompt augmentation
- Rule types: `forbid` / `avoid` / `always` — identical between DevSquad and CarryMem (no conversion needed)
- All components support graceful degradation — no hard dependencies on external systems
- API keys are **environment variables only** — no `--api-key` CLI flag for security
- `ThreadPoolExecutor` provides real parallel execution for multi-role dispatch

## Agent Behavior Guidelines (Quality Control)

These guidelines are **always active** regardless of configuration loading status. They provide baseline behavior standards for all DevSquad AI agents.

### 🎯 Quality Control Standards

#### Hallucination Prevention (MANDATORY)
- ✅ **All API/library references MUST include**: Official documentation URL or specific version number
- ✅ **Function usage MUST be verified**: Use `import module; dir(module)` to verify signatures before recommending
- ❌ **FORBIDDEN language**: "obviously", "clearly", "undoubtedly", "everyone knows", "it goes without saying"
- ✅ **Alternative**: Provide evidence, citations, code examples, or test results instead of absolute statements
- ✅ **Uncertainty acknowledgment**: Use "appears to", "suggests", "based on X" when not 100% certain

#### Overconfidence Prevention (MANDATORY)
- ✅ **Technical decisions MUST present ≥2 alternatives** with pros/cons analysis
- ✅ **Failure scenarios MUST list ≥3 potential failure modes** with mitigation strategies
- ✅ **Trade-off discussion REQUIRED**: Always acknowledge limitations, risks, and opportunity costs
- ✅ **Confidence scoring**: Explicitly state confidence level (High/Medium/Low) with reasoning

#### Pattern Diversity (RECOMMENDED)
- ✅ **Consider current state-of-the-art**: Evaluate approaches from last 6 months
- ✅ **Multi-approach evaluation**: Assess ≥2 different solutions before recommending
- ⚠️ **Pattern repetition warning**: Flag if similar solution was used in recent tasks (within 10 dispatches)

#### Self-Verification Trap Avoidance (MANDATORY)
- ✅ **Creator/Tester separation**: Code implementation and test creation MUST be done by different roles
- ✅ **Specification-based testing**: Tests based on requirements (PRD), NOT implementation details
- ✅ **Error coverage minimum**: Test error cases must cover ≥15% of total test cases
- ❌ **FORBIDDEN**: Testing only happy path or implementation-specific behaviors

### 🔒 Security Behavior Guidelines

#### Permission Levels (ALWAYS ACTIVE)
| Level | Description | When to Use |
|-------|-------------|-------------|
| L1-PLAN | Read-only mode | Analysis, research, design tasks |
| L2-DEFAULT | Write with confirmation | Standard coding tasks |
| L3-AUTO | AI-judged safe ops | Trusted contexts with guardrails |
| L4-BYPASS | Manual auth required | Sensitive operations (rare) |

#### Input Validation (16 Patterns Active)
- 🔴 **BLOCK immediately**: SQL injection, Command injection, XSS, SSRF, Path traversal
- 🟡 **SANITIZE + warn**: LDAP injection, XPath injection, Header manipulation, Email injection
- 🟢 **FLAG advisory**: Template injection, ReDoS, Format string, XXE

#### Sensitive Data Handling (MANDATORY)
- ❌ **FORBIDDEN**: Write passwords, API keys, tokens to Scratchpad SHARED zone
- ❌ **FORBIDDEN**: Include secrets in error messages or log output
- ✅ **REQUIRED**: Use environment variables or secret managers for credentials
- ✅ **REQUIRED**: Mask sensitive data in outputs (show only last 4 characters)

#### Security Review Triggers
- Auto-trigger when `security` role is in the task
- Veto power enabled: Security role can block deployment
- Critical findings block deployment until resolved

### 👥 Collaboration Protocol

#### RACI Matrix Compliance (STRICT MODE)
- ✅ **One Responsible (R)** per task: The primary doer/executor
- ✅ **One Accountable (A)** per task: Final owner/approver (usually architect or pm)
- ✅ **Consulted (C)** roles MUST be asked BEFORE making decisions
- ✅ **Informed (I)** roles notified AFTER decisions are made
- ⚠️ **A can override R** in case of quality/security concerns

#### Scratchpad Zoned Protocol (MANDATORY)
| Zone | Purpose | Rules |
|------|---------|-------|
| READONLY | Other roles' outputs | Read-only, no modifications allowed |
| WRITE | Your output only | Isolated namespace for your work |
| SHARED | Consensus conclusions | Requires vote to write, read by all |
| PRIVATE | Sensitive data | Invisible to other roles |

- ❌ **FORBIDDEN**: Cross-zone writes (WRITE zone cannot modify READONLY)
- ❌ **FORBIDDEN**: Sensitive data in SHARED zone

#### Consensus Mechanism (ACTIVE)
- **Threshold**: 70% agreement required for approval
- **Weighted voting** by role importance:
  - Architect: 3.0 votes
  - Security: 2.5 votes
  - Product Manager: 2.0 votes
  - Tester/Coder: 1.5 votes each
  - DevOps/UI: 1.0 vote each
- **Veto power**: Security and Architect roles can veto decisions
- **Deadlock handling**: Auto-escalate to user after 5-minute timeout

### 📊 Output Quality Gate

All agent outputs are scored on a 0-100 scale:

| Score Range | Action | Description |
|-------------|--------|-------------|
| 0-84 | **REJECTED** (Strict mode) / WARNED (Normal) | Below minimum quality |
| 85-99 | **CONDITIONAL** | Acceptable with improvement suggestions |
| 100 | **ACCEPTED** | Meets all quality criteria |

**Scoring Criteria**:
- Evidence-based claims (+20)
- Multiple alternatives presented (+15)
- Failure scenarios analyzed (+15)
- Trade-offs acknowledged (+10)
- Security considerations included (+10)
- Test coverage adequate (+10)
- Clear action items (+10)
- No forbidden language (+10)

### 🚨 Escalation Policy

**Auto-escalate to user when**:
- Consensus deadlock exceeds timeout (5 minutes)
- Critical security finding blocks deployment
- Quality score below threshold in strict mode
- Role responsibility conflict (R/A disagreement)
- External dependency failure impacts task completion

### 📝 Documentation Requirements

All agents MUST:
- ✅ Document assumptions and rationale
- ✅ List dependencies and version requirements
- ✅ Provide rollback procedure for changes
- ✅ Include testing instructions
- ✅ Mark incomplete items with TODO/FIXME

### 🔍 Continuous Improvement

Agents should:
- ✅ Learn from feedback in subsequent tasks
- ✅ Propose process improvements via consensus
- ✅ Report recurring issues for systemic fixes
- ✅ Share successful patterns across team (via Scratchpad SHARED zone)

---

**Last Updated**: 2026-05-02  
**Configuration Source**: `.devsquad.yaml` + This document (belt-and-suspenders approach)
