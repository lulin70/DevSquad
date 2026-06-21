#!/usr/bin/env python3
"""
协作系统数据模型 — 共享基类、枚举与核心类型定义。

本模块包含 Scratchpad 条目、任务定义、Worker 结果以及共识投票等
最基础的数据结构，被 dispatch / lifecycle 等上层模块依赖。

设计决策：
- Scratchpad 并发写入 → 时间戳排序+版本号
- Consensus 升级 → 权重投票+否决权+升级到人工
- 异常场景: 每个组件都有 timeout/retry/cancel 支持
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class EntryType(Enum):
    """Scratchpad entry type classification.

    Defines the type of information stored in Scratchpad entries.
    Each type determines how entries are processed and displayed.

    Attributes:
        FINDING: Worker discovery or output (default type)
        DECISION: Consensus decision or agreement
        CONFLICT: Detected conflict between Workers
        QUESTION: Query or request for clarification
        SUGGESTION: Improvement proposal or recommendation
        WARNING: Alert or caution notice
    """
    FINDING = "finding"
    DECISION = "decision"
    CONFLICT = "conflict"
    QUESTION = "question"
    SUGGESTION = "suggestion"
    WARNING = "warning"


class EntryStatus(Enum):
    """Scratchpad entry lifecycle status.

    Tracks the processing state of Scratchpad entries through collaboration workflow.

    Attributes:
        ACTIVE: Entry is active and visible to Workers
        RESOLVED: Issue or conflict has been resolved
        SUPERSEDED: Entry replaced by newer version
        REJECTED: Entry invalidated or dismissed
    """
    ACTIVE = "active"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"
    REJECTED = "rejected"


class ReferenceType(Enum):
    """Reference relationship type between Scratchpad entries.

    Defines how one entry relates to another, enabling traceability and dependency tracking.

    Attributes:
        SUPPORTS: Entry provides supporting evidence
        CONTRADICTS: Entry conflicts with or refutes target
        EXTENDS: Entry builds upon or expands target
        CLARIFIES: Entry provides clarification for target
    """
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    EXTENDS = "extends"
    CLARIFIES = "clarifies"


@dataclass
class Reference:
    """Cross-reference link between Scratchpad entries.

    Establishes relationships between entries for traceability and context building.

    Attributes:
        reference_type: Type of relationship (supports/contradicts/extends/clarifies)
        target_entry_id: ID of the referenced entry
        summary: Brief description of the relationship (default: empty)
    """
    reference_type: ReferenceType
    target_entry_id: str
    summary: str = ""


@dataclass
class ScratchpadEntry:
    """Single entry in the shared Scratchpad.

    Represents one unit of information exchanged between Workers.
    Supports automatic ID generation, version tracking, and serialization.

    Attributes:
        entry_id: Unique identifier (auto-generated if not provided)
        worker_id: ID of the Worker who created this entry
        role_id: Role identifier of the creating Worker
        timestamp: Creation time (defaults to now)
        entry_type: Type classification (FINDING/DECISION/CONFLICT/etc.)
        content: Main text content of the entry
        confidence: Confidence level 0.0-1.0 (default: 0.5)
        tags: List of searchable tags for categorization
        references: List of cross-references to other entries
        status: Lifecycle status (ACTIVE/RESOLVED/SUPERSEDED/REJECTED)
        version: Version number for conflict resolution (auto-incremented)

    Example:
        >>> entry = ScratchpadEntry(
        ...     worker_id="arch-001",
        ...     role_id="architect",
        ...     entry_type=EntryType.FINDING,
        ...     content="建议使用微服务架构",
        ...     confidence=0.8,
        ... )
        >>> sp.write(entry)
    """
    entry_id: str = field(default_factory=lambda: f"entry-{uuid.uuid4().hex[:12]}")
    worker_id: str = ""
    role_id: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    entry_type: EntryType = EntryType.FINDING
    content: str = ""
    confidence: float = 0.5
    tags: list[str] = field(default_factory=list)
    references: list[Reference] = field(default_factory=list)
    status: EntryStatus = EntryStatus.ACTIVE
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize entry to dictionary for JSON persistence.

        Converts all fields to JSON-serializable format, including
        enum values and datetime objects.

        Returns:
            Dictionary with all entry fields in serializable format.
        """
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
    def from_dict(cls, data: dict[str, Any]) -> "ScratchpadEntry":
        """Deserialize entry from dictionary (JSON loaded).

        Reconstructs ScratchpadEntry from persisted dictionary data,
        handling enum conversion and datetime parsing.

        Args:
            data: Dictionary containing entry fields (from to_dict() or JSON)

        Returns:
            Reconstructed ScratchpadEntry instance with all fields restored.

        Example:
            >>> data = json.load(open("entry.json"))
            >>> entry = ScratchpadEntry.from_dict(data)
        """
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
    """Cross-Worker notification message.

    Enables asynchronous communication between Workers for coordination
    and information sharing outside the Scratchpad.

    Attributes:
        from_worker: Sender Worker ID
        to_workers: List of recipient Worker IDs
        notification_type: Type classification (e.g., "question", "alert")
        priority: Priority level (low/medium/high/critical, default: medium)
        timestamp: Creation time (defaults to now)
        summary: Brief summary of the notification
        details: Detailed content or context
        references: List of related entry IDs
        action_required: Description of required recipient action

    Example:
        >>> notification = TaskNotification(
        ...     from_worker="arch-001",
        ...     to_workers=["dev-001", "test-001"],
        ...     notification_type="question",
        ...     priority="high",
        ...     summary="需要确认数据库选型",
        ... )
    """
    from_worker: str
    to_workers: list[str]
    notification_type: str
    priority: str = "medium"
    timestamp: datetime = field(default_factory=datetime.now)
    summary: str = ""
    details: str = ""
    references: list[str] = field(default_factory=list)
    action_required: str = ""

    def to_xml(self) -> str:
        """Convert notification to XML format for structured exchange.

        Generates XML representation suitable for inter-system communication
        or logging with structured parsing support.

        Returns:
            XML string containing all notification fields.
        """
        refs_xml = "".join(f"<ref>{r}</ref>" for r in self.references)
        to_xml = ",".join(self.to_workers)
        return (
            f"<task-notification\n"
            f'    from-worker="{self.from_worker}"\n'
            f'    to-workers="{to_xml}"\n'
            f'    type="{self.notification_type}"\n'
            f'    priority="{self.priority}"\n'
            f'    timestamp="{self.timestamp.isoformat()}">\n'
            f"    <summary>{self.summary}</summary>\n"
            f"    <details>{self.details}</details>\n"
            f"    <references>{refs_xml}</references>\n"
            f"    <action-required>{self.action_required}</action-required>\n"
            f"</task-notification>"
        )


