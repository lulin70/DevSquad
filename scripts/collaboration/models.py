#!/usr/bin/env python3
"""
协作系统数据模型

定义 Coordinator + Scratchpad + Worker 协作模式的所有核心数据结构。

设计决策（门禁条件解决）：
- 门禁1: Scratchpad 并发写入 → 采用"时间戳排序+版本号"方案，简单可靠
- 门禁2: Consensus 升级 → 采用"权重投票+否决权+升级到人工"机制
- 门禁3: 存储选型 → Phase 1 采用内存+JSON文件持久化，无外部依赖
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


@dataclass
class ExecutionPlan:
    """Complete execution plan generated by Coordinator.plan_task().

    Contains all task batches with scheduling information for
    BatchScheduler to execute.

    Attributes:
        plan_id: Unique plan identifier (auto-generated)
        batches: List of TaskBatch objects (parallel/sequential groups)
        total_tasks: Total number of tasks across all batches
        estimated_parallelism: Estimated parallelism level 0.0-1.0

    Example:
        >>> plan = ExecutionPlan(
        ...     batches=[parallel_batch],
        ...     total_tasks=3,
        ...     estimated_parallelism=1.0,
        ... )
    """
    plan_id: str = field(default_factory=lambda: f"plan-{uuid.uuid4().hex[:8]}")
    batches: list[Any] = field(default_factory=list)
    total_tasks: int = 0
    estimated_parallelism: float = 0.0


class BatchMode(Enum):
    """Task batch execution mode.

    Determines how tasks within a batch are executed by BatchScheduler.

    Attributes:
        PARALLEL: Execute all tasks concurrently (up to max_concurrency)
        SERIAL: Execute tasks one-by-one in order with retry support
    """
    PARALLEL = "parallel"
    SERIAL = "serial"


@dataclass
class TaskBatch:
    """Group of tasks to be executed together.

    Batches are the scheduling unit in ExecutionPlan. Each batch
    has a mode (PARALLEL/SERIAL) and contains related TaskDefinitions.

    Attributes:
        batch_id: Unique batch identifier (auto-generated)
        mode: Execution mode (PARALLEL or SERIAL)
        tasks: List of task definitions in this batch
        max_concurrency: Max parallel tasks for PARALLEL mode (default: 5)
        dependencies: List of prerequisite batch IDs that must complete first
        timeout_seconds: Maximum execution time for entire batch (default: 600)

    Example:
        >>> batch = TaskBatch(
        ...     mode=BatchMode.PARALLEL,
        ...     tasks=[task1, task2, task3],
        ...     max_concurrency=3,
        ... )
    """
    batch_id: str = field(default_factory=lambda: f"batch-{uuid.uuid4().hex[:8]}")
    mode: BatchMode = BatchMode.PARALLEL
    tasks: list[TaskDefinition] = field(default_factory=list)
    max_concurrency: int = 5
    dependencies: list[str] = field(default_factory=list)
    timeout_seconds: int = 600


@dataclass
class ScheduleResult:
    """Result of batch execution by BatchScheduler.

    Contains aggregated results from all batches, including
    success/failure counts and individual Worker results.

    Attributes:
        success: Whether all batches completed without errors
        total_tasks: Total number of tasks across all batches
        completed_tasks: Number of successfully completed tasks
        failed_tasks: Number of failed tasks
        results: List of WorkerResult objects from all Workers
        duration_seconds: Total wall-clock execution time
        errors: List of error messages from failed tasks

    Example:
        >>> result = ScheduleResult(
        ...     success=True,
        ...     total_tasks=3,
        ...     completed_tasks=3,
        ...     failed_tasks=0,
        ...     duration_seconds=5.2,
        ... )
    """
    success: bool = False
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    results: list[WorkerResult] = field(default_factory=list)
    duration_seconds: float = 0.0
    errors: list[str] = field(default_factory=list)


ROLE_WEIGHTS = {
    "architect": 1.5,
    "product-manager": 1.2,
    "security": 1.1,
    "tester": 1.0,
    "solo-coder": 1.0,
    "devops": 1.0,
    "ui-designer": 0.9,
}
"""Default voting weights by role for consensus decisions.

