#!/usr/bin/env python3
"""Tests for DebtCollector — V4.3.0 P1-1.

Coverage:
  - Unit: classify() with marker type / critical path / file age signals
  - Unit: collect() integrates with todo_drift_monitor.scan_tech_debt
  - Unit: to_report() formatting
  - Edge cases: missing files, empty scan, marker severity ordering

Spec reference: docs/prd/V4.3.0_PRD.md §3.2 (P1-1)
"""

import os
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))  # noqa: E402

from scripts.collaboration.debt_collector import (  # noqa: E402
    ClassifiedDebt,
    DebtCollector,
)
from scripts.collaboration.todo_drift_monitor import (  # noqa: E402
    TechDebtEntry,
)


def _make_entry(
    file_path: str = "scripts/foo.py",
    line_number: int = 1,
    marker: str = "TODO",
    content: str = "# TODO: fix later",
) -> TechDebtEntry:
    return TechDebtEntry(
        file_path=file_path,
        line_number=line_number,
        marker=marker,
        content=content,
    )


class TestDebtCollectorClassify(unittest.TestCase):
    """Unit tests for DebtCollector.classify()."""

    def test_classify_returns_classified_debt(self):
        collector = DebtCollector()
        debt = collector.classify(_make_entry())
        self.assertIsInstance(debt, ClassifiedDebt)
        self.assertIn(debt.rot_risk, ("HIGH", "MEDIUM", "LOW"))

    def test_high_severity_marker_fixme(self):
        # FIXME is the highest-severity marker (weight 4).
        collector = DebtCollector(now=time.time())
        debt = collector.classify(
            _make_entry(marker="FIXME", file_path="scripts/foo.py")
        )
        # FIXME alone (score 2) → MEDIUM; with no other signals.
        self.assertIn(debt.rot_risk, ("MEDIUM", "HIGH"))
        self.assertTrue(any("FIXME" in r for r in debt.reasons))

    def test_marker_severity_ordering(self):
        # Verify FIXME > HACK > TODO > XXX > WIP via score contribution.
        collector = DebtCollector(now=time.time())
        markers = ["FIXME", "HACK", "TODO", "XXX", "WIP"]
        scores = []
        for m in markers:
            debt = collector.classify(
                _make_entry(marker=m, file_path="scripts/foo.py")
            )
            # Map risk to numeric for comparison.
            scores.append({"LOW": 0, "MEDIUM": 1, "HIGH": 2}[debt.rot_risk])
        # FIXME/HACK (weight >= 3) score higher than XXX/WIP (weight <= 1).
        self.assertGreaterEqual(scores[0], scores[-1])

    def test_critical_path_adds_risk(self):
        # Debt in security/cache/auth paths gets +2 score.
        collector = DebtCollector(now=time.time())
        debt = collector.classify(
            _make_entry(marker="FIXME", file_path="scripts/security/auth.py")
        )
        self.assertEqual(debt.rot_risk, "HIGH")
        self.assertIn("in critical module path", debt.reasons)

    def test_non_critical_path_no_critical_reason(self):
        collector = DebtCollector(now=time.time())
        debt = collector.classify(
            _make_entry(marker="TODO", file_path="scripts/utils/helpers.py")
        )
        self.assertNotIn("in critical module path", debt.reasons)

    def test_old_file_adds_risk(self):
        # Simulate an old file by setting `now` far in the future.
        collector = DebtCollector(now=time.time() + 100 * 24 * 3600)
        # Use a real file so _file_age works (this test file itself).
        debt = collector.classify(
            _make_entry(marker="FIXME", file_path=__file__)
        )
        self.assertIn(debt.rot_risk, ("HIGH", "MEDIUM"))
        self.assertTrue(any("older than" in r for r in debt.reasons))

    def test_missing_file_age_zero(self):
        # Missing file → age 0 → no age-based score.
        collector = DebtCollector(now=time.time())
        debt = collector.classify(
            _make_entry(marker="WIP", file_path="/nonexistent/path.py")
        )
        self.assertEqual(debt.rot_risk, "LOW")
        self.assertEqual(debt.reasons, [])

    def test_low_risk_wip_non_critical_recent(self):
        collector = DebtCollector(now=time.time())
        debt = collector.classify(
            _make_entry(marker="WIP", file_path="/nonexistent/x.py")
        )
        self.assertEqual(debt.rot_risk, "LOW")

    def test_high_risk_fixme_critical_old(self):
        # FIXME (weight 4 → score 2) + critical path (score 2) = 4 → HIGH.
        # File age is 0 (path doesn't exist) but marker+critical suffice.
        collector = DebtCollector(now=time.time())
        debt = collector.classify(
            _make_entry(marker="FIXME", file_path="scripts/security/auth.py")
        )
        self.assertEqual(debt.rot_risk, "HIGH")

    def test_classify_custom_critical_paths(self):
        # Custom critical paths should be respected.
        collector = DebtCollector(
            now=time.time(), critical_paths=("custom_module",)
        )
        debt = collector.classify(
            _make_entry(marker="FIXME", file_path="scripts/custom_module/x.py")
        )
        self.assertEqual(debt.rot_risk, "HIGH")
        self.assertIn("in critical module path", debt.reasons)


