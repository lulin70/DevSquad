#!/usr/bin/env python3
"""Unit tests for DispatchLoopController (V4.5.6 P4-P5 Wave 3).

5 tests covering fuse logic, reason normalization, max iteration.
"""
from __future__ import annotations

import pytest

from scripts.collaboration.dispatcher_loop_controller import (
    DispatchLoopController,
    IterationKind,
    IterationResult,
    LoopStopReason,
    get_call_counter_er,
)


@pytest.fixture
def ctrl() -> DispatchLoopController:
    return DispatchLoopController(max_iterations=3, fuse_threshold=2)


class TestLoopControllerBasics:
    def test_loop_controller_initial_no_stop(self, ctrl: DispatchLoopController) -> None:
        """Fresh controller with SUCCESS result → don't stop (more iterations possible)."""
        assert ctrl.current_iteration == 0
        assert not ctrl.should_stop(IterationResult(IterationKind.SUCCESS))
        assert ctrl.stop_reason == LoopStopReason.NONE

    def test_loop_controller_consecutive_retriable_fuse(self, ctrl: DispatchLoopController) -> None:
        """Two same-reason retriable → fuse triggers."""
        # First retriable: count = 1, don't stop
        assert not ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="timeout"))
        assert ctrl.consecutive_retriable_count == 1
        # Second same-reason: count = 2, fuse triggers
        assert ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="timeout"))
        assert ctrl.consecutive_retriable_count == 2
        assert ctrl.stop_reason == LoopStopReason.CONSECUTIVE_RETRIABLE

    def test_loop_controller_different_reason_reset(self, ctrl: DispatchLoopController) -> None:
        """Different retriable reason → reset counter."""
        ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="timeout"))
        ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="timeout"))
        assert ctrl.consecutive_retriable_count == 2
        # Different reason: reset
        assert not ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="auth_error"))
        assert ctrl.consecutive_retriable_count == 1
        assert ctrl.last_retriable_reason == "auth_error"

    def test_loop_controller_max_iteration_limit(self) -> None:
        """Reaching max_iterations → stop."""
        ctrl = DispatchLoopController(max_iterations=3, fuse_threshold=100)
        # Reach max by advancing iterations
        for _ in range(3):
            ctrl.next_iteration()
        # Now current = 3, max = 3 → should stop
        assert ctrl.should_stop(IterationResult(IterationKind.SUCCESS))

    def test_loop_controller_fatal_on_fuse(self, ctrl: DispatchLoopController) -> None:
        """Fatal kind → immediate stop."""
        assert ctrl.should_stop(IterationResult(IterationKind.FATAL, reason="crash"))
        assert ctrl.stop_reason == LoopStopReason.FATAL_ERROR


class TestLoopControllerNormalization:
    def test_reason_normalization(self, ctrl: DispatchLoopController) -> None:
        """Reason strings are normalized (trim, lowercase, truncate).

        Note: After normalization, two same-source reasons match, so the fuse
        triggers on the 2nd same-reason call.
        """
        # First retriable (with whitespace + uppercase): count = 1, don't stop
        assert not ctrl.should_stop(
            IterationResult(IterationKind.RETRIABLE, reason="  TIMEOUT  ")
        )
        # Second (already-normalized "timeout"): same after normalization → count = 2 → fuse
        assert ctrl.should_stop(
            IterationResult(IterationKind.RETRIABLE, reason="timeout")
        )
        assert ctrl.consecutive_retriable_count == 2
        assert ctrl.stop_reason == LoopStopReason.CONSECUTIVE_RETRIABLE


class TestLoopControllerLifecycle:
    def test_reset(self, ctrl: DispatchLoopController) -> None:
        """Reset clears counters + stop_reason."""
        ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="x"))
        ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="x"))
        ctrl.next_iteration()
        assert ctrl.consecutive_retriable_count == 2
        ctrl.reset()
        assert ctrl.current_iteration == 0
        assert ctrl.consecutive_retriable_count == 0
        assert ctrl.last_retriable_reason is None
        assert ctrl.stop_reason == LoopStopReason.NONE

    def test_to_dict(self, ctrl: DispatchLoopController) -> None:
        """Serialization captures state."""
        ctrl.next_iteration()
        ctrl.should_stop(IterationResult(IterationKind.RETRIABLE, reason="x"))
        d = ctrl.to_dict()
        assert d["current_iteration"] == 1
        assert d["max_iterations"] == 3
        assert d["fuse_threshold"] == 2
        assert d["consecutive_retriable_count"] == 1
        assert d["last_retriable_reason"] == "x"
        assert d["stop_reason"] == "none"


class TestLoopControllerAntiGhost:
    def test_call_counter_increments(self, ctrl: DispatchLoopController) -> None:
        before = get_call_counter_er()
        ctrl.should_stop(IterationResult(IterationKind.SUCCESS))
        assert get_call_counter_er() > before
