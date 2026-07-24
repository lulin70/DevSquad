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
    PermissionRule,
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


class TestPermissionGuardAutoLevel(unittest.TestCase):
    """Contract tests for AUTO level (AI classifier auto-judges) behavior."""

    def _get_guard(self) -> PermissionGuard:
        return PermissionGuard(current_level=PermissionLevel.AUTO)

    def test_auto_level_file_read_allowed(self):
        """AUTO level must allow FILE_READ operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/read.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_auto_level_file_delete_prompts(self):
        """AUTO level must PROMPT for FILE_DELETE (human gate)."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/trash.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.PROMPT)

    def test_auto_level_process_spawn_prompts(self):
        """AUTO level must PROMPT for PROCESS_SPAWN (human gate)."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.PROCESS_SPAWN,
            target="/usr/bin/python",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.PROMPT)

    def test_auto_level_environment_prompts(self):
        """AUTO level must PROMPT for ENVIRONMENT changes (human gate)."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.ENVIRONMENT,
            target="PATH",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.PROMPT)

    def test_auto_level_file_create_py_allowed(self):
        """AUTO level must allow creating .py files (low risk)."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_CREATE,
            target="/tmp/new_module.py",
            source_role_id="coder",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)


class TestPermissionGuardExtendedContract(unittest.TestCase):
    """Extended contract tests for PermissionGuard audit, rules, and state."""

    def _get_guard(self) -> PermissionGuard:
        return PermissionGuard(current_level=PermissionLevel.DEFAULT)

    def test_plan_denies_file_modify(self):
        """PLAN level must deny FILE_MODIFY operations."""
        guard = PermissionGuard(current_level=PermissionLevel.PLAN)
        action = ProposedAction(
            action_type=ActionType.FILE_MODIFY,
            target="/tmp/file.py",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.DENIED)

    def test_plan_denies_network_request(self):
        """PLAN level must deny NETWORK_REQUEST operations."""
        guard = PermissionGuard(current_level=PermissionLevel.PLAN)
        action = ProposedAction(
            action_type=ActionType.NETWORK_REQUEST,
            target="https://api.example.com",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.DENIED)

    def test_default_file_read_allowed(self):
        """DEFAULT level must allow FILE_READ operations."""
        guard = self._get_guard()
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/read.txt",
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_audit_log_records_decisions(self):
        """Audit log should record entries after check() calls."""
        guard = self._get_guard()
        guard.check(ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/a.txt",
            source_role_id="tester",
        ))
        guard.check(ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/b.txt",
            source_role_id="tester",
        ))
        log = guard.get_audit_log()
        self.assertGreaterEqual(len(log), 2)

    def test_get_audit_log_with_outcome_filter(self):
        """get_audit_log should filter by outcome."""
        guard = self._get_guard()
        guard.check(ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/read.txt",
            source_role_id="tester",
        ))
        allowed = guard.get_audit_log(outcome=DecisionOutcome.ALLOWED)
        self.assertTrue(all(e.decision.outcome == DecisionOutcome.ALLOWED for e in allowed))

    def test_add_rule_new(self):
        """add_rule should add a new rule to the guard."""
        guard = self._get_guard()
        initial_count = len(guard.rules)
        new_rule = PermissionRule(
            rule_id="CUSTOM001",
            action_type=ActionType.FILE_READ,
            pattern="/custom/*",
            required_level=PermissionLevel.PLAN,
            description="Custom read rule",
        )
        guard.add_rule(new_rule)
        self.assertEqual(len(guard.rules), initial_count + 1)

    def test_remove_rule_existing(self):
        """remove_rule should remove an existing rule and return True."""
        guard = self._get_guard()
        result = guard.remove_rule("R001")
        self.assertTrue(result)

    def test_remove_rule_nonexistent(self):
        """remove_rule should return False for non-existent rule."""
        guard = self._get_guard()
        result = guard.remove_rule("NONEXISTENT")
        self.assertFalse(result)

    def test_set_level_changes_behavior(self):
        """set_level should dynamically change permission behavior."""
        guard = self._get_guard()
        # In DEFAULT, FILE_DELETE prompts (human gate)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
            source_role_id="tester",
        )
        decision_default = guard.check(action)
        self.assertEqual(decision_default.outcome, DecisionOutcome.PROMPT)
        # Switch to BYPASS
        guard.set_level(PermissionLevel.BYPASS)
        decision_bypass = guard.check(action)
        self.assertEqual(decision_bypass.outcome, DecisionOutcome.ALLOWED)

    def test_whitelist_allows_action(self):
        """add_whitelist should allow matching actions to bypass rules."""
        guard = self._get_guard()
        target = "/tmp/whitelisted.txt"
        guard.add_whitelist(target)
        action = ProposedAction(
            action_type=ActionType.FILE_MODIFY,
            target=target,
            source_role_id="tester",
        )
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_get_security_report(self):
        """get_security_report should return a dict with expected keys."""
        guard = self._get_guard()
        guard.check(ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/r.txt",
            source_role_id="tester",
        ))
        report = guard.get_security_report()
        self.assertIsInstance(report, dict)
        self.assertIn("total_checks", report)
        self.assertIn("allowed", report)
        self.assertIn("denied", report)
        self.assertIn("guard_level", report)

    def test_export_state(self):
        """export_state should return a serializable state dict."""
        guard = self._get_guard()
        state = guard.export_state()
        self.assertIsInstance(state, dict)
        self.assertIn("current_level", state)
        self.assertIn("rules", state)
        self.assertIn("whitelist", state)
        self.assertIn("session_id", state)

    def test_import_rules(self):
        """import_rules should import rules from dict list."""
        guard = self._get_guard()
        rules_data = [
            {
                "rule_id": "IMP001",
                "action_type": "file_read",
                "pattern": "/imported/*",
                "required_level": "plan",
                "description": "Imported rule",
            },
        ]
        count = guard.import_rules(rules_data)
        self.assertEqual(count, 1)

    def test_export_rules_returns_list(self):
        """export_rules should return a list of rule dicts."""
        guard = self._get_guard()
        rules = guard.export_rules()
        self.assertIsInstance(rules, list)
        self.assertGreater(len(rules), 0)

    def test_fail_closed_denies_on_exception(self):
        """fail_closed=True should DENY when check raises an exception."""
        guard = PermissionGuard(
            current_level=PermissionLevel.DEFAULT,
            fail_closed=True,
            audit_log=False,
        )
        # Force an exception by passing an action with an invalid action_type
        # that will cause _match_rule to fail. We use a mock approach.
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/tmp/test.txt",
            source_role_id="tester",
        )
        # Monkey-patch _check_impl to raise
        original = guard._check_impl
        guard._check_impl = lambda _a, _s: (_ for _ in ()).throw(RuntimeError("forced"))
        try:
            decision = guard.check(action)
            self.assertEqual(decision.outcome, DecisionOutcome.DENIED)
        finally:
            guard._check_impl = original


if __name__ == "__main__":
    unittest.main()
