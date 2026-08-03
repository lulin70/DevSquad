# Sub-Skills & Methodology Reference

> This document holds the detailed reference for DevSquad's 6 atomic sub-skills, the complete dispatch workflow, the 11-phase project lifecycle model, and the testing/delivery Iron Rules that govern AI-assisted development. It was extracted from `SKILL.md` during the V4.5.0 modular split (PRD §10.2).

## Layered Sub-Skill Architecture (V3.6.0)

> DevSquad provides **6 atomic sub-skills** that can be used independently or together.
> Each sub-skill is a thin wrapper (~50 lines) importing existing core modules — no duplicated logic.

```
skills/
├── dispatch/       → DispatchSkill — MultiAgentDispatcher (7-role orchestration)
├── intent/         → IntentSkill   — IntentWorkflowMapper (6 intents × 3 languages)
├── review/         → ReviewSkill   — FiveAxisConsensusEngine (5-axis code review)
├── security/       → SecuritySkill — InputValidator + OperationClassifier + PermissionGuard
├── test/           → TestSkill     — TestQualityGuard + test strategy generation
└── retrospective/  → RetroSkill    — RetrospectiveEngine + pattern extraction
```

### Sub-Skill Quick Reference

| Skill | Class | Core Method | Wraps |
|-------|-------|------------|-------|
| `dispatch` | `DispatchSkill` | `run(task, roles, mode)` | MultiAgentDispatcher |
| `intent` | `IntentSkill` | `detect(text, lang)` | IntentWorkflowMapper |
| `review` | `ReviewSkill` | `review(code, axes)` | FiveAxisConsensusEngine |
| `security` | `SecuritySkill` | `scan_input(text)` | InputValidator + OpClassifier |
| `test` | `TestSkill` | `generate_strategy(module)` | TestQualityGuard |
| `retrospective` | `RetrospectiveSkill` | `run_retrospective(results)` | RetrospectiveEngine |

#### Mock Mode Behavior

All 6 sub-skills work **without any API key** in Mock mode:

| Skill | Mock Return Value | Fidelity | Notes |
|-------|-------------------|----------|-------|
| **DispatchSkill** | Pre-built Markdown report with simulated worker results | High | Simulates all 7 roles with realistic content |
| **IntentSkill** | Detected intent + confidence score + workflow suggestion | High | Rule-based keyword matching, deterministic |
| **ReviewSkill** | Five-axis review scores + pass/warn/fail verdict | Medium | Scores follow Gaussian distribution around 0.75 |
| **SecuritySkill** | Scan result: safe/warning/critical + matched patterns | High | Pattern database is real (40 detection patterns) |
| **TestSkill** | Test strategy + quality score + improvement suggestions | Medium | Generated from task keywords |
| **RetrospectiveSkill** | Post-dispatch analysis + pattern extraction | Low-Medium | Empty history on first run, builds up over time |

**Key guarantees in Mock mode:**
- ✅ No network calls — fully offline
- ✅ Deterministic output for same input (except RetrospectiveSkill)
- ✅ Same data structure as real mode (`DispatchResult`, `ReviewResult`, etc.)
- ⚠️ Content is template-based — not LLM-generated
- ⚠️ RetrospectiveSkill needs ≥ 1 real dispatch before showing patterns

**Switching to real mode:**
```python
# Mock mode (default, no config needed)
result = skill.run("your task")

# Real mode (requires API key)
import os
result = skill.run("your task", backend="openai",
                    api_key=os.environ["OPENAI_API_KEY"])
```

### Usage Examples

```python
# Method A: Direct import (recommended for single skill use)
from skills.dispatch.handler import DispatchSkill
result = DispatchSkill().run("Fix login bug", roles=["coder", "tester"])
print(result["success"])  # True

# Method B: Via registry (recommended for dynamic/discovery use)
from skills import get_skill, list_skills
print(list_skills())  # ['dispatch', 'intent', 'review', 'security', 'test', 'retrospective']

skill = get_skill("security")
result = skill.scan_input("DROP TABLE users; --")
print(result["risk_level"])  # "critical"

# Method C: Quick one-liners
from skills.intent.handler import IntentSkill
intent = IntentSkill().detect("修复登录漏洞", lang="zh")
print(intent["intent"])  # "bug_fix"
```

### Registry API

```python
from skills import discover_all
all_skills = discover_all()  # {"dispatch": <DispatchSkill>, ...}
for name, skill in all_skills.items():
    print(f"{name}: {skill.info()['description']}")
```

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

## Project Lifecycle: 11-Phase Model (V3.6.0)

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
| Status-code-only assertion | MAJOR | Only checking `status_code` without verifying side-effects (DB write, state change, output) — Lesson: "接口 200" ≠ "功能可用" |
| `@lru_cache` without refresh | MAJOR | Config class using `@lru_cache` but no cache invalidation/refresh mechanism — Lesson: stale config causes silent bugs |

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
| **Side-Effect** | 📌 | **≥5%** | Verify DB writes / state changes / output produced — NOT just return value or status_code (Lesson: "接口 200" ≠ "功能可用") |
| **Cache Invalidation** | ♻️ | As needed | `@lru_cache` / cached config classes must test refresh/invalidation path (Lesson: stale cache = silent bugs) |

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

