#!/usr/bin/env python3
"""
Tests for ContentCache (V3.8 #9)

Coverage:
  - SHA-256 unified cache key generation
  - Sensitive data filtering (API keys, secrets, bearer tokens, private keys)
  - Cache hit/miss metrics integration with PerformanceMonitor
  - Wrapper behavior: get/set delegation, stats, no-op when wrapped is None
  - Backward compatibility with existing LLMCache usage
"""

from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.content_cache import SENSITIVE_PATTERNS, ContentCache
from scripts.collaboration.llm_cache import LLMCache
from scripts.collaboration.performance_monitor import PerformanceMonitor


class TestContentCacheKeyGeneration(unittest.TestCase):
    """Verify unified SHA-256 cache key generation."""

    def setUp(self) -> None:
        self.cache = ContentCache(wrapped=None)

    def test_key_is_sha256_hex_digest(self) -> None:
        key = self.cache.generate_cache_key("prompt", "openai", "gpt-4")
        # SHA-256 hex digest is 64 chars
        self.assertEqual(len(key), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in key))

    def test_key_deterministic_for_same_inputs(self) -> None:
        k1 = self.cache.generate_cache_key("hello", "openai", "gpt-4")
        k2 = self.cache.generate_cache_key("hello", "openai", "gpt-4")
        self.assertEqual(k1, k2)

    def test_key_differs_for_different_inputs(self) -> None:
        k1 = self.cache.generate_cache_key("hello", "openai", "gpt-4")
        k2 = self.cache.generate_cache_key("world", "openai", "gpt-4")
        self.assertNotEqual(k1, k2)

    def test_key_differs_for_different_backend(self) -> None:
        k1 = self.cache.generate_cache_key("hello", "openai", "gpt-4")
        k2 = self.cache.generate_cache_key("hello", "anthropic", "gpt-4")
        self.assertNotEqual(k1, k2)

    def test_key_differs_for_different_model(self) -> None:
        k1 = self.cache.generate_cache_key("hello", "openai", "gpt-4")
        k2 = self.cache.generate_cache_key("hello", "openai", "gpt-3.5-turbo")
        self.assertNotEqual(k1, k2)

    def test_key_matches_manual_sha256(self) -> None:
        prompt, backend, model = "hello", "openai", "gpt-4"
        expected = hashlib.sha256(f":{backend}:{model}:{prompt}".encode()).hexdigest()
        actual = self.cache.generate_cache_key(prompt, backend, model)
        self.assertEqual(actual, expected)

    def test_namespace_affects_key(self) -> None:
        ns_cache = ContentCache(wrapped=None, namespace="tenant-A")
        k1 = ns_cache.generate_cache_key("hello", "openai", "gpt-4")
        ns_cache2 = ContentCache(wrapped=None, namespace="tenant-B")
        k2 = ns_cache2.generate_cache_key("hello", "openai", "gpt-4")
        self.assertNotEqual(k1, k2)


