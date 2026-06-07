# DevSquad Team Consensus: CarryMem Integration Optimization Plan V2

> **Date**: 2026-05-01
> **Version**: V2.0 (Revised after 7-role review of CarryMem response)
> **Status**: Consensus Reached
> **Participants**: Architect, PM, Security, Tester, Coder, DevOps, UI/UX
> **Previous Version**: V1.0 (initial acceptance of CarryMem response)

---

## 0. Revision Summary

V2.0 revises V1.0 based on:
1. **Code gap analysis**: 6 P0 code items identified as not yet implemented
2. **Architecture review**: Rule injection pipeline is broken — missing `match_rules()` → `format_rules_as_prompt()` → Worker injection path
3. **Security hardening**: Three-layer defense for rule injection + Unicode normalization
4. **UX enhancement**: CLI rule status display with degradation reason

Key changes from V1.0:
- OPT-007 revised: Rule injection in Worker layer, not PromptAssembler
- Security: Two-layer defense + length check (replaces three-layer for performance)
- New: Unicode NFKC normalization for rule text (OPT-012A)
- New: CI optional CarryMem integration test job (OPT-012B)
- New: Detailed acceptance criteria with test case associations

---

## 1. Overall Assessment (Unchanged from V1.0)

CarryMem team's response is **professional and reasonable**. All decisions accepted.

| CarryMem Decision | DevSquad Position | Rationale |
|---|---|---|
| P0: `match_rules()` + `format_rules_as_prompt()` promoted | ✅ Accept | Core integration value |
| P0: `MemoryProvider` full implementation | ✅ Accept | Adapter layer independent |
| P0: `pip install carrymem[devsquad]` | ✅ Accept | Clean separation |
| P1: `log_experience()` + `max_rules` + multi-instance | ✅ Accept | Reasonable timeline |
| CM-009 Ontology matching deferred | ✅ Accept with fallback | Keyword fallback sufficient |
| CM-011 Confidence auto-adjustment deferred | ✅ Accept | DevSquad scoring works independently |
| CM-013 Rule template marketplace rejected | ✅ Accept | DevSquad RoleTemplateMarket handles this |
| CM-014 Streaming rule updates deferred | ✅ Accept | Sync mode sufficient |
| `user_id → namespace` mapping | ✅ Accept | No DevSquad code changes needed |
| `forbid ↔ never` type mapping | ✅ Accept | Extend mce_adapter.py |

---

## 2. Code Gap Analysis

### Current Implementation Status

| Component | File | Missing Methods | Impact |
|---|---|---|---|
| `MemoryProvider` Protocol | `protocols.py` | `match_rules()`, `format_rules_as_prompt()` | No structured rule matching interface |
| `NullMemoryProvider` | `null_providers.py` | `match_rules()`, `format_rules_as_prompt()` | Degradation path broken |
| `MCEAdapter` | `mce_adapter.py` | `match_rules()`, `format_rules_as_prompt()`, rule type mapping | Rule bridge missing |
| `EnhancedWorker` | `enhanced_worker.py` | `_validate_injected_rules()` | Rule injection unsafe |
| `Coordinator` | `coordinator.py` | `preload_rules()` upgrade to use `match_rules()` | Uses full rule set, no filtering |
| `PromptAssembler` | `prompt_assembler.py` | Rule injection entry point, English comments | No rule injection path, Chinese comments |
| `tests/contract/` | N/A | Entire directory missing | No contract tests |
| `pyproject.toml` | `pyproject.toml` | `carrymem[devsquad]>=0.2.8` | Wrong dependency specifier |

### Rule Injection Pipeline (Current vs Target)

```
CURRENT (broken):
  Coordinator.preload_rules() → get_rules() → List[str] → (no injection to Worker)

TARGET (complete):
  Coordinator.preload_rules() → match_rules() → List[Dict]
    → EnhancedWorker._validate_injected_rules() → safe rules
    → EnhancedWorker.execute() → inject rules into task context
    → PromptAssembler.format_rules_section() → formatted rule text
    → Worker._do_work() → LLM call with rules in prompt
    → EnhancedWorker._check_forbid_violations() → post-check
```

---

## 3. Optimization Plan

### Layer 1: Independent Implementation (No CarryMem Dependency)

