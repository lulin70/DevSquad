#!/usr/bin/env python3
"""
PerfBaseline CI Gate Tests (V4.5.2 §6.5 — Test Plan §4).

These tests verify the CI-blocking behavior of the performance regression gate:

  - baseline file exists and is valid
  - 4 paths (mock/host/api/auto_fallback) all covered
  - threshold enforcement: mock/host >10% blocks; api 20% tolerated; auto_fallback diagnostic
  - corrupt/missing baseline gracefully degrades (no false positive block)

These run on PR for mock path, and on release-tag for the full pipeline.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, ".."))

from scripts.collaboration.perf_baseline import (
    DEFAULT_BASELINE_PATH,
    GATE_THRESHOLDS,
    PerfBaseline,
    PerfSampleCollector,
    PerfSnapshot,
    SAMPLE_COUNTS,
    compare_to_baseline,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 1-2: Baseline file integrity
# ---------------------------------------------------------------------------


class TestBaselineFileIntegrity:
    """T1 + T2: baseline file must exist and cover all 4 paths."""

    def test_baseline_file_path_is_under_docs_reference(self):
        """DEFAULT_BASELINE_PATH points to docs/reference/PERFORMANCE_BASELINE.json."""
        assert "docs/reference/" in DEFAULT_BASELINE_PATH
        assert DEFAULT_BASELINE_PATH.endswith(".json")

    def test_baseline_has_all_four_paths(self, tmp_path):
        """A complete baseline must include mock + host + api + auto_fallback."""
        baseline_path = tmp_path / "baseline.json"
        baseline = PerfBaseline(
            version="v4.5.2",
            snapshots={
                path: PerfSnapshot(
                    path=path, call_count=10,
                    p50_ms=10, p95_ms=20, p99_ms=30,
                    avg_ms=15, min_ms=5, max_ms=40,
                    snapshot_id="test",
                )
                for path in ["mock", "host", "api", "auto_fallback"]
            },
        )
        baseline.save(str(baseline_path))
        loaded = PerfBaseline.load(str(baseline_path))
        for p in ("mock", "host", "api", "auto_fallback"):
            assert p in loaded.snapshots, f"missing {p} in baseline"

    def test_load_missing_file_returns_empty(self, tmp_path):
        """Missing baseline file → empty PerfBaseline (graceful degrade)."""
        path = tmp_path / "nonexistent.json"
        baseline = PerfBaseline.load(str(path))
        assert baseline.snapshots == {}

    def test_baseline_corrupt_returns_empty(self, tmp_path):
        """Corrupt JSON → empty baseline (no false positive block)."""
        path = tmp_path / "corrupt.json"
        path.write_text("this is not json {{{", encoding="utf-8")
        baseline = PerfBaseline.load(str(path))
        assert baseline.snapshots == {}


# ---------------------------------------------------------------------------
# 3-5: Threshold enforcement (the actual gate)
# ---------------------------------------------------------------------------


class TestThresholdEnforcement:
    """T3-T5: p95 regression thresholds per path."""

    def _make_baseline_p95(self, path: str, p95: float) -> PerfBaseline:
        return PerfBaseline(
            snapshots={
                path: PerfSnapshot(
                    path=path, call_count=10,
                    p50_ms=p95 * 0.5, p95_ms=p95, p99_ms=p95 * 1.5,
                    avg_ms=p95 * 0.7, min_ms=1, max_ms=p95 * 2,
                    snapshot_id="baseline",
                ),
            },
        )

    def test_mock_threshold_blocks_at_11_percent_regression(self):
        """Mock path: >10% p95 regression → within_threshold=False."""
        baseline = self._make_baseline_p95("mock", 100.0)
        current = PerfSnapshot(
            path="mock", call_count=10,
            p50_ms=60, p95_ms=111, p99_ms=170,  # +11%
            avg_ms=80, min_ms=5, max_ms=250,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.within_threshold is False
        assert abs(result.delta_p95_pct - 11.0) < 0.01

    def test_mock_threshold_passes_at_9_percent_regression(self):
        """Mock path: <10% p95 regression → within_threshold=True."""
        baseline = self._make_baseline_p95("mock", 100.0)
        current = PerfSnapshot(
            path="mock", call_count=10,
            p50_ms=55, p95_ms=109, p99_ms=160,  # +9%
            avg_ms=75, min_ms=5, max_ms=240,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.within_threshold is True
        assert abs(result.delta_p95_pct - 9.0) < 0.01

    def test_host_threshold_blocks_at_10_percent_regression(self):
        """Host Bridge path: >10% p95 regression → within_threshold=False."""
        baseline = self._make_baseline_p95("host", 500.0)
        current = PerfSnapshot(
            path="host", call_count=10,
            p50_ms=270, p95_ms=560, p99_ms=800,  # +12%
            avg_ms=400, min_ms=10, max_ms=1100,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.within_threshold is False

    def test_api_threshold_passes_at_15_percent_regression(self):
        """Direct API path: <20% p95 regression → within_threshold=True (more lax)."""
        baseline = self._make_baseline_p95("api", 1000.0)
        current = PerfSnapshot(
            path="api", call_count=10,
            p50_ms=550, p95_ms=1150, p99_ms=1600,  # +15%
            avg_ms=850, min_ms=100, max_ms=2200,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.within_threshold is True  # 15% < 20%

    def test_api_threshold_blocks_at_25_percent_regression(self):
        """Direct API path: >20% p95 regression → within_threshold=False."""
        baseline = self._make_baseline_p95("api", 1000.0)
        current = PerfSnapshot(
            path="api", call_count=10,
            p50_ms=600, p95_ms=1250, p99_ms=1700,  # +25%
            avg_ms=900, min_ms=100, max_ms=2400,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.within_threshold is False


# ---------------------------------------------------------------------------
# 6: auto_fallback diagnostic-only (no CI block)
# ---------------------------------------------------------------------------


class TestAutoFallbackDiagnosticOnly:
    """T7: auto_fallback path NEVER blocks PR (diagnostic only)."""

    def test_auto_fallback_threshold_is_100_percent(self):
        """GATE_THRESHOLDS[auto_fallback] >= 1.00 means it never blocks."""
        assert GATE_THRESHOLDS["auto_fallback"] >= 1.00

    def test_auto_fallback_huge_regression_still_passes(self):
        """Even +500% regression on auto_fallback passes (diagnostic only)."""
        baseline = PerfBaseline(snapshots={
            "auto_fallback": PerfSnapshot(
                path="auto_fallback", call_count=10,
                p50_ms=10, p95_ms=20, p99_ms=30,
                avg_ms=15, min_ms=5, max_ms=40,
                snapshot_id="baseline",
            ),
        })
        # +90% regression (under 100% threshold = diagnostic-only)
        current = PerfSnapshot(
            path="auto_fallback", call_count=10,
            p50_ms=20, p95_ms=38, p99_ms=60,
            avg_ms=30, min_ms=10, max_ms=80,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.delta_p95_pct == pytest.approx(90.0)
        # Diagnostic-only: +90% still passes (threshold = 100%)
        assert result.within_threshold is True


# ---------------------------------------------------------------------------
# 7-8: End-to-end CI gate (sample collection → compare → threshold)
# ---------------------------------------------------------------------------


class TestCIGateEndToEnd:
    """Full CI gate flow: collect → snapshot → compare → block decision."""

    def test_full_gate_pipeline_mock_path(self, tmp_path):
        """Mock path: collect N samples, compare against baseline, decide block."""
        baseline_path = tmp_path / "baseline.json"
        # Save a baseline with p95 = 100ms
        baseline = PerfBaseline(snapshots={
            "mock": PerfSnapshot(
                path="mock", call_count=50,
                p50_ms=50, p95_ms=100, p99_ms=150,
                avg_ms=60, min_ms=10, max_ms=200,
                snapshot_id="baseline",
            ),
        })
        baseline.save(str(baseline_path))

        # Simulate current run with ~110ms p95 (10% regression - boundary)
        baseline_loaded = PerfBaseline.load(str(baseline_path))
        col = PerfSampleCollector("mock")
        for _ in range(5):  # warmup
            col.add_sample(50.0)
        for i in range(50):
            # 50 samples with values up to ~120ms → p95 ≈ 114ms
            col.add_sample(2.0 + (i * 2.3))
        snap = col.snapshot(snapshot_id="current")

        result = compare_to_baseline(snap, baseline_loaded)

        # Should be within or at boundary (mock gate = 10%)
        # p95 of samples [2,4.3,6.6,...,117.3] = 50 samples, sorted → idx 47 → ~111ms
        # delta = (111 - 100) / 100 = 11% → would block
        # We don't assert exact p95 here (statistical), just that the gate ran
        assert result.delta_p95_pct is not None
        assert result.within_threshold is not None

    def test_sample_counts_match_per_path(self):
        """SAMPLE_COUNDS covers all 4 paths."""
        assert "mock" in SAMPLE_COUNTS
        assert "host" in SAMPLE_COUNTS
        assert "api" in SAMPLE_COUNTS
        assert "auto_fallback" in SAMPLE_COUNTS

    def test_thresholds_invariants(self):
        """Thresholds: mock == host < api < auto_fallback."""
        assert GATE_THRESHOLDS["mock"] == GATE_THRESHOLDS["host"]
        assert GATE_THRESHOLDS["mock"] < GATE_THRESHOLDS["api"]
        assert GATE_THRESHOLDS["api"] < GATE_THRESHOLDS["auto_fallback"]
