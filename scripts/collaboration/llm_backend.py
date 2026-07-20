#!/usr/bin/env python3
"""
LLM Backend Abstraction Layer

Provides a pluggable interface for Worker to execute prompts against
different LLM backends. Default is MockBackend (returns assembled prompt).

Usage:
    # Default (mock) - returns assembled prompt as-is
    worker = Worker(..., llm_backend=None)

    # Custom backend (API keys from environment variables)
    from scripts.collaboration.llm_backend import OpenAIBackend
    import os
    backend = OpenAIBackend(api_key=os.environ["OPENAI_API_KEY"], model="gpt-4")
    worker = Worker(..., llm_backend=backend)
"""

import os
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any

from .constants import (
    DEFAULT_LLM_MAX_RETRIES,
    DEFAULT_LLM_MAX_TOKENS,
    DEFAULT_LLM_TEMPERATURE,
    DEFAULT_LLM_TIMEOUT_SECONDS,
)
from .prometheus_metrics import get_metrics

# Shared defaults so sync and async backends stay consistent.
# Magic numbers centralized in .constants — re-exported here for backward compatibility.
DEFAULT_TIMEOUT = DEFAULT_LLM_TIMEOUT_SECONDS
DEFAULT_MAX_TOKENS = DEFAULT_LLM_MAX_TOKENS
DEFAULT_TEMPERATURE = DEFAULT_LLM_TEMPERATURE
DEFAULT_COOLDOWN_SECONDS = 30.0
DEFAULT_BACKOFF_BASE = 2
DEFAULT_MAX_RETRIES = DEFAULT_LLM_MAX_RETRIES
MOCK_SEPARATOR_WIDTH = 50
DEFAULT_MODEL_OPENAI = "gpt-4"
DEFAULT_MODEL_ANTHROPIC = "claude-sonnet-4-20250514"


class LLMBackend(ABC):
    """Abstract base class for LLM execution backends."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs: Any) -> str:
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
    def is_available(self) -> bool:
        """Check if the backend is properly configured and available."""
        ...

    def generate_stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
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
        yield self.generate(prompt, **kwargs)


class MockBackend(LLMBackend):
    """
    Default backend that generates a formatted mock analysis.

    Instead of returning raw prompt text, MockBackend produces a readable
    mock analysis with [MOCK MODE] markers so users can distinguish it
    from real LLM output.
    """

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a formatted mock analysis for the prompt.

        Args:
            prompt: User prompt text.
            **kwargs: Optional role_name and task_description for the mock header.

        Returns:
            Multi-line mock analysis string with [MOCK MODE] markers.
        """
        role_name = kwargs.get("role_name", "AI Assistant")
        task_desc = kwargs.get("task_description", "")
        lines = [
            f"[MOCK MODE] {role_name} Analysis",
            "=" * MOCK_SEPARATOR_WIDTH,
            "",
            f"Task: {task_desc}" if task_desc else "Task: (auto-detected)",
            "",
            "This is a mock response. To get real AI analysis,",
            "set --backend openai (or anthropic) with a valid API key.",
            "",
            f"Prompt length: {len(prompt)} chars",
        ]
        return "\n".join(lines)

    def is_available(self) -> bool:
        """Check whether this backend is available.

        Returns:
            Always True; the mock backend requires no external dependencies.
        """
        return True


class TraeBackend(LLMBackend):
    """
    Backend for Trae IDE's built-in AI.

    In Trae IDE, the AI host executes the prompt. This backend is a
    passthrough that signals the host to execute.
    """

    def generate(self, prompt: str, **_kwargs: Any) -> str:
        """Return the prompt unchanged for the Trae host to execute.

        Args:
            prompt: User prompt text.
            **_kwargs: Unused keyword arguments.

        Returns:
            The prompt string unchanged.
        """
        return prompt

    def is_available(self) -> bool:
        """Check whether this backend is available.

        Returns:
            Always True; the Trae backend is always available inside the IDE.
        """
        return True


