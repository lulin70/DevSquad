#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for LLM Retry and Fallback Mechanism

Tests cover:
- Retry configuration
- Exponential backoff calculation
- Circuit breaker behavior
- Multi-backend fallback
- Error classification
- Statistics tracking
"""

import pytest
import time
from unittest.mock import Mock, patch
from .llm_retry import (
    LLMRetryManager,
    RetryConfig,
    CircuitBreakerState,
    RateLimitError,
    CircuitBreakerError,
    get_retry_manager,
    retry_with_fallback
)


class TestRetryConfig:
    """Test retry configuration"""
    
    def test_default_config(self):
        """Test default configuration values"""
        config = RetryConfig()
        assert config.max_retries == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_custom_config(self):
        """Test custom configuration"""
        config = RetryConfig(
            max_retries=5,
            initial_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )
        assert config.max_retries == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False


class TestCircuitBreakerState:
    """Test circuit breaker state"""
    
    def test_initial_state(self):
        """Test initial circuit breaker state"""
        cb = CircuitBreakerState()
        assert cb.failure_count == 0
        assert cb.last_failure_time is None
        assert cb.state == "closed"
        assert cb.failure_threshold == 5
        assert cb.timeout_seconds == 60


class TestLLMRetryManager:
    """Test LLM retry manager"""
    
    def setup_method(self):
        """Setup test fixtures"""
        self.manager = LLMRetryManager()
    
    def test_initialization(self):
        """Test manager initialization"""
        assert len(self.manager.circuit_breakers) == 0
        assert self.manager.stats["total_calls"] == 0
        assert self.manager.stats["successful_calls"] == 0
        assert self.manager.stats["failed_calls"] == 0
    
    def test_calculate_delay(self):
        """Test exponential backoff delay calculation"""
        config = RetryConfig(
            initial_delay=1.0,
            exponential_base=2.0,
            max_delay=60.0,
            jitter=False
        )
        
        # Test exponential growth
        delay0 = self.manager._calculate_delay(0, config)
        delay1 = self.manager._calculate_delay(1, config)
        delay2 = self.manager._calculate_delay(2, config)
        
        assert delay0 == 1.0  # 1.0 * 2^0
        assert delay1 == 2.0  # 1.0 * 2^1
        assert delay2 == 4.0  # 1.0 * 2^2
        
        # Test max delay cap
        delay10 = self.manager._calculate_delay(10, config)
        assert delay10 == 60.0  # Capped at max_delay
    
    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter"""
        config = RetryConfig(initial_delay=1.0, jitter=True)
        
        delays = [self.manager._calculate_delay(0, config) for _ in range(10)]
        
        # All delays should be between 0.5 and 1.5 (50-150% of base)
        assert all(0.5 <= d <= 1.5 for d in delays)
        
        # Delays should vary (not all the same)
        assert len(set(delays)) > 1
    
    def test_is_retryable_error(self):
        """Test retryable error classification"""
        # Retryable errors
        assert self.manager._is_retryable_error(Exception("Connection timeout"))
        assert self.manager._is_retryable_error(Exception("Network error"))
        assert self.manager._is_retryable_error(Exception("503 Service Unavailable"))
        assert self.manager._is_retryable_error(Exception("502 Bad Gateway"))
        
        # Non-retryable errors
        assert not self.manager._is_retryable_error(Exception("400 Bad Request"))
        assert not self.manager._is_retryable_error(Exception("Invalid input"))
    
    def test_is_rate_limit_error(self):
        """Test rate limit error detection"""
        assert self.manager._is_rate_limit_error(Exception("429 Too Many Requests"))
        assert self.manager._is_rate_limit_error(Exception("Rate limit exceeded"))
        assert not self.manager._is_rate_limit_error(Exception("500 Internal Error"))
    
    def test_circuit_breaker_closed_to_open(self):
        """Test circuit breaker opening after failures"""
        backend = "test_backend"
        
        # Record failures until threshold
        for i in range(5):
            self.manager._record_failure(backend, Exception("Test error"))
        
        cb = self.manager._get_circuit_breaker(backend)
        assert cb.state == "open"
        assert cb.failure_count == 5
    
    def test_circuit_breaker_blocks_requests(self):
        """Test circuit breaker blocks requests when open"""
        backend = "test_backend"
        
        # Open the circuit breaker
        for i in range(5):
            self.manager._record_failure(backend, Exception("Test error"))
        
        # Should raise CircuitBreakerError
        with pytest.raises(CircuitBreakerError):
            self.manager._check_circuit_breaker(backend)
    
    def test_circuit_breaker_half_open(self):
        """Test circuit breaker enters half-open state after timeout"""
        backend = "test_backend"
        
        # Open the circuit breaker
        for i in range(5):
            self.manager._record_failure(backend, Exception("Test error"))
        
        cb = self.manager._get_circuit_breaker(backend)
        assert cb.state == "open"
        
        # Simulate timeout by backdating last_failure_time
        from datetime import datetime, timedelta
        cb.last_failure_time = datetime.now() - timedelta(seconds=61)
        
        # Should enter half-open state
        self.manager._check_circuit_breaker(backend)
        assert cb.state == "half_open"
    
    def test_circuit_breaker_recovery(self):
        """Test circuit breaker closes after successful call in half-open state"""
        backend = "test_backend"
        
        # Set to half-open state
        cb = self.manager._get_circuit_breaker(backend)
        cb.state = "half_open"
        cb.failure_count = 3
        
        # Record success
        self.manager._record_success(backend)
        
        assert cb.state == "closed"
        assert cb.failure_count == 0
    
    def test_successful_retry(self):
        """Test successful function execution"""
        config = RetryConfig(max_retries=3)
        
        mock_func = Mock(return_value="success")
        
        result = self.manager.retry_with_fallback(
            mock_func,
            args=(),
            kwargs={},
            config=config,
            fallback_backends=None,
            current_backend="test"
        )
        
        assert result == "success"
        assert mock_func.call_count == 1
        assert self.manager.stats["successful_calls"] == 1
    
    def test_retry_on_failure(self):
        """Test retry mechanism on transient failures"""
        config = RetryConfig(max_retries=3, initial_delay=0.01)
        
        # Fail twice, then succeed
        mock_func = Mock(side_effect=[
            Exception("503 Service Unavailable"),
            Exception("Connection timeout"),
            "success"
        ])
        
        result = self.manager.retry_with_fallback(
            mock_func,
            args=(),
            kwargs={},
            config=config,
            fallback_backends=None,
            current_backend="test"
        )
        
        assert result == "success"
        assert mock_func.call_count == 3
        assert self.manager.stats["retries"] == 2
    
    def test_fallback_on_failure(self):
        """Test fallback to alternative backend"""
        config = RetryConfig(max_retries=2, initial_delay=0.01)
        
        call_count = {"count": 0}
        
        def mock_func(*args, **kwargs):
            call_count["count"] += 1
            backend = kwargs.get("backend", "unknown")
            if backend == "primary":
                raise Exception("503 Service Unavailable")
            return f"success from {backend}"
        
        result = self.manager.retry_with_fallback(
            mock_func,
            args=(),
            kwargs={"backend": "primary"},
            config=config,
            fallback_backends=["secondary", "tertiary"],
            current_backend="primary"
        )
        
        assert "secondary" in result
        assert self.manager.stats["fallbacks"] >= 1
    
    def test_all_backends_fail(self):
        """Test behavior when all backends fail"""
        config = RetryConfig(max_retries=1, initial_delay=0.01)
        
        mock_func = Mock(side_effect=Exception("All backends down"))
        
        with pytest.raises(Exception, match="All backends down"):
            self.manager.retry_with_fallback(
                mock_func,
                args=(),
                kwargs={"backend": "primary"},
                config=config,
                fallback_backends=["secondary"],
                current_backend="primary"
            )
    
    def test_statistics_tracking(self):
        """Test statistics are correctly tracked"""
        config = RetryConfig(max_retries=2, initial_delay=0.01)
        
        # Successful call
        mock_func1 = Mock(return_value="success")
        self.manager.retry_with_fallback(
            mock_func1, (), {}, config, None, "backend1"
        )
        
        # Failed call with retry
        mock_func2 = Mock(side_effect=[
            Exception("503 Error"),
            "success"
        ])
        self.manager.retry_with_fallback(
            mock_func2, (), {}, config, None, "backend2"
        )
        
        stats = self.manager.get_stats()
        assert stats["total_calls"] == 2
        assert stats["successful_calls"] == 2
        assert stats["retries"] == 1
    
    def test_reset_circuit_breaker(self):
        """Test manual circuit breaker reset"""
        backend = "test_backend"
        
        # Open circuit breaker
        for i in range(5):
            self.manager._record_failure(backend, Exception("Error"))
        
        cb = self.manager._get_circuit_breaker(backend)
        assert cb.state == "open"
        
        # Reset
        self.manager.reset_circuit_breaker(backend)
        
        cb = self.manager._get_circuit_breaker(backend)
        assert cb.state == "closed"
        assert cb.failure_count == 0


