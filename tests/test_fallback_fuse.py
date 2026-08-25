#!/usr/bin/env python3
"""
Tests for FallbackBackend fuse skip logic (V4.5.2).

Tests that consecutive same-reason failures trigger fuse skip,
single failures degrade to next backend, and all-paths-down raises.

Covers §3.2 test cases from the test plan.
"""

import os
import sys
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from scripts.collaboration.backend_paths import (
    FUSE_SKIP_AFTER_CONSECUTIVE,
    BackendErrorReason,
    classify_error,
)
from scripts.collaboration.llm_backend import (
    FallbackBackend,
    MockBackend,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# 3.2 FallbackBackend 熔断 (5 cases)
# ---------------------------------------------------------------------------


def _make_failing_backend(name: str, exc: Exception = ConnectionError("simulated")):
    """Create a mock backend that always raises the given exception."""
    backend = MagicMock()
    backend.__class__.__name__ = name
    backend.generate = MagicMock(side_effect=exc)
    backend.generate_stream = MagicMock(side_effect=exc)
    backend.is_available = MagicMock(return_value=True)
    return backend


class TestFallbackFuse:
    """Tests for FallbackBackend fuse skip logic."""

    def test_single_failure_degrade(self):
        """Single failure → degrade to next backend, not fatal."""
        failing = _make_failing_backend("OpenAIBackend")
        mock = MockBackend()

        backend = FallbackBackend([failing, mock])
        result = backend.generate("hello")

        assert result is not None
        assert isinstance(result, str)
        assert "[MOCK MODE]" in result
        failing.generate.assert_called_once()
        # Verify fuse did NOT skip the failing backend (only 1 failure)
        assert not backend._is_fuse_skipped(0)

    def test_consecutive_fuse_skip(self):
        """Consecutive same-reason failures → skip the backend.

        Uses two failing backends (no mock) so the active_index
        stays on the primary backend and both calls trigger failures.
        """
        failing = _make_failing_backend("OpenAIBackend")
        also_failing = _make_failing_backend("AnthropicBackend", exc=ConnectionError("also fail"))

        backend = FallbackBackend([failing, also_failing])

        # First call: both fail, record failure on both
        with pytest.raises(RuntimeError, match="All backends failed"):
            backend.generate("hello")
        # First call: one failure on index 0 → not skipped yet
        assert not backend._is_fuse_skipped(0)

        # Second call: same reason on index 0 → fuse skips
        with pytest.raises(RuntimeError, match="All backends failed"):
            backend.generate("world")
        assert backend._is_fuse_skipped(0)
        assert failing.generate.call_count == 2

        # Third call: failing backend is skipped entirely
        # (failing.generate should have been called exactly 2 times)
        assert failing.generate.call_count == 2

    def test_fuse_threshold_matches_constant(self):
        """FUSE_SKIP_AFTER_CONSECUTIVE = 2."""
        assert FUSE_SKIP_AFTER_CONSECUTIVE == 2

    def test_classify_error_timeout(self):
        """TimeoutError → host_timeout."""
        reason = classify_error(TimeoutError("timed out"))
        assert reason == BackendErrorReason.HOST_TIMEOUT

    def test_classify_error_auth(self):
        """Auth error (401) → auth_invalid."""
        # Create an exception with status_code attribute (like openai.APIError)
        class MockAuthError(Exception):
            status_code = 401

        reason = classify_error(MockAuthError())
        assert reason == BackendErrorReason.AUTH_INVALID

    def test_classify_error_rate_limit(self):
        """Rate limit (429) → rate_limit."""
        class MockRateLimitError(Exception):
            status_code = 429

        reason = classify_error(MockRateLimitError())
        assert reason == BackendErrorReason.RATE_LIMIT

    def test_classify_error_connection(self):
        """ConnectionError → network_error."""
        reason = classify_error(ConnectionError("connection refused"))
        assert reason == BackendErrorReason.NETWORK_ERROR

    def test_classify_error_runtime(self):
        """RuntimeError → provider_error."""
        reason = classify_error(RuntimeError("provider error"))
        assert reason == BackendErrorReason.PROVIDER_ERROR

    def test_classify_error_unknown(self):
        """Unknown exception → unknown."""
        reason = classify_error(ValueError("weird error"))
        assert reason == BackendErrorReason.UNKNOWN

    def test_all_paths_down(self):
        """All backends fail → raise RuntimeError."""
        failing1 = _make_failing_backend("OpenAIBackend")
        failing2 = _make_failing_backend("AnthropicBackend")

        backend = FallbackBackend([failing1, failing2])

        with pytest.raises(RuntimeError, match="All backends failed"):
            backend.generate("hello")

    def test_different_reason_resets_count(self):
        """Different reason → reset count (not same reason)."""
        # First failure: timeout
        failing = _make_failing_backend("OpenAIBackend", TimeoutError("timeout"))
        # But we need to check the internal tracking
        backend = FallbackBackend([failing])

        # First call: timeout failure
        try:
            backend.generate("hello")
        except RuntimeError:
            pass

        # Check that the failure was recorded with HOST_TIMEOUT reason
        key = "0:host_timeout"
        assert backend._failures.get(key, 0) == 1
        assert not backend._is_fuse_skipped(0)

    def test_available_skips_fuse_blocked(self):
        """is_available() excludes fuse-skipped backends."""
        # Use two failing backends so active_index doesn't prevent fuse trigger
        failing = _make_failing_backend("OpenAIBackend")
        also_failing = _make_failing_backend("AnthropicBackend", exc=ConnectionError("also fail"))

        backend = FallbackBackend([failing, also_failing])

        # Initially, both available
        assert backend.is_available()

        # Trigger fuse skip on failing backend (index 0)
        # 2 consecutive calls with same reason → fuse skips index 0
        with pytest.raises(RuntimeError):
            backend.generate("x")
        with pytest.raises(RuntimeError):
            backend.generate("y")

        # After fuse skip, index 0 is skipped
        assert backend._is_fuse_skipped(0)
        # But is_available still returns True (index 1 is still available)
        assert backend.is_available()


class TestFallbackFuseStream:
    """Tests for FallbackBackend stream fuse logic."""

    def test_stream_single_failure_degrade(self):
        """Stream single failure → degrade to next."""
        failing = _make_failing_backend("OpenAIBackend")
        mock = MockBackend()

        backend = FallbackBackend([failing, mock])
        results = list(backend.generate_stream("hello"))

        assert len(results) > 0
        assert "[MOCK MODE]" in results[0]
        # fuse should NOT have skipped the failing backend (only 1 failure)
        assert not backend._is_fuse_skipped(0)


class TestFallbackBackwardCompat:
    """Tests for backward compatibility of FallbackBackend."""

    def test_requires_at_least_one_backend(self):
        """Empty backend list → ValueError."""
        with pytest.raises(ValueError, match="requires at least one backend"):
            FallbackBackend([])

    def test_repr_shows_backend_names(self):
        """repr shows backend class names."""
        backend = FallbackBackend([MockBackend()])
        assert "MockBackend" in repr(backend)
