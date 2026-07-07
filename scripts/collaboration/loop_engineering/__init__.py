"""Loop Engineering 五步闭环模块。

Discovery → Handoff → Verification → Persistence → Scheduling
"""

from .discovery_probe import DiscoveryProbe
from .handoff_adapter import HandoffAdapter
from .independent_evaluator import IndependentEvaluator
from .kernel import LoopKernel
from .loop_scheduler import LoopScheduler
from .models import (
    CycleResult,
    EvaluatorMode,
    LoopEngineeringConfig,
    LoopEvent,
    LoopEventType,
    LoopRunReport,
    LoopType,
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
from .unified_memory import UnifiedMemory

__all__ = [
    "LoopKernel",
    "LoopEngineeringConfig",
    "LoopType",
    "EvaluatorMode",
    "SchedulingAction",
    "LoopEventType",
    "LoopEvent",
    "SchedulingDecision",
    "CycleResult",
    "LoopRunReport",
    "DiscoveryProbe",
    "HandoffAdapter",
    "IndependentEvaluator",
    "UnifiedMemory",
    "LoopScheduler",
    "DiscoveryProbeProtocol",
    "HandoffAdapterProtocol",
    "IndependentEvaluatorProtocol",
    "UnifiedMemoryLayerProtocol",
    "LoopSchedulerProtocol",
]
