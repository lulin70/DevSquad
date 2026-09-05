#!/usr/bin/env python3
"""V4.6.0-doc-governance P1: Bandit CI gate wrapper tests.

These tests pin the behavior of scripts/check_bandit.py without invoking
bandit directly (which may be missing or behave differently in sandboxes).

Three contract assertions:

  1. Empty / unparseable bandit output → exit 1 (fail-closed)
  2. Parseable report with HIGH=0, MEDIUM=0 → exit 0
  3. Parseable report with HIGH>0 or MEDIUM>0 → exit 1

Test isolation:
  - All subprocess calls are mocked via ``unittest.mock.patch`` on
    ``subprocess.run`` inside ``scripts.check_bandit``.
  - Temporary JSON report paths in tmp_path keep the artifacts in pytest's
    auto-cleaned tmp tree.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import check_bandit  # noqa: E402

pytestmark = pytest.mark.unit


def _make_bandit_report(high: int = 0, medium: int = 0, low: int = 0) -> dict:
    """Build a minimal bandit JSON report with the given severity counts.

    Uses bandit 1.9.x schema (``SEVERITY.HIGH/MEDIUM/LOW``) under
    ``metrics._totals``. Falls back to legacy ``HIGH/MEDIUM/LOW`` keys for
    older bandit versions.
    """
    return {
        "results": [],
        "metrics": {
            "_totals": {
                "SEVERITY.HIGH": high,
                "SEVERITY.MEDIUM": medium,
                "SEVERITY.LOW": low,
                "HIGH": high,
                "MEDIUM": medium,
                "LOW": low,
                "loc": 1000,
                "nosec": 0,
            }
        },
    }


def _run_check_bandit(args: list[str], mock_proc: subprocess.CompletedProcess) -> int:
    """Run check_bandit.main() with subprocess.run patched to return mock_proc."""
    with patch.object(check_bandit.subprocess, "run", return_value=mock_proc):
        return check_bandit.main(args)


class TestScanCleanCheck:
    """T1: scan_clean logic — empty / unparseable reports must fail closed."""

    def test_empty_dict_is_not_clean(self):
        assert check_bandit._is_scan_clean({}) is False

    def test_none_is_not_clean(self):
        assert check_bandit._is_scan_clean(None) is False  # type: ignore[arg-type]

    def test_missing_results_is_not_clean(self):
        report = {"metrics": {"_totals": {"HIGH": 0, "MEDIUM": 0, "LOW": 0}}}
        assert check_bandit._is_scan_clean(report) is False

    def test_missing_metrics_is_not_clean(self):
        report = {"results": []}
        assert check_bandit._is_scan_clean(report) is False

    def test_complete_report_is_clean(self):
        report = _make_bandit_report()
        assert check_bandit._is_scan_clean(report) is True


class TestSummarize:
    """T2: _summarize extracts severity counts correctly."""

    def test_zero_counts(self):
        high, medium, low_count = check_bandit._summarize(_make_bandit_report())
        assert (high, medium, low_count) == (0, 0, 0)

    def test_with_findings(self):
        high, medium, low_count = check_bandit._summarize(
            _make_bandit_report(high=2, medium=5, low=101)
        )
        assert (high, medium, low_count) == (2, 5, 101)

    def test_missing_totals_returns_zeros(self):
        report = {"results": [], "metrics": {}}
        high, medium, low_count = check_bandit._summarize(report)
        assert (high, medium, low_count) == (0, 0, 0)


class TestExitCodes:
    """T3-T5: main() exit codes for each branch."""

    def test_clean_report_with_no_findings_exits_zero(self, tmp_path):
        report = _make_bandit_report()
        proc = subprocess.CompletedProcess(
            args=["bandit"], returncode=0,
            stdout=json.dumps(report), stderr="",
        )
        rc = _run_check_bandit(
            ["--source", "scripts/", "--report", str(tmp_path / "r.json")],
            proc,
        )
        assert rc == 0

    def test_low_only_findings_pass(self, tmp_path):
        """LOW severity is reported but not blocking by default."""
        report = _make_bandit_report(low=101)
        proc = subprocess.CompletedProcess(
            args=["bandit"], returncode=0,
            stdout=json.dumps(report), stderr="",
        )
        rc = _run_check_bandit(
            ["--source", "scripts/", "--report", str(tmp_path / "r.json")],
            proc,
        )
        assert rc == 0

    def test_medium_findings_block_with_fail_on_medium(self, tmp_path):
        report = _make_bandit_report(medium=1)
        proc = subprocess.CompletedProcess(
            args=["bandit"], returncode=1,
            stdout=json.dumps(report), stderr="",
        )
        rc = _run_check_bandit(
            ["--source", "scripts/", "--report", str(tmp_path / "r.json")],
            proc,
        )
        assert rc == 1

    def test_high_findings_always_block(self, tmp_path):
        report = _make_bandit_report(high=1)
        proc = subprocess.CompletedProcess(
            args=["bandit"], returncode=1,
            stdout=json.dumps(report), stderr="",
        )
        # Even with --no-fail-on-medium, HIGH blocks
        rc = _run_check_bandit(
            ["--source", "scripts/", "--report", str(tmp_path / "r.json"),
             "--no-fail-on-medium"],
            proc,
        )
        assert rc == 1

    def test_empty_stdout_fails_closed(self, tmp_path):
        """Critical: bandit returns empty stdout in restricted sandboxes."""
        proc = subprocess.CompletedProcess(
            args=["bandit"], returncode=1,
            stdout="", stderr="bandit crashed",
        )
        rc = _run_check_bandit(
            ["--source", "scripts/", "--report", str(tmp_path / "r.json")],
            proc,
        )
        # Must NOT be 0 (that would falsely report PASS)
        assert rc == 1
        # Report file should still be written (even if empty {}) so CI can inspect
        assert (tmp_path / "r.json").exists()

    def test_unparseable_json_fails_closed(self, tmp_path):
        """Bandit returned something, but not valid JSON."""
        proc = subprocess.CompletedProcess(
            args=["bandit"], returncode=1,
            stdout="this is not json at all {{{", stderr="",
        )
        rc = _run_check_bandit(
            ["--source", "scripts/", "--report", str(tmp_path / "r.json")],
            proc,
        )
        assert rc == 1


class TestBanditBinaryPresence:
    """T6: bandit installation is enforced (exit 2 if missing)."""

    def test_missing_bandit_exits_2(self, tmp_path, monkeypatch):
        # Force shutil.which to return None for both bandit names
        import shutil
        monkeypatch.setattr(shutil, "which", lambda _name: None)
        rc = check_bandit.main([
            "--source", "scripts/",
            "--report", str(tmp_path / "r.json"),
        ])
        assert rc == 2


class TestEndToEndWithRealBandit:
    """T7 (smoke): if bandit is installed in the test environment, run it
    end-to-end and verify the report file is written.

    Skipped when bandit is not installed (CI sandbox often lacks it).
    """

    @pytest.mark.skipif(
        subprocess.run(["which", "bandit"], capture_output=True).returncode != 0,
        reason="bandit not installed in this environment",
    )
    def test_real_bandit_run_writes_report(self, tmp_path):
        report_path = tmp_path / "real.json"
        rc = check_bandit.main([
            "--source", str(REPO_ROOT / "scripts"),
            "--report", str(report_path),
            "--no-fail-on-medium",  # tolerate our known 7 MEDIUM/101 LOW
        ])
        # Should be 0 (no HIGH) when LOW+MEDIUM are tolerated
        assert rc == 0
        assert report_path.exists()
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        assert "metrics" in loaded
        totals = loaded["metrics"]["_totals"]
        assert totals["HIGH"] == 0  # V4.6.0-doc-governance baseline promise
