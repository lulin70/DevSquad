# DevSquad V4.10 - ImplementationCompletenessGate (S1 Gate) - P7 Test Plan

## Document Metadata

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Created | 2026-11-03 |
| Author | DevSquad Tester + Security |
| Status | Draft - Pending Approval |
| Phase | P7 (Test Plan) |
| Dependencies | P2 PRD, P3 Technical Design |

---

## 1. Test Strategy Overview

### 1.1 Testing Philosophy

**Core Principle**: Test the "anti-shortcut" gate itself using TDD — write tests first, then implement detectors.

**Key Challenge**: How to test a system designed to prevent AI shortcuts without creating a circular dependency?

**Solution**: Use反例数据集 (counter-example datasets) — intentionally simplified/incomplete code samples that S1 should catch.

### 1.2 Test Pyramid

```
               ┌──────────────┐
               │   E2E Tests  │  (5 scenarios)
               │  Full P8 run │
               └──────────────┘
             ┌──────────────────┐
             │ Integration Tests │  (3 scenarios)
             │ S1 + WorkflowTrace│
             │ S1 + AlertSystem  │
             └──────────────────┘
       ┌────────────────────────────┐
       │      Unit Tests            │  (15+ tests)
       │  5 detectors × 3 tests each│
       │  + threshold + mode tests  │
       └────────────────────────────┘
```

### 1.3 Coverage Goals

| Category | Target Coverage |
|----------|----------------|
| Line Coverage | ≥ 90% |
| Branch Coverage | ≥ 85% |
| Detector Coverage | 100% (all 5 detectors tested) |
| Threshold Coverage | 100% (all 3 thresholds: <90%, 90-95%, ≥95%) |
| Mode Coverage | 100% (shadow, soft, full) |

---

## 2. Unit Tests (TDD Approach)

### 2.1 MockDetector Tests

#### test_completeness_001_mock_detection_baseline

**Objective**: Verify MockDetector catches `unittest.mock` in production code.

**Test Data**:
```python
# fixtures/sample_code_with_mocks.py
from unittest.mock import Mock

def get_user_data():
    return Mock(id=1, name="test")  # ❌ Should be detected
```

**Test Steps**:
1. Create `MockDetector` instance
2. Call `detector.check([Path("fixtures/sample_code_with_mocks.py")])`
3. Assert `result["score"] == 0.0`
4. Assert `len(result["violations"]) == 1`
5. Assert `result["violations"][0]["pattern"] == "mock_import"`

**Expected Result**:
```python
{
  "score": 0.0,
  "violations": [
    {
      "file": "fixtures/sample_code_with_mocks.py",
      "line": 1,
      "pattern": "mock_import",
      "code": "from unittest.mock import Mock",
      "severity": "CRITICAL"
    }
  ],
  "exempted_files": 0
}
```

---

#### test_completeness_002_mock_exemption_test_files

**Objective**: Verify test files are exempted from Mock detection.

**Test Data**:
```python
# fixtures/test_sample.py
from unittest.mock import Mock

def test_user_service():
    mock_db = Mock()  # ✅ Should be exempted (test file)
    assert service.get_user(mock_db) is not None
```

**Test Steps**:
1. Call `detector.check([Path("fixtures/test_sample.py")])`
2. Assert `result["score"] == 1.0`
3. Assert `len(result["violations"]) == 0`
4. Assert `result["exempted_files"] == 1`

**Expected Result**: No violations (test file exempted).

---

#### test_completeness_003_mock_in_main_block

**Objective**: Verify Mocks in `if __name__ == "__main__"` blocks are exempted.

**Test Data**:
```python
# fixtures/sample_cli.py
def run_demo(config):
    pass

if __name__ == "__main__":
    from unittest.mock import Mock
    mock_config = Mock()  # ✅ Should be exempted (__main__ block)
    run_demo(mock_config)
```

**Test Steps**:
1. Call `detector.check([Path("fixtures/sample_cli.py")])`
2. Assert `result["score"] == 1.0`
3. Assert `len(result["violations"]) == 0`

