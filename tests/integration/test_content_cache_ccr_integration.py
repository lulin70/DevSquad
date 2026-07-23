#!/usr/bin/env python3
"""ContentCache + CCRStore + Scratchpad Integration Tests (V4.2.1 P2-1 — Test Pyramid Improvement).

End-to-end integration tests for the reversible-compression + content-cache
trio. Verifies CROSS-MODULE interactions between:

    scripts/collaboration/content_cache.py  — ContentCache (SHA-256 keys,
        sensitive-data filtering, wraps an LLMCacheBase backend)
    scripts/collaboration/ccr_store.py      — CCRStore (SQLite + in-memory
        LRU, reversible compression store; SmartCrusher stores the original
        here and emits a ``retrieve full: trace_id=X`` marker)
    scripts/collaboration/scratchpad.py     — Scratchpad (shared blackboard;
        ``write_compressed`` stores a summary + CCRStore trace_id pointer for
        lazy retrieval of the original content)
    scripts/collaboration/content_crusher.py — SmartCrusher (structure-aware
        compressor that bridges content → CCRStore)

These tests focus on CROSS-MODULE interactions among the trio. Unit-level
behavior of each module is covered by:
    - tests/test_content_cache.py
    - tests/test_ccr_store.py
    - tests/test_token_budget_compressed_scratchpad.py
    - tests/integration/test_ccr_marker_integration.py (SmartCrusher + CCRStore)

Test categories:
    T1: ContentCache + CCRStore + SmartCrusher basic integration
    T2: Scratchpad compressed entry + CCRStore lazy retrieval
    T3: Sensitive-data filtering across ContentCache ↔ CCRStore
    T4: CCRStore TTL expiry (delete_expired) integration
    T5: CCRStore LRU eviction integration
    T6: Thread-safety across the trio
    T7: Edge cases + graceful degradation
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import threading
import unittest
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.ccr_store import CCRStore
from scripts.collaboration.content_cache import ContentCache
from scripts.collaboration.content_crusher import SmartCrusher
from scripts.collaboration.llm_cache import LLMCache
from scripts.collaboration.models import CompressedScratchpadEntry, EntryType, ScratchpadEntry
from scripts.collaboration.scratchpad import _DEVSQUAD_RETRIEVE_PATTERN, _RETRIEVE_FULL_PATTERN, Scratchpad

# Regex to extract a trace_id from a SmartCrusher ``retrieve full: trace_id=X`` marker.
_TRACE_ID_RE = re.compile(r"trace_id=([0-9a-f]+)")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_json_array(num_items: int = 100) -> str:
    """Build a JSON array string large enough to trigger SmartCrusher compression."""
    items = [{"id": i, "name": f"item-{i}", "type": "record", "status": "ok"} for i in range(num_items)]
    return json.dumps(items, ensure_ascii=False)


def _extract_trace_id(text: str) -> str:
    """Extract the first trace_id from a SmartCrusher-emitted marker."""
    match = _TRACE_ID_RE.search(text)
    assert match is not None, f"no trace_id found in: {text!r}"
    return match.group(1)


def _make_llm_cache() -> tuple[LLMCache, str]:
    """Build a real LLMCache backed by a fresh temp dir. Returns (cache, tmpdir)."""
    tmpdir = tempfile.mkdtemp(prefix="ccr_integ_llm_")
    return LLMCache(cache_dir=tmpdir, ttl_seconds=300), tmpdir


# ---------------------------------------------------------------------------
# T1: ContentCache + CCRStore + SmartCrusher basic integration
# ---------------------------------------------------------------------------


class T1_ContentCacheCCRStoreSmartCrusherIntegration(unittest.TestCase):
    """T1: Compose SmartCrusher → CCRStore → ContentCache end-to-end."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:")
        self._crusher = SmartCrusher(ccr_store=self._store)
        self._llm_cache, self._llm_dir = _make_llm_cache()
        self._cache = ContentCache(wrapped=self._llm_cache)

    def tearDown(self) -> None:
        self._llm_cache.clear()
        shutil.rmtree(self._llm_dir, ignore_errors=True)
        self._store.close()

    def test_01_crushed_response_cached_and_original_retrievable(self) -> None:
        """Verify: crush → cache compressed → ContentCache hit → CCRStore returns original."""
        original = _make_json_array(100)
        crushed = self._crusher.crush(original)
        # Original was stored in CCRStore; compressed carries a trace_id marker.
        self.assertIn("retrieve full: trace_id=", crushed)
        # Cache the compressed response through ContentCache.
        self.assertTrue(self._cache.set("prompt-1", crushed, "openai", "gpt-4"))
        cached = self._cache.get("prompt-1", "openai", "gpt-4")
        self.assertEqual(cached, crushed)
        self.assertEqual(self._cache.hits, 1)
        # The original is still lazily retrievable from CCRStore via the marker.
        trace_id = _extract_trace_id(cached)
        self.assertEqual(self._store.retrieve(trace_id), original)

    def test_02_cache_miss_then_set_enables_hit(self) -> None:
        """Verify: fresh prompt misses, then set enables a hit on the next get."""
        self.assertIsNone(self._cache.get("absent", "openai", "gpt-4"))
        self.assertEqual(self._cache.misses, 1)
        self._cache.set("absent", "payload", "openai", "gpt-4")
        self.assertEqual(self._cache.get("absent", "openai", "gpt-4"), "payload")
        self.assertEqual(self._cache.hits, 1)

    def test_03_repeated_cache_hits_keep_original_retrievable(self) -> None:
        """Verify: multiple ContentCache hits do not evict the CCRStore original."""
        original = _make_json_array(50)
        crushed = self._crusher.crush(original)
        trace_id = _extract_trace_id(crushed)
        self._cache.set("prompt-x", crushed, "openai", "gpt-4")
        for _ in range(3):
            self.assertEqual(self._cache.get("prompt-x", "openai", "gpt-4"), crushed)
        self.assertEqual(self._cache.hits, 3)
        # CCRStore original survives independent of ContentCache hit counts.
        self.assertEqual(self._store.retrieve(trace_id), original)

    def test_04_different_backends_isolated_caching(self) -> None:
        """Verify: same prompt cached under different backends stays isolated."""
        self._cache.set("shared-prompt", "openai-resp", "openai", "gpt-4")
        self._cache.set("shared-prompt", "anthropic-resp", "anthropic", "claude-3")
        self.assertEqual(self._cache.get("shared-prompt", "openai", "gpt-4"), "openai-resp")
        self.assertEqual(self._cache.get("shared-prompt", "anthropic", "claude-3"), "anthropic-resp")

    def test_05_ccrstore_independent_of_contentcache_invalidation(self) -> None:
        """Verify: invalidating ContentCache does not touch CCRStore originals."""
        original = _make_json_array(80)
        crushed = self._crusher.crush(original)
        trace_id = _extract_trace_id(crushed)
        self._cache.set("prompt-y", crushed, "openai", "gpt-4")
        # Whole-cache invalidation clears ContentCache but not CCRStore.
        self._cache.invalidate("*")
        self.assertEqual(self._store.retrieve(trace_id), original)
        self.assertEqual(self._store.stats()["total_entries"], 1)

    def test_06_invalidate_wildcard_falls_through_to_clear_on_llmcache(self) -> None:
        """Verify: V4.2.1 bugfix — invalidate("*") on LLMCache backend falls through to clear().

        Previously, ContentCache.invalidate("*") detected that LLMCache has an
        invalidate() method (hasattr=True), called it with a single pattern arg,
        caught the TypeError (LLMCache.invalidate requires 3 args: prompt/backend/model),
        and returned 0 immediately — never reaching the clear() fallback. Now the
        TypeError falls through to the clear() fallback, so the whole cache is cleared.
        """
        llm_cache = LLMCache(":memory:")
        cache = ContentCache(llm_cache)
        cache.set("prompt-a", "response-a", "openai", "gpt-4")
        cache.set("prompt-b", "response-b", "anthropic", "claude-3")
        # Both entries should be cached
        self.assertEqual(cache.get("prompt-a", "openai", "gpt-4"), "response-a")
        self.assertEqual(cache.get("prompt-b", "anthropic", "claude-3"), "response-b")
        # invalidate("*") should clear the cache via clear() fallback
        result = cache.invalidate("*")
        # Should return 1 (best-effort "cleared" signal) — not 0 (old bug behavior)
        self.assertEqual(result, 1,
                         "invalidate('*') on LLMCache should fall through to clear() "
                         "and return 1, not silently return 0 (V4.2.1 bugfix)")
        # Both entries should now be gone
        self.assertIsNone(cache.get("prompt-a", "openai", "gpt-4"))
        self.assertIsNone(cache.get("prompt-b", "anthropic", "claude-3"))


