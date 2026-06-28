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
        """TraeBackend must always be available inside the IDE."""
        backend = self._get_backend()
        self.assertTrue(backend.is_available())

    def test_generate_returns_original_prompt(self):
        """TraeBackend.generate() must return the prompt unchanged (passthrough)."""
        backend = self._get_backend()
        prompt = "Execute this task in Trae IDE"
        result = backend.generate(prompt)
        self.assertEqual(result, prompt)


if __name__ == "__main__":
    unittest.main()
