#!/usr/bin/env python3
"""Dispatcher Transaction (V4.5.5 P4-P5 Wave 2 main feature).

5-state FSM for module dependency graph transaction boundary:
    PENDING → ACTIVE → COMMITTED (terminal)
                    ↘ ROLLED_BACK → ACTIVE (retry)
                    ↘ FAILED (terminal, unrecoverable)

设计原则:
- V4.5.3 lesson #1: __slots__ + __init__ 双管齐下
- V4.5.3 lesson #4: _call_counter_er 命名统一
- V4.5.3 lesson #5: 跨模块私有状态用 public method
- V4.5.3 lesson #7: best-effort try/except (revert 失败不阻塞 fail)
- V4.5.3 lesson #8: global state + lock pattern
- V4.5.3 lesson #9: LIFO revert order
- V4.5.4 lesson #1: 装饰器零侵入 (ModuleFiber 复用模式)
- V4.5.4 lesson #2: ALLOWED_TRANSITIONS 表驱动 FSM

Anti-Ghost: _tx_call_counter_er 递增 on begin/commit/rollback/retry。
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections.abc import Callable
from contextlib import contextmanager, suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anti-Ghost counter (V4.5.3 lesson #4 naming unified)
# ---------------------------------------------------------------------------
_tx_call_counter_er: int = 0
_tx_call_counter_lock = threading.Lock()


def _inc_call_counter_er() -> None:
    """Increment DispatcherTransaction activation counter (thread-safe)."""
    global _tx_call_counter_er
    with _tx_call_counter_lock:
        _tx_call_counter_er += 1


def get_call_counter_er() -> int:
    """Return activation counter for Anti-Ghost verification."""
    return _tx_call_counter_er


# ---------------------------------------------------------------------------
# State Machine
# ---------------------------------------------------------------------------


class TxState(str, Enum):
    """5-state transaction FSM."""

    PENDING = "PENDING"          # declared, not started
    ACTIVE = "ACTIVE"            # executing modules
    COMMITTED = "COMMITTED"      # all success (terminal)
    ROLLED_BACK = "ROLLED_BACK"  # failure reverted (retryable)
    FAILED = "FAILED"            # unrecoverable (terminal)


# V4.5.4 lesson #2: ALLOWED_TRANSITIONS 表驱动
ALLOWED_TRANSITIONS: dict[TxState, frozenset[TxState]] = {
    TxState.PENDING: frozenset({TxState.ACTIVE, TxState.FAILED}),
    TxState.ACTIVE: frozenset({TxState.COMMITTED, TxState.ROLLED_BACK, TxState.FAILED}),
    TxState.COMMITTED: frozenset(),  # terminal
    TxState.ROLLED_BACK: frozenset({TxState.ACTIVE, TxState.FAILED}),  # retry
    TxState.FAILED: frozenset(),  # terminal
}


class TxStateError(RuntimeError):
    """Raised on invalid FSM transition."""


def _validate_transition(from_state: TxState, to_state: TxState) -> None:
    """Validate FSM transition; raise TxStateError if not allowed."""
    if to_state not in ALLOWED_TRANSITIONS[from_state]:
        raise TxStateError(
            f"invalid transaction transition: {from_state.value} → {to_state.value}"
        )


# ---------------------------------------------------------------------------
# Module Wrapper
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class TxModule:
    """Single module's transaction wrapper (V4.5.3 lesson #1)."""

    name: str
    enter_fn: Callable[[], None]
    revert_fn: Callable[[], None]
    entered: bool = False
    reverted: bool = False


# ---------------------------------------------------------------------------
# Transaction
# ---------------------------------------------------------------------------


