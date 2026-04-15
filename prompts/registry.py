#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PromptRegistry - 提示词统一注册与加载器

作为提示词的单一真实来源（Single Source of Truth），统一管理所有角色提示词、
阶段提示词和门禁提示词。支持按角色、阶段、门禁类型检索，支持动态组合。

核心功能：
1. 加载和管理所有提示词（角色/阶段/门禁）
2. 按角色ID获取角色提示词
3. 按阶段ID获取阶段提示词
4. 动态组合提示词（角色 + 阶段 + 门禁）
5. 为 role_matcher.py 提供角色定义数据
6. 为 skills-index.json 和 skill-manifest.yaml 提供同步数据
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class RolePromptInfo:
    role_id: str
    name: str
    name_en: str
    description: str
    keywords: List[str]
    capabilities: List[str]
    skills: List[str]
    priority: int
    prompt_content: str
    stages: Dict[str, Dict[str, Any]] = field(default_factory=dict)


@dataclass
class StagePromptInfo:
    stage_id: str
    name: str
    name_en: str
    description: str
    lead_role: str
    participant_roles: List[str]
    entry_conditions: List[str]
    exit_conditions: List[str]
    deliverables: List[Dict[str, str]]
    prompt_content: str


@dataclass
class GatePromptInfo:
    gate_id: str
    name: str
    description: str
    prompt_content: str


STAGE_ROLE_MAPPING = {
    "stage1": "product-manager",
    "stage2": "architect",
    "stage3": "ui-designer",
    "stage4": "tester",
    "stage5": "solo-coder",
    "stage6": "solo-coder",
    "stage7": "tester",
    "stage8": "architect",
}

ROLE_FILE_MAPPING = {
    "architect": "architect.md",
    "product-manager": "product_manager.md",
    "tester": "tester.md",
    "solo-coder": "solo_coder.md",
    "ui-designer": "ui_designer.md",
}

STAGE_FILE_MAPPING = {
    "stage1": "stage1_requirements.md",
    "stage2": "stage2_architecture.md",
    "stage3": "stage3_ui_design.md",
    "stage4": "stage4_test_design.md",
    "stage5": "stage5_task_breakdown.md",
    "stage6": "stage6_development.md",
    "stage7": "stage7_test_verify.md",
    "stage8": "stage8_release_review.md",
}

ROLE_METADATA = {
    "architect": {
        "name": "架构师",
        "name_en": "Architect",
        "description": "设计系统性、前瞻性、可落地、可验证的架构",
        "keywords": ["架构", "设计", "选型", "审查", "性能", "瓶颈", "模块", "接口", "部署"],
        "capabilities": ["系统架构设计", "技术选型", "架构评审", "性能优化", "安全设计"],
        "skills": ["架构设计", "技术评估", "系统设计", "代码审查"],
        "priority": 9,
    },
    "product-manager": {
        "name": "产品经理",
        "name_en": "Product Manager",
        "description": "定义用户价值清晰、需求明确、可落地、可验收的产品",
        "keywords": ["需求", "PRD", "用户故事", "竞品", "市场", "调研", "验收", "UAT", "体验"],
        "capabilities": ["需求分析", "PRD 编写", "用户研究", "竞品分析", "产品规划"],
        "skills": ["需求挖掘", "文档编写", "沟通协调", "数据分析"],
        "priority": 10,
    },
    "tester": {
        "name": "测试专家",
        "name_en": "Test Expert",
        "description": "确保全面、深入、自动化、可量化的质量保障",
        "keywords": ["测试", "质量", "验收", "自动化", "性能测试", "缺陷", "评审", "门禁"],
        "capabilities": ["测试用例设计", "测试执行", "Bug 跟踪", "质量保障", "自动化测试"],
        "skills": ["测试设计", "测试工具", "Bug 分析", "质量评估"],
        "priority": 7,
    },
    "solo-coder": {
        "name": "独立开发者",
        "name_en": "Solo Coder",
        "description": "编写完整、高质量、可维护、可测试的代码",
        "keywords": ["实现", "开发", "代码", "修复", "优化", "重构", "单元测试", "文档"],
        "capabilities": ["代码实现", "功能开发", "代码优化", "Bug 修复", "单元测试"],
        "skills": ["Java", "Python", "Spring Boot", "数据库", "Git"],
        "priority": 8,
    },
    "ui-designer": {
        "name": "UI 设计师",
        "name_en": "UI Designer",
        "description": "创建独特、生产级的 UI 界面，避免通用的 AI slop 美学",
        "keywords": ["UI设计", "界面设计", "前端设计", "视觉设计", "UI/UX", "UI原型", "界面美化", "UI优化", "UI重构"],
        "capabilities": ["界面设计", "交互设计", "视觉设计", "原型设计", "设计系统"],
        "skills": ["Figma", "Sketch", "Photoshop", "原型设计", "色彩搭配"],
        "priority": 6,
    },
}

