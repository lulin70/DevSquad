#!/usr/bin/env python3

import logging
from typing import Any

from .models import ROLE_REGISTRY, resolve_role_id

logger = logging.getLogger(__name__)

ROLE_TEMPLATES = {
    rid: {"name": rdef.name, "prompt": rdef.prompt, "keywords": rdef.keywords} for rid, rdef in ROLE_REGISTRY.items()
}

CANDIDATE_SOURCES = ("keyword", "adaptive", "similar", "semantic", "explicit", "fallback")


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

    @staticmethod
    def _candidate(
        role_id: str,
        *,
        name: str | None = None,
        score: float,
        reason: str,
        source: str,
        matched_keywords: list[str] | None = None,
    ) -> dict[str, Any]:
        """Build one normalized, backward-compatible role candidate."""
        if source not in CANDIDATE_SOURCES:
            raise ValueError(f"unsupported candidate source: {source}")
        normalized_score = float(score)
        return {
            "candidate": role_id,
            "role_id": role_id,
            "name": name or ROLE_TEMPLATES.get(role_id, {}).get("name", role_id),
            "score": normalized_score,
            "confidence": normalized_score,
            "reason": reason or "候选角色匹配",
            "source": source,
            "matched_keywords": list(matched_keywords or []),
        }

    @classmethod
    def normalize_candidates(cls, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate candidates and apply deterministic score ordering."""
        return cls._merge_candidates(candidates)

    @staticmethod
    def _merge_candidates(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate candidates and apply deterministic score ordering."""
        merged: dict[str, dict[str, Any]] = {}
        for candidate in candidates:
            role_id = str(candidate.get("candidate") or candidate.get("role_id") or "")
            if not role_id:
                continue
            score = float(candidate.get("score", candidate.get("confidence", 0.0)))
            normalized = {
                **candidate,
                "candidate": role_id,
                "role_id": role_id,
                "score": score,
                "confidence": score,
                "name": candidate.get("name") or ROLE_TEMPLATES.get(role_id, {}).get("name", role_id),
                "reason": str(candidate.get("reason") or "候选角色匹配"),
                "source": candidate.get("source", "fallback"),
                "matched_keywords": list(candidate.get("matched_keywords", [])),
            }
            current = merged.get(role_id)
            if current is None or score > current["score"]:
                merged[role_id] = normalized
        return sorted(merged.values(), key=lambda item: (-item["score"], item["candidate"]))

    def analyze_task(self, task_description: str) -> list[dict[str, Any]]:
        """Analyze a task description and return normalized keyword candidates."""
        task_lower = task_description.lower()
        matched: list[dict[str, Any]] = []

        for role_id, role_info in ROLE_TEMPLATES.items():
            matched_keywords = [kw for kw in role_info["keywords"] if kw in task_lower]
            if matched_keywords:
                score = min(len(matched_keywords) / len(role_info["keywords"]), 1.0)
                matched.append(
                    self._candidate(
                        role_id,
                        name=str(role_info["name"]),
                        score=score,
                        reason=f"匹配关键词: {', '.join(matched_keywords)}",
                        source="keyword",
                        matched_keywords=matched_keywords,
                    )
                )

        if not matched:
            matched.append(
                self._candidate(
                    "solo-coder",
                    name="独立开发者",
                    score=0.5,
                    reason="默认角色：无明确关键词匹配",
                    source="fallback",
                )
            )

        return self._merge_candidates(matched)

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
        existing_ids = {r["candidate"] for r in matched}

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
                    self._candidate(
                        role_name,
                        name=str(template.get("name", role_name)),
                        score=0.4,
                        matched_keywords=[],
                        reason="历史成功率推荐（AdaptiveRoleSelector）",
                        source="adaptive",
                    )
                )
                existing_ids.add(role_name)

        # Add similar-only roles
        for role_name in similar_roles:
            if role_name not in existing_ids:
                template = ROLE_TEMPLATES.get(role_name, {"name": role_name})
                conf = confidence_map.get(similar_confidence, 0.3)
                matched.append(
                    self._candidate(
                        role_name,
                        name=str(template.get("name", role_name)),
                        score=conf,
                        matched_keywords=[],
                        reason=f"相似任务推荐（SimilarTaskRecommender，置信度: {similar_confidence}）",
                        source="similar",
                    )
                )
                existing_ids.add(role_name)

        return self._merge_candidates(matched)

    @staticmethod
    def resolve_roles(roles: list[str], _matched_roles: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
        final: list[dict[str, Any]] = []
        for rid in resolved_roles:
            template = ROLE_TEMPLATES.get(rid, {"name": rid, "prompt": ""})
            rdef = _RR.get(rid)
            if rdef and rdef.status == "planned":
                reason = f"用户指定（{rdef.name} - 规划中角色，暂无完整模板）"
            else:
                reason = "用户指定"
            final.append(
                RoleMatcher._candidate(
                    rid,
                    name=str(template.get("name", rid)),
                    score=1.0,
                    matched_keywords=[],
                    reason=reason,
                    source="explicit",
                )
            )

        return final
