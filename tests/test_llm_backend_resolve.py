#!/usr/bin/env python3
"""
Tests for B/A/C backend path resolution (V4.5.2).

Tests that create_backend resolves to the correct path in B→A→C order.
Covers §7.6 resolve table and §7.11 test cases from the test plan.

Note: These tests intentionally avoid real network calls by monkeypatching
env vars and importing HostBridgeBackend with mock host detection.
"""

import json
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from scripts.collaboration.backend_paths import (
    BackendPath,
    BackendUnavailable,
)
from scripts.collaboration.host_llm_bridge import HostBridgeBackend
from scripts.collaboration.llm_backend import (
    AnthropicBackend,
    FallbackBackend,
    MockBackend,
    OpenAIBackend,
    TraeBackend,
    _apply_explicit_env_defaults,
    _moka_file_config,
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
        """TRAE_ENV set → auto selects HostBridgeBackend first (B path)."""
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
        assert backend.backend_id == "host-v2"
        assert backend.backend_status().selected_path == "host-v2"

    def test_auto_with_host_ignores_provider_keys(self):
        """Host selection is independent of all direct-provider credentials."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {
                "TRAE_ENV": "1",
                "MOKA_API_KEY": "sk-moka",
                "DEVSQUAD_OPENAI_API_KEY": "sk-openai",
                "DEVSQUAD_ANTHROPIC_API_KEY": "sk-anthropic",
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
        assert isinstance(backend, HostBridgeBackend)
        assert backend.backend_id == "host-v2"
        assert backend.backend_status().chain == ("host-v2",)

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
        """Both keys → auto returns FallbackBackend with [OpenAI, Anthropic, Mock].

        V4.5.20: A-path order is Moka → OpenAI → Anthropic; V4.5.2 P-1 adds the
        Mock tail for graceful degradation.
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
        # V4.5.20 order: OpenAI (DeepSeek) first, then Anthropic, then Mock
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert isinstance(backend._backends[1], AnthropicBackend)
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
        """auto-fallback with OpenAI key → FallbackBackend([OpenAI, Mock]).

        V4.5.2 P-1: graceful degradation falls back to MockBackend on failure.
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
                backend = create_backend("auto-fallback")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert len(backend._backends) == 2
        assert isinstance(backend._backends[0], OpenAIBackend)
        assert isinstance(backend._backends[1], MockBackend)

    def test_auto_fallback_exposes_distinct_bac_identities(self):
        """Host, direct providers, and mock remain distinguishable in status."""
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {
                "TRAE_ENV": "1",
                "MOKA_API_KEY": "sk-moka",
                "DEVSQUAD_OPENAI_API_KEY": "sk-openai",
                "DEVSQUAD_ANTHROPIC_API_KEY": "sk-anthropic",
            },
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
        status = backend.backend_status().to_dict()
        assert status["requested"] == "auto-fallback"
        assert status["chain"] == ["host-v2", "moka", "openai", "anthropic", "mock"]
        assert status["selected_path"] == "host-v2"


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


class TestMokaFileConfig:
    """Tests for the gitignored moka_ai.json credentials file.

    All tests bypass the default repo-root path (the maintainer may have a
    real credentials file there) by either passing an explicit ``path`` or
    monkeypatching ``_MOKA_FILE_CONFIG_CACHE``.
    """

    def test_moka_file_config_reads_url_model_key(self, tmp_path):
        """A well-formed moka_ai.json yields its url/model/key values."""
        cfg_file = tmp_path / "moka_ai.json"
        cfg_file.write_text(
            json.dumps({"url": "http://127.0.0.1:8787/v1", "model": "moka/glm-5.3", "key": "sk-test"}),
            encoding="utf-8",
        )
        cfg = _moka_file_config(path=cfg_file)
        assert cfg == {
            "url": "http://127.0.0.1:8787/v1",
            "model": "moka/glm-5.3",
            "key": "sk-test",
        }

    def test_moka_file_config_absent_is_empty(self, tmp_path):
        """Missing file → empty dict (fail-quiet, never a crash source)."""
        assert _moka_file_config(path=tmp_path / "nope.json") == {}

    def test_moka_file_config_malformed_warns_empty(self, tmp_path, caplog):
        """Bad JSON → empty dict + warning, no raise."""
        import logging

        cfg_file = tmp_path / "moka_ai.json"
        cfg_file.write_text("{not valid json", encoding="utf-8")
        with caplog.at_level(logging.WARNING, logger="scripts.collaboration.llm_backend"):
            cfg = _moka_file_config(path=cfg_file)
        assert cfg == {}
        assert any("moka_ai.json" in record.message for record in caplog.records)

    def test_moka_env_overrides_file_config(self, monkeypatch):
        """Env keys beat file values for explicit moka requests."""
        import scripts.collaboration.llm_backend as mod

        monkeypatch.setattr(
            mod,
            "_MOKA_FILE_CONFIG_CACHE",
            {"key": "sk-file", "url": "http://file:1/v1", "model": "file-model"},
        )
        kwargs: dict = {"extra": "keep"}
        with patch.dict(os.environ, {"MOKA_API_KEY": "sk-env"}, clear=True):
            _apply_explicit_env_defaults("moka", kwargs)
        assert kwargs["api_key"] == "sk-env"
        assert kwargs["base_url"] == "http://file:1/v1"
        assert kwargs["model"] == "file-model"
        assert kwargs["extra"] == "keep"

    def test_moka_file_used_when_env_absent(self, monkeypatch):
        """File values apply when the env vars are unset."""
        import scripts.collaboration.llm_backend as mod

        monkeypatch.setattr(
            mod,
            "_MOKA_FILE_CONFIG_CACHE",
            {"key": "sk-file", "url": "http://file:1/v1", "model": "file-model"},
        )
        kwargs: dict = {}
        with patch.dict(os.environ, {}, clear=True):
            _apply_explicit_env_defaults("moka", kwargs)
        assert kwargs["api_key"] == "sk-file"
        assert kwargs["base_url"] == "http://file:1/v1"
        assert kwargs["model"] == "file-model"

    def test_moka_caller_kwargs_beat_env_and_file(self, monkeypatch):
        """Explicit caller kwargs win over both env and file."""
        import scripts.collaboration.llm_backend as mod

        monkeypatch.setattr(
            mod,
            "_MOKA_FILE_CONFIG_CACHE",
            {"key": "sk-file", "url": "http://file:1/v1", "model": "file-model"},
        )
        kwargs: dict = {"api_key": "sk-caller", "base_url": "http://caller:1/v1", "model": "caller-model"}
        with patch.dict(os.environ, {"MOKA_API_KEY": "sk-env"}, clear=True):
            _apply_explicit_env_defaults("moka", kwargs)
        assert kwargs["api_key"] == "sk-caller"
        assert kwargs["base_url"] == "http://caller:1/v1"
        assert kwargs["model"] == "caller-model"

    # -- V4.5.22: the file feeds the auto / auto-fallback chains ------------

    def test_auto_chain_includes_moka_from_file(self, monkeypatch):
        """File credentials alone put Moka first in the auto A-path chain."""
        import scripts.collaboration.llm_backend as mod
        from scripts.collaboration.moka_backend import MokaAIBackend

        monkeypatch.setattr(
            mod,
            "_MOKA_FILE_CONFIG_CACHE",
            {"key": "sk-file", "url": "http://file:1/v1", "model": "file-model"},
        )
        patches = _patch_dotenv()
        with patch.dict(os.environ, {}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto-fallback")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        assert isinstance(backend._backends[0], MokaAIBackend)
        assert backend._backends[0]._api_key == "sk-file"
        assert backend._backends[0].base_url == "http://file:1/v1"
        assert backend._backends[0].model == "file-model"
        assert isinstance(backend._backends[-1], MockBackend)

    def test_auto_chain_moka_precedes_deepseek_per_design_order(self, monkeypatch):
        """Design order: Moka candidate sits before the OpenAI/DeepSeek one."""
        import scripts.collaboration.llm_backend as mod

        monkeypatch.setattr(
            mod,
            "_MOKA_FILE_CONFIG_CACHE",
            {"key": "sk-file", "url": "http://file:1/v1", "model": "file-model"},
        )
        patches = _patch_dotenv()
        with patch.dict(os.environ, {"DEVSQUAD_OPENAI_API_KEY": "sk-deepseek"}, clear=True):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto-fallback")
            finally:
                for p in reversed(patches):
                    p.stop()
        assert isinstance(backend, FallbackBackend)
        kinds = [type(b).__name__ for b in backend._backends]
        assert kinds == ["MokaAIBackend", "OpenAIBackend", "MockBackend"]

    def test_auto_chain_env_moka_key_beats_file(self, monkeypatch):
        """Env MOKA_API_KEY still wins over file values inside the auto chain."""
        import scripts.collaboration.llm_backend as mod

        monkeypatch.setattr(
            mod,
            "_MOKA_FILE_CONFIG_CACHE",
            {"key": "sk-file", "url": "http://file:1/v1", "model": "file-model"},
        )
        patches = _patch_dotenv()
        with patch.dict(
            os.environ,
            {"MOKA_API_KEY": "sk-env", "MOKA_BASE_URL": "http://env:1/v1"},
            clear=True,
        ):
            for p in patches:
                p.start()
            try:
                backend = create_backend("auto-fallback")
            finally:
                for p in reversed(patches):
                    p.stop()
        moka = backend._backends[0]
        assert moka._api_key == "sk-env"
        assert moka.base_url == "http://env:1/v1"
        assert moka.model == "file-model"  # env MOKA_MODEL unset → file value

    def test_auto_chain_without_file_or_keys_still_mock(self, monkeypatch):
        """Empty file cache + no env keys → MockBackend (regression guard)."""
        import scripts.collaboration.llm_backend as mod

        monkeypatch.setattr(mod, "_MOKA_FILE_CONFIG_CACHE", {})
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
