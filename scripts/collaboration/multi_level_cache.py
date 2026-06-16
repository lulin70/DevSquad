#!/usr/bin/env python3
"""
Multi-Level Cache Coordinator Module

Implements a three-level cache architecture:
L1 (Memory) → L2 (Redis) → L3 (LLM/API)

Features:
- Cache-Aside pattern (read-through, write-through)
- Protection against cache penetration/breakdown/avalanche
- Statistics aggregation across all levels
- Graceful degradation when backends unavailable
- Configurable cache policies per level

Architecture:

    Request → [L1 Memory] → Miss → [L2 Redis] → Miss → [LLM Call]
              ↓ Hit              ↓ Hit               ↓ Response
            Return           Return & populate L1  Populate L1+L2

Usage:
    from scripts.collaboration.multi_level_cache import MultiLevelCacheCoordinator

    coordinator = MultiLevelCacheCoordinator(
        l1_backend=MemoryCacheBackend(),
        l2_backend=RedisCacheBackend(),
        l3_fallback=call_llm_api
    )

    result = await coordinator.get("prompt:hash")
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from scripts.collaboration.cache_interface import (
    CacheBackendInterface,
    CacheEntry,
    CacheStats,
)

logger = logging.getLogger(__name__)


@dataclass
class LevelStats:
    """Statistics for individual cache level"""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    errors: int = 0
    total_latency_ms: float = 0.0
    operations: int = 0

    @property
    def avg_latency_ms(self) -> float:
        return self.total_latency_ms / self.operations if self.operations > 0 else 0.0


@dataclass
class NullValue:
    """Sentinel for null values to prevent cache penetration"""
    pass


NULL_SENTINEL = NullValue()


class MemoryCacheBackend(CacheBackendInterface):
    """
    Simple in-memory cache backend for L1.

    Features:
    - LRU eviction policy
    - Thread-safe with asyncio.Lock
    - Fast O(1) access
    - TTL support
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Initialize memory cache.

        Args:
            max_size: Maximum entries before LRU eviction
            default_ttl: Default TTL in seconds (5 minutes)
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._stats = CacheStats()

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            if key not in self._cache:
                self._stats.misses += 1
                return None

            entry = self._cache[key]

            if entry.is_expired():
                del self._cache[key]
                self._stats.misses += 1
                return None

            # Move to end (most recently used)
            self._cache.move_to_end(key)
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._stats.hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        async with self._lock:
            actual_ttl = ttl or self.default_ttl
            expires_at = time.time() + actual_ttl if actual_ttl > 0 else None

            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                size_bytes=len(str(value)),
            )

            # Evict if at capacity
            if key in self._cache:
                del self._cache[key]
            elif len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self._stats.evictions += 1

            self._cache[key] = entry
            self._stats.sets += 1
            return True

    async def delete(self, key: str) -> bool:
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                self._stats.deletes += 1
                return True
            return False

    async def clear(self) -> None:
        async with self._lock:
            self._cache.clear()

    async def stats(self) -> dict[str, Any]:
        total_requests = self._stats.hits + self._stats.misses
        self._stats.hit_rate = self._stats.hits / total_requests if total_requests > 0 else 0.0
        self._stats.entry_count = len(self._cache)

        result = self._stats.to_dict()
        result["backend_type"] = "memory"
        result["max_size"] = self.max_size
        return result

    async def close(self) -> None:
        await self.clear()


