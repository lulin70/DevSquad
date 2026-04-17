#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PromptVariantGenerator - 提示词变体生成器（Skillify 闭环反哺）

填补 Skillifier → 提示词系统 的数据流断裂:
    执行成功 → Skillifier 提取模式 → [本模块] → 候选提示词变体
                                              ↓
                                    WarmupManager 缓存 (A/B 测试)
                                              ↓
                              验证通过 → 晋升为默认模板变体

核心能力:
  1. 从 SuccessPattern 生成候选 prompt 变体
  2. 变体质量评分（基于模式置信度/频率/角色匹配度）
  3. 缓存到 WarmupManager，支持 A/B 对比
  4. 变体晋升机制（candidate → promoted）

与现有组件的关系:
  - 输入: Skillifier.SuccessPattern（成功执行模式）
  - 输出: 候选提示词文本 + 元数据
  - 存储: WarmupManager.set_cache()（进程级缓存）
  - 消费: PromptAssembler.assemble() 可读取并试用候选变体

设计原则:
    - 不修改原始 ROLE_TEMPLATES，只生成候选变体
    - 变体必须经过验证才可晋升
    - 自动降级：连续 N 次负面反馈则自动淘汰
"""

import hashlib
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    from .skillifier import SuccessPattern
except ImportError:
    class SuccessPattern:
        pattern_id = ""
        name = ""
        description = ""
        steps_template = []
        trigger_keywords = []
        applicable_roles = []
        frequency = 1
        confidence = 0.5


@dataclass
class PromptVariant:
    """
    提示词变体

    Attributes:
        variant_id: 变体唯一标识
        role_id: 适用角色
        source_pattern_id: 来源成功模式的 ID
        prompt_text: 生成的提示词文本
        status: 状态 (candidate/promoted/deprecated)
        quality_score: 质量评分 [0, 100]
        usage_count: 使用次数
        positive_feedback: 正面反馈次数
        negative_feedback: 负面反馈次数
        created_at: 创建时间
        promoted_at: 晋升时间（如有）
    """
    variant_id: str = field(default_factory=lambda: f"pv-{hashlib.md5(str(datetime.now()).encode()).hexdigest()[:12]}")
    role_id: str = ""
    source_pattern_id: str = ""
    prompt_text: str = ""
    status: str = "candidate"
    quality_score: float = 0.0
    usage_count: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    promoted_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return {
            "variant_id": self.variant_id,
            "role_id": self.role_id,
            "source_pattern_id": self.source_pattern_id,
            "status": self.status,
            "quality_score": round(self.quality_score, 1),
            "usage_count": self.usage_count,
            "positive_feedback": self.positive_feedback,
            "negative_feedback": self.negative_feedback,
            "feedback_ratio": round(self._feedback_ratio(), 2),
            "created_at": self.created_at.isoformat(),
        }

    def _feedback_ratio(self) -> float:
        total = self.positive_feedback + self.negative_feedback
        if total == 0:
            return 0.0
        return self.positive_feedback / total


@dataclass
class VariantGenerationResult:
    """变体生成结果"""
    success: bool
    variant: Optional[PromptVariant] = None
    reason: str = ""


class PromptVariantGenerator:
    """
    提示词变体生成器

    将 Skillifier 的成功模式转化为可用的提示词变体，
    通过 WarmupManager 缓存实现 A/B 测试和自动晋升。

    使用示例:
        gen = PromptVariantGenerator()
        result = gen.generate_from_pattern(success_pattern)
        if result.success:
            gen.cache_variant(result.variant)  # 存入缓存供 A/B 测试
            # ... 后续使用中收集反馈 ...
            gen.record_feedback(result.variant.variant_id, positive=True)
            gen.try_promote(result.variant.variant_id)  # 尝试晋升
    """

    MIN_CONFIDENCE = 0.7
    MIN_FREQUENCY = 2
    PROMOTION_THRESHOLD = 0.75
    DEPRECATION_THRESHOLD = 0.35
    MIN_USAGE_FOR_PROMOTION = 3

    def __init__(self):
        """初始化变体生成器"""
        self._variants: Dict[str, PromptVariant] = {}
        self._lock = threading.RLock()

    def generate_from_pattern(self,
                               pattern: SuccessPattern,
                               base_template: str = "") -> VariantGenerationResult:
        """
        从成功模式生成候选提示词变体

        生成逻辑:
        1. 质量门槛检查（置信度 >= 0.7 且频率 >= 2）
        2. 从模式步骤提取关键指令片段
        3. 组装为该角色的增强型提示词
        4. 计算质量评分

        Args:
            pattern: 成功执行模式（来自 Skillifier.analyze_history()）
            base_template: 该角色的基础提示词模板（可选，用于对比增强）

        Returns:
            VariantGenerationResult: 包含生成的变体或失败原因
        """
        if pattern.confidence < self.MIN_CONFIDENCE:
            return VariantGenerationResult(
                success=False,
                reason=f"置信度不足: {pattern.confidence:.2f} < {self.MIN_CONFIDENCE}"
            )

        if pattern.frequency < self.MIN_FREQUENCY:
            return VariantGenerationResult(
                success=False,
                reason=f"频率不足: {pattern.frequency} < {self.MIN_FREQUENCY}"
            )

        if not pattern.applicable_roles:
            return VariantGenerationResult(
                success=False,
                reason="模式未关联任何角色"
            )

        role_id = pattern.applicable_roles[0]
        prompt_text = self._assemble_variant_prompt(pattern, base_template)
        quality = self._calculate_quality(pattern, prompt_text)

        variant = PromptVariant(
            role_id=role_id,
            source_pattern_id=pattern.pattern_id,
            prompt_text=prompt_text,
            status="candidate",
            quality_score=quality,
            metadata={
                "pattern_name": pattern.name,
                "pattern_confidence": pattern.confidence,
                "pattern_frequency": pattern.frequency,
                "trigger_keywords": list(pattern.trigger_keywords)[:10],
                "step_count": len(pattern.steps_template),
                "generated_at": datetime.now().isoformat(),
            },
        )

        with self._lock:
            self._variants[variant.variant_id] = variant

        return VariantGenerationResult(success=True, variant=variant)

    def _assemble_variant_prompt(self,
                                  pattern: SuccessPattern,
                                  base_template: str) -> str:
        """
        从模式组装变体提示词

        结构:
          [角色特定头部]
          [从模式提取的关键步骤指引]
          [触发关键词作为上下文锚点]
          [输出要求]

        Args:
            pattern: 成功模式
            base_template: 基础模板（用于参考头部格式）

        Returns:
            str: 组装后的变体提示词
        """
        parts = []

        header = f"=== {pattern.name or '优化提示词'} (来自 {pattern.frequency} 次成功经验) ===\n"
        parts.append(header)

        if pattern.steps_template:
            parts.append("【推荐执行步骤】")
            for i, step in enumerate(pattern.steps_template[:6], 1):
                desc = step.description_template or step.action_type.value.replace("_", " ")
                risk_note = f" ⚠风险{step.estimated_risk:.0%}" if step.estimated_risk > 0.5 else ""
                req_mark = " *" if step.is_required else ""
                parts.append(f"  {i}. {desc}{risk_note}{req_mark}")
            parts.append("")

        if pattern.trigger_keywords:
            kw_str = ", ".join(pattern.trigger_keywords[:8])
            parts.append(f"【适用场景】包含以下关键词的任务: {kw_str}")
            parts.append("")

        output_guide = (
            "【输出要求】\n"
            "- 基于以上经验步骤执行\n"
            "- 标注每步的决策依据\n"
            "- 如遇偏差请说明原因"
        )
        parts.append(output_guide)

        return "\n".join(parts)

    def _calculate_quality(self, pattern: SuccessPattern,
                           prompt_text: str) -> float:
        """
        计算变体质量评分 [0, 100]

        维度:
        - 置信度贡献 (40%): 来自模式本身的置信度
        - 频率贡献 (20%): 出现频率越高越可信
        - 内容丰富度 (20%): 提示词长度和结构完整性
        - 特异性 (15%): 触发关键词数量
        - 步骤质量 (5%): 低风险步骤占比

        Args:
            pattern: 来源模式
            prompt_text: 生成的提示词

        Returns:
            float: 质量评分 [0, 100]
        """
        confidence_score = pattern.confidence * 40

        freq_score = min(20.0, pattern.frequency * 5)

        length_score = min(20.0, len(prompt_text) / 20 * 5)
        has_structure = "===" in prompt_text or "【" in prompt_text
        structure_bonus = 5.0 if has_structure else 0.0
        content_score = min(20.0, length_score + structure_bonus)

        specificity_score = min(15.0, len(pattern.trigger_keywords) * 1.5)

        safe_steps = sum(1 for ps in pattern.steps_template
                         if ps.estimated_risk < 0.5)
        total_steps = max(len(pattern.steps_template), 1)
        step_score = 5.0 * (safe_steps / total_steps)

        return round(confidence_score + freq_score + content_score +
                     specificity_score + step_score, 1)

    def get_variant(self, variant_id: str) -> Optional[PromptVariant]:
        """
        按 ID 获取变体

        Args:
            variant_id: 变体 ID

        Returns:
            Optional[PromptVariant]: 变体对象，不存在返回 None
        """
        with self._lock:
            return self._variants.get(variant_id)

    def get_candidates_for_role(self, role_id: str) -> List[PromptVariant]:
        """
        获取指定角色的所有候选变体（按质量排序）

        Args:
            role_id: 角色 ID

        Returns:
            List[PromptVariant]: 候选变体列表（质量分降序）
        """
        with self._lock:
            candidates = [v for v in self._variants.values()
                          if v.role_id == role_id and v.status == "candidate"]
            candidates.sort(key=lambda v: v.quality_score, reverse=True)
            return candidates

    def get_promoted_variants(self, role_id: str = "") -> List[PromptVariant]:
        """
        获取已晋升的变体

        Args:
            role_id: 角色 ID（为空则返回全部已晋升变体）

        Returns:
            List[PromptVariant]: 已晋升变体列表
        """
        with self._lock:
            results = [v for v in self._variants.values() if v.status == "promoted"]
            if role_id:
                results = [v for v in results if v.role_id == role_id]
            return results

    def record_usage(self, variant_id: str) -> bool:
        """
        记录一次变体使用

        Args:
            variant_id: 变体 ID

        Returns:
            bool: 是否成功记录
        """
        with self._lock:
            variant = self._variants.get(variant_id)
            if variant:
                variant.usage_count += 1
                return True
            return False

    def record_feedback(self, variant_id: str,
                        positive: bool = True) -> bool:
        """
        记录用户/AI 对变体的反馈

        Args:
            variant_id: 变体 ID
            positive: True=正面反馈, False=负面反馈

        Returns:
            bool: 是否成功记录
        """
        with self._lock:
            variant = self._variants.get(variant_id)
            if not variant:
                return False
            if positive:
                variant.positive_feedback += 1
            else:
                variant.negative_feedback += 1
            return True

    def try_promote(self, variant_id: str) -> Tuple[bool, str]:
        """
        尝试将候选变体晋升为正式变体

        晋升条件（需同时满足）:
        1. 使用次数 >= MIN_USAGE_FOR_PROMOTION (3次)
        2. 正面反馈率 >= PROMOTION_THRESHOLD (75%)
        3. 当前状态为 candidate

        Args:
            variant_id: 变体 ID

        Returns:
            Tuple[bool, str]: (是否晋升成功, 原因说明)
        """
        with self._lock:
            variant = self._variants.get(variant_id)
            if not variant:
                return False, "变体不存在"

            if variant.status != "candidate":
                return False, f"当前状态非candidate: {variant.status}"

            if variant.usage_count < self.MIN_USAGE_FOR_PROMOTION:
                return False, f"使用次数不足: {variant.usage_count} < {self.MIN_USAGE_FOR_PROMOTION}"

            ratio = variant._feedback_ratio()
            if ratio < self.PROMOTION_THRESHOLD:
                return False, f"正面反馈率不足: {ratio:.0%} < {self.PROMOTION_THRESHOLD:.0%}"

            variant.status = "promoted"
            variant.promoted_at = datetime.now()
            return True, f"晋升成功 (使用{variant.usage_count}次, 反馈率{ratio:.0%})"

    def auto_deprecate(self) -> List[str]:
        """
        自动淘汰低质量候选变体

        淘汰条件:
        1. 负面反馈率 >= DEPRECATION_THRESHOLD (35%) 且使用 >= 3 次
        2. 或创建超过 30 天且无任何使用

        Returns:
            List[str]: 被淘汰的变体 ID 列表
        """
        deprecated = []
        cutoff = datetime.now() - timedelta(days=30)

        with self._lock:
            for vid, variant in list(self._variants.items()):
                if variant.status != "candidate":
                    continue

                ratio = variant._feedback_ratio()
                should_deprecate = False

                if variant.usage_count >= 3 and ratio <= self.DEPRECATION_THRESHOLD:
                    should_deprecate = True
                elif variant.created_at < cutoff and variant.usage_count == 0:
                    should_deprecate = True

                if should_deprecate:
                    variant.status = "deprecated"
                    deprecated.append(vid)

        return deprecated

    def get_statistics(self) -> Dict[str, Any]:
        """
        获取变体统计信息

        Returns:
            Dict[str, Any]: 统计字典
        """
        with self._lock:
            all_vars = list(self._variants.values())
            candidates = [v for v in all_vars if v.status == "candidate"]
            promoted = [v for v in all_vars if v.status == "promoted"]
            deprecated = [v for v in all_vars if v.status == "deprecated"]

            total_usage = sum(v.usage_count for v in all_vars)
            total_positive = sum(v.positive_feedback for v in all_vars)
            total_negative = sum(v.negative_feedback for v in all_vars)

            return {
                "total_variants": len(all_vars),
                "candidates": len(candidates),
                "promoted": len(promoted),
                "deprecated": len(deprecated),
                "total_usage": total_usage,
                "total_positive_feedback": total_positive,
                "total_negative_feedback": total_negative,
                "overall_feedback_ratio": round(
                    total_positive / max(total_positive + total_negative, 1), 2
                ),
                "avg_quality_score": round(
                    sum(v.quality_score for v in all_vars) / max(len(all_vars), 1), 1
                ) if all_vars else 0.0,
            }
