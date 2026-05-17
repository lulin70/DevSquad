#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for AdaptiveRoleSelector module (V3.6.0)

Tests cover:
- Role selection based on similar historical tasks
- Intent-based role selection when no similar tasks found
- Fallback behavior returning empty list (defers to RoleMatcher)
- Manual statistics update functionality
- Comprehensive role effectiveness report generation
- Success rate filtering and threshold enforcement
- Max roles limit enforcement
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from scripts.collaboration.performance_fingerprint import PerformanceFingerprint
from scripts.collaboration.adaptive_role_selector import AdaptiveRoleSelector


class TestSelectWithSimilar:
    """Test role selection when similar tasks exist in history."""

    def test_select_returns_roles_from_successful_similar_tasks(self):
        """Should select roles from successful similar task history."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_similar_1")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Implement user authentication with JWT",
            result=MockResultSuccess(),
            timing={"total": 12.5, "planning": 2.0, "coding": 8.0, "review": 2.5},
            roles_used=["architect", "coder", "tester"],
            intent="feature_implementation",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles("Add JWT login system", max_roles=5)

        assert isinstance(roles, list)
        assert len(roles) > 0
        assert "architect" in roles or "coder" in roles or "tester" in roles

        fp.clear()

    def test_select_prioritizes_high_success_rate_combos(self):
        """Should prefer role combinations with higher success rates."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_similar_2")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        class MockResultFail:
            success = False
            error_message = "Timeout"
            error_type = "timeout"

        fp.record_execution(
            task="Build API endpoint successfully",
            result=MockResultSuccess(),
            timing={"total": 8.0},
            roles_used=["architect", "coder"],
            intent="api_development",
        )

        fp.record_execution(
            task="Failed API attempt",
            result=MockResultFail(),
            timing={"total": 20.0},
            roles_used=["coder"],
            intent="api_development",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles("Create new API endpoint", min_success_rate=0.5, max_roles=5)

        assert isinstance(roles, list)
        if roles:
            assert "architect" in roles or "coder" in roles

        fp.clear()

    def test_select_respects_max_roles_limit(self):
        """Should not return more roles than max_roles parameter."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_similar_3")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Complex multi-role task",
            result=MockResultSuccess(),
            timing={"total": 15.0},
            roles_used=["architect", "coder", "tester", "devops", "ui", "pm"],
            intent="complex_feature",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles("Another complex task", max_roles=3)

        assert len(roles) <= 3

        fp.clear()


class TestSelectByIntent:
    """Test intent-based role selection as fallback strategy."""

    def test_select_by_intent_when_no_similar_tasks(self):
        """Should use intent-based selection when no similar tasks found."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_intent_1")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Completely different task about cooking recipes",
            result=MockResultSuccess(),
            timing={"total": 10.0},
            roles_used=["tester", "qa"],
            intent="testing",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles(
            task="Quantum physics research project",
            intent="testing",
            min_success_rate=0.5,
            max_roles=5,
        )

        if roles:
            assert "tester" in roles or "qa" in roles

        fp.clear()

    def test_select_by_intent_finds_best_combo_for_intent(self):
        """Should find the most successful role combo for given intent."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_intent_2")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        class MockResultFail:
            success = False
            error_message = "Error"
            error_type = "runtime_error"

        fp.record_execution(
            task="Successful bug fix",
            result=MockResultSuccess(),
            timing={"total": 5.0},
            roles_used=["coder", "tester"],
            intent="bug_fix",
        )

        fp.record_execution(
            task="Failed bug fix attempt",
            result=MockResultFail(),
            timing={"total": 15.0},
            roles_used=["coder"],
            intent="bug_fix",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles(
            task="Unrelated new task",
            intent="bug_fix",
            min_success_rate=0.5,
            max_roles=5,
        )

        if roles:
            assert "coder" in roles or "tester" in roles

        fp.clear()

    def test_select_by_intent_no_match_returns_empty(self):
        """Should return empty list if no fingerprints match the intent."""
        import time
        fp = PerformanceFingerprint(persist_dir=f"/tmp/test_selector_intent_{int(time.time())}")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="Cooking recipe for chocolate cake with vanilla frosting",
            result=MockResultSuccess(),
            timing={"total": 8.0},
            roles_used=["coder"],
            intent="development",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles(
            task="Advanced quantum mechanics and theoretical physics research",
            intent="nonexistent_intent_category",
            min_success_rate=0.5,
            max_roles=5,
        )

        assert roles == []

        fp.clear()


class TestFallback:
    """Test fallback behavior when no data is available."""

    def test_fallback_empty_list_no_data(self):
        """Should return empty list when no historical data exists at all."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_fallback_1")
        selector = AdaptiveRoleSelector(fp)

        roles = selector.select_roles(
            task="Completely new task type",
            intent=None,
            min_success_rate=0.5,
            max_roles=5,
        )

        assert roles == []
        assert isinstance(roles, list)

        fp.clear()

    def test_fallback_below_threshold(self):
        """Should return empty list when all candidates below success rate threshold."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_fallback_2")

        class MockResultFail:
            success = False
            error_message = "Failed"
            error_type = "error"

        fp.record_execution(
            task="Failed task one",
            result=MockResultFail(),
            timing={"total": 10.0},
            roles_used=["coder"],
            intent="risky_task",
        )

        fp.record_execution(
            task="Failed task two",
            result=MockResultFail(),
            timing={"total": 12.0},
            roles_used=["coder", "tester"],
            intent="risky_task",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles(
            task="Similar risky task",
            intent="risky_task",
            min_success_rate=0.9,
            max_roles=5,
        )

        assert roles == []

        fp.clear()

    def test_fallback_allows_deferring_to_role_matcher(self):
        """Empty list returned allows caller to fall back to default RoleMatcher."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_fallback_3")
        selector = AdaptiveRoleSelector(fp)

        roles = selector.select_roles("Unknown task type")

        assert roles == []

        default_roles = ["architect", "coder"]
        final_roles = roles if roles else default_roles

        assert final_roles == ["architect", "coder"]

        fp.clear()


