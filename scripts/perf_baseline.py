#!/usr/bin/env python3
"""V4.6.0-dev perf baseline re-measurement.

Refreshes three perf numbers for the backlog item "perf baseline stale 14
iterations": dispatcher creation time, simple-dispatch throughput, and
peak memory over 10 dispatches. Output is appended to docs/perf/baseline
.md as a comparison point. Run on demand, not in CI (CI may be slower).
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def _make_dispatcher(prefix: str) -> MultiAgentDispatcher:  # noqa: F821
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    return MultiAgentDispatcher(
        persist_dir=tempfile.mkdtemp(prefix=prefix),
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


def main() -> None:
    # 1. Dispatcher creation: 5 samples, report median + max.
    create_times: list[float] = []
    for i in range(5):
        s = time.perf_counter()
        _make_dispatcher(f"perf_create_{i}_")
        create_times.append(time.perf_counter() - s)
    create_median_ms = sorted(create_times)[2] * 1000
    create_max_ms = max(create_times) * 1000

    # 2. Dispatch throughput: 10 tasks, measure total + per-task.
    disp = _make_dispatcher("perf_throughput_")
    tracemalloc.start()
    tracemalloc.reset_peak()
    s = time.perf_counter()
    for i in range(10):
        disp.dispatch(f"Quick benchmark task {i}")
    elapsed = time.perf_counter() - s
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    payload = {
        "version": "4.6.0-dev",
        "dispatcher_creation_ms": {
            "median": round(create_median_ms, 1),
            "max": round(create_max_ms, 1),
        },
        "dispatch_10_tasks": {
            "total_ms": round(elapsed * 1000, 1),
            "per_task_ms": round((elapsed / 10) * 1000, 1),
            "throughput_per_sec": round(10 / elapsed, 2) if elapsed > 0 else None,
        },
        "memory_peak_mb": round(peak / (1024 * 1024), 2),
    }
    out_dir = Path("docs/perf")
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / "v460_baseline.json"
    out_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"baseline written to {out_path}")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
