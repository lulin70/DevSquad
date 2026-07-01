"""
E2E 测试：真实用户登录流程（含 legacy 密码迁移）

模拟真实用户使用 DevSquad 的认证流程，覆盖：
  1. PBKDF2-HMAC-SHA256 标准密码登录（成功路径）
  2. Legacy SHA-256 密码登录 + 自动迁移到 PBKDF2（迁移路径）
  3. 错误密码登录（失败路径）
  4. 未知用户登录（失败路径）
  5. 角色权限校验（admin/operator/viewer）
  6. 会话 ID 生成与唯一性

测试铁律：本测试不修改源代码；只验证现有行为。
"""

import hashlib
import sys
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from scripts.auth import AuthManager, UserRole  # noqa: E402


def _hash_password(password: str) -> str:
    """Generate a PBKDF2 hash using AuthManager's real implementation.

    Uses ``config_path=None`` (default config) only to access the hash method;
    the returned hash is independent of the config contents.
    """
    auth = AuthManager(config_path=None)
    return auth._hash_password(password)


def _write_config(config_path: Path, credentials: dict) -> None:
    """Write a deployment.yaml with the given credentials block.

    Matches the real config schema: ``authentication.credentials.usernames``.
    """
    config = {
        "authentication": {
            "enabled": True,
            "session_secret": "e2e-test-session-secret-not-for-prod",
            "cookie": {"secure": False, "httponly": True, "samesite": "Lax"},
            "credentials": {"usernames": credentials},
        }
    }
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, allow_unicode=True)


@pytest.fixture
def temp_config(tmp_path):
    """Provide a temp deployment.yaml path."""
    return tmp_path / "deployment.yaml"


class TestRealUserLoginFlow:
    """模拟真实用户登录流程的 E2E 测试套件。"""

    def test_pbkdf2_password_login_success(self, temp_config):
        """场景 1：用户使用 PBKDF2 哈希密码登录，应成功。"""
        pbkdf2_hash = _hash_password("CorrectPass123!")
        _write_config(
            temp_config,
            {
                "alice": {
                    "password": pbkdf2_hash,
                    "role": "admin",
                    "email": "alice@example.com",
                    "name": "Alice Admin",
                }
            },
        )

        am = AuthManager(config_path=str(temp_config))
        user = am.verify_credentials("alice", "CorrectPass123!")

        assert user is not None, "登录应成功"
        assert user.username == "alice"
        assert user.role == UserRole.ADMIN
        assert user.email == "alice@example.com"
        assert user.session_id and len(user.session_id) >= 32, "session_id 必须为至少 32 字符的 hex"

    def test_legacy_sha256_password_auto_migration(self, temp_config):
        """场景 2：legacy SHA-256 密码登录成功后应自动迁移到 PBKDF2。"""
        legacy_hash = hashlib.sha256(b"LegacyPass456#").hexdigest()
        _write_config(
            temp_config,
            {
                "bob": {
                    "password": legacy_hash,
                    "role": "operator",
                    "email": "bob@example.com",
                    "name": "Bob Operator",
                }
            },
        )

        am = AuthManager(config_path=str(temp_config))
        assert am._needs_password_upgrade(legacy_hash), "应识别为 legacy hash"

        user = am.verify_credentials("bob", "LegacyPass456#")

        assert user is not None, "Legacy 密码登录应成功"
        assert user.role == UserRole.OPERATOR

        # 密码应已自动迁移到 PBKDF2
        new_hash = am.credentials["bob"]["password"]
        assert new_hash.startswith("pbkdf2_sha256$"), "登录后密码应迁移为 pbkdf2_sha256 格式"
        assert new_hash != legacy_hash, "迁移后的哈希必须不同于原 SHA-256"

        # 迁移后用相同密码应仍能登录，且不再触发迁移
        am2 = AuthManager(config_path=str(temp_config))
        am2.credentials["bob"]["password"] = new_hash
        user2 = am2.verify_credentials("bob", "LegacyPass456#")
        assert user2 is not None, "迁移后用相同密码应仍能登录"
        assert not am2._needs_password_upgrade(am2.credentials["bob"]["password"]), "不应再次迁移"

    def test_wrong_password_login_failure(self, temp_config):
        """场景 3：用户输入错误密码，应登录失败。"""
        correct_hash = _hash_password("RightPass789@")
        _write_config(
            temp_config,
            {
                "carol": {
                    "password": correct_hash,
                    "role": "viewer",
                    "email": "carol@example.com",
                    "name": "Carol Viewer",
                }
            },
        )

        am = AuthManager(config_path=str(temp_config))
        user = am.verify_credentials("carol", "WrongPassword!!!")

        assert user is None, "错误密码应登录失败"

    def test_unknown_user_login_failure(self, temp_config):
        """场景 4：未知用户登录，应失败。"""
        _write_config(temp_config, {"real_user": {"password": "x" * 64, "role": "viewer"}})

        am = AuthManager(config_path=str(temp_config))
        user = am.verify_credentials("nonexistent_user", "any_password")

        assert user is None, "未知用户应登录失败"

    def test_role_based_permissions(self, temp_config):
        """场景 5：不同角色的权限分层正确。"""
        _write_config(
            temp_config,
            {
                "admin_user": {
                    "password": _hash_password("AdminPass1#"),
                    "role": "admin",
                    "email": "a@e.com",
                    "name": "A",
                },
                "op_user": {
                    "password": _hash_password("OpPass2#"),
                    "role": "operator",
                    "email": "o@e.com",
                    "name": "O",
                },
                "view_user": {
                    "password": _hash_password("ViewPass3#"),
                    "role": "viewer",
                    "email": "v@e.com",
                    "name": "V",
                },
            },
        )

        am = AuthManager(config_path=str(temp_config))
        admin = am.verify_credentials("admin_user", "AdminPass1#")
        op = am.verify_credentials("op_user", "OpPass2#")
        viewer = am.verify_credentials("view_user", "ViewPass3#")

        assert admin and admin.role == UserRole.ADMIN, "admin 角色应有 admin 权限"
        assert admin and admin.can_modify_config(), "admin 应能修改配置"
        assert op and op.role == UserRole.OPERATOR, "operator 角色应为 OPERATOR"
        assert op and not op.can_modify_config(), "operator 不应能修改配置"
        assert op and op.can_execute_phases(), "operator 应能执行阶段"
        assert viewer and viewer.role == UserRole.VIEWER, "viewer 角色应为 VIEWER"
        assert viewer and not viewer.can_modify_config(), "viewer 不应能修改配置"
        assert viewer and not viewer.can_execute_phases(), "viewer 不应能执行阶段"

    def test_session_id_uniqueness(self, temp_config):
        """场景 6：多次登录生成不同的 session_id。"""
        pwd_hash = _hash_password("SessionPass0!")
        _write_config(
            temp_config,
            {
                "dave": {
                    "password": pwd_hash,
                    "role": "admin",
                    "email": "d@e.com",
                    "name": "Dave",
                }
            },
        )

        am = AuthManager(config_path=str(temp_config))
        u1 = am.verify_credentials("dave", "SessionPass0!")
        u2 = am.verify_credentials("dave", "SessionPass0!")

        assert u1 and u2, "两次登录都应成功"
        assert u1.session_id != u2.session_id, "两次登录的 session_id 必须不同"
        assert len(u1.session_id) >= 32, "session_id 应为足够长的随机 hex"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
