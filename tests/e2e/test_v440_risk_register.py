"""E2E skeletons for V4.4.0 P0-1 Risk Register (xfail TDD).

These tests are committed in V4.3.3 as xfail and must turn xpass in V4.4.0
when risk_register.py is implemented and integrated into the dispatch pipeline.
"""
import pytest

from scripts.collaboration.dispatcher import MultiAgentDispatcher


@pytest.mark.xfail(reason="V4.4.0 P0-1 Risk Register not yet implemented", strict=True)
def test_e2e_risk_register_assess_after_dispatch():
    """US-R1: A full dispatch() must call RiskRegister.assess() with 7-role votes."""
    disp = MultiAgentDispatcher()
    result = disp.dispatch("Design a payment gateway")
    from scripts.collaboration.risk_register import RiskRegister
    register = getattr(disp, "_risk_register", None) or RiskRegister()
    assert register._call_counter > 0, "RiskRegister was never called during dispatch"
    assert "## Risk Management" in result.to_markdown()
    disp.shutdown()


@pytest.mark.xfail(reason="V4.4.0 P0-1 Risk Register not yet implemented", strict=True)
def test_e2e_risk_register_section_in_report():
    """US-R3: Dispatch report must contain ## Risk Management section with items."""
    disp = MultiAgentDispatcher()
    result = disp.dispatch("Design a payment gateway")
    md = result.to_markdown()
    assert "## Risk Management" in md
    # Section should list at least one risk item with exposure score
    assert "exposure" in md.lower() or "probability" in md.lower()
    disp.shutdown()


@pytest.mark.xfail(reason="V4.4.0 P0-1 Risk Register not yet implemented", strict=True)
def test_e2e_risk_check_gate_blocks_high_exposure():
    """US-R1: Phase gate must REJECT when open risk has exposure >= 0.36."""
    from scripts.collaboration.unified_gate_engine import GateType, UnifiedGateEngine
    engine = UnifiedGateEngine()
    # Simulate a high-exposure open risk
    from scripts.collaboration.risk_register import RiskItem, RiskRegister
    register = RiskRegister()
    register.add(RiskItem(
        id="R-001",
        description="Critical data loss risk",
        probability=0.9,
        impact=0.9,
        response_strategy="mitigate",
        owner="security",
        status="open",
        category="security",
    ))
    result = engine.check(GateType.RISK_CHECK, risk_register=register)
    assert result.verdict == "REJECT", f"Expected REJECT for high exposure, got {result.verdict}"
