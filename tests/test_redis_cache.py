"""Tests for RedisCacheBackend and SyncRedisCacheWrapper (P1-A).

Uses fakeredis to simulate Redis without requiring a real Redis server.
The _get_client method is replaced with a FakeRedis instance, but all
business logic (get/set/delete/mget/mset/stats/health_check/scan_keys)
is tested against the real fakeredis implementation.
"""

from __future__ import annotations

import fakeredis.aioredis
import pytest

from scripts.collaboration.redis_cache import (
    RedisCacheBackend,
    RedisConnectionError,
    SyncRedisCacheWrapper,
)


@pytest.fixture
async def redis_backend():
    """Create a RedisCacheBackend backed by fakeredis."""
    backend = RedisCacheBackend(prefix="test:", default_ttl=60)
    fake_client = fakeredis.aioredis.FakeRedis()

    async def mock_get_client():
        backend._client = fake_client
        backend._connected = True
        return fake_client

    backend._get_client = mock_get_client
    yield backend
    await fake_client.close()


# ============================================================================
# RedisCacheBackend — Initialization
# ============================================================================


class TestRedisCacheBackendInit:
    def test_init_defaults(self):
        backend = RedisCacheBackend()
        assert backend.prefix == "devsquad:"
        assert backend.default_ttl == 3600
        assert backend.max_connections == 10
        assert backend.enable_compression is False
        assert backend._connected is False

    def test_init_custom_params(self):
        backend = RedisCacheBackend(
            redis_url="redis://custom:6379/1",
            prefix="custom:",
            default_ttl=120,
            max_connections=5,
            enable_compression=True,
        )
        assert backend.redis_url == "redis://custom:6379/1"
        assert backend.prefix == "custom:"
        assert backend.default_ttl == 120
        assert backend.max_connections == 5
        assert backend.enable_compression is True

    def test_init_with_env_vars(self, monkeypatch):
        monkeypatch.setenv("REDIS_URL", "redis://env:6379/2")
        monkeypatch.setenv("CACHE_PREFIX", "env:")
        monkeypatch.setenv("CACHE_TTL", "999")
        backend = RedisCacheBackend()
        assert backend.redis_url == "redis://env:6379/2"
        assert backend.prefix == "env:"
        assert backend.default_ttl == 999

    def test_prefixed_key(self):
        backend = RedisCacheBackend(prefix="myprefix:")
        assert backend._prefixed_key("hello") == "myprefix:hello"

    def test_strip_prefix(self):
        backend = RedisCacheBackend(prefix="myprefix:")
        assert backend._strip_prefix("myprefix:hello") == "hello"
        assert backend._strip_prefix("other:hello") == "other:hello"

    def test_repr(self):
        backend = RedisCacheBackend(prefix="test:")
        r = repr(backend)
        assert "RedisCacheBackend" in r
        assert "test:" in r


# ============================================================================
# RedisCacheBackend — Basic Operations
# ============================================================================


