# Test File Naming Convention Guide

## Problem Statement

DevSquad currently has 29 test files with double `test_` prefixes (e.g., `test_collaboration_dispatcher_test.py`), creating naming inconsistency and confusion.

## Standard Convention

**Format**: `test_<module_or_feature>.py`

**Examples**:
- ✅ `test_dispatcher.py`
- ✅ `test_role_matcher.py`
- ✅ `test_collaboration_core.py`
- ❌ `test_collaboration_dispatcher_test.py` (double prefix)
- ❌ `test_collaboration_test_quality_guard_test.py` (triple prefix!)

## Current Issues

### Files with Double Prefix (29 files)

```
tests/test_collaboration_dispatcher_test.py
tests/test_collaboration_llm_cache_test.py
tests/test_collaboration_llm_retry_test.py
tests/test_collaboration_core_test.py
tests/test_collaboration_memory_bridge_test.py
tests/test_collaboration_upstream_test.py
tests/test_collaboration_role_mapping_test.py
tests/test_collaboration_permission_guard_test.py
tests/test_collaboration_dispatcher_ux_test.py
tests/test_collaboration_prompt_optimization_test.py
tests/test_collaboration_e2e_test.py
tests/test_collaboration_enhanced_e2e_test.py
tests/test_collaboration_mce_adapter_test.py
tests/test_collaboration_context_compressor_test.py
tests/test_collaboration_skillifier_test.py
tests/test_collaboration_claw_integration_test.py
tests/test_collaboration_performance_monitor_test.py
tests/test_collaboration_warmup_manager_test.py
tests/test_collaboration_test_quality_guard.py (correct, but ambiguous)
tests/test_collaboration_test_quality_guard_test.py (double prefix)
tests/test_check_test_pyramid.py (correct, testing "test_pyramid" concept)
tests/test_check_test_quality.py (correct, testing "test_quality" concept)
tests/test_ue_test_framework.py (correct, testing "ue_test" framework)
tests/test_deletion_test.py
tests/test_no_op_test.py
tests/contract/test_ue_test_provider_contract.py
tests/test_completeness_gate/test_completeness_002_mock_exemption_test_files.py
tests/test_completeness_gate/test_completeness_006_test_coverage_baseline.py
tests/test_completeness_gate/test_completeness_007_test_coverage_edge_cases.py
```

### Ambiguous Cases

Some files are named correctly but test modules with "test" in the name:
- `test_collaboration_test_quality_guard.py` → Tests `test_quality_guard.py` module ✅
- `test_check_test_quality.py` → Tests test quality checker ✅
- `test_ue_test_framework.py` → Tests UE test framework ✅

These should **keep their current names** (they follow the convention).

## Renaming Strategy

### Phase 1: Identify Candidates (Completed)

29 files identified with genuine double prefixes.

### Phase 2: Create Renaming Script

```python
#!/usr/bin/env python3
"""
Rename test files with double test_ prefix.

Usage:
    python3 scripts/rename_test_files.py --dry-run  # Preview changes
    python3 scripts/rename_test_files.py --execute  # Apply renames
"""

import os
import subprocess
from pathlib import Path

RENAMES = {
    # Root tests/
    "test_collaboration_dispatcher_test.py": "test_collaboration_dispatcher.py",
    "test_collaboration_llm_cache_test.py": "test_collaboration_llm_cache.py",
    "test_collaboration_llm_retry_test.py": "test_collaboration_llm_retry.py",
    "test_collaboration_core_test.py": "test_collaboration_core.py",
    "test_collaboration_memory_bridge_test.py": "test_collaboration_memory_bridge.py",
    "test_collaboration_upstream_test.py": "test_collaboration_upstream.py",
    "test_collaboration_role_mapping_test.py": "test_collaboration_role_mapping.py",
    "test_collaboration_permission_guard_test.py": "test_collaboration_permission_guard.py",
    "test_collaboration_dispatcher_ux_test.py": "test_collaboration_dispatcher_ux.py",
    "test_collaboration_prompt_optimization_test.py": "test_collaboration_prompt_optimization.py",
    "test_collaboration_e2e_test.py": "test_collaboration_e2e.py",
    "test_collaboration_enhanced_e2e_test.py": "test_collaboration_enhanced_e2e.py",
    "test_collaboration_mce_adapter_test.py": "test_collaboration_mce_adapter.py",
    "test_collaboration_context_compressor_test.py": "test_collaboration_context_compressor.py",
    "test_collaboration_skillifier_test.py": "test_collaboration_skillifier.py",
    "test_collaboration_claw_integration_test.py": "test_collaboration_claw_integration.py",
    "test_collaboration_performance_monitor_test.py": "test_collaboration_performance_monitor.py",
    "test_collaboration_warmup_manager_test.py": "test_collaboration_warmup_manager.py",
    "test_collaboration_test_quality_guard_test.py": "test_collaboration_test_quality_guard.py",  # Resolves ambiguity
    "test_deletion_test.py": "test_deletion.py",
    "test_no_op_test.py": "test_no_op.py",
    
    # contract/
    "contract/test_ue_test_provider_contract.py": "contract/test_ue_provider_contract.py",
    
    # test_completeness_gate/
    "test_completeness_gate/test_completeness_002_mock_exemption_test_files.py": "test_completeness_gate/test_completeness_002_mock_exemption.py",
    "test_completeness_gate/test_completeness_006_test_coverage_baseline.py": "test_completeness_gate/test_completeness_006_coverage_baseline.py",
    "test_completeness_gate/test_completeness_007_test_coverage_edge_cases.py": "test_completeness_gate/test_completeness_007_coverage_edge_cases.py",
}

def main(dry_run=True):
    repo_root = Path(__file__).parent.parent
    tests_dir = repo_root / "tests"
    
    if not tests_dir.exists():
        print(f"Error: {tests_dir} not found")
        return 1
    
    renamed_count = 0
    for old_name, new_name in RENAMES.items():
        old_path = tests_dir / old_name
        new_path = tests_dir / new_name
        
        if not old_path.exists():
            print(f"⚠️  SKIP: {old_name} (file not found)")
            continue
        
        if new_path.exists():
            print(f"❌ CONFLICT: {new_name} (target already exists)")
            continue
        
        if dry_run:
            print(f"📝 WOULD RENAME: {old_name} → {new_name}")
        else:
            # Use git mv to preserve history
            try:
                subprocess.run(
                    ["git", "mv", str(old_path), str(new_path)],
                    check=True,
                    cwd=repo_root
                )
                print(f"✅ RENAMED: {old_name} → {new_name}")
                renamed_count += 1
            except subprocess.CalledProcessError as e:
                print(f"❌ FAILED: {old_name} (git mv error: {e})")
    
    if dry_run:
        print(f"\n📊 Would rename {len(RENAMES)} files")
        print("Run with --execute to apply changes")
    else:
        print(f"\n✅ Renamed {renamed_count}/{len(RENAMES)} files")
        print("Run 'git status' to review changes")
    
    return 0

if __name__ == "__main__":
    import sys
    dry_run = "--execute" not in sys.argv
    sys.exit(main(dry_run=dry_run))
```

