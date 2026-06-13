"""Tests for TechDebtManager module."""

import json
import os
import tempfile

import pytest

from scripts.collaboration.tech_debt_manager import (
    DebtCategory,
    DebtEffort,
    DebtSeverity,
    DebtStatus,
    TechDebt,
    TechDebtManager,
)


class TestIdentifyDebt:
    """Tests for TechDebtManager.identify_debt."""

    def test_creates_debt_item(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY,
            "God class with 800 lines", "src/main.py",
        )
        assert debt.source == "tester"
        assert debt.category == DebtCategory.CODE_QUALITY
        assert debt.description == "God class with 800 lines"
        assert debt.location == "src/main.py"

    def test_default_severity_and_effort(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "architect", DebtCategory.ARCHITECTURE,
            "Circular dependency", "src/module_a.py",
        )
        assert debt.severity == DebtSeverity.MEDIUM
        assert debt.effort == DebtEffort.MODERATE

    def test_custom_severity_and_effort(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.SECURITY,
            "SQL injection vulnerability", "src/db.py",
            severity=DebtSeverity.CRITICAL,
            effort=DebtEffort.MINOR,
        )
        assert debt.severity == DebtSeverity.CRITICAL
        assert debt.effort == DebtEffort.MINOR

    def test_debt_has_unique_id(self):
        mgr = TechDebtManager()
        d1 = mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue 1", "a.py")
        d2 = mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue 2", "b.py")
        assert d1.id != d2.id

    def test_debt_default_status_is_identified(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt("tester", DebtCategory.TEST_GAP, "Missing tests", "test_foo.py")
        assert debt.status == DebtStatus.IDENTIFIED

    def test_debt_has_identified_at_timestamp(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue", "a.py")
        assert len(debt.identified_at) > 0

    def test_debt_stored_internally(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue 1", "a.py")
        mgr.identify_debt("architect", DebtCategory.ARCHITECTURE, "Issue 2", "b.py")
        assert len(mgr._debts) == 2


class TestScanCodebaseDebt:
    """Tests for TechDebtManager.scan_codebase_debt."""

    def _create_test_dir(self):
        """Create a temporary directory with sample Python files for scanning."""
        tmpdir = tempfile.mkdtemp()
        # File with TODO comment
        with open(os.path.join(tmpdir, "sample.py"), "w") as f:
            f.write("# TODO: refactor this later\n")
            f.write("# FIXME: this is broken\n")
            f.write("x = 1\n")
        # File with broad exception
        with open(os.path.join(tmpdir, "errors.py"), "w") as f:
            f.write("try:\n    pass\nexcept Exception:\n    pass\n")
        return tmpdir

    def test_scan_detects_todos(self):
        mgr = TechDebtManager()
        tmpdir = self._create_test_dir()
        try:
            debts = mgr.scan_codebase_debt(tmpdir)
            todo_debts = [d for d in debts if d.category == DebtCategory.CODE_QUALITY and "todo" in d.tags]
            assert len(todo_debts) > 0
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_scan_detects_broad_except(self):
        mgr = TechDebtManager()
        tmpdir = self._create_test_dir()
        try:
            debts = mgr.scan_codebase_debt(tmpdir)
            except_debts = [d for d in debts if "exception-handling" in d.tags]
            assert len(except_debts) > 0
        finally:
            import shutil
            shutil.rmtree(tmpdir)

    def test_scan_nonexistent_path_returns_empty(self):
        mgr = TechDebtManager()
        debts = mgr.scan_codebase_debt("/nonexistent/path/that/does/not/exist")
        assert debts == []

    def test_scan_adds_debts_to_manager(self):
        mgr = TechDebtManager()
        tmpdir = self._create_test_dir()
        try:
            mgr.scan_codebase_debt(tmpdir)
            assert len(mgr._debts) > 0
        finally:
            import shutil
            shutil.rmtree(tmpdir)


class TestPrioritize:
    """Tests for TechDebtManager.prioritize ordering."""

    def test_returns_sorted_by_priority(self):
        mgr = TechDebtManager()
        d_low = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Low issue", "a.py",
            severity=DebtSeverity.LOW, effort=DebtEffort.EPIC,
        )
        d_critical = mgr.identify_debt(
            "tester", DebtCategory.SECURITY, "Critical issue", "b.py",
            severity=DebtSeverity.CRITICAL, effort=DebtEffort.TRIVIAL,
        )
        prioritized = mgr.prioritize()
        assert prioritized[0].id == d_critical.id
        assert prioritized[-1].id == d_low.id

    def test_excludes_remediated_debts(self):
        mgr = TechDebtManager()
        d1 = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Active issue", "a.py",
            severity=DebtSeverity.HIGH,
        )
        d2 = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Fixed issue", "b.py",
            severity=DebtSeverity.HIGH,
        )
        mgr.track_remediation(d2.id, DebtStatus.REMEDIATED)
        prioritized = mgr.prioritize()
        ids = [d.id for d in prioritized]
        assert d1.id in ids
        assert d2.id not in ids

    def test_excludes_wont_fix_debts(self):
        mgr = TechDebtManager()
        d1 = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Active", "a.py",
            severity=DebtSeverity.MEDIUM,
        )
        d2 = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Wontfix", "b.py",
            severity=DebtSeverity.MEDIUM,
        )
        mgr.track_remediation(d2.id, DebtStatus.WONT_FIX)
        prioritized = mgr.prioritize()
        ids = [d.id for d in prioritized]
        assert d2.id not in ids

    def test_empty_manager_returns_empty(self):
        mgr = TechDebtManager()
        assert mgr.prioritize() == []


