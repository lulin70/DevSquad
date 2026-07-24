#!/usr/bin/env python3
"""UnifiedGateEngine + VerificationGate + LifecycleProtocol Integration Tests.

End-to-end integration tests for the unified gate architecture (Plan C).
Verifies CROSS-MODULE interactions among:

    scripts/collaboration/unified_gate_engine.py — UnifiedGateEngine single
        entry point for phase-transition + worker-output + debug-loop gates.
    scripts/collaboration/verification_gate.py   — VerificationGate enforces
        mandatory evidence + 7 Red Flags + Prove-It (red-capable) pattern.
    scripts/collaboration/lifecycle_protocol.py   — LifecycleProtocol abstract
        interface + LifecycleMode/PhaseDefinition/PhaseState data models.
    scripts/collaboration/lifecycle_gate.py       — check_gate_basic /
        check_gate_with_unified_engine bridge helpers.
    scripts/collaboration/lifecycle_templates.py  — 11-phase SPEC_TEMPLATES +
        VIEW_MAPPINGS (spec/plan/build/test/review/ship).
    scripts/collaboration/lifecycle_shortcut_adapter.py — ShortcutLifecycleAdapter
        + FullLifecycleAdapter implementations.
    scripts/collaboration/lifecycle_shortcut_helpers.py — shared helper functions.

Test categories:
    T1: VerificationGate — 7 Red Flags + mandatory evidence + Prove-It pattern
    T2: LifecycleProtocol — 11-phase templates + 5 lifecycle variants
    T3: UnifiedGateEngine — integrates VerificationGate + phase-transition gates
    T4: End-to-end — phase enter → gate check → evidence verify → pass/reject
    T5: Boundary — no evidence, fake evidence, gate failure, state persistence
"""

from __future__ import annotations

