"""Permission, memory, and skill post-dispatch step mixins."""

import logging
from typing import Any

from .dispatch_steps_base import PostDispatchBase

logger = logging.getLogger(__name__)


class PostDispatchServicesMixin(PostDispatchBase):
    """Provides permission checks, memory pipeline, and skill learning."""

    def _check_permissions(
        self, _task: str, _worker_results: list[dict[str, Any]], _consensus_records: list[dict[str, Any]], **kwargs: Any
    ) -> list[dict[str, Any]]:
        """Check permissions via PermissionGuard and RBAC.

        Returns:
            List of permission check results.
        """
        permission_checks: list[dict[str, Any]] = []
        if self.enable_permission and self.permission_service.permission_guard:
            permission_checks = self.permission_service.check_permissions(permission_checks)

        # RBAC fine-grained check
        if self.enterprise.enable_rbac and self.enterprise.rbac_engine:
            permission_checks = self.permission_service.check_rbac(permission_checks, **kwargs)

        return permission_checks

    def _process_memory_pipeline(
        self,
        task: str,
        _worker_results: list[dict[str, Any]],
        _lang: str,
        scratchpad_summary: str,
        role_ids: list[str],
    ) -> tuple[dict[str, Any] | None, list[str]]:
        """Process memory pipeline: capture + MCE classify + AI news inject."""
        errors: list[str] = []

        memory_stats = self.memory_pipeline.capture(task, scratchpad_summary, role_ids, errors)
        memory_stats = self.memory_pipeline.classify_mce(scratchpad_summary, task, memory_stats, errors)
        self.memory_pipeline.inject_ai_news(task, errors)

        return memory_stats, errors

    def _learn_skills(
        self,
        _task: str,
        _worker_results: list[dict[str, Any]],
        _matched_roles: list[dict[str, Any]],
        exec_result: Any,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Learn skills via Skillifier. Returns (skill_proposals, errors)."""
        errors: list[str] = []
        skill_proposals: list[dict[str, Any]] = []
        patterns = None

        if self.skill_service.enable_skillify and self.skill_service.skillifier and exec_result.success:
            try:
                patterns = self.skill_service.skillifier.analyze_history()
                if patterns:
                    skill_proposals = self.skill_service.propose_from_patterns(patterns)
            except (ValueError, AttributeError, RuntimeError, ImportError) as skill_err:
                errors.append(f"Skillifier error: {skill_err}")

        return skill_proposals, errors
