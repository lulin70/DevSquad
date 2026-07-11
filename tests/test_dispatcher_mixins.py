"""Tests for dispatcher mixin modules.

Covers DispatcherUtilsMixin, DispatcherStatusMixin, DispatcherErrorMixin,
DispatcherAuditMixin, and DispatcherLifecycleMixin.
"""

from __future__ import annotations

import time
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher_audit_mixin import DispatcherAuditMixin
from scripts.collaboration.dispatcher_error_mixin import DispatcherErrorMixin
from scripts.collaboration.dispatcher_lifecycle_mixin import DispatcherLifecycleMixin
from scripts.collaboration.dispatcher_status_mixin import DispatcherStatusMixin
from scripts.collaboration.dispatcher_utils_mixin import DispatcherUtilsMixin

# ---------------------------------------------------------------------------
# DispatcherUtilsMixin tests
# ---------------------------------------------------------------------------


class TestUtilsMixinAnalyze:
    """Tests for DispatcherUtilsMixin.analyze_task and decompose_task."""

    def _make_mixin(self, **overrides: Any) -> DispatcherUtilsMixin:
        m = DispatcherUtilsMixin.__new__(DispatcherUtilsMixin)
        m.micro_task_planner = overrides.get("micro_task_planner")
        m.usage_tracker = overrides.get("usage_tracker", MagicMock())
        m.role_matcher = overrides.get("role_matcher", MagicMock())
        m.coordinator = overrides.get("coordinator", MagicMock())
        m.report_formatter = overrides.get("report_formatter", MagicMock())
        m.post_dispatch = overrides.get("post_dispatch", MagicMock())
        m.enterprise = overrides.get("enterprise", MagicMock())
        m.persist_dir = overrides.get("persist_dir", "/tmp")
        m.llm_backend = overrides.get("llm_backend", MagicMock())
        return m

    def test_analyze_task_delegates_to_role_matcher(self) -> None:
        """analyze_task delegates to role_matcher.analyze_task."""
        rm = MagicMock()
        rm.analyze_task.return_value = [{"role": "architect"}]
        mixin = self._make_mixin(role_matcher=rm)
        result = mixin.analyze_task("build a web app")
        assert result == [{"role": "architect"}]
        rm.analyze_task.assert_called_once_with("build a web app")

    def test_decompose_task_returns_none_when_no_planner(self) -> None:
        """decompose_task returns None when micro_task_planner is None."""
        mixin = self._make_mixin(micro_task_planner=None)
        assert mixin.decompose_task("task") is None

    def test_decompose_task_delegates_to_planner(self) -> None:
        """decompose_task delegates to micro_task_planner.plan."""
        plan = MagicMock()
        planner = MagicMock()
        planner.plan.return_value = plan
        mixin = self._make_mixin(micro_task_planner=planner)
        result = mixin.decompose_task("task", spec={"files": ["a.py"]})
        assert result is plan
        planner.plan.assert_called_once_with("task", spec={"files": ["a.py"]})


