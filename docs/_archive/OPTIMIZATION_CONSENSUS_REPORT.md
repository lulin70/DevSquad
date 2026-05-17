# DevSquad Optimization Consensus Report

> ⚠️ **此文档已过时** — 生成于 2026-04-18，引用的 "16 modules, ~825+ tests, 10 roles" 已不再准确。
> 当前状态：27 modules, 7 core roles, 99 unit tests。请以 README.md 为准。

> Generated: 2026-04-18 | Participants: Product Manager, Architect, Test Expert, Solo Developer, UI Designer

---

## 1. Product Essence (Consensus)

**DevSquad = Multi-Role AI Task Orchestrator**

Core value proposition: One task in → Multi-role AI collaboration → One conclusion out.

It is NOT just a "Skill" — Skill is only one integration form (Trae IDE). The core is a task orchestration engine that decomposes a task, dispatches to multiple AI roles, resolves conflicts via consensus, and delivers a unified report.

### Minimal Core (6 modules)

```
models → scratchpad → worker → coordinator → dispatcher
                        ↑
              consensus ─┘    prompt_assembler
```

Everything else (ContextCompressor, PermissionGuard, Skillifier, WarmupManager, MemoryBridge, MCE, Claw) is an optional enhancement layer.

---

## 2. Critical Findings (All Roles Agree)

### F1. Role System Broken — 5 Real vs 10 Claimed

| Source | Count | Role IDs |
|--------|-------|----------|
| `ROLE_TEMPLATES` (runtime) | **5** | architect, product-manager, tester, solo-coder, ui-designer |
| `ROLE_WEIGHTS` (consensus) | **5** | same as above |
| CLI `ROLES` | **10** | architect, pm, coder, tester, ui, devops, security, data, reviewer, optimizer |
| README.md | **10** | same as CLI |

**Double fracture:**
- 3 role IDs mismatch: `pm`→`product-manager`, `coder`→`solo-coder`, `ui`→`ui-designer`
- 5 ghost roles: `devops`, `security`, `data`, `reviewer`, `optimizer` have no prompt templates

**Impact:** User runs `--roles pm coder` → Worker gets empty prompt → success=True but empty output. Worst failure mode: silent failure.

### F2. Test Count Three-Way Contradiction

| Source | Number | Reality |
|--------|--------|---------|
| README.md badge | 41 passing | Wrong — counts test classes, not cases |
| skill-manifest.yaml | 668 | Outdated — V3.0 era count |
| SKILL.md / CLAUDE.md | ~828 | Closest to truth |
| Actual count | ~825 | All frameworks combined |

**Impact:** 41 vs 828 = 20x difference. Users cannot trust any number.

### F3. Brand Name Split

| Files using "DevSquad" | Files using "Trae Multi-Agent Skill" |
|------------------------|--------------------------------------|
| README.md, INSTALL.md, SKILL.md, CLAUDE.md, cli.py, mcp_server.py | USAGE.md, CONFIGURATION.md, CHANGELOG.md, CONTRIBUTING.md, EXAMPLES.md, QUICK_REFERENCE.md, skill-manifest.yaml |

**Impact:** New users cannot determine if these are the same project.

### F4. Version Number Fragmentation

| File | Version |
|------|---------|
| skill-manifest.yaml | 3.0.0 |
| SKILL-CN.md | V3.2 |
| SKILL.md / cli.py / mcp_server.py | V3.3 / 3.3.0 |
| dispatcher.get_status() | 3.0 |

### F5. CONTRIBUTING.md Completely Broken