class OpenAIBackend(LLMBackend):
    DEFAULT_TIMEOUT = DEFAULT_TIMEOUT
    MAX_RETRIES = DEFAULT_MAX_RETRIES

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("DEVSQUAD_OPENAI_API_KEY")
        self.model = model or os.environ.get("DEVSQUAD_OPENAI_MODEL", DEFAULT_MODEL_OPENAI)
        self.base_url = base_url or os.environ.get("DEVSQUAD_OPENAI_BASE_URL")
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client: Any | None = None
        self._client_lock = __import__("threading").Lock()

    def __repr__(self) -> str:
        return f"OpenAIBackend(model={self.model}, base_url={self.base_url})"

    def _get_client(self) -> Any:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    try:
                        from openai import OpenAI

                        client_kwargs: dict[str, Any] = {"api_key": self._api_key, "timeout": self.timeout}
                        if self.base_url:
                            client_kwargs["base_url"] = self.base_url
                        self._client = OpenAI(**client_kwargs)
                    except ImportError:
                        raise ImportError("openai package required: pip install openai") from None
        return self._client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion for a single prompt using the OpenAI API.

        Retries on transient errors with exponential backoff and records
        Prometheus metrics for each call.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model, temperature, and max_tokens.

        Returns:
            The generated completion text.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        import time

        client = self._get_client()
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            _llm_start = time.time()
            try:
                response = client.chat.completions.create(
                    model=kwargs.get("model", self.model),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                _llm_duration = time.time() - _llm_start
                # Prometheus: record successful LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call("openai", _llm_duration, True)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass
                return response.choices[0].message.content or ""
            except _get_openai_retry_exceptions() as e:
                _llm_duration = time.time() - _llm_start
                last_error = e
                # Prometheus: record failed LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call("openai", _llm_duration, False)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(DEFAULT_BACKOFF_BASE**attempt)
        raise last_error or RuntimeError(f"OpenAI generate failed after {self.MAX_RETRIES} attempts")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """Stream a completion chunk-by-chunk from the OpenAI API.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model, temperature, and max_tokens.

        Yields:
            str: Each non-empty content delta from the streamed response.
        """
        client = self._get_client()
        stream = client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stream=True,
        )
        for chunk in stream:
            # Some OpenAI-compatible providers emit empty choices during stream setup;
            # skip them instead of crashing.
            if not chunk.choices:
                continue
            content = chunk.choices[0].delta.content
            if content:
                yield content

    def is_available(self) -> bool:
        """Check whether the OpenAI backend can be initialized.

        Returns:
            True if the client can be created, False on import or connection errors.
        """
        try:
            self._get_client()
            return True
        except _get_availability_exceptions():  # health check must never crash
            return False


