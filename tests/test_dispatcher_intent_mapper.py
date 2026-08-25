#!/usr/bin/env python3
"""Unit tests for IntentWorkflowMapper (V4.5.5 P4-P5 Wave 2).

12 tests covering 6 intents × 3 languages lazy resolution.
"""
from __future__ import annotations

import pytest

from scripts.collaboration.dispatcher_intent_mapper import (
    DEFAULT_INTENT,
    SUPPORTED_INTENTS,
    SUPPORTED_LANGS,
    IntentError,
    IntentWorkflowMapper,
    get_call_counter_er,
)


@pytest.fixture
def mapper() -> IntentWorkflowMapper:
    return IntentWorkflowMapper()


class TestIntentMapperLanguages:
    def test_intent_mapper_zh_workflow(self, mapper: IntentWorkflowMapper) -> None:
        wf = mapper.resolve("design", "zh")
        assert wf.intent == "design"
        assert wf.lang == "zh"
        assert "intent_design_zh" in wf.workflow_module
        assert not wf.is_default

    def test_intent_mapper_en_workflow(self, mapper: IntentWorkflowMapper) -> None:
        wf = mapper.resolve("test", "en")
        assert wf.intent == "test"
        assert wf.lang == "en"
        assert "intent_test_en" in wf.workflow_module

    def test_intent_mapper_ja_workflow(self, mapper: IntentWorkflowMapper) -> None:
        wf = mapper.resolve("optimize", "ja")
        assert wf.intent == "optimize"
        assert wf.lang == "ja"
        assert "intent_optimize_ja" in wf.workflow_module

    def test_intent_mapper_unknown_intent_fallback(self, mapper: IntentWorkflowMapper) -> None:
        """Unknown intent returns default workflow."""
        wf = mapper.resolve("nonexistent_intent", "zh")
        assert wf.is_default
        assert wf.intent == DEFAULT_INTENT

    def test_intent_mapper_unsupported_lang_raises(self, mapper: IntentWorkflowMapper) -> None:
        """Unsupported lang raises IntentError."""
        with pytest.raises(IntentError):
            mapper.resolve("design", "fr")  # French not in SUPPORTED_LANGS


class TestIntentMapperCaching:
    def test_intent_mapper_lazy_loading(self, mapper: IntentWorkflowMapper) -> None:
        """Same intent+lang returns cached workflow."""
        wf1 = mapper.resolve("audit", "en")
        wf2 = mapper.resolve("audit", "en")
        # Same dataclass (frozen=True means __hash__ works)
        assert wf1 == wf2
        # Identity (cached)
        assert wf1 is wf2

    def test_intent_mapper_list_workflows(self, mapper: IntentWorkflowMapper) -> None:
        """List all registered workflows (6 × 3 = 18)."""
        workflows = mapper.list_workflows()
        assert len(workflows) == 6 * 3
        for wf in workflows:
            assert wf.intent in SUPPORTED_INTENTS
            assert wf.lang in SUPPORTED_LANGS


class TestIntentMapperRegistration:
    def test_register_workflow_override(self, mapper: IntentWorkflowMapper) -> None:
        """Custom workflow registration overrides default."""
        mapper.register_workflow(
            intent="dev", lang="zh",
            workflow_module="custom.dev_zh", workflow_class="CustomDevWorkflow",
        )
        wf = mapper.resolve("dev", "zh")
        assert wf.workflow_module == "custom.dev_zh"
        assert wf.workflow_class == "CustomDevWorkflow"
        # Other languages untouched
        wf_en = mapper.resolve("dev", "en")
        assert wf_en.workflow_module != "custom.dev_zh"

    def test_register_workflow_rejects_path_traversal(self, mapper: IntentWorkflowMapper) -> None:
        """Path traversal in module name is rejected (Security)."""
        with pytest.raises(IntentError):
            mapper.register_workflow(
                intent="dev", lang="zh",
                workflow_module="..malicious.module", workflow_class="Evil",
            )

    def test_register_workflow_rejects_invalid_intent(self, mapper: IntentWorkflowMapper) -> None:
        with pytest.raises(IntentError):
            mapper.register_workflow(
                intent="nonexistent", lang="zh",
                workflow_module="custom.x", workflow_class="X",
            )


class TestIntentMapperSecurity:
    def test_module_path_no_traversal(self, mapper: IntentWorkflowMapper) -> None:
        """Default workflows use safe dotted paths (no .. or absolute)."""
        for intent, langs in mapper.DEFAULT_WORKFLOWS.items():
            for lang, dotted in langs.items():
                assert ".." not in dotted, f"{intent}/{lang}: traversal in {dotted}"
                assert not dotted.startswith("."), f"{intent}/{lang}: starts with .: {dotted}"


class TestIntentMapperAntiGhost:
    def test_call_counter_increments(self, mapper: IntentWorkflowMapper) -> None:
        before = get_call_counter_er()
        mapper.resolve("design", "zh")
        assert get_call_counter_er() > before


class TestIntentMapperAllIntents:
    """Verify all 6 intents × 3 languages work."""

    @pytest.mark.parametrize("intent", list(SUPPORTED_INTENTS))
    @pytest.mark.parametrize("lang", list(SUPPORTED_LANGS))
    def test_intent_lang_combination(self, mapper: IntentWorkflowMapper, intent: str, lang: str) -> None:
        wf = mapper.resolve(intent, lang)
        assert wf.intent == intent
        assert wf.lang == lang
        assert wf.workflow_module
        assert wf.workflow_class