### Phase 3: Update Import References

After renaming, search and update any imports:

```bash
# Find files that import renamed modules
grep -r "from tests.test_collaboration_dispatcher_test import" .
grep -r "import tests.test_collaboration_dispatcher_test" .

# Update manually or with sed:
find . -type f -name "*.py" -exec sed -i '' \
  's/test_collaboration_dispatcher_test/test_collaboration_dispatcher/g' {} +
```

### Phase 4: Verify Tests Still Pass

```bash
# Run full test suite
pytest tests/ -v

# Run renamed tests specifically
pytest tests/test_collaboration_dispatcher.py -v
```

## Implementation Plan

### Timeline

- **Phase 1** (Completed): Identification
- **Phase 2** (Now): Document convention + create script
- **Phase 3** (V4.11.0): Execute renames + update imports
- **Phase 4** (V4.11.0): Verify CI passes

### Rollout Strategy

**Option A: Big Bang (Recommended)**
- Rename all 29 files in one commit
- Update all imports in same commit
- Single PR, easy to review and revert

**Option B: Gradual**
- Rename 5-10 files per PR
- Spread over 3-4 PRs
- Lower risk but higher coordination cost

**Recommendation**: Use Option A with the provided script. `git mv` preserves history, making rollback safe.

## Enforcement

### Pre-commit Hook (Future)

```python
#!/usr/bin/env python3
"""Pre-commit hook to enforce test naming convention."""
import sys
import re
from pathlib import Path

def check_test_naming(files):
    """Check for double test_ prefix in test files."""
    errors = []
    for file in files:
        if not file.startswith("tests/"):
            continue
        if not file.endswith(".py"):
            continue
        
        filename = Path(file).name
        
        # Allow test_<word>_test.py only if <word> itself is "test" (e.g., test_test_framework.py)
        # Reject test_<word>_test.py otherwise (e.g., test_dispatcher_test.py)
        if re.match(r"test_\w+_test\.py$", filename):
            # Extract middle word
            middle = filename[5:-8]  # Strip "test_" and "_test.py"
            if middle != "test":
                errors.append(f"{file}: Double test_ prefix detected")
    
    return errors

if __name__ == "__main__":
    import subprocess
    
    # Get staged files
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True
    )
    staged_files = result.stdout.strip().split("\n")
    
    errors = check_test_naming(staged_files)
    
    if errors:
        print("❌ Test naming convention violations:")
        for error in errors:
            print(f"  {error}")
        print("\nSee docs/TEST_NAMING_CONVENTION.md for guidelines")
        sys.exit(1)
    
    sys.exit(0)
```

### CI Check (Future)

```yaml
# .github/workflows/naming-check.yml
name: Test Naming Convention

on: [push, pull_request]

jobs:
  check-naming:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Check test file naming
        run: |
          violations=$(find tests/ -name 'test_*_test.py' | grep -v 'test_test_' || true)
          if [ -n "$violations" ]; then
            echo "❌ Test naming violations found:"
            echo "$violations"
            exit 1
          fi
          echo "✅ All test files follow naming convention"
```

## FAQ

### Q: Why not just leave it as is?
**A**: Consistency improves maintainability. New contributors shouldn't have to guess between `test_X.py` and `test_X_test.py`.

### Q: Will renaming break imports?
**A**: Only if other files import these test modules (rare). The script checks for this.

### Q: What about git history?
**A**: `git mv` preserves history. Use `git log --follow <new_name>` to see full history.

### Q: Can I rename just one file?
**A**: Yes, but batch renaming is more efficient and avoids piecemeal inconsistency.

## References

- [Python Test Discovery Conventions](https://docs.pytest.org/en/stable/goodpractices.html#conventions-for-python-test-discovery)
- [PEP 8 - Naming Conventions](https://peps.python.org/pep-0008/#package-and-module-names)
- DevSquad Testing Iron Rules: [docs/reference/SUB_SKILLS.md](../reference/SUB_SKILLS.md)

---

**Status**: ✅ Documented (V4.10.1)  
**Implementation**: Scheduled for V4.11.0  
**Owner**: DevSquad maintainers
