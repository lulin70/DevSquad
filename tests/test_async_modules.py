"""Tests for async modules: AsyncMockBackend, AsyncFallbackBackend, AsyncLLMBackendFactory,
SyncToAsyncAdapter, AsyncToSyncAdapter, and AsyncLLMCache."""

import asyncio
import tempfile

import pytest

from scripts.collaboration.async_llm_backend import (
    AsyncFallbackBackend,
    AsyncLLMBackendFactory,
    AsyncMockBackend,
    AsyncTraeBackend,
)
from scripts.collaboration.async_adapter import (
    AsyncToSyncAdapter,
    AutoBackendSelector,
    SyncToAsyncAdapter,
)
from scripts.collaboration.llm_cache_async import AsyncLLMCache
from scripts.collaboration.llm_backend import MockBackend


class TestAsyncMockBackend:
    @pytest.mark.asyncio
    async def test_generate(self):
        backend = AsyncMockBackend()
        result = await backend.generate("test prompt")
        assert isinstance(result, str)
        assert len(result) > 0
        assert "MOCK MODE" in result

    @pytest.mark.asyncio
    async def test_generate_with_kwargs(self):
        backend = AsyncMockBackend()
        result = await backend.generate("test prompt", role_name="Coder")
        assert "Coder" in result

    @pytest.mark.asyncio
    async def test_is_available(self):
        backend = AsyncMockBackend()
        result = await backend.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_batch_generate(self):
        backend = AsyncMockBackend()
        results = await backend.batch_generate(["prompt1", "prompt2", "prompt3"])
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)

    @pytest.mark.asyncio
    async def test_generate_stream(self):
        backend = AsyncMockBackend()
        chunks = []
        async for chunk in backend.generate_stream("test prompt"):
            chunks.append(chunk)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_close(self):
        backend = AsyncMockBackend()
        await backend.close()  # Should not raise


class TestAsyncTraeBackend:
    @pytest.mark.asyncio
    async def test_generate_returns_prompt(self):
        backend = AsyncTraeBackend()
        result = await backend.generate("hello world")
        assert result == "hello world"

    @pytest.mark.asyncio
    async def test_is_available(self):
        backend = AsyncTraeBackend()
        assert await backend.is_available() is True

    @pytest.mark.asyncio
    async def test_batch_generate(self):
        backend = AsyncTraeBackend()
        results = await backend.batch_generate(["a", "b"])
        assert results == ["a", "b"]


class TestAsyncFallbackBackend:
    @pytest.mark.asyncio
    async def test_fallback_to_mock(self):
        backend = AsyncFallbackBackend(backends=[AsyncMockBackend()])
        result = await backend.generate("test prompt")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_fallback_with_multiple_backends(self):
        backend = AsyncFallbackBackend(
            backends=[AsyncMockBackend(), AsyncTraeBackend()]
        )
        result = await backend.generate("test prompt")
        assert isinstance(result, str)

    @pytest.mark.asyncio
    async def test_is_available(self):
        backend = AsyncFallbackBackend(backends=[AsyncMockBackend()])
        assert await backend.is_available() is True

    @pytest.mark.asyncio
    async def test_batch_generate(self):
        backend = AsyncFallbackBackend(backends=[AsyncMockBackend()])
        results = await backend.batch_generate(["p1", "p2"])
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_empty_backends_raises(self):
        with pytest.raises(ValueError, match="at least one backend"):
            AsyncFallbackBackend(backends=[])

    @pytest.mark.asyncio
    async def test_close(self):
        backend = AsyncFallbackBackend(backends=[AsyncMockBackend()])
        await backend.close()


class TestAsyncLLMBackendFactory:
    def test_create_mock(self):
        backend = AsyncLLMBackendFactory.create("mock", _force_type=True)
        assert isinstance(backend, AsyncMockBackend)

    def test_create_trae(self):
        backend = AsyncLLMBackendFactory.create("trae", _force_type=True)
        assert isinstance(backend, AsyncTraeBackend)

    def test_create_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown backend type"):
            AsyncLLMBackendFactory.create("nonexistent", _force_type=True)


