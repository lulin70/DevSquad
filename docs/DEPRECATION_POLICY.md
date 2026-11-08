# DevSquad Deprecation Policy

## Overview

This document defines the deprecation lifecycle for public APIs, CLI commands, and file paths in DevSquad.

## Deprecation Lifecycle

### Standard Cycle (3-6 months)

1. **Deprecation Announcement** (Version N)
   - Add `DeprecationWarning` to the deprecated feature
   - Document in CHANGELOG under "Deprecated" section
   - Update documentation with migration path
   - Retain full functionality

2. **Warning Escalation** (Version N+1, ~1 month later)
   - Upgrade to stderr warning for CLI usage
   - Add breaking change notice to release notes
   - Functionality still intact

3. **Removal** (Version N+2, ~3-6 months later)
   - Remove deprecated feature
   - Document in CHANGELOG under "Removed" section
   - Breaking change: major version bump required

### Expedited Cycle (< 1 month)

Used only for:
- Security vulnerabilities
- Critical bugs where the workaround is worse than removal
- Features with zero measured usage (telemetry confirms)

Requires explicit approval from maintainers.

## Deprecation Categories

### 1. Public Python API

**Scope**: Functions, classes, and methods in `scripts/collaboration/` exposed in `__all__`.

**Contract**: 
- Minimum 3 months deprecation period
- Alternatives must be available before deprecation
- Type stubs updated to mark deprecation

**Example**:
```python
def old_function() -> None:
    """Deprecated in V4.10, removed in V5.0.

    Use new_function() instead.
    """
    warnings.warn("old_function() is deprecated, use new_function()", DeprecationWarning, stacklevel=2)
    return new_function()
```

### 2. CLI Commands

**Scope**: Top-level commands in `scripts/cli.py`.

**Contract**:
- Minimum 6 months deprecation period
- Help text updated with deprecation notice
- Exit with warning but still functional

**Example**:
```bash
$ devsquad old-command
⚠️  WARNING: 'old-command' is deprecated (V4.10) and will be removed in V5.0.
   Use 'new-command' instead.
   
[command executes normally]
```

### 3. File Paths and Modules

**Scope**: Importable file locations (e.g., `scripts/dashboard.py` → `scripts/dashboard/app.py`).

**Contract**:
- Minimum 3 months deprecation period
- Create shim file with `DeprecationWarning`
- Document migration in UPGRADE_GUIDE.md

**Example**: See `scripts/dashboard.py` (deprecated V4.10.1, removed V5.0.0).

### 4. Configuration Options

**Scope**: Environment variables, config file keys.

**Contract**:
- Minimum 6 months deprecation period
- Old key still honored with warning
- New key takes precedence when both present

**Example**:
```python
if "OLD_KEY" in os.environ:
    warnings.warn("OLD_KEY is deprecated, use NEW_KEY", DeprecationWarning)
    value = os.environ.get("NEW_KEY", os.environ["OLD_KEY"])
```

## Documentation Requirements

Every deprecation must update:

1. **CHANGELOG.md** — Add entry under "Deprecated" section:
   ```markdown
   - **Feature X**: Deprecated in favor of Feature Y. Will be removed in vN.M.
     Migration: [link to guide]
   ```

2. **Inline Documentation** — Update docstrings/help text:
   ```python
   .. deprecated:: 4.10.0
      Use :func:`new_function` instead.
   ```

3. **Migration Guide** — Add section to `docs/UPGRADE_GUIDE.md`:
   ```markdown
   ### Migrating from dashboard.py to scripts.dashboard.app
   
   Before (V4.9):
   ```python
   from scripts.dashboard import main
   ```
   
   After (V4.10+):
   ```python
   from scripts.dashboard.app import main
   ```
   ```

## Removal Checklist

Before removing a deprecated feature:

- [ ] Deprecation period elapsed (3-6 months)
- [ ] No usage detected in telemetry (if available)
- [ ] Migration guide published
- [ ] Breaking change tagged in release notes
- [ ] Major version bump scheduled (if public API)

## Exception Process

To request expedited deprecation/removal:

1. Open issue with `deprecation` label
2. Justify urgency (security / critical bug / zero usage)
3. Propose alternative or workaround
4. Get approval from 2+ maintainers

## Current Deprecations

| Feature | Version | Removal | Migration |
|---------|---------|---------|-----------|
| `scripts/dashboard.py` | V4.10.1 | V5.0.0 | Use `scripts.dashboard.app` |

## References

- [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
- [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
- [Python PEP 387 (Backwards Compatibility Policy)](https://www.python.org/dev/peps/pep-0387/)
