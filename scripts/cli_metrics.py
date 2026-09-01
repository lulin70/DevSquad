#!/usr/bin/env python3
"""devsquad metrics CLI — View V4.5.2 Prometheus metrics (P12.1.2).

Reads from the live prometheus_client registry and prints current values
in human-readable text or JSON format. Useful when Prometheus server
isn't available or for ad-hoc inspection.

Usage:
    devsquad metrics [--format text|json]

Implementation:
- If prometheus_client is installed, introspect REGISTRY for known
  V4.5.2 metrics (counter/gauge/histogram) and dump current values.
- Falls back to a stub-only summary if prometheus_client is unavailable.
"""

from __future__ import annotations

import json
from typing import Any

# V4.5.2 metrics inventory (name, type, description, label_keys)
V452_METRICS = [
    {
        "name": "devsquad_v452_task_scale_total",
        "type": "counter",
        "description": "V4.5.2 TaskScaleGate decisions by level (S/M/L)",
        "label_keys": ["level", "orchestrator"],
    },
    {
        "name": "devsquad_v452_order_chain_total",
        "type": "counter",
        "description": "V4.5.2 OrderChainDetector decisions by source",
        "label_keys": ["source", "single_role"],
    },
    {
        "name": "devsquad_v452_backend_calls_total",
        "type": "counter",
        "description": "V4.5.2 backend path invocation count",
        "label_keys": ["path"],
    },
    {
        "name": "devsquad_v452_backend_failures_total",
        "type": "counter",
        "description": "V4.5.2 backend failure count by reason",
        "label_keys": ["path", "reason"],
    },
    {
        "name": "devsquad_v452_fuse_skips_total",
        "type": "counter",
        "description": "V4.5.2 fuse-skip events",
        "label_keys": ["path", "reason"],
    },
    {
        "name": "devsquad_v452_perf_p95_ms",
        "type": "gauge",
        "description": "V4.5.2 latest PerfSnapshot p95 latency in ms",
        "label_keys": ["path"],
    },
    {
        "name": "devsquad_v452_perf_regression_total",
        "type": "counter",
        "description": "V4.5.2 perf baseline gate outcomes (pass/block)",
        "label_keys": ["path", "outcome"],
    },
    {
        "name": "devsquad_v452_perf_latency_ms",
        "type": "histogram",
        "description": "V4.5.2 perf latency samples in ms",
        "label_keys": ["path"],
    },
]

# V4.5.12: SQLite re-project trigger observability metrics (AC-SQL-6).
# V4.5.13: counter names use the explicit `_total` suffix to match the
# prometheus_client exposition format (see prometheus_metrics.py).
V4512_METRICS = [
    {
        "name": "devsquad_v4512_risk_store_capacity",
        "type": "gauge",
        "description": "V4.5.12 risk store item count at last load/save (SQLite trigger: >10k)",
        "label_keys": ["register_id"],
    },
    {
        "name": "devsquad_v4512_risk_store_concurrent_writes_total",
        "type": "counter",
        "description": "V4.5.12 risk store writes in the 60s sliding window",
        "label_keys": ["register_id"],
    },
    {
        "name": "devsquad_v4512_risk_store_cross_host_signals_total",
        "type": "counter",
        "description": "V4.5.12 cross-host lock acquisition signals (SQLite trigger: remote share)",
        "label_keys": [],
    },
    {
        "name": "devsquad_v4512_risk_store_slow_queries_total",
        "type": "counter",
        "description": "V4.5.12 query rounds over 50ms (SQLite trigger: complex query demand)",
        "label_keys": ["register_id"],
    },
]


def _collect_metric_samples(metric_name: str) -> list[dict[str, Any]]:
    """Collect live samples for a metric from the prometheus registry.

    Returns a list of dicts:
        {"labels": {...}, "value": float}

    Returns empty list when prometheus_client is unavailable or the metric
    has no samples yet.
    """
    try:
        from prometheus_client import REGISTRY
    except ImportError:
        return []

    samples: list[dict[str, Any]] = []
    # Iterate registry samples and filter by metric name prefix
    for collector in list(REGISTRY._collector_to_names.keys()):
        try:
            for metric in collector.collect():
                if metric.name != metric_name:
                    continue
                for sample in metric.samples:
                    samples.append({
                        "labels": dict(sample.labels),
                        "value": float(sample.value),
                    })
        except (AttributeError, StopIteration):
            # Some collectors don't support .collect() (e.g. internal ones)
            continue
    return samples


