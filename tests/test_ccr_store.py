#!/usr/bin/env python3
"""Tests for CCRStore (V3.10.0 Phase 3 §5.4).

Dimension coverage (per Testing Iron Rule 3):
  - Happy Path: store→retrieve round-trip, metadata, stats
  - Boundary: empty content, missing trace_id, LRU at capacity, TTL=0
  - Error: nonexistent trace_id returns ""
  - Performance: store+retrieve 100 entries <500ms
  - Integration: LRU miss→SQLite fallback, LRU hit path, concurrency
"""

from __future__ import annotations

import sqlite3
import threading
import time
import unittest

from scripts.collaboration.ccr_store import CCRStore


class TestCCRStoreStoreRetrieve(unittest.TestCase):
    """Verify: store returns trace_id; retrieve returns original."""

    def test_store_returns_hex_trace_id(self):
        """Verify: trace_id is 32-char hex (uuid4.hex)."""
        with CCRStore(":memory:") as store:
            trace_id = store.store("hello world")
            self.assertEqual(len(trace_id), 32)
            self.assertTrue(all(c in "0123456789abcdef" for c in trace_id))

    def test_retrieve_returns_stored_content(self):
        """Verify: round-trip store→retrieve preserves content."""
        with CCRStore(":memory:") as store:
            trace_id = store.store("original content here")
            self.assertEqual(store.retrieve(trace_id), "original content here")

    def test_retrieve_nonexistent_returns_empty(self):
        """Verify: unknown trace_id → empty string (not exception)."""
        with CCRStore(":memory:") as store:
            self.assertEqual(store.retrieve("nonexistent_id"), "")

    def test_store_empty_string(self):
        """Verify: empty string content can be stored and retrieved."""
        with CCRStore(":memory:") as store:
            trace_id = store.store("")
            self.assertEqual(store.retrieve(trace_id), "")

    def test_store_large_content(self):
        """Verify: large content (100KB) round-trips correctly."""
        large = "x" * 100_000
        with CCRStore(":memory:") as store:
            trace_id = store.store(large)
            self.assertEqual(store.retrieve(trace_id), large)

    def test_store_with_metadata(self):
        """Verify: metadata is accepted without error (stored as JSON)."""
        with CCRStore(":memory:") as store:
            trace_id = store.store(
                "content", metadata={"source": "smart_crusher", "type": "json_array"}
            )
            self.assertEqual(store.retrieve(trace_id), "content")


class TestCCRStoreQueryExcerpt(unittest.TestCase):
    """Verify: retrieve with query returns keyword-filtered excerpt."""

    def test_query_returns_matching_lines_only(self):
        """Verify: query 'error' returns only lines containing 'error'."""
        content = "line one\nERROR: something failed\nline three\nerror: lower"
        with CCRStore(":memory:") as store:
            trace_id = store.store(content)
            result = store.retrieve(trace_id, query="error")
            self.assertIn("ERROR: something failed", result)
            self.assertIn("error: lower", result)
            self.assertNotIn("line one", result)
            self.assertNotIn("line three", result)

    def test_query_case_insensitive(self):
        """Verify: query matching is case-insensitive."""
        content = "Warning: high memory\nINFO: ok"
        with CCRStore(":memory:") as store:
            trace_id = store.store(content)
            result = store.retrieve(trace_id, query="WARNING")
            self.assertIn("Warning: high memory", result)
            self.assertNotIn("INFO: ok", result)

    def test_query_no_match_returns_full_original(self):
        """Verify: query with no matches → full original returned."""
        content = "line one\nline two"
        with CCRStore(":memory:") as store:
            trace_id = store.store(content)
            result = store.retrieve(trace_id, query="nonexistent_keyword")
            self.assertEqual(result, content)

    def test_query_empty_string_returns_full(self):
        """Verify: empty query string → full original."""
        with CCRStore(":memory:") as store:
            trace_id = store.store("full content")
            self.assertEqual(store.retrieve(trace_id, query=""), "full content")

    def test_query_none_returns_full(self):
        """Verify: query=None → full original."""
        with CCRStore(":memory:") as store:
            trace_id = store.store("full content")
            self.assertEqual(store.retrieve(trace_id, query=None), "full content")


class TestCCRStoreLRUEviction(unittest.TestCase):
    """Verify: LRU cache evicts oldest entries beyond capacity."""

    def test_lru_evicts_oldest_from_cache(self):
        """Verify: storing beyond lru_max_size evicts oldest from LRU (not DB)."""
        with CCRStore(":memory:", lru_max_size=3) as store:
            ids = [store.store(f"content-{i}") for i in range(5)]
            # LRU should only hold last 3
            self.assertEqual(store.stats()["lru_size"], 3)
            # But all 5 are in SQLite
            self.assertEqual(store.stats()["total_entries"], 5)
            # Evicted entry still retrievable from SQLite
            self.assertEqual(store.retrieve(ids[0]), "content-0")

    def test_lru_move_to_end_on_retrieve(self):
        """Verify: retrieving an entry moves it to most-recently-used."""
        with CCRStore(":memory:", lru_max_size=2) as store:
            id_a = store.store("a")
            id_b = store.store("b")
            # Retrieve A to make it recently used
            store.retrieve(id_a)
            # Store C — should evict B (least recently used), not A
            store.store("c")
            self.assertEqual(store.stats()["lru_size"], 2)
            # A should still be in LRU; B should have been evicted
            self.assertIn(id_a, store._lru)
            self.assertNotIn(id_b, store._lru)


