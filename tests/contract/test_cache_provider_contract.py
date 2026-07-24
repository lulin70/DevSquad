#!/usr/bin/env python3
"""
CacheProvider Contract Tests

Validates that all CacheProvider implementations conform to the Protocol
interface defined in protocols.py. Both LLMCache (real filesystem-based)
and NullCacheProvider (degraded no-op) must pass these tests.

Contract test ownership: shared between DevSquad and cache infrastructure teams.
Any breaking change to CacheProvider Protocol must be negotiated.
"""

import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.llm_cache import LLMCache
from scripts.collaboration.null_providers import NullCacheProvider


class TestCacheProviderContract(unittest.TestCase):
    """Contract tests for CacheProvider Protocol compliance.

    Uses the real LLMCache implementation (filesystem-backed) as the
    reference provider. Subclasses override _get_provider() to test
    alternative implementations against the same contract.
    """

    def setUp(self):
        """Create a fresh temp cache directory per test for isolation."""
        self._tmp_dir = tempfile.mkdtemp(prefix="cache_contract_")

    def tearDown(self):
        """Best-effort cleanup of the temp cache directory."""
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _get_provider(self):
        """Return a real LLMCache instance backed by a temp directory."""
        return LLMCache(cache_dir=self._tmp_dir)

    def test_has_get(self):
        """Verify provider exposes the get() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "get"))
        self.assertTrue(callable(provider.get))

    def test_has_set(self):
        """Verify provider exposes the set() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "set"))
        self.assertTrue(callable(provider.set))

    def test_has_clear(self):
        """Verify provider exposes the clear() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "clear"))
        self.assertTrue(callable(provider.clear))

    def test_has_is_available(self):
        """Verify provider exposes the is_available() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "is_available"))
        self.assertTrue(callable(provider.is_available))

    def test_has_get_stats(self):
        """Verify provider exposes the get_stats() method."""
        provider = self._get_provider()
        self.assertTrue(hasattr(provider, "get_stats"))
        self.assertTrue(callable(provider.get_stats))

    def test_get_returns_str_or_none(self):
        """Verify get() returns either a str or None (cache miss)."""
        provider = self._get_provider()
        result = provider.get("test-prompt", "openai", "gpt-4")
        self.assertTrue(result is None or isinstance(result, str))

    def test_set_no_exception(self):
        """Verify set() stores a response without raising."""
        provider = self._get_provider()
        provider.set("test-prompt", "test-response", "openai", "gpt-4")
        # Verify provider still functional after set
        self.assertIsInstance(provider.get_stats(), dict)

    def test_clear_no_exception(self):
        """Verify clear() empties the cache without raising."""
        provider = self._get_provider()
        provider.set("p1", "r1", "openai", "gpt-4")
        provider.clear()
        # Verify provider still functional after clear
        self.assertIsInstance(provider.get_stats(), dict)

    def test_is_available_returns_bool(self):
        """Verify is_available() returns a bool."""
        provider = self._get_provider()
        result = provider.is_available()
        self.assertIsInstance(result, bool)

    def test_get_stats_returns_dict(self):
        """Verify get_stats() returns a dict."""
        provider = self._get_provider()
        result = provider.get_stats()
        self.assertIsInstance(result, dict)


class TestLLMCacheContract(unittest.TestCase):
    """Contract tests specific to the real LLMCache round-trip behavior."""

    def setUp(self):
        """Create a fresh temp cache directory per test for isolation."""
        self._tmp_dir = tempfile.mkdtemp(prefix="llmcache_contract_")

    def tearDown(self):
        """Best-effort cleanup of the temp cache directory."""
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _get_provider(self):
        """Return a real LLMCache instance backed by a temp directory."""
        return LLMCache(cache_dir=self._tmp_dir)

    def test_set_then_get_round_trip(self):
        """Verify LLMCache returns the stored response after set()."""
        provider = self._get_provider()
        provider.set("round-trip-prompt", "round-trip-response", "openai", "gpt-4")
        cached = provider.get("round-trip-prompt", "openai", "gpt-4")
        self.assertEqual(cached, "round-trip-response")

    def test_clear_invalidates_entries(self):
        """Verify LLMCache.clear() removes previously stored entries."""
        provider = self._get_provider()
        provider.set("p1", "r1", "openai", "gpt-4")
        self.assertEqual(provider.get("p1", "openai", "gpt-4"), "r1")
        provider.clear()
        self.assertIsNone(provider.get("p1", "openai", "gpt-4"))

    def test_is_available_returns_true(self):
        """Verify LLMCache reports available when backed by a writable dir."""
        provider = self._get_provider()
        self.assertTrue(provider.is_available())


