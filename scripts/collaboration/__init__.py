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
from .context_compressor import (
    ContextCompressor,
    Message,
    MemoryEntry,
    CompressedContext,
    CompressionLevel,
    MessageType,
    MemoryCategory,
)
from .permission_guard import (
    PermissionGuard,
    ProposedAction,
    PermissionRule,
    PermissionDecision as PermDecision,
    AuditEntry,
    PermissionLevel,
    ActionType,
    DecisionOutcome as PermOutcome,
)
from .skillifier import (
    Skillifier,
    ExecutionRecord,
    ExecutionStep,
    SuccessPattern,
    PatternStep,
    SkillProposal,
    SkillStepDef,
    ValidationResult as SkillValidationResult,
    ProposalStatus,
    SkillCategory,
)
from .warmup_manager import (
    WarmupManager,
    WarmupConfig,
    WarmupTask,
    WarmupResult,
    WarmupReport,
    CacheEntry,
    WarmupMetrics,
    WarmupLayer,
    WarmupStatus,
)
from .memory_bridge import (
    MemoryBridge,
    MemoryConfig as MemoryBridgeConfig,
    MemoryType,
    MemoryItem,
    MemoryQuery,
    MemoryRecallResult,
    MemoryStats,
    MemoryWriter,
    MemoryReader,
    MemoryIndexer,
    JsonMemoryStore,
    KnowledgeItem,
    UserFeedback,
    EpisodicMemory,
    PersistedPattern,
    AnalysisCase,
    ErrorContext,
)
from .dispatcher import (
    MultiAgentDispatcher,
    DispatchResult,
    create_dispatcher,
    quick_collaborate,
    ROLE_TEMPLATES,
)
from .test_quality_guard import (
    TestQualityGuard,
    TestQualityReport,
    QualityIssue,
    Severity,
    QualityScore,
    TestDimension,
    TestFunctionMeta,
    APISignature,
    APISignatureValidator,
    AntiPatternDetector,
    TestPurposeParser,
    quick_audit,
    project_audit,
)
from .prompt_assembler import (
    PromptAssembler,
    AssembledPrompt,
    TaskComplexity,
)
from .prompt_variant_generator import (
    PromptVariantGenerator,
    PromptVariant,
    VariantGenerationResult,
)
from .mce_adapter import (
    MCEAdapter,
    MCEResult,
    MCEStatus,
    get_global_mce_adapter,
)

__all__ = [
    "Scratchpad",
    "Worker",
    "WorkerFactory",
    "ConsensusEngine",
    "Coordinator",
    "BatchScheduler",
    "ContextCompressor",
    "PermissionGuard",
    "Skillifier",
    "Message",
    "MemoryEntry",
    "CompressedContext",
    "CompressionLevel",
    "MessageType",
    "MemoryCategory",
    "ProposedAction",
    "PermissionRule",
    "PermDecision",
    "AuditEntry",
    "PermissionLevel",
    "ActionType",
    "PermOutcome",
    "ExecutionRecord",
    "ExecutionStep",
    "SuccessPattern",
    "PatternStep",
    "SkillProposal",
    "SkillStepDef",
    "SkillValidationResult",
    "ProposalStatus",
    "SkillCategory",
    "WarmupManager",
    "WarmupConfig",
    "WarmupTask",
    "WarmupResult",
    "WarmupReport",
    "CacheEntry",
    "WarmupMetrics",
    "WarmupLayer",
    "WarmupStatus",
    "MemoryBridge",
    "MemoryBridgeConfig",
    "MemoryType",
    "MemoryItem",
    "MemoryQuery",
    "MemoryRecallResult",
    "MemoryStats",
    "MemoryWriter",
    "MemoryReader",
    "MemoryIndexer",
    "JsonMemoryStore",
    "KnowledgeItem",
    "UserFeedback",
    "EpisodicMemory",
    "PersistedPattern",
    "AnalysisCase",
    "ErrorContext",
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
    "ROLE_WEIGHTS",
    "CONSENSUS_THRESHOLDS",
    "MultiAgentDispatcher",
    "DispatchResult",
    "create_dispatcher",
    "quick_collaborate",
    "ROLE_TEMPLATES",
    "TestQualityGuard",
    "TestQualityReport",
    "QualityIssue",
    "Severity",
    "QualityScore",
    "TestDimension",
    "TestFunctionMeta",
    "APISignature",
    "APISignatureValidator",
    "AntiPatternDetector",
    "TestPurposeParser",
    "quick_audit",
    "project_audit",
    "PromptAssembler",
    "AssembledPrompt",
    "TaskComplexity",
    "PromptVariantGenerator",
    "PromptVariant",
    "VariantGenerationResult",
    "MCEAdapter",
    "MCEResult",
    "MCEStatus",
    "get_global_mce_adapter",
]