class TestGenerateRemediationPlan:
    """Tests for TechDebtManager.generate_remediation_plan within budget."""

    def test_plan_within_budget(self):
        mgr = TechDebtManager()
        mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Quick fix", "a.py",
            severity=DebtSeverity.LOW, effort=DebtEffort.TRIVIAL,
        )
        mgr.identify_debt(
            "tester", DebtCategory.SECURITY, "Security fix", "b.py",
            severity=DebtSeverity.HIGH, effort=DebtEffort.MINOR,
        )
        plan = mgr.generate_remediation_plan(budget_hours=40.0)
        assert plan.used_hours <= plan.budget_hours

    def test_tight_budget_defers_debts(self):
        mgr = TechDebtManager()
        mgr.identify_debt(
            "tester", DebtCategory.ARCHITECTURE, "Big refactor", "a.py",
            severity=DebtSeverity.HIGH, effort=DebtEffort.EPIC,
        )
        mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Small fix", "b.py",
            severity=DebtSeverity.LOW, effort=DebtEffort.TRIVIAL,
        )
        plan = mgr.generate_remediation_plan(budget_hours=1.0)
        # EPIC effort is 60h, won't fit in 1h budget
        assert len(plan.deferred_debts) > 0

    def test_plan_reflects_debt_reduction(self):
        mgr = TechDebtManager()
        mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Fix 1", "a.py",
            severity=DebtSeverity.MEDIUM, effort=DebtEffort.TRIVIAL,
        )
        plan = mgr.generate_remediation_plan(budget_hours=40.0)
        assert plan.debt_reduction_pct > 0

    def test_plan_to_dict(self):
        mgr = TechDebtManager()
        mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Fix", "a.py",
            severity=DebtSeverity.LOW, effort=DebtEffort.TRIVIAL,
        )
        plan = mgr.generate_remediation_plan(budget_hours=40.0)
        d = plan.to_dict()
        assert "total_debts" in d
        assert "budget_hours" in d
        assert "used_hours" in d


class TestTrackRemediation:
    """Tests for TechDebtManager.track_remediation status transitions."""

    def test_identified_to_acknowledged(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
        )
        mgr.track_remediation(debt.id, DebtStatus.ACKNOWLEDGED)
        assert debt.status == DebtStatus.ACKNOWLEDGED

    def test_acknowledged_to_scheduled(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
        )
        mgr.track_remediation(debt.id, DebtStatus.ACKNOWLEDGED)
        mgr.track_remediation(debt.id, DebtStatus.SCHEDULED)
        assert debt.status == DebtStatus.SCHEDULED

    def test_scheduled_to_in_progress(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
        )
        mgr.track_remediation(debt.id, DebtStatus.SCHEDULED)
        mgr.track_remediation(debt.id, DebtStatus.IN_PROGRESS)
        assert debt.status == DebtStatus.IN_PROGRESS

    def test_in_progress_to_remediated(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
        )
        mgr.track_remediation(debt.id, DebtStatus.IN_PROGRESS)
        mgr.track_remediation(debt.id, DebtStatus.REMEDIATED)
        assert debt.status == DebtStatus.REMEDIATED
        assert len(debt.remediated_at) > 0

    def test_identified_to_wont_fix(self):
        mgr = TechDebtManager()
        debt = mgr.identify_debt(
            "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
        )
        mgr.track_remediation(debt.id, DebtStatus.WONT_FIX)
        assert debt.status == DebtStatus.WONT_FIX

    def test_nonexistent_debt_id_no_error(self):
        mgr = TechDebtManager()
        # Should not raise
        mgr.track_remediation("nonexistent-id", DebtStatus.ACKNOWLEDGED)


