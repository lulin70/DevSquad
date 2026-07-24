#!/usr/bin/env python3
"""
TechDebtProvider Contract Tests

Validates that all TechDebtProvider implementations conform to the Protocol
interface defined in protocols.py.

TechDebtManager (real implementation) has identify_debt, scan_codebase_debt,
prioritize, and get_debt_report but does NOT currently implement is_available() —
this gap is documented by test_tech_debt_manager_missing_is_available.

Contract test ownership: shared between DevSquad and tech debt management teams.
Any breaking change to TechDebtProvider Protocol must be negotiated.
"""

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.protocols import TechDebtProvider


class TestTechDebtProviderProtocolDefinition(unittest.TestCase):
    """Verify the TechDebtProvider Protocol definition itself is well-formed."""

    def test_protocol_has_identify_debt(self):
        self.assertTrue(hasattr(TechDebtProvider, "identify_debt"))

    def test_protocol_has_scan_codebase_debt(self):
        self.assertTrue(hasattr(TechDebtProvider, "scan_codebase_debt"))

    def test_protocol_has_prioritize(self):
        self.assertTrue(hasattr(TechDebtProvider, "prioritize"))

    def test_protocol_has_get_debt_report(self):
        self.assertTrue(hasattr(TechDebtProvider, "get_debt_report"))

    def test_protocol_has_is_available(self):
        self.assertTrue(hasattr(TechDebtProvider, "is_available"))


class _MinimalTechDebtProvider:
    """Minimal structurally-compatible implementation for subtyping verification."""

    def identify_debt(self, source: str, category: Any, description: str, location: str, **kwargs: Any) -> Any:  # noqa: ARG002
        return {"id": 1}

    def scan_codebase_debt(self, project_path: str) -> list[Any]:  # noqa: ARG002
        return []

    def prioritize(self) -> list[Any]:
        return []

    def get_debt_report(self) -> Any:
        return {"total": 0}

    def is_available(self) -> bool:
        return True


class TestTechDebtProviderStructuralSubtyping(unittest.TestCase):
    """Verify any class with the right methods satisfies TechDebtProvider structurally."""

    def test_minimal_implementation_is_instance_of_protocol(self):
        """A class implementing all methods should satisfy runtime_checkable isinstance."""
        self.assertIsInstance(_MinimalTechDebtProvider(), TechDebtProvider)

    def test_missing_method_fails_isinstance(self):
        """A class missing a method should NOT satisfy isinstance."""

        class IncompleteProvider:
            def identify_debt(self, source, category, description, location, **kwargs):  # noqa: ARG002
                return {}

            def scan_codebase_debt(self, project_path: str) -> list:  # noqa: ARG002
                return []

            def prioritize(self) -> list:
                return []

            def get_debt_report(self):
                return {}

            # Missing is_available

        self.assertNotIsInstance(IncompleteProvider(), TechDebtProvider)


class TestTechDebtManagerContractGap(unittest.TestCase):
    """Document the known gap: TechDebtManager does not implement is_available().

    TechDebtManager has 4/5 TechDebtProvider methods (identify_debt,
    scan_codebase_debt, prioritize, get_debt_report) but is missing
    is_available(). This test documents the gap so it can be tracked.
    """

    def test_tech_debt_manager_has_identify_debt(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "identify_debt"))

    def test_tech_debt_manager_has_scan_codebase_debt(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "scan_codebase_debt"))

    def test_tech_debt_manager_has_prioritize(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "prioritize"))

    def test_tech_debt_manager_has_get_debt_report(self):
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertTrue(hasattr(TechDebtManager, "get_debt_report"))

    def test_tech_debt_manager_missing_is_available(self):
        """Document: TechDebtManager does NOT implement is_available().

        This is a known gap. When fixed, this test should be updated to
        verify TechDebtManager fully satisfies TechDebtProvider.
        """
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        self.assertFalse(
            hasattr(TechDebtManager, "is_available"),
            "TechDebtManager now has is_available() — update this test to verify full Protocol compliance",
        )


