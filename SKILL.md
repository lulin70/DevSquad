---
name: devsquad
slug: devsquad
description: |
  V3.4.0 DevSquad — Multi-Role AI Task Orchestrator.
  One task in, multi-role AI collaboration, one conclusion out.
  7 core roles (architect/pm/security/tester/coder/devops/ui), real LLM backend
  (OpenAI/Anthropic), CLI + MCP + Python API. 560+ tests all passing.
  ThreadPoolExecutor parallel, CheckpointManager, WorkflowEngine, streaming, Docker, CI.
---

# DevSquad V3.4.0 — Multi-Role AI Task Orchestrator

## Core Positioning

This Skill upgrades Trae from a "single AI assistant" to a "multi-AI team". When a task is submitted, it is no longer handled by a single role:

```
User Task → [InputValidator] → [RoleMatcher] → [Coordinator Orchestration]
           → [ThreadPoolExecutor Parallel Workers] → [Scratchpad Real-time Sharing]
           → [ConsensusEngine] → [ReportFormatter] → [Structured Report]
```

## Architecture Overview (45 Core Modules)

| # | Module | File | Responsibility |
|---|-------|------|---------------|
| 0 | **MultiAgentDispatcher** | `dispatcher.py` | Unified dispatch entry point (integrates all modules) |
| 1 | **Coordinator** | `coordinator.py` | Global orchestrator: decompose tasks, assign Workers, collect results, resolve conflicts |
| 2 | **Scratchpad** | `scratchpad.py` | Shared blackboard for real-time info exchange between Workers |
| 3 | **Worker** | `worker.py` | Executor: one instance per role, independent execution with Scratchpad writes |
| 4 | **ConsensusEngine** | `consensus.py` | Consensus engine: weighted voting + veto power + escalation mechanism |
| 5 | **BatchScheduler** | `batch_scheduler.py` | Parallel/sequential hybrid scheduling with auto safety check |
| 6 | **ContextCompressor** | `context_compressor.py` | 4-level context compression (NONE/SNIP/SESSION_MEMORY/FULL_COMPACT) |
| 7 | **PermissionGuard** | `permission_guard.py` | 4-level permission guard (PLAN/DEFAULT/AUTO/BYPASS) |
| 8 | **Skillifier** | `skillifier.py` | Auto-generate new Skills from successful operation patterns |
| 9 | **WarmupManager** | `warmup_manager.py` | 3-layer startup warmup (EAGER/ASYNC/LAZY) + process-level cache |
| 10 | **MemoryBridge** | `memory_bridge.py` | 7-type memory bridge + inverted index + TF-IDF + forgetting curve + MCE+Claw integration |
| 11 | **TestQualityGuard** | `test_quality_guard.py` | Test quality audit (API validation / anti-pattern detection / dimension coverage) |
| 12 | **PromptAssembler** | `prompt_assembler.py` | Dynamic prompt assembly (complexity detection / 3 variants / 5 styles / compression-aware / QC config injection / user rule injection) |
| 13 | **PromptVariantGenerator** | `prompt_variant_generator.py` | Skillify closed-loop feedback (pattern→variant / A-B test / auto promote-deprecate) |
| 14 | **MCEAdapter** | `mce_adapter.py` | CarryMem integration adapter (DevSquadAdapter preferred, lazy-load / graceful-degrade / thread-safe / match_rules + format_rules_as_prompt + add_rule) |
| 15 | **WorkBuddyClawSource** | `memory_bridge.py` (class) | WorkBuddy Claw read-only bridge (INDEX search / daily logs / AI news feed) |
| 16 | **RoleMatcher** | `role_matcher.py` | Keyword-based role matching with alias resolution (extracted from Dispatcher) |
| 17 | **ReportFormatter** | `report_formatter.py` | Structured/compact/detailed report generation (extracted from Dispatcher) |
| 18 | **InputValidator** | `input_validator.py` | Security validation + 21+-pattern prompt injection detection |
| 19 | **RuleCollector** | `rule_collector.py` | Natural language rule collection (intent detection / rule extraction / sanitization / CarryMem+JSON storage / prompt injection protection) |
| 20 | **AISemanticMatcher** | `ai_semantic_matcher.py` | LLM-powered semantic role matching with bilingual keyword fallback |
| 21 | **CheckpointManager** | `checkpoint_manager.py` | SHA256 integrity, handoff documents, auto-cleanup, dispatch integration |
| 22 | **WorkflowEngine** | `workflow_engine.py` | Task-to-workflow auto-split, step execution, checkpointing, agent handoff, 11-phase lifecycle templates |
| 23 | **TaskCompletionChecker** | `task_completion_checker.py` | DispatchResult/ScheduleResult completion tracking + progress persistence |
| 24 | **CodeMapGenerator** | `code_map_generator.py` | Python AST-based code structure analysis + dependency graph |
| 25 | **DualLayerContext** | `dual_layer_context.py` | Project-level + task-level context management with TTL |
| 26 | **SkillRegistry** | `skill_registry.py` | Reusable skill registration + discovery + persistence |
| 27 | **LLMBackend** | `llm_backend.py` | Mock/OpenAI/Anthropic with streaming support + 120s timeout |
| 28 | **ConfigManager** | `config_loader.py` | YAML config + env var overrides (16 parameters) |
| 29 | **Protocols** | `protocols.py` | Protocol interfaces (CacheProvider/RetryProvider/MonitorProvider/MemoryProvider + match_rules/format_rules_as_prompt) + exception hierarchy |
| 30 | **NullProviders** | `null_providers.py` | No-op implementations for all Protocol interfaces (incl. match_rules/format_rules_as_prompt, degradation + test mocking) |
| 31 | **EnhancedWorker** | `enhanced_worker.py` | Worker with protocol-based provider injection (cache/retry/monitor/briefing/memory) + rule injection pipeline |
| 32 | **PerformanceMonitor** | `performance_monitor.py` | P95/P99 response time, CPU/memory tracking, bottleneck detection, Markdown reports |
| 33 | **AgentBriefing** | `agent_briefing.py` | Context-aware briefing generation with priority filtering + persistence |
| 34 | **ConfidenceScorer** | `confidence_score.py` | 5-factor confidence scoring (completeness/certainty/specificity/consistency/model quality) |
| 35 | **RoleTemplateMarket** | `role_template_market.py` | Role template marketplace (publish/search/install/rate/export/import) |
| 36 | **LLMCache** | `llm_cache.py` | TTL-based LRU cache with disk persistence (60-80% cost reduction) |
| 37 | **LLMRetry** | `llm_retry.py` | Exponential backoff + circuit breaker + multi-backend fallback |
| 38 | **UsageTracker** | `usage_tracker.py` | Token/cost usage tracking and reporting |
| 39 | **Models** | `models.py` | Shared data models and type definitions |
| 40 | **ConfigManager (YAML)** | `config_manager.py` | Project-level YAML configuration management |
| 41 | **LLMCacheAsync** | `llm_cache_async.py` | Async LLM cache for concurrent workloads |
| 42 | **LLMRetryAsync** | `llm_retry_async.py` | Async LLM retry with backoff |
| 43 | **IntegrationExample** | `integration_example.py` | DevSquad integration example code |
| 44 | **AsyncIntegrationExample** | `async_integration_example.py` | Async DevSquad integration example |
| 45 | **AntiRationalizationEngine** | `anti_rationalization.py` | Per-role excuse→rebuttal tables (8 universal + 6-7 role-specific) injected via PromptAssembler to prevent quality shortcuts |
| 46 | **VerificationGate** | `verification_gate.py` | Mandatory evidence requirements + 7 Red Flags detection + Prove-It Pattern for completion claims |
| 47 | **IntentWorkflowMapper** | `intent_workflow_mapper.py` | User intent → workflow chain mapping (6 intents × 3 languages) with gate requirements and anti-skip messages |
| 48 | **CLI Lifecycle Commands** | `cli.py` | 6 lifecycle shortcuts (spec/plan/build/test/review/ship) with preset roles/modes/gates inspired by Agent Skills |