class TestUpdateStats:
    """Test manual statistics update functionality."""

    def test_update_stats_increments_counters(self):
        """Should increment total and successes counters correctly."""
        selector = AdaptiveRoleSelector()

        selector.update_stats(["architect", "coder"], True, 10.5)
        selector.update_stats(["architect", "coder"], False, 15.0)
        selector.update_stats(["tester"], True, 5.0)

        report = selector.get_role_report()

        assert report["architect"]["total"] == 2
        assert report["architect"]["successes"] == 1
        assert report["coder"]["total"] == 2
        assert report["coder"]["successes"] == 1
        assert report["tester"]["total"] == 1
        assert report["tester"]["successes"] == 1

    def test_update_stats_tracks_durations(self):
        """Should track duration data for average calculation."""
        selector = AdaptiveRoleSelector()

        selector.update_stats(["devops"], True, 8.0)
        selector.update_stats(["devops"], True, 12.0)
        selector.update_stats(["devops"], True, 6.0)

        report = selector.get_role_report()

        assert report["devops"]["avg_duration"] == 8.67  # (8+12+6)/3 = 8.67

    def test_update_stats_new_role_initialization(self):
        """Should initialize stats for new roles on first update."""
        selector = AdaptiveRoleSelector()

        selector.update_stats(["new_role_x"], True, 7.5)

        report = selector.get_role_report()

        assert "new_role_x" in report
        assert report["new_role_x"]["total"] == 1
        assert report["new_role_x"]["successes"] == 1
        assert report["new_role_x"]["success_rate"] == 1.0

    def test_update_stats_multiple_roles_single_call(self):
        """Should update all roles in a single call."""
        selector = AdaptiveRoleSelector()

        selector.update_stats(["role_a", "role_b", "role_c"], True, 20.0)

        report = selector.get_role_report()

        assert "role_a" in report
        assert "role_b" in report
        assert "role_c" in report
        assert report["role_a"]["total"] == 1
        assert report["role_b"]["total"] == 1
        assert report["role_c"]["total"] == 1


