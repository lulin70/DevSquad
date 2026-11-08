"""RBAC gate mixin for ``MultiAgentDispatcher``.

Resolves the pre-dispatch permission decision, including the fail-closed
paths used when RBAC is unconfigured or the provider itself errors.
"""

from __future__ import annotations

import logging
from typing import Any

from .dispatch_models import DispatchResult
from .dispatcher_base import DispatcherBase

logger = logging.getLogger(__name__)


class DispatcherRBACMixin(DispatcherBase):
    """RBAC permission checks and their denial-result builders."""

    _rbac: Any
    _rbac_fail_closed: bool

    def _check_rbac_permission(
        self,
        user_id: str,
        roles: list[str] | None,
        mode: str,
        task_description: str,
    ) -> tuple[dict[str, Any] | None, DispatchResult | None]:
        """V3.9-02: Run RBAC permission check before dispatch work begins.

        Returns ``(permission_result_dict, denied_result)``. When
        ``denied_result`` is not None the caller must return it immediately.
        When ``denied_result`` is None, ``permission_result_dict`` may carry
        the allowed-permission metadata to attach to the final result.
        """
        if self._rbac is not None:
            return self._check_rbac_with_provider(user_id, roles, mode, task_description)
        # HC-1: When no RBAC is configured, consult rbac_fail_closed flag.
        # In production (development_mode=False), deny all operations to
        # satisfy hard constraint "禁止 fail-open 直接执行".
        # In dev/test mode (development_mode=True), allow for backward compat.
        if self._rbac_fail_closed and not self.development_mode:
            return self._deny_no_rbac_configured(user_id, roles, mode, task_description)
        return None, None

    def _check_rbac_with_provider(
        self,
        user_id: str,
        roles: list[str] | None,
        mode: str,
        task_description: str,
    ) -> tuple[dict[str, Any] | None, DispatchResult | None]:
        """RBAC check path when an RBAC provider is configured."""
        if self._rbac is None:
            return None, None
        try:
            check_roles = list(roles) if roles else []
            perm = self._rbac.check_dispatch_permission(
                user_id=user_id,
                roles=check_roles,
                mode=mode,
            )
            permission_result_dict = {
                "allowed": perm.allowed,
                "reason": perm.reason,
                "user_id": perm.user_id,
                "requested_roles": perm.requested_roles,
                "requested_mode": perm.requested_mode,
            }
            if not perm.allowed:
                self._log_audit_permission_denied(user_id, perm.reason)
                self.metrics_service.safe_record(
                    lambda m: (m.dispatch_counter.labels(mode=mode, role_count="0").inc(),)
                )
                denied_result = DispatchResult(
                    success=False,
                    task_description=task_description,
                    errors=[f"Permission denied: {perm.reason}"],
                    permission_result=permission_result_dict,
                )
                self._attach_audit_entries(denied_result)
                return permission_result_dict, denied_result
            return permission_result_dict, None
        except (ValueError, AttributeError, TypeError, RuntimeError) as rbac_err:
            logger.warning("RBAC check failed: %s", rbac_err)
            if self._rbac_fail_closed:
                return self._deny_rbac_infra_error(user_id, task_description, rbac_err)
            return None, None

    def _deny_rbac_infra_error(
        self,
        user_id: str,
        task_description: str,
        rbac_err: Exception,
    ) -> tuple[dict[str, Any], DispatchResult]:
        """Build the fail-closed denial result when RBAC itself errors."""
        self._log_audit_permission_denied(user_id, f"RBAC infrastructure error: {rbac_err}")
        permission_result_dict = {
            "allowed": False,
            "reason": str(rbac_err),
            "user_id": user_id,
        }
        denied_result = DispatchResult(
            success=False,
            task_description=task_description,
            errors=[f"RBAC check failed (fail-closed): {rbac_err}"],
            permission_result=permission_result_dict,
        )
        self._attach_audit_entries(denied_result)
        return permission_result_dict, denied_result

    def _deny_no_rbac_configured(
        self,
        user_id: str,
        roles: list[str] | None,
        mode: str,
        task_description: str,
    ) -> tuple[dict[str, Any], DispatchResult]:
        """Build the denial result when no RBAC is configured in production."""
        logger.warning("Dispatch denied: no RBAC configured (fail-closed mode, user=%s, production mode)")
        permission_result_dict = {
            "allowed": False,
            "reason": "No RBAC configured (fail-closed mode denies all)",
            "user_id": user_id,
            "requested_roles": list(roles) if roles else [],
            "requested_mode": mode,
        }
        self._log_audit_permission_denied(user_id, "No RBAC configured (fail-closed mode denies all)")
        denied_result = DispatchResult(
            success=False,
            task_description=task_description,
            errors=["Permission denied: No RBAC configured (fail-closed mode)"],
            permission_result=permission_result_dict,
        )
        self._attach_audit_entries(denied_result)
        return permission_result_dict, denied_result

    def _log_audit_permission_denied(self, user_id: str, reason: str) -> None:
        """Best-effort audit log for permission-denied events."""
        if self._audit_logger is None:
            return
        try:
            self._audit_logger.log_permission_denied(
                user_id=user_id,
                reason=reason,
            )
        except (ValueError, RuntimeError, OSError) as audit_err:
            logger.warning("Audit log_permission_denied failed: %s", audit_err)