---

## Quick Start (Must Follow)

### Method 1: One-Click Collaboration (Recommended for most scenarios)

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

**CLI equivalent**:
```bash
export OPENAI_API_KEY="sk-..."
python3 scripts/cli.py dispatch -t "Design auth system" -r arch sec --backend openai
```

**When to use Method 1**:
- User requests like "Design XX", "Implement XX", "Analyze XX"
- Need quick multi-role collaboration results
- No need for fine-grained role control

### Method 2: Specify Roles

```python
disp = MultiAgentDispatcher()
result = disp.dispatch("Design user auth system", roles=["architect", "tester"])
print(result.to_markdown())
disp.shutdown()
```

### Method 3: Dry-Run Simulation (Analyze only, no execution)

```python
result = disp.dispatch("Test task", dry_run=True)
print(result.summary)
disp.shutdown()
```

### Method 4: Convenience Function (One-liner)

```python
from scripts.collaboration.dispatcher import quick_collaborate
result = quick_collaborate("Help me design a microservice architecture")
print(result.to_markdown())
```

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

## Complete Workflow (When This Skill is Invoked)

### Step 1: Create Dispatcher

```python
from scripts.collaboration.dispatcher import MultiAgentDispatcher
import tempfile

work_dir = tempfile.mkdtemp(prefix="mas_v3_")
disp = MultiAgentDispatcher(
    persist_dir=work_dir,
    enable_warmup=True,
    enable_compression=True,
    enable_permission=True,
    enable_memory=True,
    enable_skillify=True,
)
```