class TestCCRStoreTTLExpiry(unittest.TestCase):
    """Verify: delete_expired removes old entries."""

    def test_delete_expired_removes_old_entries(self):
        """Verify: entries older than ttl_days are deleted."""
        from datetime import datetime, timedelta

        with CCRStore(":memory:") as store:
            # Store a fresh entry
            fresh_id = store.store("fresh")
            # Manually insert an old entry with backdated created_at
            old_created = (datetime.now() - timedelta(days=10)).isoformat()
            store._conn.execute(
                "INSERT INTO ccr_entries (trace_id, original, metadata, created_at, last_accessed, access_count) "
                "VALUES (?, ?, NULL, ?, ?, 0)",
                ("oldtraceid", "old content", old_created, old_created),
            )
            store._conn.commit()
            self.assertEqual(store.stats()["total_entries"], 2)
            # Delete entries older than 7 days
            deleted = store.delete_expired(ttl_days=7)
            self.assertEqual(deleted, 1)
            self.assertEqual(store.stats()["total_entries"], 1)
            # Fresh entry survives
            self.assertEqual(store.retrieve(fresh_id), "fresh")
            # Old entry gone
            self.assertEqual(store.retrieve("oldtraceid"), "")

    def test_delete_expired_zero_days_removes_all(self):
        """Verify: ttl_days=0 removes everything."""
        with CCRStore(":memory:") as store:
            store.store("a")
            store.store("b")
            deleted = store.delete_expired(ttl_days=0)
            self.assertEqual(deleted, 2)
            self.assertEqual(store.stats()["total_entries"], 0)

    def test_delete_expired_nothing_to_delete(self):
        """Verify: delete_expired returns 0 when all entries are fresh."""
        with CCRStore(":memory:") as store:
            store.store("fresh")
            deleted = store.delete_expired(ttl_days=30)
            self.assertEqual(deleted, 0)


class TestCCRStoreStats(unittest.TestCase):
    """Verify: stats() returns correct metrics."""

    def test_stats_empty_store(self):
        """Verify: fresh store has 0 entries."""
        with CCRStore(":memory:") as store:
            stats = store.stats()
            self.assertEqual(stats["total_entries"], 0)
            self.assertEqual(stats["lru_size"], 0)
            self.assertEqual(stats["lru_max_size"], 128)

    def test_stats_after_stores(self):
        """Verify: stats reflects stored entries."""
        with CCRStore(":memory:", lru_max_size=10) as store:
            for i in range(5):
                store.store(f"content-{i}")
            stats = store.stats()
            self.assertEqual(stats["total_entries"], 5)
            self.assertEqual(stats["lru_size"], 5)
            self.assertEqual(stats["lru_max_size"], 10)

    def test_stats_custom_lru_max(self):
        """Verify: custom lru_max_size reflected in stats."""
        with CCRStore(":memory:", lru_max_size=256) as store:
            self.assertEqual(store.stats()["lru_max_size"], 256)


class TestCCRStoreLRUMissFallback(unittest.TestCase):
    """Verify: LRU miss falls back to SQLite correctly."""

    def test_lru_miss_retrieves_from_sqlite(self):
        """Verify: after LRU eviction, retrieve still works from SQLite."""
        with CCRStore(":memory:", lru_max_size=1) as store:
            id_a = store.store("content-a")
            store.store("content-b")  # evicts A from LRU
            self.assertNotIn(id_a, store._lru)
            # Retrieve A — should fall back to SQLite and re-populate LRU
            self.assertEqual(store.retrieve(id_a), "content-a")
            self.assertIn(id_a, store._lru)


class TestCCRStoreConcurrency(unittest.TestCase):
    """Verify: concurrent access is thread-safe."""

    def test_concurrent_stores_no_corruption(self):
        """Verify: 50 threads storing simultaneously produce 50 entries."""
        with CCRStore(":memory:") as store:
            threads = []
            errors: list[Exception] = []

            def worker(i: int) -> None:
                try:
                    store.store(f"thread-{i}")
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            for i in range(50):
                t = threading.Thread(target=worker, args=(i,))
                threads.append(t)
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(len(errors), 0)
            self.assertEqual(store.stats()["total_entries"], 50)


class TestCCRStoreContextManager(unittest.TestCase):
    """Verify: context manager opens and closes cleanly."""

    def test_context_manager_closes_connection(self):
        """Verify: __exit__ closes the SQLite connection."""
        store = CCRStore(":memory:")
        store.__enter__()
        store.store("data")
        store.__exit__(None, None, None)
        # Connection should be closed — sqlite3 raises ProgrammingError
        with self.assertRaises(sqlite3.ProgrammingError):
            store.stats()


class TestCCRStorePerformance(unittest.TestCase):
    """Verify: store+retrieve meets performance targets."""

    def test_store_retrieve_100_entries_under_500ms(self):
        """Verify: 100 store+retrieve cycles complete in <500ms."""
        with CCRStore(":memory:") as store:
            start = time.perf_counter()
            trace_ids = []
            for i in range(100):
                tid = store.store(f"content-{i}" * 50)
                trace_ids.append(tid)
            for tid in trace_ids:
                store.retrieve(tid)
            elapsed_ms = (time.perf_counter() - start) * 1000
            self.assertLess(elapsed_ms, 500, f"too slow: {elapsed_ms:.1f}ms")


if __name__ == "__main__":
    unittest.main()
