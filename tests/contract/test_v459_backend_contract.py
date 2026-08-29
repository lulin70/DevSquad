#!/usr/bin/env python3
"""V4.5.9 contract tests — AsyncLLMBackendInterface 契约锁定（AC-W2 前置）。

Locks the async backend contract consumed by Worker.aexecute:
- AsyncMockBackend / AsyncOpenAIBackend are instantiable interface instances
- generate / batch_generate / is_available are coroutine functions
- batch_generate preserves prompt order
"""

import inspect
from typing import Any

import pytest

from scripts.collaboration.async_llm_backend import (
    AsyncLLMBackendInterface,
    AsyncMockBackend,
    AsyncOpenAIBackend,
)


class TestAsyncBackendContract:
    def test_async_mock_backend_is_interface_instance(self):
        assert isinstance(AsyncMockBackend(), AsyncLLMBackendInterface)

    def test_async_openai_backend_is_interface_instance(self):
        backend = AsyncOpenAIBackend(api_key="contract-test")
        assert isinstance(backend, AsyncLLMBackendInterface)

    @pytest.mark.parametrize(
        "backend_factory",
        [lambda: AsyncMockBackend(), lambda: AsyncOpenAIBackend(api_key="contract-test")],
        ids=["async_mock", "async_openai"],
    )
    def test_backend_methods_are_coroutine_functions(self, backend_factory):
        backend: Any = backend_factory()
        assert inspect.iscoroutinefunction(backend.generate)
        assert inspect.iscoroutinefunction(backend.batch_generate)
        assert inspect.iscoroutinefunction(backend.is_available)

    @pytest.mark.asyncio
    async def test_batch_generate_preserves_order(self):
        """Order contract: results align with prompts (distinguished by length)."""
        backend = AsyncMockBackend()
        short_prompt = "ab"
        long_prompt = "a" * 64
        results = await backend.batch_generate([short_prompt, long_prompt])

        assert len(results) == 2
        assert f"Prompt length: {len(short_prompt)} chars" in results[0]
        assert f"Prompt length: {len(long_prompt)} chars" in results[1]
