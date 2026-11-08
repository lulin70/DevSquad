# DevSquad V4.10 - ImplementationCompletenessGate (S1 Gate) - P2 PRD

## Document Metadata

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Created | 2026-11-03 |
| Author | DevSquad Multi-Role Team |
| Status | Draft - Pending Approval |
| Phase | P2 (Product Requirements) |
| Target Release | DevSquad V4.10 |

---

## 1. Executive Summary

### 1.1 Problem Statement

**Current Issue**: AI agents (including ourselves) often take shortcuts during implementation phase:
- Using Mock/Stub in production code instead of real implementations
- Skipping modules defined in design documents
- Writing incomplete test suites (missing test cases from test plan)
- Omitting error handling for I/O operations
- Not implementing security features specified in design

**Impact**: These shortcuts create technical debt, security vulnerabilities, and maintenance burden that violates the DevSquad Simplicity principle.

### 1.2 Solution Overview

Introduce **S1 Gate (ImplementationCompletenessGate)** as the first gate in SimplicityRole, running **before** S2 (CRAP/Duplication) to verify implementation completeness against design specifications.

**Key Principle**: "Did you build what you promised?" (S1) precedes "Did you build it well?" (S2).

### 1.3 Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Detection Rate | ≥95% | % of actual shortcuts caught by S1 |
| False Positive Rate | <10% | % of legitimate code flagged incorrectly |
| P8 Phase Coverage | 100% | % of P8 implementations audited |
| Time to Audit | <30s | Median audit time for typical PR |

---

## 2. Functional Requirements

### 2.1 Core Detection Capabilities

#### FR-001: Mock/Stub Detection (Priority: P0)

**Description**: Detect usage of test mocks in production code paths.

**Detection Patterns**:
```python
# ❌ REJECT: Mock in production code
from unittest.mock import Mock, MagicMock


def get_user_data():
    return Mock(id=1, name="test")


# ❌ REJECT: @patch in non-test file
@patch("requests.get")
def fetch_api_data(mock_get):
    pass


# ✅ PASS: Mock in test file (test_*.py)
def test_user_service():
    mock_db = Mock()
    assert service.get_user(mock_db) is not None


# ✅ PASS: Mock in __main__ block (CLI testing)
if __name__ == "__main__":
    mock_config = Mock()
    run_demo(mock_config)
```

**Exemptions**:
- Files matching `test_*.py`, `*_test.py`, `tests/**/*.py`
- Code inside `if __name__ == "__main__"` blocks
- Docstring examples

**Output**:
```python
{
    "mock_violations": [
        {
            "file": "src/user_service.py",
            "line": 15,
            "pattern": "unittest.mock.Mock",
            "context": "return Mock(id=1)",
            "severity": "CRITICAL",
        }
    ]
}
```

---

#### FR-002: Design Document Alignment (Priority: P0)

**Description**: Verify that all classes/functions defined in P3 design doc are implemented in code.

**P3 Document Format Requirements** (Machine-Parseable):

```markdown
## 3.1 Module Structure

### Classes

- `ImplementationCompletenessGate`
  - Methods: `check(target_paths) -> dict`, `_parse_p3_doc() -> dict`
  - Dependencies: `ast`, `markdown`, `Path`

- `DesignAlignmentChecker`
  - Methods: `extract_design_elements(doc_path) -> list`, `compare_with_code(code_path) -> float`
  - Dependencies: `mistletoe`, `pathlib`

### Functions

- `parse_markdown_structure(md_path: Path) -> dict`
  - Returns: `{"classes": [...], "functions": [...]}`
  - Raises: `ValueError` if invalid format
```

**Detection Logic**:
1. Parse P3 markdown → extract class/function names
2. Parse Python AST → extract implemented class/function names
3. Calculate alignment score: `implemented_count / designed_count`

