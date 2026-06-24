#!/usr/bin/env python3
"""Redesign checkers — detection methods extracted from RedesignAuditor.

Each checker function takes a code string and returns a list of
:class:`RedesignFinding` instances. The checkers are called by
:class:`RedesignAuditor` in sequence.

Categories
----------
- YAGNI:            unused imports, dead code, placeholder functions
- STDLIB:           custom implementations that have stdlib equivalents
- DUPLICATE:        repeated code that can be extracted
- OVERENGINEERING:  excessive abstraction or unnecessary config
"""

from __future__ import annotations

import builtins
import keyword
import re
from dataclasses import dataclass


@dataclass
class RedesignFinding:
    """A single redesign/simplification finding.

    Attributes:
        severity: One of CRITICAL|HIGH|MEDIUM|LOW.
        category: One of YAGNI|STDLIB|DUPLICATE|OVERENGINEERING|REDUNDANT_DEP.
        current: Description of the current code (what was detected).
        suggested: Suggested simplification (actionable guidance).
        saving_lines: Estimated number of lines saved by applying the suggestion.
    """

    severity: str  # CRITICAL|HIGH|MEDIUM|LOW
    category: str  # YAGNI|STDLIB|DUPLICATE|OVERENGINEERING|REDUNDANT_DEP
    current: str
    suggested: str
    saving_lines: int


def check_yagni(
    code: str,
    *,
    severity_critical: str,
    severity_high: str,
    severity_low: str,
    category_yagni: str,
    dead_code_threshold: int,
) -> list[RedesignFinding]:
    """Check for unnecessary code (YAGNI).

    Detects unused imports, placeholder functions, and dead code blocks.

    Args:
        code: Source code string to audit.
        severity_critical: Severity constant for critical findings.
        severity_high: Severity constant for high findings.
        severity_low: Severity constant for low findings.
        category_yagni: Category constant for YAGNI findings.
        dead_code_threshold: Line threshold for CRITICAL dead code.

    Returns:
        List of RedesignFinding instances for YAGNI issues.
    """
    findings: list[RedesignFinding] = []
    findings.extend(_detect_unused_imports(code, severity_low, category_yagni))
    findings.extend(_detect_placeholder_functions(code, severity_high, category_yagni))

    dead_code_lines = _count_dead_code_lines(code)
    if dead_code_lines >= dead_code_threshold:
        findings.append(
            RedesignFinding(
                severity=severity_critical,
                category=category_yagni,
                current=f"{dead_code_lines} lines of dead code (pass/comment-only blocks)",
                suggested="Remove dead code blocks entirely",
                saving_lines=dead_code_lines,
            )
        )
    elif dead_code_lines >= 10:
        findings.append(
            RedesignFinding(
                severity=severity_high,
                category=category_yagni,
                current=f"{dead_code_lines} lines of dead code (pass/comment-only blocks)",
                suggested="Remove dead code blocks",
                saving_lines=dead_code_lines,
            )
        )

    return findings


def check_stdlib_replacements(
    code: str,
    patterns: list[tuple[str, str, int]],
    *,
    severity_medium: str,
    category_stdlib: str,
) -> list[RedesignFinding]:
    """Check for custom implementations that stdlib already provides.

    Args:
        code: Source code string to audit.
        patterns: List of (regex, suggestion, saving_lines) tuples.
        severity_medium: Severity constant for medium findings.
        category_stdlib: Category constant for STDLIB findings.

    Returns:
        List of RedesignFinding instances for STDLIB issues.
    """
    findings: list[RedesignFinding] = []
    for pattern, suggestion, saving in patterns:
        if re.search(pattern, code):
            findings.append(
                RedesignFinding(
                    severity=severity_medium,
                    category=category_stdlib,
                    current=f"Custom implementation detected (matches /{pattern[:40]}.../)",
                    suggested=suggestion,
                    saving_lines=saving,
                )
            )
    return findings


