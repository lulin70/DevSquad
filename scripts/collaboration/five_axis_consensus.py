#!/usr/bin/env python3
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
from typing import Any

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
        """Check whether this vote is positive.

        Returns:
            True if the score is greater than or equal to 0.6.
        """
        return self.score >= 0.6

    def is_negative(self) -> bool:
        """Check whether this vote is negative.

        Returns:
            True if the score is strictly below 0.4.
        """
        return self.score < 0.4

    def to_dict(self) -> dict[str, Any]:
        """Serialize the axis vote to a dictionary.

        Returns:
            Dictionary with axis name, rounded score and confidence, comment,
            and voter_id.
        """
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
    votes: list[AxisVote] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def calculate_overall(self) -> float:
        """Compute and store the confidence-weighted overall score.

        Returns:
            The weighted average of vote scores; 0.0 when there are no votes
            or total confidence is zero.
        """
        if not self.votes:
            return 0.0
        weighted_sum = sum(v.score * v.confidence for v in self.votes)
        total_weight = sum(v.confidence for v in self.votes)
        self.overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        return self.overall_score

    def get_vote_for_axis(self, axis: ReviewAxis) -> AxisVote | None:
        """Return the vote cast on a specific review axis, if any.

        Args:
            axis: ReviewAxis to look up.

        Returns:
            The matching AxisVote, or None when no vote exists for that axis.
        """
        for v in self.votes:
            if v.axis == axis:
                return v
        return None


@dataclass
class ConsensusResult:
    """Aggregated consensus result across all reviewers."""

    reviews: list[FiveAxisReview] = field(default_factory=list)
    axis_consensus: dict[str, float] = field(default_factory=dict)
    overall_consensus: float = 0.0
    verdict: str = ""  # APPROVE / CONDITIONAL / REJECT
    action_items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the consensus result to a dictionary.

        Returns:
            Dictionary containing review count, per-axis consensus scores,
            overall consensus, verdict, and action items.
        """
        return {
            "review_count": len(self.reviews),
            "axis_consensus": {k: round(v, 2) for k, v in self.axis_consensus.items()},
            "overall_consensus": round(self.overall_consensus, 2),
            "verdict": self.verdict,
            "action_items": self.action_items,
        }


# ---------------------------------------------------------------------------
# V4.3.0 Phase 3 P3-4: FiveAxisEvaluationResult + heuristic evaluators
# (defined before FiveAxisConsensusEngine so the engine class can reference
#  FiveAxisEvaluationResult in its method signatures without NameError.)
# ---------------------------------------------------------------------------


@dataclass
class FiveAxisEvaluationResult:
    """5-axis heuristic evaluation result (V4.3.0 Phase 3 P3-4).

    Returned by :meth:`FiveAxisConsensusEngine.evaluate`. This is a
    heuristic, non-LLM evaluation — it scores artifacts using simple
    code-quality heuristics. For LLM-powered review, use
    :meth:`compute_consensus` with reviewer-submitted
    :class:`FiveAxisReview` objects.

    Attributes
    ----------
    correctness:
        Score 0.0-1.0 — presence of error handling (raise/assert/try-except).
    readability:
        Score 0.0-1.0 — line length, comments/docstring, snake_case naming.
    architecture:
        Score 0.0-1.0 — class/def layering, modular imports, no God Class.
    security:
        Score 0.0-1.0 — absence of eval/exec/os.system, no hardcoded secrets,
        input validation.
    performance:
        Score 0.0-1.0 — no deep nesting, no O(n²) list-in-list, generator use.
    overall:
        Weighted overall score 0.0-1.0 using DEFAULT_AXIS_WEIGHTS.
    verdict:
        APPROVE / CONDITIONAL / REJECT based on overall score.
    notes:
        Per-axis human-readable explanation of scoring rationale.
    """

    correctness: float
    readability: float
    architecture: float
    security: float
    performance: float
    overall: float
    verdict: str
    notes: dict[str, str] = field(default_factory=dict)

    def to_markdown(self) -> str:
        """Render the result as a Markdown section.

        Returns
        -------
        str
            Markdown-formatted five-axis review report.
        """
        lines = [
            "## Five-Axis Review (heuristic, V4.3.0 Phase 3)",
            "",
            f"**Verdict**: `{self.verdict}`  |  **Overall**: `{self.overall:.2f}`",
            "",
            "| Axis | Score | Notes |",
            "|------|-------|-------|",
            f"| Correctness | {self.correctness:.2f} | {self.notes.get('correctness', '')} |",
            f"| Readability | {self.readability:.2f} | {self.notes.get('readability', '')} |",
            f"| Architecture | {self.architecture:.2f} | {self.notes.get('architecture', '')} |",
            f"| Security | {self.security:.2f} | {self.notes.get('security', '')} |",
            f"| Performance | {self.performance:.2f} | {self.notes.get('performance', '')} |",
            "",
            "_Heuristic evaluation — for LLM-powered review use `compute_consensus(reviews)`._",
        ]
        return "\n".join(lines)


def _evaluate_correctness(code: str) -> tuple[float, str]:
    """Heuristic: error-handling constructs present (V4.3.0 Phase 3)."""
    score = 0.0
    notes = []
    if "raise " in code or "raise\t" in code:
        score += 0.2
        notes.append("raise found")
    if "assert " in code:
        score += 0.2
        notes.append("assert found")
    if "try:" in code and "except" in code:
        score += 0.2
        notes.append("try/except found")
    if "pass" not in code:
        score += 0.1
        notes.append("no `pass` placeholder")
    # Cap at 0.9 (heuristic, never claim perfection)
    score = min(score, 0.9)
    if not notes:
        notes.append("no error-handling markers found")
    return score, "; ".join(notes)


def _evaluate_readability(code: str) -> tuple[float, str]:
    """Heuristic: line length / comments / snake_case (V4.3.0 Phase 3)."""
    score = 0.0
    notes = []
    lines = code.splitlines()
    long_lines = sum(1 for ln in lines if len(ln) > 100)
    if long_lines == 0 and lines:
        score += 0.2
        notes.append("lines < 100 chars")
    if "#" in code or '"""' in code or "'''" in code:
        score += 0.3
        notes.append("comments/docstring present")
    # snake_case detection: function defs use snake_case
    import re

    snake_funcs = re.findall(r"def\s+([a-z_][a-z0-9_]*)\s*\(", code)
    if snake_funcs:
        score += 0.2
        notes.append(f"{len(snake_funcs)} snake_case function(s)")
    if not notes:
        notes.append("no readability markers")
    return min(score, 0.9), "; ".join(notes)


