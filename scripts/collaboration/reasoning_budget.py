"""Reasoning-model token-budget resolution (V4.5.20 follow-up).

Extracted from ``constants.py``: that module is documented as a magic-number
table, while the model-marker table and the precedence logic below are real
behaviour. Numeric defaults/env name still live in ``.constants`` so there is a
single source of truth and no shadow copy.

Why this exists: reasoning models (observed: ``deepseek-flash``) emit their
chain of thought in ``reasoning_content``, but those tokens still count against
``max_tokens``. The generic 4096 default starves long-reasoning prompts (code
review / diff analysis), so such models get a larger budget by default.
"""

from .constants import (
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_MAX_TOKENS_REASONING,
    DEVSQUAD_REASONING_MAX_TOKENS_ENV,
)

# Explicit substring markers for models whose reasoning tokens count against
# max_tokens (observed case: deepseek-flash). Deliberately a plain list, not a
# clever heuristic.
REASONING_MODEL_MARKERS: tuple[str, ...] = (
    "deepseek-flash",
    "reasoner",
    "reasoning",
    "-r1",
    "thinking",
)


def is_reasoning_model(model: str | None) -> bool:
    """Return True when *model* matches a reasoning-model marker (table-tested)."""
    if not model:
        return False
    lowered = model.lower()
    return any(marker in lowered for marker in REASONING_MODEL_MARKERS)


def resolve_max_tokens(model: str | None, explicit: int | None = None) -> int:
    """Resolve the effective ``max_tokens`` budget (single precedence point).

    Precedence: explicit argument > ``DEVSQUAD_REASONING_MAX_TOKENS`` env override
    > per-model reasoning budget > ``DEFAULT_LLM_MAX_TOKENS``.
    """
    if explicit is not None:
        return explicit
    import os

    override = os.environ.get(DEVSQUAD_REASONING_MAX_TOKENS_ENV)
    if override:
        try:
            return int(override)
        except ValueError:
            pass
    if is_reasoning_model(model):
        return DEFAULT_LLM_MAX_TOKENS_REASONING
    return DEFAULT_LLM_MAX_TOKENS
