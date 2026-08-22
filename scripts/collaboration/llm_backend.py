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

# V4.5.2 P12.1.1: Lazy import for MokaAIBackend to avoid circular imports
_MOKA_BACKEND = None


def _get_moka_backend():
    """Lazy import of MokaAIBackend to avoid circular imports."""
    global _MOKA_BACKEND
    if _MOKA_BACKEND is None:
        from .moka_backend import MokaAIBackend
        _MOKA_BACKEND = MokaAIBackend
    return _MOKA_BACKEND


class LLMBackend(ABC):
    """Abstract base class for LLM execution backends.

    V4.5.2: All subclasses must declare a ``path`` attribute (B/A/C)
    for B/A/C resolve order and reporting.
    """

    # V4.5.2: Backend execution path identifier.
    # "B" = HostLLMBridge, "A" = Direct API, "C" = Mock.
    path: str = "C"  # default for backward compat

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

    # V4.5.2: C path (honest mock fallback)
    path = "C"

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

    V4.5.2: This is a legacy passthrough backend. For new code, use
    HostBridgeBackend (path B) instead. TraeBackend retains path
    "B-passthrough" for backward compatibility but is_available()
    returns False so it is never auto-selected in B→A→C resolve.
    """

    # V4.5.2: Legacy passthrough, not auto-selected.
    path = "B-passthrough"

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

        V4.5.2: Returns False so TraeBackend is never auto-selected
        in B→A→C resolve. Use HostBridgeBackend for active host bridge.
        """
        return False


