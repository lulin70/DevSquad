#!/usr/bin/env python3
"""
PerfBaseline — Performance baseline sample collector + CI gate (V4.5.2 §6).

Tracks steady-state samples for each execution path (B Host Bridge / A Direct
API / C Mock / auto-fallback). Excludes warm-up + failure samples to keep
P95/P99 meaningful.

CI gates:
  Mock path:      p95 > +10% above baseline → block PR
  Host Bridge:    p95 > +10% above baseline → block PR
  Direct API:     p95 > +20% above baseline → block PR (network slack)
  auto-fallback:  diagnostic only (no CI gate)

Anti-Ghost: _call_counter_er 每次 collect/compare 递增。
"""

from __future__ import annotations

import json
import logging
import os
import statistics
import time
from dataclasses import asdict, dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

# Module-level Anti-Ghost counter
_call_counter_er: int = 0


def get_call_counter_er() -> int:
    """Return module activation counter (for Anti-Ghost verification)."""
    return _call_counter_er


def _inc_call_counter_er() -> None:
    global _call_counter_er
    _call_counter_er += 1


# === Sample size + thresholds (PRD §5.2) ===
SAMPLE_COUNTS: dict[str, int] = {
    "mock": 50,
    "host": 50,
    "api": 20,
    "auto_fallback": 10,
}

WARMUP_DISCARD = 5  # cold-start samples are dropped

# CI thresholds: regression threshold per path
GATE_THRESHOLDS: dict[str, float] = {
    "mock": 0.10,           # +10% p95 → block
    "host": 0.10,           # +10% p95 → block
    "api": 0.20,            # +20% p95 → block (network slack)
    "auto_fallback": 1.00,  # diagnostic only (no block)
}

# === Default baseline file path ===
DEFAULT_BASELINE_PATH = "docs/reference/PERFORMANCE_BASELINE.json"


@dataclass
class PerfSnapshot:
    """Steady-state performance snapshot for a single execution path.

    Attributes:
        path: 'mock' | 'host' | 'api' | 'auto_fallback'
        call_count: Number of successful steady-state samples
        p50_ms: 50th percentile latency (ms)
        p95_ms: 95th percentile latency (ms) — primary CI gate metric
        p99_ms: 99th percentile latency (ms)
        avg_ms: Mean latency (ms)
        min_ms: Min latency (ms)
        max_ms: Max latency (ms)
        excluded_count: Number of samples excluded (warmup, failure, timeout)
        snapshot_id: Identifier (e.g., 'v452_baseline', 'pr_1234')
        timestamp: ISO timestamp when snapshot was captured
        baseline_p95_ms: Baseline p95 (set when comparing)
        delta_p95_pct: Percent change vs baseline (set when comparing)
        within_threshold: True if delta <= gate threshold
    """

    path: str
    call_count: int
    p50_ms: float
    p95_ms: float
    p99_ms: float
    avg_ms: float
    min_ms: float
    max_ms: float
    excluded_count: int = 0
    snapshot_id: str = ""
    timestamp: str = ""
    baseline_p95_ms: float | None = None
    delta_p95_pct: float | None = None
    within_threshold: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerfSnapshot:
        """Deserialize from dict."""
        return cls(**data)


@dataclass
class PerfBaseline:
    """Baseline reference holding snapshots per path.

    Loaded from / saved to JSON. Used by CI to compare current run vs baseline.
    """

    snapshots: dict[str, PerfSnapshot] = field(default_factory=dict)
    version: str = "v4.5.2"

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "snapshots": {p: s.to_dict() for p, s in self.snapshots.items()},
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PerfBaseline:
        return cls(
            version=data.get("version", "v4.5.2"),
            snapshots={
                p: PerfSnapshot.from_dict(s)
                for p, s in data.get("snapshots", {}).items()
            },
        )

    def save(self, path: str = DEFAULT_BASELINE_PATH) -> None:
        """Save baseline to JSON file."""
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("PerfBaseline saved: %s (%d paths)", path, len(self.snapshots))

    @classmethod
    def load(cls, path: str = DEFAULT_BASELINE_PATH) -> PerfBaseline:
        """Load baseline from JSON file. Empty baseline if missing."""
        if not os.path.exists(path):
            logger.debug("PerfBaseline not found: %s (returning empty)", path)
            return cls()
        try:
            with open(path, encoding="utf-8") as f:
                return cls.from_dict(json.load(f))
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("PerfBaseline load failed (%s); returning empty", e)
            return cls()


