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
        return findings
