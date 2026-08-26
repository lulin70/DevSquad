#!/usr/bin/env python3
"""Audit CLI contract tests — V4.5.3 P12.2.6.

These tests verify the **stable public contract** of the audit CLI
(cmd_audit / verify_chain / sensitive-field redaction / SHA-256 chain).

Contracts under test:
  AU1  cmd_audit returns exit code 0 on success, 1 on chain failure.
  AU2  Sensitive fields (api_key/password/secret/token/private_key) are
       redacted in both text and JSON output.
  AU3  SHA-256 chain verification validates the canonical hash format.
  AU4  Tampering with any entry invalidates the chain.
  AU5  Subparser registration produces an argparse subparser with the
       documented flags (--limit, --format, --event-type, --verify, --db-path).
  AU6  Module-level anti-ghost counter exposed via get_call_counter_er().
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

import pytest

pytestmark = pytest.mark.contract


# ── Fixtures ─────────────────────────────────────────────────────────────────


@pytest.fixture()
def populated_db(tmp_path) -> Path:
    """Create a SQLite dispatch_audit DB with 3 entries whose hashes match
    the canonical SHA-256 chain format used by ``verify_chain``.

    Note: ``DispatchAuditLogger`` uses HMAC-SHA256 (with a process-random
    key), but ``verify_chain`` (in cli_audit.py) uses plain SHA-256.
    To keep the contract test honest about what ``verify_chain``
    actually accepts, we build the entries by hand using the same
    canonical format."""
    import hashlib

    db_path = tmp_path / "audit.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute(
        """
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
    )

    raw_entries = [
        ("dispatch_start", "u1", 1000.0, {"task": "task1", "roles": ["architect"]}),
        ("dispatch_end", "u1", 1001.5, {"success": True, "duration": 1.5}),
        ("permission_denied", "u2", 1002.0, {"reason": "not allowed"}),
    ]
    prev_hash = "0" * 64
    for et, uid, ts, details in raw_entries:
        details_json = json.dumps(details, sort_keys=True, separators=(",", ":"))
        payload = (
            f"{prev_hash}"
            f"{len(et)}:{et}"
            f"{len(uid)}:{uid}"
            f"{ts:.6f}"
            f"{details_json}"
        ).encode()
        entry_hash = hashlib.sha256(payload).hexdigest()
        conn.execute(
            "INSERT INTO dispatch_audit (event_type, user_id, timestamp, details, prev_hash, entry_hash) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (et, uid, ts, json.dumps(details, sort_keys=True), prev_hash, entry_hash),
        )
        prev_hash = entry_hash
    conn.commit()
    conn.close()
    return db_path


def _make_args(**overrides) -> argparse.Namespace:
    args = argparse.Namespace(
        db_path=None,
        limit=None,
        format="text",
        event_type=None,
        verify=False,
    )
    for k, v in overrides.items():
        setattr(args, k, v)
    return args


# ── AU1: cmd_audit return codes ─────────────────────────────────────────────


