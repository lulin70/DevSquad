"""Unit tests for V4.5.12 RiskStoreStats (AC-SQL-1, AC-SQL-2).

Covers:
- stats attribute exists after __init__ (AC-SQL-1)
- load maintains capacity (AC-SQL-2)
- save/transaction maintain capacity + 60s sliding window (AC-SQL-2)
- sliding window expiry via monotonic patching
- to_dict is JSON-safe (no deque internals)
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.collaboration.file_risk_store import (
    CONCURRENT_WINDOW_SECONDS,
    FileRiskStore,
    RiskStoreStats,
    get_risk_store_stats_counter_er,
)

pytestmark = pytest.mark.unit


def _payload(register_id: str = "default", items: int = 0) -> dict:
    return {
        "version": 1,
        "register_id": register_id,
        "items": [
            {
                "id": f"R-{i}",
                "description": f"risk {i}",
                "probability": 0.5,
                "impact": 0.5,
                "response_strategy": "accept",
                "owner": "architect",
                "status": "open",
                "category": "general",
            }
            for i in range(items)
        ],
    }


class TestStatsAttribute:
    def test_stats_exists_after_init(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        assert isinstance(store.stats, RiskStoreStats)
        assert store.stats.capacity == 0
        assert store.stats.concurrent_writes_1m == 0
        assert store.stats.cross_host_lock_signals == 0
        assert store.stats.slow_query_signals == 0

    def test_load_maintains_capacity(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(items=3))
        store.load("default")
        assert store.stats.capacity == 3

    def test_save_maintains_capacity_and_window(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(items=2))
        assert store.stats.capacity == 2
        assert store.stats.concurrent_writes_1m == 1
        store.save("default", _payload(items=4))
        assert store.stats.capacity == 4
        assert store.stats.concurrent_writes_1m == 2

    def test_transaction_path_updates_window(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        with store.transaction("default") as tx:
            tx["items"] = _payload(items=1)["items"]
        assert store.stats.concurrent_writes_1m >= 1

    def test_sliding_window_expiry(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        store = FileRiskStore(root=tmp_path)
        clock = {"now": 1000.0}
        monkeypatch.setattr(
            "scripts.collaboration.file_risk_store.time.monotonic",
            lambda: clock["now"],
        )
        store.save("default", _payload(items=1))
        store.save("default", _payload(items=1))
        assert store.stats.concurrent_writes_1m == 2
        # Advance past the 60s window.
        clock["now"] += CONCURRENT_WINDOW_SECONDS + 1.0
        store.save("default", _payload(items=1))
        assert store.stats.concurrent_writes_1m == 1

    def test_window_constant_is_60s(self) -> None:
        assert CONCURRENT_WINDOW_SECONDS == 60.0


class TestStatsSignals:
    def test_cross_host_signal_counter(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        assert store.stats.cross_host_lock_signals == 0
        store.stats.record_cross_host_signal()
        store.stats.record_cross_host_signal()
        assert store.stats.cross_host_lock_signals == 2

    def test_slow_query_signal_threshold(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        store.stats.record_slow_query(10.0)
        assert store.stats.slow_query_signals == 0
        store.stats.record_slow_query(51.0)
        assert store.stats.slow_query_signals == 1

    def test_to_dict_is_json_safe(self, tmp_path: Path) -> None:
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(items=2))
        store.stats.record_cross_host_signal()
        payload = json.dumps(store.stats.to_dict())
        data = json.loads(payload)
        assert data["capacity"] == 2
        assert data["cross_host_lock_signals"] == 1
        assert "concurrent_writes_1m" in data


class TestStatsAntiGhostCounter:
    def test_counter_bumped_by_store_paths(self, tmp_path: Path) -> None:
        before = get_risk_store_stats_counter_er()
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(items=1))
        store.load("default")
        with store.transaction("default"):
            pass
        assert get_risk_store_stats_counter_er() > before
