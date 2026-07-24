#!/usr/bin/env python3
"""EventBus + DispatchHooks + ResultAssembler Integration Tests
(V4.2.1 P2-3 — Test Pyramid Lift).

End-to-end integration tests for the dispatch-event trio. Verifies
CROSS-MODULE interactions among:

    scripts/collaboration/event_bus.py              — EventBus (synchronous
        pub/sub: on/emit/off/clear; swallows handler errors)
    scripts/collaboration/dispatch_hooks.py         — DispatchHooks
        (post_dispatch_hooks, post_execution_processing, slice_outputs,
        check_anchor_drift)
    scripts/collaboration/dispatch_result_assembler.py — ResultAssembler
        (assembles the final DispatchResult; build_step_timings;
        build_lifecycle_trace)
    scripts/collaboration/dispatch_models.py        — DispatchResult dataclass

Flow:
    1. EventBus.on(event, handler) → emit(event, **kwargs) → handler called
    2. DispatchHooks.post_dispatch_hooks(result, ...) → history + perf record
    3. ResultAssembler.assemble(...) → DispatchResult
    4. End-to-end: emit → hooks fire → result assembled from hook outputs

Test categories:
    T1: EventBus on/emit/off/clear basic subscriptions
    T2: DispatchHooks post_dispatch_hooks + slice_outputs + check_anchor_drift
    T3: ResultAssembler assemble + build_step_timings + build_lifecycle_trace
    T4: End-to-end: dispatch completes → emit → hooks → result assembled
    T5: Boundary (no subscribers, off after emit, exception handler, async)
"""

from __future__ import annotations

import os
import sys
import threading
import unittest
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatch_hooks import DispatchHooks
from scripts.collaboration.dispatch_models import DispatchResult, PerformanceMetric
from scripts.collaboration.dispatch_result_assembler import (
    DISPATCH_LIFECYCLE_MAPPING,
    ResultAssembler,
)
from scripts.collaboration.event_bus import EventBus
from scripts.collaboration.scratchpad import Scratchpad

# ---------------------------------------------------------------------------
# Stub collaborators (the real classes pull in heavy dispatch dependencies;
# these stubs honor the exact method signatures DispatchHooks/ResultAssembler
# call, so we test the trio's integration logic in isolation).
# ---------------------------------------------------------------------------


class _StubSeverity(Enum):
    """Stub for AnchorSeverity used by ResultAssembler._build_anchor_dict."""
    OK = "ok"
    WARN = "warn"
    CRITICAL = "critical"


@dataclass
class _AnchorResult:
    """Stub for AnchorChecker.check() return value."""
    aligned: bool = True
    coverage: float = 1.0
    drift_score: float = 0.0
    recommendation: str = "ok"
    severity: _StubSeverity = _StubSeverity.OK


class _StubAnchorChecker:
    def __init__(self, aligned: bool = True, recommendation: str = "ok") -> None:
        sev = _StubSeverity.OK if aligned else _StubSeverity.CRITICAL
        self._result = _AnchorResult(aligned=aligned, recommendation=recommendation, severity=sev)
        self.check_calls: list[dict[str, Any]] = []

    def check(self, goal: Any, current_output: str, trigger: Any) -> _AnchorResult:
        self.check_calls.append({
            "goal": goal, "current_output": current_output, "trigger": trigger,
        })
        return self._result


