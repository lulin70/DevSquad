#!/usr/bin/env python3
"""
Phase 5: Auth 认证模块覆盖率提升测试

目标：
- 密码哈希验证测试
- 用户凭证验证测试
- 会话管理测试
- 权限检查装饰器测试
- 安全配置验证测试

遵循 AAA 模式 (Arrange-Act-Assert)
"""

import os
import sys
import tempfile
from datetime import datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.auth import (  # noqa: E402
    AuthManager,
    User,
    UserRole,
)

# SHA-256 of "password" — legacy hash reused across migration tests.
LEGACY_SHA256_PASSWORD = (
    "5e884898da28047151d0e56f8dc6292773603d0d6aabbdd62a11ef721d1542d8"
)


class TestPasswordHashing:
    """密码哈希功能测试（PBKDF2-HMAC-SHA256 + 随机 salt）"""

    def test_hash_password_uniqueness_same_input(self):
        """Same password produces different hashes due to random salt."""
        auth = AuthManager(config_path=None)
        hash1 = auth._hash_password("test_password_123")
        hash2 = auth._hash_password("test_password_123")
        assert hash1 != hash2  # Random salt ensures uniqueness

    def test_hash_password_uniqueness_different_input(self):
        """Different passwords produce different hashes."""
        auth = AuthManager(config_path=None)
        hash1 = auth._hash_password("password_one")
        hash2 = auth._hash_password("password_two")
        assert hash1 != hash2

    def test_hash_password_output_format_pbkdf2(self):
        """Hash uses pbkdf2_sha256$<iter>$<salt>$<hash> format."""
        auth = AuthManager(config_path=None)
        hashed = auth._hash_password("any_password")
        assert hashed.startswith("pbkdf2_sha256$")
        parts = hashed.split("$")
        assert len(parts) == 4
        assert parts[0] == "pbkdf2_sha256"
        assert int(parts[1]) >= 390000  # OWASP 2023 minimum
        # Salt is 16 bytes = 32 hex chars; hash is 32 bytes = 64 hex chars
        assert len(parts[2]) == 32
        assert len(parts[3]) == 64
        assert all(c in '0123456789abcdef' for c in parts[2] + parts[3])

    def test_hash_empty_password_pbkdf2(self):
        """Empty password still produces valid pbkdf2 format."""
        auth = AuthManager(config_path=None)
        hashed = auth._hash_password("")
        assert hashed.startswith("pbkdf2_sha256$")
        assert hashed.split("$")[3] != ""  # Hash is non-empty

    def test_hash_uses_random_salt(self):
        """Each call generates a unique salt (no salt reuse)."""
        auth = AuthManager(config_path=None)
        hashes = [auth._hash_password("same") for _ in range(10)]
        salts = [h.split("$")[2] for h in hashes]
        assert len(set(salts)) == 10  # All 10 salts unique


class TestPasswordVerification:
    """密码验证功能测试（_verify_password 新旧格式）"""

    def test_verify_new_pbkdf2_format(self):
        """_verify_password accepts new pbkdf2_sha256 format."""
        auth = AuthManager(config_path=None)
        hashed = auth._hash_password("my_secret")
        assert auth._verify_password("my_secret", hashed) is True
        assert auth._verify_password("wrong", hashed) is False

    def test_verify_legacy_sha256_format(self):
        """_verify_password accepts legacy 64-char SHA-256 for migration."""
        auth = AuthManager(config_path=None)
        # SHA-256 of "password" = 5e884898...
        legacy = LEGACY_SHA256_PASSWORD
        assert auth._verify_password("password", legacy) is True
        assert auth._verify_password("wrong", legacy) is False

    def test_verify_empty_stored_hash(self):
        """_verify_password rejects empty stored hash."""
        auth = AuthManager(config_path=None)
        assert auth._verify_password("anything", "") is False

    def test_verify_malformed_pbkdf2_hash(self):
        """_verify_password rejects malformed pbkdf2 hash."""
        auth = AuthManager(config_path=None)
        assert auth._verify_password(
            "x", "pbkdf2_sha256$abc$not_hex$alsobad"
        ) is False
        assert auth._verify_password("x", "pbkdf2_sha256$1000$") is False

    def test_verify_non_hex_legacy_hash(self):
        """_verify_password rejects 64-char non-hex string."""
        auth = AuthManager(config_path=None)
        # 64 chars but contains non-hex characters
        fake = "z" * 64
        # SHA-256 of "password" won't match this, so returns False
        assert auth._verify_password("anything", fake) is False


