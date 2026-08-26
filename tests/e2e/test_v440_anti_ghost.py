"""E2E test for V4.4.0 anti-ghost verification.

Verifies that all 5 new V4.4.0 modules have their _call_counter_er incremented
after a single dispatch() call, proving they are wired into the pipeline
and not dead code.
"""
from scripts.collaboration.dispatcher import MultiAgentDispatcher


def test_e2e_dispatch_increments_all_five_counters():
    """AG-1/AG-2: One dispatch() call must increment all 5 module _call_counter_er > 0."""
    disp = MultiAgentDispatcher()
    disp.dispatch("Design a payment gateway")

    import scripts.collaboration.dora_metrics_collector as dmc
    import scripts.collaboration.error_budget_tracker as ebt
    import scripts.collaboration.gap_analyzer as ga
    import scripts.collaboration.risk_register as rr
    import scripts.collaboration.viewpoint_registry as vr

    assert rr._call_counter_er > 0, "RiskRegister not activated during dispatch"
    assert vr._call_counter_er > 0, "ViewpointRegistry not activated during dispatch"
    assert ebt._call_counter_er > 0, "ErrorBudgetTracker not activated during dispatch"
    assert ga._call_counter_er > 0, "GapAnalyzer not activated during dispatch"
    assert dmc._call_counter_er > 0, "DoraMetricsCollector not activated during dispatch"

    disp.shutdown()
