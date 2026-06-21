#!/usr/bin/env python3
"""
DevSquad CLI Deep Tests (V3.6.2)

Comprehensive test coverage for CLI entry point and subcommands.

Test Categories:
  - Command-line argument parsing
  - Dispatch command variations
  - Demo command scenarios
  - Init wizard (interactive and quick modes)
  - Status and roles commands
  - Lifecycle commands (spec, plan, build, test, review, ship)
  - Error handling and validation
  - Configuration loading and saving
  - Backend creation utilities

Usage:
    pytest tests/test_cli_deep_v362.py -v --cov=scripts/cli --cov-report=term-missing
"""

import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import importlib.util

spec = importlib.util.spec_from_file_location("cli_module", os.path.join(os.path.dirname(__file__), "..", "scripts", "cli.py"))
cli_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli_module)

LIFECYCLE_PRESETS = cli_module.LIFECYCLE_PRESETS
MODES = cli_module.MODES
VERSION = cli_module.VERSION
_create_backend = cli_module._create_backend
_prompt_choice = cli_module._prompt_choice
_prompt_yes_no = cli_module._prompt_yes_no
_quick_init = cli_module._quick_init
_save_config = cli_module._save_config
cmd_demo = cli_module.cmd_demo
cmd_init = cli_module.cmd_init


class TestCLIModuleImports:
    """Test CLI module imports and constants."""

    def test_version_constant_exists(self):
        """Verify VERSION constant is defined."""
        assert VERSION is not None
        assert isinstance(VERSION, str)
        assert len(VERSION) > 0

    def test_modes_list_contains_expected(self):
        """Verify MODES list contains expected execution modes."""
        assert "auto" in MODES
        assert "parallel" in MODES
        assert "sequential" in MODES
        assert "consensus" in MODES

    def test_lifecycle_presets_complete(self):
        """Verify all lifecycle presets are defined."""
        expected_commands = ["spec", "plan", "build", "test", "review", "ship"]
        for cmd in expected_commands:
            assert cmd in LIFECYCLE_PRESETS, f"Missing lifecycle preset: {cmd}"
            preset = LIFECYCLE_PRESETS[cmd]
            assert "description" in preset
            assert "required_roles" in preset
            assert "mode" in preset
            assert "gate" in preset


class TestCreateBackend:
    """Test backend creation utility function."""

    def test_create_mock_backend(self):
        """Test creating mock backend returns None."""
        result = _create_backend("mock")
        assert result is None

    def test_create_none_backend(self):
        """Test creating None backend type returns None."""
        result = _create_backend(None)
        assert result is None

    @patch.dict(os.environ, {}, clear=True)
    def test_create_openai_missing_key(self):
        """Test OpenAI backend fails gracefully without API key."""
        result = _create_backend("openai")
        assert result is None

    @patch.dict(os.environ, {}, clear=True)
    def test_create_anthropic_missing_key(self):
        """Test Anthropic backend fails gracefully without API key."""
        result = _create_backend("anthropic")
        assert result is None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    @patch("scripts.collaboration.llm_backend.create_backend")
    def test_create_openai_with_key(self, mock_create):
        """Test OpenAI backend creation with valid API key."""
        mock_backend = MagicMock()
        mock_create.return_value = mock_backend

        result = _create_backend("openai")

        assert result == mock_backend
        mock_create.assert_called_once()

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key-67890"})
    @patch("scripts.collaboration.llm_backend.create_backend")
    def test_create_anthropic_with_key(self, mock_create):
        """Test Anthropic backend creation with valid API key."""
        mock_backend = MagicMock()
        mock_create.return_value = mock_backend

        result = _create_backend("anthropic")

        assert result == mock_backend
        mock_create.assert_called_once()


