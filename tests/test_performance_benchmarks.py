#!/usr/bin/env python3
"""Performance benchmark tests for DevSquad.

Tests covering:
1. Concurrent dispatch stability
2. Large task handling
3. Worker index O(1) lookup performance
4. Thread pool reuse across calls
5. Memory usage under load
6. Dispatcher creation speed
"""

import concurrent.futures
import os
import sys
import tempfile
import time
import tracemalloc
import unittest

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.coordinator import Coordinator
from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.scratchpad import Scratchpad


@pytest.mark.benchmark
class TestPerformanceBenchmarks(unittest.TestCase):
    """Performance benchmark tests for DevSquad core components."""

    def _create_dispatcher(self, **overrides):
        """Create a lightweight dispatcher for benchmarking."""
        tmpdir = tempfile.mkdtemp(prefix="bench_")
        defaults = {
            "persist_dir": tmpdir,
            "enable_memory": False,
            "enable_warmup": False,
            "enable_compression": False,
            "enable_permission": False,
            "enable_skillify": False,
            "enable_quality_guard": False,
            "enable_anchor_check": False,
            "enable_retrospective": False,
            "enable_usage_tracker": False,
            "enable_feedback_loop": False,
            "enable_redis_cache": False,
            "enable_execution_guard": False,
            "llm_backend": None,
        }
        defaults.update(overrides)
        return MultiAgentDispatcher(**defaults)

    def _create_coordinator(self):
        """Create a lightweight coordinator for benchmarking."""
        tmpdir = tempfile.mkdtemp(prefix="bench_coord_")
        scratchpad = Scratchpad(persist_dir=tmpdir)
        return Coordinator(
            scratchpad=scratchpad,
            persist_dir=tmpdir,
            enable_compression=False,
            llm_backend=None,
        )

    def _make_plan(self, coord, task_description, role_ids):
        """Build an ExecutionPlan for the given roles."""
        available_roles = [{"role_id": rid, "role_prompt": f"Prompt for {rid}"} for rid in role_ids]
        return coord.plan_task(task_description, available_roles)

    # ------------------------------------------------------------------
    # 1. Concurrent Dispatch Stability
    # ------------------------------------------------------------------
    def test_concurrent_dispatch_stability(self):
        """Verify dispatcher handles 5 concurrent tasks without errors."""
        disp = self._create_dispatcher()
        tasks = [f"Analyze task {i}" for i in range(5)]

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(disp.dispatch, task) for task in tasks]
            results = [f.result(timeout=120) for f in futures]

        for r in results:
            assert isinstance(r, DispatchResult)
            assert r.success is True

    # ------------------------------------------------------------------
    # 2. Large Task Handling
    # ------------------------------------------------------------------
    def test_large_task_handling(self):
        """Verify dispatcher handles a large task description (under MAX_TASK_LENGTH)."""
        disp = self._create_dispatcher()
        # InputValidator MAX_TASK_LENGTH = 10000; stay just under the limit
        large_task = "Analyze this project: " + "x" * 9000
        result = disp.dispatch(large_task)
        assert isinstance(result, DispatchResult)

    # ------------------------------------------------------------------
    # 3. Worker Index Performance (O(1) dict lookup)
    # ------------------------------------------------------------------
    def test_worker_index_performance(self):
        """Verify coordinator worker lookup is O(1) via dict index."""
        coord = self._create_coordinator()
        role_ids = ["architect", "pm", "security", "tester", "coder", "devops", "ui"]
        plan = self._make_plan(coord, "Benchmark task", role_ids)
        coord.spawn_workers(plan)

        # Warm up
        for role_id in role_ids:
            coord._worker_index.get(role_id)

        # Time 1000 lookups per role (7000 total)
        start = time.perf_counter()
        for _ in range(1000):
            for role_id in role_ids:
                coord._worker_index.get(role_id)
        elapsed = time.perf_counter() - start
        assert elapsed < 0.1, f"Worker lookup too slow: {elapsed:.3f}s for 7000 lookups"

    # ------------------------------------------------------------------
    # 4. Thread Pool Reuse
    # ------------------------------------------------------------------
    def test_thread_pool_reuse(self):
        """Verify coordinator reuses ThreadPoolExecutor across calls."""
        coord = self._create_coordinator()
        role_ids = ["architect", "pm"]
        plan = self._make_plan(coord, "Reuse test task", role_ids)
        coord.spawn_workers(plan)
        executor_id_before = id(coord._executor)
        coord.execute_plan(plan)
        executor_id_after = id(coord._executor)
        assert executor_id_before == executor_id_after, "Thread pool not reused"

    # ------------------------------------------------------------------
    # 5. Memory Usage Under Load
    # ------------------------------------------------------------------
    def test_memory_usage_under_load(self):
        """Verify memory doesn't grow unboundedly over 10 dispatches."""
        disp = self._create_dispatcher()
        tracemalloc.start()
        # Reset peak after dispatcher creation overhead
        tracemalloc.reset_peak()

        for i in range(10):
            disp.dispatch(f"Quick analysis task {i}")

        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        # Peak should be under 50MB for 10 dispatches
        assert peak < 50 * 1024 * 1024, f"Memory peak too high: {peak / 1024 / 1024:.1f}MB"

    # ------------------------------------------------------------------
    # 6. Dispatcher Creation Speed
    # ------------------------------------------------------------------
    def test_dispatcher_creation_speed(self):
        """Dispatcher should initialize in under 2 seconds."""
        start = time.perf_counter()
        self._create_dispatcher()
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"Dispatcher creation too slow: {elapsed:.3f}s"


if __name__ == "__main__":
    unittest.main()
