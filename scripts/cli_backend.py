#!/usr/bin/env python3
"""devsquad backend — manage LLM backend selection (P12.1.5).

Subcommands:
    set <provider>      Write backend to ~/.devsquad/config.yaml
    get                 Print current effective backend
    list                List all valid backends + current selection

Examples:
    devsquad backend set moka
    devsquad backend get
    devsquad backend list
    devsquad backend set openai --project
"""

from __future__ import annotations

from typing import Any

from scripts.collaboration.backend_config import (
    VALID_BACKENDS,
    _inc_call_counter,
    resolve_backend,
    save_backend_config,
)


def cmd_backend_set(args: Any) -> int:
    """Set the backend and persist to config file.

    Args:
        args: argparse Namespace with `provider` and `project` attributes.

    Returns:
        Exit code (0 on success).
    """
    _inc_call_counter()
    provider = args.provider
    project = getattr(args, "project", False)

    if provider not in VALID_BACKENDS:
        print(f"Error: Invalid backend '{provider}'")
        print(f"Valid backends: {', '.join(sorted(VALID_BACKENDS))}")
        return 1

    config_data = {"backend": provider}
    # Optional model override
    if hasattr(args, "model") and args.model:
        config_data["model"] = args.model

    path = save_backend_config(config_data, project=project)
    scope = "project" if project else "user"
    print(f"Backend set to '{provider}' in {scope} config: {path}")
    return 0


def cmd_backend_get(args: Any) -> int:
    """Print current effective backend.

    Args:
        args: argparse Namespace (unused, reserved for future flags).

    Returns:
        Exit code (0).
    """
    _inc_call_counter()
    project = getattr(args, "project", False)
    backend = resolve_backend(prefer_project=project)
    print(f"Current backend: {backend}")
    return 0


def cmd_backend_list(args: Any) -> int:
    """List all valid backends + current selection.

    Args:
        args: argparse Namespace (unused).

    Returns:
        Exit code (0).
    """
    _inc_call_counter()
    current = resolve_backend()
    print("Available LLM backends:")
    for backend in sorted(VALID_BACKENDS):
        marker = " *" if backend == current else "  "
        print(f" {marker} {backend}")
    print(f"\nCurrent: {current}")
    return 0


def cmd_backend(args: Any) -> int:
    """Dispatch to subcommand handler.

    Args:
        args: argparse Namespace with `backend_command` attribute.

    Returns:
        Exit code from subcommand.
    """
    sub = getattr(args, "backend_command", None)
    if sub == "set":
        return cmd_backend_set(args)
    elif sub == "get":
        return cmd_backend_get(args)
    elif sub == "list":
        return cmd_backend_list(args)
    else:
        print(f"Error: Unknown backend subcommand: {sub}")
        print("Valid: set, get, list")
        return 1
