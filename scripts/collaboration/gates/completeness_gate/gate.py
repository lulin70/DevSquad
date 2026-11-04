"""ImplementationCompletenessGate (S1 Gate) - Main entry point.

Orchestrates 5 detectors and calculates overall completeness score.
"""

from typing import List, Dict, Any
from pathlib import Path
from datetime import datetime, timezone

from .detectors.mock_detector import MockDetector
from .detectors.design_alignment_checker import DesignAlignmentChecker
from .detectors.test_coverage_checker import TestCoverageChecker
from .detectors.error_handling_checker import ErrorHandlingChecker
from .detectors.security_feature_checker import SecurityFeatureChecker


class ImplementationCompletenessGate:
    """
    S1 Gate: Verifies implementation completeness.
    
    Checks:
    - No mocks in production code (20% weight)
    - All design elements implemented (25% weight)
    - All test cases implemented (25% weight)
    - Error handling present (15% weight)
    - Security features present (15% weight)
    
    Verdict thresholds:
    - score ≥ 0.95: PASS
    - 0.90 ≤ score < 0.95: WARNING
    - score < 0.90: REJECT
    """
    
    # Weights for completeness score (must sum to 1.0)
    WEIGHTS = {
        "mock": 0.20,
        "alignment": 0.25,
        "test_coverage": 0.25,
        "error_handling": 0.15,
        "security": 0.15
    }
    
    def __init__(self):
        """Initialize the gate with default configuration."""
        self._activation_counter = 0
        self._trigger_counter = 0
        self._skip_counter = 0
        
        # Initialize detectors
        self._mock_detector = MockDetector()
        self._design_checker = DesignAlignmentChecker()
        self._test_checker = TestCoverageChecker()
        self._error_checker = ErrorHandlingChecker()
        self._security_checker = SecurityFeatureChecker()
    
    def check(self, target_paths: List[Path], plan: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Check implementation completeness.
        
        Args:
            target_paths: Python files to check
            plan: Dict with optional keys:
                - 'p3_doc': Path to P3 design document
                - 'p7_doc': Path to P7 test plan
                - 'test_paths': List of test file paths
                - 'mode': "shadow" | "soft" | "full" (or auto from deployment_date)
                - 'deployment_date': ISO timestamp for auto mode selection
            
        Returns:
            {
                "verdict": "PASS" | "WARNING" | "REJECT",
                "completeness_score": float,
                "mode": "shadow" | "soft" | "full",
                "original_verdict": str (only in shadow/soft modes),
                "details": {...},
                "timestamp": str
            }
        """
        self._activation_counter += 1
        self._trigger_counter += 1
        
        plan = plan or {}
        
        # Run all detectors
        mock_result = self._mock_detector.check(target_paths)
        design_result = self._design_checker.check(
            target_paths, 
            p3_doc=Path(plan["p3_doc"]) if "p3_doc" in plan else None
        )
        test_result = self._test_checker.check(
            test_paths=plan.get("test_paths", []),
            p7_doc=Path(plan["p7_doc"]) if "p7_doc" in plan else None
        )
        error_result = self._error_checker.check(target_paths)
        security_result = self._security_checker.check(
            target_paths,
            p3_doc=Path(plan["p3_doc"]) if "p3_doc" in plan else None
        )
        
        # Calculate overall score
        completeness_score = self._calculate_completeness_score(
            mock_result["mock_score"],
            design_result["alignment_score"],
            test_result["test_coverage"],
            error_result["error_handling_score"],
            security_result["security_score"]
        )
        
        # Determine base verdict
        base_verdict = self._determine_verdict(completeness_score)
        
        # Progressive mode handling
        mode = self._determine_mode(plan)
        final_verdict, result_dict = self._apply_progressive_mode(base_verdict, mode)
        
        result_dict.update({
            "verdict": final_verdict,
            "completeness_score": completeness_score,
            "mode": mode,
            "details": {
                "mock_score": mock_result["mock_score"],
                "mock_violations": mock_result["violations"],
                "alignment_score": design_result["alignment_score"],
                "missing_elements": design_result["missing_elements"],
                "extra_elements": design_result.get("extra_elements", []),
                "test_coverage": test_result["test_coverage"],
                "missing_tests": test_result["missing_tests"],
                "extra_tests": test_result.get("extra_tests", []),
                "error_handling_score": error_result["error_handling_score"],
                "unprotected_operations": error_result["unprotected_operations"],
                "security_score": security_result["security_score"],
                "missing_security_features": security_result["missing_security_features"]
            },
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return result_dict
    
    def _calculate_completeness_score(
        self, 
        mock_score: float, 
        alignment_score: float,
        test_coverage: float,
        error_handling_score: float,
        security_score: float
    ) -> float:
        """
        Calculate weighted completeness score.
        
        Formula:
            score = mock*0.20 + alignment*0.25 + test*0.25 + error*0.15 + security*0.15
        """
        score = (
            mock_score * self.WEIGHTS["mock"] +
            alignment_score * self.WEIGHTS["alignment"] +
            test_coverage * self.WEIGHTS["test_coverage"] +
            error_handling_score * self.WEIGHTS["error_handling"] +
            security_score * self.WEIGHTS["security"]
        )
        return round(score, 4)
    
    def _determine_verdict(self, score: float) -> str:
        """
        Determine verdict from completeness score.
        
        Thresholds:
        - score ≥ 0.95: PASS
        - 0.90 ≤ score < 0.95: WARNING
        - score < 0.90: REJECT
        """
        if score >= 0.95:
            return "PASS"
        elif score >= 0.90:
            return "WARNING"
        else:
            return "REJECT"
    
    def _determine_mode(self, plan: Dict[str, Any]) -> str:
        """
        Determine progressive mode from plan.
        
        Priority:
        1. Explicit 'mode' in plan
        2. Auto-calculate from 'deployment_date'
        3. Default to 'full'
        """
        if "mode" in plan:
            return plan["mode"]
        
        if "deployment_date" in plan:
            deployment_date = datetime.fromisoformat(plan["deployment_date"])
            days_since = (datetime.now(timezone.utc) - deployment_date).days
            
            if days_since < 7:
                return "shadow"
            elif days_since < 14:
                return "soft"
            else:
                return "full"
        
        return "full"  # Default to full enforcement
    
    def _apply_progressive_mode(self, base_verdict: str, mode: str) -> tuple[str, Dict[str, Any]]:
        """
        Apply progressive mode logic to verdict.
        
        Shadow mode: Always return PASS (log only)
        Soft mode: Upgrade REJECT to WARNING
        Full mode: No changes
        
        Returns:
            (final_verdict, extra_fields_dict)
        """
        result_dict = {}
        
        if mode == "shadow":
            result_dict["original_verdict"] = base_verdict
            return ("PASS", result_dict)
        
        elif mode == "soft":
            if base_verdict == "REJECT":
                result_dict["original_verdict"] = base_verdict
                return ("WARNING", result_dict)
            return (base_verdict, result_dict)
        
        else:  # full mode
            return (base_verdict, result_dict)
    
    def get_activation_stats(self) -> Dict[str, int]:
        """
        Anti-ghost verification stats.
        
        Returns:
            {
                "activation_counter": int,  # Number of check() calls
                "trigger_counter": int,     # Number of actual checks performed
                "skip_counter": int         # Number of skipped checks
            }
        """
        return {
            "activation_counter": self._activation_counter,
            "trigger_counter": self._trigger_counter,
            "skip_counter": self._skip_counter
        }
