#!/usr/bin/env python3
"""
Tests for B/A/C backend path resolution (V4.5.2).

Tests that create_backend resolves to the correct path in B→A→C order.
Covers §7.6 resolve table and §7.11 test cases from the test plan.

Note: These tests intentionally avoid real network calls by monkeypatching
env vars and importing HostBridgeBackend with mock host detection.
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from scripts.collaboration.backend_paths import BackendPath, BackendUnavailable
from scripts.collaboration.host_llm_bridge import HostBridgeBackend
from scripts.collaboration.llm_backend import (
    AnthropicBackend,
    FallbackBackend,
    MockBackend,
    OpenAIBackend,
    TraeBackend,
    create_backend,
)

pytestmark = pytest.mark.unit


def _patch_dotenv():
    """Return patches that disable .env loading so os.environ stays clean."""
    return [
        patch("scripts.collaboration.llm_backend._load_dotenv"),
    ]


# ---------------------------------------------------------------------------
# 3.1 B/A/C 路径解析 (8 cases)
# ---------------------------------------------------------------------------


class TestCreateBackendAuto:
    """Tests for create_backend(backend_type='auto') — B→A→C resolution."""

    def test_auto_without_host_or_keys_returns_mock(self):
        """No host env, no keys → auto returns MockBackend (C path)."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, MockBackend)
        assert backend.path == "C"

    def test_auto_with_host_env_returns_host_bridge(self):
        """TRAE_ENV set → auto returns HostBridgeBackend (B path)."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"TRAE_ENV": "1"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, HostBridgeBackend)
        assert backend.path == "B"

    def test_auto_with_openai_key_returns_openai(self):
        """OpenAI key only → auto returns FallbackBackend([OpenAIBackend, Mock]).

        V4.5.2 P-1: auto mode always wraps with MockBackend tail for graceful
        degradation. This means a single API failure → mock fallback (no raise).
        """
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert backend._backends[0].path == "A"

    def test_auto_with_anthropic_key_returns_anthropic(self):
        """Anthropic key only → auto returns FallbackBackend([Anthropic, Mock]).

        V4.5.2 P-1: graceful degradation wrapping.
        """
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"DEVSQUAD_ANTHROPIC_API_KEY": "sk-test-anthropic"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert isinstance(backend._backends[0], AnthropicBackend)
        assert backend._backends[0].path == "A"

    def test_auto_with_moka_key_returns_openai(self):
        """MOKA key only → auto returns FallbackBackend([MokaAIBackend, Mock])."""
        from scripts.collaboration.moka_backend import MokaAIBackend
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"MOKA_API_KEY": "sk-test-moka"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert isinstance(backend._backends[0], MokaAIBackend)
        assert backend._backends[0].path == "A"

    def test_auto_with_both_keys_returns_fallback(self):
        """Both keys → auto returns FallbackBackend with [Anthropic, OpenAI, Mock].

        V4.5.2 P-1: Mock tail added for graceful degradation.
        """
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {
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
        # Order: Anthropic first, then OpenAI, then Mock
        assert isinstance(backend._backends[0], AnthropicBackend)
        assert isinstance(backend._backends[1], OpenAIBackend)
        assert isinstance(backend._backends[2], MockBackend)

    def test_auto_reads_backend_from_env(self):
        """DEVSQUAD_LLM_BACKEND=mock overrides auto default."""
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

    def test_auto_uses_env_backend_when_specified(self):
        """DEVSQUAD_LLM_BACKEND=openai with key → OpenAIBackend."""
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
        assert isinstance(backend, OpenAIBackend)
        assert not isinstance(backend, FallbackBackend)


class TestCreateBackendExplicit:
    """Tests for explicit backend_type values."""

    def test_explicit_mock_stays_mock(self):
        """create_backend('mock') → MockBackend."""
        backend = create_backend("mock")
        assert isinstance(backend, MockBackend)
        assert backend.path == "C"

    def test_explicit_host_raises_when_not_available(self):
        """create_backend('host') without host env → BackendUnavailable."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                with pytest.raises(BackendUnavailable, match="Host bridge not available"):
                    create_backend("host")
            finally:
                for p in reversed(patches):
                    p.stop()

    def test_explicit_host_with_env_returns_host_bridge(self):
        """create_backend('host') with TRAE_ENV → HostBridgeBackend."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"TRAE_ENV": "1"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("host")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, HostBridgeBackend)
        assert backend.path == "B"

    def test_explicit_trae_returns_trae_backend(self):
        """create_backend('trae') → TraeBackend (legacy passthrough)."""
        backend = create_backend("trae")
        assert isinstance(backend, TraeBackend)
        assert backend.path == "B-passthrough"
        # V4.5.2: TraeBackend.is_available() returns False
        assert not backend.is_available()

    def test_explicit_openai_returns_openai(self):
        """create_backend('openai') → OpenAIBackend."""
        backend = create_backend("openai")
        assert isinstance(backend, OpenAIBackend)
        assert backend.path == "A"

    def test_explicit_anthropic_returns_anthropic(self):
        """create_backend('anthropic') → AnthropicBackend."""
        backend = create_backend("anthropic")
        assert isinstance(backend, AnthropicBackend)
        assert backend.path == "A"

    def test_explicit_moka_returns_openai(self):
        """create_backend('moka') → MokaAIBackend (path='A').

        V4.5.2 P12.1.1: MOKA is now an explicit backend (no longer OpenAIBackend alias).
        """
        from scripts.collaboration.moka_backend import MokaAIBackend
        backend = create_backend("moka")
        assert isinstance(backend, MokaAIBackend)
        assert backend.path == "A"

    def test_unknown_backend_type_raises_value_error(self):
        """Unknown backend type → ValueError."""
        with pytest.raises(ValueError, match="Unknown backend type"):
            create_backend("nonexistent")


class TestCreateBackendDefault:
    """Tests for create_backend() with no arguments."""

    def test_default_without_keys_or_host_is_mock(self):
        """No args, no env → MockBackend."""
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

    def test_default_with_openai_key_is_openai(self):
        """No args + OpenAI key → FallbackBackend([OpenAIBackend, Mock]).

        V4.5.2 P-1: graceful degradation wrapping.
        """
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
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert backend._backends[0].path == "A"


class TestCreateBackendAutoFallback:
    """Tests for auto-fallback mode (B→A→C chain)."""

    def test_auto_fallback_without_host_or_keys(self):
        """auto-fallback without host or keys → MockBackend (C)."""
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto-fallback")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, MockBackend)

    def test_auto_fallback_with_openai_key(self):
        """auto-fallback with OpenAI key → FallbackBackend([OpenAI, Mock])."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"DEVSQUAD_OPENAI_API_KEY": "sk-test-openai"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto-fallback")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 2
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert isinstance(backend._backends[1], MockBackend)


class TestBackendPathAttribute:
    """Tests for backend.path attribute (contract tests)."""

    def test_mock_path_is_c(self):
        assert MockBackend().path == "C"

    def test_trae_path_is_b_passthrough(self):
        assert TraeBackend().path == "B-passthrough"

    def test_openai_path_is_a(self):
        assert OpenAIBackend(api_key="sk-test").path == "A"

    def test_anthropic_path_is_a(self):
        assert AnthropicBackend(api_key="sk-test").path == "A"

    def test_host_bridge_path_is_b(self):
        assert HostBridgeBackend().path == "B"

    def test_fallback_path_is_a_plus_c(self):
        backend = FallbackBackend([MockBackend()])
        assert backend.path == "A+C"


class TestResolveOrderBAC:
    """Tests that RESOLVE_ORDER = (B, A, C)."""

    def test_resolve_order(self):
        from scripts.collaboration.backend_paths import RESOLVE_ORDER

        assert len(RESOLVE_ORDER) == 3
        assert RESOLVE_ORDER[0] == BackendPath.B_HOST_BRIDGE
        assert RESOLVE_ORDER[1] == BackendPath.A_DIRECT_API
        assert RESOLVE_ORDER[2] == BackendPath.C_MOCK
