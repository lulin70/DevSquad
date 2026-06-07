#!/usr/bin/env python3
"""
Skillifier - Automatic Skill Generation System

Analyzes successful execution histories, extracts reusable patterns,
generates Skill proposals with quality validation, and publishes to SkillRegistry.

Core workflow:
  ExecutionRecord → Pattern Extraction → Generalization → SkillProposal → Validation → Publish

This module serves as the public API. Internal logic is delegated to:
  - SkillExtractor: pattern extraction, skill generation, validation
  - SkillStorage: record/pattern/proposal persistence and querying
"""

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

try:
    from .permission_guard import ActionType as PGActionType
except ImportError:

    class PGActionType(Enum):
        FILE_READ = "file_read"
        FILE_CREATE = "file_create"
        FILE_MODIFY = "file_modify"
        FILE_DELETE = "file_delete"
        SHELL_EXECUTE = "shell_execute"
        NETWORK_REQUEST = "network_request"
        GIT_OPERATION = "git_operation"
        ENVIRONMENT = "environment"
        PROCESS_SPAWN = "process_spawn"


class ProposalStatus(Enum):
    DRAFT = "draft"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    REJECTED = "rejected"


class SkillCategory(Enum):
    CODE_GENERATION = "code-generation"
    CODE_REVIEW = "code-review"
    TESTING = "testing"
    DEPLOYMENT = "deployment"
    REFACTORING = "refactoring"
    DOCUMENTATION = "documentation"
    ANALYSIS = "analysis"
    INTEGRATION = "integration"
    SECURITY = "security"
    PERFORMANCE = "performance"
    AUTO_GENERATED = "auto-generated"


# ============================================================
# Data Models - Execution Layer
# ============================================================


@dataclass
class ExecutionStep:
    step_order: int
    action_type: PGActionType
    target: str
    description: str
    outcome: str = "success"
    duration_ms: int = 0
    input_data: str | None = None
    output_data: str | None = None

    def to_dict(self) -> dict:
        return {
            "step_order": self.step_order,
            "action_type": self.action_type.value,
            "target": self.target,
            "description": self.description,
            "outcome": self.outcome,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionStep":
        return cls(
            step_order=d.get("step_order", 0),
            action_type=PGActionType(d.get("action_type", "file_read")),
            target=d.get("target", ""),
            description=d.get("description", ""),
            outcome=d.get("outcome", "success"),
            duration_ms=d.get("duration_ms", 0),
        )


@dataclass
class ExecutionRecord:
    record_id: str = field(default_factory=lambda: f"er-{uuid.uuid4().hex[:12]}")
    task_description: str = ""
    start_time: datetime = field(default_factory=datetime.now)
    end_time: datetime | None = None
    duration_seconds: float = 0.0
    success: bool = True
    worker_id: str = ""
    role_id: str = ""
    steps: list[ExecutionStep] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def finalize(self):
        if self.end_time is None:
            self.end_time = datetime.now()
        if self.duration_seconds == 0.0 and self.start_time:
            delta = self.end_time - self.start_time
            self.duration_seconds = max(0.0, delta.total_seconds())

    def to_dict(self) -> dict:
        return {
            "record_id": self.record_id,
            "task_description": self.task_description,
            "success": self.success,
            "worker_id": self.worker_id,
            "role_id": self.role_id,
            "step_count": len(self.steps),
            "duration_seconds": round(self.duration_seconds, 2),
            "artifacts": self.artifacts,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ExecutionRecord":
        return cls(
            record_id=d.get("record_id", f"er-{uuid.uuid4().hex[:12]}"),
            task_description=d.get("task_description", ""),
            success=d.get("success", True),
            worker_id=d.get("worker_id", ""),
            role_id=d.get("role_id", ""),
        )


# ============================================================
# Data Models - Pattern Layer
# ============================================================


@dataclass
class PatternStep:
    action_type: PGActionType
    target_pattern: str
    description_template: str
    is_required: bool = True
    estimated_risk: float = 0.0

    def to_dict(self) -> dict:
        return {
            "action_type": self.action_type.value,
            "target_pattern": self.target_pattern,
            "description_template": self.description_template,
            "is_required": self.is_required,
            "estimated_risk": self.estimated_risk,
        }


@dataclass
class SuccessPattern:
    pattern_id: str = field(default_factory=lambda: f"sp-{uuid.uuid4().hex[:10]}")
    name: str = ""
    description: str = ""
    source_records: list[str] = field(default_factory=list)
    steps_template: list[PatternStep] = field(default_factory=list)
    trigger_keywords: list[str] = field(default_factory=list)
    applicable_roles: list[str] = field(default_factory=list)
    frequency: int = 1
    confidence: float = 0.5
    avg_success_rate: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "frequency": self.frequency,
            "confidence": round(self.confidence, 3),
            "avg_success_rate": round(self.avg_success_rate, 3),
            "step_count": len(self.steps_template),
            "trigger_keywords": self.trigger_keywords,
            "source_record_count": len(self.source_records),
        }


# ============================================================
# Data Models - Skill Proposal Layer
# ============================================================


@dataclass
class SkillStepDef:
    step_number: int
    action_type: PGActionType
    target_pattern: str
    description: str
    is_required: bool = True


@dataclass
class ValidationResult:
    score: float = 0.0
    completeness: float = 0.0
    specificity: float = 0.0
    repeatability: float = 0.0
    safety: float = 0.0
    issues: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)

    def grade(self) -> str:
        if self.score >= 85:
            return "A"
        elif self.score >= 70:
            return "B"
        elif self.score >= 55:
            return "C"
        else:
            return "D"

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 1),
            "grade": self.grade(),
            "completeness": round(self.completeness, 1),
            "specificity": round(self.specificity, 1),
            "repeatability": round(self.repeatability, 1),
            "safety": round(self.safety, 1),
            "issues": self.issues,
            "suggestions": self.suggestions,
        }


