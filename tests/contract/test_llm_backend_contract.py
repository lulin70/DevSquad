#!/usr/bin/env python3
"""
LLMBackend Contract Tests

Validates that all LLMBackend implementations conform to the ABC
interface defined in llm_backend.py. Both MockBackend and TraeBackend
(no API key required) must pass these tests.

Contract test ownership: shared between DevSquad and LLM integration teams.
Any breaking change to LLMBackend ABC must be negotiated.
"""

import os
import sys
import unittest
from collections.abc import Generator, Iterable

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from scripts.collaboration.llm_backend import LLMBackend, MockBackend, TraeBackend


class TestLLMBackendContract(unittest.TestCase):
    """Contract tests for LLMBackend ABC compliance.

    Uses MockBackend as the reference implementation. Subclasses override
    _get_backend() to test alternative implementations against the same
    contract.
    """

    def _get_backend(self) -> LLMBackend:
        """Return the reference LLMBackend implementation."""
        return MockBackend()

    def test_has_generate(self):
        """Verify backend exposes the generate() method."""
        backend = self._get_backend()
        self.assertTrue(hasattr(backend, "generate"))
        self.assertTrue(callable(backend.generate))

    def test_has_is_available(self):
        """Verify backend exposes the is_available() method."""
        backend = self._get_backend()
        self.assertTrue(hasattr(backend, "is_available"))
        self.assertTrue(callable(backend.is_available))

    def test_has_generate_stream(self):
        """Verify backend exposes the generate_stream() method."""
        backend = self._get_backend()
        self.assertTrue(hasattr(backend, "generate_stream"))
        self.assertTrue(callable(backend.generate_stream))

    def test_generate_returns_str(self):
        """Verify generate(prompt) returns a str."""
        backend = self._get_backend()
        result = backend.generate("test prompt")
        self.assertIsInstance(result, str)

    def test_is_available_returns_bool(self):
        """Verify is_available() returns a bool."""
        backend = self._get_backend()
        result = backend.is_available()
        self.assertIsInstance(result, bool)

    def test_generate_stream_returns_iterable(self):
        """Verify generate_stream(prompt) returns a generator/iterable of str."""
        backend = self._get_backend()
        result = backend.generate_stream("test prompt")
        self.assertIsInstance(result, (Generator, Iterable))
        # Consume the generator to verify it yields str chunks
        chunks = list(result)
        self.assertGreaterEqual(len(chunks), 1)
        self.assertTrue(all(isinstance(c, str) for c in chunks))


class TestMockBackendContract(TestLLMBackendContract):
    """Contract tests specific to MockBackend behavior."""

    def _get_backend(self) -> LLMBackend:
        return MockBackend()

    def test_is_available_returns_true(self):
        """MockBackend must always be available (no external dependencies)."""
        backend = self._get_backend()
        self.assertTrue(backend.is_available())

    def test_output_contains_mock_mode_marker(self):
        """MockBackend output must include the [MOCK MODE] marker."""
        backend = self._get_backend()
        result = backend.generate("test prompt")
        self.assertIn("[MOCK MODE]", result)


class TestTraeBackendContract(TestLLMBackendContract):
    """Contract tests specific to TraeBackend behavior."""

    def _get_backend(self) -> LLMBackend:
        return TraeBackend()

    def test_is_available_returns_true(self):
        """TraeBackend must always be available inside the IDE.

        V4.5.2: TraeBackend is_available() returns False (legacy passthrough).
        Use HostBridgeBackend for active host bridge. Tests reflect this contract.
        """
        backend = self._get_backend()
        self.assertFalse(backend.is_available())

    def test_generate_returns_original_prompt(self):
        """TraeBackend.generate() must return the prompt unchanged (passthrough)."""
        backend = self._get_backend()
        prompt = "Execute this task in Trae IDE"
        result = backend.generate(prompt)
        self.assertEqual(result, prompt)