def check_duplicates(
    code: str,
    *,
    severity_medium: str,
    category_duplicate: str,
    min_lines: int,
) -> list[RedesignFinding]:
    """Check for duplicate code blocks.

    Detects 3+ consecutive lines that are repeated elsewhere in the file.
    Uses improved normalization that preserves Python keywords and builtins
    to reduce false positives.

    Args:
        code: Source code string to audit.
        severity_medium: Severity constant for medium findings.
        category_duplicate: Category constant for DUPLICATE findings.
        min_lines: Minimum consecutive similar lines to flag.

    Returns:
        List of RedesignFinding instances for DUPLICATE issues.
    """
    findings: list[RedesignFinding] = []

    lines = code.splitlines()
    if len(lines) < min_lines * 2:
        return findings

    normalized = [line.rstrip() for line in lines]
    window_size = min_lines
    seen_blocks: dict[str, int] = {}
    reported_starts: set[int] = set()

    for i in range(len(normalized) - window_size + 1):
        block = "\n".join(normalized[i : i + window_size])
        # Skip blocks that are entirely blank or comments.
        if all(not line.strip() or line.strip().startswith("#") for line in normalized[i : i + window_size]):
            continue
        block_key = _normalize_block(block)
        if not block_key:
            continue

        if block_key in seen_blocks:
            first_start = seen_blocks[block_key]
            if first_start not in reported_starts:
                findings.append(
                    RedesignFinding(
                        severity=severity_medium,
                        category=category_duplicate,
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


def check_overengineering(
    code: str,
    patterns: list[tuple[str, str, int]],
    *,
    severity_high: str,
    category_overengineering: str,
    excessive_param_threshold: int,
) -> list[RedesignFinding]:
    """Check for excessive abstraction.

    Detects static-only classes, excessive parameters, and unnecessary patterns.

    Args:
        code: Source code string to audit.
        patterns: List of (regex, suggestion, saving_lines) tuples.
        severity_high: Severity constant for high findings.
        category_overengineering: Category constant for OVERENGINEERING findings.
        excessive_param_threshold: Max parameters before flagging.

    Returns:
        List of RedesignFinding instances for OVERENGINEERING issues.
    """
    findings: list[RedesignFinding] = []
    findings.extend(_detect_static_only_classes(code, severity_high, category_overengineering))
    findings.extend(_detect_excessive_params(code, severity_high, category_overengineering, excessive_param_threshold))

    for pattern, suggestion, saving in patterns:
        if re.search(pattern, code):
            findings.append(
                RedesignFinding(
                    severity=severity_high,
                    category=category_overengineering,
                    current=f"Overengineered pattern detected (matches /{pattern[:40]}.../)",
                    suggested=suggestion,
                    saving_lines=saving,
                )
            )

    return findings


# ------------------------------------------------------------------
# Private helpers
# ------------------------------------------------------------------

_BUILTIN_NAMES = frozenset(dir(builtins))


def _detect_unused_imports(code: str, severity: str, category: str) -> list[RedesignFinding]:
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
        if imported_name == "*":
            continue
        import_line = match.group(0)
        rest_of_code = code.replace(import_line, "", 1)
        occurrences = len(re.findall(rf"\b{re.escape(imported_name)}\b", rest_of_code))
        if occurrences == 0:
            findings.append(
                RedesignFinding(
                    severity=severity,
                    category=category,
                    current=f"Unused import: {imported_name}",
                    suggested=f"Remove unused import '{imported_name}'",
                    saving_lines=1,
                )
            )
    return findings


def _detect_placeholder_functions(code: str, severity: str, category: str) -> list[RedesignFinding]:
    """Detect functions whose body is only pass/TODO/NotImplementedError."""
    findings: list[RedesignFinding] = []
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
                severity=severity,
                category=category,
                current=f"Placeholder function '{func_name}' (body is pass/TODO/NotImplementedError)",
                suggested=f"Implement '{func_name}' or remove it if unused (YAGNI)",
                saving_lines=3,
            )
        )
    return findings


