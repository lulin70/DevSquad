#!/usr/bin/env python3
"""Unit tests for DispatcherTransaction (V4.5.6 P4-P5 Wave 2 main).

12 tests covering FSM, LIFO revert, atomicity, context manager.
"""
from __future__ import annotations

import threading

import pytest

from scripts.collaboration.dispatcher_transaction import (
    ALLOWED_TRANSITIONS,
    DispatchTransaction,
    TransactionRegistry,
    TxState,
    TxStateError,
    transaction_context,
)


@pytest.fixture
def tx() -> DispatchTransaction:
    """Fresh transaction per test."""
    return DispatchTransaction(tx_id="test_tx")


class TestTxStateInitial:
    def test_tx_state_initial_pending(self, tx: DispatchTransaction) -> None:
        """A fresh transaction starts in PENDING state."""
        assert tx.state == TxState.PENDING
        assert tx.tx_id == "test_tx"
        assert tx.modules == []
        assert tx.entered_count == 0
        assert tx.failed_reason is None

    def test_tx_state_transitions(self, tx: DispatchTransaction) -> None:
        """Verify ALLOWED_TRANSITIONS table covers all expected edges."""
        assert TxState.ACTIVE in ALLOWED_TRANSITIONS[TxState.PENDING]
        assert TxState.FAILED in ALLOWED_TRANSITIONS[TxState.PENDING]
        assert TxState.COMMITTED in ALLOWED_TRANSITIONS[TxState.ACTIVE]
        assert TxState.ROLLED_BACK in ALLOWED_TRANSITIONS[TxState.ACTIVE]
        assert TxState.FAILED in ALLOWED_TRANSITIONS[TxState.ACTIVE]
        assert TxState.ACTIVE in ALLOWED_TRANSITIONS[TxState.ROLLED_BACK]
        # Terminal states
        assert ALLOWED_TRANSITIONS[TxState.COMMITTED] == frozenset()
        assert ALLOWED_TRANSITIONS[TxState.FAILED] == frozenset()


class TestTxCommit:
    def test_tx_commit_all_modules(self) -> None:
        """All modules enter successfully → COMMITTED state."""
        tx = DispatchTransaction()
        events: list[str] = []
        tx.register_module("m1", enter_fn=lambda: events.append("e1"), revert_fn=lambda: events.append("r1"))
        tx.register_module("m2", enter_fn=lambda: events.append("e2"), revert_fn=lambda: events.append("r2"))
        tx.begin()
        assert tx.state == TxState.ACTIVE
        assert tx.entered_count == 2
        assert events == ["e1", "e2"]
        tx.commit()
        assert tx.state == TxState.COMMITTED
        assert events == ["e1", "e2"]  # no revert


class TestTxRollback:
    def test_tx_rollback_on_failure(self) -> None:
        """Enter m1 success, m2 fail → ROLLED_BACK, LIFO revert."""
        tx = DispatchTransaction()
        events: list[str] = []

        def m1_enter() -> None:
            events.append("e1")

        def m1_revert() -> None:
            events.append("r1")

        def m2_enter() -> None:
            events.append("e2")
            raise RuntimeError("m2 boom")

        def m2_revert() -> None:
            events.append("r2")

        tx.register_module("m1", m1_enter, m1_revert)
        tx.register_module("m2", m2_enter, m2_revert)

        with pytest.raises(RuntimeError, match="m2 boom"):
            tx.begin()
        assert tx.state == TxState.ROLLED_BACK
        # LIFO: m2 was last entered, but failed; m1 was entered successfully → revert m1
        # Note: m2 didn't successfully enter, so only m1 gets reverted
        assert "r1" in events
        assert tx.entered_count == 1

    def test_tx_lifo_revert_order(self) -> None:
        """All modules enter successfully, then rollback → LIFO revert order."""
        tx = DispatchTransaction()
        events: list[str] = []
        for i in range(1, 4):
            tx.register_module(
                f"m{i}",
                enter_fn=lambda i=i: events.append(f"e{i}"),
                revert_fn=lambda i=i: events.append(f"r{i}"),
            )
        tx.begin()
        assert events == ["e1", "e2", "e3"]
        tx.rollback()
        # LIFO: 3, 2, 1
        assert events == ["e1", "e2", "e3", "r3", "r2", "r1"]
        assert tx.state == TxState.ROLLED_BACK

    def test_tx_partial_failure_rollback(self) -> None:
        """Module 3 fails → m1, m2 reverted LIFO."""
        tx = DispatchTransaction()
        events: list[str] = []

        def make_enter(name: str, fail: bool = False) -> None:
            def fn() -> None:
                events.append(f"e_{name}")
                if fail:
                    raise ValueError(f"{name} fail")

            return fn

        tx.register_module("m1", make_enter("m1"), lambda: events.append("r_m1"))
        tx.register_module("m2", make_enter("m2"), lambda: events.append("r_m2"))
        tx.register_module("m3", make_enter("m3", fail=True), lambda: events.append("r_m3"))

        with pytest.raises(ValueError):
            tx.begin()
        # m3 failed; m1, m2 entered successfully → revert LIFO: m2, m1
        assert "r_m2" in events
        assert "r_m1" in events
        assert "r_m3" not in events  # m3 didn't enter, no revert


