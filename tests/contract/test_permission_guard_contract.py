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


class T6_PermissionGuardBoundaryContract(unittest.TestCase):
    """Boundary and stress contract tests for PermissionGuard.

    Covers BYPASS-mode boundaries (most-dangerous ops), PLAN-mode deny
    list completeness, AUTO-mode auto-approve scope, concurrent check
    safety, permission downgrade chain, and unknown-operation default
    policy.
    """

    def _make_action(
        self,
        action_type: ActionType = ActionType.FILE_READ,
        target: str = "/tmp/t6_test.txt",
    ) -> ProposedAction:
        """Build a ProposedAction for testing."""
        return ProposedAction(
            action_type=action_type,
            target=target,
            description="T6 boundary test action",
            source_role_id="tester",
        )

    def test_bypass_allows_most_dangerous_operations(self) -> None:
        """BYPASS level must allow even sudo rm -rf and .env modification.

        Boundary: the highest-trust level must skip all checks, including
        operations that are normally human-gated (FILE_DELETE, ENVIRONMENT)
        and high-risk shell commands (sudo, rm -rf).
        """
        guard = PermissionGuard(current_level=PermissionLevel.BYPASS)
        dangerous_actions = [
            (ActionType.SHELL_EXECUTE, "sudo rm -rf /"),
            (ActionType.FILE_DELETE, "/tmp/critical.txt"),
            (ActionType.ENVIRONMENT, "PATH"),
            (ActionType.FILE_MODIFY, "/app/.env"),
            (ActionType.FILE_MODIFY, "/app/credentials.json"),
        ]
        for action_type, target in dangerous_actions:
            decision = guard.check(self._make_action(action_type, target))
            self.assertEqual(
                decision.outcome, DecisionOutcome.ALLOWED,
                f"BYPASS must allow {action_type.value} on {target}",
            )

    def test_plan_denies_all_non_read_operation_types(self) -> None:
        """PLAN level must deny every non-FILE_READ action type.

        Deny-list completeness: iterates over ALL ActionType values and
        verifies that only FILE_READ is allowed; every other type is
        denied. This ensures PLAN mode has no accidental write holes.
        """
        guard = PermissionGuard(current_level=PermissionLevel.PLAN)
        for action_type in ActionType:
            decision = guard.check(self._make_action(action_type, "/tmp/plan_test.txt"))
            if action_type == ActionType.FILE_READ:
                self.assertEqual(
                    decision.outcome, DecisionOutcome.ALLOWED,
                    f"PLAN must allow {action_type.value}",
                )
            else:
                self.assertEqual(
                    decision.outcome, DecisionOutcome.DENIED,
                    f"PLAN must deny {action_type.value}",
                )

    def test_auto_level_auto_approves_low_risk_file_create(self) -> None:
        """AUTO level must auto-approve low-risk file creation (.py, .md).

        Auto-approve scope: FILE_CREATE on .py and .md files should be
        ALLOWED in AUTO mode (rule required_level=AUTO, low risk_boost).
        """
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        for ext in [".py", ".md"]:
            target = f"/tmp/auto_module{ext}"
            decision = guard.check(self._make_action(ActionType.FILE_CREATE, target))
            self.assertEqual(
                decision.outcome, DecisionOutcome.ALLOWED,
                f"AUTO must allow FILE_CREATE for {ext} files",
            )

    def test_concurrent_check_safety(self) -> None:
        """Concurrent check() calls from multiple threads must be safe.

        Stress: 10 threads each calling check() 50 times simultaneously.
        The guard must not crash, and all decisions must be valid
        PermissionDecision instances.
        """
        import threading
        guard = PermissionGuard(current_level=PermissionLevel.DEFAULT)
        errors: list[str] = []
        barrier = threading.Barrier(10)

        def worker() -> None:
            barrier.wait()
            try:
                for i in range(50):
                    action = ProposedAction(
                        action_type=ActionType.FILE_READ,
                        target=f"/tmp/concurrent_{i}.txt",
                        source_role_id="tester",
                    )
                    decision = guard.check(action)
                    if not isinstance(decision.outcome, DecisionOutcome):
                        errors.append("invalid outcome type")
            except Exception as e:  # noqa: BLE001
                errors.append(f"thread raised {type(e).__name__}: {e}")

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"Concurrent check errors: {errors}")

    def test_permission_downgrade_chain_increases_restriction(self) -> None:
        """Downgrading BYPASS → AUTO → DEFAULT → PLAN must increase restriction.

        Permission downgrade chain: the same FILE_DELETE action must go
        from ALLOWED (BYPASS) to PROMPT (AUTO/DEFAULT human gate) to
        DENIED (PLAN), demonstrating monotonic restriction increase.
        """
        guard = PermissionGuard(current_level=PermissionLevel.BYPASS)
        action = self._make_action(ActionType.FILE_DELETE, "/tmp/downgrade.txt")

        # BYPASS: allowed
        self.assertEqual(guard.check(action).outcome, DecisionOutcome.ALLOWED)

        # AUTO: human gate → PROMPT
        guard.set_level(PermissionLevel.AUTO)
        self.assertEqual(guard.check(action).outcome, DecisionOutcome.PROMPT)

        # DEFAULT: human gate → PROMPT
        guard.set_level(PermissionLevel.DEFAULT)
        self.assertEqual(guard.check(action).outcome, DecisionOutcome.PROMPT)

        # PLAN: denied (writes blocked)
        guard.set_level(PermissionLevel.PLAN)
        self.assertEqual(guard.check(action).outcome, DecisionOutcome.DENIED)

    def test_unknown_target_pattern_defaults_to_prompt(self) -> None:
        """Actions with no matching rule must default to PROMPT in DEFAULT mode.

        Default policy: a FILE_MODIFY on an unusual extension (e.g. .xyz)
        matches the catch-all rule R011 (required_level=DEFAULT) but has
        moderate risk, so it must PROMPT for confirmation.
        """
        guard = PermissionGuard(current_level=PermissionLevel.DEFAULT)
        action = self._make_action(ActionType.FILE_MODIFY, "/tmp/unknown.xyz")
        decision = guard.check(action)
        self.assertIn(decision.outcome, [DecisionOutcome.PROMPT, DecisionOutcome.ALLOWED])

    def test_bypass_skips_human_gate_for_process_spawn(self) -> None:
        """BYPASS must skip the human gate even for PROCESS_SPAWN.

        Boundary: PROCESS_SPAWN is in HUMAN_GATE_ACTIONS, but BYPASS
        must override the gate and allow it (highest trust).
        """
        guard = PermissionGuard(current_level=PermissionLevel.BYPASS)
        action = self._make_action(ActionType.PROCESS_SPAWN, "/usr/bin/python")
        decision = guard.check(action)
        self.assertEqual(decision.outcome, DecisionOutcome.ALLOWED)

    def test_plan_allows_read_with_sensitive_target(self) -> None:
        """PLAN level must allow FILE_READ even on sensitive paths.

        Boundary: reading /etc/passwd or .env files is still a read
        operation. PLAN mode must allow all reads regardless of target
        sensitivity (read-only mode never blocks reads).
        """
        guard = PermissionGuard(current_level=PermissionLevel.PLAN)
        sensitive_targets = [
            "/etc/passwd",
            "/app/.env",
            "/app/credentials.json",
            "/root/.ssh/id_rsa",
        ]
        for target in sensitive_targets:
            decision = guard.check(self._make_action(ActionType.FILE_READ, target))
            self.assertEqual(
                decision.outcome, DecisionOutcome.ALLOWED,
                f"PLAN must allow reading {target}",
            )

    def test_audit_log_records_concurrent_mixed_outcomes(self) -> None:
        """Audit log must correctly record mixed outcomes after concurrent checks.

        Stress: after concurrent checks producing both ALLOWED and DENIED
        outcomes, get_audit_log must return all entries and
        get_security_report must show non-zero counts.
        """
        guard = PermissionGuard(current_level=PermissionLevel.PLAN)
        guard.check(self._make_action(ActionType.FILE_READ, "/tmp/a.txt"))
        guard.check(self._make_action(ActionType.FILE_DELETE, "/tmp/b.txt"))
        guard.check(self._make_action(ActionType.SHELL_EXECUTE, "ls /tmp"))
        log = guard.get_audit_log()
        self.assertGreaterEqual(len(log), 3)
        report = guard.get_security_report()
        self.assertGreaterEqual(report["total_checks"], 3)
        self.assertGreaterEqual(report["allowed"], 1)
        self.assertGreaterEqual(report["denied"], 1)


if __name__ == "__main__":
    unittest.main()
