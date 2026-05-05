#!/usr/bin/env python3
"""
Concern Pack Loader — 关注点增强包加载引擎

根据任务描述自动匹配并加载相关的增强包，将领域知识注入到角色提示词中。

增强包位置: templates/concerns/*.yaml
触发机制: 任务描述中的关键词匹配增强包的 triggers.keywords

Usage:
    from scripts.collaboration.concern_pack_loader import ConcernPackLoader

    loader = ConcernPackLoader()
    packs = loader.match_packs("设计用户权限系统")
    # → [PermissionPack]

    enhancements = loader.get_role_enhancements(packs, "security")
    # → "【权限设计专项检查】..."
"""

import os
import sys
import logging
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class DecisionOption:
    id: str
    name: str
    when: str
    examples: str = ""
    complexity: int = 1
    pros: str = ""
    cons: str = ""


@dataclass
class DecisionStep:
    question: str
    description: str = ""
    options: List[DecisionOption] = field(default_factory=list)
    selection_guide: str = ""


@dataclass
class ChecklistItem:
    item: str
    severity: str = "required"


@dataclass
class Pitfall:
    title: str
    description: str
    severity: str = "medium"
    check: str = ""
    fix: str = ""


@dataclass
class ConcernPack:
    concern_id: str
    name: str
    version: str = "1.0"
    description: str = ""
    triggers: Dict[str, Any] = field(default_factory=dict)
    decision_framework: Dict[str, Any] = field(default_factory=dict)
    checklist: Dict[str, Any] = field(default_factory=dict)
    role_enhancements: Dict[str, str] = field(default_factory=dict)

    def get_checklist_summary(self) -> str:
        must_have = self.checklist.get("must_have", [])
        pitfalls = self.checklist.get("common_pitfalls", [])

        lines = [f"\n### {self.name} — 检查清单\n"]

        if must_have:
            lines.append("**必须检查项**:")
            for item in must_have:
                severity = item.get("severity", "required") if isinstance(item, dict) else "required"
                text = item.get("item", str(item)) if isinstance(item, dict) else str(item)
                icon = "🔴" if severity == "required" else "🟡"
                lines.append(f"- [{icon}] {text}")

        if pitfalls:
            lines.append("\n**常见陷阱**:")
            for p in pitfalls:
                if isinstance(p, dict):
                    severity = p.get("severity", "medium")
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡"}.get(severity, "🟡")
                    lines.append(f"- [{icon}] **{p.get('title', '')}** ({severity})")
                    lines.append(f"  → {p.get('check', p.get('description', ''))}")

        return "\n".join(lines)

    def get_decision_summary(self) -> str:
        steps = self.decision_framework
        if not steps:
            return ""

        lines = [f"\n### {self.name} — 决策框架\n"]

        for step_key, step_data in steps.items():
            if not isinstance(step_data, dict):
                continue
            question = step_data.get("question", "")
            if question:
                lines.append(f"**{question}**")

            options = step_data.get("options", [])
            if options:
                for opt in options:
                    if isinstance(opt, dict):
                        complexity_stars = "⭐" * opt.get("complexity", 1)
                        lines.append(f"- **{opt.get('name', '')}** {complexity_stars}")
                        when = opt.get("when", "")
                        if when:
                            lines.append(f"  适用: {when}")

            guide = step_data.get("selection_guide", "")
            if guide:
                lines.append(f"\n{guide}")

            lines.append("")

        return "\n".join(lines)