class TestTechDebtManagerExtendedContract(unittest.TestCase):
    """Extended contract tests for TechDebtManager covering all 4 Protocol methods.

    Dimensions: Happy / Error / Boundary / Config / Integration
    """

    def _get_manager(self):
        """Return a fresh TechDebtManager (no persistence) for isolation."""
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        return TechDebtManager()

    # ------------------------------------------------------------------
    # Happy: identify_debt
    # ------------------------------------------------------------------

    def test_identify_debt_returns_tech_debt(self):
        """identify_debt must return a TechDebt instance with all fields set."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtEffort,
            DebtSeverity,
            TechDebt,
            TechDebtManager,
        )

        manager = TechDebtManager()
        debt = manager.identify_debt(
            source="tester",
            category=DebtCategory.CODE_QUALITY,
            description="God class with 800 lines",
            location="src/main.py",
            severity=DebtSeverity.HIGH,
            effort=DebtEffort.MAJOR,
            tags=["god-class", "complexity"],
        )
        self.assertIsInstance(debt, TechDebt)
        self.assertEqual(debt.source, "tester")
        self.assertEqual(debt.category, DebtCategory.CODE_QUALITY)
        self.assertEqual(debt.description, "God class with 800 lines")
        self.assertEqual(debt.location, "src/main.py")
        self.assertEqual(debt.severity, DebtSeverity.HIGH)
        self.assertEqual(debt.effort, DebtEffort.MAJOR)
        self.assertEqual(debt.tags, ["god-class", "complexity"])

    def test_identify_debt_generates_unique_id(self):
        """Each identify_debt call must produce a unique debt id."""
        from scripts.collaboration.tech_debt_manager import DebtCategory

        manager = self._get_manager()
        d1 = manager.identify_debt("s1", DebtCategory.CODE_QUALITY, "d1", "f1.py")
        d2 = manager.identify_debt("s2", DebtCategory.CODE_QUALITY, "d2", "f2.py")
        self.assertNotEqual(d1.id, d2.id)
        self.assertTrue(d1.id.startswith("debt-"))
        self.assertTrue(d2.id.startswith("debt-"))

    def test_identify_debt_defaults_severity_and_effort(self):
        """identify_debt should default severity=MEDIUM, effort=MODERATE, tags=[]."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtEffort,
            DebtSeverity,
        )

        manager = self._get_manager()
        debt = manager.identify_debt(
            source="architect",
            category=DebtCategory.ARCHITECTURE,
            description="circular dep",
            location="mod/__init__.py",
        )
        self.assertEqual(debt.severity, DebtSeverity.MEDIUM)
        self.assertEqual(debt.effort, DebtEffort.MODERATE)
        self.assertEqual(debt.tags, [])

    def test_identify_debt_sets_interest_rate_from_category(self):
        """identify_debt should auto-assign interest_rate based on category."""
        from scripts.collaboration.tech_debt_manager import (
            CATEGORY_INTEREST_RATE,
            DebtCategory,
        )

        manager = self._get_manager()
        debt = manager.identify_debt(
            source="s",
            category=DebtCategory.SECURITY,
            description="missing auth",
            location="api/login",
        )
        self.assertEqual(debt.interest_rate, CATEGORY_INTEREST_RATE[DebtCategory.SECURITY])

    # ------------------------------------------------------------------
    # Error: scan_codebase_debt
    # ------------------------------------------------------------------

    def test_scan_codebase_debt_nonexistent_path_returns_empty(self):
        """scan_codebase_debt on a non-existent path must return [] (no exception)."""
        manager = self._get_manager()
        result = manager.scan_codebase_debt("/nonexistent/path/does/not/exist")
        self.assertEqual(result, [])

    def test_scan_codebase_debt_empty_directory_returns_empty(self):
        """scan_codebase_debt on an empty directory must return []."""
        import tempfile

        manager = self._get_manager()
        with tempfile.TemporaryDirectory() as tmp:
            result = manager.scan_codebase_debt(tmp)
            self.assertEqual(result, [])

    def test_scan_codebase_debt_detects_todos(self):
        """scan_codebase_debt must detect TODO/FIXME comments in a Python file."""
        import tempfile
        from pathlib import Path

        from scripts.collaboration.tech_debt_manager import DebtCategory

        manager = self._get_manager()
        with tempfile.TemporaryDirectory() as tmp:
            py_file = Path(tmp) / "mod.py"
            py_file.write_text(
                "# TODO: refactor this\n"
                "# FIXME: bug here\n"
                "def hello():\n"
                "    pass\n",
                encoding="utf-8",
            )
            debts = manager.scan_codebase_debt(tmp)
            categories = {d.category for d in debts}
            self.assertIn(DebtCategory.CODE_QUALITY, categories)
            todo_debts = [d for d in debts if "TODO" in d.description or "FIXME" in d.description]
            self.assertGreaterEqual(len(todo_debts), 2)

    # ------------------------------------------------------------------
    # Happy: prioritize
    # ------------------------------------------------------------------

    def test_prioritize_returns_sorted_by_priority_desc(self):
        """prioritize() must return debts sorted by priority_score descending."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtEffort,
            DebtSeverity,
        )

        manager = self._get_manager()
        # Low severity + epic effort -> low priority
        manager.identify_debt(
            "s", DebtCategory.DOCUMENTATION, "low", "f1",
            severity=DebtSeverity.LOW, effort=DebtEffort.EPIC,
        )
        # Critical + trivial -> high priority
        manager.identify_debt(
            "s", DebtCategory.SECURITY, "critical", "f2",
            severity=DebtSeverity.CRITICAL, effort=DebtEffort.TRIVIAL,
        )
        prioritized = manager.prioritize()
        self.assertGreaterEqual(len(prioritized), 2)
        # Verify sorted descending
        scores = [d.priority_score for d in prioritized]
        self.assertEqual(scores, sorted(scores, reverse=True))
        # Critical+trivial should rank first
        self.assertEqual(prioritized[0].severity, DebtSeverity.CRITICAL)

    def test_prioritize_excludes_remediated_and_wont_fix(self):
        """prioritize() must exclude REMEDIATED and WONT_FIX debts."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtStatus,
        )

        manager = self._get_manager()
        d1 = manager.identify_debt("s", DebtCategory.CODE_QUALITY, "active", "f1")
        d2 = manager.identify_debt("s", DebtCategory.CODE_QUALITY, "remediated", "f2")
        d3 = manager.identify_debt("s", DebtCategory.CODE_QUALITY, "wontfix", "f3")
        manager.track_remediation(d2.id, DebtStatus.REMEDIATED)
        manager.track_remediation(d3.id, DebtStatus.WONT_FIX)
        prioritized = manager.prioritize()
        active_ids = {d.id for d in prioritized}
        self.assertIn(d1.id, active_ids)
        self.assertNotIn(d2.id, active_ids)
        self.assertNotIn(d3.id, active_ids)

    def test_prioritize_empty_returns_empty(self):
        """prioritize() on a manager with no debts must return []."""
        manager = self._get_manager()
        self.assertEqual(manager.prioritize(), [])

    # ------------------------------------------------------------------
    # Happy: get_debt_report
    # ------------------------------------------------------------------

    def test_get_debt_report_returns_debt_report(self):
        """get_debt_report() must return a DebtReport instance."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtReport,
        )

        manager = self._get_manager()
        manager.identify_debt("s", DebtCategory.CODE_QUALITY, "d1", "f1")
        report = manager.get_debt_report()
        self.assertIsInstance(report, DebtReport)
        self.assertEqual(report.total_debts, 1)

    def test_get_debt_report_groups_by_category_and_severity(self):
        """get_debt_report must populate by_category and by_severity dicts."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtSeverity,
        )

        manager = self._get_manager()
        manager.identify_debt(
            "s", DebtCategory.SECURITY, "vuln1", "f1", severity=DebtSeverity.HIGH
        )
        manager.identify_debt(
            "s", DebtCategory.SECURITY, "vuln2", "f2", severity=DebtSeverity.CRITICAL
        )
        manager.identify_debt(
            "s", DebtCategory.TEST_GAP, "no test", "f3", severity=DebtSeverity.MEDIUM
        )
        report = manager.get_debt_report()
        self.assertEqual(report.by_category.get("security"), 2)
        self.assertEqual(report.by_category.get("test_gap"), 1)
        self.assertEqual(report.by_severity.get("high"), 1)
        self.assertEqual(report.by_severity.get("critical"), 1)
        self.assertEqual(report.by_severity.get("medium"), 1)

    def test_get_debt_report_includes_interest_forecast(self):
        """get_debt_report must include a 6-month interest_forecast dict."""
        from scripts.collaboration.tech_debt_manager import DebtCategory

        manager = self._get_manager()
        manager.identify_debt("s", DebtCategory.ARCHITECTURE, "d1", "f1")
        report = manager.get_debt_report()
        self.assertIsInstance(report.interest_forecast, dict)
        self.assertEqual(len(report.interest_forecast), 6)
        # Forecast should be non-decreasing month over month
        values = list(report.interest_forecast.values())
        for i in range(1, len(values)):
            self.assertGreaterEqual(values[i], values[i - 1])

    # ------------------------------------------------------------------
    # Boundary: empty report
    # ------------------------------------------------------------------

    def test_get_debt_report_empty_manager(self):
        """get_debt_report on an empty manager must return zeros, not crash."""
        manager = self._get_manager()
        report = manager.get_debt_report()
        self.assertEqual(report.total_debts, 0)
        self.assertEqual(report.by_category, {})
        self.assertEqual(report.by_severity, {})
        self.assertEqual(report.top_priority, [])
        self.assertEqual(report.debt_to_value_ratio, 0.0)

    # ------------------------------------------------------------------
    # Config: persistence
    # ------------------------------------------------------------------

    def test_persistence_round_trip(self):
        """identify_debt with persist_dir must save and reload debts."""
        import tempfile
        from pathlib import Path

        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            TechDebtManager,
        )

        with tempfile.TemporaryDirectory() as tmp:
            m1 = TechDebtManager(persist_dir=tmp)
            m1.identify_debt("s", DebtCategory.CODE_QUALITY, "persist me", "f1.py")
            self.assertTrue((Path(tmp) / "tech_debts.json").exists())

            m2 = TechDebtManager(persist_dir=tmp)
            self.assertEqual(len(m2._debts), 1)
            self.assertEqual(m2._debts[0].description, "persist me")

    def test_persistence_corrupt_file_does_not_crash(self):
        """A corrupt tech_debts.json must not crash load; debts start empty."""
        import tempfile
        from pathlib import Path

        from scripts.collaboration.tech_debt_manager import TechDebtManager

        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "tech_debts.json").write_text("not valid json{", encoding="utf-8")
            m = TechDebtManager(persist_dir=tmp)
            self.assertEqual(len(m._debts), 0)

    # ------------------------------------------------------------------
    # Integration: identify_debt -> prioritize -> report
    # ------------------------------------------------------------------

    def test_full_workflow_identify_prioritize_report(self):
        """Full workflow: identify multiple debts, prioritize, generate report.

        Priority formula: severity_weight * (1/effort_hours) + interest_rate.
        With uniform effort, severity becomes the differentiator so CRITICAL
        debts rank above HIGH.
        """
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtEffort,
            DebtSeverity,
        )

        manager = self._get_manager()
        # All MODERATE effort (10h) so severity is the differentiator.
        manager.identify_debt(
            "tester", DebtCategory.TEST_GAP, "no tests for module A", "a.py",
            severity=DebtSeverity.HIGH, effort=DebtEffort.MODERATE,
        )
        manager.identify_debt(
            "architect", DebtCategory.ARCHITECTURE, "circular import X->Y->X", "core/",
            severity=DebtSeverity.CRITICAL, effort=DebtEffort.MODERATE,
        )
        manager.identify_debt(
            "tester", DebtCategory.SECURITY, "SQL injection in search", "api/search.py",
            severity=DebtSeverity.CRITICAL, effort=DebtEffort.MODERATE,
        )
        prioritized = manager.prioritize()
        self.assertEqual(len(prioritized), 3)
        # With uniform effort, CRITICAL outranks HIGH. SECURITY (interest=1.0)
        # ranks above ARCHITECTURE (interest=0.8).
        self.assertEqual(prioritized[0].severity, DebtSeverity.CRITICAL)
        self.assertEqual(prioritized[1].severity, DebtSeverity.CRITICAL)
        self.assertEqual(prioritized[2].severity, DebtSeverity.HIGH)
        self.assertEqual(prioritized[0].category, DebtCategory.SECURITY)
        self.assertEqual(prioritized[1].category, DebtCategory.ARCHITECTURE)

        report = manager.get_debt_report()
        self.assertEqual(report.total_debts, 3)
        self.assertEqual(len(report.top_priority), 3)
        # Top priority must match prioritized order
        self.assertEqual(report.top_priority[0].id, prioritized[0].id)

    # ------------------------------------------------------------------
    # Boundary: TechDebt serialization round-trip
    # ------------------------------------------------------------------

    def test_tech_debt_to_dict_from_dict_round_trip(self):
        """TechDebt.to_dict() -> from_dict() must preserve all fields."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtEffort,
            DebtSeverity,
            TechDebt,
        )

        original = TechDebt(
            id="debt-test123",
            source="static_analysis",
            category=DebtCategory.PERFORMANCE,
            description="N+1 query in user list",
            location="api/users.py:42",
            severity=DebtSeverity.HIGH,
            effort=DebtEffort.MODERATE,
            tags=["database", "n+1"],
        )
        d = original.to_dict()
        restored = TechDebt.from_dict(d)
        self.assertEqual(restored.id, original.id)
        self.assertEqual(restored.category, original.category)
        self.assertEqual(restored.severity, original.severity)
        self.assertEqual(restored.effort, original.effort)
        self.assertEqual(restored.description, original.description)
        self.assertEqual(restored.tags, original.tags)

    # ------------------------------------------------------------------
    # Happy: track_remediation
    # ------------------------------------------------------------------

    def test_track_remediation_sets_status_and_remediated_at(self):
        """track_remediation(REMEDIATED) must set status and remediated_at timestamp."""
        from scripts.collaboration.tech_debt_manager import (
            DebtCategory,
            DebtStatus,
        )

        manager = self._get_manager()
        debt = manager.identify_debt("s", DebtCategory.CODE_QUALITY, "d1", "f1")
        self.assertEqual(debt.remediated_at, "")
        manager.track_remediation(debt.id, DebtStatus.REMEDIATED)
        # Find the debt again in the manager's internal list
        tracked = next(d for d in manager._debts if d.id == debt.id)
        self.assertEqual(tracked.status, DebtStatus.REMEDIATED)
        self.assertNotEqual(tracked.remediated_at, "")


class T6_TechDebtProviderStressContract(unittest.TestCase):
    """Stress and boundary contract tests for TechDebtProvider implementations.

    Covers empty-codebase scanning, large-file-volume scanning, empty-list
    prioritization, no-debt report generation, read-only filesystem
    behavior, and concurrent scan safety.
    """

    def _get_manager(self) -> Any:
        """Return a fresh TechDebtManager (no persistence) for isolation."""
        from scripts.collaboration.tech_debt_manager import TechDebtManager
        return TechDebtManager()

    def test_scan_codebase_debt_completely_empty_directory(self) -> None:
        """scan_codebase_debt on a truly empty dir must return [].

        Boundary: a directory with zero files (not even hidden ones)
        must yield an empty debt list without raising.
        """
        import tempfile
        manager = self._get_manager()
        with tempfile.TemporaryDirectory() as tmp:
            result = manager.scan_codebase_debt(tmp)
            self.assertEqual(result, [])

    def test_scan_codebase_debt_many_files(self) -> None:
        """scan_codebase_debt must handle 100+ files without crashing.

        Stress: creates 100 Python files each with a TODO comment and
        verifies the scan completes and detects at least 100 debts.
        """
        import tempfile
        from pathlib import Path
        manager = self._get_manager()
        with tempfile.TemporaryDirectory() as tmp:
            for i in range(100):
                (Path(tmp) / f"mod_{i}.py").write_text(
                    f"# TODO: refactor module {i}\npass\n", encoding="utf-8",
                )
            debts = manager.scan_codebase_debt(tmp)
            self.assertGreaterEqual(len(debts), 100)

    def test_prioritize_empty_returns_empty_list(self) -> None:
        """prioritize() on a manager with zero debts must return [].

        Boundary: no debts registered means no debts to prioritize.
        Must return an empty list, not None or an error.
        """
        manager = self._get_manager()
        self.assertEqual(manager.prioritize(), [])

    def test_get_debt_report_no_debt_returns_zeros(self) -> None:
        """get_debt_report() with no registered debt must return all-zero fields.

        Boundary: a fresh manager with zero debts must produce a report
        with total_debts=0, empty by_category/by_severity, and
        debt_to_value_ratio=0.0.
        """
        from scripts.collaboration.tech_debt_manager import DebtReport
        manager = self._get_manager()
        report = manager.get_debt_report()
        self.assertIsInstance(report, DebtReport)
        self.assertEqual(report.total_debts, 0)
        self.assertEqual(report.by_category, {})
        self.assertEqual(report.by_severity, {})
        self.assertEqual(report.top_priority, [])
        self.assertEqual(report.debt_to_value_ratio, 0.0)

    def test_scan_codebase_debt_read_only_files_no_exception(self) -> None:
        """scan_codebase_debt must not crash on read-only files.

        Boundary: files without write permission must still be scannable
        (read access is sufficient). The scan must complete without
        PermissionError.
        """
        import os
        import tempfile
        from pathlib import Path
        manager = self._get_manager()
        with tempfile.TemporaryDirectory() as tmp:
            ro_file = Path(tmp) / "readonly.py"
            ro_file.write_text("# TODO: fix this\npass\n", encoding="utf-8")
            os.chmod(ro_file, 0o444)  # read-only
            try:
                debts = manager.scan_codebase_debt(tmp)
                self.assertIsInstance(debts, list)
            finally:
                os.chmod(ro_file, 0o644)  # restore for cleanup

    def test_concurrent_scan_codebase_safety(self) -> None:
        """Concurrent scan_codebase_debt calls must be thread-safe.

        Stress: 5 threads scan the same directory simultaneously. No
        thread must crash, and each must return a list (possibly with
        overlapping debt detections).
        """
        import tempfile
        import threading
        from pathlib import Path
        manager = self._get_manager()
        errors: list[str] = []
        results: list[list] = []
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "mod.py").write_text("# TODO: concurrent test\n", encoding="utf-8")

            def worker() -> None:
                try:
                    res = manager.scan_codebase_debt(tmp)
                    results.append(res)
                except Exception as e:  # noqa: BLE001
                    errors.append(f"thread raised {type(e).__name__}: {e}")

            threads = [threading.Thread(target=worker) for _ in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
        self.assertEqual(errors, [], f"Concurrent scan errors: {errors}")
        self.assertEqual(len(results), 5)

    def test_identify_debt_empty_description_no_exception(self) -> None:
        """identify_debt with an empty description must not raise.

        Boundary: an empty description string is malformed but must be
        accepted. The resulting TechDebt must have description=''.
        """
        from scripts.collaboration.tech_debt_manager import DebtCategory
        manager = self._get_manager()
        debt = manager.identify_debt(
            source="tester", category=DebtCategory.CODE_QUALITY,
            description="", location="src/main.py",
        )
        self.assertEqual(debt.description, "")

    def test_identify_debt_empty_location_no_exception(self) -> None:
        """identify_debt with an empty location must not raise.

        Boundary: an empty location string must be accepted. The
        resulting TechDebt must have location=''.
        """
        from scripts.collaboration.tech_debt_manager import DebtCategory
        manager = self._get_manager()
        debt = manager.identify_debt(
            source="tester", category=DebtCategory.CODE_QUALITY,
            description="missing location", location="",
        )
        self.assertEqual(debt.location, "")


if __name__ == "__main__":
    unittest.main()
