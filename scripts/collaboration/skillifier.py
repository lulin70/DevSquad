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

    class PGActionType(Enum):  # type: ignore[no-redef]
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
        """Serialize the ExecutionStep to a JSON-compatible dictionary.

        Returns:
            Dictionary containing step_order, action_type, target, description,
            outcome, and duration_ms fields.
        """
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
        """Construct an ExecutionStep from a dictionary.

        Args:
            d: Dictionary with step fields; missing values use safe defaults.

        Returns:
            ExecutionStep instance populated from the dictionary.
        """
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

    def finalize(self) -> None:
        """Finalize the record by setting end_time and computing duration_seconds if unset."""
        if self.end_time is None:
            self.end_time = datetime.now()
        if self.duration_seconds == 0.0 and self.start_time:
            delta = self.end_time - self.start_time
            self.duration_seconds = max(0.0, delta.total_seconds())

    def to_dict(self) -> dict:
        """Serialize the ExecutionRecord to a summary JSON-compatible dictionary.

        Returns:
            Dictionary with record_id, task_description, success, worker_id,
            role_id, step_count, duration_seconds, and artifacts fields.
        """
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
        """Construct an ExecutionRecord from a summary dictionary.

        Args:
            d: Dictionary with record fields; missing values use safe defaults.

        Returns:
            ExecutionRecord instance populated from the dictionary.
        """
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
        """Serialize the PatternStep to a JSON-compatible dictionary.

        Returns:
            Dictionary with action_type, target_pattern, description_template,
            is_required, and estimated_risk fields.
        """
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
        """Serialize the SuccessPattern to a summary JSON-compatible dictionary.

        Returns:
            Dictionary with pattern_id, name, description, frequency, confidence,
            avg_success_rate, step_count, trigger_keywords, and source_record_count.
        """
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
        """Map the numeric score to a letter grade (A/B/C/D).

        Returns:
            "A" for score>=85, "B" for >=70, "C" for >=55, otherwise "D".
        """
        if self.score >= 85:
            return "A"
        elif self.score >= 70:
            return "B"
        elif self.score >= 55:
            return "C"
        else:
            return "D"

    def to_dict(self) -> dict:
        """Serialize the ValidationResult to a JSON-compatible dictionary.

        Returns:
            Dictionary with score, grade, completeness, specificity, repeatability,
            safety, issues, and suggestions fields.
        """
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

    def _generate_slug(self) -> str:
        slug = re.sub(r"[^a-zA-Z0-9\s-]", "", self.name.lower())
        slug = re.sub(r"\s+", "-", slug.strip())
        return slug or "unnamed-skill"

    def to_dict(self) -> dict:
        """Serialize the SkillProposal to a summary JSON-compatible dictionary.

        Returns:
            Dictionary with proposal_id, name, slug, version, description, category,
            status, step_count, quality_score, created_at, and optional validation
            and published_at fields.
        """
        d: dict[str, Any] = {
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
        return self._storage.get_all_records()

    @_records.setter
    def _records(self, value: list[ExecutionRecord]) -> None:
        self._storage.set_all_records(value)

    @property
    def _patterns(self) -> list[SuccessPattern]:
        return self._storage.get_all_patterns()

    @_patterns.setter
    def _patterns(self, value: list[SuccessPattern]) -> None:
        self._storage.set_all_patterns(value)

    @property
    def _proposals(self) -> dict[str, SkillProposal]:
        return self._storage.get_all_proposals()

    @_proposals.setter
    def _proposals(self, value: dict[str, SkillProposal]) -> None:
        self._storage.set_all_proposals(value)

    # Explicit delegate methods to SkillExtractor (replacing __getattr__)
    # These provide static analyzability while maintaining backward compatibility.

    def _sequence_similarity(self, seq_a: list, seq_b: list) -> float:
        return self._extractor._sequence_similarity(seq_a, seq_b)

    def _step_similarity(self, a: ExecutionStep, b: ExecutionStep) -> float:
        return self._extractor._step_similarity(a, b)

    def _cluster_sequences(self, records: list) -> dict:
        return self._extractor._cluster_sequences(records)

    def _generalize_target(self, targets: list) -> str:
        return self._extractor._generalize_target(targets)

    def _generalize_description(self, descriptions: list) -> str:
        return self._extractor._generalize_description(descriptions)

    def _generalize_step(self, step_samples: list[ExecutionStep]) -> PatternStep:
        return self._extractor._generalize_step(step_samples)

    def _word_overlap(self, text_a: str, text_b: str) -> float:
        return self._extractor._word_overlap(text_a, text_b)

    # ================================================================
    # Record Management → SkillStorage
    # ================================================================

    def record_execution(self, record: ExecutionRecord) -> None:
        """Record an execution via the underlying SkillStorage.

        Args:
            record: ExecutionRecord to finalize and persist.
        """
        self._storage.record_execution(record)

    def get_records(
        self, since: datetime | None = None, until: datetime | None = None, success_only: bool = True
    ) -> list[ExecutionRecord]:
        """Query stored execution records by time range and success status.

        Args:
            since: Optional inclusive lower bound on record start_time.
            until: Optional inclusive upper bound on record start_time.
            success_only: When True (default), only successful records are returned.

        Returns:
            List of ExecutionRecord matching the filters.
        """
        return self._storage.get_records(since=since, until=until, success_only=success_only)

    # ================================================================
    # Pattern Extraction → SkillExtractor + SkillStorage
    # ================================================================

    def analyze_history(self, since: datetime | None = None, until: datetime | None = None) -> list[SuccessPattern]:
        """Analyze execution history to extract and persist success patterns.

        Args:
            since: Optional inclusive lower bound on record start_time.
            until: Optional inclusive upper bound on record start_time.

        Returns:
            List of newly extracted SuccessPattern instances (also persisted).
        """
        with self._storage.thread_safe():
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
        """Generate, validate, and persist a SkillProposal from a SuccessPattern.

        Args:
            pattern: SuccessPattern used as the source for skill generation.

        Returns:
            SkillProposal with validation_result and quality_score populated.
        """
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
        """Validate a SkillProposal against the current pattern library.

        Args:
            proposal: SkillProposal to validate.

        Returns:
            ValidationResult with score, sub-scores, issues, and suggestions.
        """
        return self._extractor.validate_skill(proposal, patterns=self._storage.get_patterns())

    # ================================================================
    # Publishing & Discovery → SkillStorage
    # ================================================================

    def approve_and_publish(self, proposal_id: str, approver: str = "system") -> bool:
        """Approve and publish a proposal by id via the underlying storage.

        Args:
            proposal_id: Identifier of the proposal to publish.
            approver: Name of the approver (default "system").

        Returns:
            True if the proposal exists, False otherwise.
        """
        return self._storage.approve_and_publish(proposal_id, approver)

    def suggest_skills_for_task(self, task_description: str) -> list[SkillProposal]:
        """Suggest approved/published skills whose trigger conditions match a task.

        Args:
            task_description: Natural language description of the task.

        Returns:
            List of up to 10 SkillProposal sorted by relevance score (descending).
        """
        return self._storage.suggest_skills_for_task(task_description)

    # ================================================================
    # Query & Export → SkillStorage
    # ================================================================

    def get_pattern_library(self) -> list[SuccessPattern]:
        """Return all stored success patterns.

        Returns:
            List of SuccessPattern currently in storage.
        """
        return self._storage.get_patterns()

    def get_proposals(self, status: ProposalStatus | None = None) -> list[SkillProposal]:
        """List proposals, optionally filtered by status.

        Args:
            status: Optional ProposalStatus value to filter by.

        Returns:
            List of SkillProposal matching the status filter (or all if None).
        """
        return self._storage.get_proposals(status)

    def export_patterns(self) -> str:
        """Export all stored patterns as a JSON string.

        Returns:
            JSON-encoded string of the pattern library.
        """
        return self._storage.export_patterns()

    def export_state(self) -> dict:
        """Export the full storage state (records, patterns, proposals) as a dict.

        Returns:
            Dictionary containing the serializable storage state.
        """
        return self._storage.export_state()

    def get_statistics(self) -> dict[str, Any]:
        """Return aggregate statistics about records, patterns, and proposals.

        Returns:
            Dictionary with counts and quality aggregates from the storage.
        """
        return self._storage.get_statistics()

    # ------------------------------------------------------------------
    # Module 9 (Matt P0-6): Invocation type classification
    # ------------------------------------------------------------------

    # Categories that suggest broad, general-purpose skills.
    _MODEL_INVOKED_CATEGORIES: frozenset[str] = frozenset({
        SkillCategory.CODE_GENERATION.value,
        SkillCategory.CODE_REVIEW.value,
        SkillCategory.TESTING.value,
        SkillCategory.ANALYSIS.value,
        SkillCategory.REFACTORING.value,
    })

    # Categories that suggest specific, user-triggered skills.
    _USER_INVOKED_CATEGORIES: frozenset[str] = frozenset({
        SkillCategory.DEPLOYMENT.value,
        SkillCategory.SECURITY.value,
        SkillCategory.DOCUMENTATION.value,
        SkillCategory.INTEGRATION.value,
        SkillCategory.PERFORMANCE.value,
    })

    # Trigger keywords that suggest user-initiated invocation.
    _USER_TRIGGER_KEYWORDS: frozenset[str] = frozenset({
        "deploy", "publish", "release", "audit", "security",
        "migrate", "rollback", "production", "staging",
    })

    def classify_invocation_type(self, proposal: SkillProposal) -> str:
        """Classify how a skill should be invoked (Matt P0-6).

        Determines whether a skill should be:
        - ``"model-invoked"``: The AI agent decides to use it autonomously
          (broad triggers, general-purpose category)
        - ``"user-invoked"``: The user explicitly triggers it
          (specific triggers, niche category)
        - ``"both"``: Can be both model- and user-invoked

        Classification criteria:
        1. Category — general categories → model-invoked, specific → user-invoked
        2. Trigger conditions — broad/many → model-invoked, specific/few → user-invoked
        3. Required roles — multi-role → model-invoked, single-role → user-invoked

        Args:
            proposal: The :class:`SkillProposal` to classify.

        Returns:
            One of ``"model-invoked"``, ``"user-invoked"``, ``"both"``.
        """
        score = 0  # Positive → model-invoked, negative → user-invoked.

        # 1. Category signal.
        if proposal.category in self._MODEL_INVOKED_CATEGORIES:
            score += 2
        elif proposal.category in self._USER_INVOKED_CATEGORIES:
            score -= 2

        # 2. Trigger conditions signal.
        triggers = proposal.trigger_conditions
        if len(triggers) >= 3:
            score += 1  # Many triggers → broad → model-invoked.
        elif len(triggers) <= 1:
            score -= 1  # Few triggers → specific → user-invoked.

        # Check for user-trigger keywords.
        trigger_text = " ".join(triggers).lower()
        if any(kw in trigger_text for kw in self._USER_TRIGGER_KEYWORDS):
            score -= 2

        # 3. Required roles signal.
        if len(proposal.required_roles) >= 2:
            score += 1  # Multi-role → general → model-invoked.

        # Classify.
        if score > 0:
            return "model-invoked"
        elif score < 0:
            return "user-invoked"
        else:
            return "both"
