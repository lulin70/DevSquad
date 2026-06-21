#!/usr/bin/env python3
"""
Async LLM Retry and Fallback Module

Provides asynchronous retry logic with exponential backoff, circuit breaker,
and multi-backend fallback for LLM API calls.

Features:
- Async exponential backoff retry
- Circuit breaker pattern (async-safe)
- Multi-backend fallback
- Rate limit detection
- Statistics tracking

Usage:
    from scripts.collaboration import async_retry_with_fallback

    @async_retry_with_fallback(max_retries=3, fallback_backends=["openai", "anthropic"])
    async def call_llm(prompt: str, backend: str = "openai"):
        return await your_async_api_call(prompt, backend)

    result = await call_llm("Hello, world!")
"""

import asyncio
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any

from .llm_retry_base import (
    CircuitBreakerError,
    CircuitBreakerState,
    JitterStrategy,
    LLMRetryBase,
    RateLimitError,
    RetryConfig,
)

logger = logging.getLogger(__name__)

# Re-export for backward compatibility.
__all__ = [
    "AsyncLLMRetryManager",
    "CircuitBreakerError",
    "CircuitBreakerState",
    "JitterStrategy",
    "RateLimitError",
    "RetryConfig",
    "async_retry_with_fallback",
    "get_async_retry_manager",
]


