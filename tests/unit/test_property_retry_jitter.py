"""Property-based tests for LLM retry jitter delay invariants.

Uses Hypothesis to verify that ``LLMRetryBase.calculate_delay()`` and
``_apply_jitter_strategy()`` always produce valid delays:

1. Delay is always non-negative.
2. Delay is always capped by ``config.max_delay``.
3. ``JitterStrategy.NONE`` always returns the deterministic exponential
   backoff value (no randomness).
4. ``JitterStrategy.FULL`` always returns a value in ``[0, delay]``.
5. ``JitterStrategy.EQUAL`` always returns a value in ``[delay/2, delay]``.
6. ``JitterStrategy.DECORRELATED`` always returns a value in
   ``[base, min(cap, last_delay * 3)]``.
7. When ``jitter=False``, all strategies return the deterministic value.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from scripts.collaboration.llm_retry_base import (
    JitterStrategy,
    LLMRetryBase,
    RetryConfig,
)

pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Input strategies
# ---------------------------------------------------------------------------

# Reasonable ranges for retry configuration.
_initial_delay = st.floats(min_value=0.1, max_value=10.0, allow_nan=False, allow_infinity=False)
_max_delay = st.floats(min_value=1.0, max_value=300.0, allow_nan=False, allow_infinity=False)
_exponential_base = st.floats(min_value=1.5, max_value=3.0, allow_nan=False, allow_infinity=False)
_attempts = st.integers(min_value=0, max_value=10)
_last_delays = st.floats(min_value=0.1, max_value=300.0, allow_nan=False, allow_infinity=False)
_strategies = st.sampled_from(list(JitterStrategy))


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
    strategy=_strategies,
)
@settings(max_examples=100, deadline=None)
def test_calculate_delay_always_non_negative(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    strategy: JitterStrategy,
) -> None:
    """calculate_delay() must always return a non-negative value."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=True,
        jitter_strategy=strategy,
    )
    manager = LLMRetryBase()
    delay = manager.calculate_delay(attempt, config)
    assert delay >= 0, f"Negative delay: {delay} for attempt={attempt} strategy={strategy}"


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
    strategy=_strategies,
)
@settings(max_examples=100, deadline=None)
def test_calculate_delay_always_capped_by_max_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    strategy: JitterStrategy,
) -> None:
    """calculate_delay() must never exceed config.max_delay."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=True,
        jitter_strategy=strategy,
    )
    manager = LLMRetryBase()
    delay = manager.calculate_delay(attempt, config)
    assert delay <= max_delay + 1e-9, (
        f"Delay {delay} exceeds max_delay {max_delay} (attempt={attempt}, strategy={strategy})"
    )


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
)
@settings(max_examples=50, deadline=None)
def test_none_strategy_is_deterministic(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
) -> None:
    """JitterStrategy.NONE must produce deterministic exponential backoff."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=True,
        jitter_strategy=JitterStrategy.NONE,
    )
    manager = LLMRetryBase()
    expected = min(
        initial_delay * (exponential_base**attempt),
        max_delay,
    )
    delay1 = manager.calculate_delay(attempt, config)
    delay2 = manager.calculate_delay(attempt, config)
    assert delay1 == expected, f"NONE strategy mismatch: {delay1} != {expected}"
    assert delay1 == delay2, f"NONE strategy not deterministic: {delay1} != {delay2}"


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
)
@settings(max_examples=50, deadline=None)
def test_full_strategy_within_zero_to_delay(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
) -> None:
    """JitterStrategy.FULL must produce delay in [0, deterministic_delay]."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=True,
        jitter_strategy=JitterStrategy.FULL,
    )
    manager = LLMRetryBase()
    deterministic = min(
        initial_delay * (exponential_base**attempt),
        max_delay,
    )
    # Sample several times to confirm bounds
    for _ in range(20):
        delay = manager.calculate_delay(attempt, config)
        assert 0 <= delay <= deterministic + 1e-9, (
            f"FULL delay {delay} out of [0, {deterministic}]"
        )


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
)
@settings(max_examples=50, deadline=None)
def test_equal_strategy_within_half_to_full(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
) -> None:
    """JitterStrategy.EQUAL must produce delay in [delay/2, delay]."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=True,
        jitter_strategy=JitterStrategy.EQUAL,
    )
    manager = LLMRetryBase()
    deterministic = min(
        initial_delay * (exponential_base**attempt),
        max_delay,
    )
    # Sample several times to confirm bounds
    for _ in range(20):
        delay = manager.calculate_delay(attempt, config)
        lower = deterministic / 2.0 - 1e-9
        upper = deterministic + 1e-9
        assert lower <= delay <= upper, (
            f"EQUAL delay {delay} out of [{lower}, {upper}] (deterministic={deterministic})"
        )


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
    last_delay=_last_delays,
)
@settings(max_examples=50, deadline=None)
def test_decorrelated_strategy_within_bounds(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    last_delay: float,
) -> None:
    """JitterStrategy.DECORRELATED must produce delay within valid bounds.

    Decorrelated formula: min(cap, random.uniform(base, last_delay * 3))
    So delay must be in [initial_delay, max_delay] (assuming last_delay * 3
    does not exceed cap; if it does, we get min(cap, ...) = cap = max_delay).
    """
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=True,
        jitter_strategy=JitterStrategy.DECORRELATED,
        last_delay=last_delay,
    )
    manager = LLMRetryBase()
    # Sample several times to confirm bounds
    for _ in range(20):
        delay = manager.calculate_delay(attempt, config, last_delay=last_delay)
        lower_bound = min(initial_delay, max_delay)
        upper_bound = max_delay
        assert lower_bound - 1e-9 <= delay <= upper_bound + 1e-9, (
            f"DECORRELATED delay {delay} out of [{lower_bound}, {upper_bound}] "
            f"(initial_delay={initial_delay}, max_delay={max_delay}, last_delay={last_delay})"
        )


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
    strategy=_strategies,
)
@settings(max_examples=50, deadline=None)
def test_jitter_disabled_returns_deterministic(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
    strategy: JitterStrategy,
) -> None:
    """When jitter=False, calculate_delay() must return deterministic value."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=False,
        jitter_strategy=strategy,
    )
    manager = LLMRetryBase()
    expected = min(
        initial_delay * (exponential_base**attempt),
        max_delay,
    )
    delay1 = manager.calculate_delay(attempt, config)
    delay2 = manager.calculate_delay(attempt, config)
    assert delay1 == expected, (
        f"jitter=False returned {delay1}, expected {expected} (strategy={strategy})"
    )
    assert delay1 == delay2, f"jitter=False not deterministic: {delay1} != {delay2}"


@given(
    attempt=_attempts,
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
)
@settings(max_examples=30, deadline=None)
def test_attempt_zero_returns_initial_delay_when_no_jitter(
    attempt: int,
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
) -> None:
    """For attempt=0, jitter=False, delay must equal min(initial_delay, max_delay)."""
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=False,
    )
    manager = LLMRetryBase()
    delay = manager.calculate_delay(0, config)
    expected = min(initial_delay, max_delay)
    assert delay == expected, f"attempt=0 delay {delay} != expected {expected}"


@given(
    initial_delay=_initial_delay,
    max_delay=_max_delay,
    exponential_base=_exponential_base,
)
@settings(max_examples=30, deadline=None)
def test_delay_monotonically_increases_without_jitter(
    initial_delay: float,
    max_delay: float,
    exponential_base: float,
) -> None:
    """Without jitter, delay must be monotonically non-decreasing with attempt."""
    # Ensure max_delay is large enough to see the exponential growth
    config = RetryConfig(
        initial_delay=initial_delay,
        max_delay=max(initial_delay * (exponential_base**5) + 1, max_delay),
        exponential_base=exponential_base,
        jitter=False,
    )
    manager = LLMRetryBase()
    prev_delay = -1.0
    for attempt in range(6):
        delay = manager.calculate_delay(attempt, config)
        assert delay >= prev_delay - 1e-9, (
            f"Delay decreased at attempt {attempt}: {delay} < {prev_delay}"
        )
        prev_delay = delay