STAGE_METADATA = {
    "stage1": {"name": "需求分析", "name_en": "Requirements Analysis", "lead_role": "product-manager"},
    "stage2": {"name": "架构设计", "name_en": "Architecture Design", "lead_role": "architect"},
    "stage3": {"name": "UI 设计", "name_en": "UI Design", "lead_role": "ui-designer"},
    "stage4": {"name": "测试设计", "name_en": "Test Design", "lead_role": "tester"},
    "stage5": {"name": "任务分解", "name_en": "Task Breakdown", "lead_role": "solo-coder"},
    "stage6": {"name": "开发实现", "name_en": "Development Implementation", "lead_role": "solo-coder"},
    "stage7": {"name": "测试验证", "name_en": "Test Verification", "lead_role": "tester"},
    "stage8": {"name": "发布评审", "name_en": "Release Review", "lead_role": "architect"},
}


class PromptRegistry:
    def __init__(self, prompts_dir: Optional[str] = None):
        if prompts_dir is None:
            this_file_dir = os.path.dirname(os.path.abspath(__file__))
            if os.path.basename(this_file_dir) == "prompts":
                prompts_dir = this_file_dir
            else:
                prompts_dir = os.path.join(this_file_dir, "prompts")
        self.prompts_dir = Path(prompts_dir)
        self.roles_dir = self.prompts_dir / "roles"
        self.stages_dir = self.prompts_dir / "stages"
        self.gates_dir = self.prompts_dir / "gates"
        self.templates_dir = self.prompts_dir / "templates"

        self._role_prompts: Dict[str, RolePromptInfo] = {}
        self._stage_prompts: Dict[str, StagePromptInfo] = {}
        self._gate_prompts: Dict[str, GatePromptInfo] = {}
        self._templates: Dict[str, str] = {}

        self._load_all()

    def _load_all(self):
        self._load_role_prompts()
        self._load_stage_prompts()
        self._load_gate_prompts()
        self._load_templates()

    def _read_file(self, file_path: Path) -> str:
        if not file_path.exists():
            return ""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"⚠️  读取文件失败 {file_path}: {e}")
            return ""

    def _extract_section(self, content: str, section_title: str) -> str:
        pattern = rf"##\s+{re.escape(section_title)}.*?(?=\n##\s|\Z)"
        match = re.search(pattern, content, re.DOTALL)
        return match.group(0) if match else ""

    def _extract_checklist(self, content: str, section_title: str) -> List[str]:
        section = self._extract_section(content, section_title)
        items = re.findall(r"-\s*\[\s*\]\s*(.+)", section)
        return [item.strip() for item in items]

    def _load_role_prompts(self):
        for role_id, filename in ROLE_FILE_MAPPING.items():
            file_path = self.roles_dir / filename
            content = self._read_file(file_path)

            metadata = ROLE_METADATA.get(role_id, {})

            stages = {}
            for stage_id, lead_role in STAGE_ROLE_MAPPING.items():
                stage_section = self._extract_section(
                    content, f"阶段{stage_id.replace('stage', '')}"
                )
                if stage_section or lead_role == role_id:
                    stages[stage_id] = {
                        "is_lead": lead_role == role_id,
                        "entry_conditions": self._extract_checklist(
                            stage_section, "入口条件"
                        ),
                        "exit_conditions": self._extract_checklist(
                            stage_section, "出口条件"
                        ),
                    }

            self._role_prompts[role_id] = RolePromptInfo(
                role_id=role_id,
                name=metadata.get("name", role_id),
                name_en=metadata.get("name_en", role_id),
                description=metadata.get("description", ""),
                keywords=metadata.get("keywords", []),
                capabilities=metadata.get("capabilities", []),
                skills=metadata.get("skills", []),
                priority=metadata.get("priority", 5),
                prompt_content=content,
                stages=stages,
            )

        print(f"✅ 已加载 {len(self._role_prompts)} 个角色提示词")

    def _load_stage_prompts(self):
        for stage_id, filename in STAGE_FILE_MAPPING.items():
            file_path = self.stages_dir / filename
            content = self._read_file(file_path)

            metadata = STAGE_METADATA.get(stage_id, {})
            entry_conditions = self._extract_checklist(content, "入口条件")
            exit_conditions = self._extract_checklist(content, "出口条件")

            deliverables = []
            deliverable_section = self._extract_section(content, "本阶段交付物")
            table_rows = re.findall(
                r"\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*(.+?)\s*\|",
                deliverable_section,
            )
            for row in table_rows[1:]:
                deliverables.append(
                    {
                        "name": row[0].strip(),
                        "role": row[1].strip(),
                        "format": row[2].strip(),
                        "standard": row[3].strip(),
                    }
                )

            self._stage_prompts[stage_id] = StagePromptInfo(
                stage_id=stage_id,
                name=metadata.get("name", stage_id),
                name_en=metadata.get("name_en", stage_id),
                description="",
                lead_role=metadata.get("lead_role", ""),
                participant_roles=[],
                entry_conditions=entry_conditions,
                exit_conditions=exit_conditions,
                deliverables=deliverables,
                prompt_content=content,
            )

        print(f"✅ 已加载 {len(self._stage_prompts)} 个阶段提示词")

    def _load_gate_prompts(self):
        gate_files = {
            "gate_template": "gate_template.md",
            "handoff_template": "handoff_template.md",
        }

        for gate_id, filename in gate_files.items():
            file_path = self.gates_dir / filename
            content = self._read_file(file_path)

            self._gate_prompts[gate_id] = GatePromptInfo(
                gate_id=gate_id,
                name=filename.replace(".md", "").replace("_", " ").title(),
                description="",
                prompt_content=content,
            )

        print(f"✅ 已加载 {len(self._gate_prompts)} 个门禁提示词")

    def _load_templates(self):
        if not self.templates_dir.exists():
            return
        for md_file in self.templates_dir.glob("*.md"):
            template_name = md_file.stem
            content = self._read_file(md_file)
            if content:
                self._templates[template_name] = content
        if self._templates:
            print(f"✅ 已加载 {len(self._templates)} 个交付物模板")

    def get_template(self, template_name: str) -> Optional[str]:
        return self._templates.get(template_name)

    def get_all_templates(self) -> Dict[str, str]:
        return self._templates

    def get_role_prompt(self, role_id: str) -> Optional[RolePromptInfo]:
        return self._role_prompts.get(role_id)

    def get_stage_prompt(self, stage_id: str) -> Optional[StagePromptInfo]:
        return self._stage_prompts.get(stage_id)

    def get_gate_prompt(self, gate_id: str) -> Optional[GatePromptInfo]:
        return self._gate_prompts.get(gate_id)

    def get_all_roles(self) -> Dict[str, RolePromptInfo]:
        return self._role_prompts

    def get_all_stages(self) -> Dict[str, StagePromptInfo]:
        return self._stage_prompts

    def compose_prompt(
        self,
        role_id: str,
        stage_id: Optional[str] = None,
        include_gate: bool = False,
    ) -> str:
        parts = []

        role_info = self.get_role_prompt(role_id)
        if not role_info:
            return ""

        parts.append(f"# 角色指令：{role_info.name} ({role_info.name_en})\n")
        parts.append(role_info.prompt_content)

        if stage_id:
            stage_info = self.get_stage_prompt(stage_id)
            if stage_info:
                parts.append(f"\n\n---\n\n# 当前阶段：{stage_info.name} ({stage_info.name_en})\n")
                parts.append(stage_info.prompt_content)

                role_in_stage = role_info.stages.get(stage_id, {})
                if role_in_stage.get("is_lead"):
                    parts.append(
                        f"\n\n> ⚠️ 你是本阶段（{stage_info.name}）的主导角色，对阶段交付物负主要责任。"
                    )
                else:
                    parts.append(
                        f"\n\n> ℹ️ 你在本阶段（{stage_info.name}）作为参与角色，配合主导角色完成工作。"
                    )

        if include_gate:
            gate_info = self.get_gate_prompt("gate_template")
            if gate_info:
                parts.append("\n\n---\n\n# 阶段门禁检查\n")
                parts.append(gate_info.prompt_content)

            handoff_info = self.get_gate_prompt("handoff_template")
            if handoff_info:
                parts.append("\n\n---\n\n# 交接协议\n")
                parts.append(handoff_info.prompt_content)

        return "\n".join(parts)

    def get_role_definitions_for_matcher(
        self,
    ) -> List[Dict[str, Any]]:
        result = []
        for role_id, role_info in self._role_prompts.items():
            result.append(
                {
                    "role_id": role_id,
                    "name": role_info.name,
                    "description": role_info.description,
                    "capabilities": role_info.capabilities,
                    "skills": role_info.skills,
                    "keywords": role_info.keywords,
                    "priority": role_info.priority,
                }
            )
        return result

    def get_role_definitions_for_skills_index(self) -> Dict[str, Any]:
        roles = {}
        for role_id, role_info in self._role_prompts.items():
            roles[role_id] = {
                "name": role_info.name,
                "description": role_info.description,
                "keywords": role_info.keywords,
                "priority": role_info.priority,
            }
        return roles

    def get_workflow_steps_for_manifest(self) -> List[Dict[str, Any]]:
        steps = []
        for stage_id, stage_info in self._stage_prompts.items():
            steps.append(
                {
                    "step_id": stage_id,
                    "name": stage_info.name,
                    "role": stage_info.lead_role,
                    "action": f"execute_{stage_id}",
                }
            )
        return steps

    def get_stage_for_role(self, role_id: str) -> List[str]:
        lead_stages = []
        for stage_id, mapping in STAGE_ROLE_MAPPING.items():
            if mapping == role_id:
                lead_stages.append(stage_id)
        return lead_stages

    def get_lifecycle_overview(self) -> str:
        lines = ["# 项目全生命周期概览\n"]
        for stage_id in sorted(STAGE_METADATA.keys()):
            stage_info = self._stage_prompts.get(stage_id)
            if stage_info:
                role_info = self._role_prompts.get(stage_info.lead_role)
                role_name = role_info.name if role_info else stage_info.lead_role
                lines.append(
                    f"- **{stage_info.name}** ({stage_info.name_en}) — 主导：{role_name}"
                )
        lines.append(
            "\n> ⚠️ 绝对禁止：未经过设计阶段直接开始编码 | 文档未完成就开始开发 | 未经过评审直接实施"
        )
        return "\n".join(lines)