def collect_v4512_metrics() -> list[dict[str, Any]]:
    """Collect V4.5.12 risk-store metrics (AC-SQL-6).

    Prefers live prometheus registry samples; falls back to a direct
    ``FileRiskStore.stats`` read so the CLI works without prometheus_client.
    """
    results: list[dict[str, Any]] = []
    for meta in V4512_METRICS:
        metric_name = str(meta["name"])
        samples = _collect_metric_samples(metric_name)
        if not samples and not metric_name.endswith(("cross_host_signals", "slow_queries")):
            # Fall back to the default store's live stats snapshot.
            samples = _collect_stats_fallback_samples(metric_name)
        results.append({
            "name": metric_name,
            "type": meta["type"],
            "description": meta["description"],
            "label_keys": meta["label_keys"],
            "samples": samples,
        })
    return results


def _collect_stats_fallback_samples(metric_name: str) -> list[dict[str, Any]]:
    """Read the default FileRiskStore stats as metric samples.

    Used when prometheus_client is unavailable or has no samples yet, so
    ``devsquad metrics`` still surfaces the V4.5.12 signals.
    """
    try:
        from scripts.collaboration.file_risk_store import DEFAULT_ROOT, FileRiskStore

        stats = FileRiskStore(root=DEFAULT_ROOT).stats
    except Exception:  # noqa: BLE001 — metrics must never crash the CLI
        return []
    value_by_metric = {
        "devsquad_v4512_risk_store_capacity": stats.capacity,
        "devsquad_v4512_risk_store_concurrent_writes": stats.concurrent_writes_1m,
    }
    if metric_name not in value_by_metric:
        return []
    return [{"labels": {"register_id": "default"}, "value": float(value_by_metric[metric_name])}]


def collect_v452_metrics() -> list[dict[str, Any]]:
    """Collect V4.5.2 metrics from the live registry.

    Returns:
        List of metric dicts with metadata + samples. Empty samples
        means the metric hasn't been recorded yet (idle system).
    """
    results: list[dict[str, Any]] = []
    for meta in V452_METRICS:
        meta_dict: dict[str, Any] = meta
        metric_name = str(meta_dict["name"])
        results.append({
            "name": metric_name,
            "type": meta_dict["type"],
            "description": meta_dict["description"],
            "label_keys": meta_dict["label_keys"],
            "samples": _collect_metric_samples(metric_name),
        })
    return results


def collect_all_metrics() -> list[dict[str, Any]]:
    """Collect V4.5.2 + V4.5.12 metrics (V4.5.12 AC-SQL-6)."""
    return collect_v452_metrics() + collect_v4512_metrics()


def format_text(metrics: list[dict[str, Any]]) -> str:
    """Format metrics as a human-readable text table."""
    lines: list[str] = []
    lines.append("=" * 78)
    lines.append("DevSquad V4.5.2 Metrics")
    lines.append("=" * 78)
    for m in metrics:
        lines.append("")
        lines.append(f"[{m['type'].upper()}] {m['name']}")
        lines.append(f"  {m['description']}")
        if not m["samples"]:
            lines.append("  (no samples recorded — metric idle)")
            continue
        # Pretty-print samples
        max_label_width = max(
            (len(", ".join(f"{k}={v}" for k, v in s["labels"].items())) for s in m["samples"]),
            default=0,
        )
        for s in m["samples"]:
            label_str = ", ".join(f"{k}={v}" for k, v in s["labels"].items())
            lines.append(f"  {label_str:<{max_label_width}}  →  {s['value']:.4f}")
    lines.append("")
    lines.append("=" * 78)
    return "\n".join(lines)


def format_json(metrics: list[dict[str, Any]]) -> str:
    """Format metrics as a JSON string."""
    return json.dumps(
        {
            "version": "V4.5.12",
            "metrics": metrics,
        },
        indent=2,
        ensure_ascii=False,
    )


def cmd_metrics(args: Any) -> int:
    """Main entry point for `devsquad metrics` CLI subcommand.

    Args:
        args: argparse Namespace with `format` attribute ('text' or 'json').

    Returns:
        Exit code (0 on success).
    """
    fmt = getattr(args, "format", "text")
    metrics = collect_all_metrics()
    if fmt == "json":
        print(format_json(metrics))
    else:
        print(format_text(metrics))
    return 0