# ---------------------------------------------------------------------------
# T2: Scratchpad compressed entry + CCRStore lazy retrieval
# ---------------------------------------------------------------------------


class T2_ScratchpadCCRStoreLazyRetrievalIntegration(unittest.TestCase):
    """T2: Scratchpad.write_compressed + CCRStore trace_id lazy retrieval."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:")
        self._crusher = SmartCrusher(ccr_store=self._store)
        self._sp = Scratchpad()

    def tearDown(self) -> None:
        self._sp.clear()
        self._store.close()

    def test_01_write_compressed_then_retrieve_original_on_demand(self) -> None:
        """Verify: write_compressed stores summary+trace_id; original retrieved lazily."""
        original = _make_json_array(120)
        crushed = self._crusher.crush(original)
        trace_id = _extract_trace_id(crushed)
        entry = self._sp.write_compressed(
            summary=crushed,
            trace_id=trace_id,
            original_size=len(original),
            compressed_size=len(crushed),
        )
        self.assertEqual(entry.trace_id, trace_id)
        entries = self._sp.read_compressed_entries()
        self.assertEqual(len(entries), 1)
        # Lazy retrieval: pull the original from CCRStore using the stored trace_id.
        self.assertEqual(self._store.retrieve(entries[0].trace_id), original)

    def test_02_compressed_entry_records_reduction_ratio(self) -> None:
        """Verify: CompressedScratchpadEntry.reduction_ratio reflects compression."""
        original = _make_json_array(200)
        crushed = self._crusher.crush(original)
        trace_id = _extract_trace_id(crushed)
        entry = self._sp.write_compressed(
            summary=crushed,
            trace_id=trace_id,
            original_size=len(original),
            compressed_size=len(crushed),
        )
        self.assertGreater(entry.original_size, entry.compressed_size)
        self.assertGreater(entry.reduction_ratio, 0.5)

    def test_03_multiple_compressed_entries_each_independently_retrievable(self) -> None:
        """Verify: multiple write_compressed entries resolve to distinct originals."""
        originals = [_make_json_array(60 + i * 10) for i in range(3)]
        for original in originals:
            crushed = self._crusher.crush(original)
            trace_id = _extract_trace_id(crushed)
            self._sp.write_compressed(summary=crushed, trace_id=trace_id)
        entries = self._sp.read_compressed_entries()
        self.assertEqual(len(entries), 3)
        retrieved = {self._store.retrieve(e.trace_id) for e in entries}
        self.assertEqual(retrieved, set(originals))

    def test_04_devsquad_retrieve_regex_matches_canonical_marker(self) -> None:
        """Verify: _DEVSQUAD_RETRIEVE_PATTERN matches devsquad_retrieve(trace_id=X, query=Y)."""
        trace_id = "a" * 32  # CCRStore emits 32-char hex trace_ids.
        marker = f'devsquad_retrieve(trace_id={trace_id}, query="error")'
        match = _DEVSQUAD_RETRIEVE_PATTERN.search(marker)
        self.assertIsNotNone(match)
        assert match is not None  # narrowing for type checkers
        self.assertEqual(match.group(1), trace_id)
        self.assertEqual(match.group(2), "error")

    def test_05_retrieve_full_pattern_matches_smartcrusher_marker(self) -> None:
        """Verify: _RETRIEVE_FULL_PATTERN matches SmartCrusher's 'retrieve full:' marker.

        V4.2.1 bugfix: SmartCrusher emits ``retrieve full: trace_id=X`` in compressed
        content headers. Previously the Coordinator only scanned for
        ``devsquad_retrieve(trace_id=X)`` markers and missed SmartCrusher's format,
        so compressed originals were never auto-retrieved. The _RETRIEVE_FULL_PATTERN
        regex now detects both formats.
        """
        trace_id = "b" * 32
        smartcrusher_marker = f"[100 items compressed to 7; retrieve full: trace_id={trace_id}]"
        # _DEVSQUAD_RETRIEVE_PATTERN still does not match (different format)
        self.assertIsNone(_DEVSQUAD_RETRIEVE_PATTERN.search(smartcrusher_marker))
        # _RETRIEVE_FULL_PATTERN now matches (V4.2.1 bugfix)
        match = _RETRIEVE_FULL_PATTERN.search(smartcrusher_marker)
        self.assertIsNotNone(match)
        assert match is not None  # for type checker
        self.assertEqual(match.group(1), trace_id)


# ---------------------------------------------------------------------------
# T3: Sensitive-data filtering across ContentCache ↔ CCRStore
# ---------------------------------------------------------------------------


class T3_SensitiveFilteringIntegration(unittest.TestCase):
    """T3: ContentCache secret filtering vs. CCRStore (no built-in filter)."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:")
        self._llm_cache, self._llm_dir = _make_llm_cache()
        self._cache = ContentCache(wrapped=self._llm_cache)

    def tearDown(self) -> None:
        self._llm_cache.clear()
        shutil.rmtree(self._llm_dir, ignore_errors=True)
        self._store.close()

    def test_01_secret_response_never_cached_by_contentcache(self) -> None:
        """Verify: a secret-bearing response is filtered out of ContentCache."""
        secret_response = "api_key=sk-1234567890abcdef1234567890abcdef leak"
        self.assertFalse(self._cache.set("clean-prompt", secret_response, "openai", "gpt-4"))
        self.assertEqual(self._cache.filtered, 1)
        # Nothing was persisted: a get reports a miss, not the secret.
        self.assertIsNone(self._cache.get("clean-prompt", "openai", "gpt-4"))

    def test_02_secret_prompt_blocked_on_get_and_set(self) -> None:
        """Verify: a secret prompt is blocked on both set and get paths."""
        secret_prompt = "password=hunter2topsecret describe the system"
        self.assertFalse(self._cache.set(secret_prompt, "resp", "openai", "gpt-4"))
        self.assertIsNone(self._cache.get(secret_prompt, "openai", "gpt-4"))
        self.assertGreaterEqual(self._cache.filtered, 2)

    def test_03_ccrstore_has_no_builtin_sensitive_filter(self) -> None:
        """Verify: CCRStore stores secret content unchanged (filtering is ContentCache's job).

        Cross-module contract: in a composed pipeline the sensitive-data gate lives
        in ContentCache. CCRStore is a raw reversible store with no secret scan, so
        callers must filter *before* storing originals in CCRStore.
        """
        secret = "token=abcdef1234567890abcdef1234567890 supersecret"
        trace_id = self._store.store(secret)
        self.assertEqual(self._store.retrieve(trace_id), secret)

    def test_04_clean_content_round_trips_through_both_caches(self) -> None:
        """Verify: clean content is cached by ContentCache AND its original in CCRStore."""
        clean_original = _make_json_array(90)
        trace_id = self._store.store(clean_original)
        # ContentCache happily caches a clean response that references the trace_id.
        clean_response = f"summary; retrieve full: trace_id={trace_id}"
        self.assertTrue(self._cache.set("prompt-clean", clean_response, "openai", "gpt-4"))
        self.assertEqual(self._cache.get("prompt-clean", "openai", "gpt-4"), clean_response)
        self.assertEqual(self._cache.filtered, 0)
        self.assertEqual(self._store.retrieve(trace_id), clean_original)


