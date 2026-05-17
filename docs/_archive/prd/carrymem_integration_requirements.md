# CarryMem Integration Requirements

> **From**: DevSquad Team
> **To**: CarryMem Team
> **Date**: 2026-05-01
> **Version**: V3.4.0
> **Status**: Requirements for CarryMem-side implementation

---

## 1. Overview

DevSquad has completed its side of the CarryMem integration. This document specifies the interfaces and behaviors that CarryMem needs to implement to complete the integration.

**Core Principle**: DevSquad works independently without CarryMem. With CarryMem connected, each Agent gets personalized rule injection for enhanced output quality.

---

## 2. Protocol Interface: MemoryProvider

DevSquad defines the following Protocol interface. CarryMem must provide an implementation that satisfies this contract:

```python
class MemoryProvider(Protocol):
    def get_rules(self, user_id: str, context: Optional[Dict[str, Any]] = None) -> List[str]:
        """Retrieve user rules. Returns list of rule strings."""
        ...

    def add_rule(self, user_id: str, rule: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a user rule."""
        ...

    def update_rule(self, user_id: str, rule_id: str, rule: str) -> None:
        """Update an existing user rule."""
        ...

    def delete_rule(self, user_id: str, rule_id: str) -> None:
        """Delete a user rule."""
        ...

    def is_available(self) -> bool:
        """Check if memory system is available. False triggers graceful degradation."""
        ...

    def get_stats(self) -> Dict[str, Any]:
        """Return memory statistics (total_users, total_rules, etc.)."""
        ...
```

### 2.1 Key Contract Requirements

| Requirement | Description |
|---|---|
| **`is_available()` is the first gate** | If this returns `False`, DevSquad will not call any other method |
| **All calls wrapped in try/except** | CarryMem errors must not crash DevSquad; exceptions are caught and logged |
| **Return values use `dict`** | Avoids type coupling between the two projects |
| **`get_rules()` context parameter** | Contains `{"task": str, "role": str}` for role-aware rule matching |

---

## 3. CarryMemAdapter: Extended Interface (DevSquad-side definition)

For richer integration, DevSquad also defines an extended adapter interface that CarryMem should implement:

```python
class CarryMemAdapter(Protocol):
    def is_available(self) -> bool:
        """CarryMem service availability check."""
        ...

    def match_rules(
        self,
        task_description: str,
        user_id: str,
        role: Optional[str] = None,
        max_rules: int = 5
    ) -> List[Dict]:
        """
        Match user rules based on task description.

        Each rule dict must contain:
          - rule_id: str
          - trigger: str
          - action: str
          - rule_type: "forbid" | "avoid" | "always"
          - override: bool
          - relevance_score: float (0-1)
        """
        ...

    def format_rules_as_prompt(self, rules: List[Dict]) -> str:
        """Format matched rules as injectable prompt text."""
        ...

    def log_experience(
        self,
        user_id: str,
        role: Optional[str],
        task: str,
        rules_applied: List[str],
        outcome: str,
        user_feedback: Optional[str] = None
    ) -> str:
        """Log execution experience. Returns experience ID."""
        ...
```

### 3.1 Rule Types and Their Effects in DevSquad

| Rule Type | DevSquad Behavior |
|---|---|
| `forbid` | Post-processing check: if trigger appears in output, mark as violation warning |
| `avoid` | Injected as "avoid" instruction in prompt |
| `always` | Injected as mandatory instruction in prompt |
| `override=true` | Cannot be overridden by other rules; highest priority injection |

---

## 4. CarryMem-Side Requirements

### 4.1 P0: Must-Have (for basic integration)

| ID | Requirement | Description |
|---|---|---|
| CM-001 | **Implement `MemoryProvider` Protocol** | Provide a class that satisfies all 6 methods |
| CM-002 | **`is_available()` health check** | Must return `False` when CarryMem service is down/unreachable |
| CM-003 | **`get_rules()` with role filtering** | Support `context={"role": "architect"}` to return role-specific rules |
| CM-004 | **Graceful error handling** | Never raise unhandled exceptions; return empty lists on error |
| CM-005 | **Python package installation** | `pip install carrymem` should work and expose the adapter class |

