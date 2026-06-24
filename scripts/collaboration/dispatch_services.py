#!/usr/bin/env python3
"""Dispatch service classes — extracted from MultiAgentDispatcher.

These service classes encapsulate cross-cutting concerns previously implemented
as private methods on the dispatcher. Each service is self-contained with
explicit dependency injection via __init__.
"""

import logging
import os
import tempfile
import uuid
from typing import Any

from .memory_bridge import EpisodicMemory
from .models import EntryType
from .permission_guard import ActionType, ProposedAction
from .prometheus_metrics import get_metrics
from .rbac_engine import Permission, PermissionDeniedError
from .scratchpad import ScratchpadEntry

logger = logging.getLogger(__name__)


class MetricsService:
    """Safe Prometheus metrics recording wrapper."""

    def __init__(self, metrics_provider: Any = None) -> None:
        self._metrics = metrics_provider

    def safe_record(self, fn: Any) -> None:
        """Safely execute Prometheus metrics callback."""
        try:
            fn(get_metrics())
        except (ValueError, KeyError, AttributeError, RuntimeError) as _me:
            logger.debug("Metrics recording failed: %s", _me)


class PermissionService:
    """Permission checking via PermissionGuard and RBAC engine."""

    def __init__(
        self,
        permission_guard: Any = None,
        operation_classifier: Any = None,
        rbac_engine: Any = None,
        enable_rbac: bool = False,
        metrics_service: MetricsService | None = None,
    ) -> None:
        self.permission_guard = permission_guard
        self.operation_classifier = operation_classifier
        self.rbac_engine = rbac_engine
        self.enable_rbac = enable_rbac
        self.metrics_service = metrics_service

    def check_permissions(self, permission_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Run PermissionGuard checks on test actions."""
        test_actions = [
            ProposedAction(
                action_type=ActionType.FILE_CREATE, target=os.path.join(tempfile.gettempdir(), "test_output.md"), description="生成输出文件"
            ),
        ]
        for action in test_actions:
            classified = None
            try:
                classified = self.operation_classifier.classify(
                    operation_id=action.action_type.value, target=action.target,
                )
            except (ValueError, AttributeError, KeyError) as e:
                logger.debug("Operation classifier call failed: %s", e)
            decision = self.permission_guard.check(action)
            perm_entry = {
                "action": f"{action.action_type.value}:{action.target}",
                "allowed": decision.outcome.value == "ALLOWED",
                "decision": decision.outcome.value,
                "reason": decision.reason or "",
            }
            gate_result = "pass" if decision.outcome.value == "ALLOWED" else "fail"
            if self.metrics_service:
                self.metrics_service.safe_record(lambda m, r=gate_result: m.record_gate_check("permission", r))
            if classified:
                perm_entry["operation_category"] = classified.category.value
            permission_checks.append(perm_entry)
        return permission_checks

    def check_rbac(self, permission_checks: list[dict[str, Any]], **kwargs: Any) -> list[dict[str, Any]]:
        """Run RBAC fine-grained permission check."""
        try:
            user_id = kwargs.get('user_id', 'default')
            self.rbac_engine.enforce(user_id, Permission.TASK_EXECUTE)
            permission_checks.append({"action": "rbac:execute", "allowed": True})
        except PermissionDeniedError as e:
            permission_checks.append({"action": "rbac:execute", "allowed": False, "reason": str(e)})
        except (AttributeError, RuntimeError, KeyError) as e:
            logger.debug("RBAC permission check failed: %s", e)
        return permission_checks


class MemoryPipelineService:
    """Memory pipeline: capture, MCE classify, AI news injection."""

    def __init__(
        self,
        memory_bridge: Any = None,
        mce_adapter: Any = None,
        scratchpad: Any = None,
        enable_memory: bool = False,
        enterprise: Any = None,
    ) -> None:
        self.memory_bridge = memory_bridge
        self.mce_adapter = mce_adapter
        self.scratchpad = scratchpad
        self.enable_memory = enable_memory
        self.enterprise = enterprise

    def _get_current_tenant_id(self) -> str:
        """Get current tenant_id for data isolation, defaults to 'default'."""
        if self.enterprise and self.enterprise.enable_multi_tenant and self.enterprise.tenant_manager:
            current_tenant = self.enterprise.tenant_manager.get_current_tenant()
            if current_tenant:
                return current_tenant.tenant_id  # type: ignore[no-any-return]
        return "default"

    def capture(
        self,
        task: str,
        scratchpad_summary: str,
        role_ids: list[str],
        errors: list[str],
    ) -> dict[str, Any] | None:
        """Capture episodic memory via MemoryBridge."""
        memory_stats: dict[str, Any] | None = None

        if self.enable_memory and self.memory_bridge:
            try:
                mem_stats: Any = self.memory_bridge.get_statistics()
                tenant_id = self._get_current_tenant_id()
                memory_stats = {
                    "total_memories": mem_stats.total_memories,
                    "by_type_counts": mem_stats.by_type_counts,
                    "index_built": mem_stats.index_built,
                    "total_captures": mem_stats.total_captures,
                    "tenant_id": tenant_id,
                }

                # Tenant-isolated storage key prefix
                key_prefix = f"[{tenant_id}]" if tenant_id != "default" else ""
                EpisodicMemory(
                    id=f"epi-{tenant_id}-{uuid.uuid4().hex[:8]}" if key_prefix else f"epi-{uuid.uuid4().hex[:8]}",
                    task_description=f"{key_prefix}{task}" if key_prefix else task,
                    finding=scratchpad_summary[:500],
                )
                self.memory_bridge.capture_execution(
                    execution_record={"task": f"{key_prefix}{task}" if key_prefix else task, "roles": role_ids, "tenant_id": tenant_id},
                    scratchpad_entries=[],
                )
            except (ConnectionError, TimeoutError, OSError) as mem_err:
                logger.warning("MemoryBridge connection error: %s", mem_err)
                errors.append(f"MemoryBridge connection error: {type(mem_err).__name__}: {mem_err}")
            except (ValueError, KeyError, AttributeError) as mem_val_err:
                logger.debug("MemoryBridge data error: %s", mem_val_err)
                errors.append(f"MemoryBridge data error: {mem_val_err}")
            except RuntimeError as mem_err:  # Broad catch: unpredictable memory system
                logger.warning("Unexpected MemoryBridge error: %s - %s", type(mem_err).__name__, mem_err)
                errors.append(f"MemoryBridge unexpected error: {type(mem_err).__name__}")

        return memory_stats

    def classify_mce(
        self,
        scratchpad_summary: str,
        task: str,
        memory_stats: dict[str, Any] | None,
        errors: list[str],
    ) -> dict[str, Any] | None:
        """Classify memory via MCE adapter. Returns updated memory_stats."""
        # [MCE 集成点 v3.2] Dispatcher → MemoryBridge 调用链
        if self.mce_adapter and self.mce_adapter.is_available and scratchpad_summary:
            try:
                mce_classify_result = self.mce_adapter.classify(
                    scratchpad_summary, context={"task": task}, timeout_ms=500
                )
                if mce_classify_result:
                    memory_stats = memory_stats or {}
                    memory_stats["mce_classification"] = {
                        "type": mce_classify_result.memory_type,
                        "confidence": round(mce_classify_result.confidence, 3),
                        "tier": mce_classify_result.tier,
                    }
            except (ValueError, TypeError, AttributeError) as mce_type_err:
                logger.debug("MCE classification data error: %s", mce_type_err)
                errors.append(f"MCE classify data error: {mce_type_err}")
            except (TimeoutError, ConnectionError) as mce_timeout:
                logger.warning("MCE classify timeout/connection error: %s", mce_timeout)
                errors.append(f"MCE classify timeout error: {mce_timeout}")
            except (OSError, RuntimeError) as mce_err:  # Broad catch: unpredictable MCE system
                logger.warning("Unexpected MCE classify error: %s - %s", type(mce_err).__name__, mce_err)
                errors.append(f"MCE classify unexpected error: {type(mce_err).__name__}")

        return memory_stats

    def inject_ai_news(
        self,
        task: str,
        errors: list[str],
    ) -> None:
        """Inject AI news into scratchpad when task matches AI-related keywords."""
        if self.memory_bridge and self.enable_memory:
            try:
                ai_news_keywords = [
                    "ai news",
                    "industry trend",
                    "latest progress",
                    "trend",
                    "ai coding",
                    "embodied intelligence",
                    "large model",
                    "llm",
                    "cursor",
                    "claude",
                    "gpt",
                    "deepseek",
                    "anthropic",
                    "\u65b0\u95fb",
                    "\u884c\u4e1a\u52a8\u6001",
                    "\u6700\u65b0\u8fdb\u5c55",
                ]
                task_lower = task.lower()
                should_inject = any(kw in task_lower for kw in ai_news_keywords)
                if should_inject:
                    news_items = self.memory_bridge.get_workbuddy_ai_news(days=3)
                    if news_items:
                        news_summary = "\n".join(f"- [{n.title}] {n.content[:200]}..." for n in news_items[:3])
                        self.scratchpad.write(
                            ScratchpadEntry(
                                worker_id="system",
                                entry_type=EntryType.FINDING,
                                content=f"[WorkBuddy AI News Feed]\n{news_summary}",
                                confidence=0.95,
                                tags=["ai-news", "auto-injected"],
                            )
                        )
            except (AttributeError, OSError, KeyError, ValueError) as inject_err:
                errors.append(f"AI news inject error: {inject_err}")


class SkillProposalService:
    """Skill proposal generation from analyzed patterns."""

    def __init__(
        self,
        skillifier: Any = None,
        enable_skillify: bool = False,
        skill_registry: Any = None,
    ) -> None:
        self.skillifier = skillifier
        self.enable_skillify = enable_skillify
        self.skill_registry = skill_registry

    def propose_from_patterns(self, patterns: list) -> list[dict[str, Any]]:
        """Generate skill proposals from analyzed patterns and register them."""
        proposals = []
        for pattern in patterns:
            if pattern.confidence <= 0.3:
                continue
            pattern_title = getattr(pattern, 'title', None) or "新协作模式"
            category = pattern.category.value if hasattr(pattern, "category") and pattern.category else "general"
            proposals.append({"title": pattern_title, "confidence": pattern.confidence, "category": category})
            try:
                self.skill_registry.propose_from_result(
                    name=pattern_title, description=pattern_title,
                    category=category, confidence=pattern.confidence,
                )
            except (ValueError, AttributeError, OSError, KeyError) as e:
                logger.warning("SkillRegistry proposal failed: %s", e)
        return proposals
