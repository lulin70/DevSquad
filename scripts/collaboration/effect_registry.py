#!/usr/bin/env python3
"""EffectRegistry — V4.5.3 P12.2.4.

LIFO stack of applied effects. On dispatch failure, ``revert_all()`` rolls
back effects in reverse order (most recent first). Recoverable: revert
failures do not block subsequent reverts.

Anti-ghost: ``_call_counter`` exposed via ``get_call_count()``.
"""

from __future__ import annotations

import threading

from scripts.collaboration.dispatch_effect import (
    DispatchEffect,
    EffectContext,
    EffectOutcome,
)

_call_counter: int = 0
_call_counter_lock = threading.Lock()


def _inc_call_counter() -> None:
    global _call_counter
    with _call_counter_lock:
        _call_counter += 1


def get_call_count() -> int:
    """Return current anti-ghost counter value."""
    with _call_counter_lock:
        return _call_counter


class EffectRegistryError(Exception):
    """Raised on registry operation failures."""


class EffectRegistry:
    """LIFO registry of applied effects.

    Thread-safe. Revert semantics:
        - LIFO order (most recent first)
        - Idempotent (effects must be idempotent themselves)
        - Best-effort (revert failures logged, do not raise)
    """

    def __init__(self) -> None:
        self._stack: list[tuple[DispatchEffect, EffectContext]] = []
        self._lock = threading.Lock()
        _inc_call_counter()

    def pending_count(self) -> int:
        """Return number of un-reverted effects."""
        _inc_call_counter()
        with self._lock:
            return len(self._stack)

    def apply(self, effect: DispatchEffect, ctx: EffectContext) -> EffectOutcome:
        """Apply effect and push to LIFO stack.

        Args:
            effect: DispatchEffect implementation.
            ctx: EffectContext (effect_id + payload).

        Returns:
            EffectOutcome from the effect's apply(). On success, the effect
            is appended to the stack.
        """
        _inc_call_counter()
        outcome = effect.apply(ctx)
        if outcome.success:
            with self._lock:
                self._stack.append((effect, ctx))
        return outcome

    def revert_last(self) -> EffectOutcome | None:
        """Revert and pop the most recent effect.

        Returns:
            EffectOutcome, or None if the stack is empty.
        """
        _inc_call_counter()
        with self._lock:
            if not self._stack:
                return None
            effect, ctx = self._stack.pop()
        # Revert outside lock (effects may do I/O)
        return effect.revert(ctx)

    def revert_all(self) -> list[EffectOutcome]:
        """Revert all effects in LIFO order.

        Each revert failure is captured in the returned list but does not
        block subsequent reverts.

        Returns:
            List of EffectOutcome (one per applied effect, in LIFO order).
        """
        _inc_call_counter()
        outcomes: list[EffectOutcome] = []
        with self._lock:
            stack_copy = list(reversed(self._stack))
            self._stack.clear()
        for effect, ctx in stack_copy:
            try:
                outcome = effect.revert(ctx)
            except Exception as exc:  # effects should not raise, but be defensive
                outcome = EffectOutcome(success=False, error=str(exc))
            outcomes.append(outcome)
        return outcomes

    def clear(self) -> None:
        """Remove all effects from stack without reverting.

        Use with caution — typically called after explicit revert_all().
        """
        _inc_call_counter()
        with self._lock:
            self._stack.clear()
