"""E2E tests — risks CLI real-user simulation (V4.5.7 P5).

Simulates a real shell user invoking ``devsquad risks`` subcommands in
sequence: add → list → show → export → clear, verifying exit codes and
human-readable output formats along the way. Uses the standalone
``main()`` entry (same code path as ``python3 scripts/cli_risks.py``).

V4.5.11: the V4.5.7 in-process ``_RISK_STORE`` proxy was removed; tests now
read the file-backed store directly via FileRiskStore.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import scripts.cli_risks as cli_risks
from scripts.cli_risks import add_risk, main
from scripts.collaboration.file_risk_store import FileRiskStore

pytestmark = pytest.mark.e2e


@pytest.fixture(autouse=True)
def _clean_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Isolate the file-backed store in a tmp root (never the real data dir)."""
    monkeypatch.setattr(cli_risks, "DEFAULT_ROOT", tmp_path)
    yield
    store = FileRiskStore(root=tmp_path)
    with store.transaction("default") as transaction:
        transaction["items"] = []


def _count(tmp_path: Path) -> int:
    return len(FileRiskStore(root=tmp_path).load("default").get("items", []))


class TestRisksCliUserJourney:
    def test_user_journey_add_list_show_clear(self, capsys, tmp_path: Path):
        """A user registers risks from a retrospective, reviews them, inspects
        the top risk, then clears the register."""
        rid = add_risk(
            "async lock ordering regression", probability=0.6, impact=0.8
        )
        add_risk("cli export path traversal", probability=0.2, impact=0.5)

        # 1. list — user sees a Markdown table
        assert main(["risks", "list"]) == 0
        out = capsys.readouterr().out
        assert out.startswith("| Risk ID |")

        # 2. show — user drills into one risk
        assert main(["risks", "show", rid]) == 0
        out = capsys.readouterr().out
        assert "async lock ordering regression" in out

        # 3. clear — user wipes the register
        assert main(["risks", "clear"]) == 0
        assert "Cleared 2 risks" in capsys.readouterr().out
        assert _count(tmp_path) == 0

    def test_user_journey_export_to_file(self, capsys, tmp_path):
        """A user exports the register for a weekly report."""
        add_risk("reportable risk", probability=0.4, impact=0.7)
        target = tmp_path / "weekly-risks.json"

        assert main(["risks", "export", str(target)]) == 0
        capsys.readouterr()

        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload[0]["description"] == "reportable risk"
        assert payload[0]["exposure"] == pytest.approx(0.28)

    def test_user_journey_missing_risk_errors_cleanly(self, capsys):
        """A user typos a risk id and gets exit code 1 with a stderr message,
        not a traceback."""
        assert main(["risks", "show", "R-TYPO-999"]) == 1
        err = capsys.readouterr().err
        assert "not found" in err
