# Python Naming Convention Guide for DevSquad

## Overview

This guide standardizes naming conventions for DevSquad codebase to improve consistency and maintainability.

## Core Principles

Follow [PEP 8](https://peps.python.org/pep-0008/) with DevSquad-specific clarifications.

---

## Naming Patterns

### 1. Classes

**Format**: `CapWords` (PascalCase)

```python
# ✅ Good
class MultiAgentDispatcher:
    pass

class RoleMatcher:
    pass

# ❌ Bad
class multi_agent_dispatcher:  # Use CapWords
class role_Matcher:  # Inconsistent capitalization
```

### 2. Functions and Methods

**Format**: `lowercase_with_underscores` (snake_case)

```python
# ✅ Good
def dispatch_task(self, task_description: str) -> DispatchResult:
    pass

def _build_execution_plan(self, roles: list[str]) -> ExecutionPlan:
    pass

# ❌ Bad
def dispatchTask(self, task_description: str):  # Use snake_case
def Dispatch_Task(self):  # Don't capitalize
```

### 3. Variables

**Format**: `lowercase_with_underscores` (snake_case)

```python
# ✅ Good
task_description = "Design authentication"
role_candidates = ["architect", "security"]
max_retry_count = 3

# ❌ Bad
taskDescription = "..."  # Use snake_case
RoleCandidates = [...]  # Don't capitalize
MAXRETRYCOUNT = 3  # Constants use UPPER_CASE
```

### 4. Constants

**Format**: `UPPER_CASE_WITH_UNDERSCORES`

```python
# ✅ Good
MAX_WORKERS = 10
DEFAULT_TIMEOUT = 30
ROLE_WEIGHTS = {"architect": 1.5, "tester": 1.0}

# ❌ Bad
max_workers = 10  # Use UPPER_CASE for module-level constants
MaxWorkers = 10  # Not a class
```

### 5. Private Attributes and Methods

**Format**: `_single_leading_underscore`

**Convention**: Internal implementation details not part of public API.

```python
class Coordinator:
    def __init__(self):
        # ✅ Good: Private attributes
        self._worker_index: dict[str, Worker] = {}
        self._execution_history: list[dict] = []
        self._simplicity_role: SimplicityRole | None = None
        
        # ❌ Bad: Public-looking names for internal state
        self.worker_index = {}  # Looks public but shouldn't be
        self.executionHistory = []  # Mixed naming + public
    
    def _execute_plan_batches(self, plan: ExecutionPlan) -> tuple:
        """✅ Good: Private helper method."""
        pass
    
    def execute_plan(self, plan: ExecutionPlan) -> ScheduleResult:
        """✅ Good: Public API method."""
        return self._execute_plan_batches(plan)
```

### 6. Name Mangling (Double Underscore)

**Format**: `__double_leading_underscore`

**Use case**: Prevent name collisions in subclasses (rarely needed).

```python
class BaseDispatcher:
    def __init__(self):
        self.__internal_state = {}  # Name-mangled to _BaseDispatcher__internal_state


# ⚠️ Use sparingly: Only when inheritance conflicts are expected
# ✅ Prefer single underscore (_internal_state) for most private attributes
```

### 7. Magic Methods

**Format**: `__double_underscore_both_sides__`

**Use case**: Python built-in protocol methods.

```python
class DispatchResult:
    def __init__(self, ...):
        pass
    
    def __str__(self) -> str:
        return self.to_markdown()
    
    def __repr__(self) -> str:
        return f"DispatchResult(status={self.status})"
    
    # ✅ Good: Overriding built-in methods
    # ❌ Bad: Don't invent your own __custom__ methods
```

---

## DevSquad-Specific Rules

### Rule 1: Private Attributes Use Single Underscore

**Problem**: Inconsistent naming creates confusion about API surface.

**Examples from Codebase**:

```python
# scripts/collaboration/dispatcher.py
class MultiAgentDispatcher:
    def __init__(self):
        # ❌ Current: Mixed public/private naming
        self.coordinator = Coordinator()  # Public-looking
        self.scratchpad = ScratchpadHistoryStore()  # Public-looking
        self._dispatch_history = []  # Correct (private)
        self.execution_guard = ExecutionGuard()  # Public-looking
        
        # ✅ Should be:
        self._coordinator = Coordinator()  # Internal dependency
        self._scratchpad = ScratchpadHistoryStore()  # Internal state
        self._dispatch_history = []  # Correct
        self._execution_guard = ExecutionGuard()  # Internal guard
```

**Rationale**:
- `coordinator`, `scratchpad`, `execution_guard` are internal implementation details
- External code should use `dispatch()` method, not access internals
- Single underscore signals "internal use, may change"

### Rule 2: Public API Has No Underscore

**Public methods and properties**:

```python
class MultiAgentDispatcher:
    # ✅ Public API
    def dispatch(self, task_description: str, **kwargs) -> DispatchResult:
        """Public entry point for multi-agent collaboration."""
        pass
    
    def shutdown(self) -> None:
        """Public cleanup method."""
        pass
    
    @property
    def status(self) -> dict:
        """Public status query."""
        return {"active": True, "workers": len(self._workers)}
    
    # ✅ Private helpers
    def _init_components(self) -> None:
        pass
    
    def _validate_input(self, task: str) -> bool:
        pass
```

### Rule 3: Configuration Objects Are Public

```python
@dataclass
class DispatcherConfig:
    # ✅ Public fields (dataclass configuration)
    enable_warmup: bool = True
    enable_compression: bool = True
    compression_threshold: int = 100000
    
    # Not _enable_warmup - these are intentionally public config
```

### Rule 4: Test Fixtures Can Be Public

```python
@pytest.fixture
def dispatcher():  # ✅ No underscore (pytest convention)
    return MultiAgentDispatcher()


@pytest.fixture
def mock_llm_backend():  # ✅ No underscore
    return MockBackend()
```

---

## Current Inconsistencies

### High-Priority Fixes

#### 1. Dispatcher Internal State

**File**: `scripts/collaboration/dispatcher.py`

```python
# Current (mixed)
self.coordinator = Coordinator()
self.scratchpad = ScratchpadHistoryStore()
self.batch_scheduler = BatchScheduler()
self._dispatch_history = []

# Should be (consistent private)
self._coordinator = Coordinator()
self._scratchpad = ScratchpadHistoryStore()
self._batch_scheduler = BatchScheduler()
self._dispatch_history = []
```

**Impact**: High (affects dispatcher architecture clarity)

#### 2. Worker Notifications

**File**: `scripts/collaboration/worker.py`

```python
# Current
class Worker:
    def __init__(self):
        self._notifications_outbox = []  # Private (correct)
    
    def get_pending_notifications(self):  # Public getter exposes private
        return self._notifications_outbox
```

**Should be**:
```python
class Worker:
    def __init__(self):
        self._notifications = []
    
    def get_pending_notifications(self) -> list:
        """Public API to retrieve notifications (returns copy)."""
        return list(self._notifications)  # Return copy, not internal reference
```

**Impact**: Medium (encapsulation leak)

### Medium-Priority Fixes

#### 3. Coordinator Execution History

**File**: `scripts/collaboration/coordinator.py`

```python
# Current
self._execution_history = []  # Private (correct)
# But accessed directly in tests: coordinator._execution_history


# Should provide public accessor:
@property
def execution_history(self) -> list:
    """Public read-only access to execution history."""
    return list(self._execution_history)
```

---

## Migration Strategy

### Phase 1: Document (Completed)

This guide establishes naming conventions.

### Phase 2: Non-Breaking Refactor (V4.11.0)

**Approach**: Add new private names, deprecate old public names.

```python
class MultiAgentDispatcher:
    def __init__(self):
        # New private names
        self._coordinator = Coordinator()
        self._scratchpad = ScratchpadHistoryStore()
        
        # Deprecated public aliases (backward compat)
        self.coordinator = self._coordinator  # TODO: Remove in V5.0
        self.scratchpad = self._scratchpad  # TODO: Remove in V5.0
```

### Phase 3: Breaking Change (V5.0.0)

Remove deprecated public aliases. Update all internal references.

```python
class MultiAgentDispatcher:
    def __init__(self):
        self._coordinator = Coordinator()
        self._scratchpad = ScratchpadHistoryStore()
        # coordinator and scratchpad removed
```

---

## Enforcement

### Pre-commit Hook (Future)

```python
#!/usr/bin/env python3
"""Check for naming convention violations."""

import ast
import sys


def check_class_attributes(node):
    """Check for public-looking names that should be private."""
    violations = []
    for item in ast.walk(node):
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Attribute):
                    if target.attr in ["coordinator", "scratchpad", "batch_scheduler"]:
                        violations.append(f"Line {target.lineno}: '{target.attr}' should be private (_{target.attr})")
    return violations


# ... implementation ...
```

### Linter Configuration (ruff)

```toml
# pyproject.toml
[tool.ruff.lint]
select = ["N"]  # Enable naming conventions

[tool.ruff.lint.pep8-naming]
classmethod-decorators = ["classmethod"]
staticmethod-decorators = ["staticmethod"]
```

---

## FAQ

### Q: Should all internal attributes be private?

**A**: Yes, unless they're part of the documented public API. When in doubt, use `_` prefix.

### Q: What about properties?

**A**: Properties are public API. Their backing field should be private:

```python
class Dispatcher:
    def __init__(self):
        self._status = "idle"
    
    @property
    def status(self) -> str:  # Public property
        return self._status
    
    @status.setter
    def status(self, value: str):
        self._status = value
```

### Q: Can tests access private attributes?

**A**: Yes, but only for white-box testing. Prefer testing through public API.

```python
# ✅ Good: Test through public API
def test_dispatch():
    disp = MultiAgentDispatcher()
    result = disp.dispatch("task")
    assert result.status == "success"


# ⚠️ Acceptable: White-box testing
def test_internal_state():
    disp = MultiAgentDispatcher()
    assert len(disp._dispatch_history) == 0  # OK in tests
```

### Q: What about dataclasses?

**A**: Dataclass fields are public by default. Use `_` only for truly internal fields:

```python
@dataclass
class Config:
    # Public config fields
    timeout: int = 30
    retries: int = 3
    
    # Private internal state
    _initialized: bool = field(default=False, init=False, repr=False)
```

---

## References

- [PEP 8 - Style Guide for Python Code](https://peps.python.org/pep-0008/)
- [PEP 8 - Naming Conventions](https://peps.python.org/pep-0008/#naming-conventions)
- [Python Name Mangling](https://docs.python.org/3/tutorial/classes.html#private-variables)
- Google Python Style Guide: [Naming](https://google.github.io/styleguide/pyguide.html#s3.16-naming)

---

**Status**: ✅ Documented (V4.10.1)  
**Implementation**: Non-breaking refactor in V4.11.0, breaking change in V5.0.0  
**Owner**: DevSquad maintainers
