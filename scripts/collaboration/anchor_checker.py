#!/usr/bin/env python3
"""
AnchorChecker - V3.7.0 Goal Alignment Engine

Checks whether current output remains aligned with the original task goal
at key decision points (anchor points), preventing goal drift during
long-running Agent tasks.

Design Principles:
- No LLM calls: Pure algorithmic matching (keyword + TF-IDF)
- Trigger only at key nodes: step complete, phase gate, conflict, direction change
- Lightweight: <50ms per check
- Non-blocking: Warnings written to Scratchpad, execution continues
"""

import logging
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

from .models import (
    AnchorResult,
    AnchorTrigger,
    DriftItem,
    DriftSeverity,
    GoalItem,
    GoalItemStatus,
    StructuredGoal,
)

logger = logging.getLogger(__name__)

_GOAL_PATTERNS = [
    (r"(?:需要|必须|shall|must|should|需要实现|需要完成|要求)[：:\s]*(.+?)(?:[。\n；;]|$)", 0.9),
    (r"(?:目标|objective|goal|target)[：:\s]*(.+?)(?:[。\n；;]|$)", 0.85),
    (r"(?:实现|implement|build|create|develop|design)[：:\s]*(.+?)(?:[。\n；;]|$)", 0.8),
    (r"(?:确保|ensure|guarantee|verify)[：:\s]*(.+?)(?:[。\n；;]|$)", 0.75),
    (r"(?:支持|support|provide|enable)[：:\s]*(.+?)(?:[。\n；;]|$)", 0.7),
    (r"^\s*[-•*]\s*(.+?)$", 0.6),
    (r"^\s*\d+[.、)\]]\s*(.+?)$", 0.6),
]

_STOP_WORDS = frozenset(
    [
        "的",
        "了",
        "在",
        "是",
        "我",
        "有",
        "和",
        "就",
        "不",
        "人",
        "都",
        "一",
        "一个",
        "上",
        "也",
        "很",
        "到",
        "说",
        "要",
        "去",
        "你",
        "会",
        "着",
        "没有",
        "看",
        "好",
        "自己",
        "这",
        "他",
        "她",
        "它",
        "们",
        "那",
        "些",
        "什么",
        "怎么",
        "如何",
        "the",
        "a",
        "an",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "need",
        "to",
        "of",
        "in",
        "for",
        "on",
        "with",
        "at",
        "by",
        "from",
        "as",
        "into",
        "through",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "when",
        "up",
        "out",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "i",
        "me",
        "my",
    ]
)


def _tokenize(text: str) -> list[str]:
    result = []
    english_tokens = re.findall(r"[a-zA-Z_]{2,}", text.lower())
    result.extend(english_tokens)

    chinese_segments = re.findall(r"[\u4e00-\u9fff]+", text)
    for seg in chinese_segments:
        if len(seg) <= 4:
            result.append(seg)
        else:
            for i in range(len(seg) - 1):
                result.append(seg[i : i + 2])
            for i in range(len(seg) - 3):
                result.append(seg[i : i + 4])

    filtered = []
    for t in result:
        if t in _STOP_WORDS:
            continue
        if len(t) <= 1 and not re.match(r"[\u4e00-\u9fff]", t):
            continue
        filtered.append(t)
    return filtered


def _compute_tfidf_vectors(documents: list[list[str]]) -> list[dict[str, float]]:
    if not documents:
        return []
    doc_freq = Counter()
    for doc in documents:
        unique_terms = set(doc)
        for term in unique_terms:
            doc_freq[term] += 1
    n_docs = len(documents)
    idf = {term: math.log(n_docs / (freq + 1)) + 1.0 for term, freq in doc_freq.items()}
    vectors = []
    for doc in documents:
        tf = Counter(doc)
        total = len(doc) if doc else 1
        vec = {term: (count / total) * idf.get(term, 1.0) for term, count in tf.items()}
        vectors.append(vec)
    return vectors


def _cosine_similarity(v1: dict[str, float], v2: dict[str, float]) -> float:
    common = set(v1.keys()) & set(v2.keys())
    if not common:
        return 0.0
    dot = sum(v1[k] * v2[k] for k in common)
    norm1 = math.sqrt(sum(v**2 for v in v1.values()))
    norm2 = math.sqrt(sum(v**2 for v in v2.values()))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