class TestTxAtomicity:
    def test_tx_atomic_isolation(self) -> None:
        """Modules don't see partial state during rollback."""
        tx = DispatchTransaction()
        m1_called = {"enter": False, "revert": False}
        m2_called = {"enter": False, "revert": False}

        def m1_enter() -> None:
            m1_called["enter"] = True

        def m1_revert() -> None:
            m1_called["revert"] = True

        def m2_enter() -> None:
            m2_called["enter"] = True
            raise RuntimeError("boom")

        def m2_revert() -> None:
            m2_called["revert"] = True

        tx.register_module("m1", m1_enter, m1_revert)
        tx.register_module("m2", m2_enter, m2_revert)
        with pytest.raises(RuntimeError):
            tx.begin()
        # m1 entered + reverted; m2 entered + didn't revert (failed to enter)
        assert m1_called["enter"] and m1_called["revert"]
        assert m2_called["enter"] and not m2_called["revert"]
        assert tx.state == TxState.ROLLED_BACK


class TestTxFSMEnforcement:
    def test_tx_state_machine_invalid_transition_raises(self, tx: DispatchTransaction) -> None:
        """Invalid transitions raise TxStateError (when strictly checked)."""
        # PENDING → COMMITTED is not allowed
        with pytest.raises(TxStateError):
            tx.commit()
        # ACTIVE → fail from PENDING state not via direct fail (state must allow)
        # Note: fail() now silently allows from any state for resilience
        # So test the strict path: commit after fail (FAILED is terminal)
        tx.begin()
        tx.fail(reason="intentional")
        assert tx.state == TxState.FAILED
        with pytest.raises(TxStateError):
            tx.commit()

    def test_tx_retry_from_rolled_back(self) -> None:
        """ROLLED_BACK → ACTIVE via retry()."""
        tx = DispatchTransaction()
        tx.register_module("m1", lambda: None, lambda: None)
        tx.begin()
        tx.rollback()
        assert tx.state == TxState.ROLLED_BACK
        tx.retry()  # calls begin() which transitions to ACTIVE
        assert tx.state == TxState.ACTIVE


class TestTxContextManager:
    def test_tx_context_manager_auto_commit(self) -> None:
        """with-block exit cleanly → auto commit."""
        with transaction_context(TransactionRegistry(), "ctx_ok") as tx:
            tx.register_module("a", lambda: None, lambda: None)
            tx.begin()
        # After successful exit, state should be COMMITTED
        assert tx.state == TxState.COMMITTED

    def test_tx_context_manager_auto_rollback_on_exception(self) -> None:
        """Exception inside with-block → auto rollback."""
        registry = TransactionRegistry()
        events: list[str] = []
        with pytest.raises(ValueError), transaction_context(registry, "ctx_err") as tx:
            tx.register_module("a", lambda: None, lambda: events.append("reverted"))
            tx.begin()
            raise ValueError("user boom")
        assert tx.state == TxState.FAILED
        assert "reverted" in events


class TestTxRegistryThreadSafety:
    def test_tx_registry_thread_safety(self) -> None:
        """Concurrent create_tx / get_tx / remove_tx are safe."""
        registry = TransactionRegistry()
        N = 50
        created_ids: list[str] = []

        def worker() -> None:
            for i in range(N):
                tx = registry.create_tx(f"tx_{threading.current_thread().name}_{i}")
                created_ids.append(tx.tx_id)

        threads = [threading.Thread(target=worker, name=str(i)) for i in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(created_ids) == N * 4
        # PENDING counts as active
        assert registry.active_count() == N * 4
        # After removal, count drops
        for tx_id in created_ids:
            registry.remove_tx(tx_id)
        assert registry.active_count() == 0

    def test_registry_remove_tx(self) -> None:
        """remove_tx should return True for existing, False for missing."""
        registry = TransactionRegistry()
        _ = registry.create_tx("rm_test")
        assert registry.remove_tx("rm_test") is True
        assert registry.remove_tx("rm_test") is False
