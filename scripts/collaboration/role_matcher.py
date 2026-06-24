#!/usr/bin/env python3

import logging
from typing import Any

from .models import ROLE_REGISTRY, resolve_role_id

logger = logging.getLogger(__name__)

ROLE_TEMPLATES = {
    rid: {"name": rdef.name, "prompt": rdef.prompt, "keywords": rdef.keywords} for rid, rdef in ROLE_REGISTRY.items()
}


class RoleMatcher:
    """Role matching engine based on keyword analysis, enhanced with adaptive and similarity-based recommendations."""

    def __init__(self) -> None:
        """Initialize RoleMatcher with lazy-loaded enhanced components."""
        self._fingerprint_db: Any = None
        self._adaptive_selector: Any = None
        self._similar_recommender: Any = None

    def _ensure_fingerprint(self) -> Any:
        """Lazy-initialize PerformanceFingerprint."""
        if self._fingerprint_db is None:
            try:
                from .performance_fingerprint import PerformanceFingerprint
                self._fingerprint_db = PerformanceFingerprint()
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.debug("PerformanceFingerprint unavailable: %s", e)
                self._fingerprint_db = False  # sentinel: tried and failed
        return self._fingerprint_db if self._fingerprint_db is not False else None

    def _ensure_adaptive_selector(self) -> Any:
        """Lazy-initialize AdaptiveRoleSelector."""
        if self._adaptive_selector is None:
            fp = self._ensure_fingerprint()
            if fp is None:
                return None
            try:
                from .adaptive_role_selector import AdaptiveRoleSelector
                self._adaptive_selector = AdaptiveRoleSelector(fingerprint_db=fp)
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.debug("AdaptiveRoleSelector unavailable: %s", e)
                self._adaptive_selector = False
        return self._adaptive_selector if self._adaptive_selector is not False else None

    def _ensure_similar_recommender(self) -> Any:
        """Lazy-initialize SimilarTaskRecommender."""
        if self._similar_recommender is None:
            fp = self._ensure_fingerprint()
            if fp is None:
                return None
            try:
                from .similar_task_recommender import SimilarTaskRecommender
                self._similar_recommender = SimilarTaskRecommender(fingerprint_db=fp)
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.debug("SimilarTaskRecommender unavailable: %s", e)
                self._similar_recommender = False
        return self._similar_recommender if self._similar_recommender is not False else None

    def analyze_task(self, task_description: str) -> list[dict[str, Any]]:
        """
        Analyze a task description and match appropriate roles.

        Args:
            task_description: Task description text

        Returns:
            List of matched roles: [{"role_id": "...", "name": "...", "reason": "..."}]
        """
        task_lower = task_description.lower()
        matched: list[dict[str, Any]] = []

        for role_id, role_info in ROLE_TEMPLATES.items():
            score = 0
            matched_keywords = []
            for kw in role_info["keywords"]:
                if kw in task_lower:
                    score += 1
                    matched_keywords.append(kw)

            if score > 0:
                confidence = min(score / len(role_info["keywords"]), 1.0)
                matched.append(
                    {
                        "role_id": role_id,
                        "name": role_info["name"],
                        "confidence": confidence,
                        "matched_keywords": matched_keywords,
                        "reason": f"匹配关键词: {', '.join(matched_keywords)}",
                    }
                )

        matched.sort(key=lambda x: x["confidence"], reverse=True)

        if not matched:
            matched.append(
                {
                    "role_id": "solo-coder",
                    "name": "独立开发者",
                    "confidence": 0.5,
                    "matched_keywords": [],
                    "reason": "默认角色：无明确关键词匹配",
                }
            )

        return matched

    def analyze_task_enhanced(self, task_description: str) -> list[dict[str, Any]]:
        """
        Enhanced task analysis combining keyword matching with adaptive and similarity-based recommendations.

        Pipeline:
        1. Run keyword-based matching (analyze_task)
        2. Try AdaptiveRoleSelector for historical success-rate recommendations
        3. Try SimilarTaskRecommender for TF-IDF similarity recommendations
        4. Merge: add roles from adaptive/similar that are not in keyword results,
           with lower confidence and appropriate reason

        Falls back gracefully to keyword-only results when no historical data exists.

        Args:
            task_description: Task description text

        Returns:
            List of matched roles with enhanced recommendations merged in.
        """
        # Step 1: Keyword-based matching (always runs)
        matched = self.analyze_task(task_description)
        existing_ids = {r["role_id"] for r in matched}

        # Step 2: Adaptive role selection based on historical success rates
        adaptive_roles = []
        selector = self._ensure_adaptive_selector()
        if selector is not None:
            try:
                adaptive_roles = selector.select_roles(task_description)
            except (ValueError, AttributeError, RuntimeError, OSError) as e:
                logger.debug("AdaptiveRoleSelector.select_roles failed: %s", e)

        # Step 3: Similar task recommendation based on TF-IDF
        similar_roles = []
        similar_confidence = "low"
        recommender = self._ensure_similar_recommender()
        if recommender is not None:
            try:
                rec_result = recommender.recommend(task_description)
                similar_roles = rec_result.get("recommended_roles", [])
                similar_confidence = rec_result.get("confidence", "low")
            except (ValueError, AttributeError, RuntimeError, OSError) as e:
                logger.debug("SimilarTaskRecommender.recommend failed: %s", e)

        # Step 4: Merge adaptive and similar recommendations into keyword results
        # Map confidence string to numeric value for new entries
        confidence_map = {"high": 0.6, "medium": 0.45, "low": 0.3}

        # Add adaptive-only roles
        for role_name in adaptive_roles:
            if role_name not in existing_ids:
                template = ROLE_TEMPLATES.get(role_name, {"name": role_name})
                matched.append(
                    {
                        "role_id": role_name,
                        "name": template.get("name", role_name),
                        "confidence": 0.4,
                        "matched_keywords": [],
                        "reason": "历史成功率推荐（AdaptiveRoleSelector）",
                        "source": "adaptive",
                    }
                )
                existing_ids.add(role_name)

        # Add similar-only roles
        for role_name in similar_roles:
            if role_name not in existing_ids:
                template = ROLE_TEMPLATES.get(role_name, {"name": role_name})
                conf = confidence_map.get(similar_confidence, 0.3)
                matched.append(
                    {
                        "role_id": role_name,
                        "name": template.get("name", role_name),
                        "confidence": conf,
                        "matched_keywords": [],
                        "reason": f"相似任务推荐（SimilarTaskRecommender，置信度: {similar_confidence}）",
                        "source": "similar",
                    }
                )
                existing_ids.add(role_name)

        # Re-sort by confidence (keyword results keep their original confidence,
        # enhanced results have lower confidence)
        matched.sort(key=lambda x: x.get("confidence", 0), reverse=True)

        return matched

    @staticmethod
    def resolve_roles(roles: list[str], matched_roles: list[dict]) -> list[dict]:
        """
        Resolve user-specified roles, merging with auto-matched results.

        Args:
            roles: User-specified role ID list (may include aliases)
            matched_roles: Auto-matched roles from analyze_task()

        Returns:
            Final matched roles list with user overrides applied
        """
        from .models import ROLE_REGISTRY as _RR


        resolved_roles = [resolve_role_id(r) for r in roles]
        role_ids_set = set(resolved_roles)
        final = [r for r in matched_roles if r["role_id"] in role_ids_set]

        for rid, _original_rid in zip(resolved_roles, roles):
            if not any(r["role_id"] == rid for r in final):
                template = ROLE_TEMPLATES.get(rid, {"name": rid, "prompt": ""})
                rdef = _RR.get(rid)
                if rdef and rdef.status == "planned":
                    reason = f"用户指定（{rdef.name} - 规划中角色，暂无完整模板）"
                else:
                    reason = "用户指定"
                final.append(
                    {
                        "role_id": rid,
                        "name": template.get("name", rid),
                        "confidence": 1.0,
                        "matched_keywords": [],
                        "reason": reason,
                    }
                )

        return final
