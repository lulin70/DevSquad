#!/usr/bin/env python3
"""Unit tests for V4.4.3 ScratchpadHistoryStore — SQLite cross-session archive.

Iron Rules applied:
  1. Documentation-first: source (scripts/collaboration/scratchpad_history_store.py)
     read first. Documented: write() filters content via OutputValidator.redact()
     before persistence; search_history() AND-combines optional filters;
     cleanup_expired() deletes entries older than retention_days; file perms 0600.
     NOTE: source referenced ``entry.created_at`` but ScratchpadEntry (models_base)
     only has ``timestamp`` — that was a real bug, fixed in the source before
     these tests were written (write() now uses entry.timestamp; search_history
     reconstructs via timestamp=). These tests verify the corrected behavior.
  2. Failure-means-report: real SQLite (tempfile paths), no Mock.
  3. Dimension-completeness: 15 tests across 7 dimensions (matrix below).
  4. Side-effect-verification: redaction on write, file perms, cleanup, call_counter.
  5. User-journey-first: cross-session search + Scratchpad integration mirror the
     "search past sessions" journey.
  6. e2e-release-gate: covered by tests/e2e/test_v443_persistence.py.

Dimension matrix (15 tests):
  Happy      (8): write_and_search, search_across_sessions, search_by_role,
                  search_by_type, search_by_date, empty_query_returns_all,
                  cleanup_expired, scratchpad_integration
  Error      (3): sql_injection, retention_zero, concurrent_writes (error-free under concurrency)
  Boundary   (3): empty_query_returns_all, search_by_date (future since), retention_zero
  Performance(1): write_performance
  Config     (5): search_by_role, search_by_type, search_by_date, retention_zero, db_permissions
  Integration(3): search_across_sessions, concurrent_writes, scratchpad_integration
  Side-Effect(4): sensitive_data_redacted, cleanup_expired, db_permissions, call_counter

Anti-ghost note: ``_call_counter_er`` is a module-level int rebound on each public
call. We read it via module attribute access (``shs_module._call_counter_er``),
NOT ``from module import _call_counter_er`` (which would snapshot a stale int).
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.collaboration import scratchpad_history_store as shs_module  # noqa: E402
from scripts.collaboration.models_base import EntryType, ScratchpadEntry  # noqa: E402
from scripts.collaboration.scratchpad import Scratchpad  # noqa: E402
from scripts.collaboration.scratchpad_history_store import ScratchpadHistoryStore  # noqa: E402

# A realistic OpenAI-style key that OutputValidator recognizes (sk- + >=32 alnum).
# The literal short example "sk-abc123secretkey" is only 16 chars after "sk-"
# and does NOT match the validator's ``sk-[A-Za-z0-9]{32,}`` pattern, so it
# would never be redacted. We use a 40-char key so redaction actually fires.
_SENSITIVE_API_KEY = "sk-" + "a" * 40


class TestScratchpadHistoryStore(unittest.TestCase):
    """V4.4.3 ScratchpadHistoryStore unit tests (15 tests, 7 dimensions)."""

    def setUp(self) -> None:
        self._tmpdir = tempfile.mkdtemp(prefix="devsquad_shs_")
        self._db_path = Path(self._tmpdir) / "history.db"
        self._stores: list[ScratchpadHistoryStore] = []

    def tearDown(self) -> None:
        import contextlib

        for store in self._stores:
            with contextlib.suppress(Exception):
                store.close()
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _new_store(self, retention_days: int = 90) -> ScratchpadHistoryStore:
        store = ScratchpadHistoryStore(self._db_path, retention_days=retention_days)
        self._stores.append(store)
        return store

    @staticmethod
    def _entry(
        content: str = "test content",
        *,
        role_id: str = "architect",
        entry_type: EntryType = EntryType.FINDING,
        worker_id: str = "w-1",
        entry_id: str | None = None,
        timestamp: datetime | None = None,
        tags: list[str] | None = None,
        confidence: float = 0.8,
    ) -> ScratchpadEntry:
        return ScratchpadEntry(
            entry_id=entry_id or f"entry-{os.urandom(6).hex()}",
            worker_id=worker_id,
            role_id=role_id,
            entry_type=entry_type,
            content=content,
            confidence=confidence,
            tags=tags or [],
            timestamp=timestamp or datetime.now(),
        )

    # ------------------------------------------------------------------
    # Happy: write + search
    # ------------------------------------------------------------------

    def test_write_and_search_basic(self) -> None:
        """Happy: write one entry, keyword search finds it with preserved fields."""
        store = self._new_store()
        entry = self._entry("Decided to use PostgreSQL for primary DB")
        store.write(entry, scratchpad_id="sp-session-1")

        results = store.search_history(query="PostgreSQL")
        self.assertEqual(len(results), 1)
        got = results[0]
        self.assertEqual(got.content, entry.content)
        self.assertEqual(got.role_id, "architect")
        self.assertEqual(got.entry_type, EntryType.FINDING)
        self.assertEqual(got.worker_id, "w-1")
        self.assertAlmostEqual(got.confidence, 0.8)

    def test_search_across_sessions(self) -> None:
        """Happy/Integration: search returns entries from multiple scratchpad sessions."""
        store = self._new_store()
        store.write(self._entry("auth design note", entry_id="e1"), "sp-2026-08-01")
        store.write(self._entry("auth refactor note", entry_id="e2"), "sp-2026-08-02")
        store.write(self._entry("unrelated billing note", entry_id="e3"), "sp-2026-08-03")

        results = store.search_history(query="auth")
        self.assertEqual(len(results), 2)
        contents = {r.content for r in results}
        self.assertIn("auth design note", contents)
        self.assertIn("auth refactor note", contents)

    def test_search_by_role(self) -> None:
        """Happy/Config: filter by role_id returns only that role's entries."""
        store = self._new_store()
        store.write(self._entry("arch finding", role_id="architect", entry_id="a1"), "sp1")
        store.write(self._entry("test finding", role_id="tester", entry_id="t1"), "sp1")

        results = store.search_history(role_id="tester")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].role_id, "tester")
        self.assertEqual(results[0].content, "test finding")

    def test_search_by_entry_type(self) -> None:
        """Happy/Config: filter by entry_type returns only that type."""
        store = self._new_store()
        store.write(self._entry("a finding", entry_type=EntryType.FINDING, entry_id="f1"), "sp1")
        store.write(self._entry("a decision", entry_type=EntryType.DECISION, entry_id="d1"), "sp1")
        store.write(self._entry("a conflict", entry_type=EntryType.CONFLICT, entry_id="c1"), "sp1")

        results = store.search_history(entry_type=EntryType.DECISION)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].entry_type, EntryType.DECISION)

    def test_search_by_date_since(self) -> None:
        """Happy/Config/Boundary: ``since`` filter excludes older entries; future since -> empty."""
        store = self._new_store()
        old_ts = datetime.now() - timedelta(days=10)
        new_ts = datetime.now() - timedelta(hours=1)
        store.write(self._entry("old entry", entry_id="o1", timestamp=old_ts), "sp1")
        store.write(self._entry("new entry", entry_id="n1", timestamp=new_ts), "sp1")

        cutoff = datetime.now() - timedelta(days=1)
        results = store.search_history(since=cutoff)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].content, "new entry")

        # Boundary: a future ``since`` returns nothing.
        future = datetime.now() + timedelta(days=1)
        self.assertEqual(store.search_history(since=future), [])

    def test_empty_query_returns_all(self) -> None:
        """Happy/Boundary: empty query (default) returns all entries up to limit."""
        store = self._new_store()
        for i in range(5):
            store.write(self._entry(f"entry-{i}", entry_id=f"all-{i}"), "sp1")

        results = store.search_history()  # no filters
        self.assertEqual(len(results), 5)
        # Newest first (ORDER BY created_at DESC) — entry timestamps are ~now,
        # so ordering is by insert/rowid; just assert all present.
        contents = {r.content for r in results}
        self.assertEqual(contents, {f"entry-{i}" for i in range(5)})

    # ------------------------------------------------------------------
    # Side-Effect / Security: sensitive data redaction
    # ------------------------------------------------------------------

    def test_sensitive_data_api_key_redacted(self) -> None:
        """Side-Effect/Security: API key in content is redacted before persistence."""
        store = self._new_store()
        content = f"Using key {_SENSITIVE_API_KEY} for the upstream API"
        store.write(self._entry(content, entry_id="sec1"), "sp1")

        results = store.search_history(query="key")
        self.assertEqual(len(results), 1)
        persisted = results[0].content
        # The original secret MUST NOT be present in the persisted content.
        self.assertNotIn(_SENSITIVE_API_KEY, persisted,
                         "API key was persisted in cleartext — redaction failed")
        # The redaction marker (OutputValidator emits "***") must be present.
        self.assertIn("***", persisted)
        # Non-sensitive context survives.
        self.assertIn("upstream API", persisted)

    # ------------------------------------------------------------------
    # Error / Security: SQL injection
    # ------------------------------------------------------------------

    def test_sql_injection_prevention(self) -> None:
        """Error/Security: malicious query string is treated as a literal (parameterized)."""
        store = self._new_store()
        store.write(self._entry("legitimate auth finding", entry_id="leg1"), "sp1")

        injection = "'; DROP TABLE scratchpad_history; --"
        # Must NOT raise and must NOT drop the table.
        results = store.search_history(query=injection)
        self.assertEqual(results, [])  # no content matches the literal injection string

        # Table is intact: a legit search still returns the entry.
        survivors = store.search_history(query="legitimate")
        self.assertEqual(len(survivors), 1)
        self.assertEqual(survivors[0].content, "legitimate auth finding")

    # ------------------------------------------------------------------
    # Side-Effect: cleanup
    # ------------------------------------------------------------------

    def test_cleanup_expired_deletes_old_only(self) -> None:
        """Happy/Side-Effect: cleanup_expired deletes old entries, keeps recent."""
        store = self._new_store(retention_days=90)
        old_ts = datetime.now() - timedelta(days=100)
        new_ts = datetime.now() - timedelta(hours=1)
        store.write(self._entry("old entry", entry_id="old1", timestamp=old_ts), "sp1")
        store.write(self._entry("new entry", entry_id="new1", timestamp=new_ts), "sp1")

        deleted = store.cleanup_expired()
        self.assertEqual(deleted, 1)
        remaining = store.search_history()
        self.assertEqual(len(remaining), 1)
        self.assertEqual(remaining[0].content, "new entry")

    def test_retention_zero_deletes_all(self) -> None:
        """Boundary/Config/Error: retention_days=0 makes every entry eligible for cleanup."""
        store = self._new_store(retention_days=0)
        # Use a clearly-past timestamp so it's strictly older than cutoff (now).
        past_ts = datetime.now() - timedelta(seconds=5)
        store.write(self._entry("stale entry", entry_id="s1", timestamp=past_ts), "sp1")

        deleted = store.cleanup_expired()
        self.assertEqual(deleted, 1)
        self.assertEqual(store.search_history(), [])

    # ------------------------------------------------------------------
    # Side-Effect / Config: file permissions
    # ------------------------------------------------------------------

    def test_db_file_permissions_0600(self) -> None:
        """Side-Effect/Config: SQLite file is created with mode 0600 (owner rw only)."""
        store = self._new_store()
        # Trigger a write so the file definitely exists on disk.
        store.write(self._entry("perm check", entry_id="p1"), "sp1")
        self.assertTrue(self._db_path.exists())
        mode = self._db_path.stat().st_mode & 0o777
        self.assertEqual(mode, 0o600, f"expected 0600, got {oct(mode)}")

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    def test_write_performance(self) -> None:
        """Performance: 200 writes complete in < 1000ms."""
        store = self._new_store()
        start = time.perf_counter()
        for i in range(200):
            store.write(self._entry(f"perf entry {i}", entry_id=f"perf-{i}"), "sp-perf")
        elapsed_ms = (time.perf_counter() - start) * 1000
        self.assertLess(elapsed_ms, 1000.0, f"200 writes too slow: {elapsed_ms:.1f}ms")
        # All 200 persisted.
        self.assertEqual(len(store.search_history(limit=500)), 200)

    # ------------------------------------------------------------------
    # Side-Effect: anti-ghost call counter
    # ------------------------------------------------------------------

    def test_call_counter_anti_ghost(self) -> None:
        """Side-Effect: module-level _call_counter_er increments on every public call."""
        before = shs_module._call_counter_er
        store = self._new_store()
        store.write(self._entry("counter check", entry_id="cnt1"), "sp1")
        store.search_history()
        store.cleanup_expired()
        after = shs_module._call_counter_er
        self.assertGreater(after, before, "module _call_counter_er did not increment")
        # __init__ + write + search + cleanup => at least 4 increments.
        self.assertGreaterEqual(after - before, 4)

    # ------------------------------------------------------------------
    # Error / Integration: concurrent writes
    # ------------------------------------------------------------------

    def test_concurrent_writes_thread_safe(self) -> None:
        """Error/Integration: concurrent writes from many threads all persist (no errors)."""
        store = self._new_store()
        n_threads = 8
        per_thread = 25
        errors: list[Exception] = []

        def writer(tid: int) -> None:
            try:
                for j in range(per_thread):
                    store.write(
                        self._entry(f"t{tid}-entry{j}", entry_id=f"t{tid}-{j}", worker_id=f"w-{tid}"),
                        "sp-concurrent",
                    )
            except Exception as exc:  # noqa: BLE001 — collect any failure
                errors.append(exc)

        threads = [threading.Thread(target=writer, args=(t,)) for t in range(n_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [], f"concurrent writes raised: {errors}")
        results = store.search_history(limit=1000)
        self.assertEqual(len(results), n_threads * per_thread)

    # ------------------------------------------------------------------
    # Integration: Scratchpad mirrors writes to history store
    # ------------------------------------------------------------------

    def test_scratchpad_integration_mirrors_writes(self) -> None:
        """Integration: Scratchpad(history_store=...) mirrors every write to SQLite."""
        store = self._new_store()
        sp = Scratchpad(scratchpad_id="sp-integ", history_store=store)

        entry = ScratchpadEntry(
            worker_id="arch-1",
            role_id="architect",
            entry_type=EntryType.DECISION,
            content="Adopt PostgreSQL for persistence",
            confidence=0.9,
            tags=["db", "decision"],
        )
        sp.write(entry)

        # The in-memory Scratchpad has the entry...
        self.assertEqual(len(sp.read(query="PostgreSQL")), 1)
        # ...and it was mirrored to the cross-session SQLite archive.
        archived = store.search_history(query="PostgreSQL")
        self.assertEqual(len(archived), 1)
        self.assertEqual(archived[0].content, "Adopt PostgreSQL for persistence")
        self.assertEqual(archived[0].role_id, "architect")
        self.assertEqual(archived[0].entry_type, EntryType.DECISION)


if __name__ == "__main__":
    unittest.main()
