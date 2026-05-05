#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

import time
import logging
from typing import Callable, Optional, List, Dict, Any
from functools import wraps
from dataclasses import dataclass
from datetime import datetime, timedelta


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """重试配置"""
    max_retries: int = 3
    initial_delay: float = 1.0  # 初始延迟（秒）
    max_delay: float = 60.0  # 最大延迟（秒）
    exponential_base: float = 2.0  # 指数基数
    jitter: bool = True  # 添加随机抖动


@dataclass
class CircuitBreakerState:
    """熔断器状态"""
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: str = "closed"  # closed, open, half_open
    failure_threshold: int = 5
    timeout_seconds: int = 60


class RateLimitError(Exception):
    """速率限制错误"""
    pass


class CircuitBreakerError(Exception):
    """熔断器打开错误"""
    pass


class LLMRetryManager:
    """
    LLM 重试管理器
    
    Features:
    - 指数退避重试
    - 多后端故障转移
    - 熔断器保护
    - 速率限制检测
    """
    
    def __init__(self):
        self.circuit_breakers: Dict[str, CircuitBreakerState] = {}
        self.stats = {
            "total_calls": 0,
            "successful_calls": 0,
            "failed_calls": 0,
            "retries": 0,
            "fallbacks": 0,
            "circuit_breaks": 0,
        }
    
    def _get_circuit_breaker(self, backend: str) -> CircuitBreakerState:
        """获取或创建熔断器"""
        if backend not in self.circuit_breakers:
            self.circuit_breakers[backend] = CircuitBreakerState()
        return self.circuit_breakers[backend]
    
    def _check_circuit_breaker(self, backend: str):
        """检查熔断器状态"""
        cb = self._get_circuit_breaker(backend)
        
        if cb.state == "open":
            # 检查是否可以尝试恢复
            if cb.last_failure_time:
                elapsed = (datetime.now() - cb.last_failure_time).total_seconds()
                if elapsed > cb.timeout_seconds:
                    cb.state = "half_open"
                    logger.info(f"Circuit breaker for {backend} entering half-open state")
                else:
                    self.stats["circuit_breaks"] += 1
                    raise CircuitBreakerError(
                        f"Circuit breaker open for {backend}. "
                        f"Retry after {cb.timeout_seconds - elapsed:.0f}s"
                    )
    
    def _record_success(self, backend: str):
        """记录成功调用"""
        cb = self._get_circuit_breaker(backend)
        if cb.state == "half_open":
            cb.state = "closed"
            cb.failure_count = 0
            logger.info(f"Circuit breaker for {backend} closed")
        self.stats["successful_calls"] += 1
    
    def _record_failure(self, backend: str, error: Exception):
        """记录失败调用"""
        cb = self._get_circuit_breaker(backend)
        cb.failure_count += 1
        cb.last_failure_time = datetime.now()
        
        if cb.failure_count >= cb.failure_threshold:
            cb.state = "open"
            logger.warning(
                f"Circuit breaker opened for {backend} "
                f"after {cb.failure_count} failures"
            )
        
        self.stats["failed_calls"] += 1
    
    def _calculate_delay(self, attempt: int, config: RetryConfig) -> float:
        """计算重试延迟（指数退避）"""
        delay = min(
            config.initial_delay * (config.exponential_base ** attempt),
            config.max_delay
        )
        
        if config.jitter:
            import random
            delay *= (0.5 + random.random())  # 添加 50-150% 的随机抖动
        
        return delay
    
    def _is_retryable_error(self, error: Exception) -> bool:
        """判断错误是否可重试"""
        error_msg = str(error).lower()
        
        # 可重试的错误类型
        retryable_patterns = [
            "timeout",
            "connection",
            "network",
            "503",  # Service Unavailable
            "502",  # Bad Gateway
            "500",  # Internal Server Error
            "429",  # Rate Limit (但需要更长延迟)
        ]
        
        return any(pattern in error_msg for pattern in retryable_patterns)
    
    def _is_rate_limit_error(self, error: Exception) -> bool:
        """判断是否为速率限制错误"""
        error_msg = str(error).lower()
        return "429" in error_msg or "rate limit" in error_msg
    
    def retry_with_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        config: RetryConfig,
        fallback_backends: Optional[List[str]] = None,
        current_backend: Optional[str] = None
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
                    return self._try_fallback(
                        func, args, kwargs, config, fallback_backends, current_backend
                    )
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
                    logger.error(f"Non-retryable error: {e}")
                    break
                
                # 最后一次尝试不需要延迟
                if attempt < config.max_retries - 1:
                    delay = self._calculate_delay(attempt, config)
                    
                    # 速率限制错误需要更长延迟
                    if self._is_rate_limit_error(e):
                        delay *= 3
                        logger.warning(f"Rate limit detected, waiting {delay:.1f}s")
                    
                    logger.info(
                        f"Retry attempt {attempt + 1}/{config.max_retries} "
                        f"after {delay:.1f}s delay"
                    )
                    time.sleep(delay)
                    self.stats["retries"] += 1
        
        # 主后端失败，尝试故障转移
        if fallback_backends:
            try:
                return self._try_fallback(
                    func, args, kwargs, config, fallback_backends, current_backend
                )
            except Exception as fallback_error:
                logger.error(f"All fallback attempts failed: {fallback_error}")
                last_error = fallback_error
        
        # 所有尝试都失败
        raise last_error
    
    def _try_fallback(
        self,
        func: Callable,
        args: tuple,
        kwargs: dict,
        config: RetryConfig,
        fallback_backends: List[str],
        exclude_backend: Optional[str]
    ) -> Any:
        """尝试故障转移到备用后端"""
        for backend in fallback_backends:
            if backend == exclude_backend:
                continue
            
            try:
                self._check_circuit_breaker(backend)
            except CircuitBreakerError:
                logger.warning(f"Skipping {backend} (circuit breaker open)")
                continue
            
            logger.info(f"Attempting fallback to {backend}")
            self.stats["fallbacks"] += 1
            
            # 更新 kwargs 中的 backend 参数
            fallback_kwargs = kwargs.copy()
            fallback_kwargs["backend"] = backend  # 始终设置 backend 参数
            
            try:
                result = func(*args, **fallback_kwargs)
                self._record_success(backend)
                logger.info(f"Fallback to {backend} successful")
                return result
            except Exception as e:
                self._record_failure(backend, e)
                logger.warning(f"Fallback to {backend} failed: {e}")
                continue
        
        raise Exception("All fallback backends failed")
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        total = self.stats["total_calls"]
        success_rate = (
            self.stats["successful_calls"] / total * 100
            if total > 0 else 0
        )
        
        return {
            **self.stats,
            "success_rate": f"{success_rate:.1f}%",
            "circuit_breakers": {
                backend: {
                    "state": cb.state,
                    "failure_count": cb.failure_count,
                    "last_failure": (
                        cb.last_failure_time.isoformat()
                        if cb.last_failure_time else None
                    )
                }
                for backend, cb in self.circuit_breakers.items()
            }
        }
    
    def reset_circuit_breaker(self, backend: str):
        """手动重置熔断器"""
        if backend in self.circuit_breakers:
            self.circuit_breakers[backend] = CircuitBreakerState()
            logger.info(f"Circuit breaker for {backend} manually reset")


# 全局实例
_retry_manager: Optional[LLMRetryManager] = None


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
    fallback_backends: Optional[List[str]] = None,
    backend_param: str = "backend"
):
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
        @wraps(func)
        def wrapper(*args, **kwargs):
            config = RetryConfig(
                max_retries=max_retries,
                initial_delay=initial_delay,
                max_delay=max_delay
            )
            
            # 获取当前后端
            current_backend = kwargs.get(backend_param)
            
            manager = get_retry_manager()
            return manager.retry_with_fallback(
                func, args, kwargs, config,
                fallback_backends, current_backend
            )
        
        return wrapper
    return decorator
