"""Loop Engineering RollbackStrategy.

Per-dimension rollback target mapping for LoopKernel failure handling.
Maps each failure dimension (D1-D6) to a precise rollback target phase,
with an independent hard cap on rollback iterations that is separate from
``LoopEngineeringConfig.max_iterations``.

Dimension mapping (per V4.3.0 PRD P1-4):
    D1 (Discovery failure)    -> DEV
    D2 (Handoff failure)      -> DEV
    D3 (Verification failure) -> TEST
    D4 (Persistence failure)  -> DEV
    D5 (Scheduling failure)   -> DEV
    D6 (Reporting failure)    -> DEV
"""

from __future__ import annotations

from enum import Enum
from typing import Any


class RollbackTarget(str, Enum):
    """Target phase for a rollback operation.

    Attributes:
        DEV: Rollback to Development phase (Discovery + Handoff).
        TEST: Rollback to Test/Verification phase.
        NONE: No rollback target available (triggers STOP_FAILURE).
    """

    DEV = "dev"
    TEST = "test"
    NONE = "none"


class RollbackStrategy:
    """Per-dimension rollback strategy with an independent hard cap.

    The hard cap (``max_rollback_iterations``) is INDEPENDENT from
    ``LoopEngineeringConfig.max_iterations`` and controls only rollback
    retries, not normal loop iterations.

    Args:
        max_rollback_iterations: Hard cap on rollback iterations. Default 3.
            Must be >= 1 (validated by ``LoopEngineeringConfig``).

    Example:
        >>> strategy = RollbackStrategy(max_rollback_iterations=3)
        >>> strategy.determine_rollback("D3")
        <RollbackTarget.TEST: 'test'>
        >>> strategy.should_stop(3)
        True
        >>> strategy.should_stop(2)
        False
    """

    _DIMENSION_MAP: dict[str, RollbackTarget] = {
        "D1": RollbackTarget.DEV,
        "D2": RollbackTarget.DEV,
        "D3": RollbackTarget.TEST,
        "D4": RollbackTarget.DEV,
        "D5": RollbackTarget.DEV,
        "D6": RollbackTarget.DEV,
    }

    def __init__(self, max_rollback_iterations: int = 3) -> None:
        self._max_rollback_iterations = max_rollback_iterations

    def determine_rollback(self, failed_dimension: str) -> RollbackTarget:
        """Determine the rollback target for a failed dimension.

        Args:
            failed_dimension: Failure dimension identifier ("D1" through "D6").

        Returns:
            RollbackTarget for the given dimension. Unknown dimensions
            default to ``DEV`` (safest retry-from-start target).

        Example:
            >>> strategy = RollbackStrategy()
            >>> strategy.determine_rollback("D1")
            <RollbackTarget.DEV: 'dev'>
            >>> strategy.determine_rollback("D3")
            <RollbackTarget.TEST: 'test'>
        """
        return self._DIMENSION_MAP.get(failed_dimension, RollbackTarget.DEV)

    def execute_rollback(
        self,
        target: RollbackTarget,
        context: dict[str, Any],
    ) -> bool:
        """Execute a rollback to the specified target phase.

        Records the rollback decision metadata in the supplied context dict
        and returns whether the rollback was actually executed.

        Args:
            target: The rollback target phase to roll back to.
            context: Context dict to record rollback metadata in.

        Returns:
            True if the rollback was executed (target is not NONE).
            False if the target is NONE (no rollback performed).

        Example:
            >>> strategy = RollbackStrategy()
            >>> ctx: dict = {}
            >>> strategy.execute_rollback(RollbackTarget.DEV, ctx)
            True
            >>> ctx["rollback_target"]
            'dev'
        """
        if target == RollbackTarget.NONE:
            return False
        context["rollback_target"] = target.value
        context["rollback_executed"] = True
        return True

    def should_stop(self, rollback_count: int) -> bool:
        """Check if the rollback hard cap has been reached or exceeded.

        Args:
            rollback_count: Number of rollbacks already performed.

        Returns:
            True if ``rollback_count >= max_rollback_iterations``
            (the loop should stop and return STOP_FAILURE).
            False if more rollbacks are permitted.

        Example:
            >>> strategy = RollbackStrategy(max_rollback_iterations=3)
            >>> strategy.should_stop(2)
            False
            >>> strategy.should_stop(3)
            True
        """
        return rollback_count >= self._max_rollback_iterations
