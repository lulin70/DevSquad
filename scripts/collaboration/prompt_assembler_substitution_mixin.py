"""Variable substitution mixin for PromptAssembler.

Extracts context-injection helpers (user rules, role anti-patterns,
methodology skills, anti-rationalization content) and the shared
keyword-extraction utility so the main assembler file can focus on
orchestration.

Responsibilities (from IMPROVEMENT_PLAN_V3.9.2.md P2-3):
    - Placeholder substitution / context injection
    - User rule formatting
    - Skill & anti-rationalization injection
"""

import logging
import re
from typing import cast

from .prompt_assembler_base import PromptAssemblerBase

logger = logging.getLogger(__name__)


class PromptAssemblerSubstitutionMixin(PromptAssemblerBase):
    """Provides context-injection helpers for PromptAssembler."""

    _STOP_WORDS = frozenset(
        {
            "the",
            "is",
            "to",
            "of",
            "it",
            "in",
            "on",
            "at",
            "by",
            "an",
            "be",
            "do",
            "or",
            "as",
            "if",
            "so",
            "no",
            "not",
            "but",
            "and",
            "for",
            "with",
            "this",
            "that",
            "from",
            "are",
            "was",
            "were",
            "been",
            "have",
            "has",
            "had",
            "will",
            "would",
            "could",
            "should",
            "may",
            "might",
            "can",
            "shall",
            "a",
            "i",
            "you",
            "he",
            "she",
            "we",
            "they",
            "me",
            "him",
            "her",
            "us",
            "them",
            "my",
            "your",
            "his",
            "its",
            "our",
        }
    )

    def _get_user_rules_injection(self, task_description: str) -> str:
        """Query user rules from RuleCollector storage and format as prompt text."""
        try:
            from scripts.collaboration.rule_collector import RuleStorage

            if not hasattr(self, "_rule_storage"):
                self._rule_storage = RuleStorage.get_shared()
            keywords = self._extract_keywords(task_description)
            rules = self._rule_storage.query(trigger_keywords=keywords, min_confidence=0.5)
            if not rules:
                return ""
            lines = []
            for r in rules[:10]:
                rtype = r.get("type", "always")
                trigger = r.get("trigger", "")
                action = r.get("action", "")
                if rtype == "forbid":
                    lines.append(f"FORBIDDEN: {trigger + ' -> ' if trigger else ''}{action}")
                elif rtype == "avoid":
                    lines.append(f"AVOID: {trigger + ' -> ' if trigger else ''}{action}")
                elif rtype == "always":
                    lines.append(f"ALWAYS: {trigger + ' -> ' if trigger else ''}{action}")
                elif rtype == "prefer":
                    lines.append(f"PREFER: {trigger + ' -> ' if trigger else ''}{action}")
            return "\n".join(lines)
        except (AttributeError, TypeError, KeyError, ValueError) as e:
            logger.warning("format_rules_as_prompt failed: %s", e)
            return ""

    @staticmethod
    def _extract_keywords(text: str, max_keywords: int = 8) -> list[str]:
        """Extract keywords from text, supporting both CJK and Latin scripts."""
        keywords = []
        for w in text.split():
            if len(w) > 1 and w.lower() not in PromptAssemblerSubstitutionMixin._STOP_WORDS:
                keywords.append(w)
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in text)
        if has_cjk:
            cjk_segments = re.findall(r"[\u4e00-\u9fff]{2,}", text)
            for seg in cjk_segments:
                for i in range(0, len(seg) - 1, 2):
                    keywords.append(seg[i : i + 2])
        return keywords[:max_keywords]

    def _get_role_anti_patterns(self) -> list[str]:
        """
        Get role-specific anti-pattern warning list

        Different roles have different common anti-patterns.

        Returns:
            List[str]: List of anti-patterns this role should avoid
        """
        patterns = {
            "architect": [
                "Over-engineering (YAGNI violation)",
                "Ignoring non-functional requirements (performance/security/ops)",
                "Tech selection based only on popularity without considering team capability",
            ],
            "tester": [
                "Only writing happy path tests",
                "Tests disconnected from business requirements",
                "Excessive mocking making tests meaningless",
            ],
            "solo-coder": [
                "Skipping design and jumping to coding",
                "Not handling edge cases",
                "Hardcoded configuration and magic numbers",
            ],
            "product_manager": [
                "Vague requirements leading to repeated changes",
                "Priority confusion",
                "Ignoring technical feasibility",
            ],
            "ui-designer": [
                "Only creating visual mockups without considering interaction states",
                "Ignoring responsive design and accessibility",
                "Inconsistent design system",
            ],
        }
        return patterns.get(self.role_id, [])

    def _get_skill_injection(self) -> str:
        """
        Inject role-specific methodology skills from SKILL.md files.

        Loaded via RoleSkillLoader, these provide structured frameworks
        (e.g., PRD template, Opportunity Solution Tree) that the role
        should follow step-by-step.

        Returns:
            str: Formatted skill instructions, or empty string if none
        """
        try:
            from scripts.collaboration.role_skill_loader import get_shared_loader

            if not hasattr(self, "_skill_loader"):
                self._skill_loader = get_shared_loader()

            skills = self._skill_loader.load_skills(self.role_id)
            if not skills:
                return ""

            parts = ["\n\n## Methodology Frameworks (Follow these step-by-step)"]
            for skill in skills:
                parts.append(skill.to_prompt_text(max_length=1500))
            parts.append("")

            return "\n".join(parts)
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug("RoleSkillLoader not available: %s", e)
            return ""

    def _get_anti_rationalization_injection(self) -> str:
        """
        Inject AntiRationalizationEngine content into prompt (P0-1).

        Loads per-role excuse->rebuttal table and formats as markdown.
        This is the primary defense against Workers skipping quality steps.

        Returns:
            str: Formatted AR table, or empty string if unavailable
        """
        try:
            from scripts.collaboration.anti_rationalization import get_shared_engine

            if not hasattr(self, "_ar_engine"):
                self._ar_engine = get_shared_engine()
            return cast(str, self._ar_engine.format_for_prompt(self.role_id))
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug("AntiRationalizationEngine not available: %s", e)
            return ""
