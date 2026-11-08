"""Markdown parser for extracting design elements from P3 documents.

Parses markdown design documents to extract class and function definitions
using simple regex patterns.
"""

import re
from pathlib import Path


class DesignElement:
    """Represents a design element from P3 document."""

    def __init__(self, name: str, type: str, parent: str | None = None):
        self.name = name
        self.type = type  # 'class', 'function', 'method'
        self.parent = parent

    def __repr__(self) -> str:
        if self.parent:
            return f"{self.type}:{self.parent}.{self.name}"
        return f"{self.type}:{self.name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, DesignElement):
            return False
        return self.name == other.name and self.type == other.type and self.parent == other.parent

    def __hash__(self) -> int:
        return hash((self.name, self.type, self.parent))


class MarkdownParser:
    """Parses P3 markdown documents for design elements."""

    # Patterns to match class and function definitions in markdown
    CLASS_PATTERN = re.compile(r"###\s+(\w+)\s*$")  # Class: ### ClassName (no parens)
    FUNCTION_HEADER = re.compile(r"###\s+(\w+)\s*\([^)]*\)")  # Function header: ### func(args)
    # Match function signatures: - `function_name(args)` or - function_name(args)
    FUNCTION_PATTERN = re.compile(r"[-*]\s+`?(\w+)\s*\([^)]*\)")
    # Section headers to detect function-only sections
    FUNCTION_SECTION = re.compile(r"##\s+(API Functions|Functions|Utilities|Helpers)", re.IGNORECASE)

    def parse_design_doc(self, doc_path: Path) -> list[DesignElement]:
        """
        Parse a P3 markdown document and extract design elements.

        Args:
            doc_path: Path to markdown file

        Returns:
            List of DesignElement objects
        """
        if not doc_path or not doc_path.exists():
            return []

        try:
            content = doc_path.read_text(encoding="utf-8")
            elements = []
            current_class = None
            in_function_section = False

            for line in content.splitlines():
                line_stripped = line.strip()

                # Check for function-only section
                if self.FUNCTION_SECTION.match(line_stripped):
                    in_function_section = True
                    current_class = None
                    continue

                # Check for function header (### function_name(args))
                func_header_match = self.FUNCTION_HEADER.match(line_stripped)
                if func_header_match:
                    func_name = func_header_match.group(1)
                    elements.append(DesignElement(name=func_name, type="function", parent=None))
                    in_function_section = False
                    current_class = None
                    continue

                # Check for class definition (### ClassName without parens)
                class_match = self.CLASS_PATTERN.match(line_stripped)
                if class_match:
                    in_function_section = False  # Class section resets function mode
                    class_name = class_match.group(1)
                    # Check if this is a nested class (e.g., "Container.Inner")
                    if "." in class_name:
                        parts = class_name.split(".")
                        current_class = parts[-1]  # Use last part
                    else:
                        current_class = class_name

                    elements.append(DesignElement(name=current_class, type="class", parent=None))
                    continue

                # Check for function/method definition
                func_match = self.FUNCTION_PATTERN.match(line_stripped)
                if func_match:
                    func_name = func_match.group(1)

                    if current_class and not in_function_section:
                        # Method inside a class
                        elements.append(DesignElement(name=func_name, type="method", parent=current_class))
                    else:
                        # Top-level function
                        elements.append(DesignElement(name=func_name, type="function", parent=None))

                # Reset current_class on new section (## but not ###)
                if (
                    line_stripped.startswith("##")
                    and not line_stripped.startswith("###")
                    and not self.FUNCTION_SECTION.match(line_stripped)
                ):
                    current_class = None
                    in_function_section = False

            return elements

        except Exception:
            # Return empty list on any parsing error
            return []

    def get_classes(self, elements: list[DesignElement]) -> set[str]:
        """Get all class names from design elements."""
        return {e.name for e in elements if e.type == "class"}

    def get_functions(self, elements: list[DesignElement]) -> set[str]:
        """Get all function names (excluding methods)."""
        return {e.name for e in elements if e.type == "function"}

    def get_methods(self, elements: list[DesignElement], class_name: str) -> set[str]:
        """Get all method names for a specific class."""
        return {e.name for e in elements if e.type == "method" and e.parent == class_name}
