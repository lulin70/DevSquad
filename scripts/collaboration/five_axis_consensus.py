#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Five-Axis Consensus Engine (P1-4)

Extends voting dimensions from generic to five-axis review:
  1. Correctness: Logic correctness, bug-free, meets requirements
  2. Readability: Code clarity, naming, comments, structure
  3. Architecture: Design patterns, modularity, scalability
  4. Security: Vulnerabilities, input validation, data protection
  5. Performance: Efficiency, resource usage, bottlenecks

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 7.4
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ReviewAxis(Enum):
    """Five axes for code review consensus."""
    CORRECTNESS = "correctness"
    READABILITY = "readability"
    ARCHITECTURE = "architecture"
    SECURITY = "security"
    PERFORMANCE = "performance"
    OPERABILITY = "operability"


@dataclass
class AxisVote:
    """A vote on a specific review axis."""
    axis: ReviewAxis
    score: float  # 0.0 to 1.0
    confidence: float  # 0.0 to 1.0
    comment: str = ""
    voter_id: str = ""

    def is_positive(self) -> bool:
        return self.score >= 0.6

    def is_negative(self) -> bool:
        return self.score < 0.4

    def to_dict(self) -> Dict[str, Any]:
        return {
            "axis": self.axis.value,
            "score": round(self.score, 2),
            "confidence": round(self.confidence, 2),
            "comment": self.comment,
            "voter_id": self.voter_id,
        }


@dataclass
class FiveAxisReview:
    """Complete five-axis review from a single reviewer."""
    reviewer_id: str
    role: str
    votes: List[AxisVote] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def calculate_overall(self) -> float:
        if not self.votes:
            return 0.0
        weighted_sum = sum(v.score * v.confidence for v in self.votes)
        total_weight = sum(v.confidence for v in self.votes)
        self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        return self.overall_score

    def get_vote_for_axis(self, axis: ReviewAxis) -> Optional[AxisVote]:
        for v in self.votes:
            if v.axis == axis:
                return v
        return None


@dataclass
class ConsensusResult:
    """Aggregated consensus result across all reviewers."""
    reviews: List[FiveAxisReview] = field(default_factory=list)
    axis_consensus: Dict[str, float] = field(default_factory=dict)
    overall_consensus: float = 0.0
    verdict: str = ""  # APPROVE / CONDITIONAL / REJECT
    action_items: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_count": len(self.reviews),
            "axis_consensus": {k: round(v, 2) for k, v in self.axis_consensus.items()},
            "overall_consensus": round(self.overall_consensus, 2),
            "verdict": self.verdict,
            "action_items": self.action_items,
        }