# ---------------------------------------------------------------------------
# Sample collector
# ---------------------------------------------------------------------------


class PerfSampleCollector:
    """Collect steady-state samples for a single path.

    Usage:
        collector = PerfSampleCollector(path="mock")
        # Warmup (discarded)
        for _ in range(WARMUP_DISCARD):
            collector.time_call(lambda: do_work())
        # Real samples
        for _ in range(SAMPLE_COUNTS["mock"]):
            collector.time_call(lambda: do_work())
        snapshot = collector.snapshot()
    """

    def __init__(self, path: str, exclude_failures: bool = True) -> None:
        if path not in SAMPLE_COUNTS:
            raise ValueError(
                f"Unknown path: {path!r} (expected one of {list(SAMPLE_COUNTS)})"
            )
        self.path = path
        self.exclude_failures = exclude_failures
        self._samples: list[float] = []
        self._excluded: int = 0

    def time_call(self, fn: Any) -> Any:
        """Run ``fn``, record latency, return its result.

        Failed calls are counted as excluded (not added to samples).
        Returns the callable's return value for convenience.
        """
        t0 = time.perf_counter()
        try:
            result = fn()
            elapsed = time.perf_counter() - t0
            self._samples.append(elapsed * 1000)  # ms
            return result
        except Exception:
            self._excluded += 1
            if not self.exclude_failures:
                raise
            return None

    def add_sample(self, latency_ms: float) -> None:
        """Manually add a sample (e.g., from external measurement)."""
        self._samples.append(latency_ms)

    def exclude(self, reason: str = "manual") -> None:  # noqa: ARG002
        """Increment excluded counter (e.g., timeout, corrupted response)."""
        self._excluded += 1

    def _compute_percentile(self, sorted_vals: list[float], pct: float) -> float:
        if not sorted_vals:
            return 0.0
        # Nearest-rank percentile (matches performance_monitor convention)
        idx = int(len(sorted_vals) * pct)
        if idx >= len(sorted_vals):
            idx = len(sorted_vals) - 1
        return sorted_vals[idx]

    def snapshot(
        self,
        warmup_discard: int = WARMUP_DISCARD,
        snapshot_id: str = "",
    ) -> PerfSnapshot:
        """Build PerfSnapshot, dropping first ``warmup_discard`` samples."""
        _inc_call_counter_er()

        # Apply warmup discard
        steady = self._samples[warmup_discard:] if len(self._samples) > warmup_discard else []
        if not steady:
            # Not enough samples — return zero snapshot
            return PerfSnapshot(
                path=self.path,
                call_count=0,
                p50_ms=0.0,
                p95_ms=0.0,
                p99_ms=0.0,
                avg_ms=0.0,
                min_ms=0.0,
                max_ms=0.0,
                excluded_count=self._excluded,
                snapshot_id=snapshot_id,
                timestamp=_now_iso(),
            )

        sorted_vals = sorted(steady)
        snap = PerfSnapshot(
            path=self.path,
            call_count=len(steady),
            p50_ms=self._compute_percentile(sorted_vals, 0.50),
            p95_ms=self._compute_percentile(sorted_vals, 0.95),
            p99_ms=self._compute_percentile(sorted_vals, 0.99),
            avg_ms=statistics.fmean(steady),
            min_ms=min(steady),
            max_ms=max(steady),
            excluded_count=self._excluded,
            snapshot_id=snapshot_id,
            timestamp=_now_iso(),
        )
        return snap

    def reset(self) -> None:
        """Clear samples."""
        self._samples.clear()
        self._excluded = 0


