"""Tests for V4.2.1 P1-8 Human Gate Mapping.

Validates that PermissionGuard forces PROMPT for high-risk action types
(FILE_DELETE, PROCESS_SPAWN, ENVIRONMENT) regardless of PermissionLevel,
except BYPASS. Prevents AI from autonomously executing irreversible
operations (cf. Replit AI delete-db incident).
"""

from scripts.collaboration.permission_guard import (
    ActionType,
    DecisionOutcome,
    PermissionGuard,
    PermissionLevel,
    ProposedAction,
)


class TestHumanGate:
    """V4.2.1 P1-8: Human gate for irreversible operations."""

    def test_file_delete_prompts_in_default(self):
        """FILE_DELETE → PROMPT in DEFAULT mode."""
        guard = PermissionGuard(current_level=PermissionLevel.DEFAULT)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
            description="Delete temp file",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.PROMPT
        assert "Human gate" in decision.reason
        assert decision.requires_confirmation is True

    def test_file_delete_prompts_in_auto(self):
        """FILE_DELETE → PROMPT even in AUTO mode (AI cannot auto-approve)."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.PROMPT

    def test_process_spawn_prompts_in_auto(self):
        """PROCESS_SPAWN → PROMPT in AUTO mode."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.PROCESS_SPAWN,
            target="python script.py",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.PROMPT

    def test_environment_prompts_in_auto(self):
        """ENVIRONMENT → PROMPT in AUTO mode."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.ENVIRONMENT,
            target="PATH",
            description="Set PATH variable",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.PROMPT

    def test_bypass_skips_human_gate(self):
        """BYPASS mode skips human gate (highest trust, controlled env)."""
        guard = PermissionGuard(current_level=PermissionLevel.BYPASS)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.ALLOWED

    def test_plan_denies_human_gate_actions(self):
        """PLAN mode denies all writes (including human-gate actions)."""
        guard = PermissionGuard(current_level=PermissionLevel.PLAN)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
        )
        decision = guard.check(action)
        # PLAN denies all non-read operations before human gate check
        assert decision.outcome == DecisionOutcome.DENIED

    def test_file_create_not_gated(self):
        """FILE_CREATE is NOT in human gate — normal rule applies."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.FILE_CREATE,
            target="new_module.py",
        )
        decision = guard.check(action)
        # Should NOT be forced to PROMPT by human gate
        assert decision.outcome != DecisionOutcome.PROMPT or "Human gate" not in decision.reason

    def test_file_modify_not_gated(self):
        """FILE_MODIFY is NOT in human gate — normal rule applies."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.FILE_MODIFY,
            target="existing.py",
        )
        decision = guard.check(action)
        assert "Human gate" not in decision.reason

    def test_file_read_not_gated(self):
        """FILE_READ is NOT in human gate — always allowed in non-PLAN."""
        guard = PermissionGuard(current_level=PermissionLevel.DEFAULT)
        action = ProposedAction(
            action_type=ActionType.FILE_READ,
            target="/etc/hosts",
        )
        decision = guard.check(action)
        assert decision.outcome == DecisionOutcome.ALLOWED

    def test_shell_execute_not_gated(self):
        """SHELL_EXECUTE is NOT in human gate — normal risk assessment applies."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.SHELL_EXECUTE,
            target="ls -la",
        )
        decision = guard.check(action)
        # ls is low-risk, should be allowed
        assert decision.outcome == DecisionOutcome.ALLOWED

    def test_human_gate_actions_set(self):
        """HUMAN_GATE_ACTIONS contains exactly 3 irreversible types."""
        expected = {
            ActionType.FILE_DELETE,
            ActionType.PROCESS_SPAWN,
            ActionType.ENVIRONMENT,
        }
        assert expected == PermissionGuard.HUMAN_GATE_ACTIONS

    def test_audit_log_records_human_gate(self):
        """Human gate decisions are recorded in audit log."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO, audit_log=True)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
        )
        guard.check(action)
        entries = guard.get_audit_log(outcome=DecisionOutcome.PROMPT)
        assert len(entries) == 1
        assert "Human gate" in entries[0].decision.reason

    def test_whitelist_does_not_bypass_human_gate(self):
        """Whitelist does NOT bypass human gate (safety override)."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        guard.add_whitelist("/tmp/*")
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
        )
        decision = guard.check(action)
        # Even though /tmp/* is whitelisted, human gate takes priority
        assert decision.outcome == DecisionOutcome.PROMPT
        assert "Human gate" in decision.reason

    def test_high_risk_score_set(self):
        """Human gate actions set risk_score to 0.9."""
        guard = PermissionGuard(current_level=PermissionLevel.AUTO)
        action = ProposedAction(
            action_type=ActionType.FILE_DELETE,
            target="/tmp/test.txt",
        )
        guard.check(action)
        assert action.risk_score == 0.9