class FiveAxisConsensusEngine:
    """
    Five-axis consensus engine for multi-dimensional code review.

    Usage:
        engine = FiveAxisConsensusEngine()
        review = engine.create_review("coder_1", "solo-coder")
        engine.add_axis_vote(review, ReviewAxis.CORRECTNESS, 0.9, 0.8, "Logic looks correct")

        result = engine.compute_consensus([review])
        print(result.verdict)  # APPROVE/CONDITIONAL/REJECT
    """

    DEFAULT_AXIS_WEIGHTS: Dict[ReviewAxis, float] = {
        ReviewAxis.CORRECTNESS: 0.30,
        ReviewAxis.SECURITY: 0.25,
        ReviewAxis.ARCHITECTURE: 0.20,
        ReviewAxis.PERFORMANCE: 0.15,
        ReviewAxis.READABILITY: 0.10,
    }

    CONSENSUS_THRESHOLDS = {
        "APPROVE": 0.75,
        "CONDITIONAL": 0.50,
    }

    def __init__(
        self,
        custom_weights: Optional[Dict[ReviewAxis, float]] = None,
        strict_mode: bool = False,
    ):
        """
        Initialize consensus engine.

        Args:
            custom_weights: Override default axis weights
            strict_mode: If True, any negative vote on security blocks approval
        """
        self._weights = dict(self.DEFAULT_AXIS_WEIGHTS)
        if custom_weights:
            self._weights.update(custom_weights)
        self._strict_mode = strict_mode

    def create_review(
        self,
        reviewer_id: str,
        role: str,
    ) -> FiveAxisReview:
        """Create a new empty review."""
        return FiveAxisReview(
            reviewer_id=reviewer_id,
            role=role,
        )

    def add_axis_vote(
        self,
        review: FiveAxisReview,
        axis: ReviewAxis,
        score: float,
        confidence: float,
        comment: str = "",
    ) -> AxisVote:
        """Add a vote on a specific axis to a review."""
        vote = AxisVote(
            axis=axis,
            score=max(0.0, min(1.0, score)),
            confidence=max(0.0, min(1.0, confidence)),
            comment=comment,
            voter_id=review.reviewer_id,
        )
        review.votes.append(vote)
        return vote

    def compute_consensus(
        self,
        reviews: List[FiveAxisReview],
    ) -> ConsensusResult:
        """
        Compute consensus across multiple reviews.

        Args:
            reviews: List of completed reviews

        Returns:
            ConsensusResult with verdict and details
        """
        result = ConsensusResult(reviews=reviews)

        if not reviews:
            result.verdict = "REJECT"
            return result

        # Calculate per-axis consensus
        axis_scores: Dict[ReviewAxis, List[float]] = {axis: [] for axis in ReviewAxis}

        for review in reviews:
            review.calculate_overall()
            for vote in review.votes:
                axis_scores[vote.axis].append(vote.score * vote.confidence)

        # Weighted average per axis
        for axis, scores in axis_scores.items():
            if scores:
                avg = sum(scores) / len(scores)
                result.axis_consensus[axis.value] = avg

        # Calculate overall weighted consensus
        overall = 0.0
        total_weight = 0.0
        for axis, weight in self._weights.items():
            axis_score = result.axis_consensus.get(axis.value, 0.0)
            overall += axis_score * weight
            total_weight += weight

        result.overall_consensus = overall / total_weight if total_weight > 0 else 0.0

        # Determine verdict
        if self._strict_mode:
            # In strict mode, any low security score triggers conditional/reject
            sec_score = result.axis_consensus.get("security", 1.0)
            if sec_score < 0.5:
                result.verdict = "REJECT"
                result.action_items.append({
                    "axis": "security",
                    "severity": "critical",
                    "message": "Security concerns must be resolved before approval",
                })
            elif result.overall_consensus >= self.CONSENSUS_THRESHOLDS["APPROVE"]:
                result.verdict = "APPROVE"
            elif result.overall_consensus >= self.CONSENSUS_THRESHOLDS["CONDITIONAL"]:
                result.verdict = "CONDITIONAL"
            else:
                result.verdict = "REJECT"
        else:
            if result.overall_consensus >= self.CONSENSUS_THRESHOLDS["APPROVE"]:
                result.verdict = "APPROVE"
            elif result.overall_consensus >= self.CONSENSUS_THRESHOLDS["CONDITIONAL"]:
                result.verdict = "CONDITIONAL"
            else:
                result.verdict = "REJECT"

        # Generate action items for weak axes
        for axis_name, score in result.axis_consensus.items():
            if score < 0.5:
                severity = "critical" if axis_name == "security" else "warning"
                result.action_items.append({
                    "axis": axis_name,
                    "severity": severity,
                    "message": f"{axis_name.capitalize()} score ({score:.2f}) below threshold (0.50)",
                })

        return result

    def get_axis_names(self) -> List[str]:
        """Return list of axis names for this engine's configured weights."""
        return [axis.value for axis in self._weights.keys()]

    def get_default_weights(self) -> Dict[str, float]:
        """Return current weights as string-keyed dict."""
        return {k.value: v for k, v in self._weights.items()}


def create_default_engine() -> FiveAxisConsensusEngine:
    """Create engine with default settings."""
    return FiveAxisConsensusEngine()


def create_strict_engine() -> FiveAxisConsensusEngine:
    """Create engine in strict mode (security veto)."""
    return FiveAxisConsensusEngine(strict_mode=True)


def create_security_focused_engine() -> FiveAxisConsensusEngine:
    """Create engine with higher security weight."""
    custom = {
        ReviewAxis.SECURITY: 0.40,
        ReviewAxis.CORRECTNESS: 0.25,
        ReviewAxis.ARCHITECTURE: 0.15,
        ReviewAxis.PERFORMANCE: 0.10,
        ReviewAxis.READABILITY: 0.10,
    }
    return FiveAxisConsensusEngine(custom_weights=custom)


WALKTHROUGH_AXIS_WEIGHTS: Dict[ReviewAxis, float] = {
    ReviewAxis.CORRECTNESS: 0.25,
    ReviewAxis.SECURITY: 0.25,
    ReviewAxis.ARCHITECTURE: 0.20,
    ReviewAxis.OPERABILITY: 0.15,
    ReviewAxis.READABILITY: 0.15,
}

WALKTHROUGH_OPERABILITY_CHECKS = [
    "deployment_feasibility",
    "logging_standards",
    "monitoring_instrumentation",
    "disaster_recovery",
    "configuration_management",
    "performance_operations",
]


def create_walkthrough_engine() -> FiveAxisConsensusEngine:
    """
    Create walkthrough-specific five-axis consensus engine.

    Replaces Performance axis with Operability axis for code walkthrough:
    - Correctness (0.25): Logic correctness, bug-free
    - Security (0.25): Vulnerabilities, compliance (strict mode veto preserved)
    - Architecture (0.20): Design patterns, modularity
    - Operability (0.15): Deployment, monitoring, disaster recovery, config management
    - Readability (0.15): Code clarity, maintainability

    Operability axis checks:
    - Deployment feasibility (Docker/K8s config completeness)
    - Logging standards (key operations logged, appropriate log levels)
    - Monitoring instrumentation (core metrics monitored, alert thresholds set)
    - Disaster recovery (degradation plan, rollback mechanism)
    - Configuration management (externalized config, environment isolation)
    - Performance operations (resource usage, response time, capacity planning, SLA)
    """
    engine = FiveAxisConsensusEngine.__new__(FiveAxisConsensusEngine)
    engine._weights = dict(WALKTHROUGH_AXIS_WEIGHTS)
    engine._strict_mode = True
    return engine
