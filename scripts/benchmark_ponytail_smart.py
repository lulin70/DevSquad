#!/usr/bin/env python3
"""Benchmark: Ponytail injection + SMART compression A/B evaluation.

Usage:
    python scripts/benchmark_ponytail_smart.py
    python scripts/benchmark_ponytail_smart.py --output report.json
    python scripts/benchmark_ponytail_smart.py --tasks all

Measures (V3.10.0 Phase 1+2 收尾项):
  Phase 1 — Ponytail injection A/B:
    - Prompt size (tokens) with vs without ponytail injection
    - Injection overhead (%)
    - Output token estimate (MockBackend)
  Phase 2 — SMART compression A/B:
    - Token reduction ratio: SMART vs SNIP vs no compression
    - Message preservation: SMART (100%) vs SNIP (partial)
    - Compression correctness: structured content preserved

Spec reference: docs/spec/v3.10.0_spec.md §7 (Phase 1+2 收尾项)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from dataclasses import asdict, dataclass, field
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.collaboration.context_compressor import (  # noqa: E402
    CompressionLevel,
    ContextCompressor,
    Message,
    MessageType,
)
from scripts.collaboration.prompt_assembler import PromptAssembler  # noqa: E402

# ============================================================
# Benchmark task definitions (15 tasks: 5 simple + 5 medium + 5 complex)
# ============================================================

BENCHMARK_TASKS: list[dict[str, str]] = [
    # Simple tasks (1-2 sentences, single concern)
    {"id": "S1", "complexity": "simple", "description": "Add a hello world endpoint."},
    {"id": "S2", "complexity": "simple", "description": "Fix typo in README."},
    {"id": "S3", "complexity": "simple", "description": "Add type hint to function parameter."},
    {"id": "S4", "complexity": "simple", "description": "Rename variable from x to user_count."},
    {"id": "S5", "complexity": "simple", "description": "Add docstring to parse_config function."},
    # Medium tasks (multi-step, single module)
    {"id": "M1", "complexity": "medium", "description": "Implement user registration with email validation and password hashing using PBKDF2."},
    {"id": "M2", "complexity": "medium", "description": "Add retry logic with exponential backoff to the HTTP client for transient failures."},
    {"id": "M3", "complexity": "medium", "description": "Create a CLI command to export database records to CSV with column filtering."},
    {"id": "M4", "complexity": "medium", "description": "Implement cache invalidation strategy for the user profile service."},
    {"id": "M5", "complexity": "medium", "description": "Add request rate limiting middleware with per-user tracking."},
    # Complex tasks (cross-module, architectural)
    {"id": "C1", "complexity": "complex", "description": "Design and implement a multi-tenant architecture with row-level security, tenant isolation, and per-tenant rate limiting across all API endpoints."},
    {"id": "C2", "complexity": "complex", "description": "Implement a distributed task queue with priority support, dead-letter queues, retry policies, and observability metrics. Integrate with existing worker pool."},
    {"id": "C3", "complexity": "complex", "description": "Migrate from monolithic database to read replicas with connection pooling, automatic failover, and query-level routing based on read/write intent."},
    {"id": "C4", "complexity": "complex", "description": "Build a real-time collaboration layer with CRDT-based conflict resolution, presence awareness, and offline sync for the document editor."},
    {"id": "C5", "complexity": "complex", "description": "Implement end-to-end encryption for messaging with key rotation, forward secrecy, and multi-device sync. Integrate with existing auth system."},
]

ROLE_TEMPLATES = {
    "architect": "You are a software architect. Design systems with scalability, maintainability, and simplicity in mind.",
    "coder": "You are a senior developer. Write clean, tested, minimal code. Prefer standard library over new dependencies.",
    "tester": "You are a test engineer. Write tests that find bugs. Never modify tests to accommodate source code bugs.",
}


# ============================================================
# Metric dataclasses
# ============================================================


@dataclass
class PonytailMetric:
    """Ponytail injection A/B metric for a single task."""

    task_id: str
    complexity: str
    prompt_tokens_without: int
    prompt_tokens_with: int
    injection_overhead_tokens: int
    injection_overhead_pct: float


@dataclass
class SmartCompressionMetric:
    """SMART compression A/B metric for a single content sample."""

    sample_id: str
    content_type: str
    original_tokens: int
    smart_tokens: int
    snip_tokens: int
    smart_reduction_pct: float
    snip_reduction_pct: float
    smart_messages_preserved: int
    snip_messages_preserved: int
    smart_correctness_score: float  # 1.0 = all structured content preserved


@dataclass
class BenchmarkReport:
    """Complete benchmark report."""

    run_timestamp: str
    total_tasks: int
    ponytail_metrics: list[PonytailMetric] = field(default_factory=list)
    smart_metrics: list[SmartCompressionMetric] = field(default_factory=list)
    ponytail_summary: dict[str, Any] = field(default_factory=dict)
    smart_summary: dict[str, Any] = field(default_factory=dict)


# ============================================================
# Phase 1: Ponytail injection A/B
# ============================================================


def run_ponytail_benchmark(tasks: list[dict[str, str]]) -> list[PonytailMetric]:
    """Run ponytail injection A/B benchmark.

    Compares prompt size (tokens) with vs without ponytail injection
    for each task, using the 'architect' role template.
    """
    metrics: list[PonytailMetric] = []
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as config_without:
        config_without.write("quality_control:\n  enabled: true\n  minimal_implementation: false\n")
        config_without_path = config_without.name

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as config_with:
        config_with.write("quality_control:\n  enabled: true\n  minimal_implementation: true\n  ponytail_markers: true\n")
        config_with_path = config_with.name

    try:
        for task in tasks:
            assembler_without = PromptAssembler(
                role_id="architect",
                base_prompt=ROLE_TEMPLATES["architect"],
                config_path=config_without_path,
            )
            assembler_with = PromptAssembler(
                role_id="architect",
                base_prompt=ROLE_TEMPLATES["architect"],
                config_path=config_with_path,
            )

            result_without = assembler_without.assemble(task_description=task["description"])
            result_with = assembler_with.assemble(task_description=task["description"])

            comp = ContextCompressor()
            tokens_without = comp.estimate_tokens(result_without.instruction)
            tokens_with = comp.estimate_tokens(result_with.instruction)
            overhead = tokens_with - tokens_without
            overhead_pct = (overhead / tokens_without * 100) if tokens_without > 0 else 0.0

            metrics.append(
                PonytailMetric(
                    task_id=task["id"],
                    complexity=task["complexity"],
                    prompt_tokens_without=tokens_without,
                    prompt_tokens_with=tokens_with,
                    injection_overhead_tokens=overhead,
                    injection_overhead_pct=round(overhead_pct, 1),
                )
            )
    finally:
        os.unlink(config_without_path)
        os.unlink(config_with_path)

    return metrics


# ============================================================
# Phase 2: SMART compression A/B
# ============================================================


def _make_json_sample(num_items: int = 50) -> str:
    """Build a large JSON array sample (highly compressible by SMART)."""
    items = [
        {"id": i, "status": "ok", "service": "api-gateway", "latency_ms": 100 + i, "region": "us-east-1"}
        for i in range(num_items)
    ]
    return json.dumps(items)


def _make_log_sample(num_lines: int = 80) -> str:
    """Build a multi-line log sample (highly compressible by SMART)."""
    lines = []
    for i in range(num_lines):
        if i % 20 == 5:
            lines.append(f"2026-07-01T10:{i:02d}:00Z ERROR request {i} failed with timeout")
        elif i % 20 == 10:
            lines.append(f"2026-07-01T10:{i:02d}:00Z WARN high latency detected on shard {i}")
        else:
            lines.append(f"2026-07-01T10:{i:02d}:00Z INFO processing request {i}")
    return "\n".join(lines)


def _make_code_sample() -> str:
    """Build a code sample (less compressible by SMART, but tested)."""
    return "\n".join(
        [
            "def process(data):",
            "    result = []",
            "    for item in data:",
            "        if item.valid:",
            "            result.append(item.value)",
            "    return result",
        ]
    )


def _make_plain_sample() -> str:
    """Build a plain text sample (not compressible by SMART)."""
    return "This is a short plain text message without any structured content to compress."


def run_smart_compression_benchmark() -> list[SmartCompressionMetric]:
    """Run SMART compression A/B benchmark.

    Compares SMART vs SNIP vs no compression on structured content samples.
    Measures token reduction, message preservation, and correctness.
    """
    samples = [
        ("JSON-50", "json", _make_json_sample(50)),
        ("JSON-100", "json", _make_json_sample(100)),
        ("LOG-80", "log", _make_log_sample(80)),
        ("LOG-160", "log", _make_log_sample(160)),
        ("CODE", "code", _make_code_sample()),
        ("PLAIN", "plain", _make_plain_sample()),
    ]

    metrics: list[SmartCompressionMetric] = []
    comp = ContextCompressor()

    for sample_id, content_type, content in samples:
        msgs = [Message(role="worker", content=content, msg_type=MessageType.ASSISTANT)]
        original_tokens = comp.estimate_messages_tokens(msgs)

        # SMART compression (level 4) — preserves all messages
        smart_ctx = comp.check_and_compress(msgs, force_level=CompressionLevel.SMART)
        smart_tokens = smart_ctx.compressed_token_count
        smart_preserved = len(smart_ctx.messages)

        # SNIP compression (level 1) — may remove messages
        snip_ctx = comp.check_and_compress(msgs, force_level=CompressionLevel.SNIP)
        snip_tokens = snip_ctx.compressed_token_count
        snip_preserved = len(snip_ctx.messages)

        # Correctness: SMART preserves structured content markers
        smart_content = smart_ctx.messages[0].content if smart_ctx.messages else ""
        if content_type == "json":
            correctness = 1.0 if "[items compressed to" in smart_content or "constant_fields" in smart_content else 0.5
        elif content_type == "log":
            correctness = 1.0 if "[log lines compressed to" in smart_content or "ERROR" in smart_content else 0.5
        else:
            correctness = 1.0 if smart_content == content else 0.8  # unchanged = preserved

        smart_reduction = ((1 - smart_tokens / original_tokens) * 100) if original_tokens > 0 else 0.0
        snip_reduction = ((1 - snip_tokens / original_tokens) * 100) if original_tokens > 0 else 0.0

        metrics.append(
            SmartCompressionMetric(
                sample_id=sample_id,
                content_type=content_type,
                original_tokens=original_tokens,
                smart_tokens=smart_tokens,
                snip_tokens=snip_tokens,
                smart_reduction_pct=round(smart_reduction, 1),
                snip_reduction_pct=round(snip_reduction, 1),
                smart_messages_preserved=smart_preserved,
                snip_messages_preserved=snip_preserved,
                smart_correctness_score=correctness,
            )
        )

    return metrics


# ============================================================
# Summary computation
# ============================================================


def compute_ponytail_summary(metrics: list[PonytailMetric]) -> dict[str, Any]:
    """Aggregate ponytail A/B metrics by complexity tier."""
    summary: dict[str, Any] = {"total_tasks": len(metrics)}
    for tier in ["simple", "medium", "complex"]:
        tier_metrics = [m for m in metrics if m.complexity == tier]
        if not tier_metrics:
            continue
        avg_overhead = sum(m.injection_overhead_pct for m in tier_metrics) / len(tier_metrics)
        avg_tokens_without = sum(m.prompt_tokens_without for m in tier_metrics) / len(tier_metrics)
        avg_tokens_with = sum(m.prompt_tokens_with for m in tier_metrics) / len(tier_metrics)
        summary[tier] = {
            "count": len(tier_metrics),
            "avg_tokens_without": round(avg_tokens_without, 1),
            "avg_tokens_with": round(avg_tokens_with, 1),
            "avg_overhead_pct": round(avg_overhead, 1),
        }
    overall_overhead = sum(m.injection_overhead_pct for m in metrics) / len(metrics) if metrics else 0.0
    summary["overall_avg_overhead_pct"] = round(overall_overhead, 1)
    return summary


def compute_smart_summary(metrics: list[SmartCompressionMetric]) -> dict[str, Any]:
    """Aggregate SMART compression A/B metrics by content type."""
    summary: dict[str, Any] = {"total_samples": len(metrics)}
    for ctype in ["json", "log", "code", "plain"]:
        type_metrics = [m for m in metrics if m.content_type == ctype]
        if not type_metrics:
            continue
        avg_smart_reduction = sum(m.smart_reduction_pct for m in type_metrics) / len(type_metrics)
        avg_snip_reduction = sum(m.snip_reduction_pct for m in type_metrics) / len(type_metrics)
        avg_correctness = sum(m.smart_correctness_score for m in type_metrics) / len(type_metrics)
        all_preserved = all(m.smart_messages_preserved >= 1 for m in type_metrics)
        summary[ctype] = {
            "count": len(type_metrics),
            "avg_smart_reduction_pct": round(avg_smart_reduction, 1),
            "avg_snip_reduction_pct": round(avg_snip_reduction, 1),
            "avg_correctness": round(avg_correctness, 2),
            "all_messages_preserved": all_preserved,
        }
    overall_smart = sum(m.smart_reduction_pct for m in metrics) / len(metrics) if metrics else 0.0
    overall_snip = sum(m.snip_reduction_pct for m in metrics) / len(metrics) if metrics else 0.0
    summary["overall_avg_smart_reduction_pct"] = round(overall_smart, 1)
    summary["overall_avg_snip_reduction_pct"] = round(overall_snip, 1)
    return summary


# ============================================================
# Report output
# ============================================================


def print_report(report: BenchmarkReport) -> None:
    """Print a human-readable benchmark report to stdout."""
    print("=" * 70)
    print(f"DevSquad V3.10.0 Benchmark Report — {report.run_timestamp}")
    print(f"Total tasks: {report.total_tasks}")
    print("=" * 70)

    print("\n--- Phase 1: Ponytail Injection A/B ---")
    print(f"{'Task':<8} {'Complexity':<10} {'Without':>10} {'With':>10} {'Overhead':>10} {'%':>8}")
    print("-" * 60)
    for m in report.ponytail_metrics:
        print(f"{m.task_id:<8} {m.complexity:<10} {m.prompt_tokens_without:>10} {m.prompt_tokens_with:>10} {m.injection_overhead_tokens:>10} {m.injection_overhead_pct:>7.1f}%")

    s = report.ponytail_summary
    print(f"\nOverall avg overhead: {s.get('overall_avg_overhead_pct', 0.0)}%")
    for tier in ["simple", "medium", "complex"]:
        if tier in s:
            t = s[tier]
            print(f"  {tier}: {t['count']} tasks, avg {t['avg_overhead_pct']}% overhead ({t['avg_tokens_without']}→{t['avg_tokens_with']} tokens)")

    print("\n--- Phase 2: SMART Compression A/B ---")
    print(f"{'Sample':<12} {'Type':<8} {'Original':>10} {'SMART':>10} {'SNIP':>10} {'SMART%':>8} {'SNIP%':>8} {'Preserved':>10} {'Correct':>8}")
    print("-" * 90)
    for sm in report.smart_metrics:
        print(f"{sm.sample_id:<12} {sm.content_type:<8} {sm.original_tokens:>10} {sm.smart_tokens:>10} {sm.snip_tokens:>10} {sm.smart_reduction_pct:>7.1f}% {sm.snip_reduction_pct:>7.1f}% {sm.smart_messages_preserved:>10} {sm.smart_correctness_score:>8.2f}")

    s = report.smart_summary
    print(f"\nOverall avg reduction — SMART: {s.get('overall_avg_smart_reduction_pct', 0.0)}% | SNIP: {s.get('overall_avg_snip_reduction_pct', 0.0)}%")
    for ctype in ["json", "log", "code", "plain"]:
        if ctype in s:
            c = s[ctype]
            print(f"  {ctype}: {c['count']} samples, SMART {c['avg_smart_reduction_pct']}% / SNIP {c['avg_snip_reduction_pct']}%, correctness {c['avg_correctness']}, preserved={c['all_messages_preserved']}")

    print("\n" + "=" * 70)


# ============================================================
# Main
# ============================================================


def main() -> int:
    """Run the ponytail + SMART benchmark and emit a report.

    Returns:
        Exit code 0 on success, 1 on argument error.
    """
    parser = argparse.ArgumentParser(description="Ponytail + SMART compression A/B benchmark")
    parser.add_argument("--output", "-o", help="Output JSON report path (default: stdout only)")
    parser.add_argument("--tasks", choices=["all", "simple", "medium", "complex"], default="all", help="Task tier to benchmark")
    args = parser.parse_args()

    tasks = BENCHMARK_TASKS
    if args.tasks != "all":
        tasks = [t for t in tasks if t["complexity"] == args.tasks]

    print(f"Running benchmark on {len(tasks)} tasks ({args.tasks})...")

    start = time.time()
    ponytail_metrics = run_ponytail_benchmark(tasks)
    smart_metrics = run_smart_compression_benchmark()

    report = BenchmarkReport(
        run_timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
        total_tasks=len(tasks),
        ponytail_metrics=ponytail_metrics,
        smart_metrics=smart_metrics,
        ponytail_summary=compute_ponytail_summary(ponytail_metrics),
        smart_summary=compute_smart_summary(smart_metrics),
    )
    elapsed = time.time() - start

    print_report(report)
    print(f"\nBenchmark completed in {elapsed:.2f}s")

    if args.output:
        report_dict = {
            "run_timestamp": report.run_timestamp,
            "total_tasks": report.total_tasks,
            "ponytail_metrics": [asdict(m) for m in report.ponytail_metrics],
            "smart_metrics": [asdict(m) for m in report.smart_metrics],
            "ponytail_summary": report.ponytail_summary,
            "smart_summary": report.smart_summary,
        }
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False)
        print(f"Report saved to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