def _evaluate_architecture(code: str) -> tuple[float, str]:
    """Heuristic: class/def layering / modular imports (V4.3.0 Phase 3)."""
    score = 0.0
    notes = []
    if "class " in code and "def " in code:
        score += 0.3
        notes.append("class + def layering")
    if "import " in code or "from " in code:
        score += 0.2
        notes.append("modular imports")
    # God Class detection: > 500 lines in a single class block (rough heuristic)
    if len(code.splitlines()) < 500:
        score += 0.2
        notes.append("no God Class (<500 lines)")
    if not notes:
        notes.append("no architecture markers")
    return min(score, 0.9), "; ".join(notes)


def _evaluate_security(code: str) -> tuple[float, str]:
    """Heuristic: no eval/exec/os.system / no hardcoded secrets (V4.3.0 Phase 3)."""
    score = 0.0
    notes = []
    dangerous = []
    if "eval(" in code:
        dangerous.append("eval")
    if "exec(" in code:
        dangerous.append("exec")
    if "os.system(" in code:
        dangerous.append("os.system")
    if not dangerous:
        score += 0.3
        notes.append("no eval/exec/os.system")
    else:
        notes.append(f"dangerous: {','.join(dangerous)}")
    # Hardcoded secret heuristic: sk-/AKIA/password=
    import re

    secret_patterns = [
        r"sk-[a-zA-Z0-9]{20,}",
        r"AKIA[A-Z0-9]{16}",
        r"password\s*=\s*['\"][^'\"]+['\"]",
    ]
    secrets_found = sum(1 for p in secret_patterns if re.search(p, code))
    if secrets_found == 0:
        score += 0.3
        notes.append("no hardcoded secrets")
    else:
        notes.append(f"{secrets_found} hardcoded secret pattern(s)")
    # Input validation heuristic
    if "validate" in code.lower() or "isinstance(" in code:
        score += 0.2
        notes.append("input validation present")
    if not notes:
        notes.append("no security markers")
    return min(score, 0.9), "; ".join(notes)


