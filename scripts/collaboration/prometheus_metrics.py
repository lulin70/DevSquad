#!/usr/bin/env python3
"""
Prometheus Metrics Collector for DevSquad

Production-grade metrics collection using prometheus_client library.
Provides Counter/Histogram/Gauge metrics for task dispatch, LLM calls,
cache operations, worker status, and error tracking.

Usage:
    from scripts.collaboration.prometheus_metrics import get_metrics

    metrics = get_metrics()
    metrics.record_dispatch("parallel", 3, 1.5)
    metrics.record_llm_call("openai", 2.3, True)

Metrics Endpoint:
    GET /metrics  (exposed via FastAPI router)

Dependencies:
    pip install prometheus-client
"""

import importlib.util
import logging
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

_PROMETHEUS_AVAILABLE = importlib.util.find_spec("prometheus_client") is not None

if _PROMETHEUS_AVAILABLE:
    from prometheus_client import REGISTRY, Counter, Gauge, Histogram, Info, generate_latest
else:

    class Counter:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def labels(self, *_args: Any, **_kwargs: Any) -> Any:
            """Return self to support chaining when prometheus is unavailable."""
            return self

        def inc(self, amount: int = 1) -> None:
            """No-op increment for the stub counter."""
            pass

    class Gauge:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def labels(self, *_args: Any, **_kwargs: Any) -> Any:
            """Return self to support chaining when prometheus is unavailable."""
            return self

        def set(self, value: float) -> None:
            """No-op set for the stub gauge."""
            pass

        def inc(self, amount: int = 1) -> None:
            """No-op increment for the stub gauge."""
            pass

        def dec(self, amount: int = 1) -> None:
            """No-op decrement for the stub gauge."""
            pass

    class Histogram:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def labels(self, *_args: Any, **_kwargs: Any) -> Any:
            """Return self to support chaining when prometheus is unavailable."""
            return self

        def observe(self, amount: float) -> None:
            """No-op observe for the stub histogram."""
            pass

        def time(self) -> "_NullContextManager":
            """Return a null context manager for timing when prometheus is unavailable."""
            return _NullContextManager()

    class Info:  # type: ignore[no-redef]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            pass

        def info(self, info_dict: dict[str, str]) -> None:
            """No-op info setter for the stub Info metric."""
            pass


class _NullContextManager:
    """Fallback context manager when prometheus_client is not available."""

    def __enter__(self) -> "_NullContextManager":
        return self

    def __exit__(self, *args: Any) -> None:
        pass  # intentional no-op: null context manager has nothing to clean up


logger = logging.getLogger(__name__)


