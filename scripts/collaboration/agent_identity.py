#!/usr/bin/env python3
"""
AgentIdentity — Deterministic agent identity for cross-session tracking.

Inspired by block/buzz's agent identity model (secp256k1 keypair + NIP-05
handle). DevSquad uses a simpler deterministic hash: same (role, backend,
model) configuration produces the same ``agent_id`` across sessions.

This enables answering: "which AI instance made this decision 3 weeks ago?"
without storing any PII or reversible identity.

Anti-ghost: module-level ``_call_counter`` increments on every public method
call, verifiable via the read-only ``_call_counter`` property.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

__all__ = ["AgentIdentity", "derive_agent_id"]

logger = __import__("logging").getLogger(__name__)

# Anti-ghost call counter (module-level, incremented by every public method).
_call_counter: int = 0


def derive_agent_id(role_id: str, backend: str, model: str) -> str:
    """Derive a deterministic agent_id from (role, backend, model).

    Format: ``agent-{role}-{sha256(role:backend:model)[:8]}``

    Parameters
    ----------
    role_id:
        Role identifier (e.g. "architect").
    backend:
        Backend name (e.g. "mock", "openai", "anthropic").
    model:
        Model name (e.g. "gpt-4", "claude-3", "mock").

    Returns
    -------
    str
        Deterministic agent_id, e.g. "agent-architect-a1b2c3d4".
    """
    global _call_counter
    _call_counter += 1

    if not role_id:
        raise ValueError("role_id must not be empty")

    # Normalize None to "unknown" for robust hashing.
    backend = backend or "unknown"
    model = model or "unknown"

    raw = f"{role_id}:{backend}:{model}"
    short_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:8]
    return f"agent-{role_id}-{short_hash}"


@dataclass(frozen=True)
class AgentIdentity:
    """Deterministic agent identity derived from (role, backend, model).

    Same configuration → same ``agent_id`` across sessions.
    Enables cross-session agent behavior tracking via
    :meth:`DispatchAuditLogger.query_by_agent`.

    Attributes
    ----------
    agent_id:
        Deterministic ID, e.g. "agent-architect-a1b2c3d4".
    role_id:
        Role identifier (e.g. "architect").
    backend:
        Backend name (e.g. "mock", "openai").
    model:
        Model name (e.g. "gpt-4", "mock").
    """

    agent_id: str
    role_id: str
    backend: str
    model: str

    @classmethod
    def create(
        cls,
        role_id: str,
        backend: str = "mock",
        model: str = "mock",
    ) -> AgentIdentity:
        """Create a deterministic AgentIdentity.

        Parameters
        ----------
        role_id:
            Role identifier (e.g. "architect").
        backend:
            Backend name. Defaults to "mock".
        model:
            Model name. Defaults to "mock".

        Returns
        -------
        AgentIdentity
            Frozen dataclass with deterministic agent_id.
        """
        aid = derive_agent_id(role_id, backend, model)
        return cls(
            agent_id=aid,
            role_id=role_id,
            backend=backend or "unknown",
            model=model or "unknown",
        )

    @property
    def _call_counter(self) -> int:
        """Read-only access to the module-level call counter (anti-ghost)."""
        return _call_counter
