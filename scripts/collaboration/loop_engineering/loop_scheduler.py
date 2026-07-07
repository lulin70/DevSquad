"""Scheduling 阶段：决策下一步动作。"""

from __future__ import annotations

from .models import CycleResult, SchedulingAction, SchedulingDecision


class LoopScheduler:
    """决策下一步动作。

    基于验证结果、连续失败次数和迭代上限，决定 CONTINUE/FIX/STOP。
    """

    def __init__(self, human_checkpoint_every: int = 5) -> None:
        self._human_checkpoint_every = human_checkpoint_every

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
