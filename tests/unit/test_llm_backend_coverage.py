"""Supplemental coverage tests for scripts.collaboration.llm_backend.

Targets the error/degradation branches not exercised by the contract tests:
- OpenAIBackend / AnthropicBackend: client init, retry, streaming, availability
- FallbackBackend: cooldown, failover, all-fail, streaming
- create_backend factory: env-var resolution, auto mode, moka alias
- _get_*_retry_exceptions / _load_dotenv helpers

Goal (TD-3): raise llm_backend.py coverage from 58% to >=65%.
"""

from __future__ import annotations

import sys
import time
from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from scripts.collaboration.llm_backend import (
    AnthropicBackend,
    FallbackBackend,
    LLMBackend,
    MockBackend,
    OpenAIBackend,
    TraeBackend,
    _get_anthropic_retry_exceptions,
    _get_availability_exceptions,
    _get_fallback_exceptions,
    _get_openai_retry_exceptions,
    create_backend,
)

# ---------------------------------------------------------------------------
# OpenAIBackend
# ---------------------------------------------------------------------------


class TestOpenAIBackendInit:
    def test_init_with_explicit_args(self):
        backend = OpenAIBackend(
            api_key="sk-test",
            model="gpt-4-test",
            base_url="https://example.com/v1",
            temperature=0.5,
            max_tokens=123,
            timeout=45.0,
        )
        assert backend._api_key == "sk-test"
        assert backend.model == "gpt-4-test"
        assert backend.base_url == "https://example.com/v1"
        assert backend.temperature == 0.5
        assert backend.max_tokens == 123
        assert backend.timeout == 45.0

    def test_init_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "env-key")
        monkeypatch.setenv("DEVSQUAD_OPENAI_MODEL", "env-model")
        monkeypatch.setenv("DEVSQUAD_OPENAI_BASE_URL", "https://env.example/v1")
        backend = OpenAIBackend()
        assert backend._api_key == "env-key"
        assert backend.model == "env-model"
        assert backend.base_url == "https://env.example/v1"

    def test_repr_includes_model_and_base_url(self):
        backend = OpenAIBackend(api_key="k", model="m", base_url="u")
        assert "model=m" in repr(backend)
        assert "base_url=u" in repr(backend)


class TestOpenAIBackendGetClient:
    def test_get_client_raises_import_error_when_openai_missing(self, monkeypatch):
        # Force ImportError when `from openai import OpenAI` runs
        monkeypatch.setitem(sys.modules, "openai", None)
        backend = OpenAIBackend(api_key="k", model="m")
        with pytest.raises(ImportError, match="openai package required"):
            backend._get_client()

    def test_get_client_caches_instance(self):
        backend = OpenAIBackend(api_key="k", model="m")
        fake_openai = MagicMock()
        fake_client = MagicMock()
        fake_openai.OpenAI.return_value = fake_client
        with patch.dict(sys.modules, {"openai": fake_openai}):
            c1 = backend._get_client()
            c2 = backend._get_client()
        assert c1 is c2
        fake_openai.OpenAI.assert_called_once()

    def test_get_client_includes_base_url_when_provided(self):
        backend = OpenAIBackend(api_key="k", model="m", base_url="https://custom/v1")
        fake_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": fake_openai}):
            backend._get_client()
        kwargs = fake_openai.OpenAI.call_args.kwargs
        assert kwargs["base_url"] == "https://custom/v1"

    def test_get_client_omits_base_url_when_absent(self):
        backend = OpenAIBackend(api_key="k", model="m")
        fake_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": fake_openai}):
            backend._get_client()
        kwargs = fake_openai.OpenAI.call_args.kwargs
        assert "base_url" not in kwargs


