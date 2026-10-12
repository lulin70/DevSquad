#!/usr/bin/env python3
"""Unit tests: CLI backend env-var priority (V4.6.0 P1-b finding).

``_create_backend`` must prefer the product-namespaced ``DEVSQUAD_*`` env
vars over the generic ``OPENAI_*``/``ANTHROPIC_*`` fallbacks. The inverted
order let a generic value loaded from ``.env`` (python-dotenv, override=False)
silently override an explicit product-level setting — which is exactly how
the J3 blocked-journey probe first failed (exit 0 instead of 2).
"""

from __future__ import annotations

import pytest

from scripts import cli_utils


@pytest.fixture()
def capture_backend(monkeypatch):
    """Stub create_backend and return the kwargs it was called with."""
    captured: dict = {}

    def fake_create_backend(backend_type: str, **kwargs):
        captured["backend_type"] = backend_type
        captured["kwargs"] = kwargs
        return object()  # any non-None sentinel

    monkeypatch.setattr("scripts.collaboration.llm_backend.create_backend", fake_create_backend)
    return captured


class TestOpenAIEnvPriority:
    def test_devsquad_key_wins_over_generic(self, monkeypatch, capture_backend):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "sk-devsquad-wins")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-generic-loses")
        cli_utils._create_backend("openai")
        assert capture_backend["kwargs"]["api_key"] == "sk-devsquad-wins"

    def test_generic_key_used_when_devsquad_absent(self, monkeypatch, capture_backend):
        monkeypatch.delenv("DEVSQUAD_OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-generic-only")
        cli_utils._create_backend("openai")
        assert capture_backend["kwargs"]["api_key"] == "sk-generic-only"

    def test_devsquad_base_url_wins_over_generic(self, monkeypatch, capture_backend):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "sk-x")
        monkeypatch.setenv("DEVSQUAD_OPENAI_BASE_URL", "http://devsquad:9")
        monkeypatch.setenv("OPENAI_BASE_URL", "http://generic:9")
        cli_utils._create_backend("openai")
        assert capture_backend["kwargs"]["base_url"] == "http://devsquad:9"

    def test_devsquad_model_wins_over_generic(self, monkeypatch, capture_backend):
        monkeypatch.setenv("DEVSQUAD_OPENAI_API_KEY", "sk-x")
        monkeypatch.setenv("DEVSQUAD_OPENAI_MODEL", "devsquad-model")
        monkeypatch.setenv("OPENAI_MODEL", "generic-model")
        cli_utils._create_backend("openai")
        assert capture_backend["kwargs"]["model"] == "devsquad-model"


class TestAnthropicEnvPriority:
    def test_devsquad_key_wins_over_generic(self, monkeypatch, capture_backend):
        monkeypatch.setenv("DEVSQUAD_ANTHROPIC_API_KEY", "sk-ant-devsquad")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-generic")
        cli_utils._create_backend("anthropic")
        assert capture_backend["kwargs"]["api_key"] == "sk-ant-devsquad"

    def test_generic_key_used_when_devsquad_absent(self, monkeypatch, capture_backend):
        monkeypatch.delenv("DEVSQUAD_ANTHROPIC_API_KEY", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-generic")
        cli_utils._create_backend("anthropic")
        assert capture_backend["kwargs"]["api_key"] == "sk-ant-generic"