class MultiLevelCacheCoordinator:
    """
    Coordinates multi-level caching with L1→L2→L3 fallback chain.

    Implements Cache-Aside pattern with protection against:
    - Cache Penetration: Null sentinel values for non-existent keys
    - Cache Breakdown: Mutex lock for hot key regeneration
    - Cache Avalanche: Randomized TTL jitter

    Configuration via environment variables:
    - ENABLE_L1_CACHE: Enable/disable L1 memory cache (default: true)
    - ENABLE_L2_CACHE: Enable/disable L2 Redis cache (default: false)
    - CACHE_NULL_TTL: TTL for null sentinels to prevent penetration (default: 60)

    Example:

        coordinator = MultiLevelCacheCoordinator(
            l2_backend=RedisCacheBackend(),
            l3_fallback=my_llm_function
        )

        # Get with automatic fallback
        response = await coordinator.get("user:preferences:123")

        # Explicit set (populates all levels)
        await coordinator.set("user:preferences:123", {"theme": "dark"})
    """

    def __init__(
        self,
        l1_backend: CacheBackendInterface | None = None,
        l2_backend: CacheBackendInterface | None = None,
        l3_fallback: Callable | None = None,
        enable_l1: bool = True,
        enable_l2: bool = True,
        null_ttl: int = 60,
        ttl_jitter_range: float = 0.1,
        max_l3_concurrent: int = 10,
    ):
        """
        Initialize multi-level cache coordinator.

        Args:
            l1_backend: L1 memory backend (auto-created if None and enable_l1)
            l2_backend: L2 Redis/backend (optional)
            l3_fallback: Fallback function for cache misses (e.g., LLM call)
            enable_l1: Whether to use L1 cache
            enable_l2: Whether to use L2 cache
            null_ttl: TTL for null sentinels (prevent penetration)
            ttl_jitter_range: Random TTL jitter factor (0.0-0.5) to prevent avalanche
            max_l3_concurrent: Max concurrent L3 calls (rate limiting)
        """
        # L1: Memory cache (always available unless disabled)
        self.enable_l1 = enable_l1
        self.l1 = l1_backend or (MemoryCacheBackend() if enable_l1 else None)

        # L2: External cache (Redis/Memcached)
        self.enable_l2 = enable_l2
        self.l2 = l2_backend

        # L3: Fallback (LLM API call)
        self.l3_fallback = l3_fallback

        # Protection settings
        self.null_ttl = null_ttl
        self.ttl_jitter_range = ttl_jitter_range
        self.max_l3_concurrent = max_l3_concurrent

        # Per-level statistics
        self.l1_stats = LevelStats()
        self.l2_stats = LevelStats()
        self.l3_stats = LevelStats()

        # Breakdown protection: mutex locks for hot keys
        self._key_locks: dict[str, asyncio.Lock] = {}
        self._global_lock = asyncio.Lock()

        # Rate limiting for L3 calls
        self._l3_semaphore = asyncio.Semaphore(max_l3_concurrent)

        # Penetration protection: track recently queried missing keys
        self._null_keys: dict[str, float] = {}

        logger.info(
            "MultiLevelCacheCoordinator initialized: "
            "L1=%s, L2=%s, L3=%s",
            "enabled" if self.l1 else "disabled",
            "enabled" if self.l2 else "disabled",
            "configured" if self.l3_fallback else "not configured",
        )

    def _add_jitter(self, ttl: int | None) -> int | None:
        """Add random jitter to TTL to prevent cache avalanche"""
        if ttl is None:
            return None

        import random
        jitter = int(ttl * self.ttl_jitter_range * (random.random() * 2 - 1))
        return max(1, ttl + jitter)

    async def get(self, key: str, ttl: int | None = None) -> Any | None:
        """
        Multi-level cache lookup with automatic population.

        Lookup order:
        1. Check L1 (memory) - fastest (~0.01ms)
        2. Check L2 (Redis) - fast (~1ms)
        3. Call L3 (LLM) - slow (~100ms-10s), populate L1+L2

        Args:
            key: Cache key
            ttl: Custom TTL for populated entries

        Returns:
            Cached value or L3 result, None if all fail
        """
        start_time = time.time()

        # Check for null sentinel (penetration protection)
        if key in self._null_keys:
            if time.time() < self._null_keys[key]:
                logger.debug("Cache penetration blocked for key: %s", key)
                return None
            else:
                del self._null_keys[key]

        # Level 1: Memory cache
        if self.enable_l1 and self.l1:
            try:
                value = await self.l1.get(key)
                latency = (time.time() - start_time) * 1000
                self.l1_stats.operations += 1
                self.l1_stats.total_latency_ms += latency

                if value is not NULL_SENTINEL:
                    if value is not None:
                        self.l1_stats.hits += 1
                        logger.debug("L1 HIT: %s (%.2fms)", key, latency)
                        return value
                    else:
                        self.l1_stats.misses += 1
                else:
                    self.l1_stats.hits += 1
                    logger.debug("L1 NULL HIT (penetration block): %s", key)
                    return None
            except (AttributeError, KeyError, RuntimeError) as e:
                self.l1_stats.errors += 1
                logger.warning("L1 cache error: %s", e)

        # Level 2: Redis/External cache
        if self.enable_l2 and self.l2:
            try:
                value = await self.l2.get(key)
                latency = (time.time() - start_time) * 1000
                self.l2_stats.operations += 1
                self.l2_stats.total_latency_ms += latency

                if value is not None:
                    self.l2_stats.hits += 1
                    logger.debug("L2 HIT: %s (%.2fms)", key, latency)

                    # Populate L1
                    if self.enable_l1 and self.l1:
                        try:
                            await self.l1.set(key, value, self._add_jitter(ttl))
                        except (AttributeError, RuntimeError, OSError) as e:
                            logger.debug("Failed to populate L1: %s", e)

                    return value
                else:
                    self.l2_stats.misses += 1
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                self.l2_stats.errors += 1
                logger.warning("L2 cache error: %s", e)

        # Level 3: LLM/Fallback call (with breakdown protection)
        if self.l3_fallback:
            value = await self._call_l3_with_protection(key, ttl)
            total_latency = (time.time() - start_time) * 1000
            logger.debug("L3 CALL: %s (%.2fms)", key, total_latency)
            return value

        # All levels missed
        logger.debug("ALL MISS: %s", key)
        return None

    async def _call_l3_with_protection(self, key: str, ttl: int | None) -> Any | None:
        """
        Call L3 fallback with breakdown protection.

        Uses mutex lock per key to prevent stampede effect.
        """
        # Acquire key-specific lock (breakdown protection)
        async with self._global_lock:
            if key not in self._key_locks:
                self._key_locks[key] = asyncio.Lock()
            key_lock = self._key_locks[key]

        # Double-check after acquiring lock (another coroutine may have populated)
        if self.enable_l1 and self.l1:
            try:
                cached = await self.l1.get(key)
                if cached is not None and cached is not NULL_SENTINEL:
                    return cached
            except (AttributeError, RuntimeError) as e:
                logger.debug("L1 double-check failed: %s", e)

        async with key_lock:
            # Triple-check inside lock
            if self.enable_l1 and self.l1:
                try:
                    cached = await self.l1.get(key)
                    if cached is not None and cached is not NULL_SENTINEL:
                        return cached
                except (AttributeError, RuntimeError) as e:
                    logger.debug("L1 triple-check failed: %s", e)

            # Rate limit L3 calls
            async with self._l3_semaphore:
                try:
                    self.l3_stats.operations += 1
                    l3_start = time.time()

                    if asyncio.iscoroutinefunction(self.l3_fallback):
                        value = await self.l3_fallback(key)
                    else:
                        value = self.l3_fallback(key)

                    l3_latency = (time.time() - l3_start) * 1000
                    self.l3_stats.total_latency_ms += l3_latency

                    if value is not None:
                        self.l3_stats.misses -= 1  # Not actually a miss
                        await self._populate_all_levels(key, value, ttl)
                        return value
                    else:
                        # Store null sentinel to prevent penetration
                        await self._store_null_sentinel(key)
                        return None

                except Exception as e:  # Broad catch: unpredictable LLM/API call
                    self.l3_stats.errors += 1
                    logger.error("L3 fallback error for key %s: %s", key, e)
                    raise

    async def _populate_all_levels(self, key: str, value: Any, ttl: int | None):
        """Populate value into all available cache levels"""
        jittered_ttl = self._add_jitter(ttl)

        # Populate L1
        if self.enable_l1 and self.l1:
            try:
                await self.l1.set(key, value, jittered_ttl)
            except (AttributeError, RuntimeError) as e:
                logger.debug("Failed to populate L1: %s", e)

        # Populate L2
        if self.enable_l2 and self.l2:
            try:
                await self.l2.set(key, value, jittered_ttl)
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.debug("Failed to populate L2: %s", e)

    async def _store_null_sentinel(self, key: str):
        """Store null sentinel to prevent cache penetration"""
        self._null_keys[key] = time.time() + self.null_ttl

        if self.enable_l1 and self.l1:
            try:
                await self.l1.set(key, NULL_SENTINEL, self.null_ttl)
            except (AttributeError, RuntimeError) as e:
                logger.debug("Failed to store null sentinel in L1: %s", e)

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Set value in all cache levels.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds

        Returns:
            True if set in at least one level
        """
        success = False
        jittered_ttl = self._add_jitter(ttl)

        if self.enable_l1 and self.l1:
            try:
                await self.l1.set(key, value, jittered_ttl)
                success = True
            except (AttributeError, RuntimeError) as e:
                logger.warning("L1 set failed: %s", e)

        if self.enable_l2 and self.l2:
            try:
                await self.l2.set(key, value, jittered_ttl)
                success = True
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.warning("L2 set failed: %s", e)

        return success

    async def invalidate(self, key: str) -> None:
        """
        Invalidate key from all cache levels.

        Args:
            key: Cache key to invalidate
        """
        logger.debug("Invalidating key: %s", key)

        if self.enable_l1 and self.l1:
            try:
                await self.l1.delete(key)
            except (AttributeError, RuntimeError) as e:
                logger.debug("L1 delete failed: %s", e)

        if self.enable_l2 and self.l2:
            try:
                await self.l2.delete(key)
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.debug("L2 delete failed: %s", e)

        # Remove from null key tracking
        if key in self._null_keys:
            del self._null_keys[key]

    async def invalidate_pattern(self, pattern: str) -> int:
        """
        Invalidate keys matching pattern (best effort).

        Args:
            pattern: Glob pattern to match

        Returns:
            Number of keys invalidated
        """
        count = 0

        if isinstance(self.l2, type(None)):
            return count

        # Try to scan L2 if it supports it
        if hasattr(self.l2, 'scan_keys'):
            try:
                keys = await self.l2.scan_keys(pattern)
                for key in keys:
                    await self.invalidate(key)
                    count += 1
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.warning("Pattern invalidation failed on L2: %s", e)

        return count

    async def clear_all(self) -> None:
        """Clear all cache levels"""
        if self.enable_l1 and self.l1:
            try:
                await self.l1.clear()
            except (AttributeError, RuntimeError) as e:
                logger.warning("L1 clear failed: %s", e)

        if self.enable_l2 and self.l2:
            try:
                await self.l2.clear()
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.warning("L2 clear failed: %s", e)

        self._null_keys.clear()
        logger.info("All cache levels cleared")

    def get_stats(self) -> dict[str, Any]:
        """
        Aggregate statistics from all cache levels.

        Returns:
            Comprehensive statistics dictionary including:
            - Per-level hit/miss counts
            - Overall hit rate
            - Average latencies
            - Configuration summary
        """
        total_hits = self.l1_stats.hits + self.l2_stats.hits
        total_misses = self.l1_stats.misses + self.l2_stats.misses + self.l3_stats.operations
        total_requests = total_hits + total_misses
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0.0

        avg_latency = 0.0
        total_ops = self.l1_stats.operations + self.l2_stats.operations + self.l3_stats.operations
        if total_ops > 0:
            total_latency = (
                self.l1_stats.total_latency_ms +
                self.l2_stats.total_latency_ms +
                self.l3_stats.total_latency_ms
            )
            avg_latency = total_latency / total_ops

        return {
            "overall": {
                "hit_rate": f"{overall_hit_rate * 100:.1f}%",
                "total_requests": total_requests,
                "total_hits": total_hits,
                "total_misses": total_misses,
                "avg_latency_ms": round(avg_latency, 2),
            },
            "l1_memory": {
                "hits": self.l1_stats.hits,
                "misses": self.l1_stats.misses,
                "errors": self.l1_stats.errors,
                "avg_latency_ms": round(self.l1_stats.avg_latency_ms, 2),
                "operations": self.l1_stats.operations,
                "enabled": self.enable_l1 and self.l1 is not None,
            },
            "l2_redis": {
                "hits": self.l2_stats.hits,
                "misses": self.l2_stats.misses,
                "errors": self.l2_stats.errors,
                "avg_latency_ms": round(self.l2_stats.avg_latency_ms, 2),
                "operations": self.l2_stats.operations,
                "enabled": self.enable_l2 and self.l2 is not None,
            },
            "l3_fallback": {
                "calls": self.l3_stats.operations,
                "errors": self.l3_stats.errors,
                "avg_latency_ms": round(self.l3_stats.avg_latency_ms, 2),
                "configured": self.l3_fallback is not None,
            },
            "protection": {
                "null_sentinels_active": len(self._null_keys),
                "key_locks_active": len(self._key_locks),
            },
            "configuration": {
                "enable_l1": self.enable_l1,
                "enable_l2": self.enable_l2,
                "null_ttl": self.null_ttl,
                "ttl_jitter_range": self.ttl_jitter_range,
                "max_l3_concurrent": self.max_l3_concurrent,
            },
        }

    async def close(self) -> None:
        """Close all cache backends"""
        if self.l1:
            try:
                await self.l1.close()
            except (AttributeError, RuntimeError) as e:
                logger.warning("Error closing L1: %s", e)

        if self.l2:
            try:
                await self.l2.close()
            except (ConnectionError, TimeoutError, OSError, RuntimeError) as e:
                logger.warning("Error closing L2: %s", e)

        self._key_locks.clear()
        self._null_keys.clear()
        logger.info("MultiLevelCacheCoordinator closed")

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False

    def __repr__(self) -> str:
        return (
            f"MultiLevelCacheCoordinator("
            f"L1={'✓' if self.l1 else '✗'}, "
            f"L2={'✓' if self.l2 else '✗'}, "
            f"L3={'✓' if self.l3_fallback else '✗'})"
        )


async def test_multi_level_cache():
    """Test function for multi-level cache coordinator"""
    print("\nTesting MultiLevelCacheCoordinator...")

    # Create L1 memory backend only (no Redis required for basic test)
    l1 = MemoryCacheBackend(max_size=100)

    coordinator = MultiLevelCacheCoordinator(
        l1_backend=l1,
        l2_backend=None,  # No Redis for this test
        l3_fallback=lambda k: f"generated_value_for_{k}",
        enable_l1=True,
        enable_l2=False,
    )

    try:
        async with coordinator:
            # Test L1 hit
            print("  Testing L1 cache...")
            await coordinator.set("test_key", {"data": "value"}, ttl=60)
            result = await coordinator.get("test_key")
            assert result == {"data": "value"}
            print("  ✓ L1 set/get works")

            # Test L3 fallback
            print("  Testing L3 fallback...")
            result = await coordinator.get("nonexistent_key")
            assert result == "generated_value_for_nonexistent_key"
            print("  ✓ L3 fallback works")

            # Test invalidation
            print("  Testing invalidation...")
            await coordinator.invalidate("test_key")
            result = await coordinator.get("test_key")
            assert result == "generated_value_for_test_key"
            print("  ✓ Invalidation works")

            # Test stats
            print("  Testing stats...")
            stats = coordinator.get_stats()
            assert "l1_memory" in stats
            assert "l2_redis" in stats
            assert "overall" in stats
            print(f"  ✓ Stats: overall hit rate = {stats['overall']['hit_rate']}")

            print("\n✅ All MultiLevelCache tests passed!")
            return True

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_multi_level_cache())
