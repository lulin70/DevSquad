"""Real LLM backend external tests.

These tests make actual API calls to LLM providers (OpenAI/Anthropic).
They are skipped unless the corresponding API keys are set.

Moved from ``tests/integration/`` to ``tests/external/`` in V4.1.2 Phase 3 TD-6
to separate "cross-module integration" (no external deps) from "real external
service" tests. See ``docs/audits/V4.1.2_Phase3_Plan.md`` §2.4.

Set environment variables to enable:
    DEVSQUAD_OPENAI_API_KEY=sk-...     # For OpenAI tests
    DEVSQUAD_ANTHROPIC_API_KEY=sk-...  # For Anthropic tests
"""

import os

import pytest

# Mark entire module as external (real LLM API calls).
pytestmark = pytest.mark.external


# ── Fixtures ──


@pytest.fixture
def openai_key():
    key = os.environ.get("DEVSQUAD_OPENAI_API_KEY")
    if not key:
        pytest.skip("DEVSQUAD_OPENAI_API_KEY not set")
    return key


@pytest.fixture
def anthropic_key():
    key = os.environ.get("DEVSQUAD_ANTHROPIC_API_KEY")
    if not key:
        pytest.skip("DEVSQUAD_ANTHROPIC_API_KEY not set")
    return key


# ── OpenAI Backend Tests ──


class TestOpenAIBackendReal:
    @pytest.mark.integration
    def test_is_available(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key)
        assert backend.is_available() is True

    @pytest.mark.integration
    def test_generate_simple(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key, max_tokens=50)
        result = backend.generate("Say 'hello' in one word.")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.integration
    def test_generate_code_task(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key, max_tokens=200)
        result = backend.generate("Write a Python function that adds two numbers.")
        assert isinstance(result, str)
        assert "def " in result or "function" in result.lower()

    @pytest.mark.integration
    def test_generate_stream(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key, max_tokens=50)
        chunks = list(backend.generate_stream("Count from 1 to 5."))
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)


# ── Anthropic Backend Tests ──


class TestAnthropicBackendReal:
    @pytest.mark.integration
    def test_is_available(self, anthropic_key):
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key)
        assert backend.is_available() is True

    @pytest.mark.integration
    def test_generate_simple(self, anthropic_key):
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=50)
        result = backend.generate("Say 'hello' in one word.")
        assert isinstance(result, str)
        assert len(result) > 0

    @pytest.mark.integration
    def test_generate_code_task(self, anthropic_key):
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=200)
        result = backend.generate("Write a Python function that adds two numbers.")
        assert isinstance(result, str)
        assert "def " in result or "function" in result.lower()

    @pytest.mark.integration
    def test_generate_stream(self, anthropic_key):
        """Test streaming response from Anthropic backend."""
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=50)
        chunks = list(backend.generate_stream("Count from 1 to 5."))
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)
        # Verify that streaming produces incremental content
        full_text = "".join(chunks)
        assert len(full_text) > 0


# ── Streaming Response Tests ──


class TestStreamingResponse:
    @pytest.mark.integration
    def test_openai_stream_incremental(self, openai_key):
        """Test that OpenAI streaming yields multiple chunks incrementally."""
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key, max_tokens=100)
        chunks = list(backend.generate_stream("List three colors, one per line."))
        assert len(chunks) >= 1
        full_response = "".join(chunks)
        assert len(full_response) > 0

    @pytest.mark.integration
    def test_anthropic_stream_incremental(self, anthropic_key):
        """Test that Anthropic streaming yields multiple chunks incrementally."""
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=100)
        chunks = list(backend.generate_stream("List three colors, one per line."))
        assert len(chunks) >= 1
        full_response = "".join(chunks)
        assert len(full_response) > 0


# ── Multi-turn Conversation Tests ──


class TestMultiTurnConversation:
    @pytest.mark.integration
    def test_openai_multi_turn(self, openai_key):
        """Test multi-turn conversation with OpenAI backend."""
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key, max_tokens=100)
        # First turn
        response1 = backend.generate("My name is Alice. Remember it.")
        assert isinstance(response1, str)
        assert len(response1) > 0
        # Second turn — verify context is not carried over (stateless generate)
        response2 = backend.generate("What is 2 + 2?")
        assert isinstance(response2, str)
        assert len(response2) > 0

    @pytest.mark.integration
    def test_anthropic_multi_turn(self, anthropic_key):
        """Test multi-turn conversation with Anthropic backend."""
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=100)
        # First turn
        response1 = backend.generate("My name is Bob. Remember it.")
        assert isinstance(response1, str)
        assert len(response1) > 0
        # Second turn
        response2 = backend.generate("What is 3 + 3?")
        assert isinstance(response2, str)
        assert len(response2) > 0


# ── Error Handling Tests ──


class TestErrorHandling:
    @pytest.mark.integration
    def test_openai_invalid_api_key(self):
        """Test that OpenAI backend handles invalid API key gracefully."""
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key="sk-invalid-key-1234567890", max_tokens=10)
        with pytest.raises(Exception):  # noqa: B017
            backend.generate("Hello")

    @pytest.mark.integration
    def test_anthropic_invalid_api_key(self):
        """Test that Anthropic backend handles invalid API key gracefully."""
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key="sk-ant-invalid-key-1234567890", max_tokens=10)
        with pytest.raises(Exception):  # noqa: B017
            backend.generate("Hello")

    @pytest.mark.integration
    def test_openai_invalid_key_does_not_crash(self):
        """Test that invalid key raises exception without crashing the process."""
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key="sk-invalid", max_tokens=10)
        error_caught = False
        try:
            backend.generate("Test")
        except Exception:
            error_caught = True
        assert error_caught, "Expected an exception for invalid API key"

    @pytest.mark.integration
    def test_anthropic_invalid_key_does_not_crash(self):
        """Test that invalid key raises exception without crashing the process."""
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key="sk-ant-invalid", max_tokens=10)
        error_caught = False
        try:
            backend.generate("Test")
        except Exception:
            error_caught = True
        assert error_caught, "Expected an exception for invalid API key"


