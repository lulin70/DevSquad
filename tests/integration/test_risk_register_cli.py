"""Integration tests — Risk Register CLI ↔ RiskRegister ↔ ApprovalGate.

Coverage (8 cases):
- CLI add/list/show/clear operate on the shared file-backed store (tmp root)
- ApprovalGate integration: unavailable callback fail-closed + denied callback (exit 2)
- Exposure-descending sort in list output
- RiskRegister.query category filter

V4.5.8: ``--require-approval`` with no callback is fail-closed (exit 2);
the V4.5.5 auto-approve fallback was removed.

V4.5.11: V4.5.7's in-process ``_RISK_STORE`` proxy was removed; tests read
the persistent store via FileRiskStore directly.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

import scripts.cli_risks as cli_risks
from scripts.cli_risks import (
    add_risk,
    cmd_risks_clear,
    cmd_risks_list,
    cmd_risks_show,
)
from scripts.collaboration.approval_gate import ApprovalGate, ApprovalResult
from scripts.collaboration.file_risk_store import FileRiskStore
from scripts.collaboration.risk_register import RiskRegister

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _clean_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Point every store access at a tmp root; clean before and after."""
    monkeypatch.setattr(cli_risks, "DEFAULT_ROOT", tmp_path)
    yield
    store = FileRiskStore(root=tmp_path)
    with store.transaction("default") as transaction:
        transaction["items"] = []


def _count(tmp_path: Path) -> int:
    return len(FileRiskStore(root=tmp_path).load("default").get("items", []))


def _register_items(tmp_path: Path) -> dict[str, object]:
    store = FileRiskStore(root=tmp_path)
    payload = store.load("default")
    return store.payload_to_items(payload)


def _args(**kwargs):
    defaults = {"format": "md", "severity": None, "limit": None,
                "risk_id": "", "require_approval": False, "output": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCliStoreIntegration:
    def test_add_then_list_integration(self, capsys):
        rid = add_risk("integrated risk", probability=0.5, impact=0.5)
        rc = cmd_risks_list(_args())
        out = capsys.readouterr().out
        assert rc == 0
        assert rid[:24] in out

    def test_add_then_show_integration(self, capsys):
        rid = add_risk("detail risk", probability=0.9, impact=0.9)
        rc = cmd_risks_show(_args(risk_id=rid))
        out = capsys.readouterr().out
        assert rc == 0
        assert "0.90 x 0.90" in out  # exposure formula rendered

    def test_clear_empties_store_integration(self, capsys, tmp_path: Path):
        add_risk("doomed risk")
        add_risk("another doomed risk")
        rc = cmd_risks_clear(_args())
        capsys.readouterr()
        assert rc == 0
        assert _count(tmp_path) == 0
        # Post-clear list shows the empty placeholder row.
        cmd_risks_list(_args())
        out = capsys.readouterr().out
        assert "| (none) |" in out

    def test_clear_twice_reports_zero(self, capsys, tmp_path: Path):
        add_risk("single risk")
        cmd_risks_clear(_args())
        capsys.readouterr()
        rc = cmd_risks_clear(_args())
        assert rc == 0
        assert "Cleared 0 risks" in capsys.readouterr().out


class TestApprovalGateIntegration:
    def test_gate_unavailable_fails_closed(self, capsys, tmp_path: Path):
        """V4.5.8 contract: --require-approval with no callback → exit 2, no mutation."""
        add_risk("gated risk")
        rc = cmd_risks_clear(_args(require_approval=True))
        err = capsys.readouterr().err
        assert rc == 2
        assert "approval unavailable" in err
        assert _count(tmp_path) == 1

    def test_gate_denied_callback_returns_2(self, capsys, tmp_path: Path):
        add_risk("protected risk")

        def deny(request):
            return ApprovalResult(approved=False, reason="human said no")

        class DenyingGate(ApprovalGate):
            def __init__(self, approval_callback=None):
                super().__init__(approval_callback=deny)

        # cli_risks lazy-imports ApprovalGate at call time, so patching the
        # module attribute is enough to inject the denying gate.
        with patch(
            "scripts.collaboration.approval_gate.ApprovalGate", DenyingGate
        ):
            rc = cmd_risks_clear(_args(require_approval=True))

        err = capsys.readouterr().err
        assert rc == 2
        assert "Approval denied" in err
        assert "human said no" in err
        # Store must NOT be cleared when approval is denied (fail-closed).
        assert _count(tmp_path) == 1


class TestRiskRegisterIntegration:
    def test_list_sorted_by_exposure_descending(self, capsys):
        add_risk("low risk", probability=0.1, impact=0.1)     # 0.01
        add_risk("high risk", probability=0.9, impact=0.9)    # 0.81
        add_risk("mid risk", probability=0.5, impact=0.5)     # 0.25
        cmd_risks_list(_args())
        out = capsys.readouterr().out
        data = [ln for ln in out.splitlines() if ln.startswith("| `")]
        assert len(data) == 3
        exposures = [float(ln.split("|")[2].strip()) for ln in data]
        assert exposures == sorted(exposures, reverse=True)
        assert exposures[0] == pytest.approx(0.81)

    def test_register_query_category_filter(self, tmp_path: Path):
        add_risk("security risk", category="security")
        add_risk("schedule risk", category="schedule")
        register = RiskRegister()
        # Repopulate from the file-backed store (same wiring as _get_register).
        for item in _register_items(tmp_path).values():
            register.add(risk_item=item)
        security_only = register.query(category="security")
        assert len(security_only) == 1
        assert security_only[0].description == "security risk"
