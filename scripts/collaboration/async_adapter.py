#!/usr/bin/env python3
"""
Preview: Not yet integrated into the main dispatch pipeline.

Async Adapter - Backward Compatibility Layer

Provides seamless migration from sync to async backends.
Allows existing synchronous code to use async implementations
without modification.

Key Components:
- AsyncToSyncAdapter: Wraps async backends for sync usage
- AutoBackendSelector: Automatically chooses optimal backend
- Environment detection and fallback logic

Usage:
    # Option 1: Explicit adapter (for existing sync code)
    from scripts.collaboration.async_adapter import AsyncToSyncAdapter
    from scripts.collaboration.async_llm_backend import AsyncLLMBackendFactory

    async_backend = AsyncLLMBackendFactory.create("openai")
    sync_adapter = AsyncToSyncAdapter(async_backend)
    result = sync_adapter.generate("test")  # Works in sync context!

    # Option 2: Auto-detection (recommended)
    from scripts.collaboration.async_adapter import get_optimal_backend

    backend = get_optimal_backend()  # Auto-selects best backend
    result = backend.generate("test")
"""

import asyncio
import logging
import os
from typing import Any, List, Optional


from .async_coordinator import AsyncCoordinator
from .async_llm_backend import (
    AsyncLLMBackendInterface,
    AsyncLLMBackendFactory,
)
from .llm_backend import LLMBackend, create_backend


logger = logging.getLogger(__name__)


class AsyncToSyncAdapter(LLMBackend):
    """
    Adapter that wraps an async LLM backend for synchronous usage.

    Runs async methods in a new event loop (or reuses existing one).
    Allows gradual migration: keep sync API while using async internals.

    Example:
        async_backend = AsyncLLMBackendFactory.create("openai")
        sync_backend = AsyncToSyncAdapter(async_backend)

        # Now usable anywhere sync backend is expected
        result = sync_backend.generate("prompt text")
    """

    def __init__(self, async_backend: AsyncLLMBackendInterface) -> None:
        self._async_backend = async_backend
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def __repr__(self) -> str:
        return f"AsyncToSyncAdapter({repr(self._async_backend)})"

    def _get_loop(self) -> asyncio.AbstractEventLoop:
        """Get or create event loop."""
        try:
            loop = asyncio.get_running_loop()
            return loop
        except RuntimeError:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
            return self._loop

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Synchronous wrapper around async generate().

        Args:
            prompt: Prompt text.
            **kwargs: Backend parameters.

        Returns:
            str: LLM response.
        """
        loop = self._get_loop()

        try:

            async def _run():
                return await self._async_backend.generate(prompt, **kwargs)

            if loop.is_running():

                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._async_backend.generate(prompt, **kwargs),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(_run())
        finally:
            if not loop.is_running():
                pass

    def is_available(self) -> bool:
        """Check availability synchronously."""
        loop = self._get_loop()

        try:

            async def _check():
                return await self._async_backend.is_available()

            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(
                        asyncio.run,
                        self._async_backend.is_available(),
                    )
                    return future.result()
            else:
                return loop.run_until_complete(_check())
        finally:
            if not loop.is_running():
                pass


class SyncToAsyncAdapter(AsyncLLMBackendInterface):
    """
    Adapter that wraps a sync LLM backend for async usage.

    Useful when you have a sync backend but need to use it
    in async context (e.g., with AsyncCoordinator).

    Example:
        sync_backend = create_backend("openai")
        async_adapter = SyncToAsyncAdapter(sync_backend)

        # Now usable in async context
        result = await async_adapter.generate("prompt text")
    """

    def __init__(self, sync_backend: LLMBackend) -> None:
        self._sync_backend = sync_backend

    def __repr__(self) -> str:
        return f"SyncToAsyncAdapter({repr(self._sync_backend)})"

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Execute sync generate in executor."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, lambda: self._sync_backend.generate(prompt, **kwargs)
        )

    async def is_available(self) -> bool:
        """Check availability."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None, self._sync_backend.is_available
        )

    async def batch_generate(
        self, prompts: List[str], **kwargs: Any
    ) -> List[str]:
        """Batch execute with concurrency via gather."""
        tasks = [self.generate(p, **kwargs) for p in prompts]
        return await asyncio.gather(*tasks)


