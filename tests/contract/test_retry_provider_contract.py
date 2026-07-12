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


if __name__ == "__main__":
    unittest.main()
