#!/usr/bin/env python3
"""V4.2.1 P1-13: Constructor Parameter Counter.

Scans Python source files for ``__init__`` methods with too many
parameters (>7 by default), flagging "god constructor" anti-patterns
early — before they become maintenance burdens.

Usage::

    python scripts/check_constructor_params.py
    python scripts/check_constructor_params.py --source scripts/collaboration --threshold 7
    python scripts/check_constructor_params.py --json

Exit codes:
    0: No constructors exceed threshold (or none found)
    1: Some constructors exceed threshold
    2: Invalid arguments
"""

from __future__ import annotations

import argparse
import ast
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ConstructorInfo:
    """Info about a constructor and its parameters."""

    class_name: str
    file: Path
    line: int
    param_count: int
    param_names: list[str]
    has_kwargs: bool = False
    has_varargs: bool = False


@dataclass
class ConstructorReport:
    """Result of constructor parameter analysis."""

    total_constructors: int = 0
    flagged: list[ConstructorInfo] = field(default_factory=list)
    threshold: int = 7

    def to_dict(self) -> dict:
        return {
            "total_constructors": self.total_constructors,
            "flagged_count": len(self.flagged),
            "threshold": self.threshold,
            "flagged": [
                {
                    "class": f.class_name,
                    "file": str(f.file),
                    "line": f.line,
                    "param_count": f.param_count,
                    "params": f.param_names,
                    "has_kwargs": f.has_kwargs,
                    "has_varargs": f.has_varargs,
                }
                for f in self.flagged
            ],
        }


def extract_constructors(source_dir: Path) -> list[ConstructorInfo]:
    """Extract all __init__ methods from Python files in source_dir.

    Args:
        source_dir: Directory to scan recursively for .py files.

    Returns:
        List of ConstructorInfo objects.
    """
    constructors: list[ConstructorInfo] = []
    for py_file in sorted(source_dir.rglob("*.py")):
        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name != "__init__":
                    continue
                args = item.args
                # Count parameters (exclude 'self')
                pos_args = [a.arg for a in args.args if a.arg != "self"]
                # Add keyword-only args
                kwonly_args = [a.arg for a in args.kwonlyargs]
                all_params = pos_args + kwonly_args
                constructors.append(
                    ConstructorInfo(
                        class_name=node.name,
                        file=py_file,
                        line=item.lineno,
                        param_count=len(all_params),
                        param_names=all_params,
                        has_kwargs=args.kwarg is not None,
                        has_varargs=args.vararg is not None,
                    )
                )
    return constructors


def check_constructor_params(
    source_dir: Path,
    threshold: int = 7,
) -> ConstructorReport:
    """Check for constructors exceeding the parameter threshold.

    Args:
        source_dir: Source directory to scan.
        threshold: Maximum allowed parameters (exclusive). Constructors
            with more than this are flagged.

    Returns:
        ConstructorReport with flagged constructors.
    """
    constructors = extract_constructors(source_dir)
    report = ConstructorReport(total_constructors=len(constructors), threshold=threshold)
    for ctor in constructors:
        if ctor.param_count > threshold:
            report.flagged.append(ctor)
    # Sort by param count descending
    report.flagged.sort(key=lambda c: c.param_count, reverse=True)
    return report


def main() -> int:
    """CLI entry point.

    Returns:
        0 if no constructors flagged, 1 if any flagged, 2 if invalid args.
    """
    parser = argparse.ArgumentParser(
        description="V4.2.1 P1-13: Detect constructors with too many parameters."
    )
    parser.add_argument(
        "--source",
        type=Path,
        default=Path("scripts/collaboration"),
        help="Source directory to scan (default: scripts/collaboration)",
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=7,
        help="Max allowed parameters (exclusive). Default: 7",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable text",
    )

    args = parser.parse_args()

    if not args.source.is_dir():
        print(f"Error: source directory not found: {args.source}", file=sys.stderr)
        return 2

    report = check_constructor_params(args.source, args.threshold)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print("Constructor Parameter Report (V4.2.1 P1-13)")
        print("=" * 50)
        print(f"Source: {args.source}")
        print(f"Threshold: >{args.threshold} params")
        print(f"Total constructors: {report.total_constructors}")
        print(f"Flagged: {len(report.flagged)}")
        if report.flagged:
            print("\nFlagged constructors (god ctor candidates):")
            for ctor in report.flagged:
                kwargs_note = " + **kwargs" if ctor.has_kwargs else ""
                varargs_note = " + *args" if ctor.has_varargs else ""
                print(
                    f"  - {ctor.class_name}.__init__ ({ctor.param_count} params)"
                    f"{varargs_note}{kwargs_note}"
                    f" [{ctor.file}:{ctor.line}]"
                )
                print(f"    params: {', '.join(ctor.param_names)}")

    if report.flagged:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
