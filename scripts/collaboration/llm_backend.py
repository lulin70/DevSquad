#!/usr/bin/env python3
# -*- coding: utf-8 -*-
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

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Generator


class LLMBackend(ABC):
    """Abstract base class for LLM execution backends."""

    @abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
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

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
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

    def generate(self, prompt: str, **kwargs) -> str:
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

    def is_available(self) -> bool:
        return True


class TraeBackend(LLMBackend):
    """
    Backend for Trae IDE's built-in AI.

    In Trae IDE, the AI host executes the prompt. This backend is a
    passthrough that signals the host to execute.
    """

    def generate(self, prompt: str, **kwargs) -> str:
        return prompt

    def is_available(self) -> bool:
        return True


class OpenAIBackend(LLMBackend):
    DEFAULT_TIMEOUT = 120
    MAX_RETRIES = 3

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: Optional[int] = None,
    ):
        self._api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client = None
        self._client_lock = __import__('threading').Lock()

    def __repr__(self):
        return f"OpenAIBackend(model={self.model}, base_url={self.base_url})"

    def _get_client(self):
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    try:
                        from openai import OpenAI
                        kwargs = {"api_key": self._api_key, "timeout": self.timeout}
                        if self.base_url:
                            kwargs["base_url"] = self.base_url
                        self._client = OpenAI(**kwargs)
                    except ImportError:
                        raise ImportError("openai package required: pip install openai")
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        import time
        client = self._get_client()
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=kwargs.get("model", self.model),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                return response.choices[0].message.content or ""
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        raise last_error

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        client = self._get_client()
        stream = client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            stream=True,
        )
        for chunk in stream:
            content = chunk.choices[0].delta.content
            if content:
                yield content

    def is_available(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception:
            return False


class AnthropicBackend(LLMBackend):
    DEFAULT_TIMEOUT = 120
    MAX_RETRIES = 3

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        base_url: Optional[str] = None,
        max_tokens: int = 4096,
        timeout: Optional[int] = None,
    ):
        self._api_key = api_key
        self.model = model
        self.base_url = base_url
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client = None
        self._client_lock = __import__('threading').Lock()

    def __repr__(self):
        return f"AnthropicBackend(model={self.model}, base_url={self.base_url})"

    def _get_client(self):
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    try:
                        from anthropic import Anthropic
                        kwargs = {"api_key": self._api_key, "timeout": self.timeout}
                        if self.base_url:
                            kwargs["base_url"] = self.base_url
                        self._client = Anthropic(**kwargs)
                    except ImportError:
                        raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        import time
        client = self._get_client()
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.messages.create(
                    model=kwargs.get("model", self.model),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text if response.content else ""
            except Exception as e:
                last_error = e
                if attempt < self.MAX_RETRIES - 1:
                    time.sleep(2 ** attempt)
        raise last_error

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        client = self._get_client()
        with client.messages.stream(
            model=kwargs.get("model", self.model),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text

    def is_available(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception:
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

    def __init__(self, backends: list, cooldown_seconds: float = 30.0):
        if not backends:
            raise ValueError("FallbackBackend requires at least one backend")
        self._backends = backends
        self._cooldown_seconds = cooldown_seconds
        self._failed_at: Dict[str, float] = {}
        self._active_index = 0
        self._lock = __import__('threading').Lock()

    def __repr__(self):
        names = [type(b).__name__ for b in self._backends]
        return f"FallbackBackend({names})"

    def _is_cooled_down(self, backend_repr: str) -> bool:
        import time
        failed_time = self._failed_at.get(backend_repr, 0)
        return (time.time() - failed_time) > self._cooldown_seconds

    def _mark_failed(self, backend_repr: str):
        import time
        self._failed_at[backend_repr] = time.time()

    def generate(self, prompt: str, **kwargs) -> str:
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
                result = backend.generate(prompt, **kwargs)
                with self._lock:
                    self._active_index = idx
                if idx != 0:
                    logger.info("FallbackBackend: switched to %s", backend_repr)
                return result
            except Exception as e:
                last_error = e
                self._mark_failed(backend_repr)
                logger.warning(
                    "FallbackBackend: %s failed (%s), trying next",
                    backend_repr, type(e).__name__,
                )

        raise last_error

    def generate_stream(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        import logging
        logger = logging.getLogger(__name__)

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
                for chunk in backend.generate_stream(prompt, **kwargs):
                    yield chunk
                return
            except Exception as e:
                self._mark_failed(backend_repr)
                logger.warning(
                    "FallbackBackend: %s stream failed (%s), trying next",
                    backend_repr, type(e).__name__,
                )

        raise last_error

    def is_available(self) -> bool:
        return any(b.is_available() for b in self._backends)


def create_backend(backend_type: str = "mock", **kwargs) -> LLMBackend:
    """
    Factory function to create an LLM backend by type name.

    Automatically reads configuration from environment variables when not
    explicitly provided via kwargs. Supports .env file loading.

    Environment Variables:
        DEVSQUAD_LLM_BACKEND: Default backend type (mock|trae|openai|anthropic)
        DEVSQUAD_OPENAI_API_KEY: OpenAI API key
        DEVSQUAD_OPENAI_BASE_URL: OpenAI-compatible base URL
        DEVSQUAD_OPENAI_MODEL: OpenAI model name
        DEVSQUAD_ANTHROPIC_API_KEY: Anthropic API key
        DEVSQUAD_ANTHROPIC_BASE_URL: Anthropic-compatible base URL
        DEVSQUAD_ANTHROPIC_MODEL: Anthropic model name

    Args:
        backend_type: One of 'mock', 'trae', 'openai', 'anthropic'.
                      If not specified, reads from DEVSQUAD_LLM_BACKEND env var.
        **kwargs: Backend-specific configuration (overrides env vars)

    Returns:
        LLMBackend instance
    """
    import os

    _load_dotenv()

    env_backend = os.environ.get("DEVSQUAD_LLM_BACKEND", "mock").lower()

    if backend_type == "mock" and not kwargs:
        if env_backend in ("openai", "anthropic", "fallback"):
            backend_type = env_backend

    if backend_type == "fallback":
        anthropic_key = kwargs.pop("anthropic_api_key", None) or os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
        openai_key = kwargs.pop("openai_api_key", None) or os.environ.get("DEVSQUAD_OPENAI_API_KEY")
        backends_list = []
        if anthropic_key:
            backends_list.append(AnthropicBackend(
                api_key=anthropic_key,
                base_url=kwargs.pop("anthropic_base_url", None) or os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL"),
                model=kwargs.pop("anthropic_model", None) or os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=kwargs.pop("max_tokens", 4096),
                timeout=kwargs.pop("timeout", None),
            ))
        if openai_key:
            backends_list.append(OpenAIBackend(
                api_key=openai_key,
                base_url=kwargs.pop("openai_base_url", None) or os.environ.get("DEVSQUAD_OPENAI_BASE_URL"),
                model=kwargs.pop("openai_model", None) or os.environ.get("DEVSQUAD_OPENAI_MODEL", "gpt-4"),
                max_tokens=kwargs.pop("max_tokens", 4096),
                timeout=kwargs.pop("timeout", None),
            ))
        if not backends_list:
            backends_list.append(MockBackend())
        return FallbackBackend(backends_list, cooldown_seconds=kwargs.pop("cooldown_seconds", 30.0))

    backends = {
        "mock": MockBackend,
        "trae": TraeBackend,
        "openai": OpenAIBackend,
        "anthropic": AnthropicBackend,
    }
    cls = backends.get(backend_type.lower())
    if cls is None:
        raise ValueError(f"Unknown backend type: {backend_type}. Available: {list(backends.keys())}")

    if cls == OpenAIBackend:
        kwargs.setdefault("api_key", os.environ.get("DEVSQUAD_OPENAI_API_KEY"))
        kwargs.setdefault("base_url", os.environ.get("DEVSQUAD_OPENAI_BASE_URL"))
        kwargs.setdefault("model", os.environ.get("DEVSQUAD_OPENAI_MODEL", "gpt-4"))
    elif cls == AnthropicBackend:
        kwargs.setdefault("api_key", os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY"))
        kwargs.setdefault("base_url", os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL"))
        kwargs.setdefault("model", os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"))

    return cls(**kwargs)


def _load_dotenv():
    """Load .env file if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
        from pathlib import Path
        env_path = Path(__file__).parent.parent.parent / ".env"
        if env_path.exists():
            load_dotenv(env_path)
    except ImportError:
        pass
