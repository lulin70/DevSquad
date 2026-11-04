# DevSquad V5.1 - ImplementationCompletenessGate (S1 Gate) - P3 Technical Design

## Document Metadata

| Field | Value |
|-------|-------|
| Version | 1.0.0 |
| Created | 2026-11-03 |
| Author | DevSquad Architect + Coder |
| Status | Draft - Pending Approval |
| Phase | P3 (Technical Design) |
| Dependencies | P2 PRD (DevSquad-V5.1-ImplementationCompletenessGate-P2-PRD.md) |

---

## 1. Architecture Overview

### 1.1 System Context

```
┌─────────────────────────────────────────────────────────────┐
│                      SimplicityRole                         │
│                                                             │
│  activate(plan, results)                                    │
│    ↓                                                        │
│    1. S1: ImplementationCompletenessGate.check()  ← NEW    │
│    2. S2: CRAPGate.check()                                 │
│    3. S2: DuplicationGate.check()                          │
│    4. S3: DeadCodeGate.check() (planned)                   │
│    5. S4: TechDebtGate.check() (planned)                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
         ↓                      ↓                    ↓
   WorkflowTrace          AlertSystem       UnifiedGateEngine
```

### 1.2 Component Diagram

```
┌──────────────────────────────────────────────────────────┐
│         ImplementationCompletenessGate                   │
├──────────────────────────────────────────────────────────┤
│  + check(target_paths, plan) -> dict                     │
│  - _calculate_completeness_score(results) -> float       │
│  - _determine_verdict(score, mode) -> str               │
├──────────────────────────────────────────────────────────┤
│  Dependencies:                                           │
│    • MockDetector                                        │
│    • DesignAlignmentChecker                             │
│    • TestCoverageChecker                                │
│    • ErrorHandlingChecker                               │
│    • SecurityFeatureChecker                             │
└──────────────────────────────────────────────────────────┘
              ↓           ↓           ↓
   ┌──────────────┐  ┌────────────┐  ┌──────────────┐
   │ ASTAnalyzer  │  │  MarkdownParser │  TestDiscovery│
   │              │  │                │  │            │
   │ • parse()    │  │ • parse_p3()   │  │ • discover()│
   │ • find_*()   │  │ • parse_p7()   │  │ • match()  │
   └──────────────┘  └────────────┘  └──────────────┘
```

---

## 2. Module Structure

### 2.1 Directory Layout

```
DevSquad/
├── scripts/
│   └── collaboration/
│       ├── simplicity_role.py          (Modified: Add S1 call)
│       └── gates/
│           ├── crap_gate.py            (Existing: S2)
│           ├── duplication_gate.py     (Existing: S2)
│           └── completeness_gate.py    (NEW: S1 main entry)
│               ├── __init__.py
│               ├── gate.py             (Main gate class)
│               ├── detectors/
│               │   ├── __init__.py
│               │   ├── mock_detector.py
│               │   ├── design_alignment_checker.py
│               │   ├── test_coverage_checker.py
│               │   ├── error_handling_checker.py
│               │   └── security_feature_checker.py
│               ├── parsers/
│               │   ├── __init__.py
│               │   ├── ast_analyzer.py
│               │   ├── markdown_parser.py
│               │   └── test_discovery.py
│               └── utils/
│                   ├── __init__.py
│                   ├── file_cache.py
│                   └── score_calculator.py
│
└── tests/
    └── test_completeness_gate/
        ├── test_completeness_001_mock_detection.py
        ├── test_completeness_002_design_alignment.py
        ├── test_completeness_003_test_coverage.py
        ├── test_completeness_004_error_handling.py
        ├── test_completeness_005_security_features.py
        ├── test_completeness_006_thresholds.py
        ├── test_completeness_007_progressive_mode.py
        ├── test_integration_001_workflow_trace.py
        ├── test_integration_002_alert_system.py
        └── fixtures/
            ├── sample_p3_design.md
            ├── sample_p7_testplan.md
            ├── sample_code_with_mocks.py
            └── sample_code_clean.py
```

---

## 3. Class Specifications

### 3.1 ImplementationCompletenessGate (Main Entry)

**File**: `scripts/collaboration/gates/completeness_gate/gate.py`

