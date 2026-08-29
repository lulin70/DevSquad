"""V4.5.8 E2E — real-user risks CLI journey across independent processes.

Simulates a real user driving ``python3 -m scripts.cli_risks`` from separate
shell invocations (independent processes each time), covering the full PRD
journey: add → list → show → assess → mitigate → close(approval) → export →
clear, plus the exposure-threshold UX (``--min-exposure`` / ``--severity`` /
``--category``).

Each step is a fresh subprocess — this is the release-gate proof that the
file-backed store (V4.5.8 Wave 1) makes risk data visible across processes
and that destructive commands are fail-closed (V4.5.8 contract).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[2]

pytestmark = pytest.mark.e2e


def _run_cli(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(PROJECT_ROOT)
    return subprocess.run(
        [sys.executable, "-m", "scripts.cli_risks", *args],
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """A clean working directory whose .devsquad_data lives in tmp."""
    shutil.rmtree(tmp_path / ".devsquad_data", ignore_errors=True)
    return tmp_path


class TestRealUserJourney:
    def test_full_journey_add_to_clear(self, workspace: Path) -> None:
        """Independent-process journey: add → list → show → assess → mitigate
        → close (approval denied then granted) → export → clear."""
        cwd = workspace

        # 1. Process A: register a risk.
        add = _run_cli(
            [
                "risks", "add", "数据丢失风险",
                "--probability", "0.7", "--impact", "0.9",
                "--category", "technical", "--owner", "devops",
            ],
            cwd,
        )
        assert add.returncode == 0, add.stderr
        rid = json.loads(add.stdout)["id"]

        # 2. Process B: list sees it (cross-process persistence).
        listing = _run_cli(["risks", "list"], cwd)
        assert listing.returncode == 0
        assert listing.stdout.startswith("| Risk ID |")
        assert rid[:24] in listing.stdout  # Markdown table shows the id column

        # 3. Process B: drill into the risk.
        show = _run_cli(["risks", "show", rid], cwd)
        assert show.returncode == 0
        assert "0.70 x 0.90" in show.stdout

        # 4. Process C: multi-role assessment fuses both votes (weighted mean
        # of (0.8,0.9) and (0.6,0.8) lands between the two inputs).
        assess = _run_cli(
            ["risks", "assess", rid, "--votes", '{"architect":[0.8,0.9],"security":[0.6,0.8]}'],
            cwd,
        )
        assert assess.returncode == 0, assess.stderr
        assessed = json.loads(assess.stdout)
        assert 0.6 < assessed["probability"] < 0.8
        assert 0.8 < assessed["impact"] <= 0.9

        # 5. Process C: set the response strategy.
        mitigate = _run_cli(
            ["risks", "mitigate", rid, "--strategy", "mitigate",
             "--owner", "devops", "--plan", "add backup"],
            cwd,
        )
        assert mitigate.returncode == 0, mitigate.stderr
        assert json.loads(mitigate.stdout)["response_strategy"] == "mitigate"

        # 6. Process D: close requires approval; unavailable → fail-closed.
        denied = _run_cli(["risks", "close", rid, "--require-approval"], cwd)
        assert denied.returncode == 2
        assert "approval unavailable" in denied.stderr
        still_open = json.loads(_run_cli(["risks", "list", "--format", "json"], cwd).stdout)
        assert still_open[0]["status"] == "mitigating"

        # 7. Process D: approval callback granted → close succeeds.
        boot = (
            "import sys; sys.path.insert(0, " + repr(str(PROJECT_ROOT)) + "); "
            "import scripts.cli_risks as cr; "
            "cr._approval_allowed = lambda *a, **k: 0; "  # simulate granted approval
            "sys.exit(cr.main(['risks','close'," + repr(rid) + ",'--require-approval']))"
        )
        approved = subprocess.run(
            [sys.executable, "-c", boot],
            cwd=cwd,
            env=os.environ.copy(),
            text=True,
            capture_output=True,
            check=False,
        )
        assert approved.returncode == 0, approved.stderr
        after_close = json.loads(_run_cli(["risks", "list", "--format", "json"], cwd).stdout)
        assert after_close[0]["status"] == "closed"

        # 8. Process E: export includes the closed risk.
        export = _run_cli(["risks", "export", str(workspace / "risks.json")], cwd)
        assert export.returncode == 0
        exported = json.loads((workspace / "risks.json").read_text(encoding="utf-8"))
        assert [item["id"] for item in exported] == [rid]

        # 9. Process E: clear wipes the register.
        cleared = _run_cli(["risks", "clear"], cwd)
        assert cleared.returncode == 0
        assert "Cleared 1 risks" in cleared.stdout
        assert json.loads(_run_cli(["risks", "list", "--format", "json"], cwd).stdout) == []

    def test_exposure_threshold_filters_across_processes(self, workspace: Path) -> None:
        """--min-exposure boundary semantics: >= threshold, inclusive."""
        cwd = workspace
        for desc, p, i in [("low", "0.7", "0.5"), ("mid", "0.36", "1.0"), ("high", "0.9", "0.9")]:
            proc = _run_cli(
                ["risks", "add", desc, "--probability", p, "--impact", i,
                 "--category", "security", "--owner", "sec"],
                cwd,
            )
            assert proc.returncode == 0, proc.stderr

        # exposures: low=0.175, mid=0.36, high=0.81 (JSON output is unordered)
        at_boundary = json.loads(
            _run_cli(["risks", "list", "--format", "json", "--min-exposure", "0.36"], cwd).stdout
        )
        assert {item["description"] for item in at_boundary} == {"high", "mid"}

        below_boundary = json.loads(
            _run_cli(["risks", "list", "--format", "json", "--min-exposure", "0.35"], cwd).stdout
        )
        assert {item["description"] for item in below_boundary} == {"high", "mid", "low"}

        # Numeric --severity is equivalent to --min-exposure.
        by_severity = json.loads(
            _run_cli(["risks", "list", "--format", "json", "--severity", "0.36"], cwd).stdout
        )
        assert {item["description"] for item in by_severity} == {"high", "mid"}

        # Legacy category mode keeps working (with deprecation warning).
        legacy = _run_cli(["risks", "list", "--format", "json", "--severity", "security"], cwd)
        assert legacy.returncode == 0
        assert "deprecated" in legacy.stderr
        assert len(json.loads(legacy.stdout)) == 3

        # Invalid threshold values are rejected cleanly.
        for bad in ["nan", "inf", "-0.1", "1.1"]:
            proc = _run_cli(["risks", "list", "--min-exposure", bad], cwd)
            assert proc.returncode == 1, bad
            assert "Traceback" not in proc.stderr
