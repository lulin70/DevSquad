#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协作系统 (Collaboration System)

基于 Claude Code Coordinator 模式的多 Agent 协作框架。

核心组件：
- Scratchpad: 共享黑板，Worker 间交换信息
- Worker: 工作者，执行具体任务
- Coordinator: 协调者，管理全局协作
- ConsensusEngine: 共识引擎，处理投票和决策
- BatchScheduler: 批处理调度器，支持并行/串行混合

使用示例:
    from collaboration import Coordinator, Scratchpad

    scratchpad = Scratchpad()
    coordinator = Coordinator(scratchpad=scratchpad)

    plan = coordinator.plan_task("设计用户认证系统", [
        {"role_id": "architect"},
        {"role_id": "tester"},
        {"role_id": "product-manager"},
    ])

    workers = coordinator.spawn_workers(plan)
    result = coordinator.execute_plan(plan)
    report = coordinator.generate_report()
"""

from .models import (
    EntryType,
    EntryStatus,
    ReferenceType,
    Reference,
    ScratchpadEntry,
    TaskDefinition,
    WorkerResult,
    TaskNotification,
    Vote,
    DecisionProposal,
    DecisionOutcome,
    ConsensusRecord,
    ExecutionPlan,
    BatchMode,
    TaskBatch,
    ScheduleResult,
    ROLE_WEIGHTS,
    CONSENSUS_THRESHOLDS,
)
from .scratchpad import Scratchpad
from .worker import Worker, WorkerFactory
from .consensus import ConsensusEngine
from .coordinator import Coordinator
from .batch_scheduler import BatchScheduler

__all__ = [
    "Scratchpad",
    "Worker",
    "WorkerFactory",
    "ConsensusEngine",
    "Coordinator",
    "BatchScheduler",
    "EntryType",
    "EntryStatus",
    "ReferenceType",
    "Reference",
    "ScratchpadEntry",
    "TaskDefinition",
    "WorkerResult",
    "TaskNotification",
    "Vote",
    "DecisionProposal",
    "DecisionOutcome",
    "ConsensusRecord",
    "ExecutionPlan",
    "BatchMode",
    "TaskBatch",
    "ScheduleResult",
]