class ConcernPackLoader:
    """
    关注点增强包加载器

    职责：
    1. 从 templates/concerns/ 加载所有增强包定义
    2. 根据任务描述匹配相关增强包
    3. 提取角色增强提示词
    4. 生成检查清单和决策框架摘要
    """

    def __init__(self, concerns_dir: Optional[str] = None):
        if concerns_dir is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            concerns_dir = os.path.join(base_dir, "templates", "concerns")
        self.concerns_dir = os.path.realpath(concerns_dir)
        self._packs: Dict[str, ConcernPack] = {}
        self._loaded = False
        self._lock = threading.Lock()

    def _load_all_packs(self):
        """加载所有增强包"""
        with self._lock:
            if self._loaded:
                return

            if not os.path.isdir(self.concerns_dir):
                logger.debug("Concerns directory not found: %s", self.concerns_dir)
                self._loaded = True
                return

            for filename in os.listdir(self.concerns_dir):
                if not filename.endswith((".yaml", ".yml")):
                    continue

                filepath = os.path.join(self.concerns_dir, filename)
                try:
                    pack = self._load_pack(filepath)
                    if pack:
                        self._packs[pack.concern_id] = pack
                        logger.debug("Loaded concern pack: %s (%s)", pack.concern_id, pack.name)
                except Exception as e:
                    logger.warning("Failed to load concern pack %s: %s", filename, e)

            self._loaded = True
            logger.info("Loaded %d concern packs", len(self._packs))

    def _load_pack(self, filepath: str) -> Optional[ConcernPack]:
        """加载单个增强包文件"""
        try:
            import yaml
        except ImportError:
            return self._load_pack_simple(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        if not data or not data.get("concern_id"):
            return None

        return ConcernPack(
            concern_id=data["concern_id"],
            name=data.get("name", data["concern_id"]),
            version=data.get("version", "1.0"),
            description=data.get("description", ""),
            triggers=data.get("triggers", {}),
            decision_framework=data.get("decision_framework", {}),
            checklist=data.get("checklist", {}),
            role_enhancements=data.get("role_enhancements", {}),
        )

    def _load_pack_simple(self, filepath: str) -> Optional[ConcernPack]:
        """无YAML依赖时的简单加载（JSON格式备选）"""
        json_path = filepath.replace(".yaml", ".json").replace(".yml", ".json")
        if os.path.exists(json_path):
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if data and data.get("concern_id"):
                return ConcernPack(
                    concern_id=data["concern_id"],
                    name=data.get("name", data["concern_id"]),
                    version=data.get("version", "1.0"),
                    description=data.get("description", ""),
                    triggers=data.get("triggers", {}),
                    decision_framework=data.get("decision_framework", {}),
                    checklist=data.get("checklist", {}),
                    role_enhancements=data.get("role_enhancements", {}),
                )
        return None

    def match_packs(self, task_description: str) -> List[ConcernPack]:
        """
        根据任务描述匹配相关增强包

        Args:
            task_description: 任务描述文本

        Returns:
            匹配到的增强包列表
        """
        self._load_all_packs()

        if not self._packs:
            return []

        task_lower = task_description.lower()
        matched = []

        for pack_id, pack in self._packs.items():
            keywords = pack.triggers.get("keywords", [])
            if not keywords:
                continue

            match_count = 0
            for kw in keywords:
                if kw.lower() in task_lower:
                    match_count += 1

            if match_count > 0:
                matched.append((match_count, pack))

        matched.sort(key=lambda x: x[0], reverse=True)

        result = [pack for _, pack in matched]
        if result:
            pack_names = ", ".join(p.name for p in result)
            logger.info("Matched %d concern pack(s): %s", len(result), pack_names)

        return result

    def get_role_enhancements(self, packs: List[ConcernPack], role_id: str) -> str:
        """
        获取指定角色的增强提示词

        Args:
            packs: 匹配到的增强包列表
            role_id: 角色ID（如 security, architect, tester）

        Returns:
            合并后的增强提示词
        """
        enhancements = []

        for pack in packs:
            enhancement = pack.role_enhancements.get(role_id, "")
            text = self._extract_enhancement_text(enhancement)
            if text:
                enhancements.append(text)

        if enhancements:
            return "\n\n".join(enhancements)
        return ""

    def get_all_role_enhancements(self, packs: List[ConcernPack]) -> Dict[str, str]:
        """
        获取所有角色的增强提示词

        Returns:
            {role_id: enhancement_text} 字典
        """
        result = {}
        for pack in packs:
            for role_id, enhancement in pack.role_enhancements.items():
                text = self._extract_enhancement_text(enhancement)
                if not text:
                    continue
                if role_id in result:
                    result[role_id] += "\n\n" + text
                else:
                    result[role_id] = text
        return result

    @staticmethod
    def _extract_enhancement_text(enhancement) -> str:
        """从增强包数据中提取提示词文本"""
        if isinstance(enhancement, str):
            return enhancement
        if isinstance(enhancement, dict):
            return enhancement.get("extra_prompt", "")
        return str(enhancement) if enhancement else ""

    def get_combined_checklist(self, packs: List[ConcernPack]) -> str:
        """获取合并后的检查清单摘要"""
        parts = []
        for pack in packs:
            summary = pack.get_checklist_summary()
            if summary:
                parts.append(summary)
        return "\n".join(parts)

    def get_combined_decision_framework(self, packs: List[ConcernPack]) -> str:
        """获取合并后的决策框架摘要"""
        parts = []
        for pack in packs:
            summary = pack.get_decision_summary()
            if summary:
                parts.append(summary)
        return "\n".join(parts)

    def get_pack_info(self, packs: List[ConcernPack]) -> List[Dict[str, Any]]:
        """获取增强包基本信息列表"""
        return [
            {
                "concern_id": pack.concern_id,
                "name": pack.name,
                "description": pack.description,
                "matched_keywords": list(pack.triggers.get("keywords", []))[:5],
            }
            for pack in packs
        ]

    def list_available_packs(self) -> List[Dict[str, str]]:
        """列出所有可用的增强包"""
        self._load_all_packs()
        return [
            {"id": pack.concern_id, "name": pack.name, "description": pack.description}
            for pack in self._packs.values()
        ]