class TestUtilsMixinMaybeDecompose:
    """Tests for _maybe_decompose_task."""

    def _make_mixin(self, **overrides: Any) -> DispatcherUtilsMixin:
        m = DispatcherUtilsMixin.__new__(DispatcherUtilsMixin)
        m.micro_task_planner = overrides.get("micro_task_planner")
        m.usage_tracker = overrides.get("usage_tracker", MagicMock())
        m.role_matcher = overrides.get("role_matcher", MagicMock())
        m.coordinator = overrides.get("coordinator", MagicMock())
        m.report_formatter = overrides.get("report_formatter", MagicMock())
        m.post_dispatch = overrides.get("post_dispatch", MagicMock())
        m.enterprise = overrides.get("enterprise", MagicMock())
        m.persist_dir = "/tmp"
        m.llm_backend = MagicMock()
        return m

    def test_returns_none_when_not_enabled(self) -> None:
        """Returns None when use_micro_tasks=False."""
        mixin = self._make_mixin(micro_task_planner=MagicMock())
        assert mixin._maybe_decompose_task("task", False, {}) is None

    def test_returns_none_when_no_planner(self) -> None:
        """Returns None when micro_task_planner is None."""
        mixin = self._make_mixin(micro_task_planner=None)
        assert mixin._maybe_decompose_task("task", True, {}) is None

    def test_returns_plan_on_success(self) -> None:
        """Returns the plan when decomposition succeeds."""
        plan = MagicMock()
        plan.micro_tasks = [MagicMock()]
        plan.total_estimated_minutes = 5
        planner = MagicMock()
        planner.plan.return_value = plan
        tracker = MagicMock()
        mixin = self._make_mixin(micro_task_planner=planner, usage_tracker=tracker)
        result = mixin._maybe_decompose_task("task", True, {"files": ["a.py"]})
        assert result is plan
        tracker.tick.assert_called_once_with("micro_task_planner")

    def test_returns_none_on_failure(self) -> None:
        """Returns None when planner raises ValueError."""
        planner = MagicMock()
        planner.plan.side_effect = ValueError("bad spec")
        mixin = self._make_mixin(micro_task_planner=planner, usage_tracker=MagicMock())
        assert mixin._maybe_decompose_task("task", True, {}) is None

    def test_extracts_spec_keys_from_kwargs(self) -> None:
        """Extracts files, functions, tests, acceptance_criteria from kwargs."""
        plan = MagicMock()
        plan.micro_tasks = []
        plan.total_estimated_minutes = 0
        planner = MagicMock()
        planner.plan.return_value = plan
        mixin = self._make_mixin(micro_task_planner=planner, usage_tracker=MagicMock())
        mixin._maybe_decompose_task(
            "task",
            True,
            {
                "files": ["a.py"],
                "functions": ["foo"],
                "tests": ["test_foo"],
                "acceptance_criteria": "passes",
                "extra_key": "ignored",
            },
        )
        call_args = planner.plan.call_args
        spec = call_args[1]["spec"]
        assert "files" in spec
        assert "functions" in spec
        assert "tests" in spec
        assert "acceptance_criteria" in spec
        assert "extra_key" not in spec


class TestUtilsMixinResolveLanguage:
    """Tests for _resolve_language."""

    def _make_mixin(self) -> DispatcherUtilsMixin:
        m = DispatcherUtilsMixin.__new__(DispatcherUtilsMixin)
        return m

    def test_returns_specific_lang_directly(self) -> None:
        """Non-auto language is returned directly."""
        mixin = self._make_mixin()
        assert mixin._resolve_language("en") == "en"
        assert mixin._resolve_language("zh") == "zh"
        assert mixin._resolve_language("ja") == "ja"

    def test_auto_resolves_to_ja_for_japanese_locale(self) -> None:
        """auto resolves to ja when locale starts with ja."""
        mixin = self._make_mixin()
        with patch("scripts.collaboration.dispatcher_utils_mixin.locale.getlocale", return_value=("ja_JP", "UTF-8")):
            assert mixin._resolve_language("auto") == "ja"

    def test_auto_resolves_to_zh_for_chinese_locale(self) -> None:
        """auto resolves to zh when locale starts with zh."""
        mixin = self._make_mixin()
        with patch("scripts.collaboration.dispatcher_utils_mixin.locale.getlocale", return_value=("zh_CN", "UTF-8")):
            assert mixin._resolve_language("auto") == "zh"

    def test_auto_defaults_to_zh(self) -> None:
        """auto defaults to zh for unknown locale."""
        mixin = self._make_mixin()
        with patch("scripts.collaboration.dispatcher_utils_mixin.locale.getlocale", return_value=("en_US", "UTF-8")):
            assert mixin._resolve_language("auto") == "zh"

    def test_auto_defaults_to_zh_on_locale_error(self) -> None:
        """auto defaults to zh when locale detection fails."""
        mixin = self._make_mixin()
        with patch(
            "scripts.collaboration.dispatcher_utils_mixin.locale.getlocale", side_effect=ValueError("no locale")
        ):
            assert mixin._resolve_language("auto") == "zh"


