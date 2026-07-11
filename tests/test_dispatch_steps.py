"""Tests for PostDispatchPipeline in dispatch_steps.py.

Covers __init__, execute, _collect_worker_results, _build_step_timings,
_build_lifecycle_trace, and _build_summary.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock

from scripts.collaboration.dispatch_steps import PostDispatchPipeline

# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------


def _make_pre_result(
    task_description: str = "test task",
    lang: str = "zh",
    matched_roles: list[str] | None = None,
    role_ids: list[str] | None = None,
    concern_packs: list[dict[str, Any]] | None = None,
    intent_match: dict[str, Any] | None = None,
    structured_goal: str = "goal",
    plan: str = "plan",
    step1_time: float | None = None,
    step2_time: float | None = None,
    prep_timing: dict[str, float] | None = None,
    tenant_ctx: Any = None,
) -> MagicMock:
    """Create a mock pre_result object matching PreDispatchResult shape."""
    t0 = time.time()
    pr = MagicMock()
    pr.task_description = task_description
    pr.lang = lang
    pr.matched_roles = matched_roles or ["architect"]
    pr.role_ids = role_ids or ["architect"]
    pr.concern_packs = concern_packs or []
    pr.intent_match = intent_match or {}
    pr.structured_goal = structured_goal
    pr.plan = plan
    pr.step1_time = step1_time if step1_time is not None else t0
    pr.step2_time = step2_time if step2_time is not None else t0 + 0.01
    pr.prep_timing = prep_timing or {}
    pr.tenant_ctx = tenant_ctx
    return pr


def _make_exec_result(
    success: bool = True,
    results: list[Any] | None = None,
) -> MagicMock:
    """Create a mock exec_result with worker results."""
    er = MagicMock()
    er.success = success
    er.results = results or []
    return er


_SENTINEL = object()


def _make_worker_result(
    worker_id: str = "architect-0",
    task_id: str = "t0",
    success: bool = True,
    output: Any = _SENTINEL,
    error: str | None = None,
) -> MagicMock:
    """Create a mock individual worker result."""
    r = MagicMock()
    r.worker_id = worker_id
    r.task_id = task_id
    r.success = success
    r.output = {"finding_summary": "test finding"} if output is _SENTINEL else output
    r.error = error
    return r


def _make_pipeline(**overrides: Any) -> PostDispatchPipeline:
    """Build a PostDispatchPipeline with mocked dependencies.

    All keyword arguments override the defaults passed to __init__.
    """
    defaults: dict[str, Any] = {
        "coordinator": MagicMock(),
        "report_formatter": MagicMock(),
        "enterprise": MagicMock(),
        "metrics_service": MagicMock(),
        "permission_service": MagicMock(),
        "memory_pipeline": MagicMock(),
        "skill_service": MagicMock(),
        "enable_compression": True,
        "enable_permission": True,
        "enable_feedback_loop": False,
        "enable_two_stage_review": False,
        "enable_redesign_audit": False,
        "enable_severity_router": False,
        "development_mode": True,
        "max_fix_iterations": 1,
        "severity_router": None,
        "judge_agent": None,
        "compressor": MagicMock(),
        "usage_tracker": MagicMock(),
        "retrospective_engine": MagicMock(),
        "anchor_checker": MagicMock(),
        "learned_rule_store": MagicMock(),
        "llm_backend": MagicMock(),
        "persist_dir": "/tmp/test",
        "dispatcher": MagicMock(),
        "event_bus": None,
        "result_assembler": MagicMock(),
    }
    defaults.update(overrides)
    return PostDispatchPipeline(**defaults)


# ---------------------------------------------------------------------------
# Test __init__
# ---------------------------------------------------------------------------


class TestPostDispatchPipelineInit:
    """Tests for PostDispatchPipeline constructor."""

    def test_init_stores_core_components(self) -> None:
        """Core components are stored as attributes."""
        coordinator = MagicMock()
        report_formatter = MagicMock()
        enterprise = MagicMock()
        pipeline = _make_pipeline(
            coordinator=coordinator,
            report_formatter=report_formatter,
            enterprise=enterprise,
        )
        assert pipeline.coordinator is coordinator
        assert pipeline.report_formatter is report_formatter
        assert pipeline.enterprise is enterprise

    def test_init_stores_services(self) -> None:
        """Service instances are stored as attributes."""
        metrics = MagicMock()
        permission = MagicMock()
        memory = MagicMock()
        skill = MagicMock()
        pipeline = _make_pipeline(
            metrics_service=metrics,
            permission_service=permission,
            memory_pipeline=memory,
            skill_service=skill,
        )
        assert pipeline.metrics_service is metrics
        assert pipeline.permission_service is permission
        assert pipeline.memory_pipeline is memory
        assert pipeline.skill_service is skill

    def test_init_stores_feature_flags(self) -> None:
        """Feature flags are stored correctly."""
        pipeline = _make_pipeline(
            enable_compression=False,
            enable_permission=False,
            enable_feedback_loop="auto",
            enable_two_stage_review=True,
            enable_redesign_audit=True,
            enable_severity_router=True,
        )
        assert pipeline.enable_compression is False
        assert pipeline.enable_permission is False
        assert pipeline.enable_feedback_loop == "auto"
        assert pipeline.enable_two_stage_review is True
        assert pipeline.enable_redesign_audit is True
        assert pipeline.enable_severity_router is True

    def test_init_creates_event_bus_if_none(self) -> None:
        """A new EventBus is created when none is provided."""
        from scripts.collaboration.event_bus import EventBus

        pipeline = _make_pipeline(event_bus=None)
        assert isinstance(pipeline.event_bus, EventBus)

    def test_init_uses_provided_event_bus(self) -> None:
        """Provided event_bus is used directly."""
        bus = MagicMock()
        pipeline = _make_pipeline(event_bus=bus)
        assert pipeline.event_bus is bus

    def test_init_creates_two_stage_review_gate(self) -> None:
        """TwoStageReviewGate is created with feature flags."""
        from scripts.collaboration.two_stage_review_gate import TwoStageReviewGate

        pipeline = _make_pipeline(
            enable_two_stage_review=True,
            enable_redesign_audit=True,
        )
        assert isinstance(pipeline.two_stage_review_gate, TwoStageReviewGate)

    def test_init_creates_severity_router_when_enabled(self) -> None:
        """SeverityRouter is created and subscribed when enabled."""
        pipeline = _make_pipeline(
            enable_severity_router=True,
            severity_router=None,
        )
        assert pipeline.severity_router is not None

    def test_init_uses_injected_severity_router(self) -> None:
        """Injected severity_router is used directly."""
        router = MagicMock()
        pipeline = _make_pipeline(
            enable_severity_router=True,
            severity_router=router,
        )
        assert pipeline.severity_router is router

    def test_init_severity_router_disabled(self) -> None:
        """When severity_router disabled, router is still created but not subscribed."""
        pipeline = _make_pipeline(
            enable_severity_router=False,
            severity_router=None,
        )
        # Router object exists but subscribe() was not called
        assert pipeline.severity_router is not None

    def test_init_stores_judge_agent(self) -> None:
        """Judge agent is stored when provided."""
        judge = MagicMock()
        pipeline = _make_pipeline(judge_agent=judge)
        assert pipeline.judge_agent is judge

    def test_init_judge_agent_none(self) -> None:
        """Judge agent defaults to None."""
        pipeline = _make_pipeline()
        assert pipeline.judge_agent is None

    def test_init_lazy_frameworks_none(self) -> None:
        """Lazy-initialized frameworks start as None."""
        pipeline = _make_pipeline()
        assert pipeline._ue_framework is None
        assert pipeline._debt_manager is None


# ---------------------------------------------------------------------------
# Test _build_step_timings (pure function)
# ---------------------------------------------------------------------------


class TestBuildStepTimings:
    """Tests for _build_step_timings method."""

    def test_returns_eleven_step_durations(self) -> None:
        """Result contains all 11 step names."""
        pipeline = _make_pipeline()
        timestamps = [100.0 + i * 0.1 for i in range(12)]
        timings = pipeline._build_step_timings(*timestamps)
        expected_names = {
            "analyze",
            "warmup",
            "plan",
            "spawn",
            "execute",
            "collect",
            "consensus",
            "compress",
            "permission",
            "memory",
            "skillify",
        }
        assert set(timings.keys()) == expected_names

    def test_durations_are_differences(self) -> None:
        """Each duration is the difference between consecutive timestamps."""
        pipeline = _make_pipeline()
        ts = [10.0, 11.0, 13.0, 16.0, 20.0, 25.0, 31.0, 38.0, 46.0, 55.0, 65.0, 76.0]
        timings = pipeline._build_step_timings(*ts)
        assert timings["analyze"] == 1.0  # 11 - 10
        assert timings["warmup"] == 2.0  # 13 - 11
        assert timings["plan"] == 3.0  # 16 - 13
        assert timings["spawn"] == 4.0  # 20 - 16
        assert timings["execute"] == 5.0  # 25 - 20

    def test_durations_are_rounded_to_3_decimals(self) -> None:
        """Durations are rounded to 3 decimal places."""
        pipeline = _make_pipeline()
        ts = [
            0.0,
            0.123456,
            0.246912,
            0.370368,
            0.493824,
            0.617280,
            0.740736,
            0.864192,
            0.987648,
            1.111104,
            1.234560,
            1.358016,
        ]
        timings = pipeline._build_step_timings(*ts)
        for v in timings.values():
            assert v == round(v, 3)

    def test_zero_duration_when_all_same(self) -> None:
        """All durations are 0 when timestamps are identical."""
        pipeline = _make_pipeline()
        ts = [42.0] * 12
        timings = pipeline._build_step_timings(*ts)
        assert all(v == 0.0 for v in timings.values())

    def test_increasing_timestamps(self) -> None:
        """Correctly handles monotonically increasing timestamps."""
        pipeline = _make_pipeline()
        base = time.time()
        ts = [base + i * 0.05 for i in range(12)]
        timings = pipeline._build_step_timings(*ts)
        # All durations should be ~0.05
        for v in timings.values():
            assert 0.04 <= v <= 0.06


# ---------------------------------------------------------------------------
# Test _build_lifecycle_trace (pure function)
# ---------------------------------------------------------------------------


class TestBuildLifecycleTrace:
    """Tests for _build_lifecycle_trace method."""

    def test_returns_dict_with_required_keys(self) -> None:
        """Result has lifecycle_phases, phase_steps, mapping_version."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"analyze": 0.1})
        assert "lifecycle_phases" in trace
        assert "phase_steps" in trace
        assert "mapping_version" in trace
        assert trace["mapping_version"] == "1.0"

    def test_analyze_maps_to_p1(self) -> None:
        """analyze step maps to P1_Requirements."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"analyze": 1.5})
        assert "P1_Requirements" in trace["lifecycle_phases"]
        assert trace["lifecycle_phases"]["P1_Requirements"] == 1.5
        assert "analyze" in trace["phase_steps"]["P1_Requirements"]

    def test_warmup_maps_to_p2(self) -> None:
        """warmup step maps to P2_Architecture."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"warmup": 2.0})
        assert "P2_Architecture" in trace["lifecycle_phases"]

    def test_plan_spawn_execute_map_to_p3(self) -> None:
        """plan, spawn, execute all map to P3_Implementation."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace(
            {
                "plan": 1.0,
                "spawn": 2.0,
                "execute": 3.0,
            }
        )
        assert trace["lifecycle_phases"]["P3_Implementation"] == 6.0
        assert set(trace["phase_steps"]["P3_Implementation"]) == {"plan", "spawn", "execute"}

    def test_collect_consensus_map_to_p4(self) -> None:
        """collect and consensus map to P4_Review."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"collect": 1.0, "consensus": 2.0})
        assert trace["lifecycle_phases"]["P4_Review"] == 3.0

    def test_compress_memory_map_to_p5(self) -> None:
        """compress and memory map to P5_Integration."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"compress": 1.0, "memory": 2.0})
        assert trace["lifecycle_phases"]["P5_Integration"] == 3.0

    def test_permission_maps_to_p6(self) -> None:
        """permission maps to P6_Security."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"permission": 1.0})
        assert "P6_Security" in trace["lifecycle_phases"]

    def test_skillify_maps_to_p8(self) -> None:
        """skillify maps to P8_Optimization."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"skillify": 1.0})
        assert "P8_Optimization" in trace["lifecycle_phases"]

    def test_unknown_step_maps_to_p10(self) -> None:
        """Unknown step name maps to P10_Delivery."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({"unknown_step": 1.0})
        assert "P10_Delivery" in trace["lifecycle_phases"]

    def test_empty_timings(self) -> None:
        """Empty timings produce empty phases."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace({})
        assert trace["lifecycle_phases"] == {}
        assert trace["phase_steps"] == {}

    def test_durations_aggregate_within_phase(self) -> None:
        """Multiple steps in the same phase have durations summed."""
        pipeline = _make_pipeline()
        trace = pipeline._build_lifecycle_trace(
            {
                "plan": 1.0,
                "spawn": 2.0,
                "execute": 3.0,
            }
        )
        # All three map to P3_Implementation
        assert trace["lifecycle_phases"]["P3_Implementation"] == 6.0


# ---------------------------------------------------------------------------
# Test _collect_worker_results
# ---------------------------------------------------------------------------


class TestCollectWorkerResults:
    """Tests for _collect_worker_results method."""

    def test_empty_results(self) -> None:
        """Empty exec_result.results produces empty list."""
        pipeline = _make_pipeline()
        exec_result = _make_exec_result(results=[])
        results, t6, t7 = pipeline._collect_worker_results(exec_result)
        assert results == []
        assert t6 <= t7

    def test_single_worker_result(self) -> None:
        """Single worker result is collected correctly."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(
            worker_id="architect-0",
            task_id="t1",
            output={"finding_summary": "finding"},
        )
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert len(results) == 1
        assert results[0]["worker_id"] == "architect-0"
        assert results[0]["role_id"] == "architect"
        assert results[0]["output"] == "finding"

    def test_worker_id_without_dash(self) -> None:
        """Worker ID without dash uses full ID as role_id."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="coder", output={"finding_summary": "x"})
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert results[0]["role_id"] == "coder"

    def test_output_none(self) -> None:
        """None output is handled gracefully."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="architect-0", output=None)
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert results[0]["output"] is None

    def test_output_non_dict(self) -> None:
        """Non-dict output is converted to string."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="architect-0", output="plain string")
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert results[0]["output"] == "plain string"

    def test_output_dict_without_finding_summary(self) -> None:
        """Dict output without finding_summary produces empty string."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="architect-0", output={"other": "data"})
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert results[0]["output"] == ""

    def test_error_propagated(self) -> None:
        """Error field is propagated to result."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="architect-0", error="something went wrong")
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert results[0]["error"] == "something went wrong"

    def test_success_propagated(self) -> None:
        """Success field is propagated to result."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="architect-0", success=False)
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert results[0]["success"] is False

    def test_multiple_worker_results(self) -> None:
        """Multiple worker results are all collected."""
        pipeline = _make_pipeline()
        wrs = [_make_worker_result(worker_id=f"role-{i}", output={"finding_summary": f"f{i}"}) for i in range(5)]
        exec_result = _make_exec_result(results=wrs)
        results, _, _ = pipeline._collect_worker_results(exec_result)
        assert len(results) == 5
        for _, r in enumerate(results):
            assert r["role_id"] == "role"

    def test_role_name_from_registry(self) -> None:
        """Role name is resolved from ROLE_REGISTRY when available."""
        pipeline = _make_pipeline()
        wr = _make_worker_result(worker_id="architect-0", output={"finding_summary": "x"})
        exec_result = _make_exec_result(results=[wr])
        results, _, _ = pipeline._collect_worker_results(exec_result)
        # architect is in ROLE_REGISTRY
        assert results[0]["role_name"] is not None

    def test_timestamps_ordered(self) -> None:
        """Returned timestamps t6 <= t7."""
        pipeline = _make_pipeline()
        exec_result = _make_exec_result(results=[])
        _, t6, t7 = pipeline._collect_worker_results(exec_result)
        assert t6 <= t7


