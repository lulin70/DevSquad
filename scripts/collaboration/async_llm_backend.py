#!/usr/bin/env python3
"""
Async LLM Backend Abstraction Layer

Provides asynchronous versions of LLM backends for improved throughput
and reduced latency. Uses asyncio for concurrent request handling.

Key Features:
- Connection pooling via aiohttp.ClientSession (for HTTP-based backends)
- Concurrent batch generation using asyncio.gather
- Streaming support via AsyncGenerator
- Same interface as synchronous version for easy migration

Usage:
    import asyncio

    async def main():
        backend = AsyncLLMBackendFactory.create("mock")
        result = await backend.generate("test task")

        # Batch concurrent requests
        results = await backend.batch_generate(["task1", "task2", "task3"])

    asyncio.run(main())
"""

import asyncio
import logging
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from typing import Any

from scripts.collaboration.llm_backend import (
    DEFAULT_BACKOFF_BASE,
    DEFAULT_COOLDOWN_SECONDS,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL_ANTHROPIC,
    DEFAULT_MODEL_OPENAI,
    DEFAULT_TEMPERATURE,
    DEFAULT_TIMEOUT,
    _get_anthropic_retry_exceptions,
    _get_availability_exceptions,
    _get_fallback_exceptions,
    _get_openai_retry_exceptions,
)

# Async-specific defaults (sync backend has no concurrency concept).
DEFAULT_MAX_CONCURRENCY = 10

logger = logging.getLogger(__name__)


class AsyncLLMBackendInterface(ABC):
    """Abstract base class for async LLM execution backends."""

    @abstractmethod
    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """
        Generate a response from the LLM given a prompt.

        Args:
            prompt: The assembled prompt/instruction text.
            **kwargs: Backend-specific parameters (temperature, max_tokens, etc.)

        Returns:
            str: The LLM's response text.
        """
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Check if the backend is properly configured and available."""
        ...

    @abstractmethod
    async def batch_generate(self, prompts: list[str], **_kwargs: Any) -> list[str]:
        """
        Generate responses for multiple prompts concurrently.

        Args:
            prompts: List of prompt texts.
            **kwargs: Backend-specific parameters.

        Returns:
            List[str]: List of response texts in the same order as input prompts.
        """
        ...

    async def generate_stream(
        self, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """
        Stream a response from the LLM, yielding chunks as they arrive.

        Default implementation falls back to generate() and yields the full response.
        Subclasses should override for true streaming support.

        Args:
            prompt: The assembled prompt/instruction text.
            **kwargs: Backend-specific parameters.

        Yields:
            str: Chunks of the LLM's response text.
        """
        result = await self.generate(prompt, **kwargs)
        yield result

    async def close(self) -> None:  # noqa: B027
        """Clean up resources (connection pools, etc.)."""
        pass  # intentional no-op: default backend has no resources to release


class AsyncMockBackend(AsyncLLMBackendInterface):
    """
    Default async backend that generates a formatted mock analysis.

    Identical output to MockBackend but with async interface.
    """

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a formatted mock analysis response.

        Args:
            prompt: The assembled prompt/instruction text.
            **kwargs: Optional `role_name` and `task_description` used to
                format the mock output.

        Returns:
            Multi-line string describing the mock analysis.
        """
        role_name = kwargs.get("role_name", "AI Assistant")
        task_desc = kwargs.get("task_description", "")
        lines = [
            f"[MOCK MODE] {role_name} Analysis",
            "=" * 50,
            "",
            f"Task: {task_desc}" if task_desc else "Task: (auto-detected)",
            "",
            "This is a mock response. To get real AI analysis,",
            "set --backend openai (or anthropic) with a valid API key.",
            "",
            f"Prompt length: {len(prompt)} chars",
        ]
        return "\n".join(lines)

    async def is_available(self) -> bool:
        """Return True; the mock backend is always available."""
        return True

    async def batch_generate(self, prompts: list[str], **_kwargs: Any) -> list[str]:
        """Generate mock responses for multiple prompts concurrently.

        Args:
            prompts: List of prompt texts.
            **_kwargs: Ignored keyword arguments forwarded to `generate`.

        Returns:
            List of mock response strings in the same order as `prompts`.
        """
        tasks = [self.generate(p, **_kwargs) for p in prompts]
        return await asyncio.gather(*tasks)


