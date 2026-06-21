#!/usr/bin/env python3
"""
协作系统数据模型 — Re-export Hub

定义 Coordinator + Scratchpad + Worker 协作模式的所有核心数据结构。
本模块已按域拆分为三个子模块，此处仅做向后兼容的 re-export：

- models_base.py: 共享基类、枚举、核心类型定义（Scratchpad / Task / Consensus）
- models_dispatch.py: 角色派发相关定义（RoleDefinition / ROLE_REGISTRY 等）
- models_lifecycle.py: 生命周期执行与回顾（ExecutionPlan / Anchor / Retrospective）

向后兼容：所有 ``from .models import X`` 的历史导入仍然有效。
"""

# Base: shared enums, foundational dataclasses, consensus types
from .models_base import (  # noqa: F401
    CONSENSUS_THRESHOLDS,
    ConsensusRecord,
    DecisionOutcome,
    DecisionProposal,
    EntryStatus,
    EntryType,
    Reference,
    ReferenceType,
    ScratchpadEntry,
    TaskDefinition,
    TaskNotification,
    Vote,
    WorkerResult,
)

# Dispatch: role definitions, registry, resolution helpers
from .models_dispatch import (  # noqa: F401
    ROLE_ALIASES,
    ROLE_REGISTRY,
    ROLE_WEIGHTS,
    RoleDefinition,
    get_all_role_ids,
    get_cli_role_list,
    get_core_roles,
    get_planned_roles,
    resolve_role_id,
)

# Lifecycle: execution plan, batches, anchor & retrospective
from .models_lifecycle import (  # noqa: F401
    AnchorResult,
    AnchorTrigger,
    BatchMode,
    DeviationRecord,
    DriftItem,
    DriftSeverity,
    ExecutionPlan,
    GoalItem,
    GoalItemStatus,
    RetrospectiveReport,
    ScheduleResult,
    StructuredGoal,
    TaskBatch,
)
