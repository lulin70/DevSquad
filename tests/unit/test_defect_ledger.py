"""Unit tests for the V4.9.0 P2-W1 defect ledger (design §7, no skips).

Covers: all legal transitions + illegal-transition refusals with reason
text, the five negative-first cases, atomicity, JSON round-trip, and
signal resolution against a REAL sqlite audit DB (no Mock'd details).
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

from scripts.cli_defect import (
    cmd_defect_add,
    cmd_defect_audit,
    cmd_defect_close,
    cmd_defect_list,
    cmd_defect_reopen,
    cmd_defect_update,
    register_defect_subparser,
)
from scripts.collaboration.defect_ledger import (
    SCHEMA_VERSION,
    Defect,
    DefectLedger,
    DefectLedgerError,
)

pytestmark = pytest.mark.unit

# Real dispatch_audit schema (dispatch_audit.py:189-198).
_AUDIT_DDL = """
CREATE TABLE dispatch_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    user_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    details TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    entry_hash TEXT NOT NULL
)
"""


@pytest.fixture
def audit_db(tmp_path: Path) -> Path:
    """A real SQLite audit DB seeded with the events every test needs."""
    db_path = tmp_path / "audit" / "dispatch_audit.db"
    db_path.parent.mkdir(parents=True)
    conn = sqlite3.connect(db_path)
    conn.execute(_AUDIT_DDL)
    events = [
        # (event_type, details)
        (
            "review_findings",
            {"findings": [{"severity": "critical", "rule": "BREAK-2"}, {"severity": "warning", "rule": "BREAK-1"}]},
        ),
        ("dispatch_end", {"failure_class": "product_failed", "success": False}),
        ("dispatch_end", {"failure_class": "environment_blocked", "success": False}),
        ("dispatch_end", {"success": True, "duration": 1.5}),
        ("review_findings", {"findings": [{"severity": "critical", "rule": "VULN-1"}]}),
    ]
    for i, (event_type, details) in enumerate(events, start=1):
        conn.execute(
            "INSERT INTO dispatch_audit (event_type, user_id, timestamp, details, prev_hash, entry_hash)"
            " VALUES (?, 'tester', ?, ?, '0', '0')",
            (event_type, 1700000000.0 + i, json.dumps(details)),
        )
    conn.commit()
    conn.close()
    return db_path


@pytest.fixture
def ledger(tmp_path: Path, audit_db: Path) -> DefectLedger:
    return DefectLedger(
        ledger_path=tmp_path / ".devsquad" / "defects.json",
        audit_db_path=audit_db,
    )


def _file_defect(ledger: DefectLedger, ref: str = "audit:event=1&finding=0") -> Defect:
    return ledger.add(signal_ref=ref, summary="handler without return in api/routes/dispatch.py")


def _fixed_defect(ledger: DefectLedger) -> Defect:
    entry = _file_defect(ledger)
    return ledger.update(entry.id, commit_sha="abc123", summary="add missing return")


class TestLegalTransitions:
    def test_add_creates_open_entry_with_resolved_signal(self, ledger: DefectLedger) -> None:
        entry = _file_defect(ledger)
        assert entry.id == "DEF-001"
        assert entry.state.value == "open"
        assert entry.signal["type"] == "review:finding"
        assert entry.signal["ref"] == "audit:event=1&finding=0"
        assert entry.signal["captured_at"]
        assert entry.history[0]["transition"] == "create"

    def test_add_failure_class_signal(self, ledger: DefectLedger) -> None:
        entry = ledger.add("audit:event=2&failure=product_failed", "product failure on run")
        assert entry.signal["type"] == "failure:product_failed"

    def test_ids_are_monotonic(self, ledger: DefectLedger) -> None:
        first = _file_defect(ledger)
        second = ledger.add("audit:event=2&failure=product_failed", "second defect")
        assert (first.id, second.id) == ("DEF-001", "DEF-002")

    def test_update_moves_open_to_fixed(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        assert entry.state.value == "fixed"
        assert entry.fix["commit"] == "abc123"
        assert [h["transition"] for h in entry.history] == ["create", "fix"]

    def test_refix_allowed_before_close(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.update(entry.id, commit_sha="def456", summary="follow-up fix")
        assert entry.state.value == "fixed"
        assert entry.fix["commit"] == "def456"
        assert [h["transition"] for h in entry.history] == ["create", "fix", "refix"]

    def test_close_moves_fixed_to_closed_with_regression(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.close(entry.id, run_ref="audit:event=4")
        assert entry.state.value == "closed"
        assert entry.regression["run_ref"] == "audit:event=4"
        assert entry.history[-1]["transition"] == "close"

    def test_close_allows_environment_blocked_run(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.close(entry.id, run_ref="audit:event=3")
        assert entry.state.value == "closed"

    def test_reopen_moves_closed_to_open_and_preserves_old_values(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.close(entry.id, run_ref="audit:event=4")
        old_fix = dict(entry.fix or {})
        old_regression = dict(entry.regression or {})
        entry = ledger.reopen(entry.id, reason="regressed in prod")
        assert entry.state.value == "open"
        assert entry.fix is None and entry.regression is None
        assert entry.reopen_reason == "regressed in prod"
        reopen_record = entry.history[-1]
        assert reopen_record["transition"] == "reopen"
        assert reopen_record["fields"]["cleared_fix"] == old_fix
        assert reopen_record["fields"]["cleared_regression"] == old_regression


class TestIllegalTransitions:
    def test_close_rejects_open_skip_state(self, ledger: DefectLedger) -> None:
        entry = _file_defect(ledger)
        with pytest.raises(DefectLedgerError, match="open->closed"):
            ledger.close(entry.id, run_ref="audit:event=4")

    def test_update_rejects_closed(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.close(entry.id, run_ref="audit:event=4")
        with pytest.raises(DefectLedgerError, match="closed->fixed"):
            ledger.update(entry.id, commit_sha="abc", summary="late fix")

    def test_reopen_rejects_fixed(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        with pytest.raises(DefectLedgerError, match="reopen is closed->open only"):
            ledger.reopen(entry.id, reason="not closed yet")

    def test_close_rejects_already_closed(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.close(entry.id, run_ref="audit:event=4")
        with pytest.raises(DefectLedgerError, match="already closed"):
            ledger.close(entry.id, run_ref="audit:event=4")

    def test_unknown_defect_id_rejected(self, ledger: DefectLedger) -> None:
        with pytest.raises(DefectLedgerError, match="not found: DEF-999"):
            ledger.update("DEF-999", commit_sha="abc", summary="ghost")

    def test_mandatory_fields_enforced(self, ledger: DefectLedger) -> None:
        entry = _file_defect(ledger)
        with pytest.raises(DefectLedgerError, match="non-empty --summary"):
            ledger.update(entry.id, commit_sha="abc", summary="  ")
        with pytest.raises(DefectLedgerError, match="non-empty --commit"):
            ledger.update(entry.id, commit_sha="", summary="s")


class TestNegativeFirst:
    def test_add_rejects_missing_event(self, ledger: DefectLedger) -> None:
        with pytest.raises(DefectLedgerError, match="audit event 999 not found"):
            ledger.add("audit:event=999&finding=0", "ghost signal")

    def test_add_rejects_out_of_range_finding(self, ledger: DefectLedger) -> None:
        with pytest.raises(DefectLedgerError, match="finding index 5 not in"):
            ledger.add("audit:event=1&finding=5", "bad index")

    def test_add_rejects_failure_class_mismatch(self, ledger: DefectLedger) -> None:
        with pytest.raises(DefectLedgerError, match="failure_class .* != 'product_failed'"):
            ledger.add("audit:event=1&failure=product_failed", "mismatch")

    def test_add_rejects_non_audit_prefix(self, ledger: DefectLedger) -> None:
        with pytest.raises(DefectLedgerError, match="'audit:' refs only"):
            ledger.add("review:somewhere", "unsupported ref")

    def test_close_rejects_product_failed_run(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        with pytest.raises(DefectLedgerError, match="product_failed signal"):
            ledger.close(entry.id, run_ref="audit:event=2")

    def test_close_rejects_critical_findings_run(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        with pytest.raises(DefectLedgerError, match="critical finding"):
            ledger.close(entry.id, run_ref="audit:event=5")

    def test_close_fails_closed_without_audit_db(self, ledger: DefectLedger, tmp_path: Path) -> None:
        entry = _fixed_defect(ledger)
        ledger.audit_db_path = tmp_path / "missing" / "dispatch_audit.db"
        with pytest.raises(DefectLedgerError, match="audit DB not found"):
            ledger.close(entry.id, run_ref="audit:event=4")

    def test_next_id_tamper_detected(self, ledger: DefectLedger) -> None:
        _file_defect(ledger)
        ledger.add("audit:event=2&failure=product_failed", "second defect")
        data = json.loads(ledger.ledger_path.read_text(encoding="utf-8"))
        data["next_id"] = 2  # hand-rolled rollback: DEF-002 now >= next_id
        ledger.ledger_path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(DefectLedgerError, match="ID reuse detected"):
            ledger.add("audit:event=5&finding=0", "third defect")
        # Every command re-validates on load — list refuses the tampered file too.
        with pytest.raises(DefectLedgerError, match="ID reuse detected"):
            ledger.list_defects()

    def test_state_history_desync_fail_closed(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        data = json.loads(ledger.ledger_path.read_text(encoding="utf-8"))
        data["entries"][0]["state"] = "open"  # history tail still says fixed
        ledger.ledger_path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(DefectLedgerError, match="lost transition suspected"):
            ledger.update(entry.id, commit_sha="abc", summary="desynced")

    def test_truncated_json_rejected(self, ledger: DefectLedger) -> None:
        _file_defect(ledger)
        raw = ledger.ledger_path.read_text(encoding="utf-8")
        ledger.ledger_path.write_text(raw[: len(raw) // 2], encoding="utf-8")
        with pytest.raises(DefectLedgerError, match="not valid JSON"):
            ledger.list_defects()

    def test_unsupported_schema_version_rejected(self, ledger: DefectLedger) -> None:
        ledger.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        ledger.ledger_path.write_text(
            json.dumps({"schema_version": SCHEMA_VERSION + 1, "next_id": 1, "entries": []}),
            encoding="utf-8",
        )
        with pytest.raises(DefectLedgerError, match="not supported"):
            ledger.list_defects()

    def test_duplicate_id_rejected(self, ledger: DefectLedger) -> None:
        _file_defect(ledger)
        data = json.loads(ledger.ledger_path.read_text(encoding="utf-8"))
        data["entries"].append(json.loads(json.dumps(data["entries"][0])))
        data["next_id"] = 3
        ledger.ledger_path.write_text(json.dumps(data), encoding="utf-8")
        with pytest.raises(DefectLedgerError, match="duplicate defect id"):
            ledger.list_defects()


class TestAtomicityAndRoundtrip:
    def test_atomic_write_failure_leaves_file_unchanged(
        self, ledger: DefectLedger, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        entry = _file_defect(ledger)
        before = ledger.ledger_path.read_text(encoding="utf-8")

        def boom(src: str, dst: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr("scripts.collaboration.defect_ledger.os.replace", boom)
        with pytest.raises(OSError, match="disk full"):
            ledger.update(entry.id, commit_sha="abc", summary="doomed write")
        assert ledger.ledger_path.read_text(encoding="utf-8") == before
        leftovers = [p.name for p in ledger.ledger_path.parent.iterdir() if p.name.endswith(".tmp")]
        assert leftovers == []

    def test_json_roundtrip_preserves_entry(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        entry = ledger.close(entry.id, run_ref="audit:event=4")
        entry = ledger.reopen(entry.id, reason="regressed")
        restored = Defect.from_dict(json.loads(json.dumps(entry.to_dict())))
        assert restored.to_dict() == entry.to_dict()

    def test_file_reload_rebuilds_same_state(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        reloaded = DefectLedger(ledger_path=ledger.ledger_path, audit_db_path=ledger.audit_db_path)
        entries = reloaded.list_defects()
        assert len(entries) == 1
        assert entries[0].to_dict() == entry.to_dict()


class TestAuditReport:
    def test_clean_ledger_reports_no_issues(self, ledger: DefectLedger) -> None:
        entry = _fixed_defect(ledger)
        ledger.close(entry.id, run_ref="audit:event=4")
        assert ledger.audit_report() == []

    def test_audit_report_detects_next_id_rollback(self, ledger: DefectLedger) -> None:
        _file_defect(ledger)
        data = json.loads(ledger.ledger_path.read_text(encoding="utf-8"))
        data["next_id"] = 1
        ledger.ledger_path.write_text(json.dumps(data), encoding="utf-8")
        issues = ledger.audit_report()
        assert any("id >= next_id" in i for i in issues)

    def test_audit_report_detects_missing_create(self, ledger: DefectLedger) -> None:
        _file_defect(ledger)
        data = json.loads(ledger.ledger_path.read_text(encoding="utf-8"))
        data["entries"][0]["history"][0]["transition"] = "reopen"  # create record erased
        ledger.ledger_path.write_text(json.dumps(data), encoding="utf-8")
        # Load validation fails closed first (defense in depth: an entry
        # without a create record can never pass _load).
        issues = ledger.audit_report()
        assert any("history must start with create->open" in i for i in issues)


def _cli_args(**kwargs: object) -> argparse.Namespace:
    defaults: dict[str, object] = {
        "ledger_path": None,
        "audit_db_path": None,
        "json": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCliCommands:
    def _ledger_args(self, ledger: DefectLedger, **kwargs: object) -> argparse.Namespace:
        return _cli_args(ledger_path=str(ledger.ledger_path), audit_db_path=str(ledger.audit_db_path), **kwargs)

    def test_cli_add_exit_zero_with_json(self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]) -> None:
        rc = cmd_defect_add(
            self._ledger_args(ledger, signal_ref="audit:event=1&finding=0", summary="cli filed", json=True)
        )
        assert rc == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["id"] == "DEF-001"
        assert payload["state"] == "open"

    def test_cli_add_rejects_ghost_signal_exit_one(
        self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = cmd_defect_add(self._ledger_args(ledger, signal_ref="audit:event=99&finding=0", summary="ghost"))
        assert rc == 1
        assert "ERROR:" in capsys.readouterr().err

    def test_cli_full_lifecycle(self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]) -> None:
        capsys.readouterr()
        assert (
            cmd_defect_add(
                self._ledger_args(ledger, signal_ref="audit:event=2&failure=product_failed", summary="prod fail")
            )
            == 0
        )
        assert cmd_defect_update(self._ledger_args(ledger, defect_id="DEF-001", commit="abc123", summary="hotfix")) == 0
        assert cmd_defect_close(self._ledger_args(ledger, defect_id="DEF-001", run_ref="audit:event=4")) == 0
        assert cmd_defect_reopen(self._ledger_args(ledger, defect_id="DEF-001", reason="regressed")) == 0
        assert cmd_defect_list(self._ledger_args(ledger)) == 0
        assert cmd_defect_audit(self._ledger_args(ledger)) == 0
        assert "DEF-001  open" in capsys.readouterr().out

    def test_cli_list_filters_by_state(self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]) -> None:
        _file_defect(ledger)
        ledger.add("audit:event=2&failure=product_failed", "second")
        ledger.update("DEF-002", commit_sha="abc", summary="fixed second")
        capsys.readouterr()
        assert cmd_defect_list(self._ledger_args(ledger, state="fixed")) == 0
        out = capsys.readouterr().out
        assert "DEF-002" in out and "DEF-001" not in out

    def test_cli_audit_exit_one_on_corruption(self, ledger: DefectLedger, capsys: pytest.CaptureFixture[str]) -> None:
        _file_defect(ledger)
        data = json.loads(ledger.ledger_path.read_text(encoding="utf-8"))
        data["next_id"] = 1
        ledger.ledger_path.write_text(json.dumps(data), encoding="utf-8")
        assert cmd_defect_audit(self._ledger_args(ledger)) == 1
        assert "FAIL:" in capsys.readouterr().err

    def test_cli_environment_error_exits_two(
        self, tmp_path: Path, audit_db: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        ledger_path = tmp_path / "as-directory"
        ledger_path.mkdir()
        rc = cmd_defect_add(
            _cli_args(
                ledger_path=str(ledger_path),
                audit_db_path=str(audit_db),
                signal_ref="audit:event=1&finding=0",
                summary="unwritable",
            )
        )
        assert rc == 2
        assert "ERROR:" in capsys.readouterr().err

    def test_subparser_registers_all_six_commands(self) -> None:
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        register_defect_subparser(subparsers)
        for argv in (
            ["defect", "add", "--signal-ref", "audit:event=1&finding=0", "--summary", "s"],
            ["defect", "update", "DEF-001", "--commit", "abc", "--summary", "s"],
            ["defect", "close", "DEF-001", "--run-ref", "audit:event=1"],
            ["defect", "reopen", "DEF-001", "--reason", "r"],
            ["defect", "list"],
            ["defect", "audit"],
        ):
            args = parser.parse_args(argv)
            assert callable(args.func)