class TestLLMBackendAbstractContract(unittest.TestCase):
    """Contract tests for the LLMBackend ABC itself.

    Verifies that LLMBackend is abstract and cannot be instantiated
    directly, and that all required abstract methods are declared.
    """

    def test_llm_backend_is_abstract_class(self):
        """LLMBackend must be an ABC and cannot be instantiated directly."""
        from abc import ABC

        self.assertTrue(issubclass(LLMBackend, ABC))

    def test_llm_backend_cannot_be_instantiated(self):
        """Instantiating LLMBackend directly must raise TypeError."""
        with self.assertRaises(TypeError):
            LLMBackend()  # type: ignore[abstract]

    def test_llm_backend_declares_generate_abstract(self):
        """LLMBackend must declare generate() as an abstract method."""
        self.assertIn("generate", LLMBackend.__abstractmethods__)

    def test_llm_backend_declares_is_available_abstract(self):
        """LLMBackend must declare is_available() as an abstract method."""
        self.assertIn("is_available", LLMBackend.__abstractmethods__)

    def test_llm_backend_provides_generate_stream_default(self):
        """LLMBackend must provide a concrete generate_stream() default (not abstract)."""
        # generate_stream has a default implementation, so it must NOT be abstract
        self.assertNotIn("generate_stream", LLMBackend.__abstractmethods__)


class TestMockBackendExtendedContract(unittest.TestCase):
    """Extended contract tests for MockBackend behavior."""

    def _get_backend(self) -> MockBackend:
        return MockBackend()

    def test_generate_includes_role_name(self):
        """MockBackend must include role_name in output when provided via kwargs."""
        backend = self._get_backend()
        result = backend.generate("test", role_name="Senior Architect")
        self.assertIn("Senior Architect", result)

    def test_generate_includes_task_description(self):
        """MockBackend must include task_description in output when provided."""
        backend = self._get_backend()
        result = backend.generate("test", task_description="Review PR #42")
        self.assertIn("Review PR #42", result)

    def test_generate_includes_prompt_length(self):
        """MockBackend must report the prompt length in chars."""
        backend = self._get_backend()
        prompt = "abcdefghij"  # 10 chars
        result = backend.generate(prompt)
        self.assertIn("10 chars", result)

    def test_generate_includes_separator_line(self):
        """MockBackend output must include a separator line of '=' chars."""
        backend = self._get_backend()
        result = backend.generate("test")
        self.assertIn("=" * 10, result)

    def test_generate_stream_yields_at_least_one_chunk(self):
        """MockBackend.generate_stream must yield at least one non-empty chunk."""
        backend = self._get_backend()
        chunks = list(backend.generate_stream("test prompt"))
        self.assertGreaterEqual(len(chunks), 1)
        # Concatenated chunks must contain the mock marker
        full = "".join(chunks)
        self.assertIn("[MOCK MODE]", full)

    def test_generate_with_empty_prompt_does_not_crash(self):
        """MockBackend.generate must handle an empty prompt gracefully."""
        backend = self._get_backend()
        result = backend.generate("")
        self.assertIsInstance(result, str)
        self.assertIn("[MOCK MODE]", result)
        self.assertIn("0 chars", result)

    def test_generate_with_unicode_prompt(self):
        """MockBackend must handle Unicode (Chinese) prompts."""
        backend = self._get_backend()
        result = backend.generate("你好世界，这是测试")
        self.assertIn("[MOCK MODE]", result)


class TestTraeBackendExtendedContract(unittest.TestCase):
    """Extended contract tests for TraeBackend behavior."""

    def _get_backend(self) -> TraeBackend:
        return TraeBackend()

    def test_generate_ignores_kwargs(self):
        """TraeBackend.generate must ignore all kwargs and return prompt unchanged."""
        backend = self._get_backend()
        prompt = "execute task"
        result = backend.generate(prompt, role_name="X", temperature=0.5, max_tokens=100)
        self.assertEqual(result, prompt)

    def test_generate_stream_yields_single_chunk(self):
        """TraeBackend.generate_stream must yield the prompt as a single chunk."""
        backend = self._get_backend()
        prompt = "stream this"
        chunks = list(backend.generate_stream(prompt))
        self.assertEqual(chunks, [prompt])

    def test_generate_with_empty_prompt(self):
        """TraeBackend.generate must return empty string for empty prompt."""
        backend = self._get_backend()
        self.assertEqual(backend.generate(""), "")

    def test_generate_with_multiline_prompt(self):
        """TraeBackend.generate must preserve multiline prompts unchanged."""
        backend = self._get_backend()
        prompt = "line1\nline2\nline3"
        self.assertEqual(backend.generate(prompt), prompt)


