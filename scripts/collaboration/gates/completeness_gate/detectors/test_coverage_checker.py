"""TestCoverageChecker - Compares test files against P7 test plan.

Parses P7 markdown for planned test case IDs and compares with
discovered tests from test files to detect missing/extra tests.
"""

from typing import List, Dict, Any
from pathlib import Path
from scripts.collaboration.gates.completeness_gate.parsers.test_discovery import TestDiscovery
from scripts.collaboration.gates.completeness_gate.utils.score_calculator import calculate_coverage_score


class TestCoverageChecker:
    """Checks test coverage against P7 test plan."""
    
    def __init__(self):
        self.test_discovery = TestDiscovery()
    
    def check(self, test_paths: List[Path], p7_doc: Path = None) -> Dict[str, Any]:
        """
        Check test coverage against P7 test plan document.
        
        Args:
            test_paths: List of test file paths (test_*.py)
            p7_doc: Path to P7 markdown test plan document
            
        Returns:
            {
                "test_coverage": float,  # 0.0-1.0
                "missing_tests": [str, ...],  # Test IDs in P7 but not implemented
                "extra_tests": [str, ...]  # Implemented tests not in P7
            }
        """
        # Handle missing P7 document
        if not p7_doc or not p7_doc.exists():
            return {
                "test_coverage": 1.0,
                "missing_tests": [],
                "extra_tests": [],
                "message": "No P7 test plan provided - coverage check skipped"
            }
        
        # Discover planned tests from P7
        planned_tests = self.test_discovery.discover_from_p7(p7_doc)
        if not planned_tests:
            # Empty test plan means nothing required
            return {
                "test_coverage": 1.0,
                "missing_tests": [],
                "extra_tests": [],
                "message": "P7 test plan is empty - no tests to check"
            }
        
        # Discover implemented tests from files
        implemented_tests = self.test_discovery.discover_from_files(test_paths)
        
        # Match tests using normalized comparison
        match_result = self._match_tests_normalized(planned_tests, implemented_tests)
        
        # Calculate coverage score (implemented / planned)
        planned_count = len(planned_tests)
        implemented_count = len(match_result['matched'])
        test_coverage = calculate_coverage_score(planned_count, implemented_count)
        
        return {
            "test_coverage": test_coverage,
            "missing_tests": sorted(list(match_result['missing'])),
            "extra_tests": sorted(list(match_result['extra']))
        }
    
    def _match_tests_normalized(self, planned: set, implemented: set) -> dict:
        """
        Match tests with normalization for case and underscores.
        
        Normalizes test names by:
        - Converting to lowercase
        - Removing underscores
        
        This allows matching test_user_001, testuser001, TestUser001, etc.
        """
        # Create normalized mapping
        planned_norm = {}
        implemented_norm = {}
        
        for test_name in planned:
            norm_key = test_name.lower().replace('_', '')
            planned_norm[norm_key] = test_name
        
        for test_name in implemented:
            norm_key = test_name.lower().replace('_', '')
            implemented_norm[norm_key] = test_name
        
        # Find matches
        planned_keys = set(planned_norm.keys())
        implemented_keys = set(implemented_norm.keys())
        
        matched_keys = planned_keys.intersection(implemented_keys)
        missing_keys = planned_keys - implemented_keys
        extra_keys = implemented_keys - planned_keys
        
        # Map back to original names (prefer planned names for matched)
        return {
            'matched': {planned_norm[k] for k in matched_keys},
            'missing': {planned_norm[k] for k in missing_keys},
            'extra': {implemented_norm[k] for k in extra_keys}
        }
