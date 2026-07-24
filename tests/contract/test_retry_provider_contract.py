#!/usr/bin/env python3
"""
RetryProvider Contract Tests

Validates that all RetryProvider implementations conform to the Protocol
interface defined in protocols.py. Both NullRetryProvider (degraded no-op)
and any future real implementations must pass these tests.

Contract test ownership: shared between DevSquad and retry infrastructure teams.
Any breaking change to RetryProvider Protocol must be negotiated.
"""

import os
import sys
import unittest
from collections.abc import Callable
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.null_providers import NullRetryProvider
from scripts.collaboration.protocols import RetryProvider


class TestRetryProviderProtocolDefinition(unittest.TestCase):
    """Verify the RetryProvider Protocol definition itself is well-formed."""

    def test_protocol_has_retry_with_fallback(self):
        """Protocol must declare retry_with_fallback method."""
        self.assertTrue(hasattr(RetryProvider, "retry_with_fallback"))

    def test_protocol_has_is_available(self):
        """Protocol must declare is_available method."""
        self.assertTrue(hasattr(RetryProvider, "is_available"))

    def test_protocol_has_get_stats(self):
        """Protocol must declare get_stats method."""
        self.assertTrue(hasattr(RetryProvider, "get_stats"))


class _MinimalRetryProvider:
    """Minimal structurally-compatible implementation for subtyping verification."""

    def retry_with_fallback(
        self,
        func: Callable[[], Any],
        max_attempts: int = 3,  # noqa: ARG002
        fallback: Callable[[], Any] | None = None,  # noqa: ARG002
    ) -> Any:
        return func()

    def is_available(self) -> bool:
        return True

    def get_stats(self) -> dict[str, Any]:
        return {}


class TestRetryProviderStructuralSubtyping(unittest.TestCase):
    """Verify any class with the right methods satisfies RetryProvider structurally."""

    def test_minimal_implementation_is_instance_of_protocol(self):
        """A class implementing all methods should satisfy runtime_checkable isinstance."""
        provider = _MinimalRetryProvider()
        self.assertIsInstance(provider, RetryProvider)

    def test_missing_method_fails_isinstance(self):
        """A class missing a method should NOT satisfy isinstance."""

        class IncompleteProvider:
            def retry_with_fallback(self, func, max_attempts=3, fallback=None):  # noqa: ARG002
                return func()

            def is_available(self) -> bool:
                return True

            # Missing get_stats

        self.assertNotIsInstance(IncompleteProvider(), RetryProvider)


class TestNullRetryProviderContract(unittest.TestCase):
    """Contract tests for NullRetryProvider (degraded no-op) compliance."""

    def _get_provider(self) -> NullRetryProvider:
        return NullRetryProvider()

    def test_has_retry_with_fallback(self):
        provider = self._get_provider()
        self.assertTrue(callable(provider.retry_with_fallback))

    def test_has_is_available(self):
        provider = self._get_provider()
        self.assertTrue(callable(provider.is_available))

    def test_has_get_stats(self):
        provider = self._get_provider()
        self.assertTrue(callable(provider.get_stats))

    def test_retry_with_fallback_executes_function(self):
        """retry_with_fallback should execute the function and return its result."""
        provider = self._get_provider()
        result = provider.retry_with_fallback(lambda: 42)
        self.assertEqual(result, 42)

    def test_retry_with_fallback_uses_fallback_on_failure(self):
        """On failure with fallback provided, should call fallback."""
        provider = self._get_provider()

        def failing_func():
            raise RuntimeError("intentional")

        result = provider.retry_with_fallback(failing_func, fallback=lambda: "fallback")
        self.assertEqual(result, "fallback")

    def test_retry_with_fallback_raises_without_fallback(self):
        """On failure without fallback, should re-raise the exception."""
        provider = self._get_provider()

        def failing_func():
            raise RuntimeError("no fallback")

        with self.assertRaises(RuntimeError):
            provider.retry_with_fallback(failing_func)

    def test_is_available_returns_bool(self):
        provider = self._get_provider()
        self.assertIsInstance(provider.is_available(), bool)

    def test_is_available_returns_false(self):
        """NullRetryProvider must report unavailable (degraded mode)."""
        provider = self._get_provider()
        self.assertFalse(provider.is_available())

    def test_get_stats_returns_dict(self):
        provider = self._get_provider()
        self.assertIsInstance(provider.get_stats(), dict)

    def test_get_stats_has_required_keys(self):
        """get_stats should include total_attempts, success_count, failure_count."""
        provider = self._get_provider()
        provider.retry_with_fallback(lambda: 1)
        stats = provider.get_stats()
        self.assertIn("total_attempts", stats)
        self.assertIn("success_count", stats)
        self.assertIn("failure_count", stats)

    def test_satisfies_protocol_isinstance(self):
        """NullRetryProvider should satisfy RetryProvider isinstance check."""
        self.assertIsInstance(self._get_provider(), RetryProvider)


