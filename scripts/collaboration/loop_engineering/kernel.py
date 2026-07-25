"""Loop Engineering 核心编排器：LoopKernel。

实现五步闭环：
    Discovery → Handoff → Verification → Persistence → Scheduling

LoopKernel 不直接执行业务逻辑，通过 Protocol 组合各组件。
集成 RollbackStrategy 实现精准回退 + 独立硬上限 (V4.3.0 P1-4)。
"""

from __future__ import annotations

import logging
import time
from typing import Any

from .discovery_probe import DiscoveryProbe
from .handoff_adapter import HandoffAdapter
from .independent_evaluator import IndependentEvaluator
from .loop_scheduler import LoopScheduler
from .models import (
    CycleResult,
    LoopEngineeringConfig,
    LoopEvent,
    LoopEventType,
    LoopRunReport,
    SchedulingAction,
    SchedulingDecision,
)
from .protocols import (
    DiscoveryProbeProtocol,
    HandoffAdapterProtocol,
    IndependentEvaluatorProtocol,
    LoopSchedulerProtocol,
    UnifiedMemoryLayerProtocol,
)
from .rollback_strategy import RollbackStrategy
from .unified_memory import UnifiedMemory

logger = logging.getLogger(__name__)


class LoopKernel:
    """Loop Engineering 五步闭环编排核心。"""

    def __init__(
        self,
        config: LoopEngineeringConfig | None = None,
        discovery_probe: DiscoveryProbeProtocol | None = None,
        handoff_adapter: HandoffAdapterProtocol | None = None,
        evaluator: IndependentEvaluatorProtocol | None = None,
        memory: UnifiedMemoryLayerProtocol | None = None,
        scheduler: LoopSchedulerProtocol | None = None,
        rollback_strategy: RollbackStrategy | None = None,
    ) -> None:
        self._config = config or LoopEngineeringConfig()
        self._config.validate()

        self._discovery_probe = discovery_probe or DiscoveryProbe()
        self._handoff_adapter = handoff_adapter or HandoffAdapter()
        self._evaluator = evaluator or IndependentEvaluator(
            mode=self._config.evaluator_mode,
        )
        self._memory = memory or UnifiedMemory()
        self._rollback_strategy = rollback_strategy or RollbackStrategy(
            max_rollback_iterations=self._config.max_rollback_iterations,
        )
        self._scheduler = scheduler or LoopScheduler(
            human_checkpoint_every=self._config.human_checkpoint_every,
            rollback_strategy=self._rollback_strategy,
        )

        self._stop_requested = False
        self._consecutive_failures = 0
        self._rollback_count = 0
        self._accumulated_artifacts: dict[str, Any] = {}

    @property
    def rollback_count(self) -> int:
        """Number of rollbacks performed in the current run."""
        return self._rollback_count

    @property
    def accumulated_artifacts(self) -> dict[str, Any]:
        """Artifacts accumulated across rollback cycles."""
        return self._accumulated_artifacts

    def stop(self) -> None:
        """请求停止，当前轮次完成后退出。"""
        self._stop_requested = True

    def run(self, objective: str) -> LoopRunReport:
        """启动完整 Loop Engineering 流程。"""
        start_time = time.time()
        self._config.validate()
        self._rollback_count = 0
        self._accumulated_artifacts = {}

        report = LoopRunReport(
            objective=objective,
            total_iterations=0,
            final_status="failed",
        )

        iter_index = 0
        while not self._stop_requested:
            if iter_index >= self._config.max_iterations:
                report.final_status = "failed"
                report.error = f"Max iterations ({self._config.max_iterations}) reached"
                break

            cycle = self._run_one_cycle(objective, iter_index)
            report.cycles.append(cycle)
            report.events.extend(cycle.events)
            report.total_iterations = iter_index + 1

            decision = cycle.scheduling_decision
            if decision is None:
                report.final_status = "failed"
                report.error = "Cycle returned without scheduling decision"
                break
            if decision.action == SchedulingAction.STOP_SUCCESS:
                report.final_status = "completed"
                break
            if decision.action == SchedulingAction.STOP_FAILURE:
                report.final_status = "failed"
                report.error = decision.reason
                break

            iter_index = decision.next_iteration

        if self._stop_requested and report.final_status == "failed":
            report.final_status = "stopped"
            report.error = "Manually stopped"

        report.total_duration = time.time() - start_time
        if hasattr(self._memory, "save_to_disk"):
            self._memory.save_to_disk(objective)

        return report

    def _run_one_cycle(self, objective: str, iter_index: int) -> CycleResult:
        """执行单轮五步闭环。"""
        events: list[LoopEvent] = []

        # 1. Discovery
        events.append(LoopEvent(
            event_type=LoopEventType.DISCOVERY_STARTED,
            phase="discovery",
            iter_index=iter_index,
        ))
        discovery = self._discovery_probe.discover(objective, iter_index, self._memory)
        events.append(LoopEvent(
            event_type=LoopEventType.DISCOVERY_COMPLETED,
            phase="discovery",
            iter_index=iter_index,
            payload=discovery,
        ))

        if discovery.get("done"):
            return CycleResult(
                iter_index=iter_index,
                discovery=discovery,
                handoff={"status": "skipped"},
                verification_passed=True,
                verification_errors=[],
                scheduling_decision=self._scheduler.decide(
                    iter_index,
                    CycleResult(
                        iter_index=iter_index,
                        discovery=discovery,
                        handoff={},
                        verification_passed=True,
                        verification_errors=[],
                        scheduling_decision=None,
                    ),
                    self._consecutive_failures,
                    self._config.max_iterations,
                ),
                events=events,
            )

        # 2. Handoff
        handoff = self._handoff_adapter.dispatch(discovery, iter_index)
        events.append(LoopEvent(
            event_type=LoopEventType.HANDOFF_DISPATCHED,
            phase="handoff",
            iter_index=iter_index,
            payload={"status": handoff.get("status")},
        ))

        # 3. Verification
        passed, errors = self._evaluator.evaluate(objective, handoff, iter_index)
        if passed:
            events.append(LoopEvent(
                event_type=LoopEventType.VERIFICATION_PASSED,
                phase="verification",
                iter_index=iter_index,
            ))
            self._consecutive_failures = 0
            self._rollback_count = 0
        else:
            events.append(LoopEvent(
                event_type=LoopEventType.VERIFICATION_REJECTED,
                phase="verification",
                iter_index=iter_index,
                payload={"errors": errors},
            ))
            self._consecutive_failures += 1

        # 4. Persistence
        cycle = CycleResult(
            iter_index=iter_index,
            discovery=discovery,
            handoff=handoff,
            verification_passed=passed,
            verification_errors=errors,
            scheduling_decision=None,
            events=events,
        )
        self._memory.persist_cycle(cycle)
        for event in events:
            self._memory.persist_event(event)

        # 5. Scheduling
        if passed:
            decision = self._scheduler.decide(
                iter_index,
                cycle,
                self._consecutive_failures,
                self._config.max_iterations,
            )
        else:
            decision = self._handle_verification_failure(iter_index, cycle)

        cycle.scheduling_decision = decision
        events.append(LoopEvent(
            event_type=LoopEventType.SCHEDULING_DECISION,
            phase="scheduling",
            iter_index=iter_index,
            payload={"action": decision.action.value, "reason": decision.reason},
        ))

        return cycle

    def _handle_verification_failure(
        self,
        iter_index: int,
        cycle: CycleResult,
    ) -> SchedulingDecision:
        """Handle verification failure via RollbackStrategy.

        If the rollback hard cap is not yet reached, returns a ROLLBACK
        decision to retry the same iteration (accumulating artifacts).
        When the hard cap is exceeded, returns STOP_FAILURE.

        Args:
            iter_index: Current iteration index (rollback retries same index).
            cycle: The failed cycle result whose artifacts to preserve.

        Returns:
            SchedulingDecision with action ROLLBACK or STOP_FAILURE.
        """
        if self._rollback_strategy.should_stop(self._rollback_count):
            return SchedulingDecision(
                action=SchedulingAction.STOP_FAILURE,
                reason=(
                    f"Rollback iterations ({self._rollback_count}) exceeded "
                    f"hard cap ({self._config.max_rollback_iterations})"
                ),
            )
        target = self._rollback_strategy.determine_rollback("D3")
        self._rollback_count += 1
        self._merge_artifacts(cycle)
        rollback_context: dict[str, Any] = {}
        self._rollback_strategy.execute_rollback(target, rollback_context)
        return SchedulingDecision(
            action=SchedulingAction.ROLLBACK,
            reason=(
                f"Rollback to {target.value} phase for D3 verification failure "
                f"(count={self._rollback_count})"
            ),
            next_iteration=iter_index,
        )

    def _merge_artifacts(self, cycle: CycleResult) -> None:
        """Merge cycle artifacts into the accumulated store for rollback context.

        Preserves work from previous cycles so that rollback retries can
        access prior discoveries, handoffs, and verification errors.

        Args:
            cycle: The failed cycle whose artifacts to accumulate.
        """
        if cycle.discovery:
            self._accumulated_artifacts.setdefault("discoveries", []).append(
                cycle.discovery,
            )
        if cycle.handoff:
            self._accumulated_artifacts.setdefault("handoffs", []).append(
                cycle.handoff,
            )
        if cycle.verification_errors:
            self._accumulated_artifacts.setdefault(
                "verification_errors", [],
            ).extend(cycle.verification_errors)
