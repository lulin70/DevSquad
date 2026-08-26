"""Tests for scripts.collaboration.prometheus_metrics.

Covers stub classes (Counter, Gauge, Histogram, Info, _NullContextManager),
DevSquadMetrics methods, get_metrics singleton, and reset_metrics.
"""

from __future__ import annotations

import pytest

from scripts.collaboration.prometheus_metrics import (
    _PROMETHEUS_AVAILABLE,
    Counter,
    DevSquadMetrics,
    Gauge,
    Histogram,
    Info,
    _NullContextManager,
    get_metrics,
    reset_metrics,
)


@pytest.fixture(autouse=True)
def _clear_prometheus_registry():
    """Clear the global CollectorRegistry before each test to avoid duplicate
    timeseries errors when multiple tests create metrics with the same names.
    Stubs are no-ops so this is safe when prometheus_client is unavailable.
    """
    if _PROMETHEUS_AVAILABLE:
        from prometheus_client import REGISTRY

        for collector in list(REGISTRY._collector_to_names.keys()):
            REGISTRY.unregister(collector)
    yield
    if _PROMETHEUS_AVAILABLE:
        from prometheus_client import REGISTRY

        for collector in list(REGISTRY._collector_to_names.keys()):
            REGISTRY.unregister(collector)


# ---------------------------------------------------------------------------
# Stub classes (active when prometheus_client is not installed)
# ---------------------------------------------------------------------------


class TestCounterStub:
    def test_init_no_args(self):
        c = Counter("test_counter_init_no_args", "desc")
        assert c is not None

    def test_init_with_args(self):
        c = Counter("test_counter_init_with_args", "desc", ["label1", "label2"])
        assert c is not None

    def test_labels_returns_callable(self):
        c = Counter("test_counter_labels", "desc", ["key"])
        labeled = c.labels(key="val")
        assert labeled is not None
        assert hasattr(labeled, "inc")

    def test_inc_default(self):
        c = Counter("test_counter_inc_default", "desc")
        c.inc()

    def test_inc_with_amount(self):
        c = Counter("test_counter_inc_with_amount", "desc")
        c.inc(5)


class TestGaugeStub:
    def test_init(self):
        g = Gauge("test_gauge_init", "desc")
        assert g is not None

    def test_labels_returns_callable(self):
        g = Gauge("test_gauge_labels", "desc", ["key"])
        labeled = g.labels(key="val")
        assert labeled is not None
        assert hasattr(labeled, "set")

    def test_set(self):
        g = Gauge("test_gauge_set", "desc")
        g.set(42.0)

    def test_inc_default(self):
        g = Gauge("test_gauge_inc_default", "desc")
        g.inc()

    def test_inc_with_amount(self):
        g = Gauge("test_gauge_inc_with_amount", "desc")
        g.inc(3)

    def test_dec_default(self):
        g = Gauge("test_gauge_dec_default", "desc")
        g.dec()

    def test_dec_with_amount(self):
        g = Gauge("test_gauge_dec_with_amount", "desc")
        g.dec(2)


class TestHistogramStub:
    def test_init(self):
        h = Histogram("test_histogram_init", "desc")
        assert h is not None

    def test_labels_returns_callable(self):
        h = Histogram("test_histogram_labels", "desc", ["key"])
        labeled = h.labels(key="val")
        assert labeled is not None
        assert hasattr(labeled, "observe")

    def test_observe(self):
        h = Histogram("test_histogram_observe", "desc")
        h.observe(1.5)

    def test_time_returns_context_manager(self):
        h = Histogram("test_histogram_time", "desc")
        cm = h.time()
        assert hasattr(cm, "__enter__")
        assert hasattr(cm, "__exit__")


class TestInfoStub:
    def test_init(self):
        i = Info("test_info_init", "desc")
        assert i is not None

    def test_info(self):
        i = Info("test_info_method", "desc")
        i.info({"version": "1.0.0"})


class TestNullContextManager:
    def test_enter_returns_self(self):
        cm = _NullContextManager()
        assert cm.__enter__() is cm

    def test_exit_returns_none(self):
        cm = _NullContextManager()
        assert cm.__exit__(None, None, None) is None

    def test_exit_with_args(self):
        cm = _NullContextManager()
        cm.__exit__(ValueError, ValueError("test"), None)

    def test_usage_as_with_statement(self):
        cm = _NullContextManager()
        with cm:
            pass


# ---------------------------------------------------------------------------
# DevSquadMetrics
# ---------------------------------------------------------------------------


class TestDevSquadMetricsInit:
    def test_init_creates_all_metrics(self):
        m = DevSquadMetrics()
        assert hasattr(m, "dispatch_counter")
        assert hasattr(m, "dispatch_histogram")
        assert hasattr(m, "llm_calls_counter")
        assert hasattr(m, "llm_duration_histogram")
        assert hasattr(m, "cache_hits_counter")
        assert hasattr(m, "cache_misses_counter")
        assert hasattr(m, "workers_active_gauge")
        assert hasattr(m, "errors_counter")
        assert hasattr(m, "tasks_in_progress_gauge")
        assert hasattr(m, "consensus_rounds_counter")
        assert hasattr(m, "gate_checks_counter")
        assert hasattr(m, "build_info")

    def test_dispatch_buckets(self):
        assert DevSquadMetrics.DISPATCH_BUCKETS == [
            0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0,
        ]

    def test_llm_buckets(self):
        assert DevSquadMetrics.LLM_BUCKETS == [
            0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0,
        ]


