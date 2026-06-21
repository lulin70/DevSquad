#!/usr/bin/env python3
"""
ContentCache — V3.8 unified content caching wrapper.

Wraps :class:`LLMCacheBase` (and its concrete subclasses such as
``LLMCache``) with three production-grade enhancements:

1. **SHA-256 content hashing for ALL cache keys (unified)**
   Every cache key — regardless of the underlying backend/model — is
   derived from a SHA-256 digest of the canonical content tuple. This
   guarantees deterministic, collision-resistant keys across the fleet
   and prevents PII from leaking into key strings.

2. **Sensitive data filtering (API keys, secrets never cached)**
   Before any ``set``/``get`` call, the prompt is scanned for secrets.
   If sensitive material is detected, the entry is *never* written to
   or read from the cache, eliminating the risk of persisting secrets
   to disk or Redis.

3. **Cache hit/miss metrics integration with PerformanceMonitor**
   Every ``get`` records a hit or miss on the optional
   :class:`PerformanceMonitor`, giving observability into cache
   effectiveness alongside other dispatch metrics.

Design notes
------------
- ``ContentCache`` is a *composition* wrapper: it holds a reference to
  an existing cache instance (sync ``LLMCache`` or any subclass of
  ``LLMCacheBase`` that implements ``get``/``set``) and delegates the
  actual storage I/O to it. It does not subclass the cache, so it can
  wrap either the sync or async variant without modification.
- The wrapper is intentionally tolerant: if no ``monitor`` is supplied,
  metrics calls are silently skipped. If the wrapped cache is ``None``,
  all operations degrade to no-ops returning ``None`` / ``False``.

Usage::

    from scripts.collaboration.content_cache import ContentCache
    from scripts.collaboration.llm_cache import LLMCache
    from scripts.collaboration.performance_monitor import PerformanceMonitor

    cache = ContentCache(
        wrapped=LLMCache(cache_dir="/tmp/cache"),
        monitor=PerformanceMonitor(),
    )
    cache.set("prompt", "response", "openai", "gpt-4")
    cached = cache.get("prompt", "openai", "gpt-4")
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

from .llm_cache_base import LLMCacheBase

logger = logging.getLogger(__name__)


# Patterns that indicate sensitive data which must never be cached.
# Matches are case-insensitive. The list covers common secret formats:
#   - API key assignments:  api_key=..., api-key: ..., "apikey": "..."
#   - Bearer tokens:        Authorization: Bearer xxx
#   - AWS secrets:          AKIA... access keys, aws_secret_access_key=...
#   - Private keys:         -----BEGIN ... PRIVATE KEY-----
#   - Generic secret assignments:  secret=..., password=..., token=...
SENSITIVE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"(?i)\bapi[_-]?key\b\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}"),
    re.compile(r"(?i)\bauthorization\b\s*[:=]\s*['\"]?bearer\s+[A-Za-z0-9_\-\.]+"),
    re.compile(r"(?i)\baws[_-]?secret[_-]?access[_-]?key\b\s*[:=]\s*\S+"),
    re.compile(r"(?i)\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN\s+[A-Z\s]*PRIVATE KEY-----"),
    re.compile(r"(?i)\b(secret|password|passwd|token)\b\s*[:=]\s*['\"]?[^\s'\"]{8,}"),
)


class ContentCache:
    """Unified content cache wrapper with secret filtering and metrics.

    Parameters
    ----------
    wrapped:
        The underlying cache instance. Must be a subclass of
        :class:`LLMCacheBase` (e.g. ``LLMCache``) exposing ``get`` and
        ``set`` methods. May be ``None`` for a no-op cache.
    monitor:
        Optional :class:`PerformanceMonitor` (or any object exposing a
        compatible ``record_metric`` / ``monitor`` interface). When
        provided, cache hits and misses are recorded under the
        ``content_cache`` metric name.
    namespace:
        Optional namespace prefix prepended to every cache key, useful
        for multi-tenant isolation.
    """

    METRIC_NAME = "content_cache"

    def __init__(
        self,
        wrapped: LLMCacheBase | None,
        monitor: Any = None,
        namespace: str = "",
    ) -> None:
        self._wrapped = wrapped
        self._monitor = monitor
        self._namespace = namespace or ""
        # Local counters (mirror wrapped cache stats for quick access)
        self.hits = 0
        self.misses = 0
        self.filtered = 0  # number of operations blocked by secret filter

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def wrapped(self) -> LLMCacheBase | None:
        """Return the underlying cache instance (may be None)."""
        return self._wrapped

    def get(self, prompt: str, backend: str, model: str) -> str | None:
        """Retrieve a cached response, filtering sensitive prompts.

        If the prompt contains sensitive data, the lookup is skipped
        (returns ``None``) and the ``filtered`` counter is incremented.

        Parameters
        ----------
        prompt: Input prompt text.
        backend: LLM backend name (e.g. ``"openai"``).
        model: Model name (e.g. ``"gpt-4"``).

        Returns
        -------
        The cached response string, or ``None`` on miss / filtered /
        no wrapped cache.
        """
        if self._contains_sensitive(prompt):
            self.filtered += 1
            logger.debug("ContentCache.get skipped sensitive prompt")
            return None
        if self._wrapped is None:
            return None

        key = self._generate_key(prompt, backend, model)
        # Delegate to wrapped cache's get(). The wrapped cache may use
        # its own internal key derivation; we pass our unified key as
        # the prompt argument so the underlying SHA-256 is applied to
        # the canonical content, not the raw prompt.
        result = self._wrapped.get(key, backend, model)
        if result is not None:
            self.hits += 1
            self._record_metric(hit=True)
        else:
            self.misses += 1
            self._record_metric(hit=False)
        return result

    def set(self, prompt: str, response: str, backend: str, model: str) -> bool:
        """Store a response in the cache, filtering sensitive prompts.

        Returns
        -------
        ``True`` if the entry was stored, ``False`` if it was filtered
        out (sensitive prompt) or no wrapped cache is configured.
        """
        if self._wrapped is None:
            return False
        if self._contains_sensitive(prompt) or self._contains_sensitive(response):
            self.filtered += 1
            logger.debug("ContentCache.set skipped sensitive content")
            return False

        key = self._generate_key(prompt, backend, model)
        self._wrapped.set(key, response, backend, model)
        return True

    # ------------------------------------------------------------------
    # V3.8 #9: Alias API (get_cached / set_cached) — matches the task
    # spec method names while keeping the original get/set intact for
    # backward compatibility with existing callers.
    # ------------------------------------------------------------------

    def get_cached(self, prompt: str, backend: str, model: str) -> str | None:
        """Alias for :meth:`get` — retrieve a cached response.

        Provided per V3.8 #9 spec so callers can use the explicit
        ``get_cached`` name. Behavior is identical to :meth:`get`.
        """
        return self.get(prompt, backend, model)

    def set_cached(self, prompt: str, response: str, backend: str, model: str) -> bool:
        """Alias for :meth:`set` — store a response in the cache.

        Provided per V3.8 #9 spec so callers can use the explicit
        ``set_cached`` name. Behavior is identical to :meth:`set`.
        """
        return self.set(prompt, response, backend, model)

    def invalidate(self, pattern: str) -> int:
        """Invalidate cache entries whose key matches ``pattern``.

        V3.8 #9: Pattern-based cache invalidation. The pattern is matched
        against the **SHA-256 cache key** (not the original prompt) using
        ``re.search``. Because keys are hex digests, callers typically
        invalidate by recomputing the key for a known prompt/backend/model
        tuple via :meth:`generate_cache_key`, or by passing a prefix to
        invalidate a namespace.

        If the wrapped cache exposes an ``invalidate(pattern)`` method
        (e.g. a future Redis-backed cache), the call is delegated to it
        and its return value is used. Otherwise, this method falls back
        to delegating to the wrapped cache's ``clear()`` when the pattern
        matches ``"*"`` (whole-cache invalidation).

        Args:
            pattern: Regular expression matched against cache keys. Use
                ``"*"`` to invalidate the entire cache.

        Returns:
            Number of entries invalidated. When the wrapped cache does
            not expose per-key invalidation, returns ``0`` (best-effort).
        """
        if self._wrapped is None:
            return 0

        # Sensitive patterns are never invalidated (they were never stored).
        if self._contains_sensitive(pattern):
            self.filtered += 1
            logger.debug("ContentCache.invalidate skipped sensitive pattern")
            return 0

        # Delegate to wrapped cache's invalidate() when available.
        if hasattr(self._wrapped, "invalidate"):
            try:
                result = self._wrapped.invalidate(pattern)
                return int(result) if isinstance(result, int) else 0
            except (AttributeError, RuntimeError, TypeError) as exc:
                logger.debug("Wrapped invalidate failed: %s", exc)
                return 0

        # Fallback: whole-cache clear when pattern is the wildcard.
        if pattern == "*":
            try:
                if hasattr(self._wrapped, "clear"):
                    self._wrapped.clear()
                    return 1  # best-effort: signal "cleared"
            except (AttributeError, RuntimeError, TypeError) as exc:
                logger.debug("Wrapped clear failed: %s", exc)
        return 0

    def generate_cache_key(self, prompt: str, backend: str, model: str) -> str:
        """Generate the unified SHA-256 cache key for the given inputs.

        Exposed publicly so callers can pre-compute keys (e.g. for
        bulk invalidation) without triggering a get/set.
        """
        return self._generate_key(prompt, backend, model)

    def contains_sensitive(self, text: str) -> bool:
        """Public helper: check whether ``text`` matches a sensitive pattern."""
        return self._contains_sensitive(text)

    def get_stats(self) -> dict[str, Any]:
        """Return local wrapper statistics.

        Merges the wrapped cache's stats (when available) with the
        wrapper-level hit/miss/filtered counters.
        """
        stats: dict[str, Any] = {
            "hits": self.hits,
            "misses": self.misses,
            "filtered": self.filtered,
            "hit_rate": self._hit_rate(),
            "has_wrapped": self._wrapped is not None,
            "namespace": self._namespace,
        }
        if self._wrapped is not None and hasattr(self._wrapped, "get_stats"):
            try:
                stats["wrapped_stats"] = self._wrapped.get_stats()
            except (AttributeError, RuntimeError) as exc:
                logger.debug("Wrapped cache stats unavailable: %s", exc)
        return stats

    def reset_stats(self) -> None:
        """Reset local wrapper counters (does not clear the wrapped cache)."""
        self.hits = 0
        self.misses = 0
        self.filtered = 0

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _generate_key(self, prompt: str, backend: str, model: str) -> str:
        """Build a unified SHA-256 cache key.

        The canonical content is ``namespace:backend:model:prompt``.
        We hash the *full* digest (no truncation) to maximize collision
        resistance — the wrapped cache may truncate further if needed.
        """
        content = f"{self._namespace}:{backend}:{model}:{prompt}"
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def _contains_sensitive(text: str) -> bool:
        """Return True if ``text`` matches any sensitive-data pattern."""
        if not text:
            return False
        return any(pattern.search(text) for pattern in SENSITIVE_PATTERNS)

    def _hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def _record_metric(self, hit: bool) -> None:
        """Record a hit/miss metric on the optional PerformanceMonitor.

        Tolerates monitors that expose either ``record_metric`` (the
        :class:`PerformanceMonitor` API) or a generic ``monitor``
        decorator-style interface. Silently skips when no monitor is
        configured or the call fails.
        """
        if self._monitor is None:
            return
        try:
            # PerformanceMonitor.record_metric expects a PerformanceMetric
            # dataclass; we use a lightweight dict-based fallback via
            # the public ``monitor`` decorator-free path when available.
            metric_name = f"{self.METRIC_NAME}.{'hit' if hit else 'miss'}"
            if hasattr(self._monitor, "record_metric"):
                # Build a minimal PerformanceMetric-compatible object.
                # We import lazily to avoid a hard dependency at module
                # import time (tests may run without psutil).
                import time as _time

                from .performance_monitor import PerformanceMetric

                now = _time.time()
                self._monitor.record_metric(
                    PerformanceMetric(
                        name=metric_name,
                        start_time=now,
                        end_time=now,
                        duration=0.0,
                        cpu_percent=0.0,
                        memory_mb=0.0,
                        success=hit,
                    )
                )
            elif hasattr(self._monitor, "increment"):
                # Generic counter interface
                self._monitor.increment(metric_name)
        except (AttributeError, ImportError, RuntimeError, ValueError) as exc:
            logger.debug("ContentCache metric recording failed: %s", exc)


__all__ = ["ContentCache", "SENSITIVE_PATTERNS"]
