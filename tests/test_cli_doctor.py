"""Tests for devsquad doctor CLI (V4.5.2 P12.1.4)."""

from __future__ import annotations

import json
import os
from argparse import Namespace
from unittest.mock import patch

from scripts.cli_doctor import (
    PROVIDERS,
    ProviderReport,
    _check_connectivity,
    _is_configured,
    check_command_vocabulary,
    cmd_doctor,
    diagnose_all,
    diagnose_provider,
    format_command_section,
    format_json,
    format_text,
)


def _ns(provider: str = "all", fmt: str = "text", timeout: float = 5.0) -> Namespace:
    return Namespace(provider=provider, format=fmt, timeout=timeout)


class TestProvidersRegistry:
    """Test PROVIDERS configuration."""

    def test_has_moka_openai_anthropic(self):
        assert "moka" in PROVIDERS
        assert "openai" in PROVIDERS
        assert "anthropic" in PROVIDERS

    def test_provider_schema(self):
        for name, cfg in PROVIDERS.items():  # noqa: B007
            assert "api_key_env" in cfg
            assert "base_url_env" in cfg
            assert "default_base_url" in cfg
            assert "fix_hint_unconfigured" in cfg

    def test_moka_base_url(self):
        assert PROVIDERS["moka"]["default_base_url"] == "https://api.moka-ai.com/v1"


class TestIsConfigured:
    """Test _is_configured helper."""

    def setup_method(self):
        for env in ("MOKA_API_KEY", "DEVSQUAD_OPENAI_API_KEY", "DEVSQUAD_ANTHROPIC_API_KEY"):
            os.environ.pop(env, None)

    def test_unconfigured_when_env_missing(self):
        assert _is_configured("moka") is False

    def test_configured_when_env_set(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": "test-key"}):
            assert _is_configured("moka") is True

    def test_unconfigured_with_empty_string(self):
        with patch.dict(os.environ, {"MOKA_API_KEY": ""}):
            assert _is_configured("moka") is False

    def test_unknown_provider(self):
        assert _is_configured("nonexistent") is False


class TestDiagnoseProvider:
    """Test diagnose_provider function."""

    def setup_method(self):
        for env in ("MOKA_API_KEY", "DEVSQUAD_OPENAI_API_KEY", "DEVSQUAD_ANTHROPIC_API_KEY"):
            os.environ.pop(env, None)

    def test_unconfigured_returns_fix_hint(self):
        report = diagnose_provider("moka")
        assert report.configured is False
        assert report.reachable is False
        assert report.fix_hint is not None
        assert "MOKA_API_KEY" in report.fix_hint

    def test_unknown_provider(self):
        report = diagnose_provider("nonexistent")
        assert report.configured is False
        assert "Unknown provider" in report.error

    @patch("scripts.cli_doctor._check_connectivity")
    def test_configured_reachable(self, mock_check):
        with patch.dict(os.environ, {"MOKA_API_KEY": "test-key"}):
            mock_check.return_value = (True, 123.45, ["moka-gpt-5.5"], None)
            report = diagnose_provider("moka")
        assert report.configured is True
        assert report.reachable is True
        assert report.latency_ms == 123.45
        assert "moka-gpt-5.5" in report.models

    @patch("scripts.cli_doctor._check_connectivity")
    def test_configured_unreachable(self, mock_check):
        with patch.dict(os.environ, {"MOKA_API_KEY": "test-key"}):
            mock_check.return_value = (False, 5000.0, [], "Timeout")
            report = diagnose_provider("moka")
        assert report.configured is True
        assert report.reachable is False
        assert report.error == "Timeout"


class TestDiagnoseAll:
    """Test diagnose_all function."""

    def test_returns_all_providers(self):
        reports = diagnose_all(timeout=0.1)  # quick timeout
        # May have reachable=True if API is up; otherwise False
        providers = {r.provider for r in reports}
        assert providers == {"moka", "openai", "anthropic"}


class TestCheckConnectivity:
    """Test _check_connectivity HTTP probe."""

    @patch("urllib.request.urlopen")
    def test_successful_response(self, mock_urlopen):
        from unittest.mock import MagicMock

        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"data": [{"id": "model-1"}]}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = lambda s, *a: None  # noqa: ARG005
        mock_urlopen.return_value = mock_resp

        with patch.dict(os.environ, {"MOKA_API_KEY": "k"}):
            reachable, latency, models, error = _check_connectivity("moka")
        assert reachable is True
        assert error is None
        assert "model-1" in models


class TestProviderReportDataclass:
    """Test ProviderReport serialization."""

    def test_to_dict(self):
        r = ProviderReport(
            provider="moka",
            configured=True,
            reachable=True,
            latency_ms=100.0,
            models=["m1"],
        )
        d = r.to_dict()
        assert d["provider"] == "moka"
        assert d["configured"] is True
        assert d["latency_ms"] == 100.0
        assert d["models"] == ["m1"]


class TestFormatText:
    """Test text formatter."""

    def test_format_includes_provider(self):
        reports = [ProviderReport("moka", True, True, 100.0, ["m1"])]
        out = format_text(reports)
        assert "[MOKA]" in out
        assert "100ms" in out or "100" in out

    def test_format_includes_unconfigured_marker(self):
        reports = [ProviderReport("moka", False, False, error="not configured", fix_hint="Set MOKA_API_KEY")]
        out = format_text(reports)
        assert "NOT configured" in out
        assert "Set MOKA_API_KEY" in out

    def test_format_includes_header(self):
        out = format_text([])
        assert "DevSquad Doctor" in out


