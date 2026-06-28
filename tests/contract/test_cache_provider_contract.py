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


if __name__ == "__main__":
    unittest.main()
