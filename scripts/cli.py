#!/usr/bin/env python3
"""
DevSquad CLI Entry Point — Cross-platform interface for ClaudeCode, OpenClaw, and any AI coding assistant.

Usage:
    python -m scripts.cli --task "design user auth system" --roles architect coder tester
    python -m scripts.cli --task "review code" --format json --mode consensus
    python -m scripts.cli --status          # Show dispatcher status
    python -m scripts.cli --roles           # List available roles
"""
import argparse
import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.permission_guard import PermissionLevel
from scripts.collaboration.models import ROLE_REGISTRY, get_cli_role_list

ROLES = get_cli_role_list()

MODES = ["auto", "parallel", "sequential", "consensus"]
FORMATS = ["markdown", "json", "compact", "structured", "detailed"]


def cmd_dispatch(args):
    """Execute a multi-agent collaboration task."""
    kwargs = {
        "persist_dir": args.persist_dir,
        "enable_warmup": not args.no_warmup,
        "enable_compression": not args.no_compression,
        "enable_permission": not args.skip_permission,
        "enable_memory": not args.no_memory,
        "enable_skillify": not args.no_skillify,
    }
    if args.permission_level:
        kwargs["permission_level"] = PermissionLevel(args.permission_level.upper())

    disp = MultiAgentDispatcher(**kwargs)

    try:
        if args.quick:
            result = disp.quick_dispatch(
                args.task,
                output_format=args.format if args.formats in ("structured", "compact", "detailed") else "structured",
                include_action_items=args.action_items,
                include_timing=args.timing,
            )
        else:
            result = disp.dispatch(
                args.task,
                roles=args.roles,
                mode=args.mode,
                dry_run=args.dry_run,
            )

        if args.format == "json":
            output = {
                "success": result.success,
                "matched_roles": getattr(result, 'matched_roles', None),
                "summary": result.summary,
                "report": result.to_markdown(),
                "timing": getattr(result, 'timing', None),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        elif args.format == "compact":
            print(result.summary)
        else:
            print(result.to_markdown())

        return 0 if result.success else 1
    finally:
        disp.shutdown()


def cmd_status(args):
    """Show system status and available capabilities."""
    disp = MultiAgentDispatcher(enable_warmup=False)
    try:
        stats = disp.get_statistics() if hasattr(disp, 'get_statistics') else {}
        status = {
            "name": "DevSquad",
            "version": "3.3.0",
            "status": "ready",
            "available_roles": ROLES,
            "available_modes": MODES,
            "modules_loaded": list(stats.keys()) if stats else "unknown",
        }
        print(json.dumps(status, ensure_ascii=False, indent=2))
        return 0
    finally:
        disp.shutdown()


def cmd_roles(args):
    """List all available roles with descriptions."""
    role_descriptions = {}
    for rid, rdef in ROLE_REGISTRY.items():
        display_id = rdef.aliases[0] if rdef.aliases else rid
        status_tag = " [planned]" if rdef.status == "planned" else ""
        role_descriptions[display_id] = f"{rdef.description}{status_tag}"
    if args.format == "json":
        print(json.dumps(role_descriptions, ensure_ascii=False, indent=2))
    else:
        for role, desc in role_descriptions.items():
            print(f"  {role:<12} — {desc}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="DevSquad V3.3 — Multi-Agent Software Development Team CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --task "Design user auth system" --roles architect coder tester
  %(prog)s --task "Review codebase" --mode consensus --format json
  %(prog)s --quick --task "Analyze API" --format compact
  %(prog)s --roles
  %(prog)s --status
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Dispatch command
    p_dispatch = subparsers.add_parser("dispatch", aliases=["run", "d"], help="Execute a multi-agent task")
    p_dispatch.add_argument("--task", "-t", required=True, help="Task description")
    p_dispatch.add_argument("--roles", "-r", nargs="+", choices=ROLES, help="Roles to involve (default: auto-match)")
    p_dispatch.add_argument("--mode", "-m", choices=MODES, default="auto", help="Execution mode (default: auto)")
    p_dispatch.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
    p_dispatch.add_argument("--dry-run", action="store_true", help="Simulate without execution")
    p_dispatch.add_argument("--quick", "-q", action="store_true", help="Use quick_dispatch (3 formats)")
    p_dispatch.add_argument("--action-items", action="store_true", help="Include H/M/L action items")
    p_dispatch.add_argument("--timing", action="store_true", help="Include timing info")
    p_dispatch.add_argument("--persist-dir", help="Custom scratchpad directory")
    p_dispatch.add_argument("--no-warmup", action="store_true", help="Disable startup warmup")
    p_dispatch.add_argument("--no-compression", action="store_true", help="Disable context compression")
    p_dispatch.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
    p_dispatch.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
    p_dispatch.add_argument("--no-skillify", action="store_true", help="Disable skill learning")
    p_dispatch.add_argument("--permission-level", choices=["PLAN", "DEFAULT", "AUTO", "BYPASS"], help="Permission level")

    # Status command
    subparsers.add_parser("status", aliases=["s"], help="Show system status")

    # Roles command
    p_roles = subparsers.add_parser("roles", aliases=["ls"], help="List available roles")
    p_roles.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    args = parser.parse_args()

    if args.command in ("dispatch", "run", "d"):
        return cmd_dispatch(args)
    elif args.command in ("status", "s"):
        return cmd_status(args)
    elif args.command in ("roles", "ls"):
        return cmd_roles(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