### Step 2: Analyze Task & Match Roles

```python
matched = disp.analyze_task(user_task)
for role in matched:
    print(f"{role['name']} (confidence: {role['confidence']:.0%}) - {role['reason']}")
```

### Step 3: Execute Collaboration

```python
result = disp.dispatch(
    task_description=user_task,
    roles=None,          # None=auto match, or specify ["architect", "tester"]
    mode="auto",         # auto/parallel/sequential/consensus
    dry_run=False,       # True=simulation only
)
```

### Step 4: Check Results

```python
print(f"Success: {result.success}")
print(f"Roles: {result.matched_roles}")
print(f"Duration: {result.duration_seconds:.2f}s")
print(result.summary)

if result.worker_results:
    for wr in result.worker_results:
        print(f"[{wr['role']}] {wr['output'][:200]}")
```

### Step 5: Output Markdown Report

```python
report = result.to_markdown()
print(report)
```

### Step 6: Cleanup

```python
disp.shutdown()
```

---

## Advanced Features Guide

### Context Compression (Prevent Long Conversation Overflow)

When conversations get too long, ContextCompressor triggers automatically:
- **Level 1 SNIP**: Fine-grained trimming of old dialogue, preserving key decisions and conclusions
- **Level 2 SessionMemory**: Extract important info to memory then clear context
- **Level 3 FullCompact**: LLM generates one-page summary (most aggressive)

Check compression status:
```python
stats = disp.coordinator.get_compression_stats()
memory = disp.coordinator.get_session_memory()
```

### Permission Guard (Secure Operation Sentinel)

PermissionGuard auto-checks dangerous operations:
- **PLAN level**: Read-only operations only
- **DEFAULT level**: Write ops require confirmation
- **AUTO level**: AI classifier auto-judgment
- **BYPASS level**: Full skip (highest trust)

Permission records stored in `result.permission_checks`.

### Memory Bridge (Cross-session Memory)

MemoryBridge provides 7 memory types:
- `knowledge` — Knowledge entries
- `episodic` — Episodic memories (task execution records)
- `semantic` — Semantic memories
- `feedback` — User feedback
- `pattern` — Successful patterns
- `analysis` — Analysis cases
- `correction` — Correction records

Forgetting curve: 7d=1.0, 30d≈0.8, 60d≈0.5, 90d≈0.3

Check memory status:
```python
status = disp.get_status()
mem_stats = status.get("memory_stats")
```

### Startup Warmup (Reduce Cold-start Latency)

WarmupManager 3-layer warmup:
- **EAGER layer**: Synchronous preload of critical resources (~15ms)
- **ASYNC layer**: Async background warmup (~300ms)
- **LAZY layer**: On-demand loading

Check warmup status:
```python
status = disp.get_status()
warmup = status.get("warmup_metrics")
```

### Skill Learning (Evolve from Success)

Skillifier auto-extracts reusable patterns from successful operation sequences:
```python
proposals = result.skill_proposals
for p in proposals:
    print(f"New Skill candidate: {p['title']} (confidence: {p['confidence']:.0%})")
```

### Consensus Decision (Multi-role Conflict Resolution)

When Workers disagree, ConsensusEngine initiates voting:
- Weighted voting (weighted by role importance)
- Veto power (key role can single-handedly block)
- Escalation to human (mark as pending human decision when consensus unreachable)

