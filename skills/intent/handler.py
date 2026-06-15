"""Intent Detection Skill — User intent recognition and workflow mapping.

Automatically detects user intent from natural language input and maps
it to the appropriate workflow chain with required roles and stages.

Supported Intents (6 types × 3 languages):
    - bug_fix: 🐛 Bug fixing and defect resolution
    - new_feature: ✨ New feature development
    - code_review: 🔍 Code quality review and audit
    - refactor: ♻️ Code refactoring and optimization
    - investigation: 🔬 Problem diagnosis and root cause analysis
    - documentation: 📝 Documentation creation and updates

Integration:
    Uses IntentWorkflowMapper for detection and mapping to collaboration workflows.

Example:
    >>> from skills.intent.handler import IntentSkill
    >>> skill = IntentSkill()
    >>> result = skill.detect("Fix the login bug that crashes on submit")
    >>> print(result["intent"])  # "bug_fix"
    >>> print(result["required_roles"])  # ["solo-coder", "tester"]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from skills.registry import BaseSkill


class IntentSkill(BaseSkill):
    """User intent detection and workflow mapping skill.

    Analyzes natural language input to determine user intent and
    automatically maps it to the appropriate DevSquad workflow configuration,
    including required roles, optional roles, and execution stages.

    Attributes:
        name: Skill identifier ("intent")
        description: Human-readable skill description
        version: Skill semantic version (3.7.0)
        INTENT_MAP: Mapping of intent types to display labels

    Example:
        >>> skill = IntentSkill()
        >>> result = skill.detect("我们需要重构用户认证模块")
        >>> print(f"Intent: {result['label']}")
        >>> print(f"Confidence: {result['confidence']}")
        >>> print(f"Roles needed: {result['required_roles']}")
    """
    name = "intent"
    description = "Detect user intent from natural language and map to workflow chain (6 intents × 3 languages)"
    version = "3.7.0"

    INTENT_MAP = {
        "bug_fix": "🐛 Bug修复",
        "new_feature": "✨ 新功能开发",
        "code_review": "🔍 代码评审",
        "refactor": "♻️ 重构优化",
        "investigation": "🔬 问题排查",
        "documentation": "📝 文档编写",
    }

    def detect(self, text: str, lang: str = "auto") -> dict:
        """Detect intent from natural language text.

        Analyzes input text to identify the user's underlying intent
        and returns structured information about detected intent type,
        confidence level, required roles, and suggested workflow chain.

        Args:
            text: Natural language text to analyze (e.g., task description)
            lang: Language code - "auto" (detect automatically), "zh", "en", "ja"

        Returns:
            Dict with keys:
                - intent: str - Detected intent type identifier
                - label: str - Human-readable label with emoji (e.g., "🐛 Bug修复")
                - confidence: float - Detection confidence score (0.0-1.0)
                - lang: str - Detected or specified language
                - required_roles: list - Role IDs required for this intent
                - optional_roles: list - Optional but recommended role IDs
                - workflow_chain: list - Suggested workflow stage names
                - gates: list - Quality gates to apply (reserved)

        Example:
            >>> result = skill.detect("Fix authentication crash on login")
            >>> if result["confidence"] > 0.7:
            ...     print(f"Detected: {result['label']}")
        """
        from scripts.collaboration.intent_workflow_mapper import IntentWorkflowMapper

        mapper = IntentWorkflowMapper()
        result = mapper.detect_intent(text, lang=lang)
        icon = self.INTENT_MAP.get(result.intent_type, "❓")
        return {
            "intent": result.intent_type,
            "label": f"{icon} {result.intent_type}",
            "confidence": round(result.confidence, 4),
            "lang": lang,
            "required_roles": result.required_roles or [],
            "optional_roles": result.optional_roles or [],
            "workflow_chain": result.workflow_chain or [],
            "gates": [],
        }

    def batch_detect(self, texts: list, **kwargs) -> list:
        """Detect intents for multiple texts in batch.

        Convenience method for processing multiple inputs at once.
        Applies detect() to each text independently.

        Args:
            texts: List of natural language texts to analyze
            **kwargs: Additional arguments passed to detect() (e.g., lang)

        Returns:
            List of detection result dicts (same format as detect() return)
        """
        return [self.detect(t, **kwargs) for t in texts]

    def list_intents(self) -> list:
        """List all supported intent types with descriptions.

        Returns metadata about all available intent categories for
        display, documentation, or selection interfaces.

        Returns:
            List of dicts with keys:
                - type: Intent type identifier (e.g., "bug_fix")
                - label: Display label with emoji (e.g., "🐛 Bug修复")
                - description: One-line description of when to use this intent
        """
        return [{"type": k, "label": v, "description": self._describe(k)} for k, v in self.INTENT_MAP.items()]

    @staticmethod
    def _describe(intent_type: str) -> str:
        """Get human-readable description for an intent type.

        Args:
            intent_type: Intent type identifier string

        Returns:
            Description string explaining when this intent applies.
        """
        descs = {
            "bug_fix": "Fix defects, errors, or unexpected behavior",
            "new_feature": "Build new functionality or features",
            "code_review": "Review code quality, security, performance",
            "refactor": "Improve code structure without changing behavior",
            "investigation": "Diagnose root cause of problems",
            "documentation": "Create or update documentation",
        }
        return descs.get(intent_type, "")
