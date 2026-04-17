---
name: multi-agent-team
description: |
  Multi-Agent Collaboration Platform — Transform single AI into a multi-AI team.
  Use this when: user needs multi-role analysis, code review, architecture design,
  complex task decomposition, or parallel expert collaboration.

  Triggers: "design", "implement", "analyze", "review", "collaborate", "multi-role",
  "team", "architect", "test", "optimize" in task descriptions.
metadata:
  version: 3.3.0
  author: MultiAgentSkill Team
---

# Multi-Agent Team Skill

## When to Use This Skill

Activate this skill when the user request involves:
- **Multi-perspective analysis** — Need architect + tester + security reviewer opinions
- **Complex task decomposition** — Large task needs breakdown into parallel workstreams
- **Code review with roles** — Need specialized reviewer perspectives (security, performance, UX)
- **Architecture design** — System design requiring multiple expert viewpoints
- **Quality assurance** — Comprehensive analysis covering multiple dimensions

## How to Invoke

### Option A: Python API (Recommended for programmatic use)

```python
import sys
sys.path.insert(0, '/path/to/MultiAgentSkill')
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()
result = disp.dispatch("Design a REST API for user management")
print(result.to_markdown())
disp.shutdown()
```

### Option B: CLI Interface

```bash
cd /path/to/MultiAgentSkill
python3 scripts/demo/e2e_full_demo.py --task "your task" --roles architect pm coder tester
```

### Option C: Quick Dispatch (3 output formats)

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher

disp = MultiAgentDispatcher()

# Structured report (default) — best for terminal output
result = disp.quick_dispatch("Analyze the auth module", output_format="structured")

# Compact — one-line summary per role
result = disp.quick_dispatch("Review the database schema", output_format="compact")

# Detailed — full role outputs with findings and action items
result = disp.quick_dispatch("Design microservice architecture", output_format="detailed",
                              include_action_items=True, include_timing=True)

disp.shutdown()
```

## Available Roles

| Role | Best For |
|------|----------|
| `architect` | System design, tech stack, API design |
| `pm` | Requirements, user stories, acceptance criteria |
| `coder` | Implementation, code patterns, refactoring |
| `tester` | Test strategy, edge cases, coverage |
| `ui` | UX flow, interaction design, accessibility |
| `devops` | CI/CD, deployment, monitoring |
| `security` | Threat modeling, vulnerability audit |
| `data` | Data model, analytics, migration |
| `reviewer` | Code review, best practices |
| `optimizer` | Performance, caching, optimization |

**Auto-match**: If no roles specified, the dispatcher automatically matches roles based on task intent.

## Configuration Options

```python
disp = MultiAgentDispatcher(
    persist_dir="./scratch_data",       # Scratchpad storage
    enable_warmup=True,                 # Pre-load components (~300ms faster)
    enable_compression=True,            # Auto context compression
    enable_permission=True,             # Safety checks before actions
    enable_memory=True,                 # Cross-session memory
    enable_skillify=True,               # Learn from successful patterns
    compression_threshold=100000,       # Tokens before compression triggers
    permission_level=PermissionLevel.DEFAULT,  # Safety level
)
```

## Mode Selection

| Mode | Behavior |
|------|----------|
| `auto` (default) | Dispatcher decides parallel vs sequential |
| `parallel` | All workers run concurrently |
| `sequential` | Workers run one after another |
| `consensus` | Requires full consensus (any veto blocks) |

```python
result = disp.dispatch("Task", mode="consensus")
```

## Output Format

The result object provides:

- `result.summary` — One-line executive summary
- `result.to_markdown()` — Full Markdown report
- `result.matched_roles` — List of activated roles
- `result.worker_results` — Per-role detailed results
- `result.timing` — Execution timing data
- `result.success` — Boolean success flag

## Integration Notes

- **No hard dependencies**: All external integrations (MCE, WorkBuddy Claw) use graceful degradation
- **Thread-safe**: Safe for concurrent use
- **Memory**: Optional cross-session memory via MemoryBridge (7 types, TF-IDF, forgetting curve)
- **MCE v0.4**: Supports tenant isolation and permission checking if MCE backend available

## Example Workflows

### Architecture Design Session
```
User: "Design a microservices e-commerce backend"
→ Skill: dispatch("Design a microservices e-commerce backend", roles=["architect", "devops", "security"])
→ Output: Tech stack recommendation + service boundaries + security model + deployment strategy
```

### Code Review Session
```
User: "Review auth.py for security issues"
→ Skill: dispatch("Review auth.py for security", roles=["reviewer", "security", "tester"])
→ Output: Security findings + test gaps + improvement suggestions + action items (H/M/L)
```

### Full-Stack Analysis
```
User: "Analyze our project's readiness for production"
→ Skill: dispatch("Production readiness analysis")  # auto-matches roles
→ Output: Multi-role assessment with consensus decision
```
