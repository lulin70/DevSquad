#!/usr/bin/env python3
"""
Redis Cache Backend Module

Provides Redis-based cache backend implementation with:
- Connection pool management
- Auto-reconnection mechanism
- Pipeline batch operations
- Key namespace isolation (prefix)
- Optional gzip compression
- TTL support
- Comprehensive error handling and logging

Usage:
    from scripts.collaboration.redis_cache import RedisCacheBackend

    redis = RedisCacheBackend(
        redis_url="redis://localhost:6379/0",
        prefix="devsquad:",
        default_ttl=3600,
        enable_compression=True
    )

    await redis.set("key", {"data": "value"}, ttl=60)
    value = await redis.get("key")
"""

import asyncio
import contextlib
import logging
import os
import time
from typing import Any
from urllib.parse import urlparse, urlunparse

from .cache_interface import CacheBackendInterface, CacheStats, Serializer

logger = logging.getLogger(__name__)


class RedisConnectionError(Exception):
    """Custom exception for Redis connection errors"""

    pass


def _mask_redis_url(url: str) -> str:
    """Mask password in Redis URL for safe logging/stats exposure.

    redis://:secret@host:6379/0  →  redis://***@host:6379/0
    redis://user:secret@host:6379/0  →  redis://user:***@host:6379/0
    redis://host:6379/0  →  redis://host:6379/0  (no password, unchanged)
    """
    try:
        parsed = urlparse(url)
        if parsed.password:
            masked_netloc = parsed.hostname or ""
            if parsed.port:
                masked_netloc = f"{masked_netloc}:{parsed.port}"
            masked_netloc = f"{parsed.username}:***@{masked_netloc}" if parsed.username else f":***@{masked_netloc}"
            return urlunparse(parsed._replace(netloc=masked_netloc))
    except Exception:
        pass
    return url


