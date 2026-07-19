"""Supplemental coverage tests for scripts.collaboration.async_llm_backend.

Targets the error/degradation branches not exercised by existing tests:
- AsyncOpenAIBackend / AsyncAnthropicBackend: client init, retry, streaming, batch, close
- AsyncFallbackBackend: cooldown, failover, all-fail, streaming, batch, close
- AsyncLLMBackendFactory: env-var resolution, auto mode, moka alias
- _load_dotenv_async helper

Goal (TD-3): raise async_llm_backend.py coverage from 45% to >=65%.
"""

from __future__ import annotations

import asyncio
import sys
import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scripts.collaboration.async_llm_backend import (
    AsyncAnthropicBackend,
    AsyncFallbackBackend,
    AsyncLLMBackendFactory,
    AsyncLLMBackendInterface,
    AsyncMockBackend,
    AsyncOpenAIBackend,
    AsyncTraeBackend,
)
from scripts.collaboration.llm_backend import (
    _get_anthropic_retry_exceptions,
    _get_openai_retry_exceptions,
)

# ---------------------------------------------------------------------------
# AsyncMockBackend
# ---------------------------------------------------------------------------


class TestAsyncMockBackend:
    @pytest.mark.asyncio
    async def test_generate_returns_mock_output(self):
        backend = AsyncMockBackend()
        result = await backend.generate("p", role_name="R", task_description="T")
        assert "[MOCK MODE]" in result
        assert "R" in result
        assert "T" in result

    @pytest.mark.asyncio
    async def test_generate_default_role(self):
        backend = AsyncMockBackend()
        result = await backend.generate("p")
        assert "AI Assistant" in result

    @pytest.mark.asyncio
    async def test_is_available_returns_true(self):
        backend = AsyncMockBackend()
        assert await backend.is_available() is True

    @pytest.mark.asyncio
    async def test_batch_generate_returns_list_in_order(self):
        backend = AsyncMockBackend()
        results = await backend.batch_generate(["p1", "p2", "p3"])
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)

    @pytest.mark.asyncio
    async def test_batch_generate_empty_returns_empty(self):
        backend = AsyncMockBackend()
        assert await backend.batch_generate([]) == []

    @pytest.mark.asyncio
    async def test_generate_stream_default_yields_one_chunk(self):
        backend = AsyncMockBackend()
        chunks = []
        async for c in backend.generate_stream("p"):
            chunks.append(c)
        assert len(chunks) == 1

    @pytest.mark.asyncio
    async def test_close_is_noop(self):
        backend = AsyncMockBackend()
        await backend.close()  # must not raise


# ---------------------------------------------------------------------------
# AsyncTraeBackend
# ---------------------------------------------------------------------------


class TestAsyncTraeBackend:
    @pytest.mark.asyncio
    async def test_generate_returns_prompt(self):
        backend = AsyncTraeBackend()
        assert await backend.generate("hello") == "hello"

    @pytest.mark.asyncio
    async def test_is_available_returns_true(self):
        backend = AsyncTraeBackend()
        assert await backend.is_available() is True

    @pytest.mark.asyncio
    async def test_batch_generate_returns_prompts(self):
        backend = AsyncTraeBackend()
        results = await backend.batch_generate(["a", "b"])
        assert results == ["a", "b"]


# ---------------------------------------------------------------------------
# AsyncOpenAIBackend
# ---------------------------------------------------------------------------


