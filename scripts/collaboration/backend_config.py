#!/usr/bin/env python3
"""Backend config — persistent LLM backend selection (P12.1.5).

Reads/writes ``~/.devsquad/config.yaml`` to allow users to set their
preferred LLM backend without exporting environment variables.

Priority order (highest first):
    1. Explicit CLI kwargs (create_backend("moka", api_key=...))
    2. Project config: ``./.devsquad/config.yaml`` (if --project)
    3. User config: ``~/.devsquad/config.yaml``
    4. Environment variable: ``DEVSQUAD_LLM_BACKEND``
    5. Default: ``"auto"``

Usage from Python:
    from scripts.collaboration.backend_config import (
        load_backend_config,
        save_backend_config,
    )
    cfg = load_backend_config()  # {"backend": "moka", "model": "moka-gpt-5.5"}
    save_backend_config({"backend": "openai"})

Usage from CLI:
    devsquad backend set moka
    devsquad backend get
    devsquad backend list
"""

from __future__ import annotations

import os
from typing import Any

# V4.5.2 P12.1.5: Whitelist of valid backend names
VALID_BACKENDS = {
    "auto",
    "auto-fallback",
    "mock",
    "host",
    "trae",
    "openai",
    "anthropic",
    "moka",
    "fallback",
}

# Schema for the config file
CONFIG_SCHEMA_VERSION = 1


def _user_config_path() -> str:
    """Return the path to the user's config file (~/.devsquad/config.yaml)."""
    home = os.path.expanduser("~")
    return os.path.join(home, ".devsquad", "config.yaml")


def _project_config_path() -> str:
    """Return the path to the project config file (./.devsquad/config.yaml)."""
    return os.path.join(".devsquad", "config.yaml")


def _parse_yaml_simple(content: str) -> dict[str, Any]:
    """Parse a minimal subset of YAML (key: value pairs) without external deps.

    Supports:
        - key: value
        - key: "quoted value"
        - # comments
        - blank lines

    Returns:
        Dict of key-value pairs.
    """
    result: dict[str, Any] = {}
    for line in content.splitlines():
        line = line.split("#", 1)[0].strip()  # strip comments + whitespace
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip surrounding quotes
        if value.startswith('"') and value.endswith('"') or value.startswith("'") and value.endswith("'"):
            value = value[1:-1]
        result[key] = value
    return result


def _format_yaml_simple(data: dict[str, Any]) -> str:
    """Serialize a dict to minimal YAML format.

    Args:
        data: Dict of scalar key-value pairs.

    Returns:
        YAML-formatted string with header.
    """
    lines = [
        "# DevSquad user config",
        f"# schema_version: {CONFIG_SCHEMA_VERSION}",
        "",
    ]
    for key, value in data.items():
        # Quote values that contain special characters
        if isinstance(value, str) and (":" in value or "#" in value):
            lines.append(f'{key}: "{value}"')
        else:
            lines.append(f"{key}: {value}")
    return "\n".join(lines) + "\n"


def load_backend_config(project: bool = False) -> dict[str, Any]:
    """Load backend configuration.

    Priority:
        1. Project config (if project=True)
        2. User config (~/.devsquad/config.yaml)

    Args:
        project: If True, prefer project-level config.

    Returns:
        Dict with at least {"backend": str}; empty dict if no config.
    """
    paths_to_try = []
    if project:
        paths_to_try.append(_project_config_path())
    paths_to_try.append(_user_config_path())

    for path in paths_to_try:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            parsed = _parse_yaml_simple(content)
            if parsed:
                _inc_call_counter()
                return parsed
        except OSError:
            continue
    return {}


def save_backend_config(
    data: dict[str, Any],
    project: bool = False,
) -> str:
    """Save backend configuration.

    Args:
        data: Dict of config key-value pairs. Must include 'backend'.
        project: If True, save to project config; else user config.

    Returns:
        Path where config was saved.

    Raises:
        ValueError: If 'backend' is missing or invalid.
    """
    if "backend" not in data:
        raise ValueError("Config must contain 'backend' key")
    backend = data["backend"]
    if backend not in VALID_BACKENDS:
        raise ValueError(
            f"Invalid backend '{backend}'. Valid: {sorted(VALID_BACKENDS)}"
        )

    path = _project_config_path() if project else _user_config_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)

    # Read existing config and merge
    existing: dict[str, Any] = {}
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                existing = _parse_yaml_simple(f.read())
        except OSError:
            existing = {}

    merged = {**existing, **data}
    with open(path, "w", encoding="utf-8") as f:
        f.write(_format_yaml_simple(merged))
    return path


def resolve_backend(prefer_project: bool = False) -> str:
    """Resolve the effective backend using full priority order.

    Priority:
        1. Project config (if prefer_project=True and exists)
        2. User config
        3. ``DEVSQUAD_LLM_BACKEND`` environment variable
        4. Default: ``"auto"``

    Args:
        prefer_project: If True, check project config first.

    Returns:
        The resolved backend name (always in VALID_BACKENDS).
    """
    if prefer_project:
        cfg = load_backend_config(project=True)
        backend = cfg.get("backend")
        if isinstance(backend, str) and backend in VALID_BACKENDS:
            return backend

    cfg = load_backend_config(project=False)
    backend = cfg.get("backend")
    if isinstance(backend, str) and backend in VALID_BACKENDS:
        return backend

    env_backend = os.environ.get("DEVSQUAD_LLM_BACKEND", "").strip()
    if env_backend in VALID_BACKENDS:
        _inc_call_counter()
        return env_backend

    _inc_call_counter()
    return "auto"


def get_resolved_backend(prefer_project: bool = False) -> str:
    """Public alias for resolve_backend (used by cli_backend)."""
    return resolve_backend(prefer_project=prefer_project)


# Anti-Ghost counter (P12.1.5): for CI gate
_call_counter: int = 0


def get_call_count() -> int:
    """Return the call counter (for anti-ghost CI gate)."""
    return _call_counter


def _inc_call_counter() -> None:
    global _call_counter
    _call_counter += 1
