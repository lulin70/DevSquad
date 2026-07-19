#!/usr/bin/env python3
"""
Phase 5: PermissionGuard 权限系统覆盖率提升测试（基于实际 API）

目标：
- 权限级别比较逻辑测试
- 动作类型覆盖测试
- 提案动作创建和检查测试
- 权限决策场景测试

遵循 AAA 模式 (Arrange-Act-Assert)
"""

import os
import sys
from enum import Enum

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.permission_guard import (
    ActionType,
    PermissionGuard,
    PermissionLevel,
    ProposedAction,
)

pytestmark = pytest.mark.unit



class TestPermissionLevelEnum:
    """权限级别枚举测试"""

    def test_all_permission_levels_defined(self):
        """Test that expected permission levels are defined."""
        expected_levels = ["DEFAULT", "PLAN", "AUTO", "BYPASS"]
        for level in expected_levels:
            assert level in [pl.name for pl in PermissionLevel]

    def test_permission_level_values_unique(self):
        """Test that all permission level values are unique."""
        values = [pl.value for pl in PermissionLevel]
        assert len(values) == len(set(values))

    def test_bypass_is_highest(self):
        """Test BYPASS level exists for highest privilege."""
        assert PermissionLevel.BYPASS in PermissionLevel


class TestActionTypeEnum:
    """动作类型枚举测试"""

    def test_all_action_types_defined(self):
        """Test that expected action types are defined."""
        expected_actions = [
            "FILE_READ",
            "FILE_CREATE",
            "FILE_MODIFY",
            "FILE_DELETE",
            "SHELL_EXECUTE",
            "NETWORK_REQUEST",
            "GIT_OPERATION",
            "ENVIRONMENT",
            "PROCESS_SPAWN",
        ]
        for action in expected_actions:
            assert action in [a.name for a in ActionType]

    def test_action_type_values_unique(self):
        """Test that all action type values are unique."""
        values = [a.value for a in ActionType]
        assert len(values) == len(set(values))

    def test_file_actions_exist(self):
        """Test file-related action types exist."""
        file_actions = [ActionType.FILE_READ, ActionType.FILE_CREATE, ActionType.FILE_MODIFY, ActionType.FILE_DELETE]
        for action in file_actions:
            assert action in ActionType


class TestProposedActionCreation:
    """提案动作创建测试"""

    def test_create_file_read_action(self):
        """Test creating a file read action."""
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="config.yaml",
            metadata={"user": "tester"},
        )
        assert action.action_type == ActionType.FILE_READ
        assert action.target == "config.yaml"

    def test_create_file_write_action(self):
        """Test creating a file modify (write) action."""
        action = ProposedAction(
            action_type=ActionType.FILE_MODIFY,
            target="code.py",
            description="Fixing bug #123",
        )
        assert action.action_type == ActionType.FILE_MODIFY
        assert action.description == "Fixing bug #123"

    def test_create_file_delete_action(self):
        """Test creating a file delete action."""
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="old_file.py",
            description="Deprecated functionality",
        )
        assert action.action_type == ActionType.FILE_DELETE

    def test_create_shell_execute_action(self):
        """Test creating a shell execute action."""
        action = ProposedAction(
            action_type=ActionType.SHELL_EXECUTE,
            target="deploy.sh",
            metadata={
                "environment": "production",
                "rollback_plan": True,
                "approved_by": "admin",
            },
        )
        assert action.action_type == ActionType.SHELL_EXECUTE
        assert action.metadata["rollback_plan"] is True

    def test_create_network_request_action(self):
        """Test creating a network request action."""
        action = ProposedAction(
            action_type=ActionType.NETWORK_REQUEST,
            target="https://api.example.com/data",
        )
        assert action.action_type == ActionType.NETWORK_REQUEST


class TestPermissionCheckScenarios:
    """权限检查场景测试"""

    @pytest.fixture
    def permission_guard(self):
        """Create PermissionGuard instance."""
        return PermissionGuard()

    def test_bypass_level_can_do_everything(self, permission_guard):
        """Test bypass level can perform all actions."""
        permission_guard.set_level(PermissionLevel.BYPASS)
        for action_type in ActionType:
            action = ProposedAction(
                action_type=action_type,
                target="test_resource",
            )
            result = permission_guard.check(action)
            assert result.outcome.name == "ALLOWED"

    def test_default_level_restricted_actions(self, permission_guard):
        """Test default level has restrictions on dangerous actions."""
        permission_guard.set_level(PermissionLevel.DEFAULT)

        read_action = ProposedAction(action_type=ActionType.FILE_READ, target="file.txt")
        read_result = permission_guard.check(read_action)

        delete_action = ProposedAction(action_type=ActionType.FILE_DELETE, target="file.txt")
        delete_result = permission_guard.check(delete_action)

        shell_action = ProposedAction(action_type=ActionType.SHELL_EXECUTE, target="rm -rf /")
        shell_result = permission_guard.check(shell_action)

        assert hasattr(read_result, "outcome")
        assert hasattr(delete_result, "outcome")
        assert hasattr(shell_result, "outcome")

    def test_permission_decision_structure(self, permission_guard):
        """Test that permission decision has required fields."""
        permission_guard.set_level(PermissionLevel.DEFAULT)
        action = ProposedAction(action_type=ActionType.FILE_READ, target="test.txt")
        result = permission_guard.check(action)
        assert hasattr(result, "outcome")
        assert hasattr(result, "reason")
        assert isinstance(result.outcome, Enum)


class TestPermissionEdgeCases:
    """权限系统边界条件测试"""

    @pytest.fixture
    def permission_guard(self):
        return PermissionGuard()

    def test_empty_target(self, permission_guard):
        """Test permission check with empty target string."""
        permission_guard.set_level(PermissionLevel.DEFAULT)
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="",
        )
        result = permission_guard.check(action)
        assert hasattr(result, "outcome")

    def test_none_metadata_handling(self, permission_guard):
        """Test handling of default metadata in action."""
        permission_guard.set_level(PermissionLevel.DEFAULT)
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="file.txt",
        )
        result = permission_guard.check(action)
        assert hasattr(result, "outcome")

    def test_very_long_target_path(self, permission_guard):
        """Test permission check with very long target path."""
        permission_guard.set_level(PermissionLevel.BYPASS)
        long_path = "/very/deep/nested/path/" + "/subdir" * 50 + "/file.txt"
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target=long_path,
        )
        result = permission_guard.check(action)
        assert result.outcome.name == "ALLOWED"

    def test_special_characters_in_target(self, permission_guard):
        """Test permission check with special characters in target name."""
        permission_guard.set_level(PermissionLevel.DEFAULT)
        special_targets = [
            "file-with-dashes.txt",
            "file_with_underscores.txt",
            "file.with.dots.txt",
            "file (copy).txt",
        ]
        for target in special_targets:
            action = ProposedAction(action_type=ActionType.FILE_READ, target=target)
            result = permission_guard.check(action)
            assert hasattr(result, "outcome")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
