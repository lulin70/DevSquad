#!/usr/bin/env python3
"""
LLM Cache Base — Shared caching strategy for sync and async implementations.

Extracts non-I/O caching logic that is identical between LLMCache (sync) and
AsyncLLMCache (async):

- Cache key generation (SHA256 hashing strategy)
- TTL expiration calculation
- LRU eviction decision policy
- Statistics initialization and hit-rate calculation
- Configuration constants

Subclasses are responsible for the I/O layer (memory storage, disk persistence,
locking primitives). This avoids duplicating strategy logic across sync/async.

Usage (subclasses inherit, do not instantiate Base directly):
    from scripts.collaboration.llm_cache_base import LLMCacheBase

    class MyCache(LLMCacheBase):
        def get(self, prompt, backend, model): ...
        def set(self, prompt, response, backend, model): ...
"""

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class LLMCacheBase:
    """
    Base class for LLM response caches — shared strategy layer.

    Provides:
    - Cache key generation via SHA256 hashing
    - TTL expiration checks
    - LRU eviction policy decisions
    - Statistics tracking structure and hit-rate calculation
    - Common configuration constants

    Subclasses must implement I/O-bound methods (get/set/clear) using their
    preferred concurrency primitive (threading.RLock or asyncio.Lock).
    """

    # Configuration constants shared by sync and async implementations
    DEFAULT_TTL_SECONDS = 86400  # 24 hours
    DEFAULT_MAX_MEMORY_ENTRIES = 1000
    DEFAULT_HASH_LENGTH = 16  # Truncated SHA256 length for cache keys

    def __init__(
        self,
        cache_dir: str | None = None,  # noqa: ARG002  # Subclass creates the Path/directory
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_memory_entries: int = DEFAULT_MAX_MEMORY_ENTRIES,
    ):
        """
        Initialize base cache configuration.

        Args:
            cache_dir: Cache directory path (subclass creates the Path/directory)
            ttl_seconds: Time-to-live for cache entries in seconds
            max_memory_entries: Maximum number of entries in memory cache
        """
        self.ttl = ttl_seconds
        self.ttl_seconds = ttl_seconds  # Alias for async compat
        self.max_memory_entries = max_memory_entries

        # Statistics structure shared by both implementations.
        # Subclasses may extend with additional counters (e.g. expirations).
        self.stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }

    def generate_cache_key(
        self,
        prompt: str,
        backend: str,
        model: str,
        hash_length: int = DEFAULT_HASH_LENGTH,
    ) -> str:
        """
        Generate a deterministic cache key from prompt, backend, and model.

        Uses SHA256 to ensure:
        - Same inputs produce same key
        - Different inputs produce different keys
        - Fixed-length key (truncated to hash_length)

        Args:
            prompt: Input prompt text
            backend: LLM backend name (e.g. "openai")
            model: Model name (e.g. "gpt-4")
            hash_length: Truncated hash length (0 or negative = full hash)

        Returns:
            Cache key string
        """
        content = f"{backend}:{model}:{prompt}"
        full_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
        if hash_length and hash_length > 0:
            return full_hash[:hash_length]
        return full_hash

    def is_expired(self, timestamp: float, ttl_seconds: int | None = None) -> bool:
        """
        Check if a cache entry has expired based on its timestamp.

        Args:
            timestamp: Entry creation timestamp (time.time() epoch seconds)
            ttl_seconds: TTL override; if None uses instance default

        Returns:
            True if entry has expired, False otherwise
        """
        effective_ttl = ttl_seconds if ttl_seconds is not None else self.ttl
        return (time.time() - timestamp) > effective_ttl

    def calculate_age_hours(self, timestamp: float) -> float:
        """
        Calculate age of a cache entry in hours.

        Args:
            timestamp: Entry creation timestamp (epoch seconds)

        Returns:
            Age in hours
        """
        return (time.time() - timestamp) / 3600

    def should_evict(self, current_count: int) -> bool:
        """
        Determine if LRU eviction is needed.

        Args:
            current_count: Current number of entries in memory cache

        Returns:
            True if eviction is needed (count >= max_memory_entries)
        """
        return current_count >= self.max_memory_entries

    def init_stats(self, extra_keys: list[str] | None = None) -> dict[str, int]:
        """
        Initialize statistics dictionary with standard counters.

        Args:
            extra_keys: Additional counter names to include (e.g. "expirations")

        Returns:
            Statistics dictionary initialized to zero
        """
        base = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0,
        }
        if extra_keys:
            for key in extra_keys:
                base[key] = 0
        return base

    def calculate_hit_rate(self, hits: int, misses: int) -> float:
        """
        Calculate cache hit rate.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses

        Returns:
            Hit rate as a float between 0.0 and 1.0
        """
        total = hits + misses
        return hits / total if total > 0 else 0.0

    def format_hit_rate_percent(self, hits: int, misses: int) -> str:
        """
        Format hit rate as a percentage string.

        Args:
            hits: Number of cache hits
            misses: Number of cache misses

        Returns:
            Hit rate percentage string (e.g. "85.0%")
        """
        rate = self.calculate_hit_rate(hits, misses)
        return f"{rate * 100:.1f}%"

    def build_stats_dict(
        self,
        stats: dict[str, int],
        memory_entries: int,
        extra_fields: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Build a standardized statistics dictionary.

        Merges raw counters with computed fields (hit_rate, total_requests)
        and any extra implementation-specific fields.

        Args:
            stats: Raw statistics counters (hits, misses, sets, evictions)
            memory_entries: Current number of entries in memory cache
            extra_fields: Additional fields to merge into the result

        Returns:
            Complete statistics dictionary
        """
        hits = stats.get("hits", 0)
        misses = stats.get("misses", 0)
        total_requests = hits + misses
        hit_rate = self.calculate_hit_rate(hits, misses)

        result: dict[str, Any] = {
            "hits": hits,
            "misses": misses,
            "sets": stats.get("sets", 0),
            "evictions": stats.get("evictions", 0),
            "hit_rate": hit_rate,
            "total_requests": total_requests,
            "memory_entries": memory_entries,
            "max_memory_entries": self.max_memory_entries,
        }

        if extra_fields:
            result.update(extra_fields)

        return result
