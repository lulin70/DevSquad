"""Unit tests for V4.5.8 Wave 2 CLI mutators (add/assess/mitigate/close).

The mutator tests exercise the new ``devsquad risks add|assess|mitigate|close``
subcommands against a per-test temp ``FileRiskStore`` root, so file-backed
persistence behaves exactly like Python API writes.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts.cli_risks import (
    cmd_risks_add,
    cmd_risks_assess,
    cmd_risks_close,
    cmd_risks_mitigate,
)
from scripts.collaboration.file_risk_store import FileRiskStore
from scripts.collaboration.risk_register import RiskItem

pytestmark = pytest.mark.unit


@pytest.fixture
def risk_store_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Each test gets a fresh `.devsquad_data/risks/` directory."""
    root = tmp_path / ".devsquad_data" / "risks"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DEVSQUAD_RISK_ROOT", str(root))
    # Reset the FileRiskStore.DEFAULT_ROOT reader by patching helpers
    from scripts import cli_risks

    monkeypatch.setattr(cli_risks, "DEFAULT_ROOT", root, raising=False)
    return root


def _args(**kwargs: object) -> argparse.Namespace:
    defaults = {
        "register_id": "default",
        "root": None,
        "require_approval": False,
        "approval_callback": None,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestAddCommand:
    def test_add_writes_persistent_item(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = _args(
            description="data loss",
            probability=0.7,
            impact=0.9,
            category="technical",
            owner="devops",
        )
        rc = cmd_risks_add(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["description"] == "data loss"
        assert payload["exposure"] == pytest.approx(0.63)

        store = FileRiskStore(root=risk_store_root)
        loaded = store.load("default")
        assert len(loaded["items"]) == 1
        assert loaded["items"][0]["description"] == "data loss"

    def test_add_rejects_non_finite_probability(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_risks_add(_args(description="bad", probability=float("nan"), impact=0.5, category="x", owner="y"))
        assert rc == 1
        assert "ERROR:" in capsys.readouterr().err

    def test_add_rejects_out_of_range_impact(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_risks_add(_args(description="bad", probability=0.5, impact=1.5, category="x", owner="y"))
        assert rc == 1
        assert "ERROR:" in capsys.readouterr().err


class TestAssessCommand:
    def test_assess_with_votes_json(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        # Seed an item via Python API.
        store = FileRiskStore(root=risk_store_root)
        with store.transaction("default") as tx:
            tx["items"] = [RiskItem(id="R-seed", description="seed", probability=0.0, impact=0.0).to_dict()]
        rc = cmd_risks_assess(_args(risk_id="R-seed", votes='{"architect":[0.6,0.8]}'))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["probability"] == pytest.approx(0.6)
        assert payload["impact"] == pytest.approx(0.8)

    def test_assess_with_votes_file(self, risk_store_root: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        store = FileRiskStore(root=risk_store_root)
        with store.transaction("default") as tx:
            tx["items"] = [RiskItem(id="R-file", description="seed", probability=0.0, impact=0.0).to_dict()]
        votes_file = tmp_path / "votes.json"
        votes_file.write_text(json.dumps({"architect": [0.4, 0.5]}), encoding="utf-8")
        rc = cmd_risks_assess(_args(risk_id="R-file", votes=None, votes_file=str(votes_file)))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["probability"] == pytest.approx(0.4)

    def test_assess_unknown_role_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_risks_assess(_args(risk_id="R-x", votes='{"unknown-role":[0.5,0.5]}'))
        assert rc == 1

    def test_assess_invalid_json_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_risks_assess(_args(risk_id="R-x", votes="not-json"))
        assert rc == 1

    def test_assess_unknown_risk_errors(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_risks_assess(_args(risk_id="R-missing", votes='{"architect":[0.5,0.5]}'))
        assert rc == 1


class TestMitigateCommand:
    def test_mitigate_sets_strategy_and_owner(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        store = FileRiskStore(root=risk_store_root)
        with store.transaction("default") as tx:
            tx["items"] = [RiskItem(id="R-m", description="m", probability=0.5, impact=0.5).to_dict()]
        rc = cmd_risks_mitigate(_args(risk_id="R-m", strategy="mitigate", owner="devops", plan="add backup"))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["response_strategy"] == "mitigate"
        assert payload["owner"] == "devops"
        assert "add backup" in payload["description"]


class TestCloseCommand:
    def test_close_marks_status_closed(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        store = FileRiskStore(root=risk_store_root)
        with store.transaction("default") as tx:
            tx["items"] = [RiskItem(id="R-c", description="c", probability=0.5, impact=0.5).to_dict()]
        rc = cmd_risks_close(_args(risk_id="R-c", require_approval=False))
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["status"] == "closed"

    def test_close_missing_risk_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_risks_close(_args(risk_id="R-nope", require_approval=False))
        assert rc == 1
        assert "ERROR:" in capsys.readouterr().err