class TestOpenAIBackendGenerate:
    def _make_backend_with_client(self) -> tuple[OpenAIBackend, MagicMock]:
        backend = OpenAIBackend(api_key="k", model="m")
        fake_openai = MagicMock()
        fake_client = MagicMock()
        fake_openai.OpenAI.return_value = fake_client
        backend._client = fake_client  # bypass _get_client
        return backend, fake_client

    def test_generate_returns_content(self):
        backend, client = self._make_backend_with_client()
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="hello world"))]
        )
        result = backend.generate("prompt")
        assert result == "hello world"

    def test_generate_returns_empty_string_when_content_none(self):
        backend, client = self._make_backend_with_client()
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content=None))]
        )
        assert backend.generate("p") == ""

    def test_generate_retries_on_transient_error_then_succeeds(self, monkeypatch):
        backend, client = self._make_backend_with_client()
        # Force backoff sleep to be a no-op for test speed.
        monkeypatch.setattr(time, "sleep", lambda _s: None)

        # Use the project's helper so the test works whether or not the
        # openai package is installed (the retry exception tuple degrades
        # to OS-level errors when openai is missing).
        transient_exc = _get_openai_retry_exceptions()[0]

        success_resp = MagicMock(
            choices=[MagicMock(message=MagicMock(content="ok"))]
        )
        client.chat.completions.create.side_effect = [
            transient_exc("boom"),
            success_resp,
        ]
        assert backend.generate("p") == "ok"
        assert client.chat.completions.create.call_count == 2

    def test_generate_raises_after_all_retries_fail(self, monkeypatch):
        backend, client = self._make_backend_with_client()
        monkeypatch.setattr(time, "sleep", lambda _s: None)

        transient_exc = _get_openai_retry_exceptions()[0]

        client.chat.completions.create.side_effect = transient_exc("boom")
        with pytest.raises(transient_exc):
            backend.generate("p")
        # MAX_RETRIES attempts
        assert client.chat.completions.create.call_count == backend.MAX_RETRIES

    def test_generate_forwards_kwargs(self):
        backend, client = self._make_backend_with_client()
        client.chat.completions.create.return_value = MagicMock(
            choices=[MagicMock(message=MagicMock(content="x"))]
        )
        backend.generate(
            "p",
            model="override-model",
            temperature=0.1,
            max_tokens=10,
        )
        kwargs = client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "override-model"
        assert kwargs["temperature"] == 0.1
        assert kwargs["max_tokens"] == 10


class TestOpenAIBackendStream:
    def test_generate_stream_yields_non_empty_content(self):
        backend = OpenAIBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client

        chunk1 = MagicMock(choices=[MagicMock(delta=MagicMock(content="hello"))])
        chunk2 = MagicMock(choices=[MagicMock(delta=MagicMock(content=""))])
        chunk3 = MagicMock(choices=[MagicMock(delta=MagicMock(content=" world"))])
        # Empty choices chunk should be skipped, not crash.
        chunk_empty = MagicMock(choices=[])
        fake_client.chat.completions.create.return_value = iter(
            [chunk_empty, chunk1, chunk2, chunk3]
        )
        chunks = list(backend.generate_stream("p"))
        assert chunks == ["hello", " world"]

    def test_generate_stream_forwards_kwargs(self):
        backend = OpenAIBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client
        fake_client.chat.completions.create.return_value = iter([])
        list(backend.generate_stream("p", model="m2", temperature=0.2, max_tokens=5))
        kwargs = fake_client.chat.completions.create.call_args.kwargs
        assert kwargs["model"] == "m2"
        assert kwargs["temperature"] == 0.2
        assert kwargs["max_tokens"] == 5
        assert kwargs["stream"] is True


class TestOpenAIBackendAvailability:
    def test_is_available_true_when_client_ok(self):
        backend = OpenAIBackend(api_key="k", model="m")
        fake_openai = MagicMock()
        with patch.dict(sys.modules, {"openai": fake_openai}):
            assert backend.is_available() is True

    def test_is_available_false_on_import_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "openai", None)
        backend = OpenAIBackend(api_key="k", model="m")
        assert backend.is_available() is False


# ---------------------------------------------------------------------------
# AnthropicBackend
# ---------------------------------------------------------------------------


