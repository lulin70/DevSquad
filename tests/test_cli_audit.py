#!/usr/bin/env python3
"""Tests for Audit CLI — V4.5.3 P12.2.6.

Coverage:
    - Sensitive field redaction
    - Text / JSON output format
    - Hash chain verification (pass + tamper)
    - Filter by event_type + limit
    - Anti-ghost _call_counter
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, ".")

from scripts.cli_audit import (  # noqa: E402
    _format_json,
    _format_text,
    _load_entries,
    _redact_sensitive,
    cmd_audit,
    get_call_counter_er,
    register_subparser,
    verify_chain,
)


class TestRedactSensitive(unittest.TestCase):
    """Verify sensitive field redaction."""

    def test_redacts_api_key(self):
        result = _redact_sensitive({"api_key": "sk-12345", "user": "alice"})
        self.assertEqual(result["api_key"], "***REDACTED***")
        self.assertEqual(result["user"], "alice")

    def test_redacts_nested(self):
        result = _redact_sensitive(
            {"details": {"password": "secret", "info": "public"}}
        )
        self.assertEqual(result["details"]["password"], "***REDACTED***")
        self.assertEqual(result["details"]["info"], "public")

    def test_case_insensitive(self):
        result = _redact_sensitive({"API_KEY": "k", "Token": "t", "PASSWORD": "p"})
        self.assertEqual(result["API_KEY"], "***REDACTED***")
        self.assertEqual(result["Token"], "***REDACTED***")
        self.assertEqual(result["PASSWORD"], "***REDACTED***")

    def test_list_redaction(self):
        result = _redact_sensitive([{"api_key": "k"}, "plain"])
        self.assertEqual(result[0]["api_key"], "***REDACTED***")
        self.assertEqual(result[1], "plain")

    def test_non_sensitive_unchanged(self):
        result = _redact_sensitive({"task_id": "t1", "duration": 1.5})
        self.assertEqual(result["task_id"], "t1")
        self.assertEqual(result["duration"], 1.5)


class TestFormatText(unittest.TestCase):
    """Verify text formatter output."""

    def test_empty(self):
        self.assertEqual(_format_text([]), "")

    def test_basic_entry(self):
        entries = [
            {
                "event_type": "dispatch_start",
                "user_id": "alice",
                "timestamp": 1700000000.123,
                "details": {"task_id": "t1"},
                "entry_hash": "abcdef1234567890" * 4,
            }
        ]
        out = _format_text(entries)
        self.assertIn("dispatch_start", out)
        self.assertIn("alice", out)
        self.assertIn("task_id", out)


class TestFormatJson(unittest.TestCase):
    """Verify JSON formatter output."""

    def test_valid_json(self):
        entries = [{"event_type": "x", "user_id": "u", "details": {}}]
        out = _format_json(entries)
        parsed = json.loads(out)
        self.assertEqual(len(parsed), 1)

    def test_redacts_in_json(self):
        entries = [{"event_type": "x", "user_id": "u", "details": {"api_key": "secret"}}]
        out = _format_json(entries)
        self.assertNotIn("secret", out)
        self.assertIn("REDACTED", out)


class TestVerifyChain(unittest.TestCase):
    """Verify hash chain integrity check."""

    def _make_entry(self, prev_hash, event_type, user_id, ts, details):
        import hashlib

        details_json = json.dumps(details, sort_keys=True, separators=(",", ":"))
        payload = (
            f"{prev_hash}"
            f"{len(event_type):d}:{event_type}"
            f"{len(user_id):d}:{user_id}"
            f"{ts:.6f}"
            f"{details_json}"
        ).encode()
        h = hashlib.sha256(payload).hexdigest()
        return {
            "event_type": event_type,
            "user_id": user_id,
            "timestamp": ts,
            "details": details,
            "prev_hash": prev_hash,
            "entry_hash": h,
        }

    def test_valid_chain(self):
        e1 = self._make_entry("0" * 64, "dispatch_start", "alice", 100.0, {"k": 1})
        e2 = self._make_entry(
            e1["entry_hash"], "dispatch_end", "alice", 101.0, {"k": 2}
        )
        ok, msg = verify_chain([e1, e2])
        self.assertTrue(ok)
        self.assertEqual(msg, "OK")

    def test_empty_chain_is_valid(self):
        ok, msg = verify_chain([])
        self.assertTrue(ok)

    def test_tampered_chain_detected(self):
        e1 = self._make_entry("0" * 64, "dispatch_start", "alice", 100.0, {"k": 1})
        e2 = self._make_entry(
            e1["entry_hash"], "dispatch_end", "alice", 101.0, {"k": 2}
        )
        # Tamper with e2's details
        e2["details"] = {"k": 999}
        ok, msg = verify_chain([e1, e2])
        self.assertFalse(ok)
        self.assertIn("Chain broken", msg)


class TestLoadEntries(unittest.TestCase):
    """Verify _load_entries from SQLite."""

    def setUp(self):
        self.tmp = tempfile.NamedTemporaryFile(  # noqa: SIM115
            mode="w", suffix=".db", delete=False
        )
        self.tmp.close()
        self.db_path = self.tmp.name

    def tearDown(self):
        os.unlink(self.db_path)

    def _setup_db(self, entries):
        # Match DispatchAuditLogger's schema
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "CREATE TABLE dispatch_audit ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "event_type TEXT, user_id TEXT, timestamp REAL, "
            "details TEXT, prev_hash TEXT, entry_hash TEXT)"
        )
        for e in entries:
            conn.execute(
                "INSERT INTO dispatch_audit "
                "(event_type, user_id, timestamp, details, prev_hash, entry_hash) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    e["event_type"],
                    e["user_id"],
                    e["timestamp"],
                    json.dumps(e["details"]),
                    e["prev_hash"],
                    e["entry_hash"],
                ),
            )
        conn.commit()
        conn.close()

    def test_loads_entries_from_sqlite(self):
        self._setup_db(
            [
                {
                    "event_type": "dispatch_start",
                    "user_id": "u1",
                    "timestamp": 100.0,
                    "details": {"x": 1},
                    "prev_hash": "0" * 64,
                    "entry_hash": "a" * 64,
                }
            ]
        )
        entries = _load_entries(self.db_path)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["event_type"], "dispatch_start")

    def test_missing_db_returns_empty(self):
        entries = _load_entries("/nonexistent/path.db")
        self.assertEqual(entries, [])


class TestCmdAudit(unittest.TestCase):
    """Verify cmd_audit end-to-end behavior."""

    def setUp(self):
        import scripts.cli_audit as mod

        mod._call_counter_er = 0

    def test_no_db_path_returns_empty(self):
        import argparse

        args = argparse.Namespace(
            db_path=None,
            limit=20,
            format="text",
            event_type=None,
            verify=False,
        )
        # Should not crash
        rc = cmd_audit(args)
        self.assertEqual(rc, 0)

    def test_call_counter_increments(self):
        import argparse

        before = get_call_counter_er()
        args = argparse.Namespace(
            db_path=None, limit=20, format="text", event_type=None, verify=False
        )
        cmd_audit(args)
        self.assertGreater(get_call_counter_er(), before)


class TestRegisterSubparser(unittest.TestCase):
    """Verify subparser registration."""

    def test_register_subparser(self):
        import argparse

        parser = argparse.ArgumentParser()
        sub = parser.add_subparsers(dest="cmd")
        p = register_subparser(sub)
        self.assertIn("audit", str(p))


if __name__ == "__main__":
    unittest.main()