# ---------------------------------------------------------------------------
# T4: CCRStore TTL expiry (delete_expired) integration
# ---------------------------------------------------------------------------


class T4_CCRStoreTTLExpiryIntegration(unittest.TestCase):
    """T4: CCRStore TTL via delete_expired(ttl_days) — no auto-expiry on retrieve."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:")

    def tearDown(self) -> None:
        self._store.close()

    def _insert_backdated_entry(self, trace_id: str, content: str, days_old: int) -> None:
        """Insert a row with a backdated created_at to simulate aging."""
        old_ts = (datetime.now() - timedelta(days=days_old)).isoformat()
        self._store._conn.execute(
            "INSERT INTO ccr_entries (trace_id, original, metadata, created_at, last_accessed, access_count) "
            "VALUES (?, ?, NULL, ?, ?, 0)",
            (trace_id, content, old_ts, old_ts),
        )
        self._store._conn.commit()
        self._store._lru[trace_id] = content

    def test_01_delete_expired_removes_old_entries(self) -> None:
        """Verify: delete_expired(ttl_days=7) removes entries older than 7 days."""
        fresh_id = self._store.store("fresh-content")
        self._insert_backdated_entry("oldtraceid0001", "old-content", days_old=10)
        self.assertEqual(self._store.stats()["total_entries"], 2)
        deleted = self._store.delete_expired(ttl_days=7)
        self.assertEqual(deleted, 1)
        self.assertEqual(self._store.stats()["total_entries"], 1)
        self.assertEqual(self._store.retrieve(fresh_id), "fresh-content")

    def test_02_expired_entry_retrieve_returns_empty_string(self) -> None:
        """Verify: after delete_expired, retrieve returns '' (not None) for purged trace_id."""
        self._insert_backdated_entry("expiredtrace01", "gone", days_old=30)
        self.assertEqual(self._store.retrieve("expiredtrace01"), "gone")
        self._store.delete_expired(ttl_days=7)
        self.assertEqual(self._store.retrieve("expiredtrace01"), "")

    def test_03_fresh_entries_survive_expiry(self) -> None:
        """Verify: freshly-stored entries survive a delete_expired sweep."""
        ids = [self._store.store(f"fresh-{i}") for i in range(3)]
        deleted = self._store.delete_expired(ttl_days=7)
        self.assertEqual(deleted, 0)
        for i, tid in enumerate(ids):
            self.assertEqual(self._store.retrieve(tid), f"fresh-{i}")

    def test_04_delete_expired_purges_lru_cache_too(self) -> None:
        """Verify: delete_expired also evicts purged trace_ids from the in-memory LRU."""
        self._insert_backdated_entry("staletrace0002", "stale", days_old=20)
        self.assertIn("staletrace0002", self._store._lru)
        self._store.delete_expired(ttl_days=7)
        self.assertNotIn("staletrace0002", self._store._lru)


# ---------------------------------------------------------------------------
# T5: CCRStore LRU eviction integration
# ---------------------------------------------------------------------------


class T5_CCRStoreLRUEvictionIntegration(unittest.TestCase):
    """T5: CCRStore in-memory LRU eviction + SQLite fallback."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:", lru_max_size=3)

    def tearDown(self) -> None:
        self._store.close()

    def test_01_lru_evicts_oldest_beyond_capacity(self) -> None:
        """Verify: storing beyond lru_max_size caps the in-memory LRU."""
        for i in range(5):
            self._store.store(f"content-{i}")
        self.assertEqual(self._store.stats()["lru_size"], 3)
        # SQLite retains all entries.
        self.assertEqual(self._store.stats()["total_entries"], 5)

    def test_02_evicted_lru_entry_retrievable_from_sqlite(self) -> None:
        """Verify: an entry evicted from LRU is still retrievable via SQLite fallback."""
        ids = [self._store.store(f"content-{i}") for i in range(5)]
        # First stored entry was evicted from LRU (LRU holds last 3).
        self.assertNotIn(ids[0], self._store._lru)
        # ...but SQLite still has it, and retrieve re-populates the LRU.
        self.assertEqual(self._store.retrieve(ids[0]), "content-0")
        self.assertIn(ids[0], self._store._lru)

    def test_03_retrieve_moves_entry_to_most_recently_used(self) -> None:
        """Verify: retrieving an entry protects it from the next LRU eviction."""
        id_a = self._store.store("a")
        id_b = self._store.store("b")
        id_c = self._store.store("c")  # LRU now full at capacity: [a, b, c].
        # Touch A so it becomes most-recently-used → B becomes least-recently-used.
        self._store.retrieve(id_a)  # LRU order is now [b, c, a].
        # Storing a 4th entry triggers eviction of the LRU (b), not a.
        self._store.store("d")  # LRU becomes [c, a, d].
        self.assertIn(id_a, self._store._lru)
        self.assertIn(id_c, self._store._lru)
        self.assertNotIn(id_b, self._store._lru)

    def test_04_scratchpad_compressed_entry_survives_lru_eviction(self) -> None:
        """Verify: a Scratchpad compressed entry's original survives LRU pressure."""
        sp = Scratchpad()
        try:
            # Store an original, then evict it from LRU by storing many more entries.
            original = "important original content for lazy retrieval"
            trace_id = self._store.store(original)
            sp.write_compressed(summary="compressed summary", trace_id=trace_id)
            for i in range(10):
                self._store.store(f"filler-{i}")
            self.assertNotIn(trace_id, self._store._lru)
            entries = sp.read_compressed_entries()
            self.assertEqual(len(entries), 1)
            # Lazy retrieval still works via SQLite fallback.
            self.assertEqual(self._store.retrieve(entries[0].trace_id), original)
        finally:
            sp.clear()


