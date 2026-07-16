#!/usr/bin/env python3
"""
Tests for P1-3 triage — category + state dual-label with HITL/AFK.

Covers TriageLabel dataclass and triage_requirement() function.

Spec reference: V4.1.0 PRD P1-3 (Matt Pocock triage philosophy).
"""

import pytest

from scripts.collaboration.lifecycle_protocol import (
    TriageLabel,
    triage_requirement,
)


class TestTriageLabelDataclass:
    """Test the TriageLabel dataclass structure."""

    def test_triage_label_default_notes_empty(self):
        """TriageLabel defaults notes to an empty string."""
        label = TriageLabel(
            category="feature",
            state="new",
            execution_mode="AFK",
            priority="P2",
        )
        assert label.notes == ""

    def test_triage_label_all_fields_set(self):
        """TriageLabel accepts all fields including notes."""
        label = TriageLabel(
            category="bug",
            state="in_progress",
            execution_mode="HITL",
            priority="P0",
            notes="needs confirmation before deploy",
        )
        assert label.category == "bug"
        assert label.state == "in_progress"
        assert label.execution_mode == "HITL"
        assert label.priority == "P0"
        assert label.notes == "needs confirmation before deploy"


class TestTriageRequirementCategory:
    """Test category detection in triage_requirement()."""

    def test_triage_bug_chinese_quexian(self):
        """Chinese '缺陷' keyword yields bug category."""
        label = triage_requirement("修复登录页面的缺陷")
        assert label.category == "bug"

    def test_triage_bug_english_keyword(self):
        """English 'bug' keyword yields bug category."""
        label = triage_requirement("Fix the login bug")
        assert label.category == "bug"

    def test_triage_security_chinese_anquan(self):
        """Chinese '安全' keyword yields security category."""
        label = triage_requirement("检查系统安全漏洞")
        assert label.category == "security"

    def test_triage_security_english_keyword(self):
        """English 'security' keyword yields security category."""
        label = triage_requirement("Perform a security audit")
        assert label.category == "security"

    def test_triage_tech_debt_chinese_keyword(self):
        """Chinese '技术债' keyword yields tech_debt category."""
        label = triage_requirement("偿还技术债并重构模块")
        assert label.category == "tech_debt"

    def test_triage_tech_debt_english_keyword(self):
        """English 'tech debt' keyword yields tech_debt category."""
        label = triage_requirement("Pay off tech debt in the auth module")
        assert label.category == "tech_debt"

    def test_triage_feature_default(self):
        """No category keyword yields feature category."""
        label = triage_requirement("新增用户导出功能")
        assert label.category == "feature"

    def test_triage_security_takes_precedence_over_bug(self):
        """When both security and bug keywords present, security wins."""
        label = triage_requirement("security bug vulnerability")
        assert label.category == "security"


class TestTriageRequirementExecutionMode:
    """Test execution_mode (HITL/AFK) detection."""

    def test_triage_hitl_chinese_queren(self):
        """Chinese '确认' keyword yields HITL execution mode."""
        label = triage_requirement("新增功能，需要确认")
        assert label.execution_mode == "HITL"

    def test_triage_hitl_chinese_shenpi(self):
        """Chinese '审批' keyword yields HITL execution mode."""
        label = triage_requirement("发布功能，请审批")
        assert label.execution_mode == "HITL"

    def test_triage_hitl_english_confirm(self):
        """English 'confirm' keyword yields HITL execution mode."""
        label = triage_requirement("Confirm the deployment plan")
        assert label.execution_mode == "HITL"

    def test_triage_hitl_english_approve(self):
        """English 'approve' keyword yields HITL execution mode."""
        label = triage_requirement("Approve the release")
        assert label.execution_mode == "HITL"

    def test_triage_afk_default(self):
        """No HITL keyword yields AFK execution mode."""
        label = triage_requirement("新增用户导出功能")
        assert label.execution_mode == "AFK"


class TestTriageRequirementPriority:
    """Test priority detection."""

    def test_triage_priority_p0_chinese_jinji(self):
        """Chinese '紧急' keyword yields P0 priority."""
        label = triage_requirement("紧急修复线上故障")
        assert label.priority == "P0"

    def test_triage_priority_p0_english_urgent(self):
        """English 'urgent' keyword yields P0 priority."""
        label = triage_requirement("Urgent: fix the crash")
        assert label.priority == "P0"

    def test_triage_priority_p0_explicit_tag(self):
        """Explicit 'P0' tag yields P0 priority."""
        label = triage_requirement("P0: critical issue")
        assert label.priority == "P0"

    def test_triage_priority_p1_chinese_zhongyao(self):
        """Chinese '重要' keyword yields P1 priority."""
        label = triage_requirement("重要功能需要实现")
        assert label.priority == "P1"

    def test_triage_priority_p1_english_important(self):
        """English 'important' keyword yields P1 priority."""
        label = triage_requirement("Important feature to add")
        assert label.priority == "P1"

    def test_triage_priority_p2_default(self):
        """No priority keyword yields P2 priority."""
        label = triage_requirement("新增用户导出功能")
        assert label.priority == "P2"


class TestTriageRequirementState:
    """Test state field of freshly triaged requirements."""

    def test_triage_state_is_new_for_fresh_requirement(self):
        """A freshly triaged requirement has state 'new'."""
        label = triage_requirement("any requirement")
        assert label.state == "new"


class TestTriageRequirementEdgeCases:
    """Test edge cases and combined scenarios."""

    def test_triage_empty_string(self):
        """Empty string yields feature/AFK/P2 with state new."""
        label = triage_requirement("")
        assert label.category == "feature"
        assert label.execution_mode == "AFK"
        assert label.priority == "P2"
        assert label.state == "new"

    def test_triage_none_input(self):
        """None input is treated as empty and yields defaults."""
        label = triage_requirement(None)  # type: ignore[arg-type]
        assert label.category == "feature"
        assert label.execution_mode == "AFK"
        assert label.priority == "P2"

    def test_triage_case_insensitive(self):
        """Keyword detection is case-insensitive."""
        label = triage_requirement("SECURITY BUG URGENT")
        assert label.category == "security"
        assert label.priority == "P0"

    def test_triage_combined_hitl_and_priority(self):
        """A requirement needing approval and urgent is HITL+P0."""
        label = triage_requirement("紧急发布，需要审批确认")
        assert label.execution_mode == "HITL"
        assert label.priority == "P0"
        assert label.category == "feature"

    def test_triage_returns_triage_label_instance(self):
        """triage_requirement returns a TriageLabel instance."""
        label = triage_requirement("some requirement")
        assert isinstance(label, TriageLabel)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