class TestDemoCommand:
    """Test demo command functionality."""

    @patch("scripts.collaboration.intent_workflow_mapper.IntentWorkflowMapper")
    def test_demo_intent_scenario(self, mock_mapper_class):
        """Test demo intent detection scenario."""
        mock_mapper = MagicMock()
        mock_result = MagicMock()
        mock_result.intent_type = "bugfix"
        mock_result.confidence = 0.95
        mock_result.required_roles = ["coder", "tester"]
        mock_result.optional_roles = ["architect"]
        mock_mapper.detect_intent.return_value = mock_result
        mock_mapper_class.return_value = mock_mapper

        args = MagicMock(scenario="intent")
        exit_code = cmd_demo(args)

        assert exit_code == 0
        mock_mapper.detect_intent.assert_called_once()

    @patch("scripts.collaboration.input_validator.InputValidator")
    def test_demo_security_scenario(self, mock_validator_class):
        """Test demo security scanning scenario."""
        mock_validator = MagicMock()
        mock_validation = MagicMock()
        mock_validation.valid = True
        mock_validation.sanitized_input = "safe input"
        mock_validator.validate_task.return_value = mock_validation
        mock_validator_class.return_value = mock_validator

        args = MagicMock(scenario="security")
        exit_code = cmd_demo(args)

        assert exit_code == 0
        assert mock_validator.validate_task.call_count >= 1

    @patch("scripts.cli_dispatch.MultiAgentDispatcher")
    def test_demo_dispatch_scenario(self, mock_dispatcher_class):
        """Test demo dispatch dry-run scenario."""
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.matched_roles = ["architect"]
        mock_result.summary = "Analysis complete"
        mock_dispatcher.dispatch.return_value = mock_result
        mock_dispatcher_class.return_value = mock_dispatcher

        args = MagicMock(scenario="dispatch")
        exit_code = cmd_demo(args)

        assert exit_code == 0
        mock_dispatcher.shutdown.assert_called_once()

    @patch("scripts.cli_dispatch.MultiAgentDispatcher")
    def test_demo_all_scenarios(self, mock_dispatcher_class):
        """Test running all demo scenarios."""
        mock_dispatcher = MagicMock()
        mock_result = MagicMock()
        mock_result.matched_roles = []
        mock_result.summary = "Done"
        mock_dispatcher.dispatch.return_value = mock_result
        mock_dispatcher_class.return_value = mock_dispatcher

        with patch("scripts.collaboration.intent_workflow_mapper.IntentWorkflowMapper") as mock_intent, patch(
            "scripts.collaboration.input_validator.InputValidator"
        ) as mock_security:
            mock_intent_mapper = MagicMock()
            mock_intent_result = MagicMock()
            mock_intent_result.intent_type = "test"
            mock_intent_result.confidence = 0.9
            mock_intent_result.required_roles = []
            mock_intent_result.optional_roles = []
            mock_intent_mapper.detect_intent.return_value = mock_intent_result
            mock_intent.return_value = mock_intent_mapper

            mock_sec_validator = MagicMock()
            mock_sec_val = MagicMock()
            mock_sec_val.valid = True
            mock_sec_val.sanitized_input = "input"
            mock_security.validate_task.return_value = mock_sec_val
            mock_security.return_value = mock_sec_validator

            args = MagicMock(scenario="all")
            exit_code = cmd_demo(args)

            assert exit_code == 0


class TestInitWizard:
    """Test initialization wizard functionality."""

    @patch("scripts.cli_utils._save_config", return_value=True)
    def test_quick_init_success(self, mock_save):
        """Test quick non-interactive initialization succeeds."""
        with patch("sys.stdout", new=StringIO()):
            exit_code = _quick_init()

        assert exit_code == 0
        mock_save.assert_called_once()

    def test_prompt_choice_valid_input(self):
        """Test prompt choice with valid user input."""
        with patch("builtins.input", return_value="2"):
            result = _prompt_choice("Select [1-3]", ["1", "2", "3"], default="1")
            assert result == "2"

    def test_prompt_choice_default_on_empty(self):
        """Test prompt choice returns default when input is empty."""
        with patch("builtins.input", return_value=""):
            result = _prompt_choice("Select [1-3]", ["1", "2", "3"], default="1")
            assert result == "1"

    def test_prompt_choice_invalid_then_valid(self):
        """Test prompt choice rejects invalid then accepts valid input."""
        with patch("builtins.input", side_effect=["invalid", "3"]):
            result = _prompt_choice("Select [1-3]", ["1", "2", "3"])
            assert result == "3"

    def test_prompt_yes_no_true_response(self):
        """Test yes/no prompt with 'y' response."""
        with patch("builtins.input", return_value="y"):
            result = _prompt_yes_no("Continue?")
            assert result is True

    def test_prompt_yes_no_false_response(self):
        """Test yes/no prompt with 'n' response."""
        with patch("builtins.input", return_value="n"):
            result = _prompt_yes_no("Continue?")
            assert result is False

    def test_prompt_yes_no_default_on_empty(self):
        """Test yes/no prompt returns default when empty."""
        with patch("builtins.input", return_value=""):
            result = _prompt_yes_no("Continue?", default=False)
            assert result is False

    def test_prompt_yes_no_variations(self):
        """Test yes/no prompt accepts various true/false formats."""
        true_values = ["yes", "Y", "1", "true", "True"]
        false_values = ["no", "N", "0", "false", "False"]

        for val in true_values:
            with patch("builtins.input", return_value=val):
                assert _prompt_yes_no("Continue?") is True, f"Failed for: {val}"

        for val in false_values:
            with patch("builtins.input", return_value=val):
                assert _prompt_yes_no("Continue?") is False, f"Failed for: {val}"