# ---------------------------------------------------------------------------
# T6: Thread-safety across the trio
# ---------------------------------------------------------------------------


class T6_ThreadSafetyIntegration(unittest.TestCase):
    """T6: Concurrent store/retrieve/cache operations across the trio."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:")
        self._llm_cache, self._llm_dir = _make_llm_cache()
        self._cache = ContentCache(wrapped=self._llm_cache)

    def tearDown(self) -> None:
        self._llm_cache.clear()
        shutil.rmtree(self._llm_dir, ignore_errors=True)
        self._store.close()

    def test_01_concurrent_ccrstore_store_and_retrieve(self) -> None:
        """Verify: 40 threads storing + retrieving produce no corruption."""
        trace_ids: list[str] = []
        errors: list[Exception] = []
        barrier = threading.Barrier(40)

        def worker(idx: int) -> None:
            try:
                barrier.wait()
                tid = self._store.store(f"thread-content-{idx}")
                trace_ids.append(tid)
                self.assertEqual(self._store.retrieve(tid), f"thread-content-{idx}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(40)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self._store.stats()["total_entries"], 40)
        self.assertEqual(len(trace_ids), 40)
        self.assertEqual(len(set(trace_ids)), 40, "trace_ids must be unique across threads")

    def test_02_concurrent_scratchpad_write_compressed(self) -> None:
        """Verify: concurrent Scratchpad.write_compressed entries all land."""
        sp = Scratchpad()
        errors: list[Exception] = []
        try:
            def worker(idx: int) -> None:
                try:
                    tid = self._store.store(f"orig-{idx}")
                    sp.write_compressed(summary=f"summary-{idx}", trace_id=tid)
                except Exception as exc:  # noqa: BLE001
                    errors.append(exc)

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(30)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            entries = sp.read_compressed_entries()
            self.assertEqual(len(entries), 30)
            # Every compressed entry's original is retrievable.
            for e in entries:
                self.assertTrue(self._store.retrieve(e.trace_id).startswith("orig-"))
        finally:
            sp.clear()

    def test_03_concurrent_contentcache_get_set(self) -> None:
        """Verify: concurrent ContentCache get/set does not corrupt cache state."""
        errors: list[Exception] = []
        barrier = threading.Barrier(20)

        def worker(idx: int) -> None:
            try:
                barrier.wait()
                prompt = f"concurrent-prompt-{idx % 5}"
                self._cache.set(prompt, f"resp-{idx}", "openai", "gpt-4")
                self._cache.get(prompt, "openai", "gpt-4")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self._cache.hits + self._cache.misses, 20)

    def test_04_concurrent_mixed_trio_operations(self) -> None:
        """Verify: mixed crush → cache → retrieve across threads is consistent."""
        crusher = SmartCrusher(ccr_store=self._store)
        original = _make_json_array(100)
        errors: list[Exception] = []
        hits: list[int] = []
        lock = threading.Lock()

        def worker() -> None:
            try:
                crushed = crusher.crush(original)
                self._cache.set("shared-trio", crushed, "openai", "gpt-4")
                cached = self._cache.get("shared-trio", "openai", "gpt-4")
                if cached is not None and "trace_id=" in cached:
                    trace_id = _extract_trace_id(cached)
                    # At least one original must be retrievable.
                    self.assertEqual(self._store.retrieve(trace_id), original)
                    with lock:
                        hits.append(1)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertGreater(len(hits), 0)


# ---------------------------------------------------------------------------
# T7: Edge cases + graceful degradation
# ---------------------------------------------------------------------------


class T7_EdgeCasesAndGracefulDegradationIntegration(unittest.TestCase):
    """T7: Empty content, missing trace_id, no-op cache, in-memory scratchpad."""

    def setUp(self) -> None:
        self._store = CCRStore(":memory:")

    def tearDown(self) -> None:
        self._store.close()

    def test_01_empty_content_round_trips_through_ccrstore(self) -> None:
        """Verify: empty string content stores and retrieves as empty string."""
        trace_id = self._store.store("")
        self.assertEqual(self._store.retrieve(trace_id), "")

    def test_02_nonexistent_trace_id_retrieves_as_empty(self) -> None:
        """Verify: retrieve of an unknown trace_id returns '' (no exception)."""
        self.assertEqual(self._store.retrieve("doesnotexist0000000000000000000000"), "")

    def test_03_contentcache_with_none_wrapped_is_noop(self) -> None:
        """Verify: ContentCache(wrapped=None) degrades to no-op get/set."""
        noop_cache = ContentCache(wrapped=None)
        self.assertIsNone(noop_cache.get("prompt", "openai", "gpt-4"))
        self.assertFalse(noop_cache.set("prompt", "resp", "openai", "gpt-4"))
        self.assertEqual(noop_cache.misses, 0)
        self.assertEqual(noop_cache.filtered, 0)

    def test_04_scratchpad_clear_purges_compressed_entries(self) -> None:
        """Verify: Scratchpad.clear() removes compressed entries alongside regular ones."""
        sp = Scratchpad()
        try:
            sp.write_compressed(summary="s1", trace_id="t1")
            sp.write_compressed(summary="s2", trace_id="t2")
            self.assertEqual(len(sp.read_compressed_entries()), 2)
            sp.clear()
            self.assertEqual(sp.read_compressed_entries(), [])
        finally:
            sp.clear()

    def test_05_in_memory_scratchpad_works_without_persist_dir(self) -> None:
        """Verify: Scratchpad with persist_dir=None operates purely in memory."""
        sp = Scratchpad()
        try:
            entry = ScratchpadEntry(
                worker_id="w1",
                role_id="architect",
                entry_type=EntryType.FINDING,
                content="in-memory finding",
            )
            sp.write(entry)
            results = sp.read(query="in-memory")
            self.assertEqual(len(results), 1)
            self.assertEqual(results[0].content, "in-memory finding")
        finally:
            sp.clear()

    def test_06_compressed_entry_with_empty_trace_id_does_not_crash(self) -> None:
        """Verify: a compressed entry whose trace_id is empty degrades gracefully on retrieve."""
        sp = Scratchpad()
        try:
            sp.write_compressed(summary="orphan summary", trace_id="")
            entries = sp.read_compressed_entries()
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].trace_id, "")
            # Retrieving with an empty trace_id returns "" (CCRStore miss), not a crash.
            self.assertEqual(self._store.retrieve(""), "")
        finally:
            sp.clear()

    def test_07_compressed_entry_serialization_round_trip(self) -> None:
        """Verify: CompressedScratchpadEntry to_dict/from_dict preserves trace_id."""
        entry = CompressedScratchpadEntry(
            summary="summary text",
            trace_id="deadbeef" * 4,
            original_size=1000,
            compressed_size=50,
        )
        data = entry.to_dict()
        restored = CompressedScratchpadEntry.from_dict(data)
        self.assertEqual(restored.trace_id, entry.trace_id)
        self.assertEqual(restored.summary, entry.summary)
        self.assertEqual(restored.original_size, entry.original_size)
        self.assertEqual(restored.compressed_size, entry.compressed_size)


if __name__ == "__main__":
    unittest.main()