class TestUtilsMixinTenantId:
    """Tests for _get_current_tenant_id."""

    def _make_mixin(self, **overrides: Any) -> DispatcherUtilsMixin:
        m = DispatcherUtilsMixin.__new__(DispatcherUtilsMixin)
        m.enterprise = overrides.get("enterprise", MagicMock())
        return m

    def test_returns_default_when_multi_tenant_disabled(self) -> None:
        """Returns 'default' when multi-tenant is disabled."""
        enterprise = MagicMock()
        enterprise.enable_multi_tenant = False
        mixin = self._make_mixin(enterprise=enterprise)
        assert mixin._get_current_tenant_id() == "default"

    def test_returns_default_when_no_tenant_manager(self) -> None:
        """Returns 'default' when tenant_manager is None."""
        enterprise = MagicMock()
        enterprise.enable_multi_tenant = True
        enterprise.tenant_manager = None
        mixin = self._make_mixin(enterprise=enterprise)
        assert mixin._get_current_tenant_id() == "default"

    def test_returns_default_when_no_current_tenant(self) -> None:
        """Returns 'default' when get_current_tenant returns None."""
        enterprise = MagicMock()
        enterprise.enable_multi_tenant = True
        enterprise.tenant_manager.get_current_tenant.return_value = None
        mixin = self._make_mixin(enterprise=enterprise)
        assert mixin._get_current_tenant_id() == "default"

    def test_returns_tenant_id_when_available(self) -> None:
        """Returns tenant_id when a current tenant is set."""
        enterprise = MagicMock()
        enterprise.enable_multi_tenant = True
        tenant = MagicMock()
        tenant.tenant_id = "tenant-123"
        enterprise.tenant_manager.get_current_tenant.return_value = tenant
        mixin = self._make_mixin(enterprise=enterprise)
        assert mixin._get_current_tenant_id() == "tenant-123"


class TestUtilsMixinQuickDispatch:
    """Tests for quick_dispatch."""

    def _make_mixin(self, **overrides: Any) -> DispatcherUtilsMixin:
        m = DispatcherUtilsMixin.__new__(DispatcherUtilsMixin)
        m.report_formatter = overrides.get("report_formatter", MagicMock())
        m.dispatch = overrides.get("dispatch", MagicMock())
        return m

    def test_structured_format(self) -> None:
        """Structured format uses format_structured_report."""
        rf = MagicMock()
        rf.format_structured_report.return_value = "structured report"
        dispatch_mock = MagicMock(return_value=DispatchResult(success=True, task_description="t"))
        mixin = self._make_mixin(report_formatter=rf, dispatch=dispatch_mock)
        result = mixin.quick_dispatch("task", output_format="structured")
        assert result.summary == "structured report"
        rf.format_structured_report.assert_called_once()

    def test_compact_format(self) -> None:
        """Compact format uses format_compact_report."""
        rf = MagicMock()
        rf.format_compact_report.return_value = "compact report"
        dispatch_mock = MagicMock(return_value=DispatchResult(success=True, task_description="t"))
        mixin = self._make_mixin(report_formatter=rf, dispatch=dispatch_mock)
        result = mixin.quick_dispatch("task", output_format="compact")
        assert result.summary == "compact report"

    def test_default_format_uses_markdown(self) -> None:
        """Default format uses to_markdown."""
        dispatch_result = MagicMock(spec=DispatchResult)
        dispatch_result.to_markdown.return_value = "markdown report"
        dispatch_mock = MagicMock(return_value=dispatch_result)
        mixin = self._make_mixin(dispatch=dispatch_mock)
        result = mixin.quick_dispatch("task", output_format="other")
        assert result.summary == "markdown report"


