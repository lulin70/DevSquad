#!/usr/bin/env python3
"""EnterpriseFeature — RBAC, Audit, Multi-Tenant, Data Masking features.

Converted from EnterpriseMixin (Mixin pattern) to Composition pattern.
This class is now a standalone component instantiated by the dispatcher
and accessed via `self.enterprise.*` instead of mixin inheritance.
"""

import logging
import os
from datetime import datetime
from typing import Any, cast

logger = logging.getLogger(__name__)


class EnterpriseFeature:
    """Composition-based enterprise features for MultiAgentDispatcher.

    Methods
    -------
    check_rbac_access(kwargs, task, lang, start_time)
        Pre-dispatch RBAC access check; returns DispatchResult if denied.
    apply_data_masking(text)
        Mask sensitive data in text output.
    set_tenant_context(kwargs, start_time)
        Set up multi-tenant context; returns context manager or DispatchResult.
    clear_tenant_context(tenant_ctx)
        Clean up tenant context after dispatch.
    audit_dispatch_start(task_description, **kwargs)
        Log audit event at dispatch start.
    audit_dispatch_complete(result, **kwargs)
        Log audit event at dispatch completion.
    audit_quality(module_path, test_path, **kwargs)
        Execute test quality audit (public API).
    export_performance_metrics(output_file, **kwargs)
        Export performance metrics to file (public API).
    clear_performance_history(**kwargs)
        Clear performance history (public API).
    """

    def __init__(
        self,
        persist_dir: str,
        quality_guard: Any = None,
        perf_monitor: Any = None,
        config: dict | None = None,
    ) -> None:
        """Initialize enterprise features: RBAC, Audit, Multi-Tenant.

        Args:
            persist_dir: Directory for persistent storage.
            quality_guard: Optional TestQualityGuard instance.
            perf_monitor: Optional PerformanceMonitor instance.
            config: Optional dict with enable flags (enable_rbac, enable_audit,
                    enable_data_masking, enable_multi_tenant).
        """
        config = config or {}
        self.persist_dir = persist_dir
        self.quality_guard = quality_guard
        self._perf_monitor = perf_monitor

        self.enable_rbac = config.get("enable_rbac", True)
        self.enable_audit = config.get("enable_audit", True)
        self.enable_data_masking = config.get("enable_data_masking", True)
        self.enable_multi_tenant = config.get("enable_multi_tenant", True)

        self.rbac_engine = None
        self.audit_logger = None
        self.data_masker = None
        self.tenant_manager = None

        if self.enable_rbac:
            try:
                from .rbac_engine import RBACEngine, RBACUser, UserRole

                self.rbac_engine = RBACEngine()
                # Default user is OPERATOR (least privilege).
                # For production use, configure proper RBAC roles via RBACEngine.add_user().
                self.rbac_engine.add_user(RBACUser("default", "default_operator", {UserRole.OPERATOR}))
                logger.info("RBAC Engine enabled")
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning("RBAC Engine initialization failed: %s", e)

        if self.enable_audit:
            try:
                from .audit_logger import AuditLogger, SensitiveDataMasker

                audit_dir = os.path.join(self.persist_dir, "audit") if self.persist_dir else ".devsquad_data/audit"
                self.audit_logger = AuditLogger(log_dir=audit_dir)
                if self.enable_data_masking:
                    self.data_masker = SensitiveDataMasker()
                logger.info("Audit Logger enabled (data_masking=%s)", self.enable_data_masking)
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning("Audit Logger initialization failed: %s", e)

        if self.enable_multi_tenant:
            try:
                from .multi_tenant import MultiTenantManager, Tenant

                self.tenant_manager = MultiTenantManager()
                self.tenant_manager.create_tenant(Tenant(tenant_id="default", name="Default Tenant"))
                logger.info("Multi-Tenant Manager enabled")
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning("Multi-Tenant Manager initialization failed: %s", e)

    def check_rbac_access(self, kwargs: dict[str, Any], task: str, lang: str, start_time: float) -> Any | None:
        """Check RBAC access. Returns DispatchResult if denied, None if allowed."""
        if not self.enable_rbac or not self.rbac_engine:
            return None
        try:
            import time

            from .dispatch_models import DispatchResult
            from .rbac_engine import Permission, PermissionDeniedError

            user_id = kwargs.get("user_id", "default")
            self.rbac_engine.enforce(user_id, Permission.TASK_EXECUTE)
            return None
        except PermissionDeniedError as e:
            return DispatchResult(  # type: ignore[call-arg]
                success=False,
                task_description=task,
                error=f"Permission denied: {e}",
                matched_roles=[],
                summary=f"Permission denied: {e}",
                errors=[f"Permission denied: {e}"],
                duration_seconds=time.time() - start_time,
                lang=lang,
            )
        except (AttributeError, RuntimeError, KeyError) as e:
            logger.warning("RBAC check failed: %s", e)
            return None

    def apply_data_masking(self, text: str) -> str:
        """Apply data masking to text if masker is available."""
        if not self.data_masker or not text:
            return text
        try:
            masked = self.data_masker.mask({"content": text})
            return cast(str, masked.get("content", text))
        except (ValueError, AttributeError, TypeError, KeyError) as e:
            logger.debug("Data masking failed: %s", e)
            return text

    def set_tenant_context(self, kwargs: dict[str, Any], start_time: float) -> Any:
        """Set up multi-tenant context. Returns context manager or DispatchResult on quota error."""
        if not self.enable_multi_tenant or not self.tenant_manager:
            return None
        tenant_id = kwargs.get("tenant_id", "default")
        user_id = kwargs.get("user_id", "default")
        if not tenant_id:
            return None
        try:
            import time

            from .dispatch_models import DispatchResult

            tenant_ctx = self.tenant_manager.context(tenant_id, user_id)
            tenant_ctx.__enter__()
            if not self.tenant_manager.check_quota("tasks"):
                return DispatchResult(  # type: ignore[call-arg]
                    success=False,
                    task_description="",
                    error="Quota exceeded",
                    matched_roles=[],
                    summary="Quota exceeded for tenant",
                    errors=["Quota exceeded"],
                    duration_seconds=time.time() - start_time,
                )
            return tenant_ctx
        except (AttributeError, KeyError, RuntimeError, OSError) as e:
            logger.warning("Multi-tenant setup failed: %s", e)
            return None

    def clear_tenant_context(self, tenant_ctx: Any) -> None:
        """Clean up tenant context if active."""
        if tenant_ctx:
            try:
                tenant_ctx.__exit__(None, None, None)
            except (AttributeError, RuntimeError, OSError) as e:
                logger.debug("Tenant context cleanup failed: %s", e)

    def audit_dispatch_start(self, task_description: str, **kwargs: Any) -> None:
        """Audit log for dispatch start."""
        if not self.audit_logger:
            return
        try:
            self.audit_logger.log(
                user_id=kwargs.get("user_id", "system"),
                action="task:dispatch_start",
                resource_type="Task",
                resource_id="unknown",
                details={"task": task_description[:200]},
            )
        except (OSError, AttributeError, KeyError) as e:
            logger.debug("Audit logging failed: %s", e)

    def audit_dispatch_complete(self, result: Any, **kwargs: Any) -> None:
        """Audit log for dispatch completion."""
        if not self.audit_logger:
            return
        try:
            self.audit_logger.log(
                user_id=kwargs.get("user_id", "system"),
                action="task:dispatch_complete",
                resource_type="Task",
                resource_id="unknown",
                result="success" if result.success else "failure",
            )
        except (OSError, AttributeError, KeyError) as e:
            logger.debug("Audit logging failed: %s", e)

    def audit_quality(self, module_path: str | None = None, test_path: str | None = None, **kwargs: Any) -> Any:
        """Execute test quality audit (P1 integration)."""
        from .test_quality_guard import TestQualityGuard, TestQualityReport

        if self.rbac_engine:
            try:
                from .rbac_engine import Permission, PermissionDeniedError

                user_id = kwargs.get("user_id", "default")
                self.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return TestQualityReport(
                    module_name="rbac_denied",
                    test_file="",
                    source_file="",
                )

        if not self.quality_guard:
            self.quality_guard = TestQualityGuard("", "")

        if module_path and test_path:
            return self.quality_guard.__class__(module_path, test_path).audit()

        collab_dir = os.path.dirname(os.path.abspath(__file__))
        reports = self._audit_collab_modules(collab_dir)

        if len(reports) == 1:
            return reports[0]

        combined = TestQualityReport(
            module_name="project",
            test_file=f"{len(reports)} modules",
            source_file=collab_dir,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        )
        combined.total_tests = sum(r.total_tests for r in reports)
        combined.issues = [i for r in reports for i in r.issues]
        combined.test_functions = [tf for r in reports for tf in r.test_functions]
        if reports:
            scores = [r.score.overall for r in reports]
            combined.score.overall = sum(scores) / len(scores) if scores else 0
        combined.audit_time = sum(r.audit_time for r in reports)
        return combined

    def _audit_collab_modules(self, collab_dir: str) -> list:
        """Audit all collaboration modules that have matching test files."""
        reports = []
        for fname in os.listdir(collab_dir):
            if fname.endswith(".py") and not fname.startswith("_") and "test" not in fname:
                mod_name = fname.replace(".py", "")
                test_name = f"{mod_name}_test.py"
                mod_full = os.path.join(collab_dir, fname)
                test_full = os.path.join(collab_dir, test_name)
                if os.path.exists(test_full):
                    try:
                        r = self.quality_guard.__class__(mod_full, test_full).audit()
                        reports.append(r)
                    except (ValueError, AttributeError, OSError, ImportError) as e:
                        logger.warning("Quality guard audit failed for %s: %s", mod_name, e)
        return reports

    def export_performance_metrics(self, output_file: str, **kwargs: Any) -> None:
        """Export performance metrics to file."""
        if self.rbac_engine:
            try:
                from .rbac_engine import Permission, PermissionDeniedError

                user_id = kwargs.get("user_id", "default")
                self.rbac_engine.enforce(user_id, Permission.TASK_READ)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return
        self._perf_monitor.export_metrics(output_file, allowed_base_dir=self.persist_dir)

    def clear_performance_history(self, **kwargs: Any) -> None:
        """Clear performance history."""
        if self.rbac_engine:
            try:
                from .rbac_engine import Permission, PermissionDeniedError

                user_id = kwargs.get("user_id", "default")
                self.rbac_engine.enforce(user_id, Permission.TASK_EXECUTE)
            except PermissionDeniedError as e:
                logger.warning("RBAC denied: %s", e)
                return
        self._perf_monitor.clear()
        logger.info("Performance history cleared")
