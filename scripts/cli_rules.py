#!/usr/bin/env python3
"""Explain the effective deterministic rule for one path (V4.5.20 W1-2)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from scripts.collaboration.rule_engine import RuleConfigError, default_sources, resolve


def cmd_rules_check(args: argparse.Namespace) -> int:
    """Print the layer, pattern, and body selected for one path."""
    path = args.path
    sources = default_sources(repo_root=args.repo_root, cli_rule=args.rule)
    try:
        result = resolve(path, sources)
    except RuleConfigError as exc:
        print(f"Error resolving rule for {path!r}: {exc}", file=sys.stderr)
        return 1

    print(f"Path: {result.path}")
    print(f"Layer: {result.layer}")
    print(f"Pattern: {result.pattern}")
    print(f"Origin: {result.origin}")
    print("Rule:")
    print(json.dumps(result.body, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


def register_rules_subparser(subparsers: Any) -> None:
    """Register ``devsquad rules check <path>``."""
    parser = subparsers.add_parser("rules", help="Inspect deterministic rule resolution")
    commands = parser.add_subparsers(dest="rules_command", required=True)
    check = commands.add_parser("check", help="Explain which rule applies to a path")
    check.add_argument("path", help="Repository-relative path to resolve")
    check.add_argument("--rule", type=Path, help="Explicit CLI rule file (highest priority)")
    check.add_argument(
        "--repo-root",
        type=Path,
        default=Path.cwd(),
        help="Repository root for the project rule layer (default: current directory)",
    )
    check.set_defaults(func=cmd_rules_check)