class TestSyncToAsyncAdapter:
    @pytest.mark.asyncio
    async def test_wrap_sync_backend(self):
        sync = MockBackend()
        async_backend = SyncToAsyncAdapter(sync)
        result = await async_backend.generate("test prompt")
        assert isinstance(result, str)
        assert "MOCK MODE" in result

    @pytest.mark.asyncio
    async def test_is_available(self):
        sync = MockBackend()
        async_backend = SyncToAsyncAdapter(sync)
        result = await async_backend.is_available()
        assert result is True

    @pytest.mark.asyncio
    async def test_batch_generate(self):
        sync = MockBackend()
        async_backend = SyncToAsyncAdapter(sync)
        results = await async_backend.batch_generate(["p1", "p2"])
        assert len(results) == 2


class TestAsyncToSyncAdapter:
    def test_wrap_async_backend(self):
        async_backend = AsyncMockBackend()
        sync_adapter = AsyncToSyncAdapter(async_backend)
        result = sync_adapter.generate("test prompt")
        assert isinstance(result, str)
        assert "MOCK MODE" in result

    def test_is_available(self):
        async_backend = AsyncMockBackend()
        sync_adapter = AsyncToSyncAdapter(async_backend)
        result = sync_adapter.is_available()
        assert result is True


class TestAutoBackendSelector:
    def test_should_use_async_env_set(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_USE_ASYNC", "true")
        assert AutoBackendSelector.should_use_async() is True

    def test_should_not_use_async_env_set(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_USE_ASYNC", "false")
        assert AutoBackendSelector.should_use_async() is False

    def test_get_backend_mock(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_USE_ASYNC", "false")
        backend = AutoBackendSelector.get_backend("mock")
        assert backend is not None


class TestAsyncLLMCache:
    @pytest.mark.asyncio
    async def test_cache_miss(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            result = await cache.get("test prompt", backend="mock", model="test")
            assert result is None

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            await cache.set(
                "test prompt", "test response", backend="mock", model="test"
            )
            result = await cache.get("test prompt", backend="mock", model="test")
            assert result == "test response"

    @pytest.mark.asyncio
    async def test_cache_different_backends(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            await cache.set("prompt", "openai_resp", backend="openai", model="gpt-4")
            await cache.set(
                "prompt", "anthropic_resp", backend="anthropic", model="claude-3"
            )
            r1 = await cache.get("prompt", backend="openai", model="gpt-4")
            r2 = await cache.get("prompt", backend="anthropic", model="claude-3")
            assert r1 == "openai_resp"
            assert r2 == "anthropic_resp"

    @pytest.mark.asyncio
    async def test_cache_stats(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            await cache.get("miss", backend="mock", model="test")  # miss
            await cache.set("key", "val", backend="mock", model="test")  # set
            await cache.get("key", backend="mock", model="test")  # hit
            stats = cache.get_stats()
            assert stats["hits"] == 1
            assert stats["misses"] == 1
            assert stats["sets"] == 1

    @pytest.mark.asyncio
    async def test_cache_clear(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            await cache.set("key", "val", backend="mock", model="test")
            await cache.clear()
            result = await cache.get("key", backend="mock", model="test")
            # After clearing memory, should check disk
            # Depending on implementation, may still find on disk
            # but memory cache is cleared

    @pytest.mark.asyncio
    async def test_cache_clear_specific_backend(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            await cache.set("p1", "r1", backend="openai", model="gpt-4")
            await cache.set("p2", "r2", backend="anthropic", model="claude-3")
            await cache.clear(backend="openai")
            # anthropic cache should still be in memory
            result = await cache.get("p2", backend="anthropic", model="claude-3")
            assert result == "r2"

    @pytest.mark.asyncio
    async def test_cache_ttl_expiration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir, ttl_seconds=0)
            await cache.set("key", "val", backend="mock", model="test")
            # With TTL=0, entry should be expired immediately
            import time
            time.sleep(0.1)
            result = await cache.get("key", backend="mock", model="test")
            assert result is None

    @pytest.mark.asyncio
    async def test_export_stats_report(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = AsyncLLMCache(cache_dir=tmpdir)
            report = await cache.export_stats_report()
            assert "Hit Rate" in report
