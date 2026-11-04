"""ErrorHandlingChecker - Detects unprotected risky operations.

Detects risky operations (requests.*, open(), subprocess.*) and checks
if they are inside try-except blocks.
"""

import ast
from typing import List, Dict, Any
from pathlib import Path
from scripts.collaboration.gates.completeness_gate.utils.score_calculator import calculate_error_handling_score


class ErrorHandlingChecker:
    """Checks for unprotected risky operations."""
    
    # Risky operation patterns to detect
    RISKY_CALLS = {
        'requests.get', 'requests.post', 'requests.put', 'requests.delete',
        'requests.patch', 'requests.head', 'requests.options',
        'subprocess.run', 'subprocess.call', 'subprocess.check_call',
        'subprocess.check_output', 'subprocess.Popen'
    }
    
    RISKY_FUNCTIONS = {'open'}
    
    def check(self, target_paths: List[Path]) -> Dict[str, Any]:
        """
        Check for unprotected risky operations in code files.
        
        Args:
            target_paths: List of Python file paths to check
            
        Returns:
            {
                "error_handling_score": float,  # 0.0-1.0
                "unprotected_operations": [{
                    "file": str,
                    "line": int,
                    "operation": str,
                    "severity": str
                }, ...]
            }
        """
        all_violations = []
        
        for path in target_paths:
            if not path.exists() or path.suffix != ".py":
                continue
            
            try:
                content = path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(path))
                visitor = RiskyOperationVisitor(path)
                visitor.visit(tree)
                all_violations.extend(visitor.violations)
            except SyntaxError:
                # Skip files with syntax errors
                continue
        
        # Calculate score
        # all_violations contains ALL risky operations (both protected and unprotected)
        # We need to count them properly
        protected_count = sum(1 for v in all_violations if v["protected"])
        unprotected_count = sum(1 for v in all_violations if not v["protected"])
        total_count = protected_count + unprotected_count
        
        if total_count == 0:
            # No risky operations found = perfect score
            error_handling_score = 1.0
        else:
            error_handling_score = calculate_error_handling_score(
                total_count, protected_count
            )
        
        # Return only unprotected operations
        unprotected = [
            {
                "file": str(v["file"]),
                "line": v["line"],
                "operation": v["operation"],
                "severity": "MEDIUM"
            }
            for v in all_violations
            if not v["protected"]
        ]
        
        return {
            "error_handling_score": error_handling_score,
            "unprotected_operations": unprotected
        }


class RiskyOperationVisitor(ast.NodeVisitor):
    """AST visitor to find risky operations."""
    
    def __init__(self, file_path: Path):
        self.file_path = file_path
        self.violations = []
        self.try_depth = 0  # Track try-except nesting depth
    
    def visit_Try(self, node: ast.Try):
        """Track when we enter a try block."""
        self.try_depth += 1
        self.generic_visit(node)
        self.try_depth -= 1
    
    def visit_Call(self, node: ast.Call):
        """Check for risky function/method calls."""
        call_name = self._get_call_name(node.func)
        
        # Check for risky calls (requests.get, subprocess.run, etc.)
        is_risky = False
        operation_name = None
        
        if call_name in ErrorHandlingChecker.RISKY_FUNCTIONS:
            is_risky = True
            operation_name = call_name
        else:
            # Check for module.function patterns
            for risky_pattern in ErrorHandlingChecker.RISKY_CALLS:
                if call_name.endswith(risky_pattern) or call_name == risky_pattern:
                    is_risky = True
                    operation_name = risky_pattern
                    break
        
        if is_risky:
            self.violations.append({
                "file": self.file_path,
                "line": node.lineno,
                "operation": operation_name or call_name,
                "protected": self.try_depth > 0
            })
        
        self.generic_visit(node)
    
    def _get_call_name(self, node: ast.AST) -> str:
        """Extract function call name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value_name = self._get_call_name(node.value)
            return f"{value_name}.{node.attr}"
        return ""
