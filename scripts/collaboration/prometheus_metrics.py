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