class _StubOutputSlicer:
    def __init__(self, max_slice_lines: int = 10) -> None:
        self.max_slice_lines = max_slice_lines
        self.slice_calls: list[str] = []

    def slice_output(self, output: str, role_id: str = "unknown") -> list[str]:
        self.slice_calls.append(output)
        return [output[: len(output) // 2], output[len(output) // 2 :]]


class _StubUsageTracker:
    def __init__(self) -> None:
        self.ticks: list[str] = []

    def tick(self, name: str) -> None:
        self.ticks.append(name)


class _StubPerfMonitor:
    def __init__(self) -> None:
        self.records: list[PerformanceMetric] = []

    def record(self, metric: PerformanceMetric) -> None:
        self.records.append(metric)


class _StubQualityReport:
    def to_markdown(self) -> str:
        return "# Quality Report"


class _StubEnterprise:
    def __init__(self, fail_audit: bool = False) -> None:
        self._fail = fail_audit
        self.masked: list[str] = []

    def audit_quality(self) -> _StubQualityReport:
        if self._fail:
            raise RuntimeError("audit failed")
        return _StubQualityReport()

    def apply_data_masking(self, text: str) -> str:
        self.masked.append(text)
        return text


class _StubCoordinator:
    def __init__(self, scratchpad: str = "sp-summary", report: str = "REPORT") -> None:
        self._sp = scratchpad
        self._report = report

    def collect_results(self) -> dict[str, Any]:
        return {"scratchpad": self._sp, "other": "x"}

    def generate_report(self) -> str:
        return self._report


class _StubReportFormatter:
    def build_summary(self, task: str, roles: list[str], exec_result: Any, sp: str) -> str:
        return f"summary:{task}:{len(roles)}:{sp}"


class _StubConcernLoader:
    def get_pack_info(self, packs: Any) -> list[dict[str, Any]]:
        if not packs:
            return []
        return [{"name": "pack1", "description": "d"}]


@dataclass
class _StubExecResult:
    success: bool = True
    completed_tasks: int = 3
    failed_tasks: int = 0


@dataclass
class _StubPlan:
    total_tasks: int = 3


@dataclass
class _StubIntentMatch:
    intent_type: str = "feature"
    workflow_chain: list[str] = field(default_factory=lambda: ["plan", "execute"])
    confidence: float = 0.8
    suggested_next_steps: list[str] = field(default_factory=lambda: ["next"])


@dataclass
class _StubRetrospective:
    def to_dict(self) -> dict[str, Any]:
        return {"improvements": 2}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_hooks(
    *,
    enable_quality_guard: bool = True,
    anchor_aligned: bool = True,
    max_history: int = 5,
) -> tuple[DispatchHooks, _StubCoordinator, _StubEnterprise, _StubPerfMonitor,
          _StubAnchorChecker, _StubOutputSlicer, _StubUsageTracker, list]:
    """Build a DispatchHooks wired with stub collaborators. Returns the hooks
    plus the stubs so tests can assert on their state."""
    coordinator = _StubCoordinator()
    enterprise = _StubEnterprise()
    perf_monitor = _StubPerfMonitor()
    anchor_checker = _StubAnchorChecker(aligned=anchor_aligned)
    slicer = _StubOutputSlicer()
    usage_tracker = _StubUsageTracker()
    history: list[DispatchResult] = []
    hooks = DispatchHooks(
        coordinator=coordinator,
        enterprise=enterprise,
        quality_guard=True,
        perf_monitor=perf_monitor,
        anchor_checker=anchor_checker,
        output_slicer=slicer,
        scratchpad=Scratchpad(),
        usage_tracker=usage_tracker,
        dispatch_history=history,
        max_history=max_history,
        enable_quality_guard=enable_quality_guard,
    )
    return (hooks, coordinator, enterprise, perf_monitor, anchor_checker,
            slicer, usage_tracker, history)


def _make_result(success: bool = True, timing: dict[str, float] | None = None,
                 errors: list[str] | None = None) -> DispatchResult:
    """Build a minimal DispatchResult for hook/assembler tests."""
    return DispatchResult(
        success=success,
        task_description="test task",
        details={"timing": timing or {}},
        errors=errors or [],
    )


def _make_assembler() -> ResultAssembler:
    return ResultAssembler(
        concern_loader=_StubConcernLoader(),
        report_formatter=_StubReportFormatter(),
    )


# ---------------------------------------------------------------------------
# T1: EventBus on/emit/off/clear
# ---------------------------------------------------------------------------


class T1_EventBusBasicSubscriptions(unittest.TestCase):
    """T1: EventBus on/emit/off/clear basic event subscriptions."""

    def setUp(self) -> None:
        self._bus = EventBus()

    def tearDown(self) -> None:
        self._bus.clear()

    def test_01_on_then_emit_calls_handler(self) -> None:
        """Verify: a registered handler is invoked when the event is emitted."""
        calls: list[dict[str, Any]] = []
        self._bus.on("dispatch.started", lambda **kw: calls.append(kw))
        self._bus.emit("dispatch.started", task="t1", role="architect")
        self.assertEqual(calls, [{"task": "t1", "role": "architect"}])

    def test_02_multiple_handlers_all_invoked(self) -> None:
        """Verify: all handlers registered for an event are called in order."""
        order: list[int] = []
        self._bus.on("e", lambda **_kw: order.append(1))
        self._bus.on("e", lambda **_kw: order.append(2))
        self._bus.on("e", lambda **_kw: order.append(3))
        self._bus.emit("e")
        self.assertEqual(order, [1, 2, 3])

    def test_03_off_removes_specific_handler(self) -> None:
        """Verify: off(event, handler) removes only that handler."""
        calls: list[int] = []

        def h1(**kw: Any) -> None:
            calls.append(1)

        def h2(**kw: Any) -> None:
            calls.append(2)

        self._bus.on("e", h1)
        self._bus.on("e", h2)
        self._bus.off("e", h1)
        self._bus.emit("e")
        self.assertEqual(calls, [2])

    def test_04_off_without_handler_removes_all(self) -> None:
        """Verify: off(event) with no handler removes every handler for the event."""
        calls: list[int] = []
        self._bus.on("e", lambda **_kw: calls.append(1))
        self._bus.on("e", lambda **_kw: calls.append(2))
        self._bus.off("e")
        self._bus.emit("e")
        self.assertEqual(calls, [])

    def test_05_clear_removes_all_handlers(self) -> None:
        """Verify: clear() wipes every handler across all events."""
        calls: list[int] = []
        self._bus.on("a", lambda **_kw: calls.append(1))
        self._bus.on("b", lambda **_kw: calls.append(2))
        self._bus.clear()
        self._bus.emit("a")
        self._bus.emit("b")
        self.assertEqual(calls, [])

    def test_06_emit_with_no_subscribers_is_noop(self) -> None:
        """Verify: emitting an event with no handlers does not raise."""
        self._bus.emit("nobody.listening", data=42)

    def test_07_emit_passes_kwargs_to_handler(self) -> None:
        """Verify: arbitrary kwargs flow through to the handler."""
        received: dict[str, Any] = {}
        self._bus.on("e", lambda **kw: received.update(kw))
        self._bus.emit("e", a=1, b="two", c=[3])
        self.assertEqual(received, {"a": 1, "b": "two", "c": [3]})

    def test_08_off_unknown_event_is_noop(self) -> None:
        """Verify: off on an event with no handlers does not raise."""
        self._bus.off("never.registered")


# ---------------------------------------------------------------------------
# T2: DispatchHooks post_dispatch_hooks + slice_outputs + check_anchor_drift
# ---------------------------------------------------------------------------


class T2_DispatchHooksIntegration(unittest.TestCase):
    """T2: DispatchHooks post_dispatch_hooks / slice_outputs / check_anchor_drift."""

    def test_01_post_dispatch_hooks_appends_to_history(self) -> None:
        """Verify: post_dispatch_hooks records the result in dispatch_history."""
        hooks, *_ , history = _make_hooks()
        result = _make_result()
        hooks.post_dispatch_hooks(result, task="t", role_ids=["architect"], total_duration=1.2)
        self.assertEqual(len(history), 1)
        self.assertIs(history[0], result)

    def test_02_post_dispatch_hooks_records_performance_metric(self) -> None:
        """Verify: post_dispatch_hooks records a PerformanceMetric on perf_monitor."""
        hooks, _, _, perf, *_ = _make_hooks()
        result = _make_result(timing={"execute": 0.5})
        hooks.post_dispatch_hooks(result, task="task-desc", role_ids=["a", "b"], total_duration=2.0)
        self.assertEqual(len(perf.records), 1)
        metric = perf.records[0]
        self.assertEqual(metric.task_description, "task-desc")
        self.assertEqual(metric.total_duration, 2.0)
        self.assertEqual(metric.role_count, 2)
        self.assertTrue(metric.success)
        self.assertEqual(metric.error_count, 0)

    def test_03_post_dispatch_hooks_runs_quality_audit_when_enabled(self) -> None:
        """Verify: with enable_quality_guard the quality_report is populated."""
        hooks, _, enterprise, *_ = _make_hooks(enable_quality_guard=True)
        result = _make_result()
        hooks.post_dispatch_hooks(result, task="t", role_ids=[], total_duration=0.1)
        self.assertEqual(result.quality_report, "# Quality Report")

    def test_04_post_dispatch_hooks_skips_quality_audit_when_disabled(self) -> None:
        """Verify: with enable_quality_guard=False no quality_report is set."""
        hooks, *_ = _make_hooks(enable_quality_guard=False)
        result = _make_result()
        hooks.post_dispatch_hooks(result, task="t", role_ids=[], total_duration=0.1)
        self.assertIsNone(result.quality_report)

    def test_05_post_dispatch_hooks_trims_history_beyond_max(self) -> None:
        """Verify: history is trimmed to max_history entries.

        Note: post_dispatch_hooks rebinds ``self._dispatch_history`` to a fresh
        slice when the cap is exceeded (source behavior), so the trim must be
        observed on the hooks' internal reference, not the original list object.
        """
        hooks, *_ = _make_hooks(max_history=3)
        for i in range(5):
            hooks.post_dispatch_hooks(_make_result(), task=f"t{i}", role_ids=[], total_duration=0.1)
        self.assertEqual(len(hooks._dispatch_history), 3)

    def test_06_slice_outputs_truncates_oversized_output(self) -> None:
        """Verify: slice_outputs slices outputs longer than max_slice_lines*50."""
        hooks, _, _, _, _, slicer, usage, _ = _make_hooks()
        big = "line\n" * 1000  # well above max_slice_lines(10)*50 = 500 chars
        worker_results = [{"output": big, "role_id": "architect"}]
        hooks.slice_outputs(worker_results, [])
        self.assertEqual(len(slicer.slice_calls), 1)
        self.assertTrue(worker_results[0].get("_sliced"))
        self.assertIn("output_sliced", usage.ticks)

    def test_07_slice_outputs_leaves_small_output_unchanged(self) -> None:
        """Verify: outputs below the slice threshold are not sliced."""
        hooks, _, _, _, _, slicer, *_ = _make_hooks()
        small = "short output"
        worker_results = [{"output": small, "role_id": "tester"}]
        hooks.slice_outputs(worker_results, [])
        self.assertEqual(slicer.slice_calls, [])
        self.assertNotIn("_sliced", worker_results[0])

    def test_08_check_anchor_drift_aligned_returns_result(self) -> None:
        """Verify: when anchor is aligned, the result is returned unchanged."""
        hooks, _, _, _, anchor, _, usage, _ = _make_hooks(anchor_aligned=True)
        res = hooks.check_anchor_drift(
            worker_results=[{"output": "done"}], structured_goal="goal", scratchpad_summary="sp"
        )
        self.assertTrue(res.aligned)
        self.assertNotIn("anchor_drift_detected", usage.ticks)

    def test_09_check_anchor_drift_misaligned_ticks_usage(self) -> None:
        """Verify: a misaligned anchor records an anchor_drift_detected tick."""
        hooks, _, _, _, anchor, _, usage, _ = _make_hooks(anchor_aligned=False)
        res = hooks.check_anchor_drift(
            worker_results=[{"output": "partial"}], structured_goal="goal", scratchpad_summary=""
        )
        self.assertFalse(res.aligned)
        self.assertIn("anchor_drift_detected", usage.ticks)

    def test_10_check_anchor_drift_no_checker_returns_none(self) -> None:
        """Verify: with anchor_checker=None the drift check returns None."""
        hooks, *_ = _make_hooks()
        hooks.anchor_checker = None
        self.assertIsNone(
            hooks.check_anchor_drift([], structured_goal="g", scratchpad_summary="")
        )

    def test_11_check_anchor_drift_no_goal_returns_none(self) -> None:
        """Verify: with structured_goal falsy the drift check returns None."""
        hooks, *_ = _make_hooks()
        self.assertIsNone(
            hooks.check_anchor_drift([], structured_goal=None, scratchpad_summary="")
        )

    def test_12_post_execution_processing_returns_summary_and_collection(self) -> None:
        """Verify: post_execution_processing returns (summary, anchor, collection, errors, timing)."""
        hooks, coordinator, *_ = _make_hooks(anchor_aligned=True)
        summary, anchor, collection, errors, timing = hooks.post_execution_processing(
            worker_results=[{"output": "out"}], structured_goal="goal"
        )
        self.assertEqual(summary, "sp-summary")
        self.assertTrue(anchor.aligned)
        self.assertIn("scratchpad", collection)
        self.assertIsInstance(errors, list)
        self.assertIn("step8_time", timing)


# ---------------------------------------------------------------------------
# T3: ResultAssembler assemble + build_step_timings + build_lifecycle_trace
# ---------------------------------------------------------------------------


class T3_ResultAssemblerIntegration(unittest.TestCase):
    """T3: ResultAssembler.assemble + static timing/trace helpers."""

    def test_01_assemble_builds_successful_dispatch_result(self) -> None:
        """Verify: assemble produces a DispatchResult with success=True when no errors."""
        assembler = _make_assembler()
        result = assembler.assemble(
            task_description="build feature",
            role_ids=["architect", "tester"],
            exec_result=_StubExecResult(success=True, completed_tasks=3, failed_tasks=0),
            scratchpad_summary="sp summary",
            consensus_records=[{"topic": "x", "outcome": "APPROVED"}],
            compression_info={"level": "light"},
            memory_stats={"total_memories": 5},
            permission_checks=[{"action": "read", "allowed": True, "decision": "ok"}],
            skill_proposals=[{"title": "s", "confidence": 0.9}],
            anchor_result=None,
            retrospective_report=None,
            intent_match=_StubIntentMatch(),
            five_axis_result=None,
            errors=[],
            lang="en",
            concern_packs=None,
            total_duration=4.2,
            plan=_StubPlan(total_tasks=3),
            step_timings={"execute": 1.0},
            worker_results=[{"role_id": "architect", "output": "ok", "success": True}],
            coordinator=_StubCoordinator(),
        )
        self.assertTrue(result.success)
        self.assertEqual(result.task_description, "build feature")
        self.assertEqual(result.matched_roles, ["architect", "tester"])
        self.assertIn("plan_total_tasks", result.details)
        self.assertEqual(result.duration_seconds, 4.2)
        self.assertEqual(result.suggested_next_steps, ["next"])

    def test_02_assemble_marks_failed_when_errors_present(self) -> None:
        """Verify: assemble sets success=False when the errors list is non-empty."""
        assembler = _make_assembler()
        result = assembler.assemble(
            task_description="failing task",
            role_ids=[],
            exec_result=_StubExecResult(success=True),
            scratchpad_summary="",
            consensus_records=[],
            compression_info=None,
            memory_stats=None,
            permission_checks=[],
            skill_proposals=[],
            anchor_result=None,
            retrospective_report=None,
            intent_match=None,
            five_axis_result=None,
            errors=["boom"],
            lang="zh",
            concern_packs=None,
            total_duration=0.5,
            plan=_StubPlan(total_tasks=1),
            step_timings={},
            worker_results=[],
            coordinator=_StubCoordinator(),
        )
        self.assertFalse(result.success)

    def test_03_assemble_marks_failed_when_exec_failed(self) -> None:
        """Verify: assemble sets success=False when exec_result.success is False."""
        assembler = _make_assembler()
        result = assembler.assemble(
            task_description="t",
            role_ids=[],
            exec_result=_StubExecResult(success=False, completed_tasks=0, failed_tasks=2),
            scratchpad_summary="",
            consensus_records=[],
            compression_info=None,
            memory_stats=None,
            permission_checks=[],
            skill_proposals=[],
            anchor_result=None,
            retrospective_report=None,
            intent_match=None,
            five_axis_result=None,
            errors=[],
            lang="zh",
            concern_packs=None,
            total_duration=1.0,
            plan=_StubPlan(total_tasks=2),
            step_timings={},
            worker_results=[],
            coordinator=_StubCoordinator(),
        )
        self.assertFalse(result.success)

    def test_04_assemble_applies_data_masking_with_enterprise(self) -> None:
        """Verify: when enterprise is provided, apply_data_masking is called on the summary."""
        assembler = _make_assembler()
        enterprise = _StubEnterprise()
        result = assembler.assemble(
            task_description="t",
            role_ids=["architect"],
            exec_result=_StubExecResult(),
            scratchpad_summary="secret summary",
            consensus_records=[],
            compression_info=None,
            memory_stats=None,
            permission_checks=[],
            skill_proposals=[],
            anchor_result=None,
            retrospective_report=None,
            intent_match=None,
            five_axis_result=None,
            errors=[],
            lang="en",
            concern_packs=None,
            total_duration=0.1,
            plan=_StubPlan(),
            step_timings={},
            worker_results=[],
            coordinator=_StubCoordinator(),
            enterprise=enterprise,
        )
        self.assertEqual(enterprise.masked, ["secret summary"])
        self.assertEqual(result.scratchpad_summary, "secret summary")

    def test_05_assemble_builds_anchor_dict_when_present(self) -> None:
        """Verify: assemble converts an anchor_result object into a dict on the result."""
        assembler = _make_assembler()
        anchor = _AnchorResult(aligned=False, coverage=0.4, drift_score=0.6,
                               recommendation="realign")
        result = assembler.assemble(
            task_description="t", role_ids=[], exec_result=_StubExecResult(),
            scratchpad_summary="", consensus_records=[], compression_info=None,
            memory_stats=None, permission_checks=[], skill_proposals=[],
            anchor_result=anchor, retrospective_report=None, intent_match=None,
            five_axis_result=None, errors=[], lang="zh", concern_packs=None,
            total_duration=0.0, plan=_StubPlan(), step_timings={},
            worker_results=[], coordinator=_StubCoordinator(),
        )
        self.assertIsNotNone(result.anchor_result)
        self.assertFalse(result.anchor_result["aligned"])
        self.assertEqual(result.anchor_result["recommendation"], "realign")

    def test_06_assemble_includes_concern_packs_when_provided(self) -> None:
        """Verify: concern_packs are resolved through the concern_loader."""
        assembler = _make_assembler()
        result = assembler.assemble(
            task_description="t", role_ids=[], exec_result=_StubExecResult(),
            scratchpad_summary="", consensus_records=[], compression_info=None,
            memory_stats=None, permission_checks=[], skill_proposals=[],
            anchor_result=None, retrospective_report=None, intent_match=None,
            five_axis_result=None, errors=[], lang="zh", concern_packs="some-pack",
            total_duration=0.0, plan=_StubPlan(), step_timings={},
            worker_results=[], coordinator=_StubCoordinator(),
        )
        self.assertEqual(len(result.concern_packs), 1)
        self.assertEqual(result.concern_packs[0]["name"], "pack1")

    def test_07_build_step_timings_returns_eleven_named_deltas(self) -> None:
        """Verify: build_step_timings computes 11 deltas from 12 timestamps."""
        # Monotonic timestamps 0..11 → each delta = 1.0.
        times = [float(i) for i in range(12)]
        timings = ResultAssembler.build_step_timings(*times)
        expected_names = {
            "analyze", "warmup", "plan", "spawn", "execute", "collect",
            "consensus", "compress", "permission", "memory", "skillify",
        }
        self.assertEqual(set(timings.keys()), expected_names)
        for v in timings.values():
            self.assertEqual(v, 1.0)

    def test_08_build_lifecycle_trace_aggregates_phases(self) -> None:
        """Verify: build_lifecycle_trace maps steps to lifecycle phases."""
        trace = ResultAssembler.build_lifecycle_trace({
            "analyze": 1.0, "execute": 2.0, "collect": 0.5, "permission": 0.2,
        })
        self.assertEqual(trace["mapping_version"], "1.0")
        # analyze → P1, execute → P3, collect → P4, permission → P6.
        self.assertIn("P1_Requirements", trace["lifecycle_phases"])
        self.assertIn("P3_Implementation", trace["lifecycle_phases"])
        self.assertEqual(trace["lifecycle_phases"]["P3_Implementation"], 2.0)
        self.assertIn("analyze", trace["phase_steps"]["P1_Requirements"])

    def test_09_build_lifecycle_trace_unknown_step_falls_to_delivery(self) -> None:
        """Verify: an unrecognized step name maps to P10_Delivery."""
        trace = ResultAssembler.build_lifecycle_trace({"mystery_step": 3.0})
        self.assertIn("P10_Delivery", trace["lifecycle_phases"])
        self.assertEqual(trace["lifecycle_phases"]["P10_Delivery"], 3.0)

    def test_10_dispatch_lifecycle_mapping_covers_all_dispatch_steps(self) -> None:
        """Verify: DISPATCH_LIFECYCLE_MAPPING has step0..step20 keys."""
        # The mapping keys follow stepN_<name>; assert a representative subset.
        self.assertIn("step0_tenant_setup", DISPATCH_LIFECYCLE_MAPPING)
        self.assertIn("step8_execute", DISPATCH_LIFECYCLE_MAPPING)
        self.assertIn("step16_assemble", DISPATCH_LIFECYCLE_MAPPING)
        self.assertIn("step17_hooks", DISPATCH_LIFECYCLE_MAPPING)
        self.assertIn("step20_tech_debt", DISPATCH_LIFECYCLE_MAPPING)


# ---------------------------------------------------------------------------
# T4: End-to-end — emit → hooks fire → result assembled
# ---------------------------------------------------------------------------


class T4_EndToEndEventHookAssemble(unittest.TestCase):
    """T4: EventBus drives DispatchHooks; ResultAssembler consumes hook outputs."""

    def test_01_emit_dispatch_completed_triggers_post_dispatch_hooks(self) -> None:
        """Verify: emitting dispatch.completed fires post_dispatch_hooks via the bus."""
        bus = EventBus()
        hooks, *_ , history, = _make_hooks()
        result = _make_result()
        try:
            bus.on("dispatch.completed",
                   lambda **kw: hooks.post_dispatch_hooks(
                       result, task=kw["task"], role_ids=kw["roles"],
                       total_duration=kw["duration"]))
            bus.emit("dispatch.completed", task="t", roles=["architect"], duration=1.5)
            self.assertEqual(len(history), 1)
            self.assertIs(history[0], result)
        finally:
            bus.clear()

    def test_02_post_execution_then_assemble_produces_full_result(self) -> None:
        """Verify: post_execution_processing feeds into assemble end-to-end."""
        hooks, coordinator, *_ = _make_hooks(anchor_aligned=True)
        assembler = _make_assembler()
        summary, anchor, collection, errors, timing = hooks.post_execution_processing(
            worker_results=[{"output": "worker-out", "role_id": "architect"}],
            structured_goal="ship feature",
        )
        result = assembler.assemble(
            task_description="ship feature",
            role_ids=["architect"],
            exec_result=_StubExecResult(),
            scratchpad_summary=summary,
            consensus_records=[],
            compression_info=None,
            memory_stats=None,
            permission_checks=[],
            skill_proposals=[],
            anchor_result=anchor,
            retrospective_report=_StubRetrospective(),
            intent_match=_StubIntentMatch(),
            five_axis_result=None,
            errors=errors,
            lang="en",
            concern_packs=None,
            total_duration=2.0,
            plan=_StubPlan(),
            step_timings=timing,
            worker_results=[{"role_id": "architect", "output": "worker-out", "success": True}],
            coordinator=coordinator,
        )
        self.assertTrue(result.success)
        self.assertIsNotNone(result.anchor_result)
        self.assertTrue(result.anchor_result["aligned"])
        self.assertIsNotNone(result.retrospective_report)

    def test_03_event_chain_collect_then_hooks_then_assemble(self) -> None:
        """Verify: a multi-event chain (collect → hooks → assemble) completes."""
        bus = EventBus()
        hooks, coordinator, _, perf, *_ = _make_hooks(anchor_aligned=True)
        events: list[str] = []
        try:
            bus.on("dispatch.executing", lambda **_kw: events.append("executing"))
            bus.on("dispatch.completed",
                   lambda **kw: hooks.post_dispatch_hooks(
                       _make_result(), task=kw["task"], role_ids=[], total_duration=0.1))
            bus.emit("dispatch.executing")
            bus.emit("dispatch.completed", task="t")
            self.assertEqual(events, ["executing"])
            self.assertEqual(len(perf.records), 1)
        finally:
            bus.clear()

    def test_04_anchor_drift_warning_propagates_to_assembled_result(self) -> None:
        """Verify: a misaligned anchor from hooks surfaces in the assembled result."""
        hooks, coordinator, *_ = _make_hooks(anchor_aligned=False)
        assembler = _make_assembler()
        _, anchor, _, errors, timing = hooks.post_execution_processing(
            worker_results=[{"output": "drifted"}], structured_goal="goal"
        )
        result = assembler.assemble(
            task_description="t", role_ids=[], exec_result=_StubExecResult(),
            scratchpad_summary="sp", consensus_records=[], compression_info=None,
            memory_stats=None, permission_checks=[], skill_proposals=[],
            anchor_result=anchor, retrospective_report=None, intent_match=None,
            five_axis_result=None, errors=errors, lang="zh", concern_packs=None,
            total_duration=0.0, plan=_StubPlan(), step_timings=timing,
            worker_results=[], coordinator=coordinator,
        )
        self.assertFalse(result.anchor_result["aligned"])


# ---------------------------------------------------------------------------
# T5: Boundary (no subscribers, off after emit, exception handler, async)
# ---------------------------------------------------------------------------


class T5_BoundaryAndExceptions(unittest.TestCase):
    """T5: Boundary conditions and graceful exception handling."""

    def setUp(self) -> None:
        self._bus = EventBus()

    def tearDown(self) -> None:
        self._bus.clear()

    def test_01_handler_raising_value_error_is_swallowed(self) -> None:
        """Verify: a handler raising ValueError is swallowed by emit()."""
        calls: list[int] = []

        def bad(**kw: Any) -> None:
            calls.append(1)
            raise ValueError("boom")

        def good(**kw: Any) -> None:
            calls.append(2)

        self._bus.on("e", bad)
        self._bus.on("e", good)
        self._bus.emit("e")  # must not raise
        self.assertEqual(calls, [1, 2])

    def test_02_handler_raising_type_error_is_swallowed(self) -> None:
        """Verify: a handler raising TypeError is swallowed by emit()."""
        def bad(**kw: Any) -> None:
            raise TypeError("type boom")

        self._bus.on("e", bad)
        self._bus.emit("e")  # must not raise

    def test_03_emit_after_off_does_not_call_handler(self) -> None:
        """Verify: after off, a subsequent emit does not invoke the handler."""
        calls: list[int] = []

        def h(**kw: Any) -> None:
            calls.append(1)

        self._bus.on("e", h)
        self._bus.emit("e")
        self._bus.off("e", h)
        self._bus.emit("e")
        self.assertEqual(calls, [1])

    def test_04_concurrent_emit_and_on_is_safe(self) -> None:
        """Verify: concurrent emit + on from many threads does not corrupt."""
        calls: list[int] = []
        lock = threading.Lock()
        errors: list[Exception] = []

        def emitter(idx: int) -> None:
            try:
                self._bus.emit("e", idx=idx)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        def registrar(idx: int) -> None:
            try:
                def h(**kw: Any) -> None:
                    with lock:
                        calls.append(1)
                self._bus.on("e", h)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=emitter, args=(i,)) for i in range(15)]
        threads += [threading.Thread(target=registrar, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])

    def test_05_off_then_on_again_re_registers(self) -> None:
        """Verify: a handler removed by off can be re-registered and fires."""
        calls: list[int] = []

        def h(**kw: Any) -> None:
            calls.append(1)

        self._bus.on("e", h)
        self._bus.off("e", h)
        self._bus.on("e", h)
        self._bus.emit("e")
        self.assertEqual(calls, [1])

    def test_06_post_dispatch_hooks_with_empty_timing_dict(self) -> None:
        """Verify: post_dispatch_hooks handles a result with no timing details."""
        hooks, *_ = _make_hooks()
        result = DispatchResult(success=True, task_description="t", details={})
        hooks.post_dispatch_hooks(result, task="t", role_ids=[], total_duration=0.0)
        # Should not raise; perf metric recorded with empty step_timings.
        self.assertEqual(len(result.errors), 0)

    def test_07_assemble_with_none_intent_and_retrospective(self) -> None:
        """Verify: assemble tolerates None intent_match and retrospective_report."""
        assembler = _make_assembler()
        result = assembler.assemble(
            task_description="t", role_ids=[], exec_result=_StubExecResult(),
            scratchpad_summary="", consensus_records=[], compression_info=None,
            memory_stats=None, permission_checks=[], skill_proposals=[],
            anchor_result=None, retrospective_report=None, intent_match=None,
            five_axis_result=None, errors=[], lang="zh", concern_packs=None,
            total_duration=0.0, plan=_StubPlan(), step_timings={},
            worker_results=[], coordinator=_StubCoordinator(),
        )
        self.assertIsNone(result.intent_match)
        self.assertIsNone(result.retrospective_report)
        self.assertEqual(result.suggested_next_steps, [])


if __name__ == "__main__":
    unittest.main()
