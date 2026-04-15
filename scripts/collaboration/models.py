#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
协作系统数据模型

定义 Coordinator + Scratchpad + Worker 协作模式的所有核心数据结构。

设计决策（门禁条件解决）：
- 门禁1: Scratchpad 并发写入 → 采用"时间戳排序+版本号"方案，简单可靠
- 门禁2: Consensus 升级 → 采用"权重投票+否决权+升级到人工"机制
- 门禁3: 存储选型 → Phase 1 采用内存+JSON文件持久化，无外部依赖
- 异常场景: 每个组件都有 timeout/retry/cancel 支持
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import uuid


class EntryType(Enum):
    FINDING = "finding"
    DECISION = "decision"
    CONFLICT = "conflict"
    QUESTION = "question"
    SUGGESTION = "suggestion"
    WARNING = "warning"


class EntryStatus(Enum):
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class ReferenceType(Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    CLARIFIES = "clarifies"


@dataclass
class Reference:
    reference_type: ReferenceType
    target_entry_id: str
    summary: str = ""


@dataclass
class ScratchpadEntry:
    entry_id: str = field(default_factory=lambda: f"entry-{uuid.uuid4().hex[:12]}")
    worker_id: str = ""
    role_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    entry_type: EntryType = EntryType.FINDING
    content: str = ""
    confidence: float = 0.5
    tags: List[str] = field(default_factory=list)
    references: List[Reference] = field(default_factory=list)
    status: EntryStatus = EntryStatus.ACTIVE
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "timestamp": self.timestamp.isoformat(),
            "entry_type": self.entry_type.value,
            "content": self.content,
            "confidence": self.confidence,
            "tags": self.tags,
            "references": [
                {"type": r.reference_type.value, "target": r.target_entry_id, "summary": r.summary}
                for r in self.references
            ],
            "status": self.status.value,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ScratchpadEntry":
        refs = [
            Reference(
                reference_type=ReferenceType(r["type"]),
                target_entry_id=r["target"],
                summary=r.get("summary", ""),
            )
            for r in data.get("references", [])
        ]
        return cls(
            entry_id=data.get("entry_id", f"entry-{uuid.uuid4().hex[:12]}"),
            worker_id=data.get("worker_id", ""),
            role_id=data.get("role_id", ""),
            timestamp=datetime.fromisoformat(data["timestamp"]) if "timestamp" in data else datetime.now(),
            entry_type=EntryType(data.get("entry_type", "finding")),
            content=data.get("content", ""),
            confidence=data.get("confidence", 0.5),
            tags=data.get("tags", []),
            references=refs,
            status=EntryStatus(data.get("status", "active")),
            version=data.get("version", 1),
        )


@dataclass
class TaskNotification:
    from_worker: str
    to_workers: List[str]
    notification_type: str
    priority: str = "medium"
    timestamp: datetime = field(default_factory=datetime.now)
    summary: str = ""
    details: str = ""
    references: List[str] = field(default_factory=list)
    action_required: str = ""

    def to_xml(self) -> str:
        refs_xml = "".join(f"<ref>{r}</ref>" for r in self.references)
        to_xml = ",".join(self.to_workers)
        return (
            f'<task-notification\n'
            f'    from-worker="{self.from_worker}"\n'
            f'    to-workers="{to_xml}"\n'
            f'    type="{self.notification_type}"\n'
            f'    priority="{self.priority}"\n'
            f'    timestamp="{self.timestamp.isoformat()}">\n'
            f'    <summary>{self.summary}</summary>\n'
            f'    <details>{self.details}</details>\n'
            f'    <references>{refs_xml}</references>\n'
            f'    <action-required>{self.action_required}</action-required>\n'
            f'</task-notification>'
        )


@dataclass
class TaskDefinition:
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    description: str = ""
    role_id: str = ""
    stage_id: Optional[str] = None
    input_data: Dict[str, Any] = field(default_factory=dict)
    dependencies: List[str] = field(default_factory=list)
    is_read_only: bool = True
    timeout_seconds: int = 300
    retry_count: int = 3


@dataclass
class WorkerResult:
    worker_id: str
    task_id: str
    success: bool
    output: Any = None
    error: Optional[str] = None
    scratchpad_entries_written: int = 0
    notifications_sent: int = 0
    duration_seconds: float = 0.0


@dataclass
class Vote:
    voter_id: str
    voter_role: str
    decision: bool
    reason: str = ""
    weight: float = 1.0
    confidence: float = 0.7
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DecisionProposal:
    proposal_id: str = field(default_factory=lambda: f"prop-{uuid.uuid4().hex[:8]}")
    topic: str = ""
    proposer_id: str = ""
    proposal_content: str = ""
    options: List[str] = field(default_factory=list)
    deadline: Optional[datetime] = None
    votes: List[Vote] = field(default_factory=list)
    status: str = "open"


class DecisionOutcome(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    SPLIT = "split"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"


@dataclass
class ConsensusRecord:
    record_id: str = field(default_factory=lambda: f"consensus-{uuid.uuid4().hex[:8]}")
    topic: str = ""
    outcome: DecisionOutcome = DecisionOutcome.APPROVED
    final_decision: str = ""
    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    total_weight_for: float = 0.0
    total_weight_against: float = 0.0
    participants: List[str] = field(default_factory=list)
    escalation_reason: Optional[str] = None
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionPlan:
    plan_id: str = field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    batches: List[Any] = field(default_factory=list)
    total_tasks: int = 0
    estimated_parallelism: float = 0.0


class BatchMode(Enum):
    PARALLEL = "parallel"
    SERIAL = "serial"


@dataclass
class TaskBatch:
    batch_id: str = field(default_factory=lambda: f"batch-{uuid.uuid4().hex[:8]}")
    mode: BatchMode = BatchMode.PARALLEL
    tasks: List[TaskDefinition] = field(default_factory=list)
    max_concurrency: int = 5
    dependencies: List[str] = field(default_factory=list)
    timeout_seconds: int = 600


@dataclass
class ScheduleResult:
    success: bool = False
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    results: List[WorkerResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


ROLE_WEIGHTS = {
    "architect": 1.5,
    "product-manager": 1.2,
    "tester": 1.0,
    "solo-coder": 1.0,
    "ui-designer": 0.9,
}

CONSENSUS_THRESHOLDS = {
    "simple_majority": 0.51,
    "super_majority": 0.67,
    "unanimous": 1.0,
}