class AnthropicBackend(LLMBackend):
    DEFAULT_TIMEOUT = DEFAULT_TIMEOUT
    MAX_RETRIES = DEFAULT_MAX_RETRIES

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
        self.model = model or os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", DEFAULT_MODEL_ANTHROPIC)
        self.base_url = base_url or os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL")
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client: Any | None = None
        self._client_lock = __import__("threading").Lock()

    def __repr__(self) -> str:
        return f"AnthropicBackend(model={self.model}, base_url={self.base_url})"

    def _get_client(self) -> Any:
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    try:
                        from anthropic import Anthropic

                        client_kwargs: dict[str, Any] = {"api_key": self._api_key, "timeout": self.timeout}
                        if self.base_url:
                            client_kwargs["base_url"] = self.base_url
                        self._client = Anthropic(**client_kwargs)
                    except ImportError:
                        raise ImportError("anthropic package required: pip install anthropic") from None
        return self._client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion for a single prompt using the Anthropic API.

        Retries on transient errors with exponential backoff and records
        Prometheus metrics for each call.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model and max_tokens.

        Returns:
            The generated completion text.

        Raises:
            RuntimeError: If all retry attempts fail.
        """
        import time

        client = self._get_client()
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            _llm_start = time.time()
            try:
                response = client.messages.create(
                    model=kwargs.get("model", self.model),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    messages=[{"role": "user", "content": prompt}],
                )
                _llm_duration = time.time() - _llm_start
                # Prometheus: record successful LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call("anthropic", _llm_duration, True)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass
                return response.content[0].text if response.content else ""
            except _get_anthropic_retry_exceptions() as e:
                _llm_duration = time.time() - _llm_start
                last_error = e
                # Prometheus: record failed LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call("anthropic", _llm_duration, False)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(DEFAULT_BACKOFF_BASE**attempt)
        raise last_error or RuntimeError(f"Anthropic generate failed after {self.MAX_RETRIES} attempts")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """Stream a completion chunk-by-chunk from the Anthropic API.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model and max_tokens.

        Yields:
            str: Each text delta from the streamed response.
        """
        client = self._get_client()
        with client.messages.stream(
            model=kwargs.get("model", self.model),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            yield from stream.text_stream

    def is_available(self) -> bool:
        """Check whether the Anthropic backend can be initialized.

        Returns:
            True if the client can be created, False on import or connection errors.
        """
        try:
            self._get_client()
            return True
        except _get_availability_exceptions():  # health check must never crash
            return False


class FallbackBackend(LLMBackend):
    """
    Backend with automatic failover across multiple backends.

    Tries each backend in order. If the primary fails (network error,
    rate limit, auth error, etc.), automatically falls back to the next.

    Usage:
        primary = AnthropicBackend(api_key="...", model="claude-sonnet-4-6")
        fallback = OpenAIBackend(api_key="...", model="gpt-5.5")
        backend = FallbackBackend([primary, fallback])
    """

    def __init__(self, backends: list[Any], cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        if not backends:
            raise ValueError("FallbackBackend requires at least one backend")
        self._backends = backends
        self._cooldown_seconds = cooldown_seconds
        self._failed_at: dict[str, float] = {}
        self._active_index = 0
        self._lock = __import__("threading").Lock()

    def __repr__(self) -> str:
        names = [type(b).__name__ for b in self._backends]
        return f"FallbackBackend({names})"

    def _is_cooled_down(self, backend_repr: str) -> bool:
        import time

        failed_time = self._failed_at.get(backend_repr, 0)
        return (time.time() - failed_time) > self._cooldown_seconds

    def _mark_failed(self, backend_repr: str) -> None:
        import time

        self._failed_at[backend_repr] = time.time()

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion, failing over to subsequent backends on error.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides forwarded to each backend.

        Returns:
            The first successful completion text.

        Raises:
            RuntimeError: If all backends fail.
        """
        import logging
        import time

        logger = logging.getLogger(__name__)
        last_error = None

        with self._lock:
            ordered = list(range(len(self._backends)))
            ordered.sort(key=lambda i: (i != self._active_index, i))

        for idx in ordered:
            backend = self._backends[idx]
            backend_repr = repr(backend)
            backend_name = type(backend).__name__.replace("Backend", "").lower()

            if idx != self._active_index and not self._is_cooled_down(backend_repr):
                continue

            try:
                _llm_start = time.time()
                result: str = backend.generate(prompt, **kwargs)
                _llm_duration = time.time() - _llm_start
                with self._lock:
                    self._active_index = idx
                if idx != 0:
                    logger.info("FallbackBackend: switched to %s", backend_repr)
                # Prometheus: record successful LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call(backend_name, _llm_duration, True)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass
                return result
            except _get_fallback_exceptions() as e:  # backend failure -> try next backend
                last_error = e
                _llm_duration = time.time() - _llm_start if "_llm_start" in dir() else 0
                self._mark_failed(backend_repr)
                logger.warning(
                    "FallbackBackend: %s failed (%s), trying next",
                    backend_repr,
                    type(e).__name__,
                )
                # Prometheus: record failed LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call(backend_name, _llm_duration, False)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass

        raise last_error or RuntimeError("All backends failed with no specific error")

    def generate_stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """Stream a completion, failing over to subsequent backends on error.

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides forwarded to each backend.

        Yields:
            str: Content chunks from the first backend that streams successfully.

        Raises:
            RuntimeError: If all backends fail.
        """
        import logging

        logger = logging.getLogger(__name__)
        last_error = None

        with self._lock:
            ordered = list(range(len(self._backends)))
            ordered.sort(key=lambda i: (i != self._active_index, i))

        for idx in ordered:
            backend = self._backends[idx]
            backend_repr = repr(backend)

            if idx != self._active_index and not self._is_cooled_down(backend_repr):
                continue

            try:
                with self._lock:
                    self._active_index = idx
                yield from backend.generate_stream(prompt, **kwargs)
                return
            except _get_fallback_exceptions() as e:  # backend stream failure -> try next backend
                last_error = e
                self._mark_failed(backend_repr)
                logger.warning(
                    "FallbackBackend: %s stream failed (%s), trying next",
                    backend_repr,
                    type(e).__name__,
                )

        raise last_error or RuntimeError("All backends failed with no specific error")

    def is_available(self) -> bool:
        """Check whether at least one underlying backend is available.

        Returns:
            True if any backend reports availability, False otherwise.
        """
        return any(b.is_available() for b in self._backends)


