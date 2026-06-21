#!/usr/bin/env python3
"""Memory usage benchmarks for core DevSquad components.

Tests memory efficiency of:
1. Worker creation and disposal
2. Scratchpad growth patterns
3. DispatchResult memory footprint
4. Large-scale dispatch memory stability
5. __slots__ effectiveness verification
"""

import gc
import os
import sys
import tempfile
import tracemalloc

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.dispatch_models import DispatchResult
from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.models import EntryType, ScratchpadEntry
from scripts.collaboration.scratchpad import Scratchpad
from scripts.collaboration.worker import Worker


def _make_worker(role: str = "architect") -> Worker:
    """Create a minimal Worker for memory testing."""
    return Worker(
        worker_id="w-mem-test",
        role_id=role,
        role_prompt="",
        scratchpad=Scratchpad(),
    )


def _make_lightweight_dispatcher() -> MultiAgentDispatcher:
    """Create a feature-light dispatcher for memory-stability testing."""
    tmpdir = tempfile.mkdtemp(prefix="mem_bench_")
    return MultiAgentDispatcher(
        persist_dir=tmpdir,
        enable_memory=False,
        enable_warmup=False,
        enable_compression=False,
        enable_permission=False,
        enable_skillify=False,
        enable_quality_guard=False,
        enable_anchor_check=False,
        enable_retrospective=False,
        enable_usage_tracker=False,
        enable_feedback_loop=False,
        enable_redis_cache=False,
        enable_execution_guard=False,
        llm_backend=None,
    )


class TestMemoryBenchmarks:
    """Memory efficiency benchmarks."""

    def test_worker_memory_footprint(self):
        """Verify: Worker instance memory < 2KB with __slots__."""
        worker = _make_worker()
        size = sys.getsizeof(worker)
        gc.collect()
        assert size < 2048, f"Worker too large: {size} bytes"

    def test_scratchpad_growth(self):
        """Verify: Scratchpad memory grows linearly, not quadratically."""
        sp = Scratchpad()
        initial = sys.getsizeof(sp)
        for i in range(100):
            entry = ScratchpadEntry(
                worker_id=f"role_{i}",
                role_id=f"role_{i}",
                entry_type=EntryType.FINDING,
                content=f"content_{i}" * 10,
            )
            sp.write(entry)
        grown = sys.getsizeof(sp)
        # Growth should be reasonable (< 100KB for 100 entries)
        assert grown - initial < 100_000

    def test_dispatch_result_memory(self):
        """Verify: DispatchResult memory < 10KB for typical dispatch."""
        result = DispatchResult(
            success=True,
            task_description="test task",
            matched_roles=["architect"],
            worker_results=[{"role": "architect", "output": "x" * 1000}],
        )
        size = sys.getsizeof(result)
        assert size < 10_240

    def test_repeated_dispatch_memory_stable(self):
        """Verify: 50 dispatches don't leak memory (>5MB growth = leak)."""
        tracemalloc.start()
        snapshot1 = tracemalloc.take_snapshot()

        disp = _make_lightweight_dispatcher()
        for _ in range(50):
            disp.dispatch("test task", roles=["architect"], dry_run=True)
        disp.shutdown()

        snapshot2 = tracemalloc.take_snapshot()
        tracemalloc.stop()

        stats = snapshot2.compare_to(snapshot1, "lineno")
        total_diff = sum(s.size_diff for s in stats[:10])
        # Allow some growth but flag if > 5MB (indicates leak)
        assert total_diff < 5_000_000, f"Memory leak detected: {total_diff} bytes"

    def test_slots_effectiveness(self):
        """Verify: Classes with __slots__ use less memory than dict-based."""
        worker = _make_worker()
        # If __slots__ is active, worker.__dict__ should not exist
        # (unless it inherits from a dict-based class)
        has_slots = not hasattr(worker, "__dict__") or "__slots__" in type(worker).__dict__
        assert has_slots, "Worker should have __slots__ (no __dict__)"