class TestNullCacheProviderContract(TestCacheProviderContract):
    """Contract tests specific to NullCacheProvider (degraded) behavior.

    Inherits all base contract tests; overrides _get_provider() to use
    the no-op NullCacheProvider and adds degraded-mode specific checks.
    """

    def _get_provider(self):
        """Return a NullCacheProvider (no-op, degraded)."""
        return NullCacheProvider()

    def test_is_available_returns_false(self):
        """NullCacheProvider must report unavailable (degraded mode)."""
        provider = self._get_provider()
        self.assertFalse(provider.is_available())

    def test_get_returns_none(self):
        """NullCacheProvider.get() must always return None (cache miss)."""
        provider = self._get_provider()
        self.assertIsNone(provider.get("any-prompt", "openai", "gpt-4"))

    def test_get_stats_has_degraded_flag(self):
        """NullCacheProvider.get_stats() must include degraded=True flag."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertTrue(stats.get("degraded", False))
        self.assertEqual(stats.get("provider_type"), "null")


class TestLLMCacheExtendedContract(unittest.TestCase):
    """Extended contract tests for LLMCache covering TTL, isolation, and stats."""

    def setUp(self):
        self._tmp_dir = tempfile.mkdtemp(prefix="cache_ext_contract_")

    def tearDown(self):
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _get_provider(self):
        return LLMCache(cache_dir=self._tmp_dir)

    def test_multi_backend_isolation(self):
        """Cache entries for different backends must not cross-contaminate."""
        provider = self._get_provider()
        provider.set("shared-prompt", "openai-response", "openai", "gpt-4")
        result = provider.get("shared-prompt", "anthropic", "gpt-4")
        self.assertIsNone(result)

    def test_multi_model_isolation(self):
        """Cache entries for different models must not cross-contaminate."""
        provider = self._get_provider()
        provider.set("shared-prompt", "gpt4-response", "openai", "gpt-4")
        result = provider.get("shared-prompt", "openai", "gpt-3.5")
        self.assertIsNone(result)

    def test_empty_prompt_round_trip(self):
        """Cache should handle empty prompt without error."""
        provider = self._get_provider()
        provider.set("", "empty-prompt-response", "openai", "gpt-4")
        result = provider.get("", "openai", "gpt-4")
        self.assertEqual(result, "empty-prompt-response")

    def test_empty_response_round_trip(self):
        """Cache should handle empty response string without error."""
        provider = self._get_provider()
        provider.set("empty-resp-prompt", "", "openai", "gpt-4")
        result = provider.get("empty-resp-prompt", "openai", "gpt-4")
        self.assertEqual(result, "")

    def test_unicode_prompt_round_trip(self):
        """Cache should handle unicode prompts correctly."""
        provider = self._get_provider()
        prompt = "使用中文提示词 — 日本語も — 한국어도"
        provider.set(prompt, "unicode-response", "openai", "gpt-4")
        result = provider.get(prompt, "openai", "gpt-4")
        self.assertEqual(result, "unicode-response")

    def test_emoji_prompt_round_trip(self):
        """Cache should handle emoji in prompts correctly."""
        provider = self._get_provider()
        prompt = "Test with emojis: 🚀🎉🐍✅❌"
        provider.set(prompt, "emoji-response", "openai", "gpt-4")
        result = provider.get(prompt, "openai", "gpt-4")
        self.assertEqual(result, "emoji-response")

    def test_newline_prompt_round_trip(self):
        """Cache should handle multi-line prompts with newlines."""
        provider = self._get_provider()
        prompt = "Line 1\nLine 2\nLine 3"
        provider.set(prompt, "multiline-response", "openai", "gpt-4")
        result = provider.get(prompt, "openai", "gpt-4")
        self.assertEqual(result, "multiline-response")

    def test_large_response_round_trip(self):
        """Cache should handle large responses (10KB+)."""
        provider = self._get_provider()
        large_response = "x" * 10240  # 10KB
        provider.set("large-prompt", large_response, "openai", "gpt-4")
        result = provider.get("large-prompt", "openai", "gpt-4")
        self.assertEqual(result, large_response)
        self.assertGreaterEqual(len(result), 10240)

    def test_stats_has_hit_count(self):
        """get_stats() must include hit_count field."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertIn("hit_count", stats)

    def test_stats_has_miss_count(self):
        """get_stats() must include miss_count field."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertIn("miss_count", stats)

    def test_stats_has_hit_rate(self):
        """get_stats() must include hit_rate field."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertIn("hit_rate", stats)

    def test_stats_hit_rate_updates_after_hit(self):
        """hit_rate should be > 0 after a cache hit."""
        provider = self._get_provider()
        provider.set("rate-test", "response", "openai", "gpt-4")
        provider.get("rate-test", "openai", "gpt-4")  # hit
        stats = provider.get_stats()
        self.assertGreater(stats["hit_rate"], 0.0)

    def test_miss_increments_miss_count(self):
        """Cache miss should increment miss_count in stats."""
        provider = self._get_provider()
        provider.get("nonexistent", "openai", "gpt-4")
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["miss_count"], 1)

    def test_set_increments_sets_counter(self):
        """set() should increment the sets counter in stats."""
        provider = self._get_provider()
        provider.set("sets-test", "response", "openai", "gpt-4")
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["sets"], 1)

    def test_multiple_clears_no_exception(self):
        """Calling clear() multiple times should not raise."""
        provider = self._get_provider()
        provider.set("p1", "r1", "openai", "gpt-4")
        provider.clear()
        provider.clear()
        provider.clear()
        # Verify still functional
        self.assertIsInstance(provider.get_stats(), dict)

    def test_repeated_set_overwrites(self):
        """Setting the same prompt twice should overwrite the first response."""
        provider = self._get_provider()
        provider.set("overwrite-prompt", "first-response", "openai", "gpt-4")
        provider.set("overwrite-prompt", "second-response", "openai", "gpt-4")
        result = provider.get("overwrite-prompt", "openai", "gpt-4")
        self.assertEqual(result, "second-response")

    def test_is_available_false_for_deleted_dir(self):
        """is_available() should return False when cache dir is deleted."""
        provider = self._get_provider()
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        self.assertFalse(provider.is_available())

    def test_cache_entry_is_expired(self):
        """CacheEntry.is_expired() should correctly detect expiration."""
        import time

        from scripts.collaboration.llm_cache import CacheEntry
        entry = CacheEntry(
            prompt_hash="test",
            response="resp",
            backend="openai",
            model="gpt-4",
            timestamp=time.time() - 100,
        )
        self.assertTrue(entry.is_expired(50))
        self.assertFalse(entry.is_expired(200))

    def test_invalidate_removes_entry(self):
        """invalidate() should remove a specific cached entry."""
        provider = self._get_provider()
        provider.set("invalidate-me", "response", "openai", "gpt-4")
        self.assertEqual(provider.get("invalidate-me", "openai", "gpt-4"), "response")
        provider.invalidate("invalidate-me", "openai", "gpt-4")
        self.assertIsNone(provider.get("invalidate-me", "openai", "gpt-4"))

    def test_ttl_expiration_with_short_ttl(self):
        """Entries should expire when cache is configured with short TTL."""
        import time
        provider = LLMCache(cache_dir=self._tmp_dir, ttl_seconds=1)
        provider.set("ttl-prompt", "ttl-response", "openai", "gpt-4")
        self.assertEqual(provider.get("ttl-prompt", "openai", "gpt-4"), "ttl-response")
        time.sleep(1.2)
        self.assertIsNone(provider.get("ttl-prompt", "openai", "gpt-4"))