**Expected Result**: No violations (__main__ block exempted).

---

### 2.2 DesignAlignmentChecker Tests

#### test_completeness_004_design_alignment_complete

**Objective**: Verify 100% alignment when all designed elements are implemented.

**Test Data**:
```markdown
# fixtures/sample_p3_design.md
## 3.1 Module Structure

### Classes

- `UserService`
  - Methods: `get_user()`, `create_user()`
- `Database`
  - Methods: `connect()`, `query()`
```

```python
# fixtures/sample_implementation.py
class UserService:
    def get_user(self, user_id):
        pass
    
    def create_user(self, name):
        pass

class Database:
    def connect(self):
        pass
    
    def query(self, sql):
        pass
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/sample_implementation.py")], Path("fixtures/sample_p3_design.md"))`
2. Assert `result["score"] == 1.0`
3. Assert `len(result["missing_elements"]) == 0`

**Expected Result**: 100% alignment (all elements implemented).

---

#### test_completeness_005_design_alignment_missing

**Objective**: Verify detection of missing designed elements.

**Test Data**:
```markdown
# fixtures/sample_p3_design.md (same as above)
```

```python
# fixtures/sample_implementation_incomplete.py
class UserService:
    def get_user(self, user_id):
        pass
    # Missing: create_user()

# Missing: Database class
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/sample_implementation_incomplete.py")], Path("fixtures/sample_p3_design.md"))`
2. Assert `result["score"] < 0.90`
3. Assert `len(result["missing_elements"]) == 2`  # create_user(), Database
4. Assert `result["violations"][0]["type"] == "design_misalignment"`

**Expected Result**: Score < 90%, 2 missing elements detected.

---

### 2.3 TestCoverageChecker Tests

#### test_completeness_006_test_coverage_complete

**Objective**: Verify 100% test coverage when all planned tests are implemented.

**Test Data**:
```markdown
# fixtures/sample_p7_testplan.md
## Test Cases

### Unit Tests

- `test_user_service_001`: Get user by ID
- `test_user_service_002`: Create new user
- `test_database_001`: Connect to database
```

```python
# fixtures/test_user_service.py
def test_user_service_001():
    assert service.get_user(1) is not None

def test_user_service_002():
    user = service.create_user("Alice")
    assert user.name == "Alice"

def test_database_001():
    db = Database()
    assert db.connect() is True
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/test_user_service.py")], Path("fixtures/sample_p7_testplan.md"))`
2. Assert `result["score"] == 1.0`
3. Assert `len(result["missing_tests"]) == 0`

**Expected Result**: 100% test coverage.

---

#### test_completeness_007_test_coverage_missing

**Objective**: Verify detection of missing test cases.

**Test Data**:
```python
# fixtures/test_user_service_incomplete.py
def test_user_service_001():
    assert service.get_user(1) is not None

# Missing: test_user_service_002, test_database_001
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/test_user_service_incomplete.py")], Path("fixtures/sample_p7_testplan.md"))`
2. Assert `result["score"] < 0.90`  # 1/3 = 33.3%
3. Assert `len(result["missing_tests"]) == 2`

**Expected Result**: Score 33.3%, 2 missing tests.

---

### 2.4 ErrorHandlingChecker Tests

#### test_completeness_008_error_handling_protected

**Objective**: Verify detection of protected I/O operations.

**Test Data**:
```python
# fixtures/sample_with_error_handling.py
import requests

def fetch_data():
    try:
        response = requests.get("https://api.example.com", timeout=5)
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API error: {e}")
        return None
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/sample_with_error_handling.py")])`
2. Assert `result["score"] == 1.0`
3. Assert `len(result["unprotected_operations"]) == 0`

**Expected Result**: 100% error handling (all ops protected).

---

#### test_completeness_009_error_handling_unprotected

**Objective**: Verify detection of unprotected I/O operations.