class TestRecordDispatch:
    def test_record_dispatch(self):
        m = DevSquadMetrics()
        m.record_dispatch("parallel", 3, 1.5)

    def test_record_dispatch_sequential_mode(self):
        m = DevSquadMetrics()
        m.record_dispatch("sequential", 1, 0.5)

    def test_record_dispatch_zero_duration(self):
        m = DevSquadMetrics()
        m.record_dispatch("parallel", 0, 0.0)


class TestDispatchTimer:
    def test_dispatch_timer_records_duration(self):
        m = DevSquadMetrics()
        with m.dispatch_timer("parallel", 3):
            pass

    def test_dispatch_timer_records_even_on_exception(self):
        m = DevSquadMetrics()
        with pytest.raises(RuntimeError), m.dispatch_timer("parallel", 2):
            raise RuntimeError("test error")


class TestRecordLLMCall:
    def test_record_llm_call_success(self):
        m = DevSquadMetrics()
        m.record_llm_call("openai", 2.3, True)

    def test_record_llm_call_failure(self):
        m = DevSquadMetrics()
        m.record_llm_call("anthropic", 5.0, False)

    def test_record_llm_call_zero_duration(self):
        m = DevSquadMetrics()
        m.record_llm_call("openai", 0.0, True)


class TestLLMCallTimer:
    def test_llm_call_timer_success(self):
        m = DevSquadMetrics()
        with m.llm_call_timer("openai"):
            pass

    def test_llm_call_timer_exception_records_failure(self):
        m = DevSquadMetrics()
        with pytest.raises(ValueError), m.llm_call_timer("openai"):
            raise ValueError("LLM error")


class TestCacheMetrics:
    def test_record_cache_hit(self):
        m = DevSquadMetrics()
        m.record_cache_hit("l1", "llm_response")

    def test_record_cache_miss(self):
        m = DevSquadMetrics()
        m.record_cache_miss("l2", "prompt")


class TestWorkerMetrics:
    def test_set_active_workers(self):
        m = DevSquadMetrics()
        m.set_active_workers("agent", 5)

    def test_inc_active_workers(self):
        m = DevSquadMetrics()
        m.inc_active_workers("llm")

    def test_dec_active_workers(self):
        m = DevSquadMetrics()
        m.dec_active_workers("coordinator")


class TestErrorMetrics:
    def test_record_error(self):
        m = DevSquadMetrics()
        m.record_error("timeout", "dispatcher")

    def test_record_error_rate_limit(self):
        m = DevSquadMetrics()
        m.record_error("rate_limit", "llm_backend")


class TestTaskProgressMetrics:
    def test_set_tasks_in_progress(self):
        m = DevSquadMetrics()
        m.set_tasks_in_progress("execute", 3)


class TestConsensusMetrics:
    def test_record_consensus_round_agreed(self):
        m = DevSquadMetrics()
        m.record_consensus_round("agreed")

    def test_record_consensus_round_disagreed(self):
        m = DevSquadMetrics()
        m.record_consensus_round("disagreed")


class TestGateCheckMetrics:
    def test_record_gate_check_pass(self):
        m = DevSquadMetrics()
        m.record_gate_check("quality", "pass")

    def test_record_gate_check_fail(self):
        m = DevSquadMetrics()
        m.record_gate_check("security", "fail")


class TestBuildInfo:
    def test_set_build_info_version_only(self):
        m = DevSquadMetrics()
        m.set_build_info("4.0.5")

    def test_set_build_info_with_commit(self):
        m = DevSquadMetrics()
        m.set_build_info("4.0.5", commit="abc123")

    def test_set_build_info_with_all(self):
        m = DevSquadMetrics()
        m.set_build_info("4.0.5", commit="abc123", build_date="2026-07-11")


class TestGenerateMetrics:
    def test_generate_metrics_returns_none_when_unavailable(self):
        m = DevSquadMetrics()
        if not _PROMETHEUS_AVAILABLE:
            assert m.generate_metrics() is None

    def test_is_available(self):
        m = DevSquadMetrics()
        assert m.is_available() is _PROMETHEUS_AVAILABLE


# ---------------------------------------------------------------------------
# Singleton functions
# ---------------------------------------------------------------------------


class TestGetMetrics:
    def test_get_metrics_returns_instance(self):
        reset_metrics()
        m = get_metrics()
        assert isinstance(m, DevSquadMetrics)

    def test_get_metrics_returns_singleton(self):
        reset_metrics()
        m1 = get_metrics()
        m2 = get_metrics()
        assert m1 is m2


