#!/usr/bin/env python3
"""
Protocol 接口测试

测试 Protocol 接口定义的正确性和完整性。
"""

from typing import Any

import pytest


def test_import_protocols():
    """Test Protocol module imports"""
    from scripts.collaboration.protocols import (
        CacheError,
        CacheProvider,
        MemoryProvider,
        MemoryProviderError,
        MonitorError,
        MonitorProvider,
        ProviderError,
        RetryError,
        RetryProvider,
    )

    assert isinstance(CacheProvider, type)
    assert isinstance(RetryProvider, type)
    assert isinstance(MonitorProvider, type)
    assert isinstance(MemoryProvider, type)

    assert issubclass(ProviderError, Exception)
    assert issubclass(CacheError, ProviderError)
    assert issubclass(RetryError, ProviderError)
    assert issubclass(MonitorError, ProviderError)
    assert issubclass(MemoryProviderError, ProviderError)


def test_cache_provider_protocol():
    """测试 CacheProvider Protocol 定义"""
    from scripts.collaboration.protocols import CacheProvider

    # 验证 Protocol 有正确的方法
    assert hasattr(CacheProvider, "get")
    assert hasattr(CacheProvider, "set")
    assert hasattr(CacheProvider, "clear")
    assert hasattr(CacheProvider, "is_available")
    assert hasattr(CacheProvider, "get_stats")


def test_retry_provider_protocol():
    """测试 RetryProvider Protocol 定义"""
    from scripts.collaboration.protocols import RetryProvider

    # 验证 Protocol 有正确的方法
    assert hasattr(RetryProvider, "retry_with_fallback")
    assert hasattr(RetryProvider, "is_available")
    assert hasattr(RetryProvider, "get_stats")


def test_monitor_provider_protocol():
    """测试 MonitorProvider Protocol 定义"""
    from scripts.collaboration.protocols import MonitorProvider

    # 验证 Protocol 有正确的方法
    assert hasattr(MonitorProvider, "record_llm_call")
    assert hasattr(MonitorProvider, "record_agent_execution")
    assert hasattr(MonitorProvider, "generate_report")
    assert hasattr(MonitorProvider, "is_available")
    assert hasattr(MonitorProvider, "get_stats")


def test_memory_provider_protocol():
    """测试 MemoryProvider Protocol 定义"""
    from scripts.collaboration.protocols import MemoryProvider

    # 验证 Protocol 有正确的方法
    assert hasattr(MemoryProvider, "get_rules")
    assert hasattr(MemoryProvider, "add_rule")
    assert hasattr(MemoryProvider, "update_rule")
    assert hasattr(MemoryProvider, "delete_rule")
    assert hasattr(MemoryProvider, "is_available")
    assert hasattr(MemoryProvider, "get_stats")


def test_protocol_exceptions():
    """Test Protocol exceptions"""
    from scripts.collaboration.protocols import (
        CacheError,
        MemoryProviderError,
        MonitorError,
        ProviderError,
        RetryError,
    )

    assert issubclass(CacheError, ProviderError)
    assert issubclass(RetryError, ProviderError)
    assert issubclass(MonitorError, ProviderError)
    assert issubclass(MemoryProviderError, ProviderError)

    with pytest.raises(CacheError):
        raise CacheError("Test cache error")

    with pytest.raises(RetryError):
        raise RetryError("Test retry error")

    with pytest.raises(MonitorError):
        raise MonitorError("Test monitor error")

    with pytest.raises(MemoryProviderError):
        raise MemoryProviderError("Test memory provider error")

    with pytest.raises(ProviderError):
        raise CacheError("Test")


def test_protocol_version():
    """测试 Protocol 模块版本"""
    from scripts.collaboration import protocols

    assert hasattr(protocols, "__version__")
    assert protocols.__version__ == "1.0.0"


def test_protocol_all_exports():
    """Test Protocol module exports"""
    from scripts.collaboration import protocols

    assert hasattr(protocols, "__all__")

    expected_exports = [
        "CacheProvider",
        "RetryProvider",
        "MonitorProvider",
        "MemoryProvider",
        "ProviderError",
        "CacheError",
        "RetryError",
        "MonitorError",
        "MemoryProviderError",
    ]

    for export in expected_exports:
        assert export in protocols.__all__, f"{export} not in __all__"


def test_cache_provider_structural_typing():
    """测试 CacheProvider 结构化类型（鸭子类型）"""
    from scripts.collaboration.protocols import CacheProvider

    # 创建一个简单的类，实现 CacheProvider 接口
    class SimpleCacheProvider:
        def get(self, prompt: str, backend: str, model: str) -> str | None:
            return None

        def set(self, prompt: str, response: str, backend: str, model: str, ttl: int | None = None) -> None:
            pass

        def clear(self) -> None:
            pass

        def is_available(self) -> bool:
            return True

        def get_stats(self) -> dict[str, Any]:
            return {}

    # 验证可以赋值给 CacheProvider 类型（结构化类型）
    cache: CacheProvider = SimpleCacheProvider()

    # 验证方法可以调用
    assert cache.get("test", "openai", "gpt-4") is None
    cache.set("test", "response", "openai", "gpt-4")
    cache.clear()
    assert cache.is_available() == True
    assert cache.get_stats() == {}


def test_monitor_provider_structural_typing():
    """测试 MonitorProvider 结构化类型"""
    from scripts.collaboration.protocols import MonitorProvider

    # 创建一个简单的类，实现 MonitorProvider 接口
    class SimpleMonitorProvider:
        def record_llm_call(
            self,
            backend: str,
            model: str,
            duration: float,
            token_count: int,
            success: bool,
            metadata: dict[str, Any] | None = None,
        ) -> None:
            pass

        def record_agent_execution(
            self, agent_role: str, task: str, duration: float, success: bool, metadata: dict[str, Any] | None = None
        ) -> None:
            pass

        def generate_report(self, output_path: str) -> None:
            pass

        def is_available(self) -> bool:
            return True

        def get_stats(self) -> dict[str, Any]:
            return {}

    # 验证可以赋值给 MonitorProvider 类型
    monitor: MonitorProvider = SimpleMonitorProvider()

    # 验证方法可以调用
    monitor.record_llm_call("openai", "gpt-4", 1.5, 1000, True)
    monitor.record_agent_execution("Architect", "Design API", 3.0, True)
    monitor.generate_report("/tmp/report.md")
    assert monitor.is_available() == True
    assert monitor.get_stats() == {}


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
