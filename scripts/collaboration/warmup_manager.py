#!/usr/bin/env python3
"""
WarmupManager - 启动预热管理器

分层异步预热 + 懒加载 + 进程级缓存，将冷启动时间从 ~1.7s 优化到 < 1s。

核心策略:
- L1 Eager: 同步阻塞，导入时立即执行（~15ms）
- L2 Async: 后台线程异步执行（~300ms，非阻塞）
- LAZY: 首次访问时按需触发（< 200ms）
- ProcessCache: TTL + LRU 淘汰的进程级单例缓存

使用示例:
    from collaboration.warmup_manager import WarmupManager, WarmupConfig

    wm = WarmupManager.instance(WarmupConfig.default())
    report = wm.warmup()

    coordinator = wm.get_or_load("coordinator", lambda: Coordinator())
"""

import concurrent.futures
import contextlib
import logging
import os
import statistics
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, ClassVar, Optional

logger = logging.getLogger(__name__)


class WarmupLayer(Enum):
    EAGER = "eager"
    ASYNC = "async"
    LAZY = "lazy"


class WarmupStatus(Enum):
    SUCCESS = "success"
    TIMEOUT = "timeout"
    ERROR = "error"
    SKIPPED = "skipped"
    PENDING = "pending"


@dataclass
class WarmupConfig:
    enabled: bool = True
    eager_timeout_ms: int = 200
    async_timeout_ms: int = 5000
    async_workers: int = 4
    cache_enabled: bool = True
    cache_max_size: int = 200
    cache_ttl_seconds: float = 3600.0
    preload_roles: list[str] | None = None
    preload_stages: list[str] | None = None
    lazy_load_threshold: int = 3
    metrics_enabled: bool = False

    @classmethod
    def default(cls) -> "WarmupConfig":
        """Return the default warmup configuration.

        Returns:
            A WarmupConfig instance with default settings.
        """
        return cls()

    @classmethod
    def fast(cls) -> "WarmupConfig":
        """Return a fast warmup configuration optimized for low latency.

        Returns:
            A WarmupConfig with fewer async workers, smaller cache, and
            shorter timeouts.
        """
        return cls(
            async_workers=0,
            cache_max_size=50,
            eager_timeout_ms=100,
            async_timeout_ms=1000,
        )

    @classmethod
    def full(cls) -> "WarmupConfig":
        """Return a full warmup configuration optimized for throughput.

        Returns:
            A WarmupConfig with more async workers, larger cache, and
            longer timeouts.
        """
        return cls(
            async_workers=8,
            cache_max_size=500,
            cache_ttl_seconds=7200.0,
            eager_timeout_ms=500,
            async_timeout_ms=10000,
        )

    @classmethod
    def from_env(cls) -> "WarmupConfig":
        """Build a WarmupConfig from the ``WARMUP_MODE`` environment variable.

        Returns:
            WarmupConfig selected by the env var: ``FAST``, ``FULL``,
            ``DISABLED``, or the default when unset/unknown.
        """
        mode = os.environ.get("WARMUP_MODE", "DEFAULT").upper()
        if mode == "FAST":
            return cls.fast()
        elif mode == "FULL":
            return cls.full()
        elif mode == "DISABLED":
            return cls(enabled=False)
        else:
            return cls.default()


@dataclass
class WarmupTask:
    task_id: str
    name: str
    priority: int = 1
    layer: WarmupLayer = WarmupLayer.LAZY
    dependencies: list[str] = field(default_factory=list)
    executor: Callable[[], Any] | None = None
    timeout_ms: int = 5000
    retry_count: int = 1


@dataclass
class WarmupResult:
    task_id: str
    status: WarmupStatus = WarmupStatus.PENDING
    duration_ms: float = 0.0
    error: str | None = None
    cache_hit: bool = False


