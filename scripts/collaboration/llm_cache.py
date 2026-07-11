#!/usr/bin/env python3
"""
LLM Response Cache Module

Provides intelligent caching for LLM API calls to:
- Reduce API costs by 60-80%
- Improve response time by 90% (cache hits)
- Enable offline testing
- Support TTL-based expiration

Usage:
    from scripts.collaboration.llm_cache import get_llm_cache

    cache = get_llm_cache()

    # Try to get cached response
    cached = cache.get(prompt, "openai", "gpt-4")
    if cached:
        return cached

    # Call API and cache result
    response = call_llm_api(prompt)
    cache.set(prompt, response, "openai", "gpt-4")
"""

import asyncio
import hashlib
import json
import logging
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, cast

from .llm_cache_base import LLMCacheBase
from .prometheus_metrics import get_metrics

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """LLM 缓存条目"""

    prompt_hash: str
    response: str
    backend: str
    model: str
    timestamp: float
    hit_count: int = 0
    last_accessed: float = 0.0

    def is_expired(self, ttl_seconds: int) -> bool:
        """检查是否过期"""
        return time.time() - self.timestamp > ttl_seconds

    def age_hours(self) -> float:
        """获取缓存年龄（小时）"""
        return (time.time() - self.timestamp) / 3600