class TestAsyncOpenAIBackendInit:
    def test_init_defaults(self):
        backend = AsyncOpenAIBackend(api_key="k")
        assert backend._api_key == "k"
        assert backend.model == "gpt-4"
        assert backend._client is None
        assert backend._semaphore is None
        assert backend._lock is None

    def test_init_custom_params(self):
        backend = AsyncOpenAIBackend(
            api_key="k",
            model="m",
            base_url="https://x",
            temperature=0.7,
            max_tokens=200,
            timeout=30.0,
            max_concurrency=5,
        )
        assert backend.model == "m"
        assert backend.base_url == "https://x"
        assert backend.temperature == 0.7
        assert backend.max_tokens == 200
        assert backend.timeout == 30.0
        assert backend.max_concurrency == 5

    def test_repr(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m", base_url="u")
        assert "model=m" in repr(backend)
        assert "base_url=u" in repr(backend)


class TestAsyncOpenAIBackendGetClient:
    @pytest.mark.asyncio
    async def test_get_client_raises_import_error_when_openai_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "openai", None)
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        with pytest.raises(ImportError, match="openai package required"):
            await backend._get_client()

    @pytest.mark.asyncio
    async def test_get_client_caches_instance(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        fake_openai = MagicMock()
        fake_client = MagicMock()
        fake_openai.AsyncOpenAI.return_value = fake_client
        with patch.dict(sys.modules, {"openai": fake_openai}):
            c1 = await backend._get_client()
            c2 = await backend._get_client()
        assert c1 is c2
        fake_openai.AsyncOpenAI.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_includes_base_url_when_provided(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m", base_url="https://x/v1")
        fake_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": fake_openai}):
            await backend._get_client()
        kwargs = fake_openai.AsyncOpenAI.call_args.kwargs
        assert kwargs["base_url"] == "https://x/v1"

    @pytest.mark.asyncio
    async def test_get_semaphore_creates_once(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m", max_concurrency=3)
        sem1 = await backend._get_semaphore()
        sem2 = await backend._get_semaphore()
        assert sem1 is sem2


class TestAsyncOpenAIBackendGenerate:
    def _make_backend_with_client(self) -> tuple[AsyncOpenAIBackend, MagicMock]:
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client
        return backend, fake_client

    @pytest.mark.asyncio
    async def test_generate_returns_content(self):
        backend, client = self._make_backend_with_client()
        client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content="hi"))]
            )
        )
        assert await backend.generate("p") == "hi"

    @pytest.mark.asyncio
    async def test_generate_returns_empty_when_content_none(self):
        backend, client = self._make_backend_with_client()
        client.chat.completions.create = AsyncMock(
            return_value=MagicMock(
                choices=[MagicMock(message=MagicMock(content=None))]
            )
        )
        assert await backend.generate("p") == ""

    @pytest.mark.asyncio
    async def test_generate_retries_then_succeeds(self, monkeypatch):
        backend, client = self._make_backend_with_client()

        async def _noop_sleep(_s):
            return None

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        # Use the project's helper so the test runs whether or not the
        # openai package is installed.
        transient_exc = _get_openai_retry_exceptions()[0]

        success = MagicMock(choices=[MagicMock(message=MagicMock(content="ok"))])
        client.chat.completions.create = AsyncMock(
            side_effect=[
                transient_exc("boom"),
                success,
            ]
        )
        assert await backend.generate("p") == "ok"
        assert client.chat.completions.create.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_raises_after_all_retries(self, monkeypatch):
        backend, client = self._make_backend_with_client()

        async def _noop_sleep(_s):
            return None

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        transient_exc = _get_openai_retry_exceptions()[0]

        client.chat.completions.create = AsyncMock(
            side_effect=transient_exc("x")
        )
        with pytest.raises(transient_exc):
            await backend.generate("p")
        assert client.chat.completions.create.call_count == backend.MAX_RETRIES