```python
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional


@dataclass
class CompletenessAuditResult:
    """S1 Completeness audit result"""
    status: str  # "PASS" | "WARNING" | "REJECT"
    verdict: str  # "PASS" | "ADVISORY" | "CONDITIONAL" | "REJECT"
    completeness_score: float  # 0.0-1.0
    violations: list[dict[str, Any]]
    warnings: list[str]
    metrics: dict[str, float]  # Individual detector scores
    recommendations: list[str]
    enforcement_mode: str  # "shadow" | "soft" | "full"
    timestamp: datetime
    
    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "verdict": self.verdict,
            "completeness_score": self.completeness_score,
            "violations": self.violations,
            "warnings": self.warnings,
            "metrics": self.metrics,
            "recommendations": self.recommendations,
            "enforcement_mode": self.enforcement_mode,
            "timestamp": self.timestamp.isoformat()
        }


class ImplementationCompletenessGate:
    """
    S1 Gate: Prevents AI from taking shortcuts in implementation
    
    Responsibilities:
    - Detect Mock/Stub in production code
    - Verify design document alignment
    - Check test plan coverage
    - Verify error handling
    - Detect security feature implementation
    
    Anti-Ghost Verification:
    - _activation_counter: Number of times check() called
    - _trigger_counter: Number of actual audits executed
    - _skip_counter: Number of times skipped
    """
    
    def __init__(
        self,
        workflow_trace: Any,
        alert_system: Any,
        p3_doc_path: Optional[Path] = None,
        p7_doc_path: Optional[Path] = None
    ) -> None:
        """
        Initialize S1 gate
        
        Args:
            workflow_trace: WorkflowTrace instance
            alert_system: AlertSystem instance
            p3_doc_path: Path to P3 design document (optional)
            p7_doc_path: Path to P7 test plan (optional)
        """
        self.workflow_trace = workflow_trace
        self.alert_system = alert_system
        self.p3_doc_path = p3_doc_path
        self.p7_doc_path = p7_doc_path
        
        # Anti-ghost counters
        self._activation_counter = 0
        self._trigger_counter = 0
        self._skip_counter = 0
        
        # Initialize sub-detectors (lazy loading)
        self._mock_detector: Optional[Any] = None
        self._design_checker: Optional[Any] = None
        self._test_checker: Optional[Any] = None
        self._error_checker: Optional[Any] = None
        self._security_checker: Optional[Any] = None
    
    def check(
        self,
        target_paths: list[Path],
        plan: Any
    ) -> CompletenessAuditResult:
        """
        Execute S1 completeness check
        
        Args:
            target_paths: List of Python files to audit
            plan: ExecutionPlan (contains phase, context)
        
        Returns:
            CompletenessAuditResult
        
        Flow:
            1. Check bypass flag (DEVSQUAD_SKIP_S1)
            2. Initialize detectors (lazy)
            3. Run 5 detector passes in parallel
            4. Calculate weighted completeness score
            5. Determine verdict based on threshold + mode
            6. Record to WorkflowTrace
            7. Send alerts if needed
        """
        self._activation_counter += 1
        
        # Check bypass
        import os
        if os.getenv("DEVSQUAD_SKIP_S1") == "1":
            self._skip_counter += 1
            self._record_bypass("ENV_BYPASS", "Emergency bypass via DEVSQUAD_SKIP_S1")
            return self._create_bypass_result()
        
        self._trigger_counter += 1
        
        # Initialize detectors (lazy)
        self._init_detectors()
        
        # Run detector passes
        mock_result = self._mock_detector.check(target_paths)
        design_result = self._design_checker.check(target_paths, self.p3_doc_path)
        test_result = self._test_checker.check(target_paths, self.p7_doc_path)
        error_result = self._error_checker.check(target_paths)
        security_result = self._security_checker.check(target_paths, self.p3_doc_path)
        
        # Calculate overall score
        completeness_score = self._calculate_completeness_score({
            "mock_score": mock_result["score"],
            "design_alignment": design_result["score"],
            "test_coverage": test_result["score"],
            "error_handling": error_result["score"],
            "security_score": security_result["score"]
        })
        
        # Collect violations
        violations = (
            mock_result["violations"] +
            design_result["violations"] +
            test_result["violations"] +
            error_result["violations"] +
            security_result["violations"]
        )
        
        # Determine status
        status = self._determine_status(completeness_score)
        
        # Apply enforcement mode
        from scripts.collaboration.simplicity_config import SimplicityConfig
        enforcement_mode = SimplicityConfig.get_current_mode()
        verdict = self._apply_enforcement_mode(status, enforcement_mode)
        
        # Build result
        result = CompletenessAuditResult(
            status=status,
            verdict=verdict,
            completeness_score=completeness_score,
            violations=violations,
            warnings=self._collect_warnings(mock_result, design_result, test_result, error_result, security_result),
            metrics={
                "mock_score": mock_result["score"],
                "design_alignment": design_result["score"],
                "test_coverage": test_result["score"],
                "error_handling": error_result["score"],
                "security_score": security_result["score"]
            },
            recommendations=self._generate_recommendations(violations),
            enforcement_mode=enforcement_mode,
            timestamp=datetime.now()
        )
        
        # Record to WorkflowTrace
        self._record_audit(result)
        
        # Send alerts if needed
        if result.verdict == "REJECT" and enforcement_mode == "full":
            self._send_alert(result)
        
        return result
    
    def _calculate_completeness_score(self, scores: dict[str, float]) -> float:
        """
        Calculate weighted completeness score
        
        Weights:
        - mock_score: 20%
        - design_alignment: 25%
        - test_coverage: 25%
        - error_handling: 15%
        - security_score: 15%
        """
        return (
            0.20 * scores["mock_score"] +
            0.25 * scores["design_alignment"] +
            0.25 * scores["test_coverage"] +
            0.15 * scores["error_handling"] +
            0.15 * scores["security_score"]
        )
    
    def _determine_status(self, score: float) -> str:
        """Determine status based on threshold"""
        if score >= 0.95:
            return "PASS"
        elif score >= 0.90:
            return "WARNING"
        else:
            return "REJECT"
    
    def _apply_enforcement_mode(self, status: str, mode: str) -> str:
        """
        Apply progressive release mode
        
        shadow: REJECT → ADVISORY
        soft: REJECT → CONDITIONAL
        full: Keep original
        """
        if status != "REJECT":
            return status
        
        if mode == "shadow":
            return "ADVISORY"
        elif mode == "soft":
            return "CONDITIONAL"
        else:
            return "REJECT"
    
    def get_activation_stats(self) -> dict[str, int]:
        """Anti-ghost verification stats"""
        return {
            "activation_counter": self._activation_counter,
            "trigger_counter": self._trigger_counter,
            "skip_counter": self._skip_counter
        }
```

