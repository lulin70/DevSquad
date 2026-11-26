#!/usr/bin/env python3
"""TD-077 dependency gate for the DevSquad CLI entry point.

Extracted from scripts/cli.py (module size baseline gate, V4.6.0): the CLI
imports this module FIRST (stdlib-only, no yaml/pydantic) and calls
``check_critical_dependencies()`` before touching the heavy import chain.
"""

import importlib
import sys

# Modules the scripts.* import chain requires at startup. Keys are import
# names; values are the pip package names shown in the fix message.
_CRITICAL_DEPS: list[tuple[str, str]] = [
    ("yaml", "pyyaml"),
    ("pydantic", "pydantic"),
]


def check_critical_dependencies(modules: list[tuple[str, str]] | None = None) -> None:
    """Fail fast with an actionable message when critical deps are missing.

    Runs before the ``scripts.*`` import chain so the CLI never reaches an
    opaque ``ModuleNotFoundError`` deep inside the collaboration modules.

    Raises:
        SystemExit: code 2 (environment_blocked) when any dependency is missing.
    """
    checked = modules if modules is not None else _CRITICAL_DEPS
    missing = []
    for module_name, package_name in checked:
        try:
            importlib.import_module(module_name)
        except ImportError:
            missing.append(package_name)
    if missing:
        print("❌ DevSquad CLI: missing critical dependencies: " + ", ".join(missing), file=sys.stderr)
        print('   Fix: pip install -e ".[dev]"   (or: pip install ' + " ".join(missing) + ")", file=sys.stderr)
        print("   Note: running with the bare system Python is not recommended;", file=sys.stderr)
        print("   use the project virtual environment (venv/.venv).", file=sys.stderr)
        raise SystemExit(2)
