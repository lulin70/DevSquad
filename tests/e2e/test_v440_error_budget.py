"""E2E tests for V4.4.0 P1-1 Error Budget Tracker."""


def test_e2e_p10_rejects_when_budget_exhausted():
    """US-E2: P10 deployment gate must REJECT feature deploy when budget EXHAUSTED."""
    from scripts.collaboration.error_budget_tracker import BudgetStatus, ErrorBudgetTracker
    from scripts.collaboration.unified_gate_engine import UnifiedGateEngine
    engine = UnifiedGateEngine()
    tracker = ErrorBudgetTracker(slo_target=0.999, window_days=30)
    # Exhaust the budget
    tracker._budget_remaining = 0.0
    tracker._status = BudgetStatus.EXHAUSTED
    result = engine.check_deployment(error_budget_tracker=tracker)
    assert result.verdict == "REJECT", f"Expected REJECT when budget exhausted, got {result.verdict}"


def test_e2e_dashboard_error_budget_panel_renders():
    """US-E3: Dashboard must render error budget panel with progress bar + burn_rate + status."""
    from scripts.collaboration.error_budget_tracker import ErrorBudgetTracker
    tracker = ErrorBudgetTracker(slo_target=0.999, window_days=30)
    panel_md = tracker.to_dashboard_panel()
    assert "budget" in panel_md.lower()
    assert "burn_rate" in panel_md.lower() or "burn rate" in panel_md.lower()
    assert "status" in panel_md.lower()