class TestAnthropicBackendInit:
    def test_init_with_explicit_args(self):
        backend = AnthropicBackend(
            api_key="sk-ant",
            model="claude-x",
            base_url="https://anth.example",
            max_tokens=99,
            timeout=33.0,
        )
        assert backend._api_key == "sk-ant"
        assert backend.model == "claude-x"
        assert backend.base_url == "https://anth.example"
        assert backend.max_tokens == 99
        assert backend.timeout == 33.0

    def test_init_reads_env_vars(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_API_KEY", "env-ant")
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_MODEL", "env-ant-model")
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_BASE_URL", "https://env.ant")
        backend = AnthropicBackend()
        assert backend._api_key == "env-ant"
        assert backend.model == "env-ant-model"
        assert backend.base_url == "https://env.ant"

    def test_repr(self):
        backend = AnthropicBackend(api_key="k", model="m", base_url="b")
        assert "model=m" in repr(backend)
        assert "base_url=b" in repr(backend)


class TestAnthropicBackendGetClient:
    def test_get_client_raises_import_error_when_anthropic_missing(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)
        backend = AnthropicBackend(api_key="k", model="m")
        with pytest.raises(ImportError, match="anthropic package required"):
            backend._get_client()

    def test_get_client_caches_instance(self):
        backend = AnthropicBackend(api_key="k", model="m")
        fake_module = MagicMock()
        fake_client = MagicMock()
        fake_module.Anthropic.return_value = fake_client
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            c1 = backend._get_client()
            c2 = backend._get_client()
        assert c1 is c2
        fake_module.Anthropic.assert_called_once()

    def test_get_client_uses_base_url_when_provided(self):
        backend = AnthropicBackend(api_key="k", model="m", base_url="https://x")
        fake_module = MagicMock()
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            backend._get_client()
        kwargs = fake_module.Anthropic.call_args.kwargs
        assert kwargs["base_url"] == "https://x"


class TestAnthropicBackendGenerate:
    def _make_backend_with_client(self) -> tuple[AnthropicBackend, MagicMock]:
        backend = AnthropicBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client
        return backend, fake_client

    def test_generate_returns_text(self):
        backend, client = self._make_backend_with_client()
        client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="hello ant")]
        )
        assert backend.generate("p") == "hello ant"

    def test_generate_returns_empty_when_no_content(self):
        backend, client = self._make_backend_with_client()
        client.messages.create.return_value = MagicMock(content=[])
        assert backend.generate("p") == ""

    def test_generate_retries_then_succeeds(self, monkeypatch):
        backend, client = self._make_backend_with_client()
        monkeypatch.setattr(time, "sleep", lambda _s: None)

        # Use the project's helper so the test runs whether or not the
        # anthropic package is installed.
        transient_exc = _get_anthropic_retry_exceptions()[0]

        success = MagicMock(content=[MagicMock(text="ok")])
        client.messages.create.side_effect = [
            transient_exc("x"),
            success,
        ]
        assert backend.generate("p") == "ok"
        assert client.messages.create.call_count == 2

    def test_generate_raises_after_all_retries(self, monkeypatch):
        backend, client = self._make_backend_with_client()
        monkeypatch.setattr(time, "sleep", lambda _s: None)

        transient_exc = _get_anthropic_retry_exceptions()[0]

        client.messages.create.side_effect = transient_exc("x")
        with pytest.raises(transient_exc):
            backend.generate("p")
        assert client.messages.create.call_count == backend.MAX_RETRIES


class TestAnthropicBackendStream:
    def test_generate_stream_yields_text_stream(self):
        backend = AnthropicBackend(api_key="k", model="m")
        fake_client = MagicMock()
        backend._client = fake_client

        stream_ctx = MagicMock()
        stream_ctx.__enter__ = MagicMock(return_value=stream_ctx)
        stream_ctx.__exit__ = MagicMock(return_value=False)
        stream_ctx.text_stream = iter(["a", "b", "c"])
        fake_client.messages.stream.return_value = stream_ctx

        chunks = list(backend.generate_stream("p"))
        assert chunks == ["a", "b", "c"]


class TestAnthropicBackendAvailability:
    def test_is_available_true_when_client_ok(self):
        backend = AnthropicBackend(api_key="k", model="m")
        fake_module = MagicMock()
        with patch.dict(sys.modules, {"anthropic": fake_module}):
            assert backend.is_available() is True

    def test_is_available_false_on_import_error(self, monkeypatch):
        monkeypatch.setitem(sys.modules, "anthropic", None)
        backend = AnthropicBackend(api_key="k", model="m")
        assert backend.is_available() is False


# ---------------------------------------------------------------------------
# FallbackBackend
# ---------------------------------------------------------------------------


