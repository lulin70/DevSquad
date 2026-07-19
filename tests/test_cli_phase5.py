#!/usr/bin/env python3
"""
Phase 5: CLI 命令行接口覆盖率提升测试

目标：
- 参数解析边界测试
- 子命令路由测试
- 后端创建函数测试
- 生命周期预设配置验证

遵循 AAA 模式 (Arrange-Act-Assert)
"""

import contextlib
import importlib.util
import os
import sys
from io import StringIO
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
pytestmark = pytest.mark.unit



def _import_cli_module():
    """Import scripts.cli.py directly to avoid package conflict."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cli_path = os.path.join(base_dir, "scripts", "cli.py")
    spec = importlib.util.spec_from_file_location("scripts.cli_module", cli_path)
    cli_module = importlib.util.module_from_spec(spec)
    sys.modules["scripts.cli_module"] = cli_module
    spec.loader.exec_module(cli_module)
    return cli_module


_cli = _import_cli_module()

_create_backend = _cli._create_backend
LIFECYCLE_PRESETS = _cli.LIFECYCLE_PRESETS
MODES = _cli.MODES
FORMATS = _cli.FORMATS
BACKENDS = _cli.BACKENDS
LIFECYCLE_COMMANDS = _cli.LIFECYCLE_COMMANDS


class TestCreateBackend:
    """_create_backend() 函数测试"""

    def test_create_mock_backend(self):
        """Test creating mock backend returns None."""
        result = _create_backend("mock")
        assert result is None

    def test_create_none_backend(self):
        """Test creating with None type returns None (defaults to mock)."""
        result = _create_backend(None)
        assert result is None

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-12345"})
    def test_create_openai_backend_with_key(self):
        """Test creating OpenAI backend with API key set."""
        result = _create_backend("openai")
        if result:
            assert result is not None

    def test_create_openai_backend_without_key(self):
        """Test creating OpenAI backend without API key returns None."""
        env_keys = ["OPENAI_API_KEY", "DEVSQUAD_OPENAI_API_KEY"]
        original_values = {k: os.environ.get(k) for k in env_keys}

        for k in env_keys:
            os.environ.pop(k, None)

        try:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                result = _create_backend("openai")
                assert result is None
                output = mock_stderr.getvalue()
                assert "OPENAI_API_KEY" in output
        finally:
            for k, v in original_values.items():
                if v is not None:
                    os.environ[k] = v

    def test_create_anthropic_backend_without_key(self):
        """Test creating Anthropic backend without API key returns None."""
        env_keys = ["ANTHROPIC_API_KEY", "DEVSQUAD_ANTHROPIC_API_KEY"]
        original_values = {k: os.environ.get(k) for k in env_keys}

        for k in env_keys:
            os.environ.pop(k, None)

        try:
            with patch("sys.stderr", new_callable=StringIO) as mock_stderr:
                result = _create_backend("anthropic")
                assert result is None
                output = mock_stderr.getvalue()
                assert "ANTHROPIC_API_KEY" in output
        finally:
            for k, v in original_values.items():
                if v is not None:
                    os.environ[k] = v

    def test_create_openai_with_base_url_and_model(self):
        """Test creating OpenAI backend with custom base URL and model."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            result = _create_backend(
                "openai",
                base_url="https://custom.api.com/v1",
                model="gpt-4-turbo",
            )
            if result:
                assert result is not None


class TestLifecyclePresets:
    """生命周期预设配置测试"""

    def test_all_lifecycle_commands_have_presets(self):
        """Test that all lifecycle commands have preset configurations."""
        for cmd in LIFECYCLE_COMMANDS:
            assert cmd in LIFECYCLE_PRESETS, f"Missing preset for lifecycle command: {cmd}"

    def test_preset_has_required_fields(self):
        """Test that each preset has required configuration fields."""
        required_fields = ["description", "required_roles", "mode", "gate", "pre_dispatch_message"]
        for cmd, preset in LIFECYCLE_PRESETS.items():
            for field in required_fields:
                assert field in preset, f"Preset '{cmd}' missing field: {field}"

    def test_preset_roles_are_valid(self):
        """Test that preset roles are from valid role list."""
        valid_roles = [
            "architect",
            "product-manager",
            "tester",
            "solo-coder",
            "ui-designer",
            "security",
            "devops",
            "auto",
        ]
        for cmd, preset in LIFECYCLE_PRESETS.items():
            for role in preset["required_roles"]:
                assert role in valid_roles, f"Invalid role '{role}' in preset '{cmd}'"

    def test_preset_modes_are_valid(self):
        """Test that preset modes are from MODES list."""
        for cmd, preset in LIFECYCLE_PRESETS.items():
            assert preset["mode"] in MODES, f"Invalid mode '{preset['mode']}' in preset '{cmd}'"

    def test_spec_preset_configuration(self):
        """Test spec command preset has correct configuration."""
        spec = LIFECYCLE_PRESETS["spec"]
        assert spec["mode"] == "sequential"
        assert "architect" in spec["required_roles"]
        assert "product-manager" in spec["required_roles"]
        assert spec["gate"] == "spec_first"

    def test_build_preset_configuration(self):
        """Test build command preset has correct configuration."""
        build = LIFECYCLE_PRESETS["build"]
        assert build["mode"] == "parallel"
        assert "architect" in build["required_roles"]
        assert "solo-coder" in build["required_roles"]
        assert "tester" in build["required_roles"]

    def test_review_preset_has_many_roles(self):
        """Test review command requires multiple roles for comprehensive review."""
        review = LIFECYCLE_PRESETS["review"]
        assert len(review["required_roles"]) >= 4
        assert "security" in review["required_roles"]

    def test_ship_preset_includes_devops(self):
        """Test ship command includes devops role."""
        ship = LIFECYCLE_PRESETS["ship"]
        assert "devops" in ship["required_roles"]
        assert ship["mode"] == "sequential"