**Alignment Score Calculation**:
```python
alignment_score = len(implemented_elements & designed_elements) / len(designed_elements)

# Example:
# Designed: ["ClassA", "ClassB", "function_x", "function_y"]  (4 elements)
# Implemented: ["ClassA", "function_x", "function_y"]  (3/4 implemented)
# Score: 75% → WARNING (< 90%)
```

**Output**:
```python
{
    "alignment_score": 0.75,
    "missing_elements": [{"type": "class", "name": "ClassB", "designed_in": "P3-Design.md:L42"}],
    "extra_elements": [{"type": "function", "name": "helper_func", "reason": "not_in_design"}],
}
```

---

#### FR-003: Test Plan Coverage Verification (Priority: P0)

**Description**: Ensure all test cases defined in P7 test plan are implemented.

**P7 Document Format Requirements**:

```markdown
## Test Cases

### Unit Tests

- `test_completeness_001`: Mock detection baseline
- `test_completeness_002`: P3 design alignment baseline
- `test_completeness_003`: P7 test coverage baseline

### Integration Tests

- `test_integration_001`: S1 + WorkflowTrace integration
- `test_integration_002`: S1 + AlertSystem integration
```

**Detection Logic**:
1. Parse P7 markdown → extract test case IDs (pattern: `test_\w+_\d+`)
2. Scan test files → collect implemented test functions
3. Calculate coverage: `implemented_tests / planned_tests`

**Test Discovery Methods**:
- **Option A**: `pytest --collect-only` (requires pytest installed)
- **Option B**: AST scan of `test_*.py` files for `def test_*()` functions

**Output**:
```python
{
    "test_coverage": 0.857,  # 6/7 tests implemented
    "missing_tests": [{"id": "test_completeness_007", "planned_in": "P7-TestPlan.md:L89"}],
    "extra_tests": [{"id": "test_completeness_008", "reason": "not_in_plan"}],
}
```

---

#### FR-004: Error Handling Verification (Priority: P1)

**Description**: Ensure network/file operations have proper error handling.

**Detection Patterns**:

```python
# ❌ REJECT: Network call without error handling
def fetch_data():
    response = requests.get("https://api.example.com")
    return response.json()


# ✅ PASS: With try-except
def fetch_data():
    try:
        response = requests.get("https://api.example.com", timeout=5)
        return response.json()
    except requests.RequestException as e:
        logger.error(f"API error: {e}")
        return None


# ❌ REJECT: File operation without error handling
def load_config():
    with open("config.json") as f:
        return json.load(f)


# ✅ PASS: With error handling
def load_config():
    try:
        with open("config.json") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Config error: {e}")
        return {}
```

**Risky Operations to Check**:
- Network: `requests.*`, `urllib.*`, `httpx.*`, `aiohttp.*`
- File: `open()`, `Path.read_text()`, `Path.write_text()`, `json.load()`
- External process: `subprocess.run()`, `os.system()`

**Exemptions**:
- Test files (`test_*.py`)
- Operations already inside `try-except` blocks
- Operations using context managers with implicit cleanup

**Output**:
```python
{
    "error_handling_score": 0.80,  # 4/5 operations protected
    "unprotected_operations": [
        {"file": "src/api_client.py", "line": 23, "operation": "requests.get", "severity": "HIGH"}
    ],
}
```

---

#### FR-005: Security Feature Implementation (Priority: P1)

**Description**: Verify security features specified in design are implemented.

**Security Patterns to Detect**:

```python
# ✅ PASS: HMAC signature present
import hmac
import hashlib

signature = hmac.new(secret_key, message, hashlib.sha256).hexdigest()

# ❌ WARNING: Using weak hash (no HMAC)
signature = hashlib.md5(message).hexdigest()


# ✅ PASS: Input validation present
def process_user_input(data: str):
    if not isinstance(data, str):
        raise TypeError("Expected string")
    if len(data) > 1000:
        raise ValueError("Input too long")
    if not re.fullmatch(r"[a-zA-Z0-9_]+", data):
        raise ValueError("Invalid characters")
    return sanitize(data)


# ❌ WARNING: No input validation
def process_user_input(data):
    return data.upper()
```