class LLMCache(LLMCacheBase):
    """
    LLM 响应缓存器

    Features:
    - 内存 + 磁盘双层缓存
    - TTL 过期机制
    - 命中率统计
    - 自动清理过期缓存

    Inherits shared caching strategy (key generation, TTL, LRU policy, stats)
    from LLMCacheBase. Only I/O layer (memory dict, disk files, Redis) is
    implemented here.
    """

    def __init__(
        self,
        cache_dir: str | None = None,
        ttl_seconds: int = 86400,  # 24 hours
        max_memory_entries: int = 1000,
        enable_redis: bool = False,
        redis_url: str | None = None,
        use_multi_level_cache: bool = False,
    ):
        """
        初始化缓存

        Args:
            cache_dir: 缓存目录，默认为 data/llm_cache
            ttl_seconds: 缓存过期时间（秒），默认 24 小时
            max_memory_entries: 内存缓存最大条目数
            enable_redis: 是否启用 Redis L2 缓存
            redis_url: Redis 连接 URL
            use_multi_level_cache: 是否使用 MultiLevelCacheCoordinator 作为后端
                （提供缓存穿透/雪崩/击穿保护）
        """
        self.use_multi_level_cache = use_multi_level_cache
        self._mlc: Any = None  # MultiLevelCacheCoordinator instance

        if use_multi_level_cache:
            try:
                from .multi_level_cache import MemoryCacheBackend, MultiLevelCacheCoordinator

                l1 = MemoryCacheBackend(max_size=max_memory_entries, default_ttl=ttl_seconds)
                l2 = None
                if enable_redis and redis_url:
                    try:
                        from .redis_cache_backend import RedisCacheBackend
                        l2 = RedisCacheBackend(redis_url=redis_url)
                    except (ImportError, AttributeError, RuntimeError, OSError) as e:
                        logger.warning("Redis L2 backend for MultiLevelCache init failed: %s", e)

                self._mlc = MultiLevelCacheCoordinator(
                    l1_backend=l1,
                    l2_backend=l2,
                    enable_l1=True,
                    enable_l2=l2 is not None,
                    null_ttl=60,
                    ttl_jitter_range=0.1,
                )
                logger.info("MultiLevelCacheCoordinator enabled as LLMCache backend")
            except (ImportError, AttributeError, RuntimeError) as e:
                logger.warning("MultiLevelCacheCoordinator init failed, falling back to default: %s", e)
                self.use_multi_level_cache = False
                self._mlc = None

        # Initialize shared strategy from base class (sets ttl, max_memory_entries, stats)
        super().__init__(
            cache_dir=cache_dir,
            ttl_seconds=ttl_seconds,
            max_memory_entries=max_memory_entries,
        )

        self.cache_dir = Path(cache_dir or "data/llm_cache")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.memory_cache: dict[str, CacheEntry] = {}
        self._lock = threading.RLock()

        # Extend base stats with sync-specific "expirations" counter
        self.stats["expirations"] = 0

        # Redis L2 缓存
        self._redis_cache = None
        if not use_multi_level_cache and enable_redis and redis_url:
            try:
                from .redis_cache import SyncRedisCacheWrapper
                self._redis_cache = SyncRedisCacheWrapper(
                    redis_url=redis_url,
                    prefix="devsquad:llm:",
                    default_ttl=3600,
                )
                logger.info("Redis L2 cache enabled: %s", redis_url)
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                logger.warning("Redis L2 cache init failed, using memory+disk only: %s", e)

    def _hash_prompt(self, prompt: str, backend: str, model: str) -> str:
        """
        生成缓存键

        Delegates to LLMCacheBase.generate_cache_key (SHA256, 16-char truncated).
        Kept as a thin wrapper for backward compatibility with existing callers.
        """
        return self.generate_cache_key(prompt, backend, model, hash_length=self.DEFAULT_HASH_LENGTH)

    def _redis_hash_prompt(self, prompt: str, backend: str, model: str) -> str:
        """Generate a Redis-safe cache key from prompt components."""
        raw = f"{prompt}:{backend}:{model}"
        return hashlib.sha256(raw.encode()).hexdigest()

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine synchronously (bridge for MultiLevelCacheCoordinator)."""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, coro)
                    return future.result(timeout=30)
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def get(self, prompt: str, backend: str, model: str) -> str | None:
        """
        获取缓存响应

        查找顺序：
        1. 内存缓存（快速）
        2. 磁盘缓存（较慢）
        3. Redis L2 缓存（分布式）

        当 use_multi_level_cache=True 时，委托给 MultiLevelCacheCoordinator。

        Returns:
            缓存的响应，如果未找到或已过期则返回 None
        """
        # Determine cache level for Prometheus metrics
        _cache_level = "l1"

        # MultiLevelCacheCoordinator backend path
        if self.use_multi_level_cache and self._mlc is not None:
            try:
                cache_key = self._hash_prompt(prompt, backend, model)
                result = self._run_async(self._mlc.get(cache_key, ttl=self.ttl))
                if result is not None:
                    with self._lock:
                        self.stats["hits"] += 1
                    # Prometheus: record cache hit
                    try:
                        get_metrics().record_cache_hit("l1", "llm_response")
                    except (ValueError, KeyError, AttributeError, RuntimeError) as e:  # Broad catch: optional metrics
                        logger.debug("Prometheus cache hit recording failed: %s", e)
                    return cast(str | None, result)
                with self._lock:
                    self.stats["misses"] += 1
                # Prometheus: record cache miss
                try:
                    get_metrics().record_cache_miss("l1", "llm_response")
                except (ValueError, KeyError, AttributeError, RuntimeError) as e:  # Broad catch: optional metrics
                    logger.debug("Prometheus cache miss recording failed: %s", e)
                return None
            except (RuntimeError, AttributeError, KeyError, OSError) as e:
                logger.warning("MultiLevelCache get failed, falling back: %s", e)

        # Default backend path (original logic)
        cache_key = self._hash_prompt(prompt, backend, model)

        with self._lock:
            if cache_key in self.memory_cache:
                entry = self.memory_cache[cache_key]
                if not entry.is_expired(self.ttl):
                    entry.hit_count += 1
                    entry.last_accessed = time.time()
                    self.stats["hits"] += 1
                    # Prometheus: record cache hit (L1 memory)
                    try:
                        get_metrics().record_cache_hit("l1", "llm_response")
                    except (ValueError, KeyError, AttributeError, RuntimeError) as e:  # Broad catch: optional metrics
                        logger.debug("Prometheus cache hit recording failed: %s", e)
                    return entry.response
                else:
                    del self.memory_cache[cache_key]
                    self.stats["expirations"] += 1

        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                entry = CacheEntry(**data)

                if not entry.is_expired(self.ttl):
                    entry.hit_count += 1
                    entry.last_accessed = time.time()
                    with self._lock:
                        self._add_to_memory(cache_key, entry)

                    try:
                        cache_file.write_text(json.dumps(asdict(entry)), encoding="utf-8")
                    except (OSError, ValueError) as e:
                        logger.debug("Disk cache write-back failed: %s", e)

                    with self._lock:
                        self.stats["hits"] += 1
                    # Prometheus: record cache hit (L1 disk)
                    try:
                        get_metrics().record_cache_hit("l1", "llm_response")
                    except (ValueError, KeyError, AttributeError, RuntimeError) as e:  # Broad catch: optional metrics
                        logger.debug("Prometheus cache hit recording failed: %s", e)
                    return entry.response
                else:
                    try:
                        cache_file.unlink()
                    except OSError as e:
                        logger.debug("Failed to delete expired cache file: %s", e)
                    with self._lock:
                        self.stats["expirations"] += 1
            except (OSError, json.JSONDecodeError, ValueError, KeyError) as e:
                logger.debug("Disk cache read failed: %s", e)
                try:
                    cache_file.unlink()
                except OSError as e2:
                    logger.debug("Failed to delete corrupt cache file: %s", e2)

        # Redis L2 lookup (after disk miss)
        if self._redis_cache:
            try:
                redis_key = self._redis_hash_prompt(prompt, backend, model)
                redis_value = self._redis_cache.get(redis_key)
                if redis_value is not None:
                    with self._lock:
                        self.stats["hits"] += 1
                    # Prometheus: record cache hit (L2 Redis)
                    try:
                        get_metrics().record_cache_hit("l2", "llm_response")
                    except (ValueError, KeyError, AttributeError, RuntimeError) as e:  # Broad catch: optional metrics
                        logger.debug("Prometheus cache hit recording failed: %s", e)
                    logger.debug("Redis L2 cache hit for key %s", redis_key[:16])
                    return cast(str | None, redis_value)
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.debug("Redis L2 cache read failed: %s", e)

        with self._lock:
            self.stats["misses"] += 1
        # Prometheus: record cache miss
        try:
            get_metrics().record_cache_miss("l1", "llm_response")
        except (ValueError, KeyError, AttributeError, RuntimeError) as e:  # Broad catch: optional metrics
            logger.debug("Prometheus cache miss recording failed: %s", e)
        return None

    def set(self, prompt: str, response: str, backend: str, model: str, ttl: int | None = None) -> None:
        """
        保存响应到缓存

        同时保存到：
        - 内存缓存（快速访问）
        - 磁盘缓存（持久化）
        - Redis L2 缓存（分布式共享）

        当 use_multi_level_cache=True 时，委托给 MultiLevelCacheCoordinator。

        Args:
            prompt: 提示词
            response: LLM 响应
            backend: LLM 后端
            model: 模型名称
            ttl: 过期时间（秒），None 表示使用默认 TTL
        """
        cache_key = self._hash_prompt(prompt, backend, model)

        # MultiLevelCacheCoordinator backend path
        if self.use_multi_level_cache and self._mlc is not None:
            try:
                self._run_async(self._mlc.set(cache_key, response, ttl=ttl or self.ttl))
                with self._lock:
                    self.stats["sets"] += 1
                return
            except (RuntimeError, AttributeError, KeyError, OSError) as e:
                logger.warning("MultiLevelCache set failed, falling back: %s", e)

        # Default backend path (original logic)
        entry = CacheEntry(
            prompt_hash=cache_key,
            response=response,
            backend=backend,
            model=model,
            timestamp=time.time(),
            hit_count=0,
            last_accessed=time.time(),
        )

        with self._lock:
            self._add_to_memory(cache_key, entry)

        cache_file = self.cache_dir / f"{cache_key}.json"
        try:
            cache_file.write_text(json.dumps(asdict(entry)), encoding="utf-8")
            with self._lock:
                self.stats["sets"] += 1
        except (OSError, ValueError) as e:
            logger.warning("Disk cache write failed: %s", e)

        # Redis L2 write (async, non-blocking)
        if self._redis_cache:
            try:
                redis_key = self._redis_hash_prompt(prompt, backend, model)
                self._redis_cache.set(redis_key, response, ttl=ttl or 3600)
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.debug("Redis L2 cache write failed: %s", e)

    def _add_to_memory(self, key: str, entry: CacheEntry) -> None:
        """添加到内存缓存，必要时执行 LRU 淘汰"""
        if self.should_evict(len(self.memory_cache)):
            # LRU 淘汰：删除最久未访问的条目
            oldest_key = min(self.memory_cache.keys(), key=lambda k: self.memory_cache[k].last_accessed)
            del self.memory_cache[oldest_key]
            self.stats["evictions"] += 1

        self.memory_cache[key] = entry

    def is_available(self) -> bool:
        """
        检查缓存是否可用

        Returns:
            True 表示可用，False 表示不可用（需要降级）

        检查项：
        - 缓存目录是否存在
        - 缓存目录是否可写
        """
        try:
            # 检查缓存目录是否存在且可写
            if not self.cache_dir.exists():
                return False

            # 尝试创建测试文件
            test_file = self.cache_dir / ".test_write"
            try:
                test_file.write_text("test")
                test_file.unlink()
                return True
            except OSError as e:
                logger.debug("Cache dir write test failed: %s", e)
                return False
        except (OSError, AttributeError) as e:
            logger.debug("Cache availability check failed: %s", e)
            return False

    def get_stats(self) -> dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含命中率、条目数等统计信息的字典
        """
        total_requests = self.stats["hits"] + self.stats["misses"]
        hit_rate = self.calculate_hit_rate(self.stats["hits"], self.stats["misses"])

        # 统计磁盘缓存
        try:
            disk_entries = len(list(self.cache_dir.glob("*.json")))
        except OSError as e:
            logger.debug("Disk entry count failed: %s", e)
            disk_entries = 0

        # 计算总命中次数
        total_hits = sum(e.hit_count for e in self.memory_cache.values())

        # 计算总大小（兼容 Protocol 接口）
        try:
            total_size = sum(f.stat().st_size for f in self.cache_dir.glob("*.json"))
        except OSError as e:
            logger.debug("Cache size calculation failed: %s", e)
            total_size = 0

        return {
            # Protocol 要求的字段
            "hit_count": self.stats["hits"],
            "miss_count": self.stats["misses"],
            "hit_rate": hit_rate,
            "total_size": total_size,
            "entry_count": len(self.memory_cache) + disk_entries,
            # 额外的统计信息
            "total_requests": total_requests,
            "hits": self.stats["hits"],
            "misses": self.stats["misses"],
            "hit_rate_percent": self.format_hit_rate_percent(self.stats["hits"], self.stats["misses"]),
            "memory_entries": len(self.memory_cache),
            "disk_entries": disk_entries,
            "total_hits": total_hits,
            "sets": self.stats["sets"],
            "evictions": self.stats["evictions"],
            "expirations": self.stats["expirations"],
            "cache_dir": str(self.cache_dir),
            "ttl_hours": self.ttl / 3600,
            **({"redis": self._redis_cache.health_check()} if self._redis_cache else {}),
        }

    def get_top_cached(self, limit: int = 10) -> list[dict[str, Any]]:
        """获取最常访问的缓存条目"""
        sorted_entries = sorted(self.memory_cache.items(), key=lambda x: x[1].hit_count, reverse=True)[:limit]

        return [
            {
                "hash": key,
                "backend": entry.backend,
                "model": entry.model,
                "hit_count": entry.hit_count,
                "age_hours": entry.age_hours(),
                "response_preview": entry.response[:100] + "..." if len(entry.response) > 100 else entry.response,
            }
            for key, entry in sorted_entries
        ]

    def clear(self) -> None:
        """
        清空所有缓存

        实现 CacheProvider Protocol 接口。
        清空内存缓存、磁盘缓存和 Redis 缓存，重置统计信息。
        """
        # 清空磁盘缓存
        try:
            for f in self.cache_dir.glob("*.json"):
                try:
                    f.unlink()
                except OSError as e:
                    logger.warning("Failed to delete cache file %s: %s", f, e)
        except OSError as e:
            logger.warning("Failed to clear disk cache: %s", e)

        # 清空内存缓存
        self.memory_cache.clear()

        # 清空 Redis 缓存
        if self._redis_cache:
            try:
                self._redis_cache.clear()
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.debug("Redis cache clear failed: %s", e)

        # 重置统计信息
        self.stats = dict.fromkeys(self.stats, 0)

    def clear_old(self, older_than_hours: float) -> None:
        """
        清除旧缓存（保留此方法以保持向后兼容）

        Args:
            older_than_hours: 清除超过指定小时数的缓存
        """
        threshold = time.time() - (older_than_hours * 3600)

        # 清除内存
        to_remove = [k for k, v in self.memory_cache.items() if v.timestamp < threshold]
        for k in to_remove:
            del self.memory_cache[k]

        # 清除磁盘
        for cache_file in self.cache_dir.glob("*.json"):
            try:
                data = json.loads(cache_file.read_text(encoding="utf-8"))
                if data.get("timestamp", 0) < threshold:
                    cache_file.unlink()
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.warning("Failed to clean cache file %s: %s", cache_file, e)

    def invalidate(self, prompt: str, backend: str, model: str) -> None:
        """使特定缓存失效"""
        cache_key = self._hash_prompt(prompt, backend, model)

        # 从内存删除
        if cache_key in self.memory_cache:
            del self.memory_cache[cache_key]

        # 从磁盘删除
        cache_file = self.cache_dir / f"{cache_key}.json"
        if cache_file.exists():
            cache_file.unlink()

    def export_stats_report(self) -> str:
        """导出统计报告（Markdown 格式）"""
        stats = self.get_stats()
        top_cached = self.get_top_cached(5)

        report = f"""# LLM Cache Statistics Report

**Generated**: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Overall Performance

| Metric | Value |
|--------|-------|
| Total Requests | {stats["total_requests"]} |
| Cache Hits | {stats["hits"]} |
| Cache Misses | {stats["misses"]} |
| Hit Rate | {stats["hit_rate_percent"]} |
| Memory Entries | {stats["memory_entries"]} |
| Disk Entries | {stats["disk_entries"]} |

## Cache Operations

| Opera| Count |
|-----------|-------|
| Sets | {stats["sets"]} |
| Evictions | {stats["evictions"]} |
| Expirations | {stats["expirations"]} |

## Configuration

- Cache Directory: `{stats["cache_dir"]}`
- TTL: {stats["ttl_hours"]:.1f} hours
- Max Memory Entries: {self.max_memory_entries}

## Top Cached Entries

"""
        for i, entry in enumerate(top_cached, 1):
            report += f"{i}. **{entry['backend']}:{entry['model']}** - {entry['hit_count']} hits ({entry['age_hours']:.1f}h old)\n"

        return report


