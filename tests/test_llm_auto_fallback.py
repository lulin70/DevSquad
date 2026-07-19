#!/usr/bin/env python3
"""
Tests for LLM "auto" backend fallback strategy.

Goal: when DevSquad is invoked without explicit backend config, it should try
real LLM backends first and fall back to MockBackend only if real backends fail
or no API keys are configured.

These tests intentionally avoid real network calls by monkeypatching API keys
and mocking the real backend classes' availability/behavior.
"""

import os
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from scripts.collaboration.llm_backend import (
    FallbackBackend,
    MockBackend,
    create_backend,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _patch_dotenv():
    """Return patches that disable .env loading so os.environ stays clean."""
    return [
        patch("scripts.collaboration.llm_backend._load_dotenv"),
        patch("scripts.collaboration.async_llm_backend._load_dotenv_async"),
    ]


# ---------------------------------------------------------------------------
# Auto backend tests (sync)
# ---------------------------------------------------------------------------


class TestCreateBackendAuto:
    """Tests for create_backend(backend_type='auto')."""

    def test_auto_without_keys_returns_mock_backend(self):
        """No API keys -> auto should return plain MockBackend."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"DEVSQUAD_LLM_BACKEND": "auto"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, MockBackend)
        assert not isinstance(backend, FallbackBackend)

    def test_auto_with_openai_key_returns_fallback_with_mock_tail(self):
        """OpenAI key only -> FallbackBackend([OpenAIBackend, MockBackend])."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_LLM_BACKEND": "auto", "DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 2
        assert backend._backends[0].__class__.__name__ == "OpenAIBackend"
        assert isinstance(backend._backends[1], MockBackend)

    def test_auto_with_anthropic_key_returns_fallback_with_mock_tail(self):
        """Anthropic key only -> FallbackBackend([AnthropicBackend, MockBackend])."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {
                "DEVSQUAD_LLM_BACKEND": "auto",
                "DEVSQUAD_ANTHROPIC_API_KEY": "sk-test-anthropic",
            },
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 2
        assert backend._backends[0].__class__.__name__ == "AnthropicBackend"
        assert isinstance(backend._backends[1], MockBackend)

    def test_auto_with_both_keys_prefers_anthropic_then_openai_then_mock(self):
        """Both keys -> order is Anthropic, OpenAI, Mock."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {
                "DEVSQUAD_LLM_BACKEND": "auto",
                "DEVSQUAD_OPENAI_API_KEY": "sk-test-openai",
                "DEVSQUAD_ANTHROPIC_API_KEY": "sk-test-anthropic",
            },
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 3
        assert backend._backends[0].__class__.__name__ == "AnthropicBackend"
        assert backend._backends[1].__class__.__name__ == "OpenAIBackend"
        assert isinstance(backend._backends[2], MockBackend)

    def test_auto_reads_backend_from_env(self):
        """DEVSQUAD_LLM_BACKEND=mock should override auto default."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"DEVSQUAD_LLM_BACKEND": "mock"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, MockBackend)
        assert not isinstance(backend, FallbackBackend)

    def test_auto_uses_real_backend_when_env_specifies_openai(self):
        """DEVSQUAD_LLM_BACKEND=openai with key -> OpenAIBackend (no fallback chain)."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_LLM_BACKEND": "openai", "DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert backend.__class__.__name__ == "OpenAIBackend"
        assert not isinstance(backend, FallbackBackend)

    def test_explicit_mock_stays_mock(self):
        """create_backend('mock') should always return MockBackend, even with keys."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("mock")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, MockBackend)
        assert not isinstance(backend, FallbackBackend)

    def test_explicit_openai_stays_openai(self):
        """create_backend('openai') should return OpenAIBackend, no mock fallback."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("openai")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert backend.__class__.__name__ == "OpenAIBackend"
        assert not isinstance(backend, FallbackBackend)


class TestCreateBackendDefault:
    """Tests for create_backend() with no arguments (default behavior)."""

    def test_default_with_no_key_is_mock(self):
        """No args, no env, no keys -> MockBackend."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend()
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, MockBackend)

    def test_default_with_openai_key_is_auto_fallback(self):
        """No args + OPENAI key -> FallbackBackend with real LLM + mock tail."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend()
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert backend._backends[0].__class__.__name__ == "OpenAIBackend"
        assert isinstance(backend._backends[-1], MockBackend)


class TestFallbackBehavior:
    """Tests that FallbackBackend actually falls back to mock on real failure."""

    def test_fallback_to_mock_when_real_backend_fails(self):
        """Real backend raises -> FallbackBackend uses MockBackend."""
        real_backend = MagicMock()
        real_backend.__class__.__name__ = "OpenAIBackend"
        real_backend.generate = MagicMock(side_effect=ConnectionError("simulated failure"))
        real_backend.is_available = MagicMock(return_value=True)

        backend = FallbackBackend([real_backend, MockBackend()])
        result = backend.generate("hello", system_prompt="test")
        assert result is not None
        assert isinstance(result, str)
        assert "[MOCK MODE]" in result
        real_backend.generate.assert_called_once()


class TestAsyncCreateBackendAuto:
    """Tests for AsyncLLMBackendFactory.create('auto')."""

    def test_async_auto_without_keys_returns_mock(self):
        """No keys -> AsyncMockBackend."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                from scripts.collaboration.async_llm_backend import (
                    AsyncLLMBackendFactory,
                    AsyncMockBackend,
                )

                backend = AsyncLLMBackendFactory.create("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, AsyncMockBackend)

    def test_async_auto_with_openai_key_returns_fallback(self):
        """OpenAI key -> FallbackBackend with AsyncOpenAIBackend + AsyncMockBackend."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                from scripts.collaboration.async_llm_backend import (
                    AsyncFallbackBackend,
                    AsyncLLMBackendFactory,
                    AsyncMockBackend,
                )

                backend = AsyncLLMBackendFactory.create("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, AsyncFallbackBackend)
        assert backend._backends[0].__class__.__name__ == "AsyncOpenAIBackend"
        assert isinstance(backend._backends[1], AsyncMockBackend)


class TestCLIBackendChoices:
    """Tests that CLI exposes 'auto' backend choice."""

    def test_cli_backends_includes_auto(self):
        from scripts.cli_utils import BACKENDS

        assert "auto" in BACKENDS

    def test_cli_create_auto_returns_backend_or_none(self):
        """_create_backend('auto') should return a backend object."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                from scripts.cli_utils import _create_backend

                backend = _create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert backend is not None
        assert isinstance(backend, (MockBackend, FallbackBackend))

    def test_cli_create_mock_returns_none(self):
        """_create_backend('mock') should continue to return None for compat."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                from scripts.cli_utils import _create_backend

                result = _create_backend("mock")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert result is None
