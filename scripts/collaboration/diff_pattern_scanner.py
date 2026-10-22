"""Deterministic pattern scan over unified-diff added lines (V4.8.0 P1-R1).

This module wires the three existing ReviewCheckers regex families into the
review diff channel (design doc ``V4.8.0_R1_devsquad_gate_DESIGN.md`` §7.1):
anti-pattern, secret, and SQL-injection patterns run over ADDED lines only
and produce structured ``LifecycleFinding`` entries for
``result.details["lifecycle_findings"]``.

Zero new check logic: every regex is imported from
:class:`~scripts.collaboration.review_checkers.ReviewCheckers` and every
severity/suggestion follows that class's existing classification. The BV
category is a wiring convention (document_scanner precedent: BV codes are
used as a severity taxonomy beyond their route-specific names):

- critical families (secrets, SQL injection, eval/exec) -> ``VULN-4``
- warning families (bare except, TODO/FIXME, print debugging) -> ``BREAK-2``

The matched text is never copied into findings — only the pattern name,
match count, file, and line range are disclosed (secret-safe by design).
"""

from __future__ import annotations

import re
from typing import Any

from .lifecycle_break_vuln import phases_for_category
from .models_lifecycle import LifecycleFinding
from .review_checkers import ReviewCheckers
from .review_input import _header_path, _strip_diff_prefix

# Pattern-family wiring table: (family source, BV category, severity, suggestion).
# Severity follows ReviewCheckers' own classification:
# - _check_security -> critical; _check_error_handling (eval/exec) -> critical
# - _check_anti_patterns (todo/print/bare_except) -> warning
_PATTERN_FAMILY_WIRING: tuple[tuple[tuple[tuple[str, re.Pattern[str]], ...], str, str, str], ...] = (
    (
        ReviewCheckers._SECRET_PATTERNS,
        "VULN-4",
        "critical",
        "Move secrets to environment variables or a secret manager.",
    ),
    (
        ReviewCheckers._SQL_INJECTION_PATTERNS,
        "VULN-4",
        "critical",
        "Use parameterized queries instead of string formatting.",
    ),
    # _ANTI_PATTERN_REGEXES: eval/exec are critical in ReviewCheckers'
    # _check_error_handling; the rest are warnings in _check_anti_patterns.
    (
        ReviewCheckers._ANTI_PATTERN_REGEXES,
        "BREAK-2",
        "warning",
        "Resolve the {name} anti-pattern before merge.",
    ),
)

_HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@")


def _iter_added_lines(diff: str) -> list[tuple[str, int, str]]:
    """Yield (file_path, new_line_number, text) for ADDED lines only."""
    added: list[tuple[str, int, str]] = []
    current_file: str | None = None
    new_line = 0
    for line in diff.splitlines():
        if line.startswith("diff --git "):
            current_file = None
            continue
        if line.startswith("+++ "):
            header_path = _header_path(line)
            if header_path and header_path != "/dev/null":
                current_file = _strip_diff_prefix(header_path)
            continue
        hunk = _HUNK_HEADER.match(line)
        if hunk:
            new_line = int(hunk.group(1))
            continue
        if line.startswith("+"):
            # Strip the leading "+" — the added content is what gets scanned.
            # A "+line" before any "+++" header cannot occur in a git diff;
            # skip scanning it but still advance the counter.
            if current_file is not None:
                added.append((current_file, new_line, line[1:]))
            new_line += 1
        elif line.startswith(" "):
            # Context lines advance the new-side counter; removed lines do not.
            new_line += 1
    return added


def scan_diff_patterns(diff: str) -> list[LifecycleFinding]:
    """Scan unified-diff ADDED lines with the three ReviewCheckers families.

    Returns one :class:`LifecycleFinding` per (pattern, file) aggregation —
    mirroring ReviewCheckers' own ``detected N time(s) in file`` style — with
    the matched text deliberately excluded (secret-safe disclosure).
    """
    if not isinstance(diff, str) or not diff.strip():
        return []

    added = _iter_added_lines(diff)
    if not added:
        return []

    findings: list[LifecycleFinding] = []
    for patterns, category, severity, suggestion_template in _PATTERN_FAMILY_WIRING:
        # Aggregate per (pattern, file): list of matching new line numbers.
        hits: dict[tuple[str, str], list[int]] = {}
        for name, pattern in patterns:
            for file_path, line_no, text in added:
                if pattern.search(text):
                    hits.setdefault((name, file_path), []).append(line_no)
        for (name, file_path), line_numbers in sorted(hits.items()):
            first, last = min(line_numbers), max(line_numbers)
            line_range = str(first) if first == last else f"{first}-{last}"
            # eval/exec ride the ANTI_PATTERN table but are critical in
            # ReviewCheckers' _check_error_handling; keep that split here.
            finding_severity = (
                "critical" if severity == "critical" or name in ("eval_usage", "exec_usage") else "warning"
            )
            suggestion = suggestion_template.format(name=name)
            if name in ("eval_usage", "exec_usage"):
                suggestion = f"Avoid {name} — it is a security risk."
            findings.append(
                LifecycleFinding(
                    category=category,
                    rule_id=f"diff-{name}",
                    severity=finding_severity,
                    lifecycle_phase=phases_for_category(category)[0],
                    artifact="diff",
                    status="detected",
                    description=(
                        f"diff pattern '{name}' matched "
                        f"{len(line_numbers)} time(s) in {file_path} "
                        f"(added line {line_range})"
                    ),
                    evidence=[
                        {
                            "type": "location",
                            "file_path": file_path,
                            "line_range": line_range,
                            "matches": len(line_numbers),
                        }
                    ],
                    file_path=file_path,
                    line_range=line_range,
                    suggestion=suggestion,
                )
            )
    return findings


def diff_pattern_scan_to_dicts(diff: str) -> list[dict[str, Any]]:
    """JSON-compatible wrapper for the CLI wiring site."""
    return [finding.to_dict() for finding in scan_diff_patterns(diff)]


__all__ = ["scan_diff_patterns", "diff_pattern_scan_to_dicts"]
