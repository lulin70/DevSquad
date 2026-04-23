#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Backend Abstraction Layer

Provides a pluggable interface for Worker to execute prompts against
different LLM backends. Default is MockBackend (returns assembled prompt).

Usage:
    # Default (mock) - returns assembled prompt as-is
    worker = Worker(..., llm_backend=None)

    # Custom backend
    from scripts.collaboration.llm_backend import OpenAIBackend
    backend = OpenAIBackend(api_key="...", model="gpt-4")
    worker = Worker(..., llm_backend=backend)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional


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


class MockBackend(LLMBackend):
    """
    Default backend that returns the prompt as-is (dry-run mode).

    This preserves the existing behavior where Worker._do_work() returns
    the assembled instruction without calling any LLM.
    """

    def generate(self, prompt: str, **kwargs) -> str:
        return prompt

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
    """
    Backend for OpenAI-compatible APIs (OpenAI, Azure, local models).

    Requires the 'openai' package: pip install openai
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "gpt-4",
        base_url: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                kwargs = {"api_key": self.api_key}
                if self.base_url:
                    kwargs["base_url"] = self.base_url
                self._client = OpenAI(**kwargs)
            except ImportError:
                raise ImportError("openai package required: pip install openai")
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        client = self._get_client()
        response = client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[{"role": "user", "content": prompt}],
            temperature=kwargs.get("temperature", self.temperature),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
        )
        return response.choices[0].message.content or ""

    def is_available(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception:
            return False


class AnthropicBackend(LLMBackend):
    """
    Backend for Anthropic Claude API.

    Requires the 'anthropic' package: pip install anthropic
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
    ):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from anthropic import Anthropic
                self._client = Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("anthropic package required: pip install anthropic")
        return self._client

    def generate(self, prompt: str, **kwargs) -> str:
        client = self._get_client()
        response = client.messages.create(
            model=kwargs.get("model", self.model),
            max_tokens=kwargs.get("max_tokens", self.max_tokens),
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text if response.content else ""

    def is_available(self) -> bool:
        try:
            self._get_client()
            return True
        except Exception:
            return False


def create_backend(backend_type: str = "mock", **kwargs) -> LLMBackend:
    """
    Factory function to create an LLM backend by type name.

    Args:
        backend_type: One of 'mock', 'trae', 'openai', 'anthropic'
        **kwargs: Backend-specific configuration

    Returns:
        LLMBackend instance
    """
    backends = {
        "mock": MockBackend,
        "trae": TraeBackend,
        "openai": OpenAIBackend,
        "anthropic": AnthropicBackend,
    }
    cls = backends.get(backend_type.lower())
    if cls is None:
        raise ValueError(f"Unknown backend type: {backend_type}. Available: {list(backends.keys())}")
    return cls(**kwargs)
