#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PromptAssembler - 提示词动态组装引擎

借鉴 Claude Code 架构中的三个提示词优化机制:

  借鉴① Feature Flag 驱动的动态裁剪:
    按任务复杂度(Simple/Medium/Complex)自动选择不同冗余度的模板变体，
    简单任务用3行精简指令，复杂任务用增强模板(+约束+反模式+参考)。

  借鉴③ 压缩状态感知适配:
    ContextCompressor 的压缩级别(NONE/SNIP/SESSION_MEMORY/FULL_COMPACT)
    直接影响 prompt 的风格和详细程度，实现"越压缩越精简"的自适应。

设计原则:
    - 不新增独立服务，作为 Worker._do_work() 的内嵌组装器
    - 所有变体从 ROLE_TEMPLATES 派生（不改原始模板）
    - 复杂度检测全自动（基于描述长度/关键词/结构信号）
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum


class TaskComplexity(Enum):
    """任务复杂度级别"""
    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass
class AssembledPrompt:
    """
    组装后的提示词结果

    Attributes:
        instruction: 最终工作指令文本
        complexity: 检测到的任务复杂度
        variant_used: 使用的模板变体名称
        tokens_estimate: 估算的 token 数量
        metadata: 额外元数据（如触发关键词、裁剪原因等）
    """
    instruction: str
    complexity: TaskComplexity
    variant_used: str
    tokens_estimate: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class PromptAssembler:
    """
    提示词动态组装器

    核心流程:
        task_description → detect_complexity() → select_template()
            → assemble(related_findings) → AssembledPrompt

    与现有组件的关系:
    - Worker._do_work(): 调用方，传入 context 后获取 AssembledPrompt
    - ROLE_TEMPLATES: 变体基线来源（dispatcher.py 中定义）
    - ContextCompressor.CompressionLevel: 压缩感知输入（可选）

    使用示例:
        assembler = PromptAssembler(role_id="architect", base_prompt=role_template)
        result = assembler.assemble(task_description="设计微服务架构",
                                    related_findings=["发现A"],
                                    compression_level=CompressionLevel.NONE)
        print(result.instruction)
    """

    _COMPLEXITY_KEYWORDS = {
        TaskComplexity.SIMPLE: {
            "positive": ["写一个", "写个", "创建", "添加", "修复bug",
                        "改个", "简单", "快速", "单个函数", "一行代码",
                        "小改动", "补全", "格式化", "重命名", "hello",
                        "工具类", "小bug", "排序函数", "日志"],
            "negative": ["架构", "系统设计", "分布式", "重构", "迁移",
                        "多模块", "全栈", "端到端", "完整方案",
                        "高可用", "容灾", "微服务架构"],
        },
        TaskComplexity.COMPLEX: {
            "positive": ["架构", "设计模式", "微服务", "分布式",
                        "重构", "迁移", "安全审计", "性能优化",
                        "完整方案", "系统设计", "技术选型",
                        "端到端", "全链路", "高可用", "容灾",
                        "CI/CD", "流水线", "全面优化"],
            "negative": ["写个函数", "简单修改", "小调整", "补个测试",
                        "快速修复", "hello world"],
        },
    }

    _TEMPLATE_VARIANTS = {
        TaskComplexity.SIMPLE: {
            "name": "compact",
            "role_truncate": 80,
            "findings_limit": 2,
            "findings_truncate": 60,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "direct",
        },
        TaskComplexity.MEDIUM: {
            "name": "standard",
            "role_truncate": 200,
            "findings_limit": 5,
            "findings_truncate": 150,
            "include_constraints": True,
            "include_anti_patterns": False,
            "instruction_style": "structured",
        },
        TaskComplexity.COMPLEX: {
            "name": "enhanced",
            "role_truncate": 500,
            "findings_limit": 8,
            "findings_truncate": 200,
            "include_constraints": True,
            "include_anti_patterns": True,
            "instruction_style": "comprehensive",
        },
    }

    _COMPRESSION_OVERRIDES = {
        "NONE": {},
        "SNIP": {
            "role_truncate": 120,
            "findings_limit": 3,
            "findings_truncate": 100,
            "include_constraints": False,
            "include_anti_patterns": False,
        },
        "SESSION_MEMORY": {
            "role_truncate": 60,
            "findings_limit": 1,
            "findings_truncate": 50,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "minimal",
        },
        "FULL_COMPACT": {
            "role_truncate": 40,
            "findings_limit": 0,
            "findings_truncate": 0,
            "include_constraints": False,
            "include_anti_patterns": False,
            "instruction_style": "ultra_minimal",
        },
    }

    def __init__(self, role_id: str, base_prompt: str):
        """
        初始化提示词组装器

        Args:
            role_id: 角色标识（用于角色特定的裁剪策略）
            base_prompt: 基础角色提示词模板（来自 ROLE_TEMPLATES）
        """
        self.role_id = role_id
        self.base_prompt = base_prompt

    def detect_complexity(self, task_description: str) -> TaskComplexity:
        """
        自动检测任务复杂度

        三维评分模型:
          1. 长度维度: <30字→Simple, 30~150字→Medium, >150字→Complex
          2. 关键词维度: 匹配 SIMPLE/COMPLEX 关键词组
          3. 结构维度: 是否包含编号列表/多个问题/多层要求

        Args:
            task_description: 任务描述文本

        Returns:
            TaskComplexity: 检测到的复杂度级别
        """
        desc_lower = task_description.lower()
        desc_len = len(task_description)

        score_simple = 0.0
        score_complex = 0.0

        length_score = 0.0
        if desc_len < 15:
            length_score = -0.5
        elif desc_len < 30:
            length_score = -0.3
        elif desc_len < 150:
            length_score = 0.0
        else:
            length_score = 0.3

        simple_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.SIMPLE]
        complex_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.COMPLEX]

        for kw in simple_kw["positive"]:
            if kw in desc_lower:
                score_simple += 0.15
        for kw in simple_kw["negative"]:
            if kw in desc_lower:
                score_simple -= 0.2

        for kw in complex_kw["positive"]:
            if kw in desc_lower:
                score_complex += 0.2
        for kw in complex_kw["negative"]:
            if kw in desc_lower:
                score_complex -= 0.15

        has_numbering = bool(re.search(r'\d+[.\)、]', task_description))
        has_multi_question = task_description.count('?') >= 2
        has_multi_requirement = len(re.split(r'[;；\n]', task_description)) >= 3

        structure_bonus = 0.0
        if has_numbering:
            structure_bonus += 0.1
        if has_multi_question:
            structure_bonus += 0.15
        if multi_requirement := has_multi_requirement:
            structure_bonus += 0.1

        final_simple = score_simple + length_score * 0.5
        final_complex = score_complex + length_score * 0.5 + structure_bonus

        if not task_description.strip():
            return TaskComplexity.SIMPLE
        if desc_len < 15:
            return TaskComplexity.SIMPLE
        if final_complex > 0.3 and final_complex > final_simple + 0.1:
            return TaskComplexity.COMPLEX
        if final_simple > 0.15 and final_simple > final_complex + 0.05:
            return TaskComplexity.SIMPLE
        return TaskComplexity.MEDIUM

    def assemble(self,
                 task_description: str,
                 related_findings: List[str] = None,
                 task_id: str = "",
                 compression_level=None) -> AssembledPrompt:
        """
        组装最终提示词

        完整流程:
        1. 检测任务复杂度
        2. 选择基础模板变体
        3. 应用压缩级别覆盖（如有）
        4. 按配置裁剪各部分内容
        5. 组装最终指令

        Args:
            task_description: 任务描述
            related_findings: 相关发现列表（来自 Scratchpad）
            task_id: 任务ID（用于指令头）
            compression_level: ContextCompressor 压缩级别（可选）

        Returns:
            AssembledPrompt: 组装结果，包含 instruction/complexity/variant/metadata
        """
        complexity = self.detect_complexity(task_description)
        config = dict(self._TEMPLATE_VARIANTS[complexity])

        if compression_level is not None:
            override_key = compression_level.name if hasattr(compression_level, 'name') else str(compression_level).upper()
            override = self._COMPRESSION_OVERRIDES.get(override_key, {})
            config.update(override)

        role_display = self.base_prompt[:config["role_truncate"]]
        findings_to_include = (related_findings or [])[:config["findings_limit"]]
        truncated_findings = [
            f[:config["findings_truncate"]] for f in findings_to_include
        ]

        style = config.get("instruction_style", "structured")
        instruction = self._build_instruction(
            style=style,
            task_id=task_id,
            task_description=task_description,
            role_display=role_display,
            findings=truncated_findings,
            include_constraints=config.get("include_constraints", False),
            include_anti_patterns=config.get("include_anti_patterns", False),
        )

        token_est = len(instruction) // 3

        return AssembledPrompt(
            instruction=instruction,
            complexity=complexity,
            variant_used=config.get("name", f"{complexity.value}_custom"),
            tokens_estimate=token_est,
            metadata={
                "compression_applied": compression_level is not None,
                "compression_level": str(compression_level),
                "original_base_length": len(self.base_prompt),
                "assembled_length": len(instruction),
                "findings_included": len(truncated_findings),
                "findings_total": len(related_findings or []),
            },
        )

    def _build_instruction(self,
                           style: str,
                           task_id: str,
                           task_description: str,
                           role_display: str,
                           findings: List[str],
                           include_constraints: bool,
                           include_anti_patterns: bool) -> str:
        """
        按指定风格构建工作指令

        Args:
            style: 指令风格 (direct/structured/comprehensive/minimal/ultra_minimal)
            task_id: 任务ID
            task_description: 任务描述
            role_display: 裁剪后的角色提示词
            findings: 裁剪后的相关发现列表
            include_constraints: 是否包含约束提醒
            include_anti_patterns: 是否包含反模式警告

        Returns:
            str: 组装好的指令文本
        """
        if style == "ultra_minimal":
            return (
                f"[{self.role_id}] {task_description}\n"
                f"输出核心结论。"
            )

        if style == "minimal":
            parts = [f"[{self.role_id}] 任务: {task_description}"]
            if findings:
                parts.append(f"参考: {findings[0][:50]}")
            parts.append("输出关键结论。")
            return "\n".join(parts)

        if style == "direct":
            return (
                f"=== 任务 ===\n"
                f"描述: {task_description}\n"
                f"角色: {role_display}...\n\n"
                + (f"=== 相关发现 ===\n" +
                   "\n".join(f"- {f}" for f in findings) + "\n\n" if findings else "") +
                "完成你的工作，输出核心结论。"
            )

        parts = []
        parts.append(f"=== 任务 ===")
        if task_id:
            parts.append(f"任务ID: {task_id}")
        parts.append(f"描述: {task_description}")
        parts.append(f"角色: {role_display}")
        parts.append("")

        if findings:
            parts.append("=== 相关发现（来自其他Worker） ===")
            for i, f in enumerate(findings, 1):
                parts.append(f"  {i}. {f}")
            parts.append("")

        if include_constraints:
            parts.append("=== 约束条件 ===")
            parts.append("- 输出需可执行、可验证")
            parts.append("- 标注假设和风险点")
            parts.append("")

        if include_anti_patterns:
            anti_patterns = self._get_role_anti_patterns()
            if anti_patterns:
                parts.append("=== 反模式警告 ===")
                for ap in anti_patterns:
                    parts.append(f"- 避免: {ap}")
                parts.append("")

        parts.append("请基于以上信息完成你的工作。")
        if style == "comprehensive":
            parts.append("输出应包含: 分析过程、关键决策、具体方案、风险评估。")
        else:
            parts.append("输出你的核心发现（1-3条关键结论）。")

        return "\n".join(parts)

    def _get_role_anti_patterns(self) -> List[str]:
        """
        获取角色相关的反模式警告列表

        不同角色有不同的常见反模式。

        Returns:
            List[str]: 该角色应避免的反模式列表
        """
        patterns = {
            "architect": [
                "过度设计(YAGNI违反)",
                "忽略非功能性需求(性能/安全/运维)",
                "技术选型只看流行度不考虑团队能力",
            ],
            "tester": [
                "只写Happy Path测试",
                "测试与业务需求脱节",
                "Mock过度导致测试无意义",
            ],
            "solo-coder": [
                "跳过设计直接编码",
                "不做边界条件处理",
                "硬编码配置和魔法数字",
            ],
            "product_manager": [
                "需求模糊导致反复变更",
                "优先级混乱",
                "忽视技术可行性",
            ],
            "ui-designer": [
                "只做视觉稿不考虑交互状态",
                "忽略响应式和无障碍",
                "设计系统不一致",
            ],
        }
        return patterns.get(self.role_id, [])

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """
        粗估文本的 token 数量

        中英文混合场景下，约 3 字符 ≈ 1 token。

        Args:
            text: 待估算的文本

        Returns:
            int: 估算的 token 数量
        """
        return max(1, len(text) // 3)