**Test Data**:
```python
# fixtures/sample_without_error_handling.py
import requests

def fetch_data():
    response = requests.get("https://api.example.com")  # ❌ No try-except
    return response.json()
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/sample_without_error_handling.py")])`
2. Assert `result["score"] < 0.90`
3. Assert `len(result["unprotected_operations"]) == 1`
4. Assert `result["unprotected_operations"][0]["operation"] == "requests.get"`

**Expected Result**: Score < 90%, 1 unprotected operation.

---

### 2.5 SecurityFeatureChecker Tests

#### test_completeness_010_security_hmac_present

**Objective**: Verify detection of HMAC implementation.

**Test Data**:
```markdown
# fixtures/sample_p3_with_security.md
## Security Requirements

- HMAC-SHA256 signature validation for API requests
```

```python
# fixtures/sample_with_hmac.py
import hmac
import hashlib

def verify_signature(message, signature, secret_key):
    expected = hmac.new(secret_key, message, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/sample_with_hmac.py")], Path("fixtures/sample_p3_with_security.md"))`
2. Assert `result["score"] == 1.0`
3. Assert `len(result["missing_features"]) == 0`

**Expected Result**: 100% security features implemented.

---

#### test_completeness_011_security_hmac_missing

**Objective**: Verify detection of missing HMAC implementation.

**Test Data**:
```python
# fixtures/sample_without_hmac.py
import hashlib

def verify_signature(message, signature):
    # ❌ Using MD5 instead of HMAC-SHA256
    expected = hashlib.md5(message).hexdigest()
    return expected == signature
```

**Test Steps**:
1. Call `checker.check([Path("fixtures/sample_without_hmac.py")], Path("fixtures/sample_p3_with_security.md"))`
2. Assert `result["score"] < 1.0`
3. Assert `len(result["missing_features"]) == 1`
4. Assert `result["missing_features"][0]["feature"] == "HMAC"`

**Expected Result**: Score < 100%, HMAC missing.

---

### 2.6 Threshold and Mode Tests

#### test_completeness_012_threshold_pass

**Objective**: Verify PASS verdict for completeness ≥ 95%.

**Test Data**: Mock detector results with completeness_score = 0.96

**Test Steps**:
1. Call `gate._determine_status(0.96)`
2. Assert `status == "PASS"`

**Expected Result**: PASS status.

---

#### test_completeness_013_threshold_warning

**Objective**: Verify WARNING verdict for 90% ≤ completeness < 95%.

**Test Data**: Mock detector results with completeness_score = 0.92

**Test Steps**:
1. Call `gate._determine_status(0.92)`
2. Assert `status == "WARNING"`

**Expected Result**: WARNING status.

---

#### test_completeness_014_threshold_reject

**Objective**: Verify REJECT verdict for completeness < 90%.

**Test Data**: Mock detector results with completeness_score = 0.85

**Test Steps**:
1. Call `gate._determine_status(0.85)`
2. Assert `status == "REJECT"`

**Expected Result**: REJECT status.

---

#### test_completeness_015_progressive_mode_shadow

**Objective**: Verify shadow mode downgrades REJECT → ADVISORY.

**Test Steps**:
1. Set deployment date to today (day 0)
2. Call `gate._apply_enforcement_mode("REJECT", "shadow")`
3. Assert `verdict == "ADVISORY"`

**Expected Result**: ADVISORY verdict in shadow mode.

---

#### test_completeness_016_progressive_mode_soft

**Objective**: Verify soft mode downgrades REJECT → CONDITIONAL.

**Test Steps**:
1. Set deployment date to 10 days ago (day 10)
2. Call `gate._apply_enforcement_mode("REJECT", "soft")`
3. Assert `verdict == "CONDITIONAL"`

**Expected Result**: CONDITIONAL verdict in soft mode.

---

#### test_completeness_017_progressive_mode_full

**Objective**: Verify full mode enforces REJECT.

**Test Steps**:
1. Set deployment date to 20 days ago (day 20)
2. Call `gate._apply_enforcement_mode("REJECT", "full")`
3. Assert `verdict == "REJECT"`