class RedisCacheBackend(CacheBackendInterface):
    """
    Redis-based cache backend with connection pooling and auto-reconnect.

    Features:
    - Connection pool with configurable max connections
    - Automatic reconnection on failure
    - Pipeline support for batch operations
    - Key namespace isolation via prefix
    - Optional gzip compression for large values
    - Detailed statistics tracking
    - Graceful degradation when Redis unavailable

    Configuration via environment variables:
    - REDIS_URL: Redis connection string (default: redis://localhost:6379/0)
    - CACHE_PREFIX: Key namespace prefix (default: devsquad:)
    - CACHE_TTL: Default TTL in seconds (default: 3600)

    Example:

        async with RedisCacheBackend() as redis:
            await redis.set("user:1", {"name": "Alice"})
            user = await redis.get("user:1")
            stats = await redis.stats()
    """

    def __init__(
        self,
        redis_url: str | None = None,
        prefix: str = "devsquad:",
        default_ttl: int = 3600,
        max_connections: int = 10,
        enable_compression: bool = False,
        serialization_format: str = "json",
        retry_attempts: int = 3,
        retry_delay: float = 1.0,
        health_check_interval: float = 30.0,
    ) -> None:
        """
        Initialize Redis cache backend.

        Args:
            redis_url: Redis connection URL (or REDIS_URL env var)
            prefix: Key namespace prefix for isolation
            default_ttl: Default time-to-live in seconds
            max_connections: Maximum connections in pool
            enable_compression: Enable gzip compression for values
            serialization_format: 'json' or 'pickle'
            retry_attempts: Number of retry attempts on failure
            retry_delay: Delay between retries (seconds)
            health_check_interval: Interval between health checks
        """
        self.redis_url: str = redis_url or os.getenv("REDIS_URL") or "redis://localhost:6379/0"
        self.prefix = os.getenv("CACHE_PREFIX", prefix)
        self.default_ttl = int(os.getenv("CACHE_TTL", str(default_ttl)))
        self.max_connections = max_connections
        self.enable_compression = enable_compression
        self.serialization_format = serialization_format
        self.retry_attempts = retry_attempts
        self.retry_delay = retry_delay
        self.health_check_interval = health_check_interval

        # Connection state
        self._pool: Any = None
        self._client: Any = None
        self._connected = False
        self._last_health_check = 0.0

        # Statistics
        self._stats = CacheStats()
        self._latencies: list[float] = []

        logger.info(
            f"RedisCacheBackend initialized: url={_mask_redis_url(self.redis_url)}, prefix={self.prefix}, ttl={self.default_ttl}s"
        )

    def _prefixed_key(self, key: str) -> str:
        """Add namespace prefix to key"""
        return f"{self.prefix}{key}"

    def _strip_prefix(self, key: str | bytes) -> str:
        """Remove namespace prefix from key"""
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        if key.startswith(self.prefix):
            return key[len(self.prefix) :]
        return key

    async def _get_client(self) -> Any:
        """
        Get or create Redis client with connection pool.

        Implements lazy initialization and auto-reconnect.
        """
        if self._client is not None and self._connected:
            return self._client

        try:
            import redis.asyncio as aioredis
        except ImportError:
            raise ImportError("redis package required. Install with: pip install redis[asyncio]") from None

        try:
            self._pool = aioredis.ConnectionPool.from_url(
                self.redis_url,
                max_connections=self.max_connections,
                decode_responses=False,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
                retry_on_timeout=True,
            )
            self._client = aioredis.Redis(connection_pool=self._pool)
            await self._client.ping()
            self._connected = True
            logger.info("Connected to Redis: %s", _mask_redis_url(self.redis_url))
            return self._client
        except Exception as e:
            self._connected = False
            logger.error("Failed to connect to Redis: %s", e)
            raise RedisConnectionError(f"Cannot connect to Redis: {e}") from e

    async def _execute_with_retry(self, operation_name: str, operation_func: Any, *args: Any, **kwargs: Any) -> Any:
        """
        Execute operation with automatic retry on failure.

        Args:
            operation_name: Name for logging
            operation_func: Async function to execute
            *args, **kwargs: Arguments for operation

        Returns:
            Operation result or None on failure
        """
        last_error = None

        for attempt in range(self.retry_attempts):
            try:
                start_time = time.time()

                client = await self._get_client()
                result = await operation_func(client, *args, **kwargs)

                latency_ms = (time.time() - start_time) * 1000
                self._latencies.append(latency_ms)
                if len(self._latencies) > 1000:
                    self._latencies = self._latencies[-500:]

                return result

            except (
                RedisConnectionError,
                ConnectionError,
                TimeoutError,
                OSError,
                ValueError,
                KeyError,
                TypeError,
                AttributeError,
                RuntimeError,
            ) as e:
                last_error = e
                self._stats.errors += 1

                if attempt < self.retry_attempts - 1:
                    logger.warning(
                        "%s failed (attempt %s/%s): %s",
                        operation_name,
                        attempt + 1,
                        self.retry_attempts,
                        e,
                    )
                    await asyncio.sleep(self.retry_delay * (attempt + 1))

                    # Try to reconnect
                    try:
                        await self._reconnect()
                    except (ConnectionError, TimeoutError, OSError, RuntimeError) as reconnect_error:
                        logger.error("Reconnection failed: %s", reconnect_error)

        logger.error("%s failed after %s attempts: %s", operation_name, self.retry_attempts, last_error)
        return None

    async def _reconnect(self) -> Any:
        """Reconnect to Redis"""
        if self._client:
            with contextlib.suppress(OSError, RuntimeError, AttributeError):
                await self._client.close()

        if self._pool:
            with contextlib.suppress(OSError, RuntimeError, AttributeError):
                await self._pool.disconnect()

        self._client = None
        self._pool = None
        self._connected = False

        client = await self._get_client()
        return client

    async def get(self, key: str) -> Any | None:
        """
        Get value from Redis with decompression if needed.

        Args:
            key: Cache key (without prefix)

        Returns:
            Cached value or None if not found/expired
        """
        prefixed_key = self._prefixed_key(key)

        async def _do_get(client: Any) -> Any | None:
            data = await client.get(prefixed_key)
            if data is None:
                return None

            try:
                value = Serializer.deserialize(
                    data,
                    format=self.serialization_format,
                    compressed=self.enable_compression,
                )
                self._stats.hits += 1
                return value
            except (ValueError, TypeError, AttributeError) as e:
                logger.error("Failed to deserialize cached value for key %s: %s", key, e)
                self._stats.errors += 1
                return None

        result = await self._execute_with_retry("GET", _do_get)
        if result is None and self._stats.errors == 0:
            self._stats.misses += 1

        return result

    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """
        Set value in Redis with compression if enabled.

        Args:
            key: Cache key (without prefix)
            value: Value to cache
            ttl: Time-to-live in seconds (None = use default)

        Returns:
            True if successful, False otherwise
        """
        prefixed_key = self._prefixed_key(key)
        actual_ttl = ttl if ttl is not None else self.default_ttl

        try:
            serialized = Serializer.serialize(
                value,
                format=self.serialization_format,
                compress=self.enable_compression,
            )
        except (ValueError, TypeError) as e:
            logger.error("Failed to serialize value for key %s: %s", key, e)
            self._stats.errors += 1
            return False

        async def _do_set(client: Any) -> bool:
            await client.set(prefixed_key, serialized, ex=actual_ttl)
            self._stats.sets += 1
            self._stats.total_size_bytes += len(serialized)
            self._stats.entry_count += 1
            return True

        result = await self._execute_with_retry("SET", _do_set)
        return result if result is not None else False

    async def delete(self, key: str) -> bool:
        """
        Delete entry from Redis.

        Args:
            key: Cache key (without prefix)

        Returns:
            True if deleted, False if not found
        """
        prefixed_key = self._prefixed_key(key)

        async def _do_delete(client: Any) -> bool:
            result = await client.delete(prefixed_key)
            if result > 0:
                self._stats.deletes += 1
                self._stats.entry_count = max(0, self._stats.entry_count - 1)
                return True
            return False

        result = await self._execute_with_retry("DELETE", _do_delete)
        return result if result is not None else False

    async def clear(self) -> None:
        """
        Clear all entries with configured prefix.
        Uses SCAN for safe iteration (avoids blocking).
        """

        async def _do_clear(client: Any) -> int:
            cursor = 0
            total_deleted = 0

            while True:
                cursor, keys = await client.scan(cursor, match=f"{self.prefix}*", count=100)
                if keys:
                    deleted = await client.delete(*keys)
                    total_deleted += deleted

                if cursor == 0:
                    break

            self._stats.entry_count = 0
            logger.info("Cleared %s entries from Redis", total_deleted)
            return total_deleted

        await self._execute_with_retry("CLEAR", _do_clear)

    async def mget(self, keys: list[str]) -> list[Any | None]:
        """
        Batch get using pipeline for performance.

        Args:
            keys: List of cache keys (without prefix)

        Returns:
            List of values (same order as keys, None for misses)
        """
        if not keys:
            return []

        prefixed_keys = [self._prefixed_key(k) for k in keys]

        async def _do_mget(client: Any) -> list[Any | None]:
            pipeline = client.pipeline(transaction=False)
            for pk in prefixed_keys:
                pipeline.get(pk)
            results = await pipeline.execute()

            deserialized: list[Any] = []
            for i, data in enumerate(results):
                if data is None:
                    deserialized.append(None)
                    self._stats.misses += 1
                else:
                    try:
                        value = Serializer.deserialize(
                            data,
                            format=self.serialization_format,
                            compressed=self.enable_compression,
                        )
                        deserialized.append(value)
                        self._stats.hits += 1
                    except (ValueError, TypeError, AttributeError) as e:
                        logger.error("Failed to deserialize mget result[%s]: %s", i, e)
                        deserialized.append(None)
                        self._stats.errors += 1

            return deserialized

        result = await self._execute_with_retry("MGET", _do_mget)
        return result if result is not None else [None] * len(keys)

    async def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
        """
        Batch set using pipeline for performance.

        Args:
            mapping: Dictionary of key-value pairs (keys without prefix)
            ttl: Time-to-live for all entries

        Returns:
            True if all successful, False otherwise
        """
        if not mapping:
            return True

        actual_ttl = ttl if ttl is not None else self.default_ttl

        try:
            serialized_mapping = {}
            sizes = {}
            for k, v in mapping.items():
                pk = self._prefixed_key(k)
                data = Serializer.serialize(v, format=self.serialization_format, compress=self.enable_compression)
                serialized_mapping[pk] = data
                sizes[k] = len(data)
        except (ValueError, TypeError) as e:
            logger.error("Failed to serialize batch values: %s", e)
            self._stats.errors += len(mapping)
            return False

        async def _do_mset(client: Any) -> bool:
            pipeline = client.pipeline(transaction=False)
            for pk, data in serialized_mapping.items():
                pipeline.set(pk, data, ex=actual_ttl)
            results = await pipeline.execute()

            success = all(r is True or r == "OK" for r in results)
            if success:
                self._stats.sets += len(mapping)
                self._stats.total_size_bytes += sum(sizes.values())
                self._stats.entry_count += len(mapping)
            return success

        result = await self._execute_with_retry("MSET", _do_mset)
        return result if result is not None else False

    async def stats(self) -> dict[str, Any]:
        """
        Get comprehensive cache statistics.

        Returns:
            Dictionary containing statistics including:
            - hits, misses, hit_rate
            - entry_count, total_size_bytes
            - avg_latency_ms
            - connection_status
            - redis_info (if available)
        """
        total_requests = self._stats.total_requests
        self._stats.hit_rate = self._stats.hits / total_requests if total_requests > 0 else 0.0

        self._stats.avg_latency_ms = sum(self._latencies) / len(self._latencies) if self._latencies else 0.0

        stats_dict = self._stats.to_dict()
        stats_dict["backend_type"] = "redis"
        stats_dict["redis_url"] = _mask_redis_url(self.redis_url)
        stats_dict["prefix"] = self.prefix
        stats_dict["default_ttl"] = self.default_ttl
        stats_dict["compression_enabled"] = self.enable_compression
        stats_dict["serialization_format"] = self.serialization_format
        stats_dict["connected"] = self._connected

        # Try to get Redis INFO
        redis_info: dict[str, Any] = {}
        if self._connected and self._client:
            try:
                info = await self._client.info()
                redis_info = {
                    "used_memory_human": info.get("used_memory_human", "N/A"),
                    "total_commands_processed": info.get("total_commands_processed", 0),
                    "connected_clients": info.get("connected_clients", 0),
                    "uptime_in_seconds": info.get("uptime_in_seconds", 0),
                }
            except Exception as e:
                logger.debug("Failed to get Redis INFO: %s", e)
                redis_info["error"] = str(e)

        stats_dict["redis_info"] = redis_info
        return stats_dict

    async def close(self) -> None:
        """Close connection pool and cleanup resources"""
        try:
            if self._client:
                await self._client.close()
            if self._pool:
                await self._pool.disconnect()
        except (ConnectionError, OSError, RuntimeError) as e:
            logger.warning("Error closing Redis connection: %s", e)
        finally:
            self._client = None
            self._pool = None
            self._connected = False
            logger.info("Redis connection closed")

    async def health_check(self) -> dict[str, Any]:
        """
        Perform health check on Redis connection.

        Returns:
            Health status dictionary
        """
        current_time = time.time()

        # Throttle health checks
        if current_time - self._last_health_check < self.health_check_interval:
            return {"status": "skipped", "reason": "Too frequent"}

        self._last_health_check = current_time

        health = {
            "status": "unknown",
            "timestamp": current_time,
            "url": _mask_redis_url(self.redis_url),
        }

        try:
            client = await self._get_client()
            start = time.time()
            pong = await client.ping()
            latency_ms = (time.time() - start) * 1000

            if pong:
                health.update(
                    {
                        "status": "healthy",
                        "latency_ms": round(latency_ms, 2),
                        "connected": True,
                    }
                )
            else:
                health["status"] = "unhealthy"

        except (RedisConnectionError, ConnectionError, TimeoutError, OSError, RuntimeError) as e:
            health.update(
                {
                    "status": "unhealthy",
                    "error": str(e),
                    "connected": False,
                }
            )
            self._connected = False

        return health

    async def scan_keys(self, pattern: str = "*") -> list[str]:
        """
        Scan keys matching pattern (with prefix).

        Uses SCAN for non-blocking iteration.

        Args:
            pattern: Glob pattern (applied after prefix)

        Returns:
            List of keys (without prefix)
        """
        full_pattern = f"{self.prefix}{pattern}"
        keys = []

        async def _do_scan(client: Any) -> list[str]:
            cursor = 0
            while True:
                cursor, found_keys = await client.scan(cursor, match=full_pattern, count=100)
                keys.extend([self._strip_prefix(k) for k in found_keys])
                if cursor == 0:
                    break
            return keys

        await self._execute_with_retry("SCAN", _do_scan)
        return keys

    def __repr__(self) -> str:
        return f"RedisCacheBackend(url={_mask_redis_url(self.redis_url)}, prefix={self.prefix}, connected={self._connected})"


