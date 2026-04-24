#!/usr/bin/env python3
"""
DevSquad CLI Entry Point — Cross-platform interface for any AI coding assistant.

Usage:
    python3 scripts/cli.py dispatch -t "design user auth system" -r architect coder tester
    python3 scripts/cli.py dispatch -t "review code" -f json --mode consensus --backend openai
    python3 scripts/cli.py status
    python3 scripts/cli.py roles
    python3 scripts/cli.py --version
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
BACKENDS = ["mock", "trae", "openai", "anthropic"]
VERSION = "3.3.0"


def _create_backend(backend_type: str, api_key: str = None):
    if backend_type == "mock" or backend_type is None:
        return None
    from scripts.collaboration.llm_backend import create_backend
    kwargs = {}
    if api_key:
        kwargs["api_key"] = api_key
    if backend_type == "openai":
        kwargs.setdefault("api_key", os.environ.get("OPENAI_API_KEY"))
    elif backend_type == "anthropic":
        kwargs.setdefault("api_key", os.environ.get("ANTHROPIC_API_KEY"))
    return create_backend(backend_type, **kwargs)


def cmd_dispatch(args):
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

    backend = _create_backend(args.backend, args.api_key)
    if backend is not None:
        kwargs["llm_backend"] = backend

    disp = MultiAgentDispatcher(**kwargs)

    try:
        if args.quick:
            result = disp.quick_dispatch(
                args.task,
                output_format=args.format if args.format in ("structured", "compact", "detailed") else "structured",
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
    disp = MultiAgentDispatcher(enable_warmup=False)
    try:
        stats = disp.get_statistics() if hasattr(disp, 'get_statistics') else {}
        status = {
            "name": "DevSquad",
            "version": VERSION,
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
        description="DevSquad V3.3 — Multi-Agent Orchestration Engine for Software Development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s dispatch -t "Design user auth system" -r architect pm tester
  %(prog)s dispatch -t "Review codebase" --mode consensus --format json
  %(prog)s dispatch -t "Analyze API" --quick --format compact
  %(prog)s dispatch -t "Security audit" -r security --backend openai
  %(prog)s roles
  %(prog)s status
  %(prog)s --version

Environment Variables:
  DEVSQUAD_LLM_BACKEND   Default LLM backend (mock/openai/anthropic)
  OPENAI_API_KEY         OpenAI API key (for --backend openai)
  ANTHROPIC_API_KEY      Anthropic API key (for --backend anthropic)
        """,
    )
    parser.add_argument("--version", action="version", version=f"DevSquad {VERSION}")

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    p_dispatch = subparsers.add_parser("dispatch", aliases=["run", "d"], help="Execute a multi-agent task")
    p_dispatch.add_argument("--task", "-t", required=True, help="Task description")
    p_dispatch.add_argument("--roles", "-r", nargs="+", choices=ROLES, help="Roles to involve (default: auto-match)")
    p_dispatch.add_argument("--mode", "-m", choices=MODES, default="auto", help="Execution mode (default: auto)")
    p_dispatch.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
    p_dispatch.add_argument("--backend", "-b", choices=BACKENDS, default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
                            help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)")
    p_dispatch.add_argument("--api-key", help="API key for LLM backend (or use OPENAI_API_KEY/ANTHROPIC_API_KEY env)")
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

    subparsers.add_parser("status", aliases=["s"], help="Show system status")

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
