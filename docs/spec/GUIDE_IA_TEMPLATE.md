# DevSquad User Guide — Information Architecture Template (P1-6)

> **Why → When → How → Verify** 层次化信息架构

---

## 📋 Table of Contents

### Phase 0: Why (Why use this feature?)
- **Value Proposition**: What problem does it solve?
- **Benefits**: What value does it provide?
- **Alternatives**: Why not other approaches?

### Phase 1: When (When should I use this?)
- **Trigger Conditions**: When to activate
- **Anti-Patterns**: When NOT to use
- **Prerequisites**: What must be in place first

### Phase 2: How (How do I use it step-by-step?)
- **Quick Start**: Minimal working example
- **Detailed Steps**: Complete walkthrough
- **Configuration**: All options explained
- **Examples**: Common use cases with code

### Phase 3: Verify (How do I know it's working correctly?)
- **Success Criteria**: Expected outcomes
- **Common Issues**: Troubleshooting guide
- **Testing**: How to validate

---

## Feature Template Example

### 1️⃣ Why: AntiRationalizationEngine

**Problem Solved**:
- AI Workers often skip quality steps with plausible excuses ("this is simple", "I'll test later")
- These shortcuts compound into technical debt over time

**Benefits**:
- Prevents 8+ common anti-patterns per role
- Injects counter-arguments automatically into Worker prompts
- Reduces technical debt accumulation by ~40% (estimated)

**Why Not Just Rules?**
- Rules can be ignored; rationalization tables address the *thinking process*
- Each excuse has a specific, evidence-based rebuttal

### 2️⃣ When: Use AntiRationalizationEngine

**✅ Trigger Conditions**:
- Any task involving code generation or modification
- Multi-AI team collaboration scenarios
- Quality-critical projects requiring consistent standards

**❌ Anti-Patterns (When NOT to use)**:
- Pure read-only tasks (documentation review only)
- Single-step trivial operations (< 5 lines)
- When token budget is extremely constrained (< 1000 tokens)

**Prerequisites**:
- QC enabled in PromptAssembler (`enable_qc=True`)
- Role assigned to Worker (for role-specific tables)

### 3️⃣ How: Implement AntiRationalizationEngine

**Quick Start**:
```python
from scripts.collaboration.anti_rationalization import get_shared_engine

engine = get_shared_engine()
content = engine.format_for_prompt("solo-coder")
print(content)  # Markdown table ready for injection
```

**Detailed Steps**:
1. Import `get_shared_engine()` singleton
2. Call `format_for_prompt(role_id)` for target role
3. Content auto-injected via PromptAssembler if QC enabled
4. Optional: Customize max entries per role with `max_entries_per_role`

**Configuration Options**:
| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_entries_per_role` | 0 (all) | Limit entries per role for token control |
| Cache size | 64 entries | Auto-eviction when exceeded |

**Example Output**:
```markdown
## Quality Guardrails
| Excuse (DO NOT think this) | Reality (follow this instead) |
|---|---|
| This is a small change | Small changes compound... |
```

### 4️⃣ Verify: Confirm It's Working

**Success Criteria**:
- [ ] Worker prompts contain "Quality Guardrails" section
- [ ] Role-specific excuses appear in prompt
- [ ] No increase in token usage beyond expected (~200 tokens/role)

**Common Issues**:
| Issue | Cause | Solution |
|-------|-------|----------|
| No guardrails in prompt | QC disabled | Enable `--no-skip-permission` or set `enable_qc=True` |
| Too many tokens | Large role table | Set `max_entries_per_role=5` |

**Validation Test**:
```bash
python3 -m pytest tests/test_anti_rationalization.py -v
# Expected: 39 tests passing
```

---

## Apply This Architecture To All Features

For each feature in DevSquad, document using the **Why→When→How→Verify** template above.

This ensures users can quickly understand:
1. **Why** they need it (value)
2. **When** to apply it (context)
3. **How** to implement it (actionable steps)
4. **Verify** it works (confidence)

---

*Template created as part of SPEC_V35_Agent_Skills_Quality_Framework P1-6*
