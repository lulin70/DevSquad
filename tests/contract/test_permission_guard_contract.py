#!/usr/bin/env python3
"""
PermissionGuard Contract Tests

Validates that PermissionGuard conforms to its documented interface and
exhibits the expected 4-level permission decision behavior:
  PLAN    → read-only (writes denied)
  DEFAULT → dangerous ops require confirmation (PROMPT)
  AUTO    → AI classifier auto-judges
  BYPASS  → skip all checks

Contract test ownership: shared between DevSquad and security teams.
Any breaking change to PermissionGuard API must be negotiated.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.permission_guard import (
    ActionType,
    DecisionOutcome,
    PermissionDecision,
    PermissionGuard,
    PermissionLevel,
    ProposedAction,
)


class TestPermissionGuardContract(unittest.TestCase):
    """Contract tests for PermissionGuard interface compliance."""

    def _get_guard(self) -> PermissionGuard:
        """Return a PermissionGuard at DEFAULT level with default rules."""
        return PermissionGuard(current_level=PermissionLevel.DEFAULT)

    def _make_action(
        self,
        action_type: ActionType = ActionType.FILE_READ,
        target: str = "/tmp/contract_test.txt",
    ) -> ProposedAction:
        """Build a ProposedAction for testing."""
        return ProposedAction(
            action_type=action_type,
            target=target,
            description="contract test action",
            source_role_id="tester",
        )

    def test_instantiation_no_exception(self):
        """Verify PermissionGuard instantiates without raising."""
        guard = self._get_guard()
        self.assertIsInstance(guard, PermissionGuard)

    def test_has_check(self):
        """Verify guard exposes the check() method."""
        guard = self._get_guard()
        self.assertTrue(hasattr(guard, "check"))
        self.assertTrue(callable(guard.check))

    def test_has_auto_classify(self):
        """Verify guard exposes the auto_classify() method."""
        guard = self._get_guard()
        self.assertTrue(hasattr(guard, "auto_classify"))
        self.assertTrue(callable(guard.auto_classify))

    def test_check_returns_permission_decision(self):
        """Verify check(ProposedAction) returns a PermissionDecision."""
        guard = self._get_guard()
        decision = guard.check(self._make_action())
        self.assertIsInstance(decision, PermissionDecision)

    def test_auto_classify_returns_float_in_range(self):
        """Verify auto_classify(ProposedAction) returns a float in [0.0, 1.0]."""
        guard = self._get_guard()
        score = guard.auto_classify(self._make_action())
        self.assertIsInstance(score, float)
        self.assertGreaterEqual(score, 0.0)
        self.assertLessEqual(score, 1.0)

    def test_decision_has_required_fields(self):
        """Verify PermissionDecision contains all required fields.

        Required: outcome, reason, matched_rule, and risk_score (exposed
        via the embedded ProposedAction).
        """
        guard = self._get_guard()
        decision = guard.check(self._make_action())
        self.assertTrue(hasattr(decision, "outcome"))
        self.assertTrue(hasattr(decision, "reason"))
        self.assertTrue(hasattr(decision, "matched_rule"))
        self.assertTrue(hasattr(decision, "action"))
        self.assertIsInstance(decision.outcome, DecisionOutcome)
        self.assertIsInstance(decision.reason, str)
        self.assertIsInstance(decision.action, ProposedAction)
        # risk_score lives on the embedded ProposedAction
        self.assertTrue(hasattr(decision.action, "risk_score"))
        self.assertIsInstance(decision.action.risk_score, float)


class TestPermissionGuardPlanLevel(unittest.TestCase):
    """Contract tests for PLAN level (read-only) behavior."""

    def _get_guard(self) -> PermissionGuard:
        return PermissionGuard(current_level=PermissionLevel.PLAN)

    def test_read_operation_allowed(self):
        """PLAN level must allow FILE_READ operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/read.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_write_operation_denied(self):
        """PLAN level must deny FILE_CREATE operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_CREATE,
            target="/tmp/new.py",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.DENIED)

    def test_delete_operation_denied(self):
        """PLAN level must deny FILE_DELETE operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/trash.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.DENIED)

    def test_shell_operation_denied(self):
        """PLAN level must deny SHELL_EXECUTE operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.SHELL_EXECUTE,
            target="ls /tmp",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.DENIED)


class TestPermissionGuardBypassLevel(unittest.TestCase):
    """Contract tests for BYPASS level (skip all checks) behavior."""

    def _get_guard(self) -> PermissionGuard:
        return PermissionGuard(current_level=PermissionLevel.BYPASS)

    def test_read_operation_allowed(self):
        """BYPASS level must allow FILE_READ operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/read.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_write_operation_allowed(self):
        """BYPASS level must allow FILE_CREATE operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_CREATE,
            target="/tmp/new.py",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_delete_operation_allowed(self):
        """BYPASS level must allow FILE_DELETE operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/trash.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_shell_operation_allowed(self):
        """BYPASS level must allow SHELL_EXECUTE operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.SHELL_EXECUTE,
            target="rm -rf /tmp/test",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)


class TestPermissionGuardDefaultLevel(unittest.TestCase):
    """Contract tests for DEFAULT level (dangerous ops need confirmation)."""

    def _get_guard(self) -> PermissionGuard:
        return PermissionGuard(current_level=PermissionLevel.DEFAULT)

    def test_needs_review_operation_returns_prompt(self):
        """DEFAULT level must return PROMPT for high-risk operations.

        A FILE_DELETE on any file matches rule R015 (requires BYPASS),
        which in DEFAULT mode yields PROMPT (needs user review).
        """
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/important.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.PROMPT)

    def test_needs_review_decision_requires_confirmation(self):
        """DEFAULT level PROMPT decisions must set requires_confirmation."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/important.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.PROMPT)
        self.assertTrue(decision.requires_confirmation)


if __name__ == "__main__":
    unittest.main()
