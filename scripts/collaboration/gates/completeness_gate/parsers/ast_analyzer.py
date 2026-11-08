"""AST analyzer for extracting code structure.

Parses Python source files using the built-in ast module to extract
classes, functions, and methods.
"""

import ast
from pathlib import Path


class CodeElement:
    """Represents a code element (class, function, method)."""

    def __init__(self, name: str, type: str, parent: str | None = None):
        self.name = name
        self.type = type  # 'class', 'function', 'method'
        self.parent = parent  # Parent class for methods

    def __repr__(self) -> str:
        if self.parent:
            return f"{self.type}:{self.parent}.{self.name}"
        return f"{self.type}:{self.name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, CodeElement):
            return False
        return self.name == other.name and self.type == other.type and self.parent == other.parent

    def __hash__(self) -> int:
        return hash((self.name, self.type, self.parent))


class ASTAnalyzer:
    """Analyzes Python source code using AST."""

    def __init__(self) -> None:
        self._elements: list[CodeElement] = []

    def analyze_file(self, file_path: Path) -> list[CodeElement]:
        """
        Analyze a Python file and extract code elements.

        Args:
            file_path: Path to Python source file

        Returns:
            List of CodeElement objects
        """
        if not file_path.exists() or file_path.suffix != ".py":
            return []

        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))
            self._elements = []
            self._visit_node(tree)
            return self._elements
        except SyntaxError:
            # Skip files with syntax errors
            return []

    def _visit_node(self, node: ast.AST, parent_class: str | None = None) -> None:
        """Recursively visit AST nodes."""
        if isinstance(node, ast.ClassDef):
            # Add class
            self._elements.append(CodeElement(name=node.name, type="class", parent=None))
            # Visit methods inside class
            for item in node.body:
                self._visit_node(item, parent_class=node.name)

        elif isinstance(node, ast.FunctionDef):
            if parent_class:
                # Skip private methods
                if not node.name.startswith("_"):
                    self._elements.append(CodeElement(name=node.name, type="method", parent=parent_class))
            else:
                # Top-level function
                self._elements.append(CodeElement(name=node.name, type="function", parent=None))

        # Continue visiting child nodes
        for child in ast.iter_child_nodes(node):
            if isinstance(node, ast.ClassDef):
                # Already handled in ClassDef branch
                pass
            else:
                self._visit_node(child, parent_class)

    def get_classes(self) -> set[str]:
        """Get all class names."""
        return {e.name for e in self._elements if e.type == "class"}

    def get_functions(self) -> set[str]:
        """Get all function names (excluding methods)."""
        return {e.name for e in self._elements if e.type == "function"}

    def get_methods(self, class_name: str) -> set[str]:
        """Get all method names for a specific class."""
        return {e.name for e in self._elements if e.type == "method" and e.parent == class_name}
