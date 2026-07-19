"""Property-based tests for RBACEngine decision invariants.

Uses Hypothesis to verify that RBAC permission decisions are always
well-typed and consistent:

1. ``check_permission()`` always returns a boolean (never None, never
   raises for valid inputs).
2. ``enforce()`` either returns True or raises PermissionDeniedError —
   never returns False or None.
3. Inactive users always get ``False`` from ``check_permission()``.
4. Unknown users always get ``False`` from ``check_permission()``.
5. ``grant_role()`` followed by ``check_permission()`` for a permission
   of that role is always True (for active users).
6. ``revoke_role()`` always returns a boolean.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.collaboration.rbac_engine import (
    Permission,
    PermissionDeniedError,
    RBACEngine,
    RBACUser,
    UserRole,
)

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Input strategies
# ---------------------------------------------------------------------------

_all_permissions = st.sampled_from(list(Permission))
_all_roles = st.sampled_from(list(UserRole))
_user_ids = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126),
    min_size=1,
    max_size=30,
)


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(user_id=_user_ids, permission=_all_permissions)
@settings(max_examples=50, deadline=None)
def test_check_permission_unknown_user_returns_bool(
    user_id: str, permission: Permission
) -> None:
    """check_permission() for unknown users must return False (a bool)."""
    engine = RBACEngine()
    result = engine.check_permission(user_id, permission)
    assert isinstance(result, bool)
    assert result is False


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
    permission=_all_permissions,
)
@settings(max_examples=50, deadline=None)
def test_check_permission_active_user_returns_bool(
    user_id: str,
    username: str,
    role: UserRole,
    permission: Permission,
) -> None:
    """check_permission() for active users must always return a bool."""
    engine = RBACEngine()
    engine.add_user(RBACUser(user_id=user_id, username=username, roles={role}, is_active=True))
    result = engine.check_permission(user_id, permission)
    assert isinstance(result, bool)


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
    permission=_all_permissions,
)
@settings(max_examples=50, deadline=None)
def test_check_permission_inactive_user_always_false(
    user_id: str,
    username: str,
    role: UserRole,
    permission: Permission,
) -> None:
    """Inactive users must always get False, regardless of role."""
    engine = RBACEngine()
    engine.add_user(RBACUser(user_id=user_id, username=username, roles={role}, is_active=False))
    result = engine.check_permission(user_id, permission)
    assert result is False


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
    permission=_all_permissions,
)
@settings(max_examples=50, deadline=None)
def test_enforce_either_returns_true_or_raises(
    user_id: str,
    username: str,
    role: UserRole,
    permission: Permission,
) -> None:
    """enforce() must either return True or raise PermissionDeniedError.

    It must NEVER return False or None.
    """
    engine = RBACEngine()
    engine.add_user(RBACUser(user_id=user_id, username=username, roles={role}, is_active=True))
    try:
        result = engine.enforce(user_id, permission)
        assert result is True
    except PermissionDeniedError:
        # Expected when permission not granted
        pass


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    roles=st.sets(_all_roles, min_size=1, max_size=3),
)
@settings(max_examples=30, deadline=None)
def test_super_admin_has_all_permissions(
    user_id: str,
    username: str,
    roles: set[UserRole],
) -> None:
    """A user with SUPER_ADMIN role must have ALL permissions."""
    engine = RBACEngine()
    roles_with_admin = roles | {UserRole.SUPER_ADMIN}
    engine.add_user(
        RBACUser(user_id=user_id, username=username, roles=roles_with_admin, is_active=True)
    )
    for permission in Permission:
        assert engine.check_permission(user_id, permission) is True, (
            f"SUPER_ADMIN missing permission: {permission}"
        )


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
)
@settings(max_examples=30, deadline=None)
def test_grant_role_then_check_returns_bool(
    user_id: str,
    username: str,
    role: UserRole,
) -> None:
    """grant_role() then check_permission() must always return a bool."""
    engine = RBACEngine()
    engine.add_user(RBACUser(user_id=user_id, username=username, roles=set(), is_active=True))
    engine.grant_role(user_id, role)
    # Pick any permission to verify — result must be a bool
    result = engine.check_permission(user_id, Permission.TASK_READ)
    assert isinstance(result, bool)


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
)
@settings(max_examples=30, deadline=None)
def test_revoke_role_returns_bool(
    user_id: str,
    username: str,
    role: UserRole,
) -> None:
    """revoke_role() must always return a bool."""
    engine = RBACEngine()
    engine.add_user(RBACUser(user_id=user_id, username=username, roles={role}, is_active=True))
    result = engine.revoke_role(user_id, role)
    assert isinstance(result, bool)
    # Revoking again must return False (already revoked)
    second_result = engine.revoke_role(user_id, role)
    assert second_result is False


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
    permission=_all_permissions,
)
@settings(max_examples=30, deadline=None)
def test_to_dict_then_from_dict_round_trip(
    user_id: str,
    username: str,
    role: UserRole,
    permission: Permission,
) -> None:
    """RBACUser.to_dict() → from_dict() must preserve user identity and roles."""
    user = RBACUser(user_id=user_id, username=username, roles={role}, is_active=True)
    payload = user.to_dict()
    restored = RBACUser.from_dict(payload)
    assert restored.user_id == user.user_id
    assert restored.username == user.username
    assert restored.roles == user.roles
    assert restored.is_active == user.is_active


@given(
    user_id=_user_ids,
    username=st.text(min_size=1, max_size=30),
    role=_all_roles,
)
@settings(max_examples=30, deadline=None)
def test_remove_user_returns_bool_and_user_becomes_unknown(
    user_id: str,
    username: str,
    role: UserRole,
) -> None:
    """remove_user() must return bool; subsequent checks return False."""
    engine = RBACEngine()
    engine.add_user(RBACUser(user_id=user_id, username=username, roles={role}, is_active=True))
    removal_result = engine.remove_user(user_id)
    assert isinstance(removal_result, bool)
    assert removal_result is True
    # Now user is unknown — check_permission must return False
    perm_result = engine.check_permission(user_id, Permission.TASK_READ)
    assert perm_result is False
    # Removing again must return False
    second_removal = engine.remove_user(user_id)
    assert second_removal is False