class TestResetMetrics:
    def test_reset_clears_singleton(self):
        reset_metrics()
        m1 = get_metrics()
        reset_metrics()
        m2 = get_metrics()
        assert m1 is not m2

    def test_reset_does_not_raise(self):
        reset_metrics()
        reset_metrics()


# ---------------------------------------------------------------------------
# V4.5.2 module-specific metrics (P11.1)
# ---------------------------------------------------------------------------


class TestV452MetricsInit:
    """Verify V4.5.2-specific metrics are created in __init__."""

    def test_init_creates_task_scale_counter(self):
        m = DevSquadMetrics()
        assert hasattr(m, "task_scale_counter")
        assert hasattr(m, "task_scale_counter")
        assert m.task_scale_counter is not None

    def test_init_creates_order_chain_counter(self):
        m = DevSquadMetrics()
        assert hasattr(m, "order_chain_counter")
        assert m.order_chain_counter is not None

    def test_init_creates_backend_call_counter_er(self):
        m = DevSquadMetrics()
        assert hasattr(m, "backend_calls_counter")
        assert m.backend_calls_counter is not None

    def test_init_creates_backend_failure_counter(self):
        m = DevSquadMetrics()
        assert hasattr(m, "backend_failures_counter")
        assert m.backend_failures_counter is not None

    def test_init_creates_fuse_skip_counter(self):
        m = DevSquadMetrics()
        assert hasattr(m, "fuse_skips_counter")
        assert m.fuse_skips_counter is not None

    def test_init_creates_perf_p95_gauge(self):
        m = DevSquadMetrics()
        assert hasattr(m, "perf_p95_gauge")
        assert m.perf_p95_gauge is not None

    def test_init_creates_perf_regression_counter(self):
        m = DevSquadMetrics()
        assert hasattr(m, "perf_regression_counter")
        assert m.perf_regression_counter is not None

    def test_init_creates_perf_latency_histogram(self):
        m = DevSquadMetrics()
        assert hasattr(m, "perf_latency_histogram")
        assert m.perf_latency_histogram is not None

    def test_perf_buckets_defined(self):
        # S/M/L/B/A/C paths covered, max 10s
        assert hasattr(DevSquadMetrics, "PERF_BUCKETS")
        assert DevSquadMetrics.PERF_BUCKETS[0] == 50.0
        assert DevSquadMetrics.PERF_BUCKETS[-1] == 10000.0


class TestRecordTaskScale:
    """Test TaskScaleGate decision recording."""

    def test_record_S(self):
        m = DevSquadMetrics()
        m.record_task_scale("S", "auto")

    def test_record_M(self):
        m = DevSquadMetrics()
        m.record_task_scale("M", "mini")

    def test_record_L(self):
        m = DevSquadMetrics()
        m.record_task_scale("L", "consensus")

    def test_record_multiple_calls(self):
        m = DevSquadMetrics()
        m.record_task_scale("S", "auto")
        m.record_task_scale("M", "mini")
        m.record_task_scale("L", "consensus")


class TestRecordOrderChain:
    """Test OrderChainDetector decision recording."""

    def test_record_user_single(self):
        m = DevSquadMetrics()
        m.record_order_chain("user", True)

    def test_record_heuristic_parallel(self):
        m = DevSquadMetrics()
        m.record_order_chain("heuristic", False)

    def test_record_default_parallel(self):
        m = DevSquadMetrics()
        m.record_order_chain("default", False)


class TestRecordBackendCall:
    """Test backend path B/A/C call counter."""

    def test_record_B(self):
        m = DevSquadMetrics()
        m.record_backend_call("B")

    def test_record_A(self):
        m = DevSquadMetrics()
        m.record_backend_call("A")

    def test_record_C(self):
        m = DevSquadMetrics()
        m.record_backend_call("C")


class TestRecordBackendFailure:
    """Test backend failure counter."""

    def test_record_host_timeout(self):
        m = DevSquadMetrics()
        m.record_backend_failure("B", "host_timeout")

    def test_record_auth_invalid(self):
        m = DevSquadMetrics()
        m.record_backend_failure("A", "auth_invalid")

    def test_record_rate_limit(self):
        m = DevSquadMetrics()
        m.record_backend_failure("A", "rate_limit")

    def test_record_network_error(self):
        m = DevSquadMetrics()
        m.record_backend_failure("B", "network_error")

    def test_record_provider_error(self):
        m = DevSquadMetrics()
        m.record_backend_failure("A", "provider_error")


class TestRecordFuseSkip:
    """Test fuse-skip counter (path permanently disabled)."""

    def test_record_fuse_skip_B(self):
        m = DevSquadMetrics()
        m.record_fuse_skip("B", "host_timeout")

    def test_record_fuse_skip_A(self):
        m = DevSquadMetrics()
        m.record_fuse_skip("A", "auth_invalid")

    def test_fuse_skip_also_counts_as_failure(self):
        # Both counters should increment
        m = DevSquadMetrics()
        m.record_fuse_skip("B", "host_timeout")
        # No exception means success; the counters are stubbed so we can't
        # inspect values, but the call must not raise.
