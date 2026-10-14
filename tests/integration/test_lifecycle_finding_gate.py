"""Integration tests for lifecycle finding producer gate wiring."""

from scripts.collaboration.lifecycle_gate import check_gate_basic
from scripts.collaboration.lifecycle_protocol import ShortcutLifecycleAdapter
from scripts.collaboration.lifecycle_shortcut_helpers import get_phase_definition


def test_basic_gate_merges_findings_from_artifacts() -> None:
    result = check_gate_basic(
        "P1",
        get_phase_definition("P1"),
        {},
        [],
        artifacts={"missing": ["objectives"]},
    )
    assert result.lifecycle_findings[0].category == "BREAK-1"


def test_shortcut_check_gate_accepts_artifacts() -> None:
    adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
    result = adapter.check_gate("P1", artifacts={"checks": {"objectives": False}})
    assert result.lifecycle_findings[0].lifecycle_phase == "P1"


def test_check_command_gate_aggregates_findings_by_phase() -> None:
    adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
    result = adapter.check_command_gate(
        "test",
        artifacts_by_phase={"P9": {"missing": ["test_results"]}},
    )
    assert {finding.lifecycle_phase for finding in result.lifecycle_findings} == {"P9"}


def test_legacy_gate_call_has_no_findings() -> None:
    adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
    result = adapter.check_gate("P1")
    assert result.lifecycle_findings == []