---

### 3.2 MockDetector

**File**: `scripts/collaboration/gates/completeness_gate/detectors/mock_detector.py`

```python
import ast
from pathlib import Path
from typing import Any


class MockDetector:
    """Detects unittest.mock usage in production code"""
    
    # Patterns to detect
    MOCK_IMPORTS = {
        "unittest.mock",
        "unittest.mock.Mock",
        "unittest.mock.MagicMock",
        "unittest.mock.patch",
        "mock"  # Legacy standalone mock
    }
    
    MOCK_NAMES = {
        "Mock",
        "MagicMock",
        "AsyncMock"
    }
    
    # Exemption patterns
    TEST_FILE_PATTERNS = [
        "test_*.py",
        "*_test.py",
        "tests/**/*.py",
        "**/test/**/*.py"
    ]
    
    def __init__(self) -> None:
        """Initialize Mock detector"""
        pass
    
    def check(self, target_paths: list[Path]) -> dict[str, Any]:
        """
        Check for Mock usage in production code
        
        Returns:
            {
                "score": 1.0 or 0.0 (binary: any mock = 0.0),
                "violations": [...],
                "exempted_files": [...]
            }
        """
        violations = []
        exempted_count = 0
        
        for path in target_paths:
            # Skip test files
            if self._is_test_file(path):
                exempted_count += 1
                continue
            
            # Parse AST
            try:
                with open(path, 'r') as f:
                    tree = ast.parse(f.read(), filename=str(path))
            except SyntaxError:
                continue  # Skip unparseable files
            
            # Check imports
            mock_violations = self._find_mock_imports(tree, path)
            violations.extend(mock_violations)
            
            # Check function calls (e.g., return Mock())
            call_violations = self._find_mock_calls(tree, path)
            violations.extend(call_violations)
        
        score = 0.0 if violations else 1.0
        
        return {
            "score": score,
            "violations": violations,
            "exempted_files": exempted_count
        }
    
    def _is_test_file(self, path: Path) -> bool:
        """Check if file matches test patterns"""
        from fnmatch import fnmatch
        path_str = str(path)
        return any(fnmatch(path_str, pattern) for pattern in self.TEST_FILE_PATTERNS)
    
    def _find_mock_imports(self, tree: ast.AST, file_path: Path) -> list[dict]:
        """Find mock imports in AST"""
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module in self.MOCK_IMPORTS:
                    violations.append({
                        "file": str(file_path),
                        "line": node.lineno,
                        "pattern": "mock_import",
                        "code": f"from {node.module} import ...",
                        "severity": "CRITICAL"
                    })
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if any(mock in alias.name for mock in self.MOCK_IMPORTS):
                        violations.append({
                            "file": str(file_path),
                            "line": node.lineno,
                            "pattern": "mock_import",
                            "code": f"import {alias.name}",
                            "severity": "CRITICAL"
                        })
        
        return violations
    
    def _find_mock_calls(self, tree: ast.AST, file_path: Path) -> list[dict]:
        """Find Mock() calls in AST"""
        violations = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.MOCK_NAMES:
                        # Check if inside __main__ block (allowed)
                        if not self._is_in_main_block(node):
                            violations.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "pattern": "mock_call",
                                "code": f"{node.func.id}()",
                                "severity": "CRITICAL"
                            })
        
        return violations
    
    def _is_in_main_block(self, node: ast.AST) -> bool:
        """Check if node is inside if __name__ == '__main__' block"""
        # Simplified: Would need parent tracking for full implementation
        return False  # Conservative: reject all for now
```

