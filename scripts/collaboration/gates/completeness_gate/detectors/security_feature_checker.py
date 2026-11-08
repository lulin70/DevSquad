"""SecurityFeatureChecker - Checks for required security features.

Checks for:
- HMAC usage (hmac.new with hashlib.sha256)
- Input validation patterns (isinstance, len checks, regex validation)
"""

import ast
from pathlib import Path
from typing import Any

from scripts.collaboration.gates.completeness_gate.utils.score_calculator import calculate_security_score


class SecurityFeatureChecker:
    """Checks for presence of security features."""

    def __init__(self) -> None:
        self.required_features = ["hmac_usage", "input_validation"]

    def check(self, target_paths: list[Path], p3_doc: Path | None = None) -> dict[str, Any]:
        """
        Check for security features in code files.

        Args:
            target_paths: List of Python file paths to check
            p3_doc: Optional P3 document with security requirements

        Returns:
            {
                "security_score": float,  # 0.0-1.0
                "missing_security_features": [str, ...]
            }
        """
        # If no P3 doc provided, no security requirements → perfect score
        if p3_doc is None or not p3_doc.exists():
            return {"security_score": 1.0, "missing_security_features": []}

        found_features = set()

        for path in target_paths:
            if not path.exists() or path.suffix != ".py":
                continue

            try:
                content = path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(path))

                # Check for HMAC usage
                if self._has_hmac_usage(tree, content):
                    found_features.add("hmac_usage")

                # Check for input validation
                if self._has_input_validation(tree):
                    found_features.add("input_validation")

            except SyntaxError:
                # Skip files with syntax errors
                continue

        # Calculate score
        required_count = len(self.required_features)
        found_count = len(found_features)
        security_score = calculate_security_score(required_count, found_count)

        # Missing features
        missing = [f for f in self.required_features if f not in found_features]

        return {"security_score": security_score, "missing_security_features": missing}

    def _has_hmac_usage(self, tree: ast.AST, content: str) -> bool:
        """Check for hmac.new(..., hashlib.sha256) pattern."""
        # Check for hmac import
        has_hmac_import = False

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if "hmac" in alias.name:
                        has_hmac_import = True
            elif (
                isinstance(node, ast.ImportFrom) and node.module and ("hmac" in node.module or "hashlib" in node.module)
            ):
                has_hmac_import = True

        # Simple text search for the hmac.new pattern
        return has_hmac_import and "hmac.new" in content and ("sha256" in content or "SHA256" in content)

    def _has_input_validation(self, tree: ast.AST) -> bool:
        """Check for input validation patterns."""
        for node in ast.walk(tree):
            # isinstance checks
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "isinstance":
                return True

            # len() checks
            if (
                isinstance(node, ast.Compare)
                and isinstance(node.left, ast.Call)
                and isinstance(node.left.func, ast.Name)
                and node.left.func.id == "len"
            ):
                return True

        return False