class TestFallbackBackendInit:
    def test_empty_backends_raises_value_error(self):
        with pytest.raises(ValueError, match="at least one backend"):
            FallbackBackend([])

    def test_init_defaults(self):
        b1 = MockBackend()
        b2 = TraeBackend()
        fb = FallbackBackend([b1, b2])
        assert fb._backends == [b1, b2]
        assert fb._active_index == 0
        assert fb._failed_at == {}

    def test_repr_lists_backend_types(self):
        fb = FallbackBackend([MockBackend(), TraeBackend()])
        r = repr(fb)
        assert "MockBackend" in r
        assert "TraeBackend" in r


class TestFallbackBackendCooldown:
    def test_is_cooled_down_returns_true_when_no_failure_recorded(self):
        fb = FallbackBackend([MockBackend()])
        assert fb._is_cooled_down(repr(MockBackend())) is True

    def test_is_cooled_down_returns_false_within_cooldown_window(self):
        fb = FallbackBackend([MockBackend()], cooldown_seconds=1000.0)
        key = repr(MockBackend())
        fb._mark_failed(key)
        assert fb._is_cooled_down(key) is False

    def test_is_cooled_down_returns_true_after_cooldown_expires(self):
        fb = FallbackBackend([MockBackend()], cooldown_seconds=0.0)
        key = repr(MockBackend())
        fb._mark_failed(key)
        time.sleep(0.01)
        assert fb._is_cooled_down(key) is True

    def test_mark_failed_records_timestamp(self):
        fb = FallbackBackend([MockBackend()])
        key = repr(MockBackend())
        assert key not in fb._failed_at
        fb._mark_failed(key)
        assert key in fb._failed_at


class TestFallbackBackendGenerate:
    def test_generate_uses_primary_backend_first(self):
        primary = MockBackend()
        fb = FallbackBackend([primary])
        result = fb.generate("prompt")
        assert "[MOCK MODE]" in result

    def test_generate_falls_over_to_secondary_on_failure(self):
        primary = MagicMock()
        primary.generate.side_effect = RuntimeError("primary down")
        secondary = MockBackend()
        fb = FallbackBackend([primary, secondary])
        result = fb.generate("prompt")
        assert "[MOCK MODE]" in result
        assert fb._active_index == 1

    def test_generate_skips_cooled_down_secondary(self):
        primary = MagicMock()
        primary.generate.side_effect = RuntimeError("primary down")
        secondary = MagicMock()
        secondary.generate.side_effect = RuntimeError("secondary down")
        fb = FallbackBackend([primary, secondary], cooldown_seconds=1000.0)
        # Mark secondary as recently failed so it should be skipped.
        fb._mark_failed(repr(secondary))
        with pytest.raises(RuntimeError, match="primary down"):
            fb.generate("p")

    def test_generate_raises_when_all_backends_fail(self):
        primary = MagicMock()
        primary.generate.side_effect = RuntimeError("p down")
        secondary = MagicMock()
        secondary.generate.side_effect = RuntimeError("s down")
        fb = FallbackBackend([primary, secondary])
        with pytest.raises(RuntimeError, match="s down"):
            fb.generate("p")

    def test_generate_logs_info_when_switching_to_non_primary(self, caplog):
        primary = MagicMock()
        primary.generate.side_effect = RuntimeError("p down")
        secondary = MockBackend()
        fb = FallbackBackend([primary, secondary])
        with caplog.at_level("INFO"):
            fb.generate("p")
        assert any("switched to" in rec.message for rec in caplog.records)


