"""Validation mixin for PromptAssembler.

Extracts task-complexity detection (input validation) so the main
assembler file can focus on orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Input validation / complexity detection
    - Keyword scoring tables
"""

import re

from .prompt_assembler_base import PromptAssemblerBase, TaskComplexity

_RE_NUMBERING = re.compile(r"\d+[.\)、]")
_RE_MULTI_REQ = re.compile(r"[;；\n]")


class PromptAssemblerValidationMixin(PromptAssemblerBase):
    """Provides task-complexity detection for PromptAssembler."""

    _COMPLEXITY_KEYWORDS = {
        TaskComplexity.SIMPLE: {
            "positive": [
                "write a",
                "create",
                "add",
                "fix bug",
                "change a",
                "simple",
                "quick",
                "single function",
                "one line of code",
                "small change",
                "complete",
                "format",
                "rename",
                "hello",
                "utility class",
                "minor bug",
                "sort function",
                "logging",
                "写个",
                "快速",
                "简单",
                "小修改",
                "修复",
                "添加",
                "工具函数",
                "排序函数",
                "日志",
                "格式化",
                "重命名",
            ],
            "negative": [
                "architecture",
                "system design",
                "distributed",
                "refactor",
                "migration",
                "multi-module",
                "full-stack",
                "end-to-end",
                "complete solution",
                "high availability",
                "disaster recovery",
                "microservice architecture",
                "架构",
                "分布式",
                "重构",
                "迁移",
                "微服务",
                "高可用",
                "容灾",
                "全链路",
                "端到端",
                "完整方案",
            ],
        },
        TaskComplexity.COMPLEX: {
            "positive": [
                "architecture",
                "design pattern",
                "microservice",
                "distributed",
                "refactor",
                "migration",
                "security audit",
                "performance optimization",
                "complete solution",
                "system design",
                "tech selection",
                "end-to-end",
                "full pipeline",
                "high availability",
                "disaster recovery",
                "CI/CD",
                "pipeline",
                "comprehensive optimization",
                "架构",
                "设计模式",
                "微服务",
                "分布式",
                "重构",
                "迁移",
                "安全审计",
                "性能优化",
                "完整方案",
                "系统设计",
                "技术选型",
                "端到端",
                "流水线",
                "高可用",
                "容灾",
                "负载均衡",
                "服务发现",
                "全面优化",
                "全链路",
                "监控告警",
            ],
            "negative": [
                "write a function",
                "simple modification",
                "minor adjustment",
                "add a test",
                "quick fix",
                "hello world",
                "写个函数",
                "简单修改",
                "小调整",
                "添加测试",
                "快速修复",
            ],
        },
    }

    def detect_complexity(self, task_description: str) -> TaskComplexity:
        """
        Automatically detect task complexity

        Three-dimensional scoring model:
          1. Length dimension: <30 chars -> Simple, 30~150 chars -> Medium, >150 chars -> Complex
          2. Keyword dimension: Match SIMPLE/COMPLEX keyword groups
          3. Structure dimension: Whether it contains numbered lists/multiple questions/multi-layer requirements

        Args:
            task_description: Task description text

        Returns:
            TaskComplexity: Detected complexity level
        """
        if not task_description.strip():
            return TaskComplexity.SIMPLE
        desc_lower = task_description.lower()
        desc_len = len(task_description)

        length_score = self._length_score(desc_len)
        score_simple, score_complex = self._keyword_scores(desc_lower)
        structure_bonus = self._structure_bonus(task_description)

        final_simple = score_simple + length_score * 0.5
        final_complex = score_complex + length_score * 0.5 + structure_bonus
        return self._classify_by_scores(final_simple, final_complex, desc_len)

    def _length_score(self, desc_len: int) -> float:
        """Return the length-dimension score for a task description."""
        if desc_len < 15:
            return -0.5
        if desc_len < 30:
            return -0.3
        if desc_len < 150:
            return 0.0
        return 0.3

    @staticmethod
    def _word_match(keyword: str, text: str) -> bool:
        """Match a complexity keyword against text (substring for CJK, word-boundary otherwise)."""
        if "\u4e00" <= keyword[0] <= "\u9fff":
            return keyword in text
        return bool(re.search(r"\b" + re.escape(keyword) + r"\b", text))

    def _keyword_scores(self, desc_lower: str) -> tuple[float, float]:
        """Return ``(simple_score, complex_score)`` from keyword matching."""
        simple_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.SIMPLE]
        complex_kw = self._COMPLEXITY_KEYWORDS[TaskComplexity.COMPLEX]
        score_simple = 0.0
        score_complex = 0.0
        for kw in simple_kw["positive"]:
            if self._word_match(kw, desc_lower):
                score_simple += 0.15
        for kw in simple_kw["negative"]:
            if self._word_match(kw, desc_lower):
                score_simple -= 0.2
        for kw in complex_kw["positive"]:
            if self._word_match(kw, desc_lower):
                score_complex += 0.2
        for kw in complex_kw["negative"]:
            if self._word_match(kw, desc_lower):
                score_complex -= 0.15
        return score_simple, score_complex

    def _structure_bonus(self, task_description: str) -> float:
        """Return the structure-dimension bonus (numbering/questions/multi-requirement)."""
        bonus = 0.0
        if _RE_NUMBERING.search(task_description):
            bonus += 0.1
        if task_description.count("?") >= 2:
            bonus += 0.15
        if len(_RE_MULTI_REQ.split(task_description)) >= 3:
            bonus += 0.1
        return bonus

    def _classify_by_scores(
        self, final_simple: float, final_complex: float, desc_len: int
    ) -> TaskComplexity:
        """Classify complexity from the final simple/complex scores and length."""
        if desc_len < 15:
            return TaskComplexity.SIMPLE
        if final_complex > 0.3 and final_complex > final_simple + 0.1:
            return TaskComplexity.COMPLEX
        if final_simple > 0.15 and final_simple > final_complex + 0.05:
            return TaskComplexity.SIMPLE
        return TaskComplexity.MEDIUM