Higher weight means more influence in consensus voting.
Architect has highest weight (1.5) due to technical decision importance.
"""


@dataclass
class RoleDefinition:
    """Complete definition of a collaboration role.

    Contains all metadata needed for role matching, prompt generation,
    and Worker creation in the multi-agent system.

    Attributes:
        role_id: Unique identifier (e.g., "architect", "tester")
        name: Human-readable display name (e.g., "架构师")
        aliases: Alternative identifiers or abbreviations (e.g., ["arch"])
        prompt: System prompt / instruction template for this role
        keywords: List of keywords for automatic role matching
        weight: Default voting weight in consensus (e.g., 1.5 for architect)
        description: Short description of the role's responsibilities
        status: Role status ("core"=active, "planned"=future)

    Example:
        >>> role = RoleDefinition(
        ...     role_id="architect",
        ...     name="架构师",
        ...     aliases=["arch"],
        ...     prompt="你是系统架构师...",
        ...     keywords=["架构", "设计"],
        ...     weight=1.5,
        ... )
    """
    role_id: str
    name: str
    aliases: list[str]
    prompt: str
    keywords: list[str]
    weight: float
    description: str
    status: str = "core"


ROLE_REGISTRY: dict[str, RoleDefinition] = {
    "architect": RoleDefinition(
        role_id="architect",
        name="架构师",
        aliases=["arch"],
        prompt="你是系统架构师。负责：\n1. 系统架构设计（分层、模块化、接口定义）\n2. 技术选型和评估\n3. 性能架构设计（缓存架构、CDN策略、分库分表方案）\n4. 安全架构设计（认证授权方案、加密策略、安全边界）\n5. 数据架构设计（数据模型、数据仓库架构、ETL架构）\n6. 输出：架构文档、技术方案、模块设计",
        keywords=[
            "架构",
            "设计",
            "选型",
            "性能",
            "模块",
            "接口",
            "微服务",
            "数据架构",
            "architecture",
            "design",
            "microservice",
            "module",
            "interface",
            "performance",
            "scalability",
            "system",
        ],
        weight=1.5,
        description="System design, tech stack, API design, performance/security/data architecture",
        status="core",
    ),
    "product-manager": RoleDefinition(
        role_id="product-manager",
        name="产品经理",
        aliases=["pm"],
        prompt="你是产品经理。负责：\n1. 需求分析和PRD编写\n2. 用户故事和验收标准\n3. 竞品分析\n4. 输出：需求文档、用户故事、功能规格",
        keywords=[
            "需求",
            "PRD",
            "用户故事",
            "竞品",
            "验收",
            "体验",
            "功能",
            "requirement",
            "prd",
            "user story",
            "acceptance",
            "feature",
            "product",
            "specification",
        ],
        weight=1.2,
        description="Requirements analysis, user stories, acceptance criteria",
        status="core",
    ),
    "tester": RoleDefinition(
        role_id="tester",
        name="测试专家",
        aliases=["test", "qa"],
        prompt="你是测试专家。负责：\n1. 测试策略和用例设计\n2. 自动化测试方案\n3. 质量评估和缺陷追踪\n4. 输出：测试计划、测试用例、质量报告",
        keywords=[
            "测试",
            "质量",
            "验收",
            "自动化",
            "性能测试",
            "缺陷",
            "门禁",
            "test",
            "quality",
            "qa",
            "automated",
            "coverage",
            "bug",
            "validation",
        ],
        weight=1.0,
        description="Test strategy, quality assurance, edge cases",
        status="core",
    ),
    "solo-coder": RoleDefinition(
        role_id="solo-coder",
        name="独立开发者",
        aliases=["coder", "dev"],
        prompt="你是全栈开发者。负责：\n1. 功能实现和代码编写\n2. 代码审查与质量把关（风格一致性、最佳实践、设计模式合规）\n3. 性能优化实现（算法优化、内存优化、并发优化、SQL调优）\n4. 代码重构和优化\n5. Bug修复\n6. 数据迁移实现\n7. 输出：源代码、测试、技术文档",
        keywords=[
            "实现",
            "开发",
            "代码",
            "修复",
            "优化",
            "重构",
            "审查",
            "最佳实践",
            "implement",
            "develop",
            "code",
            "fix",
            "optimize",
            "refactor",
            "review",
            "debug",
        ],
        weight=1.0,
        description="Implementation, code review, performance optimization, refactoring",
        status="core",
    ),
    "ui-designer": RoleDefinition(
        role_id="ui-designer",
        name="UI设计师",
        aliases=["ui"],
        prompt="你是UI/UX设计师。负责：\n1. 界面设计和交互原型\n2. 设计系统和组件规范\n3. 视觉稿和设计交付\n4. 输出：设计稿、原型、设计规范",
        keywords=[
            "UI",
            "界面",
            "前端",
            "视觉",
            "交互",
            "原型",
            "设计",
            "ui",
            "interface",
            "frontend",
            "visual",
            "interaction",
            "prototype",
            "ux",
            "accessibility",
        ],
        weight=0.9,
        description="UX design, interaction logic, accessibility",
        status="core",
    ),
    "devops": RoleDefinition(
        role_id="devops",
        name="DevOps工程师",
        aliases=["infra"],
        prompt="你是DevOps工程师。负责：\n1. CI/CD流水线设计与实现（GitHub Actions、GitLab CI、Jenkins）\n2. 容器化与编排（Docker、Kubernetes、Docker Compose）\n3. 基础设施即代码（Terraform、Pulumi、CloudFormation）\n4. 监控告警体系搭建（Prometheus、Grafana、ELK、Sentry）\n5. 部署策略设计（蓝绿部署、金丝雀发布、滚动更新）\n6. 环境管理（开发/测试/预生产/生产环境配置与隔离）\n7. 输出：CI/CD配置、Dockerfile、K8s Manifests、监控配置、部署文档",
        keywords=[
            "CI/CD",
            "部署",
            "监控",
            "运维",
            "Docker",
            "Kubernetes",
            "基础设施",
            "容器",
            "deploy",
            "monitor",
            "infrastructure",
            "container",
            "pipeline",
            "devops",
            "ci/cd",
            "cloud",
        ],
        weight=1.0,
        description="CI/CD pipeline, containerization, monitoring, infrastructure",
        status="core",
    ),
    "security": RoleDefinition(
        role_id="security",
        name="安全专家",
        aliases=["sec"],
        prompt="你是安全专家。负责：\n1. 威胁建模（STRIDE、DREAD攻击树分析）\n2. 漏洞审计（OWASP Top 10、CWE常见弱点枚举）\n3. 认证与授权安全审查（OAuth2、JWT、RBAC/ABAC）\n4. 数据安全评估（加密方案、密钥管理、数据脱敏）\n5. 依赖安全扫描与供应链安全（Snyk、Dependabot、SBOM）\n6. 合规性检查（GDPR、SOC2、HIPAA、PCI-DSS）\n7. 安全编码规范与最佳实践\n8. 输出：威胁模型、漏洞报告、安全建议、合规评估",
        keywords=[
            "安全",
            "漏洞",
            "审计",
            "威胁",
            "加密",
            "认证",
            "授权",
            "OWASP",
            "security",
            "vulnerability",
            "audit",
            "threat",
            "encrypt",
            "auth",
            "compliance",
            "owasp",
        ],
        weight=1.1,
        description="Threat modeling, vulnerability audit, compliance, security review",
        status="core",
    ),
}


def _build_role_aliases() -> dict[str, str]:
    aliases = {}
    for rid, rdef in ROLE_REGISTRY.items():
        for alias in rdef.aliases:
            aliases[alias] = rid
    return aliases


ROLE_ALIASES: dict[str, str] = _build_role_aliases()


def resolve_role_id(role_id: str) -> str:
    """Resolve role identifier to canonical form.

    Converts aliases or abbreviations to the canonical role_id.
    If the input is already a valid role_id, returns it unchanged.
    Otherwise returns the input as-is (for custom/unknown roles).

    Args:
        role_id: Role identifier or alias to resolve (e.g., "arch", "architect")

    Returns:
        Canonical role_id string (e.g., "architect")

    Example:
        >>> resolve_role_id("arch")
        'architect'
        >>> resolve_role_id("unknown-role")
        'unknown-role'
    """
    if role_id in ROLE_REGISTRY:
        return role_id
    return ROLE_ALIASES.get(role_id, role_id)


def get_core_roles() -> dict[str, RoleDefinition]:
    """Get all core (active) role definitions.

    Filters ROLE_REGISTRY to return only roles with status="core".

    Returns:
        Dictionary mapping role_id to RoleDefinition for active roles.
    """
    return {rid: rdef for rid, rdef in ROLE_REGISTRY.items() if rdef.status == "core"}


def get_planned_roles() -> dict[str, RoleDefinition]:
    """Get all planned (future) role definitions.

    Filters ROLE_REGISTRY to return only roles with status="planned".
    These roles are defined but not yet fully implemented.

    Returns:
        Dictionary mapping role_id to RoleDefinition for planned roles.
    """
    return {rid: rdef for rid, rdef in ROLE_REGISTRY.items() if rdef.status == "planned"}


def get_all_role_ids() -> list[str]:
    """Get list of all registered role IDs.

    Returns:
        Sorted list of all role identifiers in registry.
    """
    return list(ROLE_REGISTRY.keys())


def get_cli_role_list() -> list[str]:
    """Get role list formatted for CLI display.

    Returns primary alias (first in list) for each role,
    suitable for command-line argument completion.

    Returns:
        List of short role identifiers/aliases for CLI use.
    """
    result = []
    for rid, rdef in ROLE_REGISTRY.items():
        result.append(rdef.aliases[0] if rdef.aliases else rid)
    return result


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


# ============================================================
# V3.7.0 "Anchor & Retrospect" Data Models
# ============================================================


class GoalItemStatus(Enum):
    """Coverage status of a goal item in retrospective analysis.

    Tracks how well each goal item was addressed during task execution.

    Attributes:
        PENDING: Goal item not yet addressed
        PARTIALLY_COVERED: Some progress made but incomplete
        FULLY_COVERED: Goal item completely satisfied
        EXCEEDED: Goal exceeded expectations
    """
    PENDING = "pending"
    PARTIALLY_COVERED = "partially_covered"
    FULLY_COVERED = "fully_covered"
    EXCEEDED = "exceeded"


class AnchorTrigger(Enum):
    """Events that trigger anchor checking.

    Defines when the AnchorChecker should verify alignment with goals.

    Attributes:
        STEP_COMPLETE: After each major step finishes
        PHASE_GATE: At phase transition points
        DIRECTION_CHANGE: When execution direction changes significantly
        CONFLICT: When conflict is detected between Workers
        MILESTONE: At predefined milestone markers
    """
    STEP_COMPLETE = "step_complete"
    PHASE_GATE = "phase_gate"
    DIRECTION_CHANGE = "direction_change"
    CONFLICT = "conflict"
    MILESTONE = "milestone"


class DriftSeverity(Enum):
    """Severity level of goal drift detection.

    Categorizes how much execution has deviated from original goals.

    Attributes:
        NONE: No drift detected (perfect alignment)
        LOW: Minor deviation, within acceptable tolerance
        MEDIUM: Moderate drift, may need attention
        HIGH: Significant drift, corrective action recommended
        CRITICAL: Severe drift, immediate intervention required
    """
    NONE = "none"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GoalItem:
    """Individual item within a structured goal.

    Represents one specific objective to be tracked and measured
    for coverage during task execution.

    Attributes:
        item_id: Unique identifier for this goal item
        description: Human-readable description of the goal
        keywords: List of keywords for automatic matching (default: empty)
        status: Current coverage status (default: PENDING)
        coverage_score: Coverage level 0.0-1.0 (default: 0.0)
        evidence: List of evidence strings proving coverage (default: empty)
    """
    item_id: str
    description: str
    keywords: list[str] = field(default_factory=list)
    status: GoalItemStatus = GoalItemStatus.PENDING
    coverage_score: float = 0.0
    evidence: list[str] = field(default_factory=list)


@dataclass
class StructuredGoal:
    """Structured goal with multiple trackable items.

    Represents a high-level goal decomposed into measurable items
    for anchor checking and retrospective analysis.

    Attributes:
        goal_id: Unique identifier for this goal
        original_description: Original user-provided goal description
        items: List of GoalItem objects to track (default: empty)
        created_at: ISO format timestamp of creation

    Properties:
        overall_coverage: Average coverage across all items (0.0-1.0)
        uncovered_items: List of items not yet fully covered
    """
    goal_id: str = ""
    original_description: str = ""
    items: list[GoalItem] = field(default_factory=list)
    created_at: str = ""

    @property
    def overall_coverage(self) -> float:
        """Calculate average coverage score across all goal items.

        Returns:
            Float from 0.0 (no coverage) to 1.0 (fully covered).
            Returns 0.0 if no items exist.
        """
        if not self.items:
            return 0.0
        return sum(i.coverage_score for i in self.items) / len(self.items)

    @property
    def uncovered_items(self) -> list[GoalItem]:
        """Get list of goal items that are not yet fully covered.

        Returns items with PENDING or PARTIALLY_COVERED status.

        Returns:
            List of GoalItem objects needing more work.
        """
        return [i for i in self.items if i.status in (GoalItemStatus.PENDING, GoalItemStatus.PARTIALLY_COVERED)]


@dataclass
class DriftItem:
    """Single drift detection result.

    Describes one instance of goal misalignment detected during
    anchor checking.

    Attributes:
        content: Description of the detected drift
        severity: Severity level (default: LOW)
        reason: Explanation of why this is considered drift
    """
    content: str
    severity: DriftSeverity = DriftSeverity.LOW
    reason: str = ""


@dataclass
class AnchorResult:
    """Result of an anchor check (goal alignment verification).

    Produced by AnchorChecker to verify that execution remains
    aligned with the original structured goal.

    Attributes:
        aligned: Whether execution is aligned with goals (default: True)
        trigger: What event triggered this anchor check (default: STEP_COMPLETE)
        coverage: Current goal coverage level 0.0-1.0 (default: 1.0)
        drift_score: Accumulated drift score (higher = more misalignment, default: 0.0)
        drifts: List of detected drift items (default: empty)
        uncovered_goals: List of goal item IDs not yet covered (default: empty)
        recommendation: Suggested corrective action (default: empty)
        checked_at: ISO format timestamp when check was performed

    Properties:
        severity: Computed DriftSeverity based on drift_score threshold
    """
    aligned: bool = True
    trigger: AnchorTrigger = AnchorTrigger.STEP_COMPLETE
    coverage: float = 1.0
    drift_score: float = 0.0
    drifts: list[DriftItem] = field(default_factory=list)
    uncovered_goals: list[str] = field(default_factory=list)
    recommendation: str = ""
    checked_at: str = ""

    @property
    def severity(self) -> DriftSeverity:
        """Compute drift severity from drift score.

        Maps numeric drift score to categorical severity:
        - < 0.1: NONE (perfect alignment)
        - < 0.2: LOW (minor deviation)
        - < 0.3: MEDIUM (moderate concern)
        - < 0.5: HIGH (significant issue)
        - >= 0.5: CRITICAL (urgent action needed)

        Returns:
            DriftSeverity enum value representing current drift level.
        """
        if self.drift_score < 0.1:
            return DriftSeverity.NONE
        elif self.drift_score < 0.2:
            return DriftSeverity.LOW
        elif self.drift_score < 0.3:
            return DriftSeverity.MEDIUM
        elif self.drift_score < 0.5:
            return DriftSeverity.HIGH
        return DriftSeverity.CRITICAL


@dataclass
class DeviationRecord:
    """Single deviation from original plan detected in retrospective.

    Records one instance where execution diverged from the expected path,
    with optional impact analysis and corrective suggestions.

    Attributes:
        step_description: Description of the step where deviation occurred
        deviation_type: Category of deviation (e.g., "scope_creep", "technical_debt")
        reason: Explanation of why the deviation happened
        impact: Assessment of the deviation's effect (default: empty)
        suggestion: Recommended corrective action (default: empty)
    """
    step_description: str
    deviation_type: str
    reason: str
    impact: str = ""
    suggestion: str = ""


@dataclass
class RetrospectiveReport:
    """Comprehensive retrospective analysis report.

    Generated by RetrospectiveEngine after task completion to capture
    lessons learned, deviations, and improvement opportunities.

    Attributes:
        task_goal: Original goal description
        goal_id: Associated structured goal ID
        deviations: List of detected deviations from plan (default: empty)
        redundant_steps: List of steps identified as redundant (default: empty)
        improvements: List of suggested improvements for next time (default: empty)
        anchor_check_count: Total number of anchor checks performed
        anchor_drift_count: Number of anchor checks that detected drift
        final_coverage: Final goal coverage score 0.0-1.0 (default: 1.0)
        summary: Executive summary of the retrospective (default: empty)
        created_at: ISO format timestamp of report creation

    Methods:
        to_dict(): Convert report to dictionary for JSON serialization
        to_markdown(): Generate Markdown formatted report for display
    """
    task_goal: str = ""
    goal_id: str = ""
    deviations: list[DeviationRecord] = field(default_factory=list)
    redundant_steps: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    anchor_check_count: int = 0
    anchor_drift_count: int = 0
    final_coverage: float = 1.0
    summary: str = ""
    created_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert report to dictionary for JSON serialization.

        Returns summary statistics rather than full details for compactness.

        Returns:
            Dictionary with key metrics and metadata.
        """
        return {
            "task_goal": self.task_goal,
            "goal_id": self.goal_id,
            "deviation_count": len(self.deviations),
            "redundant_step_count": len(self.redundant_steps),
            "improvement_count": len(self.improvements),
            "anchor_check_count": self.anchor_check_count,
            "anchor_drift_count": self.anchor_drift_count,
            "final_coverage": self.final_coverage,
            "summary": self.summary,
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        """Generate Markdown formatted report for display.

        Creates a human-readable Markdown document with sections for
        task info, deviations, and improvements.

        Returns:
            Multi-line string in Markdown format ready for rendering.
        """
        lines = [
            "# Retrospective Report",
            "",
            f"**Task**: {self.task_goal}",
            f"**Goal ID**: {self.goal_id}",
            f"**Final Coverage**: {self.final_coverage:.0%}",
            f"**Anchor Checks**: {self.anchor_check_count} (drifts: {self.anchor_drift_count})",
            "",
        ]
        if self.deviations:
            lines.append("## Deviations")
            for d in self.deviations:
                lines.append(f"- **{d.deviation_type}**: {d.reason}")
                if d.suggestion:
                    lines.append(f"  → {d.suggestion}")
            lines.append("")
        if self.improvements:
            lines.append("## Improvements for Next Time")
            for imp in self.improvements:
                lines.append(f"- {imp}")
            lines.append("")
        lines.append("---\n*Generated by RetrospectiveEngine V3.7.0*")
        return "\n".join(lines)
