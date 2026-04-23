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


@dataclass
class RoleDefinition:
    role_id: str
    name: str
    aliases: List[str]
    prompt: str
    keywords: List[str]
    weight: float
    description: str
    status: str = "core"


ROLE_REGISTRY: Dict[str, RoleDefinition] = {
    "architect": RoleDefinition(
        role_id="architect",
        name="架构师",
        aliases=["arch"],
        prompt="你是系统架构师。负责：\n1. 系统架构设计（分层、模块化、接口定义）\n2. 技术选型和评估\n3. 性能、安全、可扩展性设计\n4. 输出：架构文档、技术方案、模块设计",
        keywords=["架构", "设计", "选型", "性能", "模块", "接口", "部署", "微服务"],
        weight=1.5,
        description="System design, tech stack decisions, API design",
        status="core",
    ),
    "product-manager": RoleDefinition(
        role_id="product-manager",
        name="产品经理",
        aliases=["pm"],
        prompt="你是产品经理。负责：\n1. 需求分析和PRD编写\n2. 用户故事和验收标准\n3. 竞品分析\n4. 输出：需求文档、用户故事、功能规格",
        keywords=["需求", "PRD", "用户故事", "竞品", "验收", "体验", "功能"],
        weight=1.2,
        description="Requirements analysis, user stories, acceptance criteria",
        status="core",
    ),
    "tester": RoleDefinition(
        role_id="tester",
        name="测试专家",
        aliases=["test", "qa"],
        prompt="你是测试专家。负责：\n1. 测试策略和用例设计\n2. 自动化测试方案\n3. 质量评估和缺陷追踪\n4. 输出：测试计划、测试用例、质量报告",
        keywords=["测试", "质量", "验收", "自动化", "性能测试", "缺陷", "门禁"],
        weight=1.0,
        description="Test strategy, quality assurance, edge cases",
        status="core",
    ),
    "solo-coder": RoleDefinition(
        role_id="solo-coder",
        name="独立开发者",
        aliases=["coder", "dev"],
        prompt="你是全栈开发者。负责：\n1. 功能实现和代码编写\n2. 单元测试和文档\n3. 代码重构和优化\n4. Bug修复\n5. 输出：源代码、测试、技术文档",
        keywords=["实现", "开发", "代码", "修复", "优化", "重构", "单元测试"],
        weight=1.0,
        description="Implementation, code generation, refactoring",
        status="core",
    ),
    "ui-designer": RoleDefinition(
        role_id="ui-designer",
        name="UI设计师",
        aliases=["ui"],
        prompt="你是UI/UX设计师。负责：\n1. 界面设计和交互原型\n2. 设计系统和组件规范\n3. 视觉稿和设计交付\n4. 输出：设计稿、原型、设计规范",
        keywords=["UI", "界面", "前端", "视觉", "交互", "原型", "设计"],
        weight=0.9,
        description="UX design, interaction logic, accessibility",
        status="core",
    ),
    "devops": RoleDefinition(
        role_id="devops",
        name="DevOps工程师",
        aliases=[],
        prompt="",
        keywords=["CI/CD", "部署", "监控", "运维", "Docker", "Kubernetes", "基础设施"],
        weight=1.0,
        description="CI/CD, deployment, infrastructure",
        status="planned",
    ),
    "security": RoleDefinition(
        role_id="security",
        name="安全专家",
        aliases=[],
        prompt="",
        keywords=["安全", "漏洞", "审计", "威胁", "加密", "认证", "授权"],
        weight=1.1,
        description="Security audit, vulnerability assessment",
        status="planned",
    ),
    "data": RoleDefinition(
        role_id="data",
        name="数据工程师",
        aliases=[],
        prompt="",
        keywords=["数据", "ETL", "分析", "建模", "迁移", "SQL", "数据仓库"],
        weight=0.9,
        description="Data modeling, analytics, migrations",
        status="planned",
    ),
    "reviewer": RoleDefinition(
        role_id="reviewer",
        name="代码审查员",
        aliases=[],
        prompt="",
        keywords=["审查", "规范", "最佳实践", "代码质量", "重构", "风格"],
        weight=1.0,
        description="Code review, best practices, standards",
        status="planned",
    ),
    "optimizer": RoleDefinition(
        role_id="optimizer",
        name="性能优化师",
        aliases=[],
        prompt="",
        keywords=["性能", "优化", "缓存", "延迟", "吞吐", "瓶颈", "分析"],
        weight=1.0,
        description="Performance optimization, caching, profiling",
        status="planned",
    ),
}


def _build_role_aliases() -> Dict[str, str]:
    aliases = {}
    for rid, rdef in ROLE_REGISTRY.items():
        for alias in rdef.aliases:
            aliases[alias] = rid
    return aliases


ROLE_ALIASES: Dict[str, str] = _build_role_aliases()


def resolve_role_id(role_id: str) -> str:
    if role_id in ROLE_REGISTRY:
        return role_id
    return ROLE_ALIASES.get(role_id, role_id)


def get_core_roles() -> Dict[str, RoleDefinition]:
    return {rid: rdef for rid, rdef in ROLE_REGISTRY.items() if rdef.status == "core"}


def get_planned_roles() -> Dict[str, RoleDefinition]:
    return {rid: rdef for rid, rdef in ROLE_REGISTRY.items() if rdef.status == "planned"}


def get_all_role_ids() -> List[str]:
    return list(ROLE_REGISTRY.keys())


def get_cli_role_list() -> List[str]:
    result = []
    for rid, rdef in ROLE_REGISTRY.items():
        result.append(rdef.aliases[0] if rdef.aliases else rid)
    return result

CONSENSUS_THRESHOLDS = {
    "simple_majority": 0.51,
    "super_majority": 0.67,
    "unanimous": 1.0,
}
