#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Cache Module Tests

Simple tests to verify LLM cache functionality.
"""

import pytest
import time
import tempfile
from pathlib import Path
from .llm_cache import LLMCache, CacheEntry, get_llm_cache, reset_cache


class TestCacheEntry:
    """测试 CacheEntry 数据类"""
    
    def test_is_expired(self):
        entry = CacheEntry(
            prompt_hash="test123",
            response="test response",
            backend="openai",
            model="gpt-4",
            timestamp=time.time() - 100,  # 100 秒前
            hit_count=0
        )
        
        assert not entry.is_expired(200)  # TTL 200秒，未过期
        assert entry.is_expired(50)  # TTL 50秒，已过期
    
    def test_age_hours(self):
        entry = CacheEntry(
            prompt_hash="test123",
            response="test response",
            backend="openai",
            model="gpt-4",
            timestamp=time.time() - 3600,  # 1 小时前
            hit_count=0
        )
        
        age = entry.age_hours()
        assert 0.9 < age < 1.1  # 约 1 小时


class TestLLMCache:
    """测试 LLMCache 核心功能"""
    
    @pytest.fixture
    def cache(self):
        """创建临时缓存实例"""
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LLMCache(cache_dir=tmpdir, ttl_seconds=60)
            yield cache
            cache.clear()
    
    def test_set_and_get(self, cache):
        """测试基本的设置和获取"""
        prompt = "What is Python?"
        response = "Python is a programming language."
        
        # 设置缓存
        cache.set(prompt, response, "openai", "gpt-4")
        
        # 获取缓存
        cached = cache.get(prompt, "openai", "gpt-4")
        assert cached == response
        
        # 统计信息
        stats = cache.get_stats()
        assert stats["hits"] == 1
        assert stats["misses"] == 0
        assert stats["sets"] == 1
    
    def test_cache_miss(self, cache):
        """测试缓存未命中"""
        result = cache.get("nonexistent prompt", "openai", "gpt-4")
        assert result is None
        
        stats = cache.get_stats()
        assert stats["misses"] == 1
        assert stats["hits"] == 0
    
    def test_cache_expiration(self, cache):
        """测试缓存过期"""
        # 创建短 TTL 的缓存
        cache.ttl = 1  # 1 秒 TTL
        
        prompt = "Test prompt"
        response = "Test response"
        
        cache.set(prompt, response, "openai", "gpt-4")
        
        # 立即获取，应该命中
        assert cache.get(prompt, "openai", "gpt-4") == response
        
        # 等待过期
        time.sleep(1.5)
        
        # 再次获取，应该过期
        assert cache.get(prompt, "openai", "gpt-4") is None
        
        stats = cache.get_stats()
        assert stats["expirations"] >= 1
    
    def test_lru_eviction(self, cache):
        """测试 LRU 淘汰"""
        cache.max_memory_entries = 3
        
        # 添加 4 个条目
        for i in range(4):
            cache.set(f"prompt_{i}", f"response_{i}", "openai", "gpt-4")
        
        # 第一个应该被淘汰
        assert cache.get("prompt_0", "openai", "gpt-4") is None
        
        # 其他应该还在
        assert cache.get("prompt_3", "openai", "gpt-4") == "response_3"
        
        stats = cache.get_stats()
        assert stats["evictions"] >= 1
    
    def test_hit_count(self, cache):
        """测试命中计数"""
        prompt = "Test prompt"
        response = "Test response"
        
        cache.set(prompt, response, "openai", "gpt-4")
        
        # 多次获取
        for _ in range(5):
            cache.get(prompt, "openai", "gpt-4")
        
        # 检查命中次数
        cache_key = cache._hash_prompt(prompt, "openai", "gpt-4")
        entry = cache.memory_cache[cache_key]
        assert entry.hit_count == 5
    
    def test_different_backends(self, cache):
        """测试不同后端的缓存隔离"""
        prompt = "Same prompt"
        
        cache.set(prompt, "OpenAI response", "openai", "gpt-4")
        cache.set(prompt, "Anthropic response", "anthropic", "claude-3")
        
        assert cache.get(prompt, "openai", "gpt-4") == "OpenAI response"
        assert cache.get(prompt, "anthropic", "claude-3") == "Anthropic response"
    
    def test_clear_all(self, cache):
        """测试清空所有缓存"""
        for i in range(5):
            cache.set(f"prompt_{i}", f"response_{i}", "openai", "gpt-4")
        
        cache.clear()
        
        # 所有缓存应该被清空
        for i in range(5):
            assert cache.get(f"prompt_{i}", "openai", "gpt-4") is None
        
        stats = cache.get_stats()
        assert stats["memory_entries"] == 0
    
    def test_clear_old(self, cache):
        """测试清除旧缓存"""
        # 添加一个旧缓存
        old_entry = CacheEntry(
            prompt_hash="old",
            response="old response",
            backend="openai",
            model="gpt-4",
            timestamp=time.time() - 7200,  # 2 小时前
            hit_count=0
        )
        cache.memory_cache["old"] = old_entry
        
        # 添加一个新缓存
        cache.set("new prompt", "new response", "openai", "gpt-4")
        
        # 清除 1 小时以上的缓存
        cache.clear(older_than_hours=1)
        
        # 旧缓存应该被清除
        assert "old" not in cache.memory_cache
        
        # 新缓存应该还在
        assert cache.get("new prompt", "openai", "gpt-4") == "new response"
    
    def test_invalidate(self, cache):
        """测试使缓存失效"""
        prompt = "Test prompt"
        response = "Test response"
        
        cache.set(prompt, response, "openai", "gpt-4")
        assert cache.get(prompt, "openai", "gpt-4") == response
        
        # 使缓存失效
        cache.invalidate(prompt, "openai", "gpt-4")
        
        # 应该获取不到
        assert cache.get(prompt, "openai", "gpt-4") is None
    
    def test_get_top_cached(self, cache):
        """测试获取最常访问的缓存"""
        # 添加多个缓存并访问不同次数
        cache.set("prompt_1", "response_1", "openai", "gpt-4")
        cache.set("prompt_2", "response_2", "openai", "gpt-4")
        cache.set("prompt_3", "response_3", "openai", "gpt-4")
        
        # 访问不同次数
        for _ in range(5):
            cache.get("prompt_1", "openai", "gpt-4")
        for _ in range(3):
            cache.get("prompt_2", "openai", "gpt-4")
        cache.get("prompt_3", "openai", "gpt-4")
        
        # 获取 top 2
        top = cache.get_top_cached(limit=2)
        assert len(top) == 2
        assert top[0]["hit_count"] == 5  # prompt_1
        assert top[1]["hit_count"] == 3  # prompt_2
    
    def test_export_stats_report(self, cache):
        """测试导出统计报告"""
        cache.set("test", "response", "openai", "gpt-4")
        cache.get("test", "openai", "gpt-4")
        
        report = cache.export_stats_report()
        
        assert "LLM Cache Statistics Report" in report
        assert "Total Requests" in report
        assert "Hit Rate" in report
        assert "openai:gpt-4" in report


class TestGlobalCache:
    """测试全局缓存单例"""
    
    def test_singleton(self):
        """测试单例模式"""
        reset_cache()
        
        cache1 = get_llm_cache()
        cache2 = get_llm_cache()
        
        assert cache1 is cache2
    
    def test_reset(self):
        """测试重置"""
        cache1 = get_llm_cache()
        reset_cache()
        cache2 = get_llm_cache()
        
        assert cache1 is not cache2


def test_integration():
    """集成测试：模拟真实使用场景"""
    reset_cache()
    cache = get_llm_cache()
    cache.clear()
    
    # 模拟 LLM 调用
    def mock_llm_call(prompt: str, backend: str = "openai", model: str = "gpt-4") -> str:
        # 尝试从缓存获取
        cached = cache.get(prompt, backend, model)
        if cached:
            return cached
        
        # 模拟 API 调用（耗时操作）
        time.sleep(0.01)
        response = f"Response to: {prompt}"
        
        # 保存到缓存
        cache.set(prompt, response, backend, model)
        return response
    
    # 第一次调用（缓存未命中）
    start = time.time()
    result1 = mock_llm_call("What is AI?")
    duration1 = time.time() - start
    
    # 第二次调用（缓存命中）
    start = time.time()
    result2 = mock_llm_call("What is AI?")
    duration2 = time.time() - start
    
    # 验证结果相同
    assert result1 == result2
    
    # 验证缓存命中更快
    assert duration2 < duration1 * 0.5  # 至少快 50%
    
    # 验证统计信息
    stats = cache.get_stats()
    assert stats["hits"] == 1
    assert stats["misses"] == 1
    assert stats["hit_rate"] == 0.5
    
    print(f"\n✅ Integration test passed!")
    print(f"   First call: {duration1*1000:.2f}ms (cache miss)")
    print(f"   Second call: {duration2*1000:.2f}ms (cache hit)")
    print(f"   Speed improvement: {(duration1/duration2):.1f}x faster")
    print(f"   Hit rate: {stats['hit_rate_percent']}")
