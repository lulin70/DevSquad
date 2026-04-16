#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Skillifier - Automatic Skill Generation System

Analyzes successful execution histories, extracts reusable patterns,
generates Skill proposals with quality validation, and publishes to SkillRegistry.

Core workflow:
  ExecutionRecord → Pattern Extraction → Generalization → SkillProposal → Validation → Publish
"""

import re
import json
import uuid
import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

try:
    from collaboration.permission_guard import ActionType as PGActionType
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
    input_data: Optional[str] = None
    output_data: Optional[str] = None

    def to_dict(self) -> Dict:
        return {
            "step_order": self.step_order,
            "action_type": self.action_type.value,
            "target": self.target,
            "description": self.description,
            "outcome": self.outcome,
            "duration_ms": self.duration_ms,
        }

    @classmethod
    def from_dict(cls, d: Dict) -> "ExecutionStep":
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
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = True
    worker_id: str = ""
    role_id: str = ""
    steps: List[ExecutionStep] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finalize(self):
        if self.end_time is None:
            self.end_time = datetime.now()
        if self.duration_seconds == 0.0 and self.start_time:
            delta = self.end_time - self.start_time
            self.duration_seconds = max(0.0, delta.total_seconds())

    def to_dict(self) -> Dict:
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
    def from_dict(cls, d: Dict) -> "ExecutionRecord":
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

    def to_dict(self) -> Dict:
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
    source_records: List[str] = field(default_factory=list)
    steps_template: List[PatternStep] = field(default_factory=list)
    trigger_keywords: List[str] = field(default_factory=list)
    applicable_roles: List[str] = field(default_factory=list)
    frequency: int = 1
    confidence: float = 0.5
    avg_success_rate: float = 1.0
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict:
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
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    def grade(self) -> str:
        if self.score >= 85:
            return "A"
        elif self.score >= 70:
            return "B"
        elif self.score >= 55:
            return "C"
        else:
            return "D"

    def to_dict(self) -> Dict:
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
    trigger_conditions: List[str] = field(default_factory=list)
    steps: List[SkillStepDef] = field(default_factory=list)
    required_roles: List[str] = field(default_factory=list)
    input_schema: Dict[str, Any] = field(default_factory=dict)
    output_schema: Dict[str, Any] = field(default_factory=dict)
    acceptance_criteria: List[str] = field(default_factory=list)
    source_pattern: Optional[str] = None
    quality_score: float = 0.0
    validation_result: Optional[ValidationResult] = None
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    approved_by: Optional[str] = None
    published_at: Optional[datetime] = None

    def _generate_slug(self):
        slug = re.sub(r'[^a-zA-Z0-9\s-]', '', self.name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug or "unnamed-skill"

    def to_dict(self) -> Dict:
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
# Skillifier Core Engine
# ============================================================

class Skillifier:
    """Automatic skill generation from execution history analysis"""

    DEFAULT_MIN_OCCURRENCES = 2
    DEFAULT_MIN_CONFIDENCE = 0.6

    CATEGORY_KEYWORDS = {
        SkillCategory.CODE_GENERATION: ["create", "generate", "init", "setup", "build",
                                          "implement", "develop", "write", "new"],
        SkillCategory.CODE_REVIEW: ["review", "audit", "inspect", "check", "analyze-code",
                                     "lint", "quality"],
        SkillCategory.TESTING: ["test", "spec", "verify", "assert", "coverage", "pytest",
                                 "unittest", "e2e"],
        SkillCategory.DEPLOYMENT: ["deploy", "release", "ship", "publish", "ci/cd",
                                    "docker", "kubernetes", "production"],
        SkillCategory.REFACTORING: ["refactor", "cleanup", "optimize", "restructure",
                                     "simplify", "improve"],
        SkillCategory.DOCUMENTATION: ["document", "readme", "api-doc", "comment",
                                      "wiki", "guide", "manual"],
        SkillCategory.ANALYSIS: ["analyze", "diagnose", "investigate", "profile",
                                  "benchmark", "measure"],
        SkillCategory.INTEGRATION: ["integrate", "connect", "configure", "setup-env",
                                    "pipeline", "workflow"],
        SkillCategory.SECURITY: ["security", "vulnerability", "auth", "permission",
                                  "encrypt", "scan"],
        SkillCategory.PERFORMANCE: ["performance", "speed", "cache", "optimize-fast",
                                      "latency", "throughput"],
    }

    def __init__(self,
                 min_pattern_occurrences: int = DEFAULT_MIN_OCCURRENCES,
                 min_confidence: float = DEFAULT_MIN_CONFIDENCE,
                 auto_analyze: bool = True):
        self.min_occurrences = min_pattern_occurrences
        self.min_confidence = min_confidence
        self.auto_analyze = auto_analyze
        self._records: List[ExecutionRecord] = []
        self._patterns: List[SuccessPattern] = []
        self._proposals: Dict[str, SkillProposal] = {}
        self._lock = threading.RLock()

    # ================================================================
    # Record Management
    # ================================================================

    def record_execution(self, record: ExecutionRecord) -> None:
        with self._lock:
            record.finalize()
            self._records.append(record)

    def get_records(self, since: datetime = None, until: datetime = None,
                    success_only: bool = True) -> List[ExecutionRecord]:
        results = self._records
        if since:
            results = [r for r in results if r.start_time >= since]
        if until:
            results = [r for r in results if r.start_time <= until]
        if success_only:
            results = [r for r in results if r.success]
        return list(results)

    # ================================================================
    # Pattern Extraction
    # ================================================================

    def analyze_history(self, since: datetime = None,
                       until: datetime = None) -> List[SuccessPattern]:
        with self._lock:
            records = self.get_records(since=since, until=until, success_only=True)
            if len(records) < self.min_occurrences:
                return []

            clusters = self._cluster_sequences(records)
            patterns = []
            for cluster_records in clusters.values():
                if len(cluster_records) < self.min_occurrences:
                    continue
                pattern = self._build_pattern_from_cluster(cluster_records)
                if pattern.confidence >= self.min_confidence:
                    patterns.append(pattern)
                    existing_ids = {p.pattern_id for p in self._patterns}
                    if pattern.pattern_id not in existing_ids:
                        self._patterns.append(pattern)

            patterns.sort(key=lambda p: p.confidence, reverse=True)
            return patterns

    def _cluster_sequences(self, records: List[ExecutionRecord]) -> Dict[int, List[ExecutionRecord]]:
        clusters: Dict[int, List[ExecutionRecord]] = {}
        cluster_id = 0

        for record in records:
            if len(record.steps) == 0:
                continue
            best_cluster = -1
            best_similarity = -1.0

            for cid, members in clusters.items():
                rep = members[0]
                sim = self._sequence_similarity(record.steps, rep.steps)
                if sim > best_similarity and sim > 0.45:
                    best_similarity = sim
                    best_cluster = cid

            if best_cluster >= 0:
                clusters[best_cluster].append(record)
            else:
                clusters[cluster_id] = [record]
                cluster_id += 1

        return clusters

    def _sequence_similarity(self, seq_a: List[ExecutionStep],
                            seq_b: List[ExecutionStep]) -> float:
        if not seq_a or not seq_b:
            return 0.0
        len_a, len_b = len(seq_a), len(seq_b)
        if abs(len_a - len_b) > max(len_a, len_b) * 0.7:
            return 0.0

        n = min(len_a, len_b)
        total_sim = 0.0
        match_count = 0
        for i in range(n):
            sim = self._step_similarity(seq_a[i], seq_b[i])
            total_sim += sim
            if sim > 0.3:
                match_count += 1

        base_score = total_sim / max(n, 1)
        length_penalty = 1.0 - abs(len_a - len_b) / max(len_a, len_b, 1)
        match_ratio = match_count / max(n, 1)
        return base_score * 0.5 + length_penalty * 0.25 + match_ratio * 0.25

    def _step_similarity(self, a: ExecutionStep, b: ExecutionStep) -> float:
        if a.action_type != b.action_type:
            return 0.0
        score = 0.4
        if self._extension_match(a.target, b.target):
            score += 0.3
        elif self._directory_match(a.target, b.target):
            score += 0.15
        word_overlap = self._word_overlap(a.description, b.description)
        score += 0.2 * word_overlap
        if a.outcome == b.outcome == "success":
            score += 0.1
        return min(1.0, score)

    def _extension_match(self, target_a: str, target_b: str) -> bool:
        ext_a = self._get_extension(target_a)
        ext_b = self._get_extension(target_b)
        return ext_a and ext_b and ext_a == ext_b

    def _directory_match(self, target_a: str, target_b: str) -> bool:
        parts_a = target_a.replace("\\", "/").rstrip("/").split("/")
        parts_b = target_b.replace("\\", "/").rstrip("/").split("/")
        if len(parts_a) < 2 or len(parts_b) < 2:
            return False
        return parts_a[:-1] == parts_b[:-1]

    @staticmethod
    def _get_extension(path: str) -> str:
        if "." in path:
            return path.rsplit(".", 1)[-1].lower()
        return ""

    @staticmethod
    def _word_overlap(text_a: str, text_b: str) -> float:
        words_a = set(re.findall(r'\w{2,}', text_a.lower()))
        words_b = set(re.findall(r'\w{2,}', text_b.lower()))
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _build_pattern_from_cluster(self, records: List[ExecutionRecord]) -> SuccessPattern:
        rep = records[0]
        all_steps = [r.steps for r in records if r.steps]
        if not all_steps:
            return SuccessPattern(name="empty-pattern")

        min_len = min(len(s) for s in all_steps)
        template_steps = []
        for i in range(min_len):
            step_samples = [s[i] for s in all_steps if i < len(s)]
            if step_samples:
                ps = self._generalize_step(step_samples)
                template_steps.append(ps)

        keywords = self._extract_trigger_keywords(rep.task_description, rep.steps)
        roles = list(set(r.role_id for r in records if r.role_id))
        success_rate = sum(1 for r in records if r.success) / max(len(records), 1)
        confidence = self._calculate_confidence(records, template_steps)

        name = self._generate_pattern_name(rep.task_description, template_steps)

        return SuccessPattern(
            name=name,
            description=f"Auto-extracted pattern from {len(records)} executions",
            source_records=[r.record_id for r in records],
            steps_template=template_steps,
            trigger_keywords=keywords,
            applicable_roles=roles,
            frequency=len(records),
            confidence=confidence,
            avg_success_rate=success_rate,
        )

    def _generalize_step(self, step_samples: List[ExecutionStep]) -> PatternStep:
        sample = step_samples[0]
        targets = [s.target for s in step_samples]
        generalized_target = self._generalize_target(targets)
        descriptions = [s.description for s in step_samples]
        desc_template = self._generalize_description(descriptions)

        risk_scores = []
        has_error = any(s.outcome != "success" for s in step_samples)
        avg_duration = sum(s.duration_ms for s in step_samples) / max(len(step_samples), 1)

        return PatternStep(
            action_type=sample.action_type,
            target_pattern=generalized_target,
            description_template=desc_template,
            is_required=not has_error,
            estimated_risk=min(1.0, avg_duration / 5000.0),
        )

    def _generalize_target(self, targets: List[str]) -> str:
        if not targets:
            return "*"
        extensions = set(self._get_extension(t) for t in targets)
        directories = set("/".join(t.replace("\\", "/").rstrip("/").split("/")[:-1])
                        for t in targets if "/" in t or "\\" in t)

        if len(extensions) == 1 and list(extensions)[0]:
            ext = list(extensions)[0]
            if len(directories) == 1:
                dir_part = list(directories)[0]
                return f"{dir_part}/*.{ext}"
            return f"*.{ext}"
        if len(directories) == 1:
            return f"{list(directories)[0]}/*"
        return "*"

    def _generalize_description(self, descriptions: List[str]) -> str:
        if not descriptions:
            return ""
        common_words = []
        if descriptions:
            word_counts: Dict[str, int] = {}
            for desc in descriptions:
                for w in re.findall(r'\w{3,}', desc.lower()):
                    word_counts[w] = word_counts.get(w, 0) + 1
            threshold = max(len(descriptions) * 0.6, 1)
            common_words = [w for w, c in sorted(word_counts.items(), key=lambda x: -x[1])
                           if c >= threshold][:8]
        return " ".join(common_words) if common_words else descriptions[0]

    def _extract_trigger_keywords(self, task_desc: str,
                                   steps: List[ExecutionStep]) -> List[str]:
        keywords = set()
        text = (task_desc + " " + " ".join(s.description for s in steps)).lower()
        important = re.findall(r'\b\w{4,}\b', text)
        stop_words = {"that", "with", "from", "this", "they", "have", "been",
                      "were", "their", "will", "would", "could", "should", "into"}
        for w in important:
            if w not in stop_words and len(w) >= 4:
                keywords.add(w)
        return sorted(list(keywords))[:10]

    def _calculate_confidence(self, records: List[ExecutionRecord],
                               steps: List[PatternStep]) -> float:
        freq_factor = min(1.0, len(records) / 10.0)
        success_factor = sum(1 for r in records if r.success) / max(len(records), 1)
        consistency = 1.0
        if len(records) >= 2:
            lengths = [len(r.steps) for r in records]
            avg_len = sum(lengths) / len(lengths)
            variance = sum((l - avg_len) ** 2 for l in lengths) / len(lengths)
            consistency = max(0.3, 1.0 - variance / (avg_len ** 2 + 1))
        step_quality = sum(1.0 - ps.estimated_risk for ps in steps) / max(len(steps), 1)
        return (freq_factor * 0.3 + success_factor * 0.3 +
                consistency * 0.2 + step_quality * 0.2)

    def _generate_pattern_name(self, task_desc: str,
                                steps: List[PatternStep]) -> str:
        if task_desc:
            words = re.findall(r'[A-Za-z][A-Za-z0-9 ]{2,20}', task_desc)
            if words:
                return words[0].strip().title() + " Pattern"
        if steps:
            action_names = {s.action_type.value.replace("_", " ").title() for s in steps}
            return " & ".join(sorted(action_names)[:3]) + " Pattern"
        return "Unnamed Pattern"

    # ================================================================
    # Skill Generation
    # ================================================================

    def generate_skill(self, pattern: SuccessPattern) -> SkillProposal:
        steps = [
            SkillStepDef(
                step_number=i + 1,
                action_type=ps.action_type,
                target_pattern=ps.target_pattern,
                description=ps.description_template or ps.action_type.value,
                is_required=ps.is_required,
            )
            for i, ps in enumerate(pattern.steps_template)
        ]

        category = self._classify_category(pattern)
        slug = self._make_slug(pattern.name)
        desc = self._generate_description(pattern, steps)
        input_schema = self._infer_input_schema(steps)
        output_schema = self._infer_output_schema(pattern)
        acceptance = self._infer_acceptance_criteria(pattern)

        proposal = SkillProposal(
            name=pattern.name.replace(" Pattern", "").strip(),
            slug=slug,
            description=desc,
            category=category.value,
            trigger_conditions=list(pattern.trigger_keywords),
            steps=steps,
            required_roles=list(pattern.applicable_roles),
            input_schema=input_schema,
            output_schema=output_schema,
            acceptance_criteria=acceptance,
            source_pattern=pattern.pattern_id,
            quality_score=pattern.confidence * 100,
            status=ProposalStatus.DRAFT,
        )
        proposal.slug = proposal._generate_slug()

        validation = self.validate_skill(proposal)
        proposal.validation_result = validation
        proposal.quality_score = validation.score
        self._proposals[proposal.proposal_id] = proposal
        return proposal

    def _classify_category(self, pattern: SuccessPattern) -> SkillCategory:
        text = (pattern.name + " " +
                " ".join(pattern.trigger_keywords) +
                " ".join(ps.description_template for ps in pattern.steps_template)).lower()
        best_cat = SkillCategory.AUTO_GENERATED
        best_score = 0
        for cat, keywords in self.CATEGORY_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in text)
            if score > best_score:
                best_score = score
                best_cat = cat
        return best_cat

    def _make_slug(self, name: str) -> str:
        slug = re.sub(r'[^a-z0-9\s-]', '', name.lower())
        slug = re.sub(r'\s+', '-', slug.strip())
        return slug or "auto-skill"

    def _generate_description(self, pattern: SuccessPattern,
                              steps: List[SkillStepDef]) -> str:
        action_types = [s.action_type.value.replace("_", " ") for s in steps]
        unique_actions = list(dict.fromkeys(action_types))
        return (f"Auto-generated skill: {' → '.join(unique_actions[:5])}. "
                f"Based on {pattern.frequency} successful executions. "
                f"Confidence: {pattern.confidence:.0%}.")

    def _infer_input_schema(self, steps: List[SkillStepDef]) -> Dict[str, Any]:
        schema: Dict[str, Any] = {}
        has_wildcard = any("*" in s.target_pattern for s in steps)
        if has_wildcard:
            schema["target_path"] = {"type": "string", "description": "Target file/directory path"}
        has_shell = any(s.action_type == PGActionType.SHELL_EXECUTE for s in steps)
        if has_shell:
            schema["command_args"] = {"type": "string", "description": "Command arguments"}
        return schema

    def _infer_output_schema(self, pattern: SuccessPattern) -> Dict[str, Any]:
        create_steps = [ps for ps in pattern.steps_template
                        if ps.action_type in (PGActionType.FILE_CREATE,
                                               PGActionType.FILE_MODIFY)]
        if create_steps:
            return {
                "created_files": {"type": "array", "description": "Files created/modified"},
                "artifacts": {"type": "array", "description": "Output artifacts"},
            }
        return {}

    def _infer_acceptance_criteria(self, pattern: SuccessPattern) -> List[str]:
        criteria = []
        if pattern.avg_success_rate >= 0.9:
            criteria.append(f"Historical success rate >= {pattern.avg_success_rate:.0%}")
        if pattern.frequency >= 3:
            criteria.append(f"Verified across {pattern.frequency}+ executions")
        if pattern.steps_template:
            criteria.append(f"All {len(pattern.steps_template)} steps completed successfully")
        return criteria

    # ================================================================
    # Quality Validation (5-Dimension Scoring)
    # ================================================================

    def validate_skill(self, proposal: SkillProposal) -> ValidationResult:
        completeness = self._score_completeness(proposal)
        specificity = self._score_specificity(proposal)
        repeatability = self._score_repeatability(proposal)
        safety = self._score_safety(proposal)
        practicality = self._score_practicality(proposal)

        score = (completeness * 0.25 + specificity * 0.20 +
                 repeatability * 0.20 + safety * 0.20 + practicality * 0.15)

        issues = []
        suggestions = []

        if completeness < 60:
            issues.append("步骤定义不完整，缺少关键信息")
        if len(proposal.steps) == 0:
            issues.append("无任何步骤定义")
        if len(proposal.steps) > 20:
            issues.append(f"步骤过多({len(proposal.steps)}步)，建议拆分")
        if safety < 50:
            issues.append("包含高风险操作")
        if len(proposal.trigger_conditions) < 3:
            issues.append("触发条件过于宽泛")
            suggestions.append("增加更多触发关键词以提高特异性")
        if repeatability < 50:
            suggestions.append("需要更多成功执行记录来提高可重复性")
        if completeness < 80:
            suggestions.append("补充输入输出Schema和验收标准")

        result = ValidationResult(
            score=round(score, 1),
            completeness=round(completeness, 1),
            specificity=round(specificity, 1),
            repeatability=round(repeatability, 1),
            safety=round(safety, 1),
            issues=issues,
            suggestions=suggestions,
        )
        proposal.validation_result = result
        return result

    def _score_completeness(self, p: SkillProposal) -> float:
        score = 100.0
        if not p.name:
            score -= 30
        if not p.description:
            score -= 15
        if not p.steps:
            score -= 40
        if not p.input_schema:
            score -= 10
        if not p.output_schema:
            score -= 5
        if not p.acceptance_criteria:
            score -= 10
        for s in p.steps:
            if not s.description or s.description == s.action_type.value:
                score -= 3
        return max(0.0, score)

    def _score_specificity(self, p: SkillProposal) -> float:
        score = 80.0
        kw_count = len(p.trigger_conditions)
        score += min(20, kw_count * 3)
        generic_patterns = sum(1 for s in p.steps if s.target_pattern == "*")
        score -= generic_patterns * 10
        return max(0.0, min(100.0, score))

    def _score_repeatability(self, p: SkillProposal) -> float:
        score = 60.0
        if p.source_pattern:
            pattern = next((pat for pat in self._patterns
                             if pat.pattern_id == p.source_pattern), None)
            if pattern:
                score += min(30, pattern.frequency * 5)
                score += pattern.avg_success_rate * 10
        return max(0.0, min(100.0, score))

    def _score_safety(self, p: SkillProposal) -> float:
        score = 100.0
        high_risk_types = {PGActionType.FILE_DELETE, PGActionType.SHELL_EXECUTE,
                          PGActionType.PROCESS_SPAWN}
        for s in p.steps:
            if s.action_type in high_risk_types:
                score -= 15
            if "*" in s.target_pattern and s.action_type in high_risk_types:
                score -= 10
        return max(0.0, score)

    def _score_practicality(self, p: SkillProposal) -> float:
        score = 70.0
        n_steps = len(p.steps)
        if 3 <= n_steps <= 15:
            score += 20
        elif n_steps < 3:
            score -= 15
        elif n_steps <= 20:
            score += 5
        else:
            score -= 20
        return max(0.0, min(100.0, score))

    # ================================================================
    # Publishing & Discovery
    # ================================================================

    def approve_and_publish(self, proposal_id: str,
                           approver: str = "system") -> bool:
        with self._lock:
            proposal = self._proposals.get(proposal_id)
            if not proposal:
                return False
            if proposal.status == ProposalStatus.PUBLISHED:
                return True
            proposal.status = ProposalStatus.PUBLISHED
            proposal.approved_by = approver
            proposal.published_at = datetime.now()
            return True

    def suggest_skills_for_task(self, task_description: str) -> List[SkillProposal]:
        task_lower = task_description.lower()
        task_words = set(re.findall(r'\w{3,}', task_lower))
        scored = []
        for prop in self._proposals.values():
            if prop.status not in (ProposalStatus.APPROVED, ProposalStatus.PUBLISHED):
                continue
            score = 0.0
            for tc in prop.trigger_conditions:
                if tc.lower() in task_lower:
                    score += 2.0
                for tw in task_words:
                    if tw in tc.lower():
                        score += 0.5
            if prop.quality_score >= 70:
                score += 1.0
            if score > 0:
                scored.append((score, prop))

        scored.sort(key=lambda x: -x[0])
        return [p for _, p in scored[:10]]

    # ================================================================
    # Query & Export
    # ================================================================

    def get_pattern_library(self) -> List[SuccessPattern]:
        return list(self._patterns)

    def get_proposals(self, status=None) -> List[SkillProposal]:
        props = list(self._proposals.values())
        if status:
            props = [p for p in props if p.status == status]
        return props

    def export_patterns(self) -> str:
        return json.dumps([p.to_dict() for p in self._patterns],
                         indent=2, ensure_ascii=False, default=str)

    def export_state(self) -> Dict:
        with self._lock:
            return {
                "records_count": len(self._records),
                "patterns_count": len(self._patterns),
                "proposals_count": len(self._proposals),
                "patterns": [p.to_dict() for p in self._patterns],
                "proposal_ids": list(self._proposals.keys()),
            }

    def get_statistics(self) -> Dict[str, Any]:
        with self._lock:
            published = sum(1 for p in self._proposals.values()
                           if p.status == ProposalStatus.PUBLISHED)
            avg_confidence = 0.0
            if self._patterns:
                avg_confidence = sum(p.confidence for p in self._patterns) / len(self._patterns)
            avg_quality = 0.0
            validated = [p for p in self._proposals.values() if p.validation_result]
            if validated:
                avg_quality = sum(p.quality_score for p in validated) / len(validated)
            return {
                "total_records": len(self._records),
                "successful_records": sum(1 for r in self._records if r.success),
                "total_patterns": len(self._patterns),
                "total_proposals": len(self._proposals),
                "published_skills": published,
                "avg_pattern_confidence": round(avg_confidence, 3),
                "avg_quality_score": round(avg_quality, 1),
            }
