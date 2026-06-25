"""Smoke tests for the 'auto' LLM backend mode with real API keys.

These tests verify that DevSquad's default "auto" backend correctly prefers real
LLM backends and gracefully degrades to mock when real backends fail.

They are skipped in CI and marked as slow. Run locally with:

    DEVSQUAD_OPENAI_API_KEY=sk-... python -m pytest tests/smoke/test_real_llm_auto_mode.py -v

or:

    DEVSQUAD_ANTHROPIC_API_KEY=sk-... python -m pytest tests/smoke/test_real_llm_auto_mode.py -v
"""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

pytestmark = [
    pytest.mark.slow,
    pytest.mark.smoke,
]


def _has_real_key() -> bool:
    return bool(
        os.environ.get("DEVSQUAD_OPENAI_API_KEY")
        or os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
    )


@pytest.mark.skipif(not _has_real_key(), reason="No real LLM API key configured")
class TestRealLLMAutoMode:
    """Smoke-test the default 'auto' backend with real LLM providers."""

    def test_auto_backend_prefers_real_llm(self) -> None:
        """Verify create_backend('auto') returns a FallbackBackend with a real LLM head."""
        from scripts.collaboration.llm_backend import FallbackBackend, create_backend

        backend = create_backend("auto")
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) >= 2
        first_class = backend._backends[0].__class__.__name__
        assert first_class in ("OpenAIBackend", "AnthropicBackend")

    def test_auto_backend_ends_with_mock_fallback(self) -> None:
        """Verify the auto backend chain always terminates with MockBackend."""
        from scripts.collaboration.llm_backend import MockBackend, create_backend

        backend = create_backend("auto")
        assert isinstance(backend._backends[-1], MockBackend)

    def test_auto_backend_generates_with_real_llm(self) -> None:
        """Verify the auto backend can actually generate content via real LLM."""
        from scripts.collaboration.llm_backend import create_backend

        backend = create_backend("auto")
        result = backend.generate(
            "Say 'auto mode works' in one short sentence.",
            max_tokens=50,
        )
        assert isinstance(result, str)
        assert len(result) > 0

    def test_auto_falls_back_to_mock_when_real_backend_is_unavailable(self) -> None:
        """If the real backend is forced unavailable, auto degrades to mock output."""
        from scripts.collaboration.llm_backend import MockBackend, create_backend

        backend = create_backend("auto")
        # Force every real backend in the chain to report unavailable.
        for b in backend._backends[:-1]:
            if hasattr(b, "is_available"):
                b.is_available = lambda: False  # type: ignore[method-assign]

        result = backend.generate(
            "Say 'fallback works' in one short sentence.",
            max_tokens=50,
        )
        assert isinstance(result, str)
        assert "[MOCK MODE]" in result


class TestRealLLMAutoModeNoKey:
    """Behavior when no real API key is available."""

    def test_auto_backend_without_keys_is_mock(self) -> None:
        """Without keys, auto should return MockBackend (plain or single fallback)."""
        from scripts.collaboration.llm_backend import (
            FallbackBackend,
            MockBackend,
            create_backend,
        )

        with patch.dict(
            os.environ,
            {
                "DEVSQUAD_LLM_BACKEND": "auto",
                "DEVSQUAD_OPENAI_API_KEY": "",
                "DEVSQUAD_ANTHROPIC_API_KEY": "",
                "OPENAI_API_KEY": "",
                "ANTHROPIC_API_KEY": "",
            },
            clear=False,
        ):
            backend = create_backend("auto")
            # Accept either a plain MockBackend or a FallbackBackend wrapping
            # only a MockBackend (the latter happens when env_backend is set
            # to "fallback" before the auto short-circuit runs).
            if isinstance(backend, FallbackBackend):
                assert len(backend._backends) == 1
                assert isinstance(backend._backends[0], MockBackend)
            else:
                assert isinstance(backend, MockBackend)