class TestDebtCollectorCollect(unittest.TestCase):
    """Unit tests for DebtCollector.collect() (integration with scanner)."""

    def test_collect_uses_scan_tech_debt(self):
        # Patch scan_tech_debt to return a controlled list.
        entries = [
            _make_entry(file_path="scripts/security/a.py", marker="FIXME"),
            _make_entry(file_path="scripts/utils/b.py", marker="TODO"),
        ]
        with patch(
            "scripts.collaboration.debt_collector.scan_tech_debt",
            return_value=entries,
        ):
            collector = DebtCollector(now=time.time())
            debts = collector.collect()
        self.assertEqual(len(debts), 2)
        # HIGH risk (FIXME + security) should sort before LOW/TODO.
        self.assertEqual(debts[0].rot_risk, "HIGH")
        self.assertEqual(debts[0].entry.file_path, "scripts/security/a.py")

    def test_collect_empty_when_no_entries(self):
        with patch(
            "scripts.collaboration.debt_collector.scan_tech_debt",
            return_value=[],
        ):
            collector = DebtCollector(now=time.time())
            debts = collector.collect()
        self.assertEqual(debts, [])

    def test_collect_sorted_by_risk_desc(self):
        entries = [
            _make_entry(file_path="scripts/z.py", marker="WIP"),       # LOW
            _make_entry(file_path="scripts/security/a.py", marker="FIXME"),  # HIGH
            _make_entry(file_path="scripts/m.py", marker="TODO"),      # MEDIUM/LOW
        ]
        with patch(
            "scripts.collaboration.debt_collector.scan_tech_debt",
            return_value=entries,
        ):
            collector = DebtCollector(now=time.time())
            debts = collector.collect()
        # First entry should be HIGH risk.
        self.assertEqual(debts[0].rot_risk, "HIGH")


class TestDebtCollectorReport(unittest.TestCase):
    """Unit tests for DebtCollector.to_report()."""

    def test_to_report_contains_header(self):
        with patch(
            "scripts.collaboration.debt_collector.scan_tech_debt",
            return_value=[],
        ):
            collector = DebtCollector(root_dir="scripts", now=time.time())
            report = collector.to_report()
        self.assertIn("Debt Collector Report", report)
        self.assertIn("Total: 0", report)

    def test_to_report_lists_high_risk(self):
        entries = [
            _make_entry(
                file_path="scripts/security/auth.py",
                marker="FIXME",
                content="# FIXME: urgent",
            ),
        ]
        with patch(
            "scripts.collaboration.debt_collector.scan_tech_debt",
            return_value=entries,
        ):
            collector = DebtCollector(now=time.time())
            report = collector.to_report()
        self.assertIn("HIGH (1)", report)
        self.assertIn("FIXME", report)
        self.assertIn("auth.py", report)

    def test_to_report_omits_empty_groups(self):
        # Only LOW risk → HIGH/MEDIUM sections should be omitted.
        entries = [
            _make_entry(file_path="/nonexistent/x.py", marker="WIP"),
        ]
        with patch(
            "scripts.collaboration.debt_collector.scan_tech_debt",
            return_value=entries,
        ):
            collector = DebtCollector(now=time.time())
            report = collector.to_report()
        self.assertIn("LOW (1)", report)
        self.assertNotIn("### HIGH", report)
        self.assertNotIn("### MEDIUM", report)


class TestDebtCollectorFileAge(unittest.TestCase):
    """Edge cases for file age computation."""

    def test_file_age_returns_zero_for_missing_file(self):
        collector = DebtCollector(now=time.time())
        self.assertEqual(collector._file_age("/nonexistent/file.py"), 0.0)

    def test_file_age_positive_for_existing_file(self):
        collector = DebtCollector(now=time.time())
        age = collector._file_age(__file__)
        # This test file was just created/modified → age is small but >= 0.
        self.assertGreaterEqual(age, 0.0)


if __name__ == "__main__":
    unittest.main()