Consensus records in `result.consensus_records`.

---

## Dispatch Mode Table

| Mode | Description | Use Case |
|------|-------------|----------|
| `auto` | Auto-select optimal mode | Default recommended |
| `parallel` | All roles execute concurrently | No inter-role dependencies |
| `sequential` | Execute in order | Has dependency chain |
| `consensus` | Force consensus vote after execution | Needs unanimous decision |

---

## System Status Query

```python
status = disp.get_status()
# Returns:
# {
#   "version": "3.4.0",
#   "components": {...},        # Component enabled status
#   "dispatch_count": N,         # Completed dispatch count
#   "scratchpad_stats": {...}, # Blackboard stats
#   "warmup_metrics": {...},    # Warmup metrics (if enabled)
#   "memory_stats": {...},      # Memory stats (if enabled)
# }

history = disp.get_history(limit=10)
# Returns last N dispatch complete results
```

---

## Error Handling

All exceptions are captured inside `DispatchResult`, never thrown:

```python
result = disp.dispatch("Any task")
if not result.success:
    print("Errors:", result.errors)
    print("Summary:", result.summary)
```

Common errors and handling:
- `FILE_CREATE` / Permission related → PermissionGuard blocked, check `result.permission_checks`
- Memory write failure → MemoryBridge storage issue, check directory permissions
- Compression failure → ContextCompressor issue, usually doesn't affect main flow

---

## Language Rules

- Auto-detect user language (Chinese/English/Japanese)
- All output uses same language as user
- Role name mapping: 架构师→Architect, PM→Product Manager, etc.

---

## Testing Iron Rules (⚠️ Must Follow When AI Writes Tests)

> This section addresses three chronic issues in AI-assisted test development.
> **Violating any rule is a serious error.**

### Iron Rule 1: Documentation First — Never Write API Calls From Memory

```
❌ WRONG: Guess parameter names from memory
   result = obj.method(bad_param="value")  # Parameter name is guessed

✅ CORRECT: Read source code to confirm signature first, then write tests
   # 1. Use AST extraction or read source directly to confirm params
   # 2. Use TestQualityGuard for auto-validation
   from scripts.collaboration.test_quality_guard import quick_audit
   report = quick_audit("module.py", "module_test.py")
   print(report.to_markdown())  # Check for API param errors
```

**Mandatory requirements**:
- Before writing any test, must `import` target module and verify actual signature
- Forbidden to use non-existent parameter names (e.g., `id` vs `record_id`)
- Can use `TestQualityGuard.quick_audit()` for auto-detection

### Iron Rule 2: Failure Means Report — Never Modify Assertions to Pass

```
❌ CRITICAL ERROR: Modify assertions when test fails to "pass"
   # Original: assertEqual(result, expected_value)
   # Changed to: assertTrue(result > 0)          ← This is cheating!
   # Changed to: assertGreater(score, 0.0)      ← 0.0 threshold always passes!

✅ CORRECT: Analyze root cause on failure, fix implementation or correct test logic
   # 1. Confirm API signature is correct (Iron Rule 1)
   # 2. Verify test data is reasonable
   # 3. If implementation has real bug → report to architect/developer
   # 4. Only modify assertions if test logic itself is wrong
```

**Forbidden anti-patterns** (auto-detected by TestQualityGuard):
| Anti-pattern | Severity | Description |
|------------|----------|-------------|
| Loose assertion (`assertTrue`) | MINOR | Prefer `assertEqual/assertIn` |
| Invalid threshold (`>0.0`) | MINOR | Must set meaningful thresholds |
| Bare `except:` | MAJOR | Must specify exception type |
| Magic numbers (>999) | MINOR | Extract to named constants |

### Iron Rule 3: Dimension Completeness — Never Only Test Happy Path

Every module's test suite **must** cover these dimensions:

| Dimension | Symbol | Min % | Description |
|-----------|--------|-------|-------------|
| **Happy Path** | ✅ | ≥50% | Normal input → Expected output |
| **Error Case** | 🔴 | **≥15%** | Illegal input / empty / out-of-bounds → Exception or error return |
| **Boundary** | 🟡 | ≥10% | Empty string, zero value, max value, None |
| **Performance** | ⚡ | **≥5%** | Critical path timing baseline (e.g., `<100ms`) |
| **Configuration** | ⚙️ | ≥5% | Different config combinations |
| **Integration** | 🔗 | ≥10% | Inter-module collaboration scenarios |
| **Security** | 🔒 | As needed | Permission / injection / privilege escalation (if security-related) |