def _evaluate_performance(code: str) -> tuple[float, str]:
    """Heuristic: no deep nesting / no O(n²) / generator use (V4.3.0 Phase 3)."""
    score = 0.0
    notes = []
    lines = code.splitlines()
    # Deep nesting: indent depth > 6 levels (24 spaces)
    deep = sum(1 for ln in lines if ln.startswith(" " * 24) or ln.startswith("\t" * 6))
    if deep == 0:
        score += 0.2
        notes.append("no deep nesting")
    else:
        notes.append(f"{deep} deep-nested line(s)")
    # O(n²) heuristic: `for ... in` inside another `for ... in` with `in` list op
    if "for " in code and "[x for" in code:
        # Look for nested list comprehension
        import re

        nested = re.findall(r"\[[^\]]*for[^\]]*for[^\]]*\]", code)
        if not nested:
            score += 0.2
            notes.append("no nested list comp")
        else:
            notes.append(f"{len(nested)} nested list comp(s)")
    else:
        score += 0.2
        notes.append("no list comp nesting")
    # Generator use
    if "yield " in code or "yieldfrom" in code.replace(" ", ""):
        score += 0.1
        notes.append("generator present")
    if not notes:
        notes.append("no performance markers")
    return min(score, 0.9), "; ".join(notes)


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

    DEFAULT_AXIS_WEIGHTS: dict[ReviewAxis, float] = {
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
        custom_weights: dict[ReviewAxis, float] | None = None,
        strict_mode: bool = False,
        replace_weights: bool = False,
    ):
        """
        Initialize consensus engine.

        Args:
            custom_weights: Override default axis weights
            strict_mode: If True, any negative vote on security blocks approval
            replace_weights: If True, custom_weights fully replace defaults instead of merging
        """
        if replace_weights and custom_weights:
            self._weights = dict(custom_weights)
        else:
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
        reviews: list[FiveAxisReview],
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
        axis_scores: dict[ReviewAxis, list[float]] = {axis: [] for axis in ReviewAxis}

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
                result.action_items.append(
                    {
                        "axis": "security",
                        "severity": "critical",
                        "message": "Security concerns must be resolved before approval",
                    }
                )
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
                result.action_items.append(
                    {
                        "axis": axis_name,
                        "severity": severity,
                        "message": f"{axis_name.capitalize()} score ({score:.2f}) below threshold (0.50)",
                    }
                )

        return result

    def get_axis_names(self) -> list[str]:
        """Return list of axis names for this engine's configured weights."""
        return [axis.value for axis in self._weights]

    def get_default_weights(self) -> dict[str, float]:
        """Return current weights as string-keyed dict."""
        return {k.value: v for k, v in self._weights.items()}

    def evaluate(
        self,
        artifacts: dict[str, Any],
        reviewer_id: str = "heuristic",
    ) -> FiveAxisEvaluationResult:
        """Heuristic 5-axis evaluation of code artifacts (V4.3.0 Phase 3 P3-4).

        Performs a non-LLM heuristic evaluation of the supplied artifacts
        using the engine's configured axis weights. The evaluation scores
        five axes (correctness / readability / architecture / security /
        performance) via simple code-quality heuristics, then aggregates
        them into a weighted overall score and verdict.

        Args:
            artifacts: dict with optional keys ``code`` (str), ``tests``
                (list[str]), ``docs`` (str). At least ``code`` should be
                provided for a meaningful evaluation; missing keys default
                to empty.
            reviewer_id: Identifier for the evaluation source (default
                ``"heuristic"``). Stored in the result for traceability.

        Returns:
            :class:`FiveAxisEvaluationResult` with per-axis scores 0.0-1.0,
            weighted overall score, verdict (APPROVE/CONDITIONAL/REJECT),
            and per-axis notes explaining the scoring rationale.

        Notes:
            - This is a heuristic, non-LLM evaluation. For LLM-powered
              review use :meth:`compute_consensus` with reviewer-submitted
              :class:`FiveAxisReview` objects.
            - Scores are capped at 0.9 to reflect heuristic uncertainty.
            - The ``reviewer_id`` parameter is currently recorded for
              traceability but does not affect scoring. V4.4.0 may
              integrate it into the audit log.
        """
        _ = reviewer_id  # reserved for V4.4.0 audit log integration
        return evaluate_artifacts(artifacts, weights=self._weights)


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


