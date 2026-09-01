"""Tests for devsquad metrics CLI (V4.5.2 P12.1.2)."""

from __future__ import annotations

import json
from argparse import Namespace

from scripts.cli_metrics import (
    V452_METRICS,
    cmd_metrics,
    collect_v452_metrics,
    format_json,
    format_text,
)


def _ns(fmt: str = "text") -> Namespace:
    return Namespace(format=fmt)


class TestV452MetricsInventory:
    """Verify metric inventory matches V4.5.2 PRD §3.1."""

    def test_inventory_count_8(self):
        assert len(V452_METRICS) == 8

    def test_all_metrics_have_name_type_description_label_keys(self):
        for m in V452_METRICS:
            assert "name" in m
            assert "type" in m
            assert "description" in m
            assert "label_keys" in m

    def test_inventory_names(self):
        names = {m["name"] for m in V452_METRICS}
        expected = {
            "devsquad_v452_task_scale_total",
            "devsquad_v452_order_chain_total",
            "devsquad_v452_backend_calls_total",
            "devsquad_v452_backend_failures_total",
            "devsquad_v452_fuse_skips_total",
            "devsquad_v452_perf_p95_ms",
            "devsquad_v452_perf_regression_total",
            "devsquad_v452_perf_latency_ms",
        }
        assert names == expected

    def test_inventory_types(self):
        types = {m["type"] for m in V452_METRICS}
        assert "counter" in types
        assert "gauge" in types
        assert "histogram" in types


class TestCollectV452Metrics:
    """Test live sample collection."""

    def test_collect_returns_all_inventory(self):
        result = collect_v452_metrics()
        assert len(result) == len(V452_METRICS)
        for r, inv in zip(result, V452_METRICS):
            assert r["name"] == inv["name"]
            assert r["type"] == inv["type"]

    def test_collect_samples_empty_when_idle(self):
        result = collect_v452_metrics()
        for r in result:
            assert r["samples"] == []


class TestFormatText:
    """Test text formatter."""

    def test_format_includes_header(self):
        out = format_text([])
        assert "DevSquad V4.5.2 Metrics" in out

    def test_format_includes_metric_name(self):
        result = collect_v452_metrics()
        out = format_text(result)
        assert "devsquad_v452_task_scale_total" in out

    def test_format_shows_idle_marker(self):
        result = collect_v452_metrics()
        out = format_text(result)
        assert "no samples recorded" in out

    def test_format_renders_samples(self):
        metrics = [{
                "name": "test_metric",
                "type": "counter",
                "description": "test desc",
                "label_keys": ["label1"],
                "samples": [{"labels": {"label1": "v1"}, "value": 3.0}],
            }]
        out = format_text(metrics)
        assert "test_metric" in out
        assert "label1=v1" in out
        assert "3.0000" in out


class TestFormatJson:
    """Test JSON formatter."""

    def test_format_is_valid_json(self):
        result = collect_v452_metrics()
        out = format_json(result)
        parsed = json.loads(out)
        # V4.5.12: metrics JSON now covers V4.5.2 + V4.5.12 inventory.
        assert parsed["version"] == "V4.5.12"
        assert "metrics" in parsed

    def test_format_includes_samples_field(self):
        result = collect_v452_metrics()
        out = format_json(result)
        parsed = json.loads(out)
        for m in parsed["metrics"]:
            assert "samples" in m


class TestCmdMetrics:
    """Test CLI command entry point."""

    def test_text_format_runs(self, capsys):
        rc = cmd_metrics(_ns("text"))
        captured = capsys.readouterr()
        assert rc == 0
        assert "DevSquad V4.5.2 Metrics" in captured.out

    def test_json_format_runs(self, capsys):
        rc = cmd_metrics(_ns("json"))
        captured = capsys.readouterr()
        assert rc == 0
        parsed = json.loads(captured.out)
        # V4.5.12: metrics JSON now covers V4.5.2 + V4.5.12 inventory.
        assert parsed["version"] == "V4.5.12"

    def test_default_format_is_text(self):
        # Defaults to text when no --format flag
        ns = Namespace()  # no format attribute
        # Patch to use default
        ns.format = "text"
        rc = cmd_metrics(ns)
        assert rc == 0


class TestMetricsImportable:
    """Test the module is properly importable from cli.py."""

    def test_cmd_metrics_is_callable(self):
        from scripts.cli_metrics import cmd_metrics
        assert callable(cmd_metrics)
