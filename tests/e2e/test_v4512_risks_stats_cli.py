"""E2E tests for V4.5.12 risks stats CLI + metrics inventory (AC-SQL-5, AC-SQL-6).

Real subprocess journeys:
- `python3 -m scripts.cli_risks risks stats --format text|json`
- `python3 -m scripts.cli metrics --format json` exposes 4 v4512 metrics
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

pytestmark = pytest.mark.e2e

V4512_METRIC_NAMES = [
    "devsquad_v4512_risk_store_capacity",
    "devsquad_v4512_risk_store_concurrent_writes_total",
    "devsquad_v4512_risk_store_cross_host_signals_total",
    "devsquad_v4512_risk_store_slow_queries_total",
]


def _run_cli(argv: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *argv],
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=120,
    )


CLI = PROJECT_ROOT / "scripts" / "cli.py"


class TestRisksStatsCliJourney:
    def test_stats_text_journey(self, tmp_path: Path) -> None:
        proc = _run_cli(["-m", "scripts.cli_risks", "risks", "stats", "--format", "text",
                         "--root", str(tmp_path)], PROJECT_ROOT)
        assert proc.returncode == 0, proc.stderr
        assert "Risk Store Stats" in proc.stdout
        assert "capacity:" in proc.stdout

    def test_stats_json_journey(self, tmp_path: Path) -> None:
        proc = _run_cli(["-m", "scripts.cli_risks", "risks", "stats", "--format", "json",
                         "--root", str(tmp_path)], PROJECT_ROOT)
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        for key in ("capacity", "concurrent_writes_1m", "cross_host_lock_signals",
                    "slow_query_signals"):
            assert key in payload

    def test_add_then_stats_capacity_visible(self, tmp_path: Path) -> None:
        add = _run_cli(
            ["-m", "scripts.cli_risks", "risks", "add", "e2e risk",
             "--probability", "0.5", "--impact", "0.5",
             "--category", "general", "--owner", "architect",
             "--root", str(tmp_path)],
            PROJECT_ROOT,
        )
        assert add.returncode == 0, add.stderr
        stats = _run_cli(["-m", "scripts.cli_risks", "risks", "stats", "--format", "json",
                          "--root", str(tmp_path)], PROJECT_ROOT)
        assert stats.returncode == 0, stats.stderr
        payload = json.loads(stats.stdout)
        assert payload["capacity"] == 1


class TestMetricsInventory:
    def test_metrics_json_exposes_v4512_inventory(self) -> None:
        proc = _run_cli([str(CLI), "metrics", "--format", "json"], PROJECT_ROOT)
        assert proc.returncode == 0, proc.stderr
        payload = json.loads(proc.stdout)
        names = {m["name"] for m in payload["metrics"]}
        for metric in V4512_METRIC_NAMES:
            assert metric in names, metric
        assert payload["version"] == "V4.5.12"

    def test_metrics_text_exposes_v4512_inventory(self) -> None:
        proc = _run_cli([str(CLI), "metrics", "--format", "text"], PROJECT_ROOT)
        assert proc.returncode == 0, proc.stderr
        for metric in V4512_METRIC_NAMES:
            assert metric in proc.stdout, metric
