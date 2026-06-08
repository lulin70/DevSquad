"""Real LLM backend integration tests.

These tests make actual API calls to LLM providers.
They are skipped unless the corresponding API keys are set.

Set environment variables to enable:
    DEVSQUAD_OPENAI_API_KEY=sk-...     # For OpenAI tests
    DEVSQUAD_ANTHROPIC_API_KEY=sk-...  # For Anthropic tests
"""
import os
import pytest
import time

# Mark entire module as integration
pytestmark = pytest.mark.integration


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
    def test_is_available(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend
        backend = OpenAIBackend(api_key=openai_key)
        assert backend.is_available() is True

    def test_generate_simple(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend
        backend = OpenAIBackend(api_key=openai_key, max_tokens=50)
        result = backend.generate("Say 'hello' in one word.")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_code_task(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend
        backend = OpenAIBackend(api_key=openai_key, max_tokens=200)
        result = backend.generate("Write a Python function that adds two numbers.")
        assert isinstance(result, str)
        assert "def " in result or "function" in result.lower()

    def test_generate_stream(self, openai_key):
        from scripts.collaboration.llm_backend import OpenAIBackend
        backend = OpenAIBackend(api_key=openai_key, max_tokens=50)
        chunks = list(backend.generate_stream("Count from 1 to 5."))
        assert len(chunks) > 0
        assert all(isinstance(c, str) for c in chunks)


# ── Anthropic Backend Tests ──

class TestAnthropicBackendReal:
    def test_is_available(self, anthropic_key):
        from scripts.collaboration.llm_backend import AnthropicBackend
        backend = AnthropicBackend(api_key=anthropic_key)
        assert backend.is_available() is True

    def test_generate_simple(self, anthropic_key):
        from scripts.collaboration.llm_backend import AnthropicBackend
        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=50)
        result = backend.generate("Say 'hello' in one word.")
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_code_task(self, anthropic_key):
        from scripts.collaboration.llm_backend import AnthropicBackend
        backend = AnthropicBackend(api_key=anthropic_key, max_tokens=200)
        result = backend.generate("Write a Python function that adds two numbers.")
        assert isinstance(result, str)
        assert "def " in result or "function" in result.lower()


# ── Full Dispatcher Integration Tests ──

class TestDispatcherRealLLM:
    def test_dispatch_with_openai(self, openai_key):
        """Test full dispatch pipeline with real OpenAI backend."""
        from scripts.collaboration.llm_backend import OpenAIBackend
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

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

    def test_dispatch_with_anthropic(self, anthropic_key):
        """Test full dispatch pipeline with real Anthropic backend."""
        from scripts.collaboration.llm_backend import AnthropicBackend
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

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

    def test_fallback_backend_real(self, openai_key):
        """Test FallbackBackend with real OpenAI as primary."""
        from scripts.collaboration.llm_backend import OpenAIBackend, MockBackend, FallbackBackend
        from scripts.collaboration.dispatcher import MultiAgentDispatcher

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
