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

if sys.version_info < (3, 9):
    print("Error: DevSquad requires Python 3.9+. Current: " + sys.version, file=sys.stderr)
    sys.exit(1)

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.permission_guard import PermissionLevel
from scripts.collaboration.models import ROLE_REGISTRY, get_cli_role_list, resolve_role_id
from scripts.collaboration.input_validator import InputValidator

ROLES = get_cli_role_list()
ALL_ROLE_IDS = list(ROLE_REGISTRY.keys()) + ROLES
ALL_ROLE_IDS = sorted(set(ALL_ROLE_IDS))
MODES = ["auto", "parallel", "sequential", "consensus"]
FORMATS = ["markdown", "json", "compact", "structured", "detailed"]
BACKENDS = ["mock", "trae", "openai", "anthropic"]
LIFECYCLE_COMMANDS = ["spec", "plan", "build", "test", "review", "ship"]
from scripts.collaboration._version import __version__
VERSION = __version__

LIFECYCLE_PRESETS = {
    "spec": {
        "description": "Define and refine requirements before implementation",
        "required_roles": ["architect", "product-manager"],
        "mode": "sequential",
        "gate": "spec_first",
        "pre_dispatch_message": (
            "📋 Generating specification before any code. "
            "Output will include objectives, commands, structure, testing plan, and boundaries."
        ),
    },
    "plan": {
        "description": "Break down work into small, verifiable tasks",
        "required_roles": ["architect", "product-manager"],
        "mode": "auto",
        "gate": "task_breakdown_complete",
        "pre_dispatch_message": (
            "📝 Decomposing into atomic tasks with acceptance criteria and dependency ordering."
        ),
    },
    "build": {
        "description": "Implement incrementally with TDD discipline",
        "required_roles": ["architect", "solo-coder", "tester"],
        "mode": "parallel",
        "gate": "incremental_verification",
        "pre_dispatch_message": (
            "🔨 Building in thin vertical slices. Each slice: implement → test → verify → commit. "
            "~100 lines per slice maximum."
        ),
    },
    "test": {
        "description": "Run tests with mandatory evidence requirements",
        "required_roles": ["tester", "solo-coder"],
        "mode": "consensus",
        "gate": "evidence_required",
        "pre_dispatch_message": (
            "🧪 Running tests with verification gate. Evidence required: test output, build status, diff summary. "
            "'Seems right' is NOT sufficient."
        ),
    },
    "review": {
        "description": "Five-axis code review (correctness/readability/arch/security/performance)",
        "required_roles": ["solo-coder", "security", "tester", "architect"],
        "mode": "consensus",
        "gate": "change_size_limit",
        "pre_dispatch_message": (
            "🔍 Conducting multi-dimensional code review. Change size target: ~100 lines. "
            "Severity labels: Critical (blocks merge) / Required / Nit (optional)."
        ),
    },
    "ship": {
        "description": "Pre-launch verification and deployment preparation",
        "required_roles": ["devops", "security", "architect"],
        "mode": "sequential",
        "gate": "pre_launch_checklist",
        "pre_dispatch_message": (
            "🚀 Running pre-launch checklist across 6 dimensions: Code Quality, Security, Performance, "
            "Accessibility, Infrastructure, Documentation. Rollback plan required."
        ),
    },
}