**Expected Result**: REJECT verdict in full mode.

---

## 3. Integration Tests

### 3.1 WorkflowTrace Integration

#### test_integration_001_workflow_trace_recording

**Objective**: Verify S1 audit events are recorded to WorkflowTrace.

**Test Steps**:
1. Initialize `ImplementationCompletenessGate` with `WorkflowTrace`
2. Run `gate.check(target_paths, plan)`
3. Query `WorkflowTrace` for events with `event == "s1_completeness_audit"`
4. Assert event count > 0
5. Assert event contains `completeness_score`, `verdict`, `violations`

**Expected Result**: S1 audit event recorded with full details.

---

### 3.2 AlertSystem Integration

#### test_integration_002_alert_system_bypass

**Objective**: Verify P1 alert is sent when S1 is bypassed.

**Test Steps**:
1. Set `DEVSQUAD_SKIP_S1=1`
2. Initialize `ImplementationCompletenessGate` with `AlertSystem`
3. Run `gate.check(target_paths, plan)`
4. Assert `alert_system.send_bypass_alert()` was called
5. Assert alert severity == "P1"

**Expected Result**: P1 bypass alert sent.

---

#### test_integration_003_alert_system_reject

**Objective**: Verify P2 alert is sent when S1 rejects in full mode.

**Test Steps**:
1. Set deployment date to 20 days ago (full mode)
2. Provide code with completeness < 90%
3. Run `gate.check(target_paths, plan)`
4. Assert `alert_system.send_threshold_violation_alert()` was called
5. Assert alert severity == "P2"

**Expected Result**: P2 threshold violation alert sent.

---

## 4. End-to-End Tests

### 4.1 E2E Scenario 1: AI Tries to Use Mock

**User Story**: AI agent attempts to use `Mock()` instead of real implementation.

**Test Steps**:
1. Create a P8 implementation with `from unittest.mock import Mock`
2. Trigger `SimplicityRole.activate()` with P8 plan
3. Assert S1 gate is triggered
4. Assert `result.verdict == "REJECT"` (or "ADVISORY" in shadow mode)
5. Assert violation message contains "Mock usage in production code"

**Expected Result**: S1 rejects the implementation.

---

### 4.2 E2E Scenario 2: AI Skips Design Module

**User Story**: AI agent skips implementing a class defined in P3 design doc.

**Test Steps**:
1. Provide P3 design with `Database` class
2. Provide implementation without `Database` class
3. Trigger S1 gate
4. Assert `result.completeness_score < 0.90`
5. Assert violation message contains "Missing class: Database"

**Expected Result**: S1 detects missing design element.

---

### 4.3 E2E Scenario 3: AI Writes Incomplete Tests

**User Story**: AI agent writes only 60% of test cases from P7 plan.

**Test Steps**:
1. Provide P7 plan with 10 test cases
2. Provide implementation with only 6 test cases
3. Trigger S1 gate
4. Assert `result.metrics["test_coverage"] == 0.60`
5. Assert `result.verdict == "REJECT"`

**Expected Result**: S1 detects incomplete test coverage.

---

### 4.4 E2E Scenario 4: AI Omits Error Handling

**User Story**: AI agent makes network calls without `try-except`.

**Test Steps**:
1. Provide code with `requests.get()` without error handling
2. Trigger S1 gate
3. Assert `result.metrics["error_handling"] < 0.90`
4. Assert violation message contains "Unprotected operation: requests.get"

**Expected Result**: S1 detects missing error handling.

---

### 4.5 E2E Scenario 5: AI Skips Security Features

**User Story**: AI agent skips implementing HMAC validation specified in P3.

**Test Steps**:
1. Provide P3 design requiring HMAC-SHA256
2. Provide implementation without `hmac.new()`
3. Trigger S1 gate
4. Assert `result.metrics["security_score"] < 1.0`
5. Assert violation message contains "Missing security feature: HMAC"

**Expected Result**: S1 detects missing security feature.

---

## 5. Performance Tests

