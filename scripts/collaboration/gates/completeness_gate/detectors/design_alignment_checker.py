"""DesignAlignmentChecker - Compares code against P3 design document.

Parses P3 markdown for class/function definitions and compares with
AST-parsed code to detect missing/extra implementations.
"""

from pathlib import Path
from typing import Any

from scripts.collaboration.gates.completeness_gate.parsers.ast_analyzer import ASTAnalyzer
from scripts.collaboration.gates.completeness_gate.parsers.markdown_parser import MarkdownParser
from scripts.collaboration.gates.completeness_gate.utils.score_calculator import calculate_alignment_score


class DesignAlignmentChecker:
    """Checks alignment between design document and implementation."""

    def __init__(self) -> None:
        self.ast_analyzer = ASTAnalyzer()
        self.md_parser = MarkdownParser()

    def check(self, target_paths: list[Path], p3_doc: Path | None = None) -> dict[str, Any]:
        """
        Check code alignment with P3 design document.

        Args:
            target_paths: List of Python file paths to check
            p3_doc: Path to P3 markdown design document

        Returns:
            {
                "alignment_score": float,  # 0.0-1.0
                "missing_elements": [{"name": str, "type": str, "parent": str}, ...],
                "extra_elements": [{"name": str, "type": str, "parent": str}, ...],
                "message": str (optional warning)
            }
        """
        # Handle missing P3 document
        if not p3_doc or not p3_doc.exists():
            return {
                "alignment_score": 1.0,
                "missing_elements": [],
                "extra_elements": [],
                "message": "No P3 document provided - alignment check skipped",
            }

        # Parse design document
        design_elements = self.md_parser.parse_design_doc(p3_doc)
        if not design_elements:
            # Empty design doc means nothing required
            return {
                "alignment_score": 1.0,
                "missing_elements": [],
                "extra_elements": [],
                "message": "P3 document is empty - no requirements to check",
            }

        # Parse all code files
        code_elements = []
        for path in target_paths:
            elements = self.ast_analyzer.analyze_file(path)
            code_elements.extend(elements)

        # Normalize for case-insensitive comparison
        design_set = self._normalize_elements(design_elements)
        code_set = self._normalize_elements(code_elements)

        # Create comparison keys (first 3 elements of tuple)
        design_keys = {(e[0], e[1], e[2]) for e in design_set}
        code_keys = {(e[0], e[1], e[2]) for e in code_set}

        # Find missing and extra elements
        missing_keys = design_keys - code_keys
        extra_keys = code_keys - design_keys

        # Map back to full tuples for original names
        missing = {e for e in design_set if (e[0], e[1], e[2]) in missing_keys}
        extra = {e for e in code_set if (e[0], e[1], e[2]) in extra_keys}

        # Calculate alignment score (implemented / required)
        required_count = len(design_keys)
        implemented_count = len(design_keys.intersection(code_keys))
        alignment_score = calculate_alignment_score(required_count, implemented_count)

        return {
            "alignment_score": alignment_score,
            "missing_elements": [self._element_to_dict(e) for e in missing],
            "extra_elements": [self._element_to_dict(e) for e in extra],
        }

    def _normalize_elements(self, elements: list) -> set:
        """
        Normalize elements for case-insensitive matching.

        Converts to lowercase for comparison and creates a set of tuples.
        Each tuple is (normalized_name, type, normalized_parent, original_name, original_parent).
        """
        normalized = set()
        for elem in elements:
            # Handle both CodeElement and DesignElement
            name_lower = elem.name.lower()
            # Convert CamelCase/snake_case variants for matching
            name_normalized = name_lower.replace("_", "")
            elem_type = elem.type
            parent_lower = elem.parent.lower() if elem.parent else None

            # Store both normalized and original names
            normalized.add((name_normalized, elem_type, parent_lower, elem.name, elem.parent))

        return normalized

    def _element_to_dict(self, element: tuple) -> dict[str, Any]:
        """Convert normalized element tuple to dictionary."""
        name_normalized, elem_type, parent_lower, original_name, original_parent = element
        result = {
            "name": original_name,  # Use original name, not normalized
            "type": elem_type,
        }
        if original_parent:
            result["parent"] = original_parent
        return result