class TestFallbackBackendStream:
    def test_generate_stream_uses_primary(self):
        primary = MockBackend()
        fb = FallbackBackend([primary])
        chunks = list(fb.generate_stream("p"))
        assert len(chunks) >= 1
        assert all(isinstance(c, str) for c in chunks)

    def test_generate_stream_falls_over_on_failure(self):
        primary = MagicMock()
        primary.generate_stream.side_effect = RuntimeError("stream down")
        secondary = MockBackend()
        fb = FallbackBackend([primary, secondary])
        chunks = list(fb.generate_stream("p"))
        assert len(chunks) >= 1

    def test_generate_stream_raises_when_all_fail(self):
        primary = MagicMock()
        primary.generate_stream.side_effect = RuntimeError("p stream down")
        secondary = MagicMock()
        secondary.generate_stream.side_effect = RuntimeError("s stream down")
        fb = FallbackBackend([primary, secondary])
        with pytest.raises(RuntimeError, match="s stream down"):
            list(fb.generate_stream("p"))

    def test_generate_stream_skips_cooled_down_secondary(self):
        primary = MagicMock()
        primary.generate_stream.side_effect = RuntimeError("p stream down")
        secondary = MagicMock()
        secondary.generate_stream.side_effect = RuntimeError("s stream down")
        fb = FallbackBackend([primary, secondary], cooldown_seconds=1000.0)
        fb._mark_failed(repr(secondary))
        with pytest.raises(RuntimeError, match="p stream down"):
            list(fb.generate_stream("p"))


class TestFallbackBackendAvailability:
    def test_is_available_true_if_any_backend_available(self):
        primary = MagicMock()
        primary.is_available.return_value = False
        secondary = MockBackend()
        fb = FallbackBackend([primary, secondary])
        assert fb.is_available() is True

    def test_is_available_false_if_all_unavailable(self):
        primary = MagicMock()
        primary.is_available.return_value = False
        secondary = MagicMock()
        secondary.is_available.return_value = False
        fb = FallbackBackend([primary, secondary])
        assert fb.is_available() is False


# ---------------------------------------------------------------------------
# create_backend factory
# ---------------------------------------------------------------------------