class TestGetDebtReport:
    """Tests for TechDebtManager.get_debt_report."""

    def test_empty_report(self):
        mgr = TechDebtManager()
        report = mgr.get_debt_report()
        assert report.total_debts == 0

    def test_report_by_category(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue 1", "a.py")
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue 2", "b.py")
        mgr.identify_debt("tester", DebtCategory.SECURITY, "Issue 3", "c.py")
        report = mgr.get_debt_report()
        assert report.by_category.get("code_quality", 0) == 2
        assert report.by_category.get("security", 0) == 1

    def test_report_by_severity(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Low", "a.py",
                          severity=DebtSeverity.LOW)
        mgr.identify_debt("tester", DebtCategory.SECURITY, "Critical", "b.py",
                          severity=DebtSeverity.CRITICAL)
        report = mgr.get_debt_report()
        assert report.by_severity.get("low", 0) == 1
        assert report.by_severity.get("critical", 0) == 1

    def test_report_top_priority(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Low", "a.py",
                          severity=DebtSeverity.LOW, effort=DebtEffort.EPIC)
        mgr.identify_debt("tester", DebtCategory.SECURITY, "Critical", "b.py",
                          severity=DebtSeverity.CRITICAL, effort=DebtEffort.TRIVIAL)
        report = mgr.get_debt_report()
        assert len(report.top_priority) > 0
        assert report.top_priority[0].severity == DebtSeverity.CRITICAL

    def test_report_interest_forecast(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.SECURITY, "Issue", "a.py",
                          severity=DebtSeverity.HIGH)
        report = mgr.get_debt_report()
        assert len(report.interest_forecast) == 6

    def test_report_remediation_progress(self):
        mgr = TechDebtManager()
        d1 = mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Active", "a.py")
        d2 = mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Fixed", "b.py")
        mgr.track_remediation(d2.id, DebtStatus.REMEDIATED)
        report = mgr.get_debt_report()
        assert report.remediation_progress.get("identified", 0) >= 1
        assert report.remediation_progress.get("remediated", 0) >= 1

    def test_report_to_dict(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue", "a.py")
        report = mgr.get_debt_report()
        d = report.to_dict()
        assert "total_debts" in d
        assert "by_category" in d
        assert "by_severity" in d

    def test_report_to_markdown(self):
        mgr = TechDebtManager()
        mgr.identify_debt("tester", DebtCategory.CODE_QUALITY, "Issue", "a.py")
        report = mgr.get_debt_report()
        md = report.to_markdown()
        assert "Tech Debt Report" in md


class TestJsonPersistence:
    """Tests for TechDebtManager JSON persistence (save/load)."""

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create and save
            mgr1 = TechDebtManager(persist_dir=tmpdir)
            mgr1.identify_debt(
                "tester", DebtCategory.CODE_QUALITY, "Test issue", "a.py",
                severity=DebtSeverity.HIGH, effort=DebtEffort.MINOR,
            )
            mgr1.identify_debt(
                "architect", DebtCategory.ARCHITECTURE, "Structural issue", "b.py",
                severity=DebtSeverity.CRITICAL, effort=DebtEffort.MAJOR,
            )

            # Load in new instance
            mgr2 = TechDebtManager(persist_dir=tmpdir)
            assert len(mgr2._debts) == 2
            assert mgr2._debts[0].description == "Test issue"
            assert mgr2._debts[1].description == "Structural issue"

    def test_persistence_preserves_category(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = TechDebtManager(persist_dir=tmpdir)
            mgr1.identify_debt(
                "tester", DebtCategory.SECURITY, "Vuln", "c.py",
            )
            mgr2 = TechDebtManager(persist_dir=tmpdir)
            assert mgr2._debts[0].category == DebtCategory.SECURITY

    def test_persistence_preserves_severity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = TechDebtManager(persist_dir=tmpdir)
            mgr1.identify_debt(
                "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
                severity=DebtSeverity.CRITICAL,
            )
            mgr2 = TechDebtManager(persist_dir=tmpdir)
            assert mgr2._debts[0].severity == DebtSeverity.CRITICAL

    def test_persistence_preserves_status(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr1 = TechDebtManager(persist_dir=tmpdir)
            debt = mgr1.identify_debt(
                "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
            )
            mgr1.track_remediation(debt.id, DebtStatus.REMEDIATED)

            mgr2 = TechDebtManager(persist_dir=tmpdir)
            assert mgr2._debts[0].status == DebtStatus.REMEDIATED

    def test_persistence_file_format(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = TechDebtManager(persist_dir=tmpdir)
            mgr.identify_debt(
                "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
            )
            debt_file = os.path.join(tmpdir, "tech_debts.json")
            assert os.path.exists(debt_file)
            with open(debt_file) as f:
                data = json.load(f)
            assert "debts" in data
            assert "counter" in data
            assert len(data["debts"]) == 1

    def test_no_persist_dir_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = TechDebtManager()  # No persist_dir
            mgr.identify_debt(
                "tester", DebtCategory.CODE_QUALITY, "Issue", "a.py",
            )
            debt_file = os.path.join(tmpdir, "tech_debts.json")
            assert not os.path.exists(debt_file)

    def test_load_nonexistent_file_no_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise even if file doesn't exist
            mgr = TechDebtManager(persist_dir=tmpdir)
            assert len(mgr._debts) == 0