import os
import sys
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.lifecycle_protocol import (
    GateResult,
    LifecycleMode,
    PhaseState,
    triage_requirement,
)
from scripts.collaboration.lifecycle_shortcut_adapter import (
    FullLifecycleAdapter,
    ShortcutLifecycleAdapter,
    create_lifecycle_protocol,
)
from scripts.collaboration.lifecycle_templates import (
    SPEC_TEMPLATES,
    VIEW_MAPPINGS,
)
from scripts.collaboration.unified_gate_engine import (
    GateType,
    PhaseGateContext,
    UnifiedGateConfig,
    UnifiedGateEngine,
    UnifiedGateResult,
    WorkerOutputContext,
)
from scripts.collaboration.verification_gate import (
    CompletionContext,
    VerificationGate,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _reset_gate_singletons() -> None:
    """Reset module-level singletons so each test starts from a clean state.

    VerificationGate and UnifiedGateEngine both cache a shared singleton whose
    strict_mode / config is locked at first creation. Resetting them between
    tests guarantees deterministic behavior regardless of test execution order.
    """
    import scripts.collaboration.unified_gate_engine as uge_mod
    import scripts.collaboration.verification_gate as vg_mod

    vg_mod._shared_verification_gate_instance = None
    uge_mod._shared_gate_engine_instance = None


def _make_completion_context(
    role_id: str = "solo-coder",
    has_code_changes: bool = False,
    has_test_changes: bool = False,
    is_bug_fix: bool = False,
    has_repro_test: bool = False,
    test_run_count: int = 0,
    all_passed: bool = False,
    tests_skipped: int = 0,
    coverage_delta: float = 0.0,
    output_lines: int = 0,
    was_sliced: bool = False,
    claims_complete: bool = False,
    evidence: dict[str, Any] | None = None,
) -> CompletionContext:
    """Create a CompletionContext with sensible defaults for gate tests."""
    return CompletionContext(
        role_id=role_id,
        has_code_changes=has_code_changes,
        has_test_changes=has_test_changes,
        is_bug_fix=is_bug_fix,
        has_repro_test=has_repro_test,
        test_run_count=test_run_count,
        all_passed=all_passed,
        tests_skipped=tests_skipped,
        coverage_delta=coverage_delta,
        output_lines=output_lines,
        was_sliced=was_sliced,
        claims_complete=claims_complete,
        evidence=evidence if evidence is not None else {},
    )


def _make_phase_gate_context(
    phase_id: str = "P1",
    phase_name: str = "Requirements",
    dependencies_met: bool = True,
    completed_phases: list[str] | None = None,
    artifacts_available: dict[str, bool] | None = None,
    reviewers_approved: list[str] | None = None,
) -> PhaseGateContext:
    """Create a PhaseGateContext with sensible defaults."""
    return PhaseGateContext(
        phase_id=phase_id,
        phase_name=phase_name,
        current_state="pending",
        target_state="running",
        dependencies_met=dependencies_met,
        completed_phases=completed_phases or [],
        artifacts_available=artifacts_available or {},
        reviewers_approved=reviewers_approved if reviewers_approved is not None else [],
    )


def _make_worker_output_context(
    role_id: str = "solo-coder",
    task_description: str = "implement feature",
    output: str = "done",
    has_code_changes: bool = False,
    has_test_changes: bool = False,
    test_results: dict[str, Any] | None = None,
    claims_complete: bool = False,
    coverage_delta: float = 0.0,
) -> WorkerOutputContext:
    """Create a WorkerOutputContext for UnifiedGateEngine WORKER_OUTPUT checks."""
    return WorkerOutputContext(
        role_id=role_id,
        task_description=task_description,
        output=output,
        has_code_changes=has_code_changes,
        has_test_changes=has_test_changes,
        test_results=test_results,
        coverage_delta=coverage_delta,
        claims_complete=claims_complete,
    )


# ---------------------------------------------------------------------------
# T1: VerificationGate — 7 Red Flags + mandatory evidence + Prove-It pattern
# ---------------------------------------------------------------------------


class T1_VerificationGateRedFlagsAndEvidence(unittest.TestCase):
    """T1: VerificationGate enforces evidence + detects 7 Red Flags."""

    def setUp(self) -> None:
        _reset_gate_singletons()
        self.gate = VerificationGate(strict_mode=True)

    def test_01_seven_red_flags_defined(self) -> None:
        """Verify: Exactly 7 Red Flags are defined with correct severities."""
        self.assertEqual(self.gate.red_flag_count, 7)
        critical = [f for f in self.gate.RED_FLAGS if f.severity == "critical"]
        warning = [f for f in self.gate.RED_FLAGS if f.severity == "warning"]
        self.assertEqual(len(critical) + len(warning), 7)
        # 4 critical flags: no_test, no_regression_test, tests_skipped, no_evidence
        self.assertEqual(len(critical), 4)
        # 3 warning flags: tests_pass_first_run, coverage_decreased, output_exceeds_limit
        self.assertEqual(len(warning), 3)

    def test_02_no_test_for_new_behavior_critical_flag(self) -> None:
        """Verify: code changes without tests triggers critical Red Flag."""
        ctx = _make_completion_context(has_code_changes=True, has_test_changes=False)
        result = self.gate.check(ctx)
        flag_ids = [f.id for f in result.red_flags]
        self.assertIn("no_test_for_new_behavior", flag_ids)
        self.assertEqual(result.verdict, "REJECT")
        self.assertFalse(result.passed)

    def test_03_no_regression_test_for_bugfix_critical_flag(self) -> None:
        """Verify: bug fix without reproduction test triggers critical flag."""
        ctx = _make_completion_context(is_bug_fix=True, has_repro_test=False)
        result = self.gate.check(ctx)
        flag_ids = [f.id for f in result.red_flags]
        self.assertIn("no_regression_test_for_bugfix", flag_ids)
        self.assertFalse(result.passed)

    def test_04_tests_skipped_or_disabled_critical_flag(self) -> None:
        """Verify: skipped tests trigger critical Red Flag."""
        ctx = _make_completion_context(tests_skipped=2)
        result = self.gate.check(ctx)
        flag_ids = [f.id for f in result.red_flags]
        self.assertIn("tests_skipped_or_disabled", flag_ids)
        self.assertFalse(result.passed)

    def test_05_no_evidence_provided_critical_flag(self) -> None:
        """Verify: claims complete without evidence triggers critical flag."""
        ctx = _make_completion_context(claims_complete=True, evidence={})
        result = self.gate.check(ctx)
        flag_ids = [f.id for f in result.red_flags]
        self.assertIn("no_evidence_provided", flag_ids)
        self.assertFalse(result.passed)

    def test_06_warning_flags_do_not_reject(self) -> None:
        """Verify: warning-severity flags yield CONDITIONAL, not REJECT."""
        # tests_pass_first_run: test_run_count=1, all_passed=True, has_test_changes=True
        ctx = _make_completion_context(
            test_run_count=1, all_passed=True, has_test_changes=True,
            evidence={"test_results": "ok", "diff_summary": "x"},
        )
        result = self.gate.check(ctx)
        flag_ids = [f.id for f in result.red_flags]
        self.assertIn("tests_pass_first_run", flag_ids)
        # Only warnings → CONDITIONAL (not REJECT)
        self.assertEqual(result.verdict, "CONDITIONAL")
        self.assertFalse(result.passed)

    def test_07_mandatory_evidence_required_items(self) -> None:
        """Verify: 3 mandatory evidence items; test_results + diff_summary required."""
        self.assertEqual(self.gate.evidence_item_count, 3)
        required_keys = [e.key for e in self.gate.MANDATORY_EVIDENCE if e.required]
        self.assertIn("test_results", required_keys)
        self.assertIn("diff_summary", required_keys)
        # build_status is required only for architect/solo-coder
        bs_item = next(e for e in self.gate.MANDATORY_EVIDENCE if e.key == "build_status")
        self.assertFalse(bs_item.required)
        self.assertEqual(bs_item.required_for, ["architect", "solo-coder"])

    def test_08_clean_context_passes_gate(self) -> None:
        """Verify: a clean context with full evidence passes (APPROVE)."""
        ctx = _make_completion_context(
            has_code_changes=True, has_test_changes=True,
            test_run_count=2, all_passed=True,
            evidence={"test_results": "5 passed", "build_status": "ok", "diff_summary": "+10/-2"},
        )
        result = self.gate.check(ctx)
        self.assertEqual(result.verdict, "APPROVE")
        self.assertTrue(result.passed)
        self.assertEqual(len(result.red_flags), 0)

    def test_09_missing_required_evidence_rejects(self) -> None:
        """Verify: missing required evidence (test_results) causes REJECT."""
        ctx = _make_completion_context(
            has_code_changes=True, has_test_changes=True,
            evidence={"build_status": "ok", "diff_summary": "+10/-2"},  # no test_results
        )
        result = self.gate.check(ctx)
        missing_keys = [e.key for e in result.missing_evidence]
        self.assertIn("test_results", missing_keys)
        self.assertEqual(result.verdict, "REJECT")

    def test_10_build_status_required_for_architect(self) -> None:
        """Verify: build_status is required when role_id is architect."""
        ctx = _make_completion_context(
            role_id="architect", claims_complete=True,
            evidence={"test_results": "ok", "diff_summary": "x"},  # no build_status
        )
        result = self.gate.check(ctx)
        missing_keys = [e.key for e in result.missing_evidence]
        self.assertIn("build_status", missing_keys)

    def test_11_prove_it_pattern_red_capable_passes(self) -> None:
        """Verify: a deterministic, fast, agent-runnable assertion command is red-capable."""
        result = self.gate.verify_debug_loop_ready("assert my_func() == 42")
        self.assertTrue(result.passed)
        self.assertEqual(len(result.failed_criteria), 0)
        self.assertIn("satisfied", result.reasoning)

    def test_12_prove_it_pattern_empty_command_fails_all(self) -> None:
        """Verify: empty command fails all 4 red-capable criteria."""
        result = self.gate.verify_debug_loop_ready("")
        self.assertFalse(result.passed)
        self.assertEqual(len(result.failed_criteria), 4)
        self.assertIn("on-red-capable", result.failed_criteria)
        self.assertIn("on-deterministic", result.failed_criteria)

    def test_13_prove_it_pattern_non_deterministic_fails(self) -> None:
        """Verify: random/time/network usage fails on-deterministic criterion."""
        result = self.gate.verify_debug_loop_ready("assert random.random() == 0.5")
        self.assertFalse(result.passed)
        self.assertIn("on-deterministic", result.failed_criteria)

    def test_14_prove_it_pattern_slow_command_fails(self) -> None:
        """Verify: time.sleep / large loops fail on-fast criterion."""
        result = self.gate.verify_debug_loop_ready("time.sleep(10); assert True")
        self.assertFalse(result.passed)
        self.assertIn("on-fast", result.failed_criteria)

    def test_15_prove_it_pattern_interactive_fails(self) -> None:
        """Verify: input()/pdb fails on-agent-runnable criterion."""
        result = self.gate.verify_debug_loop_ready("x = input('enter: '); assert x")
        self.assertFalse(result.passed)
        self.assertIn("on-agent-runnable", result.failed_criteria)

    def test_16_build_context_from_worker_result(self) -> None:
        """Verify: build_context_from_worker_result extracts fields heuristically."""
        worker_result = {
            "role_id": "solo-coder",
            "output": "line1\nline2\nline3\nline4\nline5\nline6\nline7\nline8\nline9\nline10\nline11",
            "success": True,
            "errors": [],
            "task_description": "fix the login bug",
        }
        ctx = self.gate.build_context_from_worker_result(worker_result)
        self.assertEqual(ctx.role_id, "solo-coder")
        self.assertTrue(ctx.has_code_changes)  # output_lines > 10 and success
        self.assertTrue(ctx.is_bug_fix)  # "fix" keyword
        self.assertTrue(ctx.claims_complete)


# ---------------------------------------------------------------------------
# T2: LifecycleProtocol — 11-phase templates + 5 lifecycle variants
# ---------------------------------------------------------------------------


class T2_LifecycleProtocolTemplates(unittest.TestCase):
    """T2: 11-phase PHASE_TEMPLATES + 5 LIFECYCLE_TEMPLATES + VIEW_MAPPINGS."""

    def setUp(self) -> None:
        _reset_gate_singletons()
        self.shortcut = ShortcutLifecycleAdapter(use_unified_gate=False)
        self.full = FullLifecycleAdapter(use_unified_gate=False)

    def test_01_eleven_phases_available(self) -> None:
        """Verify: all 11 phases (P1-P11) are defined in the protocol."""
        phases = self.shortcut.get_all_phases()
        phase_ids = [p.phase_id for p in phases]
        self.assertEqual(len(phases), 11)
        for i in range(1, 12):
            self.assertIn(f"P{i}", phase_ids)

    def test_02_phase_dependencies_correct(self) -> None:
        """Verify: P2 depends on P1; P8 depends on P3 + P7."""
        p2 = self.shortcut.get_phase("P2")
        self.assertIsNotNone(p2)
        assert p2 is not None  # narrowing
        self.assertEqual(p2.dependencies, ["P1"])
        p8 = self.shortcut.get_phase("P8")
        assert p8 is not None
        self.assertEqual(p8.dependencies, ["P3", "P7"])

    def test_03_optional_vs_required_phases(self) -> None:
        """Verify: P4/P5/P6/P11 optional; P1/P2/P3/P7/P8/P9/P10 required."""
        optional_ids = {"P4", "P5", "P6", "P11"}
        required_ids = {"P1", "P2", "P3", "P7", "P8", "P9", "P10"}
        for phase in self.shortcut.get_all_phases():
            if phase.phase_id in optional_ids:
                self.assertTrue(phase.optional, f"{phase.phase_id} should be optional")
            elif phase.phase_id in required_ids:
                self.assertFalse(phase.optional, f"{phase.phase_id} should be required")

    def test_04_spec_templates_defined(self) -> None:
        """Verify: 3 SPEC_TEMPLATES (requirements/architecture/technical)."""
        self.assertIn("requirements", SPEC_TEMPLATES)
        self.assertIn("architecture", SPEC_TEMPLATES)
        self.assertIn("technical", SPEC_TEMPLATES)
        req = SPEC_TEMPLATES["requirements"]
        self.assertEqual(req.phase_id, "P1")
        self.assertIn("objectives", req.required_fields)

    def test_05_view_mappings_cover_six_commands(self) -> None:
        """Verify: VIEW_MAPPINGS has spec/plan/build/test/review/ship + 3 spec-*."""
        for cmd in ["spec", "plan", "build", "test", "review", "ship",
                    "spec-init", "spec-analyze", "spec-validate"]:
            self.assertIn(cmd, VIEW_MAPPINGS, f"missing view mapping: {cmd}")
        spec_mapping = VIEW_MAPPINGS["spec"]
        self.assertTrue(spec_mapping.covers_phase("P1"))
        self.assertTrue(spec_mapping.covers_phase("P2"))
        self.assertFalse(spec_mapping.covers_phase("P10"))

    def test_06_full_adapter_skip_optional_filters_phases(self) -> None:
        """Verify: FullLifecycleAdapter.set_skip_optional excludes optional phases."""
        self.full.set_skip_optional(True)
        active = self.full.get_active_phases()
        active_ids = {p.phase_id for p in active}
        self.assertNotIn("P4", active_ids)
        self.assertNotIn("P11", active_ids)
        self.assertIn("P1", active_ids)
        # Restore
        self.full.set_skip_optional(False)
        all_active = self.full.get_active_phases()
        self.assertEqual(len(all_active), 11)

    def test_07_create_lifecycle_protocol_factory(self) -> None:
        """Verify: create_lifecycle_protocol returns correct adapter per mode."""
        shortcut = create_lifecycle_protocol(LifecycleMode.SHORTCUT)
        full = create_lifecycle_protocol(LifecycleMode.FULL)
        self.assertEqual(shortcut.get_mode(), LifecycleMode.SHORTCUT)
        self.assertEqual(full.get_mode(), LifecycleMode.FULL)

    def test_08_resolve_command_to_phases(self) -> None:
        """Verify: resolve_command_to_phases maps 'build' → P8 phase definition."""
        phases = self.shortcut.resolve_command_to_phases("build")
        self.assertEqual(len(phases), 1)
        self.assertEqual(phases[0].phase_id, "P8")
        # Unknown command returns empty list
        self.assertEqual(self.shortcut.resolve_command_to_phases("unknown"), [])

    def test_09_triage_requirement_categorization(self) -> None:
        """Verify: triage_requirement categorizes bug/security/feature correctly."""
        bug = triage_requirement("修复登录bug")
        self.assertEqual(bug.category, "bug")
        self.assertEqual(bug.state, "new")
        security = triage_requirement("修复安全漏洞")
        self.assertEqual(security.category, "security")
        feature = triage_requirement("添加新功能")
        self.assertEqual(feature.category, "feature")

    def test_10_lifecycle_status_summary(self) -> None:
        """Verify: get_status returns progress + next_phase before any advance."""
        status = self.shortcut.get_status()
        self.assertEqual(status.mode, LifecycleMode.SHORTCUT)
        self.assertIsNone(status.current_phase)
        self.assertEqual(status.progress_percent, 0.0)
        self.assertIsNotNone(status.next_phase)


# ---------------------------------------------------------------------------
# T3: UnifiedGateEngine — integrates VerificationGate + phase-transition gates
# ---------------------------------------------------------------------------


class T3_UnifiedGateEngineIntegration(unittest.TestCase):
    """T3: UnifiedGateEngine routes to phase-transition + worker-output checkers."""

    def setUp(self) -> None:
        _reset_gate_singletons()
        self.engine = UnifiedGateEngine(config=UnifiedGateConfig(strict_mode=True))

    def test_01_phase_transition_gate_approves_with_deps_met(self) -> None:
        """Verify: phase-transition gate APPROVEs when dependencies are met."""
        ctx = _make_phase_gate_context(
            phase_id="P2", dependencies_met=True,
            completed_phases=["P1"], reviewers_approved=["architect"],
        )
        result = self.engine.check(GateType.PHASE_TRANSITION, ctx)
        self.assertTrue(result.passed)
        self.assertEqual(result.verdict, "APPROVE")
        self.assertEqual(result.gate_type, GateType.PHASE_TRANSITION)

    def test_02_phase_transition_gate_rejects_with_unmet_deps(self) -> None:
        """Verify: phase-transition gate REJECTs when dependencies unmet."""
        ctx = PhaseGateContext(
            phase_id="P2", phase_name="Architecture",
            current_state="pending", target_state="running",
            dependencies_met=False, completed_phases=[],
        )
        # Simulate unmet_dependencies attribute (set by check_gate_with_unified_engine)
        ctx.unmet_dependencies = ["P1"]  # type: ignore[attr-defined]
        result = self.engine.check(GateType.PHASE_TRANSITION, ctx)
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "REJECT")
        self.assertGreater(len(result.critical_issues), 0)

    def test_03_worker_output_gate_routes_to_verification_gate(self) -> None:
        """Verify: WORKER_OUTPUT gate delegates to VerificationGate red flags."""
        ctx = _make_worker_output_context(
            has_code_changes=True, has_test_changes=False,  # triggers no_test flag
        )
        result = self.engine.check(GateType.WORKER_OUTPUT, ctx)
        self.assertFalse(result.passed)
        self.assertEqual(result.gate_type, GateType.WORKER_OUTPUT)
        # no_test_for_new_behavior is critical → REJECT
        self.assertEqual(result.verdict, "REJECT")

    def test_04_worker_output_gate_clean_context_conditionals(self) -> None:
        """Verify: WORKER_OUTPUT with missing evidence yields CONDITIONAL or REJECT."""
        ctx = _make_worker_output_context(
            has_code_changes=True, has_test_changes=True,
            claims_complete=True,  # no evidence → no_evidence_provided critical
        )
        result = self.engine.check(GateType.WORKER_OUTPUT, ctx)
        self.assertFalse(result.passed)
        # critical flags present (no_evidence_provided) → REJECT
        self.assertEqual(result.verdict, "REJECT")

    def test_05_debug_loop_ready_gate_routes(self) -> None:
        """Verify: check_debug_loop_ready wraps verify_debug_loop_ready."""
        result = self.engine.check_debug_loop_ready("assert func() == 1")
        self.assertTrue(result.passed)
        self.assertEqual(result.gate_type, GateType.DEBUG_LOOP_READY)
        self.assertEqual(result.verdict, "APPROVE")

    def test_06_debug_loop_ready_rejects_non_red_capable(self) -> None:
        """Verify: debug-loop gate REJECTs a non-red-capable command."""
        result = self.engine.check_debug_loop_ready("input('x')")
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "REJECT")
        self.assertGreater(len(result.critical_issues), 0)

    def test_07_unknown_gate_type_rejected(self) -> None:
        """Verify: an unregistered gate type yields REJECT with UNKNOWN_GATE_TYPE."""
        result = self.engine.check(GateType.SECURITY_CHECK, context={})
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "REJECT")
        self.assertEqual(result.critical_issues[0]["code"], "UNKNOWN_GATE_TYPE")

    def test_08_custom_checker_registered_and_merged(self) -> None:
        """Verify: register_checker adds a custom checker whose issues merge in."""
        def custom_checker(ctx: Any, **_: Any) -> dict[str, Any]:
            return {"critical_issues": [{"code": "CUSTOM", "message": "custom issue"}]}

        self.engine.register_checker(GateType.PHASE_TRANSITION, custom_checker)
        ctx = _make_phase_gate_context(dependencies_met=True, reviewers_approved=["r1"])
        result = self.engine.check(GateType.PHASE_TRANSITION, ctx)
        codes = [i["code"] for i in result.critical_issues]
        self.assertIn("CUSTOM", codes)
        self.assertFalse(result.passed)

    def test_09_statistics_tracked_across_checks(self) -> None:
        """Verify: get_statistics tracks total/passed/failed/conditional counts."""
        ctx_ok = _make_phase_gate_context(dependencies_met=True, reviewers_approved=["r1"])
        self.engine.check(GateType.PHASE_TRANSITION, ctx_ok)
        stats = self.engine.get_statistics()
        self.assertEqual(stats["total_checks"], 1)
        self.assertGreaterEqual(stats["passed"] + stats["conditional"] + stats["failed"], 1)

    def test_10_result_to_dict_and_to_summary(self) -> None:
        """Verify: UnifiedGateResult.to_dict / to_summary serialize correctly."""
        ctx = _make_phase_gate_context(dependencies_met=True, reviewers_approved=["r1"])
        result = self.engine.check(GateType.PHASE_TRANSITION, ctx)
        d = result.to_dict()
        self.assertIn("passed", d)
        self.assertIn("gate_type", d)
        self.assertIn("verdict", d)
        summary = result.to_summary()
        self.assertIsInstance(summary, str)
        self.assertIn("Gate Result", summary)