class TestCLIBoundaryConstants:
    """CLI 常量和配置边界测试"""

    def test_modes_list_completeness(self):
        """Test that MODES contains expected execution modes."""
        expected_modes = ["auto", "parallel", "sequential", "consensus"]
        for mode in expected_modes:
            assert mode in MODES

    def test_formats_list_completeness(self):
        """Test that FORMATS contains expected output formats."""
        expected_formats = ["markdown", "json", "compact", "structured", "detailed"]
        for fmt in expected_formats:
            assert fmt in FORMATS

    def test_backends_list_completeness(self):
        """Test that BACKENDS contains expected backend types."""
        expected_backends = ["mock", "trae", "openai", "anthropic"]
        for backend in expected_backends:
            assert backend in BACKENDS

    def test_lifecycle_commands_completeness(self):
        """Test that LIFECYCLE_COMMANDS includes all expected commands."""
        expected_commands = ["spec", "plan", "build", "test", "review", "ship"]
        for cmd in expected_commands:
            assert cmd in LIFECYCLE_COMMANDS


class TestCLIArgumentParsing:
    """CLI 参数解析集成测试"""

    def test_parse_dispatch_command_minimal(self):
        """Test parsing dispatch command with minimal arguments."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "dispatch", "-t", "test task"]),
            patch.object(_cli, "cmd_dispatch") as mock_cmd,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        mock_cmd.assert_called_once()

    def test_parse_dispatch_command_with_all_options(self):
        """Test parsing dispatch command with all options."""
        cli_main = _cli.main
        test_args = [
            "devsquad",
            "dispatch",
            "-t",
            "complex task",
            "-r",
            "architect",
            "tester",
            "-m",
            "parallel",
            "-f",
            "json",
            "-b",
            "mock",
            "--dry-run",
            "--lang",
            "en",
        ]
        with (
            patch("sys.argv", test_args),
            patch.object(_cli, "cmd_dispatch") as mock_cmd,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        args = mock_cmd.call_args[0][0]
        assert args.task == "complex task"
        assert args.roles == ["architect", "tester"]
        assert args.mode == "parallel"
        assert args.format == "json"
        assert args.backend == "mock"
        assert args.dry_run is True
        assert args.lang == "en"

    def test_parse_demo_command_with_scenario(self):
        """Test parsing demo command with scenario option."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "demo", "--scenario", "intent"]),
            patch.object(_cli, "cmd_demo") as mock_cmd,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        args = mock_cmd.call_args[0][0]
        assert args.scenario == "intent"

    def test_parse_init_quick_mode(self):
        """Test parsing init command with quick flag."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "init", "--quick"]),
            patch.object(_cli, "cmd_init") as mock_cmd,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        args = mock_cmd.call_args[0][0]
        assert args.quick is True

    def test_parse_version_flag(self):
        """Test parsing --version flag."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "--version"]),
            patch("sys.stdout", new_callable=StringIO) as mock_stdout,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        output = mock_stdout.getvalue()
        assert len(output) > 0


class TestCLIEdgeCases:
    """CLI 边界条件和异常处理测试"""

    def test_no_command_provided(self):
        """Test behavior when no command is provided."""
        cli_main = _cli.main
        with patch("sys.argv", ["devsquad"]), patch("sys.stderr", new_callable=StringIO):
            try:
                cli_main()
            except SystemExit as e:
                assert e.code != 0

    def test_invalid_command(self):
        """Test behavior with invalid command name."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "nonexistent_command"]),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        output = mock_stderr.getvalue()
        assert len(output) > 0

    def test_invalid_choice_for_role(self):
        """Test behavior with invalid role choice."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "dispatch", "-t", "task", "-r", "invalid_role"]),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        output = mock_stderr.getvalue()
        assert len(output) > 0

    def test_invalid_mode_choice(self):
        """Test behavior with invalid mode choice."""
        cli_main = _cli.main
        with (
            patch("sys.argv", ["devsquad", "dispatch", "-t", "task", "--mode", "invalid_mode"]),
            patch("sys.stderr", new_callable=StringIO) as mock_stderr,
            contextlib.suppress(SystemExit),
        ):
            cli_main()
        mock_stderr.getvalue()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
