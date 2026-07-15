---
name: deep-shallow-analysis
description: Deep/shallow module analysis using Matt Pocock codebase-design vocabulary
---

# Deep/Shallow Module Analysis

## Leading Words

Analyze module depth, detect premature seams, and identify deepening opportunities using Matt Pocock's codebase-design vocabulary.

## Vocabulary (from GLOSSARY.md)

- **Deep module**: Small interface + large implementation. High leverage, high locality. Best module design.
- **Shallow module**: Large interface + small implementation. Pass-through. Should be avoided.
- **Seam**: A point where behavior can be changed without editing in place. Key for testing and refactoring.
- **Deletion test**: Imagine deleting the module. If complexity disappears, it's pass-through (shallow).
- **One adapter = hypothetical seam**: A seam with only one implementation is premature.
- **Two adapters = real seam**: A seam with multiple implementations is justified.
- **The interface is the test surface**: Test against the interface, not the implementation.

## Analysis Steps

### Step 1: Identify Seams

Find all abstract base classes, protocols, and interfaces in the target module.

- Classes inheriting from `ABC`, `Protocol`, `ABCMeta`, or `Interface`
- Classes containing `@abstractmethod`-decorated methods
- Duck-typed interfaces (implicit protocols)

### Step 2: Count Adapters

For each seam, count how many concrete implementations exist.

- **0 adapters**: Dead seam — the interface exists but nothing implements it. Consider removal.
- **1 adapter**: Premature seam — the abstraction isn't justified yet. Consider inlining.
- **2+ adapters**: Real seam — the abstraction is justified. Keep the interface.

Use `YagniChecker.check_premature_seam(code)` to automate this check.

### Step 3: Apply Deletion Test

For each module, imagine deleting it:

- If complexity disappears → pass-through (shallow module). Inline it.
- If complexity remains → the module encapsulates real complexity (deep module). Keep it.

Use `RedesignAuditor.deletion_test(code)` to automate this check.

### Step 4: Identify Deepening Opportunities

Look for shallow modules that could be deepened:

- Large interface + small implementation → shallow
- Small interface + large implementation → deep
- Can the interface be simplified while keeping the implementation?
- Can the implementation be enriched without expanding the interface?

## Failure Modes

- **Premature abstraction**: Creating an interface before having 2+ implementations. Wait for the second adapter.
- **Pass-through wrapper**: A module that just delegates to another without adding logic. Inline it.
- **Interface bloat**: Adding methods to an interface that only one implementation needs. Split the interface.
- **Missing seam**: No interface where behavior needs to be swappable. Add a seam when you have 2+ variants.

## Anti-Patterns

- Creating `AbstractFooFactory` with only one `FooFactory` implementation
- Wrapper classes whose only method is `return self._inner.method()`
- Protocol classes with no runtime check (`@runtime_checkable`)
- Interface methods that throw `NotImplementedError` instead of using `@abstractmethod`
