#!/usr/bin/env python3
"""
RedesignAuditor — Third-stage code simplicity audit.

Inspired by Leonxlnx/taste-skill's redesign-audit protocol.
Checks if code can be simpler, shorter, or eliminated entirely.

Review categories
-----------------
- YAGNI:            Unnecessary code/functions/classes
- STDLIB:           Custom implementations that have stdlib equivalents
- DUPLICATE:        Repeated code that can be extracted
- OVERENGINEERING:  Excessive abstraction or unnecessary config
- REDUNDANT_DEP:    Dependencies that could be removed

Integration
-----------
The auditor is usable standalone via :meth:`RedesignAuditor.audit`.
It returns a list of :class:`RedesignFinding` instances, each describing
one simplification opportunity with severity, category, current code
description, suggested simplification, and estimated line savings.

Usage::

    from scripts.collaboration.redesign_auditor import RedesignAuditor

    auditor = RedesignAuditor()
    findings = auditor.audit(code_string)
    for f in findings:
        print(f"[{f.severity}] {f.category}: {f.suggested} (saves ~{f.saving_lines} lines)")
"""

from __future__ import annotations

import ast
from html import escape

from .redesign_checkers import (
    RedesignFinding,
    check_duplicates,
    check_overengineering,
    check_stdlib_replacements,
    check_yagni,
)

__all__ = ["RedesignAuditor", "RedesignFinding"]


