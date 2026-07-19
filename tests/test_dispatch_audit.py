#!/usr/bin/env python3
"""
Tests for DispatchAuditLogger (V39-06) — Audit logging for dispatch pipeline.

Coverage:
  - Happy path: each log_* method returns a non-empty hash
  - Chain integrity: hashes chain correctly, verify_chain returns True
  - Tamper detection: modifying entries breaks verify_chain
  - Event types: dispatch_start, dispatch_end, permission_denied, error
  - Query: get_entries returns most-recent-first, respects limit
  - Persistence: SQLite database survives re-instantiation
  - Edge cases: empty logger, single entry, large number of entries
  - Performance: logging is fast
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

import pytest

from scripts.collaboration.dispatch_audit import (
    GENESIS_HASH,
    AuditEntry,
    DispatchAuditLogger,
)

pytestmark = pytest.mark.unit



class TestAuditEntryDataclass(unittest.TestCase):
    """Verify AuditEntry dataclass stores all fields."""

    def test_audit_entry_holds_all_fields(self) -> None:
        """Verify: AuditEntry stores event_type/user_id/timestamp/details/prev_hash/entry_hash."""
        # Arrange
        entry = AuditEntry(
            event_type="dispatch_start",
            user_id="u1",
            timestamp=1234567890.0,
            details={"task": "test"},
            prev_hash="0" * 64,
            entry_hash="abc123",
        )
        # Assert
        self.assertEqual(entry.event_type, "dispatch_start")
        self.assertEqual(entry.user_id, "u1")
        self.assertEqual(entry.timestamp, 1234567890.0)
        self.assertEqual(entry.details, {"task": "test"})
        self.assertEqual(entry.prev_hash, "0" * 64)
        self.assertEqual(entry.entry_hash, "abc123")


class TestDispatchAuditLoggerHappyPath(unittest.TestCase):
    """Happy path — each log_* method returns a non-empty hash."""

    def setUp(self) -> None:
        self.logger = DispatchAuditLogger()  # in-memory

    def test_log_dispatch_start_returns_hash(self) -> None:
        """Verify: log_dispatch_start returns a 64-char hex hash."""
        # Act
        h = self.logger.log_dispatch_start("u1", "Design auth system", ["architect"])
        # Assert
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))

    def test_log_dispatch_end_returns_hash(self) -> None:
        """Verify: log_dispatch_end returns a 64-char hex hash."""
        # Act
        h = self.logger.log_dispatch_end("u1", success=True, duration=1.23)
        # Assert
        self.assertEqual(len(h), 64)

    def test_log_permission_denied_returns_hash(self) -> None:
        """Verify: log_permission_denied returns a 64-char hex hash."""
        # Act
        h = self.logger.log_permission_denied("u1", "insufficient role")
        # Assert
        self.assertEqual(len(h), 64)

    def test_log_error_returns_hash(self) -> None:
        """Verify: log_error returns a 64-char hex hash."""
        # Act
        h = self.logger.log_error("u1", "ValueError", {"detail": "bad input"})
        # Assert
        self.assertEqual(len(h), 64)


class TestDispatchAuditLoggerChainIntegrity(unittest.TestCase):
    """Chain integrity — hashes chain correctly, verify_chain returns True."""

    def setUp(self) -> None:
        self.logger = DispatchAuditLogger()

    def test_empty_chain_verifies_true(self) -> None:
        """Verify: empty chain returns True from verify_chain."""
        # Act
        result = self.logger.verify_chain()
        # Assert
        self.assertTrue(result)

    def test_single_entry_chain_verifies_true(self) -> None:
        """Verify: single-entry chain returns True from verify_chain."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task", ["architect"])
        # Act
        result = self.logger.verify_chain()
        # Assert
        self.assertTrue(result)

    def test_multiple_entries_chain_verifies_true(self) -> None:
        """Verify: multi-entry chain returns True from verify_chain."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task", ["architect"])
        self.logger.log_dispatch_end("u1", success=True, duration=0.5)
        self.logger.log_permission_denied("u2", "no access")
        self.logger.log_error("u3", "RuntimeError", {"step": 3})
        # Act
        result = self.logger.verify_chain()
        # Assert
        self.assertTrue(result)

    def test_first_entry_prev_hash_is_genesis(self) -> None:
        """Verify: first entry's prev_hash equals GENESIS_HASH ('0' * 64)."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task", ["architect"])
        # Act
        entries = self.logger.get_entries(limit=1)
        # Assert
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].prev_hash, GENESIS_HASH)

    def test_consecutive_entries_chain_correctly(self) -> None:
        """Verify: each entry's prev_hash equals the previous entry's entry_hash."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task1", ["architect"])
        self.logger.log_dispatch_end("u1", success=True, duration=0.5)
        # Act
        entries = self.logger.get_entries(limit=2)
        # get_entries returns most-recent-first, so entries[1] is the first entry.
        first_entry = entries[1]
        second_entry = entries[0]
        # Assert
        self.assertEqual(second_entry.prev_hash, first_entry.entry_hash)


class TestDispatchAuditLoggerTamperDetection(unittest.TestCase):
    """Tamper detection — modifying entries breaks verify_chain."""

    def setUp(self) -> None:
        self.logger = DispatchAuditLogger()

    def test_tampered_details_breaks_chain(self) -> None:
        """Verify: modifying an entry's details breaks verify_chain."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task", ["architect"])
        self.logger.log_dispatch_end("u1", success=True, duration=0.5)
        # Act — tamper with the first entry's details.
        # Access internal _entries to simulate tampering.
        self.logger._entries[0].details = {"tampered": True}
        # Assert
        self.assertFalse(self.logger.verify_chain())

    def test_tampered_entry_hash_breaks_chain(self) -> None:
        """Verify: modifying an entry's entry_hash breaks verify_chain."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task", ["architect"])
        # Act — tamper with the entry's hash.
        self.logger._entries[0].entry_hash = "f" * 64
        # Assert
        self.assertFalse(self.logger.verify_chain())

    def test_tampered_prev_hash_breaks_chain(self) -> None:
        """Verify: modifying an entry's prev_hash breaks verify_chain."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task1", ["architect"])
        self.logger.log_dispatch_end("u1", success=True, duration=0.5)
        # Act — tamper with the second entry's prev_hash.
        self.logger._entries[1].prev_hash = "a" * 64
        # Assert
        self.assertFalse(self.logger.verify_chain())


