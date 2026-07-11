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

# ---------------------------------------------------------------------------
# Stub classes (active when prometheus_client is not installed)
# ---------------------------------------------------------------------------


class TestCounterStub:
    def test_init_no_args(self):
        c = Counter("name", "desc")
        assert c is not None

    def test_init_with_args(self):
        c = Counter("name", "desc", ["label1", "label2"])
        assert c is not None

    def test_labels_returns_self(self):
        c = Counter("name", "desc")
        assert c.labels(key="val") is c

    def test_inc_default(self):
        c = Counter("name", "desc")
        c.inc()

    def test_inc_with_amount(self):
        c = Counter("name", "desc")
        c.inc(5)

    def test_observe(self):
        c = Counter("name", "desc")
        c.observe(3.14)


class TestGaugeStub:
    def test_init(self):
        g = Gauge("name", "desc")
        assert g is not None

    def test_labels_returns_self(self):
        g = Gauge("name", "desc")
        assert g.labels(key="val") is g

    def test_set(self):
        g = Gauge("name", "desc")
        g.set(42.0)

    def test_inc_default(self):
        g = Gauge("name", "desc")
        g.inc()

    def test_inc_with_amount(self):
        g = Gauge("name", "desc")
        g.inc(3)

    def test_dec_default(self):
        g = Gauge("name", "desc")
        g.dec()

    def test_dec_with_amount(self):
        g = Gauge("name", "desc")
        g.dec(2)


class TestHistogramStub:
    def test_init(self):
        h = Histogram("name", "desc")
        assert h is not None

    def test_labels_returns_self(self):
        h = Histogram("name", "desc")
        assert h.labels(key="val") is h

    def test_observe(self):
        h = Histogram("name", "desc")
        h.observe(1.5)

    def test_time_returns_context_manager(self):
        h = Histogram("name", "desc")
        cm = h.time()
        assert isinstance(cm, _NullContextManager)


class TestInfoStub:
    def test_init(self):
        i = Info("name", "desc")
        assert i is not None

    def test_info(self):
        i = Info("name", "desc")
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
        m.set_build_info("4.0.4")

    def test_set_build_info_with_commit(self):
        m = DevSquadMetrics()
        m.set_build_info("4.0.4", commit="abc123")

    def test_set_build_info_with_all(self):
        m = DevSquadMetrics()
        m.set_build_info("4.0.4", commit="abc123", build_date="2026-07-11")


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
    def test_reset_clears_instance(self):
        get_metrics()
        reset_metrics()
        from scripts.collaboration import prometheus_metrics

        assert prometheus_metrics._metrics_instance is None

    def test_reset_then_get_creates_new(self):
        m1 = get_metrics()
        reset_metrics()
        m2 = get_metrics()
        assert m1 is not m2
