#!/usr/bin/env python3
"""
LLM Retry and Fallback Mechanism

Provides robust error handling for LLM API calls:
- Exponential backoff retry
- Multiple backend fallback
- Circuit breaker pattern
- Rate limiting protection

Usage:
    from scripts.collaboration.llm_retry import retry_with_fallback

    @retry_with_fallback(
        max_retries=3,
        fallback_backends=["openai", "anthropic", "zhipu"]
    )
    def call_llm(prompt: str, backend: str, model: str):
        # Your LLM API call
        return response
"""

import logging
import time
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

# Re-export for backward compatibility — existing imports like
# `from scripts.collaboration.llm_retry import RetryConfig` continue to work.
__all__ = [
    "CircuitBreakerError",
    "CircuitBreakerState",
    "JitterStrategy",
    "LLMRetryManager",
    "RateLimitError",
    "RetryConfig",
    "get_retry_manager",
    "retry_with_fallback",
]


class LLMRetryManager(LLMRetryBase):
    """
    LLM 重试管理器

    Features:
    - 指数退避重试
    - 多后端故障转移
    - 熔断器保护
    - 速率限制检测

    Inherits shared retry/circuit-breaker strategy (delay calculation,
    error classification, state transitions) from LLMRetryBase.
    Only the I/O layer (time.sleep, synchronous calls) is implemented here.
    """

    def __init__(self) -> None:
        # Initialize shared strategy from base class (sets stats, circuit_breakers)
        super().__init__()
        # Extend base stats with sync-specific "circuit_breaks" counter
        self.stats["circuit_breaks"] = 0

    def _check_circuit_breaker(self, backend: str) -> None:
        """检查熔断器状态 (sync wrapper around base state-transition logic)."""
        try:
            self.check_circuit_breaker_state(backend)
        except CircuitBreakerError:
            self.stats["circuit_breaks"] += 1
            raise

    def _record_success(self, backend: str) -> None:
        """记录成功调用"""
        self.record_success(backend)
        self.stats["successful_calls"] += 1

    def _record_failure(self, backend: str, _error: Exception) -> None:
        """记录失败调用"""
        self.record_failure(backend)
        self.stats["failed_calls"] += 1

    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算重试延迟（指数退避）— delegates to base class."""
        return self.calculate_delay(attempt, config)

    def _is_retryable_error(self, error: Exception) -> bool:
        """判断错误是否可重试 — delegates to base class."""
        return self.is_retryable_error(error)

    def _is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否为速率限制错误 — delegates to base class."""
        return self.is_rate_limit_error(error)

    def _get_circuit_breaker(self, backend: str) -> CircuitBreakerState:
        """获取或创建熔断器 — delegates to base class."""
        return self.get_circuit_breaker(backend)

    def retry_with_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        config: RetryConfig,
        fallback_backends: list[str] | None = None,
        current_backend: str | None = None,
    ) -> Any:
        """
        执行带重试和故障转移的函数调用

        Args:
            func: 要调用的函数
            args: 位置参数
            kwargs: 关键字参数
            config: 重试配置
            fallback_backends: 备用后端列表
            current_backend: 当前使用的后端

        Returns:
            函数执行结果

        Raises:
            最后一次尝试的异常
        """
        self.stats["total_calls"] += 1
        last_error = None

        # 如果指定了当前后端，检查熔断器
        if current_backend:
            try:
                self._check_circuit_breaker(current_backend)
            except CircuitBreakerError as e:
                logger.warning(str(e))
                # 熔断器打开，直接尝试故障转移
                if fallback_backends:
                    return self._try_fallback(func, args, kwargs, config, fallback_backends, current_backend)
                raise

        # 主后端重试
        for attempt in range(config.max_retries):
            try:
                result = func(*args, **kwargs)
                if current_backend:
                    self._record_success(current_backend)
                return result

            except Exception as e:
                last_error = e

                if current_backend:
                    self._record_failure(current_backend, e)

                # 检查是否可重试
                if not self._is_retryable_error(e):
                    logger.error("Non-retryable error: %s", e)
                    break

                # 最后一次尝试不需要延迟
                if attempt < config.max_retries - 1:
                    delay = self.get_enhanced_delay(attempt, config, e)

                    logger.info("Retry attempt %s/%s after %.1fs delay", attempt + 1, config.max_retries, delay)
                    time.sleep(delay)
                    self.stats["retries"] += 1

        # 主后端失败，尝试故障转移
        if fallback_backends:
            try:
                return self._try_fallback(func, args, kwargs, config, fallback_backends, current_backend)
            except Exception as fallback_error:
                logger.error("All fallback attempts failed: %s", fallback_error)
                last_error = fallback_error

        # 所有尝试都失败
        if last_error is not None:
            raise last_error
        raise RuntimeError("All retry attempts failed with no specific error")

    def _try_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        _config: RetryConfig,
        fallback_backends: list[str],
        exclude_backend: str | None,
    ) -> Any:
        """尝试故障转移到备用后端"""
        for backend in fallback_backends:
            if backend == exclude_backend:
                continue

            try:
                self._check_circuit_breaker(backend)
            except CircuitBreakerError:
                logger.warning("Skipping %s (circuit breaker open)", backend)
                continue

            logger.info("Attempting fallback to %s", backend)
            self.stats["fallbacks"] += 1

            # 更新 kwargs 中的 backend 参数 (sync always sets backend)
            fallback_kwargs = self.build_fallback_kwargs(kwargs, backend, always_set=True)

            try:
                result = func(*args, **fallback_kwargs)
                self._record_success(backend)
                logger.info("Fallback to %s successful", backend)
                return result
            except Exception as e:
                self._record_failure(backend, e)
                logger.warning("Fallback to %s failed: %s", backend, e)
                continue

        raise Exception("All fallback backends failed")

    def get_stats(self) -> dict[str, Any]:
        """获取统计信息"""
        total = self.stats["total_calls"]
        success_rate = self.stats["successful_calls"] / total * 100 if total > 0 else 0

        return {
            **self.stats,
            "success_rate": f"{success_rate:.1f}%",
            "circuit_breakers": {
                backend: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "last_failure": (cb.last_failure_time.isoformat() if cb.last_failure_time else None),
                }
                for backend, cb in self.circuit_breakers.items()
            },
        }

    def reset_circuit_breaker(self, backend: str) -> None:
        """手动重置熔断器"""
        if backend in self.circuit_breakers:
            self.circuit_breakers[backend] = CircuitBreakerState()
            logger.info("Circuit breaker for %s manually reset", backend)


