"""Scheduling 阶段：决策下一步动作。"""

from __future__ import annotations

from .models import CycleResult, SchedulingAction, SchedulingDecision
from .rollback_strategy import RollbackStrategy, RollbackTarget


class LoopScheduler:
    """决策下一步动作。

    基于验证结果、连续失败次数和迭代上限，决定 CONTINUE/FIX/STOP。
    集成 RollbackStrategy 实现精准回退决策。
    """

    def __init__(
        self,
        human_checkpoint_every: int = 5,
        rollback_strategy: RollbackStrategy | None = None,
    ) -> None:
        self._human_checkpoint_every = human_checkpoint_every
        self._rollback_strategy = rollback_strategy

    def decide(
        self,
        iter_index: int,
        cycle_result: CycleResult,
        consecutive_failures: int,
        max_iterations: int,
    ) -> SchedulingDecision:
        if cycle_result.verification_passed:
            if cycle_result.discovery.get("done"):
                return SchedulingDecision(
                    action=SchedulingAction.STOP_SUCCESS,
                    reason="All tasks completed and verified",
                )
            return SchedulingDecision(
                action=SchedulingAction.CONTINUE,
                reason="Verification passed, continue next iteration",
                next_iteration=iter_index + 1,
            )

        if consecutive_failures >= 3:
            return SchedulingDecision(
                action=SchedulingAction.STOP_FAILURE,
                reason=f"Consecutive failures ({consecutive_failures}) exceeded limit",
            )

        if iter_index + 1 >= max_iterations:
            return SchedulingDecision(
                action=SchedulingAction.STOP_FAILURE,
                reason=f"Max iterations ({max_iterations}) reached",
            )

        if (
            self._human_checkpoint_every > 0
            and (iter_index + 1) % self._human_checkpoint_every == 0
        ):
            return SchedulingDecision(
                action=SchedulingAction.HUMAN_CHECKPOINT,
                reason=f"Human checkpoint at iteration {iter_index}",
                next_iteration=iter_index + 1,
            )

        return SchedulingDecision(
            action=SchedulingAction.FIX,
            reason="Verification failed, attempt fix",
            next_iteration=iter_index + 1,
        )

    def decide_rollback(
        self,
        iter_index: int,
        failed_dimension: str,
        rollback_count: int,
        max_rollback_iterations: int,
    ) -> SchedulingDecision:
        """Consult RollbackStrategy for rollback target on dimension failure.

        When the rollback hard cap is exceeded, returns STOP_FAILURE.
        Otherwise, returns ROLLBACK with the target phase determined by
        the RollbackStrategy's per-dimension mapping.

        Args:
            iter_index: Current iteration index (rollback retries same index).
            failed_dimension: Failure dimension identifier ("D1"-"D6").
            rollback_count: Number of rollbacks already performed.
            max_rollback_iterations: Hard cap on rollback iterations.

        Returns:
            SchedulingDecision with action ROLLBACK (retry same iteration)
            or STOP_FAILURE (hard cap exceeded).

        Example:
            >>> scheduler = LoopScheduler(rollback_strategy=RollbackStrategy(3))
            >>> d = scheduler.decide_rollback(0, "D3", 0, 3)
            >>> d.action.value
            'rollback'
        """
        strategy = self._rollback_strategy or RollbackStrategy(max_rollback_iterations)
        if strategy.should_stop(rollback_count):
            return SchedulingDecision(
                action=SchedulingAction.STOP_FAILURE,
                reason=(
                    f"Rollback iterations ({rollback_count}) exceeded "
                    f"hard cap ({max_rollback_iterations})"
                ),
            )
        target = strategy.determine_rollback(failed_dimension)
        if target == RollbackTarget.NONE:
            return SchedulingDecision(
                action=SchedulingAction.STOP_FAILURE,
                reason=f"No rollback target for dimension {failed_dimension}",
            )
        return SchedulingDecision(
            action=SchedulingAction.ROLLBACK,
            reason=f"Rollback to {target.value} phase for {failed_dimension} failure",
            next_iteration=iter_index,
        )
