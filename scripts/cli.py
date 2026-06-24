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
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.cli_dispatch import cmd_demo, cmd_dispatch, cmd_roles, cmd_status
from scripts.cli_lifecycle import cmd_lifecycle
from scripts.cli_utils import (
    ALL_ROLE_IDS,
    BACKENDS,
    FORMATS,
    LIFECYCLE_COMMANDS,
    LIFECYCLE_PRESETS,
    MODES,
    VERSION,
    _create_backend,  # noqa: F401  re-exported for test compatibility
    _prompt_choice,
    _prompt_yes_no,
    _quick_init,
    _save_config,
)
from scripts.collaboration.models import ROLE_REGISTRY


def cmd_init(args):
    """
    Interactive initialization wizard for DevSquad.

    Guides new users through setup:
    - Project type selection
    - LLM backend configuration
    - Default role preferences
    - Output language
    - Config file generation
    """

    # Quick init: non-interactive mode with sensible defaults
    if getattr(args, "quick", False) or getattr(args, "non_interactive", False):
        return _quick_init()

    print("\n" + "=" * 60)
    print("🚀 Welcome to DevSquad Setup Wizard!")
    print("=" * 60)
    print("\nThis wizard will help you configure DevSquad for your project.")
    print("It should take about 1-2 minutes.\n")

    config = {
        "project_type": None,
        "llm_backend": "mock",
        "default_roles": ["auto"],
        "language": "auto",
        "features": {},
    }

    # Step 1: Project Type
    print("📋 Step 1/5: Project Type")
    print("-" * 40)
    project_types = {
        "1": {
            "id": "web-api",
            "name": "Web API / Backend Service",
            "desc": "REST API, GraphQL, microservices",
            "roles": ["architect", "solo-coder", "security", "tester"],
        },
        "2": {
            "id": "web-fullstack",
            "name": "Full-Stack Web App",
            "desc": "Frontend + Backend + Database",
            "roles": ["architect", "ui-designer", "solo-coder", "tester"],
        },
        "3": {
            "id": "cli-tool",
            "name": "CLI Tool / Utility",
            "desc": "Command-line application, DevOps tool",
            "roles": ["architect", "solo-coder", "tester"],
        },
        "4": {
            "id": "ml-service",
            "name": "AI/ML Service",
            "desc": "Machine learning pipeline, data service",
            "roles": ["architect", "solo-coder", "tester", "devops"],
        },
        "5": {
            "id": "library",
            "name": "Library / SDK",
            "desc": "Reusable package, API wrapper",
            "roles": ["architect", "solo-coder", "tester"],
        },
        "6": {
            "id": "generic",
            "name": "Generic / Other",
            "desc": "Custom project or exploring DevSquad",
            "roles": ["auto"],
        },
    }

    for key, ptype in project_types.items():
        print(f"   {key}) {ptype['name']}")
        print(f"      {ptype['desc']}")

    project_choice = _prompt_choice("Select your project type [1-6]", list(project_types.keys()), default="6")
    selected_type = project_types[project_choice]
    config["project_type"] = selected_type["id"]
    config["default_roles"] = selected_type["roles"]

    print(f"\n   ✅ Selected: {selected_type['name']}")
    print(f"   💡 Recommended roles: {', '.join(selected_type['roles'])}")

    # Step 2: LLM Backend
    print("\n\n🤖 Step 2/5: AI Backend Configuration")
    print("-" * 40)
    print("DevSquad can work with different AI backends:")
    print()
    print("   1) Mock Mode (Recommended for beginners)")
    print("      • No API key needed")
    print("      • Fast response (< 1 second)")
    print("      • Great for testing and learning")
    print()
    print("   2) OpenAI (GPT-4, GPT-3.5)")
    print("      • Requires OPENAI_API_KEY")
    print("      • Real AI analysis and suggestions")
    print("      • Best for production use")
    print()
    print("   3) Anthropic (Claude)")
    print("      • Requires ANTHROPIC_API_KEY")
    print("      • Excellent at complex reasoning")
    print("      • Good for architecture decisions")
    print()

    backend_options = {"1": "mock", "2": "openai", "3": "anthropic"}
    backend_choice = _prompt_choice("Select AI backend [1-3]", list(backend_options.keys()), default="1")
    config["llm_backend"] = backend_options[backend_choice]

    if config["llm_backend"] != "mock":
        env_var = "OPENAI_API_KEY" if config["llm_backend"] == "openai" else "ANTHROPIC_API_KEY"
        if not os.environ.get(env_var):
            print(f"\n   ⚠️  Warning: {env_var} is not set!")
            print("   You'll need to set it before using real AI:")
            print(f'   export {env_var}="your-api-key-here"')
            print("\n   For now, we'll save the preference. You can configure the key later.")

    print(f"\n   ✅ Backend: {config['llm_backend'].upper()}")

    # Step 3: Default Roles
    print("\n\n👥 Step 3/5: Role Preferences")
    print("-" * 40)

    if "auto" in config["default_roles"]:
        print("   With 'Generic' project type, roles will be auto-matched based on task content.")
        print("   This is recommended for beginners!")
    else:
        print("   Based on your project type, we recommend these roles:")
        for role in config["default_roles"]:
            role_def = ROLE_REGISTRY.get(role)
            if role_def:
                print(f"   • {role_def.name} — {role_def.description}")

        customize = _prompt_yes_no("Customize role selection?", default=False)
        if customize:
            print("\n   Available roles:")
            all_roles = []
            for rid, rdef in ROLE_REGISTRY.items():
                alias = rdef.aliases[0] if rdef.aliases else rid
                status = "" if rdef.status == "active" else " [planned]"
                print(f"     {alias:<12} — {rdef.description}{status}")
                all_roles.append(alias)

            print()
            roles_input = input("   Enter roles (comma-separated, e.g., arch sec test): ").strip()
            if roles_input:
                config["default_roles"] = [r.strip() for r in roles_input.split(",")]

    print("\n   ✅ Roles configured")

    # Step 4: Language & Features
    print("\n\n🌐 Step 4/5: Language & Features")
    print("-" * 40)

    lang_options = {
        "1": ("auto", "Auto-detect from system locale"),
        "2": ("zh", "中文 (Chinese)"),
        "3": ("en", "English"),
        "4": ("ja", "日本語 (Japanese)"),
    }
    print("   Output language:")
    for key, (_code, desc) in lang_options.items():
        print(f"   {key}) {desc}")

    lang_choice = _prompt_choice("Select language [1-4]", list(lang_options.keys()), default="1")
    config["language"] = lang_options[lang_choice][0]

    print("\n   Optional features (can be enabled later):")
    features = {
        "warmup": _prompt_yes_no("   Enable startup warmup? (faster subsequent runs)", default=True),
        "compression": _prompt_yes_no("   Enable context compression? (for long tasks)", default=True),
        "memory": _prompt_yes_no("   Enable memory bridge? (learn from history)", default=False),
        "permission": _prompt_yes_no("   Enable permission guard? (security checks)", default=True),
    }
    config["features"] = features

    print(f"\n   ✅ Language: {config['language']}")
    enabled_features = [k for k, v in features.items() if v]
    if enabled_features:
        print(f"   ✅ Features: {', '.join(enabled_features)}")

    # Step 5: Summary & Save
    print("\n\n💾 Step 5/5: Configuration Summary")
    print("-" * 60)

    print(f"\n   📁 Project Type: {selected_type['name']}")
    print(f"   🤖 AI Backend:   {config['llm_backend'].upper()}")
    print(f"   👥 Default Roles: {', '.join(config['default_roles'])}")
    print(f"   🌐 Language:     {config['language']}")
    print(f"   ⚙️  Features:     {', '.join(enabled_features) if enabled_features else 'None'}")

    confirm = _prompt_yes_no("\n   Save this configuration?", default=True)

    if not confirm:
        print("\n   ❌ Configuration cancelled. You can run 'devsquad init' again anytime.")
        return 0

    # Generate configuration file
    config_path = os.path.expanduser("~/.devsquad.yaml")
    saved = _save_config(config, config_path)

    if saved:
        print(f"\n   ✅ Configuration saved to: {config_path}")
    else:
        print(f"\n   ⚠️  Could not save to {config_path}. Using inline defaults.")

    # Final success message
    print("\n" + "=" * 60)
    print("🎉 Setup Complete! DevSquad is ready to use.")
    print("=" * 60)

    print("\n🚀 Quick Start Commands:\n")
    print("   # Basic usage (auto-match roles)")
    print('   devsquad dispatch -t "your task description"')
    print()
    print("   # With specific roles")
    print('   devsquad dispatch -t "design auth system" -r arch sec')
    print()
    print("   # Use lifecycle commands")
    print('   devsquad spec -t "user authentication"')
    print('   devsquad build -t "implement login API"')
    print()

    if config["llm_backend"] != "mock":
        print("⚡ To use real AI, set your API key:")
        env_var = "OPENAI_API_KEY" if config["llm_backend"] == "openai" else "ANTHROPIC_API_KEY"
        print(f'   export {env_var}="your-key-here"')
        print()

    print("📚 Learn more:")
    print("   • docs: https://github.com/lulin70/DevSquad#readme")
    print("   • examples: python examples/quick_start.py")
    print("   • help: devsquad --help")
    print("   • roles: devsquad roles")
    print()

    print("Happy coding! 🎯\n")

    return 0


