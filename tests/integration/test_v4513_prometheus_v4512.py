"""Integration tests for V4.5.13 /metrics exposure of v4512 risk-store series."""

from __future__ import annotations

from pathlib import Path

import pytest

from scripts.collaboration.file_risk_store import FileRiskStore
from scripts.collaboration.prometheus_metrics import get_metrics

pytestmark = pytest.mark.integration

SERIES = [
    "devsquad_v4512_risk_store_capacity",
    "devsquad_v4512_risk_store_concurrent_writes_total",
    "devsquad_v4512_risk_store_cross_host_signals_total",
    "devsquad_v4512_risk_store_slow_queries_total",
]


def _payload(items: int) -> dict:
    return {
        "version": 1,
        "register_id": "default",
        "items": [
            {"id": f"R-{i}", "description": f"r{i}", "probability": 0.5, "impact": 0.5,
             "response_strategy": "accept", "owner": "architect", "status": "open",
             "category": "general"}
            for i in range(items)
        ],
    }


def _body_text(metrics: object) -> str:
    raw = metrics.generate_metrics()
    return raw.decode() if isinstance(raw, bytes) else raw


class TestRegistryExposition:
    def test_generate_metrics_contains_all_series(self, tmp_path: Path) -> None:
        metrics = get_metrics()
        if not metrics.is_available():
            pytest.skip("prometheus_client not installed")
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(2))
        store.stats.record_cross_host_signal()
        store.stats.record_slow_query(80.0)
        metrics.record_risk_store_stats(store.stats)
        body = _body_text(metrics)
        for name in SERIES:
            assert name in body, name

    def test_record_is_delta_based_no_double_count(self, tmp_path: Path) -> None:
        metrics = get_metrics()
        if not metrics.is_available():
            pytest.skip("prometheus_client not installed")
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(1))
        metrics.record_risk_store_stats(store.stats)
        metrics.record_risk_store_stats(store.stats)  # same snapshot → no extra inc
        body = _body_text(metrics)
        line = next(
            ln for ln in body.splitlines()
            if ln.startswith("devsquad_v4512_risk_store_concurrent_writes_total{")
        )
        assert line.rstrip().endswith("1.0")

    def test_capacity_gauge_tracks_value(self, tmp_path: Path) -> None:
        metrics = get_metrics()
        if not metrics.is_available():
            pytest.skip("prometheus_client not installed")
        store = FileRiskStore(root=tmp_path)
        store.save("default", _payload(7))
        metrics.record_risk_store_stats(store.stats)
        body = _body_text(metrics)
        line = next(
            ln for ln in body.splitlines()
            if ln.startswith("devsquad_v4512_risk_store_capacity{")
        )
        assert line.rstrip().endswith("7.0")


class TestMetricsEndpointSmoke:
    def test_metrics_endpoint_contains_v4512_series(self) -> None:
        pytest.importorskip("fastapi")
        pytest.importorskip("prometheus_client")
        import os

        from fastapi.testclient import TestClient

        from scripts.api_server import app  # noqa: F401 — app factory import

        os.environ.setdefault("DEVSQUAD_API_AUTH_DISABLED", "1")
        client = TestClient(app)
        resp = client.get("/metrics")
        assert resp.status_code == 200
        assert "devsquad_v4512_risk_store_capacity" in resp.text