class TestUtilsMixinFormatHelpers:
    """Tests for _format_structured_report, _format_compact_report, etc."""

    def _make_mixin(self) -> DispatcherUtilsMixin:
        m = DispatcherUtilsMixin.__new__(DispatcherUtilsMixin)
        m.report_formatter = MagicMock()
        return m

    def test_format_structured_delegates(self) -> None:
        mixin = self._make_mixin()
        mixin._format_structured_report(MagicMock())
        mixin.report_formatter.format_structured_report.assert_called_once()

    def test_format_compact_delegates(self) -> None:
        mixin = self._make_mixin()
        mixin._format_compact_report(MagicMock())
        mixin.report_formatter.format_compact_report.assert_called_once()

    def test_extract_findings_delegates(self) -> None:
        mixin = self._make_mixin()
        mixin._extract_findings("summary text")
        mixin.report_formatter.extract_findings.assert_called_once_with("summary text")

    def test_generate_action_items_delegates(self) -> None:
        mixin = self._make_mixin()
        mixin._generate_action_items(MagicMock())
        mixin.report_formatter.generate_action_items.assert_called_once()


# ---------------------------------------------------------------------------
# DispatcherStatusMixin tests
# ---------------------------------------------------------------------------


class TestStatusMixinGetStatus:
    """Tests for DispatcherStatusMixin.get_status."""

    def _make_mixin(self, **overrides: Any) -> DispatcherStatusMixin:
        m = DispatcherStatusMixin.__new__(DispatcherStatusMixin)
        m.coordinator = overrides.get("coordinator", MagicMock())
        m.scratchpad = overrides.get("scratchpad", MagicMock())
        m.batch_scheduler = overrides.get("batch_scheduler", MagicMock())
        m.consensus_engine = overrides.get("consensus_engine", MagicMock())
        m.compressor = overrides.get("compressor", MagicMock())
        m.permission_guard = overrides.get("permission_guard", MagicMock())
        m.warmup_manager = overrides.get("warmup_manager", MagicMock())
        m.memory_bridge = overrides.get("memory_bridge", MagicMock())
        m.skillifier = overrides.get("skillifier", MagicMock())
        m.quality_guard = overrides.get("quality_guard", MagicMock())
        m.execution_guard = overrides.get("execution_guard", MagicMock())
        m._perf_monitor = overrides.get("_perf_monitor", MagicMock())
        m._dispatch_history = overrides.get("_dispatch_history", [])
        m.enterprise = overrides.get("enterprise", MagicMock())
        m.persist_dir = overrides.get("persist_dir", "/tmp")
        return m

    def test_status_contains_version(self) -> None:
        """Status dict contains version."""
        mixin = self._make_mixin()
        status = mixin.get_status()
        assert "version" in status

    def test_status_contains_components(self) -> None:
        """Status dict contains component availability."""
        mixin = self._make_mixin()
        status = mixin.get_status()
        assert "components" in status
        assert "coordinator" in status["components"]

    def test_status_contains_dispatch_count(self) -> None:
        """Status dict contains dispatch count."""
        mixin = self._make_mixin(_dispatch_history=[MagicMock(), MagicMock()])
        status = mixin.get_status()
        assert status["dispatch_count"] == 2

    def test_status_includes_perf_stats(self) -> None:
        """Performance stats are appended when available."""
        perf = MagicMock()
        perf.get_statistics.return_value = {"p99": 1.5}
        perf.detect_regression.return_value = None
        mixin = self._make_mixin(_perf_monitor=perf)
        status = mixin.get_status()
        assert status["performance"] == {"p99": 1.5}

    def test_status_includes_regression(self) -> None:
        """Regression is included when detected."""
        perf = MagicMock()
        perf.get_statistics.return_value = {}
        perf.detect_regression.return_value = {"type": "latency"}
        mixin = self._make_mixin(_perf_monitor=perf)
        status = mixin.get_status()
        assert status["regression_detected"] == {"type": "latency"}

    def test_status_perf_error_handled(self) -> None:
        """Performance stats errors are handled gracefully."""
        perf = MagicMock()
        perf.get_statistics.side_effect = RuntimeError("fail")
        mixin = self._make_mixin(_perf_monitor=perf)
        status = mixin.get_status()
        # No crash, just no performance key
        assert "performance" not in status or status.get("performance") is None

    def test_status_includes_warmup_metrics(self) -> None:
        """Warmup metrics are appended when available."""
        wm = MagicMock()
        metrics = MagicMock()
        metrics.cache_size = 10
        metrics.cache_hit_rate = 0.85
        metrics.tasks_completed = 5
        metrics.eager_duration_ms = 123.4
        wm.get_metrics.return_value = metrics
        mixin = self._make_mixin(warmup_manager=wm)
        status = mixin.get_status()
        assert status["warmup_metrics"]["cache_size"] == 10
        assert status["warmup_metrics"]["hit_rate"] == 0.85

    def test_status_warmup_none_when_no_manager(self) -> None:
        """Warmup metrics not included when manager is None."""
        mixin = self._make_mixin(warmup_manager=None)
        status = mixin.get_status()
        assert "warmup_metrics" not in status

    def test_status_includes_memory_stats(self) -> None:
        """Memory stats are appended when available."""
        mb = MagicMock()
        mem_stats = MagicMock()
        mem_stats.total_memories = 42
        mem_stats.by_type_counts = {"episodic": 10}
        mem_stats.index_built = True
        mb.get_statistics.return_value = mem_stats
        mixin = self._make_mixin(memory_bridge=mb)
        status = mixin.get_status()
        assert status["memory_stats"]["total_memories"] == 42

    def test_status_scratchpad_stats(self) -> None:
        """Scratchpad stats are included when scratchpad is available."""
        sp = MagicMock()
        sp.get_stats.return_value = {"entries": 5}
        mixin = self._make_mixin(scratchpad=sp)
        status = mixin.get_status()
        assert status["scratchpad_stats"] == {"entries": 5}