class DispatchTransaction:
    """Module dependency graph transaction boundary.

    Lifecycle:
        PENDING → register modules → begin() → ACTIVE
        ACTIVE → commit() → COMMITTED
        ACTIVE → rollback() → ROLLED_BACK (LIFO revert)
        ACTIVE → fail() → FAILED (unrecoverable)
        ROLLED_BACK → retry() → ACTIVE (re-execute)
    """

    __slots__ = (
        "_tx_id",
        "_state",
        "_modules",
        "_modules_lock",
        "_entered_count",
        "_created_at",
        "_commit_at",
        "_rollback_at",
        "_failed_reason",
    )

    def __init__(self, tx_id: str | None = None) -> None:
        _inc_call_counter_er()
        self._tx_id = tx_id or self._generate_tx_id()
        self._state: TxState = TxState.PENDING
        self._modules: list[TxModule] = []
        self._modules_lock = threading.Lock()
        self._entered_count: int = 0
        self._created_at: str = datetime.now(timezone.utc).isoformat()
        self._commit_at: str | None = None
        self._rollback_at: str | None = None
        self._failed_reason: str | None = None

    @staticmethod
    def _generate_tx_id() -> str:
        """Generate unique transaction ID."""
        short_uuid = uuid.uuid4().hex[:12]
        return f"tx_{short_uuid}"

    # ---- public properties ----

    @property
    def state(self) -> TxState:
        return self._state

    @property
    def tx_id(self) -> str:
        return self._tx_id

    @property
    def modules(self) -> list[str]:
        """Snapshot of registered module names (thread-safe copy)."""
        with self._modules_lock:
            return [m.name for m in self._modules]

    @property
    def entered_count(self) -> int:
        return self._entered_count

    @property
    def failed_reason(self) -> str | None:
        return self._failed_reason

    @failed_reason.setter
    def failed_reason(self, value: str | None) -> None:
        self._failed_reason = value

    # ---- public API ----

    def register_module(
        self,
        name: str,
        enter_fn: Callable[[], None],
        revert_fn: Callable[[], None],
    ) -> None:
        """Register a module (PENDING or ROLLED_BACK state).

        Args:
            name: Module identifier (for logging + debugging).
            enter_fn: Called during begin() in registration order.
            revert_fn: Called during rollback() in reverse order (LIFO).

        Raises:
            TxStateError: If state doesn't allow registration.
        """
        with self._modules_lock:
            if self._state not in (TxState.PENDING, TxState.ROLLED_BACK):
                raise TxStateError(
                    f"cannot register in state {self._state.value}"
                )
            self._modules.append(
                TxModule(name=name, enter_fn=enter_fn, revert_fn=revert_fn)
            )
            logger.debug(
                "tx %s: registered module %s (total=%d)",
                self._tx_id, name, len(self._modules),
            )

    def begin(self) -> None:
        """PENDING/ROLLED_BACK → ACTIVE: execute all modules in order.

        Raises:
            TxStateError: If state doesn't allow begin.
            RuntimeError: If a module's enter_fn fails (triggers auto-rollback).
        """
        _validate_transition(self._state, TxState.ACTIVE)
        if self._state == TxState.ROLLED_BACK:
            # Retry: reset entered/reverted flags
            with self._modules_lock:
                for m in self._modules:
                    m.entered = False
                    m.reverted = False
                self._entered_count = 0

        prev_state = self._state
        self._state = TxState.ACTIVE
        logger.info("tx %s: BEGIN (%s → ACTIVE)", self._tx_id, prev_state.value)

        # Execute modules in registration order (V4.5.3 lesson #9 LIFO inverse)
        with self._modules_lock:
            modules_snapshot = list(self._modules)
        for module in modules_snapshot:
            try:
                module.enter_fn()
                module.entered = True
                self._entered_count += 1
                logger.debug("tx %s: entered %s", self._tx_id, module.name)
            except Exception as exc:
                logger.error(
                    "tx %s: enter %s failed: %s",
                    self._tx_id, module.name, exc,
                )
                self.failed_reason = f"{module.name}: {exc}"
                self.rollback()
                raise

    def commit(self) -> None:
        """ACTIVE → COMMITTED: terminal success."""
        _validate_transition(self._state, TxState.COMMITTED)
        self._state = TxState.COMMITTED
        self._commit_at = datetime.now(timezone.utc).isoformat()
        logger.info(
            "tx %s: COMMIT (%d modules committed)",
            self._tx_id, self._entered_count,
        )

    def rollback(self) -> None:
        """ACTIVE → ROLLED_BACK: revert all entered modules in LIFO order.

        V4.5.3 lesson #9: LIFO revert (last entered first reverted).
        V4.5.3 lesson #7: best-effort — revert failures don't block overall rollback.
        """
        _validate_transition(self._state, TxState.ROLLED_BACK)
        logger.info("tx %s: ROLLBACK (LIFO)", self._tx_id)

        # LIFO revert: walk modules in reverse, only revert those that entered
        with self._modules_lock:
            modules_snapshot = list(reversed(self._modules))

        for module in modules_snapshot:
            if not module.entered or module.reverted:
                continue
            try:
                module.revert_fn()
                module.reverted = True
                logger.debug("tx %s: reverted %s", self._tx_id, module.name)
            except Exception as exc:
                # V4.5.3 lesson #7: best-effort, don't block
                logger.error(
                    "tx %s: revert %s failed (best-effort): %s",
                    self._tx_id, module.name, exc,
                )
                # Mark as reverted even on failure to avoid double-revert
                module.reverted = True

        self._state = TxState.ROLLED_BACK
        self._rollback_at = datetime.now(timezone.utc).isoformat()

    def fail(self, reason: str) -> None:
        """Any state → FAILED (unrecoverable, terminal)."""
        with suppress(TxStateError):
            _validate_transition(self._state, TxState.FAILED)
        self._state = TxState.FAILED
        self._failed_reason = reason
        logger.error("tx %s: FAILED (%s)", self._tx_id, reason)

    def retry(self) -> None:
        """ROLLED_BACK → ACTIVE: re-execute modules."""
        _validate_transition(self._state, TxState.ACTIVE)
        # begin() handles the actual re-execution
        self.begin()

    def to_dict(self) -> dict[str, Any]:
        """Serialize transaction state (for logging/telemetry)."""
        return {
            "tx_id": self._tx_id,
            "state": self._state.value,
            "modules": self.modules,
            "entered_count": self._entered_count,
            "created_at": self._created_at,
            "commit_at": self._commit_at,
            "rollback_at": self._rollback_at,
            "failed_reason": self._failed_reason,
        }


