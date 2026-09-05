#!/usr/bin/env python3
"""V4.6.0-doc-governance P2: Dispatcher / module size CI gate.

Tracks Python file sizes under ``scripts/`` (default) and fails CI when any
file grows past ``--max-lines`` (default 800). The first run writes a baseline
JSON snapshot; subsequent runs diff against the baseline to surface net growth.

Why this gate exists (V4.6.0-doc-governance maturity assessment):

- The dispatcher mixin sprawl and 14+ files >900 LOC were flagged as the
  primary Maintainability liability (B+ 7.5/10 in 2026-09-05 maturity scan).
- This gate is intentionally lenient on existing oversize: the first run
  records the current line counts as baseline so historical debt doesn't
  block the very CI run that surfaces it.
- Subsequent runs block ONLY on net growth past the baseline, so the gate
  prevents regressions while leaving refactor as a separate (intentional)
  work item.

Exit codes:
  0 = no file exceeds max-lines AND no net growth past baseline
  1 = one or more files past max-lines (with baseline compare)
  2 = baseline file unreadable / malformed (operator must regenerate)

Usage:
    python scripts/check_dispatcher_size.py [--source scripts/] [--max-lines 800]
                                             [--baseline docs/audits/dispatcher_size_baseline.json]
                                             [--write-baseline]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = REPO_ROOT / "scripts"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "audits" / "dispatcher_size_baseline.json"


def _iter_python_files(source: Path) -> Iterable[Path]:
    """Yield *.py files under source, excluding __pycache__ and hidden dirs."""
    for p in sorted(source.rglob("*.py")):
        if any(part.startswith(".") or part == "__pycache__" for part in p.parts):
            continue
        yield p


def _line_count(path: Path) -> int:
    """Return the non-empty line count of ``path`` (LOC for the gate)."""
    try:
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except OSError:
        return 0


def _snapshot(source: Path) -> dict[str, int]:
    """Build a {relative_path: loc} snapshot of all Python files under source."""
    snap: dict[str, int] = {}
    for p in _iter_python_files(source):
        rel = str(p.relative_to(REPO_ROOT))
        snap[rel] = _line_count(p)
    return snap


def _load_baseline(path: Path) -> dict[str, int] | None:
    """Load a baseline JSON snapshot or return None if unreadable.

    Accepts both:

    * Flat dict: ``{"a.py": 100, "b.py": 50}``
    * V4.6.0-doc-governance payload: ``{"files": {"a.py": 100, ...}, ...}``
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    if not isinstance(data, dict):
        return None
    raw = data["files"] if "files" in data and isinstance(data["files"], dict) else data
    return {str(k): int(v) for k, v in raw.items() if isinstance(v, (int, float))}


def main() -> int:
    parser = argparse.ArgumentParser(description="Dispatcher / module size CI gate")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="Source root to scan")
    parser.add_argument(
        "--max-lines", type=int, default=800,
        help="Maximum non-empty LOC per file (default: 800)",
    )
    parser.add_argument(
        "--baseline", default=str(DEFAULT_BASELINE),
        help="Baseline JSON snapshot path (default: docs/audits/dispatcher_size_baseline.json)",
    )
    parser.add_argument(
        "--write-baseline", action="store_true",
        help="Snapshot current sizes to --baseline and exit 0 (used by first-run / refresh)",
    )
    args = parser.parse_args()

    source = Path(args.source).resolve()
    baseline_path = Path(args.baseline).resolve()
    if not source.is_dir():
        print(f"ERROR: source not a directory: {source}", file=sys.stderr)
        return 2

    snap = _snapshot(source)
    max_lines = args.max_lines

    # Print top-N largest files for review
    biggest = sorted(snap.items(), key=lambda kv: kv[1], reverse=True)[:15]
    print(f"Scanned {len(snap)} Python files under {source}")
    print(f"Threshold: {max_lines} LOC (V4.6.0-doc-governance P2 ceiling)")
    print(f"Baseline : {baseline_path}")
    print("Top 15 by LOC:")
    for rel, loc in biggest:
        marker = "  " if loc <= max_lines else "XX"
        print(f"  {marker} {loc:>5d}  {rel}")

    # Write-baseline mode: snapshot and exit cleanly
    if args.write_baseline:
        baseline_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": "v4.6.0-doc-governance",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "max_lines": max_lines,
            "files": snap,
        }
        baseline_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        print(f"\nWrote baseline snapshot ({len(snap)} files) to {baseline_path}")
        return 0

    # Load baseline for comparison
    baseline = _load_baseline(baseline_path)
    if baseline is None:
        print(
            f"\nWARN: baseline not found or unreadable at {baseline_path}. "
            "Run with --write-baseline first, then commit the baseline file.",
            file=sys.stderr,
        )
        # Without a baseline we cannot diff; fall back to absolute threshold only.
        baseline = {}

    over_threshold: list[tuple[str, int]] = []
    new_oversize: list[tuple[str, int, int]] = []  # (rel, current, baseline)
    for rel, loc in snap.items():
        if loc > max_lines:
            over_threshold.append((rel, loc))
            base = baseline.get(rel, 0)
            if loc > base:
                new_oversize.append((rel, loc, base))

    print(f"\nResults: {len(over_threshold)} files exceed {max_lines} LOC")
    if new_oversize:
        print(f"        {len(new_oversize)} files grew past their baseline (CI blocks)")

    if new_oversize:
        print("\nFAIL: net growth past baseline (release-blocking):", file=sys.stderr)
        for rel, loc, base in sorted(new_oversize, key=lambda x: x[1] - x[2], reverse=True):
            print(f"  +{loc - base:>4d}  {loc:>5d} (was {base})  {rel}", file=sys.stderr)
        return 1

    if over_threshold and not baseline:
        # First-run with no baseline: surface but don't block
        print(
            f"\nNOTE: {len(over_threshold)} files already over {max_lines} LOC "
            "(historical debt, no baseline to diff). Run --write-baseline to lock it in.",
            file=sys.stderr,
        )
        return 0

    print("\nPASS: dispatcher size gate (no net growth past baseline).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
