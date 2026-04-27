#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Async LLM Cache Module

Provides asynchronous caching for LLM API responses to reduce costs and improve performance.
Compatible with asyncio-based applications.

Features:
- Async memory + disk dual-layer caching
- TTL-based expiration
- LRU eviction policy
- Thread-safe operations
- Statistics tracking

Usage:
    from scripts.collaboration import get_async_llm_cache
    
    cache = get_async_llm_cache()
    
    # Try to get from cache
    response = await cache.get(prompt, backend="openai", model="gpt-4")
    if not response:
        # Call API
        response = await your_async_api_call(prompt)
        # Save to cache
        await cache.set(prompt, response, backend="openai", model="gpt-4")
"""

import asyncio
import hashlib
import json
import logging
import os
import time
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from collections import OrderedDict

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """Cache entry with metadata"""
    prompt: str
    response: str
    backend: str
    model: str
    timestamp: float
    ttl_seconds: int
    hit_count: int = 0
    
    def is_expired(self) -> bool:
        """Check if entry has expired"""
        age = time.time() - self.timestamp
        return age > self.ttl_seconds
    
    def age_hours(self) -> float:
        """Get age in hours"""
        return (time.time() - self.timestamp) / 3600


class AsyncLLMCache:
    """
    Async LLM response cache with memory and disk persistence.
    
    Thread-safe and asyncio-compatible implementation.
    """
    
    def __init__(
        self,
        cache_dir: str = "data/llm_cache",
        ttl_seconds: int = 86400,  # 24 hours
        max_memory_entries: int = 1000
    ):
        """
        Initialize async cache.
        
        Args:
            cache_dir: Directory for disk cache
            ttl_seconds: Time-to-live for cache entries (default: 24 hours)
            max_memory_entries: Maximum entries in memory cache
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        self.ttl_seconds = ttl_seconds
        self.max_memory_entries = max_memory_entries
        
        # Memory cache (LRU)
        self._memory_cache: OrderedDict[str, CacheEntry] = OrderedDict()
        
        # Statistics
        self._stats = {
            "hits": 0,
            "misses": 0,
            "sets": 0,
            "evictions": 0
        }
        
        # Lock for thread safety
        self._lock = asyncio.Lock()
        
        logger.info(f"AsyncLLMCache initialized: dir={cache_dir}, ttl={ttl_seconds}s, max_memory={max_memory_entries}")
    
    def _generate_cache_key(self, prompt: str, backend: str, model: str) -> str:
        """Generate cache key from prompt, backend, and model"""
        content = f"{backend}:{model}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()
    
    def _get_disk_path(self, cache_key: str) -> Path:
        """Get disk cache file path"""
        # Use first 2 chars for subdirectory to avoid too many files in one dir
        subdir = cache_key[:2]
        return self.cache_dir / subdir / f"{cache_key}.json"
    
    async def get(
        self,
        prompt: str,
        backend: str,
        model: str
    ) -> Optional[str]:
        """
        Get cached response asynchronously.
        
        Args:
            prompt: Input prompt
            backend: LLM backend (e.g., "openai", "anthropic")
            model: Model name (e.g., "gpt-4", "claude-3")
        
        Returns:
            Cached response or None if not found/expired
        """
        cache_key = self._generate_cache_key(prompt, backend, model)
        
        async with self._lock:
            # Try memory cache first
            if cache_key in self._memory_cache:
                entry = self._memory_cache[cache_key]
                
                if not entry.is_expired():
                    # Move to end (LRU)
                    self._memory_cache.move_to_end(cache_key)
                    entry.hit_count += 1
                    self._stats["hits"] += 1
                    logger.debug(f"Memory cache hit: {cache_key[:8]}... (age: {entry.age_hours():.1f}h)")
                    return entry.response
                else:
                    # Expired, remove from memory
                    del self._memory_cache[cache_key]
                    logger.debug(f"Memory cache expired: {cache_key[:8]}...")
            
            # Try disk cache
            disk_path = self._get_disk_path(cache_key)
            if disk_path.exists():
                try:
                    # Read from disk asynchronously
                    loop = asyncio.get_event_loop()
                    data = await loop.run_in_executor(None, disk_path.read_text)
                    entry_dict = json.loads(data)
                    entry = CacheEntry(**entry_dict)
                    
                    if not entry.is_expired():
                        # Load into memory cache
                        self._memory_cache[cache_key] = entry
                        self._memory_cache.move_to_end(cache_key)
                        entry.hit_count += 1
                        self._stats["hits"] += 1
                        
                        # Evict if memory cache is full
                        await self._evict_if_needed()
                        
                        logger.debug(f"Disk cache hit: {cache_key[:8]}... (age: {entry.age_hours():.1f}h)")
                        return entry.response
                    else:
                        # Expired, delete from disk
                        await loop.run_in_executor(None, disk_path.unlink)
                        logger.debug(f"Disk cache expired: {cache_key[:8]}...")
                except Exception as e:
                    logger.warning(f"Error reading disk cache: {e}")
            
            # Cache miss
            self._stats["misses"] += 1
            logger.debug(f"Cache miss: {cache_key[:8]}...")
            return None
    
    async def set(
        self,
        prompt: str,
        response: str,
        backend: str,
        model: str,
        ttl_seconds: Optional[int] = None
    ):
        """
        Set cache entry asynchronously.
        
        Args:
            prompt: Input prompt
            response: LLM response
            backend: LLM backend
            model: Model name
            ttl_seconds: Custom TTL (optional, uses default if not provided)
        """
        cache_key = self._generate_cache_key(prompt, backend, model)
        ttl = ttl_seconds or self.ttl_seconds
        
        entry = CacheEntry(
            prompt=prompt,
            response=response,
            backend=backend,
            model=model,
            timestamp=time.time(),
            ttl_seconds=ttl,
            hit_count=0
        )
        
        async with self._lock:
            # Add to memory cache
            self._memory_cache[cache_key] = entry
            self._memory_cache.move_to_end(cache_key)
            self._stats["sets"] += 1
            
            # Evict if needed
            await self._evict_if_needed()
            
            # Save to disk asynchronously
            disk_path = self._get_disk_path(cache_key)
            disk_path.parent.mkdir(parents=True, exist_ok=True)
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                disk_path.write_text,
                json.dumps(asdict(entry), indent=2)
            )
            
            logger.debug(f"Cache set: {cache_key[:8]}... (ttl: {ttl}s)")
    
    async def _evict_if_needed(self):
        """Evict oldest entries if memory cache is full"""
        while len(self._memory_cache) > self.max_memory_entries:
            # Remove oldest (first) entry
            oldest_key, _ = self._memory_cache.popitem(last=False)
            self._stats["evictions"] += 1
            logger.debug(f"Evicted from memory: {oldest_key[:8]}...")
    
    async def clear(self, backend: Optional[str] = None):
        """
        Clear cache asynchronously.
        
        Args:
            backend: If provided, only clear entries for this backend
        """
        async with self._lock:
            if backend:
                # Clear specific backend
                keys_to_remove = [
                    k for k, v in self._memory_cache.items()
                    if v.backend == backend
                ]
                for key in keys_to_remove:
                    del self._memory_cache[key]
                logger.info(f"Cleared cache for backend: {backend}")
            else:
                # Clear all
                self._memory_cache.clear()
                logger.info("Cleared all cache")
    
    def get_stats(self) -> Dict:
        """Get cache statistics"""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "sets": self._stats["sets"],
            "evictions": self._stats["evictions"],
            "hit_rate": hit_rate,
            "memory_entries": len(self._memory_cache),
            "max_memory_entries": self.max_memory_entries
        }
    
    async def export_stats_report(self) -> str:
        """Export statistics as markdown report"""
        stats = self.get_stats()
        
        report = "# Async LLM Cache Statistics\n\n"
        report += f"**Hit Rate**: {stats['hit_rate']:.1%}\n\n"
        report += "| Metric | Value |\n"
        report += "|--------|-------|\n"
        report += f"| Cache Hits | {stats['hits']} |\n"
        report += f"| Cache Misses | {stats['misses']} |\n"
        report += f"| Cache Sets | {stats['sets']} |\n"
        report += f"| Evictions | {stats['evictions']} |\n"
        report += f"| Memory Entries | {stats['memory_entries']} / {stats['max_memory_entries']} |\n"
        
        return report


# Global async cache instance
_global_async_cache: Optional[AsyncLLMCache] = None


def get_async_llm_cache() -> AsyncLLMCache:
    """Get global async LLM cache instance (singleton)"""
    global _global_async_cache
    if _global_async_cache is None:
        _global_async_cache = AsyncLLMCache()
    return _global_async_cache


def reset_async_cache():
    """Reset global async cache instance"""
    global _global_async_cache
    _global_async_cache = None


if __name__ == "__main__":
    # Example usage
    async def main():
        cache = get_async_llm_cache()
        
        # Set cache
        await cache.set(
            prompt="What is Python?",
            response="Python is a programming language.",
            backend="openai",
            model="gpt-4"
        )
        
        # Get from cache
        response = await cache.get(
            prompt="What is Python?",
            backend="openai",
            model="gpt-4"
        )
        print(f"Cached response: {response}")
        
        # Print stats
        print(await cache.export_stats_report())
    
    asyncio.run(main())
