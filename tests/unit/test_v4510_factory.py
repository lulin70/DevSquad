#!/usr/bin/env python3
"""V4.5.10 factory wiring tests (G-α).

Proves create_backend("host"/"auto"/"auto-fallback") resolves the real
HostBridgeBackendV2 adapter by default, with fail-closed flag handling.
"""
from __future__ import annotations

import pytest

from scripts.collaboration.host_llm_bridge import (
    HostBridgeBackend,
    HostBridgeBackendV2,
)
from scripts.collaboration.llm_backend import (
    _build_host_bridge_backend,
    _resolve_host_bridge_version,
    create_backend,
)


@pytest.fixture(autouse=True)
def clean_host_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Isolate host-bridge feature flags for every test."""
    for var in (
        "DEVSQUAD_HOST_BRIDGE_VERSION",
        "DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2",
        "TRAE_ENV",
        "TRAE_AGENT_PATH",
        "CLAUDE_CODE_ENV",
        "ANTHROPIC_ENV",
    ):
        monkeypatch.delenv(var, raising=False)


class TestResolveHostBridgeVersion:
    def test_default_is_v2(self) -> None:
        assert _resolve_host_bridge_version() == "v2"

    def test_explicit_v1(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "v1")
        assert _resolve_host_bridge_version() == "v1"

    def test_explicit_v2(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "v2")
        assert _resolve_host_bridge_version() == "v2"

    @pytest.mark.parametrize("raw", ["V1", " v2 ", "V2"])
    def test_case_and_space_tolerant(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", raw)
        assert _resolve_host_bridge_version() == raw.strip().lower()

    @pytest.mark.parametrize("raw", ["v3", "1", "legacy", "protocol_version_9"])
    def test_invalid_value_fails_closed(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", raw)
        with pytest.raises(ValueError):
            _resolve_host_bridge_version()

    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "True"])
    def test_disable_flag_forces_v1(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2", raw)
        assert _resolve_host_bridge_version() == "v1"

    def test_disable_flag_beats_version_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2", "1")
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "v2")
        assert _resolve_host_bridge_version() == "v1"

    def test_empty_version_value_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "")
        assert _resolve_host_bridge_version() == "v2"


class TestBuildHostBridgeBackend:
    def test_default_builds_v2_adapter(self, tmp_path) -> None:
        backend = _build_host_bridge_backend(bridge_dir=str(tmp_path / "b"))
        assert isinstance(backend, HostBridgeBackendV2)
        assert isinstance(backend, HostBridgeBackend)  # contract preserved
        assert backend.timeout == 600

    def test_v1_flag_builds_v1_adapter(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "v1")
        backend = _build_host_bridge_backend(bridge_dir=str(tmp_path / "b"))
        assert type(backend) is HostBridgeBackend

    def test_disable_flag_builds_v1_adapter(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DEVSQUAD_V455_DISABLE_HOST_BRIDGE_V2", "1")
        backend = _build_host_bridge_backend(bridge_dir=str(tmp_path / "b"))
        assert type(backend) is HostBridgeBackend

    def test_v2_default_dir_is_versioned(self) -> None:
        from scripts.collaboration.host_llm_bridge_v2 import HostLLMBridgeV2

        backend = _build_host_bridge_backend(bridge_dir=None)
        assert isinstance(backend.bridge, HostLLMBridgeV2)
        assert backend.bridge.bridge_dir.name == "v2"
        assert backend.bridge.bridge_dir.parent.name == "host_llm_bridge"


class TestCreateBackendWiring:
    def test_host_backend_type_is_v2(self, tmp_path) -> None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setenv("TRAE_ENV", "1")
            backend = create_backend("host", bridge_dir=str(tmp_path / "b"))
        assert isinstance(backend, HostBridgeBackendV2)
        assert type(backend) is not HostBridgeBackend

    def test_host_explicit_v1_flag(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "v1")
        backend = create_backend("host", bridge_dir=str(tmp_path / "b"))
        assert type(backend) is HostBridgeBackend

    def test_host_v1_explicit_type(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        backend = create_backend("host-v1", bridge_dir=str(tmp_path / "b"))
        assert type(backend) is HostBridgeBackend

    def test_host_v2_explicit_type(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        backend = create_backend("host-v2", bridge_dir=str(tmp_path / "b"))
        assert type(backend) is HostBridgeBackendV2

    def test_auto_b_path_returns_v2(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        backend = create_backend("auto", bridge_dir=str(tmp_path / "b"))
        assert isinstance(backend, HostBridgeBackendV2)

    def test_auto_fallback_b_candidate_is_v2(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        backend = create_backend(
            "auto-fallback", bridge_dir=str(tmp_path / "b"), timeout_seconds=600
        )
        # auto-fallback wraps candidates in FallbackBackend; the B candidate
        # (first) must be the real v2 adapter
        assert type(backend._backends[0]) is HostBridgeBackendV2

    def test_auto_fallback_v1_flag(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        monkeypatch.setenv("DEVSQUAD_HOST_BRIDGE_VERSION", "v1")
        backend = create_backend(
            "auto-fallback", bridge_dir=str(tmp_path / "b"), timeout_seconds=600
        )
        assert type(backend._backends[0]) is HostBridgeBackend

    def test_trae_passthrough_unchanged(self) -> None:
        from scripts.collaboration.llm_backend import TraeBackend

        backend = create_backend("trae")
        assert type(backend) is TraeBackend

    def test_host_timeout_passthrough(self, tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("TRAE_ENV", "1")
        backend = create_backend(
            "host", bridge_dir=str(tmp_path / "b"), timeout_seconds=123
        )
        assert backend.timeout == 123

    def test_host_without_env_raises(self, tmp_path) -> None:
        from scripts.collaboration.backend_paths import BackendUnavailable

        with pytest.raises(BackendUnavailable):
            create_backend("host", bridge_dir=str(tmp_path / "b"))