- Fork URL: `trae-multi-agent` (wrong repo)
- `pip install -r requirements-dev.txt` (file doesn't exist)
- `pytest tests/ -v` (directory doesn't exist, code is in `scripts/`)
- `from src.dispatcher import AgentDispatcher` (wrong module path)
- Contact: `your-email@example.com` (placeholder)

### F6. EXAMPLES.md Shows Idealized Outputs

- Commands use non-existent parameters (`--consensus true`, `--priority high`, `--fast-track`)
- Output examples are hand-written templates, not real tool output
- References to legacy scripts (`trae_agent_dispatch.py`, `spec_tools.py`)

---

## 3. Cross-Role Q&A (Consensus Answers)

### Q1: How many roles should we claim? (PM asked, Architect answered, all agreed)

**Consensus: Claim 5 roles honestly.** Mark 5 additional roles as "planned" or "extensible."

Rationale:
- Runtime truth is 5 roles with full prompt templates
- 5 ghost roles produce empty output — claiming them as available is a functional lie
- 5 roles already deliver the core value ("multi-role collaboration")
- Over-promising 10 roles and delivering 5 is worse than honestly promising 5

**Action:** Update all docs to list 5 core roles + 5 planned roles. Add role alias mapping in code.

### Q2: What test count should we display? (PM asked, Test Expert answered)

**Consensus: Display "~825 total" with breakdown.**

Breakdown:
- Core modules (collaboration/): ~770
- Enhancement modules: ~55
- Total: ~825

**Action:** Update README badge to `825+ passing`. Update INSTALL.md verification step with accurate count. Remove "41" and "668" from all files.

### Q3: Where should role ID mapping be resolved? (Test Expert asked, Architect answered)

**Consensus: Add ROLE_ALIASES in dispatcher.py, resolve at entry point.**

```python
ROLE_ALIASES = {
    "pm": "product-manager",
    "coder": "solo-coder",
    "ui": "ui-designer",
}
```

Resolution happens in `dispatch()` and `analyze_task()` before role lookup. CLI and MCP pass short IDs, dispatcher resolves internally.

**Action:** Add ROLE_ALIASES + `resolve_role_id()` in dispatcher.py. Add corresponding tests.

### Q4: Is DevSquad a Skill or a Platform? (PM raised, all discussed)

**Consensus: DevSquad is a multi-agent orchestration engine. Skill is one integration form.**

| Integration | Method |
|-------------|--------|
| Trae IDE | skill-manifest.yaml (Skill form) |
| Claude Code | CLAUDE.md + .claude/skills/ (Skill form) |
| OpenClaw / Cursor | MCP Server (Protocol form) |
| Any IDE / Terminal | CLI / Python import (Library form) |

**Action:** Positioning text should say "Multi-Agent Orchestration Engine" not "Skill". Keep skill-manifest.yaml for Trae compatibility.

### Q5: Should we restructure docs/? (UI Designer proposed, all agreed)

**Consensus: Yes, but in phases. Phase 1 = fix inconsistencies. Phase 2 = restructure.**

Phase 1 (immediate, 1 day):
- Fix all brand names, version numbers, test counts, role counts
- Fix CONTRIBUTING.md paths
- Fix EXAMPLES.md commands

Phase 2 (next sprint, 2-3 days):
- Move non-essential .md files from root to docs/
- Reorganize docs/ into guide/ architecture/ contributing/ i18n/ archive/
- Slim README.md to <80 lines

---

## 4. Prioritized Action Items

### P0 — Functional Bugs (Must Fix Now)

| # | Action | Owner | Files |
|---|--------|-------|-------|
| P0-1 | Add ROLE_ALIASES + resolve_role_id() in dispatcher.py | Architect | dispatcher.py |
| P0-2 | Add role_mapping_test.py | Test Expert | (new file) |
| P0-3 | Unify role count to "5 core + 5 planned" across all docs | PM | README.md, SKILL.md, SKILL-CN.md, SKILL-JP.md, CLAUDE.md, cli.py, mcp_server.py, skill-manifest.yaml |
| P0-4 | Fix test count: badge → "825+ passing", remove 41/668 | Test Expert | README.md, INSTALL.md, SKILL.md, CLAUDE.md, skill-manifest.yaml |

### P1 — Trust & Credibility (Fix This Sprint)

| # | Action | Owner | Files |
|---|--------|-------|-------|
| P1-1 | Unify brand name to "DevSquad" in all files | PM | USAGE.md, CONFIGURATION.md, CHANGELOG.md, CONTRIBUTING.md, EXAMPLES.md, QUICK_REFERENCE.md, skill-manifest.yaml |
| P1-2 | Update version to 3.3.0 everywhere | Architect | skill-manifest.yaml, dispatcher.py |
| P1-3 | Rewrite CONTRIBUTING.md with correct paths/URLs | Solo Dev | CONTRIBUTING.md |
| P1-4 | Fix EXAMPLES.md — remove legacy commands, add real output | Solo Dev | EXAMPLES.md, EXAMPLES_EN.md |
| P1-5 | Update skill-manifest.yaml: name=devsquad, version=3.3.0, 16 modules | Architect | skill-manifest.yaml |
| P1-6 | Fix SKILL-CN.md slug: multi-agent-team-v3 → devsquad | PM | SKILL-CN.md |

### P2 — UX & Structure (Next Sprint)

| # | Action | Owner | Files |
|---|--------|-------|-------|
| P2-1 | Slim README.md to <80 lines, move details to docs/ | UI Designer | README.md |
| P2-2 | Move USAGE.md, CONFIGURATION.md, QUICK_REFERENCE.md, EXAMPLES*.md to docs/guide/ | UI Designer | directory restructure |
| P2-3 | Create docs/guide/ with quick-start, roles, cli-reference, api-reference | UI Designer | (new files) |
| P2-4 | Archive docs/dev/, docs/planning/, docs/vibe-coding/ multi-version files | UI Designer | docs/ cleanup |
| P2-5 | Add real output examples with verification date | Solo Dev | docs/guide/examples.md |

### P3 — Architecture (Backlog)

| # | Action | Owner | Files |
|---|--------|-------|-------|
| P3-1 | Create RoleRegistry in models.py (SSOT for roles) | Architect | models.py, dispatcher.py, cli.py |
| P3-2 | Refactor Dispatcher from God Class to Pipeline pattern | Architect | dispatcher.py |
| P3-3 | Add LLMBackend abstraction for Worker execution | Architect | worker.py |
| P3-4 | Unify test framework to pytest | Test Expert | all test files |
| P3-5 | Create metadata.json / VERSION as SSOT for project metadata | PM | (new file) |

---

## 5. Unified Project Description (Consensus)

### One-Line Definition

> **DevSquad — Multi-Agent Orchestration Engine for Software Development**

### Short Description (for README / GitHub About)

> DevSquad transforms a single AI assistant into a specialized multi-role dev team. One task in → multiple expert roles collaborate → one unified conclusion out. 5 built-in roles, Coordinator/Worker/Scratchpad architecture, cross-platform (Trae / Claude Code / MCP / CLI).

### Key Facts (Consensus Values)

| Dimension | Value |
|-----------|-------|
| Product Name | **DevSquad** |
| Tagline | Multi-Agent Orchestration Engine for Software Development |
| Version | **3.3.0** |
| Core Roles | **5** (architect, product-manager, tester, solo-coder, ui-designer) |
| Planned Roles | **5** (devops, security, data, reviewer, optimizer) |
| Core Modules | **6** (models, scratchpad, consensus, worker, coordinator, dispatcher) |
| Enhancement Modules | **10** (context-compressor, permission-guard, skillifier, warmup-manager, memory-bridge, mce-adapter, batch-scheduler, prompt-assembler, prompt-variant-generator, test-quality-guard) |
| Total Modules | **16** |
| Test Cases | **~825** |
| Architecture Pattern | Coordinator/Worker/Scratchpad |
| Skill Name/Slug | **devsquad** / **devsquad** |
| ContextCompressor | **4-level** |

---

## 6. Role Review Summary

| Role | Top Concern | Key Insight |
|------|-------------|-------------|
| **Product Manager** | Brand & trust fracture | "A product claiming multi-role collaboration can't even collaborate its own docs into consistency" |
| **Architect** | Role ID mapping broken | "5 ghost roles + 3 mismatched IDs = silent failure in production" |
| **Test Expert** | Zero coverage on role mapping | "825 tests but none verify the most critical user path: role ID resolution" |
| **Solo Developer** | Can't trust the docs | "EXAMPLES.md commands don't work, CONTRIBUTING.md paths are all wrong" |
| **UI Designer** | Cognitive overload + info inconsistency | "14 .md files in root, 3 different test counts, 2 different brand names" |

---

## 7. Next Steps

1. **Immediate (today):** Execute P0 items — fix role aliases, unify numbers, fix brand names
2. **This sprint:** Execute P1 items — rewrite CONTRIBUTING.md, fix EXAMPLES.md, update skill-manifest.yaml
3. **Next sprint:** Execute P2 items — restructure docs/, slim README, add real examples
4. **Backlog:** P3 items — RoleRegistry, Pipeline refactor, LLMBackend, test framework unification
