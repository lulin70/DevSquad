#!/usr/bin/env python3
import re
from typing import Dict, List

from .models import ROLE_REGISTRY, ROLE_ALIASES, resolve_role_id

ROLE_TEMPLATES = {rid: {"name": rdef.name, "prompt": rdef.prompt, "keywords": rdef.keywords} for rid, rdef in ROLE_REGISTRY.items()}


class RoleMatcher:
    """Role matching engine based on keyword analysis."""

    def analyze_task(self, task_description: str) -> List[Dict[str, str]]:
        """
        Analyze a task description and match appropriate roles.

        Args:
            task_description: Task description text

        Returns:
            List of matched roles: [{"role_id": "...", "name": "...", "reason": "..."}]
        """
        task_lower = task_description.lower()
        matched = []

        for role_id, role_info in ROLE_TEMPLATES.items():
            score = 0
            matched_keywords = []
            for kw in role_info["keywords"]:
                if kw in task_lower:
                    score += 1
                    matched_keywords.append(kw)

            if score > 0:
                confidence = min(score / len(role_info["keywords"]), 1.0)
                matched.append({
                    "role_id": role_id,
                    "name": role_info["name"],
                    "confidence": confidence,
                    "matched_keywords": matched_keywords,
                    "reason": f"匹配关键词: {', '.join(matched_keywords)}",
                })

        matched.sort(key=lambda x: x["confidence"], reverse=True)

        if not matched:
            matched.append({
                "role_id": "solo-coder",
                "name": "独立开发者",
                "confidence": 0.5,
                "matched_keywords": [],
                "reason": "默认角色：无明确关键词匹配",
            })

        return matched

    @staticmethod
    def resolve_roles(roles: List[str], matched_roles: List[Dict]) -> List[Dict]:
        """
        Resolve user-specified roles, merging with auto-matched results.

        Args:
            roles: User-specified role ID list (may include aliases)
            matched_roles: Auto-matched roles from analyze_task()

        Returns:
            Final matched roles list with user overrides applied
        """
        from .models import ROLE_REGISTRY as _RR
        PLANNED_ROLES = {}

        resolved_roles = [resolve_role_id(r) for r in roles]
        role_ids_set = set(resolved_roles)
        final = [r for r in matched_roles if r["role_id"] in role_ids_set]

        for rid, original_rid in zip(resolved_roles, roles):
            if not any(r["role_id"] == rid for r in final):
                template = ROLE_TEMPLATES.get(rid, {"name": rid, "prompt": ""})
                rdef = _RR.get(rid)
                if rdef and rdef.status == "planned":
                    reason = f"用户指定（{rdef.name} - 规划中角色，暂无完整模板）"
                else:
                    reason = "用户指定"
                final.append({
                    "role_id": rid,
                    "name": template.get("name", rid),
                    "confidence": 1.0,
                    "matched_keywords": [],
                    "reason": reason,
                })

        return final
