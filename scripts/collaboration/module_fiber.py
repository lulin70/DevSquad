#!/usr/bin/env python3
"""ModuleFiber — V4.5.4 P12.3.1 — Module lifecycle state machine.

Lifecycle states for a single DevSquad enhancement module.
Replaces implicit "init success = active" with explicit state tracking.

V4.5.3 lesson #1 applied: __slots__ + __init__ 双修改.
V4.5.3 lesson #4 applied: get_call_counter_er naming (统一 _er 后缀).
"""

from __future__ import annotations

import enum
import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


# ── Anti-ghost counter (V4.5.3 lesson #4: get_call_counter_er naming) ─────

_call_counter_er: int = 0
_call_counter_lock = threading.Lock()


def _inc_call_counter_er() -> None:
    global _call_counter_er
    with _call_counter_lock:
        _call_counter_er += 1


def get_call_counter_er() -> int:
    """Return current anti-ghost counter (V4.5.4 unified naming)."""
    with _call_counter_lock:
        return _call_counter_er


# ── State machine ──────────────────────────────────────────────────────────


class FiberState(str, enum.Enum):
    """Module lifecycle states (V4.5.4 P12.3.1).

    6 states total:
    - INACTIVE: not yet activated
    - ACTIVATING: in the process of activating
    - ACTIVE: fully activated, ready to use
    - DEACTIVATING: in the process of deactivating
    - FAILED: activation failed; can be retried
    - DEGRADED: partial activation; usable but with reduced capability
    """

    INACTIVE = "inactive"
    ACTIVATING = "activating"
    ACTIVE = "active"
    DEACTIVATING = "deactivating"
    FAILED = "failed"
    DEGRADED = "degraded"


# Allowed state transitions: FSM contract
ALLOWED_TRANSITIONS: dict[FiberState, set[FiberState]] = {
    FiberState.INACTIVE: {FiberState.ACTIVATING},
    FiberState.ACTIVATING: {FiberState.ACTIVE, FiberState.FAILED, FiberState.DEGRADED},
    FiberState.ACTIVE: {FiberState.DEACTIVATING, FiberState.DEGRADED},
    FiberState.DEACTIVATING: {FiberState.INACTIVE, FiberState.FAILED},
    FiberState.FAILED: {FiberState.ACTIVATING, FiberState.INACTIVE},
    FiberState.DEGRADED: {FiberState.ACTIVE, FiberState.INACTIVE},
}


class ModuleFiber:
    """Lifecycle state machine for a single module (V4.5.4 P12.3.1).

    V4.5.3 lesson #1: __slots__ classes MUST add new fields to BOTH
    __slots__ tuple and __init__ together.

    Note: Manual __init__ instead of @dataclass(slots=True) for cross-version
    compat. Production code in DevSQuad (3.10+) can use @dataclass(slots=True).
    """

    __slots__ = (
        "module_id",
        "state",
        "depends_on",
        "last_error",
        "retry_count",
        "activated_at",
        "transition_history",
    )

    def __init__(
        self,
        module_id: str,
        state: FiberState = FiberState.INACTIVE,
        depends_on: tuple[str, ...] = (),
        last_error: str | None = None,
        retry_count: int = 0,
        activated_at: float | None = None,
        transition_history: list[dict[str, Any]] | None = None,
    ) -> None:
        self.module_id = module_id
        self.state = state
        self.depends_on = depends_on
        self.last_error = last_error
        self.retry_count = retry_count
        self.activated_at = activated_at
        self.transition_history = (
            transition_history if transition_history is not None else []
        )

    def transition(self, target: FiberState, *, reason: str = "") -> bool:
        """FSM transition. Returns True on success, False on invalid transition.

        On entry to ACTIVE: clears last_error and sets activated_at.
        On entry to FAILED: increments retry_count.
        """
        allowed = ALLOWED_TRANSITIONS.get(self.state, set())
        if target not in allowed:
            logger.warning(
                "Fiber %s: invalid transition %s -> %s (%s)",
                self.module_id,
                self.state.value,
                target.value,
                reason,
            )
            return False
        prev = self.state
        self.state = target
        self.transition_history.append(
            {
                "from": prev.value,
                "to": target.value,
                "reason": reason,
                "ts": time.time(),
            }
        )
        if target == FiberState.ACTIVE:
            self.activated_at = time.time()
            self.last_error = None
        elif target == FiberState.FAILED:
            self.retry_count += 1
        _inc_call_counter_er()
        return True

    def is_usable(self) -> bool:
        """A fiber is usable if ACTIVE or DEGRADED."""
        return self.state in (FiberState.ACTIVE, FiberState.DEGRADED)


class ModuleFiberRegistry:
    """Thread-safe registry of all ModuleFiber instances in the dispatcher."""

    def __init__(self) -> None:
        self._fibers: dict[str, ModuleFiber] = {}
        self._lock = threading.Lock()
        _inc_call_counter_er()

    def register(
        self,
        module_id: str,
        *,
        depends_on: tuple[str, ...] = (),
    ) -> ModuleFiber:
        """Register a new module fiber. Idempotent for same module_id."""
        with self._lock:
            if module_id not in self._fibers:
                self._fibers[module_id] = ModuleFiber(
                    module_id=module_id,
                    depends_on=depends_on,
                )
            return self._fibers[module_id]

    def get(self, module_id: str) -> ModuleFiber | None:
        with self._lock:
            return self._fibers.get(module_id)

    def all_fibers(self) -> list[ModuleFiber]:
        with self._lock:
            return list(self._fibers.values())

    def transition(
        self,
        module_id: str,
        target: FiberState,
        *,
        reason: str = "",
    ) -> bool:
        with self._lock:
            fiber = self._fibers.get(module_id)
            if fiber is None:
                return False
            return fiber.transition(target, reason=reason)