def create_backend(backend_type: str = "auto", **kwargs: Any) -> LLMBackend:
    """
    Factory function to create an LLM backend by type name.

    Automatically reads configuration from environment variables when not
    explicitly provided via kwargs. Supports .env file loading.

    Environment Variables:
        DEVSQUAD_LLM_BACKEND: Default backend type (auto|mock|trae|openai|anthropic|moka|fallback)
        DEVSQUAD_OPENAI_API_KEY: OpenAI API key
        DEVSQUAD_OPENAI_BASE_URL: OpenAI-compatible base URL
        DEVSQUAD_OPENAI_MODEL: OpenAI model name
        DEVSQUAD_ANTHROPIC_API_KEY: Anthropic API key
        DEVSQUAD_ANTHROPIC_BASE_URL: Anthropic-compatible base URL
        DEVSQUAD_ANTHROPIC_MODEL: Anthropic model name
        MOKA_API_KEY: Moka AI API key (OpenAI-compatible)
        MOKA_API_BASE: Moka AI base URL (default: https://api.moka-ai.com/v1)
        MOKA_MODEL: Moka AI model name (default: moka/claude-sonnet-4-6)

    Args:
        backend_type: One of 'auto', 'mock', 'trae', 'openai', 'anthropic', 'moka', 'fallback'.
                      If not specified, reads from DEVSQUAD_LLM_BACKEND env var.
                      'auto' tries real backends first, then falls back to mock.
                      'moka' uses OpenAIBackend with Moka AI's OpenAI-compatible API.
        **kwargs: Backend-specific configuration (overrides env vars)

    Returns:
        LLMBackend instance
    """
    import os

    _load_dotenv()

    env_backend = os.environ.get("DEVSQUAD_LLM_BACKEND", "auto").lower()

    if (
        backend_type == "auto"
        and not kwargs
        and env_backend in ("openai", "anthropic", "moka", "fallback", "mock", "trae")
    ):
        backend_type = env_backend

    if backend_type in ("fallback", "auto"):
        anthropic_key = kwargs.pop("anthropic_api_key", None) or os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
        openai_key = kwargs.pop("openai_api_key", None) or os.environ.get("DEVSQUAD_OPENAI_API_KEY")
        backends_list: list[LLMBackend] = []
        if anthropic_key:
            backends_list.append(
                AnthropicBackend(
                    api_key=anthropic_key,
                    base_url=kwargs.pop("anthropic_base_url", None) or os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL"),
                    model=kwargs.pop("anthropic_model", None)
                    or os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", DEFAULT_MODEL_ANTHROPIC),
                    max_tokens=kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS),
                    timeout=kwargs.pop("timeout", None),
                )
            )
        if openai_key:
            backends_list.append(
                OpenAIBackend(
                    api_key=openai_key,
                    base_url=kwargs.pop("openai_base_url", None) or os.environ.get("DEVSQUAD_OPENAI_BASE_URL"),
                    model=kwargs.pop("openai_model", None)
                    or os.environ.get("DEVSQUAD_OPENAI_MODEL", DEFAULT_MODEL_OPENAI),
                    max_tokens=kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS),
                    timeout=kwargs.pop("timeout", None),
                )
            )
        # Always append MockBackend as the final fallback so real-LLM failures
        # degrade gracefully instead of crashing the dispatch.
        backends_list.append(MockBackend())
        if backend_type == "auto" and len(backends_list) == 1:
            # No real API keys available: return plain MockBackend to avoid
            # wrapping a single mock inside a FallbackBackend.
            return backends_list[0]
        return FallbackBackend(backends_list, cooldown_seconds=kwargs.pop("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS))

    backends = {
        "mock": MockBackend,
        "trae": TraeBackend,
        "openai": OpenAIBackend,
        "anthropic": AnthropicBackend,
        "moka": OpenAIBackend,
    }
    cls = backends.get(backend_type.lower())
    if cls is None:
        raise ValueError(f"Unknown backend type: {backend_type}. Available: {list(backends.keys())}")

    if backend_type.lower() == "moka":
        kwargs.setdefault("api_key", os.environ.get("MOKA_API_KEY"))
        kwargs.setdefault("base_url", os.environ.get("MOKA_API_BASE", "https://api.moka-ai.com/v1"))
        kwargs.setdefault("model", os.environ.get("MOKA_MODEL", "moka/claude-sonnet-4-6"))
    elif cls == OpenAIBackend:
        kwargs.setdefault("api_key", os.environ.get("DEVSQUAD_OPENAI_API_KEY"))
        kwargs.setdefault("base_url", os.environ.get("DEVSQUAD_OPENAI_BASE_URL"))
        kwargs.setdefault("model", os.environ.get("DEVSQUAD_OPENAI_MODEL", DEFAULT_MODEL_OPENAI))
    elif cls == AnthropicBackend:
        kwargs.setdefault("api_key", os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY"))
        kwargs.setdefault("base_url", os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL"))
        kwargs.setdefault("model", os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", DEFAULT_MODEL_ANTHROPIC))

    return cls(**kwargs)


def _get_openai_retry_exceptions() -> tuple[type[BaseException], ...]:
    """Return exceptions that should trigger a retry in OpenAI generate()."""
    try:
        from openai import APIError

        return (ConnectionError, TimeoutError, OSError, APIError)
    except ImportError:
        return (ConnectionError, TimeoutError, OSError)


def _get_anthropic_retry_exceptions() -> tuple[type[BaseException], ...]:
    """Return exceptions that should trigger a retry in Anthropic generate()."""
    try:
        from anthropic import APIError

        return (ConnectionError, TimeoutError, OSError, APIError)
    except ImportError:
        return (ConnectionError, TimeoutError, OSError)


def _get_availability_exceptions() -> tuple[type[BaseException], ...]:
    """Return exceptions that availability/health checks should tolerate."""
    return (ImportError, ConnectionError, TimeoutError, OSError, RuntimeError)


def _get_fallback_exceptions() -> tuple[type[BaseException], ...]:
    """Return exceptions that FallbackBackend should treat as backend failures."""
    exceptions: set[type[BaseException]] = {ConnectionError, TimeoutError, OSError, RuntimeError}
    try:
        from openai import APIError as OpenAIAPIError

        exceptions.add(OpenAIAPIError)
    except ImportError:
        pass
    try:
        from anthropic import APIError as AnthropicAPIError

        exceptions.add(AnthropicAPIError)
    except ImportError:
        pass
    return tuple(exceptions)


_DOTENV_LOADED = False


def _load_dotenv() -> None:
    """Load .env file if python-dotenv is available.

    Uses a module-level sentinel so the .env file is loaded at most once per
    process. This prevents runtime monkey-patching of ``os.environ`` (e.g. in
    tests) from being overwritten on every ``create_backend`` call.
    """
    global _DOTENV_LOADED
    if _DOTENV_LOADED:
        return
    _DOTENV_LOADED = True
    try:
        from pathlib import Path

        from dotenv import load_dotenv

        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
