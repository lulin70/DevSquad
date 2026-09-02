"""Unit tests for V4.5.15 verify_prometheus_e2e.py (AC-PM-1..3)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import scripts.verify_prometheus_e2e as verifier  # noqa: E402

pytestmark = pytest.mark.unit


class TestFindBinaries:
    def test_missing_binaries_reported(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(verifier.shutil, "which", lambda _n: None)
        monkeypatch.setattr(verifier, "BREW_BIN_DIRS", (str(tmp_path),))
        found = verifier.find_binaries()
        assert found == {"prometheus": None, "promtool": None}

    def test_brew_prefix_fallback(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(verifier.shutil, "which", lambda _n: None)
        (tmp_path / "promtool").write_text("#!/bin/sh\n")
        monkeypatch.setattr(verifier, "BREW_BIN_DIRS", (str(tmp_path),))
        found = verifier.find_binaries()
        assert found["promtool"] == str(tmp_path / "promtool")
        assert found["prometheus"] is None


class TestRunE2EStatuses:
    def test_tool_missing_is_honest_non_pass(self, monkeypatch) -> None:
        monkeypatch.setattr(
            verifier, "find_binaries",
            lambda: {"prometheus": None, "promtool": None},
        )
        result = verifier.run_e2e()
        assert result["status"] == "tool_missing"
        assert "brew install prometheus" in result["error"]

    def test_fail_contract_never_reports_pass_without_samples(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """query_series returning only errors must NOT be treated as pass."""
        monkeypatch.setattr(
            verifier, "find_binaries",
            lambda: {"prometheus": "prom", "promtool": "tool"},
        )
        monkeypatch.setattr(
            verifier, "build_exposition_provider", lambda: (lambda: b""))

        def _fake_config(_wd: Path, _ep: int, _lp: int) -> Path:
            return Path(_wd) / "prometheus.yml"

        def _fake_run(*_a: object, **_k: object) -> object:
            return type("R", (), {"returncode": 0, "stdout": b"", "stderr": b""})()

        class _FakeProc:
            def terminate(self) -> None:
                pass

            def wait(self, *_a: object, **_k: object) -> int:
                return 0

            def kill(self) -> None:
                pass

        monkeypatch.setattr(
            verifier, "serve_exposition",
            lambda _p: (None, 19999),
        )
        monkeypatch.setattr(verifier, "write_prometheus_config", _fake_config)
        # pretend promtool passes but prometheus readiness never comes
        monkeypatch.setattr(verifier.subprocess, "run", _fake_run)
        monkeypatch.setattr(verifier.subprocess, "Popen", lambda *_a, **_k: _FakeProc())
        monkeypatch.setattr(
            verifier, "_wait_prometheus_ready",
            lambda *_a: None,
        )
        monkeypatch.setattr(
            verifier, "query_series",
            lambda *_a: [{"error": "no sample"}],
        )
        monkeypatch.setattr(verifier.shutil, "rmtree", lambda *_a, **_k: None)
        result = verifier.run_e2e()
        assert result["status"] == "fail"
        assert "no sample" in result["error"]


class TestExpositionAndConfig:
    def test_exposition_provider_contains_risk_store_series(
        self, tmp_path: Path
    ) -> None:
        from scripts.collaboration.prometheus_metrics import get_metrics

        if not get_metrics().is_available():
            pytest.skip("prometheus_client not installed")
        provider = verifier.build_exposition_provider()
        body = provider().decode("utf-8")
        assert "devsquad_v4512_risk_store_cross_host_signals_total" in body
        assert "devsquad_v4512_risk_store_capacity" in body

    def test_config_contains_job_and_target(self, tmp_path: Path) -> None:
        config = verifier.write_prometheus_config(tmp_path, 19000, 19001)
        text = config.read_text(encoding="utf-8")
        assert "job_name: devsquad_e2e" in text
        assert "127.0.0.1:19000" in text
        assert "scrape_interval: 1s" in text


class TestMainContract:
    def test_tool_missing_exits_1_and_writes_evidence(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        monkeypatch.setattr(
            verifier, "find_binaries",
            lambda: {"prometheus": None, "promtool": None},
        )
        evidence = tmp_path / "evidence"
        rc = verifier.main(["--evidence-dir", str(evidence)])
        assert rc == 1
        out = capsys.readouterr().out
        assert "tool_missing" in out
        result = (evidence / "result.json").read_text(encoding="utf-8")
        assert '"status": "tool_missing"' in result