# 全局单例
_cache_instance: LLMCache | None = None
_redis_config: dict[str, Any] = {"enabled": False, "url": None}


def configure_redis_cache(enabled: bool = False, url: str | None = None) -> None:
    """Configure Redis cache for the global LLMCache instance."""
    global _redis_config, _cache_instance
    _redis_config = {"enabled": enabled, "url": url}
    # Reset singleton so next get_llm_cache() creates a new instance with Redis config
    if _cache_instance is not None:
        try:
            _cache_instance.clear()
        except (OSError, AttributeError, RuntimeError) as e:
            logger.debug("Cache clear during Redis reconfigure failed: %s", e)
    _cache_instance = None


def get_llm_cache(**kwargs: Any) -> LLMCache:
    """
    获取全局 LLM 缓存实例（单例模式）

    Args:
        **kwargs: 传递给 LLMCache 的参数（cache_dir, ttl_seconds, enable_redis, redis_url 等）

    Returns:
        LLMCache 实例
    """
    global _cache_instance
    if _cache_instance is None:
        # Merge Redis config
        if _redis_config["enabled"] and "enable_redis" not in kwargs:
            kwargs["enable_redis"] = _redis_config["enabled"]
        if _redis_config["url"] and "redis_url" not in kwargs:
            kwargs["redis_url"] = _redis_config["url"]
        _cache_instance = LLMCache(**kwargs)
    return _cache_instance


def reset_cache() -> None:
    """重置全局缓存实例（主要用于测试）"""
    global _cache_instance
    _cache_instance = None