class TestCreateBackendFactoryContract(unittest.TestCase):
    """Contract tests for the create_backend() factory function."""

    def test_create_backend_mock_returns_mock_instance(self):
        """create_backend('mock') must return a MockBackend instance."""
        from scripts.collaboration.llm_backend import create_backend

        backend = create_backend("mock")
        self.assertIsInstance(backend, MockBackend)

    def test_create_backend_trae_returns_trae_instance(self):
        """create_backend('trae') must return a TraeBackend instance."""
        from scripts.collaboration.llm_backend import create_backend

        backend = create_backend("trae")
        self.assertIsInstance(backend, TraeBackend)

    def test_create_backend_unknown_type_raises_value_error(self):
        """create_backend with an unknown type must raise ValueError."""
        from scripts.collaboration.llm_backend import create_backend

        with self.assertRaises(ValueError) as ctx:
            create_backend("nonexistent-backend-type")
        self.assertIn("Unknown backend type", str(ctx.exception))

    def test_create_backend_auto_without_keys_returns_mock(self):
        """create_backend('auto') with no API keys must return a MockBackend (not FallbackBackend)."""
        import os
        from unittest.mock import patch

        from scripts.collaboration.llm_backend import (
            MockBackend,
            create_backend,
        )

        # Ensure no API keys in env so auto falls back to plain MockBackend
        env_patch = {
            "DEVSQUAD_LLM_BACKEND": "",
            "DEVSQUAD_OPENAI_API_KEY": "",
            "DEVSQUAD_ANTHROPIC_API_KEY": "",
            "MOKA_API_KEY": "",
        }
        with patch.dict(os.environ, env_patch, clear=False):
            backend = create_backend("auto")
            # With no real backends, auto returns plain MockBackend
            self.assertIsInstance(backend, MockBackend)

    def test_create_backend_default_arg_is_auto(self):
        """create_backend() with no args must default to 'auto' behavior."""
        import os
        from unittest.mock import patch

        from scripts.collaboration.llm_backend import create_backend

        env_patch = {
            "DEVSQUAD_LLM_BACKEND": "",
            "DEVSQUAD_OPENAI_API_KEY": "",
            "DEVSQUAD_ANTHROPIC_API_KEY": "",
            "MOKA_API_KEY": "",
        }
        with patch.dict(os.environ, env_patch, clear=False):
            backend = create_backend()
            # Must not raise; falls back to MockBackend when no keys present
            self.assertTrue(backend.is_available())


class TestBackendAvailabilityContract(unittest.TestCase):
    """Contract tests for backend is_available() behavior across implementations."""

    def test_mock_backend_always_available(self):
        """MockBackend.is_available() must always return True (no external deps)."""
        self.assertTrue(MockBackend().is_available())

    def test_trae_backend_always_available(self):
        """TraeBackend.is_available() returns False (V4.5.2 legacy passthrough).

        Use HostBridgeBackend for active host bridge invocation.
        """
        self.assertFalse(TraeBackend().is_available())

    def test_openai_backend_without_package_returns_false(self):
        """OpenAIBackend.is_available() must return False when the openai package
        is not installed (ImportError caught by the availability exception tuple).

        Note: when the openai package IS installed but no api_key is set, the
        OpenAI client raises OpenAIError which is NOT in the availability
        exception tuple. That is a known source-code gap documented here; this
        test covers the documented contract (ImportError → False).
        """
        import sys
        from unittest.mock import patch

        from scripts.collaboration.llm_backend import OpenAIBackend

        backend = OpenAIBackend(api_key=None)
        # Force _get_client to raise ImportError by hiding the openai module
        with patch.dict(sys.modules, {"openai": None}):
            result = backend.is_available()
        self.assertFalse(result)

    def test_anthropic_backend_without_package_returns_false(self):
        """AnthropicBackend.is_available() must return False when the anthropic
        package is not installed (ImportError caught by availability tuple).
        """
        import sys
        from unittest.mock import patch

        from scripts.collaboration.llm_backend import AnthropicBackend

        backend = AnthropicBackend(api_key=None)
        with patch.dict(sys.modules, {"anthropic": None}):
            result = backend.is_available()
        self.assertFalse(result)