class TestFormatJson:
    """Test JSON formatter."""

    def test_format_is_valid_json(self):
        reports = [ProviderReport("moka", True, True, 50.0, ["m1"])]
        out = format_json(reports)
        import json

        parsed = json.loads(out)
        assert parsed["version"] == "V4.5.2"
        assert len(parsed["reports"]) == 1


class TestCmdDoctor:
    """Test CLI command entry point."""

    def test_all_providers_text(self, capsys):
        rc = cmd_doctor(_ns("all", "text", timeout=0.1))  # noqa: F841
        captured = capsys.readouterr()
        assert "DevSquad Doctor" in captured.out

    def test_all_providers_json(self, capsys):
        rc = cmd_doctor(_ns("all", "json", timeout=0.1))  # noqa: F841
        captured = capsys.readouterr()
        import json

        parsed = json.loads(captured.out)
        assert parsed["version"] == "V4.5.2"

    @patch("scripts.cli_doctor.diagnose_provider")
    def test_single_provider(self, mock_diag, capsys):
        mock_diag.return_value = ProviderReport("moka", True, True, 50.0, ["m1"])
        rc = cmd_doctor(_ns("moka", "text"))  # noqa: F841
        captured = capsys.readouterr()
        assert "[MOKA]" in captured.out
        mock_diag.assert_called_once_with("moka", 5.0)

    @patch("scripts.cli_doctor.diagnose_provider")
    def test_unreachable_returns_exit_1(self, mock_diag, capsys):
        mock_diag.return_value = ProviderReport("moka", True, False, error="connection failed")
        rc = cmd_doctor(_ns("moka", "text"))
        assert rc == 1

    @patch("scripts.cli_doctor.diagnose_provider")
    def test_unconfigured_returns_exit_0(self, mock_diag, capsys):
        mock_diag.return_value = ProviderReport("moka", False, False, fix_hint="Set MOKA_API_KEY")
        rc = cmd_doctor(_ns("moka", "text"))
        assert rc == 0


class TestCommandVocabulary:
    """Test check_command_vocabulary (V4.8.0 P1-E1 wiring)."""

    def test_registered_top_level(self):
        check = check_command_vocabulary("status")
        assert check["registered"] is True
        assert check["registered_where"] == "top-level"
        assert check["aligned"] is False
        assert check["suggested_alias"] == "show"

    def test_registered_normalizes_case_and_space(self):
        check = check_command_vocabulary("  STATUS ")
        assert check["registered"] is True
        assert check["normalized"] == "status"

    def test_typo_close_match(self):
        check = check_command_vocabulary("sesions")
        assert check["registered"] is False
        assert check["close_matches"][0]["command"] == "sessions"
        assert check["close_matches"][0]["where"] == "top-level"

    def test_subcommand_typo_located(self):
        check = check_command_vocabulary("lst")
        assert check["registered"] is False
        best = check["close_matches"][0]
        assert best["command"] == "list"
        assert "sessions" in best["where"]

    def test_garbage_no_matches(self):
        check = check_command_vocabulary("zzqqxy")
        assert check["registered"] is False
        assert check["close_matches"] == []
        assert "no similar command" in check["hint"]

    def test_aligned_command(self):
        check = check_command_vocabulary("review")
        assert check["registered"] is True
        assert check["aligned"] is True
        assert check["suggested_alias"] is None

    def test_hint_registered(self):
        check = check_command_vocabulary("status")
        assert "devsquad status --help" in check["hint"]

    def test_hint_typo(self):
        check = check_command_vocabulary("sesions")
        assert "sessions" in check["hint"]


class TestFormatCommandSection:
    """Test format_command_section display rules."""

    def test_registered_unknown_category_omitted(self):
        check = check_command_vocabulary("status")
        text = format_command_section(check)
        assert "Category:" not in text
        assert "Alias hint:" in text

    def test_unregistered_shows_closest(self):
        check = check_command_vocabulary("sesions")
        text = format_command_section(check)
        assert "✗ not a DevSquad command" in text
        assert "sessions" in text
        assert "unknown category" not in text


class TestCmdDoctorCommandFlag:
    """Test cmd_doctor with the --command (command_word) flag."""

    @patch("scripts.cli_doctor.diagnose_provider")
    def test_text_output_contains_section(self, mock_diag, capsys):
        mock_diag.return_value = ProviderReport("moka", False, False, fix_hint="Set MOKA_API_KEY")
        ns = Namespace(provider="moka", format="text", timeout=5.0, command_word="sesions")
        rc = cmd_doctor(ns)
        assert rc == 0
        out = capsys.readouterr().out
        assert "[COMMAND VOCABULARY]" in out
        assert "sessions" in out

    @patch("scripts.cli_doctor.diagnose_provider")
    def test_json_output_has_key(self, mock_diag, capsys):
        mock_diag.return_value = ProviderReport("moka", False, False, fix_hint="Set MOKA_API_KEY")
        ns = Namespace(provider="moka", format="json", timeout=5.0, command_word="status")
        rc = cmd_doctor(ns)
        assert rc == 0
        data = json.loads(capsys.readouterr().out)
        assert data["command_vocabulary"]["registered"] is True

    @patch("scripts.cli_doctor.diagnose_provider")
    def test_without_command_word_no_section(self, mock_diag, capsys):
        mock_diag.return_value = ProviderReport("moka", False, False, fix_hint="Set MOKA_API_KEY")
        ns = Namespace(provider="moka", format="text", timeout=5.0, command_word=None)
        rc = cmd_doctor(ns)
        assert rc == 0
        assert "[COMMAND VOCABULARY]" not in capsys.readouterr().out
