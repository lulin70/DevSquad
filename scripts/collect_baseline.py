#!/usr/bin/env python3
"""
collect_baseline.py — V4.7.0 Performance Baseline Collector (one-shot script).

Runs representative samples for each execution path and writes them to
docs/reference/PERFORMANCE_BASELINE.json.

- mock:          measured — real MockBackend.generate() calls via
                 collect_snapshot_for_path (warmup discarded, failures excluded)
- host:          measured when the host bridge environment is present;
                 stub otherwise (environment_blocked, printed honestly)
- api:           measured when provider credentials are configured
                 (openai → anthropic → moka priority); stub otherwise
- auto_fallback: stub — depends on which sub-path triggers

Run locally once to seed the baseline file:

    python3 scripts/collect_baseline.py

This file is committed to the repo and consumed by CI (mock path) and
release tag workflows (host/api paths).

Note: Real LLM API timings require the actual provider; we emit stub samples
      for host/api that are clearly marked as 'stub' so CI can distinguish
      measured vs. placeholder values.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from scripts.collaboration.llm_backend import create_backend  # noqa: E402
from scripts.collaboration.perf_baseline import (  # noqa: E402
    DEFAULT_BASELINE_PATH,
    GATE_THRESHOLDS,
    SAMPLE_COUNTS,
    WARMUP_DISCARD,
    PerfBaseline,
    PerfSampleCollector,
    PerfSnapshot,
    collect_snapshot_for_path,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _collect_mock() -> PerfSnapshot:
    """Collect measured samples for the C path (real MockBackend.generate calls)."""
    backend = create_backend("mock")
    snap = collect_snapshot_for_path(
        "mock",
        backend,
        prompt="baseline ping",
        role_name="perf",
        snapshot_id="v470_baseline",
    )
    snap.timestamp = _now_iso()
    return snap


def _collect_api() -> tuple[PerfSnapshot, str]:
    """Collect measured samples for the A path (real provider API calls).

    Tries each provider backend in priority order (openai → anthropic →
    moka); the first available one is measured for real. A short pause
    between samples avoids provider burst rate limits, and the whole
    attempt is bounded by ``_API_MEASURE_BUDGET_S``: when a provider's
    minute-level rate limit makes the collection exceed the budget (two
    local attempts — 20 samples, then 10 samples + 1s spacing — each ran
    past 25 minutes in retry backoff), the caller gets a stub snapshot
    (environment_blocked — printed honestly) instead of hanging.
    """
    import time as _time

    budget_s = 180.0
    started = _time.perf_counter()
    reason = "no provider credentials configured"
    for name in ("openai", "anthropic", "moka"):
        try:
            backend = create_backend(name)
        except Exception:
            continue
        try:
            if not backend.is_available():
                continue
        except Exception:
            continue
        collector = PerfSampleCollector(path="api")
        total = SAMPLE_COUNTS["api"] + WARMUP_DISCARD
        for _ in range(total):
            if _time.perf_counter() - started > budget_s:
                reason = f"{name} measurement exceeded {budget_s:.0f}s budget (provider rate limit)"
                print(f"  api: {reason} — stub retained")
                break
            collector.time_call(lambda b=backend: b.generate("Reply with exactly: pong", role_name="perf"))
            _time.sleep(1.0)  # avoid provider burst rate limits
        else:
            snap = collector.snapshot(snapshot_id="v470_baseline_api")
            snap.timestamp = _now_iso()
            return snap, name
    return (
        _collect_stub("api", SAMPLE_COUNTS["api"], avg_ms=1500.0, jitter_ms=400.0),
        reason,
    )


def _collect_host() -> tuple[PerfSnapshot, bool]:
    """Collect the B path: real host-bridge calls when the host environment
    is present; otherwise a stub snapshot (environment_blocked)."""
    backend = None
    try:
        backend = create_backend("host")
        available = backend.is_available()
    except Exception:
        available = False
    if available and backend is not None:
        snap = collect_snapshot_for_path(
            "host",
            backend,
            prompt="Reply with exactly: pong",
            role_name="perf",
            snapshot_id="v470_baseline_host",
        )
        snap.timestamp = _now_iso()
        return snap, True
    return (
        _collect_stub("host", SAMPLE_COUNTS["host"], avg_ms=200.0, jitter_ms=80.0),
        False,
    )


def _collect_stub(path: str, n: int, avg_ms: float, jitter_ms: float) -> PerfSnapshot:
    """Emit a stub snapshot for paths not measured locally (host/api).

    These are clearly marked with snapshot_id ending in '_stub' so CI can
    distinguish real measurements from placeholder seeds.
    """
    col = PerfSampleCollector(path)
    # Warmup samples are pre-warmed at the target average
    for _ in range(WARMUP_DISCARD):
        col.add_sample(avg_ms + (jitter_ms / 2))

    # Steady-state samples around avg with bounded jitter
    step = jitter_ms / max(n, 1)
    for i in range(n):
        val = avg_ms + ((i - n / 2) * step)
        col.add_sample(val)

    snap = col.snapshot(snapshot_id=f"v470_baseline_{path}_stub")
    snap.timestamp = _now_iso()
    snap.excluded_count = 0
    return snap


def main() -> int:
    """Collect baseline for all 4 paths and write to docs/reference/."""
    print("V4.7.0 Performance Baseline Collector")
    print("=" * 60)

    # C path: actually measured (real MockBackend.generate calls)
    print(f"[mock] Collecting {SAMPLE_COUNTS['mock']} samples (+{WARMUP_DISCARD} warmup discarded)...")
    mock_snap = _collect_mock()
    print(f"  mock: p50={mock_snap.p50_ms:.2f}ms p95={mock_snap.p95_ms:.2f}ms p99={mock_snap.p99_ms:.2f}ms [measured]")

    # B path: real host-bridge calls when the host environment is present
    print("[host] Probing host bridge availability...")
    host_snap, host_measured = _collect_host()
    if host_measured:
        print(
            f"  host: p50={host_snap.p50_ms:.2f}ms p95={host_snap.p95_ms:.2f}ms p99={host_snap.p99_ms:.2f}ms [measured]"
        )
    else:
        print("  host: host bridge unavailable in this environment (environment_blocked) — stub retained")
        print(f"  host: p50={host_snap.p50_ms:.2f}ms p95={host_snap.p95_ms:.2f}ms p99={host_snap.p99_ms:.2f}ms [stub]")

    # A path: real provider API calls when credentials are configured
    print("[api] Probing provider backends (openai → anthropic → moka)...")
    api_snap, api_outcome = _collect_api()
    if api_outcome in ("openai", "anthropic", "moka"):
        print(
            f"  api: measured via {api_outcome} backend — p50={api_snap.p50_ms:.2f}ms p95={api_snap.p95_ms:.2f}ms p99={api_snap.p99_ms:.2f}ms [measured]"
        )
    else:
        print(f"  api: {api_outcome} (environment_blocked) — stub retained")
        print(f"  api: p50={api_snap.p50_ms:.2f}ms p95={api_snap.p95_ms:.2f}ms p99={api_snap.p99_ms:.2f}ms [stub]")

    # auto_fallback: stub (depends on which sub-path triggered)
    print("[auto_fallback] Emitting stub snapshot...")
    auto_snap = _collect_stub(
        "auto_fallback",
        SAMPLE_COUNTS["auto_fallback"],
        avg_ms=800.0,
        jitter_ms=300.0,
    )
    print(
        f"  auto_fallback: p50={auto_snap.p50_ms:.2f}ms "
        f"p95={auto_snap.p95_ms:.2f}ms p99={auto_snap.p99_ms:.2f}ms [stub]"
    )

    # Assemble + save
    baseline = PerfBaseline(
        version="v4.7.0",
        snapshots={
            "mock": mock_snap,
            "host": host_snap,
            "api": api_snap,
            "auto_fallback": auto_snap,
        },
    )

    out_path = os.path.join(ROOT, DEFAULT_BASELINE_PATH)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    baseline.save(out_path)

    print()
    print(f"Baseline written to: {out_path}")
    print()
    print("CI thresholds (regression %):")
    for path, threshold in GATE_THRESHOLDS.items():
        print(f"  {path:15s}  +{threshold * 100:.0f}% p95 blocks")
    print()
    print("Note: host/api snapshots are measured when their environment is")
    print("      available; unavailable paths keep clearly-marked stubs.")
    print("      auto_fallback stays a stub (depends on which sub-path triggers).")

    return 0


if __name__ == "__main__":
    sys.exit(main())
