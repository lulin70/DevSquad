---
name: codebase-audit
description: Audit code for YAGNI violations, premature seams, simplification opportunities, and deletion test failures
---

# Codebase Audit — YAGNI + Seam + Deletion Test

## Leading Words

Audit codebase health using four complementary techniques: YAGNI ladder (is this feature necessary?), premature seam detection (is this abstraction justified?), simplification audit (can this be simpler?), and deletion test (does this module encapsulate real complexity?).

## Vocabulary (from GLOSSARY.md)

- **YAGNI ladder**: 6-level necessity check — NECESSARY > EXPLICIT_REQUEST > DOMAIN_VALUE > CONVENIENCE > SPECULATIVE > UNNECESSARY. Security, error-handling, data-loss, test, and accessibility tasks are NEVER skipped.
- **Premature seam**: An interface (ABC/Protocol) with only one implementation. One adapter = hypothetical seam. Two adapters = real seam.
- **Deletion test**: Imagine deleting the module. If complexity disappears, it's pass-through (shallow). If complexity remains, it encapsulates real logic (deep).
- **Deepening opportunity**: A shallow module that could be deepened — simplify the interface while keeping or enriching the implementation.
- **Simplification category**: YAGNI (unnecessary feature) / STDLIB (reinventing standard library) / DUPLICATE (redundant code) / OVERENGINEERING (excessive abstraction).

## Audit Techniques

### Technique 1: YAGNI Ladder Check

Before implementing a feature, walk the YAGNI ladder to verify necessity:

```python
from scripts.collaboration.yagni_checker import YagniChecker

checker = YagniChecker()
result = checker.check(
    task_description="Add a caching layer to the user service",
    task_details={"file": "user_service.py", "lines": 45},
)
# result.level: NECESSARY / EXPLICIT_REQUEST / DOMAIN_VALUE / CONVENIENCE / SPECULATIVE / UNNECESSARY
# result.should_skip: True for CONVENIENCE and below
```

**Never-skipped categories**: Security, error-handling, data-loss prevention, testing, and accessibility tasks always return NECESSARY — they are never skipped regardless of the ladder level.

### Technique 2: Premature Seam Detection

Scan for interfaces with only one implementation — these are premature abstractions:

```python
from scripts.collaboration.yagni_checker import YagniChecker

checker = YagniChecker()
results = checker.check_premature_seam(code, file_path="repository.py")
for r in results:
    print(f"{r.seam_name}: {r.reason} (adapters: {r.adapter_count})")
```

Rules:
- **0 adapters**: Dead seam — interface exists but nothing implements it. Remove.
- **1 adapter**: Premature seam — abstraction not justified. Inline the implementation.
- **2+ adapters**: Real seam — abstraction is justified. Keep.

### Technique 3: Simplification Audit

Scan code for four categories of simplification opportunities:

```python
from scripts.collaboration.redesign_auditor import RedesignAuditor

auditor = RedesignAuditor()
findings = auditor.audit(code, context={"file_path": "service.py"})
for f in findings:
    print(f"[{f.category}] {f.description} (severity: {f.severity})")
```

Categories:
- **YAGNI**: Feature that isn't needed yet. Remove or defer.
- **STDLIB**: Code that reinvents a standard library function. Replace with `stdlib`.
- **DUPLICATE**: Redundant code that duplicates existing logic. Consolidate.
- **OVERENGINEERING**: Excessive abstraction for the current need. Simplify.

### Technique 4: Deletion Test

For each module/function, ask: "If I delete this, what breaks?"

```python
from scripts.collaboration.redesign_auditor import RedesignAuditor

auditor = RedesignAuditor()
findings = auditor.deletion_test(code, file_path="utils.py")
for f in findings:
    print(f"{f.symbol_name}: {f.description}")
    print(f"  → {f.recommendation}")
```

Interpretation:
- **Complexity disappears** → pass-through (shallow module). Inline it.
- **Complexity remains** → the module encapsulates real logic (deep module). Keep it.
- **Multiple callers break** → the module has high leverage. Definitely keep.

## Audit Workflow

### Step 1: Run YAGNI Check on Planned Features

Before implementing any feature, run `YagniChecker.check()`. If the result is CONVENIENCE or below, defer the feature.

### Step 2: Scan for Premature Seams

After writing code, run `YagniChecker.check_premature_seam()` on the new modules. Inline any single-adapter interfaces.

### Step 3: Run Simplification Audit

Run `RedesignAuditor.audit()` on the codebase. Address YAGNI and STDLIB findings first (quick wins), then DUPLICATE and OVERENGINEERING.

### Step 4: Apply Deletion Test to Existing Modules

For modules with low cohesion or suspected pass-through behavior, run `RedesignAuditor.deletion_test()`. Inline any pass-through modules.

### Step 5: Identify Deepening Opportunities

For shallow modules that can't be deleted (they have callers), look for ways to deepen them:
- Can the interface be simplified?
- Can the implementation be enriched without expanding the interface?

## Failure Modes

- **"It might be needed someday"**: YAGNI violation. Implement when needed, not before. The ladder exists to prevent speculative features.
- **"We need an interface for testability"**: Premature seam. Use duck typing or dependency injection instead of creating an ABC with one implementation.
- **"More abstraction is better"**: Overengineering. The right amount of abstraction is the minimum needed for the current requirements.
- **"I'll just wrap it"**: Pass-through wrapper. If the wrapper adds no logic, inline it. If it adds logic, it's a deep module — keep it.
- **"It's just a utility function"**: Don't dismiss small functions. A small function with a clear interface is a deep module. A large class with a bloated interface is shallow.

## Anti-Patterns

- Creating `AbstractFooFactory` with only one `FooFactory` implementation
- Wrapper classes whose only method is `return self._inner.method()`
- Adding a caching layer before measuring that it's needed
- Creating a generic framework when only one specific use case exists
- Keeping dead interfaces "for future use" (0 adapters)

## Verification Requirements

- Every interface (ABC/Protocol) must have 2+ implementations, or be marked as explicitly planned for a second adapter
- Every module must pass the deletion test — deleting it must either break callers (high leverage) or leave complexity (deep module)
- YAGNI ladder must be checked for all new features — CONVENIENCE and below must be deferred
- Simplification audit must be run on all new code before merge — YAGNI and STDLIB findings must be fixed
