# DevSquad — Project Instructions for AI Coding Assistants

## Project Overview

**DevSquad** is a **V3.3 Multi-Agent Software Development Team** platform. It transforms a single AI assistant into a specialized development squad with 10 roles (architect/pm/coder/tester/ui/devops/security/data/reviewer/optimizer). Based on the Coordinator/Worker/Scratchpad pattern for parallel agent collaboration.

**16 Core Modules**: Coordinator, Scratchpad, Worker, ConsensusEngine, BatchScheduler, ContextCompressor (4-level), PermissionGuard (4-level), Skillifier, WarmupManager (3-layer), MemoryBridge (MCE+Claw), TestQualityGuard, PromptAssembler, PromptVariantGenerator, MCEAdapter, WorkBuddyClawSource.

**Test Coverage**: ~825+ tests, all passing.
**Cross-Platform**: Trae IDE / ClaudeCode / OpenClaw / Any MCP-compatible client.

## Architecture

```
User Task → [Intent Analysis] → [Role Matching] → [Coordinator Orchestration]
           → [Parallel Worker Execution] → [Scratchpad Real-time Sharing]
           → [Consensus Decision] → [MCE Classification] → [Result Return]
```

## Key Entry Points

### Primary API (Python)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design user authentication system")
print(result.to_markdown())
disp.shutdown()
```

### CLI Entry Point

```bash
python -m scripts.demo.e2e_full_demo --task "your task here" --roles architect coder tester
python -m scripts.demo.e2e_full_demo --json   # JSON output format
```

### Quick Dispatch (3 formats)

```python
result = disp.quick_dispatch(task, output_format="structured")  # structured / compact / detailed
result = disp.quick_dispatch(task, include_action_items=True)   # auto-generate H/M/L action items
```

## Directory Structure

```
DevSquad/
├── scripts/
│   ├── collaboration/          # ★ Core V3 modules (16 files)
│   │   ├── dispatcher.py       # MultiAgentDispatcher — unified entry point
│   │   ├── coordinator.py      # Global orchestrator
│   │   ├── scratchpad.py       # Shared blackboard
│   │   ├── worker.py           # Role executor
│   │   ├── consensus.py        # Weighted voting + veto
│   │   ├── memory_bridge.py    # MemoryBridge + WorkBuddyClawSource
│   │   ├── mce_adapter.py      # MCE v0.4 adapter (tenant/permission)
│   │   └── *_test.py           # Test files (176 core tests)
│   ├── demo/
│   │   └── e2e_full_demo.py    # E2E demo with CLI interface
│   └── vibe_coding/            # Vibe Coding subsystem
├── SKILL.md                    # English skill manual (default)
├── SKILL-CN.md                 # Chinese skill manual
├── SKILL-JP.md                 # Japanese skill manual
├── README.md                   # English readme (default)
├── README-CN.md                # Chinese readme
├── README-JP.md                # Japanese readme
├── skill-manifest.yaml         # Trae skill manifest
├── CHANGELOG.md                # Complete version history
└── docs/                       # Architecture specs, plans, test plans
```

## Code Conventions

- **Language**: All code comments and docstrings in **English**
- **Business data** (ROLE_TEMPLATES prompts, report format strings): Chinese (CN locale)
- **Documentation**: EN (README.md/SKILL.md) + CN (README-CN.md/SKILL-CN.md) + JP variants
- **Testing**: pytest-based, 176 core collaboration tests
- **Style**: PEP 8, dataclasses for models, type hints throughout

## Role System (5 Core + 5 Planned)

| Role | Responsibility |
|---------------------|
| architect | System design, tech stack decisions |
| pm | Requirements analysis, user stories |
| coder | Implementation, code generation |
| tester | Test strategy, quality assurance |
| ui | UX design, interaction logic |
| devops | CI/CD, deployment, infrastructure |
| security | Security audit, vulnerability scan |
| data | Data modeling, analytics |
| reviewer | Code review, best practices |
| optimizer | Performance optimization |

## External Integrations

| Component | Path | Status |
|-----------|------|--------|
| MCE (Memory Classification Engine) | Local pip package | v0.4.0 integrated |
| WorkBuddy Claw | `/Users/lin/WorkBuddy/Claw` | Read-only bridge |
| GitHub Remote | `github.com/lulin70/TraeDevSquad` | Active |

## Running Tests

```bash
cd /path/to/DevSquad
python3 -m pytest scripts/collaboration/mce_adapter_test.py \
  scripts/collaboration/dispatcher_ux_test.py \
  scripts/collaboration/claw_integration_test.py \
  scripts/collaboration/memory_bridge_test.py -v
# Expected: 176 passed
```

## Important Notes

- This project originated as a **Trae IDE skill** but has been refactored for cross-platform compatibility
- The `WorkBuddyClawSource` class has a hardcoded path to `/Users/lin/WorkBuddy/Claw` — this is external and optional (graceful degradation if missing)
- MCE adapter uses lazy-load pattern — works fine even without MCE installed
- All components support graceful degradation — no hard dependencies on external systems