def _count_dead_code_lines(code: str) -> int:
    """Count lines in dead-code blocks.

    Only counts consecutive comment-only and pass-only lines (>=5 consecutive).
    Blank lines are NOT counted as dead code to avoid false positives from
    PEP 8 compliant spacing.
    """
    dead_lines = 0
    consecutive = 0
    for line in code.splitlines():
        stripped = line.strip()
        # Only count comments and pass as dead code, NOT blank lines.
        if stripped.startswith("#") or stripped == "pass":
            consecutive += 1
        else:
            if consecutive >= 5:
                dead_lines += consecutive
            consecutive = 0
    if consecutive >= 5:
        dead_lines += consecutive
    return dead_lines


def _normalize_block(block: str) -> str:
    """Normalize a code block for duplicate comparison.

    Replaces identifiers and string/number literals with placeholders.
    Python keywords AND builtins are preserved to reduce false positives.
    Identifiers are replaced with sequential names (id0, id1, ...) to
    preserve structural distinction between different variable names.
    """
    # Replace string literals.
    normalized = re.sub(r'"[^"]*"', '"X"', block)
    normalized = re.sub(r"'[^']*'", "'X'", normalized)
    # Replace numeric literals.
    normalized = re.sub(r"\b\d+\b", "N", normalized)

    # Replace identifiers that are NOT keywords or builtins.
    # Use sequential naming to preserve structural distinction.
    id_counter = [0]
    id_map: dict[str, str] = {}

    def replacer(m: re.Match[str]) -> str:
        word = m.group(0)
        if keyword.iskeyword(word) or word in _BUILTIN_NAMES:
            return word
        if word not in id_map:
            id_map[word] = f"id{id_counter[0]}"
            id_counter[0] += 1
        return id_map[word]

    normalized = re.sub(r"\b[a-z_]\w*\b", replacer, normalized, flags=re.IGNORECASE)
    return normalized.strip()


def _detect_static_only_classes(code: str, severity: str, category: str) -> list[RedesignFinding]:
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
        methods = re.findall(r"^\s+def\s+(\w+)\s*\(", body, re.MULTILINE)
        if not methods:
            continue
        static_decorators = re.findall(
            r"^\s*@(?:staticmethod|classmethod)\s*$", body, re.MULTILINE
        )
        if len(static_decorators) == len(methods) and len(methods) >= 2:
            findings.append(
                RedesignFinding(
                    severity=severity,
                    category=category,
                    current=(
                        f"Class '{class_name}' has only static/class methods "
                        f"({len(methods)} methods)"
                    ),
                    suggested=f"Replace class '{class_name}' with module-level functions",
                    saving_lines=5 + len(methods),
                )
            )
    return findings


def _detect_excessive_params(code: str, severity: str, category: str, threshold: int) -> list[RedesignFinding]:
    """Detect functions with more than threshold parameters."""
    findings: list[RedesignFinding] = []
    func_pattern = re.compile(
        r"^\s*def\s+(\w+)\s*\(([^)]*)\)\s*(?:->\s*\S+\s*)?:",
        re.MULTILINE | re.DOTALL,
    )
    for match in func_pattern.finditer(code):
        func_name = match.group(1)
        params_str = match.group(2).strip()
        if not params_str:
            continue
        params = [p.strip() for p in params_str.split(",") if p.strip()]
        params = [p for p in params if p not in ("self", "cls")]
        params = [p for p in params if not p.startswith("*")]
        if len(params) > threshold:
            findings.append(
                RedesignFinding(
                    severity=severity,
                    category=category,
                    current=(
                        f"Function '{func_name}' has {len(params)} parameters "
                        f"(threshold: {threshold})"
                    ),
                    suggested=(
                        f"Group related parameters into a dataclass or "
                        f"reduce parameter count in '{func_name}'"
                    ),
                    saving_lines=0,
                )
            )
    return findings
