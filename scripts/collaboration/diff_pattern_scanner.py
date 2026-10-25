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
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from .lifecycle_break_vuln import phases_for_category
from .models_lifecycle import LifecycleFinding
from .review_checkers import ReviewCheckers
from .review_filter import ReviewFilterConfig, filter_review_paths
from .review_input import _header_path, _strip_diff_prefix
from .rule_engine import RuleConfigError, default_sources, resolve

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

# V4.9.0 dogfood finding (PR #71, 2026-10-25): a print statement to stdout
# is the product interface of the CLI command family (``scripts/cli*.py`` —
# same output convention as cli_risks/cli_audit), not debug residue. The
# print_debug anti-pattern skips those files; every other pattern family
# (secrets, SQL injection, eval/exec) still applies to them in full.
_CLI_PATH_PREFIX = "scripts/cli"


def _is_cli_output_layer(file_path: str) -> bool:
    """True for the CLI command-family modules where a print statement is the interface."""
    return file_path.replace("\\", "/").startswith(_CLI_PATH_PREFIX)


# V4.8.1 F-D1 (design §7.4): secret-leak findings are meaningful in ANY
# review-retained file (a document can leak a real key); the other families
# (anti-patterns, SQL injection) are code smells — product judgments only
# for source-kind files, so doc text quoting an anti-pattern is not a finding.
_SECRET_RULE_IDS = frozenset(f"diff-{name}" for name, _ in ReviewCheckers._SECRET_PATTERNS)


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
                if name == "print_debug" and _is_cli_output_layer(file_path):
                    continue
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


def filter_diff_pattern_findings(
    findings: Sequence[LifecycleFinding],
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    repo_root: str | Path | None = None,
    rule: str | Path | None = None,
) -> list[LifecycleFinding]:
    """Apply the deterministic review path gates to diff pattern findings.

    V4.8.1 F-D1 fix (design doc §7.4): findings are product-meaningful only
    for paths the deterministic review filter would retain — user
    ``--include/--exclude`` globs, built-in default excludes, and the
    unsupported-extension gate apply with the exact semantics of the
    changeset face, reusing
    :func:`~scripts.collaboration.review_filter.filter_review_paths` (same
    gate sequence, same ``rule_engine.matches`` globs). Content-driven gates
    (binary / too_large) are inert by construction on the diff face: no file
    contents are passed and ``max_size_bytes`` is disabled, so the decision
    is purely path/extension-deterministic.

    Family split on top of the path gates: secret findings survive for any
    review-retained path (a document can leak a real key); code-smell
    families (anti-patterns, SQL injection) additionally require
    ``kind == "source"`` — doc text quoting an anti-pattern is prose, not
    a product defect. ``resolve`` failures fail closed to non-source.
    """
    if not findings:
        return []
    paths = sorted({finding.file_path for finding in findings if finding.file_path})
    rule_sources = default_sources(repo_root, rule)
    config = ReviewFilterConfig(
        max_size_bytes=None,
        user_include=tuple(include or ()),
        user_exclude=tuple(exclude or ()),
        rule_sources=rule_sources,
    )
    result = filter_review_paths(paths, config=config)
    retained = set(result.retained_paths)

    source_paths: set[str] = set()
    for path in retained:
        try:
            resolution = resolve(path, rule_sources)
        except RuleConfigError:
            continue
        if resolution.body.get("kind") == "source":
            source_paths.add(path)

    return [
        finding
        for finding in findings
        if finding.file_path in retained and (finding.rule_id in _SECRET_RULE_IDS or finding.file_path in source_paths)
    ]


def diff_pattern_scan_to_dicts(
    diff: str,
    *,
    include: Sequence[str] = (),
    exclude: Sequence[str] = (),
    repo_root: str | Path | None = None,
    rule: str | Path | None = None,
) -> list[dict[str, Any]]:
    """JSON-compatible wrapper for the CLI wiring site.

    V4.8.1 F-D1: the deterministic path gates (user include/exclude,
    unsupported extensions, built-in default excludes) filter the findings
    face with review_filter semantics before disclosure.
    """
    findings = filter_diff_pattern_findings(
        scan_diff_patterns(diff),
        include=include,
        exclude=exclude,
        repo_root=repo_root,
        rule=rule,
    )
    return [finding.to_dict() for finding in findings]


__all__ = ["filter_diff_pattern_findings", "scan_diff_patterns", "diff_pattern_scan_to_dicts"]