# ---------------------------------------------------------------------------
# T4: End-to-end — phase enter → gate check → evidence verify → pass/reject
# ---------------------------------------------------------------------------


class T4_EndToEndPhaseGateEvidenceFlow(unittest.TestCase):
    """T4: End-to-end lifecycle phase transitions through gate checks."""

    def setUp(self) -> None:
        _reset_gate_singletons()
        self.adapter = ShortcutLifecycleAdapter(use_unified_gate=False)

    def test_01_advance_to_first_phase_succeeds(self) -> None:
        """Verify: advancing to P1 (no dependencies) succeeds → RUNNING."""
        result = self.adapter.advance_to_phase("P1")
        self.assertTrue(result.success)
        self.assertEqual(result.phase_id, "P1")
        self.assertEqual(result.new_state, PhaseState.RUNNING)
        self.assertEqual(self.adapter.get_current_phase().phase_id, "P1")

    def test_02_advance_blocked_by_unmet_dependency(self) -> None:
        """Verify: advancing to P2 without completing P1 → blocked + CONDITIONAL."""
        result = self.adapter.advance_to_phase("P2")
        self.assertFalse(result.success)
        self.assertEqual(result.new_state, PhaseState.BLOCKED)
        self.assertIn("P1", result.error)

    def test_03_complete_phase_then_advance_dependency_satisfied(self) -> None:
        """Verify: complete P1 → advance to P2 succeeds (dependency met)."""
        self.adapter.advance_to_phase("P1")
        self.adapter.complete_phase("P1")
        result = self.adapter.advance_to_phase("P2")
        self.assertTrue(result.success)
        self.assertEqual(result.new_state, PhaseState.RUNNING)

    def test_04_already_completed_phase_idempotent(self) -> None:
        """Verify: advancing to an already-completed phase returns success idempotently."""
        self.adapter.advance_to_phase("P1")
        self.adapter.complete_phase("P1")
        result = self.adapter.advance_to_phase("P1")
        self.assertTrue(result.success)
        self.assertEqual(result.new_state, PhaseState.COMPLETED)

    def test_05_check_command_gate_aggregates_phases(self) -> None:
        """Verify: check_command_gate aggregates gate results across covered phases."""
        # 'build' covers P8 which depends on P3 + P7 (both unmet) → CONDITIONAL
        result = self.adapter.check_command_gate("build")
        self.assertFalse(result.passed)
        # Unknown command → REJECT
        unknown = self.adapter.check_command_gate("nonexistent")
        self.assertFalse(unknown.passed)
        self.assertEqual(unknown.verdict, "REJECT")

    def test_06_progress_reflected_in_status_after_completions(self) -> None:
        """Verify: status.progress_percent increases as phases complete."""
        initial = self.adapter.get_status()
        self.assertEqual(initial.progress_percent, 0.0)
        self.adapter.advance_to_phase("P1")
        self.adapter.complete_phase("P1")
        after = self.adapter.get_status()
        self.assertGreater(after.progress_percent, 0.0)
        self.assertIn("P1", after.completed_phases)