**Security Feature Checklist** (from P3 design):
- [ ] HMAC signature validation (`hmac.new(..., hashlib.sha256)`)
- [ ] Input type validation (`isinstance()` checks)
- [ ] Input length validation (`len(input) < threshold`)
- [ ] Input format validation (regex `re.match()` / `re.fullmatch()`)
- [ ] SQL injection prevention (parameterized queries, no string concatenation)
- [ ] Path traversal prevention (`Path.resolve()`, no `../` in user input)

**Detection Logic**:
1. Parse P3 → extract security requirements
2. Scan code AST → check for security patterns
3. Calculate security score: `implemented_security_features / required_security_features`

**Output**:
```python
{
    "security_score": 0.833,  # 5/6 features implemented
    "missing_security_features": [
        {"feature": "HMAC signature validation", "required_in": "P3-Design.md:L156", "severity": "CRITICAL"}
    ],
}
```

---

### 2.2 Threshold and Verdict Logic

#### FR-006: Completeness Score Calculation

**Overall Completeness Score**:
```python
completeness_score = weighted_average(
    [
        (mock_score, 0.20),  # 20%: No mocks in production
        (alignment_score, 0.25),  # 25%: Design alignment
        (test_coverage, 0.25),  # 25%: Test coverage
        (error_handling_score, 0.15),  # 15%: Error handling
        (security_score, 0.15),  # 15%: Security features
    ]
)

# mock_score: 1.0 if no violations, 0.0 if any violations (binary)
```

**Verdict Thresholds**:
```
completeness_score >= 0.95  → PASS
0.90 <= completeness_score < 0.95  → WARNING
completeness_score < 0.90  → REJECT
```

**Example Calculation**:
```python
mock_score = 1.0          # No mocks found
alignment_score = 0.88    # 88% design alignment (2 classes missing)
test_coverage = 0.92      # 92% test coverage (1 test missing)
error_handling = 0.85     # 85% error handling (3/20 ops unprotected)
security_score = 1.0      # 100% security features present

completeness = 0.20*1.0 + 0.25*0.88 + 0.25*0.92 + 0.15*0.85 + 0.15*1.0
             = 0.20 + 0.22 + 0.23 + 0.1275 + 0.15
             = 0.9275  → WARNING (90-95%)
```

---

### 2.3 Progressive Release Mode

#### FR-007: Enforcement Mode Management

**Three Modes** (inherited from V5.0 Simplicity):

| Mode | Timeframe | Behavior | Use Case |
|------|-----------|----------|----------|
| **Shadow** | Day 0-6 | REJECT → ADVISORY | Collect baseline data, tune thresholds |
| **Soft** | Day 7-13 | REJECT → CONDITIONAL | Allow manual override with approval |
| **Full** | Day 14+ | REJECT enforced | Production enforcement |

**Mode Determination**:
```python
def get_enforcement_mode() -> str:
    deployment_date = DeploymentDateStore.load()
    days_since = (datetime.now() - deployment_date).days
    
    if days_since < 7:
        return "shadow"
    elif days_since < 14:
        return "soft"
    else:
        return "full"
```

**Auto-Downgrade on High False Positive Rate**:
```python
if false_positive_rate > 0.10:  # >10% false positives
    logger.warning("High FP rate detected, downgrading to soft mode")
    return "soft"  # Override current mode
```

---

### 2.4 Integration Requirements

#### FR-008: WorkflowTrace Integration

Record all S1 audit events to WorkflowTrace for:
- Audit trail (who bypassed, when, why)
- False positive rate calculation
- Trend analysis (completeness over time)

**Event Schema**:
```python
{
    "event": "s1_completeness_audit",
    "timestamp": "2026-11-03T14:23:45Z",
    "phase": "P8",
    "result": {"completeness_score": 0.927, "verdict": "WARNING", "enforcement_mode": "shadow", "violations": [...]},
    "target_files": ["src/gate.py", "src/checker.py"],
    "bypass": False,
    "approver": None,
}
```