def main():
    registry = PromptRegistry()

    print("\n" + "=" * 60)
    print("角色提示词列表")
    print("=" * 60)
    for role_id, role_info in registry.get_all_roles().items():
        print(f"  {role_id}: {role_info.name} ({role_info.name_en}) - 优先级: {role_info.priority}")

    print("\n" + "=" * 60)
    print("阶段提示词列表")
    print("=" * 60)
    for stage_id, stage_info in registry.get_all_stages().items():
        print(f"  {stage_id}: {stage_info.name} - 主导角色: {stage_info.lead_role}")

    print("\n" + "=" * 60)
    print("组合提示词示例：架构师 + 阶段2 + 门禁")
    print("=" * 60)
    composed = registry.compose_prompt("architect", "stage2", include_gate=True)
    print(composed[:500] + "..." if len(composed) > 500 else composed)

    print("\n" + "=" * 60)
    print("全生命周期概览")
    print("=" * 60)
    print(registry.get_lifecycle_overview())

    print("\n" + "=" * 60)
    print("角色定义数据（供 role_matcher.py 使用）")
    print("=" * 60)
    for role_def in registry.get_role_definitions_for_matcher():
        print(f"  {role_def['role_id']}: {role_def['name']} - 关键词: {role_def['keywords'][:3]}...")


if __name__ == "__main__":
    main()
