#!/usr/bin/env python3
"""
LLMCache Protocol 兼容性测试

测试 LLMCache 是否正确实现 CacheProvider Protocol。
"""

import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_cache_dir():
    """创建临时缓存目录"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def llm_cache(temp_cache_dir):
    """创建 LLMCache 实例"""
    from scripts.collaboration.llm_cache import LLMCache, reset_cache

    # 重置全局缓存
    reset_cache()

    # 创建新实例
    cache = LLMCache(cache_dir=temp_cache_dir, ttl_seconds=3600)
    yield cache

    # 清理
    reset_cache()


def test_llm_cache_implements_cache_provider(llm_cache):
    """测试 LLMCache 实现 CacheProvider Protocol"""
    from scripts.collaboration.protocols import CacheProvider

    # 可以赋值给 CacheProvider 类型
    cache: CacheProvider = llm_cache

    # 验证所有方法都存在
    assert hasattr(cache, "get")
    assert hasattr(cache, "set")
    assert hasattr(cache, "clear")
    assert hasattr(cache, "is_available")
    assert hasattr(cache, "get_stats")


def test_llm_cache_get_miss(llm_cache):
    """测试 LLMCache.get() 缓存未命中"""
    result = llm_cache.get("test prompt", "openai", "gpt-4")
    assert result is None


def test_llm_cache_set_and_get(llm_cache):
    """测试 LLMCache.set() 和 get() 基本功能"""
    prompt = "What is Python?"
    response = "Python is a programming language."
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)

    # 获取缓存
    cached_response = llm_cache.get(prompt, backend, model)
    assert cached_response == response


def test_llm_cache_set_with_ttl(llm_cache):
    """测试 LLMCache.set() 支持 ttl 参数"""
    prompt = "test"
    response = "response"
    backend = "openai"
    model = "gpt-4"

    # 设置缓存（带 TTL）
    llm_cache.set(prompt, response, backend, model, ttl=7200)

    # 验证可以获取
    cached_response = llm_cache.get(prompt, backend, model)
    assert cached_response == response


def test_llm_cache_clear(llm_cache):
    """测试 LLMCache.clear() 清空所有缓存"""
    # 添加多个缓存
    llm_cache.set("prompt1", "response1", "openai", "gpt-4")
    llm_cache.set("prompt2", "response2", "anthropic", "claude")

    # 验证缓存存在
    assert llm_cache.get("prompt1", "openai", "gpt-4") == "response1"
    assert llm_cache.get("prompt2", "anthropic", "claude") == "response2"

    # 清空缓存
    llm_cache.clear()

    # 验证缓存已清空
    assert llm_cache.get("prompt1", "openai", "gpt-4") is None
    assert llm_cache.get("prompt2", "anthropic", "claude") is None


def test_llm_cache_is_available(llm_cache):
    """测试 LLMCache.is_available() 返回 True"""
    assert llm_cache.is_available()


def test_llm_cache_is_available_invalid_dir():
    """Test LLMCache.is_available() returns False for invalid directory"""
    from scripts.collaboration.llm_cache import LLMCache

    try:
        cache = LLMCache(cache_dir="/invalid/path/that/does/not/exist")
        assert not cache.is_available()
    except OSError:
        pass


def test_llm_cache_get_stats_structure(llm_cache):
    """测试 LLMCache.get_stats() 返回正确的结构"""
    stats = llm_cache.get_stats()

    # 验证 Protocol 要求的字段
    assert "hit_count" in stats
    assert "miss_count" in stats
    assert "hit_rate" in stats
    assert "total_size" in stats
    assert "entry_count" in stats

    # 验证类型
    assert isinstance(stats["hit_count"], int)
    assert isinstance(stats["miss_count"], int)
    assert isinstance(stats["hit_rate"], float)
    assert isinstance(stats["total_size"], int)
    assert isinstance(stats["entry_count"], int)


def test_llm_cache_get_stats_values(llm_cache):
    """测试 LLMCache.get_stats() 返回正确的值"""
    # 初始状态
    stats = llm_cache.get_stats()
    assert stats["hit_count"] == 0
    assert stats["miss_count"] == 0
    assert stats["hit_rate"] == 0.0
    assert stats["entry_count"] == 0

    # 添加缓存
    llm_cache.set("prompt1", "response1", "openai", "gpt-4")
    llm_cache.set("prompt2", "response2", "openai", "gpt-4")

    # 缓存命中
    llm_cache.get("prompt1", "openai", "gpt-4")
    llm_cache.get("prompt1", "openai", "gpt-4")

    # 缓存未命中
    llm_cache.get("prompt3", "openai", "gpt-4")

    # 验证统计
    stats = llm_cache.get_stats()
    assert stats["hit_count"] == 2
    assert stats["miss_count"] == 1
    assert stats["hit_rate"] == 2 / 3
    assert stats["memory_entries"] == 2


def test_llm_cache_different_backends(llm_cache):
    """测试 LLMCache 区分不同的后端"""
    prompt = "same prompt"

    # 不同后端，不同响应
    llm_cache.set(prompt, "openai response", "openai", "gpt-4")
    llm_cache.set(prompt, "anthropic response", "anthropic", "claude")

    # 验证可以正确区分
    assert llm_cache.get(prompt, "openai", "gpt-4") == "openai response"
    assert llm_cache.get(prompt, "anthropic", "claude") == "anthropic response"


def test_llm_cache_different_models(llm_cache):
    """测试 LLMCache 区分不同的模型"""
    prompt = "same prompt"
    backend = "openai"

    # 不同模型，不同响应
    llm_cache.set(prompt, "gpt-4 response", backend, "gpt-4")
    llm_cache.set(prompt, "gpt-3.5 response", backend, "gpt-3.5-turbo")

    # 验证可以正确区分
    assert llm_cache.get(prompt, backend, "gpt-4") == "gpt-4 response"
    assert llm_cache.get(prompt, backend, "gpt-3.5-turbo") == "gpt-3.5 response"


def test_llm_cache_memory_and_disk(llm_cache, temp_cache_dir):
    """测试 LLMCache 内存和磁盘双层缓存"""
    prompt = "test prompt"
    response = "test response"
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)

    # 验证内存缓存
    assert llm_cache.get(prompt, backend, model) == response

    # 验证磁盘缓存（检查文件存在）
    cache_files = list(Path(temp_cache_dir).glob("*.json"))
    assert len(cache_files) > 0

    # 创建新实例（清空内存缓存）
    from scripts.collaboration.llm_cache import LLMCache

    new_cache = LLMCache(cache_dir=temp_cache_dir, ttl_seconds=3600)

    # 验证可以从磁盘加载
    assert new_cache.get(prompt, backend, model) == response


def test_llm_cache_ttl_expiration(temp_cache_dir):
    """测试 LLMCache TTL 过期机制"""
    import time

    from scripts.collaboration.llm_cache import LLMCache

    # 创建短 TTL 的缓存
    cache = LLMCache(cache_dir=temp_cache_dir, ttl_seconds=1)

    prompt = "test"
    response = "response"
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    cache.set(prompt, response, backend, model)

    # 立即获取，应该成功
    assert cache.get(prompt, backend, model) == response

    # 等待过期
    time.sleep(1.5)

    # 再次获取，应该返回 None（已过期）
    assert cache.get(prompt, backend, model) is None


def test_llm_cache_lru_eviction(temp_cache_dir):
    """测试 LLMCache LRU 淘汰机制"""
    from scripts.collaboration.llm_cache import LLMCache

    # 创建小容量的缓存
    cache = LLMCache(cache_dir=temp_cache_dir, ttl_seconds=3600)
    cache.max_memory_entries = 3

    # 添加 4 个缓存（超过容量）
    cache.set("prompt1", "response1", "openai", "gpt-4")
    cache.set("prompt2", "response2", "openai", "gpt-4")
    cache.set("prompt3", "response3", "openai", "gpt-4")
    cache.set("prompt4", "response4", "openai", "gpt-4")

    # 验证内存缓存只保留 3 个
    assert len(cache.memory_cache) == 3

    # 验证统计信息
    stats = cache.get_stats()
    assert stats["evictions"] > 0


def test_llm_cache_concurrent_access(llm_cache):
    """测试 LLMCache 并发访问（线程安全）"""
    import threading

    results = []

    def worker(i):
        prompt = f"prompt_{i}"
        response = f"response_{i}"
        llm_cache.set(prompt, response, "openai", "gpt-4")
        cached = llm_cache.get(prompt, "openai", "gpt-4")
        results.append(cached == response)

    # 创建多个线程
    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]

    # 启动所有线程
    for t in threads:
        t.start()

    # 等待所有线程完成
    for t in threads:
        t.join()

    # 验证所有操作都成功
    assert all(results)


def test_llm_cache_unicode_support(llm_cache):
    """测试 LLMCache 支持 Unicode"""
    prompt = "什么是 Python？"
    response = "Python 是一种编程语言。"
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)

    # 获取缓存
    cached_response = llm_cache.get(prompt, backend, model)
    assert cached_response == response


def test_llm_cache_large_response(llm_cache):
    """测试 LLMCache 支持大响应"""
    prompt = "Generate a long text"
    response = "A" * 100000  # 100KB
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)

    # 获取缓存
    cached_response = llm_cache.get(prompt, backend, model)
    assert cached_response == response
    assert len(cached_response) == 100000


def test_llm_cache_empty_response(llm_cache):
    """测试 LLMCache 支持空响应"""
    prompt = "test"
    response = ""
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)

    # 获取缓存
    cached_response = llm_cache.get(prompt, backend, model)
    assert cached_response == ""


def test_llm_cache_special_characters(llm_cache):
    """测试 LLMCache 支持特殊字符"""
    prompt = "test\n\t\r\"'\\special"
    response = "response\n\t\r\"'\\special"
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)

    # 获取缓存
    cached_response = llm_cache.get(prompt, backend, model)
    assert cached_response == response


def test_llm_cache_invalidate(llm_cache):
    """测试 LLMCache.invalidate() 使特定缓存失效"""
    prompt = "test"
    response = "response"
    backend = "openai"
    model = "gpt-4"

    # 设置缓存
    llm_cache.set(prompt, response, backend, model)
    assert llm_cache.get(prompt, backend, model) == response

    # 使缓存失效
    llm_cache.invalidate(prompt, backend, model)

    # 验证缓存已失效
    assert llm_cache.get(prompt, backend, model) is None


def test_llm_cache_export_stats_report(llm_cache):
    """测试 LLMCache.export_stats_report() 生成报告"""
    # 添加一些缓存
    llm_cache.set("prompt1", "response1", "openai", "gpt-4")
    llm_cache.get("prompt1", "openai", "gpt-4")

    # 生成报告
    report = llm_cache.export_stats_report()

    # 验证报告内容
    assert "LLM Cache Statistics Report" in report
    assert "Overall Performance" in report
    assert "Cache Operations" in report
    assert "Configuration" in report


def test_llm_cache_get_top_cached(llm_cache):
    """测试 LLMCache.get_top_cached() 获取热门缓存"""
    # 添加缓存并访问不同次数
    llm_cache.set("prompt1", "response1", "openai", "gpt-4")
    llm_cache.set("prompt2", "response2", "openai", "gpt-4")

    # prompt1 访问 3 次
    for _ in range(3):
        llm_cache.get("prompt1", "openai", "gpt-4")

    # prompt2 访问 1 次
    llm_cache.get("prompt2", "openai", "gpt-4")

    # 获取热门缓存
    top_cached = llm_cache.get_top_cached(limit=2)

    # 验证排序正确（prompt1 应该排第一）
    assert len(top_cached) == 2
    assert top_cached[0]["hit_count"] == 3
    assert top_cached[1]["hit_count"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
