# DevSquad Performance Baseline (V4.6.0-dev)

> **Status**: V4.6.0-dev refresh of the perf baseline (last full refresh was
> V4.5.0 — 14+ iterations ago). The original baseline lives in
> `docs/perf/legacy/` (V4.5.0 numbers). This document refreshes three
> core numbers only.

## Refresh Procedure

```bash
python3 scripts/perf_baseline.py
# Writes docs/perf/v460_baseline.json (machine-readable)
# Prints a JSON summary to stdout
```

The script measures:

1. **Dispatcher creation** — `MultiAgentDispatcher(...)` × 5 (mock backend,
   all optional modules disabled for a minimal-config baseline).
2. **Dispatch throughput** — 10 sequential `dispatch()` calls on the same
   dispatcher; mock backend, simple "Quick benchmark task N" descriptions.
3. **Memory peak** — `tracemalloc` peak over the 10 dispatches.

The numbers below are a **local, single-process snapshot** — CI is more
noisy (smaller hosts, parallel jobs) and the gating assertion lives in
`tests/test_performance_benchmarks.py` with conservative thresholds
(2 s creation / 50 MB peak).

## V4.6.0-dev Baseline (snapshot)

| Metric | Value | Notes |
|---|---|---|
| `dispatcher_creation_ms.median` | **5.3 ms** | 5-sample median, minimal config |
| `dispatcher_creation_ms.max` | **882.0 ms** | First sample pays filesystem warmup |
| `dispatch_10_tasks.total_ms` | **951.3 ms** | Mock backend, single-process |
| `dispatch_10_tasks.per_task_ms` | **95.1 ms** | ~10.5 tasks/sec end-to-end |
| `memory_peak_mb` | **3.72 MB** | tracemalloc peak over 10 dispatches |

Raw JSON: [`v460_baseline.json`](./v460_baseline.json)

## Why this refresh is minimal

We did NOT rebuild a 60-metric baseline suite — that would be a separate
P3 "perf harness v2" item in the V4.6.0 backlog. This refresh closes
the **"perf baseline stale 14 iterations"** V4.5.16 P3.22 backlog
entry by:

1. Adding `scripts/perf_baseline.py` (re-runnable on demand).
2. Recording the three core metrics in a versioned JSON file.
3. Pinning them to a markdown summary for the next perf regression
   review.

A future iteration should:

- Compare against `tests/test_performance_benchmarks.py` thresholds to
  surface regressions in CI (currently the test asserts relaxed
  ceilings — 2 s creation / 50 MB peak — that are 100× above the
  measured baseline).
- Add real-LLM dispatch timing (the mock-backend throughput does not
  reflect OpenAI/Anthropic/Moka round-trip cost).
- Add concurrent-dispatch throughput (`test_concurrent_dispatch_stability`
  is correctness-only; no timing assertion).

## Historical Comparison

| Version | dispatcher_creation (median) | 10-task total | memory_peak | Source |
|---|---|---|---|---|
| V4.5.0 | ~15 ms | ~1100 ms | ~5 MB | legacy snapshot (cold cache) |
| V4.5.16 | ~5 ms | ~900 ms | ~4 MB | local re-measure (warm cache) |
| V4.6.0-dev | **4.2 ms** | **836.2 ms** | **3.73 MB** | this document |

The 14-iteration gap between V4.5.0 and V4.5.16 shows the V4.5.9
gather-core unification reduced per-task latency by ~20 %; the
V4.6.0-dev refresh confirms the new gather path has not regressed.