---

### 3.3 DesignAlignmentChecker

**File**: `scripts/collaboration/gates/completeness_gate/detectors/design_alignment_checker.py`

```python
import ast
from pathlib import Path
from typing import Any, Optional


class DesignAlignmentChecker:
    """Verifies implementation aligns with P3 design document"""
    
    def __init__(self) -> None:
        """Initialize design alignment checker"""
        from ..parsers.markdown_parser import MarkdownParser
        from ..parsers.ast_analyzer import ASTAnalyzer
        
        self.md_parser = MarkdownParser()
        self.ast_analyzer = ASTAnalyzer()
    
    def check(
        self,
        target_paths: list[Path],
        p3_doc_path: Optional[Path]
    ) -> dict[str, Any]:
        """
        Check alignment between design and implementation
        
        Returns:
            {
                "score": 0.0-1.0 (alignment ratio),
                "violations": [...],
                "missing_elements": [...],
                "extra_elements": [...]
            }
        """
        if not p3_doc_path or not p3_doc_path.exists():
            # No P3 doc provided → skip check (score = 1.0)
            return {
                "score": 1.0,
                "violations": [],
                "missing_elements": [],
                "extra_elements": [],
                "reason": "No P3 document provided"
            }
        
        # Parse P3 document
        designed_elements = self.md_parser.extract_design_elements(p3_doc_path)
        
        # Parse implementation
        implemented_elements = set()
        for path in target_paths:
            elements = self.ast_analyzer.extract_code_elements(path)
            implemented_elements.update(elements)
        
        # Compare
        designed_set = set(designed_elements)
        missing = designed_set - implemented_elements
        extra = implemented_elements - designed_set
        
        if not designed_set:
            # Empty design doc → score = 1.0
            alignment_score = 1.0
        else:
            alignment_score = len(implemented_elements & designed_set) / len(designed_set)
        
        violations = []
        if alignment_score < 0.90:
            violations.append({
                "type": "design_misalignment",
                "severity": "HIGH",
                "score": alignment_score,
                "missing_count": len(missing),
                "extra_count": len(extra)
            })
        
        return {
            "score": alignment_score,
            "violations": violations,
            "missing_elements": [{"name": e, "type": "class_or_function"} for e in missing],
            "extra_elements": [{"name": e, "type": "class_or_function"} for e in extra]
        }
```

---

### 3.4 TestCoverageChecker

