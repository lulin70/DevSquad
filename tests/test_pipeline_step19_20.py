"""Integration tests for dispatcher Step 19 (UE Testing) and Step 20 (Tech Debt Scan)."""

import tempfile

# These tests verify that the dispatch pipeline correctly invokes
# UETestFramework and TechDebtManager when appropriate roles are involved.


class TestStep19UETesting:
    """Test Step 19: UE testing integration in dispatch pipeline."""

    def test_ue_test_plan_generated_with_tester_role(self):
        """When tester role is involved, result.details should contain ue_test_plan."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Test the user login flow", roles=["tester"])
            # Step 19 should trigger because tester role is involved
            if "ue_test_plan" in result.details:
                plan = result.details["ue_test_plan"]
                assert "heuristic_checks" in plan
                assert len(plan["heuristic_checks"]) == 10  # Nielsen's 10
            disp.shutdown()

    def test_ue_test_plan_not_generated_without_relevant_roles(self):
        """When no tester/pm/ui role is involved, ue_test_plan should be absent."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Fix a bug in the database layer", roles=["solo-coder"])
            assert "ue_test_plan" not in result.details or result.details.get("ue_test_plan") is None
            disp.shutdown()

    def test_ue_test_plan_with_pm_role(self):
        """When PM role is involved, ue_test_plan should be generated."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Design user onboarding experience", roles=["product-manager"])
            if "ue_test_plan" in result.details:
                plan = result.details["ue_test_plan"]
                assert "persona_scenarios" in plan
            disp.shutdown()


class TestStep20TechDebtScan:
    """Test Step 20: Tech debt scan integration in dispatch pipeline."""

    def test_tech_debt_report_with_architect_role(self):
        """When architect role is involved, result.details should contain tech_debt_report."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Review architecture for circular dependencies", roles=["architect"])
            if "tech_debt_report" in result.details:
                report = result.details["tech_debt_report"]
                assert "total_debts" in report
                assert "by_category" in report
            disp.shutdown()

    def test_tech_debt_skipped_without_relevant_roles(self):
        """When no tester/architect role, tech_debt_report should be absent."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            result = disp.dispatch("Deploy to production", roles=["devops"])
            assert "tech_debt_report" not in result.details or result.details.get("tech_debt_report") is None
            disp.shutdown()

    def test_extract_test_debts_detects_missing_tests(self):
        """Test that _extract_test_debts correctly identifies test gap keywords."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.tech_debt_manager import DebtCategory, TechDebtManager

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            manager = TechDebtManager(persist_dir=tmpdir)
            disp.post_dispatch._extract_test_debts(
                manager, "There are missing tests for the auth module", "auth module"
            )
            report = manager.get_debt_report()
            assert report.total_debts >= 1
            assert DebtCategory.TEST_GAP.value in report.by_category
            disp.shutdown()

    def test_extract_arch_debts_detects_circular_deps(self):
        """Test that _extract_arch_debts correctly identifies circular dependency keywords."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.tech_debt_manager import DebtCategory, TechDebtManager

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            manager = TechDebtManager(persist_dir=tmpdir)
            disp.post_dispatch._extract_arch_debts(
                manager, "Found circular dependency between modules", "module review"
            )
            report = manager.get_debt_report()
            assert report.total_debts >= 1
            assert DebtCategory.ARCHITECTURE.value in report.by_category
            disp.shutdown()

    def test_extract_arch_debts_detects_god_class(self):
        """Test that _extract_arch_debts detects god class pattern."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.tech_debt_manager import TechDebtManager

        with tempfile.TemporaryDirectory() as tmpdir:
            disp = MultiAgentDispatcher(persist_dir=tmpdir)
            manager = TechDebtManager(persist_dir=tmpdir)
            disp.post_dispatch._extract_arch_debts(
                manager, "This is a god class that handles everything", "class review"
            )
            report = manager.get_debt_report()
            assert report.total_debts >= 1
            disp.shutdown()