class TestStatusMixinHistory:
    """Tests for get_history and performance methods."""

    def _make_mixin(self, **overrides: Any) -> DispatcherStatusMixin:
        m = DispatcherStatusMixin.__new__(DispatcherStatusMixin)
        m._dispatch_history = overrides.get("_dispatch_history", [])
        m.enterprise = overrides.get("enterprise", MagicMock())
        m._perf_monitor = overrides.get("_perf_monitor", MagicMock())
        m.persist_dir = "/tmp"
        return m

    def test_get_history_returns_dicts(self) -> None:
        """get_history returns to_dict() for each entry."""
        r1 = MagicMock()
        r1.to_dict.return_value = {"success": True}
        r2 = MagicMock()
        r2.to_dict.return_value = {"success": False}
        mixin = self._make_mixin(_dispatch_history=[r1, r2])
        history = mixin.get_history(limit=10)
        assert len(history) == 2
        assert history[0] == {"success": True}

    def test_get_history_respects_limit(self) -> None:
        """get_history respects the limit parameter."""
        results = [MagicMock() for _ in range(20)]
        for i, r in enumerate(results):
            r.to_dict.return_value = {"i": i}
        mixin = self._make_mixin(_dispatch_history=results)
        history = mixin.get_history(limit=5)
        assert len(history) == 5
        # Should return the last 5
        assert history[-1] == {"i": 19}

    def test_get_history_rbac_denied_returns_empty(self) -> None:
        """get_history returns empty list when RBAC denies."""
        from scripts.collaboration.rbac_engine import Permission, PermissionDeniedError

        enterprise = MagicMock()
        enterprise.rbac_engine.enforce.side_effect = PermissionDeniedError("user1", Permission.TASK_READ)
        mixin = self._make_mixin(enterprise=enterprise)
        assert mixin.get_history(user_id="user1") == []

    def test_get_performance_stats_delegates(self) -> None:
        """get_performance_stats delegates to perf_monitor."""
        perf = MagicMock()
        perf.get_statistics.return_value = {"p99": 2.0}
        mixin = self._make_mixin(_perf_monitor=perf)
        assert mixin.get_performance_stats() == {"p99": 2.0}

    def test_check_performance_regression_delegates(self) -> None:
        """check_performance_regression delegates to perf_monitor."""
        perf = MagicMock()
        perf.detect_regression.return_value = {"type": "latency"}
        mixin = self._make_mixin(_perf_monitor=perf)
        assert mixin.check_performance_regression() == {"type": "latency"}


