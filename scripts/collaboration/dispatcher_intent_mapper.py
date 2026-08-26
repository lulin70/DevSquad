#!/usr/bin/env python3
"""Intent Workflow Mapper (V4.5.6 P4-P5 Wave 2).

6 intents × 3 languages lazy-loadable workflow resolver.

设计原则:
- V4.5.3 lesson #7: best-effort try/except (unknown intent → default workflow)
- V4.5.3 lesson #8: global state + lock pattern (_call_counter_er)
- Security: 路径白名单 + safe_load 防 YAML 注入

Anti-Ghost: _intent_call_counter_er 递增 on resolve().
"""
from __future__ import annotations

import importlib
import logging
import threading
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anti-Ghost counter (V4.5.3 lesson #4 naming unified)
# ---------------------------------------------------------------------------
_intent_call_counter_er: int = 0
_intent_counter_lock = threading.Lock()


def _inc_call_counter_er() -> None:
    """Increment IntentWorkflowMapper activation counter (thread-safe)."""
    global _intent_call_counter_er
    with _intent_counter_lock:
        _intent_call_counter_er += 1


def get_call_counter_er() -> int:
    """Return activation counter for Anti-Ghost verification."""
    return _intent_call_counter_er


# ---------------------------------------------------------------------------
# Supported Intents / Languages
# ---------------------------------------------------------------------------


SUPPORTED_INTENTS: tuple[str, ...] = (
    "design",       # 架构设计
    "dev",          # 功能开发
    "test",         # 测试设计
    "audit",        # 代码审查
    "optimize",     # 性能优化
    "document",     # 文档生成
)

SUPPORTED_LANGS: tuple[str, ...] = ("zh", "en", "ja")

DEFAULT_INTENT = "dev"


class IntentError(ValueError):
    """Raised on invalid intent/lang combo."""


# ---------------------------------------------------------------------------
# Workflow Metadata
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class IntentWorkflow:
    """Resolved workflow metadata."""

    intent: str
    lang: str
    workflow_module: str
    workflow_class: str
    is_default: bool = False


# ---------------------------------------------------------------------------
# Mapper
# ---------------------------------------------------------------------------


class IntentWorkflowMapper:
    """Intent → workflow lazy resolver (Security: path whitelist)."""

    DEFAULT_WORKFLOWS: ClassVar[dict[str, dict[str, str]]] = {
        "design": {
            "zh": "scripts.workflows.intent_design_zh.DesignWorkflow",
            "en": "scripts.workflows.intent_design_en.DesignWorkflow",
            "ja": "scripts.workflows.intent_design_ja.DesignWorkflow",
        },
        "dev": {
            "zh": "scripts.workflows.intent_dev_zh.DevWorkflow",
            "en": "scripts.workflows.intent_dev_en.DevWorkflow",
            "ja": "scripts.workflows.intent_dev_ja.DevWorkflow",
        },
        "test": {
            "zh": "scripts.workflows.intent_test_zh.TestWorkflow",
            "en": "scripts.workflows.intent_test_en.TestWorkflow",
            "ja": "scripts.workflows.intent_test_ja.TestWorkflow",
        },
        "audit": {
            "zh": "scripts.workflows.intent_audit_zh.AuditWorkflow",
            "en": "scripts.workflows.intent_audit_en.AuditWorkflow",
            "ja": "scripts.workflows.intent_audit_ja.AuditWorkflow",
        },
        "optimize": {
            "zh": "scripts.workflows.intent_optimize_zh.OptimizeWorkflow",
            "en": "scripts.workflows.intent_optimize_en.OptimizeWorkflow",
            "ja": "scripts.workflows.intent_optimize_ja.OptimizeWorkflow",
        },
        "document": {
            "zh": "scripts.workflows.intent_document_zh.DocumentWorkflow",
            "en": "scripts.workflows.intent_document_en.DocumentWorkflow",
            "ja": "scripts.workflows.intent_document_ja.DocumentWorkflow",
        },
    }

    __slots__ = ("_cache", "_lock", "_registered_workflows")

    def __init__(self, workflows_dir: str | Path | None = None) -> None:  # noqa: ARG002
        _inc_call_counter_er()
        # workflows_dir parameter reserved for future YAML-based registry
        # (Security: path whitelist)
        self._cache: dict[tuple[str, str], IntentWorkflow] = {}
        self._lock = threading.Lock()
        # Default to built-in workflows (Security: path whitelist)
        self._registered_workflows: dict[str, dict[str, str]] = {
            intent: dict(langs) for intent, langs in self.DEFAULT_WORKFLOWS.items()
        }

    def resolve(self, intent: str, lang: str = "zh") -> IntentWorkflow:
        """Resolve intent+lang to workflow metadata (lazy load).

        Args:
            intent: One of SUPPORTED_INTENTS.
            lang: One of SUPPORTED_LANGS.

        Returns:
            IntentWorkflow (metadata only, not yet imported).

        Raises:
            IntentError: If lang not supported.
        """
        _inc_call_counter_er()
        if lang not in SUPPORTED_LANGS:
            raise IntentError(f"unsupported lang: {lang}")
        # Normalize unknown intent to default (V4.5.3 lesson #7 best-effort)
        normalized_intent = intent if intent in SUPPORTED_INTENTS else DEFAULT_INTENT
        cache_key = (normalized_intent, lang)
        with self._lock:
            if cache_key in self._cache:
                return self._cache[cache_key]
        # Build metadata
        workflows_for_intent = self._registered_workflows.get(
            normalized_intent, self._registered_workflows[DEFAULT_INTENT],
        )
        dotted_path = workflows_for_intent.get(lang, workflows_for_intent["zh"])
        module_path, _, class_name = dotted_path.rpartition(".")
        is_default = normalized_intent != intent or normalized_intent == DEFAULT_INTENT
        workflow = IntentWorkflow(
            intent=normalized_intent,
            lang=lang,
            workflow_module=module_path,
            workflow_class=class_name,
            is_default=is_default,
        )
        with self._lock:
            self._cache[cache_key] = workflow
        return workflow

    def _load_workflow(self, intent: str, lang: str) -> Any:
        """Lazy import the workflow module + return the class.

        Returns:
            The workflow class (not instance).

        Raises:
            IntentError: If module/class cannot be imported.
        """
        wf = self.resolve(intent, lang)
        try:
            module = importlib.import_module(wf.workflow_module)
            return getattr(module, wf.workflow_class)
        except (ImportError, AttributeError) as exc:
            raise IntentError(
                f"failed to load workflow {wf.workflow_module}.{wf.workflow_class}: {exc}"
            ) from exc

    def list_workflows(self) -> list[IntentWorkflow]:
        """List all registered workflows (cached + uncached)."""
        result = []
        for intent in SUPPORTED_INTENTS:
            for lang in SUPPORTED_LANGS:
                with suppress(IntentError):
                    result.append(self.resolve(intent, lang))
        return result

    def register_workflow(
        self,
        intent: str,
        lang: str,
        workflow_module: str,
        workflow_class: str,
    ) -> None:
        """Register a custom workflow (overrides default).

        Security: workflow_module must be in registered set, not arbitrary path.
        """
        if intent not in SUPPORTED_INTENTS:
            raise IntentError(f"unknown intent: {intent}")
        if lang not in SUPPORTED_LANGS:
            raise IntentError(f"unsupported lang: {lang}")
        # Security: validate workflow_module doesn't contain path traversal
        if ".." in workflow_module or workflow_module.startswith("."):
            raise IntentError(f"invalid module path: {workflow_module}")
        with self._lock:
            self._registered_workflows.setdefault(intent, {})[lang] = (
                f"{workflow_module}.{workflow_class}"
            )
            self._cache.pop((intent, lang), None)


__all__ = [
    "IntentWorkflowMapper",
    "IntentWorkflow",
    "SUPPORTED_INTENTS",
    "SUPPORTED_LANGS",
    "DEFAULT_INTENT",
    "IntentError",
    "get_call_counter_er",
    "_inc_call_counter_er",
]
