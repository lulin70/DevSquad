#!/usr/bin/env python3
"""
Unit tests for PerfBaseline (V4.5.2 §6).

Covers T1–T5 from V4.5.2_ARCHITECTURE.md §6.2 / V4.5.2_TEST_PLAN §3.6:
  T1 warmup_discard: 前 5 次样本丢弃
  T2 exclude_timeout: 超时/熔断样本不入 P95
  T3 mock_baseline_gate: mock P95 <10% 上升
  T4 host_bridge_baseline: 50 样本，排除 marker 损坏 >3 重试
  T5 snapshot_fields: details["perf_snapshot"] 字段齐全
"""

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
    WARMUP_DISCARD,
    compare_to_baseline,
    get_call_counter,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# T1 — Warmup discard
# ---------------------------------------------------------------------------


class TestT1WarmupDiscard:
    def test_warmup_discard_constant(self):
        """WARMUP_DISCARD = 5."""
        assert WARMUP_DISCARD == 5

    def test_warmup_samples_excluded_from_p95(self):
        """前 5 次样本必须丢弃，不计入 P95."""
        collector = PerfSampleCollector("mock")
        # Add 5 warmup (very high) + 50 steady (low)
        for _ in range(WARMUP_DISCARD):
            collector.add_sample(10000.0)  # very high (cold-start)
        for i in range(50):
            collector.add_sample(float(i + 1))  # 1..50

        snap = collector.snapshot()
        # After discarding warmup, p95 should be near 48 (95% of 50 samples)
        assert snap.call_count == 50
        assert snap.p95_ms <= 50.0
        assert snap.max_ms <= 50.0  # warmup samples gone

    def test_warmup_constant_used(self):
        """DEFAULT warmup = WARMUP_DISCARD."""
        collector = PerfSampleCollector("mock")
        for i in range(WARMUP_DISCARD + 10):
            collector.add_sample(float(i))
        # default warmup applied
        snap = collector.snapshot()
        assert snap.call_count == 10


# ---------------------------------------------------------------------------
# T2 — Exclude failures / timeouts
# ---------------------------------------------------------------------------


class TestT2ExcludeFailures:
    def test_excluded_count_increments_on_failure(self):
        """time_call 失败时 excluded_count 增加，样本不进入 P95."""
        collector = PerfSampleCollector("mock")

        def fail():
            raise RuntimeError("timeout")

        def succeed():
            return "ok"

        # 5 warmup fails + 50 steady ok
        for _ in range(WARMUP_DISCARD):
            collector.time_call(fail)
        for _ in range(50):
            collector.time_call(succeed)

        snap = collector.snapshot()
        assert snap.excluded_count == 5  # warmup failures excluded
        assert snap.call_count == 45     # 50 ok - 5 warmup discard

    def test_manual_exclude_call(self):
        """collector.exclude() 增加排除计数（用于超时/熔断等外部事件）."""
        collector = PerfSampleCollector("host")
        for _ in range(WARMUP_DISCARD + 10):
            collector.add_sample(5.0)
        collector.exclude("timeout")
        collector.exclude("marker_corrupt")
        snap = collector.snapshot()
        assert snap.excluded_count == 2

    def test_failure_excluded_does_not_pollute_p95(self):
        """failure 样本不会污染 P95."""
        collector = PerfSampleCollector("mock")
        for _ in range(WARMUP_DISCARD):
            collector.add_sample(100.0)
        # Add 50 normal samples
        for i in range(50):
            collector.add_sample(float(i + 1))
        # Now add a failure (should be excluded, not added)
        collector.time_call(lambda: (_ for _ in ()).throw(RuntimeError("fail")))
        snap = collector.snapshot()
        # Sample count = 50 steady; the failed call was excluded
        assert snap.call_count == 50
        assert snap.excluded_count >= 1


# ---------------------------------------------------------------------------
# T3 — Mock baseline gate
# ---------------------------------------------------------------------------