WALKTHROUGH_AXIS_WEIGHTS: dict[ReviewAxis, float] = {
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
    return FiveAxisConsensusEngine(
        custom_weights=WALKTHROUGH_AXIS_WEIGHTS,
        strict_mode=True,
        replace_weights=True,
    )


# V4.3.0 Phase 3 P3-4: evaluate_artifacts() — module-level helper invoked by
# FiveAxisConsensusEngine.evaluate(). Defined after the engine class so it can
# reference DEFAULT_AXIS_WEIGHTS and CONSENSUS_THRESHOLDS.


def evaluate_artifacts(
    artifacts: dict[str, Any],
    weights: dict[ReviewAxis, float] | None = None,
) -> FiveAxisEvaluationResult:
    """Heuristic 5-axis evaluation of code artifacts (V4.3.0 Phase 3 P3-4).

    Args:
        artifacts: dict with optional keys ``code`` (str), ``tests`` (list[str]),
            ``docs`` (str). At least ``code`` should be provided for a
            meaningful evaluation; missing keys default to empty.
        weights: Optional axis-weight override. Defaults to
            :attr:`FiveAxisConsensusEngine.DEFAULT_AXIS_WEIGHTS`.

    Returns:
        :class:`FiveAxisEvaluationResult` with per-axis scores 0.0-1.0,
        weighted overall score, and verdict.

    Notes:
        - This is a heuristic, non-LLM evaluation. For LLM-powered review
          use :meth:`FiveAxisConsensusEngine.compute_consensus` with
          reviewer-submitted :class:`FiveAxisReview` objects.
        - Scores are capped at 0.9 to reflect heuristic uncertainty.
    """
    code = str(artifacts.get("code", "")) if artifacts.get("code") is not None else ""
    # tests/docs are accepted but not yet scored (reserved for V4.4.0)
    # _ = artifacts.get("tests", [])
    # _ = artifacts.get("docs", "")

    correctness, c_note = _evaluate_correctness(code)
    readability, r_note = _evaluate_readability(code)
    architecture, a_note = _evaluate_architecture(code)
    security, s_note = _evaluate_security(code)
    performance, p_note = _evaluate_performance(code)

    weights = weights or FiveAxisConsensusEngine.DEFAULT_AXIS_WEIGHTS
    overall = (
        correctness * weights.get(ReviewAxis.CORRECTNESS, 0.0)
        + readability * weights.get(ReviewAxis.READABILITY, 0.0)
        + architecture * weights.get(ReviewAxis.ARCHITECTURE, 0.0)
        + security * weights.get(ReviewAxis.SECURITY, 0.0)
        + performance * weights.get(ReviewAxis.PERFORMANCE, 0.0)
    )
    # Normalize by total weight
    total_weight = sum(weights.values()) or 1.0
    overall = overall / total_weight

    thresholds = FiveAxisConsensusEngine.CONSENSUS_THRESHOLDS
    if overall >= thresholds["APPROVE"]:
        verdict = "APPROVE"
    elif overall >= thresholds["CONDITIONAL"]:
        verdict = "CONDITIONAL"
    else:
        verdict = "REJECT"

    return FiveAxisEvaluationResult(
        correctness=correctness,
        readability=readability,
        architecture=architecture,
        security=security,
        performance=performance,
        overall=overall,
        verdict=verdict,
        notes={
            "correctness": c_note,
            "readability": r_note,
            "architecture": a_note,
            "security": s_note,
            "performance": p_note,
        },
    )