# ---------------------------------------------------------------------------
# CI compare gate
# ---------------------------------------------------------------------------


def compare_to_baseline(
    snapshot: PerfSnapshot,
    baseline: PerfBaseline,
    threshold: float | None = None,
) -> PerfSnapshot:
    """Compare a snapshot against the baseline; annotate with delta + gate result.

    Mutates the snapshot's `baseline_p95_ms`, `delta_p95_pct`,
    `within_threshold` fields and returns it.

    Args:
        snapshot: The current run snapshot.
        baseline: Loaded PerfBaseline.
        threshold: Override regression threshold (default uses
            GATE_THRESHOLDS[snapshot.path]).

    Returns:
        The same snapshot, annotated.
    """
    _inc_call_counter_er()

    base = baseline.snapshots.get(snapshot.path)
    if base is None:
        logger.debug("No baseline for path=%s (skip compare)", snapshot.path)
        return snapshot

    gate = threshold if threshold is not None else GATE_THRESHOLDS.get(snapshot.path, 0.10)

    baseline_p95 = base.p95_ms
    if baseline_p95 <= 0:
        return snapshot

    delta_pct = (snapshot.p95_ms - baseline_p95) / baseline_p95 * 100.0
    within_threshold = (delta_pct / 100.0) <= gate

    # P11.1: emit prometheus metric for the perf snapshot + gate outcome
    try:
        from .prometheus_metrics import get_metrics as _gm

        _gm().record_perf_snapshot(
            snapshot.path, snapshot.p95_ms, delta_p95_pct=delta_pct,
            within_threshold=within_threshold,
        )
    except (RuntimeError, ValueError, AttributeError):
        # Metrics are best-effort; never break the compare gate
        pass

    # Re-create frozen dataclass with updated fields (dataclass(frozen=True))
    return PerfSnapshot(
        path=snapshot.path,
        call_count=snapshot.call_count,
        p50_ms=snapshot.p50_ms,
        p95_ms=snapshot.p95_ms,
        p99_ms=snapshot.p99_ms,
        avg_ms=snapshot.avg_ms,
        min_ms=snapshot.min_ms,
        max_ms=snapshot.max_ms,
        excluded_count=snapshot.excluded_count,
        snapshot_id=snapshot.snapshot_id,
        timestamp=snapshot.timestamp,
        baseline_p95_ms=baseline_p95,
        delta_p95_pct=delta_pct,
        within_threshold=within_threshold,
    )


def collect_snapshot_for_path(
    path: str,
    backend: Any,
    prompt: str = "ping",
    role_name: str = "perf",
    snapshot_id: str = "",
) -> PerfSnapshot:
    """High-level helper: collect a PerfSnapshot by invoking ``backend``.

    Runs warmup + steady-state samples. Excludes failures automatically.
    """
    if path not in SAMPLE_COUNTS:
        raise ValueError(f"Unknown path: {path!r}")

    collector = PerfSampleCollector(path=path)
    target_count = SAMPLE_COUNTS[path] + WARMUP_DISCARD

    for _ in range(target_count):
        # backend.generate is sync per V4.5.2 contract
        collector.time_call(lambda: backend.generate(prompt, role_name=role_name))

    return collector.snapshot(snapshot_id=snapshot_id)


# ---------------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------------


__all__ = [
    "PerfSnapshot",
    "PerfBaseline",
    "PerfSampleCollector",
    "compare_to_baseline",
    "collect_snapshot_for_path",
    "get_call_counter_er",
    "SAMPLE_COUNTS",
    "WARMUP_DISCARD",
    "GATE_THRESHOLDS",
    "DEFAULT_BASELINE_PATH",
]


def _now_iso() -> str:
    """ISO timestamp helper."""
    import datetime as _dt

    return _dt.datetime.now().isoformat()


# Initialize anti-ghost counter on module load
_inc_call_counter_er()
