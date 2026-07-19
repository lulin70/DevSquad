#!/usr/bin/env python3
"""
Tests for DispatchRBAC (V39-06) — RBAC integration for dispatch pipeline.

Coverage:
  - Happy path: open mode (no AuthManager) allows all
  - Happy path: admin role allows all roles and modes
  - Permission matrix: operator, viewer restrictions
  - Error cases: unknown user, unrecognized role, denied role, denied mode
  - Edge cases: empty roles list, empty user_id
  - Integration: works with a mock AuthManager-like object
"""

from __future__ import annotations

import os
import sys
import time
import unittest
from dataclasses import dataclass, field

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from scripts.collaboration.dispatch_rbac import DispatchRBAC, PermissionResult

pytestmark = pytest.mark.unit



@dataclass
class MockAuthManager:
    """Mock AuthManager with a credentials dict (matches AuthManager API)."""

    credentials: dict = field(default_factory=dict)


class TestPermissionResultDataclass(unittest.TestCase):
    """Verify PermissionResult dataclass stores all fields."""

    def test_permission_result_holds_all_fields(self) -> None:
        """Verify: PermissionResult stores allowed/reason/user_id/roles/mode."""
        # Arrange
        result = PermissionResult(
            allowed=True,
            reason="OK",
            user_id="u1",
            requested_roles=["architect"],
            requested_mode="auto",
        )
        # Assert
        self.assertTrue(result.allowed)
        self.assertEqual(result.reason, "OK")
        self.assertEqual(result.user_id, "u1")
        self.assertEqual(result.requested_roles, ["architect"])
        self.assertEqual(result.requested_mode, "auto")


class TestDispatchRBACOpenMode(unittest.TestCase):
    """Open mode — no AuthManager configured, all operations allowed."""

    def setUp(self) -> None:
        self.rbac = DispatchRBAC()  # No auth_manager.

    def test_open_mode_allows_any_user(self) -> None:
        """Verify: without AuthManager, any user is allowed."""
        # Act
        result = self.rbac.check_dispatch_permission("anyone", ["architect"], "auto")
        # Assert
        self.assertTrue(result.allowed)
        self.assertIn("No RBAC", result.reason)

    def test_open_mode_allows_any_role_and_mode(self) -> None:
        """Verify: without AuthManager, any role/mode is allowed."""
        # Act
        result = self.rbac.check_dispatch_permission("u1", ["security", "coder"], "consensus")
        # Assert
        self.assertTrue(result.allowed)

    def test_open_mode_preserves_request_fields(self) -> None:
        """Verify: PermissionResult echoes back the requested roles/mode."""
        # Act
        result = self.rbac.check_dispatch_permission("u1", ["architect"], "parallel")
        # Assert
        self.assertEqual(result.user_id, "u1")
        self.assertEqual(result.requested_roles, ["architect"])
        self.assertEqual(result.requested_mode, "parallel")


class TestDispatchRBACFailClosedMode(unittest.TestCase):
    """Fail-closed mode — no AuthManager configured, all operations DENIED.

    P1-2 fix (HC-1 alignment): when ``fail_closed=True`` and no AuthManager
    is configured, DispatchRBAC denies all operations instead of allowing
    them. This is the production-safe default.
    """

    def setUp(self) -> None:
        self.rbac = DispatchRBAC(fail_closed=True)  # No auth_manager, fail-closed.

    def test_fail_closed_denies_any_user(self) -> None:
        """Verify: fail-closed mode denies any user when no AuthManager."""
        result = self.rbac.check_dispatch_permission("anyone", ["architect"], "auto")
        self.assertFalse(result.allowed)
        self.assertIn("fail-closed", result.reason)

    def test_fail_closed_denies_any_role_and_mode(self) -> None:
        """Verify: fail-closed mode denies any role/mode combination."""
        result = self.rbac.check_dispatch_permission("u1", ["security", "coder"], "consensus")
        self.assertFalse(result.allowed)

    def test_fail_closed_preserves_request_fields(self) -> None:
        """Verify: PermissionResult still echoes request fields in fail-closed mode."""
        result = self.rbac.check_dispatch_permission("u1", ["architect"], "parallel")
        self.assertFalse(result.allowed)
        self.assertEqual(result.user_id, "u1")
        self.assertEqual(result.requested_roles, ["architect"])
        self.assertEqual(result.requested_mode, "parallel")

    def test_fail_closed_default_is_false(self) -> None:
        """Verify: DispatchRBAC defaults to open mode (fail_closed=False)."""
        rbac = DispatchRBAC()  # No fail_closed arg.
        result = rbac.check_dispatch_permission("u1", ["architect"], "auto")
        self.assertTrue(result.allowed)  # Open mode allows all.


class TestDispatchRBACAdminRole(unittest.TestCase):
    """Admin role — all roles and modes permitted."""

    def setUp(self) -> None:
        self.auth = MockAuthManager(credentials={"admin": {"role": "admin", "name": "Admin User"}})
        self.rbac = DispatchRBAC(auth_manager=self.auth)

    def test_admin_can_dispatch_all_roles(self) -> None:
        """Verify: admin can dispatch with any combination of roles."""
        # Act
        result = self.rbac.check_dispatch_permission(
            "admin",
            ["architect", "security", "coder", "tester", "devops", "ui-designer", "product-manager"],
            "auto",
        )
        # Assert
        self.assertTrue(result.allowed)

    def test_admin_can_use_all_modes(self) -> None:
        """Verify: admin can use all dispatch modes."""
        # Act + Assert
        for mode in ("auto", "parallel", "sequential", "consensus"):
            result = self.rbac.check_dispatch_permission("admin", ["architect"], mode)
            self.assertTrue(result.allowed, f"Admin should be allowed mode={mode}")


