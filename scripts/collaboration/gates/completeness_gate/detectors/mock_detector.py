"""MockDetector - Detects unittest.mock usage in production code.

Detects:
- `from unittest.mock import Mock/MagicMock/patch/...`
- `import unittest.mock`
- `unittest.mock.Mock()` usage

Exemptions:
- Test files: test_*.py, *_test.py, tests/**/*.py
- Code inside `if __name__ == "__main__"` blocks
- Docstring examples
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class MockViolation:
    """Represents a mock usage violation."""

    file: str
    line: int
    pattern: str
    context: str
    severity: str = "CRITICAL"


class MockDetector:
    """Detects mock usage in production code."""

    def __init__(self) -> None:
        self._mock_patterns = {
            "Mock",
            "MagicMock",
            "AsyncMock",
            "patch",
            "patch.object",
            "patch.dict",
            "patch.multiple",
            "create_autospec",
            "seal",
        }
        self._test_file_patterns = ["test_*.py", "*_test.py"]

    def check(self, target_paths: list[Path]) -> dict[str, Any]:
        """
        Check files for mock usage in production code.

        Args:
            target_paths: List of Python file paths to check

        Returns:
            {
                "has_violations": bool,
                "violations": [MockViolation, ...],
                "mock_score": float  # 1.0 if no violations, 0.0 if any
            }
        """
        violations = []

        for path in target_paths:
            if not path.exists() or path.suffix != ".py":
                continue

            # Skip test files
            if self._is_test_file(path):
                continue

            try:
                content = path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(path))
                file_violations = self._check_ast(tree, path, content)
                violations.extend(file_violations)
            except SyntaxError:
                # Skip files with syntax errors (will be caught by other tools)
                continue

        return {
            "has_violations": len(violations) > 0,
            "violations": [self._violation_to_dict(v) for v in violations],
            "mock_score": 0.0 if len(violations) > 0 else 1.0,
        }

    def _is_test_file(self, path: Path) -> bool:
        """Check if file is a test file (exempted from mock rules)."""
        filename = path.name

        # Check file name patterns
        if filename.startswith("test_") or filename.endswith("_test.py"):
            return True

        # Check if in tests/ directory
        return "tests" in path.parts or "test" in path.parts

    def _check_ast(self, tree: ast.AST, path: Path, content: str) -> list[MockViolation]:
        """Parse AST and find mock usage."""
        visitor = MockVisitor(self._mock_patterns, path, content)
        visitor.visit(tree)
        return visitor.violations

    def _violation_to_dict(self, violation: MockViolation) -> dict[str, Any]:
        """Convert MockViolation to dictionary."""
        return {
            "file": violation.file,
            "line": violation.line,
            "pattern": violation.pattern,
            "context": violation.context,
            "severity": violation.severity,
        }


class MockVisitor(ast.NodeVisitor):
    """AST visitor to find mock usage."""

    def __init__(self, mock_patterns: set[str], path: Path, content: str) -> None:
        self.mock_patterns = mock_patterns
        self.path = path
        self.content = content
        self.violations: list[MockViolation] = []
        self.in_main_block = False
        self._lines = content.splitlines()

    def visit_If(self, node: ast.If) -> None:
        """Track __main__ blocks."""
        # Check if this is: if __name__ == "__main__":
        is_main_block = False
        test = node.test
        if (
            isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__"
            and len(test.comparators) == 1
        ):
            comparator = test.comparators[0]
            if isinstance(comparator, ast.Constant) and comparator.value == "__main__":
                is_main_block = True

        # Visit body with main block context
        old_in_main = self.in_main_block
        if is_main_block:
            self.in_main_block = True

        self.generic_visit(node)
        self.in_main_block = old_in_main

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """Check for `from unittest.mock import ...`"""
        if self.in_main_block:
            self.generic_visit(node)
            return

        if node.module and "unittest.mock" in node.module:
            # Check if importing mock-related names
            for alias in node.names:
                if alias.name in self.mock_patterns or alias.name == "*":
                    context = self._get_line_context(node.lineno)
                    self.violations.append(
                        MockViolation(
                            file=str(self.path),
                            line=node.lineno,
                            pattern=f"from unittest.mock import {alias.name}",
                            context=context,
                            severity="CRITICAL",
                        )
                    )

        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        """Check for `import unittest.mock` or `import unittest`"""
        if self.in_main_block:
            self.generic_visit(node)
            return

        for alias in node.names:
            if "unittest" in alias.name and ("mock" in alias.name or alias.name == "unittest"):
                context = self._get_line_context(node.lineno)
                self.violations.append(
                    MockViolation(
                        file=str(self.path),
                        line=node.lineno,
                        pattern=f"import {alias.name}",
                        context=context,
                        severity="CRITICAL",
                    )
                )

        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        """Check for Mock() / MagicMock() calls."""
        if self.in_main_block:
            self.generic_visit(node)
            return

        # Check if calling a mock constructor
        func_name = self._get_call_name(node.func)
        if func_name and any(pattern in func_name for pattern in self.mock_patterns):
            context = self._get_line_context(node.lineno)
            self.violations.append(
                MockViolation(
                    file=str(self.path),
                    line=node.lineno,
                    pattern=f"{func_name}()",
                    context=context,
                    severity="CRITICAL",
                )
            )

        self.generic_visit(node)

    def _get_call_name(self, node: ast.AST) -> str:
        """Extract function call name from AST node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_call_name(node.value)}.{node.attr}"
        return ""

    def _get_line_context(self, lineno: int) -> str:
        """Get source code context for a line."""
        if 1 <= lineno <= len(self._lines):
            return self._lines[lineno - 1].strip()
        return ""
