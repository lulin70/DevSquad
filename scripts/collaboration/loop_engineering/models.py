"""Loop Engineering 核心数据模型。

定义五步闭环运行所需的全部结构化数据类型，与现有模块解耦。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class LoopType(str, Enum):
    """业务 Loop 类型。"""

    DESIGN = "design"
    CODING = "coding"
    TESTING = "testing"


class EvaluatorMode(str, Enum):
    """独立 Evaluator 严格程度。"""

    STRICT = "strict"
    STANDARD = "standard"
    OFF = "off"


class SchedulingAction(str, Enum):
    """LoopScheduler 决策动作。"""

    CONTINUE = "continue"
    FIX = "fix"
    HUMAN_CHECKPOINT = "human_checkpoint"
    STOP_SUCCESS = "stop_success"
    STOP_FAILURE = "stop_failure"


class LoopEventType(str, Enum):
    """Loop 运行事件类型。"""

    DISCOVERY_STARTED = "discovery_started"
    DISCOVERY_COMPLETED = "discovery_completed"
    HANDOFF_DISPATCHED = "handoff_dispatched"
    VERIFICATION_REJECTED = "verification_rejected"
    VERIFICATION_PASSED = "verification_passed"
    SCHEDULING_DECISION = "scheduling_decision"
    HUMAN_CHECKPOINT = "human_checkpoint"
    LOOP_COMPLETED = "loop_completed"
    LOOP_FAILED = "loop_failed"


@dataclass
class LoopEngineeringConfig:
    """Loop Engineering 配置。"""

    loop_type: LoopType = LoopType.CODING
    evaluator_mode: EvaluatorMode = EvaluatorMode.STRICT
    max_iterations: int = 50
    max_tokens: int = 500_000
    human_checkpoint_every: int = 5
    stop_when: str = ""
    project_root: str = "."

    def validate(self) -> None:
        if self.max_iterations < 1:
            raise ValueError("max_iterations must be >= 1")
        if self.max_tokens < 1000:
            raise ValueError("max_tokens must be >= 1000")
        if self.human_checkpoint_every < 0 or self.human_checkpoint_every > self.max_iterations:
            raise ValueError("human_checkpoint_every must be in [0, max_iterations]")


@dataclass
class LoopEvent:
    """Loop 运行事件。"""

    event_type: LoopEventType
    phase: str
    iter_index: int
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SchedulingDecision:
    """调度决策结果。"""

    action: SchedulingAction
    reason: str
    next_iteration: int = 0


@dataclass
class CycleResult:
    """单轮执行结果。"""

    iter_index: int
    discovery: dict[str, Any]
    handoff: dict[str, Any]
    verification_passed: bool
    verification_errors: list[str]
    scheduling_decision: SchedulingDecision | None = None
    events: list[LoopEvent] = field(default_factory=list)


@dataclass
class LoopRunReport:
    """完整运行报告。"""

    objective: str
    total_iterations: int
    final_status: str  # "completed" | "failed" | "stopped"
    cycles: list[CycleResult] = field(default_factory=list)
    events: list[LoopEvent] = field(default_factory=list)
    total_duration: float = 0.0
    total_tokens_used: int = 0
    error: str = ""

    @property
    def success(self) -> bool:
        return self.final_status == "completed"