class DevSquadMetrics:
    """
    Prometheus Metrics Collector for DevSquad.

    Provides production-grade metrics for monitoring and alerting.
    All metrics follow Prometheus naming conventions with 'devsquad_' prefix.

    Metrics Defined:
    - devsquad_dispatch_total: Task dispatch counter
    - devsquad_dispatch_duration_seconds: Dispatch latency histogram
    - devsquad_llm_calls_total: LLM API call counter
    - devsquad_llm_duration_seconds: LLM latency histogram
    - devsquad_cache_hits_total: Cache hit counter
    - devsquad_cache_misses_total: Cache miss counter
    - devsquad_workers_active: Active worker gauge
    - devsquad_errors_total: Error counter by type
    """

    DISPATCH_BUCKETS = [0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0]
    LLM_BUCKETS = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
    PERF_BUCKETS = [50.0, 100.0, 200.0, 500.0, 1000.0, 2000.0, 5000.0, 10000.0]

    def __init__(self) -> None:
        """Initialize all Prometheus metrics."""
        if not _PROMETHEUS_AVAILABLE:
            logger.warning(
                "prometheus-client not installed. "
                "Install with: pip install prometheus-client"
            )

        self.dispatch_counter = Counter(
            "devsquad_dispatch_total",
            "Total number of task dispatches",
            ["mode", "role_count"],
        )
        self.dispatch_histogram = Histogram(
            "devsquad_dispatch_duration_seconds",
            "Time spent on task dispatch",
            ["mode"],
            buckets=self.DISPATCH_BUCKETS,
        )
        self.llm_calls_counter = Counter(
            "devsquad_llm_calls_total",
            "Total number of LLM API calls",
            ["backend", "success"],
        )
        self.llm_duration_histogram = Histogram(
            "devsquad_llm_duration_seconds",
            "Time spent on LLM API calls",
            ["backend"],
            buckets=self.LLM_BUCKETS,
        )
        self.cache_hits_counter = Counter(
            "devsquad_cache_hits_total",
            "Total number of cache hits",
            ["cache_level", "operation"],
        )
        self.cache_misses_counter = Counter(
            "devsquad_cache_misses_total",
            "Total number of cache misses",
            ["cache_level", "operation"],
        )
        self.workers_active_gauge = Gauge(
            "devsquad_workers_active",
            "Number of currently active workers",
            ["worker_type"],
        )
        self.errors_counter = Counter(
            "devsquad_errors_total",
            "Total number of errors",
            ["error_type", "component"],
        )
        self.tasks_in_progress_gauge = Gauge(
            "devsquad_tasks_in_progress",
            "Number of tasks currently in progress",
            ["phase"],
        )
        self.consensus_rounds_counter = Counter(
            "devsquad_consensus_rounds_total",
            "Total number of consensus rounds",
            ["outcome"],
        )
        self.gate_checks_counter = Counter(
            "devsquad_gate_checks_total",
            "Total number of gate checks",
            ["gate_name", "result"],
        )
        self.build_info = Info(
            "devsquad_build",
            "DevSquad build information",
        )

        # === V4.5.2 module-specific metrics (P11.1) ===

        # TaskScaleGate — counts decisions by S/M/L level
        self.task_scale_counter = Counter(
            "devsquad_v452_task_scale_total",
            "V4.5.2 TaskScaleGate decisions by level (S/M/L)",
            ["level", "orchestrator"],
        )

        # OrderChainDetector — counts decisions by source
        self.order_chain_counter = Counter(
            "devsquad_v452_order_chain_total",
            "V4.5.2 OrderChainDetector decisions by source",
            ["source", "single_role"],
        )

        # Backend path B/A/C usage
        self.backend_calls_counter = Counter(
            "devsquad_v452_backend_calls_total",
            "V4.5.2 backend path invocation count by path",
            ["path"],
        )

        # Backend failures classified by reason (drives fuse counter)
        self.backend_failures_counter = Counter(
            "devsquad_v452_backend_failures_total",
            "V4.5.2 backend failure count by reason",
            ["path", "reason"],
        )

        # Fuse skip events (path permanently skipped after N consecutive failures)
        self.fuse_skips_counter = Counter(
            "devsquad_v452_fuse_skips_total",
            "V4.5.2 fuse-skip events (path permanently disabled)",
            ["path", "reason"],
        )

        # PerfBaseline p95 gauge (latest snapshot per path)
        self.perf_p95_gauge = Gauge(
            "devsquad_v452_perf_p95_ms",
            "V4.5.2 latest PerfSnapshot p95 latency in ms",
            ["path"],
        )

        # Perf regression vs baseline (1 = within_threshold, 0 = regression blocked)
        self.perf_regression_counter = Counter(
            "devsquad_v452_perf_regression_total",
            "V4.5.2 perf baseline comparison outcome (1=blocked)",
            ["path", "outcome"],
        )

        # Perf latency histogram per path
        self.perf_latency_histogram = Histogram(
            "devsquad_v452_perf_latency_ms",
            "V4.5.2 perf latency samples in ms",
            ["path"],
            buckets=self.PERF_BUCKETS,
        )

        # === V4.5.13: risk store re-project trigger metrics (from V4.5.12 stats) ===

        # V4.5.13: names carry the explicit `_total` suffix (prometheus_client
        # normalizes Counter samples to `_total`; naming them up front keeps
        # ALERT_RULES expressions and exposition samples identical).
        self.risk_store_capacity_gauge = Gauge(
            "devsquad_v4512_risk_store_capacity",
            "V4.5.12 risk store item count at last load/save (SQLite trigger: >10k)",
            ["register_id"],
        )
        self.risk_store_concurrent_writes_counter = Counter(
            "devsquad_v4512_risk_store_concurrent_writes_total",
            "V4.5.12 risk store writes in the 60s sliding window",
            ["register_id"],
        )
        self.risk_store_cross_host_counter = Counter(
            "devsquad_v4512_risk_store_cross_host_signals_total",
            "V4.5.12 cross-host lock acquisition signals (SQLite trigger: remote share)",
            ["register_id"],
        )
        self.risk_store_slow_queries_counter = Counter(
            "devsquad_v4512_risk_store_slow_queries_total",
            "V4.5.12 query rounds over 50ms (SQLite trigger: complex query demand)",
            ["register_id"],
        )

    def record_risk_store_stats(self, stats: Any, register_id: str = "default") -> None:
        """V4.5.13: publish a FileRiskStore.stats snapshot to Prometheus.

        Counters are driven by delta against the last exported values so
        repeated exports do not double-increment.
        """
        last = getattr(self, "_risk_store_stats_last", None)
        if last is None:
            last = self._risk_store_stats_last = {
                "concurrent": 0,
                "cross_host": 0,
                "slow": 0,
            }
        self.risk_store_capacity_gauge.labels(register_id=register_id).set(stats.capacity)
        if stats.concurrent_writes_1m > last["concurrent"]:
            self.risk_store_concurrent_writes_counter.labels(register_id=register_id).inc(
                stats.concurrent_writes_1m - last["concurrent"]
            )
            last["concurrent"] = stats.concurrent_writes_1m
        if stats.cross_host_lock_signals > last["cross_host"]:
            self.risk_store_cross_host_counter.labels(register_id=register_id).inc(
                stats.cross_host_lock_signals - last["cross_host"]
            )
            last["cross_host"] = stats.cross_host_lock_signals
        if stats.slow_query_signals > last["slow"]:
            self.risk_store_slow_queries_counter.labels(register_id=register_id).inc(
                stats.slow_query_signals - last["slow"]
            )
            last["slow"] = stats.slow_query_signals

    # ------------------------------------------------------------------
    # V4.5.2 module-specific recording helpers (P11.1)
    # ------------------------------------------------------------------

    def record_task_scale(self, level: str, orchestrator: str) -> None:
        """Record TaskScaleGate.decide() outcome.

        Args:
            level: 'S' | 'M' | 'L' — scale decision
            orchestrator: 'auto' | 'mini' | 'consensus' — coordinator mode
        """
        self.task_scale_counter.labels(level=level, orchestrator=orchestrator).inc()

    def record_order_chain(self, source: str, single_role: bool) -> None:
        """Record OrderChainDetector.detect() outcome.

        Args:
            source: 'user' | 'role_meta' | 'heuristic' | 'default'
            single_role: True if chain executed sequentially
        """
        self.order_chain_counter.labels(
            source=source,
            single_role="true" if single_role else "false",
        ).inc()

    def record_backend_call(self, path: str) -> None:
        """Record a backend path invocation.

        Args:
            path: 'B' (host bridge) | 'A' (direct API) | 'C' (mock)
        """
        self.backend_calls_counter.labels(path=path).inc()

    def record_backend_failure(self, path: str, reason: str) -> None:
        """Record a backend failure classified by reason.

        Args:
            path: 'B' | 'A' | 'C'
            reason: BackendErrorReason value (host_timeout/auth_invalid/...)
        """
        self.backend_failures_counter.labels(path=path, reason=reason).inc()

    def record_fuse_skip(self, path: str, reason: str) -> None:
        """Record a fuse-skip event (path permanently disabled).

        Args:
            path: 'B' | 'A' | 'C'
            reason: The reason that triggered the skip
        """
        self.fuse_skips_counter.labels(path=path, reason=reason).inc()
        # Also count as a backend failure for alerting
        self.backend_failures_counter.labels(path=path, reason=reason).inc()

    def record_perf_snapshot(
        self,
        path: str,
        p95_ms: float,
        within_threshold: bool | None = None,
        delta_p95_pct: float | None = None,
    ) -> None:
        """Record PerfBaseline snapshot.

        Args:
            path: 'mock' | 'host' | 'api' | 'auto_fallback'
            p95_ms: p95 latency in ms
            within_threshold: True/False/None — whether regression is within gate
            delta_p95_pct: % vs baseline (None if no baseline)
        """
        # Note: delta_p95_pct is retained for future alerting use but not
        # currently emitted as a metric. The gate outcome (within_threshold)
        # is the signal consumed by Prometheus rules.
        del delta_p95_pct
        self.perf_p95_gauge.labels(path=path).set(p95_ms)
        self.perf_latency_histogram.labels(path=path).observe(p95_ms)
        if within_threshold is True:
            self.perf_regression_counter.labels(path=path, outcome="pass").inc()
        elif within_threshold is False:
            self.perf_regression_counter.labels(path=path, outcome="block").inc()

    def record_dispatch(self, mode: str, role_count: int, duration: float) -> None:
        """
        Record a task dispatch event.

        Args:
            mode: Dispatch mode ('parallel', 'sequential', 'adaptive')
            role_count: Number of roles involved
            duration: Dispatch duration in seconds
        """
        self.dispatch_counter.labels(mode=mode, role_count=str(role_count)).inc()
        self.dispatch_histogram.labels(mode=mode).observe(duration)
        logger.debug(
            "Recorded dispatch: mode=%s, roles=%d, duration=%.3fs",
            mode,
            role_count,
            duration,
        )

    @contextmanager
    def dispatch_timer(self, mode: str, role_count: int) -> Generator[None, None, None]:
        """
        Context manager for timing dispatch operations.

        Args:
            mode: Dispatch mode
            role_count: Number of roles involved

        Example:
            with metrics.dispatch_timer("parallel", 3):
                result = dispatcher.run(task)
        """
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_dispatch(mode, role_count, duration)

    def record_llm_call(self, backend: str, duration: float, success: bool) -> None:
        """
        Record an LLM API call event.

        Args:
            backend: LLM backend name ('openai', 'anthropic', etc.)
            duration: Call duration in seconds
            success: Whether the call was successful
        """
        success_label = "true" if success else "false"
        self.llm_calls_counter.labels(backend=backend, success=success_label).inc()
        self.llm_duration_histogram.labels(backend=backend).observe(duration)
        logger.debug(
            "Recorded LLM call: backend=%s, success=%s, duration=%.3fs",
            backend,
            success_label,
            duration,
        )

    @contextmanager
    def llm_call_timer(self, backend: str) -> Generator[None, None, None]:
        """
        Context manager for timing LLM calls.

        Args:
            backend: LLM backend name

        Example:
            with metrics.llm_call_timer("openai"):
                response = await client.chat.completions.create(...)
        """
        start_time = time.time()
        success = True
        try:
            yield
        except Exception as e:
            logger.debug("LLM call failed in observe context: %s", e)
            success = False
            raise
        finally:
            duration = time.time() - start_time
            self.record_llm_call(backend, duration, success)

    def record_cache_hit(self, cache_level: str, operation: str) -> None:
        """
        Record a cache hit event.

        Args:
            cache_level: Cache level ('l1', 'l2', 'redis')
            operation: Operation type ('llm_response', 'prompt', 'embedding')
        """
        self.cache_hits_counter.labels(cache_level=cache_level, operation=operation).inc()

    def record_cache_miss(self, cache_level: str, operation: str) -> None:
        """
        Record a cache miss event.

        Args:
            cache_level: Cache level ('l1', 'l2', 'redis')
            operation: Operation type ('llm_response', 'prompt', 'embedding')
        """
        self.cache_misses_counter.labels(cache_level=cache_level, operation=operation).inc()

    def set_active_workers(self, worker_type: str, count: int) -> None:
        """
        Set the number of active workers.

        Args:
            worker_type: Type of worker ('agent', 'llm', 'coordinator')
            count: Current active count
        """
        self.workers_active_gauge.labels(worker_type=worker_type).set(count)

    def inc_active_workers(self, worker_type: str) -> None:
        """Increment active worker count."""
        self.workers_active_gauge.labels(worker_type=worker_type).inc()

    def dec_active_workers(self, worker_type: str) -> None:
        """Decrement active worker count."""
        self.workers_active_gauge.labels(worker_type=worker_type).dec()

    def record_error(self, error_type: str, component: str) -> None:
        """
        Record an error event.

        Args:
            error_type: Error category ('timeout', 'rate_limit', 'auth', 'validation', 'unknown')
            component: Component that raised the error ('dispatcher', 'llm_backend', 'cache', etc.)
        """
        self.errors_counter.labels(error_type=error_type, component=component).inc()
        logger.debug("Recorded error: type=%s, component=%s", error_type, component)

    def set_tasks_in_progress(self, phase: str, count: int) -> None:
        """
        Set the number of tasks in progress for a phase.

        Args:
            phase: Lifecycle phase name
            count: Current task count
        """
        self.tasks_in_progress_gauge.labels(phase=phase).set(count)

    def record_consensus_round(self, outcome: str) -> None:
        """
        Record a consensus round completion.

        Args:
            outcome: Round outcome ('agreed', 'disagreed', 'timeout', 'error')
        """
        self.consensus_rounds_counter.labels(outcome=outcome).inc()

    def record_gate_check(self, gate_name: str, result: str) -> None:
        """
        Record a gate check event.

        Args:
            gate_name: Name of the gate ('quality', 'security', 'performance')
            result: Check result ('pass', 'fail', 'warn', 'skip')
        """
        self.gate_checks_counter.labels(gate_name=gate_name, result=result).inc()

    def set_build_info(self, version: str, commit: str = "", build_date: str = "") -> None:
        """
        Set build information metadata.

        Args:
            version: Application version
            commit: Git commit hash
            build_date: Build timestamp
        """
        info_dict = {"version": version}
        if commit:
            info_dict["commit"] = commit
        if build_date:
            info_dict["build_date"] = build_date
        self.build_info.info(info_dict)

    def generate_metrics(self) -> bytes | None:
        """
        Generate Prometheus exposition format metrics.

        Returns:
            Bytes containing Prometheus metrics text, or None if unavailable
        """
        if not _PROMETHEUS_AVAILABLE:
            return None
        latest = generate_latest(REGISTRY)
        return bytes(latest) if latest is not None else None

    def is_available(self) -> bool:
        """Check if Prometheus client is available."""
        return _PROMETHEUS_AVAILABLE


_metrics_instance: DevSquadMetrics | None = None


def get_metrics() -> DevSquadMetrics:
    """
    Get or create global metrics instance (singleton).

    Returns:
        DevSquadMetrics singleton instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = DevSquadMetrics()
    return _metrics_instance


def reset_metrics() -> None:
    """Reset global metrics instance (mainly for testing).

    Also unregisters all collectors from the global REGISTRY so that
    a subsequent ``get_metrics()`` call can re-create metrics without
    hitting "Duplicated timeseries" errors.
    """
    global _metrics_instance
    _metrics_instance = None
    if _PROMETHEUS_AVAILABLE:
        for collector in list(REGISTRY._collector_to_names.keys()):
            REGISTRY.unregister(collector)