---

#### FR-009: AlertSystem Integration

Send alerts for:
- **P1 (CRITICAL)**: S1 bypass events
- **P2 (HIGH)**: Completeness < 90% in full mode
- **P2 (HIGH)**: False positive rate > 10%

**Alert Channels**:
- PagerDuty (P1 only)
- Slack (P1 + P2)

---

## 3. Non-Functional Requirements

### 3.1 Performance

| Requirement | Target |
|-------------|--------|
| Audit time (typical PR, 10 files) | < 30 seconds |
| Audit time (large PR, 50 files) | < 120 seconds |
| Memory usage | < 500 MB |
| P3/P7 document parsing cache hit rate | > 80% |

### 3.2 Reliability

| Requirement | Target |
|-------------|--------|
| False positive rate (after tuning) | < 10% |
| False negative rate | < 5% |
| Availability (gate check) | 99.9% |

### 3.3 Maintainability

- **Anti-Ghost Verification**: `_activation_counter`, `_trigger_counter`, `_skip_counter`
- **Test Coverage**: ≥ 90% (unit + integration)
- **Radon Complexity**: No functions with CRAP > 10

### 3.4 Security

- **HMAC Protection**: Deployment date protected by HMAC-SHA256
- **Input Validation**: All P3/P7 file paths validated (no path traversal)
- **Fail-Closed**: Parse errors → REJECT (never PASS on error)

---

## 4. Technical Constraints

### 4.1 Technology Stack

| Component | Technology | Rationale |
|-----------|------------|-----------|
| AST Parsing | Python `ast` (built-in) | Zero dependency, fast, reliable |
| Markdown Parsing | `markdown` + `mistletoe` | Lightweight, extensible |
| Test Discovery | `pytest --collect-only` (fallback: AST) | Standard in DevSquad ecosystem |
| Complexity Analysis | Reuse `radon` (from S2) | Consistent with V5.0 |

### 4.2 File Path Handling

- Only scan `target_paths` provided by `ExecutionPlan` (no full repo scan)
- Cache P3/P7 parsing results (key: `sha256(file_content)`)
- Timeout: 5 seconds per file (fail-safe)

### 4.3 Backward Compatibility

- S1 gate is **additive**: existing S2/S3/S4 gates unchanged
- Emergency bypass: `DEVSQUAD_SKIP_S1=1` (same as `DEVSQUAD_SKIP_SIMPLICITY=1`)
- CLI flag: `devsquad dispatch --skip-s1` (explicit bypass)

---

## 5. Out of Scope (V4.10)

The following are **explicitly excluded** from V4.10:

1. ❌ **Cross-language support**: Only Python AST (no JavaScript/TypeScript/Go)
2. ❌ **Semantic code analysis**: Only structural alignment (no AI-based code understanding)
3. ❌ **Auto-fixing**: S1 detects issues but does not auto-fix them
4. ❌ **Custom rule engine**: No user-defined completeness rules (fixed rule set)
5. ❌ **Historical trend dashboard**: Raw data collected but no visualization (defer to V5.2)

---

## 6. Dependencies

### 6.1 External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| `markdown` | ≥3.5 | Markdown parsing (P3/P7 docs) |
| `mistletoe` | ≥1.3.0 | Advanced Markdown AST |
| `pytest` | ≥7.0 (optional) | Test discovery (fallback: manual AST scan) |

### 6.2 Internal Dependencies (DevSquad V5.0)

- `SimplicityRole` (integration point)
- `AlertSystem` (PagerDuty + Slack)
- `WorkflowTrace` (event recording)
- `DeploymentDateStore` (HMAC-protected timeline)
- `UnifiedGateEngine` (gate orchestration)

---

## 7. Acceptance Criteria

### 7.1 Functional Acceptance

