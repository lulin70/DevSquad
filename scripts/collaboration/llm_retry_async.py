#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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
import random
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Callable, Any, Dict
from functools import wraps

logger = logging.getLogger(__name__)


class RateLimitError(Exception):
    """Raised when rate limit is exceeded"""
    pass


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open"""
    pass


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True


@dataclass
class CircuitBreakerState:
    """Circuit breaker state for a backend"""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half_open
    failure_threshold: int = 5
    timeout_seconds: int = 60


class AsyncLLMRetryManager:
    """
    Async retry manager with circuit breaker and fallback.
    
    Thread-safe and -compatible implementation.
    """
    
    def __init__(self):
        """Initialize async retry manager"""
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "circuit_breaker_trips": 0
        }
        self._lock = asyncio.Lock()
        
        logger.info("AsyncLLMRetryManager initialized")
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """Calculate delay for retry attempt with exponential backoff"""
        delay = min(
            config.initial_delay * (config.exponential_base ** attempt),
            config.max_delay
        )
        
        if config.jitter:
            # Add jitter: random value between 50% and 150% of delay
            delay = delay * (0.5 + random.random())
        
        return delay
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """Check if error is retryable"""
        error_str = str(error).lower()
        retryable_patterns = [
            "timeout", "connection", "network", "unavailable",
            "503", "502", "504", "429"
        ]
        return any(pattern in error_str for pattern in retryable_patterns)
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """Check if error is rate limit related"""
        error_str = str(error).lower()
        return "429" in error_str or "rate limit" in error_str
    
    def _get_circuit_breaker(self, backend: str) -> CircuitBreakerState:
        """Get or create circuit breaker for backend"""
        if backend not in self.circuit_breakers:
            self.circuit_breakers[backend] = CircuitBreakerState()
        return self.circuit_breakers[backend]
    
    async def _check_circuit_breaker(self, backend: str):
        """Check if circuit breaker allows request"""
        async with self._lock:
            cb = self._get_circuit_breaker(backend)
            
            if cb.state == "open":
                # Check if timeout has passed
                if cb.last_failure_time:
                    elapsed = (datetime.now() - cb.last_failure_time).total_seconds()
                    if elapsed > cb.timeout_seconds:
                        # Move to half-open state
                        cb.state = "half_open"
                        logger.info(f"Circuit breaker half-open: {backend}")
                    else:
                        raise CircuitBreakerError(f"Circuit breaker open for {backend}")
    
    async def _record_success(self, backend: str):
        """Record successful call"""
        async with self._lock:
            cb = self._get_circuit_breaker(backend)
            
            if cb.state == "half_open":
                # Close circuit breaker
                cb.state = "closed"
                cb.failure_count = 0
                logger.info(f"Circuit breaker closed: {backend}")
    
    async def _record_failure(self, backend: str, error: Exception):
        """Record failed call"""
        async with self._lock:
            cb = self._get_circuit_breaker(backend)
            cb.failure_count += 1
            cb.last_failure_time = datetime.now()
            
            if cb.failure_count >= cb.failure_threshold:
                if cb.state != "open":
                    cb.state = "open"
                    self.stats["circuit_breaker_trips"] += 1
                    logger.warning(f"Circuit breaker opened: {backend} (failures: {cb.failure_count})")
    
    async def retry_with_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        config: RetryConfig,
        fallback_backends: Optional[List[str]],
        current_backend: Optional[str]
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
                    return await self._try_fallback(
                        func, args, kwargs, config, fallback_backends, current_backend
                    )
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
                    logger.error(f"Non-retryable error: {e}")
                    break
                
                # Last attempt, no need to delay
                if attempt < config.max_retries - 1:
                    delay = self._calculate_delay(attempt, config)
                    
                    # Rate limit errors need longer delay
                    if self._is_rate_limit_error(e):
                        delay *= 3
                        logger.warning(f"Rate limit detected, waiting {delay:.1f}s")
                    
                    logger.info(
                        f"Retry attempt {attempt + 1}/{config.max_retries} "
                        f"after {delay:.1f}s delay"
                    )
                    await asyncio.sleep(delay)
                    self.stats["retries"] += 1
        
        # Primary backend failed, try fallback
        if fallback_backends:
            try:
                return await self._try_fallback(
                    func, args, kwargs, config, fallback_backends, current_backend
                )
            except Exception as fallback_error:
                logger.error(f"All fallback attempts failed: {fallback_error}")
                last_error = fallback_error
        
        # All attempts failed
        self.stats["failed_calls"] += 1
        raise last_error
    
    async def _try_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        config: RetryConfig,
        fallback_backends: List[str],
        exclude_backend: Optional[str]
    ) -> Any:
        """Try fallback to alternative backends"""
        for backend in fallback_backends:
            if backend == exclude_backend:
                continue
            
            try:
                await self._check_circuit_breaker(backend)
            except CircuitBreakerError:
                logger.warning(f"Skipping {backend} (circuit breaker open)")
                continue
            
            logger.info(f"Attempting fallback to {backend}")
            self.stats["fallbacks"] += 1
            
            # Update backend parameter in kwargs
            fallback_kwargs = kwargs.copy()
            if "backend" in fallback_kwargs:
                fallback_kwargs["backend"] = backend
            
            try:
                result = await func(*args, **fallback_kwargs)
                await self._record_success(backend)
                logger.info(f"Fallback to {backend} successful")
                return result
            except Exception as e:
                await self._record_failure(backend, e)
                logger.warning(f"Fallback to {backend} failed: {e}")
                continue
        
        raise Exception("All fallback backends failed")
    
    def get_stats(self) -> Dict[str, Any]:
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
                logger.info(f"Circuit breaker reset: {backend}")


# Global async retry manager
_global_async_retry_manager: Optional[AsyncLLMRetryManager] = None


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
    fallback_backends: Optional[List[str]] = None
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
        @wraps(func)
        async def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay,
                exponential_base=exponential_base,
                jitter=jitter
            )
            
            # Extract current backend from kwargs
            current_backend = kwargs.get("backend")
            
            manager = get_async_retry_manager()
            return await manager.retry_with_fallback(
                func, args, kwargs, config, fallback_backends, current_backend
            )
        
        return wrapper
    return decorator


if __name__ == "__main__":
    # Example usage
    async def main():
        @async_retry_with_fallback(max_retries=3, fallback_backends=["backup"])
        async def test_func(value: int, backend: str = "primary"):
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