@dataclass
class SkillProposal:
    proposal_id: str = field(default_factory=lambda: f"prop-{uuid.uuid4().hex[:10]}")
    name: str = ""
    slug: str = ""
    version: str = "1.0.0"
    description: str = ""
    category: str = "auto-generated"
    trigger_conditions: list[str] = field(default_factory=list)
    steps: list[SkillStepDef] = field(default_factory=list)
    required_roles: list[str] = field(default_factory=list)
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: list[str] = field(default_factory=list)
    source_pattern: str | None = None
    quality_score: float = 0.0
    validation_result: ValidationResult | None = None
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: str | None = None
    published_at: datetime | None = None

    def _generate_slug(self):
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", self.name.lower())
        slug = re.sub(r"\s+", "-", slug.strip())
        return slug or "unnamed-skill"

    def to_dict(self) -> dict:
        d = {
            "proposal_id": self.proposal_id,
            "name": self.name,
            "slug": self.slug,
            "version": self.version,
            "description": self.description,
            "category": self.category,
            "status": self.status.value,
            "step_count": len(self.steps),
            "quality_score": round(self.quality_score, 1),
            "created_at": self.created_at.isoformat(),
        }
        if self.validation_result:
            d["validation"] = self.validation_result.to_dict()
        if self.published_at:
            d["published_at"] = self.published_at.isoformat()
        return d


# ============================================================
# Skillifier Core Engine (Facade)
# ============================================================