### Iron Rule 4: Side-Effect Verification — Never Only Check Status Code

```
❌ WRONG: Only assert HTTP status code, ignore actual system state
   response = client.post("/api/users", json=payload)
   assert response.status_code == 200          ← Side effects unverified!

✅ CORRECT: Verify side-effects (DB / state / output) in addition to status
   response = client.post("/api/users", json=payload)
   assert response.status_code == 200
   # Verify side-effects — Lesson: "接口 200" ≠ "功能可用"
   user = db.query(User).filter_by(email=payload["email"]).first()
   assert user is not None                     ← DB write verified
   assert user.is_active is True               ← State verified
   assert "welcome" in response.json()["message"]  ← Output verified
```

**Mandatory requirements**:
- API tests MUST verify at least one side-effect beyond status_code (DB row, state change, output content)
- "200 OK" only means the server didn't crash — it does NOT mean the feature works
- Auto-detected by `AntiPatternDetector` (pattern: `anti-status-code-only`)

### Iron Rule 5: User Journey First — Test From User Perspective

```
❌ WRONG: Test API endpoint in isolation, miss real-user workflow
   def test_login_api():
       response = client.post("/api/login", json={...})
       assert response.status_code == 200      ← Passes, but can user actually use the app?

✅ CORRECT: Design test as a user journey, not just an API call
   def test_user_can_access_dashboard_after_login():
       """Verify: User can log in and see their dashboard content."""
       # Step 1: User logs in
       login_resp = client.post("/api/login", json={...})
       assert login_resp.status_code == 200
       token = login_resp.json()["token"]
       # Step 2: User accesses protected resource
       headers = {"Authorization": f"Bearer {token}"}
       dashboard = client.get("/api/dashboard", headers=headers)
       assert dashboard.status_code == 200
       # Step 3: Verify user-visible content
       assert "welcome" in dashboard.json()["greeting"].lower()
```

**Mandatory requirements**:
- E2E tests MUST follow real user journeys (login → action → verify outcome)
- "接口 200" ≠ "功能可用" — API success does not guarantee user can accomplish their goal
- Test what the USER experiences, not what the API returns

### Iron Rule 6: E2E Release Gate — No Release Without E2E

```
❌ WRONG: Release after unit tests pass, skip E2E
   pytest tests/unit/  # All pass → ship it!  ← E2E never run!

✅ CORRECT: E2E is a mandatory release gate (user rule 3)
   pytest tests/unit/           # Unit tests pass
   pytest tests/integration/    # Integration tests pass
   pytest tests/e2e/            # E2E tests pass ← MANDATORY before release
   # Only release when ALL three layers pass
```

**Mandatory requirements**:
- E2E tests are a **release gate** — no release without E2E passing (user rule 3)
- E2E must simulate real user usage scenarios before any release (用户规则 3)
- E2E tests must use real components (real DB, real browser) not Mock when API requires底层对象
- Unit pass + Integration pass + E2E pass = Release ready (all three required)

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
5. **Docs are living documents** (Lesson: 文档与代码必须同步): Documentation is NOT a one-time deliverable — it must be updated synchronously with code changes. Stale docs are worse than no docs because they actively mislead. Every code change MUST trigger a doc review. Version/module/test counts must be consistent across ALL docs at ALL times.

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

### Iron Rule: Deployment Checklist — All Platform-Side Configs Included

> **Principle: Deployment checklist must include ALL platform-side configurations.**
> **Lesson: Missing platform config (nginx/CORS/DNS/cert) causes silent production failures.**

| Checklist Item | Verify |
|---------------|--------|
| **Application config** | Environment variables, feature flags, secrets loaded |
| **Platform config** | nginx routes, CORS headers, DNS records, SSL/TLS certs |
| **Infrastructure config** | Database migrations run, Redis connected, volumes mounted |
| **Monitoring config** | Alerts configured, dashboards deployed, log shipping active |
| **Network config** | Firewall rules, security groups, port mappings |

**Mandatory requirements**:
- Deployment checklist must cover ALL layers: app → platform → infra → monitoring → network
- "App starts successfully" does NOT mean deployment is complete — platform-side config matters
- Verify each config item with a concrete check command (curl, nc, redis-cli ping, etc.)

### Annotation Standards (Language Separation)

| Category | Language |
|----------|----------|
| **Documentation (SKILL.md / README.md)** | **English** |
| **README-CN.md** | **Chinese (简体)** |
| **README-JP.md** | **Japanese (日本語)** |
| **Code docstring** | **English** (Args / Returns / Example) |
| **Inline comments** | **English** (explaining business logic) |

---

Back to [SKILL.md](../../SKILL.md)