class RedesignAuditor:
    """Audit code for simplification opportunities.

    The auditor runs four category-specific checkers in sequence and
    aggregates their findings. Each checker is a heuristic that flags
    common simplification patterns without executing code.

    Categories
    ----------
    1. YAGNI             — unused imports, dead code, placeholder functions.
    2. STDLIB            — custom implementations that stdlib provides.
    3. DUPLICATE         — repeated similar lines (3+ consecutive).
    4. OVERENGINEERING   — classes with only static methods, single-method
                           interfaces, excessive parameters, factory patterns.
    """

    # Severity constants.
    SEVERITY_CRITICAL = "CRITICAL"
    SEVERITY_HIGH = "HIGH"
    SEVERITY_MEDIUM = "MEDIUM"
    SEVERITY_LOW = "LOW"

    # Category constants.
    CATEGORY_YAGNI = "YAGNI"
    CATEGORY_STDLIB = "STDLIB"
    CATEGORY_DUPLICATE = "DUPLICATE"
    CATEGORY_OVERENGINEERING = "OVERENGINEERING"
    CATEGORY_REDUNDANT_DEP = "REDUNDANT_DEP"
    CATEGORY_DELETION_TEST = "DELETION_TEST"

    # Threshold for CRITICAL dead-code detection (lines).
    DEAD_CODE_CRITICAL_THRESHOLD = 50

    # Threshold for excessive function parameters.
    EXCESSIVE_PARAM_THRESHOLD = 5

    # Minimum consecutive similar lines to flag DUPLICATE.
    DUPLICATE_MIN_LINES = 3

    # Stdlib replacement patterns: (regex, suggestion, saving_lines).
    STDLIB_PATTERNS: list[tuple[str, str, int]] = [
        (
            r"(?i)\bdef\s+\w+\s*\([^)]*\)\s*:\s*\n\s*\"\"\"[^\"]*\"\"\"\s*\n\s*return\s+json\.loads?\(",
            "Use json.loads() / json.dumps() directly",
            5,
        ),
        (
            r"(?i)\bdef\s+parse_url\b|def\s+url_parse\b",
            "Use urllib.parse.urlparse() instead of custom URL parser",
            8,
        ),
        (
            r"(?i)\bdef\s+\w*hash\w*\s*\([^)]*\)\s*:\s*\n\s*(?:return\s+)?hashlib\.",
            "Use hashlib directly instead of wrapping it",
            4,
        ),
        (
            r"(?i)\bdef\s+\w*base64\w*\s*\([^)]*\)\s*:\s*\n\s*(?:return\s+)?base64\.",
            "Use base64 module directly instead of wrapping it",
            4,
        ),
        (
            r"(?i)\bdef\s+\w*uuid\w*\s*\([^)]*\)\s*:\s*\n\s*(?:return\s+)?uuid\.",
            "Use uuid.uuid4() directly instead of wrapping it",
            4,
        ),
        (
            r"(?i)\bclass\s+\w*(?:Json|JSON)(?:Parser|Encoder|Decoder)\b",
            "Replace custom JSON parser with stdlib json module",
            15,
        ),
        (
            r"(?i)\bclass\s+\w*(?:Url|URL)(?:Parser|Builder)\b",
            "Replace custom URL parser with stdlib urllib.parse",
            15,
        ),
        (
            r"(?i)\bdef\s+\w*(?:deep_copy|deepClone)\w*\s*\(",
            "Use copy.deepcopy() instead of custom deep copy",
            10,
        ),
        (
            r"(?i)\bdef\s+\w*(?:counter|frequency)\w*\s*\([^)]*\)\s*:\s*\n\s*(?:result\s*=\s*)?\{\}",
            "Use collections.Counter instead of custom counter",
            8,
        ),
        (
            r"(?i)\bdef\s+\w*(?:merge_dict|combine_dict)\w*\s*\(",
            "Use {**a, **b} or dict.update() instead of custom merge",
            6,
        ),
    ]

    # Overengineering patterns: (regex, suggestion, saving_lines).
    OVERENGINEERING_PATTERNS: list[tuple[str, str, int]] = [
        (
            r"(?i)\bclass\s+\w*Factory\w*\b",
            "Replace factory class with direct constructor call",
            12,
        ),
        (
            r"(?i)\bclass\s+\w*Builder\w*\b",
            "Replace builder class with keyword arguments",
            15,
        ),
        (
            r"(?i)\bclass\s+\w*Manager\w*\b(?![\s\S]*def\s+\w+\s*\(self)",
            "Replace empty manager class with module-level functions",
            10,
        ),
        (
            r"(?i)\bclass\s+\w*Handler\w*\b(?![\s\S]*def\s+\w+\s*\(self)",
            "Replace empty handler class with function",
            8,
        ),
        (
            r"(?i)\bclass\s+\w*Adapter\w*\b(?![\s\S]*def\s+\w+\s*\(self)",
            "Replace empty adapter class with direct call",
            8,
        ),
    ]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def audit(self, code: str, context: dict | None = None) -> list[RedesignFinding]:
        """Audit code string for redesign opportunities.

        Parameters
        ----------
        code:
            Source code string to audit.
        context:
            Optional context dict (e.g. ``{"file_path": "..."}``).
            Currently informational only.

        Returns
        -------
        list[RedesignFinding]
            Findings from all four category checkers, in order:
            YAGNI, STDLIB, DUPLICATE, OVERENGINEERING.
        """
        if not code or not code.strip():
            return []

        _ = context  # Reserved for future use.

        findings: list[RedesignFinding] = []
        findings.extend(
            check_yagni(
                code,
                severity_critical=self.SEVERITY_CRITICAL,
                severity_high=self.SEVERITY_HIGH,
                severity_low=self.SEVERITY_LOW,
                category_yagni=self.CATEGORY_YAGNI,
                dead_code_threshold=self.DEAD_CODE_CRITICAL_THRESHOLD,
            )
        )
        findings.extend(
            check_stdlib_replacements(
                code,
                self.STDLIB_PATTERNS,
                severity_medium=self.SEVERITY_MEDIUM,
                category_stdlib=self.CATEGORY_STDLIB,
            )
        )
        findings.extend(
            check_duplicates(
                code,
                severity_medium=self.SEVERITY_MEDIUM,
                category_duplicate=self.CATEGORY_DUPLICATE,
                min_lines=self.DUPLICATE_MIN_LINES,
            )
        )
        findings.extend(
            check_overengineering(
                code,
                self.OVERENGINEERING_PATTERNS,
                severity_high=self.SEVERITY_HIGH,
                category_overengineering=self.CATEGORY_OVERENGINEERING,
                excessive_param_threshold=self.EXCESSIVE_PARAM_THRESHOLD,
            )
        )
        # Module 6 (Matt P0-3): deletion test
        findings.extend(self.deletion_test(code))
        return findings

    # ------------------------------------------------------------------
    # Module 6 (Matt P0-3): Deletion Test
    # ------------------------------------------------------------------

    def deletion_test(
        self, code: str, file_path: str = ""
    ) -> list[RedesignFinding]:
        """Run Matt Pocock's deletion test on source code.

        For each function/class, asks: "If I delete this, what breaks?"

        Detects:
        1. Pass-through functions — body just delegates to another call.
        2. Dead code — defined but never referenced in the same file.
        3. Single-use functions — called only once (inlining candidate).

        Args:
            code: Python source code string to analyze.
            file_path: File path for reporting (informational).

        Returns:
            List of RedesignFinding with category DELETION_TEST.
        """
        findings: list[RedesignFinding] = []
        if not code or not code.strip():
            return findings
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return findings

        # Collect top-level function and class names
        definitions: dict[str, ast.AST] = {}
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                definitions[node.name] = node

        # Count references (Name nodes and Attribute nodes)
        call_counts: dict[str, int] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                call_counts[node.id] = call_counts.get(node.id, 0) + 1
            elif isinstance(node, ast.Attribute):
                call_counts[node.attr] = call_counts.get(node.attr, 0) + 1

        for name, node in definitions.items():
            # Skip dunder methods
            if name.startswith("__") and name.endswith("__"):
                continue

            # Check for pass-through (functions only)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and self._is_pass_through(node):
                body_lines = (node.end_lineno or node.lineno) - node.lineno + 1
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_MEDIUM,
                        category=self.CATEGORY_DELETION_TEST,
                        current=(
                            f"Function ``{name}`` is a pass-through "
                            f"(body just delegates to another call)"
                            + (f" in {file_path}" if file_path else "")
                        ),
                        suggested=(
                            f"Delete ``{name}`` and call the delegated "
                            f"function directly, or deepen it with real logic"
                        ),
                        saving_lines=body_lines,
                    )
                )
                continue

            # Reference count: FunctionDef.name / ClassDef.name are string
            # attributes (not ast.Name nodes), so ast.walk does not count the
            # definition itself. ref_count therefore equals the number of
            # actual references (call sites / attribute accesses).
            ref_count = call_counts.get(name, 0)
            actual_callers = ref_count

            if actual_callers == 0:
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_HIGH,
                        category=self.CATEGORY_DELETION_TEST,
                        current=(
                            f"Function/class ``{name}`` is defined but never "
                            f"referenced in the same file"
                        ),
                        suggested=(
                            f"Delete ``{name}`` if truly unused. "
                            f"Verify cross-file references before deleting."
                        ),
                        saving_lines=3,
                    )
                )
            elif actual_callers == 1:
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_LOW,
                        category=self.CATEGORY_DELETION_TEST,
                        current=(
                            f"Function/class ``{name}`` is called only once "
                            f"— inlining candidate"
                        ),
                        suggested=(
                            f"Consider inlining ``{name}`` at the call site "
                            f"to reduce indirection"
                        ),
                        saving_lines=2,
                    )
                )

        return findings

    def _is_pass_through(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef
    ) -> bool:
        """Check if a function is a pass-through (body just delegates).

        A pass-through function has a body consisting of only a docstring
        and a single return statement that calls another function, or just
        a ``pass`` statement.

        Args:
            node: AST FunctionDef node to check.

        Returns:
            True if the function is a pass-through.
        """
        # Filter out docstrings (Expr nodes with Constant string values)
        body = [
            n
            for n in node.body
            if not (
                isinstance(n, ast.Expr)
                and isinstance(n.value, ast.Constant)
                and isinstance(n.value.value, str)
            )
        ]
        if len(body) != 1:
            return False
        stmt = body[0]
        # return other_func(...) or return self.other_func(...)
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Call):
            return True
        # pass
        return isinstance(stmt, ast.Pass)

    # ------------------------------------------------------------------
    # Module 6 (Matt P0-3): HTML Report
    # ------------------------------------------------------------------

    def to_html_report(
        self,
        findings: list[RedesignFinding],
        title: str = "Redesign Audit Report",
    ) -> str:
        """Generate an HTML report from redesign findings.

        Produces a standalone HTML document with a color-coded table of
        findings, sorted by severity. No external dependencies (inline CSS).

        Args:
            findings: List of RedesignFinding to render.
            title: Report title (defaults to "Redesign Audit Report").

        Returns:
            HTML string suitable for writing to a file.
        """
        severity_colors = {
            "CRITICAL": "#dc2626",
            "HIGH": "#ea580c",
            "MEDIUM": "#ca8a04",
            "LOW": "#2563eb",
        }
        severity_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        sorted_findings = sorted(
            findings, key=lambda f: severity_order.get(f.severity, 99)
        )

        rows_html: list[str] = []
        for f in sorted_findings:
            color = severity_colors.get(f.severity, "#6b7280")
            rows_html.append(
                "<tr>"
                f'<td style="color:{color};font-weight:bold">{escape(f.severity)}</td>'
                f"<td>{escape(f.category)}</td>"
                f"<td>{escape(f.current)}</td>"
                f"<td>{escape(f.suggested)}</td>"
                f'<td style="text-align:right">{f.saving_lines}</td>'
                "</tr>"
            )

        total_savings = sum(f.saving_lines for f in findings)
        by_category: dict[str, int] = {}
        for f in findings:
            by_category[f.category] = by_category.get(f.category, 0) + 1

        summary_items = [
            f"<li>{escape(cat)}: {count}</li>"
            for cat, count in sorted(by_category.items())
        ]

        return (
            "<!DOCTYPE html>\n"
            '<html lang="en">\n'
            "<head>\n"
            '<meta charset="utf-8">\n'
            f"<title>{escape(title)}</title>\n"
            "<style>\n"
            "body { font-family: -apple-system, sans-serif; margin: 2rem; }\n"
            "h1 { color: #1f2937; }\n"
            "table { border-collapse: collapse; width: 100%; }\n"
            "th, td { border: 1px solid #d1d5db; padding: 0.5rem; text-align: left; }\n"
            "th { background-color: #f3f4f6; }\n"
            ".summary { background: #f9fafb; padding: 1rem; margin: 1rem 0; }\n"
            "</style>\n"
            "</head>\n"
            "<body>\n"
            f"<h1>{escape(title)}</h1>\n"
            f'<div class="summary">\n'
            f"<p><strong>Total findings:</strong> {len(findings)}</p>\n"
            f"<p><strong>Estimated lines saved:</strong> {total_savings}</p>\n"
            f"<ul>{''.join(summary_items)}</ul>\n"
            "</div>\n"
            "<table>\n"
            "<thead><tr>"
            "<th>Severity</th><th>Category</th><th>Current</th>"
            "<th>Suggested</th><th>Lines Saved</th>"
            "</tr></thead>\n"
            "<tbody>\n"
            + "\n".join(rows_html)
            + "\n</tbody>\n"
            "</table>\n"
            "</body>\n"
            "</html>"
        )