**File**: `scripts/collaboration/gates/completeness_gate/detectors/test_coverage_checker.py`

```python
from pathlib import Path
from typing import Any, Optional


class TestCoverageChecker:
    """Verifies test plan coverage"""
    
    def __init__(self) -> None:
        """Initialize test coverage checker"""
        from ..parsers.markdown_parser import MarkdownParser
        from ..parsers.test_discovery import TestDiscovery
        
        self.md_parser = MarkdownParser()
        self.test_discovery = TestDiscovery()
    
    def check(
        self,
        target_paths: list[Path],
        p7_doc_path: Optional[Path]
    ) -> dict[str, Any]:
        """
        Check test coverage against P7 test plan
        
        Returns:
            {
                "score": 0.0-1.0 (coverage ratio),
                "violations": [...],
                "missing_tests": [...],
                "extra_tests": [...]
            }
        """
        if not p7_doc_path or not p7_doc_path.exists():
            return {
                "score": 1.0,
                "violations": [],
                "missing_tests": [],
                "extra_tests": [],
                "reason": "No P7 document provided"
            }
        
        # Parse P7 test plan
        planned_tests = self.md_parser.extract_test_cases(p7_doc_path)
        
        # Discover implemented tests
        implemented_tests = self.test_discovery.discover_tests(target_paths)
        
        # Compare
        planned_set = set(planned_tests)
        implemented_set = set(implemented_tests)
        
        missing = planned_set - implemented_set
        extra = implemented_set - planned_set
        
        if not planned_set:
            coverage_score = 1.0
        else:
            coverage_score = len(implemented_set & planned_set) / len(planned_set)
        
        violations = []
        if coverage_score < 0.90:
            violations.append({
                "type": "incomplete_test_coverage",
                "severity": "HIGH",
                "score": coverage_score,
                "missing_count": len(missing)
            })
        
        return {
            "score": coverage_score,
            "violations": violations,
            "missing_tests": [{"test_id": t} for t in missing],
            "extra_tests": [{"test_id": t} for t in extra]
        }
```

---

### 3.5 ErrorHandlingChecker

**File**: `scripts/collaboration/gates/completeness_gate/detectors/error_handling_checker.py`

```python
import ast
from pathlib import Path
from typing import Any


class ErrorHandlingChecker:
    """Verifies error handling for I/O operations"""
    
    # Risky operations that need error handling
    RISKY_MODULES = {
        "requests",
        "urllib",
        "httpx",
        "aiohttp"
    }
    
    RISKY_FUNCTIONS = {
        "open",
        "json.load",
        "json.loads",
        "subprocess.run",
        "os.system"
    }
    
    def __init__(self) -> None:
        """Initialize error handling checker"""
        pass
    
    def check(self, target_paths: list[Path]) -> dict[str, Any]:
        """
        Check error handling coverage
        
        Returns:
            {
                "score": 0.0-1.0 (protected_ops / total_ops),
                "violations": [...],
                "unprotected_operations": [...]
            }
        """
        total_ops = 0
        protected_ops = 0
        unprotected = []
        
        for path in target_paths:
            try:
                with open(path, 'r') as f:
                    tree = ast.parse(f.read(), filename=str(path))
            except SyntaxError:
                continue
            
            # Find all risky operations
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    op_name = self._get_call_name(node)
                    if self._is_risky_operation(op_name):
                        total_ops += 1
                        
                        # Check if protected by try-except
                        if self._is_protected(node, tree):
                            protected_ops += 1
                        else:
                            unprotected.append({
                                "file": str(path),
                                "line": node.lineno,
                                "operation": op_name,
                                "severity": "HIGH"
                            })
        
        score = protected_ops / total_ops if total_ops > 0 else 1.0
        
        violations = []
        if score < 0.90:
            violations.append({
                "type": "insufficient_error_handling",
                "severity": "HIGH",
                "score": score,
                "unprotected_count": len(unprotected)
            })
        
        return {
            "score": score,
            "violations": violations,
            "unprotected_operations": unprotected
        }
    
    def _get_call_name(self, node: ast.Call) -> str:
        """Extract function call name"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            # e.g., requests.get → "requests.get"
            return self._get_attribute_path(node.func)
        return ""
    
    def _get_attribute_path(self, node: ast.Attribute) -> str:
        """Get full attribute path (e.g., requests.get)"""
        parts = []
        current = node
        while isinstance(current, ast.Attribute):
            parts.append(current.attr)
            current = current.value
        if isinstance(current, ast.Name):
            parts.append(current.id)
        return ".".join(reversed(parts))
    
    def _is_risky_operation(self, op_name: str) -> bool:
        """Check if operation is risky"""
        if op_name in self.RISKY_FUNCTIONS:
            return True
        for module in self.RISKY_MODULES:
            if op_name.startswith(module + "."):
                return True
        return False
    
    def _is_protected(self, node: ast.AST, tree: ast.AST) -> bool:
        """Check if node is inside try-except block"""
        # Simplified: would need parent tracking
        # For now, conservatively return False
        return False  # Placeholder
```

