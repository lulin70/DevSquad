"""Contract tests — cli_risks CLI vs Python API behavior consistency.

Design §3 contract: the risks CLI subcommands and the module-level Python
helpers must render identical content, and the CLI's store wiring must be
consistent with RiskRegister's own API.
"""

from __future__ import annotations

import argparse
import json

import pytest

from scripts.cli_risks import (
    _RISK_STORE,
    _format_markdown,
    _get_register,
    add_risk,
    cmd_risks_list,
    cmd_risks_show,
)
from scripts.collaboration.risk_register import RiskRegister

pytestmark = pytest.mark.contract


@pytest.fixture(autouse=True)
def _clean_store():
    _RISK_STORE.clear()
    yield
    _RISK_STORE.clear()


def _args(**kwargs):
    defaults = {"format": "md", "severity": None, "limit": None,
                "risk_id": "", "require_approval": False, "output": None}
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCliPythonApiConsistency:
    def test_cli_list_matches_direct_format_call(self, capsys):
        """``cmd_risks_list`` stdout must equal ``_format_markdown`` on the
        same store content (CLI and Python API are interchangeable)."""
        add_risk("contract risk A", probability=0.3, impact=0.3)
        add_risk("contract risk B", probability=0.6, impact=0.6)

        rc = cmd_risks_list(_args())
        cli_out = capsys.readouterr().out

        register = _get_register()
        expected = _format_markdown(register.query())
        assert rc == 0
        assert cli_out.rstrip("\n") == expected.rstrip("\n")

    def test_cli_store_matches_risk_register_api(self, capsys):
        """Items added via ``add_risk`` (Python API) are visible through
        ``RiskRegister.query`` via the CLI's store wiring, and the JSON
        payload shape matches the CLI export contract."""
        rid = add_risk("shape check", probability=0.5, impact=0.4)

        register = RiskRegister()
        for item in _RISK_STORE.values():
            register.add(risk_item=item)
        found = register.query()
        assert len(found) == 1
        assert found[0].id == rid

        rc = cmd_risks_show(_args(risk_id=rid, format="json"))
        payload = json.loads(capsys.readouterr().out)
        assert rc == 0
        assert set(payload[0]) == {
            "id", "description", "probability", "impact", "exposure",
            "response_strategy", "owner", "status", "category",
        }
        assert payload[0]["exposure"] == pytest.approx(0.2)