class TestRetryDecorator:
    """Test retry decorator"""
    
    def test_decorator_basic(self):
        """Test basic decorator usage"""
        call_count = {"count": 0}
        
        @retry_with_fallback(max_retries=3, initial_delay=0.01)
        def test_func():
            call_count["count"] += 1
            if call_count["count"] < 2:
                raise Exception("503 Error")
            return "success"
        
        result = test_func()
        assert result == "success"
        assert call_count["count"] == 2
    
    def test_decorator_with_fallback(self):
        """Test decorator with fallback backends"""
        @retry_with_fallback(
            max_retries=2,
            initial_delay=0.01,
            fallback_backends=["openai", "anthropic"]
        )
        def test_func(prompt: str, backend: str = "primary"):
            if backend == "primary":
                raise Exception("Primary down")
            return f"{backend}: {prompt}"
        
        result = test_func("test prompt")
        assert "openai" in result or "anthropic" in result


class TestGlobalManager:
    """Test global manager singleton"""
    
    def test_singleton(self):
        """Test global manager is singleton"""
        manager1 = get_retry_manager()
        manager2 = get_retry_manager()
        assert manager1 is manager2
    
    def test_shared_state(self):
        """Test global manager shares state"""
        manager = get_retry_manager()
        
        # Record some stats
        manager.stats["total_calls"] = 10
        
        # Get manager again
        manager2 = get_retry_manager()
        assert manager2.stats["total_calls"] == 10


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