class AsyncLLMRetryManager(LLMRetryBase):
    """
    Async retry manager with circuit breaker and fallback.

    Thread-safe and asyncio-compatible implementation.

    Inherits shared retry/circuit-breaker strategy (delay calculation,
    error classification, state transitions) from LLMRetryBase.
    Only the I/O layer (asyncio.Lock, asyncio.sleep, await) is implemented here.
    """

    def __init__(self) -> None:
        """Initialize async retry manager"""
        # Initialize shared strategy from base class (sets stats, circuit_breakers)
        super().__init__()
        # Extend base stats with async-specific "circuit_breaker_trips" counter
        self.stats["circuit_breaker_trips"] = 0
        self._lock = asyncio.Lock()

        logger.info("AsyncLLMRetryManager initialized")

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for retry attempt — delegates to base class."""
        return self.calculate_delay(attempt, config)

    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable — delegates to base class."""
        return self.is_retryable_error(error)

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is rate limit related — delegates to base class."""
        return self.is_rate_limit_error(error)

    def _get_circuit_breaker(self, backend: str) -> CircuitBreakerState:
        """Get or create circuit breaker for backend — delegates to base class."""
        return self.get_circuit_breaker(backend)

    async def _check_circuit_breaker(self, backend: str) -> None:
        """Check if circuit breaker allows request (async, with lock)."""
        async with self._lock:
            try:
                self.check_circuit_breaker_state(backend)
            except CircuitBreakerError:
                # Note: async version does not increment circuit_breaker_trips here;
                # the trip is counted in _record_failure when the breaker opens.
                raise

    async def _record_success(self, backend: str):
        """Record successful call (async, with lock)."""
        async with self._lock:
            self.record_success(backend)

    async def _record_failure(self, backend: str, _error: Exception):
        """Record failed call (async, with lock)."""
        async with self._lock:
            opened = self.record_failure(backend)
            if opened:
                self.stats["circuit_breaker_trips"] += 1

    async def retry_with_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        config: RetryConfig,
        fallback_backends: list[str] | None,
        current_backend: str | None,
    ) -> Any:
        """
        Execute async function with retry and fallback logic.

        Args:
            func: Async function to execute
            args: Positional arguments
            kwargs: Keyword arguments
            config: Retry configuration
            fallback_backends: List of fallback backends
            current_backend: Current backend name

        Returns:
            Function result

        Raises:
            Exception: If all retries and fallbacks fail
        """
        self.stats["total_calls"] += 1
        last_error = None

        # Check circuit breaker first
        if current_backend:
            try:
                await self._check_circuit_breaker(current_backend)
            except CircuitBreakerError as e:
                logger.warning(str(e))
                # Circuit breaker open, try fallback immediately
                if fallback_backends:
                    return await self._try_fallback(func, args, kwargs, config, fallback_backends, current_backend)
                raise

        # Try with retries
        for attempt in range(config.max_retries):
            try:
                result = await func(*args, **kwargs)
                if current_backend:
                    await self._record_success(current_backend)
                self.stats["successful_calls"] += 1
                return result

            except Exception as e:
                last_error = e

                if current_backend:
                    await self._record_failure(current_backend, e)

                # Check if retryable
                if not self._is_retryable_error(e):
                    logger.error("Non-retryable error: %s", e)
                    break

                # Last attempt, no need to delay
                if attempt < config.max_retries - 1:
                    delay = self.get_enhanced_delay(attempt, config, e)

                    logger.info("Retry attempt %s/%s after %.1fs delay", attempt + 1, config.max_retries, delay)
                    await asyncio.sleep(delay)
                    self.stats["retries"] += 1

        # Primary backend failed, try fallback
        if fallback_backends:
            try:
                return await self._try_fallback(func, args, kwargs, config, fallback_backends, current_backend)
            except Exception as fallback_error:
                logger.error("All fallback attempts failed: %s", fallback_error)
                last_error = fallback_error

        # All attempts failed
        self.stats["failed_calls"] += 1
        raise last_error

    async def _try_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        _config: RetryConfig,
        fallback_backends: list[str],
        exclude_backend: str | None,
    ) -> Any:
        """Try fallback to alternative backends"""
        for backend in fallback_backends:
            if backend == exclude_backend:
                continue

            try:
                await self._check_circuit_breaker(backend)
            except CircuitBreakerError:
                logger.warning("Skipping %s (circuit breaker open)", backend)
                continue

            logger.info("Attempting fallback to %s", backend)
            self.stats["fallbacks"] += 1

            # Update backend parameter in kwargs (async only sets if "backend" key exists)
            fallback_kwargs = self.build_fallback_kwargs(kwargs, backend, always_set=False)

            try:
                result = await func(*args, **fallback_kwargs)
                await self._record_success(backend)
                logger.info("Fallback to %s successful", backend)
                return result
            except Exception as e:
                await self._record_failure(backend, e)
                logger.warning("Fallback to %s failed: %s", backend, e)
                continue

        raise Exception("All fallback backends failed")

    def get_stats(self) -> dict[str, Any]:
        """Get retry statistics"""
        return self.stats.copy()

    async def reset_circuit_breaker(self, backend: str):
        """Manually reset circuit breaker for a backend"""
        async with self._lock:
            if backend in self.circuit_breakers:
                cb = self.circuit_breakers[backend]
                cb.state = "closed"
                cb.failure_count = 0
                cb.last_failure_time = None
                logger.info("Circuit breaker reset: %s", backend)


# Global async retry manager
_global_async_retry_manager: AsyncLLMRetryManager | None = None


def get_async_retry_manager() -> AsyncLLMRetryManager:
    """Get global async retry manager instance (singleton)"""
    global _global_async_retry_manager
    if _global_async_retry_manager is None:
        _global_async_retry_manager = AsyncLLMRetryManager()
    return _global_async_retry_manager


def async_retry_with_fallback(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    fallback_backends: list[str] | None = None,
):
    """
    Decorator for async functions with retry and fallback.

    Args:
        max_retries: Maximum number of retries
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        exponential_base: Base for exponential backoff
        jitter: Whether to add random jitter
        fallback_backends: List of fallback backends

    Usage:
        @async_retry_with_fallback(max_retries=3, fallback_backends=["openai", "anthropic"])
        async def call_llm(prompt: str, backend: str = "openai"):
            return await your_api_call(prompt, backend)
    """

    def decorator(func: Callable):
        """Decorate an async function to add retry-with-fallback behavior.

        Args:
            func: Async callable to wrap.

        Returns:
            Wrapped async callable that retries on failure and falls back
            across backends.
        """
        @wraps(func)
        async def wrapper(*args, **kwargs):
            """Invoke the wrapped async function with retry and fallback handling."""
            config = RetryConfig(
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter,
            )

            # Extract current backend from kwargs
            current_backend = kwargs.get("backend")

            manager = get_async_retry_manager()
            return await manager.retry_with_fallback(func, args, kwargs, config, fallback_backends, current_backend)

        return wrapper

    return decorator


if __name__ == "__main__":
    # Example usage
    async def main():
        """Run an example demonstrating async retry-with-fallback behavior."""
        @async_retry_with_fallback(max_retries=3, fallback_backends=["backup"])
        async def test_func(value: int, backend: str = "primary"):
            """Example function that fails for values below 3 to demonstrate retries."""
            print(f"Calling {backend} with {value}")
            if value < 3:
                raise Exception("503 Service Unavailable")
            return f"Success from {backend}"

        try:
            result = await test_func(1)
            print(f"Result: {result}")
        except Exception as e:
            print(f"Failed: {e}")

        # Print stats
        manager = get_async_retry_manager()
        print(f"Stats: {manager.get_stats()}")

    asyncio.run(main())
