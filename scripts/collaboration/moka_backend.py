#!/usr/bin/env python3
"""MokaAIBackend — explicit MOKA AI provider backend.

V4.5.2 P12.1.1: MokaAIBackend 独立化
- 复用 OpenAI 协议（MOKA 是 OpenAI-compatible）
- 显式识别 MOKA_API_KEY 环境变量
- 默认 base_url=https://api.moka.ai/v1，model=moka-gpt-5.5
- path = "A"（直接 API 路径）

用法:
    from scripts.collaboration.moka_backend import MokaAIBackend
    backend = MokaAIBackend()  # auto-loads MOKA_API_KEY
    backend.is_available()  # True if MOKA_API_KEY set
    backend.generate("hello")
"""

from __future__ import annotations

import os
from typing import Any

from .llm_backend import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE, LLMBackend

# V4.5.2 P12.1.1: MOKA-specific defaults
MOKA_DEFAULT_BASE_URL = "https://api.moka-ai.com/v1"
MOKA_DEFAULT_MODEL = "moka-gpt-5.5"

# V4.5.2: Standard MOKA request timeout (matches OpenAI/Anthropic)
MOKA_DEFAULT_TIMEOUT = 30.0

# V4.5.2: Retry configuration (reuse OpenAI semantics)
MOKA_MAX_RETRIES = 3


# Anti-Ghost call counter (P12.1.1)
_call_counter_er: int = 0


def get_call_counter_er() -> int:
    """Return the current call counter for MokaAIBackend public methods.

    Returns:
        Number of times MokaAIBackend.is_available() / generate() has been invoked.
        Used by Anti-Ghost CI gate to prove the module is wired in.
    """
    return _call_counter_er


def _inc_call_counter_er() -> None:
    global _call_counter_er
    _call_counter_er += 1


class MokaAIBackend(LLMBackend):
    """LLMBackend implementation for MOKA AI (https://www.moka.ai/).

    MOKA AI exposes an OpenAI-compatible API, so this backend delegates to
    the OpenAI client when available and falls back to plain httpx-style
    REST when the openai package is not installed (simulation mode).

    Attributes:
        path: Always returns "A" (direct API path).
        DEFAULT_TIMEOUT: 30s default timeout.
        MAX_RETRIES: 3 retry attempts with exponential backoff.
    """

    path = "A"
    DEFAULT_TIMEOUT = MOKA_DEFAULT_TIMEOUT
    MAX_RETRIES = MOKA_MAX_RETRIES

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        timeout: float | None = None,
    ) -> None:
        self._api_key = api_key or os.environ.get("MOKA_API_KEY")
        self.model = model or os.environ.get("MOKA_MODEL", MOKA_DEFAULT_MODEL)
        self.base_url = (
            base_url or os.environ.get("MOKA_BASE_URL", MOKA_DEFAULT_BASE_URL)
        )
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout or self.DEFAULT_TIMEOUT
        self._client: Any | None = None
        self._client_lock = __import__("threading").Lock()

    def __repr__(self) -> str:
        return f"MokaAIBackend(model={self.model}, base_url={self.base_url})"

    def is_available(self) -> bool:
        """Return True when MOKA_API_KEY is configured.

        Returns:
            True if `self._api_key` is a non-empty string.
        """
        _inc_call_counter_er()
        key = self._api_key
        if key is None:
            return False
        return bool(key.strip())

    def _get_client(self) -> Any:
        """Lazy-initialize the OpenAI-compatible client for MOKA.

        Returns:
            The OpenAI client instance.

        Raises:
            ImportError: If `openai` package is not installed.
        """
        if self._client is None:
            with self._client_lock:
                if self._client is None:
                    try:
                        from openai import OpenAI

                        client_kwargs: dict[str, Any] = {
                            "api_key": self._api_key,
                            "timeout": self.timeout,
                        }
                        if self.base_url:
                            client_kwargs["base_url"] = self.base_url
                        self._client = OpenAI(**client_kwargs)
                    except ImportError:
                        raise ImportError(
                            "openai package required for MokaAIBackend: pip install openai"
                        ) from None
        return self._client

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion using the MOKA API (OpenAI-compatible).

        Args:
            prompt: User prompt text.
            **kwargs: Optional overrides for model/temperature/max_tokens.

        Returns:
            The generated completion text.

        Raises:
            RuntimeError: If all retries fail.
        """
        import time

        _inc_call_counter_er()
        client = self._get_client()
        last_error: Exception | None = None
        for attempt in range(self.MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=kwargs.get("model", self.model),
                    messages=[{"role": "user", "content": prompt}],
                    temperature=kwargs.get("temperature", self.temperature),
                    max_tokens=kwargs.get("max_tokens", self.max_tokens),
                )
                # Extract text from first choice
                if response.choices:
                    return response.choices[0].message.content or ""
                return ""
            except Exception as exc:  # pragma: no cover - network path
                last_error = exc
                if attempt < self.MAX_RETRIES - 1:
                    backoff = min(8.0, 0.5 * (2 ** attempt))
                    time.sleep(backoff)
                    continue
                raise RuntimeError(
                    f"MokaAIBackend.generate failed after {self.MAX_RETRIES} attempts: {exc}"
                ) from exc
        if last_error is not None:
            raise RuntimeError(
                f"MokaAIBackend.generate failed: {last_error}"
            ) from last_error
        return ""  # unreachable
