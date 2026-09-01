"""Unit tests for V4.5.12 --severity removal (AC-SE-1..4) + risks stats CLI.

Covers:
- cmd_risks_stats text + json output (AC-SQL-5)
- _filter_risks behavior without --severity (category/min-exposure only)
"""

from __future__ import annotations

import json
from argparse import Namespace
from pathlib import Path

import pytest

import scripts.cli_risks as cli_risks
from scripts.cli_risks import _filter_risks, cmd_risks_stats

pytestmark = pytest.mark.unit


def _args(**kwargs) -> Namespace:
    defaults = {"format": "text", "min_exposure": None, "category": None}
    defaults.update(kwargs)
    return Namespace(**defaults)


class _Risk:
    def __init__(self, exposure: float, category: str = "general") -> None:
        self.exposure = exposure
        self.category = category


class TestFilterRisksWithoutSeverity:
    def test_no_flags_returns_all(self) -> None:
        risks = [_Risk(0.2), _Risk(0.8)]
        assert _filter_risks(risks, _args()) == risks

    def test_min_exposure_filter(self) -> None:
        low, high = _Risk(0.2), _Risk(0.8)
        assert _filter_risks([low, high], _args(min_exposure=0.5)) == [high]

    def test_category_filter_case_insensitive(self) -> None:
        sec = _Risk(0.5, category="Security")
        gen = _Risk(0.5, category="general")
        assert _filter_risks([sec, gen], _args(category="security")) == [sec]

    def test_no_severity_attribute_needed(self) -> None:
        # _filter_risks must work without a `severity` attribute at all.
        assert _filter_risks([_Risk(0.5)], _args()) is not None


class TestRisksStatsCli:
    @pytest.fixture(autouse=True)
    def _isolated_store(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        monkeypatch.setattr(cli_risks, "DEFAULT_ROOT", tmp_path)
        self.root = tmp_path
        yield

    def test_stats_text_output(self, capsys) -> None:
        rc = cmd_risks_stats(_args(register_id="default", root=str(self.root)))
        out = capsys.readouterr().out
        assert rc == 0
        assert "Risk Store Stats" in out
        assert "capacity:" in out
        assert "concurrent_writes_1m:" in out
        assert "cross_host_lock_signals:" in out
        assert "slow_query_signals:" in out

    def test_stats_json_output(self, capsys) -> None:
        rc = cmd_risks_stats(_args(register_id="default", root=str(self.root), format="json"))
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload["register_id"] == "default"
        for key in ("capacity", "concurrent_writes_1m", "cross_host_lock_signals",
                    "slow_query_signals", "last_updated"):
            assert key in payload
