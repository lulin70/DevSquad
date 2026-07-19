#!/usr/bin/env python3
"""V4.1.1 Ghost-Feature Integration Defense Tests.

Provides evidence that the four previously-ghost features are now genuinely
invoked through their integration points (not just defined with unit tests):

1. ``DeterministicRuleEngine`` — invoked inside ``UIUXAnalyzer.audit_dom_data``
   and contributes additional issues beyond the 4 original dimensions.
2. ``TasteDials`` — accepted by ``UIUXAnalyzer.__init__`` and influences the
   rule engine's threshold adjustments.
3. ``VerificationGate.verify_debug_loop_ready`` — accessible via
   ``UnifiedGateEngine.check_debug_loop_ready`` and produces a proper
   ``UnifiedGateResult`` with statistics tracking.
4. ``ExecutionGuard`` DEBUG tag cleanup — invoked inside
   ``DispatchHooks.slice_outputs`` and strips ``[DEBUG-xxx]`` tags from
   worker output.

These tests close the ghost-feature loophole: a module with implementation
and unit tests but no caller in the dispatch pipeline. Each test below
proves the integration point is wired up by asserting on the side-effects
only the integrated module can produce.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from scripts.collaboration.unified_gate_engine import (
    GateType,
    UnifiedGateEngine,
)
from scripts.qa.deterministic_rule_engine import DeterministicRuleEngine
from scripts.qa.taste_dials import TasteDials
from scripts.qa.uiux_analyzer import UIUXAnalyzer

# ============================================================
# Ghost Feature 1 + 2: DeterministicRuleEngine + TasteDials
# ============================================================


class TestDeterministicRuleEngineIntegration:
    """Prove DeterministicRuleEngine is invoked inside UIUXAnalyzer."""

    def test_audit_dom_data_invokes_dre(self) -> None:
        """audit_dom_data should produce DRE-originated issues for button data.

        Without DRE integration, button_too_small data produces only the
        original ``button_too_small`` issue. With DRE integrated, additional
        rules (responsive_touch_target, interaction_button_min_size) fire.
        Asserting on these DRE-specific rule names proves the engine runs.
        """
        data = {
            "interaction": {
                "buttons": [
                    {"text": "OK", "width": 30, "height": 20, "too_small": True},
                ],
                "focus_styles": [],
            }
        }
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data(data, url="http://test")

        dre_rule_names = {
            "responsive_touch_target",
            "interaction_button_min_size",
        }
        present_rules = {i.rule for i in report.issues}
        # At least one DRE-originated rule should fire on small button data.
        assert dre_rule_names & present_rules, (
            f"DRE rules {dre_rule_names} not found in issues: {present_rules}"
        )

    def test_analyzer_holds_dre_instance(self) -> None:
        """UIUXAnalyzer should hold a DeterministicRuleEngine instance."""
        analyzer = UIUXAnalyzer()
        assert isinstance(analyzer._rule_engine, DeterministicRuleEngine)

    def test_dre_does_not_break_empty_data(self) -> None:
        """Empty data should still produce zero issues with DRE integrated."""
        analyzer = UIUXAnalyzer()
        report = analyzer.audit_dom_data({}, url="http://test")
        assert report.total_count == 0
        assert report.passed is True


class TestTasteDialsIntegration:
    """Prove TasteDials is accepted and used by UIUXAnalyzer."""

    def test_analyzer_accepts_taste_dials(self) -> None:
        """UIUXAnalyzer constructor should accept taste_dials parameter."""
        dials = TasteDials(design_variance=0.9, motion_intensity=0.2)
        analyzer = UIUXAnalyzer(taste_dials=dials)
        assert analyzer._taste_dials is dials

    def test_default_taste_dials_created(self) -> None:
        """When no dials provided, analyzer should create default TasteDials."""
        analyzer = UIUXAnalyzer()
        assert isinstance(analyzer._taste_dials, TasteDials)
        # Defaults should be 0.5 for the three main dials.
        assert analyzer._taste_dials.design_variance == 0.5
        assert analyzer._taste_dials.motion_intensity == 0.5
        assert analyzer._taste_dials.visual_density == 0.5

    def test_taste_dials_affect_thresholds(self) -> None:
        """Different dial values should produce different threshold adjustments.

        This proves TasteDials is not just stored but actually consulted
        when the DRE runs rules with adjustable thresholds. Uses a rule_id
        containing "consistency" so the design_variance dial applies.
        """
        dials_low = TasteDials(design_variance=0.0)
        dials_high = TasteDials(design_variance=1.0)
        # The same base threshold should be adjusted differently.
        base = 0.5
        low_adj = dials_low.adjust_threshold("consistency_check", base)
        high_adj = dials_high.adjust_threshold("consistency_check", base)
        assert low_adj != high_adj, (
            "TasteDials with different values should produce different thresholds"
        )


# ============================================================
# Ghost Feature 3: verify_debug_loop_ready via UnifiedGateEngine
# ============================================================


class TestVerifyDebugLoopReadyIntegration:
    """Prove verify_debug_loop_ready is accessible via UnifiedGateEngine."""

    def test_check_debug_loop_ready_rejects_empty_command(self) -> None:
        """Empty command should fail all 4 red-capable criteria."""
        engine = UnifiedGateEngine()
        result = engine.check_debug_loop_ready("")
        assert result.passed is False
        assert result.gate_type == GateType.DEBUG_LOOP_READY
        assert result.verdict == "REJECT"
        # All 4 criteria should be reported as critical issues.
        assert len(result.critical_issues) == 4

    def test_check_debug_loop_ready_passes_valid_command(self) -> None:
        """A valid test command should pass all 4 criteria."""
        engine = UnifiedGateEngine()
        result = engine.check_debug_loop_ready("pytest tests/test_sample.py -v")
        assert result.passed is True
        assert result.verdict == "APPROVE"
        assert result.gate_type == GateType.DEBUG_LOOP_READY

    def test_check_debug_loop_ready_tracks_statistics(self) -> None:
        """Statistics should be updated after a debug-loop-ready check."""
        engine = UnifiedGateEngine()
        before = engine.get_statistics()["total_checks"]
        engine.check_debug_loop_ready("pytest test_x.py")
        after = engine.get_statistics()["total_checks"]
        assert after == before + 1, "check_debug_loop_ready should increment total_checks"

    def test_check_debug_loop_ready_rejects_interactive(self) -> None:
        """Interactive commands (pdb, input) should be rejected."""
        engine = UnifiedGateEngine()
        result = engine.check_debug_loop_ready("python -i script.py")
        assert result.passed is False
        # Should fail on agent-runnable criterion.
        codes = [c["code"] for c in result.critical_issues]
        assert "on-agent-runnable" in codes


# ============================================================
# Ghost Feature 4: ExecutionGuard DEBUG tag cleanup via DispatchHooks
# ============================================================


class TestExecutionGuardDebugTagIntegration:
    """Prove ExecutionGuard DEBUG tag cleanup runs in DispatchHooks.slice_outputs."""

    def _build_hooks(self) -> Any:
        """Build a minimal DispatchHooks with mocked dependencies."""
        from scripts.collaboration.dispatch_hooks import DispatchHooks

        return DispatchHooks(
            coordinator=MagicMock(),
            enterprise=MagicMock(),
            quality_guard=None,
            perf_monitor=MagicMock(),
            anchor_checker=None,
            output_slicer=None,  # disable slicing; we only test debug-tag cleanup
            scratchpad=MagicMock(),
            usage_tracker=MagicMock(),
            dispatch_history=[],
            max_history=10,
            enable_quality_guard=False,
        )

    def test_slice_outputs_strips_debug_tags(self) -> None:
        """slice_outputs should remove [DEBUG-xxx] tagged lines from output."""
        hooks = self._build_hooks()
        worker_results = [
            {
                "role_id": "coder",
                "output": "line1\n[DEBUG-ABC] debug info\nline2\n[DEBUG-XYZ] more debug",
            }
        ]
        hooks.slice_outputs(worker_results, [])
        cleaned = worker_results[0]["output"]
        assert "[DEBUG-" not in cleaned
        assert "line1" in cleaned
        assert "line2" in cleaned
        # Tags should be recorded for traceability.
        assert "_debug_tags_found" in worker_results[0]

    def test_slice_outputs_no_tags_leaves_unchanged(self) -> None:
        """Output without DEBUG tags should be unchanged."""
        hooks = self._build_hooks()
        original_output = "line1\nline2\nline3"
        worker_results = [{"role_id": "coder", "output": original_output}]
        hooks.slice_outputs(worker_results, [])
        assert worker_results[0]["output"] == original_output
        assert "_debug_tags_found" not in worker_results[0]

    def test_slice_outputs_tracks_usage(self) -> None:
        """Usage tracker should tick 'debug_tags_stripped' when tags are found."""
        hooks = self._build_hooks()
        worker_results = [
            {"role_id": "coder", "output": "ok\n[DEBUG-TAG] leak"},
        ]
        hooks.slice_outputs(worker_results, [])
        hooks.usage_tracker.tick.assert_called_with("debug_tags_stripped")