class AnchorChecker:
    """
    Goal alignment checker that runs at key decision points.

    Usage:
        checker = AnchorChecker()
        goal = checker.parse_goal("Design a secure auth system with JWT and RBAC")
        result = checker.check(goal, "Implemented JWT token generation...", trigger=AnchorTrigger.STEP_COMPLETE)
        if not result.aligned:
            print(f"DRIFT: {result.recommendation}")
    """

    DRIFT_THRESHOLD = 0.3
    COVERAGE_THRESHOLD = 0.6

    def __init__(self, drift_threshold: float = 0.3, coverage_threshold: float = 0.6):
        self._drift_threshold = drift_threshold
        self._coverage_threshold = coverage_threshold
        self._check_history: list[AnchorResult] = []

    def parse_goal(self, task_description: str) -> StructuredGoal:
        """Parse a free-form task description into a StructuredGoal."""
        items = []
        item_id = 0
        seen = set()

        for pattern, _ in _GOAL_PATTERNS:
            for match in re.finditer(pattern, task_description, re.MULTILINE | re.IGNORECASE):
                desc = match.group(1).strip()
                if desc and len(desc) > 3 and desc not in seen:
                    seen.add(desc)
                    keywords = _tokenize(desc)
                    items.append(
                        GoalItem(
                            item_id=f"G{item_id}",
                            description=desc,
                            keywords=keywords,
                        )
                    )
                    item_id += 1

        if not items:
            keywords = _tokenize(task_description)
            items.append(
                GoalItem(
                    item_id="G0",
                    description=task_description.strip(),
                    keywords=keywords,
                )
            )

        return StructuredGoal(
            goal_id=f"goal_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            original_description=task_description,
            items=items,
            created_at=datetime.now().isoformat(),
        )

    def check(
        self,
        goal: StructuredGoal,
        current_output: str,
        trigger: AnchorTrigger = AnchorTrigger.STEP_COMPLETE,
        _context: dict[str, Any] | None = None,
    ) -> AnchorResult:
        """
        Check whether current output aligns with the original goal.

        Args:
            goal: The structured goal to check against.
            current_output: The current output text to evaluate.
            trigger: What triggered this anchor check.
            context: Optional additional context (e.g., step info).

        Returns:
            AnchorResult with alignment status, coverage, drift info.
        """
        output_tokens = _tokenize(current_output)
        output_text_lower = current_output.lower()

        all_docs = [item.keywords for item in goal.items] + [output_tokens]
        all_vectors = _compute_tfidf_vectors(all_docs)
        output_vector = all_vectors[-1]

        uncovered = []
        drifts = []

        for i, item in enumerate(goal.items):
            item_vector = all_vectors[i]
            sim = _cosine_similarity(item_vector, output_vector)

            keyword_hits = sum(1 for kw in item.keywords if kw in output_text_lower)
            keyword_ratio = keyword_hits / max(len(item.keywords), 1)

            coverage = max(sim, keyword_ratio * 0.8 + sim * 0.2)
            coverage = min(coverage, 1.0)

            item.coverage_score = coverage

            if coverage >= 0.7:
                item.status = GoalItemStatus.FULLY_COVERED
            elif coverage >= 0.3:
                item.status = GoalItemStatus.PARTIALLY_COVERED
                uncovered.append(item.description)
            else:
                item.status = GoalItemStatus.PENDING
                uncovered.append(item.description)

        overall_coverage = goal.overall_coverage
        drift_score = 1.0 - overall_coverage

        output_terms = set(output_tokens)
        goal_terms = set()
        for item in goal.items:
            goal_terms.update(item.keywords)

        extra_terms = output_terms - goal_terms
        if extra_terms and goal_terms:
            extra_ratio = len(extra_terms) / max(len(output_terms), 1)
            if extra_ratio > 0.5:
                drift_score = min(drift_score + 0.1, 1.0)
                drifts.append(
                    DriftItem(
                        content=f"Output contains significant off-topic content ({extra_ratio:.0%} new terms)",
                        severity=DriftSeverity.MEDIUM,
                        reason=f"New terms not in goal: {', '.join(list(extra_terms)[:5])}",
                    )
                )

        aligned = drift_score < self._drift_threshold and overall_coverage >= self._coverage_threshold

        recommendation = ""
        if not aligned:
            if uncovered:
                recommendation = f"Goal drift detected. Uncovered goals: {'; '.join(uncovered[:3])}"
            if drifts:
                recommendation += f" | Drifts: {'; '.join(d.reason for d in drifts[:2])}"

        result = AnchorResult(
            aligned=aligned,
            trigger=trigger,
            coverage=overall_coverage,
            drift_score=drift_score,
            drifts=drifts,
            uncovered_goals=uncovered,
            recommendation=recommendation,
            checked_at=datetime.now().isoformat(),
        )

        self._check_history.append(result)

        if not aligned:
            logger.warning(
                "Anchor check FAILED: coverage=%.0f%%, drift=%.0f%%, trigger=%s, rec=%s",
                overall_coverage * 100,
                drift_score * 100,
                trigger.value,
                recommendation[:80],
            )
        else:
            logger.debug(
                "Anchor check PASSED: coverage=%.0f%%, drift=%.0f%%, trigger=%s",
                overall_coverage * 100,
                drift_score * 100,
                trigger.value,
            )

        return result

    @property
    def check_history(self) -> list[AnchorResult]:
        """Return a copy of the recorded anchor check results.

        Returns:
            List of AnchorResult instances produced by previous checks.
        """
        return list(self._check_history)

    @property
    def drift_count(self) -> int:
        """Count how many historical checks reported drift.

        Returns:
            Number of historical results where alignment failed.
        """
        return sum(1 for r in self._check_history if not r.aligned)

    @property
    def total_checks(self) -> int:
        """Return the total number of recorded anchor checks.

        Returns:
            Count of historical check results.
        """
        return len(self._check_history)

    def reset(self):
        """Clear all recorded anchor check history."""
        self._check_history.clear()
