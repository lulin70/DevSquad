"""Test discovery for finding test cases in test files.

Discovers test case IDs from P7 test plan documents and actual test files.
"""

import re
import ast
from pathlib import Path
from typing import List, Set


class TestDiscovery:
    """Discovers test cases from test files and P7 documents."""
    
    # Patterns for test case IDs in P7:
    # - test_module_001 (numbered format)
    # - test_function_name (standard format)
    NUMBERED_TEST_PATTERN = re.compile(r'test_\w+_\d+')
    STANDARD_TEST_PATTERN = re.compile(r'[-*]\s+(?:`)?(?:def\s+)?(test_\w+)(?:`)?')
    
    def discover_from_p7(self, p7_doc: Path) -> Set[str]:
        """
        Discover planned test case IDs from P7 test plan document.
        
        Supports two formats:
        - Numbered: test_user_001, test_login_002
        - Standard: test_create_user, test_login
        
        Args:
            p7_doc: Path to P7 markdown test plan
            
        Returns:
            Set of test case IDs (e.g., {'test_user_001', 'test_create_user'})
        """
        if not p7_doc or not p7_doc.exists():
            return set()
        
        try:
            content = p7_doc.read_text(encoding="utf-8")
            
            # Find numbered tests (test_xxx_001 format)
            numbered_matches = self.NUMBERED_TEST_PATTERN.findall(content)
            
            # Find standard tests (- test_xxx format)
            standard_matches = self.STANDARD_TEST_PATTERN.findall(content)
            
            # Combine both
            all_matches = set(numbered_matches) | set(standard_matches)
            
            return all_matches
        except Exception:
            return set()
    
    def discover_from_files(self, test_paths: List[Path]) -> Set[str]:
        """
        Discover implemented test functions from test files.
        
        Args:
            test_paths: List of test file paths (test_*.py)
            
        Returns:
            Set of test function names (e.g., {'test_create_user', 'test_login'})
        """
        test_functions = set()
        
        for path in test_paths:
            if not path.exists() or path.suffix != ".py":
                continue
            
            try:
                content = path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(path))
                
                # Find all test functions and test methods
                for node in ast.walk(tree):
                    # Support both sync and async test functions
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if node.name.startswith("test_"):
                            test_functions.add(node.name)
            
            except SyntaxError:
                # Skip files with syntax errors
                continue
        
        return test_functions
    
    def match_tests(self, planned: Set[str], implemented: Set[str]) -> dict:
        """
        Match planned tests against implemented tests.
        
        Args:
            planned: Set of planned test IDs from P7
            implemented: Set of implemented test function names
            
        Returns:
            {
                'missing': set of planned but not implemented,
                'extra': set of implemented but not planned,
                'matched': set of tests present in both
            }
        """
        # Normalize for comparison (case-insensitive)
        planned_lower = {t.lower() for t in planned}
        implemented_lower = {t.lower() for t in implemented}
        
        missing = planned_lower - implemented_lower
        extra = implemented_lower - planned_lower
        matched = planned_lower.intersection(implemented_lower)
        
        return {
            'missing': missing,
            'extra': extra,
            'matched': matched
        }
