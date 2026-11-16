"""P8-007: WorkflowTrace false-positive-rate query tests (TD-078 / W4).

Verifies the real wiring — not mocks — because the anti-ghost principle
requires modules to be *activated*, not just importable:

- SimplicityRole records ``simplicity_reject`` events on REJECT verdicts
- SimplicityConfig.check_false_positive_rate() queries those events
- auto_downgrade_if_needed() revives the >10% downgrade (former dead code)
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from scripts.collaboration.simplicity_config import SimplicityConfig


class FakeTrace:
    """Minimal duck-typed WorkflowTrace: record() + records list."""

    def __init__(self) -> None:
        self.records: list[dict] = []

    def record(self, event: dict) -> None:
        self.records.append(event)


def _make_plan(tmp_path, target_files):
    plan = Mock()
    plan.phase = "P8"
    plan.target_files = target_files
    # S1 Gate needs real design/test docs to avoid a completeness REJECT
    p3_doc = tmp_path / "p3_design.md"
    p3_doc.write_text("# P3 Design\nclass TestClass:\n    pass")
    p7_doc = tmp_path / "p7_test_plan.md"
    p7_doc.write_text("# P7 Test Plan\n- test_foo()")
    plan.p3_doc = str(p3_doc)
    plan.p7_doc = str(p7_doc)
    plan.test_paths = []
    plan.test_files = []
    return plan


_CRAP_PASS = {"status": "PASS", "max_crap": 5.0, "violations": [], "summary": "OK"}
_CRAP_REJECT = {
    "status": "REJECT",
    "max_crap": 42.0,
    "violations": [{"file": "a.py", "function": "foo", "crap": 42.0}],
    "recommendations": [],
}

_S1_PASS = {
    "verdict": "PASS",
    "completeness_score": 0.98,
    "mode": "full",
    "timestamp": "2026-11-16T00:00:00",
    "details": {
        "mock_score": 1.0,
        "alignment_score": 0.95,
        "test_coverage": 1.0,
        "error_handling_score": 1.0,
        "security_score": 0.95,
        "mock_violations": [],
        "missing_elements": [],
        "extra_elements": [],
        "missing_tests": [],
        "extra_tests": [],
        "unprotected_operations": [],
        "missing_security_features": [],
    },
}


def _activate(role, plan):
    """Run activate() with CRAPGate + S1 gate mocked (radon not in test deps;
    S1 completeness would otherwise reject a minimal target) while keeping
    DuplicationGate REAL."""
    from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate
    from scripts.collaboration.gates.crap_gate import CRAPGate

    with (
        patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": ""}),
        patch.object(ImplementationCompletenessGate, "check", return_value=dict(_S1_PASS)),
        patch.object(CRAPGate, "check", return_value=dict(_CRAP_PASS)),
    ):
        return role.activate(plan, [])


class TestCheckFalsePositiveRate:
    """Unit tests for the WorkflowTrace query formula."""

    def test_no_trace_returns_zero(self) -> None:
        assert SimplicityConfig.check_false_positive_rate(None) == 0.0

    def test_no_reject_events_returns_zero(self) -> None:
        trace = SimpleNamespace(records=[{"event": "simplicity_audit"}, {"event": "simplicity_bypass"}])
        assert SimplicityConfig.check_false_positive_rate(trace) == 0.0

    def test_rate_formula_counts_overrides(self) -> None:
        events = [
            {"event": "simplicity_reject", "human_override": True},
            {"event": "simplicity_reject", "human_override": False},
            {"event": "simplicity_reject", "human_override": False},
            {"event": "simplicity_reject", "human_override": False},
        ]
        trace = SimpleNamespace(records=events)
        assert SimplicityConfig.check_false_positive_rate(trace) == pytest.approx(0.25)

    def test_events_attribute_fallback(self) -> None:
        trace = SimpleNamespace(events=[{"event": "simplicity_reject", "human_override": True}])
        assert SimplicityConfig.check_false_positive_rate(trace) == 1.0

    def test_raw_event_list_input(self) -> None:
        events = [{"event": "simplicity_reject", "human_override": False}]
        assert SimplicityConfig.check_false_positive_rate(events) == 0.0


class TestRejectEventRecording:
    """Integration: real SimplicityRole REJECT records the event."""

    def test_reject_records_simplicity_reject_event(self, tmp_path) -> None:
        from scripts.collaboration.gates.completeness_gate import ImplementationCompletenessGate
        from scripts.collaboration.gates.crap_gate import CRAPGate
        from scripts.collaboration.simplicity_role import SimplicityRole

        target = tmp_path / "unique.py"
        target.write_text("def only_here():\n    return 42\n")

        trace = FakeTrace()
        with (
            patch.dict(os.environ, {"DEVSQUAD_SKIP_SIMPLICITY": ""}),
            patch.object(ImplementationCompletenessGate, "check", return_value=dict(_S1_PASS)),
            patch.object(CRAPGate, "check", return_value=dict(_CRAP_REJECT)),
        ):
            role = SimplicityRole(trace, Mock())
            result = role.activate(_make_plan(tmp_path, [str(target)]), [])

        assert result is not None
        assert result.status == "REJECT"
        rejects = [e for e in trace.records if e.get("event") == "simplicity_reject"]
        assert len(rejects) == 1
        assert rejects[0]["human_override"] is False

    def test_pass_verdict_records_no_reject_event(self, tmp_path) -> None:
        from scripts.collaboration.simplicity_role import SimplicityRole

        target = tmp_path / "unique.py"
        target.write_text("def only_here():\n    return 42\n")

        trace = FakeTrace()
        role = SimplicityRole(trace, Mock())
        _activate(role, _make_plan(tmp_path, [str(target)]))

        assert not [e for e in trace.records if e.get("event") == "simplicity_reject"]


class TestAutoDowngrade:
    """The >10% downgrade threshold is no longer dead code."""

    def test_low_rate_keeps_current_mode(self) -> None:
        deployment = datetime.now() - timedelta(days=30)  # full mode window
        events = [{"event": "simplicity_reject", "human_override": False}]
        trace = SimpleNamespace(records=events)
        with patch.object(SimplicityConfig, "get_deployment_date", return_value=deployment):
            assert SimplicityConfig.auto_downgrade_if_needed(trace) == "full"

    def test_high_rate_downgrades_to_soft(self) -> None:
        deployment = datetime.now() - timedelta(days=30)  # full mode window
        events = [{"event": "simplicity_reject", "human_override": True}] * 2 + [
            {"event": "simplicity_reject", "human_override": False}
        ]
        trace = SimpleNamespace(records=events)  # rate = 2/3 > 0.1
        with patch.object(SimplicityConfig, "get_deployment_date", return_value=deployment):
            assert SimplicityConfig.auto_downgrade_if_needed(trace) == "soft"

    def test_no_trace_returns_current_mode(self) -> None:
        deployment = datetime.now() - timedelta(days=2)  # shadow mode window
        with patch.object(SimplicityConfig, "get_deployment_date", return_value=deployment):
            assert SimplicityConfig.auto_downgrade_if_needed(None) == "shadow"