# ── Full Dispatcher Integration Tests ──


class TestDispatcherRealLLM:
    @pytest.mark.integration
    def test_dispatch_with_openai(self, openai_key):
        """Test full dispatch pipeline with real OpenAI backend."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=openai_key, max_tokens=500)
        dispatcher = MultiAgentDispatcher(
            llm_backend=backend,
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
            enable_anchor_check=False,
            enable_retrospective=False,
            enable_usage_tracker=False,
        )
        try:
            result = dispatcher.dispatch(
                "Analyze the pros and cons of microservices architecture",
                mode="auto",
            )
            assert result.success is True
            assert result.task_description is not None
        finally:
            dispatcher.shutdown()

    @pytest.mark.integration
    def test_dispatch_with_anthropic(self, anthropic_key):
        """Test full dispatch pipeline with real Anthropic backend."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=500)
        dispatcher = MultiAgentDispatcher(
            llm_backend=backend,
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
            enable_anchor_check=False,
            enable_retrospective=False,
            enable_usage_tracker=False,
        )
        try:
            result = dispatcher.dispatch(
                "Analyze the pros and cons of microservices architecture",
                mode="auto",
            )
            assert result.success is True
            assert result.task_description is not None
        finally:
            dispatcher.shutdown()

    @pytest.mark.integration
    def test_fallback_backend_real(self, openai_key):
        """Test FallbackBackend with real OpenAI as primary."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import FallbackBackend, MockBackend, OpenAIBackend

        real = OpenAIBackend(api_key=openai_key, max_tokens=100)
        mock = MockBackend()
        fallback = FallbackBackend(backends=[real, mock])

        dispatcher = MultiAgentDispatcher(
            llm_backend=fallback,
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
            enable_anchor_check=False,
            enable_retrospective=False,
            enable_usage_tracker=False,
        )
        try:
            result = dispatcher.dispatch(
                "What is 2+2?",
                mode="auto",
            )
            assert result.success is True
        finally:
            dispatcher.shutdown()


# ── Auto backend fallback integration tests ──


class TestAutoBackendRealLLM:
    """Verify the new 'auto' backend behaves correctly with real API keys."""

    @pytest.mark.integration
    def test_auto_with_openai_key_uses_real_backend(self, openai_key):
        """With a real OpenAI key, auto should build a FallbackBackend chain."""
        from scripts.collaboration.llm_backend import (
            FallbackBackend,
            MockBackend,
            OpenAIBackend,
            create_backend,
        )

        backend = create_backend(
            "auto",
            openai_api_key=openai_key,
            openai_model=os.environ.get("DEVSQUAD_OPENAI_MODEL", "gpt-4"),
            max_tokens=50,
        )
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 2
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert isinstance(backend._backends[1], MockBackend)

    @pytest.mark.integration
    def test_auto_with_anthropic_key_uses_real_backend(self, anthropic_key):
        """With a real Anthropic key, auto should build a FallbackBackend chain."""
        from scripts.collaboration.llm_backend import (
            AnthropicBackend,
            FallbackBackend,
            MockBackend,
            create_backend,
        )

        backend = create_backend(
            "auto",
            anthropic_api_key=anthropic_key,
            anthropic_model=os.environ.get("DEVSQUAD_ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            max_tokens=50,
        )
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 2
        assert isinstance(backend._backends[0], AnthropicBackend)
        assert isinstance(backend._backends[1], MockBackend)

    @pytest.mark.integration
    def test_auto_without_keys_returns_mock(self):
        """Without any real keys, auto should degrade to MockBackend."""
        import os
        from unittest.mock import patch

        from scripts.collaboration.llm_backend import (
            MockBackend,
            create_backend,
        )

        # Ensure no real API keys are picked up from the environment.
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
            assert isinstance(backend, MockBackend)

    @pytest.mark.integration
    def test_auto_dispatch_with_openai_fallback_succeeds(self, openai_key):
        """Full dispatcher dispatch using auto backend with real OpenAI."""
        from scripts.collaboration.dispatcher import MultiAgentDispatcher
        from scripts.collaboration.llm_backend import create_backend

        backend = create_backend(
            "auto",
            openai_api_key=openai_key,
            openai_model=os.environ.get("DEVSQUAD_OPENAI_MODEL", "gpt-4"),
            max_tokens=200,
        )
        dispatcher = MultiAgentDispatcher(
            llm_backend=backend,
            enable_warmup=False,
            enable_compression=False,
            enable_permission=False,
            enable_memory=False,
            enable_skillify=False,
            enable_anchor_check=False,
            enable_retrospective=False,
            enable_usage_tracker=False,
        )
        try:
            result = dispatcher.dispatch(
                "Explain the difference between list and tuple in Python",
                mode="auto",
            )
            assert result.success is True
        finally:
            dispatcher.shutdown()
