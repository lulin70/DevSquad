#!/usr/bin/env python3
"""Dispatch Loop Controller (V4.5.6 P4-P5 Wave 3).

Loop-level fuse: consecutive same-reason retriable → fatal (avoid 100-min waste).
对齐 weiransoft/TraeMultiAgentSkill v2.8.4 §3.3 WorkflowLoopController.

设计原则:
- V4.5.3 lesson #1: __slots__ + __init__ 双管齐下
- V4.5.3 lesson #4: _call_counter_er 命名统一
- V4.5.3 lesson #7: best-effort try/except (reason 比较失败降级字符串)
- 上游 §3.3: 连续 2 次相同 retriable → fatal
- 上游 §6.2: reason 变化时重置计数器

Anti-Ghost: _loop_call_counter_er 递增 on should_stop().
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anti-Ghost counter (V4.5.3 lesson #4 naming unified)
# ---------------------------------------------------------------------------
_loop_call_counter_er: int = 0
_loop_counter_lock = threading.Lock()


def _inc_call_counter_er() -> None:
    """Increment DispatchLoopController activation counter (thread-safe)."""
    global _loop_call_counter_er
    with _loop_counter_lock:
        _loop_call_counter_er += 1


def get_call_counter_er() -> int:
    """Return activation counter for Anti-Ghost verification."""
    return _loop_call_counter_er


# ---------------------------------------------------------------------------
# Stop Reasons
# ---------------------------------------------------------------------------


class LoopStopReason(str, Enum):
    """Reason for loop termination."""

    MAX_ITERATION = "max_iteration"
    CONSECUTIVE_RETRIABLE = "consecutive_retriable"
    FATAL_ERROR = "fatal_error"
    SUCCESS = "success"
    NONE = "none"


class IterationKind(str, Enum):
    """Iteration outcome kind."""

    SUCCESS = "success"
    RETRIABLE = "retriable"
    FATAL = "fatal"


@dataclass(slots=True, frozen=True)
class IterationResult:
    """Result of a single iteration."""

    kind: IterationKind
    reason: str = ""
    message: str = ""


# ---------------------------------------------------------------------------
# Controller
# ---------------------------------------------------------------------------


class DispatchLoopController:
    """Loop-level fuse controller.

    Continues iterations until:
    - success (any reason)
    - fatal error
    - max iterations reached
    - consecutive same-reason retriable count ≥ fuse_threshold (升级 fatal)
    """

    DEFAULT_MAX_ITERATIONS = 3
    DEFAULT_FUSE_THRESHOLD = 2

    __slots__ = (
        "_max_iterations",
        "_fuse_threshold",
        "_current_iteration",
        "_consecutive_retriable_count",
        "_last_retriable_reason",
        "_lock",
        "_stop_reason",
    )

    def __init__(
        self,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
        fuse_threshold: int = DEFAULT_FUSE_THRESHOLD,
    ) -> None:
        _inc_call_counter_er()
        self._max_iterations = max_iterations
        self._fuse_threshold = fuse_threshold
        self._current_iteration = 0
        self._consecutive_retriable_count = 0
        self._last_retriable_reason: str | None = None
        self._lock = threading.Lock()
        self._stop_reason: LoopStopReason = LoopStopReason.NONE

    # ---- public properties ----

    @property
    def current_iteration(self) -> int:
        return self._current_iteration

    @property
    def stop_reason(self) -> LoopStopReason:
        return self._stop_reason

    @property
    def consecutive_retriable_count(self) -> int:
        return self._consecutive_retriable_count

    @property
    def last_retriable_reason(self) -> str | None:
        return self._last_retriable_reason

    # ---- public API ----

    def should_stop(self, iter_result: IterationResult) -> bool:
        """Decide whether to stop the loop based on iteration result.

        Rules:
        - kind=FATAL → stop with FATAL_ERROR
        - kind=RETRIABLE:
            - same reason as last retriable → count++
                - count >= fuse_threshold → stop (CONSECUTIVE_RETRIABLE)
            - different reason → reset count, set new reason
        - kind=SUCCESS → reset counters (don't stop, continue to next iteration)
            - actually stop if max_iterations reached
        - Always check max_iterations first.

        Returns:
            True if loop should terminate.
        """
        _inc_call_counter_er()

        # 1. Fatal: immediate stop
        if iter_result.kind == IterationKind.FATAL:
            with self._lock:
                self._stop_reason = LoopStopReason.FATAL_ERROR
            logger.error(
                "loop: FATAL at iter %d: %s",
                self._current_iteration, iter_result.reason,
            )
            return True

        # 2. Max iteration check
        if self._current_iteration >= self._max_iterations:
            with self._lock:
                self._stop_reason = LoopStopReason.MAX_ITERATION
            logger.warning(
                "loop: max iterations reached (%d)", self._max_iterations,
            )
            return True

        # 3. Retriable: check fuse
        if iter_result.kind == IterationKind.RETRIABLE:
            with self._lock:
                normalized_reason = self._normalize_reason(iter_result.reason)
                if normalized_reason == self._last_retriable_reason:
                    self._consecutive_retriable_count += 1
                    if self._consecutive_retriable_count >= self._fuse_threshold:
                        self._stop_reason = LoopStopReason.CONSECUTIVE_RETRIABLE
                        logger.error(
                            "loop: fuse triggered (%d consecutive '%s') → fatal",
                            self._consecutive_retriable_count,
                            normalized_reason,
                        )
                        return True
                else:
                    # Different reason: reset counter
                    self._consecutive_retriable_count = 1
                    self._last_retriable_reason = normalized_reason
                logger.info(
                    "loop: retriable #%d (reason=%s)",
                    self._consecutive_retriable_count, normalized_reason,
                )
            return False

        # 4. Success: reset counters, continue
        if iter_result.kind == IterationKind.SUCCESS:
            with self._lock:
                self._consecutive_retriable_count = 0
                self._last_retriable_reason = None
        return False

    def next_iteration(self) -> int:
        """Increment iteration counter, return new value."""
        with self._lock:
            self._current_iteration += 1
            return self._current_iteration

    def reset(self) -> None:
        """Reset all counters (for retry)."""
        with self._lock:
            self._current_iteration = 0
            self._consecutive_retriable_count = 0
            self._last_retriable_reason = None
            self._stop_reason = LoopStopReason.NONE

    @staticmethod
    def _normalize_reason(reason: str) -> str:
        """Normalize reason string for comparison (V4.5.3 lesson #7 best-effort).

        Trim, lowercase, truncate to 50 chars to avoid pathological differences.
        """
        try:
            normalized = reason.strip().lower()[:50]
            return normalized or "unknown"
        except Exception:
            return "unknown"

    def to_dict(self) -> dict[str, Any]:
        """Serialize state for logging."""
        return {
            "current_iteration": self._current_iteration,
            "max_iterations": self._max_iterations,
            "fuse_threshold": self._fuse_threshold,
            "consecutive_retriable_count": self._consecutive_retriable_count,
            "last_retriable_reason": self._last_retriable_reason,
            "stop_reason": self._stop_reason.value,
        }


__all__ = [
    "DispatchLoopController",
    "IterationKind",
    "IterationResult",
    "LoopStopReason",
    "get_call_counter_er",
    "_inc_call_counter_er",
]