# ---------------------------------------------------------------------------
# DispatcherErrorMixin tests
# ---------------------------------------------------------------------------


class TestErrorMixin:
    """Tests for DispatcherErrorMixin._handle_dispatch_error."""

    def _make_mixin(self, **overrides: Any) -> DispatcherErrorMixin:
        m = DispatcherErrorMixin.__new__(DispatcherErrorMixin)
        m.enterprise = overrides.get("enterprise", MagicMock())
        m.metrics_service = overrides.get("metrics_service", MagicMock())
        return m

    def test_validation_error_handled(self) -> None:
        """ValueError is handled as validation error."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ValueError("bad input"), "task", None, "test", time.time(), "zh")
        assert result.success is False
        assert len(result.errors) == 1

    def test_type_error_handled(self) -> None:
        """TypeError is handled as validation error."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(TypeError("wrong type"), "task", None, "test", time.time(), "zh")
        assert result.success is False

    def test_attribute_error_handled(self) -> None:
        """AttributeError is handled as validation error."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(AttributeError("no attr"), "task", None, "test", time.time(), "zh")
        assert result.success is False

    def test_import_error_handled(self) -> None:
        """ImportError is handled as backend unavailable."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ImportError("missing module"), "task", None, "test", time.time(), "zh")
        assert result.success is False

    def test_module_not_found_error_handled(self) -> None:
        """ModuleNotFoundError is handled as backend unavailable."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ModuleNotFoundError("no module"), "task", None, "test", time.time(), "zh")
        assert result.success is False

    def test_generic_error_handled(self) -> None:
        """Generic Exception is handled as unexpected error."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(RuntimeError("unexpected"), "task", None, "test", time.time(), "zh")
        assert result.success is False

    def test_async_prefix_in_log(self) -> None:
        """is_async=True adds 'Async ' prefix to log."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ValueError("err"), "task", None, "test", time.time(), "zh", is_async=True)
        assert result.success is False

    def test_clears_tenant_context(self) -> None:
        """Tenant context is cleared on error."""
        enterprise = MagicMock()
        mixin = self._make_mixin(enterprise=enterprise)
        tenant_ctx = {"tenant_id": "t1"}
        mixin._handle_dispatch_error(ValueError("err"), "task", tenant_ctx, "test", time.time(), "zh")
        enterprise.clear_tenant_context.assert_called_once_with(tenant_ctx)

    def test_records_metrics(self) -> None:
        """Metrics are recorded on error."""
        metrics = MagicMock()
        mixin = self._make_mixin(metrics_service=metrics)
        mixin._handle_dispatch_error(ValueError("err"), "task", None, "test", time.time(), "zh")
        assert metrics.safe_record.called

    def test_result_contains_task_description(self) -> None:
        """Result contains the original task description."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ValueError("err"), "my task", None, "test", time.time(), "zh")
        assert result.task_description == "my task"

    def test_result_contains_lang(self) -> None:
        """Result contains the specified language."""
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ValueError("err"), "task", None, "test", time.time(), "en")
        assert result.lang == "en"

    def test_result_duration_positive(self) -> None:
        """Result has positive duration."""
        start = time.time() - 1.0
        mixin = self._make_mixin()
        result = mixin._handle_dispatch_error(ValueError("err"), "task", None, "test", start, "zh")
        assert result.duration_seconds > 0


