#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tests for CLI Lifecycle Commands (P0-4).

Spec reference: SPEC_V35_Agent_Skills_Quality_Framework.md Section 6.4
Test plan: P6(TestPlan) for CLI Lifecycle Commands module.
"""

import pytest
import sys
import os
from io import StringIO
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.cli import (
    LIFECYCLE_PRESETS,
    LIFECYCLE_COMMANDS,
    cmd_lifecycle,
    main,
)


class TestLifecyclePresets:
    """Test lifecycle preset definitions."""

    def test_all_six_commands_defined(self):
        assert len(LIFECYCLE_PRESETS) == 6
        expected = ["spec", "plan", "build", "test", "review", "ship"]
        for cmd in expected:
            assert cmd in LIFECYCLE_PRESETS

    def test_spec_preset_has_required_fields(self):
        preset = LIFECYCLE_PRESETS["spec"]
        assert "description" in preset
        assert "required_roles" in preset
        assert "mode" in preset
        assert "gate" in preset
        assert "pre_dispatch_message" in preset

    def test_spec_requires_architect_and_pm(self):
        roles = LIFECYCLE_PRESETS["spec"]["required_roles"]
        assert "architect" in roles
        assert "product-manager" in roles

    def test_plan_requires_architect_and_pm(self):
        roles = LIFECYCLE_PRESETS["plan"]["required_roles"]
        assert "architect" in roles
        assert "product-manager" in roles

    def test_build_requires_three_roles(self):
        roles = LIFECYCLE_PRESETS["build"]["required_roles"]
        assert len(roles) == 3
        assert "architect" in roles
        assert "solo-coder" in roles
        assert "tester" in roles

    def test_test_requires_tester_and_coder(self):
        roles = LIFECYCLE_PRESETS["test"]["required_roles"]
        assert "tester" in roles
        assert "solo-coder" in roles

    def test_review_requires_four_roles(self):
        roles = LIFECYCLE_PRESETS["review"]["required_roles"]
        assert len(roles) == 4
        assert "solo-coder" in roles
        assert "security" in roles
        assert "tester" in roles
        assert "architect" in roles

    def test_ship_requires_devops_security_architect(self):
        roles = LIFECYCLE_PRESETS["ship"]["required_roles"]
        assert "devops" in roles
        assert "security" in roles
        assert "architect" in roles

    def test_spec_mode_is_sequential(self):
        assert LIFECYCLE_PRESETS["spec"]["mode"] == "sequential"

    def test_plan_mode_is_auto(self):
        assert LIFECYCLE_PRESETS["plan"]["mode"] == "auto"

    def test_build_mode_is_parallel(self):
        assert LIFECYCLE_PRESETS["build"]["mode"] == "parallel"

    def test_test_mode_is_consensus(self):
        assert LIFECYCLE_PRESETS["test"]["mode"] == "consensus"

    def test_review_mode_is_consensus(self):
        assert LIFECYCLE_PRESETS["review"]["mode"] == "consensus"

    def test_ship_mode_is_sequential(self):
        assert LIFECYCLE_PRESETS["ship"]["mode"] == "sequential"

    def test_all_gates_defined(self):
        gates = {
            "spec": "spec_first",
            "plan": "task_breakdown_complete",
            "build": "incremental_verification",
            "test": "evidence_required",
            "review": "change_size_limit",
            "ship": "pre_launch_checklist",
        }
        for cmd, expected_gate in gates.items():
            assert LIFECYCLE_PRESETS[cmd]["gate"] == expected_gate


class TestLifecycleCommandsConstant:
    """Test LIFECYCLE_COMMANDS constant."""

    def test_contains_all_six_commands(self):
        assert len(LIFECYCLE_COMMANDS) == 6
        assert "spec" in LIFECYCLE_COMMANDS
        assert "plan" in LIFECYCLE_COMMANDS
        assert "build" in LIFECYCLE_COMMANDS
        assert "test" in LIFECYCLE_COMMANDS
        assert "review" in LIFECYCLE_COMMANDS
        assert "ship" in LIFECYCLE_COMMANDS

    def test_commands_match_presets(self):
        for cmd in LIFECYCLE_COMMANDS:
            assert cmd in LIFECYCLE_PRESETS


class TestCmdLifecycle:
    """Test cmd_lifecycle function."""

    def test_unknown_command_returns_error(self):
        args = MagicMock()
        args.lifecycle_command = "nonexistent"
        args.task = None
        args.task_positional = None

        result = cmd_lifecycle(args)
        assert result == 1

    def test_missing_task_returns_error(self):
        args = MagicMock()
        args.lifecycle_command = "spec"
        args.task = None
        args.task_positional = None

        result = cmd_lifecycle(args)
        assert result == 1

    @patch('scripts.cli.MultiAgentDispatcher')
    def test_spec_command_calls_dispatch(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.summary = "Spec generated successfully"
        mock_result.to_markdown.return_value = "# Spec Report"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        args = MagicMock()
        args.lifecycle_command = "spec"
        args.task = "User authentication system"
        args.task_positional = None
        args.format = "markdown"
        args.backend = "mock"
        args.base_url = None
        args.model = None
        args.dry_run = False
        args.persist_dir = None
        args.no_warmup = False
        args.no_compression = False
        args.stream = False
        args.lang = "auto"
        args.skip_permission = False
        args.no_memory = False
        args.no_skillify = False

        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = cmd_lifecycle(args)
            output = fake_out.getvalue()

        assert result == 0
        assert "SPEC" in output
        assert "architect" in output
        assert "product-manager" in output

    @patch('scripts.cli.MultiAgentDispatcher')
    def test_build_command_uses_correct_roles(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_markdown.return_value = "# Build Report"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        args = MagicMock()
        args.lifecycle_command = "build"
        args.task = "Implement login API"
        args.task_positional = None
        args.format = "markdown"
        args.backend = "mock"
        args.base_url = None
        args.model = None
        args.dry_run = False
        args.persist_dir = None
        args.no_warmup = False
        args.no_compression = False
        args.stream = False
        args.lang = "auto"
        args.skip_permission = False
        args.no_memory = False
        args.no_skillify = False

        with patch('sys.stdout', new=StringIO()):
            result = cmd_lifecycle(args)

        assert result == 0
        call_args = mock_disp.dispatch.call_args
        called_roles = call_args[1]["roles"]
        assert "architect" in called_roles
        assert "solo-coder" in called_roles
        assert "tester" in called_roles

    @patch('scripts.cli.MultiAgentDispatcher')
    def test_ship_command_uses_sequential_mode(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_markdown.return_value = "# Ship Report"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        args = MagicMock()
        args.lifecycle_command = "ship"
        args.task = "Deploy v2.0 to production"
        args.task_positional = None
        args.format = "markdown"
        args.backend = "mock"
        args.base_url = None
        args.model = None
        args.dry_run = False
        args.persist_dir = None
        args.no_warmup = False
        args.no_compression = False
        args.stream = False
        args.lang = "auto"
        args.skip_permission = False
        args.no_memory = False
        args.no_skillify = False

        with patch('sys.stdout', new=StringIO()):
            result = cmd_lifecycle(args)

        assert result == 0
        call_args = mock_disp.dispatch.call_args
        assert call_args[1]["mode"] == "sequential"


class TestCLIIntegration:
    """Test CLI main() integration with lifecycle commands."""

    @patch('sys.argv', ['devsquad', 'spec', '-t', 'Test task', '--dry-run'])
    @patch('scripts.cli.MultiAgentDispatcher')
    def test_main_with_spec_command(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_markdown.return_value = "# Result"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        with patch('sys.stdout', new=StringIO()):
            result = main()

        assert result == 0

    @patch('sys.argv', ['devsquad', 'build', 'Implement feature'])
    @patch('scripts.cli.MultiAgentDispatcher')
    def test_main_with_build_command_positional(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.to_markdown.return_value = "# Result"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        with patch('sys.stdout', new=StringIO()):
            result = main()

        assert result == 0

    @patch('sys.argv', ['devsquad', '--help'])
    def test_main_help_includes_lifecycle_commands(self):
        with pytest.raises(SystemExit) as exc_info:
            with patch('sys.stdout', new=StringIO()) as fake_out:
                main()

        assert exc_info.value.code == 0
        output = fake_out.getvalue()
        assert "spec" in output
        assert "build" in output
        assert "test" in output
        assert "review" in output
        assert "ship" in output


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_task_validation(self):
        args = MagicMock()
        args.lifecycle_command = "test"
        args.task = ""
        args.task_positional = None

        result = cmd_lifecycle(args)
        assert result == 1

    @patch('scripts.cli.MultiAgentDispatcher')
    def test_dispatch_failure_returns_error_code(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.to_markdown.return_value = "# Failed"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        args = MagicMock()
        args.lifecycle_command = "review"
        args.task = "Review code"
        args.task_positional = None
        args.format = "markdown"
        args.backend = "mock"
        args.base_url = None
        args.model = None
        args.dry_run = False
        args.persist_dir = None
        args.no_warmup = False
        args.no_compression = False
        args.stream = False
        args.lang = "auto"
        args.skip_permission = False
        args.no_memory = False
        args.no_skillify = False

        with patch('sys.stdout', new=StringIO()):
            result = cmd_lifecycle(args)

        assert result == 1

    @patch('scripts.cli.MultiAgentDispatcher')
    def test_json_format_output(self, MockDispatcher):
        mock_disp = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.summary = "Test completed"
        mock_result.matched_roles = ["tester", "solo-coder"]
        mock_result.to_markdown.return_value = "# Report"
        mock_disp.dispatch.return_value = mock_result
        MockDispatcher.return_value = mock_disp

        args = MagicMock()
        args.lifecycle_command = "test"
        args.task = "Run tests"
        args.task_positional = None
        args.format = "json"
        args.backend = "mock"
        args.base_url = None
        args.model = None
        args.dry_run = False
        args.persist_dir = None
        args.no_warmup = False
        args.no_compression = False
        args.stream = False
        args.lang = "auto"
        args.skip_permission = False
        args.no_memory = False
        args.no_skillify = False

        import json
        import re
        with patch('sys.stdout', new=StringIO()) as fake_out:
            result = cmd_lifecycle(args)
            output = fake_out.getvalue()

        assert result == 0
        match = re.search(r'\{.*\}', output, re.DOTALL)
        assert match is not None, f"No JSON found in output: {output[:300]}"
        data = json.loads(match.group())
        assert data["lifecycle_command"] == "test"
        assert data["gate"] == "evidence_required"
        assert data["success"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