class TestSaveConfig:
    """Test configuration saving functionality."""

    def test_save_config_creates_yaml_file(self):
        """Test saving config creates valid YAML file."""
        config = {
            "project_type": "web-api",
            "llm_backend": "mock",
            "default_roles": ["architect"],
            "language": "en",
            "features": {"warmup": True, "compression": True},
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            temp_path = f.name

        try:
            result = _save_config(config, temp_path)
            assert result is True
            assert os.path.exists(temp_path)

            with open(temp_path, "r") as f:
                content = f.read()
                assert "project_type" in content
                assert "web-api" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)

    def test_save_config_symlink_rejected(self):
        """Test saving config to symlink path is rejected."""
        config = {"project_type": "test"}

        with tempfile.NamedTemporaryFile(suffix=".link", delete=True) as f:
            temp_path = f.name

        try:
            os.symlink("/tmp", temp_path)
            result = _save_config(config, temp_path)
            assert result is False
        finally:
            if os.path.islink(temp_path):
                os.unlink(temp_path)
            elif os.path.exists(temp_path):
                os.unlink(temp_path)


class TestLifecyclePresets:
    """Test lifecycle command presets configuration."""

    def test_spec_preset_requires_architect_and_pm(self):
        """Verify spec preset requires architect and product-manager."""
        spec = LIFECYCLE_PRESETS["spec"]
        assert "architect" in spec["required_roles"]
        assert "product-manager" in spec["required_roles"]

    def test_build_preset_uses_parallel_mode(self):
        """Verify build preset uses parallel execution mode."""
        build = LIFECYCLE_PRESETS["build"]
        assert build["mode"] == "parallel"

    def test_test_preset_uses_consensus_mode(self):
        """Verify test preset uses consensus mode."""
        test = LIFECYCLE_PRESETS["test"]
        assert test["mode"] == "consensus"

    def test_review_preset_includes_security_role(self):
        """Verify review preset includes security role."""
        review = LIFECYCLE_PRESETS["review"]
        assert "security" in review["required_roles"]

    def test_ship_preset_includes_devops(self):
        """Verify ship preset includes devops role."""
        ship = LIFECYCLE_PRESETS["ship"]
        assert "devops" in ship["required_roles"]

    def test_all_presets_have_pre_dispatch_message(self):
        """Verify all presets have pre-dispatch message."""
        for cmd, preset in LIFECYCLE_PRESETS.items():
            assert "pre_dispatch_message" in preset, f"Missing pre_dispatch_message for {cmd}"
            assert len(preset["pre_dispatch_message"]) > 0


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_prompt_choice_eof_returns_default(self):
        """Test prompt choice handles EOF by returning default."""
        with patch("builtins.input", side_effect=EOFError):
            result = _prompt_choice("Select", ["1", "2"], default="2")
            assert result == "2"

    def test_prompt_choice_keyboard_interrupt_exits(self):
        """Test prompt choice handles keyboard interrupt."""
        with patch("builtins.input", side_effect=KeyboardInterrupt), pytest.raises(SystemExit):
            _prompt_choice("Select", ["1", "2"])

    def test_prompt_yes_no_eof_returns_default(self):
        """Test yes/no prompt handles EOF by returning default."""
        with patch("builtins.input", side_effect=EOFError):
            result = _prompt_yes_no("Continue?", default=True)
            assert result is True

    def test_prompt_yes_no_keyboard_interrupt_exits(self):
        """Test yes/no prompt handles keyboard interrupt."""
        with patch("builtins.input", side_effect=KeyboardInterrupt), pytest.raises(SystemExit):
            _prompt_yes_no("Continue?")


class TestConfigurationEdgeCases:
    """Test configuration edge cases and boundary conditions."""

    def test_save_config_to_nonexistent_directory(self):
        """Test saving config to nonexistent directory path."""
        config = {"project_type": "test"}
        nonexistent_path = "/nonexistent/directory/path/config.yaml"

        result = _save_config(config, nonexistent_path)
        assert result is False

    def test_lifecycle_preset_descriptions_are_strings(self):
        """Verify all lifecycle descriptions are non-empty strings."""
        for cmd, preset in LIFECYCLE_PRESETS.items():
            assert isinstance(preset["description"], str)
            assert len(preset["description"]) > 0

    def test_lifecycle_preset_roles_are_lists(self):
        """Verify all lifecycle required_roles are lists."""
        for cmd, preset in LIFECYCLE_PRESETS.items():
            assert isinstance(preset["required_roles"], list)
            assert len(preset["required_roles"]) > 0


class TestBackendCreationEdgeCases:
    """Test backend creation edge cases."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}, clear=False)
    def test_openai_env_vars_fallback(self):
        """Test OpenAI backend uses environment variable fallbacks."""
        with patch("scripts.collaboration.llm_backend.create_backend") as mock_create:
            mock_create.return_value = MagicMock()
            result = _create_backend("openai", base_url="https://custom.api.com", model="gpt-4-turbo")

            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("base_url") == "https://custom.api.com"
            assert call_kwargs.get("model") == "gpt-4-turbo"

    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}, clear=False)
    def test_anthropic_custom_model(self):
        """Test Anthropic backend accepts custom model parameter."""
        with patch("scripts.collaboration.llm_backend.create_backend") as mock_create:
            mock_create.return_value = MagicMock()
            result = _create_backend("anthropic", model="claude-3-opus")

            call_kwargs = mock_create.call_args[1]
            assert call_kwargs.get("model") == "claude-3-opus"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