class Skillifier:
    """Automatic skill generation from execution history analysis.

    Delegates to SkillExtractor for computation and SkillStorage for persistence.
    Maintains the same public API as the original monolithic implementation.
    """

    DEFAULT_MIN_OCCURRENCES = 2
    DEFAULT_MIN_CONFIDENCE = 0.6

    CATEGORY_KEYWORDS = {
        SkillCategory.CODE_GENERATION: [
            "create",
            "generate",
            "init",
            "setup",
            "build",
            "implement",
            "develop",
            "write",
            "new",
        ],
        SkillCategory.CODE_REVIEW: ["review", "audit", "inspect", "check", "analyze-code", "lint", "quality"],
        SkillCategory.TESTING: ["test", "spec", "verify", "assert", "coverage", "pytest", "unittest", "e2e"],
        SkillCategory.DEPLOYMENT: [
            "deploy",
            "release",
            "ship",
            "publish",
            "ci/cd",
            "docker",
            "kubernetes",
            "production",
        ],
        SkillCategory.REFACTORING: ["refactor", "cleanup", "optimize", "restructure", "simplify", "improve"],
        SkillCategory.DOCUMENTATION: ["document", "readme", "api-doc", "comment", "wiki", "guide", "manual"],
        SkillCategory.ANALYSIS: ["analyze", "diagnose", "investigate", "profile", "benchmark", "measure"],
        SkillCategory.INTEGRATION: ["integrate", "connect", "configure", "setup-env", "pipeline", "workflow"],
        SkillCategory.SECURITY: ["security", "vulnerability", "auth", "permission", "encrypt", "scan"],
        SkillCategory.PERFORMANCE: ["performance", "speed", "cache", "optimize-fast", "latency", "throughput"],
    }

    def __init__(
        self,
        min_pattern_occurrences: int = DEFAULT_MIN_OCCURRENCES,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
        auto_analyze: bool = True,
    ):
        self.min_occurrences = min_pattern_occurrences
        self.min_confidence = min_confidence
        self.auto_analyze = auto_analyze

        # Lazy import to avoid circular dependency
        from .skill_extractor import SkillExtractor
        from .skill_storage import SkillStorage

        self._extractor = SkillExtractor(
            min_occurrences=min_pattern_occurrences,
            min_confidence=min_confidence,
        )
        self._storage = SkillStorage()

    # Backward-compatible property accessors for internal state
    @property
    def _records(self) -> list[ExecutionRecord]:
        return self._storage._records

    @_records.setter
    def _records(self, value: list[ExecutionRecord]) -> None:
        self._storage._records = value

    @property
    def _patterns(self) -> list[SuccessPattern]:
        return self._storage._patterns

    @_patterns.setter
    def _patterns(self, value: list[SuccessPattern]) -> None:
        self._storage._patterns = value

    @property
    def _proposals(self) -> dict[str, SkillProposal]:
        return self._storage._proposals

    @_proposals.setter
    def _proposals(self, value: dict[str, SkillProposal]) -> None:
        self._storage._proposals = value

    @property
    def _lock(self):
        return self._storage._lock

    def __getattr__(self, name: str) -> Any:
        """Delegate attribute access to SkillExtractor for backward compatibility.

        Allows code that accesses private methods like sf._sequence_similarity()
        to continue working by delegating to the SkillExtractor instance.
        """
        if name.startswith("_") and not name.startswith("__") and hasattr(self.__dict__.get("_extractor", None), name):
            return getattr(self._extractor, name)
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")

    # ================================================================
    # Record Management → SkillStorage
    # ================================================================

    def record_execution(self, record: ExecutionRecord) -> None:
        self._storage.record_execution(record)

    def get_records(
        self, since: datetime = None, until: datetime = None, success_only: bool = True
    ) -> list[ExecutionRecord]:
        return self._storage.get_records(since=since, until=until, success_only=success_only)

    # ================================================================
    # Pattern Extraction → SkillExtractor + SkillStorage
    # ================================================================

    def analyze_history(self, since: datetime = None, until: datetime = None) -> list[SuccessPattern]:
        with self._lock:
            records = self._storage.get_records(since=since, until=until, success_only=True)
            patterns = self._extractor.analyze_history(
                records,
                existing_patterns=self._storage.get_patterns(),
            )
            self._storage.add_patterns(patterns)
            return patterns

    # ================================================================
    # Skill Generation → SkillExtractor + SkillStorage
    # ================================================================

    def generate_skill(self, pattern: SuccessPattern) -> SkillProposal:
        proposal = self._extractor.generate_skill(pattern)
        validation = self._extractor.validate_skill(proposal, patterns=self._storage.get_patterns())
        proposal.validation_result = validation
        proposal.quality_score = validation.score
        self._storage.add_proposal(proposal)
        return proposal

    # ================================================================
    # Quality Validation → SkillExtractor
    # ================================================================

    def validate_skill(self, proposal: SkillProposal) -> ValidationResult:
        return self._extractor.validate_skill(proposal, patterns=self._storage.get_patterns())

    # ================================================================
    # Publishing & Discovery → SkillStorage
    # ================================================================

    def approve_and_publish(self, proposal_id: str, approver: str = "system") -> bool:
        return self._storage.approve_and_publish(proposal_id, approver)

    def suggest_skills_for_task(self, task_description: str) -> list[SkillProposal]:
        return self._storage.suggest_skills_for_task(task_description)

    # ================================================================
    # Query & Export → SkillStorage
    # ================================================================

    def get_pattern_library(self) -> list[SuccessPattern]:
        return self._storage.get_patterns()

    def get_proposals(self, status=None) -> list[SkillProposal]:
        return self._storage.get_proposals(status)

    def export_patterns(self) -> str:
        return self._storage.export_patterns()

    def export_state(self) -> dict:
        return self._storage.export_state()

    def get_statistics(self) -> dict[str, Any]:
        return self._storage.get_statistics()