class TestAsyncOpenAIBackendStream:
    @pytest.mark.asyncio
    async def test_generate_stream_yields_non_empty_content(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client

        # Async iterator stub
        class _AsyncIter:
            def __init__(self, items):
                self._items = list(items)
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        chunk1 = MagicMock(choices=[MagicMock(delta=MagicMock(content="a"))])
        chunk2 = MagicMock(choices=[MagicMock(delta=MagicMock(content=""))])
        chunk3 = MagicMock(choices=[MagicMock(delta=MagicMock(content="b"))])
        fake_client.chat.completions.create = AsyncMock(
            return_value=_AsyncIter([chunk1, chunk2, chunk3])
        )
        chunks = []
        async for c in backend.generate_stream("p"):
            chunks.append(c)
        assert chunks == ["a", "b"]


class TestAsyncOpenAIBackendBatch:
    @pytest.mark.asyncio
    async def test_batch_generate_returns_in_order(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m", max_concurrency=3)
        # Patch generate to avoid client init
        backend.generate = AsyncMock(side_effect=lambda p, **_kw: f"r:{p}")

        results = await backend.batch_generate(["a", "b", "c"])
        assert results == ["r:a", "r:b", "r:c"]


class TestAsyncOpenAIBackendAvailability:
    @pytest.mark.asyncio
    async def test_is_available_true_when_client_ok(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        fake_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": fake_openai}):
            assert await backend.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_import_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "openai", None)
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        assert await backend.is_available() is False


class TestAsyncOpenAIBackendClose:
    @pytest.mark.asyncio
    async def test_close_releases_client(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        fake_client = MagicMock()
        fake_client.close = AsyncMock()
        backend._client = fake_client
        await backend.close()
        fake_client.close.assert_awaited_once()
        assert backend._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client_is_noop(self):
        backend = AsyncOpenAIBackend(api_key="k", model="m")
        await backend.close()  # must not raise


# ---------------------------------------------------------------------------
# AsyncAnthropicBackend
# ---------------------------------------------------------------------------


class TestAsyncAnthropicBackendInit:
    def test_init_defaults(self):
        backend = AsyncAnthropicBackend(api_key="k")
        assert backend._api_key == "k"
        assert backend._client is None

    def test_init_custom_params(self):
        backend = AsyncAnthropicBackend(
            api_key="k",
            model="m",
            base_url="https://x",
            max_tokens=99,
            timeout=10.0,
            max_concurrency=2,
        )
        assert backend.model == "m"
        assert backend.base_url == "https://x"
        assert backend.max_tokens == 99
        assert backend.timeout == 10.0
        assert backend.max_concurrency == 2

    def test_repr(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m", base_url="b")
        assert "model=m" in repr(backend)


class TestAsyncAnthropicBackendGetClient:
    @pytest.mark.asyncio
    async def test_get_client_raises_import_error_when_anthropic_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        with pytest.raises(ImportError, match="anthropic package required"):
            await backend._get_client()

    @pytest.mark.asyncio
    async def test_get_client_caches_instance(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        fake_module = MagicMock()
        fake_client = MagicMock()
        fake_module.AsyncAnthropic.return_value = fake_client
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            c1 = await backend._get_client()
            c2 = await backend._get_client()
        assert c1 is c2
        fake_module.AsyncAnthropic.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_client_uses_base_url_when_provided(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m", base_url="https://ant")
        fake_module = MagicMock()
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            await backend._get_client()
        kwargs = fake_module.AsyncAnthropic.call_args.kwargs
        assert kwargs["base_url"] == "https://ant"

    @pytest.mark.asyncio
    async def test_get_semaphore_creates_once(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m", max_concurrency=4)
        s1 = await backend._get_semaphore()
        s2 = await backend._get_semaphore()
        assert s1 is s2


class TestAsyncAnthropicBackendGenerate:
    def _make_backend_with_client(self) -> tuple[AsyncAnthropicBackend, MagicMock]:
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client
        return backend, fake_client

    @pytest.mark.asyncio
    async def test_generate_returns_text(self):
        backend, client = self._make_backend_with_client()
        client.messages.create = AsyncMock(
            return_value=MagicMock(content=[MagicMock(text="hi")])
        )
        assert await backend.generate("p") == "hi"

    @pytest.mark.asyncio
    async def test_generate_returns_empty_when_no_content(self):
        backend, client = self._make_backend_with_client()
        client.messages.create = AsyncMock(return_value=MagicMock(content=[]))
        assert await backend.generate("p") == ""

    @pytest.mark.asyncio
    async def test_generate_retries_then_succeeds(self, monkeypatch):
        backend, client = self._make_backend_with_client()

        async def _noop_sleep(_s):
            return None

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        # Use the project's helper so the test runs whether or not the
        # anthropic package is installed.
        transient_exc = _get_anthropic_retry_exceptions()[0]

        success = MagicMock(content=[MagicMock(text="ok")])
        client.messages.create = AsyncMock(
            side_effect=[
                transient_exc("x"),
                success,
            ]
        )
        assert await backend.generate("p") == "ok"
        assert client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_generate_raises_after_all_retries(self, monkeypatch):
        backend, client = self._make_backend_with_client()

        async def _noop_sleep(_s):
            return None

        monkeypatch.setattr(asyncio, "sleep", _noop_sleep)

        transient_exc = _get_anthropic_retry_exceptions()[0]

        client.messages.create = AsyncMock(
            side_effect=transient_exc("x")
        )
        with pytest.raises(transient_exc):
            await backend.generate("p")
        assert client.messages.create.call_count == backend.MAX_RETRIES


class TestAsyncAnthropicBackendStream:
    @pytest.mark.asyncio
    async def test_generate_stream_yields_text_stream(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client

        # Set up async context manager
        stream_ctx = MagicMock()
        stream_ctx.__aenter__ = AsyncMock(return_value=stream_ctx)
        stream_ctx.__aexit__ = AsyncMock(return_value=False)

        class _AsyncIter:
            def __init__(self, items):
                self._items = list(items)
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._i >= len(self._items):
                    raise StopAsyncIteration
                item = self._items[self._i]
                self._i += 1
                return item

        stream_ctx.text_stream = _AsyncIter(["a", "b", "c"])
        fake_client.messages.stream = MagicMock(return_value=stream_ctx)

        chunks = []
        async for c in backend.generate_stream("p"):
            chunks.append(c)
        assert chunks == ["a", "b", "c"]


class TestAsyncAnthropicBackendBatch:
    @pytest.mark.asyncio
    async def test_batch_generate_returns_in_order(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m", max_concurrency=3)
        backend.generate = AsyncMock(side_effect=lambda p, **_kw: f"r:{p}")
        results = await backend.batch_generate(["a", "b"])
        assert results == ["r:a", "r:b"]


class TestAsyncAnthropicBackendAvailability:
    @pytest.mark.asyncio
    async def test_is_available_true_when_client_ok(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        fake_module = MagicMock()
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            assert await backend.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_on_import_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        assert await backend.is_available() is False


class TestAsyncAnthropicBackendClose:
    @pytest.mark.asyncio
    async def test_close_releases_client(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        fake_client = MagicMock()
        fake_client.close = AsyncMock()
        backend._client = fake_client
        await backend.close()
        fake_client.close.assert_awaited_once()
        assert backend._client is None

    @pytest.mark.asyncio
    async def test_close_when_no_client_is_noop(self):
        backend = AsyncAnthropicBackend(api_key="k", model="m")
        await backend.close()


# ---------------------------------------------------------------------------
# AsyncFallbackBackend
# ---------------------------------------------------------------------------


class TestAsyncFallbackBackendInit:
    @pytest.mark.asyncio
    async def test_empty_backends_raises_value_error(self):
        with pytest.raises(ValueError, match="at least one backend"):
            AsyncFallbackBackend([])

    @pytest.mark.asyncio
    async def test_init_defaults(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        assert fb._active_index == 0
        assert fb._failed_at == {}
        assert fb._lock is None

    @pytest.mark.asyncio
    async def test_repr(self):
        fb = AsyncFallbackBackend([AsyncMockBackend(), AsyncTraeBackend()])
        r = repr(fb)
        assert "AsyncMockBackend" in r
        assert "AsyncTraeBackend" in r

    @pytest.mark.asyncio
    async def test_get_lock_creates_once(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        lock1 = await fb._get_lock()
        lock2 = await fb._get_lock()
        assert lock1 is lock2

    def test_is_cooled_down_true_when_no_failure(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        assert fb._is_cooled_down(repr(AsyncMockBackend())) is True

    def test_is_cooled_down_false_within_cooldown(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()], cooldown_seconds=1000.0)
        key = repr(AsyncMockBackend())
        fb._mark_failed(key)
        assert fb._is_cooled_down(key) is False

    def test_is_cooled_down_true_after_cooldown_expires(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()], cooldown_seconds=0.0)
        key = repr(AsyncMockBackend())
        fb._mark_failed(key)
        time.sleep(0.01)
        assert fb._is_cooled_down(key) is True

    def test_mark_failed_records_timestamp(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        key = repr(AsyncMockBackend())
        fb._mark_failed(key)
        assert key in fb._failed_at


class TestAsyncFallbackBackendGenerate:
    @pytest.mark.asyncio
    async def test_generate_uses_primary_first(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        result = await fb.generate("p")
        assert "[MOCK MODE]" in result

    @pytest.mark.asyncio
    async def test_generate_falls_over_on_failure(self):
        primary = MagicMock()
        primary.generate = AsyncMock(side_effect=RuntimeError("p down"))
        secondary = AsyncMockBackend()
        fb = AsyncFallbackBackend([primary, secondary])
        result = await fb.generate("p")
        assert "[MOCK MODE]" in result
        assert fb._active_index == 1

    @pytest.mark.asyncio
    async def test_generate_skips_cooled_down_secondary(self):
        primary = MagicMock()
        primary.generate = AsyncMock(side_effect=RuntimeError("p down"))
        secondary = MagicMock()
        secondary.generate = AsyncMock(side_effect=RuntimeError("s down"))
        fb = AsyncFallbackBackend([primary, secondary], cooldown_seconds=1000.0)
        fb._mark_failed(repr(secondary))
        with pytest.raises(RuntimeError, match="p down"):
            await fb.generate("p")

    @pytest.mark.asyncio
    async def test_generate_raises_when_all_fail(self):
        primary = MagicMock()
        primary.generate = AsyncMock(side_effect=RuntimeError("p down"))
        secondary = MagicMock()
        secondary.generate = AsyncMock(side_effect=RuntimeError("s down"))
        fb = AsyncFallbackBackend([primary, secondary])
        with pytest.raises(RuntimeError, match="s down"):
            await fb.generate("p")

    @pytest.mark.asyncio
    async def test_generate_logs_info_when_switching_to_non_primary(self, caplog):
        primary = MagicMock()
        primary.generate = AsyncMock(side_effect=RuntimeError("p down"))
        secondary = AsyncMockBackend()
        fb = AsyncFallbackBackend([primary, secondary])
        with caplog.at_level("INFO"):
            await fb.generate("p")
        assert any("switched to" in rec.message for rec in caplog.records)


class TestAsyncFallbackBackendStream:
    @pytest.mark.asyncio
    async def test_generate_stream_uses_primary(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        chunks = []
        async for c in fb.generate_stream("p"):
            chunks.append(c)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_generate_stream_falls_over_on_failure(self):
        primary = MagicMock()

        async def _fail_stream(_p, **_kw):
            raise RuntimeError("p stream down")
            yield  # pragma: no cover - make it an async generator

        primary.generate_stream = _fail_stream
        secondary = AsyncMockBackend()
        fb = AsyncFallbackBackend([primary, secondary])
        chunks = []
        async for c in fb.generate_stream("p"):
            chunks.append(c)
        assert len(chunks) >= 1

    @pytest.mark.asyncio
    async def test_generate_stream_raises_when_all_fail(self):
        primary = MagicMock()

        async def _fail_stream_a(_p, **_kw):
            raise RuntimeError("p stream down")
            yield  # pragma: no cover

        primary.generate_stream = _fail_stream_a
        secondary = MagicMock()

        async def _fail_stream_b(_p, **_kw):
            raise RuntimeError("s stream down")
            yield  # pragma: no cover

        secondary.generate_stream = _fail_stream_b
        fb = AsyncFallbackBackend([primary, secondary])
        with pytest.raises(RuntimeError, match="s stream down"):
            async for _ in fb.generate_stream("p"):
                pass

    @pytest.mark.asyncio
    async def test_generate_stream_skips_cooled_down_secondary(self):
        primary = MagicMock()

        async def _fail_stream_a(_p, **_kw):
            raise RuntimeError("p stream down")
            yield  # pragma: no cover

        primary.generate_stream = _fail_stream_a
        secondary = MagicMock()

        async def _fail_stream_b(_p, **_kw):
            raise RuntimeError("s stream down")
            yield  # pragma: no cover

        secondary.generate_stream = _fail_stream_b
        fb = AsyncFallbackBackend([primary, secondary], cooldown_seconds=1000.0)
        fb._mark_failed(repr(secondary))
        with pytest.raises(RuntimeError, match="p stream down"):
            async for _ in fb.generate_stream("p"):
                pass


class TestAsyncFallbackBackendBatch:
    @pytest.mark.asyncio
    async def test_batch_generate_returns_in_order(self):
        fb = AsyncFallbackBackend([AsyncMockBackend()])
        results = await fb.batch_generate(["a", "b", "c"])
        assert len(results) == 3
        assert all(isinstance(r, str) for r in results)


class TestAsyncFallbackBackendAvailability:
    @pytest.mark.asyncio
    async def test_is_available_true_when_any_available(self):
        primary = MagicMock()
        primary.is_available = AsyncMock(return_value=False)
        secondary = AsyncMockBackend()
        fb = AsyncFallbackBackend([primary, secondary])
        assert await fb.is_available() is True

    @pytest.mark.asyncio
    async def test_is_available_false_when_all_unavailable(self):
        primary = MagicMock()
        primary.is_available = AsyncMock(return_value=False)
        secondary = MagicMock()
        secondary.is_available = AsyncMock(return_value=False)
        fb = AsyncFallbackBackend([primary, secondary])
        assert await fb.is_available() is False


class TestAsyncFallbackBackendClose:
    @pytest.mark.asyncio
    async def test_close_closes_all_backends(self):
        primary = MagicMock()
        primary.close = AsyncMock()
        secondary = MagicMock()
        secondary.close = AsyncMock()
        fb = AsyncFallbackBackend([primary, secondary])
        await fb.close()
        primary.close.assert_awaited_once()
        secondary.close.assert_awaited_once()


# ---------------------------------------------------------------------------
# AsyncLLMBackendFactory
# ---------------------------------------------------------------------------


class TestAsyncLLMBackendFactory:
    @pytest.mark.asyncio
    async def test_create_mock(self):
        backend = AsyncLLMBackendFactory.create("mock", _force_type=True)
        assert isinstance(backend, AsyncMockBackend)

    @pytest.mark.asyncio
    async def test_create_trae(self):
        backend = AsyncLLMBackendFactory.create("trae", _force_type=True)
        assert isinstance(backend, AsyncTraeBackend)

    @pytest.mark.asyncio
    async def test_create_openai_with_kwargs(self):
        backend = AsyncLLMBackendFactory.create(
            "openai", api_key="k", model="m", _force_type=True
        )
        assert isinstance(backend, AsyncOpenAIBackend)
        assert backend._api_key == "k"
        assert backend.model == "m"

    @pytest.mark.asyncio
    async def test_create_anthropic_with_kwargs(self):
        backend = AsyncLLMBackendFactory.create(
            "anthropic", api_key="k", model="m", _force_type=True
        )
        assert isinstance(backend, AsyncAnthropicBackend)
        assert backend._api_key == "k"

    @pytest.mark.asyncio
    async def test_create_unknown_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown backend type"):
            AsyncLLMBackendFactory.create("nonexistent", _force_type=True)

    @pytest.mark.asyncio
    async def test_create_auto_with_no_keys_returns_mock(self, monkeypatch):
        for var in (
            "DEVSQUAD_OPENAI_API_KEY",
            "DEVSQUAD_ANTHROPIC_API_KEY",
            "DEVSQUAD_LLM_BACKEND",
        ):
            monkeypatch.delenv(var, raising=False)
        backend = AsyncLLMBackendFactory.create("auto")
        assert isinstance(backend, AsyncMockBackend)

    @pytest.mark.asyncio
    async def test_create_auto_with_anthropic_key_returns_fallback(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_API_KEY", "ant-k")
        monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
        backend = AsyncLLMBackendFactory.create("auto")
        assert isinstance(backend, AsyncFallbackBackend)
        assert isinstance(backend._backends[0], AsyncAnthropicBackend)
        assert isinstance(backend._backends[-1], AsyncMockBackend)

    @pytest.mark.asyncio
    async def test_create_auto_with_openai_key_returns_fallback(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "oai-k")
        monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
        backend = AsyncLLMBackendFactory.create("auto")
        assert isinstance(backend, AsyncFallbackBackend)
        assert isinstance(backend._backends[0], AsyncOpenAIBackend)
        assert isinstance(backend._backends[-1], AsyncMockBackend)

    @pytest.mark.asyncio
    async def test_create_explicit_fallback_with_kwargs(self, monkeypatch):
        monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
        backend = AsyncLLMBackendFactory.create(
            "fallback",
            openai_api_key="oai-k",
            openai_model="oai-m",
            anthropic_api_key="ant-k",
            anthropic_model="ant-m",
        )
        assert isinstance(backend, AsyncFallbackBackend)
        types_in_fb = [type(b) for b in backend._backends]
        assert AsyncAnthropicBackend in types_in_fb
        assert AsyncOpenAIBackend in types_in_fb
        # Explicit fallback mode does NOT auto-append MockBackend
        assert AsyncMockBackend not in types_in_fb

    @pytest.mark.asyncio
    async def test_create_explicit_fallback_no_keys_appends_mock(self, monkeypatch):
        monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
        backend = AsyncLLMBackendFactory.create("fallback")
        assert isinstance(backend, AsyncFallbackBackend)
        assert isinstance(backend._backends[0], AsyncMockBackend)

    @pytest.mark.asyncio
    async def test_env_backend_override_when_auto_and_no_kwargs(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_LLM_BACKEND", "mock")
        backend = AsyncLLMBackendFactory.create("auto")
        assert isinstance(backend, AsyncMockBackend)

    @pytest.mark.asyncio
    async def test_create_openai_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "env-oai")
        monkeypatch.setenv("DEVSQUAD_OPENAI_BASE_URL", "https://env.oai")
        monkeypatch.setenv("DEVSQUAD_OPENAI_MODEL", "env-model")
        backend = AsyncLLMBackendFactory.create("openai", _force_type=True)
        assert isinstance(backend, AsyncOpenAIBackend)
        assert backend._api_key == "env-oai"
        assert backend.base_url == "https://env.oai"
        assert backend.model == "env-model"

    @pytest.mark.asyncio
    async def test_create_anthropic_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_API_KEY", "env-ant")
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_BASE_URL", "https://env.ant")
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_MODEL", "env-ant-model")
        backend = AsyncLLMBackendFactory.create("anthropic", _force_type=True)
        assert isinstance(backend, AsyncAnthropicBackend)
        assert backend._api_key == "env-ant"
        assert backend.base_url == "https://env.ant"
        assert backend.model == "env-ant-model"


# ---------------------------------------------------------------------------
# _load_dotenv_async
# ---------------------------------------------------------------------------


class TestLoadDotenvAsync:
    def test_load_dotenv_async_is_idempotent(self, monkeypatch):
        import scripts.collaboration.async_llm_backend as alb

        monkeypatch.setattr(alb, "_DOTENV_LOADED_ASYNC", False)
        alb._load_dotenv_async()
        assert alb._DOTENV_LOADED_ASYNC is True
        # Second call: no-op
        alb._load_dotenv_async()
        assert alb._DOTENV_LOADED_ASYNC is True

    def test_load_dotenv_async_silently_skips_when_dotenv_missing(self, monkeypatch):
        import scripts.collaboration.async_llm_backend as alb

        monkeypatch.setattr(alb, "_DOTENV_LOADED_ASYNC", False)
        monkeypatch.setitem(sys.modules, "dotenv", None)
        alb._load_dotenv_async()  # must not raise
        assert alb._DOTENV_LOADED_ASYNC is True


# ---------------------------------------------------------------------------
# AsyncLLMBackendInterface ABC
# ---------------------------------------------------------------------------


class TestAsyncLLMBackendInterfaceABC:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            AsyncLLMBackendInterface()  # type: ignore[abstract]

    @pytest.mark.asyncio
    async def test_default_generate_stream_yields_single_chunk(self):
        class _OneShot(AsyncLLMBackendInterface):
            async def generate(self, prompt: str, **_kwargs: Any) -> str:
                return f"r:{prompt}"

            async def is_available(self) -> bool:
                return True

            async def batch_generate(self, prompts: list[str], **_kw: Any) -> list[str]:
                return [await self.generate(p) for p in prompts]

        backend = _OneShot()
        chunks = []
        async for c in backend.generate_stream("p"):
            chunks.append(c)
        assert chunks == ["r:p"]

    @pytest.mark.asyncio
    async def test_default_close_is_noop(self):
        class _OneShot(AsyncLLMBackendInterface):
            async def generate(self, _prompt: str, **_kwargs: Any) -> str:
                return "r"

            async def is_available(self) -> bool:
                return True

            async def batch_generate(self, _prompts: list[str], **_kw: Any) -> list[str]:
                return []

        backend = _OneShot()
        await backend.close()  # must not raise