# 全局实例
_retry_manager: LLMRetryManager | None = None


def get_retry_manager() -> LLMRetryManager:
    """获取全局重试管理器实例"""
    global _retry_manager
    if _retry_manager is None:
        _retry_manager = LLMRetryManager()
    return _retry_manager


def retry_with_fallback(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    fallback_backends: list[str] | None = None,
    backend_param: str = "backend",
) -> Callable:
    """
    装饰器：为 LLM 调用添加重试和故障转移

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟（秒）
        max_delay: 最大延迟（秒）
        fallback_backends: 备用后端列表
        backend_param: 后端参数名称

    Example:
        @retry_with_fallback(
            max_retries=3,
            fallback_backends=["openai", "anthropic", "zhipu"]
        )
        def call_llm(prompt: str, backend: str = "openai"):
            # Your API call
            return response
    """

    def decorator(func: Callable) -> Callable:
        """Decorate a sync function to add retry-with-fallback behavior.

        Args:
            func: Callable to wrap.

        Returns:
            Wrapped callable that retries on failure and falls back across backends.
        """
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            """Invoke the wrapped function with retry and fallback handling."""
            config = RetryConfig(max_retries=max_retries, initial_delay=initial_delay, max_delay=max_delay)

            # 获取当前后端
            current_backend = kwargs.get(backend_param)

            manager = get_retry_manager()
            return manager.retry_with_fallback(func, args, kwargs, config, fallback_backends, current_backend)

        return wrapper

    return decorator