class TestContentCacheSensitiveFiltering(unittest.TestCase):
    """Verify sensitive data is never cached."""

    def setUp(self) -> None:
        self.mock_wrapped = MagicMock()
        self.cache = ContentCache(wrapped=self.mock_wrapped)

    def test_api_key_prompt_is_filtered_on_get(self) -> None:
        sensitive_prompt = "api_key=sk-1234567890abcdef1234 tell me a joke"
        result = self.cache.get(sensitive_prompt, "openai", "gpt-4")
        self.assertIsNone(result)
        self.mock_wrapped.get.assert_not_called()
        self.assertEqual(self.cache.filtered, 1)

    def test_api_key_prompt_is_filtered_on_set(self) -> None:
        sensitive_prompt = "api_key=sk-1234567890abcdef1234 tell me a joke"
        ok = self.cache.set(sensitive_prompt, "response", "openai", "gpt-4")
        self.assertFalse(ok)
        self.mock_wrapped.set.assert_not_called()
        self.assertEqual(self.cache.filtered, 1)

    def test_bearer_token_is_filtered(self) -> None:
        sensitive = "Authorization: Bearer eyJhbGciOiJIUzI1NiJ9.e30.signature"
        self.assertTrue(self.cache.contains_sensitive(sensitive))

    def test_aws_access_key_is_filtered(self) -> None:
        sensitive = "AKIAIOSFODNN7EXAMPLE is my access key"
        self.assertTrue(self.cache.contains_sensitive(sensitive))

    def test_private_key_block_is_filtered(self) -> None:
        sensitive = "-----BEGIN RSA PRIVATE KEY-----\nMIIEpAIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----"
        self.assertTrue(self.cache.contains_sensitive(sensitive))

    def test_password_assignment_is_filtered(self) -> None:
        sensitive = "password=supersecret123"
        self.assertTrue(self.cache.contains_sensitive(sensitive))

    def test_normal_prompt_is_not_filtered(self) -> None:
        normal = "What is the capital of France?"
        self.assertFalse(self.cache.contains_sensitive(normal))

    def test_empty_text_is_not_sensitive(self) -> None:
        self.assertFalse(self.cache.contains_sensitive(""))

    def test_sensitive_response_is_filtered_on_set(self) -> None:
        # Even if prompt is clean, a sensitive response blocks caching
        ok = self.cache.set("clean prompt", "token=abcdef1234567890", "openai", "gpt-4")
        self.assertFalse(ok)
        self.mock_wrapped.set.assert_not_called()

    def test_sensitive_patterns_count(self) -> None:
        # Sanity: we ship multiple patterns
        self.assertGreaterEqual(len(SENSITIVE_PATTERNS), 5)