**Auto-check tool**:
```python
from scripts.collaboration.test_quality_guard import TestQualityGuard

guard = TestQualityGuard(
    module_path="scripts/collaboration/coordinator.py",
    test_path="scripts/collaboration/coordinator_test.py",
)
report = guard.audit()
print(report.to_markdown())
# Output: Score + Issue list + Dimension coverage + Anti-pattern detection
```

### Test Function Template (Must Follow Format)

```python
def test_<feature>_<scenario>(self):
    """Verify: <What exactly to verify, one sentence>

    Scenario: <What condition triggers this>
    Expected: <What should happen>
    """
    # Arrange - Prepare data and dependencies

    # Act - Execute operation under test

    # Assert - Verify results (use precise assertions, never use assertTrue to bypass)
```

---

## Project Lifecycle: 11-Phase Model (V3.4.0)

> **Definition document**: `docs/prd/lifecycle_phases_definition.md` (authoritative)
> **Review report**: `docs/prd/lifecycle_phases_review.md` (7-role review, 9 suggestions adopted)

### Phase Overview

| # | Phase | Lead | Reviewers | Optional | Gate |
|---|-------|------|-----------|----------|------|
| P1 | Requirements Analysis | pm | arch+test+sec+ui | ❌ | Acceptance criteria quantifiable |
| P2 | Architecture Design | arch | pm+sec+infra | ❌ | Weighted consensus ≥70% |
| P3 | Technical Design | arch+coder | coder+test | ❌ | API specs unambiguous |
| P4 | Data Design | arch+coder | arch+sec | ✅ | 3NF or denormalization justified |
| P5 | Interaction Design | ui | pm+test+sec | ✅ | Core flow usability verified |
| P6 | Security Review | sec | arch+infra | ✅ | No P0/P1 vulns, compliance green |
| P7 | Test Planning | test | arch+sec+infra+pm | ❌ | Test plan review passed |
| P8 | Implementation | coder | arch+sec+test+coder | ❌ | Code review passed, no P0 defects |
| P9 | Test Execution | test | arch+pm+sec+infra | ❌ | Coverage≥80% + P7 plan 100% executed |
| P10 | Deployment & Release | infra | arch+sec+test | ❌ | Deployment drill passed |
| P11 | Operations & Assurance | infra+sec | arch+infra | ✅ | P99<target, alerts 100% |

### Dependency Graph

```
P1 → P2 ──┬──→ P3 ──→ P6 ──→ P7 ──→ P8 ──→ P9 ──→ P10 ──→ P11
           ├──→ P4(∥P3) ──↗
           └──→ P5(dep P1+P3) ──↗
```

### Lifecycle Templates

| Template | Phases | Use Case |
|----------|--------|----------|
| `full` | P1-P11 | Complete project |
| `backend` | No P5 | Backend services |
| `frontend` | No P4,P6 | Frontend applications |
| `internal_tool` | No P4,P5,P6,P11 | Internal tools |
| `minimal` | P1,P3,P7,P8,P9 | Minimum set |

### Gate Mechanism

- **Mandatory**: Every phase gate must be checked
- **Non-blocking on failure**: Generate gap report → user decides
- **Traceability**: All gate results recorded to checkpoints

### Requirement Change Process

```
Change Request(pm/user) → Impact Analysis(arch+sec+test) → Change Review(all roles) → Approve/Reject → Rollback to affected phase
```

---

## Meta Iron Rule: Documentation First, Trace Everything (⚠️ Supreme Law)

> **文档先行，万事留痕** — This is the supreme iron rule that governs all other rules.
> **Violating this rule is a critical error that invalidates all work done.**

### Core Principle

```
Before any code is written → Plan/Spec document must exist
Before any change is made → Impact analysis must be documented
After any work is done → Results must be recorded in docs
After any decision is made → Rationale must be traceable
```

### Mandatory Requirements