class AutoBackendSelector:
    """
    Automatically selects the optimal backend based on environment.

    Selection Logic:
    1. If DEVSQUAD_USE_ASYNC=true → Use async backend
    2. If running in async context (event loop running) → Use async
    3. Otherwise → Use sync backend (safer default)

    Also handles graceful degradation: if async backend fails to initialize,
    falls back to sync version automatically.
    """

    @staticmethod
    def should_use_async() -> bool:
        """
        Determine if async backend should be used.

        Returns:
            bool: True if async is preferred.
        """
        env_async = os.environ.get("DEVSQUAD_USE_ASYNC", "").lower()
        if env_async in ("true", "1", "yes"):
            return True
        if env_async in ("false", "0", "no"):
            return False

        try:
            asyncio.get_running_loop()
            return True
        except RuntimeError:
            return False

    @staticmethod
    def get_backend(
        backend_type: str = "mock", **kwargs: Any
    ) -> Any:
        """
        Get the optimal backend (sync or auto).

        Args:
            backend_type: Backend type name.
            **kwargs: Backend configuration.

        Returns:
            Either LLMBackend or AsyncLLMBackendInterface depending on environment.
        """
        if AutoBackendSelector.should_use_async():
            try:
                return AsyncLLMBackendFactory.create(backend_type, **kwargs)
            except Exception as e:
                logger.warning(
                    "Failed to create async backend (%s), falling back to sync",
                    e,
                )
                return create_backend(backend_type, **kwargs)
        else:
            return create_backend(backend_type, **kwargs)


def get_optimal_backend(
    backend_type: str = "mock", **kwargs: Any
) -> Any:
    """
    Convenience function to get the optimal backend.

    Automatically detects environment and returns the best option.

    Args:
        backend_type: Backend type ('mock', 'openai', 'anthropic', etc.)
        **kwargs: Backend-specific config

    Returns:
        Optimal backend instance (sync or async)

    Example:
        # In async code:
        backend = get_optimal_backend("openai")
        if hasattr(backend, 'generate'):  # Works for both!
            result = await backend.generate(...) if asyncio.iscoroutinefunction(backend.generate) else backend.generate(...)
    """
    return AutoBackendSelector.get_backend(backend_type, **kwargs)


def wrap_for_sync(async_backend: AsyncLLMBackendInterface) -> LLMBackend:
    """
    Wrap an async backend for synchronous usage.

    Args:
        async_backend: Async backend instance

    Returns:
        Synchronous adapter
    """
    return AsyncToSyncAdapter(async_backend)


def wrap_for_async(sync_backend: LLMBackend) -> AsyncLLMBackendInterface:
    """
    Wrap a sync backend for asynchronous usage.

    Args:
        sync_backend: Sync backend instance

    Returns:
        Async adapter
    """
    return SyncToAsyncAdapter(sync_backend)


async def test_adapter():
    """Test the adapter layer."""
    print("Testing Async Adapter...")

    # Test 1: SyncToAsyncAdapter
    print("\n1. Testing SyncToAsyncAdapter...")
    from .llm_backend import MockBackend

    sync_mock = MockBackend()
    async_mock = SyncToAsyncAdapter(sync_mock)

    result = await async_mock.generate("test", role_name="Tester")
    assert "MOCK MODE" in result
    print(f"   ✓ Sync→Async: {result[:40]}...")

    results = await async_mock.batch_generate(["a", "b", "c"])
    assert len(results) == 3
    print(f"   ✓ Batch: {len(results)} results")

    available = await async_mock.is_available()
    assert available is True
    print(f"   ✓ Available: {available}")

    # Test 2: AsyncToSyncAdapter
    print("\n2. Testing AsyncToSyncAdapter...")
    from .async_llm_backend import AsyncMockBackend

    async_mock_raw = AsyncMockBackend()
    sync_adapter = AsyncToSyncAdapter(async_mock_raw)

    sync_result = sync_adapter.generate("test", role_name="Tester")
    assert "MOCK MODE" in sync_result
    print(f"   ✓ Async→Sync: {sync_result[:40]}...")

    sync_available = sync_adapter.is_available()
    assert sync_available is True
    print(f"   ✓ Available: {sync_available}")

    # Test 3: AutoBackendSelector
    print("\n3. Testing AutoBackendSelector...")
    backend = get_optimal_backend("mock")
    assert backend is not None
    print(f"   ✓ Auto-selected: {type(backend).__name__}")

    print("\n✓ All adapter tests passed!")


if __name__ == "__main__":
    asyncio.run(test_adapter())