class TestDispatchRBACOperatorRole(unittest.TestCase):
    """Operator role — all roles except security, no consensus mode."""

    def setUp(self) -> None:
        self.auth = MockAuthManager(credentials={"op": {"role": "operator", "name": "Op User"}})
        self.rbac = DispatchRBAC(auth_manager=self.auth)

    def test_operator_can_dispatch_coder(self) -> None:
        """Verify: operator can dispatch with coder role."""
        # Act
        result = self.rbac.check_dispatch_permission("op", ["coder"], "parallel")
        # Assert
        self.assertTrue(result.allowed)

    def test_operator_cannot_dispatch_security(self) -> None:
        """Verify: operator cannot dispatch with security role."""
        # Act
        result = self.rbac.check_dispatch_permission("op", ["security"], "auto")
        # Assert
        self.assertFalse(result.allowed)
        self.assertIn("security", result.reason)

    def test_operator_cannot_use_consensus_mode(self) -> None:
        """Verify: operator cannot use consensus mode."""
        # Act
        result = self.rbac.check_dispatch_permission("op", ["coder"], "consensus")
        # Assert
        self.assertFalse(result.allowed)
        self.assertIn("consensus", result.reason)


class TestDispatchRBACViewerRole(unittest.TestCase):
    """Viewer role — read-only roles, auto mode only."""

    def setUp(self) -> None:
        self.auth = MockAuthManager(credentials={"viewer": {"role": "viewer", "name": "Viewer"}})
        self.rbac = DispatchRBAC(auth_manager=self.auth)

    def test_viewer_can_dispatch_architect(self) -> None:
        """Verify: viewer can dispatch with architect role."""
        # Act
        result = self.rbac.check_dispatch_permission("viewer", ["architect"], "auto")
        # Assert
        self.assertTrue(result.allowed)

    def test_viewer_cannot_dispatch_coder(self) -> None:
        """Verify: viewer cannot dispatch with coder role."""
        # Act
        result = self.rbac.check_dispatch_permission("viewer", ["coder"], "auto")
        # Assert
        self.assertFalse(result.allowed)
        self.assertIn("coder", result.reason)

    def test_viewer_cannot_use_parallel_mode(self) -> None:
        """Verify: viewer cannot use parallel mode."""
        # Act
        result = self.rbac.check_dispatch_permission("viewer", ["architect"], "parallel")
        # Assert
        self.assertFalse(result.allowed)
        self.assertIn("parallel", result.reason)


class TestDispatchRBACErrorCases(unittest.TestCase):
    """Error cases — unknown user, unrecognized role."""

    def setUp(self) -> None:
        self.auth = MockAuthManager(
            credentials={
                "admin": {"role": "admin"},
                "viewer": {"role": "viewer"},
            }
        )
        self.rbac = DispatchRBAC(auth_manager=self.auth)

    def test_unknown_user_denied(self) -> None:
        """Verify: unknown user is denied."""
        # Act
        result = self.rbac.check_dispatch_permission("nonexistent", ["architect"], "auto")
        # Assert
        self.assertFalse(result.allowed)
        self.assertIn("not found", result.reason)

    def test_user_with_unrecognized_role_denied(self) -> None:
        """Verify: user with unrecognized role is denied."""
        # Arrange
        auth = MockAuthManager(credentials={"weird": {"role": "superuser"}})
        rbac = DispatchRBAC(auth_manager=auth)
        # Act
        result = rbac.check_dispatch_permission("weird", ["architect"], "auto")
        # Assert
        self.assertFalse(result.allowed)
        self.assertIn("unrecognized", result.reason)


class TestDispatchRBACEdgeCases(unittest.TestCase):
    """Edge cases — empty roles, empty user_id."""

    def setUp(self) -> None:
        self.auth = MockAuthManager(credentials={"admin": {"role": "admin"}})
        self.rbac = DispatchRBAC(auth_manager=self.auth)

    def test_empty_roles_list_allowed_for_admin(self) -> None:
        """Verify: empty roles list is allowed (no roles to check)."""
        # Act
        result = self.rbac.check_dispatch_permission("admin", [], "auto")
        # Assert
        self.assertTrue(result.allowed)

    def test_empty_user_id_denied(self) -> None:
        """Verify: empty user_id is denied (not found in credentials)."""
        # Act
        result = self.rbac.check_dispatch_permission("", ["architect"], "auto")
        # Assert
        self.assertFalse(result.allowed)


class TestDispatchRBACPerformance(unittest.TestCase):
    """Performance baseline — check should be fast."""

    def test_check_completes_under_5ms(self) -> None:
        """Verify: a single check completes in < 5ms."""
        # Arrange
        auth = MockAuthManager(credentials={"admin": {"role": "admin"}})
        rbac = DispatchRBAC(auth_manager=auth)
        # Act
        start = time.perf_counter()
        for _ in range(1000):
            rbac.check_dispatch_permission("admin", ["architect", "coder"], "parallel")
        elapsed = time.perf_counter() - start
        # Assert
        self.assertLess(elapsed, 5.0, f"1000 checks took {elapsed:.3f}s (> 5ms per call)")


if __name__ == "__main__":
    unittest.main()
