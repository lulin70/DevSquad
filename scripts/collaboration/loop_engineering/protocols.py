"""Loop Engineering Protocol 接口定义。

各组件通过 Protocol 组合，LoopKernel 不直接依赖具体实现。
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from .models import CycleResult, LoopEvent, SchedulingDecision


@runtime_checkable
class DiscoveryProbeProtocol(Protocol):
    """Discovery 阶段：发现本轮该做什么。"""

    def discover(self, objective: str, iter_index: int, memory: Any) -> dict[str, Any]:
        """返回本轮发现的工作项。"""
        ...


@runtime_checkable
class HandoffAdapterProtocol(Protocol):
    """Handoff 阶段：生成工作项并调用 Generator 执行。"""

    def dispatch(self, discovery_result: dict[str, Any], iter_index: int) -> dict[str, Any]:
        """执行工作项，返回产出。"""
        ...


@runtime_checkable
class IndependentEvaluatorProtocol(Protocol):
    """Verification 阶段：独立评估 Generator 产出。"""

    def evaluate(
        self,
        objective: str,
        handoff_result: dict[str, Any],
        iter_index: int,
    ) -> tuple[bool, list[str]]:
        """返回 (passed, errors)。"""
        ...


@runtime_checkable
class UnifiedMemoryLayerProtocol(Protocol):
    """Persistence 阶段：统一记忆读写。"""

    def persist_event(self, event: LoopEvent) -> None:
        """持久化事件。"""
        ...

    def load_history(self, objective: str) -> list[dict[str, Any]]:
        """加载历史记录。"""
        ...

    def persist_cycle(self, cycle: CycleResult) -> None:
        """持久化单轮结果。"""
        ...


@runtime_checkable
class LoopSchedulerProtocol(Protocol):
    """Scheduling 阶段：决策下一步动作。"""

    def decide(
        self,
        iter_index: int,
        cycle_result: CycleResult,
        consecutive_failures: int,
        max_iterations: int,
    ) -> SchedulingDecision:
        """返回调度决策。"""
        ...