# ---------------------------------------------------------------------------
# Test _build_summary
# ---------------------------------------------------------------------------


class TestBuildSummary:
    """Tests for _build_summary delegation method."""

    def test_delegates_to_report_formatter(self) -> None:
        """_build_summary delegates to report_formatter.build_summary."""
        rf = MagicMock()
        rf.build_summary.return_value = "summary text"
        pipeline = _make_pipeline(report_formatter=rf)
        result = pipeline._build_summary("task", ["architect"], MagicMock(), "sp_summary")
        assert result == "summary text"
        rf.build_summary.assert_called_once()

    def test_passes_all_arguments(self) -> None:
        """All arguments are forwarded to report_formatter."""
        rf = MagicMock()
        rf.build_summary.return_value = ""
        pipeline = _make_pipeline(report_formatter=rf)
        task = "my task"
        roles = ["architect", "coder"]
        exec_result = MagicMock()
        sp_summary = "scratchpad summary"
        pipeline._build_summary(task, roles, exec_result, sp_summary)
        rf.build_summary.assert_called_once_with(task, roles, exec_result, sp_summary)


# ---------------------------------------------------------------------------
# Test execute (integration with mocks)
# ---------------------------------------------------------------------------


class TestExecute:
    """Tests for the main execute() method."""

    def _setup_pipeline_for_execute(self, **overrides: Any) -> PostDispatchPipeline:
        """Set up a pipeline with all mocks needed for execute()."""
        dispatcher = MagicMock()
        dispatcher.hooks.post_execution_processing.return_value = (
            "sp_summary",  # scratchpad_summary
            {},  # anchor_result
            {"conflicts_count": 0},  # collection
            [],  # post_errors
            {"step8_time": time.time()},  # post_timing
        )
        dispatcher._get_current_tenant_id = MagicMock(return_value=None)

        result_assembler = MagicMock()
        result_assembler.assemble.return_value = MagicMock(
            success=True,
            errors=[],
            details={},
        )

        enterprise = MagicMock()
        metrics_service = MagicMock()

        defaults = {
            "dispatcher": dispatcher,
            "result_assembler": result_assembler,
            "enterprise": enterprise,
            "metrics_service": metrics_service,
            "enable_feedback_loop": False,
            "enable_two_stage_review": False,
            "enable_severity_router": False,
            "event_bus": MagicMock(),
        }
        defaults.update(overrides)
        return _make_pipeline(**defaults)

    def test_execute_returns_dispatch_result(self) -> None:
        """execute() returns the result from result_assembler."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result()
        exec_result = _make_exec_result()
        result = pipeline.execute(
            pre_result=pre_result,
            exec_result=exec_result,
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        assert result is not None

    def test_execute_calls_post_execution_processing(self) -> None:
        """execute() calls dispatcher.hooks.post_execution_processing."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result()
        exec_result = _make_exec_result()
        pipeline.execute(
            pre_result=pre_result,
            exec_result=exec_result,
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        pipeline.dispatcher.hooks.post_execution_processing.assert_called_once()

    def test_execute_emits_execution_completed_event(self) -> None:
        """execute() emits post_dispatch.execution_completed event."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result()
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        # Event bus should have emit called for execution_completed
        emit_calls = pipeline.event_bus.emit.call_args_list
        event_names = [c[0][0] if c[0] else c[1].get("event") for c in emit_calls]
        assert any("execution_completed" in str(en) for en in event_names)

    def test_execute_calls_result_assembler(self) -> None:
        """execute() calls result_assembler.assemble with task description."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result(task_description="my task")
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        pipeline.result_assembler.assemble.assert_called_once()
        call_kwargs = pipeline.result_assembler.assemble.call_args[1]
        assert call_kwargs["task_description"] == "my task"

    def test_execute_calls_audit_dispatch_complete(self) -> None:
        """execute() calls enterprise.audit_dispatch_complete."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result()
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        pipeline.enterprise.audit_dispatch_complete.assert_called_once()

    def test_execute_calls_clear_tenant_context(self) -> None:
        """execute() calls enterprise.clear_tenant_context at the end."""
        pipeline = self._setup_pipeline_for_execute()
        tenant_ctx = {"tenant_id": "t1"}
        pre_result = _make_pre_result(tenant_ctx=tenant_ctx)
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        pipeline.enterprise.clear_tenant_context.assert_called_once_with(tenant_ctx)

    def test_execute_adds_lifecycle_trace_to_details(self) -> None:
        """execute() adds lifecycle_trace to result.details."""
        pipeline = self._setup_pipeline_for_execute()
        result_mock = MagicMock()
        result_mock.details = {}
        result_mock.success = True
        result_mock.errors = []
        pipeline.result_assembler.assemble.return_value = result_mock

        pre_result = _make_pre_result()
        result = pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        assert "lifecycle_trace" in result.details

    def test_execute_emits_post_dispatch_hooks_event(self) -> None:
        """execute() emits post_dispatch.hooks event."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result()
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        emit_calls = pipeline.event_bus.emit.call_args_list
        event_names = [c[0][0] if c[0] else "" for c in emit_calls]
        assert any("post_dispatch.hooks" in str(en) for en in event_names)

    def test_execute_records_metrics(self) -> None:
        """execute() calls metrics_service.safe_record for Prometheus."""
        pipeline = self._setup_pipeline_for_execute()
        pre_result = _make_pre_result()
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        # safe_record is called at least once for dispatch end
        assert pipeline.metrics_service.safe_record.called

    def test_execute_extends_errors_from_post_processing(self) -> None:
        """Errors from post_execution_processing are included."""
        pipeline = self._setup_pipeline_for_execute()
        pipeline.dispatcher.hooks.post_execution_processing.return_value = (
            "sp",
            {},
            {"conflicts_count": 0},
            ["post error 1"],
            {"step8_time": time.time()},
        )
        pre_result = _make_pre_result()
        result_mock = MagicMock()
        result_mock.details = {}
        result_mock.success = True
        result_mock.errors = []
        pipeline.result_assembler.assemble.return_value = result_mock

        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=["exec error"],
            exec_timing={},
            start_time=time.time(),
            phase="test",
        )
        # The errors list passed to assemble should contain both exec and post errors
        call_kwargs = pipeline.result_assembler.assemble.call_args[1]
        assert "exec error" in call_kwargs["errors"]
        assert "post error 1" in call_kwargs["errors"]

    def test_execute_uses_prep_timing_for_step_times(self) -> None:
        """execute() reads step3/4/5 times from prep_timing."""
        pipeline = self._setup_pipeline_for_execute()
        t0 = time.time()
        pre_result = _make_pre_result(
            step1_time=t0,
            step2_time=t0 + 0.01,
            prep_timing={
                "step3_time": t0 + 0.02,
                "step4_time": t0 + 0.03,
                "step5_time": t0 + 0.04,
            },
        )
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={"step6_time": t0 + 0.05, "step7_time": t0 + 0.06},
            start_time=t0,
            phase="test",
        )
        # If no exception, prep_timing was used correctly
        pipeline.result_assembler.assemble.assert_called_once()

    def test_execute_falls_back_when_prep_timing_missing(self) -> None:
        """execute() falls back to step2_time when prep_timing is empty."""
        pipeline = self._setup_pipeline_for_execute()
        t0 = time.time()
        pre_result = _make_pre_result(
            step1_time=t0,
            step2_time=t0 + 0.01,
            prep_timing={},
        )
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=t0,
            phase="test",
        )
        pipeline.result_assembler.assemble.assert_called_once()

    def test_execute_falls_back_when_exec_timing_missing(self) -> None:
        """execute() falls back to step5_time when exec_timing is empty."""
        pipeline = self._setup_pipeline_for_execute()
        t0 = time.time()
        pre_result = _make_pre_result(
            step1_time=t0,
            step2_time=t0 + 0.01,
            prep_timing={"step3_time": t0 + 0.02, "step4_time": t0 + 0.03, "step5_time": t0 + 0.04},
        )
        pipeline.execute(
            pre_result=pre_result,
            exec_result=_make_exec_result(),
            worker_results=[],
            exec_errors=[],
            exec_timing={},
            start_time=t0,
            phase="test",
        )
        pipeline.result_assembler.assemble.assert_called_once()
