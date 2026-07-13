# conftest.py - Pytest configuration for DevSquad
"""
Pytest configuration with markers and fixtures.
"""

import os
from pathlib import Path


def _load_env_file() -> None:
    """Load .env file if it exists (not tracked by git).

    Manually parses KEY=VALUE lines without requiring python-dotenv.
    Only sets variables that are not already in the environment (env wins over .env).
    """
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_env_file()


def pytest_configure(config):
    """Configure custom markers."""
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "integration: marks tests as integration tests")
    config.addinivalue_line("markers", "tech_debt: marks tests with known failures (V3.7.0 tech debt)")


# Known failing tests - now marked with @pytest.mark.xfail instead of collect_ignore
# See individual test files for xfail reasons


class FakeLLMBackend:
    """Unified fake LLM backend for tests.

    Supports multiple instantiation patterns to consolidate the previously
    duplicated FakeLLMBackend definitions in test_feedback_control_loop.py
    (sequential responses + default) and test_ue_test_framework.py (single
    response + exception raising):

    - Sequential:  ``FakeLLMBackend(["resp1", "resp2"], default="fallback")``
    - Single:      ``FakeLLMBackend("a single response")``  (repeats every call)
    - Exception:   ``FakeLLMBackend(RuntimeError("boom"))``  (raises every call)
    - Default only: ``FakeLLMBackend(default="refined task")``  (returns default every call)
    - Empty:       ``FakeLLMBackend()``  (returns default every call)

    Attributes:
        _call_count:        Number of times generate() was called.
        _received_prompts:  List of prompts passed to generate(), in order.

    The public ``call_count`` property mirrors the original ue_test_framework
    attribute name (without underscore) for backward compatibility.
    """

    def __init__(
        self,
        responses: list[str] | str | Exception | None = None,
        *,
        default: str = "Refined task with clearer objectives",
    ) -> None:
        self._default = default
        self._index = 0
        self._call_count = 0
        self._received_prompts: list[str] = []
        self._raises: Exception | None = None
        self._responses: list[str] = []
        self._repeat_single: str | None = None
        if isinstance(responses, Exception):
            self._raises = responses
        elif isinstance(responses, str):
            self._repeat_single = responses
        elif isinstance(responses, list):
            self._responses = list(responses)

    @property
    def call_count(self) -> int:
        """Public call count accessor (backward compat with ue_test_framework)."""
        return self._call_count

    def generate(self, prompt: str) -> str:
        """Return next scripted response, raise the scripted exception, or default."""
        self._call_count += 1
        self._received_prompts.append(prompt)
        if self._raises is not None:
            raise self._raises
        if self._repeat_single is not None:
            return self._repeat_single
        if self._index < len(self._responses):
            resp = self._responses[self._index]
            self._index += 1
            return resp
        return self._default