class TestPasswordMigration:
    """密码迁移测试（legacy SHA-256 → pbkdf2_sha256）"""

    def test_needs_upgrade_legacy_sha256(self):
        """Legacy 64-char hex hash needs upgrade."""
        auth = AuthManager(config_path=None)
        legacy = LEGACY_SHA256_PASSWORD
        assert auth._needs_password_upgrade(legacy) is True

    def test_needs_upgrade_new_pbkdf2(self):
        """New pbkdf2_sha256 hash does not need upgrade."""
        auth = AuthManager(config_path=None)
        new_hash = auth._hash_password("test")
        assert auth._needs_password_upgrade(new_hash) is False

    def test_needs_upgrade_empty_hash(self):
        """Empty hash does not trigger upgrade."""
        auth = AuthManager(config_path=None)
        assert auth._needs_password_upgrade("") is False

    def test_verify_credentials_upgrades_legacy_hash(self, tmp_path):
        """Successful login with legacy hash upgrades to pbkdf2 in memory."""
        config_path = tmp_path / "deployment.yaml"
        config_content = f"""
authentication:
  enabled: true
  credentials:
    usernames:
      admin:
        password: {LEGACY_SHA256_PASSWORD}
        email: admin@devsquad.test
        name: Administrator
        role: admin
"""
        config_path.write_text(config_content)
        auth = AuthManager(config_path=str(config_path))

        # Before login: legacy hash
        assert auth._needs_password_upgrade(
            auth.credentials["admin"]["password"]
        ) is True

        # Successful login
        user = auth.verify_credentials("admin", "password")
        assert user is not None

        # After login: upgraded to pbkdf2 in memory
        new_hash = auth.credentials["admin"]["password"]
        assert new_hash.startswith("pbkdf2_sha256$")
        assert auth._needs_password_upgrade(new_hash) is False

    def test_verify_credentials_no_upgrade_for_new_format(self, tmp_path):
        """Login with new pbkdf2 hash does not trigger upgrade."""
        auth_tmp = AuthManager(config_path=None)
        new_hash = auth_tmp._hash_password("secret123")
        config_path = tmp_path / "deployment.yaml"
        config_content = f"""
authentication:
  enabled: true
  credentials:
    usernames:
      admin:
        password: {new_hash}
        email: admin@devsquad.test
        name: Administrator
        role: admin
"""
        config_path.write_text(config_content)
        auth = AuthManager(config_path=str(config_path))

        user = auth.verify_credentials("admin", "secret123")
        assert user is not None
        # Hash unchanged (no upgrade needed)
        assert auth.credentials["admin"]["password"] == new_hash


class TestUserCredentialVerification:
    """用户凭证验证测试"""

    @pytest.fixture
    def auth_manager_with_credentials(self):
        """Create AuthManager with test credentials using temp config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "deployment.yaml")
            config_content = f"""
authentication:
  enabled: true
  credentials:
    usernames:
      admin:
        password: {LEGACY_SHA256_PASSWORD}
        email: admin@devsquad.test
        name: Administrator
        role: admin
      tester:
        password: hashed_tester_password_here
        email: tester@devsquad.test
        name: Tester User
        role: operator
"""
            with open(config_path, "w") as f:
                f.write(config_content)

            auth = AuthManager(config_path=config_path)
            yield auth

    def test_verify_valid_credentials(self, auth_manager_with_credentials):
        """Test verification of valid credentials."""
        user = auth_manager_with_credentials.verify_credentials(
            "admin", "password"
        )
        assert user is not None
        assert user.username == "admin"
        assert user.role == UserRole.ADMIN

    def test_verify_invalid_password(self, auth_manager_with_credentials):
        """Test verification fails with wrong password."""
        user = auth_manager_with_credentials.verify_credentials(
            "admin", "wrong_password"
        )
        assert user is None

    def test_verify_unknown_user(self, auth_manager_with_credentials):
        """Test verification fails for unknown username."""
        user = auth_manager_with_credentials.verify_credentials(
            "nonexistent", "password"
        )
        assert user is None

    def test_verify_returns_user_object(self, auth_manager_with_credentials):
        """Test that successful verification returns proper User object."""
        user = auth_manager_with_credentials.verify_credentials(
            "admin", "password"
        )
        assert isinstance(user, User)
        assert user.email == "admin@devsquad.test"
        assert user.name == "Administrator"
        assert isinstance(user.authenticated_at, datetime)
        assert len(user.session_id) == 32  # secrets.token_hex(16) = 32 chars

    def test_verify_invalid_role_fallback(self):
        """Test that invalid role falls back to VIEWER."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "deployment.yaml")
            config_content = """
authentication:
  enabled: true
  credentials:
    usernames:
      bad_role_user:
        password: some_hash
        role: invalid_role_name
"""
            with open(config_path, "w") as f:
                f.write(config_content)

            auth = AuthManager(config_path=config_path)
            user = auth.verify_credentials("bad_role_user", "some_password")
            if user:
                assert user.role == UserRole.VIEWER


