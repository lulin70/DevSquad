"""Contract tests for V4.5.8 Wave 2 CLI mutators.

Validates:
- V4.5.7 JSON schema is preserved on `list/show/export`.
- Stable error code mapping per design §3.3.
- argparse contract for add/assess/mitigate/close/clear.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pytest

from scripts import cli_risks
from scripts.cli_risks import (
    cmd_risks_add,
    cmd_risks_assess,
    cmd_risks_clear,
    cmd_risks_close,
    cmd_risks_export,
    cmd_risks_list,
    cmd_risks_mitigate,
    cmd_risks_show,
    main,
    register_risks_subparser,
)
from scripts.collaboration.file_risk_store import FileRiskStore
from scripts.collaboration.risk_register import RiskItem, RiskStatus

pytestmark = pytest.mark.contract

REQUIRED_FIELDS = {
    "id",
    "description",
    "probability",
    "impact",
    "exposure",
    "response_strategy",
    "owner",
    "status",
    "category",
}


@pytest.fixture
def risk_store_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / ".devsquad_data" / "risks"
    root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(cli_risks, "DEFAULT_ROOT", root, raising=False)
    return root


def _seed(root: Path, rid: str = "R-seed") -> RiskItem:
    store = FileRiskStore(root=root)
    with store.transaction("default") as tx:
        tx["items"] = [
            RiskItem(
                id=rid,
                description="contract",
                probability=0.4,
                impact=0.5,
                response_strategy="accept",
                owner="architect",
                status=RiskStatus.OPEN,
                category="technical",
            ).to_dict()
        ]
    return RiskItem.from_dict(
        store.load("default")["items"][0]
    )


class TestJsonSchemaContract:
    def test_list_json_contains_required_fields(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed(risk_store_root)
        args = argparse.Namespace(
            register_id="default", root=None,
            format="json", min_exposure=None,
            category=None, limit=None, approval_callback=None,
            require_approval=False,
        )
        rc = cmd_risks_list(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload[0]) == REQUIRED_FIELDS

    def test_show_json_contains_required_fields(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed(risk_store_root, rid="R-show")
        args = argparse.Namespace(
            register_id="default", root=None,
            risk_id="R-show", format="json",
            min_exposure=None, category=None,
            approval_callback=None, require_approval=False,
        )
        rc = cmd_risks_show(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload[0]) == REQUIRED_FIELDS

    def test_export_json_matches_v457_shape(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed(risk_store_root)
        args = argparse.Namespace(
            register_id="default", root=None,
            output=None, output_positional=None,
            min_exposure=None, category=None,
            approval_callback=None, require_approval=False,
        )
        rc = cmd_risks_export(args)
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert set(payload[0]) == REQUIRED_FIELDS


class TestErrorCodeContract:
    def test_argparse_missing_required_returns_2(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        # ``risks add`` requires --probability etc. → argparse error → exit 2.
        with pytest.raises(SystemExit) as exit_info:
            main(["risks", "add", "no-required-flags"])
        assert exit_info.value.code == 2
        combined = capsys.readouterr()
        assert "Traceback" not in (combined.out + combined.err)

    def test_unknown_strategy_returns_2(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rc = main(
            [
                "risks", "add", "x",
                "--probability", "0.4", "--impact", "0.5",
                "--category", "general", "--owner", "architect",
            ]
        )
        assert rc == 0
        list_proc_capsys = capsys.readouterr()
        payload = json.loads(list_proc_capsys.out.splitlines()[-1])
        rid = payload["id"]
        with pytest.raises(SystemExit) as exit_info:
            main(["risks", "mitigate", rid, "--strategy", "bogus", "--owner", "devops"])
        assert exit_info.value.code == 2
        assert "Traceback" not in capsys.readouterr().err

    def test_storage_corrupt_returns_3(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        target = risk_store_root / "default.json"
        target.write_text("{", encoding="utf-8")
        args = argparse.Namespace(
            register_id="default", root=None,
            format="md", min_exposure=None,
            category=None, limit=None, approval_callback=None,
            require_approval=False,
        )
        rc = cmd_risks_list(args)
        assert rc == 3
        assert "ERROR" in capsys.readouterr().err

    def test_approval_unavailable_returns_2(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed(risk_store_root, rid="R-approve")
        rc = main(["risks", "close", "R-approve", "--require-approval"])
        assert rc == 2
        assert "approval unavailable" in capsys.readouterr().err


class TestArgumentParserContract:
    def test_register_id_argument_present_on_all_commands(self) -> None:
        parser = argparse.ArgumentParser()
        register_risks_subparser(parser.add_subparsers(dest="command"))

        for cmd, extra in [
            ("list", []),
            ("show", ["R-x"]),
            ("add", ["desc", "--probability", "0.5", "--impact", "0.5", "--category", "c", "--owner", "o"]),
            ("assess", ["R-x", "--votes", '{"architect":[0.5,0.5]}']),
            ("mitigate", ["R-x", "--strategy", "accept", "--owner", "devops"]),
            ("close", ["R-x"]),
            ("clear", []),
            ("export", []),
        ]:
            args = parser.parse_args(["risks", cmd, *extra])
            assert hasattr(args, "register_id"), cmd
            assert args.register_id == "default", cmd

    def test_assess_requires_exactly_one_votes_source(self) -> None:
        parser = argparse.ArgumentParser(exit_on_error=False)
        register_risks_subparser(parser.add_subparsers(dest="command"))
        with pytest.raises(SystemExit):
            parser.parse_args(["risks", "assess", "R-x"])

    def test_export_supports_both_output_forms(self) -> None:
        parser = argparse.ArgumentParser()
        register_risks_subparser(parser.add_subparsers(dest="command"))
        args = parser.parse_args(["risks", "export", "/tmp/out.json"])
        # The CLI resolves either field; the parser must accept the positional.
        assert args.output_positional == "/tmp/out.json"

        args = parser.parse_args(["risks", "export", "--output", "/tmp/out.json"])
        assert args.output == "/tmp/out.json"

    def test_no_severity_flag(self) -> None:
        # V4.5.12 AC-SE-3: --severity is removed (Breaking); argparse must
        # reject it with exit code 2 for list/show/export.
        parser = argparse.ArgumentParser()
        register_risks_subparser(parser.add_subparsers(dest="command"))
        for cmd, extra in [("list", []), ("show", ["R-x"]), ("export", [])]:
            with pytest.raises(SystemExit) as exit_info:
                parser.parse_args(["risks", cmd, "--severity", "0.5", *extra])
            assert exit_info.value.code == 2, cmd


class TestMutatorApiContract:
    def test_add_assess_mitigate_close_chain(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        add = cmd_risks_add(
            argparse.Namespace(
                register_id="default", root=None,
                description="chain", probability=0.6, impact=0.7,
                category="general", owner="architect",
                approval_callback=None, require_approval=False,
            )
        )
        assert add == 0
        rid = json.loads(capsys.readouterr().out)["id"]

        rc = cmd_risks_assess(
            argparse.Namespace(
                register_id="default", root=None,
                risk_id=rid, votes='{"architect":[0.7,0.8]}', votes_file=None,
                approval_callback=None, require_approval=False,
            )
        )
        assert rc == 0
        assess_payload = json.loads(capsys.readouterr().out)
        assert assess_payload["probability"] == pytest.approx(0.7)

        rc = cmd_risks_mitigate(
            argparse.Namespace(
                register_id="default", root=None,
                risk_id=rid, strategy="mitigate", owner="devops", plan="",
                approval_callback=None, require_approval=False,
            )
        )
        assert rc == 0
        mitigate_payload = json.loads(capsys.readouterr().out)
        assert mitigate_payload["response_strategy"] == "mitigate"
        assert mitigate_payload["status"] == "mitigating"

        rc = cmd_risks_close(
            argparse.Namespace(
                register_id="default", root=None,
                risk_id=rid, require_approval=False,
                approval_callback=None,
            )
        )
        assert rc == 0
        close_payload = json.loads(capsys.readouterr().out)
        assert close_payload["status"] == "closed"


class TestClearApprovalContract:
    def test_clear_without_approval_succeeds(self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _seed(risk_store_root)
        args = argparse.Namespace(
            register_id="default", root=None,
            require_approval=False, approval_callback=None,
        )
        assert cmd_risks_clear(args) == 0
        assert "Cleared" in capsys.readouterr().out

    def test_clear_with_approval_unavailable_does_not_clear(
        self, risk_store_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        _seed(risk_store_root)
        args = argparse.Namespace(
            register_id="default", root=None,
            require_approval=True, approval_callback=None,
        )
        assert cmd_risks_clear(args) == 2
        assert "approval unavailable" in capsys.readouterr().err
        # State must remain: store must still contain the seeded item.
        store = FileRiskStore(root=risk_store_root)
        items = store.payload_to_items(store.load("default"))
        assert len(items) == 1