- [ ] **AC-001**: S1 detects `unittest.mock.Mock` in `src/user_service.py` → REJECT
- [ ] **AC-002**: S1 detects missing class from P3 design → alignment_score < 0.90 → REJECT
- [ ] **AC-003**: S1 detects missing test case from P7 plan → test_coverage < 0.90 → WARNING
- [ ] **AC-004**: S1 detects `requests.get()` without `try-except` → error_handling_score < 0.90 → REJECT
- [ ] **AC-005**: S1 detects missing HMAC in code when P3 requires it → security_score < 1.0 → REJECT
- [ ] **AC-006**: S1 in shadow mode downgrades REJECT → ADVISORY
- [ ] **AC-007**: S1 in soft mode allows manual bypass with approval
- [ ] **AC-008**: S1 in full mode enforces REJECT (no override)

### 7.2 Performance Acceptance

- [ ] **AC-009**: S1 audit completes in < 30s for 10-file PR
- [ ] **AC-010**: S1 memory usage < 500 MB for 50-file PR

### 7.3 Quality Acceptance

- [ ] **AC-011**: S1 test coverage ≥ 90%
- [ ] **AC-012**: S1 false positive rate < 10% (after 1 week shadow mode)
- [ ] **AC-013**: S1 anti-ghost counters: `_activation_counter > 0`, `_trigger_counter > 0`

---

## 8. Risks and Mitigations

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| **R-001**: High false positive rate (legitimate code flagged) | Medium | High | Run shadow mode for 2 weeks, collect data, tune thresholds |
| **R-002**: Performance degradation (slow audits) | Low | Medium | Cache P3/P7 parsing, limit scan to `target_paths`, 5s timeout per file |
| **R-003**: P3/P7 doc format inconsistency | High | Medium | Define strict machine-parseable format in this PRD, validate in P3 |
| **R-004**: AI finds bypass tricks (e.g., hiding mocks in lambda) | Medium | High | Continuous red-team testing, expand detection patterns in V5.2 |
| **R-005**: Deployment date tampering | Low | High | HMAC-SHA256 protection (already in V5.0) |

---

## 9. Success Criteria

### 9.1 Launch Criteria (V4.10 Release)

- All AC-001 to AC-013 pass
- Shadow mode data collected (≥50 audits)
- False positive rate measured < 15% (will tune to <10% in soft mode)
- Documentation complete (P2, P3, P7)
- Code review passed (security + architecture)

### 9.2 Post-Launch Metrics (30 days)

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| AI shortcut detection rate | ≥90% | Manual review of PRs |
| False positive rate (production) | <10% | WorkflowTrace events |
| P8 phase coverage | 100% | All P8 audits logged |
| Bypass rate | <5% | WorkflowTrace bypass events |

---

## 10. Appendix

### 10.1 Glossary

| Term | Definition |
|------|------------|
| **S1 Gate** | ImplementationCompletenessGate (first gate in Simplicity Role) |
| **S2 Gate** | CRAP + Duplication Gate (second gate) |
| **P3 Design Doc** | Technical design document (DevSquad Phase 3) |
| **P7 Test Plan** | Test strategy document (DevSquad Phase 7) |
| **P8 Phase** | Implementation phase (where S1 triggers) |
| **Shadow Mode** | Enforcement mode that downgrades REJECT to ADVISORY |
| **Soft Mode** | Enforcement mode that allows manual bypass |
| **Full Mode** | Enforcement mode that strictly enforces REJECT |

### 10.2 References

- DevSquad V5.0 Simplicity Role: `DevSquad-V5.0-Simplicity-P8-Test-Summary.md`
- AlertSystem: `scripts/collaboration/alert_system.py`
- SimplicityConfig: `scripts/collaboration/simplicity_config.py`
- CRAPGate: `scripts/collaboration/gates/crap_gate.py`

---

## Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Product Manager | DevSquad PM | ⏸️ Pending | - |
| Architect | DevSquad Architect | ⏸️ Pending | - |
| Security Expert | DevSquad Security | ⏸️ Pending | - |
| Tech Lead | User | ⏸️ Pending | - |

**Next Step**: Generate P3 Technical Design Document