@dataclass
class WarmupReport:
    total_tasks: int = 0
    completed: int = 0
    failed: int = 0
    cached: int = 0
    total_duration_ms: float = 0.0
    tasks: list[WarmupResult] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    last_accessed: float = field(default_factory=time.time)
    access_count: int = 0
    size_bytes: int = 0
    ttl_seconds: float = 3600.0
    source: str = ""

    @property
    def is_expired(self) -> bool:
        """Return True if the cache entry has exceeded its TTL.

        Returns:
            False when `ttl_seconds` is non-positive (no expiry),
            otherwise True when `age_seconds` exceeds `ttl_seconds`.
        """
        if self.ttl_seconds <= 0:
            return False
        return (time.time() - self.created_at) > self.ttl_seconds

    @property
    def age_seconds(self) -> float:
        """Return the age of this cache entry in seconds since creation."""
        return time.time() - self.created_at


@dataclass
class WarmupMetrics:
    startup_time_ms: float = 0.0
    eager_duration_ms: float = 0.0
    async_duration_ms: float = 0.0
    cache_hit_rate: float = 0.0
    cache_size: int = 0
    memory_usage_mb: float = 0.0
    tasks_completed: int = 0
    tasks_failed: int = 0
    lazy_loads_triggered: int = 0


class WarmupManager:
    _instance: ClassVar[Optional["WarmupManager"]] = None
    _lock: ClassVar[threading.RLock] = threading.RLock()
    _eager_task_ids: ClassVar[set] = set()

    def __init__(self, config: WarmupConfig | None = None):
        self.config = config or WarmupConfig.from_env()
        self._tasks: dict[str, WarmupTask] = {}
        self._results: dict[str, WarmupResult] = {}
        self._cache: dict[str, CacheEntry] = {}
        self._ready_flags: dict[str, threading.Event] = {}
        self._executor: concurrent.futures.ThreadPoolExecutor | None = None
        self._start_time: float = 0.0
        self._is_warming_up: bool = False
        self._shutdown_flag: bool = False
        self._lazy_load_count: int = 0
        self._inner_lock = threading.RLock()
        self._eager_task_ids_local: set = set()

    @classmethod
    def instance(cls, config: WarmupConfig | None = None) -> "WarmupManager":
        """Return the singleton WarmupManager, creating it on first call.

        Args:
            config: Optional WarmupConfig. Used only when the singleton is
                first created; subsequent calls ignore this argument.

        Returns:
            The shared WarmupManager instance with builtin tasks registered.
        """
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls(config=config or WarmupConfig.from_env())
                cls._instance._register_builtin_tasks()
                cls._eager_task_ids = {t.task_id for t in cls._instance._tasks.values() if t.layer == WarmupLayer.EAGER}
            return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Shut down and destroy the singleton instance.

        Calls `shutdown()` on the existing instance (if any) and clears the
        singleton reference so the next `instance()` call creates a fresh one.
        """
        with cls._lock:
            if cls._instance:
                cls._instance.shutdown()
            cls._instance = None
            cls._eager_task_ids = set()

    def _register_builtin_tasks(self):
        self.register_task(
            WarmupTask(
                task_id="core-models",
                name="核心数据模型加载",
                priority=0,
                layer=WarmupLayer.EAGER,
                executor=self._load_core_models,
                timeout_ms=200,
            )
        )
        self.register_task(
            WarmupTask(
                task_id="role-metadata",
                name="角色元数据加载",
                priority=0,
                layer=WarmupLayer.EAGER,
                dependencies=["core-models"],
                executor=self._load_role_metadata,
                timeout_ms=100,
            )
        )

    def _load_core_models(self) -> dict[str, str]:
        return {"models_loaded": True, "timestamp": time.time()}

    def _load_role_metadata(self) -> dict[str, Any]:
        try:
            from prompts.registry import ROLE_METADATA, STAGE_METADATA

            return {
                "roles": list(ROLE_METADATA.keys()),
                "stages": list(STAGE_METADATA.keys()),
                "count": len(ROLE_METADATA),
            }
        except ImportError as e:
            logger.debug("Registry import failed: %s", e)
            return {"roles": [], "stages": [], "count": 0, "error": "registry_import_failed"}

    def register_task(self, task: WarmupTask) -> None:
        """Register a warmup task with the manager.

        Args:
            task: WarmupTask to register. Its `task_id` must be unique.
        """
        with self._inner_lock:
            self._tasks[task.task_id] = task
            self._results[task.task_id] = WarmupResult(task_id=task.task_id)
            if task.layer == WarmupLayer.EAGER:
                self._eager_task_ids_local.add(task.task_id)

    def warmup(self, layers: list[WarmupLayer] | None = None) -> WarmupReport:
        """Run warmup for the specified layers and return a report.

        Args:
            layers: Optional list of WarmupLayer values to run. When None,
                both EAGER and ASYNC layers are executed.

        Returns:
            WarmupReport with task counts, durations, and per-task results.
            Returns an empty report when warmup is disabled via config.
        """
        if not self.config.enabled:
            return WarmupReport(timestamp=datetime.now())
        self._start_time = time.perf_counter()
        if layers is None or WarmupLayer.EAGER in layers:
            self.warmup_eager()
        if layers is None or WarmupLayer.ASYNC in layers:
            self.warmup_async()
        all_results = list(self._results.values())
        total_dur = (time.perf_counter() - self._start_time) * 1000
        completed = sum(1 for r in all_results if r.status == WarmupStatus.SUCCESS)
        failed = sum(1 for r in all_results if r.status in (WarmupStatus.ERROR, WarmupStatus.TIMEOUT))
        cached = sum(1 for r in all_results if r.cache_hit)
        return WarmupReport(
            total_tasks=len(all_results),
            completed=completed,
            failed=failed,
            cached=cached,
            total_duration_ms=total_dur,
            tasks=all_results,
            timestamp=datetime.now(),
        )

    def warmup_eager(self) -> list[WarmupResult]:
        """Synchronously execute all EAGER-layer warmup tasks.

        Tasks are executed in topological order respecting dependencies.
        Results are cached and stored in `_results`.

        Returns:
            List of WarmupResult for each eager task, in execution order.
        """
        eager_tasks = [t for t in self._tasks.values() if t.layer == WarmupLayer.EAGER]
        sorted_tasks = self._topological_sort(eager_tasks)
        results = []
        for task in sorted_tasks:
            start = time.perf_counter()
            try:
                result_val = None if task.executor is None else task.executor()
                duration = (time.perf_counter() - start) * 1000
                entry = CacheEntry(
                    key=task.task_id,
                    value=result_val,
                    created_at=time.time(),
                    last_accessed=time.time(),
                    source=f"eager:{task.name}",
                    ttl_seconds=self.config.cache_ttl_seconds,
                )
                with self._inner_lock:
                    self._cache[task.task_id] = entry
                wr = WarmupResult(
                    task_id=task.task_id,
                    status=WarmupStatus.SUCCESS,
                    duration_ms=duration,
                )
                with self._inner_lock:
                    self._results[task.task_id] = wr
                results.append(wr)
            except Exception as e:
                # Broad catch: warmup task execution; isolates per-task failures
                duration = (time.perf_counter() - start) * 1000
                wr = WarmupResult(
                    task_id=task.task_id,
                    status=WarmupStatus.ERROR,
                    duration_ms=duration,
                    error=str(e),
                )
                with self._inner_lock:
                    self._results[task.task_id] = wr
                results.append(wr)
        return results

    def warmup_async(self) -> None:
        """Execute ASYNC-layer warmup tasks in a background thread pool.

        Returns immediately after submitting tasks; results are populated
        asynchronously. No-op if already warming up, no async workers
        configured, or shutdown has been requested.
        """
        if self._executor is not None or self._is_warming_up:
            return
        if self.config.async_workers <= 0:
            return
        if self._shutdown_flag:
            return
        async_tasks = [t for t in self._tasks.values() if t.layer == WarmupLayer.ASYNC]
        if not async_tasks:
            return
        sorted_tasks = self._topological_sort(async_tasks)
        self._is_warming_up = True
        self._executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=self.config.async_workers,
            thread_name_prefix="warmup",
        )
        futures_map: dict[concurrent.futures.Future, WarmupTask] = {}

        def _run_task(task: WarmupTask):
            start = time.perf_counter()
            try:
                result_val = None if task.executor is None else task.executor()
                duration = (time.perf_counter() - start) * 1000
                entry = CacheEntry(
                    key=task.task_id,
                    value=result_val,
                    created_at=time.time(),
                    last_accessed=time.time(),
                    source=f"async:{task.name}",
                    ttl_seconds=self.config.cache_ttl_seconds,
                )
                with self._inner_lock:
                    self._cache[task.task_id] = entry
                wr = WarmupResult(
                    task_id=task.task_id,
                    status=WarmupStatus.SUCCESS,
                    duration_ms=duration,
                )
                with self._inner_lock:
                    self._results[task.task_id] = wr
                event = self._ready_flags.get(task.task_id)
                if event:
                    event.set()
            except Exception as e:
                # Broad catch: async warmup task execution; isolates per-task failures
                duration = (time.perf_counter() - start) * 1000
                wr = WarmupResult(
                    task_id=task.task_id,
                    status=WarmupStatus.ERROR,
                    duration_ms=duration,
                    error=str(e),
                )
                with self._inner_lock:
                    self._results[task.task_id] = wr
                event = self._ready_flags.get(task.task_id)
                if event:
                    event.set()

        for task in sorted_tasks:
            future = self._executor.submit(_run_task, task)
            futures_map[future] = task

        def _on_done(future: concurrent.futures.Future):
            task = futures_map.pop(future, None)
            if task:
                with contextlib.suppress(concurrent.futures.TimeoutError, Exception):
                    future.result(timeout=task.timeout_ms / 1000.0)

        for future in list(futures_map.keys()):
            future.add_done_callback(_on_done)

        def _wait_all():
            for f in list(futures_map.keys()):
                try:
                    f.result(timeout=max(t.timeout_ms for t in sorted_tasks) / 1000.0)
                except Exception as e:
                    # Broad catch: future result from thread pool; per-task isolation
                    logger.debug("Warmup task failed: %s", e)
            self._is_warming_up = False

        wait_thread = threading.Thread(target=_wait_all, daemon=True, name="warmup-waiter")
        wait_thread.start()

    def get(self, key: str, default: Any = None) -> Any:
        """Retrieve a cached value by key.

        Args:
            key: Cache key to look up.
            default: Value to return on miss or expiry.

        Returns:
            The cached value, or ``default`` when missing or expired.
        """
        if not self.config.cache_enabled:
            return default
        entry = self._cache.get(key)
        if entry is None:
            return default
        if entry.is_expired:
            del self._cache[key]
            return default
        entry.last_accessed = time.time()
        entry.access_count += 1
        return entry.value

    def get_or_load(self, key: str, loader: Callable[[], Any], _layer: WarmupLayer = WarmupLayer.LAZY) -> Any:
        """Return a cached value, loading it via ``loader`` on miss.

        Args:
            key: Cache key to look up or populate.
            loader: Callable that produces the value when the cache misses.
            _layer: Warmup layer tag for the lazy load (currently unused).

        Returns:
            The cached or freshly loaded value.
        """
        value = self.get(key)
        if value is not None:
            return value
        self._lazy_load_count += 1
        if key not in self._ready_flags:
            with self._inner_lock:
                if key not in self._ready_flags:
                    self._ready_flags[key] = threading.Event()
        event = self._ready_flags[key]
        if not event.is_set():
            with self._inner_lock:
                if not event.is_set():
                    try:
                        result = loader()
                        self._cache[key] = CacheEntry(
                            key=key,
                            value=result,
                            created_at=time.time(),
                            last_accessed=time.time(),
                            source=f"lazy:{key}",
                            ttl_seconds=self.config.cache_ttl_seconds,
                        )
                    finally:
                        event.set()
        event.wait(timeout=30)
        return self.get(key, default=None)

    def set_cache(self, key: str, value: Any, source: str = "", ttl: float | None = None) -> None:
        """Manually store a value in the cache.

        Args:
            key: Cache key to set.
            value: Value to store.
            source: Optional source label for the entry.
            ttl: Optional TTL in seconds overriding the config default.
        """
        if not self.config.cache_enabled:
            return
        entry = CacheEntry(
            key=key,
            value=value,
            created_at=time.time(),
            last_accessed=time.time(),
            source=source or f"manual:{key}",
            ttl_seconds=ttl if ttl is not None else self.config.cache_ttl_seconds,
        )
        with self._inner_lock:
            self._cache[key] = entry
            self._evict_if_needed()

    def is_ready(self, task_id: str) -> bool:
        """Check whether a warmup task completed successfully.

        Args:
            task_id: Identifier of the task to check.

        Returns:
            True when the task result status is SUCCESS, False otherwise.
        """
        result = self._results.get(task_id)
        if result is None:
            return False
        return result.status == WarmupStatus.SUCCESS

    def is_fully_warmed(self) -> bool:
        """Check whether all registered tasks have finished warming up.

        Returns:
            True when no task is pending and no async warmup is in progress.
        """
        if not self._tasks:
            return True
        for result in self._results.values():
            if result.status in (WarmupStatus.PENDING,):
                return False
        return not self._is_warming_up

    def get_report(self) -> WarmupReport:
        """Build a WarmupReport from current task results.

        Returns:
            WarmupReport with totals, completed/failed/cached counts,
            duration, and per-task results.
        """
        all_results = list(self._results.values())
        completed = sum(1 for r in all_results if r.status == WarmupStatus.SUCCESS)
        failed = sum(1 for r in all_results if r.status in (WarmupStatus.ERROR, WarmupStatus.TIMEOUT))
        cached = sum(1 for r in all_results if r.cache_hit)
        return WarmupReport(
            total_tasks=len(all_results),
            completed=completed,
            failed=failed,
            cached=cached,
            total_duration_ms=(time.perf_counter() - self._start_time) * 1000 if self._start_time else 0,
            tasks=all_results,
            timestamp=datetime.now(),
        )

    def get_metrics(self) -> WarmupMetrics:
        """Collect detailed warmup and cache metrics.

        Returns:
            WarmupMetrics with startup time, eager/async durations, cache
            hit rate, cache size, memory estimate, and task counts. When
            metrics are disabled an empty WarmupMetrics is returned.
        """
        if not self.config.metrics_enabled:
            return WarmupMetrics()
        total_hits = sum(e.access_count for e in self._cache.values())
        total_entries = len(self._cache)
        hit_rate = total_hits / max(total_hits + max(total_entries, 1), 1)
        eager_dur = sum(
            r.duration_ms
            for tid, r in self._results.items()
            if tid in self._eager_task_ids and r.status == WarmupStatus.SUCCESS
        )
        async_dur = sum(
            r.duration_ms
            for tid, r in self._results.items()
            if tid not in self._eager_task_ids and r.status == WarmupStatus.SUCCESS
        )
        completed = sum(1 for r in self._results.values() if r.status == WarmupStatus.SUCCESS)
        failed = sum(1 for r in self._results.values() if r.status in (WarmupStatus.ERROR, WarmupStatus.TIMEOUT))
        return WarmupMetrics(
            startup_time_ms=(time.perf_counter() - self._start_time) * 1000 if self._start_time else 0,
            eager_duration_ms=eager_dur,
            async_duration_ms=async_dur,
            cache_hit_rate=hit_rate,
            cache_size=len(self._cache),
            memory_usage_mb=self._estimate_memory(),
            tasks_completed=completed,
            tasks_failed=failed,
            lazy_loads_triggered=self._lazy_load_count,
        )

    def print_diagnostics(self) -> str:
        """Return a human-readable diagnostics report as a multi-line string.

        Includes startup timing, eager/async durations, cache hit rate,
        memory usage, task completion counts, and per-task status lines.
        """
        m = self.get_metrics()
        lines = [
            "=== WarmupManager Diagnostics ===",
            f"Startup: {m.startup_time_ms:.1f}ms",
            f"Eager: {m.eager_duration_ms:.1f}ms | Async: {m.async_duration_ms:.1f}ms",
            f"Cache: {m.cache_size} entries | Hit Rate: {m.cache_hit_rate:.1%}",
            f"Memory: {m.memory_usage_mb:.1f}MB",
            f"Tasks: {m.tasks_completed}/{m.tasks_completed + m.tasks_failed}",
            f"Lazy loads triggered: {m.lazy_loads_triggered}",
            "--- Task Details ---",
        ]
        status_icon = {
            WarmupStatus.SUCCESS: "\u2705",
            WarmupStatus.ERROR: "\u274c",
            WarmupStatus.TIMEOUT: "\u23f3",
            WarmupStatus.PENDING: "\u23f3",
            WarmupStatus.SKIPPED: "\u23ef",
        }
        for rid in sorted(self._results.keys()):
            r = self._results[rid]
            icon = status_icon.get(r.status, "?")
            lines.append(f"  {icon} {rid}: {r.duration_ms:.1f}ms")
            if r.error:
                lines.append(f"      error: {r.error[:80]}")
        return "\n".join(lines)

    def benchmark(self, iterations: int = 5) -> dict[str, Any]:
        """Run warmup repeatedly and return timing statistics.

        Args:
            iterations: Number of warmup cycles to run. Each cycle
                invalidates the cache and re-runs warmup.

        Returns:
            Dict with mean_ms, min_ms, max_ms, p50_ms, p95_ms, and
            iterations keys.
        """
        times = []
        for _ in range(iterations):
            self.invalidate_all()
            with self._inner_lock:
                for tid in self._results:
                    self._results[tid] = WarmupResult(task_id=tid)
            self._start_time = time.perf_counter()
            self.warmup()
            max_wait = self.config.async_timeout_ms / 1000.0 + 1.0
            deadline = time.monotonic() + max_wait
            while not self.is_fully_warmed() and time.monotonic() < deadline:
                time.sleep(0.01)
            elapsed = (time.perf_counter() - self._start_time) * 1000
            times.append(elapsed)
        if not times:
            return {"mean_ms": 0, "min_ms": 0, "max_ms": 0, "p50_ms": 0, "p95_ms": 0, "iterations": 0}
        sorted_times = sorted(times)
        p50_idx = int(len(sorted_times) * 0.5)
        p95_idx = min(int(len(sorted_times) * 0.95), len(sorted_times) - 1)
        return {
            "mean_ms": statistics.mean(times),
            "min_ms": min(times),
            "max_ms": max(times),
            "p50_ms": sorted_times[p50_idx],
            "p95_ms": sorted_times[p95_idx],
            "iterations": iterations,
        }

    def invalidate(self, key: str) -> None:
        """Remove a single entry from the cache.

        Args:
            key: Cache key to invalidate.
        """
        with self._inner_lock:
            self._cache.pop(key, None)

    def invalidate_all(self) -> None:
        """Clear all entries from the cache."""
        with self._inner_lock:
            self._cache.clear()

    def shutdown(self) -> None:
        """Shut down the async executor and clear the cache."""
        self._shutdown_flag = True
        self._is_warming_up = False
        if self._executor is not None:
            self._executor.shutdown(wait=False, cancel_futures=True)
            self._executor = None
        with self._inner_lock:
            self._cache.clear()

    def _topological_sort(self, tasks: list[WarmupTask]) -> list[WarmupTask]:
        if not tasks:
            return []
        task_map = {t.task_id: t for t in tasks}
        in_degree = {t.task_id: 0 for t in tasks}
        adj: dict[str, list[str]] = {t.task_id: [] for t in tasks}
        for task in tasks:
            for dep in task.dependencies:
                if dep in in_degree:
                    adj.setdefault(dep, []).append(task.task_id)
                    in_degree[task.task_id] += 1
        queue = deque(tid for tid, deg in in_degree.items() if deg == 0)
        result = []
        while queue:
            tid = queue.popleft()
            if tid in task_map:
                result.append(task_map[tid])
            for neighbor in adj.get(tid, []):
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        if len(result) != len(tasks):
            remaining = [t.name for t in tasks if t not in result]
            raise ValueError(f"Circular dependency detected: {remaining}")
        return result

    def _evict_if_needed(self) -> None:
        if not self.config.cache_enabled or self.config.cache_max_size <= 0:
            return
        time.time()
        expired = [k for k, v in self._cache.items() if v.is_expired]
        for k in expired:
            self._cache.pop(k, None)
        if len(self._cache) > self.config.cache_max_size:
            sorted_by_lru = sorted(self._cache.items(), key=lambda x: x[1].last_accessed)
            excess = len(self._cache) - self.config.cache_max_size
            for k, _ in sorted_by_lru[:excess]:
                self._cache.pop(k, None)

    @staticmethod
    def _estimate_memory() -> float:
        import tracemalloc

        if not tracemalloc.is_tracing():
            return 0.0
        current, peak = tracemalloc.get_traced_memory()
        return current / (1024 * 1024)
