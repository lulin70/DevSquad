"""Simple file cache for completeness gate checks.

Provides in-memory caching of file parsing results to avoid redundant work.
"""

from collections.abc import Callable
from typing import Any


class FileCache:
    """Simple dictionary-based cache for file parsing results."""

    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}

    def get(self, key: str) -> Any | None:
        """
        Get cached value by key.

        Args:
            key: Cache key (usually file path string)

        Returns:
            Cached value or None if not found
        """
        return self._cache.get(key)

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to cache
        """
        self._cache[key] = value

    def clear(self) -> None:
        """Clear all cached values."""
        self._cache.clear()

    def get_or_compute(self, key: str, compute_fn: Callable[[], Any]) -> Any:
        """
        Get cached value or compute and cache it.

        Args:
            key: Cache key
            compute_fn: Function to compute value if not cached

        Returns:
            Cached or computed value
        """
        if key in self._cache:
            return self._cache[key]

        value = compute_fn()
        self._cache[key] = value
        return value

    def __len__(self) -> int:
        """Return number of cached items."""
        return len(self._cache)

    def __contains__(self, key: str) -> bool:
        """Check if key exists in cache."""
        return key in self._cache
