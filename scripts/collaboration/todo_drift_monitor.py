#!/usr/bin/env python3
"""Todo drift monitor — V4.3.0 P0-2.

Lightweight scanner that detects new TODO/FIXME/HACK/XXX/WIP/待办/待修复
markers in ``scripts/`` and reports any that are not registered in
``docs/TECH_DEBT.md``. Designed as a pre-commit hook + CI lint job that
**blocks** the introduction of unregistered tech debt.

Architecture reference: docs/architecture/V4.3.0_ARCHITECTURE.md §3.1, §4.1.
Test plan: docs/testing/V4.3.0_TEST_PLAN.md §3 (P0-2 row).

Design constraints (PRD P0-2):
- <100 lines, radon cc < D
- Regex case-insensitive + extended marker set (TODO/FIXME/HACK/XXX/WIP/待办/待修复)
- Read-only — does not modify source code
- Does not scan ``tests/`` or ``__pycache__`` (only ``scripts/`` by default)

Exit codes (when invoked as ``python -m``):
- 0: No unregistered tech debt
- 1: New unregistered tech debt found (blocks commit/CI)
- 2: Tool error (e.g. tracker file missing)
"""

from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Case-insensitive markers covering English + Chinese.
# ``XXX`` and ``WIP`` are included per P0-2 architecture spec §4.1.
# ``待办`` and ``待修复`` cover Chinese markers (DevSquad is bilingual).
#
# V4.3.0 P0-2 refinement: the pattern requires comment context — the marker
# must appear after ``#`` (Python comment) at the start of the comment text,
# and must be followed by ``:`` or whitespace or end-of-line. This excludes
# the 57 false positives found in the initial scan (variable names like
# ``todos``, string literals like ``"TODO"``, enum definitions like
# ``TODO = "todo"``, descriptive comments like ``# TODO/FIXME/HACK comments``,
# and substring matches like ``wipe`` → ``wip``).
MARKER_PATTERN = re.compile(
    r"#\s*(TODO|FIXME|HACK|XXX|WIP|待办|待修复)(?=[\s:]|$)",
    re.IGNORECASE,
)

# Default scan root and tracker path (relative to repo root).
DEFAULT_SCAN_ROOT = "scripts"
DEFAULT_TRACKER_PATH = "docs/TECH_DEBT.md"
DEFAULT_EXCLUDE_DIRS = ("tests", "__pycache__", ".venv", ".mypy_cache", ".pytest_cache")

# Files registered in TECH_DEBT.md by line number — we match the literal
# ``path/to/file.py:NN`` pattern that the tracker uses in its entries.
# The path may be relative (``scripts/...``) or absolute (``/tmp/.../scripts/...``).
# We capture the full non-whitespace path up to ``:line_number``.
_TRACKER_LOCATION_PATTERN = re.compile(
    r"(\S*(?:scripts|tests)/\S+?\.py):(\d+)",
    re.IGNORECASE,
)


@dataclass
class TechDebtEntry:
    """A single TODO/FIXME/HACK marker found in source code."""

    file_path: str
    line_number: int
    marker: str  # the matched marker text (preserving case)
    content: str  # the full source line (stripped)
    context: str = ""  # optional surrounding context


@dataclass
class DriftReport:
    """Result of diffing scanned markers against the tracker."""

    scanned_files: int
    total_markers: int
    registered_count: int
    new_unregistered: list[TechDebtEntry] = field(default_factory=list)
    removed_registered: list[str] = field(default_factory=list)  # tracker locations no longer in source


