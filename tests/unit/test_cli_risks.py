"""Unit tests for cli_risks (V4.5.7 P12.5.2, updated for V4.5.8 contracts).

Coverage (12 cases):
- list: empty / Markdown header / JSON format / category filter / limit
- show: existing / missing (exit 1) / JSON format
- clear: plain / --require-approval fail-closed (V4.5.8 contract)
- export: stdout JSON / to file

V4.5.8 changes:
- The store is file-backed; each test runs against an isolated tmp root via
  ``monkeypatch`` so the developer's real ``.devsquad_data/risks`` is never
  touched by unit tests.
- ``--require-approval`` with an unavailable callback is fail-closed
  (exit 2, no mutation) — the V4.5.5 auto-approve fallback was removed.

V4.5.11 changes:
- V4.5.7's in-process ``_RISK_STORE`` proxy was removed; tests now assert
  directly against ``FileRiskStore(root=tmp_path).transaction("default")``.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

import scripts.cli_risks as cli_risks
from scripts.cli_risks import (
    RISK_FIELD_ORDER,
    add_risk,
    cmd_risks_clear,
    cmd_risks_export,
    cmd_risks_list,
    cmd_risks_show,
    get_call_counter_er,
)
from scripts.collaboration.file_risk_store import FileRiskStore


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point every store access at a tmp root; clean before and after."""
    monkeypatch.setattr(cli_risks, "DEFAULT_ROOT", tmp_path)
    yield
    store = FileRiskStore(root=tmp_path)
    with store.transaction("default") as transaction:
        transaction["items"] = []


def _count(tmp_path: Path) -> int:
    return len(FileRiskStore(root=tmp_path).load("default").get("items", []))


def _args(**kwargs) -> argparse.Namespace:
    # V4.5.12: severity removed from defaults (--severity flag deleted).
    defaults = {"format": "md", "limit": None,
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
        # V4.5.11: list JSON uses the canonical field order.
        assert list(payload[0].keys()) == list(RISK_FIELD_ORDER)

    def test_list_category_filter(self, capsys):
        # V4.5.12: was test_list_severity_filter (--severity removed; use --category).
        p0_id = add_risk("P0 risk", category="P0")
        general_id = add_risk("general risk", category="general")
        rc = cmd_risks_list(_args(category="P0"))
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
        assert list(payload[0].keys()) == list(RISK_FIELD_ORDER)


class TestClear:
    def test_clear_without_approval(self, capsys, tmp_path: Path):
        add_risk("to be cleared")
        rc = cmd_risks_clear(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert "Cleared 1 risks" in out
        assert _count(tmp_path) == 0

    def test_clear_with_approval_unavailable_fails_closed(self, capsys, tmp_path: Path):
        """V4.5.8 contract: --require-approval with no callback → exit 2, no mutation."""
        add_risk("gate cleared")
        rc = cmd_risks_clear(_args(require_approval=True))
        err = capsys.readouterr().err
        assert rc == 2
        assert "approval unavailable" in err
        # The risk must remain in the store (nothing was cleared).
        assert _count(tmp_path) == 1


class TestExport:
    def test_export_stdout_json(self, capsys):
        add_risk("exported risk")
        rc = cmd_risks_export(_args())
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert payload[0]["description"] == "exported risk"
        assert list(payload[0].keys()) == list(RISK_FIELD_ORDER)

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


def test_store_uses_file_backed_root(tmp_path: Path):
    """add_risk writes through FileRiskStore; the tmp root holds the items."""
    add_risk("file backed risk", probability=0.4, impact=0.5)
    store = FileRiskStore(root=tmp_path)
    payload = store.load("default")
    assert payload["version"] == 1
    assert payload["items"][0]["description"] == "file backed risk"


def test_add_json_output_uses_canonical_field_order(capsys, tmp_path: Path):
    """V4.5.11: add JSON output matches list/show field order."""
    # add_risk returns the id only; the JSON shape is emitted by cmd_risks_add.
    from scripts.cli_risks import cmd_risks_add

    args = argparse.Namespace(
        description="field order",
        probability=0.2,
        impact=0.2,
        category="general",
        owner="",
        register_id="default",
        root=None,
    )
    rc = cmd_risks_add(args)
    assert rc == 0
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert list(payload.keys()) == list(RISK_FIELD_ORDER)
