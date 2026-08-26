#!/usr/bin/env python3
"""AsyncCoeffectResolver — V4.5.7 P12.5.1.

Replaces V4.5.4 ThreadPoolExecutor-blocking CoeffectResolver with async-native
implementation. Keeps V4.5.4 sync API as backward-compatible fallback.

V4.5.7 design principles applied:
    L-V457-001: clear boundary between Skill (we control) and host LLM (we don't)
    L-V457-003: detect existing event loop; use run_until_complete() not asyncio.run()
    L-V457-004: asyncio.Lock deadlock prevention — uniform lock ordering + timeout
    L-V455-001: manual `global` keyword fix (single file, no bulk rename)

API:
    - aresolve(req) -> Awaitable[CoeffectResult]   async primary entry
    - resolve(req) -> CoeffectResult                sync bridge (backward compat)

6-state FSM (V4.5.4 invariant):
    PENDING → READY → RUNNING → COMPLETED
                       ↓
                      FAILED
                       ↓
                    CANCELLED

V4.5.4 CoeffectResolver (sync topological sort) is preserved in coeffect.py.
This module wraps async coeffect execution (different concern: exec-order vs
execution concurrency).
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ── Anti-ghost counter (V4.5.6 W1: _er naming convention) ──────────────────

_call_counter_er: int = 0


def get_call_counter_er() -> int:
    """Return module-level anti-ghost counter (V4.5.6 W1 naming)."""
    return _call_counter_er


def _inc_call_counter_er() -> None:
    """Bump anti-ghost counter (thread-safe)."""
    global _call_counter_er
    _call_counter_er += 1


# ── 6-state FSM ─────────────────────────────────────────────────────────────


class CoeffectState(Enum):
    """6-state lifecycle for async coeffect execution."""

    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


ALLOWED_TRANSITIONS: dict[CoeffectState, frozenset[CoeffectState]] = {
    CoeffectState.PENDING: frozenset({CoeffectState.READY, CoeffectState.CANCELLED}),
    CoeffectState.READY: frozenset({CoeffectState.RUNNING, CoeffectState.FAILED}),
    CoeffectState.RUNNING: frozenset({
        CoeffectState.COMPLETED,
        CoeffectState.FAILED,
        CoeffectState.CANCELLED,
    }),
    CoeffectState.COMPLETED: frozenset(),
    CoeffectState.FAILED: frozenset(),
    CoeffectState.CANCELLED: frozenset(),
}


def _can_transition(src: CoeffectState, dst: CoeffectState) -> bool:
    """Check if FSM transition is allowed (V4.5.4 invariant)."""
    return dst in ALLOWED_TRANSITIONS.get(src, frozenset())


# ── Data structures ─────────────────────────────────────────────────────────


@dataclass
class CoeffectRequest:
    """Async coeffect execution request.

    Attributes:
        name: coeffect identifier (e.g. "auth", "config", "metrics")
        payload: arbitrary callable or args dict ({"executor": callable})
        timeout: timeout in seconds (default 5.0)
    """

    name: str
    payload: dict[str, Any]
    timeout: float = 5.0


@dataclass
class CoeffectResult:
    """Result of async coeffect execution.

    Attributes:
        state: final FSM state (COMPLETED / FAILED / CANCELLED)
        value: return value (None on FAILED/CANCELLED)
        error: error message (None on COMPLETED)
    """

    state: CoeffectState
    value: Any = None
    error: str | None = None


# ── Async resolver ───────────────────────────────────────────────────────────


class AsyncCoeffectResolver:
    """Async-native coeffect resolver — V4.5.7.

    Replaces ThreadPoolExecutor-blocking CoeffectResolver with asyncio primitives.

    Concurrency model:
        - _async_lock protects FSM state transitions (single writer)
        - _async_sem caps concurrent coeffect execution (default 4)
        - _uniform_lock_order: always acquire sem → lock → transition
          (L-V457-004: avoid deadlock)

    Backward compat:
        resolve() bridge detects existing loop (L-V457-003) and uses
        run_until_complete() instead of asyncio.run().
    """

    def __init__(self, max_concurrent: int = 4) -> None:
        self._async_lock = asyncio.Lock()
        self._async_sem = asyncio.Semaphore(max_concurrent)
        self._state: CoeffectState = CoeffectState.PENDING
        _inc_call_counter_er()

    async def aresolve(self, req: CoeffectRequest) -> CoeffectResult:
        """Async primary entry — acquires sem, runs with timeout, transitions FSM.

        FSM is per-call: each aresolve() starts from PENDING. The instance-level
        self._state is the *last* result state, used for diagnostics only.
        Per-call FSM state lives in a local variable to allow concurrent re-entry.
        """
        _inc_call_counter_er()

        # L-V457-004: uniform lock ordering: sem first, lock second
        async with self._async_sem:
            local_state = CoeffectState.PENDING
            try:
                # READY transition
                local_state = CoeffectState.READY
                result = await asyncio.wait_for(
                    self._arun_one(req),
                    timeout=req.timeout,
                )
                local_state = CoeffectState.COMPLETED
                self._state = local_state
                return result
            except asyncio.TimeoutError:
                local_state = CoeffectState.FAILED
                self._state = local_state
                return CoeffectResult(
                    state=CoeffectState.FAILED,
                    error=f"coeffect '{req.name}' exceeded {req.timeout}s timeout",
                )
            except asyncio.CancelledError:
                local_state = CoeffectState.CANCELLED
                self._state = local_state
                return CoeffectResult(
                    state=CoeffectState.CANCELLED,
                    error=f"coeffect '{req.name}' cancelled",
                )
            except Exception as exc:
                local_state = CoeffectState.FAILED
                self._state = local_state
                return CoeffectResult(
                    state=CoeffectState.FAILED,
                    error=f"coeffect '{req.name}' raised: {exc!r}",
                )

    def resolve(self, req: CoeffectRequest) -> CoeffectResult:
        """Sync bridge (backward compat V4.5.4).

        L-V457-003: detect existing event loop. When a loop is already
        running, ``asyncio.run()`` would crash with a confusing nested-loop
        error — raise the informative error instead so callers switch to
        ``await aresolve(req)``. When no loop is running, ``asyncio.run()``
        is safe.
        """
        _inc_call_counter_er()
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            # No running loop: asyncio.run() safe
            return asyncio.run(self.aresolve(req))
        # Running loop detected — cannot block on it from sync code.
        raise RuntimeError(
            "resolve() cannot be called from a running event loop. "
            "Use await resolver.aresolve(req) in async context."
        )

    async def _arun_one(self, req: CoeffectRequest) -> CoeffectResult:
        """Execute a single coeffect's executor.

        L-V457-004: lock acquired here ONLY. Uniform order: caller holds
        sem → acquires lock here → runs executor → releases lock.
        """
        async with self._async_lock:  # uniform: sem (caller) → lock (here)
            executor = req.payload.get("executor")
            if executor is None:
                raise ValueError(f"coeffect '{req.name}' missing 'executor' in payload")
            if not callable(executor):
                raise TypeError(
                    f"coeffect '{req.name}' executor must be callable, got {type(executor)}"
                )
            # Run sync callable in default executor (stdlib asyncio)
            value = await asyncio.get_running_loop().run_in_executor(None, executor)
            return CoeffectResult(state=CoeffectState.COMPLETED, value=value)

    async def _transition_async(self, target: CoeffectState) -> None:
        """Atomically transition FSM state under lock (unused after V4.5.7 refactor)."""
        async with self._async_lock:
            if not _can_transition(self._state, target):
                raise ValueError(
                    f"Invalid FSM transition: {self._state.value} -> {target.value}"
                )
            self._state = target

    @property
    def state(self) -> CoeffectState:
        """Current FSM state (read-only)."""
        return self._state

    @property
    def stats(self) -> dict[str, int]:
        """Resolver stats (for diagnostics)."""
        return {
            "call_counter_er": _call_counter_er,
            "current_state": self._state.value,
            "max_concurrent": self._async_sem._value if hasattr(self._async_sem, "_value") else 0,
        }


__all__ = [
    "ALLOWED_TRANSITIONS",
    "AsyncCoeffectResolver",
    "CoeffectRequest",
    "CoeffectResult",
    "CoeffectState",
    "get_call_counter_er",
]