def _create_backend(backend_type: str,
                    base_url: str = None, model: str = None):
    if backend_type == "mock" or backend_type is None:
        return None
    from scripts.collaboration.llm_backend import create_backend
    kwargs = {}
    if base_url:
        kwargs["base_url"] = base_url
    if model:
        kwargs["model"] = model
    if backend_type == "openai":
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
            print("  export OPENAI_API_KEY=\"sk-...\"", file=sys.stderr)
            return None
        kwargs["api_key"] = api_key
        kwargs.setdefault("base_url", os.environ.get("OPENAI_BASE_URL"))
        kwargs.setdefault("model", os.environ.get("OPENAI_MODEL", "gpt-4"))
    elif backend_type == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
            print("  export ANTHROPIC_API_KEY=\"sk-ant-...\"", file=sys.stderr)
            return None
        kwargs["api_key"] = api_key
        kwargs.setdefault("model", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
    return create_backend(backend_type, **kwargs)


def cmd_dispatch(args):
    task_text = args.task if args.task is not None else args.task_positional
    if not task_text:
        print("Error: Task description required. Usage: devsquad dispatch \"your task\" or devsquad dispatch -t \"your task\"", file=sys.stderr)
        return 1

    validator = InputValidator()
    
    task_result = validator.validate_task(task_text)
    if not task_result.valid:
        print(f"Error: Invalid task - {task_result.reason}", file=sys.stderr)
        return 1
    
    task = task_result.sanitized_input or task_text
    
    # 验证角色列表（如果提供）
    if args.roles:
        args.roles = [resolve_role_id(r) for r in args.roles]
        roles_result = validator.validate_roles(args.roles)
        if not roles_result.valid:
            print(f"Error: Invalid roles - {roles_result.reason}", file=sys.stderr)
            return 1
    
    # 检查可疑模式（警告但不阻止）
    warnings = validator.check_suspicious_patterns(task)
    if warnings:
        print(f"Warning: Suspicious patterns detected: {', '.join(warnings)}", file=sys.stderr)
        print("Proceeding anyway...", file=sys.stderr)
    
    kwargs = {
        "persist_dir": args.persist_dir,
        "enable_warmup": not args.no_warmup,
        "enable_compression": not args.no_compression,
        "enable_permission": not args.skip_permission,
        "enable_memory": not args.no_memory,
        "enable_skillify": not args.no_skillify,
        "stream": getattr(args, 'stream', False),
        "lang": getattr(args, 'lang', 'auto'),
    }
    if args.permission_level:
        kwargs["permission_level"] = PermissionLevel(args.permission_level.upper())

    backend = _create_backend(args.backend, args.base_url, args.model)
    if backend is None and args.backend not in ("mock", None):
        print(f"\nError: Failed to create '{args.backend}' backend.", file=sys.stderr)
        print("Falling back to mock mode is NOT allowed when a backend is explicitly specified.", file=sys.stderr)
        print("Please check your API key and configuration.", file=sys.stderr)
        return 1
    if backend is not None:
        kwargs["llm_backend"] = backend

    disp = MultiAgentDispatcher(**kwargs)

    try:
        if args.quick:
            result = disp.quick_dispatch(
                task,  # 使用验证后的任务
                output_format=args.format if args.format in ("structured", "compact", "detailed") else "structured",
                include_action_items=args.action_items,
                include_timing=args.timing,
            )
        else:
            result = disp.dispatch(
                task,  # 使用验证后的任务
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
        stats = disp.get_status() if hasattr(disp, 'get_status') else {}
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


def cmd_lifecycle(args):
    """Handle lifecycle commands (spec/plan/build/test/review/ship) as View Layer over 11-phase lifecycle."""
    command = args.lifecycle_command
    preset = LIFECYCLE_PRESETS.get(command)

    if not preset:
        print(f"Error: Unknown lifecycle command '{command}'", file=sys.stderr)
        print(f"Available: {', '.join(LIFECYCLE_COMMANDS)}", file=sys.stderr)
        return 1

    task_text = args.task if args.task is not None else args.task_positional
    if not task_text:
        print(f"Error: Task description required for '{command}' command.", file=sys.stderr)
        print(f"Usage: devsquad {command} \"your task\"", file=sys.stderr)
        return 1

    validator = InputValidator()
    task_result = validator.validate_task(task_text)
    if not task_result.valid:
        print(f"Error: Invalid task - {task_result.reason}", file=sys.stderr)
        return 1

    task = task_result.sanitized_input or task_text

    # Show view layer mapping information (Plan C: CLI as View Layer)
    try:
        from scripts.collaboration.lifecycle_protocol import VIEW_MAPPINGS, get_shared_protocol
        mapping = VIEW_MAPPINGS.get(command)

        print(f"\n{'='*60}")
        print(f"🔄 DevSquad Lifecycle [View Layer Mode]")
        print(f"{'='*60}")
        print(f"📌 Command: {command.upper()}")
        if mapping:
            print(f"📋 Maps to Phases: {', '.join(mapping.phases)}")
            print(f"🎯 Mode: SHORTCUT (simplified view of 11-phase lifecycle)")
        print(f"📝 Description: {preset['description']}")
        print(f"👥 Roles: {', '.join(preset['required_roles'])}")
        print(f"🚧 Gate: {preset['gate']}")
        print(f"\n{preset['pre_dispatch_message']}\n")
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"🔄 DevSquad Lifecycle: {command.upper()}")
        print(f"{'='*60}")
        print(f"📌 Description: {preset['description']}")
        print(f"👥 Roles: {', '.join(preset['required_roles'])}")
        print(f"(View mapping info unavailable: {e})\n")
    print(f"⚙️  Mode: {preset['mode']}")
    print(f"🚧 Gate: {preset['gate']}")
    print(f"\n{preset['pre_dispatch_message']}\n")
    print(f"{'='*60}\n")

    kwargs = {
        "persist_dir": args.persist_dir,
        "enable_warmup": not args.no_warmup,
        "enable_compression": not args.no_compression,
        "enable_permission": not args.skip_permission,
        "enable_memory": not args.no_memory,
        "enable_skillify": not args.no_skillify,
        "stream": getattr(args, 'stream', False),
        "lang": getattr(args, 'lang', 'auto'),
    }

    backend = _create_backend(args.backend, args.base_url, args.model)
    if backend is not None:
        kwargs["llm_backend"] = backend

    disp = MultiAgentDispatcher(**kwargs)

    try:
        result = disp.dispatch(
            task,
            roles=preset["required_roles"],
            mode=preset["mode"],
            dry_run=args.dry_run,
        )

        if args.format == "json":
            output = {
                "lifecycle_command": command,
                "gate": preset["gate"],
                "success": result.success,
                "matched_roles": getattr(result, 'matched_roles', None),
                "summary": result.summary,
                "report": result.to_markdown(),
            }
            print(json.dumps(output, ensure_ascii=False, indent=2))
        elif args.format == "compact":
            print(result.summary)
        else:
            print(result.to_markdown())

        return 0 if result.success else 1
    finally:
        disp.shutdown()


def main():
    parser = argparse.ArgumentParser(
        description="DevSquad V3.4 — Multi-Agent Orchestration Engine for Software Development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s dispatch -t "Design user auth system" -r architect pm tester
  %(prog)s dispatch -t "Review codebase" --mode consensus --format json
  %(prog)s dispatch -t "Analyze API" --quick --format compact
  %(prog)s dispatch -t "Security audit" -r security --backend openai
  %(prog)s spec -t "User authentication system"
  %(prog)s build -t "Implement login API"
  %(prog)s test -t "Run all unit tests"
  %(prog)s review -t "Check PR #123"
  %(prog)s ship -t "Deploy v2.0 to production"
  %(prog)s roles
  %(prog)s status
  %(prog)s --version

Lifecycle Commands (P0-4 Agent Skills Integration):
  spec      Define/refine requirements into specification (architect + pm)
  plan      Break down spec into atomic tasks (architect + pm)
  build     Implement with TDD discipline (architect + coder + tester)
  test      Run tests with evidence requirements (tester + coder)
  review    Five-axis code review (coder + security + tester + architect)
  ship      Pre-launch checklist + deployment prep (devops + security + architect)

Environment Variables (API keys are read from env vars only, never command line):
  DEVSQUAD_LLM_BACKEND   Default LLM backend (mock/openai/anthropic)
  OPENAI_API_KEY         OpenAI API key (required for --backend openai)
  OPENAI_BASE_URL        Custom API endpoint (for OpenAI-compatible APIs)
  OPENAI_MODEL           Model name (default: gpt-4)
  ANTHROPIC_API_KEY      Anthropic API key (required for --backend anthropic)
  ANTHROPIC_MODEL        Model name (default: claude-sonnet-4-20250514)
        """,
    )
    parser.add_argument("--version", action="version", version=f"DevSquad {VERSION}")

    subparsers = parser.add_subparsers(dest="command", required=True, help="Available commands")

    p_dispatch = subparsers.add_parser("dispatch", aliases=["run", "d"], help="Execute a multi-agent task")
    p_dispatch.add_argument("task_positional", nargs="?", default=None, help="Task description (positional, no -t needed)")
    p_dispatch.add_argument("--task", "-t", help="Task description (alternative to positional)")
    p_dispatch.add_argument("--roles", "-r", nargs="+", choices=ALL_ROLE_IDS, help="Roles to involve (default: auto-match)")
    p_dispatch.add_argument("--mode", "-m", choices=MODES, default="auto", help="Execution mode (default: auto)")
    p_dispatch.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
    p_dispatch.add_argument("--backend", "-b", choices=BACKENDS, default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
                            help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)")
    p_dispatch.add_argument("--base-url", help="Custom API base URL (or use OPENAI_BASE_URL env)")
    p_dispatch.add_argument("--model", help="Model name (or use OPENAI_MODEL/ANTHROPIC_MODEL env)")
    p_dispatch.add_argument("--dry-run", action="store_true", help="Simulate without execution")
    p_dispatch.add_argument("--quick", "-q", action="store_true", help="Use quick_dispatch (3 formats)")
    p_dispatch.add_argument("--action-items", action="store_true", help="Include H/M/L action items")
    p_dispatch.add_argument("--timing", action="store_true", help="Include timing info")
    p_dispatch.add_argument("--persist-dir", help="Custom scratchpad directory")
    p_dispatch.add_argument("--no-warmup", action="store_true", help="Disable startup warmup")
    p_dispatch.add_argument("--no-compression", action="store_true", help="Disable context compression")
    p_dispatch.add_argument("--stream", action="store_true", help="Stream LLM output in real-time (requires --backend)")
    p_dispatch.add_argument("--lang", choices=["auto", "en", "zh", "ja"], default="auto", help="Output language (default: auto-detect)")
    p_dispatch.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
    p_dispatch.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
    p_dispatch.add_argument("--no-skillify", action="store_true", help="Disable skill learning")
    p_dispatch.add_argument("--permission-level", choices=["PLAN", "DEFAULT", "AUTO", "BYPASS"], help="Permission level")

    subparsers.add_parser("status", aliases=["s"], help="Show system status")

    p_roles = subparsers.add_parser("roles", aliases=["ls"], help="List available roles")
    p_roles.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    p_lifecycle = subparsers.add_parser("lifecycle", aliases=["lc"], help="Execute lifecycle workflow command")
    p_lifecycle.add_argument("lifecycle_command", choices=LIFECYCLE_COMMANDS, help="Lifecycle command to execute")
    p_lifecycle.add_argument("task_positional", nargs="?", default=None, help="Task description (positional)")
    p_lifecycle.add_argument("--task", "-t", help="Task description (alternative to positional)")
    p_lifecycle.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
    p_lifecycle.add_argument("--backend", "-b", choices=BACKENDS, default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
                              help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)")
    p_lifecycle.add_argument("--base-url", help="Custom API base URL (or use OPENAI_BASE_URL env)")
    p_lifecycle.add_argument("--model", help="Model name (or use OPENAI_MODEL/ANTHROPIC_MODEL env)")
    p_lifecycle.add_argument("--dry-run", action="store_true", help="Simulate without execution")
    p_lifecycle.add_argument("--persist-dir", help="Custom scratchpad directory")
    p_lifecycle.add_argument("--no-warmup", action="store_true", help="Disable startup warmup")
    p_lifecycle.add_argument("--no-compression", action="store_true", help="Disable context compression")
    p_lifecycle.add_argument("--stream", action="store_true", help="Stream LLM output in real-time (requires --backend)")
    p_lifecycle.add_argument("--lang", choices=["auto", "en", "zh", "ja"], default="auto", help="Output language (default: auto-detect)")
    p_lifecycle.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
    p_lifecycle.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
    p_lifecycle.add_argument("--no-skillify", action="store_true", help="Disable skill learning")

    for cmd_name in LIFECYCLE_COMMANDS:
        cmd_help = LIFECYCLE_PRESETS[cmd_name]["description"]
        p_cmd = subparsers.add_parser(cmd_name, help=cmd_help)
        p_cmd.add_argument("task_positional", nargs="?", default=None, help="Task description (positional)")
        p_cmd.add_argument("--task", "-t", help="Task description (alternative to positional)")
        p_cmd.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
        p_cmd.add_argument("--backend", "-b", choices=BACKENDS, default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
                            help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)")
        p_cmd.add_argument("--base-url", help="Custom API base URL (or use OPENAI_BASE_URL env)")
        p_cmd.add_argument("--model", help="Model name (or use OPENAI_MODEL/ANTHROPIC_MODEL env)")
        p_cmd.add_argument("--dry-run", action="store_true", help="Simulate without execution")
        p_cmd.add_argument("--persist-dir", help="Custom scratchpad directory")
        p_cmd.add_argument("--no-warmup", action="store_true", help="Disable startup warmup")
        p_cmd.add_argument("--no-compression", action="store_true", help="Disable context compression")
        p_cmd.add_argument("--stream", action="store_true", help="Stream LLM output in real-time (requires --backend)")
        p_cmd.add_argument("--lang", choices=["auto", "en", "zh", "ja"], default="auto", help="Output language (default: auto-detect)")
        p_cmd.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
        p_cmd.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
        p_cmd.add_argument("--no-skillify", action="store_true", help="Disable skill learning")

    args = parser.parse_args()

    if args.command in ("dispatch", "run", "d"):
        return cmd_dispatch(args)
    elif args.command in ("status", "s"):
        return cmd_status(args)
    elif args.command in ("roles", "ls"):
        return cmd_roles(args)
    elif args.command in ("lifecycle", "lc") or args.command in LIFECYCLE_COMMANDS:
        if args.command in LIFECYCLE_COMMANDS:
            args.lifecycle_command = args.command
        return cmd_lifecycle(args)
    else:
        parser.print_help()
        return 0


if __name__ == "__main__":
    sys.exit(main())
