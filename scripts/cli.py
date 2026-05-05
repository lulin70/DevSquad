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
import logging

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
logger = logging.getLogger(__name__)

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
    import sys as _sys

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
        "1": {"id": "web-api", "name": "Web API / Backend Service", "desc": "REST API, GraphQL, microservices", "roles": ["architect", "solo-coder", "security", "tester"]},
        "2": {"id": "web-fullstack", "name": "Full-Stack Web App", "desc": "Frontend + Backend + Database", "roles": ["architect", "ui-designer", "solo-coder", "tester"]},
        "3": {"id": "cli-tool", "name": "CLI Tool / Utility", "desc": "Command-line application, DevOps tool", "roles": ["architect", "solo-coder", "tester"]},
        "4": {"id": "ml-service", "name": "AI/ML Service", "desc": "Machine learning pipeline, data service", "roles": ["architect", "solo-coder", "tester", "devops"]},
        "5": {"id": "library", "name": "Library / SDK", "desc": "Reusable package, API wrapper", "roles": ["architect", "solo-coder", "tester"]},
        "6": {"id": "generic", "name": "Generic / Other", "desc": "Custom project or exploring DevSquad", "roles": ["auto"]},
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
    print(f"\n\n🤖 Step 2/5: AI Backend Configuration")
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
            print(f"   You'll need to set it before using real AI:")
            print(f'   export {env_var}="your-api-key-here"')
            print(f"\n   For now, we'll save the preference. You can configure the key later.")

    print(f"\n   ✅ Backend: {config['llm_backend'].upper()}")

    # Step 3: Default Roles
    print(f"\n\n👥 Step 3/5: Role Preferences")
    print("-" * 40)

    if "auto" in config["default_roles"]:
        print("   With 'Generic' project type, roles will be auto-matched based on task content.")
        print("   This is recommended for beginners!")
    else:
        print(f"   Based on your project type, we recommend these roles:")
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

    print(f"\n   ✅ Roles configured")

    # Step 4: Language & Features
    print(f"\n\n🌐 Step 4/5: Language & Features")
    print("-" * 40)

    lang_options = {
        "1": ("auto", "Auto-detect from system locale"),
        "2": ("zh", "中文 (Chinese)"),
        "3": ("en", "English"),
        "4": ("ja", "日本語 (Japanese)"),
    }
    print("   Output language:")
    for key, (code, desc) in lang_options.items():
        print(f"   {key}) {desc}")

    lang_choice = _prompt_choice("Select language [1-4]", list(lang_options.keys()), default="1")
    config["language"] = lang_options[lang_choice][0]

    print(f"\n   Optional features (can be enabled later):")
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
    print(f"\n\n💾 Step 5/5: Configuration Summary")
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

    print(f"\n🚀 Quick Start Commands:\n")
    print(f"   # Basic usage (auto-match roles)")
    print(f'   devsquad dispatch -t "your task description"')
    print()
    print(f"   # With specific roles")
    print(f'   devsquad dispatch -t "design auth system" -r arch sec')
    print()
    print(f"   # Use lifecycle commands")
    print(f'   devsquad spec -t "user authentication"')
    print(f'   devsquad build -t "implement login API"')
    print()

    if config["llm_backend"] != "mock":
        print(f"⚡ To use real AI, set your API key:")
        env_var = "OPENAI_API_KEY" if config["llm_backend"] == "openai" else "ANTHROPIC_API_KEY"
        print(f'   export {env_var}="your-key-here"')
        print()

    print(f"📚 Learn more:")
    print(f"   • docs: https://github.com/lulin70/DevSquad#readme")
    print(f"   • examples: python examples/quick_start.py")
    print(f"   • help: devsquad --help")
    print(f"   • roles: devsquad roles")
    print()

    print("Happy coding! 🎯\n")

    return 0


def _prompt_choice(prompt: str, valid_choices: list, default: str = None) -> str:
    """Prompt user for choice with validation."""
    while True:
        try:
            user_input = input(f"   {prompt}: ").strip()
            if not user_input and default:
                return default
            if user_input in valid_choices:
                return user_input
            print(f"   ❌ Invalid choice. Please enter: {', '.join(valid_choices)}")
        except EOFError:
            if default:
                return default
            print("   Non-interactive mode detected. Using default.")
            return default
        except KeyboardInterrupt:
            print("\n\n❌ Setup cancelled by user.")
            sys.exit(1)


def _prompt_yes_no(prompt: str, default: bool = True) -> bool:
    """Prompt user for yes/no confirmation."""
    default_str = "Y/n" if default else "y/N"
    while True:
        try:
            user_input = input(f"{prompt} [{default_str}]: ").strip().lower()
            if not user_input:
                return default
            if user_input in ("y", "yes", "1", "true"):
                return True
            if user_input in ("n", "no", "0", "false"):
                return False
            print("   Please enter y/n or yes/no")
        except EOFError:
            return default
        except KeyboardInterrupt:
            print("\n\n❌ Setup cancelled by user.")
            sys.exit(1)


