#!/usr/bin/env python3
"""
MetaSkillGrouper — 6-Layer Meta-skill Architecture for DevSquad.

ROADMAP P2-UI-3: Skillifier Meta-skills 分层架构评估与最小实现.

Inspired by Leonxlnx/taste-skill's 6 meta-skill layers. Adapts the concept to
DevSquad's 8 existing sub-skills (dispatch/intent/review/retrospective/
security/test/prototype/teach), organizing them into 6 functional layers.

This is an assessment/organization layer ON TOP OF the existing flat
skill_registry.py — it does NOT replace the flat registry, but provides a
higher-level grouping for documentation, discovery, and progressive disclosure.

=====================================================================
EVALUATION REPORT (P2-UI-3)
=====================================================================

1. DevSquad 现有扁平 skill_registry.py 架构分析
-------------------------------------------------
DevSquad 当前存在两套并行的 skill 注册体系:

(a) skills/registry.py — Sub-skill 扁平注册表 (本模块的主要数据源)
    - BaseSkill 基类 + 8 个 sub-skill handler (dispatch/intent/review/
      retrospective/security/test/prototype/teach)
    - list_skills() 扫描 skills/ 目录，按目录名发现 handler.py
    - get_skill(name) 懒加载并缓存 skill 实例
    - 特点: 扁平结构，无层级关系，所有 skill 地位平等
    - 局限: 随 skill 数量增长，发现性和可学习性下降；新用户无法
      知道应该先学哪个 skill

(b) scripts/collaboration/skill_registry.py — SkillEntry 持久化注册表
    - SkillEntry dataclass (name/description/category/tags/confidence)
    - SkillRegistry 类支持 register/unregister/search/execute
    - 持久化到 registry.json，支持跨 session 复用
    - 由 Skillifier 从执行历史自动生成 SkillProposal 并发布
    - 特点: 面向"自动生成的可复用技能"，category 字段已有轻度分类
    - 局限: category 是自由字符串（如 "code-review"/"testing"），
      无统一的层级语义

两套体系互补但均扁平: sub-skill 无层级，SkillEntry.category 无架构。
随着 skill 数量增长 (P2-UI-3+ 预留 governance/integration 层)，
扁平结构的发现性和 onboarding 成本会成为瓶颈。

2. 6 层 Meta-skill 分层的适配方案
----------------------------------
借鉴 taste-skill 的 6 层 meta-skill 理念，将 DevSquad 8 个 sub-skill
映射到 6 个功能层 (disclosure_level 1-6 代表渐进式披露顺序):

    Layer 1  Foundation    intent, teach                  (基础能力)
    Layer 2  Orchestration  dispatch                        (编排调度)
    Layer 3  Quality        review, test, security          (质量保障)
    Layer 4  Evolution      retrospective, prototype       (持续演进)
    Layer 5  Governance     (预留: compliance/audit)        (治理规则)
    Layer 6  Integration    (预留: mcp/plugin)              (集成扩展)

适配原则:
- 8 个现有 skill 100% 覆盖到 Layer 1-4 (coverage = 1.0)
- Layer 5-6 预留，为未来 P2-UI-4+ 扩展提供架构锚点
- 层级语义与 Skillifier.CATEGORY_KEYWORDS 对齐 (code-review→quality,
  testing→quality, security→quality, refactoring→evolution 等)
- disclosure_level 与 StandardizedRoleTemplate 的渐进式披露协同

3. 与 standardized_role_template.py progressive disclosure 的协同方式
---------------------------------------------------------------------
standardized_role_template.py 实现了 Agent Skills SKILL.md anatomy:
  overview(What) → when_to_use/when_not_to_use(When) → process_steps(How)
  → rationalizations/red_flags(Warnings) → verification_requirements(Proof)

这是"单个 skill/role 的渐进式披露"——按用户阅读顺序逐步展开细节。

MetaSkillGrouper 的 progressive disclosure 是"跨 skill 的渐进式披露"——
按用户成熟度逐步暴露更多 skill 层级:

    beginner       → Layer 1-2 (Foundation + Orchestration)
                     新用户先理解意图识别和任务调度
    intermediate   → Layer 1-4 (+ Quality + Evolution)
                     成熟用户掌握质量保障和持续演进
    advanced       → Layer 1-6 (全部含 Governance + Integration)
                     高级用户接触治理和集成扩展

两层 progressive disclosure 正交且互补:
- standardized_role_template: 单个 skill 内部 "What→When→How→Proof"
- MetaSkillGrouper:           多个 skill 之间 "基础→编排→质量→演进→治理→集成"
协同点: StandardizedRoleTemplate 的 category 字段可映射到 meta-skill layer，
未来 get_progressive_disclosure() 可同时返回 skill 的 SKILL.md 摘要，
实现"先看层级概览，再展开单 skill 细节"的双重渐进披露。

4. 对 role_skill_loader.py 加载逻辑的影响评估
------------------------------------------------
role_skill_loader.py 按 role_id 加载 skills/role_skills/<role_id>/SKILL.md，
是面向"角色→方法论"的映射 (如 product-manager/PRD-Skill.md)。

MetaSkillGrouper 面向"skill 层级→发现顺序"的映射，与 role_skill_loader
是正交维度:
- role_skill_loader: role_id → SKILL.md list (按角色查方法论)
- MetaSkillGrouper:  skill_name → meta_layer (按 skill 查层级)

影响评估:
- 零侵入: 本模块不修改 role_skill_loader.py，不影响其加载逻辑
- 可选增强: 未来 role_skill_loader.load_skills() 可选择性调用
  MetaSkillGrouper.get_progressive_disclosure(user_level) 按用户成熟度
  过滤/排序返回的 SkillContent 列表 (当前不实现，留作 P2-UI-4+ 评估)
- 缓存隔离: MetaSkillGrouper 不共享 role_skill_loader 的 _cache，
  避免缓存污染

5. 不替换扁平注册而是叠加分层的理由
-------------------------------------
理由 1: 单一职责 (SRP)
  skills/registry.py 负责发现和实例化 skill (How to load);
  MetaSkillGrouper 负责组织和导航 skill (How to discover).
  混合两者会破坏 registry.py 的简洁性和现有 5355+ 测试的稳定性。

理由 2: 向后兼容
  8 个 sub-skill 的 handler.py 通过 list_skills()/get_skill() 被大量调用
  (dispatcher/intent_workflow_mapper/test_*.py 等). 替换扁平注册会
  引发大面积破坏性变更，违反"禁止修改现有源码"约束.

理由 3: 评估优先 (ROADMAP 定位)
  P2-UI-3 明确是"评估与最小实现". 叠加分层允许我们先验证 6 层架构的
  有效性，再决定是否在 P2-UI-4+ 深度集成. 避免基于未验证假设的大重构
  (符合 CarryMem 教训: "基于过期数据/未验证假设的任务需先校验前提").

理由 4: 数据源解耦
  MetaSkillGrouper.group_skills() 接受可选 skill_names 参数，可脱离
  registry 独立测试和用于 SkillEntry 体系 (skill_registry.py 的
  SkillEntry.category 同样可映射到 meta layer). 叠加分层使两套注册
  体系都能受益于 meta-skill 组织.

理由 5: 预留扩展空间
  Layer 5-6 (Governance/Integration) 当前为空. 若替换扁平注册，需先
  设计空层的占位机制; 叠加分层允许空层自然存在，待 P2-UI-4+ 填充.

=====================================================================
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Known DevSquad sub-skills (fallback when skills.registry import fails).
# Kept in sync with skills/ directory: dispatch/intent/review/retrospective/
# security/test/prototype/teach.
_KNOWN_SUBSKILLS: tuple[str, ...] = (
    "dispatch",
    "intent",
    "review",
    "retrospective",
    "security",
    "test",
    "prototype",
    "teach",
)


class MetaSkillGrouper:
    """Group flat skill registry into 6-layer meta-skill architecture.

    Inspired by taste-skill's 6 meta-skill layers. Adapts the concept to
    DevSquad's 8 existing sub-skills (dispatch/intent/review/retrospective/
    security/test/prototype/teach), organizing them into 6 functional layers.

    This is an assessment/organization layer on top of the existing flat
    skill_registry.py — it does NOT replace the flat registry, but provides
    a higher-level grouping for documentation, discovery, and progressive
    disclosure.

    Layers:
        1. Foundation — basic capabilities (intent detection, teaching)
        2. Orchestration — task coordination (dispatch)
        3. Quality — quality assurance (review, test, security)
        4. Evolution — continuous improvement (retrospective, prototype)
        5. Governance — compliance and audit (reserved for future)
        6. Integration — external integration (reserved for future)
    """

    META_LAYERS: dict[str, dict[str, Any]] = {
        "foundation": {
            "description": "Basic capabilities — intent detection and user onboarding",
            "skills": ["intent", "teach"],
            "disclosure_level": 1,  # Shown first to new users
        },
        "orchestration": {
            "description": "Task coordination and multi-role dispatch",
            "skills": ["dispatch"],
            "disclosure_level": 2,
        },
        "quality": {
            "description": "Quality assurance — review, test, security",
            "skills": ["review", "test", "security"],
            "disclosure_level": 3,
        },
        "evolution": {
            "description": "Continuous improvement — retrospective and prototype",
            "skills": ["retrospective", "prototype"],
            "disclosure_level": 4,
        },
        "governance": {
            "description": "Compliance and audit (reserved for future skills)",
            "skills": [],
            "disclosure_level": 5,
        },
        "integration": {
            "description": "External integration and plugins (reserved for future skills)",
            "skills": [],
            "disclosure_level": 6,
        },
    }

    # Keyword → layer mapping for suggest_layer_for_skill().
    # Ordered by layer disclosure_level; first match wins.
    _LAYER_KEYWORDS: dict[str, list[str]] = {
        "foundation": ["intent", "detect", "teach", "onboard", "guide", "basic", "intro"],
        "orchestration": ["dispatch", "coordinate", "orchestrate", "schedule", "route", "delegate", "assign"],
        "quality": ["test", "review", "security", "audit", "scan", "quality", "verify", "validate", "lint", "check"],
        "evolution": ["retrospective", "improve", "prototype", "evolve", "iterate", "postmortem", "retro", "learn"],
        "governance": ["compliance", "policy", "rule", "govern", "regulat", "standard", "audit-trail"],
        "integration": ["integrate", "plugin", "mcp", "connect", "external", "adapter", "bridge", "webhook"],
    }

    # Progressive disclosure user-level → max disclosure_level shown.
    _USER_LEVEL_MAX_DISCLOSURE: dict[str, int] = {
        "beginner": 2,       # Foundation + Orchestration
        "intermediate": 4,   # + Quality + Evolution
        "advanced": 6,       # All layers
    }

    def _resolve_skill_names(self, skill_names: list[str] | None) -> list[str]:
        """Resolve the skill list to group, falling back to the registry.

        Args:
            skill_names: Explicit list of skill names. When None, the flat
                skills.registry.list_skills() is consulted; if that import
                fails, the hardcoded _KNOWN_SUBSKILLS fallback is used.

        Returns:
            De-duplicated list of skill names preserving first-seen order.
        """
        if skill_names is not None:
            # De-duplicate while preserving order.
            seen: set[str] = set()
            unique: list[str] = []
            for name in skill_names:
                if name not in seen:
                    seen.add(name)
                    unique.append(name)
            return unique

        # Default: read from the flat sub-skill registry.
        try:
            from skills.registry import list_skills

            discovered = list_skills()
            if discovered:
                return discovered
        except Exception as e:  # noqa: BLE001 — registry import is best-effort
            logger.debug("skills.registry import failed, using fallback: %s", e)

        return list(_KNOWN_SUBSKILLS)

    def group_skills(self, skill_names: list[str] | None = None) -> dict[str, Any]:
        """Group skills into meta-skill layers.

        Args:
            skill_names: List of skill names to group (default: all from registry).

        Returns:
            Dict with keys:
                - layers: dict[str, dict] — {layer_name: {description, skills,
                  disclosure_level, actual_skills}}
                - ungrouped: list[str] — skills not fitting any layer
                - coverage: float — percentage of skills grouped (0.0-1.0)
        """
        resolved = self._resolve_skill_names(skill_names)

        # Build a reverse lookup: skill_name → layer_name.
        skill_to_layer: dict[str, str] = {}
        for layer_name, layer_info in self.META_LAYERS.items():
            for skill in layer_info["skills"]:
                skill_to_layer[skill] = layer_name

        layers: dict[str, dict[str, Any]] = {}
        ungrouped: list[str] = []

        for skill in resolved:
            placed = False
            for layer_name, layer_info in self.META_LAYERS.items():
                if skill in layer_info["skills"]:
                    layer_dict = layers.setdefault(
                        layer_name,
                        {
                            "description": layer_info["description"],
                            "skills": list(layer_info["skills"]),
                            "disclosure_level": layer_info["disclosure_level"],
                            "actual_skills": [],
                        },
                    )
                    layer_dict["actual_skills"].append(skill)
                    placed = True
                    break
            if not placed:
                ungrouped.append(skill)

        # Ensure all 6 layers appear in the result even when empty/unhit.
        for layer_name, layer_info in self.META_LAYERS.items():
            if layer_name not in layers:
                layers[layer_name] = {
                    "description": layer_info["description"],
                    "skills": list(layer_info["skills"]),
                    "disclosure_level": layer_info["disclosure_level"],
                    "actual_skills": [],
                }

        total = len(resolved)
        grouped = total - len(ungrouped)
        coverage = (grouped / total) if total > 0 else 0.0

        return {
            "layers": layers,
            "ungrouped": ungrouped,
            "coverage": round(coverage, 4),
        }

    def get_layer(self, layer_name: str) -> dict[str, Any]:
        """Get details of a specific meta-skill layer.

        Args:
            layer_name: Name of the layer (e.g. "foundation", "quality").

        Returns:
            Dict with keys: description, skills, disclosure_level.

        Raises:
            ValueError: When layer_name is not a recognized meta-skill layer.
        """
        if layer_name not in self.META_LAYERS:
            raise ValueError(
                f"Unknown meta-skill layer: {layer_name!r}. "
                f"Valid layers: {list(self.META_LAYERS.keys())}"
            )
        info = self.META_LAYERS[layer_name]
        return {
            "description": info["description"],
            "skills": list(info["skills"]),
            "disclosure_level": info["disclosure_level"],
        }

    def get_progressive_disclosure(self, user_level: str = "beginner") -> list[dict[str, Any]]:
        """Get skills in progressive disclosure order.

        Args:
            user_level: "beginner" (layers 1-2 only), "intermediate" (1-4),
                "advanced" (all 1-6).

        Returns:
            Ordered list of {layer, disclosure_level, skills, show_to_user}
            sorted by disclosure_level ascending.

        Raises:
            ValueError: When user_level is not one of the supported levels.
        """
        if user_level not in self._USER_LEVEL_MAX_DISCLOSURE:
            raise ValueError(
                f"Unknown user_level: {user_level!r}. "
                f"Valid levels: {list(self._USER_LEVEL_MAX_DISCLOSURE.keys())}"
            )
        max_level = self._USER_LEVEL_MAX_DISCLOSURE[user_level]

        result: list[dict[str, Any]] = []
        for layer_name, info in sorted(
            self.META_LAYERS.items(),
            key=lambda kv: kv[1]["disclosure_level"],
        ):
            result.append(
                {
                    "layer": layer_name,
                    "disclosure_level": info["disclosure_level"],
                    "skills": list(info["skills"]),
                    "show_to_user": info["disclosure_level"] <= max_level,
                }
            )
        return result

    def suggest_layer_for_skill(self, skill_name: str, skill_description: str) -> str:
        """Suggest which meta-skill layer a new skill should belong to.

        Uses keyword matching on skill_description to suggest the best layer.
        When no keywords match, returns "foundation" (the default layer with
        the lowest disclosure_level, safest place to surface a new skill).

        Args:
            skill_name: Name of the skill (also scanned for keywords).
            skill_description: Natural language description of the skill.

        Returns:
            Suggested layer name (one of the META_LAYERS keys).
        """
        haystack = f"{skill_name} {skill_description}".lower()

        # Iterate layers in disclosure_level order so lower layers win ties.
        for layer_name in sorted(
            self._LAYER_KEYWORDS.keys(),
            key=lambda ln: self.META_LAYERS[ln]["disclosure_level"],
        ):
            for keyword in self._LAYER_KEYWORDS[layer_name]:
                if keyword in haystack:
                    return layer_name

        # Default: foundation (disclosure_level 1).
        return "foundation"

    def audit_layering(self) -> dict[str, Any]:
        """Audit current skill layering against the 6-layer architecture.

        Returns:
            Dict with keys:
                - total_skills: int
                - grouped_skills: int
                - ungrouped_skills: list[str]
                - coverage_percentage: float (0.0-100.0)
                - empty_layers: list[str] — layers with no skills
                - recommendations: list[str]
        """
        grouped = self.group_skills()
        resolved = self._resolve_skill_names(None)

        total_skills = len(resolved)
        ungrouped = grouped["ungrouped"]
        grouped_count = total_skills - len(ungrouped)
        coverage_pct = round((grouped_count / total_skills) * 100, 2) if total_skills > 0 else 0.0

        empty_layers = [
            layer_name
            for layer_name, info in self.META_LAYERS.items()
            if len(info["skills"]) == 0
        ]

        recommendations: list[str] = []
        if ungrouped:
            recommendations.append(
                f"Found {len(ungrouped)} ungrouped skill(s): {ungrouped}. "
                "Assign them to an appropriate meta-skill layer or extend META_LAYERS."
            )
        if empty_layers:
            recommendations.append(
                f"{len(empty_layers)} layer(s) have no skills yet: {empty_layers}. "
                "Consider populating governance/integration layers in future P2-UI-4+ work."
            )
        if coverage_pct < 80.0:
            recommendations.append(
                f"Coverage is {coverage_pct}% (< 80%). Review skill-to-layer mapping "
                "to improve grouping."
            )
        if not recommendations:
            recommendations.append(
                "Layering is healthy: all known skills grouped, coverage >= 80%."
            )

        return {
            "total_skills": total_skills,
            "grouped_skills": grouped_count,
            "ungrouped_skills": ungrouped,
            "coverage_percentage": coverage_pct,
            "empty_layers": empty_layers,
            "recommendations": recommendations,
        }