# ---------------------------------------------------------------------------
# DispatcherAuditMixin tests
# ---------------------------------------------------------------------------


class TestAuditMixin:
    """Tests for DispatcherAuditMixin."""

    def _make_mixin(self, **overrides: Any) -> DispatcherAuditMixin:
        m = DispatcherAuditMixin.__new__(DispatcherAuditMixin)
        m._audit_logger = overrides.get("_audit_logger")
        return m

    def test_log_end_no_logger_does_nothing(self) -> None:
        """_log_dispatch_end_audit does nothing when logger is None."""
        mixin = self._make_mixin(_audit_logger=None)
        mixin._log_dispatch_end_audit("user1", True, 1.5)

    def test_log_end_calls_logger(self) -> None:
        """_log_dispatch_end_audit calls logger.log_dispatch_end."""
        logger = MagicMock()
        mixin = self._make_mixin(_audit_logger=logger)
        mixin._log_dispatch_end_audit("user1", True, 1.5)
        logger.log_dispatch_end.assert_called_once_with(user_id="user1", success=True, duration=1.5)

    def test_log_end_handles_logger_error(self) -> None:
        """_log_dispatch_end_audit handles logger errors gracefully."""
        logger = MagicMock()
        logger.log_dispatch_end.side_effect = RuntimeError("fail")
        mixin = self._make_mixin(_audit_logger=logger)
        # Should not raise
        mixin._log_dispatch_end_audit("user1", True, 1.5)

    def test_log_error_no_logger_does_nothing(self) -> None:
        """_log_dispatch_error_audit does nothing when logger is None."""
        mixin = self._make_mixin(_audit_logger=None)
        mixin._log_dispatch_error_audit("user1", ValueError("err"))

    def test_log_error_calls_logger(self) -> None:
        """_log_dispatch_error_audit calls logger.log_error."""
        logger = MagicMock()
        mixin = self._make_mixin(_audit_logger=logger)
        error = ValueError("test error")
        mixin._log_dispatch_error_audit("user1", error)
        logger.log_error.assert_called_once()
        call_kwargs = logger.log_error.call_args[1]
        assert call_kwargs["user_id"] == "user1"
        assert call_kwargs["error_type"] == "ValueError"

    def test_log_error_handles_logger_error(self) -> None:
        """_log_dispatch_error_audit handles logger errors gracefully."""
        logger = MagicMock()
        logger.log_error.side_effect = OSError("fail")
        mixin = self._make_mixin(_audit_logger=logger)
        mixin._log_dispatch_error_audit("user1", ValueError("err"))

    def test_attach_entries_no_logger_does_nothing(self) -> None:
        """_attach_audit_entries does nothing when logger is None."""
        result = DispatchResult(success=True, task_description="t")
        mixin = self._make_mixin(_audit_logger=None)
        mixin._attach_audit_entries(result)
        assert result.audit_entries == []

    def test_attach_entries_attaches_from_logger(self) -> None:
        """_attach_audit_entries attaches entries from logger."""
        entry = MagicMock()
        entry.event_type = "dispatch_end"
        entry.user_id = "user1"
        entry.timestamp = "2026-01-01T00:00:00Z"
        entry.details = {"success": True}
        entry.entry_hash = "abc123"
        logger = MagicMock()
        logger.get_entries.return_value = [entry]
        result = DispatchResult(success=True, task_description="t")
        mixin = self._make_mixin(_audit_logger=logger)
        mixin._attach_audit_entries(result)
        assert len(result.audit_entries) == 1
        assert result.audit_entries[0]["event_type"] == "dispatch_end"
        assert result.audit_entries[0]["entry_hash"] == "abc123"

    def test_attach_entries_handles_error(self) -> None:
        """_attach_audit_entries handles logger errors gracefully."""
        logger = MagicMock()
        logger.get_entries.side_effect = RuntimeError("fail")
        result = DispatchResult(success=True, task_description="t")
        mixin = self._make_mixin(_audit_logger=logger)
        mixin._attach_audit_entries(result)
        # Should not crash, entries stay empty
        assert result.audit_entries == []


