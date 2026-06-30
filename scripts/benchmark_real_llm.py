#!/usr/bin/env python3
"""Benchmark: real LLM backend dispatch performance.

Usage:
    DEVSQUAD_OPENAI_API_KEY=sk-... python scripts/benchmark_real_llm.py --backend openai --tasks 5
    DEVSQUAD_ANTHROPIC_API_KEY=sk-... python scripts/benchmark_real_llm.py --backend anthropic --tasks 5

Measures:
- Per-task latency
- Throughput (tasks/second)
- Success rate
- Token usage (if available)
"""

import argparse
import os
import sys
import time
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def create_backend(backend_type: str) -> Any:
    """Create an LLM backend instance for the given type.

    Args:
        backend_type: One of ``"openai"`` or ``"anthropic"``. The
            corresponding API key must be set in the environment.

    Returns:
        Configured LLM backend instance with max_tokens=500.

    Raises:
        SystemExit: When the backend type is unknown or the required API
            key environment variable is not set.
    """
    if backend_type == "openai":
        from scripts.collaboration.llm_backend import OpenAIBackend

        api_key = os.environ.get("DEVSQUAD_OPENAI_API_KEY")
        if not api_key:
            print("Error: DEVSQUAD_OPENAI_API_KEY not set")
            sys.exit(1)
        return OpenAIBackend(api_key=api_key, max_tokens=500)
    elif backend_type == "anthropic":
        from scripts.collaboration.llm_backend import AnthropicBackend

        api_key = os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
        if not api_key:
            print("Error: DEVSQUAD_ANTHROPIC_API_KEY not set")
            sys.exit(1)
        return AnthropicBackend(api_key=api_key, max_tokens=500)
    else:
        print(f"Error: Unknown backend '{backend_type}'. Use 'openai' or 'anthropic'")
        sys.exit(1)


def run_benchmark(backend_type: str, num_tasks: int, mode: str) -> None:
    """Run a real-LLM dispatch benchmark and print latency/throughput stats.

    Args:
        backend_type: LLM backend identifier (``"openai"`` or
            ``"anthropic"``).
        num_tasks: Number of benchmark tasks to dispatch.
        mode: Dispatch mode (``"auto"``, ``"parallel"``,
            ``"sequential"``, or ``"consensus"``).
    """
    from scripts.collaboration.dispatcher import MultiAgentDispatcher

    backend = create_backend(backend_type)
    dispatcher = MultiAgentDispatcher(
        llm_backend=backend,
        enable_warmup=False,
        enable_compression=False,
        enable_permission=False,
        enable_memory=False,
        enable_skillify=False,
        enable_anchor_check=False,
        enable_retrospective=False,
        enable_usage_tracker=False,
        enable_rbac=False,
        enable_audit=False,
        enable_data_masking=False,
        enable_multi_tenant=False,
    )

    tasks = [
        f"Analyze the trade-offs between monolith and microservices for a {['e-commerce', 'healthcare', 'fintech', 'education', 'gaming'][i % 5]} platform"
        for i in range(num_tasks)
    ]

    print(f"\n{'='*60}")
    print(f"Real LLM Benchmark: {backend_type.upper()} backend")
    print(f"Tasks: {num_tasks}, Mode: {mode}")
    print(f"{'='*60}")

    latencies = []
    successes = 0

    for i, task in enumerate(tasks):
        start = time.time()
        try:
            result = dispatcher.dispatch(task, mode=mode)
            elapsed = time.time() - start
            latencies.append(elapsed)
            if result.success:
                successes += 1
            status = "OK" if result.success else "FAIL"
        except (RuntimeError, ValueError, ConnectionError, TimeoutError) as e:
            elapsed = time.time() - start
            latencies.append(elapsed)
            status = f"ERROR: {e}"

        print(f"  Task {i+1}/{num_tasks}: {elapsed:.2f}s [{status}]")

    total_time = sum(latencies)
    avg_latency = total_time / len(latencies) if latencies else 0
    throughput = num_tasks / total_time if total_time > 0 else 0

    print(f"\n{'='*60}")
    print("RESULTS")
    print(f"{'='*60}")
    print(f"  Total time:       {total_time:.2f}s")
    print(f"  Avg latency:      {avg_latency:.2f}s")
    print(f"  Min latency:      {min(latencies):.2f}s")
    print(f"  Max latency:      {max(latencies):.2f}s")
    print(f"  Throughput:       {throughput:.2f} tasks/s")
    print(f"  Success rate:     {successes}/{num_tasks} ({100*successes/num_tasks:.0f}%)")
    print(f"{'='*60}")

    dispatcher.shutdown()


def main() -> None:
    """Parse CLI arguments and launch the real-LLM benchmark.

    Required argument: ``--backend`` (openai or anthropic). Optional
    arguments: ``--tasks`` (default 5) and ``--mode`` (default auto).
    """
    parser = argparse.ArgumentParser(description="Benchmark real LLM backend dispatch")
    parser.add_argument("--backend", choices=["openai", "anthropic"], required=True)
    parser.add_argument("--tasks", type=int, default=5)
    parser.add_argument("--mode", default="auto", choices=["auto", "parallel", "sequential", "consensus"])
    args = parser.parse_args()

    run_benchmark(args.backend, args.tasks, args.mode)


if __name__ == "__main__":
    main()