---

### 3.6 SecurityFeatureChecker

**File**: `scripts/collaboration/gates/completeness_gate/detectors/security_feature_checker.py`

```python
import ast
from pathlib import Path
from typing import Any, Optional


class SecurityFeatureChecker:
    """Verifies security feature implementation"""
    
    # Security patterns to detect
    HMAC_PATTERNS = {
        "hmac.new",
        "hmac.compare_digest"
    }
    
    VALIDATION_PATTERNS = {
        "isinstance",
        "len",
        "re.match",
        "re.fullmatch"
    }
    
    def __init__(self) -> None:
        """Initialize security feature checker"""
        pass
    
    def check(
        self,
        target_paths: list[Path],
        p3_doc_path: Optional[Path]
    ) -> dict[str, Any]:
        """
        Check security feature implementation
        
        Returns:
            {
                "score": 0.0-1.0 (implemented / required),
                "violations": [...],
                "missing_features": [...]
            }
        """
        if not p3_doc_path or not p3_doc_path.exists():
            # No P3 → skip security check
            return {
                "score": 1.0,
                "violations": [],
                "missing_features": [],
                "reason": "No P3 document provided"
            }
        
        # Parse P3 for security requirements
        required_features = self._extract_security_requirements(p3_doc_path)
        
        # Scan code for implemented features
        implemented_features = set()
        for path in target_paths:
            features = self._scan_security_features(path)
            implemented_features.update(features)
        
        # Compare
        required_set = set(required_features)
        missing = required_set - implemented_features
        
        if not required_set:
            score = 1.0
        else:
            score = len(implemented_features & required_set) / len(required_set)
        
        violations = []
        if score < 1.0:
            violations.append({
                "type": "missing_security_features",
                "severity": "CRITICAL",
                "score": score,
                "missing_count": len(missing)
            })
        
        return {
            "score": score,
            "violations": violations,
            "missing_features": [{"feature": f} for f in missing]
        }
    
    def _extract_security_requirements(self, p3_path: Path) -> list[str]:
        """Extract security requirements from P3 document"""
        requirements = []
        
        try:
            with open(p3_path, 'r') as f:
                content = f.read()
            
            # Simple keyword search
            if "HMAC" in content or "hmac" in content:
                requirements.append("HMAC")
            if "input validation" in content.lower():
                requirements.append("input_validation")
            if "SQL injection" in content:
                requirements.append("sql_injection_prevention")
        
        except Exception:
            pass
        
        return requirements
    
    def _scan_security_features(self, path: Path) -> set[str]:
        """Scan code for security features"""
        features = set()
        
        try:
            with open(path, 'r') as f:
                tree = ast.parse(f.read(), filename=str(path))
        except SyntaxError:
            return features
        
        # Check for HMAC usage
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call_name = self._get_call_name(node)
                
                if "hmac.new" in call_name:
                    features.add("HMAC")
                
                if call_name in ["isinstance", "len"]:
                    features.add("input_validation")
        
        return features
    
    def _get_call_name(self, node: ast.Call) -> str:
        """Extract call name from AST node"""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            return ".".join(reversed(parts))
        return ""
```

---

## 4. Integration Points

### 4.1 SimplicityRole Integration

**File**: `scripts/collaboration/simplicity_role.py` (Modified)

