"""Intent Detection Skill — 用户意图自动识别与工作流映射。"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from skills.registry import BaseSkill


class IntentSkill(BaseSkill):
    name = "intent"
    description = "Detect user intent from natural language and map to workflow chain (6 intents × 3 languages)"
    version = "3.6.0"

    INTENT_MAP = {
        "bug_fix": "🐛 Bug修复",
        "new_feature": "✨ 新功能开发",
        "code_review": "🔍 代码评审",
        "refactor": "♻️ 重构优化",
        "investigation": "🔬 问题排查",
        "documentation": "📝 文档编写",
    }

    def detect(self, text: str, lang: str = "auto") -> dict:
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
        return [self.detect(t, **kwargs) for t in texts]

    def list_intents(self) -> list:
        return [
            {"type": k, "label": v, "description": self._describe(k)}
            for k, v in self.INTENT_MAP.items()
        ]

    @staticmethod
    def _describe(intent_type: str) -> str:
        descs = {
            "bug_fix": "Fix defects, errors, or unexpected behavior",
            "new_feature": "Build new functionality or features",
            "code_review": "Review code quality, security, performance",
            "refactor": "Improve code structure without changing behavior",
            "investigation": "Diagnose root cause of problems",
            "documentation": "Create or update documentation",
        }
        return descs.get(intent_type, "")
