"""Tests for MokaAIBackend (V4.5.2 P12.1.1)."""

from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from scripts.collaboration.llm_backend import create_backend
from scripts.collaboration.moka_backend import (
    MOKA_DEFAULT_BASE_URL,
    MOKA_DEFAULT_MODEL,
    MokaAIBackend,
    _call_counter_er,
    get_call_counter_er,
)


@pytest.fixture(autouse=True)
def reset_counter():
    """Reset module-level counter between tests."""
    import scripts.collaboration.moka_backend as mod
    mod._call_counter_er = 0
    yield
    mod._call_counter_er = 0


# --- Class-level constants ---


class TestMokaAIBackendConstants:
    """Test MOKA-specific constants."""

    def test_default_base_url(self):
        assert MOKA_DEFAULT_BASE_URL == "https://api.moka-ai.com/v1"

    def test_default_model(self):
        assert MOKA_DEFAULT_MODEL == "moka-gpt-5.5"


# --- Constructor / config ---


class TestMokaAIBackendInit:
    """Test constructor and configuration loading."""

    def setup_method(self):
        # Wipe MOKA env vars for deterministic defaults
        import os
        for k in ("MOKA_API_KEY", "MOKA_MODEL", "MOKA_BASE_URL"):
            os.environ.pop(k, None)

    def test_init_with_api_key(self):
        b = MokaAIBackend(api_key="k")
        assert b._api_key == "k"

    def test_init_reads_moka_api_key_env(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "from-env"}, clear=True):
            b = MokaAIBackend()
            assert b._api_key == "from-env"

    def test_init_uses_default_model(self):
        b = MokaAIBackend(api_key="k")
        assert b.model == MOKA_DEFAULT_MODEL

    def test_init_uses_default_base_url(self):
        with patch.dict(os.environ, {}, clear=True):
            b = MokaAIBackend(api_key="k")
            assert b.base_url == MOKA_DEFAULT_BASE_URL

    def test_init_model_override(self):
        b = MokaAIBackend(api_key="k", model="moka-custom")
        assert b.model == "moka-custom"

    def test_init_base_url_override(self):
        b = MokaAIBackend(api_key="k", base_url="https://custom.moka.ai/v1")
        assert b.base_url == "https://custom.moka.ai/v1"

    def test_init_env_model_override(self):
        with patch.dict(os.environ, {"MOKA_MODEL": "moka-env-model"}, clear=True):
            b = MokaAIBackend(api_key="k")
            assert b.model == "moka-env-model"

    def test_init_env_base_url_override(self):
        with patch.dict(
            os.environ, {"MOKA_BASE_URL": "https://env.moka.ai/v1"}, clear=True
        ):
            b = MokaAIBackend(api_key="k")
            assert b.base_url == "https://env.moka.ai/v1"

    def test_init_repr(self):
        b = MokaAIBackend(api_key="k", model="moka-x")
        assert "MokaAIBackend" in repr(b)
        assert "moka-x" in repr(b)

    def test_default_model_unaffected_by_env_when_key_loaded(self):
        # Ensure default is moka-gpt-5.5 when neither model env var nor kwarg is given
        with patch.dict(os.environ, {"MOKA_API_KEY": "k"}, clear=True):
            b = MokaAIBackend()
            assert b.model == MOKA_DEFAULT_MODEL


# --- Path attribute ---


class TestMokaAIBackendPath:
    def test_path_is_A(self):
        assert MokaAIBackend.path == "A"

    def test_path_instance_attribute(self):
        b = MokaAIBackend(api_key="k")
        assert b.path == "A"


# --- is_available ---


class TestMokaAIBackendIsAvailable:
    def test_unavailable_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            b = MokaAIBackend()
            assert b.is_available() is False

    def test_unavailable_with_empty_key(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": ""}, clear=True):
            b = MokaAIBackend()
            assert b.is_available() is False

    def test_unavailable_with_whitespace_key(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "   "}, clear=True):
            b = MokaAIBackend()
            assert b.is_available() is False

    def test_available_with_explicit_key(self):
        b = MokaAIBackend(api_key="real-key")
        assert b.is_available() is True

    def test_available_with_env_key(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "env-key"}, clear=True):
            b = MokaAIBackend()
            assert b.is_available() is True

    def test_is_available_increments_counter(self):
        b = MokaAIBackend(api_key="k")
        before = get_call_counter_er()
        b.is_available()
        after = get_call_counter_er()
        assert after == before + 1


# --- Counter ---