### 5.1 Benchmark: 10-File PR (Cold Cache)

**Test Setup**:
- 10 Python files, ~200 LOC each
- P3 doc: 50 classes/functions
- P7 doc: 30 test cases
- Cold cache (no cached parse results)

**Target**: < 30 seconds

**Measurement**:
```python
import time

start = time.time()
result = gate.check(target_paths, plan)
elapsed = time.time() - start

assert elapsed < 30.0, f"Audit took {elapsed}s (expected < 30s)"
```

---

### 5.2 Benchmark: 10-File PR (Warm Cache)

**Test Setup**: Same as 5.1, but run twice (second run uses cache)

**Target**: < 5 seconds

---

### 5.3 Benchmark: 50-File PR (Cold Cache)

**Test Setup**:
- 50 Python files, ~200 LOC each
- P3 doc: 200 classes/functions
- P7 doc: 100 test cases

**Target**: < 120 seconds

---

## 6. Red-Team Tests (Adversarial)

### 6.1 Bypass Attempt 1: Hide Mock in Lambda

**Attack Vector**: AI tries to hide Mock usage in lambda function.

**Test Code**:
```python
# Attempt to bypass MockDetector
get_mock = lambda: __import__('unittest.mock').Mock()
user = get_mock()(id=1)
```

**Expected Behavior**: S1 should detect `__import__('unittest.mock')` pattern.

**Test Assertion**: `result["violations"]` contains mock detection.

---

### 6.2 Bypass Attempt 2: TODO Comments

**Attack Vector**: AI writes `# TODO: Implement HMAC` instead of actual code.

**Test Code**:
```python
def verify_signature(message, signature):
    # TODO: Implement HMAC-SHA256 validation
    return True  # ❌ Always passes
```

**Expected Behavior**: S1 should detect `pass` or `# TODO` in critical functions.

**Test Assertion**: `result["violations"]` contains placeholder detection.

---

### 6.3 Bypass Attempt 3: Path Traversal in P3 Path

**Attack Vector**: User provides malicious P3 path: `../../etc/passwd`.

**Test Code**:
```python
gate.check(target_paths, p3_doc_path=Path("../../etc/passwd"))
```

**Expected Behavior**: S1 should validate and reject path traversal.

**Test Assertion**: `ValueError` raised with "Invalid path" message.

---

## 7. Anti-Ghost Verification Tests

### 7.1 test_anti_ghost_activation_counter

**Objective**: Verify `_activation_counter` increments on every call.

**Test Steps**:
1. Call `gate.check()` 3 times
2. Assert `gate.get_activation_stats()["activation_counter"] == 3`

**Expected Result**: Counter increments correctly.

---

### 7.2 test_anti_ghost_trigger_counter

**Objective**: Verify `_trigger_counter` increments only when actually triggered.

**Test Steps**:
1. Call `gate.check()` 3 times (2 bypassed via ENV, 1 triggered)
2. Assert `gate.get_activation_stats()["trigger_counter"] == 1`

**Expected Result**: Only actual triggers counted.

---

### 7.3 test_anti_ghost_skip_counter

**Objective**: Verify `_skip_counter` increments when skipped.

**Test Steps**:
1. Set `DEVSQUAD_SKIP_S1=1`
2. Call `gate.check()` 2 times
3. Assert `gate.get_activation_stats()["skip_counter"] == 2`

**Expected Result**: Skip counter increments.

---

## 8. Test Data Management

### 8.1 Fixture Directory Structure

```
tests/
└── test_completeness_gate/
    └── fixtures/
        ├── sample_code_with_mocks.py
        ├── sample_code_clean.py
        ├── test_sample.py  (test file)
        ├── sample_cli.py  (__main__ block)
        ├── sample_p3_design.md
        ├── sample_p7_testplan.md
        ├── sample_implementation.py
        ├── sample_implementation_incomplete.py
        ├── sample_with_error_handling.py
        ├── sample_without_error_handling.py
        ├── sample_with_hmac.py
        ├── sample_without_hmac.py
        └── sample_p3_with_security.md
```

