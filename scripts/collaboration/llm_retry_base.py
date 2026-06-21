#!/usr/bin/env python3
"""
LLM Retry Base — Shared retry/circuit-breaker strategy for sync and async.

Extracts non-I/O retry logic that is identical or near-identical between
LLMRetryManager (sync) and AsyncLLMRetryManager (async):

- RetryConfig dataclass (configuration)
- CircuitBreakerState dataclass (per-backend state)
- RateLimitError / CircuitBreakerError exceptions
- Exponential backoff delay calculation (with optional jitter)
- Retryable-error classification (unified pattern list)
- Rate-limit-error classification
- Circuit breaker state transitions (open/half_open/closed)
- Statistics structure initialization

Subclasses are responsible for the I/O layer (locking, sleep, await).
This avoids duplicating strategy logic across sync/async.

Usage (subclasses inherit, do not instantiate Base directly):
    from scripts.collaboration.llm_retry_base import LLMRetryBase

    class MyRetryManager(LLMRetryBase):
        def retry_with_fallback(self, func, args, kwargs, config, ...): ...
"""

import logging
import random
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class JitterStrategy(Enum):
    """V3.8 #9: Jitter strategies for exponential backoff retry.

    - ``NONE``: No jitter — deterministic exponential backoff.
    - ``EQUAL``: Equal jitter — ``delay/2 + random.uniform(0, delay/2)``.
      Preserves half of the deterministic component while spreading
      the rest, balancing predictability and dispersion.
    - ``FULL``: Full jitter — ``random.uniform(0, delay)``. Maximum
      dispersion; ideal for rate-limit backoff (AWS recommendation).
    - ``DECORRELATED``: Decorrelated jitter —
      ``min(cap, random.uniform(base, last_delay * 3))``. Each delay
      is derived from the previous one, preventing synchronized
      retry storms across clients (AWS "Exponential Backoff With
      Decorrelated Jitter").
    """

    NONE = "none"
    EQUAL = "equal"
    FULL = "full"
    DECORRELATED = "decorrelated"


@dataclass
class RetryConfig:
    """重试配置 (shared by sync and async)"""

    max_retries: int = 3
    initial_delay: float = 1.0  # 初始延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数基数
    jitter: bool = True  # 添加随机抖动
    # V3.8: Jitter mode selection (legacy string-based API, kept for
    # backward compatibility with existing callers).
    #   "none"          — no jitter (deterministic exponential backoff)
    #   "full"          — full jitter: random.uniform(0, delay)
    #   "decorrelated"  — current behavior: delay * random.uniform(0.5, 1.5)
    jitter_mode: str = "decorrelated"
    # V3.8 #9: New enum-based jitter strategy selection.
    # When set (non-None), takes precedence over the legacy ``jitter_mode``
    # string. Defaults to ``None`` for backward compatibility — existing
    # callers continue to use the legacy ``jitter_mode`` string (default
    # "decorrelated", i.e. 50-150% proportional jitter). New callers can
    # opt in to the AWS-recommended full jitter by setting this to
    # ``JitterStrategy.FULL``.
    jitter_strategy: JitterStrategy | None = None
    # V3.8 #9: Last delay used (for decorrelated jitter state tracking).
    # Callers performing multi-attempt retries should update this field
    # after each attempt so the next decorrelated-jitter calculation can
    # use it. When None, the decorrelated strategy falls back to using
    # ``initial_delay`` as the previous delay.
    last_delay: float | None = field(default=None, repr=False)


@dataclass
class CircuitBreakerState:
    """熔断器状态 (shared by sync and async)"""

    failure_count: int = 0
    last_failure_time: datetime | None = None
    state: str = "closed"  # closed, open, half_open
    failure_threshold: int = 5
    timeout_seconds: int = 60


class RateLimitError(Exception):
    """速率限制错误 (shared by sync and async)"""

    pass


class CircuitBreakerError(Exception):
    """熔断器打开错误 (shared by sync and async)"""

    pass


