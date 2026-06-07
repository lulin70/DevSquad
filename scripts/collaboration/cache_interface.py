#!/usr/bin/env python3
"""
Cache Backend Interface Module

Defines the unified cache backend interface (ABC) for multi-level caching architecture.
Supports various backends: Memory, Redis, Memcached, Disk, etc.

Features:
- Abstract base class for cache backend implementations
- Unified API: get/set/delete/clear/stats
- TTL (Time-To-Live) support
- Serialization/Deserialization (JSON/Pickle)
- Async-first design

Usage:
    from scripts.collaboration.cache_interface import CacheBackendInterface, CacheStats

    class MyCustomBackend(CacheBackendInterface):
        async def get(self, key: str) -> Optional[Any]:
            # Implementation
            pass
"""

import abc
import gzip
import json
import logging
import pickle
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type, Union

logger = logging.getLogger(__name__)


@dataclass
class CacheStats:
    """Cache statistics data structure"""

    hits: int = 0
    misses: int = 0
    sets: int = 0
    deletes: int = 0
    evictions: int = 0
    errors: int = 0
    total_size_bytes: int = 0
    entry_count: int = 0
    hit_rate: float = 0.0
    avg_latency_ms: float = 0.0
    last_operation_time: float = 0.0
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "errors": self.errors,
            "total_size_bytes": self.total_size_bytes,
            "entry_count": self.entry_count,
            "hit_rate": f"{self.hit_rate * 100:.1f}%",
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "last_operation_time": self.last_operation_time,
            **self.extra,
        }

    @property
    def total_requests(self) -> int:
        """Total number of requests"""
        return self.hits + self.misses


@dataclass
class CacheEntry:
    """Cache entry with metadata"""

    key: str
    value: Any
    created_at: float = field(default_factory=time.time)
    expires_at: Optional[float] = None
    size_bytes: int = 0
    access_count: int = 0
    last_accessed: float = 0.0

    def is_expired(self) -> bool:
        """Check if entry has expired"""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    def age_seconds(self) -> float:
        """Get age in seconds"""
        return time.time() - self.created_at

    @property
    def ttl_remaining(self) -> Optional[float]:
        """Remaining TTL in seconds"""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.time()
        return max(0, remaining)


class Serializer:
    """
    Serialization utility for cache values.

    Supports JSON and Pickle serialization formats.
    """

    @staticmethod
    def serialize(value: Any, format: str = "json", compress: bool = False) -> bytes:
        """
        Serialize value to bytes.

        Args:
            value: Value to serialize
            format: Serialization format ('json' or 'pickle')
            compress: Whether to compress with gzip

        Returns:
            Serialized bytes
        """
        try:
            if format == "json":
                data = json.dumps(value, default=str).encode("utf-8")
            elif format == "pickle":
                data = pickle.dumps(value)
            else:
                raise ValueError(f"Unsupported serialization format: {format}")

            if compress:
                data = gzip.compress(data)

            return data
        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise

    @staticmethod
    def deserialize(data: bytes, format: str = "json", compressed: bool = False) -> Any:
        """
        Deserialize bytes to value.

        Args:
            data: Serialized bytes
            format: Serialization format ('json' or 'pickle')
            compressed: Whether data is gzip compressed

        Returns:
            Deserialized value
        """
        try:
            if compressed:
                data = gzip.decompress(data)

            if format == "json":
                return json.loads(data.decode("utf-8"))
            elif format == "pickle":
                return pickle.loads(data)
            else:
                raise ValueError(f"Unsupported deserialization format: {format}")
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise


class CacheBackendInterface(abc.ABC):
    """
    Abstract base class for cache backend implementations.

    All cache backends must implement this interface to ensure
    consistent behavior across different storage mechanisms.

    Supported operations:
    - get: Retrieve cached value
    - set: Store value with optional TTL
    - delete: Remove specific entry
    - clear: Clear all entries
    - stats: Get cache statistics
    - close: Cleanup resources

    Example implementation:

        class RedisCacheBackend(CacheBackendInterface):
            async def get(self, key: str) -> Optional[Any]:
                # Redis-specific implementation
                pass
    """

    @abc.abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abc.abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> bool:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            TTL: Time-to-live in seconds (None = no expiration)

        Returns:
            True if successful, False otherwise
        """
        pass

    @abc.abstractmethod
    async def delete(self, key: str) -> bool:
        """
        Delete entry from cache.

        Args:
            key: Cache key

        Returns:
            True if deleted, False if not found
        """
        pass

    @abc.abstractmethod
    async def clear(self) -> None:
        """
        Clear all entries from cache.
        """
        pass

    @abc.abstractmethod
    async def stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary containing cache statistics
        """
        pass

    @abc.abstractmethod
    async def close(self) -> None:
        """
        Close connection and cleanup resources.
        """
        pass

    async def mget(self, keys: List[str]) -> List[Optional[Any]]:
        """
        Batch get multiple values (default implementation).

        Override in subclasses for better performance (e.g., pipeline).

        Args:
            keys: List of cache keys

        Returns:
            List of values (same order as keys, None for misses)
        """
        results = []
        for key in keys:
            result = await self.get(key)
            results.append(result)
        return results

    async def mset(self, mapping: Dict[str, Any], ttl: Optional[int] = None) -> bool:
        """
        Batch set multiple values (default implementation).

        Override in subclasses for better performance (e.g., pipeline).

        Args:
            mapping: Dictionary of key-value pairs
            TTL: Time-to-live for all entries

        Returns:
            True if all successful, False otherwise
        """
        success = True
        for key, value in mapping.items():
            result = await self.set(key, value, ttl)
            if not result:
                success = False
        return success

    async def exists(self, key: str) -> bool:
        """
        Check if key exists in cache.

        Args:
            key: Cache key

        Returns:
            True if exists and not expired
        """
        value = await self.get(key)
        return value is not None

    async def touch(self, key: str, ttl: Optional[int] = None) -> bool:
        """
        Update TTL for existing key without changing value.

        Args:
            key: Cache key
            TTL: New TTL (None = keep existing)

        Returns:
            True if updated, False if not found
        """
        value = await self.get(key)
        if value is not None:
            return await self.set(key, value, ttl)
        return False

    async def increment(self, key: str, delta: int = 1) -> Optional[int]:
        """
        Increment numeric value (default implementation).

        Override in subclasses for atomic operations.

        Args:
            key: Cache key (must hold numeric value)
            delta: Amount to increment

        Returns:
            New value or None if not found/not numeric
        """
        value = await self.get(key)
        if value is None:
            return None
        try:
            new_value = int(value) + delta
            await self.set(key, new_value)
            return new_value
        except (ValueError, TypeError):
            logger.warning(f"Cannot increment non-numeric value for key: {key}")
            return None

    async def __aenter__(self):
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()
        return False

    def __repr__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}()"