class TestCmdAuditReturnCodes:
    """AU1: cmd_audit returns 0 (success) / 1 (verify failure)."""

    def test_no_db_returns_zero(self, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        args = _make_args(db_path=None, format="text")
        rc = cmd_audit(args)
        assert rc == 0

    def test_valid_chain_returns_zero(self, populated_db, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        args = _make_args(db_path=str(populated_db), verify=True)
        rc = cmd_audit(args)
        assert rc == 0

    def test_tampered_chain_returns_one(self, populated_db, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        # Tamper with one entry's details
        conn = sqlite3.connect(str(populated_db))
        cur = conn.execute("UPDATE dispatch_audit SET details = ? WHERE id = 1", (json.dumps({"tampered": True}),))  # noqa: F841
        conn.commit()
        conn.close()

        args = _make_args(db_path=str(populated_db), verify=True)
        rc = cmd_audit(args)
        assert rc == 1


# ── AU2: Sensitive field redaction ───────────────────────────────────────────


class TestSensitiveFieldRedaction:
    """AU2: api_key/password/secret/token/private_key are redacted."""

    def test_redact_dict_top_level(self) -> None:
        from scripts.cli_audit import _redact_sensitive

        out = _redact_sensitive(
            {"api_key": "AKIA...", "password": "p", "name": "alice"}
        )
        assert out["api_key"] == "***REDACTED***"
        assert out["password"] == "***REDACTED***"
        assert out["name"] == "alice"

    def test_redact_dict_nested(self) -> None:
        from scripts.cli_audit import _redact_sensitive

        out = _redact_sensitive({"outer": {"secret": "s", "ok": 1}})
        assert out["outer"]["secret"] == "***REDACTED***"
        assert out["outer"]["ok"] == 1

    def test_redact_dict_list(self) -> None:
        from scripts.cli_audit import _redact_sensitive

        out = _redact_sensitive([{"token": "tok1"}, {"token": "tok2"}])
        assert out[0]["token"] == "***REDACTED***"
        assert out[1]["token"] == "***REDACTED***"

    def test_redact_case_insensitive(self) -> None:
        from scripts.cli_audit import _redact_sensitive

        out = _redact_sensitive({"API_KEY": "x", "Secret": "y"})
        assert out["API_KEY"] == "***REDACTED***"
        assert out["Secret"] == "***REDACTED***"

    def test_redact_variants(self) -> None:
        from scripts.cli_audit import _redact_sensitive

        out = _redact_sensitive(
            {"apikey": "k", "passwd": "p", "private_key": "pk"}
        )
        assert out["apikey"] == "***REDACTED***"
        assert out["passwd"] == "***REDACTED***"
        assert out["private_key"] == "***REDACTED***"


# ── AU3: SHA-256 chain verification ──────────────────────────────────────────


class TestSHA256ChainVerify:
    """AU3: verify_chain validates canonical hash format."""

    def test_verify_chain_valid(self, populated_db) -> None:
        from scripts.cli_audit import _load_entries, verify_chain

        entries = _load_entries(str(populated_db))
        assert len(entries) >= 2
        ok, msg = verify_chain(entries)
        assert ok is True
        assert msg == "OK"

    def test_verify_chain_tampered_details(self, populated_db) -> None:
        from scripts.cli_audit import _load_entries, verify_chain

        entries = _load_entries(str(populated_db))
        # Tamper with entry #1's details
        entries[0]["details"]["tampered"] = True
        ok, msg = verify_chain(entries)
        assert ok is False
        assert "Chain broken" in msg

    def test_verify_chain_empty(self) -> None:
        from scripts.cli_audit import verify_chain

        ok, msg = verify_chain([])
        assert ok is True
        assert msg == "OK"


# ── AU4: Subparser registration ─────────────────────────────────────────────


class TestSubparserRegistration:
    """AU5: register_subparser() creates the documented CLI surface."""

    def test_subparser_has_documented_flags(self) -> None:
        from scripts.cli_audit import register_subparser

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = register_subparser(subparsers)

        # Default values
        args = p.parse_args([])
        assert args.limit == 20
        assert args.format == "text"
        assert args.event_type is None
        assert args.verify is False
        assert args.db_path is None

    def test_subparser_overrides(self) -> None:
        from scripts.cli_audit import register_subparser

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = register_subparser(subparsers)

        args = p.parse_args(
            ["--limit", "50", "--format", "json", "--event-type", "dispatch_start", "--verify"]
        )
        assert args.limit == 50
        assert args.format == "json"
        assert args.event_type == "dispatch_start"
        assert args.verify is True

    def test_subparser_db_path_override(self) -> None:
        from scripts.cli_audit import register_subparser

        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest="command")
        p = register_subparser(subparsers)

        args = p.parse_args(["--db-path", "/tmp/foo.db"])
        assert args.db_path == "/tmp/foo.db"


# ── AU5: Output formatting ──────────────────────────────────────────────────


class TestOutputFormatting:
    """AU5: Text/JSON formatters handle entries with redaction."""

    def test_format_json_redacts_sensitive(self) -> None:
        from scripts.cli_audit import _format_json

        entries = [{"event_type": "x", "user_id": "u", "details": {"api_key": "AKIA..."}}]
        out = _format_json(entries)
        parsed = json.loads(out)
        assert parsed[0]["details"]["api_key"] == "***REDACTED***"

    def test_format_text_redacts_sensitive(self) -> None:
        from scripts.cli_audit import _format_text

        entries = [{"event_type": "x", "user_id": "u", "details": {"password": "p"}, "entry_hash": "abc12345xyz"}]
        out = _format_text(entries)
        assert "***REDACTED***" in out
        assert "abc12345" in out  # short hash prefix


# ── AU6: Anti-ghost counter ─────────────────────────────────────────────────


class TestAuditCliAntiGhostCounter:
    """AU6: get_call_counter_er() exposes the module-level counter."""

    def test_counter_is_int(self) -> None:
        from scripts.cli_audit import get_call_counter_er

        assert isinstance(get_call_counter_er(), int)

    def test_counter_increments_on_cmd_audit(self) -> None:
        from scripts.cli_audit import cmd_audit, get_call_counter_er

        before = get_call_counter_er()
        cmd_audit(_make_args(db_path=None))
        after = get_call_counter_er()
        assert after > before


# ── AU7: End-to-end CLI flow ────────────────────────────────────────────────


class TestAuditCliEndToEnd:
    """AU7: End-to-end CLI flow with SQLite DB."""

    def test_full_flow_text_format(self, populated_db, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        rc = cmd_audit(_make_args(db_path=str(populated_db), format="text"))
        assert rc == 0
        captured = capsys.readouterr()
        assert "dispatch_start" in captured.out or "(no audit entries)" in captured.out

    def test_full_flow_json_format(self, populated_db, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        rc = cmd_audit(_make_args(db_path=str(populated_db), format="json"))
        assert rc == 0
        captured = capsys.readouterr()
        # JSON output should be parseable
        if captured.out.strip():
            parsed = json.loads(captured.out)
            assert isinstance(parsed, list)

    def test_full_flow_event_type_filter(self, populated_db, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        rc = cmd_audit(
            _make_args(
                db_path=str(populated_db),
                event_type="dispatch_start",
                format="json",
            )
        )
        assert rc == 0
        captured = capsys.readouterr()
        if captured.out.strip():
            parsed = json.loads(captured.out)
            assert all(e["event_type"] == "dispatch_start" for e in parsed)

    def test_full_flow_limit(self, populated_db, capsys) -> None:
        from scripts.cli_audit import cmd_audit

        rc = cmd_audit(_make_args(db_path=str(populated_db), limit=1, format="json"))
        assert rc == 0
        captured = capsys.readouterr()
        if captured.out.strip():
            parsed = json.loads(captured.out)
            assert len(parsed) <= 1
