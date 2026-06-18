#!/usr/bin/env python3
"""Benchmark: sync dispatch vs async dispatch throughput.

Usage:
    python scripts/benchmark_async_dispatch.py [--tasks 10] [--warmup 2]

Measures:
- Total time for N tasks with sync dispatch
- Total time for N tasks with async dispatch
- Throughput (tasks/second) for each
- Speedup ratio
"""

import argparse
import asyncio
import os
import sys
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collaboration.dispatcher import MultiAgentDispatcher


def run_sync_benchmark(dispatcher, task_descriptions):
    """Run N tasks sequentially with sync dispatch."""
    start = time.time()
    results = []
    for desc in task_descriptions:
        result = dispatcher.dispatch(desc, mode="auto")
        results.append(result)
    elapsed = time.time() - start
    return elapsed, results


async def run_async_benchmark(dispatcher, task_descriptions):
    """Run N tasks with async dispatch."""
    start = time.time()
    results = []
    for desc in task_descriptions:
        result = await dispatcher.async_dispatch(desc, mode="auto")
        results.append(result)
    elapsed = time.time() - start
    return elapsed, results


def main():
    """Run the sync-vs-async dispatch benchmark and print results.

    Parses ``--tasks`` and ``--warmup`` CLI arguments, creates a
    MultiAgentDispatcher with mock backend, and prints timing comparisons.
    """
    parser = argparse.ArgumentParser(description="Benchmark sync vs async dispatch")
    parser.add_argument("--tasks", type=int, default=10, help="Number of tasks to dispatch")
    parser.add_argument("--warmup", type=int, default=2, help="Warmup iterations")
    args = parser.parse_args()

    # Create dispatcher with mock backend (llm_backend=None = MockBackend)
    dispatcher = MultiAgentDispatcher(
        persist_dir=None,
        enable_warmup=False,
        enable_compression=False,
        enable_permission=False,
        enable_memory=False,
        enable_skillify=False,
        enable_anchor_check=False,
        enable_retrospective=False,
        enable_usage_tracker=False,
        enable_feedback_loop=False,
        enable_redis_cache=False,
    )

    task_descriptions = [
        f"Benchmark task {i}: Analyze the requirements for a microservice architecture"
        for i in range(args.tasks)
    ]

    # Warmup
    print(f"Warming up with {args.warmup} iterations...")
    for _ in range(args.warmup):
        dispatcher.dispatch("Warmup task: simple analysis", mode="auto")

    # Sync benchmark
    print(f"\nRunning sync dispatch benchmark ({args.tasks} tasks)...")
    sync_time, sync_results = run_sync_benchmark(dispatcher, task_descriptions)
    sync_throughput = args.tasks / sync_time if sync_time > 0 else 0
    sync_success = sum(1 for r in sync_results if r.success)

    # Async benchmark
    print(f"Running async dispatch benchmark ({args.tasks} tasks)...")
    async_time, async_results = asyncio.run(run_async_benchmark(dispatcher, task_descriptions))
    async_throughput = args.tasks / async_time if async_time > 0 else 0
    async_success = sum(1 for r in async_results if r.success)

    # Results
    speedup = sync_time / async_time if async_time > 0 else float('inf')

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS")
    print("=" * 60)
    print(f"{'Metric':<30} {'Sync':>12} {'Async':>12}")
    print("-" * 60)
    print(f"{'Total time (s)':<30} {sync_time:>12.3f} {async_time:>12.3f}")
    print(f"{'Throughput (tasks/s)':<30} {sync_throughput:>12.2f} {async_throughput:>12.2f}")
    print(f"{'Success rate':<30} {sync_success}/{args.tasks:>10} {async_success}/{args.tasks:>9}")
    print(f"{'Avg time per task (s)':<30} {sync_time/args.tasks:>12.4f} {async_time/args.tasks:>12.4f}")
    print("-" * 60)
    print(f"{'Speedup ratio':<30} {speedup:>12.2f}x")
    print("=" * 60)

    if speedup > 1.0:
        print(f"\n✓ Async dispatch is {speedup:.2f}x faster than sync dispatch")
    else:
        print(f"\n✗ Async dispatch is {1/speedup:.2f}x slower than sync dispatch")
        print("  Note: With mock backend, async overhead may outweigh benefits.")
        print("  Real LLM backends with network I/O should show improvement.")

    dispatcher.shutdown()


if __name__ == "__main__":
    main()