class TestRoleReport:
    """Test role effectiveness report generation."""

    def test_role_report_contains_required_fields(self):
        """Report should contain all required performance metrics."""
        selector = AdaptiveRoleSelector()

        selector.update_stats(["architect"], True, 10.0)
        selector.update_stats(["architect"], True, 8.0)
        selector.update_stats(["architect"], False, 25.0)

        report = selector.get_role_report()
        architect_stats = report["architect"]

        assert "total" in architect_stats
        assert "successes" in architect_stats
        assert "success_rate" in architect_stats
        assert "avg_duration" in architect_stats

        assert architect_stats["total"] == 3
        assert architect_stats["successes"] == 2
        assert architect_stats["success_rate"] == round(2/3, 4)

    def test_role_report_includes_fp_data(self):
        """Report should include data from fingerprint database."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_report_1")

        class MockResultSuccess:
            success = True
            error_message = None
            error_type = None

        fp.record_execution(
            task="FP-based task",
            result=MockResultSuccess(),
            timing={"total": 11.0},
            roles_used=["fp_role"],
            intent="test_intent",
        )

        selector = AdaptiveRoleSelector(fp)
        report = selector.get_role_report()

        assert "fp_role" in report
        assert report["fp_role"]["total"] >= 1

        fp.clear()

    def test_role_report_empty_state(self):
        """Report should be empty dict when no data available."""
        selector = AdaptiveRoleSelector()

        report = selector.get_role_report()

        assert isinstance(report, dict)
        assert len(report) == 0

    def test_role_report_success_rate_calculation(self):
        """Should calculate success rate accurately."""
        selector = AdaptiveRoleSelector()

        for i in range(8):
            selector.update_stats(["consistent_role"], True, 5.0)
        for i in range(2):
            selector.update_stats(["consistent_role"], False, 20.0)

        report = selector.get_role_report()

        assert report["consistent_role"]["success_rate"] == 0.8
        assert report["consistent_role"]["total"] == 10
        assert report["consistent_role"]["successes"] == 8


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_task_string(self):
        """Should handle empty task string gracefully."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_edge_1")
        selector = AdaptiveRoleSelector(fp)

        roles = selector.select_roles("", intent=None, max_roles=5)

        assert isinstance(roles, list)

        fp.clear()

    def test_zero_max_roles(self):
        """Should handle zero max_roles gracefully."""
        fp = PerformanceFingerprint(persist_dir="/tmp/test_selector_edge_2")
        selector = AdaptiveRoleSelector(fp)

        roles = selector.select_roles("Some task", max_roles=0)

        assert roles == []

        fp.clear()

    def test_very_high_min_success_rate(self):
        """Should return empty when threshold exceeds all available rates."""
        import time
        fp = PerformanceFingerprint(persist_dir=f"/tmp/test_selector_edge_{int(time.time())}")

        class MockResultFail:
            success = False
            error_message = "Failed"
            error_type = "error"

        fp.record_execution(
            task="Failed task one",
            result=MockResultFail(),
            timing={"total": 10.0},
            roles_used=["coder"],
            intent="moderate",
        )

        fp.record_execution(
            task="Failed task two",
            result=MockResultFail(),
            timing={"total": 12.0},
            roles_used=["coder"],
            intent="moderate",
        )

        selector = AdaptiveRoleSelector(fp)
        roles = selector.select_roles(
            "Task requiring high success rate but only failures exist",
            min_success_rate=0.5,
            max_roles=5,
        )

        assert roles == []

        fp.clear()

    def test_multiple_updates_same_role(self):
        """Should accumulate multiple updates for same role correctly."""
        selector = AdaptiveRoleSelector()

        for i in range(10):
            success = i % 3 != 0
            selector.update_stats(["frequent_role"], success, float(i + 1))

        report = selector.get_role_report()

        assert report["frequent_role"]["total"] == 10
        assert 0 < report["frequent_role"]["success_rate"] < 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