class SyncRedisCacheWrapper:
    """Synchronous wrapper for RedisCacheBackend.

    Allows the async Redis backend to be used from synchronous code (LLMCache).
    Automatically handles event loop management.
    """

    def __init__(
        self, redis_url: str, prefix: str = "devsquad:", default_ttl: int = 3600, compression: bool = False
    ) -> None:
        self._redis_url = redis_url
        self._prefix = prefix
        self._default_ttl = default_ttl
        self._compression = compression
        self._backend: Any = None
        self._initialized = False

    def _ensure_backend(self) -> None:
        """Lazy initialization of the async Redis backend."""
        if not self._initialized:
            try:
                self._backend = RedisCacheBackend(
                    redis_url=self._redis_url,
                    prefix=self._prefix,
                    default_ttl=self._default_ttl,
                    enable_compression=self._compression,
                )
                self._initialized = True
            except (ImportError, AttributeError, RuntimeError, OSError) as e:
                import logging

                logging.getLogger(__name__).warning("Redis cache backend init failed: %s", e)
                self._backend = None
                self._initialized = True  # Don't retry

    def _run_async(self, coro: Any) -> Any:
        """Run an async coroutine from synchronous context."""
        self._ensure_backend()
        if self._backend is None:
            return None
        try:
            import asyncio

            try:
                asyncio.get_running_loop()
                # We're inside an existing event loop - use thread
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, coro).result()
            except RuntimeError:
                # No running loop - safe to use asyncio.run
                return asyncio.run(coro)
        except (RuntimeError, ConnectionError, OSError) as e:
            import logging

            logging.getLogger(__name__).debug("Redis cache operation failed: %s", e)
            return None

    def get(self, key: str) -> Any:
        """Get a value from Redis cache (sync)."""
        return self._run_async(self._backend.get(key)) if self._backend else None

    def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set a value in Redis cache (sync)."""
        result = self._run_async(self._backend.set(key, value, ttl=ttl)) if self._backend else False
        return result if result is not None else False

    def delete(self, key: str) -> bool:
        """Delete a key from Redis cache (sync)."""
        result = self._run_async(self._backend.delete(key)) if self._backend else False
        return result if result is not None else False

    def clear(self) -> None:
        """Clear all keys in Redis cache (sync)."""
        self._run_async(self._backend.clear()) if self._backend else None

    def health_check(self) -> dict[str, Any]:
        """Check Redis health (sync)."""
        result: dict[str, Any] = self._run_async(self._backend.health_check()) if self._backend else {}
        return result if result else {"status": "unavailable"}

    def close(self) -> None:
        """Close Redis connection (sync)."""
        self._run_async(self._backend.close()) if self._backend else None


async def test_redis_cache_backend() -> bool:
    """Test function for Redis cache backend"""
    print("Testing RedisCacheBackend...")

    backend = RedisCacheBackend(
        redis_url="redis://localhost:6379/0",
        prefix="test:",
        enable_compression=False,
    )

    try:
        async with backend:
            # Test set/get
            print("  Testing set/get...")
            await backend.set("key1", {"data": "value1"}, ttl=60)
            result = await backend.get("key1")
            assert result == {"data": "value1"}, f"Expected {{'data': 'value1'}}, got {result}"
            print("  ✓ Basic set/get works")

            # Test delete
            print("  Testing delete...")
            deleted = await backend.delete("key1")
            assert deleted is True
            result = await backend.get("key1")
            assert result is None
            print("  ✓ Delete works")

            # Test mset/mget
            print("  Testing batch operations...")
            await backend.mset({"k1": "v1", "k2": "v2", "k3": "v3"}, ttl=30)
            results = await backend.mget(["k1", "k2", "k3"])
            assert results == ["v1", "v2", "v3"], f"Batch get failed: {results}"
            print("  ✓ Batch operations work")

            # Test stats
            print("  Testing stats...")
            stats = await backend.stats()
            assert "hits" in stats
            assert "hit_rate" in stats
            print(f"  ✓ Stats: {stats['hit_rate']} hit rate")

            # Test clear
            print("  Testing clear...")
            await backend.clear()
            remaining = await backend.scan_keys("*")
            assert len(remaining) == 0
            print("  ✓ Clear works")

            print("\n✅ All Redis cache tests passed!")
            return True

    except ImportError as e:
        print(f"\n⚠️  Skipping test (redis not installed): {e}")
        print("   Install with: pip install redis[asyncio]")
        return False
    except (ConnectionError, TimeoutError, OSError, ValueError, RuntimeError) as e:  # Broad catch: test harness
        print(f"\n❌ Test failed: {e}")
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_redis_cache_backend())