def scan_tech_debt(
    root_dir: str | Path = DEFAULT_SCAN_ROOT,
    file_pattern: str = "*.py",
    exclude_dirs: tuple[str, ...] = DEFAULT_EXCLUDE_DIRS,
) -> list[TechDebtEntry]:
    """Scan ``root_dir`` recursively for tech-debt markers.

    Args:
        root_dir: Directory to scan (default ``scripts/``).
        file_pattern: Glob pattern for files to scan (default ``*.py``).
        exclude_dirs: Directory names to skip.

    Returns:
        List of :class:`TechDebtEntry` sorted by ``(file_path, line_number)``.

    Raises:
        FileNotFoundError: If ``root_dir`` does not exist.
    """
    root = Path(root_dir)
    if not root.exists():
        raise FileNotFoundError(f"Scan root does not exist: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Scan root is not a directory: {root}")

    entries: list[TechDebtEntry] = []
    exclude_set = set(exclude_dirs)

    for path in root.rglob(file_pattern):
        if any(part in exclude_set for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        entries.extend(_scan_file_markers(path, text))

    entries.sort(key=lambda e: (e.file_path, e.line_number))
    return entries


def _scan_file_markers(path: Path, text: str) -> list[TechDebtEntry]:
    """Find tech-debt markers in Python comments using :mod:`tokenize`.

    V4.3.0 P0-2: Uses Python's tokenizer to distinguish real comments from
    ``#`` characters that appear inside string literals (e.g., Markdown
    headers like ``"## Todo Drift Report"``). Falls back to line-by-line
    regex scan if the file has syntax errors that break tokenization.

    Args:
        path: File path (for the returned ``file_path`` field).
        text: File contents (UTF-8 decoded).

    Returns:
        List of :class:`TechDebtEntry` found in comments only.
    """
    entries: list[TechDebtEntry] = []
    try:
        tokens = tokenize.generate_tokens(io.StringIO(text).readline)
        for tok in tokens:
            if tok.type != tokenize.COMMENT:
                continue
            match = MARKER_PATTERN.search(tok.string)
            if match is None:
                continue
            entries.append(
                TechDebtEntry(
                    file_path=str(path),
                    line_number=tok.start[0],
                    marker=match.group(1),
                    content=tok.string.strip(),
                )
            )
    except (tokenize.TokenError, IndentationError, SyntaxError):
        # Syntax error — fall back to line-by-line scan. This may produce
        # false positives for '#' inside strings, but is better than
        # silently skipping the file.
        for lineno, line in enumerate(text.splitlines(), start=1):
            match = MARKER_PATTERN.search(line)
            if match is None:
                continue
            entries.append(
                TechDebtEntry(
                    file_path=str(path),
                    line_number=lineno,
                    marker=match.group(1),
                    content=line.strip(),
                )
            )
    return entries


def _parse_registered_locations(tracker_path: str | Path) -> set[str]:
    """Extract ``scripts/.../file.py:NN`` locations from TECH_DEBT.md.

    Returns a set of normalized ``path:line`` strings. Lines outside the
    tracker file that mention these patterns (e.g. inside a regex literal
    in a code block) are intentionally included — the tracker is the source
    of truth for "this location is known".
    """
    tracker = Path(tracker_path)
    if not tracker.exists():
        raise FileNotFoundError(f"Tech debt tracker not found: {tracker}")
    text = tracker.read_text(encoding="utf-8")
    locations: set[str] = set()
    for match in _TRACKER_LOCATION_PATTERN.finditer(text):
        path_str = match.group(1).strip()
        line_str = match.group(2)
        locations.add(f"{path_str}:{line_str}")
    return locations


def diff_with_tracker(
    scanned: list[TechDebtEntry],
    tracker_path: str | Path = DEFAULT_TRACKER_PATH,
    total_files_scanned: int | None = None,
) -> DriftReport:
    """Diff scanned markers against the tracker.

    Args:
        scanned: Output of :func:`scan_tech_debt`.
        tracker_path: Path to ``docs/TECH_DEBT.md``.
        total_files_scanned: Total number of files scanned (not just files
            with markers). If None, falls back to counting unique file paths
            in ``scanned`` (for backward compatibility). Pass the real count
            from the scan step for accurate reporting.

    Returns:
        A :class:`DriftReport` with new unregistered markers and any tracker
        entries no longer present in source.

    Raises:
        FileNotFoundError: If ``tracker_path`` does not exist.
    """
    registered = _parse_registered_locations(tracker_path)

    new_unregistered: list[TechDebtEntry] = []
    scanned_locations: set[str] = set()

    for entry in scanned:
        loc = f"{entry.file_path}:{entry.line_number}"
        scanned_locations.add(loc)
        if loc not in registered:
            new_unregistered.append(entry)

    removed_registered = sorted(registered - scanned_locations)

    files_count = (
        total_files_scanned
        if total_files_scanned is not None
        else len({e.file_path for e in scanned})
    )

    return DriftReport(
        scanned_files=files_count,
        total_markers=len(scanned),
        registered_count=len(registered),
        new_unregistered=new_unregistered,
        removed_registered=removed_registered,
    )


def report_new_debts(report: DriftReport, output_format: str = "text") -> str:
    """Format a :class:`DriftReport` for human or machine consumption.

    Args:
        report: The drift report to format.
        output_format: ``"text"``, ``"json"``, or ``"markdown"``.

    Returns:
        Formatted report string.

    Raises:
        ValueError: If ``output_format`` is not supported.
    """
    if output_format == "json":
        return json.dumps(asdict(report), indent=2, ensure_ascii=False)
    if output_format == "markdown":
        lines = [
            "## Todo Drift Report",
            "",
            f"- Scanned files: **{report.scanned_files}**",
            f"- Total markers: **{report.total_markers}**",
            f"- Registered in tracker: **{report.registered_count}**",
            f"- New unregistered: **{len(report.new_unregistered)}**",
            "",
        ]
        if report.new_unregistered:
            lines.append("### New unregistered markers")
            lines.append("")
            lines.append("| File | Line | Marker | Content |")
            lines.append("|------|------|--------|---------|")
            for e in report.new_unregistered:
                lines.append(f"| {e.file_path} | {e.line_number} | `{e.marker}` | {e.content[:80]} |")
            lines.append("")
        if report.removed_registered:
            lines.append("### Tracker entries no longer in source")
            lines.append("")
            for loc in report.removed_registered:
                lines.append(f"- `{loc}`")
            lines.append("")
        return "\n".join(lines)
    if output_format == "text":
        lines = [
            f"Scanned {report.scanned_files} files, found {report.total_markers} markers "
            f"({report.registered_count} registered, {len(report.new_unregistered)} new unregistered).",
        ]
        for e in report.new_unregistered:
            lines.append(f"  NEW: {e.file_path}:{e.line_number} [{e.marker}] {e.content[:80]}")
        for loc in report.removed_registered:
            lines.append(f"  GONE: {loc} (registered but no longer in source)")
        return "\n".join(lines)
    raise ValueError(f"Unsupported output_format: {output_format!r}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Todo drift monitor — block unregistered tech debt (V4.3.0 P0-2).",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=DEFAULT_SCAN_ROOT,
        help=f"Directory to scan (default: {DEFAULT_SCAN_ROOT})",
    )
    parser.add_argument(
        "--tracker",
        type=str,
        default=DEFAULT_TRACKER_PATH,
        help=f"Tech debt tracker path (default: {DEFAULT_TRACKER_PATH})",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="text",
        choices=["text", "json", "markdown"],
        help="Output format (default: text)",
    )
    args = parser.parse_args(argv)

    try:
        scanned = scan_tech_debt(args.root)
        # Count total files scanned (not just files with markers) for accurate reporting.
        exclude_set = set(DEFAULT_EXCLUDE_DIRS)
        total_files = sum(
            1
            for p in Path(args.root).rglob("*.py")
            if not any(part in exclude_set for part in p.parts)
        )
        report = diff_with_tracker(scanned, args.tracker, total_files_scanned=total_files)
    except FileNotFoundError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2

    print(report_new_debts(report, args.format))
    return 1 if report.new_unregistered else 0


if __name__ == "__main__":
    sys.exit(main())
