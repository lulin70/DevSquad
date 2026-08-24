#!/usr/bin/env python3
"""ModulesCLI — V4.5.4 P12.3.3 — Module lifecycle CLI (status / graph / retry).

Subcommands:
    devsquad modules status [--module X] [--format text|json]
    devsquad modules graph  [--format ascii|dot]
    devsquad modules retry <module_id>

V4.5.3 lesson #3 applied: subcommand registration via register_subparser
(consistent with cli_audit.py:221-260 pattern).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from scripts.collaboration.module_fiber import (
    FiberState,
    ModuleFiberRegistry,
    _inc_call_counter_er,
)

logger = logging.getLogger(__name__)


# ── Anti-ghost counter ─────────────────────────────────────────────────────


def _inc_call_counter_modules() -> None:
    """Increment CLI-level call counter (V4.5.3 lesson #4)."""
    _inc_call_counter_er()


# ── Subcommands ─────────────────────────────────────────────────────────────


def cmd_modules_status(args: argparse.Namespace) -> int:
    """Print status table for all registered modules.

    V4.5.3 lesson #7: best-effort guard with try/except — registry may be empty
    or stale in some integration paths.
    """
    try:
        registry: ModuleFiberRegistry = args.registry
        output_format: str = getattr(args, "format", "text")
        module_filter: str | None = getattr(args, "module", None)

        fibers = registry.all_fibers()
        if module_filter:
            fibers = [f for f in fibers if f.module_id == module_filter]

        if output_format == "json":
            payload = [
                {
                    "module_id": f.module_id,
                    "state": f.state.value,
                    "depends_on": list(f.depends_on),
                    "retry_count": f.retry_count,
                    "last_error": f.last_error,
                    "activated_at": f.activated_at,
                }
                for f in fibers
            ]
            print(json.dumps(payload, indent=2))
        else:
            print(f"{'MODULE':<25} {'STATE':<12} {'DEPS':<14} {'RETRY':<6} LAST_ERROR")
            print("-" * 80)
            for f in fibers:
                deps_str = ",".join(f.depends_on)[:14] if f.depends_on else "-"
                err_str = (
                    (f.last_error[:30] + "...")
                    if f.last_error and len(f.last_error) > 30
                    else (f.last_error or "-")
                )
                print(
                    f"{f.module_id:<25} {f.state.value:<12} "
                    f"{deps_str:<14} {f.retry_count:<6} {err_str}"
                )
    except Exception as exc:  # noqa: BLE001 — best-effort CLI
        print(f"Error reading module status: {exc}", file=sys.stderr)
        return 1
    _inc_call_counter_modules()
    return 0


def cmd_modules_graph(args: argparse.Namespace) -> int:
    """Print ASCII tree or DOT format of module dependency graph."""
    try:
        resolver: Any = args.resolver
        output_format: str = getattr(args, "format", "ascii")

        if output_format == "dot":
            print("digraph modules {")
            for node, deps in resolver._graph.items():
                for dep in deps:
                    print(f"  {dep} -> {node};")
            print("}")
        else:
            roots = sorted(n for n, d in resolver._graph.items() if not d)
            print("Module dependency graph (ASCII):")
            print()
            for root in roots:
                print(f"  [{root}] (root)")
            for node in sorted(resolver._graph):
                deps = resolver._graph[node]
                if not deps:
                    continue
                for dep in sorted(deps):
                    if dep in resolver._modules:
                        print(f"  [{node}] <-- depends on -- [{dep}]")
    except Exception as exc:  # noqa: BLE001
        print(f"Error rendering dependency graph: {exc}", file=sys.stderr)
        return 1
    _inc_call_counter_modules()
    return 0


def cmd_modules_retry(args: argparse.Namespace) -> int:
    """Manually retry a Failed module (V4.5.4 D6: state self-healing)."""
    try:
        registry: ModuleFiberRegistry = args.registry
        module_id: str = args.module_id
        fiber = registry.get(module_id)
        if fiber is None:
            print(f"Module {module_id!r} not found", file=sys.stderr)
            return 1
        if fiber.state != FiberState.FAILED:
            print(
                f"Module {module_id!r} is in state {fiber.state.value}, not Failed",
                file=sys.stderr,
            )
            return 1
        fiber.retry_count = 0
        ok = fiber.transition(FiberState.ACTIVATING, reason="manual retry")
        if not ok:
            print(f"Cannot transition {module_id!r} to Activating", file=sys.stderr)
            return 1
        fiber.transition(FiberState.ACTIVE, reason="manual retry succeeded")
    except Exception as exc:  # noqa: BLE001
        print(f"Error retrying module: {exc}", file=sys.stderr)
        return 1
    _inc_call_counter_modules()
    print(f"Module {module_id!r} reactivated.")
    return 0


def register_modules_subparser(subparsers: Any) -> None:
    """Register `devsquad modules {status,graph,retry}` subcommands.

    V4.5.3 lesson #5 (cli_audit pattern): use register_subparser to keep
    main() clean and avoid if/elif chain in cli.py.
    """
    p = subparsers.add_parser("modules", help="Module lifecycle operations")
    modules_sub = p.add_subparsers(dest="modules_cmd", required=True)

    p_status = modules_sub.add_parser("status", help="Show module status")
    p_status.add_argument("--module", help="Filter by module_id")
    p_status.add_argument("--format", choices=["text", "json"], default="text")
    p_status.set_defaults(func=cmd_modules_status)

    p_graph = modules_sub.add_parser("graph", help="Show dependency graph")
    p_graph.add_argument("--format", choices=["ascii", "dot"], default="ascii")
    p_graph.set_defaults(func=cmd_modules_graph)

    p_retry = modules_sub.add_parser("retry", help="Retry a Failed module")
    p_retry.add_argument("module_id", help="Module ID to retry")
    p_retry.set_defaults(func=cmd_modules_retry)
