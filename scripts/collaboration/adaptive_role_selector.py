#!/usr/bin/env python3
"""
AdaptiveRoleSelector - V3.7.0 Statistics-based Adaptive Role Selection

Intelligently selects role combinations based on historical success rates and performance data.
Uses a three-tier strategy to find optimal roles for different scenarios.

Features:
- Similarity-based role selection from historical tasks
- Intent-based fallback when no similar tasks found
- Success rate filtering to ensure quality
- Manual statistics updates for external integration
- Comprehensive role effectiveness reporting
- Graceful degradation with empty fallback (defers to default RoleMatcher)
"""

import logging
from collections import defaultdict

from .performance_fingerprint import PerformanceFingerprint

logger = logging.getLogger(__name__)


class AdaptiveRoleSelector:
    """
    Adaptive role selector based on historical execution statistics.

    Analyzes success patterns from past executions to recommend optimal
    role combinations for new tasks. Uses a three-tier selection strategy.

    Usage:
        selector = AdaptiveRoleSelector(fingerprint_db)
        roles = selector.select_roles("Implement user authentication")
        # Returns: ["architect", "coder", "tester"] or [] if no data

        selector.update_stats(["architect", "coder"], True, 12.5)
        report = selector.get_role_report()

    Selection Strategy (Priority Order):
        1. Similar task history → Use most successful role combination
        2. Intent-based matching → Use best roles for that intent category
        3. No data available → Return empty list (fallback to default RoleMatcher)

    Attributes:
        _fp: PerformanceFingerprint instance for accessing historical data.
        _role_stats: Cached dictionary of per-role statistics.
    """

    def __init__(self, fingerprint_db: PerformanceFingerprint | None = None):
        """
        Initialize the selector with a fingerprint database.

        Args:
            fingerprint_db: Optional PerformanceFingerprint instance.
                          If None, creates a new instance.
        """
        self._fp = fingerprint_db or PerformanceFingerprint()
        self._role_stats: dict[str, dict] = {}

    def select_roles(
        self,
        task: str,
        intent: str | None = None,
        min_success_rate: float = 0.5,
        max_roles: int = 5,
    ) -> list[str]:
        """
        Select optimal role combination based on historical statistics.

        Uses a three-tier strategy:
        1. If similar tasks exist in history → Use highest success rate combination
        2. If intent is provided and has history → Use best roles for that intent
        3. If neither has data → Return empty list (fallback to RoleMatcher)

        Args:
            task: Task description text.
            intent: Optional intent classification string.
            min_success_rate: Minimum success rate threshold (default: 0.5).
            max_roles: Maximum number of roles to return (default: 5).

        Returns:
            List of recommended role names. Empty list if no suitable data found
            (caller should fall back to default RoleMatcher).
        """
        similar_cases = self._fp.find_similar(task, top_k=5)

        if similar_cases:
            roles = self._select_from_similar_tasks(similar_cases, min_success_rate, max_roles)
            if roles:
                logger.debug("Selected roles from similar tasks: %s", roles)
                return roles

        if intent:
            roles = self._select_by_intent(intent, min_success_rate, max_roles)
            if roles:
                logger.debug("Selected roles by intent '%s': %s", intent, roles)
                return roles

        logger.debug("No historical data for role selection, returning empty (fallback)")
        return []

    def update_stats(self, roles: list[str], success: bool, duration_s: float) -> None:
        """
        Manually update role statistics (for external integration).

        Allows external systems to feed execution results into the selector's
        statistics cache without going through the full fingerprint recording process.

        Args:
            roles: List of role names used in the execution.
            success: Whether the execution was successful.
            duration_s: Execution duration in seconds.
        """
        for role in roles:
            if role not in self._role_stats:
                self._role_stats[role] = {
                    "total": 0,
                    "successes": 0,
                    "durations": [],
                }

            self._role_stats[role]["total"] += 1
            if success:
                self._role_stats[role]["successes"] += 1
            self._role_stats[role]["durations"].append(duration_s)

        logger.debug(
            "Updated stats for roles %s (success=%s, duration=%.2fs)",
            roles,
            success,
            duration_s,
        )

    def get_role_report(self) -> dict[str, dict]:
        """
        Generate comprehensive role effectiveness report.

        Combines cached manual stats with fingerprint database statistics
        to provide a complete view of role performance.

        Returns:
            Dictionary mapping role name to performance metrics:
            {
                "architect": {
                    "total": 50,
                    "successes": 45,
                    "success_rate": 0.9,
                    "avg_duration": 8.2,
                },
                ...
            }
        """
        report: dict[str, dict] = {}

        for role, stats in self._role_stats.items():
            total = stats["total"]
            successes = stats["successes"]
            durations = stats["durations"]

            avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0
            success_rate = round(successes / total, 4) if total > 0 else 0.0

            report[role] = {
                "total": total,
                "successes": successes,
                "success_rate": success_rate,
                "avg_duration": avg_duration,
            }

        fp_stats = self._fp.get_stats()
        for role_entry in fp_stats.get("top_roles", []):
            role_name = role_entry["role"]
            if role_name not in report:
                report[role_name] = {
                    "total": role_entry["count"],
                    "successes": 0,
                    "success_rate": 0.0,
                    "avg_duration": 0.0,
                }

        return report

    def _select_from_similar_tasks(
        self,
        similar_cases: list[dict],
        min_success_rate: float,
        max_roles: int,
    ) -> list[str]:
        """
        Select roles based on similar task history.

        Finds successful cases among similar tasks and extracts the most
        common high-performing role combination.

        Args:
            similar_cases: List of similar case dictionaries from find_similar().
            min_success_rate: Minimum success rate threshold.
            max_roles: Maximum number of roles to return.

        Returns:
            List of recommended roles, or empty if no suitable candidates.
        """
        successful_combos: dict[tuple, dict] = {}
        combo_success_counts: dict[tuple, int] = defaultdict(int)
        combo_total_counts: dict[tuple, int] = defaultdict(int)

        for case in similar_cases:
            roles = case.get("roles_used", [])
            if not roles:
                continue

            combo_key = tuple(sorted(roles))
            combo_total_counts[combo_key] += 1

            if case.get("success", False):
                combo_success_counts[combo_key] += 1
                if combo_key not in successful_combos:
                    successful_combos[combo_key] = {
                        "roles": roles,
                        "avg_duration": case.get("total_duration", 0.0),
                        "count": 1,
                        "similarity": case.get("similarity", 0.0),
                    }
                else:
                    existing = successful_combos[combo_key]
                    n = existing["count"]
                    existing["avg_duration"] = (existing["avg_duration"] * n + case.get("total_duration", 0.0)) / (
                        n + 1
                    )
                    existing["count"] += 1
                    existing["similarity"] = max(existing["similarity"], case.get("similarity", 0.0))

        if not successful_combos:
            return []

        best_combo = None
        best_score = -1

        for combo_key, info in successful_combos.items():
            total = combo_total_counts.get(combo_key, 1)
            successes = combo_success_counts.get(combo_key, 0)
            success_rate = successes / total if total > 0 else 0.0

            if success_rate < min_success_rate:
                continue

            score = success_rate * 0.6 + info["similarity"] * 0.4

            if score > best_score:
                best_score = score
                best_combo = combo_key

        if best_combo:
            roles = list(best_combo)[:max_roles]
            return roles

        return []

    def _select_by_intent(
        self,
        intent: str,
        min_success_rate: float,
        max_roles: int,
    ) -> list[str]:
        """
        Select roles based on intent category history.

        Searches fingerprints with matching intent and finds the most
        successful role combination for that category.

        Args:
            intent: Intent classification string to match.
            min_success_rate: Minimum success rate threshold.
            max_roles: Maximum number of roles to return.

        Returns:
            List of recommended roles, or empty if no suitable candidates.
        """
        intent_matches = [fp for fp in self._fp.get_all_fingerprints() if fp.get("intent") == intent]

        if not intent_matches:
            return []

        role_combo_stats: dict[tuple, dict] = defaultdict(lambda: {"total": 0, "successes": 0})

        for fp in intent_matches:
            roles = fp.get("roles_used", [])
            if not roles:
                continue

            combo_key = tuple(sorted(roles))
            role_combo_stats[combo_key]["total"] += 1
            if fp.get("success", False):
                role_combo_stats[combo_key]["successes"] += 1

        best_combo = None
        best_success_rate: float = -1.0

        for combo_key, stats in role_combo_stats.items():
            total = stats["total"]
            successes = stats["successes"]
            success_rate = successes / total if total > 0 else 0.0

            if success_rate >= min_success_rate and success_rate > best_success_rate:
                best_success_rate = success_rate
                best_combo = combo_key

        if best_combo:
            roles = list(best_combo)[:max_roles]
            return roles

        return []