| Phase | Requirement | Verification |
|-------|-------------|--------------|
| **Pre-work** | No code without a spec/plan document | `docs/spec/` or `docs/prd/` has corresponding doc |
| **During work** | All decisions logged with rationale | Commit messages, ADRs, or inline comments explain WHY |
| **Post-work** | All affected docs updated synchronously | Version/module count/test count consistent across all docs |
| **Always** | No orphaned code without documentation origin traceable | Every file's purpose documented in at least one doc |

### What "Documentation First" Means

1. **Spec before implementation**: If there's no SPEC or PRD, write one first. Even a one-paragraph spec beats no spec.
2. **Design before coding**: Architecture decisions recorded before code written.
3. **Test plan before tests**: What to test and why, before writing test code.
4. **Change log before merge**: What changed and why, before pushing.

### What "Trace Everything" Means

1. **Every decision has a why**: Code comments, commit messages, ADRs — pick at least one.
2. **Every file has an owner/purpose**: Why does this file exist? Document it.
3. **Every change has a trail**: Git history + doc updates = full audit trail.
4. **No stealth changes**: Nothing committed without a corresponding doc update.

### Enforcement

- CI check: `docs/` directory must have updated files matching code changes
- Review gate: PR reviewer checks doc sync status
- Consensus: Coordinator verifies documentation completeness before approval
- Retroactively: Work done without prior docs must be backfilled immediately

---

## Delivery Workflow Iron Rules (⚠️ Must Execute After Every Push)

> This section defines the standard closed-loop workflow: Implement→Test→Walkthrough→Annotate→Docs→Git.
> **Violating any step is a serious error.**

### Iron Rule: Mandatory Post-push Closed Loop

```
Implement → Test(Regression All) → Code Walkthrough → Annotate → Docs Update → Cleanup → Git Push
```

**Mandatory actions per step**:

| Step | Mandatory Action | Verification Criteria |
|------|-----------------|----------------------|
| **1. Implement** | Write/modify code per Plan/Spec | Feature complete, no TODO placeholders |
| **2. Test** | New tests + full regression | 0 failure, 0 error, 100% pass |
| **3. Walkthrough** | Read every new/modified line in each file | Understand each method's I/O and edge behavior |
| **4. Annotate** | Public method docstring (Args/Returns) + key logic inline comments | No "naked methods" (public method without docstring) |
| **5. Docs Update** | **Sync ALL relevant docs** (see checklist below) | All docs have consistent version/module count/test count, no stale content |
| **6. Cleanup** | Delete process docs / temp docs / temp code | No residual `_tmp`/`_draft`/`_old` files |
| **7. Git Push** | commit message includes version+change summary+test count | push success, visible on remote |

### Iron Rule: Doc Coverage Checklist (Step 5 must check ALL categories)

> **Principle: All doc types related to the change must be updated — requirements/design/test/API/install/SKILL/etc.**

| Doc Category | Check Item | Relevant? |
|-------------|-----------|----------|
| **Requirements** | `docs/spec/*.md` — Spec status update (pending→in-progress→implemented) | ✅ Must check |
| **Design** | `docs/architecture/*.md` — Architecture evolution record, Phase additions | ✅ Must check |
| **Planning** | `docs/planning/*.md` — Consensus action items checked, extension notes | ✅ Must check |
| **SKILL Docs** | `SKILL.md` — Module table, test table, version history, rules | ✅ Must check |
| **Project Overview** | `README.md` (EN) / `README-CN.md` (CN) / `README-JP.md` (JP) — Version, modules, timeline | ✅ Must check |
| **Changelog** | `CHANGELOG.md` — New version entries (Added/Changed/Fixed) | ✅ Must check |
| **Status Doc** | `docs/PROJECT_STATUS.md` — Current version, module list, test summary | ✅ Must check |
| **Config** | `CONFIGURATION.md` — New external integration config options | 🔍 If has integrations |
| **API Docs** | Update interface docs if API changes | 🔍 If API changed |
| **Install Deps** | `INSTALL.md` / `requirements.txt` — Update if new deps | 🔍 If new deps |
| **Test Plan** | Reflect new test coverage scope | 🔍 For major changes |

### Iron Rule: Cleanup Rules (Step 6)

> **Principle: Process docs and temporary artifacts should NOT remain in codebase.**

