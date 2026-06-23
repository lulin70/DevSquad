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

import keyword
import re
from dataclasses import dataclass

__all__ = ["RedesignAuditor", "RedesignFinding"]


@dataclass
class RedesignFinding:
    """A single redesign/simplification finding.

    Attributes
    ----------
    severity:
        One of CRITICAL|HIGH|MEDIUM|LOW.
    category:
        One of YAGNI|STDLIB|DUPLICATE|OVERENGINEERING|REDUNDANT_DEP.
    current:
        Description of the current code (what was detected).
    suggested:
        Suggested simplification (actionable guidance).
    saving_lines:
        Estimated number of lines saved by applying the suggestion.
    """

    severity: str  # CRITICAL|HIGH|MEDIUM|LOW
    category: str  # YAGNI|STDLIB|DUPLICATE|OVERENGINEERING|REDUNDANT_DEP
    current: str
    suggested: str
    saving_lines: int


class RedesignAuditor:
    """Audit code for simplification opportunities.

    The auditor runs four category-specific checkers in sequence and
    aggregates their findings. Each checker is a regex-based heuristic
    that flags common simplification patterns without executing code.

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

        # Context is accepted for future use (e.g. file_path-based exclusions).
        # Mark as used to satisfy linters; behavior is currently context-independent.
        _ = context

        findings: list[RedesignFinding] = []
        findings.extend(self._check_yagni(code))
        findings.extend(self._check_stdlib_replacements(code))
        findings.extend(self._check_duplicates(code))
        findings.extend(self._check_overengineering(code))
        return findings

    # ------------------------------------------------------------------
    # Category 1: YAGNI — unnecessary code
    # ------------------------------------------------------------------

    def _check_yagni(self, code: str) -> list[RedesignFinding]:
        """Check for unnecessary code.

        Detects:
        - Unused imports (heuristic: imported name not used elsewhere).
        - Dead code blocks (large ``pass``-only or commented-out regions).
        - Placeholder functions (body is only ``pass`` or ``TODO``).

        Severity:
        - CRITICAL if >50 lines of dead code detected.
        - HIGH for unused functions/classes and placeholder functions.
        - LOW for unused imports.
        """
        findings: list[RedesignFinding] = []

        # 1. Unused imports (heuristic).
        findings.extend(self._detect_unused_imports(code))

        # 2. Placeholder functions (body is only pass/TODO/NotImplementedError).
        findings.extend(self._detect_placeholder_functions(code))

        # 3. Dead code blocks (consecutive pass/comment-only lines).
        dead_code_lines = self._count_dead_code_lines(code)
        if dead_code_lines >= self.DEAD_CODE_CRITICAL_THRESHOLD:
            findings.append(
                RedesignFinding(
                    severity=self.SEVERITY_CRITICAL,
                    category=self.CATEGORY_YAGNI,
                    current=f"{dead_code_lines} lines of dead code (pass/comment-only blocks)",
                    suggested="Remove dead code blocks entirely",
                    saving_lines=dead_code_lines,
                )
            )
        elif dead_code_lines >= 10:
            findings.append(
                RedesignFinding(
                    severity=self.SEVERITY_HIGH,
                    category=self.CATEGORY_YAGNI,
                    current=f"{dead_code_lines} lines of dead code (pass/comment-only blocks)",
                    suggested="Remove dead code blocks",
                    saving_lines=dead_code_lines,
                )
            )

        return findings

    def _detect_unused_imports(self, code: str) -> list[RedesignFinding]:
        """Detect imports whose names don't appear elsewhere in the code."""
        findings: list[RedesignFinding] = []
        import_pattern = re.compile(
            r"^\s*(?:from\s+(\S+)\s+import\s+(\S+)|import\s+(\S+)(?:\s+as\s+(\S+))?)\s*$",
            re.MULTILINE,
        )
        for match in import_pattern.finditer(code):
            module_from, name_from, name_plain, alias = match.groups()
            imported_name = alias or name_plain or name_from
            if not imported_name:
                continue
            # Skip wildcard imports (always considered used).
            if imported_name == "*":
                continue
            # Count occurrences excluding the import line itself.
            import_line = match.group(0)
            rest_of_code = code.replace(import_line, "", 1)
            occurrences = len(re.findall(rf"\b{re.escape(imported_name)}\b", rest_of_code))
            if occurrences == 0:
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_LOW,
                        category=self.CATEGORY_YAGNI,
                        current=f"Unused import: {imported_name}",
                        suggested=f"Remove unused import '{imported_name}'",
                        saving_lines=1,
                    )
                )
        return findings

    def _detect_placeholder_functions(self, code: str) -> list[RedesignFinding]:
        """Detect functions whose body is only pass/TODO/NotImplementedError."""
        findings: list[RedesignFinding] = []
        # Match def name(...): followed by pass/TODO/NotImplementedError body.
        placeholder_pattern = re.compile(
            r"^\s*def\s+(\w+)\s*\([^)]*\)\s*(?:->\s*\S+\s*)?:\s*\n"
            r"(?:\s*(?:\"\"\"[^\"]*\"\"\"|'''[^']*''')\s*\n)?"
            r"\s*(?:pass|raise\s+NotImplementedError|\.\.\.|#\s*TODO[^\n]*)\s*$",
            re.MULTILINE,
        )
        for match in placeholder_pattern.finditer(code):
            func_name = match.group(1)
            findings.append(
                RedesignFinding(
                    severity=self.SEVERITY_HIGH,
                    category=self.CATEGORY_YAGNI,
                    current=f"Placeholder function '{func_name}' (body is pass/TODO/NotImplementedError)",
                    suggested=f"Implement '{func_name}' or remove it if unused (YAGNI)",
                    saving_lines=3,
                )
            )
        return findings

    def _count_dead_code_lines(self, code: str) -> int:
        """Count lines in dead-code blocks (consecutive pass/comment-only lines)."""
        dead_lines = 0
        consecutive = 0
        for line in code.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or stripped == "pass":
                consecutive += 1
            else:
                if consecutive >= 5:
                    dead_lines += consecutive
                consecutive = 0
        if consecutive >= 5:
            dead_lines += consecutive
        return dead_lines

    # ------------------------------------------------------------------
    # Category 2: STDLIB — custom implementations stdlib already provides
    # ------------------------------------------------------------------

    def _check_stdlib_replacements(self, code: str) -> list[RedesignFinding]:
        """Check for custom implementations that stdlib already provides.

        Detects custom JSON parsers, URL parsers, hash wrappers, etc.
        Severity: MEDIUM.
        """
        findings: list[RedesignFinding] = []
        for pattern, suggestion, saving in self.STDLIB_PATTERNS:
            if re.search(pattern, code):
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_MEDIUM,
                        category=self.CATEGORY_STDLIB,
                        current=f"Custom implementation detected (matches /{pattern[:40]}.../)",
                        suggested=suggestion,
                        saving_lines=saving,
                    )
                )
        return findings

    # ------------------------------------------------------------------
    # Category 3: DUPLICATE — repeated code blocks
    # ------------------------------------------------------------------

    def _check_duplicates(self, code: str) -> list[RedesignFinding]:
        """Check for duplicate code blocks.

        Detects 3+ consecutive lines that are repeated elsewhere in the file
        (heuristic: same indentation level and similar structure).

        Severity: MEDIUM.
        """
        findings: list[RedesignFinding] = []

        lines = code.splitlines()
        if len(lines) < self.DUPLICATE_MIN_LINES * 2:
            return findings

        # Normalize lines for comparison (strip trailing whitespace).
        normalized = [line.rstrip() for line in lines]

        # Slide a window of DUPLICATE_MIN_LINES and check if it appears later.
        window_size = self.DUPLICATE_MIN_LINES
        seen_blocks: dict[str, int] = {}
        reported_starts: set[int] = set()

        for i in range(len(normalized) - window_size + 1):
            block = "\n".join(normalized[i : i + window_size])
            # Skip blocks that are entirely blank or comments.
            if all(not line.strip() or line.strip().startswith("#") for line in normalized[i : i + window_size]):
                continue
            # Skip blocks with too much variance (e.g. all unique tokens).
            block_key = self._normalize_block(block)
            if not block_key:
                continue

            if block_key in seen_blocks:
                first_start = seen_blocks[block_key]
                if first_start not in reported_starts:
                    findings.append(
                        RedesignFinding(
                            severity=self.SEVERITY_MEDIUM,
                            category=self.CATEGORY_DUPLICATE,
                            current=(
                                f"Duplicate {window_size}-line block at lines "
                                f"{first_start + 1}-{first_start + window_size} "
                                f"and {i + 1}-{i + window_size}"
                            ),
                            suggested="Extract repeated block into a helper function",
                            saving_lines=window_size,
                        )
                    )
                    reported_starts.add(first_start)
            else:
                seen_blocks[block_key] = i

        return findings

    def _normalize_block(self, block: str) -> str:
        """Normalize a code block for duplicate comparison.

        Replaces identifiers and string/number literals with placeholders
        so that structurally similar blocks match. Python keywords are
        preserved to avoid false DUPLICATE findings (e.g. two functions
        that both use ``return`` should not match solely because every
        identifier collapsed to the same token).
        """
        # Replace string literals.
        normalized = re.sub(r'"[^"]*"', '"X"', block)
        normalized = re.sub(r"'[^']*'", "'X'", normalized)
        # Replace numeric literals.
        normalized = re.sub(r"\b\d+\b", "N", normalized)
        # Replace identifiers that are NOT Python keywords (variable/function names).
        def replacer(m):
            word = m.group(0)
            if keyword.iskeyword(word):
                return word
            return "id"
        normalized = re.sub(r"\b[a-z_]\w*\b", replacer, normalized, flags=re.IGNORECASE)
        return normalized.strip()

    # ------------------------------------------------------------------
    # Category 4: OVERENGINEERING — excessive abstraction
    # ------------------------------------------------------------------

    def _check_overengineering(self, code: str) -> list[RedesignFinding]:
        """Check for excessive abstraction.

        Detects:
        - Classes with only static methods.
        - Single-method interfaces (abstract base classes with one method).
        - Functions with excessive parameters (>5).
        - Unnecessary factory/builder/manager/handler/adapter patterns.

        Severity: HIGH.
        """
        findings: list[RedesignFinding] = []

        # 1. Classes with only static methods.
        findings.extend(self._detect_static_only_classes(code))

        # 2. Functions with excessive parameters.
        findings.extend(self._detect_excessive_params(code))

        # 3. Factory/Builder/Manager/Handler/Adapter patterns.
        for pattern, suggestion, saving in self.OVERENGINEERING_PATTERNS:
            if re.search(pattern, code):
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_HIGH,
                        category=self.CATEGORY_OVERENGINEERING,
                        current=f"Overengineered pattern detected (matches /{pattern[:40]}.../)",
                        suggested=suggestion,
                        saving_lines=saving,
                    )
                )

        return findings

    def _detect_static_only_classes(self, code: str) -> list[RedesignFinding]:
        """Detect classes that contain only static methods."""
        findings: list[RedesignFinding] = []
        class_pattern = re.compile(
            r"^class\s+(\w+)\s*(?:\([^)]*\))?\s*:\s*\n((?:\s+[^\n]*\n)*)",
            re.MULTILINE,
        )
        for match in class_pattern.finditer(code):
            class_name = match.group(1)
            body = match.group(2)
            if not body.strip():
                continue
            # Extract all method definitions in the class body.
            methods = re.findall(r"^\s+def\s+(\w+)\s*\(", body, re.MULTILINE)
            if not methods:
                continue
            # Check if all methods are static/class methods.
            static_decorators = re.findall(
                r"^\s*@(?:staticmethod|classmethod)\s*$", body, re.MULTILINE
            )
            # If every method has a static/class decorator, flag it.
            if len(static_decorators) == len(methods) and len(methods) >= 2:
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_HIGH,
                        category=self.CATEGORY_OVERENGINEERING,
                        current=(
                            f"Class '{class_name}' has only static/class methods "
                            f"({len(methods)} methods)"
                        ),
                        suggested=(
                            f"Replace class '{class_name}' with module-level functions"
                        ),
                        saving_lines=5 + len(methods),
                    )
                )
        return findings

    def _detect_excessive_params(self, code: str) -> list[RedesignFinding]:
        """Detect functions with more than 5 parameters."""
        findings: list[RedesignFinding] = []
        # Match def name(param1, param2, ...): across multiple lines.
        func_pattern = re.compile(
            r"^\s*def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*\S+\s*)?:",
            re.MULTILINE | re.DOTALL,
        )
        for match in func_pattern.finditer(code):
            func_name = match.group(1)
            params_str = match.group(2).strip()
            if not params_str:
                continue
            # Count parameters (ignore *args, **kwargs, defaults, type hints).
            params = [p.strip() for p in params_str.split(",") if p.strip()]
            # Remove self/cls from count.
            params = [p for p in params if p not in ("self", "cls")]
            # Remove *args, **kwargs from count (they're variadic).
            params = [p for p in params if not p.startswith("*")]
            if len(params) > self.EXCESSIVE_PARAM_THRESHOLD:
                findings.append(
                    RedesignFinding(
                        severity=self.SEVERITY_HIGH,
                        category=self.CATEGORY_OVERENGINEERING,
                        current=(
                            f"Function '{func_name}' has {len(params)} parameters "
                            f"(threshold: {self.EXCESSIVE_PARAM_THRESHOLD})"
                        ),
                        suggested=(
                            f"Group related parameters into a dataclass or "
                            f"reduce parameter count in '{func_name}'"
                        ),
                        saving_lines=0,
                    )
                )
        return findings
