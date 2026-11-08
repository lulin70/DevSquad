"""Shared primitives for the deterministic UI/UX rule checks.

Holds the severity constants and the safe probe accessor used by every
pillar module in this package.
"""

from __future__ import annotations

from typing import Any

SEVERITY_ERROR = "critical"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"

# ── Helper: safe probe access ─────────────────────────────────────────────────


def _safe_get(probes: dict[str, Any], *keys: str, default: Any = None) -> Any:
    """Safely traverse nested dict, returning default if any key is missing."""
    current: Any = probes
    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key, default)
        if current is None:
            return default
    return current
