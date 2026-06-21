#!/usr/bin/env python3
"""
Tests for JudgeAgent (V3.8 #4) — Judge Agent + History Learning.

Coverage:
  - JudgeAction enum values
  - JudgeDecision / JudgeResult dataclasses (to_dict)
  - HistoryRecord dataclass (to_dict / from_dict)
  - Deduplication of identical findings
  - Deduplication of similar findings (text similarity)
  - Conflict resolution (two reviewers, different severities)
  - Confidence filtering (below threshold rejected)
  - History learning disabled by default
  - History learning enabled (records decisions)
  - History learning suggests based on past
  - JudgeResult summary
  - Various JudgeAction types
  - Integration with ReviewFinding
  - get_history_stats
  - Empty findings handling
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.judge_agent import (
    HistoryRecord,
    JudgeAction,
    JudgeAgent,
    JudgeDecision,
    JudgeResult,
)
from scripts.collaboration.two_stage_review_gate import (
    ReviewFinding,
    ReviewStage,
)


class TestJudgeActionEnum(unittest.TestCase):
    """Verify JudgeAction enum values."""

    def test_action_values(self) -> None:
        self.assertEqual(JudgeAction.ACCEPT.value, "accept")
        self.assertEqual(JudgeAction.REJECT.value, "reject")
        self.assertEqual(JudgeAction.MERGE.value, "merge")
        self.assertEqual(JudgeAction.DOWNGRADE.value, "downgrade")
        self.assertEqual(JudgeAction.UPGRADE.value, "upgrade")
        self.assertEqual(JudgeAction.DEFER.value, "defer")


class TestJudgeDecision(unittest.TestCase):
    """Verify JudgeDecision dataclass."""

    def test_to_dict_round_trip(self) -> None:
        decision = JudgeDecision(
            action=JudgeAction.MERGE,
            finding_ids=["id1", "id2"],
            rationale="Duplicate findings",
            confidence=0.9,
        )
        d = decision.to_dict()
        self.assertEqual(d["action"], "merge")
        self.assertEqual(d["finding_ids"], ["id1", "id2"])
        self.assertEqual(d["rationale"], "Duplicate findings")
        self.assertEqual(d["confidence"], 0.9)
        self.assertIsNone(d["merged_finding"])

    def test_to_dict_with_merged_finding(self) -> None:
        finding = ReviewFinding(
            ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
        )
        decision = JudgeDecision(
            action=JudgeAction.MERGE,
            finding_ids=["id1", "id2"],
            rationale="Merged",
            confidence=0.95,
            merged_finding=finding,
        )
        d = decision.to_dict()
        self.assertIsNotNone(d["merged_finding"])
        self.assertEqual(d["merged_finding"]["description"], "SQL injection")


class TestJudgeResult(unittest.TestCase):
    """Verify JudgeResult dataclass."""

    def test_to_dict_includes_all_fields(self) -> None:
        result = JudgeResult(
            decisions=[],
            accepted_findings=[],
            rejected_count=0,
            merged_count=0,
            deferred_count=0,
            history_used=False,
            summary="test",
        )
        d = result.to_dict()
        self.assertIn("decisions", d)
        self.assertIn("accepted_findings", d)
        self.assertIn("rejected_count", d)
        self.assertIn("merged_count", d)
        self.assertIn("deferred_count", d)
        self.assertIn("history_used", d)
        self.assertIn("summary", d)


class TestHistoryRecord(unittest.TestCase):
    """Verify HistoryRecord dataclass."""

    def test_to_dict_round_trip(self) -> None:
        record = HistoryRecord(
            finding_text="SQL injection",
            category="security",
            severity="critical",
            action="reject",
            human_override=True,
        )
        d = record.to_dict()
        self.assertEqual(d["finding_text"], "SQL injection")
        self.assertEqual(d["category"], "security")
        self.assertEqual(d["severity"], "critical")
        self.assertEqual(d["action"], "reject")
        self.assertTrue(d["human_override"])
        self.assertTrue(d["record_id"])
        self.assertTrue(d["timestamp"] > 0)

    def test_from_dict_round_trip(self) -> None:
        d = {
            "record_id": "abc-123",
            "finding_text": "xss",
            "category": "security",
            "severity": "high",
            "action": "accept",
            "human_override": False,
            "timestamp": 12345.0,
        }
        record = HistoryRecord.from_dict(d)
        self.assertEqual(record.record_id, "abc-123")
        self.assertEqual(record.finding_text, "xss")
        self.assertEqual(record.action, "accept")
        self.assertEqual(record.timestamp, 12345.0)

    def test_from_dict_with_missing_fields_uses_defaults(self) -> None:
        record = HistoryRecord.from_dict({"finding_text": "test"})
        self.assertEqual(record.finding_text, "test")
        self.assertEqual(record.category, "")
        self.assertEqual(record.action, "accept")
        self.assertFalse(record.human_override)
        self.assertTrue(record.record_id)  # auto-generated


class TestDeduplication(unittest.TestCase):
    """Verify deduplication logic."""

    def test_deduplication_of_identical_findings(self) -> None:
        """Deduplication of identical findings — should produce a MERGE decision."""
        judge = JudgeAgent(similarity_threshold=0.85)
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
        ]
        result = judge.judge(findings, context={})
        # One MERGE decision (with 2 finding IDs) + one REJECT for the duplicate.
        merge_decisions = [d for d in result.decisions if d.action == JudgeAction.MERGE]
        self.assertEqual(len(merge_decisions), 1)
        self.assertEqual(len(merge_decisions[0].finding_ids), 2)
        # Only one finding should be accepted.
        self.assertEqual(len(result.accepted_findings), 1)
        self.assertEqual(result.merged_count, 1)

    def test_deduplication_of_similar_findings(self) -> None:
        """Deduplication of similar findings (text similarity)."""
        judge = JudgeAgent(similarity_threshold=0.75)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security",
                "SQL injection vulnerability in login form"
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security",
                "SQL injection vulnerability in login form found by tester"
            ),
        ]
        result = judge.judge(findings, context={})
        # Should be detected as duplicates.
        merge_decisions = [d for d in result.decisions if d.action == JudgeAction.MERGE]
        self.assertEqual(len(merge_decisions), 1)
        self.assertEqual(len(result.accepted_findings), 1)

    def test_deduplication_does_not_merge_unrelated_findings(self) -> None:
        judge = JudgeAgent(similarity_threshold=0.85)
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "style", "Long line in foo.py",
                suggestion="Shorten the line",
            ),
        ]
        result = judge.judge(findings, context={})
        merge_decisions = [d for d in result.decisions if d.action == JudgeAction.MERGE]
        self.assertEqual(len(merge_decisions), 0)
        self.assertEqual(len(result.accepted_findings), 2)

    def test_deduplication_respects_category_mismatch(self) -> None:
        """Findings with different categories are not duplicates."""
        judge = JudgeAgent(similarity_threshold=0.5)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security",
                "Same description here"
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "style",
                "Same description here"
            ),
        ]
        result = judge.judge(findings, context={})
        merge_decisions = [d for d in result.decisions if d.action == JudgeAction.MERGE]
        self.assertEqual(len(merge_decisions), 0)


class TestConflictResolution(unittest.TestCase):
    """Verify conflict resolution logic."""

    def test_conflict_resolution_upgrades_severity(self) -> None:
        """Conflict resolution — two reviewers, different severities → upgrade."""
        judge = JudgeAgent(similarity_threshold=0.85)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "security",
                "SQL injection vulnerability in login"
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security",
                "SQL injection vulnerability in login"
            ),
        ]
        result = judge.judge(findings, context={})
        # An UPGRADE decision should be present.
        upgrade_decisions = [d for d in result.decisions if d.action == JudgeAction.UPGRADE]
        self.assertGreaterEqual(len(upgrade_decisions), 1)
        # Both accepted findings should now be critical.
        for f in result.accepted_findings:
            self.assertEqual(f.severity, "critical")


class TestConfidenceFiltering(unittest.TestCase):
    """Verify confidence filtering logic."""

    def test_low_confidence_findings_rejected(self) -> None:
        """Confidence filtering — below threshold rejected."""
        # Use a high threshold to force rejection of low-confidence findings.
        judge = JudgeAgent(confidence_threshold=0.95)
        # A finding with no suggestion and no file_path → confidence 0.5.
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "style", "Long line"
            ),
        ]
        result = judge.judge(findings, context={})
        reject_decisions = [d for d in result.decisions if d.action == JudgeAction.REJECT]
        self.assertGreaterEqual(len(reject_decisions), 1)
        self.assertEqual(len(result.accepted_findings), 0)
        self.assertGreater(result.rejected_count, 0)

    def test_critical_findings_always_kept(self) -> None:
        """Critical findings have confidence 1.0 — always kept."""
        judge = JudgeAgent(confidence_threshold=0.95)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
            ),
        ]
        result = judge.judge(findings, context={})
        self.assertEqual(len(result.accepted_findings), 1)

    def test_filter_by_confidence_legacy_method(self) -> None:
        """The legacy _filter_by_confidence method works."""
        judge = JudgeAgent(confidence_threshold=0.7)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "style", "Long line"
            ),
        ]
        decisions = judge._filter_by_confidence(findings, threshold=0.95)
        self.assertEqual(len(decisions), 1)
        self.assertEqual(decisions[0].action, JudgeAction.REJECT)


class TestHistoryLearningDisabled(unittest.TestCase):
    """Verify history learning is off by default."""

    def test_history_disabled_by_default(self) -> None:
        judge = JudgeAgent()
        self.assertFalse(judge.history_enabled)
        self.assertEqual(judge._history, [])

    def test_no_history_decisions_when_disabled(self) -> None:
        judge = JudgeAgent()
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
            ),
        ]
        result = judge.judge(findings, context={})
        self.assertFalse(result.history_used)

    def test_record_decision_is_noop_when_disabled(self) -> None:
        judge = JudgeAgent()
        decision = JudgeDecision(
            action=JudgeAction.ACCEPT,
            finding_ids=["id1"],
            rationale="ok",
        )
        # Should not raise and should not record anything.
        judge.record_decision(decision)
        self.assertEqual(judge._history, [])

    def test_get_history_stats_when_disabled(self) -> None:
        judge = JudgeAgent()
        stats = judge.get_history_stats()
        self.assertEqual(stats["total"], 0)
        self.assertFalse(stats["history_enabled"])


class TestHistoryLearningEnabled(unittest.TestCase):
    """Verify history learning when enabled."""

    def test_enable_history_learning_loads_existing_records(self) -> None:
        # Create a temp file with existing records.
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump([
                {
                    "record_id": "r1",
                    "finding_text": "SQL injection",
                    "category": "security",
                    "severity": "critical",
                    "action": "reject",
                    "human_override": False,
                    "timestamp": 1.0,
                }
            ], f)
            path = f.name
        try:
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            self.assertTrue(judge.history_enabled)
            self.assertEqual(len(judge._history), 1)
            self.assertEqual(judge._history[0].finding_text, "SQL injection")
        finally:
            os.unlink(path)

    def test_enable_history_learning_creates_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "subdir", "history.json")
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            self.assertTrue(judge.history_enabled)
            # File doesn't need to exist yet — it's created on save.
            self.assertEqual(len(judge._history), 0)

    def test_record_decision_persists_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            finding = ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
            )
            decision = JudgeDecision(
                action=JudgeAction.ACCEPT,
                finding_ids=["id1"],
                rationale="ok",
                merged_finding=finding,
            )
            judge.record_decision(decision)
            # Verify it was persisted.
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["finding_text"], "SQL injection")
            self.assertEqual(data[0]["action"], "accept")

    def test_history_learning_suggests_based_on_past(self) -> None:
        """History learning suggests based on past — DEFER for rejected past findings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            # Pre-populate history with a rejected finding.
            with open(path, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "record_id": "r1",
                        "finding_text": "SQL injection vulnerability in login",
                        "category": "security",
                        "severity": "critical",
                        "action": "reject",
                        "human_override": False,
                        "timestamp": 1.0,
                    }
                ], f)
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            # Judge a similar finding — should DEFER.
            findings = [
                ReviewFinding(
                    ReviewStage.CODE_QUALITY, "critical", "security",
                    "SQL injection vulnerability in login"
                ),
            ]
            result = judge.judge(findings, context={})
            self.assertTrue(result.history_used)
            defer_decisions = [d for d in result.decisions if d.action == JudgeAction.DEFER]
            self.assertGreaterEqual(len(defer_decisions), 1)
            self.assertGreaterEqual(result.deferred_count, 1)

    def test_history_learning_accept_suggestion_for_accepted_past(self) -> None:
        """When past finding was accepted, judge records an ACCEPT suggestion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "record_id": "r1",
                        "finding_text": "SQL injection vulnerability in login",
                        "category": "security",
                        "severity": "critical",
                        "action": "accept",
                        "human_override": False,
                        "timestamp": 1.0,
                    }
                ], f)
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            findings = [
                ReviewFinding(
                    ReviewStage.CODE_QUALITY, "critical", "security",
                    "SQL injection vulnerability in login"
                ),
            ]
            result = judge.judge(findings, context={})
            self.assertTrue(result.history_used)
            accept_decisions = [d for d in result.decisions if d.action == JudgeAction.ACCEPT]
            self.assertGreaterEqual(len(accept_decisions), 1)

    def test_get_history_stats_with_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            finding = ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
            )
            judge.record_decision(
                JudgeDecision(
                    action=JudgeAction.ACCEPT,
                    finding_ids=["id1"],
                    rationale="ok",
                    merged_finding=finding,
                )
            )
            judge.record_decision(
                JudgeDecision(
                    action=JudgeAction.REJECT,
                    finding_ids=["id2"],
                    rationale="dup",
                    merged_finding=finding,
                ),
                human_override=True,
            )
            stats = judge.get_history_stats()
            self.assertEqual(stats["total"], 2)
            self.assertEqual(stats["by_action"].get("accept"), 1)
            self.assertEqual(stats["by_action"].get("reject"), 1)
            self.assertEqual(stats["human_overrides"], 1)
            self.assertGreater(stats["human_override_rate"], 0)


class TestJudgeResultSummary(unittest.TestCase):
    """Verify JudgeResult summary content."""

    def test_summary_contains_key_info(self) -> None:
        judge = JudgeAgent()
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection"
            ),
        ]
        result = judge.judge(findings, context={})
        self.assertIn("JudgeAgent", result.summary)
        self.assertIn("accepted", result.summary)
        self.assertIn("Rejected", result.summary)
        self.assertIn("Merged", result.summary)

    def test_empty_findings_summary(self) -> None:
        judge = JudgeAgent()
        result = judge.judge([], context={})
        self.assertIn("no findings", result.summary)
        self.assertEqual(len(result.accepted_findings), 0)


class TestVariousJudgeActions(unittest.TestCase):
    """Verify various JudgeAction types are produced."""

    def test_merge_action_produced_for_duplicates(self) -> None:
        judge = JudgeAgent()
        findings = [
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "Same issue"),
            ReviewFinding(ReviewStage.CODE_QUALITY, "critical", "security", "Same issue"),
        ]
        result = judge.judge(findings, context={})
        actions = {d.action for d in result.decisions}
        self.assertIn(JudgeAction.MERGE, actions)

    def test_reject_action_produced_for_low_confidence(self) -> None:
        judge = JudgeAgent(confidence_threshold=0.95)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "style", "Long line"
            ),
        ]
        result = judge.judge(findings, context={})
        actions = {d.action for d in result.decisions}
        self.assertIn(JudgeAction.REJECT, actions)

    def test_upgrade_action_produced_for_conflict(self) -> None:
        judge = JudgeAgent(similarity_threshold=0.85)
        findings = [
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "security", "Same issue"
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "critical", "security", "Same issue"
            ),
        ]
        result = judge.judge(findings, context={})
        actions = {d.action for d in result.decisions}
        self.assertIn(JudgeAction.UPGRADE, actions)

    def test_defer_action_produced_with_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "history.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump([
                    {
                        "record_id": "r1",
                        "finding_text": "SQL injection vulnerability in login",
                        "category": "security",
                        "severity": "critical",
                        "action": "reject",
                        "human_override": False,
                        "timestamp": 1.0,
                    }
                ], f)
            judge = JudgeAgent()
            judge.enable_history_learning(path)
            findings = [
                ReviewFinding(
                    ReviewStage.CODE_QUALITY, "critical", "security",
                    "SQL injection vulnerability in login"
                ),
            ]
            result = judge.judge(findings, context={})
            actions = {d.action for d in result.decisions}
            self.assertIn(JudgeAction.DEFER, actions)


class TestIntegrationWithReviewFinding(unittest.TestCase):
    """Verify integration with ReviewFinding from TwoStageReviewGate."""

    def test_judge_accepts_review_findings_from_gate(self) -> None:
        """End-to-end: ReviewFinding objects flow through the judge."""
        judge = JudgeAgent()
        findings = [
            ReviewFinding(
                ReviewStage.SPEC_COMPLIANCE, "critical", "missing_file",
                "Planned file not found: src/auth.py",
                file_path="src/auth.py",
                suggestion="Create src/auth.py",
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "warning", "bare_except",
                "Bare except clause in src/foo.py",
                file_path="src/foo.py",
                suggestion="Catch specific exceptions",
            ),
            ReviewFinding(
                ReviewStage.CODE_QUALITY, "info", "note",
                "Consider adding docstrings",
            ),
        ]
        result = judge.judge(findings, context={})
        # All three should be accepted (critical=1.0, with suggestion=0.9,
        # info without suggestion/file → 0.5 → rejected at 0.7 threshold).
        # Actually: info without suggestion/file → 0.5 → rejected.
        # So accepted = 2 (critical + warning-with-suggestion).
        self.assertEqual(len(result.accepted_findings), 2)
        # The info finding should be rejected.
        self.assertGreater(result.rejected_count, 0)

    def test_judge_preserves_finding_attributes(self) -> None:
        """Accepted findings retain their original attributes."""
        judge = JudgeAgent()
        original = ReviewFinding(
            ReviewStage.CODE_QUALITY, "critical", "security", "SQL injection",
            file_path="src/db.py",
            line_range="10-20",
            suggestion="Use parameterized queries",
        )
        result = judge.judge([original], context={})
        self.assertEqual(len(result.accepted_findings), 1)
        accepted = result.accepted_findings[0]
        self.assertEqual(accepted.severity, "critical")
        self.assertEqual(accepted.category, "security")
        self.assertEqual(accepted.file_path, "src/db.py")
        self.assertEqual(accepted.line_range, "10-20")
        self.assertEqual(accepted.suggestion, "Use parameterized queries")


class TestTextSimilarity(unittest.TestCase):
    """Verify the text similarity helper."""

    def test_identical_strings_have_similarity_1(self) -> None:
        judge = JudgeAgent()
        self.assertEqual(
            judge._text_similarity("SQL injection", "SQL injection"),
            1.0,
        )

    def test_empty_strings_have_similarity_0(self) -> None:
        judge = JudgeAgent()
        self.assertEqual(judge._text_similarity("", "something"), 0.0)
        self.assertEqual(judge._text_similarity("something", ""), 0.0)

    def test_case_insensitive(self) -> None:
        judge = JudgeAgent()
        self.assertEqual(
            judge._text_similarity("SQL Injection", "sql injection"),
            1.0,
        )


if __name__ == "__main__":
    unittest.main()
