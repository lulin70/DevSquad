#!/usr/bin/env python3
"""Tests for V3.8 #9: Jitter strategies for LLM retry backoff."""

import pytest

from scripts.collaboration.llm_retry_base import (
    JitterStrategy,
    LLMRetryBase,
    RateLimitError,
    RetryConfig,
)


class TestJitterStrategyEnum:
    """Verify JitterStrategy enum values."""

    def test_jitter_strategy_has_four_values(self):
        """Verify: JitterStrategy has NONE, EQUAL, FULL, DECORRELATED."""
        assert JitterStrategy.NONE.value == "none"
        assert JitterStrategy.EQUAL.value == "equal"
        assert JitterStrategy.FULL.value == "full"
        assert JitterStrategy.DECORRELATED.value == "decorrelated"

    def test_jitter_strategy_count(self):
        """Verify: Exactly 4 JitterStrategy values exist."""
        assert len(list(JitterStrategy)) == 4


class TestRetryConfigJitterStrategy:
    """Verify RetryConfig supports jitter_strategy field."""

    def test_default_jitter_strategy_is_none(self):
        """Verify: Default jitter_strategy is None (uses legacy jitter_mode)."""
        config = RetryConfig()
        assert config.jitter_strategy is None

    def test_can_set_full_jitter_strategy(self):
        """Verify: Can set jitter_strategy to FULL."""
        config = RetryConfig(jitter_strategy=JitterStrategy.FULL)
        assert config.jitter_strategy == JitterStrategy.FULL

    def test_can_set_decorrelated_jitter_strategy(self):
        """Verify: Can set jitter_strategy to DECORRELATED."""
        config = RetryConfig(jitter_strategy=JitterStrategy.DECORRELATED)
        assert config.jitter_strategy == JitterStrategy.DECORRELATED


class TestCalculateDelayStrategies:
    """Verify each jitter strategy produces correct delay ranges."""

    def setup_method(self):
        """Set up retry manager for each test."""
        self.manager = LLMRetryBase()

    def test_none_jitter_returns_base_delay(self):
        """Verify: NONE strategy returns exact base delay without jitter."""
        config = RetryConfig(
            initial_delay=2.0,
            exponential_base=2.0,
            jitter=False,
            jitter_strategy=JitterStrategy.NONE,
        )
        delay = self.manager.calculate_delay(0, config)
        assert delay == pytest.approx(2.0)

    def test_equal_jitter_within_range(self):
        """Verify: EQUAL strategy returns delay between base/2 and base."""
        config = RetryConfig(
            initial_delay=4.0,
            exponential_base=2.0,
            jitter=False,
            jitter_strategy=JitterStrategy.EQUAL,
        )
        for _ in range(100):
            delay = self.manager.calculate_delay(0, config)
            assert 2.0 <= delay <= 4.0

    def test_full_jitter_within_range(self):
        """Verify: FULL strategy returns delay between 0 and base."""
        config = RetryConfig(
            initial_delay=4.0,
            exponential_base=2.0,
            jitter=False,
            jitter_strategy=JitterStrategy.FULL,
        )
        for _ in range(100):
            delay = self.manager.calculate_delay(0, config)
            assert 0.0 <= delay <= 4.0

    def test_decorrelated_jitter_within_range(self):
        """Verify: DECORRELATED strategy returns delay between base/2 and base*1.5."""
        config = RetryConfig(
            initial_delay=4.0,
            exponential_base=2.0,
            jitter=False,
            jitter_strategy=JitterStrategy.DECORRELATED,
        )
        for _ in range(100):
            delay = self.manager.calculate_delay(0, config)
            assert 2.0 <= delay <= 6.0

    def test_max_delay_cap_respected(self):
        """Verify: Delay never exceeds max_delay."""
        config = RetryConfig(
            initial_delay=10.0,
            max_delay=5.0,
            exponential_base=2.0,
            jitter=False,
            jitter_strategy=JitterStrategy.FULL,
        )
        for attempt in range(10):
            delay = self.manager.calculate_delay(attempt, config)
            assert delay <= 5.0

    def test_exponential_growth_with_none_jitter(self):
        """Verify: Without jitter, delay grows exponentially."""
        config = RetryConfig(
            initial_delay=1.0,
            max_delay=1000.0,
            exponential_base=2.0,
            jitter=False,
            jitter_strategy=JitterStrategy.NONE,
        )
        assert self.manager.calculate_delay(0, config) == pytest.approx(1.0)
        assert self.manager.calculate_delay(1, config) == pytest.approx(2.0)
        assert self.manager.calculate_delay(2, config) == pytest.approx(4.0)
        assert self.manager.calculate_delay(3, config) == pytest.approx(8.0)


class TestRateLimitMultiplier:
    """Verify rate limit 3x multiplier works with new strategies."""

    def setup_method(self):
        self.manager = LLMRetryBase()

    def test_rate_limit_3x_with_full_jitter(self):
        """Verify: Rate limit error gets 3x delay with FULL jitter."""
        config = RetryConfig(
            initial_delay=2.0,
            max_delay=1000.0,
            jitter=False,
            jitter_strategy=JitterStrategy.FULL,
        )
        error = RateLimitError("429 rate limit exceeded")
        delay = self.manager.get_enhanced_delay(0, config, error)
        # Full jitter: 0 <= base <= 2.0, then *3 → 0 <= delay <= 6.0
        assert 0.0 <= delay <= 6.0

    def test_rate_limit_3x_with_none_jitter(self):
        """Verify: Rate limit error gets 3x delay with NONE jitter."""
        config = RetryConfig(
            initial_delay=2.0,
            max_delay=1000.0,
            jitter=False,
            jitter_strategy=JitterStrategy.NONE,
        )
        error = RateLimitError("429 rate limit exceeded")
        delay = self.manager.get_enhanced_delay(0, config, error)
        assert delay == pytest.approx(6.0)  # 2.0 * 3

    def test_non_rate_limit_error_no_multiplier(self):
        """Verify: Non-rate-limit error does not get 3x multiplier."""
        config = RetryConfig(
            initial_delay=2.0,
            max_delay=1000.0,
            jitter=False,
            jitter_strategy=JitterStrategy.NONE,
        )
        error = ConnectionError("connection timeout")
        delay = self.manager.get_enhanced_delay(0, config, error)
        assert delay == pytest.approx(2.0)  # No multiplier
