# DevSquad — Project Instructions for AI Coding Assistants

## Project Overview

**DevSquad** is a **V3.3.0 Multi-Role AI Task Orchestrator**. It transforms a single AI task into multi-role AI collaboration with 7 core roles. Based on the Coordinator/Worker/Scratchpad pattern with ThreadPoolExecutor parallel execution.

**27 Core Modules**: MultiAgentDispatcher, Coordinator, Scratchpad, Worker, ConsensusEngine, BatchScheduler, ContextCompressor, PermissionGuard, Skillifier, WarmupManager, MemoryBridge, TestQualityGuard, PromptAssembler, PromptVariantGenerator, MCEAdapter, WorkBuddyClawSource, RoleMatcher, ReportFormatter, InputValidator, AISemanticMatcher, CheckpointManager, WorkflowEngine, TaskCompletionChecker, CodeMapGenerator, DualLayerContext, SkillRegistry, LLMBackend, ConfigManager.

**Test Coverage**: 129 unit tests, all passing.
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
python3 scripts/cli.py --version  # 3.3.0
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
│   ├── collaboration/          # ★ Core V3 modules (27 files)
│   │   ├── _version.py         # Version SSOT (3.3.0)
│   │   ├── dispatcher.py       # MultiAgentDispatcher — unified entry point
│   │   ├── coordinator.py      # Global orchestrator
│   │   ├── scratchpad.py       # Shared blackboard
│   │   ├── worker.py           # Role executor (with streaming)
│   │   ├── consensus.py        # Weighted voting + veto
│   │   ├── llm_backend.py      # Mock/OpenAI/Anthropic + streaming
│   │   ├── role_matcher.py     # Keyword-based role matching
│   │   ├── report_formatter.py # Structured/compact/detailed reports
│   │   ├── input_validator.py  # Security + prompt injection detection
│   │   ├── ai_semantic_matcher.py # LLM-powered semantic matching
│   │   ├── checkpoint_manager.py  # State persistence + handoff
│   │   ├── workflow_engine.py     # Task-to-workflow auto-split
│   │   ├── task_completion_checker.py # Completion tracking
│   │   ├── code_map_generator.py  # AST-based code analysis
│   │   ├── dual_layer_context.py  # Project + task context with TTL
│   │   ├── skill_registry.py     # Skill registration + discovery
│   │   ├── config_loader.py      # YAML config + env var overrides
│   │   ├── memory_bridge.py    # MemoryBridge + WorkBuddyClawSource
│   │   ├── mce_adapter.py      # CarryMem integration adapter
│   │   └── *_test.py           # Test files (129 unit tests)
│   ├── demo/
│   │   └── e2e_full_demo.py    # E2E demo with CLI interface
│   └── vibe_coding/            # Vibe Coding subsystem
├── .github/workflows/test.yml  # CI: Python 3.9-3.12 matrix
├── Dockerfile                  # Docker support
├── pyproject.toml              # pip-installable package
├── SKILL.md                    # English skill manual (default)
├── SKILL-CN.md                 # Chinese skill manual
├── SKILL-JP.md                 # Japanese skill manual
├── README.md                   # English readme (default)
├── README-CN.md                # Chinese readme
├── README-JP.md                # Japanese readme
├── EXAMPLES.md                 # Usage examples (Chinese)
├── EXAMPLES_EN.md              # Usage examples (English)
├── skill-manifest.yaml         # Trae skill manifest
├── CHANGELOG.md                # Complete version history
└── docs/                       # Architecture specs, plans, test plans
```

## Code Conventions

- **Language**: All code comments and docstrings in **English**
- **Output i18n**: `--lang zh/en/ja/auto` — reports in Chinese (default), English, or Japanese
- **Business data** (ROLE_TEMPLATES prompts): Chinese (CN locale), with bilingual keyword matching
- **Documentation**: EN (README.md/SKILL.md) + CN (README-CN.md/SKILL-CN.md) + JP variants
- **Testing**: pytest-based, 129 unit tests
- **Style**: PEP 8, dataclasses for models, type hints throughout
- **Version**: Single source of truth in `_version.py` (`3.3.0`)

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
| MCE (Memory Classification Engine) | Local pip package | v0.4.0 integrated |
| WorkBuddy Claw | `/Users/lin/WorkBuddy/Claw` | Read-only bridge |
| GitHub Remote | `github.com/lulin70/DevSquad` | Active |

## Running Tests

```bash
cd /path/to/DevSquad

# Core unit tests (99 tests)
python3 -m pytest scripts/collaboration/core_test.py \
  scripts/collaboration/role_mapping_test.py \
  scripts/collaboration/upstream_test.py -v

# Quick smoke test
python3 scripts/cli.py --version    # 3.3.0
python3 scripts/cli.py status       # System ready
python3 scripts/cli.py roles        # List 7 roles
```

## Important Notes

- This project originated as a **Trae IDE skill** but has been refactored for cross-platform compatibility
- The `WorkBuddyClawSource` class has a hardcoded path to `/Users/lin/WorkBuddy/Claw` — this is external and optional (graceful degradation if missing)
- MCE adapter uses lazy-load pattern — works fine even without MCE installed
- All components support graceful degradation — no hard dependencies on external systems
- API keys are **environment variables only** — no `--api-key` CLI flag for security
- `ThreadPoolExecutor` provides real parallel execution for multi-role dispatch