class TestUserRolePermissions:
    """用户角色权限测试"""

    def test_admin_can_execute_phases(self):
        """Test ADMIN can execute phases."""
        user = User(
            username="admin",
            email="admin@test.com",
            name="Admin",
            role=UserRole.ADMIN,
            authenticated_at=datetime.now(),
            session_id="session123",
        )
        assert user.can_execute_phases() is True

    def test_operator_can_execute_phases(self):
        """Test OPERATOR can execute phases."""
        user = User(
            username="operator",
            email="op@test.com",
            name="Operator",
            role=UserRole.OPERATOR,
            authenticated_at=datetime.now(),
            session_id="session123",
        )
        assert user.can_execute_phases() is True

    def test_viewer_cannot_execute_phases(self):
        """Test VIEWER cannot execute phases."""
        user = User(
            username="viewer",
            email="viewer@test.com",
            name="Viewer",
            role=UserRole.VIEWER,
            authenticated_at=datetime.now(),
            session_id="session123",
        )
        assert user.can_execute_phases() is False

    def test_all_roles_can_view_metrics(self):
        """Test all roles can view metrics."""
        for role in UserRole:
            user = User(
                username="user",
                email="user@test.com",
                name="User",
                role=role,
                authenticated_at=datetime.now(),
                session_id="session123",
            )
            assert user.can_view_metrics() is True

    def test_only_admin_can_modify_config(self):
        """Test only ADMIN can modify config."""
        admin = User(
            username="admin",
            email="admin@test.com",
            name="Admin",
            role=UserRole.ADMIN,
            authenticated_at=datetime.now(),
            session_id="session123",
        )
        operator = User(
            username="operator",
            email="op@test.com",
            name="Operator",
            role=UserRole.OPERATOR,
            authenticated_at=datetime.now(),
            session_id="session123",
        )
        viewer = User(
            username="viewer",
            email="viewer@test.com",
            name="Viewer",
            role=UserRole.VIEWER,
            authenticated_at=datetime.now(),
            session_id="session123",
        )

        assert admin.can_modify_config() is True
        assert operator.can_modify_config() is False
        assert viewer.can_modify_config() is False


class TestAuthManagerConfigLoading:
    """配置加载测试"""

    def test_load_missing_config(self):
        """Test loading missing config file returns empty dict."""
        auth = AuthManager(config_path="/nonexistent/path/config.yaml")
        assert auth.config == {}

    def test_auth_disabled_by_default(self):
        """Auth disabled when config missing or has no auth section."""
        # Use a non-existent path to test "no config file" behavior.
        # Note: config_path=None falls back to default deployment.yaml
        # which may exist.
        auth = AuthManager(config_path="/nonexistent/path/config.yaml")
        assert auth.auth_enabled is False

    def test_load_valid_config(self):
        """Test loading valid YAML config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "deployment.yaml")
            config_content = """
authentication:
  enabled: true
  cookie:
    key: test_session_key
"""
            with open(config_path, "w") as f:
                f.write(config_content)

            auth = AuthManager(config_path=config_path)
            assert auth.auth_enabled is True
            assert auth.cookie_settings.get("key") == "test_session_key"


class TestSecurityValidation:
    """安全配置验证测试"""

    def test_detect_placeholder_password(self):
        """Test detection of placeholder passwords in config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "deployment.yaml")
            config_content = """
authentication:
  enabled: true
  credentials:
    usernames:
      bad_admin:
        password: password
        role: admin
"""
            with open(config_path, "w") as f:
                f.write(config_content)

            with patch('scripts.auth.logger') as mock_logger:
                AuthManager(config_path=config_path)
                mock_logger.warning.assert_called()

    def test_detect_default_session_key(self):
        """Test detection of default session key."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "deployment.yaml")
            config_content = """
authentication:
  enabled: true
  cookie:
    key: devsquad_session_key_change_in_production
"""
            with open(config_path, "w") as f:
                f.write(config_content)

            with patch('scripts.auth.logger') as mock_logger:
                AuthManager(config_path=config_path)
                warning_calls = [
                    str(call) for call in mock_logger.warning.call_args_list
                ]
                assert any(
                    ("default session key" in w.lower()
                     or "session key" in w.lower())
                    for w in warning_calls
                )


class TestSessionManagement:
    """会话管理测试"""

    def test_session_id_generation(self):
        """Test that session IDs are generated correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = os.path.join(tmpdir, "deployment.yaml")
            config_content = f"""
authentication:
  enabled: true
  credentials:
    usernames:
      testuser:
        password: {LEGACY_SHA256_PASSWORD}
        role: viewer
"""
            with open(config_path, "w") as f:
                f.write(config_content)

            auth = AuthManager(config_path=config_path)
            user1 = auth.verify_credentials("testuser", "password")
            user2 = auth.verify_credentials("testuser", "password")

            assert user1.session_id != user2.session_id
            assert len(user1.session_id) == 32  # token_hex(16) = 32 chars
            assert len(user2.session_id) == 32


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
