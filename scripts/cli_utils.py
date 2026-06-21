#!/usr/bin/env python3
"""
DevSquad CLI 共享工具函数与常量。

本模块包含 CLI 子命令共享的常量（ROLES / MODES / FORMATS / BACKENDS /
LIFECYCLE_COMMANDS / LIFECYCLE_PRESETS）、后端创建函数（_create_backend）
以及交互式初始化辅助函数（_prompt_choice / _prompt_yes_no / _save_config /
_quick_init）。
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scripts.collaboration._version import __version__
from scripts.collaboration.models import ROLE_REGISTRY, get_cli_role_list

ROLES = get_cli_role_list()
ALL_ROLE_IDS = list(ROLE_REGISTRY.keys()) + ROLES
ALL_ROLE_IDS = sorted(set(ALL_ROLE_IDS))
MODES = ["auto", "parallel", "sequential", "consensus"]
FORMATS = ["markdown", "json", "compact", "structured", "detailed"]
BACKENDS = ["mock", "trae", "openai", "anthropic"]
LIFECYCLE_COMMANDS = ["spec", "plan", "build", "test", "review", "ship"]

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
        "pre_dispatch_message": ("📝 Decomposing into atomic tasks with acceptance criteria and dependency ordering."),
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


def _create_backend(backend_type: str, base_url: str = None, model: str = None):
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
            print('  export OPENAI_API_KEY="sk-..."', file=sys.stderr)
            return None
        kwargs["api_key"] = api_key
        kwargs.setdefault("base_url", os.environ.get("OPENAI_BASE_URL"))
        kwargs.setdefault("model", os.environ.get("OPENAI_MODEL", "gpt-4"))
    elif backend_type == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
            print('  export ANTHROPIC_API_KEY="sk-ant-..."', file=sys.stderr)
            return None
        kwargs["api_key"] = api_key
        kwargs.setdefault("model", os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))
    return create_backend(backend_type, **kwargs)


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
                f.write("# DevSquad Configuration (generated by init wizard)\n")
                f.write(f"# Created: {__import__('datetime').datetime.now().isoformat()}\n\n")
                f.write(f"project_type: {config['project_type']}\n")
                f.write(f"llm_backend: {config['llm_backend']}\n")
                f.write(f"default_language: {config['language']}\n")
                f.write(f"default_roles: {', '.join(config['default_roles'])}\n")
            return True
        except OSError as e:
            logger.warning("Failed to save config: %s", e)
            return False
    except (OSError, TypeError, ValueError, KeyError) as e:
        logger.warning("Failed to save config: %s", e)
        return False


def _quick_init():
    """
    Quick non-interactive initialization with sensible defaults.

    Generates:
      - ~/.devsquad.yaml (main config)
      - ~/.devsquad/.env (environment template, copied from .env.example if exists)
    """
    import shutil as _shutil

    print("\n⚡ DevSquad Quick Setup (non-interactive)")

    config = {
        "project_type": "generic",
        "llm_backend": "mock",
        "default_roles": ["auto"],
        "language": "auto",
        "features": {
            "warmup": True,
            "compression": True,
            "memory": False,
            "permission": True,
        },
    }

    # Save main config
    config_path = os.path.expanduser("~/.devsquad.yaml")
    saved = _save_config(config, config_path)

    if saved:
        print(f"  ✅ Config saved: {config_path}")
    else:
        print(f"  ⚠️  Could not save config to {config_path}")

    # Copy .env.example to ~/.devsquad/.env (if not exists)
    devsquad_dir = os.path.expanduser("~/.devsquad")
    env_path = os.path.join(devsquad_dir, ".env")

    try:
        os.makedirs(devsquad_dir, exist_ok=True)

        if not os.path.exists(env_path):
            # Try to copy from project root .env.example
            project_env_example = os.path.join(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env.example"
            )
            if os.path.exists(project_env_example):
                _shutil.copy2(project_env_example, env_path)
                logger.info("  ✅ Env template: %s", env_path)
                logger.info("     Edit this file to add your API keys")
            else:
                # Create minimal .env
                with open(env_path, "w") as f:
                    f.write("# DevSquad Environment Configuration\n")
                    f.write("# Generated by quick init\n\n")
                    f.write("DEVSQUAD_LLM_BACKEND=mock\n")
                    f.write("# Uncomment and fill in your API keys:\n")
                    f.write("# OPENAI_API_KEY=\n")
                    f.write("# ANTHROPIC_API_KEY=\n")
                logger.info("  ✅ Env template: %s (minimal)", env_path)
        else:
            logger.info("  ℹ️  Env file already exists: %s", env_path)

    except (OSError, RuntimeError) as e:
        logger.warning("Failed to create env template: %s", e)
        logger.warning("  ⚠️  Could not create env template: %s", e)

    # Summary
    logger.info("\n🎉 Quick setup complete!")
    logger.info("\n📋 Next steps:")
    logger.info("  1. Run demo:  devsquad demo")
    logger.info('  2. Run task:  devsquad dispatch -t "your task"')
    logger.info("  3. Set keys:  edit ~/.devsquad/.env (optional, for real AI)")
    logger.info("")

    return 0
