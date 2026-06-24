#!/usr/bin/env python3
"""
SimilarTaskRecommender - V3.7.0 Historical Fingerprint-based Task Recommendation

Provides intelligent task configuration recommendations based on historical execution fingerprints.
Uses TF-IDF similarity to find similar past tasks and extracts optimal configurations.

Features:
- Role combination recommendation from successful cases
- Intent prediction based on similar tasks
- Duration estimation from historical data
- Confidence scoring based on similarity strength
- Graceful degradation on cold start (no historical data)
"""

import logging
from collections import Counter
from typing import Any

from .performance_fingerprint import PerformanceFingerprint

logger = logging.getLogger(__name__)


class SimilarTaskRecommender:
    """
    Task configuration recommender based on historical execution fingerprints.

    Analyzes past task executions to recommend optimal role combinations,
    intents, and estimate execution duration for new tasks.

    Usage:
        recommender = SimilarTaskRecommender(fingerprint_db)
        result = recommender_recommend("Implement user authentication")
        print(result["recommended_roles"])  # ["architect", "coder", "tester"]
        print(result["confidence"])  # "high"

    Attributes:
        _fp: PerformanceFingerprint instance for accessing historical data.
    """

    def __init__(self, fingerprint_db: PerformanceFingerprint | None = None):
        """
        Initialize the recommender with a fingerprint database.

        Args:
            fingerprint_db: Optional PerformanceFingerprint instance.
                          If None, creates a new instance.
        """
        self._fp = fingerprint_db or PerformanceFingerprint()

    def recommend(self, task: str, top_k: int = 3) -> dict[str, Any]:
        """
        Recommend optimal configuration for a given task.

        Analyzes historical fingerprints to find similar tasks and extract
        the most successful configuration patterns.

        Args:
            task: Task description text to get recommendations for.
            top_k: Number of similar cases to consider (default: 3).

        Returns:
            Dictionary containing:
            - similar_cases: List of similar historical cases with details
            - recommended_roles: List of recommended role names
            - recommended_intent: Most common intent from similar cases
            - estimated_duration_s: Estimated execution time in seconds
            - confidence: "high", "medium", or "low" based on max similarity
        """
        similar_cases = self._fp.find_similar(task, top_k=top_k)

        if not similar_cases:
            return {
                "similar_cases": [],
                "recommended_roles": [],
                "recommended_intent": None,
                "estimated_duration_s": 0.0,
                "confidence": "low",
            }

        formatted_cases = []
        for case in similar_cases:
            formatted_cases.append(
                {
                    "task": case.get("task", ""),
                    "roles": case.get("roles_used", []),
                    "intent": case.get("intent"),
                    "success": case.get("success", False),
                    "duration_s": case.get("total_duration", 0.0),
                    "similarity": case.get("similarity", 0.0),
                }
            )

        successful_cases = [c for c in formatted_cases if c["success"]]

        if successful_cases:
            recommended_roles = self._extract_most_common_roles(successful_cases)
            recommended_intent = self._extract_most_common_intent(successful_cases)
            estimated_duration = self._calculate_avg_duration(successful_cases)
        else:
            all_roles = []
            for case in formatted_cases:
                all_roles.extend(case.get("roles", []))
            recommended_roles = list(set(all_roles)) if all_roles else []
            recommended_intent = formatted_cases[0].get("intent") if formatted_cases else None
            estimated_duration = self._calculate_avg_duration(formatted_cases)

        max_similarity = max(c["similarity"] for c in formatted_cases) if formatted_cases else 0.0
        confidence = self._determine_confidence(max_similarity)

        return {
            "similar_cases": formatted_cases,
            "recommended_roles": recommended_roles,
            "recommended_intent": recommended_intent,
            "estimated_duration_s": round(estimated_duration, 2),
            "confidence": confidence,
        }

    def get_role_suggestion(self, task: str) -> list[str]:
        """
        Quick method to get role suggestions for a task.

        Simplified version of recommend() that only returns the recommended roles.

        Args:
            task: Task description text.

        Returns:
            List of recommended role names. Empty list if no data available.
        """
        result = self.recommend(task, top_k=3)
        return result.get("recommended_roles", [])  # type: ignore[no-any-return]

    def _extract_most_common_roles(self, cases: list[dict]) -> list[str]:
        """
        Extract the most common role combination from successful cases.

        Strategy:
        1. Find the most frequent role combination (role_combo)
        2. If no clear winner, return union of all roles from top cases

        Args:
            cases: List of successful case dictionaries.

        Returns:
            List of recommended role names.
        """
        role_combos: Counter = Counter()
        all_roles: list[str] = []

        for case in cases:
            roles = case.get("roles", [])
            if roles:
                combo_key = tuple(sorted(roles))
                role_combos[combo_key] += 1
                all_roles.extend(roles)

        if role_combos:
            most_common_combo = role_combos.most_common(1)[0][0]
            return list(most_common_combo)

        return list(set(all_roles)) if all_roles else []

    def _extract_most_common_intent(self, cases: list[dict]) -> str | None:
        """
        Extract the most common intent from successful cases.

        Args:
            cases: List of successful case dictionaries.

        Returns:
            Most common intent string, or None if no intents available.
        """
        intents = [case.get("intent") for case in cases if case.get("intent")]

        if intents:
            intent_counts = Counter(intents)
            return intent_counts.most_common(1)[0][0]

        return None

    def _calculate_avg_duration(self, cases: list[dict]) -> float:
        """
        Calculate average duration from cases.

        Args:
            cases: List of case dictionaries with duration_s field.

        Returns:
            Average duration in seconds (0.0 if no valid durations).
        """
        durations = [case.get("duration_s", 0.0) for case in cases if case.get("duration_s", 0.0) > 0]

        if durations:
            return sum(durations) / len(durations)  # type: ignore[no-any-return]

        return 0.0

    def _determine_confidence(self, max_similarity: float) -> str:
        """
        Determine confidence level based on maximum similarity score.

        Thresholds:
        - >0.7: high confidence (strong match found)
        - >0.4: medium confidence (moderate match)
        - <=0.4: low confidence (weak or no match)

        Args:
            max_similarity: Highest similarity score from similar cases.

        Returns:
            Confidence level string: "high", "medium", or "low".
        """
        if max_similarity > 0.7:
            return "high"
        elif max_similarity > 0.4:
            return "medium"
        else:
            return "low"