# ---------------------------------------------------------------------------
# DispatcherLifecycleMixin tests
# ---------------------------------------------------------------------------


class TestLifecycleMixin:
    """Tests for DispatcherLifecycleMixin."""

    def _make_mixin(self, **overrides: Any) -> DispatcherLifecycleMixin:
        m = DispatcherLifecycleMixin.__new__(DispatcherLifecycleMixin)
        m.warmup_manager = overrides.get("warmup_manager", MagicMock())
        m.memory_bridge = overrides.get("memory_bridge", MagicMock())
        m.usage_tracker = overrides.get("usage_tracker", MagicMock())
        m.enterprise = overrides.get("enterprise", MagicMock())
        m._audit_logger = overrides.get("_audit_logger", MagicMock())
        return m

    def test_shutdown_calls_all_components(self) -> None:
        """shutdown calls shutdown on all components."""
        wm = MagicMock()
        mb = MagicMock()
        ut = MagicMock()
        enterprise = MagicMock()
        audit_logger = MagicMock()
        mixin = self._make_mixin(
            warmup_manager=wm,
            memory_bridge=mb,
            usage_tracker=ut,
            enterprise=enterprise,
            _audit_logger=audit_logger,
        )
        mixin.shutdown()
        wm.shutdown.assert_called_once()
        mb.cleanup_expired_memories.assert_called_once()
        ut.persist.assert_called_once()
        enterprise.audit_logger.force_flush.assert_called_once()
        audit_logger.close.assert_called_once()
        enterprise.tenant_manager.clear_context.assert_called_once()

    def test_shutdown_handles_none_components(self) -> None:
        """shutdown handles None components gracefully."""
        mixin = self._make_mixin(
            warmup_manager=None,
            memory_bridge=None,
            usage_tracker=None,
        )
        # Should not raise
        mixin.shutdown()

    def test_shutdown_handles_exceptions(self) -> None:
        """shutdown handles component exceptions gracefully."""
        wm = MagicMock()
        wm.shutdown.side_effect = RuntimeError("fail")
        mixin = self._make_mixin(warmup_manager=wm)
        # Should not raise
        mixin.shutdown()

    def test_shutdown_component_none(self) -> None:
        """_shutdown_component does nothing when component is None."""
        mixin = self._make_mixin()
        mixin._shutdown_component(None, "method", (RuntimeError,), "msg")

    def test_shutdown_component_success(self) -> None:
        """_shutdown_component calls the method on the component."""
        component = MagicMock()
        mixin = self._make_mixin()
        mixin._shutdown_component(component, "shutdown", (RuntimeError,), "msg")
        component.shutdown.assert_called_once()

    def test_shutdown_component_handles_exception(self) -> None:
        """_shutdown_component handles specified exceptions."""
        component = MagicMock()
        component.shutdown.side_effect = RuntimeError("fail")
        mixin = self._make_mixin()
        # Should not raise
        mixin._shutdown_component(component, "shutdown", (RuntimeError,), "msg")

    def test_shutdown_component_does_not_handle_unspecified_exception(self) -> None:
        """_shutdown_component does not handle exceptions outside exc_types."""
        component = MagicMock()
        component.shutdown.side_effect = ValueError("not in exc_types")
        mixin = self._make_mixin()
        # ValueError is not in (RuntimeError,), so it should propagate
        with pytest.raises(ValueError):
            mixin._shutdown_component(component, "shutdown", (RuntimeError,), "msg")