@dataclass
class TaskDefinition:
    """Definition of a task to be executed by a Worker.

    Encapsulates all information needed for a Worker to understand and
    execute its assigned work, including role context and constraints.

    Attributes:
        task_id: Unique task identifier (auto-generated)
        description: Human-readable task description
        role_id: Target role ID for this task
        role_prompt: System prompt/instructions for the role
        stage_id: Workflow stage identifier (optional, for multi-phase tasks)
        input_data: Additional context data as key-value pairs
        dependencies: List of prerequisite task IDs
        is_read_only: Whether task only reads (no side effects, default: True)
        timeout_seconds: Maximum execution time in seconds (default: 300)
        retry_count: Number of retry attempts on failure (default: 3)

    Example:
        >>> task = TaskDefinition(
        ...     description="设计用户认证模块",
        ...     role_id="architect",
        ...     stage_id="phase1",
        ... )
    """
    task_id: str = field(default_factory=lambda: f"task-{uuid.uuid4().hex[:8]}")
    description: str = ""
    role_id: str = ""
    role_prompt: str = ""
    stage_id: str | None = None
    input_data: dict[str, Any] = field(default_factory=dict)
    dependencies: list[str] = field(default_factory=list)
    is_read_only: bool = True
    timeout_seconds: int = 300
    retry_count: int = 3


@dataclass
class WorkerResult:
    """Result returned by a Worker after task execution.

    Contains execution outcome, output data, and performance metrics
    for Coordinator to collect and process.

    Attributes:
        worker_id: ID of the executing Worker
        task_id: ID of the completed task
        success: Whether execution succeeded without exceptions
        output: Output content (dict with findings, summary, etc.)
        error: Error message string (on failure only)
        scratchpad_entries_written: Number of Scratchpad entries created
        notifications_sent: Number of notifications dispatched
        duration_seconds: Wall-clock execution time in seconds

    Example:
        >>> result = WorkerResult(
        ...     worker_id="arch-001",
        ...     task_id="task-abc123",
        ...     success=True,
        ...     output={"finding_summary": "建议使用微服务架构"},
        ...     duration_seconds=2.5,
        ... )
    """
    worker_id: str
    task_id: str
    success: bool
    output: Any = None
    error: str | None = None
    scratchpad_entries_written: int = 0
    notifications_sent: int = 0
    duration_seconds: float = 0.0