class OpenAIBackend(LLMBackend):
    # V4.5.2: A path (direct API)
    path = "A"
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
    # V4.5.2: A path (direct API)
    path = "A"
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
    Backend with automatic failover across multiple backends and fuse logic.

    V4.5.2 additions:
    - Fuse skip: consecutive same-reason failures permanently skip the backend.
    - ``path`` attribute exposes the resolved path for reporting.
    - Single failure degrades to the next backend (no fatal, continue).

    Usage:
        primary = AnthropicBackend(api_key="...", model="claude-sonnet-4-6")
        fallback = OpenAIBackend(api_key="...", model="gpt-5.5")
        backend = FallbackBackend([primary, fallback])
    """

    # V4.5.2: Composite path — actual path depends on available backends
    path = "A+C"

    def __init__(self, backends: list[Any], cooldown_seconds: float = DEFAULT_COOLDOWN_SECONDS) -> None:
        if not backends:
            raise ValueError("FallbackBackend requires at least one backend")
        self._backends = backends
        self._cooldown_seconds = cooldown_seconds
        self._failed_at: dict[str, float] = {}
        self._active_index = 0
        self._lock = __import__("threading").Lock()
        # V4.5.2: fuse tracking — skip index after N consecutive same-reason failures
        self._failures: dict[str, int] = {}  # reason -> count
        self._skipped: set[int] = set()  # indices skipped by fuse
        from .backend_paths import FUSE_SKIP_AFTER_CONSECUTIVE
        self._fuse_threshold = FUSE_SKIP_AFTER_CONSECUTIVE

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

    # V4.5.2: fuse tracking helpers
    def _record_failure(self, idx: int, reason: str) -> None:
        """Record a backend failure and skip if threshold reached.

        Same reason string → increment count toward fuse skip.
        Different reason → reset count (it's a different failure mode).
        """
        key = f"{idx}:{reason}"
        self._failures[key] = self._failures.get(key, 0) + 1
        if self._failures[key] >= self._fuse_threshold:
            self._skipped.add(idx)
            import logging
            logger = logging.getLogger(__name__)
            backend_repr = repr(self._backends[idx])
            logger.warning(
                "FallbackBackend: fuse blocked %s after %d consecutive %s failures",
                backend_repr, self._failures[key], reason,
            )

    def _is_fuse_skipped(self, idx: int) -> bool:
        """Check if a backend index is permanently skipped by fuse."""
        return idx in self._skipped

    def _classify(self, exc: Exception) -> str:
        """Classify exception to a reason string for fuse counting."""
        from .backend_paths import classify_error as _ce
        return _ce(exc)

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate a completion, failing over to subsequent backends on error.

        V4.5.2: single failure → degrade to next backend.
        Consecutive same-reason failures → fuse skip the backend permanently.

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
            # V4.5.2: skip fuse-blocked backends
            if self._is_fuse_skipped(idx):
                continue

            backend = self._backends[idx]
            backend_repr = repr(backend)
            backend_name = type(backend).__name__.replace("Backend", "").lower()
            backend_path = getattr(backend, "path", "?")

            # P11.1: record backend path invocation
            try:
                from .prometheus_metrics import get_metrics as _gm_metrics

                _gm_metrics().record_backend_call(backend_path)
            except (RuntimeError, ValueError, AttributeError, NameError):
                # Metrics are best-effort; never break backend flow
                pass

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
                # V4.5.2: record failure for fuse tracking
                reason = self._classify(e)
                self._record_failure(idx, reason)
                # P11.1: record backend failure (per path+reason)
                try:
                    from .prometheus_metrics import get_metrics as _gm

                    _gm().record_backend_failure(backend_path, reason)
                except (RuntimeError, ValueError, AttributeError, NameError):
                    # backend_path may be undefined if exception happened during setup;
                    # metrics are best-effort.
                    pass
                logger.warning(
                    "FallbackBackend: %s failed (%s, reason=%s), trying next",
                    backend_repr,
                    type(e).__name__,
                    reason,
                )
                # Prometheus: record failed LLM call
                try:
                    _metrics = get_metrics()
                    _metrics.record_llm_call(backend_name, _llm_duration, False)
                except (RuntimeError, ValueError, AttributeError):  # optional metrics must never break LLM calls
                    pass

        raise RuntimeError("All backends failed with no specific error") from last_error

    def generate_stream(self, prompt: str, **kwargs: Any) -> Generator[str, None, None]:
        """Stream a completion, failing over to subsequent backends on error.

        V4.5.2: same fuse logic as generate().

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
            if self._is_fuse_skipped(idx):
                continue

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
                reason = self._classify(e)
                self._record_failure(idx, reason)
                logger.warning(
                    "FallbackBackend: %s stream failed (%s, reason=%s), trying next",
                    backend_repr,
                    type(e).__name__,
                    reason,
                )

        raise RuntimeError("All backends failed with no specific error") from last_error

    def is_available(self) -> bool:
        """Check whether at least one non-fuse-skipped backend is available.

        Returns:
            True if any backend (not fuse-skipped) reports availability.
        """
        for i, b in enumerate(self._backends):
            if i not in self._skipped and b.is_available():
                return True
        return False


def create_backend(backend_type: str = "auto", **kwargs: Any) -> LLMBackend:
    """
    Factory function to create an LLM backend by type name.

    V4.5.2 B/A/C resolve order: B (Host Bridge) → A (Direct API) → C (Mock).
    ``auto`` mode resolves to the first available path per RESOLVE_ORDER.

    Automatically reads configuration from environment variables when not
    explicitly provided via kwargs. Supports .env file loading.

    Environment Variables:
        DEVSQUAD_LLM_BACKEND: Default backend type (auto|host|mock|trae|openai|anthropic|moka|fallback|auto-fallback)
        DEVSQUAD_OPENAI_API_KEY: OpenAI API key
        DEVSQUAD_OPENAI_BASE_URL: OpenAI-compatible base URL
        DEVSQUAD_OPENAI_MODEL: OpenAI model name
        DEVSQUAD_ANTHROPIC_API_KEY: Anthropic API key
        DEVSQUAD_ANTHROPIC_BASE_URL: Anthropic-compatible base URL
        DEVSQUAD_ANTHROPIC_MODEL: Anthropic model name
        MOKA_API_KEY: Moka AI API key (OpenAI-compatible)
        MOKA_API_BASE: Moka AI base URL (default: https://api.moka-ai.com/v1)
        MOKA_BASE_URL: Alias for MOKA_API_BASE (preferred in P12.1.1+)
        MOKA_MODEL: Moka AI model name (default: moka/claude-sonnet-4-6)
        TRAE_ENV: Triggers B path (host bridge detection)
        TRAE_AGENT_PATH: Triggers B path (host bridge detection)
        CLAUDE_CODE_ENV: Triggers B path (host bridge detection)
        ANTHROPIC_ENV: Triggers B path (host bridge detection)

    Args:
        backend_type: One of:
            'auto' (default) → B→A→C single path resolution (first available)
            'host' → HostBridgeBackend (raises BackendUnavailable if host not found)
            'mock' → MockBackend
            'trae' → TraeBackend (legacy passthrough, is_available=False)
            'openai' → OpenAIBackend (requires key)
            'anthropic' → AnthropicBackend (requires key)
            'moka' → OpenAIBackend with Moka AI endpoint (requires key)
            'fallback' → FallbackBackend with A→C (existing behavior)
            'auto-fallback' → FallbackBackend with B→A→C (new)
            If not specified, reads from DEVSQUAD_LLM_BACKEND env var.
            'moka' uses OpenAIBackend with Moka AI's OpenAI-compatible API.
        bridge_dir: B path bridge directory (for HostBridgeBackend).
        timeout_seconds: B path timeout (default 600s).
        path_only: testing only — force resolve to a specific path.
        **kwargs: Backend-specific configuration (overrides env vars)

    Returns:
        LLMBackend instance

    Raises:
        BackendUnavailable: host mode but host not available; or all paths unavailable.
        ValueError: Unknown backend type.
    """
    import os

    from .backend_paths import (
        API_KEY_ENV_TRIGGERS,
        BackendPath,
        HOST_ENV_TRIGGERS,
        RESOLVE_ORDER,
        BackendUnavailable,
    )

    _load_dotenv()

    env_backend = os.environ.get("DEVSQUAD_LLM_BACKEND", "auto").lower()

    # Resolve backend_type from env if auto and no explicit overrides
    if (
        backend_type == "auto"
        and not kwargs
        and env_backend
        in ("openai", "anthropic", "moka", "fallback", "auto-fallback", "mock", "trae", "host")
    ):
        backend_type = env_backend

    # === Explicit single-type backends (direct, no chain) ===
    explicit_backends = {
        "mock": MockBackend,
        "trae": TraeBackend,
        "openai": OpenAIBackend,
        "anthropic": AnthropicBackend,
        "moka": _get_moka_backend(),  # V4.5.2 P12.1.1: explicit MokaAIBackend
    }
    if backend_type in explicit_backends:
        cls = explicit_backends[backend_type]
        if backend_type == "moka":
            kwargs.setdefault("api_key", os.environ.get("MOKA_API_KEY"))
            # Support both MOKA_BASE_URL (P12.1.1) and MOKA_API_BASE (legacy)
            kwargs.setdefault(
                "base_url",
                os.environ.get("MOKA_BASE_URL") or os.environ.get("MOKA_API_BASE"),
            )
            kwargs.setdefault("model", os.environ.get("MOKA_MODEL"))
        elif cls == OpenAIBackend:
            kwargs.setdefault("api_key", os.environ.get("DEVSQUAD_OPENAI_API_KEY"))
            kwargs.setdefault("base_url", os.environ.get("DEVSQUAD_OPENAI_BASE_URL"))
            kwargs.setdefault("model", os.environ.get("DEVSQUAD_OPENAI_MODEL", DEFAULT_MODEL_OPENAI))
        elif cls == AnthropicBackend:
            kwargs.setdefault("api_key", os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY"))
            kwargs.setdefault("base_url", os.environ.get("DEVSQUAD_ANTHROPIC_BASE_URL"))
            kwargs.setdefault("model", os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", DEFAULT_MODEL_ANTHROPIC))
        return cls(**kwargs)

    # === "host" → HostBridgeBackend (always returns a backend, or raises) ===
    if backend_type == "host":
        bridge_dir = kwargs.pop("bridge_dir", None)
        from .host_llm_bridge import HostBridgeBackend
        backend = HostBridgeBackend(bridge_dir=bridge_dir)
        if not backend.is_available():
            raise BackendUnavailable("Host bridge not available: no TRAE/ClaudeCode environment detected")
        return backend

    # === "fallback" (existing A→C) ===
    if backend_type == "fallback":
        return _build_fallback_backend(kwargs)

    # === "auto-fallback" (new B→A→C with FallbackBackend) ===
    if backend_type == "auto-fallback":
        bridge_dir = kwargs.pop("bridge_dir", None)
        timeout_seconds = kwargs.pop("timeout_seconds", 600)
        backends: list[LLMBackend] = []
        # B path
        from .host_llm_bridge import HostBridgeBackend
        host_bridge = HostBridgeBackend(bridge_dir=bridge_dir, timeout_seconds=timeout_seconds)
        if host_bridge.is_available():
            backends.append(host_bridge)
        # A path
        api_backends = _build_api_backends(kwargs)
        backends.extend(api_backends)
        # C path
        backends.append(MockBackend())
        if len(backends) == 1:
            return backends[0]
        return FallbackBackend(backends, cooldown_seconds=kwargs.pop("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS))

    # === Catch-all for unknown backend types ===
    known_types = {"auto", "host", "mock", "trae", "openai", "anthropic", "moka", "fallback", "auto-fallback"}
    if backend_type not in known_types:
        raise ValueError(
            f"Unknown backend type: {backend_type}. "
            f"Available: auto, host, mock, trae, openai, anthropic, moka, fallback, auto-fallback"
        )

    # === "auto" — B→A→C single path resolution ===
    # First available wins; no chain wrapping.
    dst_path = kwargs.pop("path_only", None)  # testing override

    # B path: host detection
    if dst_path is None or dst_path == BackendPath.B_HOST_BRIDGE:
        for env_var in HOST_ENV_TRIGGERS:
            if os.environ.get(env_var):
                from .host_llm_bridge import HostBridgeBackend
                bridge_dir = kwargs.pop("bridge_dir", None)
                timeout_seconds = kwargs.pop("timeout_seconds", 600)
                host_backend = HostBridgeBackend(bridge_dir=bridge_dir, timeout_seconds=timeout_seconds)
                if host_backend.is_available():
                    return host_backend
                if dst_path:
                    raise BackendUnavailable(f"Host bridge unavailable (env={env_var} set but host not ready)")
                break  # host env set but unavailable → fall through to A

    # A path: API key detection
    if dst_path is None or dst_path == BackendPath.A_DIRECT_API:
        api_backends = _build_api_backends(kwargs)
        if api_backends:
            # V4.5.2 P-1: wrap with MockBackend tail for graceful degradation.
            # This means auto mode always returns FallbackBackend([API, Mock])
            # when API keys are present, so a single API failure falls back
            # to honest mock rather than raising.
            backends_with_tail = list(api_backends) + [MockBackend()]
            return FallbackBackend(
                backends_with_tail,
                cooldown_seconds=kwargs.pop("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS),
            )
        if dst_path:
            raise BackendUnavailable("Direct API path unavailable: no API keys configured")

    # C path: Mock
    if dst_path is None or dst_path == BackendPath.C_MOCK:
        return MockBackend()

    # Unreachable (RESOLVE_ORDER covers all paths)
    raise BackendUnavailable("No available backend path")


def _build_api_backends(kwargs: dict) -> list[LLMBackend]:
    """Build a list of API backends from available keys.

    Returns:
        list of (OpenAI, Anthropic, MOKA) backends for which keys are available.
        Empty list means no API keys found.
    """
    import os

    backends_list: list[LLMBackend] = []
    anthropic_key = kwargs.pop("anthropic_api_key", None) or os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
    openai_key = kwargs.pop("openai_api_key", None) or os.environ.get("DEVSQUAD_OPENAI_API_KEY")
    moka_key = kwargs.pop("moka_api_key", None) or os.environ.get("MOKA_API_KEY")

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
    if moka_key:
        # V4.5.2 P12.1.1: Use explicit MokaAIBackend instead of OpenAIBackend
        backends_list.append(
            _get_moka_backend()(
                api_key=moka_key,
                base_url=kwargs.pop("moka_base_url", None)
                or os.environ.get("MOKA_BASE_URL")
                or os.environ.get("MOKA_API_BASE"),
                model=kwargs.pop("moka_model", None)
                or os.environ.get("MOKA_MODEL"),
                max_tokens=kwargs.pop("max_tokens", DEFAULT_MAX_TOKENS),
                timeout=kwargs.pop("timeout", None),
            )
        )
    return backends_list


def _build_fallback_backend(kwargs: dict) -> LLMBackend:
    """Build a FallbackBackend with A→C (existing behavior).

    For backward compatibility: returns FallbackBackend([API_backend(s), MockBackend]).
    If no API keys, returns plain MockBackend.
    """
    backends_list = _build_api_backends(kwargs)
    backends_list.append(MockBackend())
    if len(backends_list) == 1:
        return backends_list[0]
    return FallbackBackend(backends_list, cooldown_seconds=kwargs.pop("cooldown_seconds", DEFAULT_COOLDOWN_SECONDS))


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