### 8.2 Golden Dataset (Manual Labels)

**Purpose**: Measure false positive/negative rates.

**Structure**:
```json
{
  "golden_dataset": [
    {
      "file": "sample_001.py",
      "ground_truth": {
        "has_mock": true,
        "is_legitimate": false,
        "reason": "Production code using Mock"
      }
    },
    {
      "file": "test_sample_002.py",
      "ground_truth": {
        "has_mock": true,
        "is_legitimate": true,
        "reason": "Test file (exempted)"
      }
    }
  ]
}
```

---

## 9. Test Execution Plan

### 9.1 Local Development (TDD Loop)

```bash
# 1. Write test (test_completeness_001)
# 2. Run test (should fail)
pytest tests/test_completeness_gate/test_completeness_001_mock_detection.py -v

# 3. Implement detector (mock_detector.py)
# 4. Run test (should pass)
pytest tests/test_completeness_gate/test_completeness_001_mock_detection.py -v

# 5. Repeat for all tests
```

### 9.2 CI Pipeline

```yaml
# .github/workflows/test.yml
name: S1 Gate Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Install dependencies
        run: pip install -r requirements-dev.txt
      - name: Run unit tests
        run: pytest tests/test_completeness_gate/ -v --cov=scripts/collaboration/gates/completeness_gate --cov-report=term-missing
      - name: Check coverage
        run: |
          coverage report --fail-under=90
      - name: Run integration tests
        run: pytest tests/test_integration_001_workflow_trace.py -v
      - name: Run E2E tests
        run: pytest tests/test_e2e_s1_gate.py -v
      - name: Run performance benchmarks
        run: pytest tests/test_performance_s1.py -v --benchmark-only
```

---

## 10. Acceptance Criteria (from P2)

| AC ID | Description | Test ID | Status |
|-------|-------------|---------|--------|
| AC-001 | S1 detects Mock in production → REJECT | test_completeness_001 | ⏸️ Pending |
| AC-002 | S1 detects missing class from P3 → REJECT | test_completeness_005 | ⏸️ Pending |
| AC-003 | S1 detects missing test from P7 → WARNING/REJECT | test_completeness_007 | ⏸️ Pending |
| AC-004 | S1 detects unprotected requests.get() → REJECT | test_completeness_009 | ⏸️ Pending |
| AC-005 | S1 detects missing HMAC → REJECT | test_completeness_011 | ⏸️ Pending |
| AC-006 | Shadow mode: REJECT → ADVISORY | test_completeness_015 | ⏸️ Pending |
| AC-007 | Soft mode: manual bypass allowed | test_completeness_016 | ⏸️ Pending |
| AC-008 | Full mode: REJECT enforced | test_completeness_017 | ⏸️ Pending |
| AC-009 | Audit < 30s for 10-file PR | test_performance_10_files | ⏸️ Pending |
| AC-010 | Memory < 500 MB for 50-file PR | test_performance_memory | ⏸️ Pending |
| AC-011 | Test coverage ≥ 90% | CI coverage gate | ⏸️ Pending |
| AC-012 | False positive rate < 10% | Golden dataset eval | ⏸️ Pending |
| AC-013 | Anti-ghost counters increment | test_anti_ghost_* | ⏸️ Pending |

---

## 11. Test Priorities

### P0 (Must Have for V4.10 Release)

- test_completeness_001-011 (5 detector baselines)
- test_completeness_012-017 (threshold + mode)
- test_integration_001-002 (WorkflowTrace + AlertSystem)
- test_e2e_scenario_1-5 (5 E2E scenarios)
- test_anti_ghost_* (3 anti-ghost tests)

### P1 (Nice to Have)

- Performance benchmarks (test_performance_*)
- Red-team tests (test_redteam_*)

### P2 (Future)

- Golden dataset false positive evaluation
- Cross-language support tests (deferred to V5.2)

---

## 12. Known Test Gaps

