# P2 Design Document — V4.2.1 P2 Items

**Version**: 4.2.1 (no version bump — P2 enhancements within current version)
**Date**: 2026-07-22
**Status**: Pending User Review
**Scope**: 4 P2 items (#11, #5, #21, #15) from 32-issue training-materials audit

---

## Overview

This document designs 4 P2 items selected by user consensus. Per user instruction
"做好设计，再推进", implementation begins only after this design is approved.

| # | Item | Effort | New Files | Modified Files |
|---|------|--------|-----------|----------------|
| #11 | PRD-version linkage check | Low | 0 | `check_version_consistency.py` |
| #5 | Sensitive info input interception | Medium | 0 | `input_validator.py` |
| #21 | Test pyramid distribution analysis | Medium | 2 | 0 |
| #15 | Configuration consistency audit | Medium | 2 | 0 |

**Total**: 4 new files + 2 modified files + 4 new test files = 10 files.

---

## #11: PRD-Version Linkage Check (Low Effort)

### Problem

`check_version_consistency.py` checks 24 files for version consistency but does
NOT include `docs/prd/` directory. PRD documents may reference stale version
numbers after a release, creating documentation drift.

### Current State

- `docs/prd/` contains 4 files:
  - `V3.9_PRD_Code_Intelligence.md`
  - `V3.9_Test_Plan.md`
  - `V4.1.0_PRD_Consensus_Record.md`
  - `V4.1.0_PRD_Matt_Skills_Fusion.md`
- These files are versioned (V3.9, V4.1.0 in filename) and may reference
  version numbers in content.
- `check_version_consistency.py` has 24 checkpoints using `contains` mode
  (file contains current version) and `first_match` mode (CHANGELOG).

### Design

**Approach**: Add PRD files as optional checkpoints (optional=True) using
`contains` mode. PRD files are versioned by filename (V3.9, V4.1.0), so
requiring them to contain the *current* version (4.2.1) would be wrong.
Instead, check that version references inside PRD content are internally
consistent (no stale references to older versions that should have been
updated).

**Refined approach**: Scan PRD files for version-like patterns (`v4.x.x`,
`V4.x.x`) and report any that reference versions older than the current
release minus 2 MINOR versions (grace window for historical PRDs). This
avoids false positives on intentionally historical PRD documents.

**Simpler approach (recommended)**: Add a `--check-prd` flag that scans
`docs/prd/*.md` for version references and warns if any PRD references a
version that doesn't exist in CHANGELOG. This catches typos like "v4.1.5"
when the actual version was "v4.1.5-rc1" or "v4.2.0".

**Final design (simplest viable)**: Add `docs/prd/*.md` as optional
checkpoints with `contains` mode, but check for the file's own version
tag (extracted from filename like `V3.9` → check that "3.9" appears in
content). This verifies PRD internal consistency without forcing PRDs to
reference the current release.

### Files to Modify

- `scripts/check_version_consistency.py`: Add `_prd_checkpoints()` function
  that scans `docs/prd/*.md`, extracts version from filename, verifies
  that version appears in file content. Add as optional checks.

### Tests

- `tests/test_check_version_consistency.py` (extend existing):
  - PRD file with matching version in content → PASS
  - PRD file with mismatched version → WARN (optional, non-blocking)
  - Non-existent PRD directory → skip gracefully

### CI Integration

No new CI step needed — PRD checks are integrated into existing
`check_version_consistency.py` which already runs in CI.

---

## #5: Sensitive Info Input Interception (Medium Effort)

### Problem

`InputValidator` has 40 patterns (FORBIDDEN + SUSPICIOUS + PROMPT_INJECTION)
but does NOT detect sensitive information (API keys, passwords, tokens) at
input boundaries. Users might accidentally submit secrets in prompts or
scratchpad entries, leading to:
1. Secrets logged in plaintext to dispatch audit
2. Secrets cached in LLM cache (content_cache.py)
3. Secrets transmitted to LLM backends

### Current State

- `secret_patterns.py` has 10 comprehensive `SECRET_PATTERNS`:
  openai_api_key, github_token, aws_access_key, aws_secret_key,
  generic_api_key, password, secret, bearer_token, private_key,
  connection_string
- Functions: `is_sensitive()`, `find_secrets()`, `mask_secrets()`
- Used by: `review_checkers.py`, `content_cache.py`, `tech_debt_manager.py`,
  `audit_logger.py` (output-side masking)
- NOT used by: `input_validator.py` (input-side detection)

### Design

**Approach**: Add a new `SENSITIVE_INFO` category to `InputValidator` that
uses `secret_patterns.py` patterns. When sensitive info is detected at
input, return a WARNING (not block) — the user may legitimately need to
discuss API key formats, just not leak actual keys.

**New API**:

```python
class InputValidator:
    # New category for sensitive info detection.
    SENSITIVE_INFO_PATTERNS: list[tuple[str, str]] = []  # populated from secret_patterns.py

    def scan_input(self, text: str, ...) -> dict[str, Any]:
        # Existing scan logic...
        # New: check for sensitive info patterns.
        sensitive_findings = self._check_sensitive_info(text)
        if sensitive_findings:
            result["warnings"].extend(sensitive_findings)
            result["risk_level"] = max(result["risk_level"], "warning")
        return result

    def _check_sensitive_info(self, text: str) -> list[str]:
        """Detect sensitive info patterns (API keys, passwords, tokens).

        Returns warning messages — does NOT block input (user may
        legitimately discuss key formats).
        """
        warnings = []
        for name, _ in SECRET_PATTERNS:
            matches = find_secrets(text)
            for pattern_name, matched_value in matches:
                # Mask the matched value in the warning message.
                masked = matched_value[:4] + "*" * (len(matched_value) - 4)
                warnings.append(
                    f"Sensitive info detected: {pattern_name} ({masked}). "
                    f"This will be masked in logs and cache."
                )
        return warnings
```

**Behavior**:
- WARNING level (non-blocking) — user can proceed
- Detected secrets are automatically masked in downstream logs/cache
  (already handled by `content_cache.py` and `audit_logger.py`)
- Integration with `OutputValidator` pipeline for defense-in-depth

### Files to Modify

- `scripts/collaboration/input_validator.py`:
  - Import `SECRET_PATTERNS`, `find_secrets` from `secret_patterns`
  - Add `_check_sensitive_info()` method
  - Integrate into `scan_input()` as warning-level check

### Tests

- `tests/test_input_validator_phase5.py` (extend existing):
  - Input with OpenAI API key (sk-xxx) → warning returned
  - Input with GitHub token (ghp_xxx) → warning returned
  - Input with password assignment → warning returned
  - Clean input → no warning
  - Warning is non-blocking (risk_level = "warning", not "critical")

### CI Integration

No new CI step — `InputValidator` is tested via existing test suite.

---

## #21: Test Pyramid Distribution Analysis (Medium Effort)

### Problem

No tool to analyze test pyramid distribution (unit/integration/e2e ratio).
With 5981 tests across 6 directories, there's no visibility into test
composition. A top-heavy pyramid (too many e2e, too few unit) indicates
slow test suite and brittle tests.

### Current State

- `tests/` structure:
  - `tests/unit/` — 14 files (unit tests)
  - `tests/integration/` — 9 files (integration tests)
  - `tests/e2e/` — 7 files (end-to-end tests)
  - `tests/contract/` — 7 files (contract tests)
  - `tests/smoke/` — 2 files (smoke tests)
  - `tests/external/` — 1 file (external API tests)
  - `tests/test_*.py` (root) — ~120 files (mixed, mostly unit)
- No existing tool to categorize and report distribution.

### Design

**Approach**: New script `scripts/check_test_pyramid.py` that:
1. Walks `tests/` directory
2. Categorizes each test file by location + naming convention
3. Counts test functions per category (using AST, not just file count)
4. Reports distribution + ratio + health assessment

**Categories**:
- `unit` — `tests/unit/` + root `tests/test_*.py` (default)
- `integration` — `tests/integration/`
- `e2e` — `tests/e2e/` + files matching `*_e2e.py` / `*_e2e_test.py`
- `contract` — `tests/contract/`
- `smoke` — `tests/smoke/`
- `external` — `tests/external/`

**Health Assessment** (ideal pyramid ratios):
- Unit: ≥60% (fast, isolated, numerous)
- Integration: 15-25% (module interaction)
- E2E: ≤10% (slow, brittle, few)
- Contract: 5-10% (interface verification)
- Smoke: ≤5% (deployment verification)

**Output**:

```
Test Pyramid Report (V4.2.1 P2-21)
  Total: 5981 tests across 160 files

  Layer        Files   Tests   Ratio   Status
  ─────────────────────────────────────────────
  unit           134    5200   86.9%   ✅ Healthy
  integration      9     350    5.9%   ⚠️  Low
  e2e              7     180    3.0%   ✅ Healthy
  contract         7     200    3.3%   ✅ Healthy
  smoke            2      31    0.5%   ✅ Healthy
  external         1      20    0.3%   ✅ Healthy
  ─────────────────────────────────────────────

  Assessment: Unit ratio 86.9% exceeds 60% target (healthy).
  Integration ratio 5.9% below 15% target — consider adding
  integration tests for module interaction coverage.

Exit codes:
  0 = all layers within healthy ranges
  1 = one or more layers outside healthy range (warning)
  2 = script error
```

### Files to Create

- `scripts/check_test_pyramid.py`: Main script with `TestPyramidAnalyzer` class
- `tests/test_check_test_pyramid.py`: Test suite (target 20+ tests)

### API Design

```python
@dataclass
class LayerStats:
    layer: str          # "unit", "integration", etc.
    file_count: int     # Number of test files
    test_count: int     # Number of test functions
    ratio: float        # Percentage of total

@dataclass
class PyramidReport:
    total_tests: int
    total_files: int
    layers: list[LayerStats]
    assessment: str     # "healthy" / "warning"
    issues: list[str]   # Specific issues found

class TestPyramidAnalyzer:
    HEALTHY_RANGES = {
        "unit": (0.60, 1.00),        # ≥60%
        "integration": (0.15, 0.25), # 15-25%
        "e2e": (0.00, 0.10),         # ≤10%
        "contract": (0.05, 0.10),    # 5-10%
        "smoke": (0.00, 0.05),       # ≤5%
        "external": (0.00, 0.05),    # ≤5%
    }

    def analyze(self, tests_dir: Path) -> PyramidReport: ...
    def _categorize_file(self, path: Path) -> str: ...
    def _count_tests(self, path: Path) -> int: ...  # AST-based
```

### CI Integration

Add as non-blocking CI step (informational, does not fail build):
```yaml
- name: Test pyramid analysis (added in V4.2.1 P2-21)
  run: python scripts/check_test_pyramid.py tests/ || true
```

---

## #15: Configuration Consistency Audit (Medium Effort)

### Problem

No tool to audit configuration consistency across multiple config files.
Config drift can cause subtle bugs:
- Version mismatch between `VERSION` and `pyproject.toml`
- Dependency mismatch between `requirements.txt` and `requirements.lock`
- Missing required keys in `.devsquad.yaml`
- Conflicting settings between `config/deployment.yaml` and `helm/devsquad/values.yaml`

### Current State

- `check_version_consistency.py` — checks version numbers (24 checkpoints)
- `check_dependency_sync.py` — checks dependency sync
- No unified config consistency checker

### Design

**Approach**: New script `scripts/check_config_consistency.py` that performs
cross-file consistency checks:

**Check categories**:

1. **Version consistency** (delegate to `check_version_consistency.py`)
   - Already handled, do not duplicate

2. **Dependency consistency**
   - `requirements.txt` vs `requirements.lock` — all deps in .txt must be in .lock
   - `requirements-dev.txt` vs `requirements-dev.lock` — same check
   - `pyproject.toml` dependencies vs `requirements.txt` — all in toml must be in .txt

3. **Config key presence**
   - `.devsquad.yaml` must have required keys: `version`, `quality_control`
   - `config/deployment.yaml` must have: `replicas`, `image`, `port`
   - `helm/devsquad/values.yaml` must have: `image.repository`, `image.tag`

4. **Cross-file consistency**
   - `Dockerfile` version ARG must match `VERSION` file
   - `helm/devsquad/Chart.yaml` `appVersion` must match `VERSION`
   - `config/deployment.yaml` image tag must match `VERSION`

**Output**:

```
Configuration Consistency Report (V4.2.1 P2-15)
  Checks: 15 passed, 0 failed, 2 warnings

  [PASS] requirements.txt → requirements.lock (all deps synced)
  [PASS] pyproject.toml → requirements.txt (all deps present)
  [PASS] .devsquad.yaml required keys present
  [PASS] Dockerfile ARG VERSION = 4.2.1
  [WARN] helm/devsquad/Chart.yaml appVersion = 4.2.1 (matches)
  [WARN] config/deployment.yaml missing 'port' key (using default)
  ...

Exit codes:
  0 = all critical checks passed (warnings may exist)
  1 = one or more critical checks failed
  2 = script error
```

### Files to Create

- `scripts/check_config_consistency.py`: Main script with `ConfigConsistencyChecker` class
- `tests/test_check_config_consistency.py`: Test suite (target 20+ tests)

### API Design

```python
@dataclass
class ConfigCheck:
    name: str           # "requirements_lock_sync"
    category: str       # "dependency" / "key_presence" / "cross_file"
    status: str         # "pass" / "fail" / "warn"
    message: str        # Human-readable result

class ConfigConsistencyChecker:
    def check_all(self) -> list[ConfigCheck]: ...
    def _check_dependency_sync(self) -> list[ConfigCheck]: ...
    def _check_key_presence(self) -> list[ConfigCheck]: ...
    def _check_cross_file(self) -> list[ConfigCheck]: ...
```

### CI Integration

Add as blocking CI step:
```yaml
- name: Config consistency check (added in V4.2.1 P2-15)
  run: python scripts/check_config_consistency.py
```

---

## Implementation Order

Recommended order (low → high effort, each step verifiable):

1. **#11 PRD-version check** (Low, 30 min) — extend existing script
2. **#5 Sensitive info input** (Medium, 1 hour) — integrate existing patterns
3. **#21 Test pyramid** (Medium, 1.5 hours) — new script, self-contained
4. **#15 Config consistency** (Medium, 1.5 hours) — new script, cross-file

Each item: Design → Implement → Test → CI gate → Commit.

---

## Risk Assessment

| Risk | Mitigation |
|------|-----------|
| #5 false positives on legitimate API key discussions | WARNING level (non-blocking); user can proceed |
| #21 misclassification of root-level tests | Default to "unit" category; naming override |
| #15 false positives on optional config keys | Mark optional keys as WARN, not FAIL |
| #11 false positives on historical PRDs | Optional checks (non-blocking); filename-version extraction |

---

## Success Criteria

- [ ] All 4 items implemented with tests (target: 20+ tests per new script)
- [ ] 5 CI gates green: ruff / radon / mypy / version / pytest
- [ ] No false positives on existing codebase
- [ ] CHANGELOG.md + CHANGELOG-CN.md updated
- [ ] CI workflow updated with new steps
- [ ] Git commit + push to origin/main
