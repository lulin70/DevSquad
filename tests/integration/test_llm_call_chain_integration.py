#!/usr/bin/env python3
"""LLM Call Chain Integration Tests.

Integration tests for the LLM invocation chain:
    LLMCache + LLMRetry + UsageTracker + LLMBackend (Mock/Trae/Fallback)

These tests verify cross-module interactions when a prompt flows through:
    cache miss → retry-on-failure → backend call → cache set → usage tracked
    → cache hit on subsequent call.

Flow:
    1. LLMCache.get() → None (miss)
    2. LLMRetryManager.retry_with_fallback(backend.generate, ...) → response
    3. LLMCache.set(prompt, response, ...) → persisted
    4. UsageTracker.track("llm.call", success=True) → recorded
    5. LLMCache.get() → response (hit)

References:
    - scripts/collaboration/llm_cache.py (LLMCache)
    - scripts/collaboration/llm_cache_base.py (LLMCacheBase — key/TTL/LRU strategy)
    - scripts/collaboration/llm_retry.py (LLMRetryManager)
    - scripts/collaboration/llm_retry_base.py (RetryConfig, CircuitBreakerState)
    - scripts/collaboration/usage_tracker.py (UsageTracker)
    - scripts/collaboration/llm_backend.py (MockBackend, TraeBackend, FallbackBackend)
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import unittest
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.llm_backend import (
    FallbackBackend,
    LLMBackend,
    MockBackend,
    TraeBackend,
    create_backend,
)
from scripts.collaboration.llm_cache import LLMCache
from scripts.collaboration.llm_retry import LLMRetryManager
from scripts.collaboration.llm_retry_base import (
    CircuitBreakerError,
    JitterStrategy,
    RetryConfig,
)
from scripts.collaboration.usage_tracker import UsageTracker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_cache(tmpdir: str | None = None) -> tuple[LLMCache, str]:
    """Build an LLMCache backed by a fresh temp dir. Returns (cache, tmpdir)."""
    tmpdir = tmpdir or tempfile.mkdtemp(prefix="llmchain_integ_")
    return LLMCache(cache_dir=tmpdir, ttl_seconds=300), tmpdir


def _fast_retry_config(max_retries: int = 3) -> RetryConfig:
    """RetryConfig with near-zero delays so tests run fast."""
    return RetryConfig(
        max_retries=max_retries,
        initial_delay=0.001,
        max_delay=0.01,
        jitter=False,
    )


class _FlakyFunc:
    """Callable that fails N times then succeeds (or always fails)."""

    def __init__(self, fail_times: int, error_msg: str = "connection timeout",
                 success_value: str = "ok") -> None:
        self.fail_times = fail_times
        self.error_msg = error_msg
        self.success_value = success_value
        self.call_count = 0

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        self.call_count += 1
        if self.call_count <= self.fail_times:
            raise ConnectionError(self.error_msg)
        return self.success_value


class _AlwaysFailFunc:
    """Callable that always raises a retryable error."""

    def __init__(self, error_msg: str = "connection timeout") -> None:
        self.error_msg = error_msg
        self.call_count = 0

    def __call__(self, *args: Any, **kwargs: Any) -> str:
        self.call_count += 1
        raise ConnectionError(self.error_msg)


# ---------------------------------------------------------------------------
# T1: LLMCache + LLMRetry coordination (cache miss → retry → cache set)
# ---------------------------------------------------------------------------


class T1_CacheRetryCoordinationIntegration(unittest.TestCase):
    """T1: LLMCache miss triggers retry-aware backend call, then cache set."""

    def setUp(self) -> None:
        self.cache, self.tmpdir = _make_cache()
        self.retry = LLMRetryManager()

    def tearDown(self) -> None:
        self.cache.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_cache_miss_returns_none_and_records_miss(self) -> None:
        """Verify: fresh prompt misses cache and increments miss counter."""
        result = self.cache.get("missing-prompt", "openai", "gpt-4")
        self.assertIsNone(result)
        self.assertEqual(self.cache.stats["misses"], 1)

    def test_02_cache_set_then_get_returns_response(self) -> None:
        """Verify: set then get returns the cached response and records a hit."""
        self.cache.set("prompt-1", "response-1", "openai", "gpt-4")
        self.assertEqual(self.cache.get("prompt-1", "openai", "gpt-4"), "response-1")
        self.assertEqual(self.cache.stats["hits"], 1)
        self.assertEqual(self.cache.stats["sets"], 1)

    def test_03_retry_succeeds_after_transient_failure(self) -> None:
        """Verify: retry returns success after one transient timeout."""
        flaky = _FlakyFunc(fail_times=1, success_value="recovered-response")
        config = _fast_retry_config(max_retries=3)
        result = self.retry.retry_with_fallback(
            flaky, args=(), kwargs={}, config=config, current_backend="openai")
        self.assertEqual(result, "recovered-response")
        self.assertEqual(self.retry.stats["retries"], 1)
        self.assertEqual(self.retry.stats["successful_calls"], 1)

    def test_04_retry_exhausts_and_raises_last_error(self) -> None:
        """Verify: all retries exhausted raises the last error."""
        always_fail = _AlwaysFailFunc("connection timeout")
        config = _fast_retry_config(max_retries=2)
        with self.assertRaises(ConnectionError):
            self.retry.retry_with_fallback(
                always_fail, args=(), kwargs={}, config=config, current_backend="openai")
        self.assertEqual(always_fail.call_count, 2)
        self.assertEqual(self.retry.stats["failed_calls"], 2)

    def test_05_non_retryable_error_not_retried(self) -> None:
        """Verify: a non-retryable error (ValueError) breaks the retry loop immediately."""

        def raise_value_error(*args: Any, **kwargs: Any) -> str:
            raise ValueError("invalid argument: not retryable")

        config = _fast_retry_config(max_retries=3)
        with self.assertRaises(ValueError):
            self.retry.retry_with_fallback(
                raise_value_error, args=(), kwargs={}, config=config, current_backend="openai")
        # Non-retryable → only 1 attempt, no retries.
        self.assertEqual(self.retry.stats["retries"], 0)

    def test_06_cache_miss_then_backend_then_set_then_hit(self) -> None:
        """Verify: cache miss → backend.generate → cache.set → cache hit."""
        backend = MockBackend()
        prompt = "Analyze microservice design"
        # Step 1: cache miss
        self.assertIsNone(self.cache.get(prompt, "mock", "mock-v1"))
        # Step 2: backend call
        response = backend.generate(prompt, role_name="Architect")
        self.assertIn("[MOCK MODE]", response)
        # Step 3: cache set
        self.cache.set(prompt, response, "mock", "mock-v1")
        # Step 4: cache hit
        cached = self.cache.get(prompt, "mock", "mock-v1")
        self.assertEqual(cached, response)
        self.assertEqual(self.cache.stats["hits"], 1)


# ---------------------------------------------------------------------------
# T2: UsageTracker statistics accuracy
# ---------------------------------------------------------------------------


class T2_UsageTrackerIntegration(unittest.TestCase):
    """T2: UsageTracker tracks feature counts, errors, and metadata accurately."""

    def setUp(self) -> None:
        self.tmpdir = tempfile.mkdtemp(prefix="usage_integ_")
        self.persist_file = os.path.join(self.tmpdir, "usage.json")
        self.tracker = UsageTracker(persist_file=self.persist_file)

    def tearDown(self) -> None:
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_track_increments_count_and_sets_timestamps(self) -> None:
        """Verify: track() increments count and sets first_used/last_used."""
        self.tracker.track("llm.call")
        stats = self.tracker.get_stats("llm.call")
        self.assertEqual(stats["count"], 1)
        self.assertIsNotNone(stats["first_used"])
        self.assertIsNotNone(stats["last_used"])
        self.assertEqual(stats["errors"], 0)

    def test_02_track_failure_increments_errors(self) -> None:
        """Verify: track(success=False) increments the errors counter."""
        self.tracker.track("llm.call", success=True)
        self.tracker.track("llm.call", success=False)
        stats = self.tracker.get_stats("llm.call")
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["errors"], 1)

    def test_03_get_top_features_sorted_by_count(self) -> None:
        """Verify: get_top_features returns features sorted by count descending."""
        for _ in range(5):
            self.tracker.track("feature.a")
        for _ in range(3):
            self.tracker.track("feature.b")
        top = self.tracker.get_top_features(limit=10)
        self.assertEqual(top[0], ("feature.a", 5))
        self.assertEqual(top[1], ("feature.b", 3))

    def test_04_get_unused_features(self) -> None:
        """Verify: get_unused_features returns features never tracked."""
        self.tracker.track("used.feature")
        unused = self.tracker.get_unused_features(["used.feature", "unused.one", "unused.two"])
        self.assertEqual(sorted(unused), ["unused.one", "unused.two"])

    def test_05_metadata_capped_to_ten_entries(self) -> None:
        """Verify: metadata list is capped to the most recent 10 entries."""
        for i in range(15):
            self.tracker.track("feature.meta", metadata={"index": i})
        stats = self.tracker.get_stats("feature.meta")
        self.assertEqual(len(stats["metadata"]), 10)
        # Most recent 10 → indices 5..14
        self.assertEqual(stats["metadata"][0]["index"], 5)
        self.assertEqual(stats["metadata"][-1]["index"], 14)

    def test_06_persist_and_reload_round_trip(self) -> None:
        """Verify: save() then new UsageTracker(same file) reloads stats."""
        self.tracker.track("persisted.feature", success=True)
        self.tracker.track("persisted.feature", success=False)
        self.assertTrue(self.tracker.save())
        reloaded = UsageTracker(persist_file=self.persist_file)
        stats = reloaded.get_stats("persisted.feature")
        self.assertEqual(stats["count"], 2)
        self.assertEqual(stats["errors"], 1)

    def test_07_clear_resets_all_stats(self) -> None:
        """Verify: clear() empties the stats and returns the cleared count."""
        self.tracker.track("a")
        self.tracker.track("b")
        cleared = self.tracker.clear()
        self.assertEqual(cleared, 2)
        self.assertEqual(self.tracker.get_stats(), {})

    def test_08_concurrent_track_thread_safe(self) -> None:
        """Verify: concurrent track() calls produce consistent counts."""
        errors: list[Exception] = []

        def worker() -> None:
            try:
                for _ in range(50):
                    self.tracker.track("concurrent.feature")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        self.assertEqual(self.tracker.get_stats("concurrent.feature")["count"], 500)


# ---------------------------------------------------------------------------
# T3: LLMBackend Mock mode + streaming + FallbackBackend
# ---------------------------------------------------------------------------


class T3_LLMBackendIntegration(unittest.TestCase):
    """T3: MockBackend, TraeBackend, and FallbackBackend behavior."""

    def test_01_mock_backend_generate_returns_mock_marker(self) -> None:
        """Verify: MockBackend.generate includes [MOCK MODE] marker."""
        backend = MockBackend()
        result = backend.generate("test prompt", role_name="Architect", task_description="design")
        self.assertIn("[MOCK MODE]", result)
        self.assertIn("Architect", result)
        self.assertIn("design", result)

    def test_02_mock_backend_is_available(self) -> None:
        """Verify: MockBackend.is_available() always returns True."""
        self.assertTrue(MockBackend().is_available())

    def test_03_mock_backend_generate_stream_yields_response(self) -> None:
        """Verify: generate_stream yields the full response as a single chunk."""
        backend = MockBackend()
        chunks = list(backend.generate_stream("stream prompt"))
        self.assertEqual(len(chunks), 1)
        self.assertIn("[MOCK MODE]", chunks[0])

    def test_04_trae_backend_returns_prompt_unchanged(self) -> None:
        """Verify: TraeBackend.generate returns the prompt unchanged."""
        backend = TraeBackend()
        result = backend.generate("execute this prompt")
        self.assertEqual(result, "execute this prompt")

    def test_05_fallback_backend_fails_over_to_second(self) -> None:
        """Verify: FallbackBackend tries primary, then falls back to secondary."""

        class _PrimaryFail(LLMBackend):
            def generate(self, prompt: str, **kwargs: Any) -> str:
                raise ConnectionError("primary down")

            def is_available(self) -> bool:
                return True

        secondary = MockBackend()
        fb = FallbackBackend([_PrimaryFail(), secondary])
        result = fb.generate("test prompt")
        self.assertIn("[MOCK MODE]", result)

    def test_06_fallback_backend_all_fail_raises_runtime_error(self) -> None:
        """Verify: FallbackBackend raises RuntimeError when all backends fail."""

        class _AlwaysDown(LLMBackend):
            def generate(self, prompt: str, **kwargs: Any) -> str:
                raise ConnectionError("all down")

            def is_available(self) -> bool:
                return True

        fb = FallbackBackend([_AlwaysDown(), _AlwaysDown()])
        with self.assertRaises((RuntimeError, ConnectionError)):
            fb.generate("test")

    def test_07_fallback_backend_is_available_if_any_available(self) -> None:
        """Verify: FallbackBackend.is_available() returns True if any backend is available."""

        class _Down(LLMBackend):
            def generate(self, prompt: str, **kwargs: Any) -> str:
                raise ConnectionError("down")

            def is_available(self) -> bool:
                return False

        fb = FallbackBackend([_Down(), MockBackend()])
        self.assertTrue(fb.is_available())

    def test_08_create_backend_mock_returns_mock_backend(self) -> None:
        """Verify: create_backend('mock') returns a MockBackend instance."""
        backend = create_backend("mock")
        self.assertIsInstance(backend, MockBackend)
        self.assertTrue(backend.is_available())


# ---------------------------------------------------------------------------
# T4: End-to-end cache miss → backend → retry → cache set → tracked → hit
# ---------------------------------------------------------------------------


class T4_EndToEndCallChainIntegration(unittest.TestCase):
    """T4: Full LLM call chain — cache, retry, backend, usage tracking."""

    def setUp(self) -> None:
        self.cache, self.tmpdir = _make_cache()
        self.retry = LLMRetryManager()
        self.tracker = UsageTracker(persist_file=os.path.join(self.tmpdir, "usage.json"))

    def tearDown(self) -> None:
        self.cache.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_full_flow_cache_miss_backend_call_cache_hit(self) -> None:
        """Verify: miss → backend.generate → set → track → hit."""
        backend = MockBackend()
        prompt = "Design a retry mechanism"
        backend_name, model_name = "mock", "mock-v1"

        # Cache miss
        cached = self.cache.get(prompt, backend_name, model_name)
        self.assertIsNone(cached)

        # Backend call (no retry needed — succeeds first try)
        config = _fast_retry_config(max_retries=2)
        response = self.retry.retry_with_fallback(
            backend.generate, args=(prompt,), kwargs={"role_name": "Architect"},
            config=config, current_backend=backend_name)
        self.assertIn("[MOCK MODE]", response)

        # Cache set + track usage
        self.cache.set(prompt, response, backend_name, model_name)
        self.tracker.track("llm.call", success=True)

        # Cache hit
        self.assertEqual(self.cache.get(prompt, backend_name, model_name), response)
        self.assertEqual(self.cache.stats["hits"], 1)
        self.assertEqual(self.tracker.get_stats("llm.call")["count"], 1)

    def test_02_full_flow_with_retry_on_failure_then_cache_set(self) -> None:
        """Verify: flaky backend → retry recovers → response cached."""
        flaky = _FlakyFunc(fail_times=1, success_value="recovered")
        prompt = "Flaky backend test"
        config = _fast_retry_config(max_retries=3)

        # Cache miss
        self.assertIsNone(self.cache.get(prompt, "flaky", "v1"))

        # Retry recovers
        response = self.retry.retry_with_fallback(
            flaky, args=(), kwargs={}, config=config, current_backend="flaky")
        self.assertEqual(response, "recovered")

        # Cache set
        self.cache.set(prompt, response, "flaky", "v1")
        self.assertEqual(self.cache.get(prompt, "flaky", "v1"), "recovered")
        self.assertEqual(self.retry.stats["retries"], 1)

    def test_03_full_flow_failure_tracked_and_no_cache_set(self) -> None:
        """Verify: all retries fail → error tracked, nothing cached."""
        always_fail = _AlwaysFailFunc("connection timeout")
        config = _fast_retry_config(max_retries=2)
        with self.assertRaises(ConnectionError):
            self.retry.retry_with_fallback(
                always_fail, args=(), kwargs={}, config=config, current_backend="openai")
        # Track failure
        self.tracker.track("llm.call", success=False, metadata={"error": "timeout"})
        # Nothing cached
        self.assertIsNone(self.cache.get("failed-prompt", "openai", "gpt-4"))
        self.assertEqual(self.tracker.get_stats("llm.call")["errors"], 1)

    def test_04_full_flow_with_fallback_backend(self) -> None:
        """Verify: primary fails → fallback succeeds → response cached."""

        class _PrimaryFail(LLMBackend):
            def generate(self, prompt: str, **kwargs: Any) -> str:
                raise ConnectionError("primary timeout")

            def is_available(self) -> bool:
                return True

        fb = FallbackBackend([_PrimaryFail(), MockBackend()])
        prompt = "Fallback flow test"
        config = _fast_retry_config(max_retries=1)

        response = self.retry.retry_with_fallback(
            fb.generate, args=(prompt,), kwargs={},
            config=config, fallback_backends=["mock"], current_backend="primary")
        self.assertIn("[MOCK MODE]", response)
        self.cache.set(prompt, response, "fallback", "v1")
        self.assertEqual(self.cache.get(prompt, "fallback", "v1"), response)

    def test_05_cache_invalidation_forces_miss_on_next_get(self) -> None:
        """Verify: invalidate() removes the entry so next get is a miss."""
        self.cache.set("invalidate-me", "resp", "openai", "gpt-4")
        self.assertEqual(self.cache.get("invalidate-me", "openai", "gpt-4"), "resp")
        self.cache.invalidate("invalidate-me", "openai", "gpt-4")
        self.assertIsNone(self.cache.get("invalidate-me", "openai", "gpt-4"))


# ---------------------------------------------------------------------------
# T5: Boundary — empty/long prompts, TTL expiry, circuit breaker, concurrency
# ---------------------------------------------------------------------------


class T5_BoundaryAndEdgeCasesIntegration(unittest.TestCase):
    """T5: Empty prompt, long prompt, TTL expiry, circuit breaker, concurrency."""

    def setUp(self) -> None:
        self.cache, self.tmpdir = _make_cache()
        self.retry = LLMRetryManager()

    def tearDown(self) -> None:
        self.cache.clear()
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_01_empty_prompt_cache_round_trip(self) -> None:
        """Verify: empty-string prompt caches and retrieves correctly."""
        self.cache.set("", "empty-response", "openai", "gpt-4")
        self.assertEqual(self.cache.get("", "openai", "gpt-4"), "empty-response")

    def test_02_long_prompt_cache_round_trip(self) -> None:
        """Verify: a 10k-char prompt caches and retrieves correctly."""
        long_prompt = "x" * 10000
        self.cache.set(long_prompt, "long-response", "openai", "gpt-4")
        self.assertEqual(self.cache.get(long_prompt, "openai", "gpt-4"), "long-response")

    def test_03_cache_ttl_expiry_returns_none(self) -> None:
        """Verify: an expired memory entry returns None and is evicted.

        LLMCache.get() falls through memory → disk → Redis. To test pure
        memory-TTL expiry we backdate the memory entry AND remove the disk
        file so the disk layer does not shadow the expired memory entry.
        """
        tmp = tempfile.mkdtemp(prefix="ttl_integ_")
        try:
            cache = LLMCache(cache_dir=tmp, ttl_seconds=1)
            cache.set("expire-soon", "resp", "openai", "gpt-4")
            cache_key = cache._hash_prompt("expire-soon", "openai", "gpt-4")
            # Backdate memory entry to epoch (definitely expired).
            cache.memory_cache[cache_key].timestamp = 0.0
            # Remove the disk file so get() does not fall through to a fresh disk copy.
            disk_file = cache.cache_dir / f"{cache_key}.json"
            if disk_file.exists():
                disk_file.unlink()
            self.assertIsNone(cache.get("expire-soon", "openai", "gpt-4"))
            self.assertNotIn(cache_key, cache.memory_cache)
            self.assertEqual(cache.stats["expirations"], 1)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_04_cache_clear_resets_all_stats(self) -> None:
        """Verify: clear() empties memory cache and resets stats to zero."""
        self.cache.set("a", "1", "openai", "gpt-4")
        self.cache.set("b", "2", "openai", "gpt-4")
        self.cache.get("a", "openai", "gpt-4")
        self.cache.clear()
        self.assertEqual(len(self.cache.memory_cache), 0)
        self.assertEqual(self.cache.stats["hits"], 0)
        self.assertEqual(self.cache.stats["misses"], 0)
        self.assertEqual(self.cache.stats["sets"], 0)

    def test_05_circuit_breaker_opens_after_threshold(self) -> None:
        """Verify: 5 consecutive failures open the circuit breaker."""
        always_fail = _AlwaysFailFunc("connection timeout")
        config = _fast_retry_config(max_retries=1)
        # 5 failures → failure_count reaches threshold (5) → circuit opens.
        for _ in range(5):
            with self.assertRaises(ConnectionError):
                self.retry.retry_with_fallback(
                    always_fail, args=(), kwargs={}, config=config, current_backend="openai")
        cb = self.retry.get_circuit_breaker("openai")
        self.assertEqual(cb.state, "open")

    def test_06_circuit_breaker_open_blocks_next_call(self) -> None:
        """Verify: once open, the next call raises CircuitBreakerError (no fallback)."""
        always_fail = _AlwaysFailFunc("connection timeout")
        config = _fast_retry_config(max_retries=1)
        for _ in range(5):
            with self.assertRaises(ConnectionError):
                self.retry.retry_with_fallback(
                    always_fail, args=(), kwargs={}, config=config, current_backend="openai")
        # 6th call → circuit open → CircuitBreakerError (no fallback backends).
        with self.assertRaises(CircuitBreakerError):
            self.retry.retry_with_fallback(
                always_fail, args=(), kwargs={}, config=config, current_backend="openai")

    def test_07_rate_limit_error_triples_delay(self) -> None:
        """Verify: get_enhanced_delay triples delay for rate-limit errors."""
        config = RetryConfig(max_retries=3, initial_delay=1.0, max_delay=60.0, jitter=False)
        normal_error = ConnectionError("connection timeout")
        rate_limit_error = ConnectionError("429 rate limit exceeded")
        normal_delay = self.retry.get_enhanced_delay(0, config, normal_error)
        rate_delay = self.retry.get_enhanced_delay(0, config, rate_limit_error)
        self.assertAlmostEqual(rate_delay, normal_delay * 3, places=5)

    def test_08_concurrent_cache_get_set_thread_safe(self) -> None:
        """Verify: concurrent get/set does not corrupt cache state."""
        errors: list[Exception] = []
        barrier = threading.Barrier(10)

        def worker(idx: int) -> None:
            try:
                barrier.wait()
                prompt = f"concurrent-prompt-{idx % 3}"
                self.cache.set(prompt, f"resp-{idx}", "openai", "gpt-4")
                self.cache.get(prompt, "openai", "gpt-4")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(errors, [])
        # 10 get calls → hits + misses = 10
        self.assertEqual(self.cache.stats["hits"] + self.cache.stats["misses"], 10)

    def test_09_cache_key_deterministic_for_same_inputs(self) -> None:
        """Verify: same prompt/backend/model produces the same cache key."""
        key1 = self.cache._hash_prompt("prompt", "openai", "gpt-4")
        key2 = self.cache._hash_prompt("prompt", "openai", "gpt-4")
        self.assertEqual(key1, key2)

    def test_10_cache_key_differs_for_different_model(self) -> None:
        """Verify: different model produces a different cache key."""
        key1 = self.cache._hash_prompt("prompt", "openai", "gpt-4")
        key2 = self.cache._hash_prompt("prompt", "openai", "gpt-3.5")
        self.assertNotEqual(key1, key2)

    def test_11_jitter_strategy_none_returns_deterministic_delay(self) -> None:
        """Verify: JitterStrategy.NONE produces deterministic exponential backoff."""
        config = RetryConfig(max_retries=3, initial_delay=1.0, max_delay=60.0,
                             jitter=True, jitter_strategy=JitterStrategy.NONE)
        delay_attempt0 = self.retry.calculate_delay(0, config)
        delay_attempt1 = self.retry.calculate_delay(1, config)
        # No jitter → delay == initial_delay * base^attempt
        self.assertAlmostEqual(delay_attempt0, 1.0, places=5)
        self.assertAlmostEqual(delay_attempt1, 2.0, places=5)


if __name__ == "__main__":
    unittest.main()