class TestRedisCacheBackendOperations:
    @pytest.mark.asyncio
    async def test_set_and_get(self, redis_backend):
        await redis_backend.set("key1", {"data": "value1"})
        result = await redis_backend.get("key1")
        assert result == {"data": "value1"}

    @pytest.mark.asyncio
    async def test_get_miss(self, redis_backend):
        result = await redis_backend.get("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_with_custom_ttl(self, redis_backend):
        await redis_backend.set("key2", "val", ttl=30)
        result = await redis_backend.get("key2")
        assert result == "val"

    @pytest.mark.asyncio
    async def test_set_string_value(self, redis_backend):
        await redis_backend.set("str_key", "hello world")
        assert await redis_backend.get("str_key") == "hello world"

    @pytest.mark.asyncio
    async def test_set_list_value(self, redis_backend):
        await redis_backend.set("list_key", [1, 2, 3])
        assert await redis_backend.get("list_key") == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_delete_existing(self, redis_backend):
        await redis_backend.set("del_key", "val")
        deleted = await redis_backend.delete("del_key")
        assert deleted is True
        assert await redis_backend.get("del_key") is None

    @pytest.mark.asyncio
    async def test_delete_miss(self, redis_backend):
        deleted = await redis_backend.delete("nonexistent")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_clear(self, redis_backend):
        await redis_backend.set("k1", "v1")
        await redis_backend.set("k2", "v2")
        await redis_backend.clear()
        keys = await redis_backend.scan_keys("*")
        assert len(keys) == 0

    @pytest.mark.asyncio
    async def test_clear_only_removes_prefixed(self, redis_backend):
        await redis_backend.set("k1", "v1")
        fake_client = await redis_backend._get_client()
        await fake_client.set("other:key", "other")
        await redis_backend.clear()
        keys = await redis_backend.scan_keys("*")
        assert len(keys) == 0
        other = await fake_client.get("other:key")
        assert other is not None


# ============================================================================
# RedisCacheBackend — Batch Operations
# ============================================================================


class TestRedisCacheBackendBatch:
    @pytest.mark.asyncio
    async def test_mset_and_mget(self, redis_backend):
        await redis_backend.mset({"k1": "v1", "k2": "v2", "k3": "v3"}, ttl=30)
        results = await redis_backend.mget(["k1", "k2", "k3"])
        assert results == ["v1", "v2", "v3"]

    @pytest.mark.asyncio
    async def test_mget_empty_keys(self, redis_backend):
        results = await redis_backend.mget([])
        assert results == []

    @pytest.mark.asyncio
    async def test_mset_empty_mapping(self, redis_backend):
        result = await redis_backend.mset({})
        assert result is True

    @pytest.mark.asyncio
    async def test_mget_with_misses(self, redis_backend):
        await redis_backend.set("exists", "val")
        results = await redis_backend.mget(["exists", "missing"])
        assert results[0] == "val"
        assert results[1] is None

    @pytest.mark.asyncio
    async def test_mset_with_dict_values(self, redis_backend):
        await redis_backend.mset({"d1": {"a": 1}, "d2": {"b": 2}})
        results = await redis_backend.mget(["d1", "d2"])
        assert results[0] == {"a": 1}
        assert results[1] == {"b": 2}


# ============================================================================
# RedisCacheBackend — Statistics
# ============================================================================


class TestRedisCacheBackendStats:
    @pytest.mark.asyncio
    async def test_stats_contains_required_fields(self, redis_backend):
        await redis_backend.set("k", "v")
        await redis_backend.get("k")
        stats = await redis_backend.stats()
        assert "hits" in stats
        assert "misses" in stats
        assert "hit_rate" in stats
        assert "backend_type" in stats
        assert stats["backend_type"] == "redis"
        assert stats["prefix"] == "test:"
        assert stats["connected"] is True

    @pytest.mark.asyncio
    async def test_stats_hit_rate(self, redis_backend):
        await redis_backend.set("k1", "v1")
        await redis_backend.get("k1")
        await redis_backend.get("missing")
        stats = await redis_backend.stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        hit_rate_pct = float(stats["hit_rate"].rstrip("%"))
        assert 0 < hit_rate_pct < 100

    @pytest.mark.asyncio
    async def test_stats_tracks_sets(self, redis_backend):
        await redis_backend.set("k1", "v1")
        await redis_backend.set("k2", "v2")
        stats = await redis_backend.stats()
        assert stats["sets"] >= 2


# ============================================================================
# RedisCacheBackend — Health Check
# ============================================================================


class TestRedisCacheBackendHealth:
    @pytest.mark.asyncio
    async def test_health_check_healthy(self, redis_backend):
        health = await redis_backend.health_check()
        assert health["status"] == "healthy"
        assert "latency_ms" in health
        assert health["connected"] is True

    @pytest.mark.asyncio
    async def test_health_check_throttled(self, redis_backend):
        await redis_backend.health_check()
        health = await redis_backend.health_check()
        assert health["status"] == "skipped"
        assert "Too frequent" in health["reason"]


# ============================================================================
# RedisCacheBackend — Scan Keys
# ============================================================================


class TestRedisCacheBackendScan:
    @pytest.mark.asyncio
    async def test_scan_keys_all(self, redis_backend):
        await redis_backend.set("k1", "v1")
        await redis_backend.set("k2", "v2")
        keys = await redis_backend.scan_keys("*")
        assert set(keys) == {"k1", "k2"}

    @pytest.mark.asyncio
    async def test_scan_keys_pattern(self, redis_backend):
        await redis_backend.set("user:1", "v1")
        await redis_backend.set("user:2", "v2")
        await redis_backend.set("post:1", "v3")
        keys = await redis_backend.scan_keys("user:*")
        assert set(keys) == {"user:1", "user:2"}

    @pytest.mark.asyncio
    async def test_scan_keys_empty(self, redis_backend):
        keys = await redis_backend.scan_keys("*")
        assert keys == []


# ============================================================================
# RedisCacheBackend — Close
# ============================================================================


class TestRedisCacheBackendClose:
    @pytest.mark.asyncio
    async def test_close(self, redis_backend):
        await redis_backend.close()
        assert redis_backend._connected is False

    @pytest.mark.asyncio
    async def test_close_idempotent(self, redis_backend):
        await redis_backend.close()
        await redis_backend.close()
        assert redis_backend._connected is False


# ============================================================================
# RedisCacheBackend — Compression
# ============================================================================


class TestRedisCacheBackendCompression:
    @pytest.mark.asyncio
    async def test_compression_roundtrip(self):
        backend = RedisCacheBackend(prefix="comp:", enable_compression=True)
        fake_client = fakeredis.aioredis.FakeRedis()

        async def mock_get_client():
            backend._client = fake_client
            backend._connected = True
            return fake_client

        backend._get_client = mock_get_client

        large_data = {"items": list(range(100)), "text": "x" * 500}
        await backend.set("large", large_data)
        result = await backend.get("large")
        assert result == large_data
        await fake_client.close()


# ============================================================================
# RedisCacheBackend — Error Handling
# ============================================================================


class TestRedisCacheBackendErrors:
    @pytest.mark.asyncio
    async def test_connection_error_raises(self):
        backend = RedisCacheBackend(redis_url="redis://localhost:1/0", retry_attempts=1, retry_delay=0.01)
        with pytest.raises(RedisConnectionError):
            await backend._get_client()

    @pytest.mark.asyncio
    async def test_get_returns_none_on_connection_failure(self):
        backend = RedisCacheBackend(redis_url="redis://localhost:1/0", retry_attempts=1, retry_delay=0.01)
        result = await backend.get("key")
        assert result is None

    @pytest.mark.asyncio
    async def test_set_returns_false_on_connection_failure(self):
        backend = RedisCacheBackend(redis_url="redis://localhost:1/0", retry_attempts=1, retry_delay=0.01)
        result = await backend.set("key", "val")
        assert result is False


# ============================================================================
# SyncRedisCacheWrapper
# ============================================================================


class TestSyncRedisCacheWrapper:
    def test_init(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0", prefix="sync:")
        assert wrapper._redis_url == "redis://localhost:6379/0"
        assert wrapper._prefix == "sync:"
        assert wrapper._initialized is False

    def test_get_set_sync(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0", prefix="sync:")
        fake_client = fakeredis.aioredis.FakeRedis()

        async def mock_get_client():
            wrapper._backend._client = fake_client
            wrapper._backend._connected = True
            return fake_client

        wrapper._ensure_backend()
        wrapper._backend._get_client = mock_get_client

        wrapper.set("key", "value")
        assert wrapper.get("key") == "value"

    def test_delete_sync(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0", prefix="sync:")
        fake_client = fakeredis.aioredis.FakeRedis()

        async def mock_get_client():
            wrapper._backend._client = fake_client
            wrapper._backend._connected = True
            return fake_client

        wrapper._ensure_backend()
        wrapper._backend._get_client = mock_get_client

        wrapper.set("del", "val")
        assert wrapper.delete("del") is True
        assert wrapper.get("del") is None

    def test_clear_sync(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0", prefix="sync:")
        fake_client = fakeredis.aioredis.FakeRedis()

        async def mock_get_client():
            wrapper._backend._client = fake_client
            wrapper._backend._connected = True
            return fake_client

        wrapper._ensure_backend()
        wrapper._backend._get_client = mock_get_client

        wrapper.set("k1", "v1")
        wrapper.clear()
        assert wrapper.get("k1") is None

    def test_health_check_sync(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0", prefix="sync:")
        fake_client = fakeredis.aioredis.FakeRedis()

        async def mock_get_client():
            wrapper._backend._client = fake_client
            wrapper._backend._connected = True
            return fake_client

        wrapper._ensure_backend()
        wrapper._backend._get_client = mock_get_client

        health = wrapper.health_check()
        assert health["status"] in ("healthy", "skipped")

    def test_health_check_no_backend(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0")
        wrapper._backend = None
        wrapper._initialized = True
        health = wrapper.health_check()
        assert health["status"] == "unavailable"

    def test_close_sync(self):
        wrapper = SyncRedisCacheWrapper("redis://localhost:6379/0", prefix="sync:")
        fake_client = fakeredis.aioredis.FakeRedis()

        async def mock_get_client():
            wrapper._backend._client = fake_client
            wrapper._backend._connected = True
            return fake_client

        wrapper._ensure_backend()
        wrapper._backend._get_client = mock_get_client
        wrapper.close()
        assert wrapper._backend._connected is False