class AsyncTraeBackend(AsyncLLMBackendInterface):
    """
    Async backend for Trae IDE's built-in AI.

    Passthrough that returns the prompt as-is (same as sync version).
    """

    async def generate(self, prompt: str, **_kwargs: Any) -> str:
        """Return the prompt unchanged (Trae passthrough).

        Args:
            prompt: The assembled prompt/instruction text.
            **_kwargs: Ignored keyword arguments.

        Returns:
            The input `prompt` string verbatim.
        """
        return prompt

    async def is_available(self) -> bool:
        """Return True; the Trae passthrough backend is always available."""
        return True

    async def batch_generate(self, prompts: list[str], **_kwargs: Any) -> list[str]:
        """Return all prompts unchanged (Trae passthrough).

        Args:
            prompts: List of prompt texts.
            **_kwargs: Ignored keyword arguments.

        Returns:
            A shallow copy of `prompts` as a list.
        """
        return list(prompts)


class AsyncOpenAIBackend(AsyncLLMBackendInterface):
    """
    Async OpenAI backend using the official openai async client.

    Uses AsyncOpenAI for non-blocking HTTP calls with connection pooling.
    Supports concurrent requests via asyncio.gather in batch_generate().
    """

    DEFAULT_TIMEOUT = DEFAULT_TIMEOUT
    MAX_RETRIES = DEFAULT_MAX_RETRIES
    MAX_CONCURRENCY = DEFAULT_MAX_CONCURRENCY

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL_OPENAI,
        base_url: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float | None = None,
        max_concurrency: int = MAX_CONCURRENCY,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_concurrency = max_concurrency
        self._client: Any | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._lock: asyncio.Lock | None = None

    def __repr__(self) -> str:
        return f"AsyncOpenAIBackend(model={self.model}, base_url={self.base_url})"

    async def _get_client(self) -> Any:
        if self._client is None:
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                if self._client is None:
                    try:
                        from openai import AsyncOpenAI

                        client_kwargs: dict[str, Any] = {
                            "api_key": self._api_key,
                            "timeout": self.timeout,
                        }
                        if self.base_url:
                            client_kwargs["base_url"] = self.base_url
                        self._client = AsyncOpenAI(**client_kwargs)
                    except ImportError:
                        raise ImportError(
                            "openai package required: pip install openai"
                        ) from None
        return self._client

    async def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion for a single prompt using the OpenAI API.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model, temperature, and max_tokens.

        Returns:
            The generated completion text.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        client = await self._get_client()
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.chat.completions.create(
                    model=kwargs.get("model", self.model),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                return response.choices[0].message.content or ""
            except _get_openai_retry_exceptions() as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(DEFAULT_BACKOFF_BASE**attempt)

        raise last_error or RuntimeError(
            f"OpenAI generate failed after {self.MAX_RETRIES} attempts"
        )

    async def generate_stream(
        self, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a completion chunk-by-chunk from the OpenAI API.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model, temperature, and max_tokens.

        Yields:
            str: Each non-empty content delta from the streamed response.
        """
        client = await self._get_client()
        stream = await client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stream=True,
        )
        async for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    async def batch_generate(
        self, prompts: list[str], **kwargs: Any
    ) -> list[str]:
        """Generate completions for multiple prompts concurrently.

        Args:
            prompts: List of prompt strings.
            **kwargs: Optional overrides forwarded to generate().

        Returns:
            List of completion strings in the same order as prompts.
        """
        semaphore = await self._get_semaphore()

        async def _generate_with_limit(prompt: str) -> str:
            async with semaphore:
                return await self.generate(prompt, **kwargs)

        tasks = [_generate_with_limit(p) for p in prompts]
        return await asyncio.gather(*tasks)

    async def is_available(self) -> bool:
        """Check whether the OpenAI backend can be initialized.

        Returns:
            True if the client can be created, False on import or connection errors.
        """
        try:
            await self._get_client()
            return True
        except _get_availability_exceptions():  # health check must never crash
            return False

    async def close(self) -> None:
        """Close the underlying OpenAI async client and release resources."""
        if self._client:
            await self._client.close()
            self._client = None


class AsyncAnthropicBackend(AsyncLLMBackendInterface):
    """
    Async Anthropic backend using the official anthropic async client.

    Uses AsyncAnthropic for non-blocking HTTP calls with connection pooling.
    """

    DEFAULT_TIMEOUT = DEFAULT_TIMEOUT
    MAX_RETRIES = DEFAULT_MAX_RETRIES
    MAX_CONCURRENCY = DEFAULT_MAX_CONCURRENCY

    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL_ANTHROPIC,
        base_url: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float | None = None,
        max_concurrency: int = MAX_CONCURRENCY,
    ) -> None:
        self._api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self.max_concurrency = max_concurrency
        self._client: Any | None = None
        self._semaphore: asyncio.Semaphore | None = None
        self._lock: asyncio.Lock | None = None

    def __repr__(self) -> str:
        return f"AsyncAnthropicBackend(model={self.model}, base_url={self.base_url})"

    async def _get_client(self) -> Any:
        if self._client is None:
            if self._lock is None:
                self._lock = asyncio.Lock()
            async with self._lock:
                if self._client is None:
                    try:
                        from anthropic import AsyncAnthropic

                        client_kwargs: dict[str, Any] = {
                            "api_key": self._api_key,
                            "timeout": self.timeout,
                        }
                        if self.base_url:
                            client_kwargs["base_url"] = self.base_url
                        self._client = AsyncAnthropic(**client_kwargs)
                    except ImportError:
                        raise ImportError(
                            "anthropic package required: pip install anthropic"
                        ) from None
        return self._client

    async def _get_semaphore(self) -> asyncio.Semaphore:
        if self._semaphore is None:
            self._semaphore = asyncio.Semaphore(self.max_concurrency)
        return self._semaphore

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion for a single prompt using the Anthropic API.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model and max_tokens.

        Returns:
            The generated completion text.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        client = await self._get_client()
        last_error = None

        for attempt in range(self.MAX_RETRIES):
            try:
                response = await client.messages.create(
                    model=kwargs.get("model", self.model),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text if response.content else ""  # type: ignore[no-any-return]
            except _get_anthropic_retry_exceptions() as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    await asyncio.sleep(DEFAULT_BACKOFF_BASE**attempt)

        raise last_error or RuntimeError(
            f"Anthropic generate failed after {self.MAX_RETRIES} attempts"
        )

    async def generate_stream(
        self, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a completion chunk-by-chunk from the Anthropic API.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model and max_tokens.

        Yields:
            str: Each text delta from the streamed response.
        """
        client = await self._get_client()
        async with client.messages.stream(
            model=kwargs.get("model", self.model),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            async for text in stream.text_stream:
                yield text

    async def batch_generate(
        self, prompts: list[str], **kwargs: Any
    ) -> list[str]:
        """Generate completions for multiple prompts concurrently.

        Args:
            prompts: List of prompt strings.
            **kwargs: Optional overrides forwarded to generate().

        Returns:
            List of completion strings in the same order as prompts.
        """
        semaphore = await self._get_semaphore()

        async def _generate_with_limit(prompt: str) -> str:
            async with semaphore:
                return await self.generate(prompt, **kwargs)

        tasks = [_generate_with_limit(p) for p in prompts]
        return await asyncio.gather(*tasks)

    async def is_available(self) -> bool:
        """Check whether the Anthropic backend can be initialized.

        Returns:
            True if the client can be created, False on import or connection errors.
        """
        try:
            await self._get_client()
            return True
        except _get_availability_exceptions():  # health check must never crash
            return False

    async def close(self) -> None:
        """Close the underlying Anthropic async client and release resources."""
        if self._client:
            await self._client.close()
            self._client = None


class AsyncFallbackBackend(AsyncLLMBackendInterface):
    """
    Async backend with automatic failover across multiple backends.

    Tries each backend in order. If the primary fails (network error,
    rate limit, auth error, etc.), automatically falls back to the next.
    """

    def __init__(
        self,
        backends: list[AsyncLLMBackendInterface],
        cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS,
    ) -> None:
        if not backends:
            raise ValueError(
                "AsyncFallbackBackend requires at least one backend"
            )
        self._backends = backends
        self._cooldown_seconds = cooldown_seconds
        self._failed_at: dict[str, float] = {}
        self._active_index = 0
        self._lock: asyncio.Lock | None = None

    def __repr__(self) -> str:
        names = [type(b).__name__ for b in self._backends]
        return f"AsyncFallbackBackend({names})"

    async def _get_lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def _is_cooled_down(self, backend_repr: str) -> bool:
        failed_time = self._failed_at.get(backend_repr, 0)
        return (time.time() - failed_time) > self._cooldown_seconds

    def _mark_failed(self, backend_repr: str) -> None:
        self._failed_at[backend_repr] = time.time()

    async def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion, failing over to subsequent backends on error.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides forwarded to each backend.

        Returns:
            The first successful completion text.

        Raises:
            RuntimeError: If all backends fail.
        """
        lock = await self._get_lock()
        last_error = None

        async with lock:
            ordered = list(range(len(self._backends)))
            ordered.sort(key=lambda i: (i != self._active_index, i))

        for idx in ordered:
            backend = self._backends[idx]
            backend_repr = repr(backend)

            if idx != self._active_index and not self._is_cooled_down(
                backend_repr
            ):
                continue

            try:
                result: str = await backend.generate(prompt, **kwargs)
                async with lock:
                    self._active_index = idx
                if idx != 0:
                    logger.info(
                        "AsyncFallbackBackend: switched to %s", backend_repr
                    )
                return result
            except _get_fallback_exceptions() as e:  # backend failure -> try next backend
                last_error = e
                self._mark_failed(backend_repr)
                logger.warning(
                    "AsyncFallbackBackend: %s failed (%s), trying next",
                    backend_repr,
                    type(e).__name__,
                )

        raise last_error or RuntimeError(
            "All backends failed with no specific error"
        )

    async def generate_stream(
        self, prompt: str, **kwargs: Any
    ) -> AsyncGenerator[str, None]:
        """Stream a completion, failing over to subsequent backends on error.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides forwarded to each backend.

        Yields:
            str: Content chunks from the first backend that streams successfully.

        Raises:
            RuntimeError: If all backends fail.
        """
        lock = await self._get_lock()
        last_error = None

        async with lock:
            ordered = list(range(len(self._backends)))
            ordered.sort(key=lambda i: (i != self._active_index, i))

        for idx in ordered:
            backend = self._backends[idx]
            backend_repr = repr(backend)

            if idx != self._active_index and not self._is_cooled_down(
                backend_repr
            ):
                continue

            try:
                async with lock:
                    self._active_index = idx
                async for chunk in backend.generate_stream(prompt, **kwargs):
                    yield chunk
                return
            except _get_fallback_exceptions() as e:  # backend stream failure -> try next backend
                last_error = e
                self._mark_failed(backend_repr)
                logger.warning(
                    "AsyncFallbackBackend: %s stream failed (%s), trying next",
                    backend_repr,
                    type(e).__name__,
                )

        raise last_error or RuntimeError(
            "All backends failed with no specific error"
        )

    async def batch_generate(
        self, prompts: list[str], **kwargs: Any
    ) -> list[str]:
        """Generate completions for multiple prompts concurrently.

        Args:
            prompts: List of prompt strings.
            **kwargs: Optional overrides forwarded to generate().

        Returns:
            List of completion strings in the same order as prompts.
        """
        tasks = [self.generate(p, **kwargs) for p in prompts]
        return await asyncio.gather(*tasks)

    async def is_available(self) -> bool:
        """Check whether at least one underlying backend is available.

        Returns:
            True if any backend reports availability, False otherwise.
        """
        results = await asyncio.gather(
            *[b.is_available() for b in self._backends]
        )
        return any(results)

    async def close(self) -> None:
        """Close all underlying backends and release their resources."""
        for backend in self._backends:
            await backend.close()


class AsyncLLMBackendFactory:
    """
    Factory class for creating async LLM backends.

    Provides a unified interface to create any supported async backend type.
    Mirrors the sync create_backend() function signature for consistency.
    """

    @staticmethod
    def create(
        backend_type: str = "auto", **kwargs: Any
    ) -> AsyncLLMBackendInterface:
        """
        Create an async LLM backend by type name.

        Args:
            backend_type: One of 'auto', 'mock', 'trae', 'openai', 'anthropic', 'fallback'.
                        'auto' tries real backends first, then falls back to mock.
            **kwargs: Backend-specific configuration parameters.

        Returns:
            AsyncLLMBackendInterface: Async backend instance.

        Raises:
            ValueError: If backend_type is not recognized.
        """
        import os

        _load_dotenv_async()

        env_backend = os.environ.get(
            "DEVSQUAD_LLM_BACKEND", "auto"
        ).lower()

        if backend_type == "auto" and not kwargs and env_backend in ("openai", "anthropic", "fallback", "mock", "trae"):
            backend_type = env_backend

        if kwargs.pop("_force_type", None):
            pass  # intentional no-op: skip env override when explicitly forced

        if backend_type in ("fallback", "auto"):
            return AsyncLLMBackendFactory._create_fallback(backend_type=backend_type, **kwargs)

        backends = {
            "mock": AsyncMockBackend,
            "trae": AsyncTraeBackend,
            "openai": AsyncOpenAIBackend,
            "anthropic": AsyncAnthropicBackend,
        }
        cls = backends.get(backend_type.lower())
        if cls is None:
            raise ValueError(
                f"Unknown backend type: {backend_type}. "
                f"Available: {list(backends.keys())}"
            )

        if cls == AsyncOpenAIBackend:
            kwargs.setdefault(
                "api_key", os.environ.get("DEVSQUAD_OPENAI_API_KEY")
            )
            kwargs.setdefault(
                "base_url", os.environ.get("DEVSQUAD_OPENAI_BASE_URL")
            )
            kwargs.setdefault(
                "model",
                os.environ.get("DEVSQUAD_OPENAI_MODEL", DEFAULT_MODEL_OPENAI),
            )
        elif cls == AsyncAnthropicBackend:
            kwargs.setdefault(
                "api_key", os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
            )
            kwargs.setdefault(
                "base_url", os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL")
            )
            kwargs.setdefault(
                "model",
                os.environ.get(
                    "DEVSQUAD_ANTHROPIC_MODEL",
                    DEFAULT_MODEL_ANTHROPIC,
                ),
            )

        return cls(**kwargs)  # type: ignore[no-any-return]

    @staticmethod
    def _create_fallback(
        backend_type: str = "fallback", **kwargs: Any
    ) -> AsyncLLMBackendInterface:
        import os

        anthropic_key = kwargs.pop("anthropic_api_key", None) or os.environ.get(
            "DEVSQUAD_ANTHROPIC_API_KEY"
        )
        openai_key = kwargs.pop("openai_api_key", None) or os.environ.get(
            "DEVSQUAD_OPENAI_API_KEY"
        )
        backends_list: list[AsyncLLMBackendInterface] = []

        if anthropic_key:
            backends_list.append(
                AsyncAnthropicBackend(
                    api_key=anthropic_key,
                    base_url=kwargs.pop("anthropic_base_url", None)
                    or os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL"),
                    model=kwargs.pop("anthropic_model", None)
                    or os.environ.get(
                        "DEVSQUAD_ANTHROPIC_MODEL",
                        DEFAULT_MODEL_ANTHROPIC,
                    ),
                    max_tokens=kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS),
                    timeout=kwargs.pop("timeout", None),
                )
            )

        if openai_key:
            backends_list.append(
                AsyncOpenAIBackend(
                    api_key=openai_key,
                    base_url=kwargs.pop("openai_base_url", None)
                    or os.environ.get("DEVSQUAD_OPENAI_BASE_URL"),
                    model=kwargs.pop("openai_model", None)
                    or os.environ.get("DEVSQUAD_OPENAI_MODEL", DEFAULT_MODEL_OPENAI),
                    max_tokens=kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS),
                    timeout=kwargs.pop("timeout", None),
                )
            )

        if backend_type == "auto":
            # In auto mode, always append MockBackend as the final fallback
            # so real-LLM failures degrade gracefully instead of crashing.
            backends_list.append(AsyncMockBackend())
            if len(backends_list) == 1:
                # No real API keys available: return plain MockBackend to avoid
                # wrapping a single mock inside a FallbackBackend.
                return backends_list[0]
        elif not backends_list:
            backends_list.append(AsyncMockBackend())

        return AsyncFallbackBackend(
            backends_list,
            cooldown_seconds=kwargs.pop("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS),
        )


_DOTENV_LOADED_ASYNC = False


def _load_dotenv_async() -> None:
    """Load .env file if python-dotenv is available.

    Uses a module-level sentinel so the .env file is loaded at most once per
    process, matching the synchronous backend behaviour.
    """
    global _DOTENV_LOADED_ASYNC
    if _DOTENV_LOADED_ASYNC:
        return
    _DOTENV_LOADED_ASYNC = True
    try:
        from pathlib import Path

        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass


async def test_async_backend() -> None:
    """Quick smoke test for async backends."""
    print("Testing AsyncMockBackend...")
    backend = AsyncLLMBackendFactory.create("mock", _force_type=True)
    result = await backend.generate("test task", role_name="AI Assistant")
    assert "MOCK MODE" in result
    print(f"✓ Single generate: {result[:50]}...")

    results = await backend.batch_generate(["task1", "task2", "task3"])
    assert len(results) == 3
    print(f"✓ Batch generate: {len(results)} results")

    available = await backend.is_available()
    assert available is True
    print(f"✓ is_available: {available}")

    await backend.close()
    print("\nAll tests passed! ✓")


if __name__ == "__main__":
    asyncio.run(test_async_backend())