class TestNullRetryProviderExtendedContract(unittest.TestCase):
    """Extended contract tests for NullRetryProvider behavior."""

    def _get_provider(self) -> NullRetryProvider:
        return NullRetryProvider()

    def test_null_retry_returns_func_result(self):
        """NullRetryProvider should return the function's result directly."""
        provider = self._get_provider()
        result = provider.retry_with_fallback(lambda: "success")
        self.assertEqual(result, "success")

    def test_null_retry_with_fallback_on_success(self):
        """NullRetryProvider should not call fallback when func succeeds."""
        provider = self._get_provider()
        fallback_called = []

        def fallback():
            fallback_called.append(True)
            return "fallback"

        result = provider.retry_with_fallback(lambda: 42, fallback=fallback)
        self.assertEqual(result, 42)
        self.assertEqual(len(fallback_called), 0)

    def test_null_retry_stats_after_success(self):
        """NullRetryProvider stats should reflect successful calls."""
        provider = self._get_provider()
        provider.retry_with_fallback(lambda: 1)
        provider.retry_with_fallback(lambda: 2)
        stats = provider.get_stats()
        self.assertEqual(stats["total_attempts"], 2)
        self.assertEqual(stats["success_count"], 2)
        self.assertEqual(stats["failure_count"], 0)

    def test_null_retry_stats_after_failure(self):
        """NullRetryProvider stats should reflect failed calls."""
        provider = self._get_provider()

        def fail():
            raise RuntimeError("fail")

        provider.retry_with_fallback(fail, fallback=lambda: "fb")
        stats = provider.get_stats()
        self.assertEqual(stats["total_attempts"], 1)
        self.assertEqual(stats["failure_count"], 1)
        self.assertEqual(stats["fallback_count"], 1)

    def test_null_retry_stats_accumulate(self):
        """NullRetryProvider stats should accumulate across mixed calls."""
        provider = self._get_provider()
        provider.retry_with_fallback(lambda: "ok1")
        provider.retry_with_fallback(lambda: "ok2")

        def fail():
            raise ValueError("nope")

        provider.retry_with_fallback(fail, fallback=lambda: "fb")
        stats = provider.get_stats()
        self.assertEqual(stats["total_attempts"], 3)
        self.assertEqual(stats["success_count"], 2)
        self.assertEqual(stats["failure_count"], 1)
        self.assertEqual(stats["fallback_count"], 1)

    def test_null_retry_avg_attempts_is_one(self):
        """NullRetryProvider avg_attempts should always be 1.0 (no retry)."""
        provider = self._get_provider()
        provider.retry_with_fallback(lambda: 1)
        stats = provider.get_stats()
        self.assertEqual(stats["avg_attempts"], 1.0)

    def test_null_retry_provider_type_is_null(self):
        """NullRetryProvider stats should report provider_type='null'."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertEqual(stats.get("provider_type"), "null")

    def test_null_retry_degraded_flag(self):
        """NullRetryProvider stats should include degraded=True."""
        provider = self._get_provider()
        stats = provider.get_stats()
        self.assertTrue(stats.get("degraded", False))


class TestRetryBaseContract(unittest.TestCase):
    """Contract tests for LLMRetryBase shared strategy methods."""

    def _get_manager(self):
        from scripts.collaboration.llm_retry import LLMRetryManager
        return LLMRetryManager()

    def test_is_retryable_connection_error(self):
        """ConnectionError message should be classified as retryable."""
        manager = self._get_manager()
        self.assertTrue(manager.is_retryable_error(ConnectionError("connection refused")))

    def test_is_retryable_timeout_error(self):
        """TimeoutError message should be classified as retryable."""
        manager = self._get_manager()
        self.assertTrue(manager.is_retryable_error(TimeoutError("request timeout")))

    def test_is_retryable_503_error(self):
        """HTTP 503 error message should be classified as retryable."""
        manager = self._get_manager()
        self.assertTrue(manager.is_retryable_error(RuntimeError("503 Service Unavailable")))

    def test_not_retryable_value_error(self):
        """ValueError without retryable keywords should NOT be retryable."""
        manager = self._get_manager()
        self.assertFalse(manager.is_retryable_error(ValueError("invalid argument")))

    def test_not_retryable_type_error(self):
        """TypeError without retryable keywords should NOT be retryable."""
        manager = self._get_manager()
        self.assertFalse(manager.is_retryable_error(TypeError("wrong type")))

    def test_rate_limit_error_detected(self):
        """429 / 'rate limit' errors should be detected as rate-limit."""
        manager = self._get_manager()
        self.assertTrue(manager.is_rate_limit_error(RuntimeError("429 Too Many Requests")))
        self.assertTrue(manager.is_rate_limit_error(RuntimeError("rate limit exceeded")))

    def test_calculate_delay_increases_with_attempts(self):
        """Exponential backoff delay should increase with attempt number."""
        from scripts.collaboration.llm_retry_base import RetryConfig
        manager = self._get_manager()
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, jitter=False)
        delay_0 = manager.calculate_delay(0, config)
        delay_1 = manager.calculate_delay(1, config)
        delay_2 = manager.calculate_delay(2, config)
        self.assertGreater(delay_1, delay_0)
        self.assertGreater(delay_2, delay_1)

    def test_calculate_delay_capped_at_max(self):
        """Delay should be capped at config.max_delay."""
        from scripts.collaboration.llm_retry_base import RetryConfig
        manager = self._get_manager()
        config = RetryConfig(initial_delay=1.0, exponential_base=2.0, max_delay=10.0, jitter=False)
        delay = manager.calculate_delay(20, config)
        self.assertLessEqual(delay, 10.0)

    def test_jitter_strategy_none_is_deterministic(self):
        """JitterStrategy.NONE should produce deterministic delay (no jitter)."""
        from scripts.collaboration.llm_retry_base import JitterStrategy, RetryConfig
        manager = self._get_manager()
        config = RetryConfig(
            initial_delay=2.0, exponential_base=2.0, max_delay=60.0,
            jitter=True, jitter_strategy=JitterStrategy.NONE,
        )
        delay1 = manager.calculate_delay(1, config)
        delay2 = manager.calculate_delay(1, config)
        self.assertEqual(delay1, delay2)

    def test_retry_config_default_values(self):
        """RetryConfig should have sensible default values."""
        from scripts.collaboration.llm_retry_base import RetryConfig
        config = RetryConfig()
        self.assertEqual(config.max_retries, 3)
        self.assertEqual(config.initial_delay, 1.0)
        self.assertEqual(config.max_delay, 60.0)
        self.assertEqual(config.exponential_base, 2.0)
        self.assertTrue(config.jitter)

    def test_circuit_breaker_initial_state_closed(self):
        """New circuit breaker should start in 'closed' state."""
        manager = self._get_manager()
        cb = manager.get_circuit_breaker("openai")
        self.assertEqual(cb.state, "closed")
        self.assertEqual(cb.failure_count, 0)

    def test_get_stats_includes_circuit_breakers(self):
        """get_stats() should include circuit_breakers key."""
        manager = self._get_manager()
        manager.get_circuit_breaker("openai")
        stats = manager.get_stats()
        self.assertIn("circuit_breakers", stats)
        self.assertIn("openai", stats["circuit_breakers"])

    def test_get_stats_has_total_calls(self):
        """get_stats() should include total_calls counter."""
        manager = self._get_manager()
        stats = manager.get_stats()
        self.assertIn("total_calls", stats)

    def test_llm_retry_manager_satisfies_stats_structure(self):
        """LLMRetryManager should have all required stats keys initialized."""
        manager = self._get_manager()
        stats = manager.get_stats()
        for key in ("total_calls", "successful_calls", "failed_calls", "retries", "fallbacks"):
            self.assertIn(key, stats, f"Missing stats key: {key}")


class T6_RetryProviderBoundaryContract(unittest.TestCase):
    """Boundary and accuracy contract tests for RetryProvider implementations.

    Covers zero-retry behavior, last-attempt success, total backend
    failure, degraded-mode availability, stats accuracy, and exception
    type filtering (only retryable exceptions trigger retries).
    """

    def _get_null_provider(self) -> NullRetryProvider:
        """Return a NullRetryProvider (degraded, no actual retry)."""
        return NullRetryProvider()

    def _get_manager(self) -> Any:
        """Return a fresh LLMRetryManager for real retry-behavior tests."""
        from scripts.collaboration.llm_retry import LLMRetryManager
        return LLMRetryManager()

    def _fast_config(self, max_retries: int = 3) -> Any:
        """Return a RetryConfig with zero-delay backoff for fast tests."""
        from scripts.collaboration.llm_retry_base import RetryConfig
        return RetryConfig(
            max_retries=max_retries,
            initial_delay=0.0,
            max_delay=0.0,
            exponential_base=1.0,
            jitter=False,
        )

    def test_null_retry_zero_max_attempts_still_executes(self) -> None:
        """NullRetryProvider must execute the function even with max_attempts=0.

        The null provider ignores max_attempts (no retry loop), but must
        still call the function once and return its result. This verifies
        the zero-retry boundary does not skip execution entirely.
        """
        provider = self._get_null_provider()
        result = provider.retry_with_fallback(lambda: 42, max_attempts=0)
        self.assertEqual(result, 42)

    def test_manager_last_attempt_succeeds(self) -> None:
        """LLMRetryManager must succeed when the final attempt passes.

        Function fails on attempts 1..N-1 and succeeds on attempt N.
        The manager must retry through failures and return the final
        successful result without raising.
        """
        manager = self._get_manager()
        config = self._fast_config(max_retries=3)
        call_count = [0]

        def flaky_func() -> str:
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("connection timeout")
            return "success-on-3rd"

        result = manager.retry_with_fallback(
            flaky_func, args=(), kwargs={}, config=config,
        )
        self.assertEqual(result, "success-on-3rd")
        self.assertEqual(call_count[0], 3)
        stats = manager.get_stats()
        self.assertGreaterEqual(stats["retries"], 2)

    def test_manager_all_attempts_fail_raises_last_error(self) -> None:
        """LLMRetryManager must raise the last error when all attempts fail.

        With no fallback backends, exhausting all retries must re-raise
        the final exception so callers can handle total failure.
        """
        manager = self._get_manager()
        config = self._fast_config(max_retries=2)

        def always_fail() -> None:
            raise ConnectionError("connection timeout")

        with self.assertRaises(ConnectionError):
            manager.retry_with_fallback(always_fail, args=(), kwargs={}, config=config)
        stats = manager.get_stats()
        self.assertGreaterEqual(stats["total_calls"], 1)

    def test_null_provider_is_available_false_in_degraded_mode(self) -> None:
        """NullRetryProvider.is_available() must return False (degraded).

        In degraded mode, the retry provider reports unavailable so
        callers know retries are not actually being attempted.
        """
        provider = self._get_null_provider()
        self.assertFalse(provider.is_available())
        # Must remain False even after multiple calls (no state change)
        provider.retry_with_fallback(lambda: 1)
        self.assertFalse(provider.is_available())

    def test_null_provider_get_stats_accuracy_mixed_calls(self) -> None:
        """NullRetryProvider.get_stats() must accurately count success/failure.

        After a sequence of 3 successful calls and 2 failed-with-fallback
        calls, stats must show total_attempts=5, success_count=3,
        failure_count=2, fallback_count=2.
        """
        provider = self._get_null_provider()
        # 3 successes
        provider.retry_with_fallback(lambda: "ok1")
        provider.retry_with_fallback(lambda: "ok2")
        provider.retry_with_fallback(lambda: "ok3")

        # 2 failures with fallback
        def fail() -> None:
            raise RuntimeError("fail")

        provider.retry_with_fallback(fail, fallback=lambda: "fb1")
        provider.retry_with_fallback(fail, fallback=lambda: "fb2")

        stats = provider.get_stats()
        self.assertEqual(stats["total_attempts"], 5)
        self.assertEqual(stats["success_count"], 3)
        self.assertEqual(stats["failure_count"], 2)
        self.assertEqual(stats["fallback_count"], 2)

    def test_manager_non_retryable_error_does_not_retry(self) -> None:
        """LLMRetryManager must NOT retry non-retryable exceptions.

        ValueError without retryable keywords is non-retryable. The
        manager must raise immediately without incrementing the retries
        counter, even though max_retries > 1.
        """
        manager = self._get_manager()
        config = self._fast_config(max_retries=3)
        call_count = [0]

        def raises_value_error() -> None:
            call_count[0] += 1
            raise ValueError("invalid argument, not retryable")

        with self.assertRaises(ValueError):
            manager.retry_with_fallback(
                raises_value_error, args=(), kwargs={}, config=config,
            )
        self.assertEqual(call_count[0], 1, "Non-retryable error must not trigger retries")
        stats = manager.get_stats()
        self.assertEqual(stats["retries"], 0)

    def test_null_provider_fallback_not_called_on_success(self) -> None:
        """NullRetryProvider must not invoke fallback when func succeeds.

        Verifies the success path: fallback is only a safety net and
        must remain untouched when the primary function returns normally.
        """
        provider = self._get_null_provider()
        fallback_calls = [0]

        def fallback() -> str:
            fallback_calls[0] += 1
            return "fallback"

        result = provider.retry_with_fallback(lambda: "primary-ok", fallback=fallback)
        self.assertEqual(result, "primary-ok")
        self.assertEqual(fallback_calls[0], 0)

    def test_null_provider_stats_avg_attempts_always_one(self) -> None:
        """NullRetryProvider.avg_attempts must always be 1.0 (no retry).

        Even after a mix of successes and failures, the null provider
        never retries, so avg_attempts must remain exactly 1.0.
        """
        provider = self._get_null_provider()
        provider.retry_with_fallback(lambda: 1)
        provider.retry_with_fallback(lambda: 2)

        def fail() -> None:
            raise RuntimeError("fail")

        provider.retry_with_fallback(fail, fallback=lambda: "fb")
        stats = provider.get_stats()
        self.assertEqual(stats["avg_attempts"], 1.0)


if __name__ == "__main__":
    unittest.main()