class TestCreateBackend:
    def test_creates_mock_backend(self):
        backend = create_backend("mock")
        assert isinstance(backend, MockBackend)

    def test_creates_trae_backend(self):
        backend = create_backend("trae")
        assert isinstance(backend, TraeBackend)

    def test_creates_openai_backend_with_kwargs(self):
        backend = create_backend(
            "openai", api_key="k", model="m", base_url="https://x"
        )
        assert isinstance(backend, OpenAIBackend)
        assert backend._api_key == "k"
        assert backend.model == "m"

    def test_creates_anthropic_backend_with_kwargs(self):
        backend = create_backend("anthropic", api_key="k", model="m")
        assert isinstance(backend, AnthropicBackend)
        assert backend._api_key == "k"
        assert backend.model == "m"

    def test_creates_moka_alias_openai_backend(self, monkeypatch):
        monkeypatch.setenv("MOKA_API_KEY", "moka-key")
        monkeypatch.setenv("MOKA_API_BASE", "https://moka.example/v1")
        monkeypatch.setenv("MOKA_MODEL", "moka/claude-x")
        backend = create_backend("moka")
        assert isinstance(backend, OpenAIBackend)
        assert backend._api_key == "moka-key"
        assert backend.base_url == "https://moka.example/v1"
        assert backend.model == "moka/claude-x"

    def test_unknown_backend_type_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown backend type"):
            create_backend("nonexistent")

    def test_auto_with_no_keys_returns_mock(self, monkeypatch):
        # Ensure no env keys
        for var in (
            "DEVSQUAD_OPENAI_API_KEY",
            "DEVSQUAD_ANTHROPIC_API_KEY",
            "DEVSQUAD_LLM_BACKEND",
        ):
            monkeypatch.delenv(var, raising=False)
        backend = create_backend("auto")
        assert isinstance(backend, MockBackend)

    def test_auto_with_anthropic_key_returns_fallback(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_API_KEY", "ant-key")
        monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEVSQUAD_LLM_BACKEND", raising=False)
        backend = create_backend("auto")
        assert isinstance(backend, FallbackBackend)
        # First backend should be Anthropic, last should be Mock
        assert isinstance(backend._backends[0], AnthropicBackend)
        assert isinstance(backend._backends[-1], MockBackend)

    def test_auto_with_openai_key_returns_fallback(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "oai-key")
        monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("DEVSQUAD_LLM_BACKEND", raising=False)
        backend = create_backend("auto")
        assert isinstance(backend, FallbackBackend)
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert isinstance(backend._backends[-1], MockBackend)

    def test_explicit_fallback_with_kwargs(self, monkeypatch):
        monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
        backend = create_backend(
            "fallback",
            openai_api_key="oai-k",
            openai_model="oai-m",
            anthropic_api_key="ant-k",
            anthropic_model="ant-m",
        )
        assert isinstance(backend, FallbackBackend)
        types_in_fb = [type(b) for b in backend._backends]
        assert AnthropicBackend in types_in_fb
        assert OpenAIBackend in types_in_fb
        assert MockBackend in types_in_fb

    def test_env_backend_override_when_auto_and_no_kwargs(self, monkeypatch):
        monkeypatch.setenv("DEVSQUAD_LLM_BACKEND", "mock")
        backend = create_backend("auto")
        assert isinstance(backend, MockBackend)

    def test_kwargs_override_env_backend(self, monkeypatch):
        # When kwargs provided, env override should NOT trigger
        monkeypatch.setenv("DEVSQUAD_LLM_BACKEND", "mock")
        backend = create_backend("auto", api_key="k", model="m")
        # With kwargs, auto falls through to fallback path (no real key → mock wrap)
        assert isinstance(backend, (MockBackend, FallbackBackend))


# ---------------------------------------------------------------------------
# Helper exception functions
# ---------------------------------------------------------------------------


class TestRetryExceptionHelpers:
    def test_get_openai_retry_exceptions_includes_os_errors(self):
        excs = _get_openai_retry_exceptions()
        assert ConnectionError in excs
        assert TimeoutError in excs
        assert OSError in excs

    def test_get_anthropic_retry_exceptions_includes_os_errors(self):
        excs = _get_anthropic_retry_exceptions()
        assert ConnectionError in excs
        assert TimeoutError in excs
        assert OSError in excs

    def test_get_availability_exceptions_includes_import_runtime(self):
        excs = _get_availability_exceptions()
        assert ImportError in excs
        assert RuntimeError in excs
        assert ConnectionError in excs

    def test_get_fallback_exceptions_includes_runtime_os(self):
        excs = _get_fallback_exceptions()
        assert RuntimeError in excs
        assert OSError in excs
        assert TimeoutError in excs
        assert ConnectionError in excs


# ---------------------------------------------------------------------------
# _load_dotenv
# ---------------------------------------------------------------------------


class TestLoadDotenv:
    def test_load_dotenv_is_idempotent(self, monkeypatch):
        # Reset sentinel and call twice; second call should be a no-op
        import scripts.collaboration.llm_backend as lb

        monkeypatch.setattr(lb, "_DOTENV_LOADED", False)
        # Should not raise even if dotenv is not installed
        lb._load_dotenv()
        assert lb._DOTENV_LOADED is True
        # Second call: still True, no-op
        lb._load_dotenv()
        assert lb._DOTENV_LOADED is True

    def test_load_dotenv_silently_skips_when_dotenv_missing(self, monkeypatch):
        import scripts.collaboration.llm_backend as lb

        monkeypatch.setattr(lb, "_DOTENV_LOADED", False)
        # Force ImportError on `from dotenv import load_dotenv`
        monkeypatch.setitem(sys.modules, "dotenv", None)
        lb._load_dotenv()  # must not raise
        assert lb._DOTENV_LOADED is True


# ---------------------------------------------------------------------------
# LLMBackend ABC contract
# ---------------------------------------------------------------------------


class TestLLMBackendABC:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            LLMBackend()  # type: ignore[abstract]

    def test_default_generate_stream_falls_back_to_generate(self):
        """Default LLMBackend.generate_stream should call generate()."""

        class _OneShotBackend(LLMBackend):
            def __init__(self) -> None:
                self.calls = 0

            def generate(self, prompt: str, **_kwargs: Any) -> str:
                self.calls += 1
                return f"gen:{prompt}"

            def is_available(self) -> bool:
                return True

        b = _OneShotBackend()
        chunks = list(b.generate_stream("hello"))
        assert chunks == ["gen:hello"]
        assert b.calls == 1


# ---------------------------------------------------------------------------
# Generator type smoke test
# ---------------------------------------------------------------------------


def test_generate_stream_default_returns_generator():
    """LLMBackend.generate_stream default impl returns a Generator."""
    backend = MockBackend()
    result = backend.generate_stream("p")
    assert isinstance(result, Generator)