class LLMRetryBase:
    """
    Base class for LLM retry managers — shared strategy layer.

    Provides:
    - Exponential backoff delay calculation (with optional jitter)
    - Retryable-error classification (unified pattern list)
    - Rate-limit-error classification
    - Circuit breaker state management (non-locking transitions)
    - Statistics structure initialization

    Subclasses must implement I/O-bound methods (retry_with_fallback,
    _try_fallback) using their preferred concurrency primitive
    (threading or asyncio.Lock) and sleep mechanism (time.sleep or
    asyncio.sleep).
    """

    # Unified retryable error patterns (superset of sync and async originals).
    # Sync originally had: timeout, connection, network, 503, 502, 500, 429
    # Async originally had: timeout, connection, network, unavailable, 503, 502, 504, 429
    # Unified: all of the above to avoid behavior divergence.
    RETRYABLE_PATTERNS = [
        "timeout",
        "connection",
        "network",
        "unavailable",
        "503",  # Service Unavailable
        "502",  # Bad Gateway
        "504",  # Gateway Timeout
        "500",  # Internal Server Error
        "429",  # Rate Limit (needs longer delay)
    ]

    RATE_LIMIT_PATTERNS = ["429", "rate limit"]

    def __init__(self):
        """Initialize base retry manager with shared stats structure."""
        # Statistics structure shared by both implementations.
        # Subclasses may extend with additional counters.
        self.circuit_breakers: dict[str, CircuitBreakerState] = {}
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "fallbacks": 0,
        }

    def calculate_delay(
        self,
        attempt: int,
        config: RetryConfig,
        last_delay: float | None = None,
    ) -> float:
        """Calculate retry delay using exponential backoff with optional jitter.

        V3.8 #9 supports four jitter strategies:

        - **NONE**: deterministic exponential backoff, no jitter.
        - **EQUAL**: equal jitter — ``delay/2 + random.uniform(0, delay/2)``.
          Half the delay is preserved deterministically; the other half
          is randomized to spread retries.
        - **FULL**: full jitter — ``random.uniform(0, delay)``. Maximum
          dispersion; the AWS-recommended default for rate-limit backoff.
        - **DECORRELATED**: decorrelated jitter —
          ``min(cap, random.uniform(base, last_delay * 3))``. The next
          delay is derived from the previous one (stateful), preventing
          synchronized retry storms.

        Strategy selection precedence (V3.8 #9):

        1. If ``config.jitter_strategy`` is set (non-None), use it. This
           is the new enum-based API and takes precedence.
        2. Otherwise, fall back to the legacy ``config.jitter_mode`` string
           for backward compatibility ("none" / "full" / "decorrelated").
           The legacy "decorrelated" string maps to the original 50-150%
           proportional jitter (NOT the standard AWS decorrelated formula).

        When ``config.jitter`` is False, jitter is disabled regardless of
        ``jitter_strategy`` / ``jitter_mode`` (preserves the original
        opt-out flag).

        Args:
            attempt: Zero-based attempt number.
            config: Retry configuration.
            last_delay: Previous delay (for decorrelated jitter). When
                None, falls back to ``config.last_delay`` and then to
                ``config.initial_delay``.

        Returns:
            Delay in seconds (capped at config.max_delay, with optional jitter)
        """
        delay = min(
            config.initial_delay * (config.exponential_base**attempt),
            config.max_delay,
        )

        if not config.jitter:
            return delay

        # V3.8 #9: enum-based strategy takes precedence over legacy string.
        if config.jitter_strategy is not None:
            return self._apply_jitter_strategy(delay, config, last_delay)

        # Legacy string-based fallback (backward compatibility).
        mode = (config.jitter_mode or "decorrelated").lower()
        if mode == "none":
            return delay
        if mode == "full":
            # Full jitter: random value between 0 and delay
            return random.uniform(0, delay)
        # Default: legacy "decorrelated" (50-150% of delay) — backward compat
        return delay * (0.5 + random.random())

    def _apply_jitter_strategy(
        self,
        delay: float,
        config: RetryConfig,
        last_delay: float | None,
    ) -> float:
        """Apply the V3.8 #9 ``JitterStrategy`` enum to a base delay.

        Args:
            delay: Base exponential backoff delay (already capped at
                ``config.max_delay``).
            config: Retry configuration (provides ``jitter_strategy``,
                ``max_delay``, ``initial_delay``, ``last_delay``).
            last_delay: Caller-supplied previous delay. When None, falls
                back to ``config.last_delay`` then ``config.initial_delay``.

        Returns:
            Jittered delay in seconds, capped at ``config.max_delay``.
        """
        strategy = config.jitter_strategy
        if strategy == JitterStrategy.NONE:
            return delay
        if strategy == JitterStrategy.EQUAL:
            # Equal jitter: half deterministic + half randomized.
            # Range: [delay/2, delay]
            return delay / 2 + random.uniform(0, delay / 2)
        if strategy == JitterStrategy.FULL:
            # Full jitter: random value between 0 and delay.
            # Range: [0, delay]
            return random.uniform(0, delay)
        if strategy == JitterStrategy.DECORRELATED:
            # Decorrelated jitter (AWS formula):
            #   delay = min(cap, random.uniform(base, last_delay * 3))
            # ``base`` is config.initial_delay; ``last_delay`` is the
            # delay used in the previous attempt.
            prev = last_delay if last_delay is not None else config.last_delay
            prev = prev if prev is not None else config.initial_delay
            upper = prev * 3
            # Ensure upper >= base so random.uniform(base, upper) is valid.
            if upper < config.initial_delay:
                upper = config.initial_delay
            return min(config.max_delay, random.uniform(config.initial_delay, upper))
        # Unknown strategy: fall back to deterministic delay.
        return delay

    def is_retryable_error(self, error: Exception) -> bool:
        """
        Check if an error is retryable based on its message.

        Uses the unified RETRYABLE_PATTERNS list (superset of the original
        sync and async pattern lists).

        Args:
            error: The exception to classify

        Returns:
            True if the error is retryable, False otherwise
        """
        error_msg = str(error).lower()
        return any(pattern in error_msg for pattern in self.RETRYABLE_PATTERNS)

    def is_rate_limit_error(self, error: Exception) -> bool:
        """
        Check if an error is rate-limit related.

        Args:
            error: The exception to classify

        Returns:
            True if the error indicates rate limiting
        """
        error_msg = str(error).lower()
        return any(pattern in error_msg for pattern in self.RATE_LIMIT_PATTERNS)

    def get_circuit_breaker(self, backend: str) -> CircuitBreakerState:
        """
        Get or create a circuit breaker for a backend.

        Non-locking; subclasses that need thread/async safety should
        wrap this call in their preferred lock.

        Args:
            backend: Backend name

        Returns:
            CircuitBreakerState for the backend (created if missing)
        """
        if backend not in self.circuit_breakers:
            self.circuit_breakers[backend] = CircuitBreakerState()
        return self.circuit_breakers[backend]

    def check_circuit_breaker_state(self, backend: str) -> None:
        """
        Check circuit breaker state and raise if open.

        Pure state-transition logic (non-locking). Subclasses should wrap
        this in their preferred lock and handle the CircuitBreakerError.

        Transitions open → half_open if timeout has elapsed.

        Args:
            backend: Backend name to check

        Raises:
            CircuitBreakerError: If circuit breaker is open and timeout
                has not elapsed
        """
        cb = self.get_circuit_breaker(backend)

        if cb.state == "open" and cb.last_failure_time:
            elapsed = (datetime.now() - cb.last_failure_time).total_seconds()
            if elapsed > cb.timeout_seconds:
                cb.state = "half_open"
                logger.info("Circuit breaker for %s entering half-open state", backend)
            else:
                raise CircuitBreakerError(
                    f"Circuit breaker open for {backend}. "
                    f"Retry after {cb.timeout_seconds - elapsed:.0f}s"
                )

    def record_success(self, backend: str) -> None:
        """
        Record a successful call — closes half-open circuit breakers.

        Non-locking state transition; subclasses should wrap in their lock
        and increment their own success counter.

        Args:
            backend: Backend name that succeeded
        """
        cb = self.get_circuit_breaker(backend)
        if cb.state == "half_open":
            cb.state = "closed"
            cb.failure_count = 0
            logger.info("Circuit breaker for %s closed", backend)

    def record_failure(self, backend: str) -> bool:
        """
        Record a failed call — may open the circuit breaker.

        Non-locking state transition; subclasses should wrap in their lock
        and increment their own failure counter.

        Args:
            backend: Backend name that failed

        Returns:
            True if the circuit breaker was opened (or already open),
            False otherwise
        """
        cb = self.get_circuit_breaker(backend)
        cb.failure_count += 1
        cb.last_failure_time = datetime.now()

        if cb.failure_count >= cb.failure_threshold and cb.state != "open":
            cb.state = "open"
            logger.warning(
                "Circuit breaker opened for %s after %s failures",
                backend,
                cb.failure_count,
            )
            return True
        return False

    def get_enhanced_delay(
        self,
        attempt: int,
        config: RetryConfig,
        error: Exception,
        last_delay: float | None = None,
    ) -> float:
        """Calculate delay with rate-limit awareness.

        Rate-limit errors (429) get 3x longer delay.

        Args:
            attempt: Zero-based attempt number
            config: Retry configuration
            error: The exception that triggered the retry
            last_delay: Previous delay (for decorrelated jitter). When
                None, ``calculate_delay`` falls back to ``config.last_delay``.

        Returns:
            Delay in seconds
        """
        delay = self.calculate_delay(attempt, config, last_delay)

        if self.is_rate_limit_error(error):
            delay *= 3
            logger.warning("Rate limit detected, waiting %.1fs", delay)

        return delay

    def build_fallback_kwargs(
        self,
        kwargs: dict,
        backend: str,
        always_set: bool = False,
    ) -> dict:
        """
        Build kwargs for a fallback backend call.

        Args:
            kwargs: Original kwargs dict
            backend: Fallback backend name
            always_set: If True, always set "backend" key (sync behavior);
                if False, only set if "backend" already exists (async behavior)

        Returns:
            New kwargs dict with updated backend
        """
        fallback_kwargs = kwargs.copy()
        if always_set or "backend" in fallback_kwargs:
            fallback_kwargs["backend"] = backend
        return fallback_kwargs

    def get_stats_base(self) -> dict[str, Any]:
        """
        Return base statistics dictionary.

        Subclasses can extend this with additional fields
        (e.g. circuit_breaker_trips, success_rate).

        Returns:
            Copy of the stats dictionary
        """
        return self.stats.copy()