| Gap | Impact | Mitigation Plan |
|-----|--------|----------------|
| **G1**: Parent tracking for try-except detection | ErrorHandlingChecker may have false positives | Implement AST parent tracking in P8 |
| **G2**: No test for concurrent S1 calls | Possible race conditions in FileCache | Add thread-safety tests in P8 |
| **G3**: No test for >10MB file handling | DoS risk | Add timeout + file size limit test |
| **G4**: No test for malformed P3/P7 docs | Parser crashes | Add fuzzing tests in V5.2 |

---

## 13. Test Iron Rules (DevSquad Standard)

### Rule 1: No Status-Code-Only Tests

❌ **Bad**:
```python
def test_completeness_check():
    result = gate.check(paths, plan)
    assert result["score"] >= 0  # Too weak
```

✅ **Good**:
```python
def test_completeness_check():
    result = gate.check(paths, plan)
    assert result["score"] == 0.0  # Exact value
    assert len(result["violations"]) == 1
    assert result["violations"][0]["pattern"] == "mock_import"
```

### Rule 2: Test Data Must Be Realistic

❌ **Bad**: Empty file, trivial code
✅ **Good**: Real-world code samples with actual logic

### Rule 3: Assert on Behavior, Not Implementation

❌ **Bad**: `assert detector._internal_state == ...`
✅ **Good**: `assert result["score"] == ...`

---

## 14. Meta Iron Rule (Testing the Tester)

**Principle**: S1 gate itself must follow its own rules.

**Self-Check**:
- [ ] S1 implementation has no Mocks in production code
- [ ] S1 aligns with this P3 design document
- [ ] S1 has all test cases from this P7 plan
- [ ] S1 has error handling for all I/O operations
- [ ] S1 implements security features (HMAC for DeploymentDateStore)

**Recursive Test**: Run S1 gate on S1 gate's own code → should PASS.

---

## 15. Test Deliverables

| Deliverable | Format | Location |
|-------------|--------|----------|
| Unit Tests | pytest | `tests/test_completeness_gate/test_completeness_*.py` |
| Integration Tests | pytest | `tests/test_integration_*.py` |
| E2E Tests | pytest | `tests/test_e2e_s1_gate.py` |
| Test Fixtures | Python + Markdown | `tests/test_completeness_gate/fixtures/` |
| Golden Dataset | JSON | `tests/test_completeness_gate/golden_dataset.json` |
| Coverage Report | HTML | `htmlcov/index.html` |
| Performance Report | JSON | `benchmark_results.json` |

---

## 16. Rollout Plan with Tests

### Week 1: Shadow Mode (Day 0-6)

**Testing Activities**:
- Run unit tests (all 15 tests)
- Deploy S1 in shadow mode
- Collect audit data (≥50 audits)
- Measure false positive rate (target: < 15%)

**Metrics to Track**:
- Audit count
- Completeness score distribution
- Violation types frequency
- False positive incidents (manual review)

### Week 2: Soft Mode (Day 7-13)

**Testing Activities**:
- Run integration tests
- Deploy S1 in soft mode
- Allow manual overrides (track approval rate)
- Tune thresholds if FP rate > 10%

**Metrics to Track**:
- Override rate
- False positive rate (target: < 10%)
- Alert counts (P1, P2)

### Week 3: Full Mode (Day 14+)

**Testing Activities**:
- Run E2E tests
- Deploy S1 in full mode
- Monitor REJECT incidents
- Verify anti-ghost counters

**Metrics to Track**:
- REJECT rate
- Bypass attempts
- P8 phase coverage (target: 100%)

---

## Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Tester | DevSquad Tester | ⏸️ Pending | - |
| Security | DevSquad Security | ⏸️ Pending | - |
| Architect | DevSquad Architect | ⏸️ Pending | - |
| Tech Lead | User | ⏸️ Pending | - |

---

## Next Step

**Action Required**: User review and approval of P2 PRD, P3 Technical Design, and P7 Test Plan.

**After Approval**: Proceed to P8 Implementation phase.