def main():
    """Entry point for the ``devsquad`` CLI.

    Builds the top-level argparse parser with all subcommands (init,
    dispatch, spec, plan, build, test, review, ship, roles, status, demo)
    and dispatches to the corresponding ``cmd_*`` handler.

    Returns:
        The exit code from the selected subcommand, or 0 for ``--version``.
    """
    parser = argparse.ArgumentParser(
        description="DevSquad V3.6 — Multi-Agent Orchestration Engine for Software Development",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s init                              # Interactive setup wizard (recommended for new users)
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
  %(prog)s demo                              # Quick demo (no API key needed)
  %(prog)s demo --scenario intent            # Run only intent detection scenario
  %(prog)s --version

Getting Started (New Users):
  1. Run: %(prog)s init          # Launches interactive setup wizard
  2. Choose your project type and AI backend
  3. Start collaborating: %(prog)s dispatch -t "your task"

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

    # Init command (interactive setup wizard)
    p_init = subparsers.add_parser("init", aliases=["setup", "i"], help="Interactive setup wizard for new users")
    p_init.add_argument("--non-interactive", action="store_true", help="Run in non-interactive mode (use defaults)")
    p_init.add_argument("--quick", "-q", action="store_true", help="Quick non-interactive setup with sensible defaults")

    # Demo command (quick demo, no API key needed)
    p_demo = subparsers.add_parser(
        "demo", aliases=["play", "try"], help="Quick demo showing DevSquad capabilities (mock mode)"
    )
    p_demo.add_argument(
        "--scenario",
        "-s",
        choices=["all", "intent", "security", "dispatch"],
        default="all",
        help="Which scenario to run (default: all)",
    )

    p_dispatch = subparsers.add_parser("dispatch", aliases=["run", "d"], help="Execute a multi-agent task")
    p_dispatch.add_argument(
        "task_positional", nargs="?", default=None, help="Task description (positional, no -t needed)"
    )
    p_dispatch.add_argument("--task", "-t", help="Task description (alternative to positional)")
    p_dispatch.add_argument(
        "--roles", "-r", nargs="+", choices=ALL_ROLE_IDS, help="Roles to involve (default: auto-match)"
    )
    p_dispatch.add_argument("--mode", "-m", choices=MODES, default="auto", help="Execution mode (default: auto)")
    p_dispatch.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
    p_dispatch.add_argument(
        "--backend",
        "-b",
        choices=BACKENDS,
        default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
        help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)",
    )
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
    p_dispatch.add_argument(
        "--lang", choices=["auto", "en", "zh", "ja"], default="auto", help="Output language (default: auto-detect)"
    )
    p_dispatch.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
    p_dispatch.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
    p_dispatch.add_argument("--no-skillify", action="store_true", help="Disable skill learning")
    p_dispatch.add_argument(
        "--permission-level", choices=["PLAN", "DEFAULT", "AUTO", "BYPASS"], help="Permission level"
    )
    p_dispatch.add_argument(
        "--host",
        choices=["claude-code", "cursor", "codex", "cline", "trae", "generic"],
        default=None,
        help="AI host platform adapter (enables host-specific role mapping and output formatting)",
    )

    subparsers.add_parser("status", aliases=["s"], help="Show system status")

    p_roles = subparsers.add_parser("roles", aliases=["ls"], help="List available roles")
    p_roles.add_argument("--format", "-f", choices=["text", "json"], default="text", help="Output format")

    p_lifecycle = subparsers.add_parser("lifecycle", aliases=["lc"], help="Execute lifecycle workflow command")
    p_lifecycle.add_argument("lifecycle_command", choices=LIFECYCLE_COMMANDS, help="Lifecycle command to execute")
    p_lifecycle.add_argument("task_positional", nargs="?", default=None, help="Task description (positional)")
    p_lifecycle.add_argument("--task", "-t", help="Task description (alternative to positional)")
    p_lifecycle.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
    p_lifecycle.add_argument(
        "--backend",
        "-b",
        choices=BACKENDS,
        default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
        help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)",
    )
    p_lifecycle.add_argument("--base-url", help="Custom API base URL (or use OPENAI_BASE_URL env)")
    p_lifecycle.add_argument("--model", help="Model name (or use OPENAI_MODEL/ANTHROPIC_MODEL env)")
    p_lifecycle.add_argument("--dry-run", action="store_true", help="Simulate without execution")
    p_lifecycle.add_argument("--persist-dir", help="Custom scratchpad directory")
    p_lifecycle.add_argument("--no-warmup", action="store_true", help="Disable startup warmup")
    p_lifecycle.add_argument("--no-compression", action="store_true", help="Disable context compression")
    p_lifecycle.add_argument(
        "--stream", action="store_true", help="Stream LLM output in real-time (requires --backend)"
    )
    p_lifecycle.add_argument(
        "--lang", choices=["auto", "en", "zh", "ja"], default="auto", help="Output language (default: auto-detect)"
    )
    p_lifecycle.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
    p_lifecycle.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
    p_lifecycle.add_argument("--no-skillify", action="store_true", help="Disable skill learning")
    p_lifecycle.add_argument(
        "--visual",
        "-v",
        action="store_true",
        help="Enable enhanced visual output (colored progress, icons, formatted tables)",
    )
    p_lifecycle.add_argument("--verbose", action="store_true", help="Show detailed phase information and gate status")

    for cmd_name in LIFECYCLE_COMMANDS:
        cmd_help = LIFECYCLE_PRESETS[cmd_name]["description"]
        p_cmd = subparsers.add_parser(cmd_name, help=cmd_help)
        p_cmd.add_argument("task_positional", nargs="?", default=None, help="Task description (positional)")
        p_cmd.add_argument("--task", "-t", help="Task description (alternative to positional)")
        p_cmd.add_argument("--format", "-f", choices=FORMATS, default="markdown", help="Output format")
        p_cmd.add_argument(
            "--backend",
            "-b",
            choices=BACKENDS,
            default=os.environ.get("DEVSQUAD_LLM_BACKEND", "mock"),
            help="LLM backend (default: mock, or DEVSQUAD_LLM_BACKEND env)",
        )
        p_cmd.add_argument("--base-url", help="Custom API base URL (or use OPENAI_BASE_URL env)")
        p_cmd.add_argument("--model", help="Model name (or use OPENAI_MODEL/ANTHROPIC_MODEL env)")
        p_cmd.add_argument("--dry-run", action="store_true", help="Simulate without execution")
        p_cmd.add_argument("--persist-dir", help="Custom scratchpad directory")
        p_cmd.add_argument("--no-warmup", action="store_true", help="Disable startup warmup")
        p_cmd.add_argument("--no-compression", action="store_true", help="Disable context compression")
        p_cmd.add_argument("--stream", action="store_true", help="Stream LLM output in real-time (requires --backend)")
        p_cmd.add_argument(
            "--lang", choices=["auto", "en", "zh", "ja"], default="auto", help="Output language (default: auto-detect)"
        )
        p_cmd.add_argument("--skip-permission", action="store_true", help="Skip permission checks")
        p_cmd.add_argument("--no-memory", action="store_true", help="Disable memory bridge")
        p_cmd.add_argument("--no-skillify", action="store_true", help="Disable skill learning")

    args = parser.parse_args()

    if args.command in ("init", "setup", "i"):
        return cmd_init(args)
    elif args.command in ("demo", "play", "try"):
        return cmd_demo(args)
    elif args.command in ("dispatch", "run", "d"):
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