@dataclass
class Vote:
    """Single vote in consensus decision-making.

    Represents one Worker's position on a proposal, including
    weighted influence based on role importance.

    Attributes:
        voter_id: ID of the voting Worker
        voter_role: Role identifier of the voter (determines weight)
        decision: Vote direction (True=approve, False=reject)
        reason: Explanation for the vote decision
        weight: Voting weight (role-based, e.g., architect=1.5, default=1.0)
        confidence: Voter's confidence level 0.0-1.0 (default: 0.7)
        timestamp: Time when vote was cast (defaults to now)

    Example:
        >>> vote = Vote(
        ...     voter_id="arch-001",
        ...     voter_role="architect",
        ...     decision=True,
        ...     reason="方案符合架构最佳实践",
        ...     weight=1.5,
        ... )
    """
    voter_id: str
    voter_role: str
    decision: bool
    reason: str = ""
    weight: float = 1.0
    confidence: float = 0.7
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class DecisionProposal:
    """Proposal subject to consensus voting.

    Represents a decision topic that requires multi-Worker agreement
    through the ConsensusEngine's weighted voting mechanism.

    Attributes:
        proposal_id: Unique identifier (auto-generated)
        topic: Short title or subject of the proposal
        proposer_id: ID of the entity creating the proposal (usually Coordinator)
        proposal_content: Detailed description of what is being proposed
        options: List of voting options (default: ["approve", "reject"])
        deadline: Voting deadline (optional, reserved for future use)
        votes: List of cast votes (accumulated during voting phase)
        status: Current status ("open", "closed", "cancelled")

    Example:
        >>> proposal = DecisionProposal(
        ...     topic="技术选型决策",
        ...     proposer_id="coord-001",
        ...     proposal_content="建议采用 PostgreSQL 作为主数据库",
        ...     options=["PostgreSQL", "MySQL", "MongoDB"],
        ... )
    """
    proposal_id: str = field(default_factory=lambda: f"prop-{uuid.uuid4().hex[:8]}")
    topic: str = ""
    proposer_id: str = ""
    proposal_content: str = ""
    options: list[str] = field(default_factory=list)
    deadline: datetime | None = None
    votes: list[Vote] = field(default_factory=list)
    status: str = "open"


class DecisionOutcome(Enum):
    """Possible outcomes of consensus decision-making.

    Determines the final resolution after all votes are counted
    and thresholds are evaluated by ConsensusEngine.

    Attributes:
        APPROVED: Proposal passed all threshold requirements
        REJECTED: Proposal failed to meet minimum thresholds
        SPLIT: Votes too evenly divided (40-60% range), needs discussion
        ESCALATED: Veto detected or irreconcilable conflict, needs human intervention
        TIMEOUT: No votes cast within deadline, auto-resolved
    """
    APPROVED = "approved"
    REJECTED = "rejected"
    SPLIT = "split"
    ESCALATED = "escalated"
    TIMEOUT = "timeout"


@dataclass
class ConsensusRecord:
    """Permanent record of a consensus decision outcome.

    Created by ConsensusEngine.reach_consensus() and stored for
    audit trail and future reference.

    Attributes:
        record_id: Unique identifier (auto-generated)
        topic: Subject of the decision
        outcome: Final decision outcome (APPROVED/REJECTED/SPLIT/ESCALATED/TIMEOUT)
        final_decision: Human-readable summary of the decision
        votes_for: Number of approving votes
        votes_against: Number of rejecting votes
        votes_abstain: Number of abstentions (no vote or neutral)
        total_weight_for: Sum of weights from approving votes
        total_weight_against: Sum of absolute weights from veto/rejecting votes
        participants: List of participant Worker IDs
        escalation_reason: Reason for ESCALATED outcome (if applicable)
        timestamp: Time when consensus was reached

    Example:
        >>> record = ConsensusRecord(
        ...     topic="数据库选型",
        ...     outcome=DecisionOutcome.APPROVED,
        ...     final_decision="采用 PostgreSQL",
        ... )
    """
    record_id: str = field(default_factory=lambda: f"consensus-{uuid.uuid4().hex[:8]}")
    topic: str = ""
    outcome: DecisionOutcome = DecisionOutcome.APPROVED
    final_decision: str = ""
    votes_for: int = 0
    votes_against: int = 0
    votes_abstain: int = 0
    total_weight_for: float = 0.0
    total_weight_against: float = 0.0
    participants: list[str] = field(default_factory=list)
    escalation_reason: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


CONSENSUS_THRESHOLDS = {
    "simple_majority": 0.51,
    "super_majority": 0.67,
    "unanimous": 1.0,
}
"""Consensus approval thresholds for different decision levels.

- simple_majority (0.51): Minimum for basic decisions
- super_majority (0.67): Required for important architectural choices
- unanimous (1.0): Full agreement needed for critical security decisions
"""