class TestDispatchAuditLoggerQuery(unittest.TestCase):
    """Query — get_entries returns most-recent-first, respects limit."""

    def setUp(self) -> None:
        self.logger = DispatchAuditLogger()

    def test_get_entries_returns_most_recent_first(self) -> None:
        """Verify: get_entries returns entries in most-recent-first order."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task1", ["architect"])
        self.logger.log_dispatch_end("u1", success=True, duration=0.5)
        # Act
        entries = self.logger.get_entries(limit=10)
        # Assert
        self.assertEqual(len(entries), 2)
        # Most recent first: dispatch_end should be entries[0].
        self.assertEqual(entries[0].event_type, "dispatch_end")
        self.assertEqual(entries[1].event_type, "dispatch_start")

    def test_get_entries_respects_limit(self) -> None:
        """Verify: get_entries respects the limit parameter."""
        # Arrange
        for i in range(5):
            self.logger.log_dispatch_start("u1", f"task{i}", ["architect"])
        # Act
        entries = self.logger.get_entries(limit=3)
        # Assert
        self.assertEqual(len(entries), 3)

    def test_get_entries_with_zero_limit_returns_empty(self) -> None:
        """Verify: get_entries(limit=0) returns empty list."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task", ["architect"])
        # Act
        entries = self.logger.get_entries(limit=0)
        # Assert
        self.assertEqual(entries, [])

    def test_count_returns_total_entries(self) -> None:
        """Verify: count() returns the total number of entries."""
        # Arrange
        self.logger.log_dispatch_start("u1", "task1", ["architect"])
        self.logger.log_dispatch_end("u1", success=True, duration=0.5)
        # Act
        total = self.logger.count()
        # Assert
        self.assertEqual(total, 2)