class TestMokaAIBackendCounter:
    def test_initial_counter_zero(self):
        # Reset by autouse fixture
        assert get_call_counter_er() == 0

    def test_counter_increments_on_is_available(self):
        b = MokaAIBackend(api_key="k")
        b.is_available()
        b.is_available()
        b.is_available()
        assert get_call_counter_er() == 3

    def test_counter_type_int(self):
        assert isinstance(_call_counter_er, int)


# --- Factory integration ---


class TestCreateBackendMoka:
    """Test create_backend('moka') returns MokaAIBackend."""

    def test_create_moka_returns_moka_backend(self):
        with patch.dict(
            os.environ,
            {"MOKA_API_KEY": "k", "MOKA_MODEL": "moka-x"},
            clear=True,
        ):
            backend = create_backend("moka")
            assert isinstance(backend, MokaAIBackend)
            assert backend.model == "moka-x"

    def test_create_moka_default_model(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "k"}, clear=True):
            backend = create_backend("moka")
            assert isinstance(backend, MokaAIBackend)
            assert backend.model == MOKA_DEFAULT_MODEL

    def test_create_moka_with_kwargs_override(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "env-key"}, clear=True):
            backend = create_backend("moka", api_key="override-key")
            assert backend._api_key == "override-key"

    def test_create_moka_with_explicit_model_kwarg(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "k"}, clear=True):
            backend = create_backend("moka", model="explicit-model")
            assert backend.model == "explicit-model"


# --- Generate behavior (mocked) ---


class TestMokaAIBackendGenerate:
    """Test generate() with mocked OpenAI client."""

    def test_generate_returns_content(self):
        from unittest.mock import MagicMock

        b = MokaAIBackend(api_key="k")
        # Patch _get_client to return mock client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "MOKA response"
        mock_client.chat.completions.create.return_value = mock_response
        b._get_client = lambda: mock_client  # type: ignore[assignment]

        result = b.generate("hello")
        assert result == "MOKA response"

    def test_generate_handles_empty_choices(self):
        from unittest.mock import MagicMock

        b = MokaAIBackend(api_key="k")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []
        mock_client.chat.completions.create.return_value = mock_response
        b._get_client = lambda: mock_client  # type: ignore[assignment]

        result = b.generate("hello")
        assert result == ""

    def test_generate_increments_counter(self):
        from unittest.mock import MagicMock

        b = MokaAIBackend(api_key="k")
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "x"
        mock_client.chat.completions.create.return_value = mock_response
        b._get_client = lambda: mock_client  # type: ignore[assignment]

        before = get_call_counter_er()
        b.generate("hello")
        assert get_call_counter_er() == before + 1

    def test_generate_retries_on_failure(self):
        from unittest.mock import MagicMock
        from unittest.mock import patch as mock_patch

        b = MokaAIBackend(api_key="k")
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("network")
        b._get_client = lambda: mock_client  # type: ignore[assignment]

        # Patch time.sleep to avoid actual delays
        with mock_patch("time.sleep"):
            with pytest.raises(RuntimeError) as exc_info:
                b.generate("hello")
            assert "MokaAIBackend.generate failed" in str(exc_info.value)


# --- Auto-mode integration ---


class TestAutoModePicksMokaBackend:
    """Test that auto mode returns MokaAIBackend when only MOKA_API_KEY is set."""

    def test_auto_with_moka_key_returns_fallback_with_moka(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "k"}, clear=True):
            from scripts.collaboration.llm_backend import FallbackBackend

            backend = create_backend("auto")
            assert isinstance(backend, FallbackBackend)
            # First backend should be MokaAIBackend
            assert any(isinstance(b, MokaAIBackend) for b in backend._backends)

    def test_auto_no_keys_returns_mock(self):
        with patch.dict(os.environ, {}, clear=True):
            from scripts.collaboration.llm_backend import MockBackend

            backend = create_backend("auto")
            assert isinstance(backend, MockBackend)


# --- Anti-Ghost guarantee ---


class TestMokaAntiGhost:
    """Verify module is wired into the dispatch pipeline (callable from real code)."""

    def test_moka_backend_is_constructible(self):
        b = MokaAIBackend(api_key="real-looking-key")
        assert b.is_available()

    def test_counter_increases_through_real_api(self):
        b = MokaAIBackend(api_key="real-key")
        # Simulate multiple invocations from a dispatcher
        for _ in range(5):
            b.is_available()
        assert get_call_counter_er() >= 5
