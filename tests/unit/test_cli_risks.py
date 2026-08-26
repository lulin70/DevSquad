"""Unit tests for cli_risks (V4.5.7 P12.5.2).

Coverage (12 cases):
- list: empty / Markdown header / JSON format / severity filter / limit
- show: existing / missing (exit 1) / JSON format
- clear: plain / with ApprovalGate auto-approve
- export: stdout JSON / to file
"""

from __future__ import annotations

import argparse
import json

import pytest

from scripts.cli_risks import (
    _RISK_STORE,
    add_risk,
    cmd_risks_clear,
    cmd_risks_export,
    cmd_risks_list,
    cmd_risks_show,
    get_call_counter_er,
)


@pytest.fixture(autouse=True)
def _clean_store():
    """Isolate the in-process risk store between tests."""
    _RISK_STORE.clear()
    yield
    _RISK_STORE.clear()


def _args(**kwargs) -> argparse.Namespace:
    defaults = {"format": "md", "severity": None, "limit": None,
                "risk_id": "", "require_approval": False, "output": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestList:
    def test_list_empty_prints_none_row(self, capsys):
        rc = cmd_risks_list(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "| Risk ID |" in out
        assert "| (none) |" in out

    def test_list_markdown_header(self, capsys):
        add_risk("async deadlock in coeffect", probability=0.6, impact=0.8)
        rc = cmd_risks_list(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert out.startswith("| Risk ID | Exposure | Probability | Impact | Status | Category |")

    def test_list_json_format(self, capsys):
        add_risk("json risk", probability=0.3, impact=0.4)
        rc = cmd_risks_list(_args(format="json"))
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert isinstance(payload, list)
        assert payload[0]["description"] == "json risk"

    def test_list_severity_filter(self, capsys):
        p0_id = add_risk("P0 risk", category="P0")
        general_id = add_risk("general risk", category="general")
        rc = cmd_risks_list(_args(severity="P0"))
        out = capsys.readouterr().out
        assert rc == 0
        assert p0_id[:24] in out
        assert "| P0 |" in out
        assert general_id[:24] not in out

    def test_list_limit(self, capsys):
        for i in range(5):
            add_risk(f"risk-{i}")
        rc = cmd_risks_list(_args(limit=2))
        out = capsys.readouterr().out
        assert rc == 0
        # Data rows start with "| `R-..." (header/separator do not).
        data_rows = [ln for ln in out.splitlines() if ln.startswith("| `")]
        assert len(data_rows) == 2


class TestShow:
    def test_show_existing_risk(self, capsys):
        rid = add_risk("showable risk", probability=0.7, impact=0.9)
        rc = cmd_risks_show(_args(risk_id=rid))
        out = capsys.readouterr().out
        assert rc == 0
        assert rid in out
        assert "showable risk" in out
        assert "**Exposure**" in out

    def test_show_missing_risk_returns_1(self, capsys):
        rc = cmd_risks_show(_args(risk_id="does-not-exist"))
        err = capsys.readouterr().err
        assert rc == 1
        assert "not found" in err

    def test_show_json_format(self, capsys):
        rid = add_risk("json detail risk")
        rc = cmd_risks_show(_args(risk_id=rid, format="json"))
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload[0]["id"] == rid


class TestClear:
    def test_clear_without_approval(self, capsys):
        add_risk("to be cleared")
        rc = cmd_risks_clear(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "Cleared 1 risks" in out
        assert len(_RISK_STORE) == 0

    def test_clear_with_approval_auto_approved(self, capsys):
        add_risk("gate cleared")
        rc = cmd_risks_clear(_args(require_approval=True))
        out = capsys.readouterr().out
        # ApprovalGate with no callback auto-approves (V4.5.5 contract)
        assert rc == 0
        assert "Cleared 1 risks" in out


class TestExport:
    def test_export_stdout_json(self, capsys):
        add_risk("exported risk")
        rc = cmd_risks_export(_args())
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload[0]["description"] == "exported risk"

    def test_export_to_file(self, capsys, tmp_path):
        add_risk("file risk")
        target = tmp_path / "risks.json"
        rc = cmd_risks_export(_args(output=str(target)))
        capsys.readouterr()
        assert rc == 0
        payload = json.loads(target.read_text(encoding="utf-8"))
        assert payload[0]["description"] == "file risk"


def test_call_counter_bumped_by_cli():
    before = get_call_counter_er()
    add_risk("counter risk")
    cmd_risks_list(_args())
    assert get_call_counter_er() >= before + 2
