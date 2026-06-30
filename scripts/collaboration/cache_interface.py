#!/usr/bin/env python3
"""
Cache Backend Interface Module

Defines the unified cache backend interface (ABC) for multi-level caching architecture.
Supports various backends: Memory, Redis, Memcached, Disk, etc.

Features:
- Abstract base class for cache backend implementations
- Unified API: get/set/delete/clear/stats
- TTL (Time-To-Live) support
- Serialization/Deserialization (JSON primary, pickle fallback for legacy data)
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
import time
from dataclasses import dataclass, field
from typing import Any

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
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
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
    expires_at: float | None = None
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
    def ttl_remaining(self) -> float | None:
        """Remaining TTL in seconds"""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.time()
        return max(0, remaining)


class Serializer:
    """
    Serialization utility for cache values.

    V3.8.1 P1: JSON is now the primary serialization format. Pickle is
    retained solely as a read-side fallback for legacy cache entries
    written before the migration. New writes always use JSON.

    The ``_serialize``/``_deserialize`` methods implement the JSON path
    and are the recommended entry points for new code. The legacy
    ``serialize``/``deserialize`` methods accept a ``format`` argument
    for backward compatibility but default to JSON.
    """

    # ------------------------------------------------------------------
    # JSON-first helpers (recommended for new code)
    # ------------------------------------------------------------------

    @staticmethod
    def _serialize(value: Any) -> bytes:
        """Serialize a value to JSON-encoded bytes.

        Args:
            value: Value to serialize (must be JSON-serializable; non-serializable
                values are coerced to str via ``default=str``).

        Returns:
            UTF-8 encoded JSON bytes.
        """
        try:
            return json.dumps(value, default=str).encode("utf-8")
        except (TypeError, ValueError) as e:
            logger.error("JSON serialization failed: %s", e)
            raise

    @staticmethod
    def _deserialize(data: bytes | str) -> Any:
        """Deserialize JSON bytes/str to a value, with pickle fallback.

        Attempts JSON first. If JSON parsing fails (e.g., the data was
        written by an older pickle-based cache), falls back to pickle
        and logs a warning. This enables transparent migration of
        existing cache entries.

        Args:
            data: Serialized data (bytes or str).

        Returns:
            Deserialized value.

        Raises:
            ValueError: If neither JSON nor pickle can decode the data.
        """
        # Try JSON first — decode bytes to str then parse
        try:
            text = data.decode("utf-8", errors="strict") if isinstance(data, bytes) else data
            return json.loads(text)
        except (json.JSONDecodeError, UnicodeDecodeError) as json_err:
            # Legacy pickle fallback for backward compat with old cache files.
            # Only bytes can be pickle data; str inputs have no pickle path.
            if isinstance(data, bytes):
                try:
                    import pickle  # nosec B403 — local import for trusted legacy cache deserialization only

                    value = pickle.loads(data)  # nosec B301  # noqa: S301 - trusted local cache
                    logger.warning(
                        "Deserialized legacy pickle cache entry via fallback; "
                        "it will be re-written as JSON on next set()."
                    )
                    return value
                except Exception as pickle_err:  # broad: pickle can raise many errors
                    logger.error(
                        "Both JSON and pickle deserialization failed. "
                        "JSON error: %s | pickle error: %s",
                        json_err,
                        pickle_err,
                    )
            raise ValueError(
                f"Unable to deserialize cache data with JSON or pickle: {json_err}"
            ) from json_err

    # ------------------------------------------------------------------
    # Legacy format-aware API (backward compatible)
    # ------------------------------------------------------------------

    @staticmethod
    def serialize(value: Any, format: str = "json", compress: bool = False) -> bytes:
        """
        Serialize value to bytes.

        Args:
            value: Value to serialize
            format: Serialization format ('json' default; 'pickle' deprecated)
            compress: Whether to compress with gzip

        Returns:
            Serialized bytes
        """
        try:
            if format == "json":
                data = Serializer._serialize(value)
            elif format == "pickle":
                # Deprecated: kept for backward compat with callers that
                # explicitly request pickle. New writes should use JSON.
                import pickle  # nosec B403 — local import for explicit pickle format (backward compat)

                logger.warning(
                    "Pickle serialization requested (deprecated); prefer JSON."
                )
                data = pickle.dumps(value)
            else:
                raise ValueError(f"Unsupported serialization format: {format}")

            if compress:
                data = gzip.compress(data)

            return data
        except (TypeError, ValueError, OSError) as e:
            logger.error("Serialization failed: %s", e)
            raise

    @staticmethod
    def deserialize(data: bytes, format: str = "json", compressed: bool = False) -> Any:
        """
        Deserialize bytes to value.

        Args:
            data: Serialized bytes
            format: Serialization format ('json' default; 'pickle' deprecated)
            compressed: Whether data is gzip compressed

        Returns:
            Deserialized value
        """
        try:
            if compressed:
                data = gzip.decompress(data)

            if format == "json":
                return Serializer._deserialize(data)
            elif format == "pickle":
                # Deprecated: kept for backward compat with callers that
                # explicitly request pickle. _deserialize already falls
                # back to pickle for legacy data, so this branch is only
                # reached when the caller explicitly opts in.
                import pickle  # nosec B403 — local import for explicit pickle format (caller opts in)

                logger.warning(
                    "Pickle deserialization requested (deprecated); prefer JSON."
                )
                return pickle.loads(data)  # nosec B301  # noqa: S301 - trusted local cache
            else:
                raise ValueError(f"Unsupported deserialization format: {format}")
        except (TypeError, ValueError, OSError, json.JSONDecodeError) as e:
            logger.error("Deserialization failed: %s", e)
            raise


# NOTE: CacheBackendInterface is the low-level storage interface used by the multi-level
# cache coordinator. CacheProvider (in protocols.py) is the high-level LLM cache interface
# used by the dispatch pipeline. They serve different layers:
# - CacheBackendInterface: storage-level (key → value caching)
# - CacheProvider: business-level (prompt → response caching)
# Do NOT merge these — they are intentionally separate abstractions.


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
    async def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value or None if not found/expired
        """
        pass

    @abc.abstractmethod
    async def set(self, key: str, value: Any, ttl: int | None = None) -> bool:
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
    async def stats(self) -> dict[str, Any]:
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

    async def mget(self, keys: list[str]) -> list[Any | None]:
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

    async def mset(self, mapping: dict[str, Any], ttl: int | None = None) -> bool:
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

    async def touch(self, key: str, ttl: int | None = None) -> bool:
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

    async def increment(self, key: str, delta: int = 1) -> int | None:
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
            logger.warning("Cannot increment non-numeric value for key: %s", key)
            return None

    async def __aenter__(self) -> "CacheBackendInterface":
        """Async context manager entry"""
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: Any) -> bool | None:
        """Async context manager exit"""
        await self.close()
        return False

    def __repr__(self) -> str:
        """String representation"""
        return f"{self.__class__.__name__}()"