def _save_config(config: dict, config_path: str) -> bool:
    """Save configuration to YAML file."""
    config_path = os.path.expanduser(config_path)

    if os.path.islink(config_path):
        print(f"\n   ⚠️  {config_path} is a symbolic link. Skipping for security.")
        return False

    try:
        import yaml

        yaml_config = {
            "version": VERSION,
            "project_type": config["project_type"],
            "llm_backend": config["llm_backend"],
            "default_language": config["language"],
            "default_roles": config["default_roles"],
            "features": {
                "warmup": config["features"].get("warmup", True),
                "compression": config["features"].get("compression", True),
                "memory_bridge": config["features"].get("memory", False),
                "permission_guard": config["features"].get("permission", True),
            },
        }

        with open(config_path, "w") as f:
            yaml.dump(yaml_config, f, default_flow_style=False, allow_unicode=True)

        return True

    except ImportError:
        # YAML not available, create simple format
        try:
            with open(config_path, "w") as f:
                f.write(f"# DevSquad Configuration (generated by init wizard)\n")
                f.write(f"# Created: {__import__('datetime').datetime.now().isoformat()}\n\n")
                f.write(f"project_type: {config['project_type']}\n")
                f.write(f"llm_backend: {config['llm_backend']}\n")
                f.write(f"default_language: {config['language']}\n")
                f.write(f"default_roles: {', '.join(config['default_roles'])}\n")
            return True
        except Exception as e:
            logger.warning("Failed to save config: %s", e)
            return False
    except Exception as e:
        logger.warning("Failed to save config: %s", e)
        return False


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

    # Check for visual mode
    use_visual = getattr(args, 'visual', False)
    use_verbose = getattr(args, 'verbose', False)

    # Show view layer mapping information (Plan C: CLI as View Layer)
    try:
        from scripts.collaboration.lifecycle_protocol import VIEW_MAPPINGS, get_shared_protocol
        mapping = VIEW_MAPPINGS.get(command)

        if use_visual:
            # Use enhanced visual output
            import sys as _sys
            import os as _os
            _sys.path.insert(0, _os.path.join(_os.path.dirname(__file__), 'cli'))
            
            try:
                from cli_visual import VisualFormatter, get_visual_formatter, Colors, Icons
                
                vf = get_visual_formatter(use_color=True)
                
                vf.print_lifecycle_header(command, mapping, preset)
                
                # Show resolved phases with details
                protocol = get_shared_protocol()
                if mapping:
                    phases = protocol.resolve_command_to_phases(command)
                    if phases:
                        vf.print_phase_list(phases)
                        
                        # Show progress overview
                        completed_count = len([p for p in phases if p.phase_id in (protocol._completed_phases or [])])
                        vf.print_progress_overview(
                            completed_count,
                            len(phases),
                            f"Command '{command}' Coverage"
                        )
                
                # Show gate status
                gate_name = preset.get('gate', 'Unknown')
                vf.print_gate_status(None, gate_name)
                
                # Verbose mode: show additional info
                if use_verbose:
                    status = protocol.get_status()
                    vf.print_status_summary(status)
                    
                    # Show all available phases info
                    all_phases = protocol.get_all_phases()
                    vf.print_info_box(
                        "All Available Phases",
                        [f"{p.phase_id}: {p.name} ({p.role_id})" for p in all_phases[:8]],
                        icon="📋",
                        color=Colors.BLUE,
                    )
                
                # Print action prompt
                vf.print_info_box(
                    "Ready to Execute",
                    [
                        f"Task: {task[:60]}{'...' if len(task) > 60 else ''}",
                        f"Command: {command.upper()}",
                        f"Next step: Run dispatch or view examples",
                    ],
                    icon=Icons.ROCKET,
                    color=Colors.GREEN,
                )
                
                vf.print_footer()
                
            except ImportError as ve:
                print(f"\n⚠️  Visual module not available: {ve}")
                print("Falling back to standard output...\n")
                use_visual = False  # Fall back to standard output
        
        elif use_verbose:
            # Verbose text output (no colors but detailed)
            print(f"\n{'='*60}")
            print(f"🔄 DevSquad Lifecycle [Verbose Mode]")
            print(f"{'='*60}")
            print(f"📌 Command: {command.upper()}")
            if mapping:
                print(f"📋 Maps to Phases: {', '.join(mapping.phases)}")
                print(f"🎯 Mode: SHORTCUT (simplified view of 11-phase lifecycle)")
                
                # Show phase details
                protocol = get_shared_protocol()
                phases = protocol.resolve_command_to_phases(command)
                if phases:
                    print(f"\n📝 Phase Details:")
                    for p in phases:
                        print(f"   • {p.phase_id}: {p.name}")
                        print(f"     Role: {p.role_id}")
                        if p.dependencies:
                            print(f"     Dependencies: {', '.join(p.dependencies)}")
            
            print(f"\n📝 Description: {preset['description']}")
            print(f"👥 Roles: {', '.join(preset['required_roles'])}")
            print(f"⚙️  Mode: {preset['mode']}")
            print(f"🚧 Gate: {preset['gate']}")
            print(f"\n{preset['pre_dispatch_message']}\n")
            print(f"{'='*60}\n")
        
        else:
            # Original simple output (backward compatible)
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
            print(f"💡 Tip: Use --visual for enhanced output, --verbose for details\n")

    except Exception as e:
        print(f"\n{'='*60}")
        print(f"🔄 DevSquad Lifecycle: {command.upper()}")
        print(f"{'='*60}")
        print(f"📌 Description: {preset['description']}")
        print(f"👥 Roles: {', '.join(preset['required_roles'])}")
        print(f"(View mapping info unavailable: {e})\n")

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
    p_init = subparsers.add_parser("init", aliases=["setup", "i"],
                                    help="Interactive setup wizard for new users")
    p_init.add_argument("--non-interactive", action="store_true",
                        help="Run in non-interactive mode (use defaults)")

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
    p_lifecycle.add_argument("--visual", "-v", action="store_true",
                              help="Enable enhanced visual output (colored progress, icons, formatted tables)")
    p_lifecycle.add_argument("--verbose", action="store_true",
                              help="Show detailed phase information and gate status")

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

    if args.command in ("init", "setup", "i"):
        return cmd_init(args)
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