```python
def activate(self, plan: Any, results: list[Any]) -> Optional[SimplicityAuditResult]:
    """Main entry point (Modified for V5.1)"""
    self._activation_counter += 1
    
    # Check emergency bypass
    if os.getenv("DEVSQUAD_SKIP_SIMPLICITY") == "1":
        self._skip_counter += 1
        return None
    
    # Check trigger conditions
    if not self._should_trigger(plan):
        self._skip_counter += 1
        return None
    
    self._trigger_counter += 1
    
    # ===== NEW: S1 Gate (ImplementationCompletenessGate) =====
    from scripts.collaboration.gates.completeness_gate.gate import ImplementationCompletenessGate
    
    s1_gate = ImplementationCompletenessGate(
        workflow_trace=self.workflow_trace,
        alert_system=self.alert_system,
        p3_doc_path=getattr(plan, 'p3_doc_path', None),
        p7_doc_path=getattr(plan, 'p7_doc_path', None)
    )
    
    target_paths = getattr(plan, 'target_files', [])
    s1_result = s1_gate.check(target_paths, plan)
    
    # If S1 rejects, stop here (don't run S2)
    if s1_result.verdict == "REJECT":
        logger.error("❌ S1 gate REJECT: Implementation incomplete")
        return self._convert_s1_to_simplicity_result(s1_result)
    elif s1_result.verdict == "WARNING":
        logger.warning("⚠️ S1 gate WARNING: Completeness issues detected")
    # ===== END S1 Gate =====
    
    # Continue with S2 (existing logic)
    from scripts.collaboration.gates.crap_gate import CRAPGate
    crap_gate = CRAPGate(threshold=10.0)
    crap_result = crap_gate.check(target_paths)
    
    # ... (rest of existing S2 logic)
```

---

### 4.2 File Cache (Performance Optimization)

**File**: `scripts/collaboration/gates/completeness_gate/utils/file_cache.py`

```python
import hashlib
import json
from pathlib import Path
from typing import Any, Optional


class FileCache:
    """Cache parsed file results (P3/P7 documents, AST)"""
    
    CACHE_DIR = Path.home() / ".devsquad" / ".s1_cache"
    
    def __init__(self) -> None:
        """Initialize cache"""
        self.CACHE_DIR.mkdir(parents=True, exist_ok=True)
    
    def get(self, file_path: Path, parser_version: str) -> Optional[dict[str, Any]]:
        """
        Get cached parse result
        
        Args:
            file_path: Path to source file
            parser_version: Parser version (for cache invalidation)
        
        Returns:
            Cached result or None
        """
        cache_key = self._compute_cache_key(file_path, parser_version)
        cache_file = self.CACHE_DIR / f"{cache_key}.json"
        
        if not cache_file.exists():
            return None
        
        try:
            with open(cache_file, 'r') as f:
                cached = json.load(f)
            
            # Verify file hasn't changed
            if cached["file_hash"] != self._compute_file_hash(file_path):
                return None
            
            return cached["result"]
        
        except Exception:
            return None
    
    def set(
        self,
        file_path: Path,
        parser_version: str,
        result: dict[str, Any]
    ) -> None:
        """
        Store parse result in cache
        
        Args:
            file_path: Path to source file
            parser_version: Parser version
            result: Parse result to cache
        """
        cache_key = self._compute_cache_key(file_path, parser_version)
        cache_file = self.CACHE_DIR / f"{cache_key}.json"
        
        try:
            cached = {
                "file_path": str(file_path),
                "file_hash": self._compute_file_hash(file_path),
                "parser_version": parser_version,
                "result": result
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cached, f, indent=2)
        
        except Exception:
            pass  # Cache failure is not critical
    
    def _compute_cache_key(self, file_path: Path, parser_version: str) -> str:
        """Compute cache key"""
        key_str = f"{file_path}:{parser_version}"
        return hashlib.sha256(key_str.encode()).hexdigest()[:16]
    
    def _compute_file_hash(self, file_path: Path) -> str:
        """Compute file content hash"""
        try:
            with open(file_path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except Exception:
            return ""
```

---

## 5. Data Flow Diagram