### 4.2 P1: Should-Have (for enhanced integration)

| ID | Requirement | Description |
|---|---|---|
| CM-006 | **Implement `CarryMemAdapter.match_rules()`** | Return structured rule dicts with `rule_type`, `override`, `relevance_score` |
| CM-007 | **Implement `CarryMemAdapter.format_rules_as_prompt()`** | Format rules as Markdown text suitable for prompt injection |
| CM-008 | **Implement `CarryMemAdapter.log_experience()`** | Accept execution outcomes and user feedback for rule refinement |
| CM-009 | **Rule matching by Ontology Object Type** | `trigger` should match not just natural language but also DevSquad task type identifiers (e.g., `task_type:code_review`) |
| CM-010 | **Rate limiting** | Support `max_rules` parameter to limit returned rules (prevent prompt overflow) |

### 4.3 P2: Nice-to-Have (for deep integration)

| ID | Requirement | Description |
|---|---|---|
| CM-011 | **Confidence-adjusted rule relevance** | When CarryMem has a rule contradicting an Agent assumption, automatically lower the confidence score |
| CM-012 | **Multi-adapter support** | Allow multiple CarryMem instances (e.g., personal + enterprise) to coexist |
| CM-013 | **Rule template marketplace bridge** | CarryMem rules can be packaged as DevSquad RoleTemplate for sharing |
| CM-014 | **Streaming rule updates** | Support real-time rule updates without restarting DevSquad |

---

## 5. Integration Test Checklist

When CarryMem provides an implementation, the following tests should pass:

```python
# 1. Basic availability
adapter = CarryMemAdapterImpl()
assert adapter.is_available() == True

# 2. Rule retrieval
rules = adapter.get_rules(user_id="user1", context={"task": "design API", "role": "architect"})
assert isinstance(rules, list)

# 3. Rule matching with relevance
matched = adapter.match_rules(task_description="Design REST API", user_id="user1", role="architect", max_rules=5)
assert all("rule_type" in r for r in matched)
assert all("relevance_score" in r for r in matched)

# 4. Prompt formatting
prompt_text = adapter.format_rules_as_prompt(matched)
assert isinstance(prompt_text, str)
assert len(prompt_text) > 0

# 5. Experience logging
exp_id = adapter.log_experience(user_id="user1", role="architect", task="Design API", rules_applied=["r1"], outcome="Success")
assert isinstance(exp_id, str)

# 6. Graceful degradation
adapter_broken = CarryMemAdapterImpl(service_url="http://nonexistent:9999")
assert adapter_broken.is_available() == False
rules = adapter_broken.get_rules(user_id="user1")  # Should not crash
assert rules == []
```

---

## 6. DevSquad-Side Integration Points (Already Implemented)

| Component | File | Integration |
|---|---|---|
| Protocol Definition | `protocols.py` | `MemoryProvider` Protocol |
| Null Provider | `null_providers.py` | `NullMemoryProvider` (degradation) |
| Enhanced Worker | `enhanced_worker.py` | Rule injection + forbid check + confidence scoring |
| Coordinator | `coordinator.py` | `preload_rules()` + briefing handoff |
| Agent Briefing | `agent_briefing.py` | Context-aware briefing with rule context |
| Confidence Scorer | `confidence_score.py` | 5-factor scoring with low-confidence warnings |
| MCE Adapter | `mce_adapter.py` | Existing CarryMem type mapping |

---

## 7. Contact & Collaboration

- **DevSquad Repo**: https://github.com/lulin70/DevSquad
- **Integration Spec**: `docs/architecture/protocol_interfaces_spec.md`
- **CarryMem Adapter Template**: `scripts/collaboration/mce_adapter.py`
- **Null Provider Reference**: `scripts/collaboration/null_providers.py`

For questions or clarifications, please open an issue in the DevSquad repository with the label `carrymem-integration`.