class TestT3MockBaselineGate:
    def test_within_threshold_passes(self):
        """P95 上升 <10% → within_threshold=True."""
        baseline = PerfBaseline(snapshots={
            "mock": PerfSnapshot(
                path="mock", call_count=50,
                p50_ms=25.0, p95_ms=50.0, p99_ms=70.0,
                avg_ms=30.0, min_ms=10.0, max_ms=80.0,
                snapshot_id="v452_baseline",
            ),
        })
        # +6% (within 10% gate)
        current = PerfSnapshot(
            path="mock", call_count=50,
            p50_ms=26.0, p95_ms=53.0, p99_ms=72.0,
            avg_ms=31.0, min_ms=11.0, max_ms=85.0,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.delta_p95_pct == pytest.approx(6.0, rel=0.01)
        assert result.within_threshold is True

    def test_exceeds_threshold_blocks(self):
        """P95 上升 >10% → within_threshold=False."""
        baseline = PerfBaseline(snapshots={
            "mock": PerfSnapshot(
                path="mock", call_count=50,
                p50_ms=25.0, p95_ms=50.0, p99_ms=70.0,
                avg_ms=30.0, min_ms=10.0, max_ms=80.0,
                snapshot_id="v452_baseline",
            ),
        })
        # +50% (way over 10% gate)
        current = PerfSnapshot(
            path="mock", call_count=50,
            p50_ms=30.0, p95_ms=75.0, p99_ms=100.0,
            avg_ms=45.0, min_ms=15.0, max_ms=120.0,
            snapshot_id="current",
        )
        result = compare_to_baseline(current, baseline)
        assert result.delta_p95_pct == pytest.approx(50.0, rel=0.01)
        assert result.within_threshold is False

    def test_gate_thresholds_per_path(self):
        """GATE_THRESHOLDS 不同路径不同阈值（mock/host 10%, api 20%）."""
        assert GATE_THRESHOLDS["mock"] == 0.10
        assert GATE_THRESHOLDS["host"] == 0.10
        assert GATE_THRESHOLDS["api"] == 0.20
        assert GATE_THRESHOLDS["auto_fallback"] >= 1.00  # diagnostic only


# ---------------------------------------------------------------------------
# T4 — Host bridge baseline (50 samples, exclude corrupted marker)
# ---------------------------------------------------------------------------


class TestT4HostBridgeBaseline:
    def test_sample_count_for_host_is_50(self):
        """SAMPLE_COUNTS[host] = 50."""
        assert SAMPLE_COUNTS["host"] == 50

    def test_host_collector_handles_marker_corruption(self):
        """Host Bridge 场景：marker 损坏 >3 重试 → exclude."""
        collector = PerfSampleCollector("host")

        # Warmup + steady
        for _ in range(WARMUP_DISCARD):
            collector.add_sample(20.0)
        for i in range(50):
            collector.add_sample(float(i + 5))

        # Corrupted marker → exclude (3 retries wasted)
        for _ in range(3):
            collector.exclude("marker_corrupt_retry")

        snap = collector.snapshot()
        assert snap.call_count == 50
        assert snap.excluded_count == 3  # corrupted retries excluded

    def test_host_collector_snapshot_fields_complete(self):
        """Snapshot 字段齐全：p50/p95/p99/avg/min/max/call_count/excluded."""
        collector = PerfSampleCollector("host")
        for i in range(WARMUP_DISCARD + 30):
            collector.add_sample(float(i + 1))
        snap = collector.snapshot()
        assert snap.path == "host"
        assert snap.call_count == 30
        assert snap.p50_ms >= 0
        assert snap.p95_ms >= snap.p50_ms
        assert snap.p99_ms >= snap.p95_ms
        assert snap.avg_ms >= 0
        assert snap.min_ms >= 0
        assert snap.max_ms >= snap.p95_ms


# ---------------------------------------------------------------------------
# T5 — Snapshot fields (contract for details["perf_snapshot"])
# ---------------------------------------------------------------------------


class TestT5SnapshotFields:
    def test_snapshot_required_fields(self):
        """所有必需字段（path/call_count/p50/p95/p99/avg/min/max）存在."""
        snap = PerfSnapshot(
            path="mock",
            call_count=50,
            p50_ms=10.0,
            p95_ms=20.0,
            p99_ms=30.0,
            avg_ms=15.0,
            min_ms=5.0,
            max_ms=40.0,
        )
        d = snap.to_dict()
        assert d["path"] == "mock"
        assert d["call_count"] == 50
        assert d["p50_ms"] == 10.0
        assert d["p95_ms"] == 20.0
        assert d["p99_ms"] == 30.0
        assert d["avg_ms"] == 15.0
        assert d["min_ms"] == 5.0
        assert d["max_ms"] == 40.0
        # Optional but present (default values)
        assert "excluded_count" in d
        assert "snapshot_id" in d
        assert "timestamp" in d
        assert "baseline_p95_ms" in d
        assert "delta_p95_pct" in d
        assert "within_threshold" in d

    def test_baseline_round_trip_json(self):
        """Baseline save/load 必须 round-trip 完整。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "baseline.json")
            original = PerfBaseline(
                version="v4.5.2",
                snapshots={
                    "mock": PerfSnapshot(
                        path="mock", call_count=50,
                        p50_ms=10, p95_ms=20, p99_ms=30,
                        avg_ms=15, min_ms=5, max_ms=40,
                        snapshot_id="test_baseline",
                    ),
                    "host": PerfSnapshot(
                        path="host", call_count=50,
                        p50_ms=20, p95_ms=40, p99_ms=60,
                        avg_ms=30, min_ms=10, max_ms=80,
                        snapshot_id="test_baseline",
                    ),
                },
            )
            original.save(path)
            loaded = PerfBaseline.load(path)
            assert loaded.version == "v4.5.2"
            assert "mock" in loaded.snapshots
            assert "host" in loaded.snapshots
            assert loaded.snapshots["mock"].p95_ms == 20.0
            assert loaded.snapshots["host"].p95_ms == 40.0

    def test_baseline_load_missing_file_returns_empty(self):
        """Baseline 文件缺失 → 返回空 baseline（不抛异常）。"""
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "nonexistent.json")
            baseline = PerfBaseline.load(path)
            assert baseline.snapshots == {}
            assert baseline.version == "v4.5.2"

    def test_default_baseline_path_constant(self):
        """DEFAULT_BASELINE_PATH 指向 docs/reference/."""
        assert "PERFORMANCE_BASELINE" in DEFAULT_BASELINE_PATH

    def test_compare_against_missing_path_is_noop(self):
        """compare_to_baseline 对缺失路径保持原 snapshot（不做 delta 计算）."""
        baseline = PerfBaseline(snapshots={})  # no entries
        snap = PerfSnapshot(
            path="mock", call_count=10,
            p50_ms=10, p95_ms=20, p99_ms=30,
            avg_ms=15, min_ms=5, max_ms=40,
        )
        result = compare_to_baseline(snap, baseline)
        # Should be unchanged (delta_p95_pct=None)
        assert result.delta_p95_pct is None
        assert result.baseline_p95_ms is None
        assert result.within_threshold is None


# ---------------------------------------------------------------------------
# Anti-Ghost + path validation
# ---------------------------------------------------------------------------


class TestAntiGhostAndPathValidation:
    def test_call_counter_increments(self):
        """collect/compare 每次让 _call_counter 增加。"""
        before = get_call_counter()
        collector = PerfSampleCollector("mock")
        collector.add_sample(10.0)
        collector.snapshot()
        baseline = PerfBaseline()
        snap = collector.snapshot()
        compare_to_baseline(snap, baseline)
        after = get_call_counter()
        assert after > before

    def test_invalid_path_raises(self):
        """未知 path → ValueError."""
        with pytest.raises(ValueError, match="Unknown path"):
            PerfSampleCollector("unknown_path")

    def test_sample_counts_all_paths(self):
        """SAMPLE_COUNTS 涵盖所有 4 个路径。"""
        assert set(SAMPLE_COUNTS.keys()) == {"mock", "host", "api", "auto_fallback"}