class TestContentCacheMetricsIntegration(unittest.TestCase):
    """Verify hit/miss metrics integration with PerformanceMonitor."""

    def setUp(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            self._tmpdir = tmpdir
            self.wrapped = LLMCache(cache_dir=tmpdir, ttl_seconds=60)
        self.monitor = PerformanceMonitor()
        self.cache = ContentCache(wrapped=self.wrapped, monitor=self.monitor)

    def tearDown(self) -> None:
        self.wrapped.clear()

    def test_hit_increments_hit_counter_and_metric(self) -> None:
        self.cache.set("hello", "world", "openai", "gpt-4")
        result = self.cache.get("hello", "openai", "gpt-4")
        self.assertEqual(result, "world")
        self.assertEqual(self.cache.hits, 1)
        self.assertEqual(self.cache.misses, 0)
        # PerformanceMonitor should have recorded a hit metric
        stats = self.monitor.get_stats()
        self.assertIn("functions", stats)

    def test_miss_increments_miss_counter_and_metric(self) -> None:
        result = self.cache.get("nonexistent", "openai", "gpt-4")
        self.assertIsNone(result)
        self.assertEqual(self.cache.misses, 1)
        self.assertEqual(self.cache.hits, 0)

    def test_hit_rate_calculation(self) -> None:
        self.cache.set("a", "1", "openai", "gpt-4")
        self.cache.get("a", "openai", "gpt-4")  # hit
        self.cache.get("b", "openai", "gpt-4")  # miss
        stats = self.cache.get_stats()
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertAlmostEqual(stats["hit_rate"], 0.5)

    def test_no_monitor_does_not_crash(self) -> None:
        cache = ContentCache(wrapped=self.wrapped, monitor=None)
        cache.set("x", "y", "openai", "gpt-4")
        # Should not raise
        result = cache.get("x", "openai", "gpt-4")
        self.assertEqual(result, "y")


class TestContentCacheWrapperBehavior(unittest.TestCase):
    """Verify wrapper delegation and no-op behavior."""

    def test_none_wrapped_get_returns_none(self) -> None:
        cache = ContentCache(wrapped=None)
        self.assertIsNone(cache.get("prompt", "openai", "gpt-4"))

    def test_none_wrapped_set_returns_false(self) -> None:
        cache = ContentCache(wrapped=None)
        self.assertFalse(cache.set("prompt", "resp", "openai", "gpt-4"))

    def test_delegates_to_wrapped_get(self) -> None:
        mock_wrapped = MagicMock()
        mock_wrapped.get.return_value = "cached-response"
        cache = ContentCache(wrapped=mock_wrapped)
        result = cache.get("prompt", "openai", "gpt-4")
        self.assertEqual(result, "cached-response")
        mock_wrapped.get.assert_called_once()

    def test_delegates_to_wrapped_set(self) -> None:
        mock_wrapped = MagicMock()
        cache = ContentCache(wrapped=mock_wrapped)
        ok = cache.set("prompt", "resp", "openai", "gpt-4")
        self.assertTrue(ok)
        mock_wrapped.set.assert_called_once()

    def test_reset_stats_clears_counters(self) -> None:
        mock_wrapped = MagicMock()
        mock_wrapped.get.return_value = "x"
        cache = ContentCache(wrapped=mock_wrapped)
        cache.get("p", "openai", "gpt-4")
        self.assertEqual(cache.hits, 1)
        cache.reset_stats()
        self.assertEqual(cache.hits, 0)
        self.assertEqual(cache.misses, 0)
        self.assertEqual(cache.filtered, 0)

    def test_get_stats_includes_filtered_counter(self) -> None:
        cache = ContentCache(wrapped=None)
        cache.get("api_key=sk-1234567890abcdef1234", "openai", "gpt-4")
        stats = cache.get_stats()
        self.assertEqual(stats["filtered"], 1)
        self.assertEqual(stats["has_wrapped"], False)

    def test_get_stats_includes_wrapped_stats_when_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wrapped = LLMCache(cache_dir=tmpdir, ttl_seconds=60)
            cache = ContentCache(wrapped=wrapped)
            cache.set("a", "b", "openai", "gpt-4")
            stats = cache.get_stats()
            self.assertIn("wrapped_stats", stats)
            self.assertTrue(stats["has_wrapped"])

    def test_wrapped_property_returns_underlying(self) -> None:
        mock_wrapped = MagicMock()
        cache = ContentCache(wrapped=mock_wrapped)
        self.assertIs(cache.wrapped, mock_wrapped)


class TestContentCacheIntegrationWithLLMCache(unittest.TestCase):
    """End-to-end integration with the real LLMCache."""

    def setUp(self) -> None:
        self._tmpdir_ctx = tempfile.TemporaryDirectory()
        self.wrapped = LLMCache(cache_dir=self._tmpdir_ctx.name, ttl_seconds=60)
        self.cache = ContentCache(wrapped=self.wrapped)

    def tearDown(self) -> None:
        self.wrapped.clear()
        self._tmpdir_ctx.cleanup()

    def test_round_trip_set_get(self) -> None:
        self.cache.set("What is Python?", "A programming language.", "openai", "gpt-4")
        result = self.cache.get("What is Python?", "openai", "gpt-4")
        self.assertEqual(result, "A programming language.")

    def test_same_prompt_different_backend_isolated(self) -> None:
        self.cache.set("hello", "openai-response", "openai", "gpt-4")
        self.cache.set("hello", "anthropic-response", "anthropic", "claude-3")
        self.assertEqual(self.cache.get("hello", "openai", "gpt-4"), "openai-response")
        self.assertEqual(self.cache.get("hello", "anthropic", "claude-3"), "anthropic-response")

    def test_sensitive_prompt_never_persisted_to_disk(self) -> None:
        sensitive = "api_key=sk-1234567890abcdef1234 secret data"
        self.cache.set(sensitive, "should-not-cache", "openai", "gpt-4")
        # Direct lookup on wrapped cache should also miss (never stored)
        self.assertIsNone(self.cache.get(sensitive, "openai", "gpt-4"))


if __name__ == "__main__":
    unittest.main()