| ID | Action | Owner | File | Acceptance Criteria | Test Case |
|---|---|---|---|---|---|
| **OPT-001** | Extend `MemoryProvider` Protocol | Coder | `protocols.py` | `match_rules(task_description, user_id, role, max_rules) -> List[Dict]` and `format_rules_as_prompt(rules) -> str` defined with full type annotations | `test_protocols.py::test_memory_provider_has_match_rules` |
| **OPT-002** | Extend `NullMemoryProvider` | Coder | `null_providers.py` | `match_rules()` returns `[]`, `format_rules_as_prompt()` returns `""`, `is_available()` returns `False`, no exceptions raised | `test_null_providers.py::test_null_memory_match_rules` |
| **OPT-003** | Add rule type constants | Coder | `mce_adapter.py` | `RULE_TYPES = {"forbid", "avoid", "always"}` defined; no conversion needed (CarryMem uses same types) | `test_mce_adapter_rules.py::test_rule_types` |
| **OPT-004** | MCEAdapter rule bridge methods | Coder | `mce_adapter.py` | `match_rules()` calls CarryMem when available, falls back to `_keyword_fallback_match()`; `format_rules_as_prompt()` calls CarryMem, falls back to `_format_rules_fallback()`; both wrapped in try/except | `test_mce_adapter_rules.py::test_match_rules_fallback` |
| **OPT-005** | Rule injection security validation | Security | `enhanced_worker.py` | `_validate_injected_rules()` filters: (1) InputValidator check on rule text, (2) single rule length ≤500 chars, (3) Unicode NFKC normalization, (4) skip suspicious rules silently | `test_rule_injection_security.py::test_validate_injected_rules` |
| **OPT-006** | Upgrade `preload_rules()` | Architect | `coordinator.py` | Uses `match_rules()` when available (`hasattr`), falls back to `get_rules()`; returns `Dict[str, List[Dict]]` | `test_coordinator_rules.py::test_preload_rules_with_match` |
| **OPT-007** | Worker rule injection pipeline | Coder | `enhanced_worker.py` | `execute()` calls `match_rules()` → `_validate_injected_rules()` → injects into task context; PromptAssembler gets `format_rules_section()` helper | `test_rule_injection_security.py::test_rule_injection_pipeline` |
| **OPT-008** | Contract test suite | Tester | `tests/contract/` | `test_memory_provider_contract.py` covers all 8 MemoryProvider methods; both NullProvider and MCEAdapter pass | `pytest tests/contract/ -v` |
| **OPT-009** | user_id security filter | Security | `mce_adapter.py` | `_sanitize_user_id()` blocks path traversal (`../`, `\`), SQL injection (`'`, `;`), and special chars; returns sanitized string | `test_rule_injection_security.py::test_sanitize_user_id` |
| **OPT-010** | pyproject.toml dependency update | DevOps | `pyproject.toml` | `carrymem[devsquad]>=0.2.8` in optional-dependencies; `all` target includes it | `pip install -e ".[carrymem]"` succeeds |
| **OPT-011** | PromptAssembler English comments | Coder | `prompt_assembler.py` | All Chinese comments and docstrings converted to English | `grep -c "[\u4e00-\u9fff]" prompt_assembler.py` returns 0 |
| **OPT-012** | CLI rule status display | UI/UX | `cli.py` | Shows `[CarryMem] N rules injected (X always, Y forbid)` or `[CarryMem] degraded: not installed` or `[CarryMem] degraded: version too low` | Manual verification |

### Layer 2: CarryMem v0.2.8 Integration Testing

| ID | Action | Prerequisite | Acceptance Criteria |
|---|---|---|---|
| **OPT-013** | Integration test (Phase 1+2) | CarryMem v0.2.8 | 4 integration test cases verified by CarryMem `test_devsquad_adapter.py::TestEndToEnd::test_full_workflow` |
| **OPT-014** | DevSquadAdapter verification | CarryMem v0.2.8 | `pip install carrymem[devsquad]` → `DevSquadAdapter` usable (confirmed by CarryMem v0.2.8) |
| **OPT-015** | Rule type E2E verification | CarryMem v0.2.8 | `forbid → forbid` direct passthrough (no conversion needed; types are identical between DevSquad and CarryMem) |

### Layer 3: CarryMem v0.3.0 Enhancement

| ID | Action | Prerequisite |
|---|---|---|
| **OPT-016** | `log_experience()` experience learning loop | CM-008 delivery |
| **OPT-017** | Multi-instance support verification | CM-012 delivery |
| **OPT-018** | RoleTemplateMarket rule import interface | CM-013 alternative |

---

## 4. Design Decisions

### 4.1 MCEAdapter Extension vs Independent CarryMemRuleAdapter

**Decision**: Extend MCEAdapter

**Rationale**: MCEAdapter already has CarryMem connection management, thread safety (RLock), and lazy initialization. Adding rule methods reuses this infrastructure, avoiding duplicate code.

### 4.2 Rule Injection Position

**Decision**: Worker layer injection, PromptAssembler formatting only

**Rationale**:
- PromptAssembler is responsible for template assembly, not business logic
- Rule injection is a business logic concern (match → validate → inject → post-check)
- Injection order: Role instruction → Rules → Related findings → QC injection
- Semantic flow: "Who am I" → "What rules I follow" → "What I know" → "What quality I guarantee"

**Implementation**:
```python
# In EnhancedWorker.execute():
if self._memory_provider and self._memory_provider.is_available():
    raw_rules = self._memory_provider.match_rules(
        task_description=task.description,
        user_id=task.user_id or "default",
        role=self.role_id,
        max_rules=5
    )
    safe_rules = self._validate_injected_rules(raw_rules)
    self._injected_rules = safe_rules
    # Rules injected into task context before _do_work()
```

### 4.3 preload_rules() Upgrade Strategy

**Decision**: Progressive upgrade with `hasattr` detection

```python
def preload_rules(self, task_description, user_id="default"):
    if not self.memory_provider or not self.memory_provider.is_available():
        return {}
    
    role_rules = {}
    for wid, worker in self.workers.items():
        try:
            if hasattr(self.memory_provider, 'match_rules'):
                rules = self.memory_provider.match_rules(
                    task_description=task_description,
                    user_id=user_id,
                    role=worker.role_id,
                    max_rules=5
                )
            else:
                rules = self.memory_provider.get_rules(
                    user_id=user_id,
                    context={"task": task_description, "role": worker.role_id}
                )
            if rules:
                role_rules[worker.role_id] = rules
        except Exception:
            continue
    return role_rules
```

### 4.4 Rule Injection Security Strategy

**Decision**: Two-layer defense + length check

| Layer | Check | Location | Performance Impact |
|---|---|---|---|
| Layer 1 | InputValidator + Unicode NFKC + length ≤500 | `_validate_injected_rules()` | One-time per rule set |
| Layer 2 | Length check only | `format_rules_as_prompt()` | Negligible |

**Why not three layers**: Running InputValidator again in `format_rules_as_prompt()` would double processing time with no additional security benefit since Layer 1 already validates.

**Unicode normalization**: All rule text normalized via `unicodedata.normalize('NFKC', text)` before validation to prevent Unicode homograph attacks.

### 4.5 Rule Type Mapping

**Correction**: CarryMem's RuleEngine uses `forbid` (not `never`). Rule types are identical between DevSquad and CarryMem.

```python
RULE_TYPES = {"forbid", "avoid", "always"}
```

No conversion needed — direct mapping. The `forbid ↔ never` mapping mentioned in CarryMem's response document was incorrect; CarryMem RuleEngine natively uses `forbid`.

Separate from existing memory type mapping (`CARRYMEM_TO_DEVOPSQUAD` / `DEVSQUAD_TO_CARRYMEM`) which handles knowledge/episodic/semantic types.

### 4.6 get_rules() Return Format

Per CarryMem response, `get_rules()` returns `List[str]` with type prefix:
```python
# Example: "[ALWAYS] Use SSL for all database connections (override)"
#          "[AVOID] Using MongoDB for relational data"
#          "[FORBID] Storing passwords in plain text"
```

DevSquad can parse the prefix if needed, but structured data should come from `match_rules()`.

---

## 5. Risk Assessment

| Risk | Probability | Impact | Mitigation | Owner |
|---|---|---|---|---|
| CarryMem v0.2.8 delay | Medium | High | NullProvider degradation; no blocking dependency | Architect |
| Natural language rule matching imprecise | High | Medium | Keyword fallback + relevance_score threshold | Coder |
| Rule text prompt injection | Low | High | Two-layer defense + Unicode NFKC | Security |
| `user_id` spoofing | Low | Medium | `_sanitize_user_id()` + trusted source only | Security |
| Rule injection pipeline regression | Medium | High | Contract tests + edge case tests | Tester |
| PromptAssembler Chinese comments missed | Low | Low | `grep` verification in CI | Coder |

---

## 6. Timeline

| Week | DevSquad Actions | CarryMem Dependency |
|---|---|---|
| Week 1 | OPT-001~012 (Layer 1: all independent items) | None (NullProvider for testing) |
| Week 2 | OPT-013~015 (Layer 2: integration testing) | CarryMem v0.2.8 Phase 1+2 |
| Week 3 | Bug fixes + documentation update | None |
| Week 4 | OPT-016~018 (Layer 3: enhancement) | CarryMem v0.3.0-rc |

---

## 7. Consensus

All 7 roles **approve** this revised plan (V2.0). Key agreements:

1. **Accept all CarryMem decisions** including deferrals and rejections
2. **Extend Protocol** with `match_rules()` and `format_rules_as_prompt()`
3. **Rule injection in Worker layer**, not PromptAssembler
4. **Two-layer defense** for rule injection security (InputValidator + length check)
5. **Unicode NFKC normalization** for all rule text
6. **Progressive upgrade** for `preload_rules()` with `hasattr` detection
7. **Maintain independence**: DevSquad works fully without CarryMem
8. **Contract test co-ownership**: both teams maintain protocol contract tests
9. **12 independent items** can be completed in Week 1 without CarryMem dependency

### Role Sign-offs

| Role | Sign-off | Key Concern Addressed |
|---|---|---|
| Architect | ✅ | Rule injection pipeline complete; Worker-layer injection |
| PM | ✅ | Clear timeline; acceptance criteria with test cases |
| Security | ✅ | Two-layer defense; Unicode NFKC; user_id sanitization |
| Tester | ✅ | Contract tests; edge cases; specific test file names |
| Coder | ✅ | MCEAdapter extension; CarryMem-unavailable safety |
| DevOps | ✅ | Dependency update; CI optional job |
| UI/UX | ✅ | CLI status with degradation reason; violation details |

---

*DevSquad Team — 2026-05-01 — V2.0*