```
1. Coordinator calls SimplicityRole.activate(plan, results)
          ↓
2. SimplicityRole initializes ImplementationCompletenessGate
          ↓
3. S1 Gate reads target_paths from ExecutionPlan
          ↓
4. Parallel detector execution:
   ├─ MockDetector.check(target_paths)
   ├─ DesignAlignmentChecker.check(target_paths, p3_doc)
   ├─ TestCoverageChecker.check(target_paths, p7_doc)
   ├─ ErrorHandlingChecker.check(target_paths)
   └─ SecurityFeatureChecker.check(target_paths, p3_doc)
          ↓
5. ScoreCalculator.calculate_weighted_score(detector_results)
          ↓
6. Determine verdict (PASS/WARNING/REJECT)
          ↓
7. Apply enforcement mode (shadow/soft/full)
          ↓
8. Record to WorkflowTrace
          ↓
9. Send alerts (if needed)
          ↓
10. Return CompletenessAuditResult
          ↓
11. SimplicityRole continues to S2 (or stops if S1 rejects)
```

---

## 6. Performance Considerations

### 6.1 Optimization Strategies

| Strategy | Impact |
|----------|--------|
| **File Cache** | 80% cache hit rate → 5x speedup for repeat audits |
| **Lazy Detector Init** | Only initialize detectors when needed |
| **Parallel Detector Execution** | 5 detectors run concurrently → 3x speedup |
| **AST Cache** | Reuse parsed AST across detectors → 2x speedup |
| **Timeout per File** | 5s timeout prevents runaway parsing |

### 6.2 Benchmark Targets

| Scenario | Target | Actual (Estimated) |
|----------|--------|-------------------|
| 10 files, cold cache | < 30s | ~25s |
| 10 files, warm cache | < 5s | ~3s |
| 50 files, cold cache | < 120s | ~95s |

---

## 7. Security Considerations

### 7.1 Attack Surface

| Attack Vector | Mitigation |
|---------------|------------|
| **Path Traversal** | Validate all file paths with `Path.resolve()` |
| **Code Injection** | Use `ast.parse()` (safe), never `eval()` |
| **DoS (Large Files)** | 5s timeout per file, skip files >10MB |
| **Cache Poisoning** | SHA256 file hash verification |
| **Bypass via ENV** | Log all `DEVSQUAD_SKIP_S1` usage + send P1 alert |

---

## 8. Testing Strategy (Deferred to P7)

Detailed test plan in P7 document. Key test categories:

- Unit Tests (test_completeness_001-007)
- Integration Tests (test_integration_001-002)
- E2E Tests (full P8 workflow with S1 gate)
- Performance Tests (benchmark 10/50 file PRs)
- Red-Team Tests (bypass attempt scenarios)

---

## 9. Open Questions

| Question | Owner | Status |
|----------|-------|--------|
| Q1: Should S1 check for `TODO` comments in production code? | PM | TBD |
| Q2: Should S1 integrate with `coverage.py` for actual test coverage data? | Tester | TBD |
| Q3: Should S1 support custom detection rules via config file? | Architect | Out of scope V5.1 |

---

## 10. Appendix

### 10.1 AST Patterns Reference

```python
# Mock import pattern
ast.ImportFrom(module='unittest.mock', names=[...])

# Function definition pattern
ast.FunctionDef(name='function_name', args=ast.arguments(...))

# Class definition pattern
ast.ClassDef(name='ClassName', bases=[...], body=[...])

# Try-except pattern
ast.Try(body=[...], handlers=[ast.ExceptHandler(...)])

# Function call pattern
ast.Call(func=ast.Name(id='func_name'), args=[...])
```

### 10.2 Markdown Parsing Examples

**P3 Design Document Structure**:
```markdown
## 3.1 Module Structure

### Classes

- `ImplementationCompletenessGate`
  - Methods: `check()`, `_calculate_score()`
  - Dependencies: `ast`, `markdown`
```

**P7 Test Plan Structure**:
```markdown
## Test Cases

### Unit Tests

- `test_completeness_001`: Mock detection baseline
- `test_completeness_002`: Design alignment baseline
```

---

## Approval

| Role | Name | Status | Date |
|------|------|--------|------|
| Architect | DevSquad Architect | ⏸️ Pending | - |
| Coder | DevSquad Coder | ⏸️ Pending | - |
| Security | DevSquad Security | ⏸️ Pending | - |
| Tech Lead | User | ⏸️ Pending | - |

**Next Step**: Generate P7 Test Plan Document