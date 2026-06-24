#!/usr/bin/env python3
"""
DispatchRBAC — RBAC integration for dispatch pipeline.

Integrates the existing AuthManager (V3.6.5 preview) into the dispatch pipeline.
Uses RBAC0 model: user → role → permission (adopted from Security review S2).

The checker integrates with :class:`scripts.auth.AuthManager` by reading its
``credentials`` dict (username → ``{"role": "admin"|"operator"|"viewer", ...}``).
If no AuthManager is provided, all operations are allowed (open mode).

Permission Matrix (default)
---------------------------
+----------+-----------------------------------+--------------------------------+
| Role     | Allowed dispatch roles            | Allowed modes                  |
+==========+===================================+================================+
| admin    | all 7 roles                       | auto, parallel, sequential,    |
|          |                                   | consensus                      |
+----------+-----------------------------------+--------------------------------+
| operator | all except security               | auto, parallel, sequential     |
+----------+-----------------------------------+--------------------------------+
| viewer   | architect, product-manager,       | auto                           |
|          | ui-designer (read-only)           |                                |
+----------+-----------------------------------+--------------------------------+

Usage::

    from scripts.collaboration.dispatch_rbac import DispatchRBAC

    # Open mode (no AuthManager) — all operations allowed
    rbac = DispatchRBAC()
    result = rbac.check_dispatch_permission("u1", ["architect"], "auto")
    assert result.allowed

    # Integrated mode (with AuthManager)
    from scripts.auth import AuthManager
    auth = AuthManager(config_path="config/deployment.yaml")
    rbac = DispatchRBAC(auth_manager=auth)
    result = rbac.check_dispatch_permission("admin", ["coder"], "parallel")
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

__all__ = ["DispatchRBAC", "PermissionResult"]

logger = logging.getLogger(__name__)


@dataclass
class PermissionResult:
    """Result of a dispatch permission check.

    Attributes
    ----------
    allowed:
        True if the dispatch is permitted, False otherwise.
    reason:
        Human-readable explanation of the decision.
    user_id:
        The user ID that was checked.
    requested_roles:
        The dispatch roles requested.
    requested_mode:
        The dispatch mode requested.
    """

    allowed: bool
    reason: str
    user_id: str
    requested_roles: list[str]
    requested_mode: str


class DispatchRBAC:
    """RBAC checker for dispatch operations.

    Integrates with :class:`scripts.auth.AuthManager` (V3.6.5 preview) to
    enforce role-based access control on dispatch operations. Uses the
    RBAC0 model: user → role → permission.

    When ``auth_manager`` is None, all operations are allowed (open mode).
    When ``auth_manager`` is provided, the user must exist in the
    AuthManager's credentials dict and have a role that permits the
    requested dispatch roles and mode.
    """

    # All valid dispatch roles (from SKILL.md role system).
    ALL_DISPATCH_ROLES: set[str] = {
        "architect",
        "product-manager",
        "security",
        "tester",
        "solo-coder",
        "devops",
        "ui-designer",
    }

    # All valid dispatch modes (from SKILL.md dispatch mode table).
    ALL_DISPATCH_MODES: set[str] = {"auto", "parallel", "sequential", "consensus"}

    # Mapping from CLI short IDs to full role IDs (from SKILL.md).
    ROLE_ALIASES: dict[str, str] = {
        "arch": "architect",
        "pm": "product-manager",
        "sec": "security",
        "test": "tester",
        "coder": "solo-coder",
        "infra": "devops",
        "ui": "ui-designer",
    }

    # Default permission matrix: role → (allowed_roles, allowed_modes).
    # admin: all roles, all modes.
    # operator: all except security (security review needs admin), no consensus.
    # viewer: read-only roles only, auto mode only.
    DEFAULT_PERMISSIONS: dict[str, tuple[set[str], set[str]]] = {
        "admin": (
            ALL_DISPATCH_ROLES,
            ALL_DISPATCH_MODES,
        ),
        "operator": (
            ALL_DISPATCH_ROLES - {"security"},
            {"auto", "parallel", "sequential"},
        ),
        "viewer": (
            {"architect", "product-manager", "ui-designer"},
            {"auto"},
        ),
    }

    def __init__(self, auth_manager: Any | None = None) -> None:
        """Initialize with optional AuthManager.

        Parameters
        ----------
        auth_manager:
            An AuthManager instance (or any object with a ``credentials``
            dict attribute mapping usernames to ``{"role": str, ...}``).
            If None, all operations are allowed (open mode).
        """
        self._auth = auth_manager

    def check_dispatch_permission(
        self,
        user_id: str,
        roles: list[str],
        mode: str,
    ) -> PermissionResult:
        """Check if user can dispatch with given roles/mode.

        Parameters
        ----------
        user_id:
            The user ID to check (must exist in AuthManager.credentials).
        roles:
            List of dispatch role IDs requested (e.g. ``["architect", "coder"]``).
        mode:
            Dispatch mode (one of auto/parallel/sequential/consensus).

        Returns
        -------
        PermissionResult
            The decision with reason. If ``auth_manager`` is None,
            always returns ``allowed=True``.
        """
        # Open mode: no AuthManager configured → allow all.
        if self._auth is None:
            logger.warning(
                "DispatchRBAC running in OPEN mode (no AuthManager configured) "
                "— all operations allowed"
            )
            return PermissionResult(
                allowed=True,
                reason="No RBAC configured (open mode)",
                user_id=user_id,
                requested_roles=list(roles),
                requested_mode=mode,
            )

        # 1. Check user exists in AuthManager.
        user_role = self._lookup_user_role(user_id)
        if user_role is None:
            return PermissionResult(
                allowed=False,
                reason=f"User '{user_id}' not found in AuthManager",
                user_id=user_id,
                requested_roles=list(roles),
                requested_mode=mode,
            )

        # 2. Check user's role is recognized.
        permissions = self.DEFAULT_PERMISSIONS.get(user_role)
        if permissions is None:
            return PermissionResult(
                allowed=False,
                reason=f"User '{user_id}' has unrecognized role '{user_role}'",
                user_id=user_id,
                requested_roles=list(roles),
                requested_mode=mode,
            )

        allowed_roles, allowed_modes = permissions

        # 3. Check each requested role is permitted (normalize short IDs first).
        for role in roles:
            normalized_role = self.ROLE_ALIASES.get(role, role)
            if normalized_role not in allowed_roles:
                return PermissionResult(
                    allowed=False,
                    reason=(
                        f"User '{user_id}' (role={user_role}) is not permitted "
                        f"to dispatch with role '{role}'"
                    ),
                    user_id=user_id,
                    requested_roles=list(roles),
                    requested_mode=mode,
                )

        # 4. Check mode is permitted.
        if mode not in allowed_modes:
            return PermissionResult(
                allowed=False,
                reason=(
                    f"User '{user_id}' (role={user_role}) is not permitted "
                    f"to use dispatch mode '{mode}'"
                ),
                user_id=user_id,
                requested_roles=list(roles),
                requested_mode=mode,
            )

        # 5. All checks passed.
        return PermissionResult(
            allowed=True,
            reason=f"User '{user_id}' (role={user_role}) permitted",
            user_id=user_id,
            requested_roles=list(roles),
            requested_mode=mode,
        )

    def _lookup_user_role(self, user_id: str) -> str | None:
        """Look up a user's role from the AuthManager.

        Parameters
        ----------
        user_id:
            The username to look up.

        Returns
        -------
        str | None
            The user's role string (e.g. "admin", "operator", "viewer"),
            or None if the user is not found.
        """
        credentials = getattr(self._auth, "credentials", None)
        if not credentials or not isinstance(credentials, dict):
            return None
        cred = credentials.get(user_id)
        if not cred or not isinstance(cred, dict):
            return None
        role = cred.get("role")
        if isinstance(role, str):
            return role
        # Handle enum roles (e.g. UserRole.ADMIN).
        if hasattr(role, "value"):
            assert role is not None
            return str(role.value)
        return None
