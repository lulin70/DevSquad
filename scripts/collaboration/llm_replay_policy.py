#!/usr/bin/env python3
"""LLM Replay Cache Policy (V4.6.0 P1-a).

Pure-policy module for the LLM replay cache — no I/O, fully unit-testable.
Inspired by tester-army/e2e's replay cache (docs/prd/V4.6.0_e2e-inspired-testing_PRD.md):
record a verified LLM response once, replay it without a model call on later
runs, and let any change to the prompt-producing code invalidate the recording.

Design invariants:
- OFF is the default: production behavior is byte-identical to V4.5.24.
- The replay key binds the DevSquad version and ``PROMPT_TEMPLATE_VERSION``,
  so any prompt-template or release change causes a miss (the "app changed"
  analog of tester-army's replay cache).
- An invalid mode value is fail-closed (raises) rather than silently degrading
  to OFF — a typo'd env var must not masquerade as a disabled cache.

Verification gating ("only save what a later check verified") lives at two
levels outside this module: the worker only caches successful backend
responses (existing behavior), and CI persists the cache directory only when
the e2e job passes (actions/cache post-step).
"""

from __future__ import annotations

import hashlib
import os
import re
from enum import StrEnum

from ._version import __version__

__all__ = [
    "PROMPT_TEMPLATE_VERSION",
    "REPLAY_ENV_VAR",
    "REPLAY_TTL_SECONDS",
    "ReplayMode",
    "ReplayPolicyError",
    "build_replay_key",
    "resolve_replay_mode",
]


class ReplayMode(StrEnum):
    """Replay cache operating mode.

    - ``OFF``: replay disabled (default) — existing cache behavior only.
    - ``READ``: serve hits from the replay cache; never write.
    - ``READ_WRITE``: serve hits and record verified responses.
    """

    OFF = "off"
    READ = "read"
    READ_WRITE = "read-write"


REPLAY_ENV_VAR = "DEVSQUAD_LLM_REPLAY_CACHE"

# Bump when any PromptAssembler template or role-prompt text changes. The key
# binds this constant, so a stale recording can never answer for a prompt the
# code no longer produces. Kept as a named constant (not derived from file
# hashes) so the invalidation decision is explicit and reviewable in diffs.
PROMPT_TEMPLATE_VERSION = "1"

# Replay entries must outlive any test cycle: a "read" run weeks later must
# still replay instead of silently expiring into a real model call. Ten years
# in seconds; TTL checks in LLMCache use this value when replay mode is on.
REPLAY_TTL_SECONDS = 315_360_000


class ReplayPolicyError(ValueError):
    """Raised when a replay mode value cannot be resolved (fail-closed)."""


# Per-dispatch metadata embedded in the assembled instruction. A fresh task id
# must not defeat replay (tester-army/e2e wraps such values in `unique()` for
# the same reason); the replay key strips these lines before hashing. Extend
# this pattern whenever a new volatile field enters PromptAssembler output.
_VOLATILE_LINE_PATTERNS = (re.compile(r"^\s*Task ID:\s*\S+.*$", re.MULTILINE),)


def _normalize_instruction(instruction: str) -> str:
    """Strip volatile per-dispatch metadata lines from an instruction."""
    for pattern in _VOLATILE_LINE_PATTERNS:
        instruction = pattern.sub("", instruction)
    return instruction


def resolve_replay_mode(explicit: ReplayMode | str | None = None) -> ReplayMode:
    """Resolve the active replay mode.

    Precedence: explicit argument > ``DEVSQUAD_LLM_REPLAY_CACHE`` env var >
    ``ReplayMode.OFF``. Invalid values raise ``ReplayPolicyError`` (fail-closed)
    instead of silently falling back to OFF.
    """
    raw = str(explicit).strip().lower() if explicit is not None else os.environ.get(REPLAY_ENV_VAR, "").strip().lower()
    if not raw:
        return ReplayMode.OFF
    try:
        return ReplayMode(raw)
    except ValueError as exc:
        valid = ", ".join(m.value for m in ReplayMode)
        raise ReplayPolicyError(
            f"{REPLAY_ENV_VAR if explicit is None else 'explicit replay mode'} must be one of: {valid}; got {raw!r}"
        ) from exc


def build_replay_key(instruction: str, backend: str, model: str) -> str:
    """Build the replay cache key (full SHA256, never truncated).

    Binds backend, model, the DevSquad release version, and
    ``PROMPT_TEMPLATE_VERSION`` so recordings cannot outlive the code that
    produced the prompt. Volatile per-dispatch metadata (``Task ID:``) is
    normalized away first — two dispatches of the same task must produce the
    same key regardless of their ids. Deliberately a different key space from
    the regular LLM cache (``replay-v1`` prefix) so the two cannot collide.
    """
    content = (
        f"replay-v1:{__version__}:ptv{PROMPT_TEMPLATE_VERSION}:{backend}:{model}:{_normalize_instruction(instruction)}"
    )
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
