"""Tests for backend config + devsquad backend CLI (V4.5.2 P12.1.5)."""

from __future__ import annotations

import os
from argparse import Namespace
from unittest.mock import patch

import pytest

from scripts.cli_backend import cmd_backend, cmd_backend_get, cmd_backend_list, cmd_backend_set
from scripts.collaboration.backend_config import (
    VALID_BACKENDS,
    _call_counter,
    _user_config_path,
    get_call_count,
    load_backend_config,
    resolve_backend,
    save_backend_config,
)


@pytest.fixture(autouse=True)
def reset_counter():
    """Reset module-level counter between tests."""
    import scripts.collaboration.backend_config as mod
    mod._call_counter = 0
    yield
    mod._call_counter = 0


def _ns(**kwargs) -> Namespace:
    base = {"provider": None, "project": False, "model": None, "backend_command": None}
    base.update(kwargs)
    return Namespace(**base)


# --- backend_config module ---


class TestValidBackends:
    def test_includes_moka(self):
        assert "moka" in VALID_BACKENDS

    def test_includes_openai(self):
        assert "openai" in VALID_BACKENDS

    def test_includes_anthropic(self):
        assert "anthropic" in VALID_BACKENDS

    def test_includes_mock_and_auto(self):
        assert "mock" in VALID_BACKENDS
        assert "auto" in VALID_BACKENDS


class TestSaveLoadConfig:
    """Test save/load round-trip using a tmp HOME."""

    def test_save_and_load_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        path = save_backend_config({"backend": "moka"})
        assert path.endswith("config.yaml")
        cfg = load_backend_config()
        assert cfg["backend"] == "moka"

    def test_save_validates_backend(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with pytest.raises(ValueError):
            save_backend_config({"backend": "invalid-provider"})

    def test_save_requires_backend_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        with pytest.raises(ValueError):
            save_backend_config({"model": "x"})

    def test_save_with_model(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        save_backend_config({"backend": "openai", "model": "gpt-4o"})
        cfg = load_backend_config()
        assert cfg["backend"] == "openai"
        assert cfg["model"] == "gpt-4o"

    def test_load_returns_empty_when_no_file(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        cfg = load_backend_config()
        assert cfg == {}

    def test_save_overwrites_existing_key(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        save_backend_config({"backend": "moka", "model": "moka-x"})
        save_backend_config({"backend": "openai"})  # overwrite backend only
        cfg = load_backend_config()
        assert cfg["backend"] == "openai"
        assert cfg["model"] == "moka-x"  # model preserved


class TestResolveBackend:
    """Test resolve_backend priority order."""

    def test_default_is_auto(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DEVSQUAD_LLM_BACKEND", raising=False)
        assert resolve_backend() == "auto"

    def test_env_var_takes_priority_over_default(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DEVSQUAD_LLM_BACKEND", "mock")
        assert resolve_backend() == "mock"

    def test_user_config_takes_priority_over_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setenv("DEVSQUAD_LLM_BACKEND", "mock")
        save_backend_config({"backend": "moka"})
        assert resolve_backend() == "moka"

    def test_invalid_user_config_falls_back(self, monkeypatch, tmp_path):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DEVSQUAD_LLM_BACKEND", raising=False)
        # Write invalid config
        path = _user_config_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write("backend: invalid-thing\n")
        assert resolve_backend() == "auto"


# --- CLI commands ---


class TestCmdBackendSet:
    """Test cmd_backend_set."""

    def test_set_moka(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        args = _ns(provider="moka", project=False)
        rc = cmd_backend_set(args)
        assert rc == 0
        captured = capsys.readouterr()
        assert "moka" in captured.out.lower()
        cfg = load_backend_config()
        assert cfg["backend"] == "moka"

    def test_set_with_model(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        args = _ns(provider="openai", model="gpt-4o")
        rc = cmd_backend_set(args)
        assert rc == 0
        cfg = load_backend_config()
        assert cfg["backend"] == "openai"
        assert cfg["model"] == "gpt-4o"

    def test_set_invalid_returns_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        args = _ns(provider="invalid-thing")
        rc = cmd_backend_set(args)
        assert rc == 1

    def test_set_increments_counter(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        before = get_call_count()
        cmd_backend_set(_ns(provider="moka"))
        assert get_call_count() == before + 1


class TestCmdBackendGet:
    """Test cmd_backend_get."""

    def test_get_default(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.delenv("DEVSQUAD_LLM_BACKEND", raising=False)
        rc = cmd_backend_get(_ns())
        captured = capsys.readouterr()
        assert rc == 0
        assert "auto" in captured.out

    def test_get_after_set(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        cmd_backend_set(_ns(provider="moka"))
        cmd_backend_get(_ns())
        captured = capsys.readouterr()
        assert "moka" in captured.out


class TestCmdBackendList:
    """Test cmd_backend_list."""

    def test_list_shows_all_backends(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        cmd_backend_list(_ns())
        captured = capsys.readouterr()
        assert "moka" in captured.out
        assert "openai" in captured.out
        assert "anthropic" in captured.out

    def test_list_marks_current(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("HOME", str(tmp_path))
        cmd_backend_set(_ns(provider="moka"))
        cmd_backend_list(_ns())
        captured = capsys.readouterr()
        assert "*" in captured.out  # marker for current


class TestCmdBackendDispatcher:
    """Test cmd_backend top-level dispatcher."""

    def test_dispatches_to_set(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        args = _ns(backend_command="set", provider="moka")
        rc = cmd_backend(args)
        assert rc == 0

    def test_dispatches_to_get(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        args = _ns(backend_command="get")
        rc = cmd_backend(args)
        assert rc == 0

    def test_dispatches_to_list(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        args = _ns(backend_command="list")
        rc = cmd_backend(args)
        assert rc == 0

    def test_unknown_subcommand_returns_error(self, capsys):
        args = _ns(backend_command="invalid")
        rc = cmd_backend(args)
        assert rc == 1


# --- Anti-Ghost ---


class TestBackendConfigAntiGhost:
    def test_counter_increments_on_real_use(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HOME", str(tmp_path))
        cmd_backend_set(_ns(provider="moka"))
        cmd_backend_get(_ns())
        cmd_backend_list(_ns())
        assert get_call_count() >= 3