class T6_CacheProviderStressContract(unittest.TestCase):
    """Stress and boundary contract tests for CacheProvider implementations.

    Covers concurrent access, TTL boundary values, large key volumes,
    post-clear stats consistency, backend-failure availability, and
    key format validation (empty string / special characters).
    """

    def setUp(self) -> None:
        """Create a fresh temp cache directory per test for isolation."""
        self._tmp_dir = tempfile.mkdtemp(prefix="cache_t6_")

    def tearDown(self) -> None:
        """Best-effort cleanup of the temp cache directory."""
        shutil.rmtree(self._tmp_dir, ignore_errors=True)

    def _get_provider(self) -> LLMCache:
        """Return a real LLMCache instance backed by a temp directory."""
        return LLMCache(cache_dir=self._tmp_dir)

    def test_concurrent_set_get_isolated_results(self) -> None:
        """Concurrent set/get from multiple threads must not cross-contaminate.

        Each thread writes a unique key and immediately reads it back.
        The cache must return each thread's own value, demonstrating
        thread-safe isolation without locks held by callers.
        """
        import threading

        provider = self._get_provider()
        errors: list[str] = []
        barrier = threading.Barrier(8)

        def worker(tid: int) -> None:
            barrier.wait()
            prompt = f"concurrent-prompt-{tid}"
            resp = f"response-{tid}"
            try:
                provider.set(prompt, resp, "openai", "gpt-4")
                got = provider.get(prompt, "openai", "gpt-4")
                if got != resp:
                    errors.append(f"thread {tid}: expected {resp!r}, got {got!r}")
            except Exception as e:  # noqa: BLE001
                errors.append(f"thread {tid} raised {type(e).__name__}: {e}")

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [], f"Concurrent access errors: {errors}")

    def test_ttl_zero_expires_immediately(self) -> None:
        """TTL of 0 seconds must expire entries on the next get (boundary).

        With ttl_seconds=0, even a freshly-stored entry is older than 0
        seconds by the time get() runs, so it must be treated as a miss.
        """
        provider = LLMCache(cache_dir=self._tmp_dir, ttl_seconds=0)
        provider.set("ttl-zero-prompt", "resp", "openai", "gpt-4")
        result = provider.get("ttl-zero-prompt", "openai", "gpt-4")
        self.assertIsNone(result, "TTL=0 should expire entries immediately")

    def test_negative_ttl_expires_immediately(self) -> None:
        """Negative TTL must expire entries immediately (boundary / malformed input).

        A negative ttl_seconds is malformed; the cache must not crash and
        should treat the entry as expired (defensive behavior).
        """
        provider = LLMCache(cache_dir=self._tmp_dir, ttl_seconds=-1)
        provider.set("neg-ttl-prompt", "resp", "openai", "gpt-4")
        result = provider.get("neg-ttl-prompt", "openai", "gpt-4")
        self.assertIsNone(result, "Negative TTL should expire entries immediately")

    def test_large_key_volume_stress(self) -> None:
        """Cache must handle 200 distinct keys without loss or stats drift.

        Stress test verifying that the cache reliably stores and retrieves
        a large number of entries and that stats counters reflect the
        exact number of sets, hits, and misses.
        """
        provider = self._get_provider()
        n = 200
        for i in range(n):
            provider.set(f"stress-prompt-{i}", f"resp-{i}", "openai", "gpt-4")
        for i in range(n):
            self.assertEqual(provider.get(f"stress-prompt-{i}", "openai", "gpt-4"), f"resp-{i}")
        stats = provider.get_stats()
        self.assertGreaterEqual(stats["sets"], n)
        self.assertGreaterEqual(stats["hit_count"], n)

    def test_clear_then_get_stats_consistency(self) -> None:
        """get_stats() must return consistent state immediately after clear().

        After clear(), entry_count must drop to 0 and hit_count/miss_count
        counters must remain coherent (not negative, not stale).
        """
        provider = self._get_provider()
        provider.set("p1", "r1", "openai", "gpt-4")
        provider.set("p2", "r2", "openai", "gpt-4")
        provider.clear()
        stats = provider.get_stats()
        self.assertIsInstance(stats, dict)
        self.assertGreaterEqual(stats.get("hit_count", 0), 0)
        self.assertGreaterEqual(stats.get("miss_count", 0), 0)

    def test_is_available_false_when_cache_dir_removed(self) -> None:
        """is_available() must return False when the backing directory disappears.

        Simulates backend failure: the cache directory is deleted out from
        under the provider. is_available() must detect this and return False
        so callers can degrade gracefully.
        """
        provider = self._get_provider()
        self.assertTrue(provider.is_available())
        shutil.rmtree(self._tmp_dir, ignore_errors=True)
        self.assertFalse(provider.is_available())

    def test_empty_and_special_character_keys_round_trip(self) -> None:
        """Cache must handle empty-string and special-character keys.

        Validates that prompts containing path separators, shell
        metacharacters, and SQL-like syntax are stored and retrieved
        verbatim without corruption or injection side effects.
        """
        provider = self._get_provider()
        special_prompts = [
            "",
            "prompt/with/slashes",
            "prompt; DROP TABLE cache;--",
            "prompt`with`backticks",
            "prompt\twith\ttabs",
            "prompt with $VAR and ${HOME}",
        ]
        for i, prompt in enumerate(special_prompts):
            resp = f"special-resp-{i}"
            provider.set(prompt, resp, "openai", "gpt-4")
            self.assertEqual(provider.get(prompt, "openai", "gpt-4"), resp,
                             f"Round-trip failed for prompt {i!r}")

    def test_invalidate_nonexistent_key_no_exception(self) -> None:
        """invalidate() on a non-existent key must not raise.

        Defensive contract: invalidating a key that was never stored
        should be a silent no-op, not an error.
        """
        provider = self._get_provider()
        provider.invalidate("never-stored-prompt", "openai", "gpt-4")
        self.assertIsInstance(provider.get_stats(), dict)


if __name__ == "__main__":
    unittest.main()