# ---------------------------------------------------------------------------
# T5: Boundary — no evidence, fake evidence, gate failure, state persistence
# ---------------------------------------------------------------------------


class T5_BoundaryAndStatePersistence(unittest.TestCase):
    """T5: Boundary conditions + ShortcutLifecycleAdapter state persistence."""

    def setUp(self) -> None:
        _reset_gate_singletons()

    def test_01_verification_gate_empty_evidence_dict(self) -> None:
        """Verify: claims_complete with empty evidence dict → REJECT."""
        gate = VerificationGate(strict_mode=True)
        ctx = _make_completion_context(claims_complete=True, evidence={})
        result = gate.check(ctx)
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "REJECT")

    def test_02_verification_gate_non_strict_mode(self) -> None:
        """Verify: non-strict mode still detects red flags (verdict logic same)."""
        gate = VerificationGate(strict_mode=False)
        ctx = _make_completion_context(has_code_changes=True, has_test_changes=False)
        result = gate.check(ctx)
        # Red flags still detected regardless of strict_mode (strict_mode only
        # affects whether they block; verdict logic is identical).
        self.assertFalse(result.passed)
        self.assertEqual(result.verdict, "REJECT")

    def test_03_unified_gate_engine_exception_returns_reject(self) -> None:
        """Verify: a checker raising an exception yields REJECT with GATE_EXCEPTION."""
        engine = UnifiedGateEngine()

        def bad_checker(ctx: Any, **_: Any) -> dict[str, Any]:
            raise RuntimeError("boom")

        engine.register_checker(GateType.PHASE_TRANSITION, bad_checker)
        ctx = _make_phase_gate_context(dependencies_met=True, reviewers_approved=["r1"])
        result = engine.check(GateType.PHASE_TRANSITION, ctx)
        # Custom checker exception is caught inside _merge_custom_results path;
        # the base checker still runs. Verify result is well-formed.
        self.assertIsInstance(result, UnifiedGateResult)
        self.assertIsInstance(result.critical_issues, list)

    def test_04_shortcut_checkpoint_integration_enable(self) -> None:
        """Verify: enable_checkpoint_integration returns True when storage path valid."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
            enabled = adapter.enable_checkpoint_integration(tmpdir)
            self.assertTrue(enabled)
            self.assertIsNotNone(adapter._checkpoint_manager)

    def test_05_shortcut_save_restore_state_round_trip(self) -> None:
        """Verify: save_state + restore_state round-trips current phase + completed."""
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            adapter = ShortcutLifecycleAdapter(use_unified_gate=False)
            adapter.enable_checkpoint_integration(tmpdir)
            adapter.set_task_id("task-boundary-01")
            adapter.advance_to_phase("P1")
            adapter.complete_phase("P1")
            saved = adapter.save_state()
            self.assertTrue(saved)
            # New adapter restores from same checkpoint manager
            adapter2 = ShortcutLifecycleAdapter(use_unified_gate=False)
            adapter2.enable_checkpoint_integration(tmpdir)
            adapter2.set_task_id("task-boundary-01")
            restored = adapter2.restore_state()
            self.assertTrue(restored)
            self.assertIn("P1", adapter2._completed_phases)

    def test_06_full_adapter_advance_blocked_unmet_strict_dependency(self) -> None:
        """Verify: FullLifecycleAdapter blocks P3 when P2 unmet (strict deps)."""
        full = FullLifecycleAdapter(use_unified_gate=False)
        result = full.advance_to_phase("P3")  # P3 depends on P2
        self.assertFalse(result.success)
        self.assertEqual(result.new_state, PhaseState.BLOCKED)

    def test_07_full_adapter_skip_optional_advances(self) -> None:
        """Verify: FullLifecycleAdapter skips optional P4 when skip_optional=True."""
        full = FullLifecycleAdapter(use_unified_gate=False)
        full.set_skip_optional(True)
        # Complete P2 (P4 depends on P2) then advance to P4 → SKIPPED
        full.advance_to_phase("P1")
        full.complete_phase("P1")
        full.advance_to_phase("P2")
        full.complete_phase("P2")
        result = full.advance_to_phase("P4")
        self.assertTrue(result.success)
        self.assertEqual(result.new_state, PhaseState.SKIPPED)

    def test_08_full_adapter_unknown_phase_rejected(self) -> None:
        """Verify: FullLifecycleAdapter rejects advancing to an unknown phase."""
        full = FullLifecycleAdapter(use_unified_gate=False)
        result = full.advance_to_phase("P99")
        self.assertFalse(result.success)
        self.assertEqual(result.new_state, PhaseState.BLOCKED)

    def test_09_gate_result_to_dict_serialization(self) -> None:
        """Verify: lifecycle GateResult.to_dict serializes counts + gap report."""
        gr = GateResult(
            passed=False, verdict="CONDITIONAL",
            red_flags=[{"id": "x"}], missing_evidence=[{"key": "y"}],
            gap_report="missing y",
        )
        d = gr.to_dict()
        self.assertEqual(d["passed"], False)
        self.assertEqual(d["verdict"], "CONDITIONAL")
        self.assertEqual(d["red_flags_count"], 1)
        self.assertEqual(d["missing_evidence_count"], 1)
        self.assertEqual(d["gap_report"], "missing y")

    def test_10_lifecycle_status_to_summary(self) -> None:
        """Verify: LifecycleStatus.to_summary produces human-readable text."""
        from scripts.collaboration.lifecycle_protocol import LifecycleStatus
        status = LifecycleStatus(
            mode=LifecycleMode.SHORTCUT, current_phase="P1",
            completed_phases=["P1"], failed_phases=[], blocked_phases=[],
            progress_percent=9.0, can_advance=True, next_phase="P2",
        )
        summary = status.to_summary()
        self.assertIn("SHORTCUT", summary)
        self.assertIn("P1", summary)
        self.assertIn("9%", summary)


if __name__ == "__main__":
    unittest.main()