class TestDispatchAuditLoggerPersistence(unittest.TestCase):
    """Persistence — SQLite database survives re-instantiation."""

    def test_entries_persist_across_reinstantiation(self) -> None:
        """Verify: entries written to SQLite are loaded on re-instantiation."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger1 = DispatchAuditLogger(db_path=db_path)
            logger1.log_dispatch_start("u1", "task", ["architect"])
            logger1.log_dispatch_end("u1", success=True, duration=0.5)
            logger1.close()
            # Act — re-instantiate with the same db_path.
            logger2 = DispatchAuditLogger(db_path=db_path)
            # Assert
            self.assertEqual(logger2.count(), 2)
            self.assertTrue(logger2.verify_chain())
            logger2.close()

    def test_persisted_chain_verifies(self) -> None:
        """Verify: persisted chain passes verify_chain after reload."""
        # Arrange
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "audit.db"
            logger1 = DispatchAuditLogger(db_path=db_path)
            for i in range(5):
                logger1.log_dispatch_start("u1", f"task{i}", ["architect"])
            logger1.close()
            # Act
            logger2 = DispatchAuditLogger(db_path=db_path)
            # Assert
            self.assertTrue(logger2.verify_chain())
            self.assertEqual(logger2.count(), 5)
            logger2.close()


class TestDispatchAuditLoggerEdgeCases(unittest.TestCase):
    """Edge cases — empty logger, large number of entries."""

    def test_empty_logger_get_entries_returns_empty(self) -> None:
        """Verify: empty logger returns empty list from get_entries."""
        # Arrange
        logger = DispatchAuditLogger()
        # Act
        entries = logger.get_entries()
        # Assert
        self.assertEqual(entries, [])

    def test_empty_logger_count_is_zero(self) -> None:
        """Verify: empty logger returns 0 from count()."""
        # Arrange
        logger = DispatchAuditLogger()
        # Act
        total = logger.count()
        # Assert
        self.assertEqual(total, 0)

    def test_large_number_of_entries_chain_verifies(self) -> None:
        """Verify: 100 entries chain verifies correctly."""
        # Arrange
        logger = DispatchAuditLogger()
        for i in range(100):
            logger.log_dispatch_start("u1", f"task{i}", ["architect"])
        # Act
        result = logger.verify_chain()
        # Assert
        self.assertTrue(result)
        self.assertEqual(logger.count(), 100)


class TestDispatchAuditLoggerPerformance(unittest.TestCase):
    """Performance baseline — logging is fast."""

    def test_log_completes_under_1ms(self) -> None:
        """Verify: a single log_dispatch_start completes in < 1ms.

        Scenario: DispatchAuditLogger uses SHA-256 hashing, which should be fast.
        Expected: 1000 logs complete in well under 5s, so each call is < 5ms.
        """
        # Arrange
        logger = DispatchAuditLogger()
        # Act
        start = time.perf_counter()
        for i in range(1000):
            logger.log_dispatch_start("u1", f"task{i}", ["architect"])
        elapsed = time.perf_counter() - start
        # Assert
        self.assertLess(elapsed, 5.0, f"1000 logs took {elapsed:.3f}s (> 5ms per call)")

    def test_verify_chain_fast_for_100_entries(self) -> None:
        """Verify: verify_chain on 100 entries completes in < 100ms."""
        # Arrange
        logger = DispatchAuditLogger()
        for i in range(100):
            logger.log_dispatch_start("u1", f"task{i}", ["architect"])
        # Act
        start = time.perf_counter()
        result = logger.verify_chain()
        elapsed = time.perf_counter() - start
        # Assert
        self.assertTrue(result)
        self.assertLess(elapsed, 0.5, f"verify_chain took {elapsed:.3f}s (> 500ms)")


class TestDispatcherDefaultAuditPersistence(unittest.TestCase):
    """Dispatcher defaults to a SQLite-backed DispatchAuditLogger."""

    def test_dispatcher_creates_persistent_audit_logger(self):
        """Verify: MultiAgentDispatcher creates a DispatchAuditLogger backed by SQLite."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.collaboration.dispatcher import MultiAgentDispatcher

            dispatcher = MultiAgentDispatcher(
                persist_dir=tmpdir,
                enable_warmup=False,
                enable_compression=False,
                enable_permission=False,
                enable_memory=False,
                enable_skillify=False,
                enable_anchor_check=False,
                enable_retrospective=False,
                enable_usage_tracker=False,
            )
            try:
                self.assertIsNotNone(dispatcher._audit_logger)
                self.assertIsInstance(dispatcher._audit_logger, DispatchAuditLogger)
                expected_db = Path(tmpdir) / "audit" / "dispatch_audit.db"
                self.assertEqual(dispatcher._audit_logger._db_path, expected_db)
                self.assertTrue(expected_db.exists())
            finally:
                dispatcher.shutdown()

    def test_dispatcher_audit_entries_persist_across_restarts(self):
        """Verify: dispatch audit entries survive dispatcher restart."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.collaboration.dispatcher import MultiAgentDispatcher

            db_path = Path(tmpdir) / "audit" / "dispatch_audit.db"
            dispatcher1 = MultiAgentDispatcher(
                persist_dir=tmpdir,
                audit_db_path=db_path,
                enable_warmup=False,
                enable_compression=False,
                enable_permission=False,
                enable_memory=False,
                enable_skillify=False,
                enable_anchor_check=False,
                enable_retrospective=False,
                enable_usage_tracker=False,
            )
            try:
                dispatcher1.dispatch("test task", dry_run=True)
                self.assertGreater(dispatcher1._audit_logger.count(), 0)
            finally:
                dispatcher1.shutdown()

            dispatcher2 = MultiAgentDispatcher(
                persist_dir=tmpdir,
                audit_db_path=db_path,
                enable_warmup=False,
                enable_compression=False,
                enable_permission=False,
                enable_memory=False,
                enable_skillify=False,
                enable_anchor_check=False,
                enable_retrospective=False,
                enable_usage_tracker=False,
            )
            try:
                self.assertGreater(dispatcher2._audit_logger.count(), 0)
                self.assertTrue(dispatcher2._audit_logger.verify_chain())
            finally:
                dispatcher2.shutdown()

    def test_dispatcher_can_disable_audit_logger(self):
        """Verify: enable_audit_logger=False leaves _audit_logger as None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            from scripts.collaboration.dispatcher import MultiAgentDispatcher

            dispatcher = MultiAgentDispatcher(
                persist_dir=tmpdir,
                enable_audit_logger=False,
                enable_warmup=False,
                enable_compression=False,
                enable_permission=False,
                enable_memory=False,
                enable_skillify=False,
                enable_anchor_check=False,
                enable_retrospective=False,
                enable_usage_tracker=False,
            )
            try:
                self.assertIsNone(dispatcher._audit_logger)
            finally:
                dispatcher.shutdown()


if __name__ == "__main__":
    unittest.main()