# ---------------------------------------------------------------------------
# Registry (thread-safe)
# ---------------------------------------------------------------------------


class TransactionRegistry:
    """Thread-safe transaction registry."""

    __slots__ = ("_txs", "_lock")

    def __init__(self) -> None:
        _inc_call_counter_er()
        self._txs: dict[str, DispatchTransaction] = {}
        self._lock = threading.Lock()

    def create_tx(self, tx_id: str | None = None) -> DispatchTransaction:
        """Create and register a new transaction."""
        tx = DispatchTransaction(tx_id=tx_id)
        with self._lock:
            self._txs[tx.tx_id] = tx
        return tx

    def get_tx(self, tx_id: str) -> DispatchTransaction | None:
        """Look up transaction by ID."""
        with self._lock:
            return self._txs.get(tx_id)

    def remove_tx(self, tx_id: str) -> bool:
        """Remove transaction (after COMMIT/FAILED). Returns True if removed."""
        with self._lock:
            return self._txs.pop(tx_id, None) is not None

    def active_count(self) -> int:
        """Count active transactions (for metric).

        Active = PENDING or ACTIVE (i.e., not yet terminal).
        """
        with self._lock:
            return sum(
                1 for tx in self._txs.values()
                if tx.state in (TxState.PENDING, TxState.ACTIVE)
            )

    def list_active(self) -> list[str]:
        """Snapshot of active transaction IDs."""
        with self._lock:
            return [
                tx.tx_id for tx in self._txs.values()
                if tx.state in (TxState.PENDING, TxState.ACTIVE)
            ]


# ---------------------------------------------------------------------------
# Context Manager (V4.5.3 lesson #9 LIFO revert on exception)
# ---------------------------------------------------------------------------


@contextmanager
def transaction_context(
    registry: TransactionRegistry,
    tx_id: str | None = None,
) -> Any:
    """Auto-commit on success, auto-rollback on exception.

    Usage:
        with transaction_context(registry) as tx:
            tx.register_module("a", enter, revert)
            tx.register_module("b", enter, revert)
            tx.begin()
            # ... if exception → auto rollback; else → auto commit
    """
    tx = registry.create_tx(tx_id=tx_id)
    try:
        yield tx
    except Exception as exc:
        logger.error("tx %s: exception in context, rolling back: %s", tx.tx_id, exc)
        tx.failed_reason = str(exc)
        if tx.state == TxState.ACTIVE:
            tx.rollback()
        tx.fail(reason=str(exc))
        raise
    else:
        if tx.state == TxState.ACTIVE:
            tx.commit()


__all__ = [
    "DispatchTransaction",
    "TransactionRegistry",
    "TxState",
    "TxStateError",
    "TxModule",
    "ALLOWED_TRANSITIONS",
    "transaction_context",
    "get_call_counter_er",
    "_inc_call_counter_er",
]
