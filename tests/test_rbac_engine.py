"""Tests for RBACEngine - Role-Based Access Control System."""

import pytest

from scripts.collaboration.rbac_engine import (
    Permission,
    PermissionDeniedError,
    RBACEngine,
    RBACUser,
    UserRole,
)

pytestmark = pytest.mark.unit



class TestRBACEngine:
    def setup_method(self):
        self.engine = RBACEngine()
        self.engine.add_user(RBACUser("admin", "admin_user", {UserRole.SUPER_ADMIN}))
        self.engine.add_user(RBACUser("viewer", "viewer_user", {UserRole.VIEWER}))
        self.engine.add_user(RBACUser("operator", "op_user", {UserRole.OPERATOR}))

    def test_super_admin_has_all_permissions(self):
        for perm in Permission:
            assert self.engine.check_permission("admin", perm) is True

    def test_viewer_cannot_execute_tasks(self):
        assert self.engine.check_permission("viewer", Permission.TASK_EXECUTE) is False

    def test_viewer_can_only_read_tasks(self):
        assert self.engine.check_permission("viewer", Permission.TASK_READ) is True
        assert self.engine.check_permission("viewer", Permission.TASK_CREATE) is False
        assert self.engine.check_permission("viewer", Permission.TASK_UPDATE) is False
        assert self.engine.check_permission("viewer", Permission.TASK_DELETE) is False

    def test_operator_has_task_and_config_read_permissions(self):
        assert self.engine.check_permission("operator", Permission.TASK_EXECUTE) is True
        assert self.engine.check_permission("operator", Permission.TASK_CREATE) is True
        assert self.engine.check_permission("operator", Permission.CONFIG_READ) is True
        assert self.engine.check_permission("operator", Permission.CONFIG_UPDATE) is False
        assert self.engine.check_permission("operator", Permission.USER_CREATE) is False

    def test_enforce_raises_on_denied(self):
        with pytest.raises(PermissionDeniedError):
            self.engine.enforce("viewer", Permission.TASK_EXECUTE)

    def test_enforce_passes_on_allowed(self):
        result = self.engine.enforce("admin", Permission.TASK_EXECUTE)
        assert result is True

    def test_enforce_error_contains_details(self):
        with pytest.raises(PermissionDeniedError) as exc_info:
            self.engine.enforce("viewer", Permission.TASK_EXECUTE)
        assert exc_info.value.user_id == "viewer"
        assert exc_info.value.permission == Permission.TASK_EXECUTE

    def test_map_legacy_level(self):
        assert RBACEngine.map_legacy_level("bypass") == UserRole.SUPER_ADMIN
        assert RBACEngine.map_legacy_level("auto") == UserRole.ADMIN
        assert RBACEngine.map_legacy_level("default") == UserRole.OPERATOR
        assert RBACEngine.map_legacy_level("plan") == UserRole.VIEWER

    def test_map_legacy_level_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown legacy level"):
            RBACEngine.map_legacy_level("full")

    def test_unknown_user_denied(self):
        assert self.engine.check_permission("nonexistent", Permission.TASK_EXECUTE) is False

    def test_inactive_user_denied(self):
        inactive = RBACUser("inactive", "inactive_user", {UserRole.SUPER_ADMIN}, is_active=False)
        self.engine.add_user(inactive)
        assert self.engine.check_permission("inactive", Permission.TASK_READ) is False

    def test_add_user_with_empty_id_raises(self):
        with pytest.raises(ValueError, match="user_id cannot be empty"):
            self.engine.add_user(RBACUser("", "empty", {UserRole.VIEWER}))

    def test_remove_user(self):
        assert self.engine.remove_user("viewer") is True
        assert self.engine.get_user("viewer") is None
        assert self.engine.remove_user("nonexistent") is False

    def test_get_user(self):
        user = self.engine.get_user("admin")
        assert user is not None
        assert user.username == "admin_user"
        assert UserRole.SUPER_ADMIN in user.roles

    def test_list_users(self):
        users = self.engine.list_users(active_only=True)
        assert len(users) == 3
        assert all(u.is_active for u in users)

    def test_list_users_includes_inactive(self):
        self.engine.add_user(RBACUser("inactive", "inactive_user", {UserRole.VIEWER}, is_active=False))
        active = self.engine.list_users(active_only=True)
        all_users = self.engine.list_users(active_only=False)
        assert len(all_users) == len(active) + 1

    def test_grant_role(self):
        self.engine.grant_role("viewer", UserRole.OPERATOR)
        roles = self.engine.get_user_roles("viewer")
        assert UserRole.OPERATOR in roles
        assert UserRole.VIEWER in roles

    def test_grant_role_unknown_user_raises(self):
        with pytest.raises(KeyError, match="not found"):
            self.engine.grant_role("nonexistent", UserRole.OPERATOR)

    def test_revoke_role(self):
        result = self.engine.revoke_role("operator", UserRole.OPERATOR)
        assert result is True
        roles = self.engine.get_user_roles("operator")
        assert UserRole.OPERATOR not in roles

    def test_revoke_role_not_held(self):
        result = self.engine.revoke_role("viewer", UserRole.SUPER_ADMIN)
        assert result is False

    def test_get_user_roles_unknown_returns_empty(self):
        roles = self.engine.get_user_roles("nonexistent")
        assert roles == set()

    def test_get_role_permissions(self):
        perms = self.engine.get_role_permissions(UserRole.SUPER_ADMIN)
        assert len(perms) == len(Permission)

        viewer_perms = self.engine.get_role_permissions(UserRole.VIEWER)
        assert Permission.TASK_READ in viewer_perms
        assert Permission.TASK_EXECUTE not in viewer_perms

    def test_add_permission_to_role(self):
        self.engine.add_permission_to_role(UserRole.VIEWER, Permission.AUDIT_READ)
        perms = self.engine.get_role_permissions(UserRole.VIEWER)
        assert Permission.AUDIT_READ in perms

    def test_remove_permission_from_role(self):
        result = self.engine.remove_permission_from_role(UserRole.OPERATOR, Permission.TASK_EXECUTE)
        assert result is True
        perms = self.engine.get_role_permissions(UserRole.OPERATOR)
        assert Permission.TASK_EXECUTE not in perms

    def test_remove_permission_not_present(self):
        result = self.engine.remove_permission_from_role(UserRole.VIEWER, Permission.TASK_EXECUTE)
        assert result is False

    def test_audit_log_records_permission_checks(self):
        self.engine.check_permission("admin", Permission.TASK_EXECUTE)
        log = self.engine.get_audit_log()
        assert len(log) > 0
        # Find the permission check record
        perm_checks = [r for r in log if r.action == "permission:check"]
        assert len(perm_checks) > 0
        last_check = perm_checks[-1]
        assert last_check.user_id == "admin"
        assert last_check.resource_id == Permission.TASK_EXECUTE.value

    def test_verify_audit_integrity(self):
        self.engine.enforce("admin", Permission.TASK_EXECUTE)
        result = self.engine.verify_audit_integrity()
        assert result["valid"] is True
        assert result["total_records"] > 0

    def test_verify_audit_integrity_empty(self):
        engine = RBACEngine()
        result = engine.verify_audit_integrity()
        assert result["valid"] is True
        assert result["total_records"] == 0

    def test_clear_audit_log(self):
        self.engine.check_permission("admin", Permission.TASK_READ)
        self.engine.clear_audit_log()
        log = self.engine.get_audit_log()
        assert len(log) == 0

    def test_get_stats(self):
        stats = self.engine.get_stats()
        assert stats["total_users"] == 3
        assert stats["active_users"] == 3
        assert stats["inactive_users"] == 0
        assert stats["total_permissions"] == len(Permission)
        assert stats["total_roles"] == len(UserRole)

    def test_multi_role_user(self):
        multi = RBACUser("multi", "multi_user", {UserRole.VIEWER, UserRole.OPERATOR})
        self.engine.add_user(multi)
        assert self.engine.check_permission("multi", Permission.TASK_EXECUTE) is True
        assert self.engine.check_permission("multi", Permission.TASK_READ) is True

    def test_rbac_user_serialization(self):
        user = RBACUser("u1", "Test User", {UserRole.ADMIN}, {"dept": "eng"})
        d = user.to_dict()
        assert d["user_id"] == "u1"
        assert d["username"] == "Test User"
        assert "admin" in d["roles"]
        assert d["attributes"]["dept"] == "eng"

        restored = RBACUser.from_dict(d)
        assert restored.user_id == "u1"
        assert UserRole.ADMIN in restored.roles