| Cleanup Category | Action | Examples |
|-----------------|--------|---------|
| Process analysis scripts | Keep valuable ones, delete one-off | `*_review.py`, `*_analysis.py` → evaluate then decide |
| Temp debug files | **Must delete** | `test_*.py.tmp`, `debug_*.py`, `*.bak.*` |
| Draft/deprecated docs | **Must delete** | `*_DRAFT.md`, `*_old.md`, `*_tmp.md` |
| Unused placeholder code | **Must delete** or replace with real impl | `pass # TODO`, `raise NotImplementedError` |
| Duplicate/redundant files | Merge or delete | Keep only latest version of same doc |

### Annotation Standards (Language Separation)

| Category | Language |
|----------|----------|
| **Documentation (SKILL.md / README.md)** | **English** |
| **README-CN.md** | **Chinese (简体)** |
| **README-JP.md** | **Japanese (日本語)** |
| **Code docstring** | **English** (Args / Returns / Example) |
| **Inline comments** | **English** (explaining business logic) |

---

## Test Coverage

| Module | Tests | Status |
|--------|-------|--------|
| Core (Dispatcher+Coordinator+Worker+Scratchpad+Consensus) | 39 | ✅ PASS |
| Role Mapping (RoleMatcher+alias resolution+bilingual keywords) | 25 | ✅ PASS |
| Upstream (Checkpoint+SemanticMatcher+Workflow+CompletionChecker) | 35 | ✅ PASS |
| MCEAdapter (CarryMem integration+type mapping+graceful degrade) | 30 | ✅ PASS |
| Contract Tests (Protocols+NullProviders+Cache+Monitor+Security) | 234 | ✅ PASS |
| V3.5 Integration (Lifecycle+ChangeRequest+Templates) | 7 | ✅ PASS |
| **P0-1 AntiRationalizationEngine** | **39** | **✅ PASS** |
| **P0-2 VerificationGate** | **42** | **✅ PASS** |
| **P0-3 IntentWorkflowMapper** | **58** | **✅ PASS** |
| **P0-4 CLI Lifecycle Commands** | **28** | **✅ PASS** |
**Total** | **537+** | **✅ ALL PASS** |

---

## Version History

- **v3.4.1** (2026-05-03): Agent Skills Quality Framework (P0) - AntiRationalizationEngine(39 tests) + VerificationGate(42 tests) + IntentWorkflowMapper(58 tests) + CLI Lifecycle Commands(28 tests) + 167 new tests + Google Agent Skills integration + 49 core modules
- **v3.4.0** (2026-05-02): 11-Phase Project Lifecycle (full/backend/frontend/internal_tool/minimal templates) + requirement change management + gate mechanism with gap reporting + WorkflowEngine lifecycle support + Natural Language Rule Collection (RuleCollector) + 560+ tests passing
- **v3.3** (2026-04-17): WorkBuddy Claw Integration - WorkBuddyClawSource(read-only bridge/INDEX search/daily logs/AI news feed) + Dispatcher AI News auto-inject + Annotation Standards (EN docs/docstring/inline) + Code comment audit (all EN) + MCE v0.4 support (tenant/permission) + Multi-language README (EN/CN/JP) + 33 new tests
- **v3.2** (2026-04-17): MVP Three Lines - E2E Full Demo(10-step flow/CLI) + Dispatcher UX Enhancement(structured/compact/detailed 3-format report) + MCEAdapter Memory Classification Adapter(lazy-load/graceful-degrade) + Delivery Workflow Iron Rule
- **v3.1** (2026-04-16): Prompt Optimization System - Dynamic Prompt Assembly(3 variants) + Skillify Closed-loop Feedback(A/B promotion) + Compression-Aware Adaptation
- **v3.0.1** (2026-04-16): Comprehensive code annotation (6 core modules 100% docstring coverage) + TestQualityGuard integration
- **v3.0** (2026-04-16): Complete redesign to Coordinator/Worker/Scratchpad architecture, 11 core modules (incl. Dispatcher+TestQualityGuard), ~710 tests all passing
- **v2.5** (2026-04-06): Memory Classification Engine integration
- **v2.4** (2026-04-01~03): Vibe Coding + Core Rules + Lifecycle recognition
- **v2.3** (2026-03-28): Multi-role code walkthrough + 3D visualization
- **v2.2** (2026-03-21): Long-running Agent (Checkpoint + Handoff)
- **v2.1** (2026-03-17): Dual-layer context + AI semantic matching
- **v2.0/v1.0** (2026-03-16): Initial release
