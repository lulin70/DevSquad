---
name: tautological-test-detection
description: Detect tautological tests that re-compute implementation logic instead of verifying behavior
---

# Tautological Test Detection

## Leading Words

Detect tests whose assertions re-compute the implementation's logic rather than verifying observable behavior — a test that can never fail because it mirrors the code under test.

## Vocabulary (from GLOSSARY.md)

- **Tautological test**: A test whose assertion duplicates the implementation formula. `expect(add(a,b)).toBe(a+b)` always passes because it computes the same thing twice.
- **Seam**: A point where behavior can be swapped without editing in place. Tests should target seams, not internals.
- **Red-green (no refactor)**: TDD cycle — red (failing test) → green (make it pass) → stop. Refactoring belongs to the review skill, not the TDD loop.
- **Seams-up-front**: Before writing tests, confirm the seam exists. No seam = no testable unit.
- **Vertical slice tracer bullet**: A thin end-to-end slice that validates the architecture before fleshing out features.

## Detection Patterns

The detector scans test files for 5 tautological anti-patterns:

### Pattern 1: Re-computed Expression

The assertion recomputes the function's known formula:

```python
# BAD — tautological
def test_add():
    assert add(2, 3) == 2 + 3  # Re-computes the implementation

# GOOD — behavioral
def test_add():
    assert add(2, 3) == 5  # Hard-coded expected value
```

### Pattern 2: Self-Referential Assertion

The test passes the test's own input as the expected output:

```python
# BAD — tautological
def test_transform(data):
    result = transform(data)
    assert result == transform(data)  # Calls the same function

# GOOD — behavioral
def test_transform():
    result = transform("input")
    assert result == "expected_output"
```

### Pattern 3: Mirror Assignment

The expected value is assigned from the function's output before asserting:

```python
# BAD — tautological
def test_parse():
    expected = parse("input")
    actual = parse("input")
    assert actual == expected  # Always true

# GOOD — behavioral
def test_parse():
    assert parse("input") == {"key": "value"}
```

### Pattern 4: Constant Comparison (No Variable)

The assertion compares two constants with no test act:

```python
# BAD — tautological
def test_nothing():
    assert 1 == 1  # No function call, no act
```

### Pattern 5: Assert True With Computed Expression

`assertTrue` / `assertFalse` with a computed boolean expression:

```python
# BAD — tautological
def test_is_valid():
    assertTrue(is_valid(data))  # If is_valid returns True, this passes
    # Should assert specific properties instead

# GOOD — behavioral
def test_is_valid():
    assert is_valid(good_data) is True
    assert is_valid(bad_data) is False
```

## Process Steps

### Step 1: Confirm the Seam

Before writing a test, confirm there is a seam (interface/protocol/public API) to test against. No seam = no testable unit.

```
Use SeamsAnalyzer to scan for:
  - ABC / Protocol / @abstractmethod
  - Public methods on concrete classes
  - Module-level functions
```

### Step 2: Write the Test (Red)

Write a test that fails because the feature isn't implemented yet. If the test passes immediately, it's either tautological or the feature already exists.

### Step 3: Make It Pass (Green)

Write the minimum code to make the test pass. Do NOT refactor in this step.

### Step 4: Run Tautological Detection

After writing tests, run the detector:

```python
from scripts.collaboration.test_quality_guard import TautologicalTestDetector

detector = TautologicalTestDetector()
issues = detector.detect(test_code)
for issue in issues:
    print(f"{issue.pattern_id}: {issue.description} at line {issue.line}")
```

### Step 5: Fix Tautological Tests

Replace re-computed expressions with hard-coded expected values. If you can't determine the expected value, the test doesn't have a clear behavioral specification.

## Failure Modes

- **"It passes, so it must be right"**: A tautological test always passes but verifies nothing. Passing is not proof of correctness.
- **"I'll fix it later"**: Tautological tests accumulate technical debt. Fix them immediately.
- **"The formula is obvious"**: Even if the formula is `a + b`, hard-code `5` for `add(2, 3)`. The test should verify behavior, not re-derive the formula.
- **"Testing internals is more thorough"**: Testing private methods leads to tautological tests because internals are implementation details.

## Anti-Patterns

- `assert func(x) == func(x)` — self-referential
- `assert func(x) == x + 1` where `func` is `lambda x: x + 1` — re-computed formula
- `expected = func(x); assert func(x) == expected` — mirror assignment
- `assertTrue(func(x))` without testing the False case — one-sided assertion
- `assert 1 == 1` — no act, no assertion

## Verification Requirements

- Every test must have a hard-coded expected value (not computed from the function under test)
- Every test must call the function under test at least once (the "act")
- `assertTrue` / `assertFalse` must be paired — test both True and False cases
- Run `TautologicalTestDetector.detect()` on all new test files before merge