class T6_LLMBackendBoundaryContract(unittest.TestCase):
    """Boundary and stress contract tests for LLMBackend implementations.

    Covers empty-string prompts, very-long prompts, special-character
    prompts, streaming interruption recovery, timeout configuration, and
    model-name validation across MockBackend and TraeBackend.
    """

    def _get_mock(self) -> MockBackend:
        return MockBackend()

    def _get_trae(self) -> TraeBackend:
        return TraeBackend()

    def test_mock_generate_empty_string_prompt(self) -> None:
        """MockBackend.generate with empty-string prompt must not crash.

        Boundary: an empty prompt must still produce a valid mock
        response containing the [MOCK MODE] marker and '0 chars'.
        """
        backend = self._get_mock()
        result = backend.generate("")
        self.assertIsInstance(result, str)
        self.assertIn("[MOCK MODE]", result)
        self.assertIn("0 chars", result)

    def test_mock_generate_very_long_prompt(self) -> None:
        """MockBackend.generate must handle a 100KB prompt without crashing.

        Stress: a 100,000-character prompt must be processed and the
        response must report the correct length.
        """
        backend = self._get_mock()
        long_prompt = "x" * 100_000
        result = backend.generate(long_prompt)
        self.assertIn("100000 chars", result)

    def test_mock_generate_special_characters_prompt(self) -> None:
        """MockBackend.generate must handle special characters in prompts.

        Boundary: prompts with null bytes, unicode control chars, SQL
        injection syntax, and shell metacharacters must not crash the
        backend or corrupt the response.
        """
        backend = self._get_mock()
        special_prompts = [
            "prompt\x00with\x00nulls",
            "prompt; DROP TABLE users;--",
            "prompt`echo hacked`",
            "prompt\n\t\rwith\tcontrol",
            "prompt with $HOME and ${PATH}",
            "prompt with emoji 🚀🎉 and unicode 中文",
        ]
        for prompt in special_prompts:
            result = backend.generate(prompt)
            self.assertIsInstance(result, str)
            self.assertIn("[MOCK MODE]", result)

    def test_trae_generate_stream_interruption_recovery(self) -> None:
        """TraeBackend.generate_stream must recover after partial consumption.

        Streaming boundary: consuming part of a generator and then
        abandoning it must not prevent subsequent generate_stream calls
        from working correctly.
        """
        backend = self._get_trae()
        gen1 = backend.generate_stream("first prompt")
        next(gen1)  # consume one chunk
        gen1.close()  # abandon the generator
        # Subsequent call must work normally
        chunks = list(backend.generate_stream("second prompt"))
        self.assertEqual(chunks, ["second prompt"])

    def test_openai_backend_timeout_configurable(self) -> None:
        """OpenAIBackend must accept and store a custom timeout value.

        Timeout boundary: the timeout parameter must be stored on the
        instance so callers can configure per-backend timeouts.
        """
        from scripts.collaboration.llm_backend import OpenAIBackend
        backend = OpenAIBackend(api_key="test-key", timeout=42.0)
        self.assertEqual(backend.timeout, 42.0)

    def test_anthropic_backend_timeout_configurable(self) -> None:
        """AnthropicBackend must accept and store a custom timeout value.

        Timeout boundary: the timeout parameter must be stored on the
        instance so callers can configure per-backend timeouts.
        """
        from scripts.collaboration.llm_backend import AnthropicBackend
        backend = AnthropicBackend(api_key="test-key", timeout=99.0)
        self.assertEqual(backend.timeout, 99.0)

    def test_openai_backend_custom_model_name(self) -> None:
        """OpenAIBackend must accept and store a custom model name.

        Model-name validation: the model parameter must be stored on the
        instance for use in API calls.
        """
        from scripts.collaboration.llm_backend import OpenAIBackend
        backend = OpenAIBackend(api_key="test-key", model="gpt-4o-mini")
        self.assertEqual(backend.model, "gpt-4o-mini")

    def test_anthropic_backend_custom_model_name(self) -> None:
        """AnthropicBackend must accept and store a custom model name.

        Model-name validation: the model parameter must be stored on the
        instance for use in API calls.
        """
        from scripts.collaboration.llm_backend import AnthropicBackend
        backend = AnthropicBackend(api_key="test-key", model="claude-3-opus")
        self.assertEqual(backend.model, "claude-3-opus")

    def test_trae_generate_empty_prompt_returns_empty(self) -> None:
        """TraeBackend.generate with empty prompt must return empty string.

        Boundary: the passthrough backend must return '' for an empty
        prompt, preserving the input verbatim.
        """
        backend = self._get_trae()
        self.assertEqual(backend.generate(""), "")

    def test_mock_generate_stream_partial_then_full_consumption(self) -> None:
        """MockBackend.generate_stream must support partial then full consumption.

        Streaming boundary: two independent generate_stream calls must
        each produce complete results, even if a previous generator was
        only partially consumed.
        """
        backend = self._get_mock()
        gen1 = backend.generate_stream("partial")
        first_chunk = next(gen1)
        self.assertIsInstance(first_chunk, str)
        gen1.close()
        # New independent call must yield all chunks
        chunks = list(backend.generate_stream("complete"))
        full = "".join(chunks)
        self.assertIn("[MOCK MODE]", full)


if __name__ == "__main__":
    unittest.main()
