#!/usr/bin/env python3
"""
DevSquad MCP Server Tests (V3.6.2 → V3.7.0 rewrite)

Comprehensive test coverage for MCP protocol server.
Rewritten to match the closure-based architecture where tool functions
are registered via @mcp.tool() inside create_mcp_server().

Test Categories:
  - Server creation and initialization
  - Tool registration and listing
  - multiagent_dispatch tool functionality
  - multiagent_quick tool functionality
  - multiagent_roles tool functionality
  - multiagent_status tool functionality
  - multiagent_analyze tool functionality
  - Input validation and security
  - Error handling and edge cases
  - Dispatcher lifecycle management

Usage:
    pytest tests/test_mcp_server_v362.py -v --cov=scripts/mcp_server --cov-report=term-missing
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Skip entire module if MCP SDK is not installed (optional dependency)
pytest.importorskip("mcp", reason="MCP SDK not installed. Run: pip install mcp")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_dispatcher():
    """Create a mock MultiAgentDispatcher instance."""
    dispatcher = MagicMock()
    mock_result = MagicMock()
    mock_result.success = True
    mock_result.matched_roles = ["architect", "coder"]
    mock_result.summary = "Task completed successfully"
    mock_result.to_markdown.return_value = "# Task Result\n\nCompleted."
    dispatcher.dispatch.return_value = mock_result

    mock_quick_result = MagicMock()
    mock_quick_result.summary = "Quick analysis done"
    mock_quick_result.to_markdown.return_value = "**Quick Result**\n\nAnalysis complete."
    dispatcher.quick_dispatch.return_value = mock_quick_result

    mock_status = {
        "total_tasks": 10,
        "success_rate": 95.5,
        "active_workers": 3,
    }
    dispatcher.get_status.return_value = mock_status

    return dispatcher


@pytest.fixture
def mcp_server_with_mock(mock_dispatcher):
    """Create an MCP server with a mocked dispatcher.

    Returns (mcp, mock_dispatcher) where mcp is the FastMCP instance.
    Tool functions can be accessed via mcp._tool_manager._tools[name].fn
    """
    with patch.object(
        __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
        "_get_dispatcher",
        return_value=mock_dispatcher,
    ):
        from scripts.mcp_server import create_mcp_server

        mcp = create_mcp_server()
        yield mcp, mock_dispatcher


def _get_tool_fn(mcp, name: str):
    """Helper to get a tool function from the FastMCP instance."""
    return mcp._tool_manager._tools[name].fn


# ---------------------------------------------------------------------------
# Test: DevSquadMCPServer class (still has __init__, _get_dispatcher, shutdown)
# ---------------------------------------------------------------------------

class TestDevSquadMCPServerClass:
    """Test DevSquadMCPServer class."""

    def test_initialization(self):
        """Test server initializes with no dispatcher."""
        from scripts.mcp_server import DevSquadMCPServer

        server = DevSquadMCPServer()
        assert server._dispatcher is None

    def test_get_dispatcher_lazy_init(self, mock_dispatcher):
        """Test lazy initialization of dispatcher."""
        from scripts.mcp_server import DevSquadMCPServer

        with patch("scripts.mcp_server.MultiAgentDispatcher", return_value=mock_dispatcher):
            server = DevSquadMCPServer()
            disp = server._get_dispatcher()

            assert disp == mock_dispatcher
            assert server._dispatcher is not None

    def test_get_dispatcher_caching(self, mock_dispatcher):
        """Test dispatcher is cached after first creation."""
        from scripts.mcp_server import DevSquadMCPServer

        with patch("scripts.mcp_server.MultiAgentDispatcher", return_value=mock_dispatcher) as mock_cls:
            server = DevSquadMCPServer()
            disp1 = server._get_dispatcher()
            disp2 = server._get_dispatcher()

            assert disp1 == disp2
            mock_cls.assert_called_once()

    def test_shutdown_clears_dispatcher(self, mock_dispatcher):
        """Test shutdown clears dispatcher reference."""
        from scripts.mcp_server import DevSquadMCPServer

        server = DevSquadMCPServer()
        server._dispatcher = mock_dispatcher

        server.shutdown()

        assert server._dispatcher is None
        mock_dispatcher.shutdown.assert_called_once()

    def test_shutdown_when_no_dispatcher(self):
        """Test shutdown when no dispatcher exists."""
        from scripts.mcp_server import DevSquadMCPServer

        server = DevSquadMCPServer()
        server.shutdown()  # should not raise


# ---------------------------------------------------------------------------
# Test: create_mcp_server factory function
# ---------------------------------------------------------------------------

class TestCreateMCPServerFunction:
    """Test create_mcp_server factory function."""

    @patch("scripts.mcp_server.MCP_AVAILABLE", False)
    def test_create_mcp_server_unavailable_raises(self):
        """Test creating server when MCP SDK unavailable raises ImportError."""
        from scripts.mcp_server import create_mcp_server

        with pytest.raises(ImportError, match="MCP SDK not installed"):
            create_mcp_server()

    def test_create_mcp_server_returns_fastmcp(self):
        """Test create_mcp_server returns a FastMCP instance."""
        from mcp.server.fastmcp import FastMCP
        from scripts.mcp_server import create_mcp_server

        mcp = create_mcp_server()
        assert isinstance(mcp, FastMCP)

    def test_create_mcp_server_registers_expected_tools(self):
        """Test that create_mcp_server registers all expected tool names."""
        from scripts.mcp_server import create_mcp_server

        mcp = create_mcp_server()
        tool_names = set(mcp._tool_manager._tools.keys())

        expected = {
            "multiagent_dispatch",
            "multiagent_quick",
            "multiagent_roles",
            "multiagent_status",
            "multiagent_analyze",
            "multiagent_shutdown",
            # V3.9-02: Code Knowledge Graph tools
            "codegraph_explore",
            "codegraph_status",
            "codegraph_refresh",
        }
        assert expected == tool_names


# ---------------------------------------------------------------------------
# Test: multiagent_dispatch tool
# ---------------------------------------------------------------------------

class TestMultiagentDispatchTool:
    """Test multiagent_dispatch MCP tool."""

    def test_dispatch_success_markdown_format(self, mcp_server_with_mock):
        """Test dispatch returns markdown format by default."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        result = fn(
            task="Design auth system",
            roles=["architect"],
            mode="auto",
            output_format="markdown",
            dry_run=False,
        )

        assert "Task completed successfully" in result or "#" in result
        mock_disp.dispatch.assert_called_once_with(
            task="Design auth system",
            roles=["architect"],
            mode="auto",
            dry_run=False,
        )

    def test_dispatch_json_format(self, mcp_server_with_mock):
        """Test dispatch returns JSON format when requested."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        result = fn(task="Test task", output_format="json", dry_run=False)

        data = json.loads(result)
        assert data["success"] is True
        assert "summary" in data

    def test_dispatch_compact_format(self, mcp_server_with_mock):
        """Test dispatch returns compact format (summary only)."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        result = fn(task="Test task", output_format="compact", dry_run=False)

        assert result == "Task completed successfully"

    def test_dispatch_dry_run_mode(self, mcp_server_with_mock):
        """Test dispatch with dry_run=True."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        fn(task="Analyze codebase", dry_run=True)

        call_kwargs = mock_disp.dispatch.call_args[1]
        assert call_kwargs["dry_run"] is True

    def test_dispatch_with_roles_list(self, mcp_server_with_mock):
        """Test dispatch accepts custom role list."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        fn(task="Security review", roles=["security", "architect"], mode="consensus")

        call_kwargs = mock_disp.dispatch.call_args[1]
        assert call_kwargs["roles"] == ["security", "architect"]
        assert call_kwargs["mode"] == "consensus"


# ---------------------------------------------------------------------------
# Test: multiagent_quick tool
# ---------------------------------------------------------------------------

class TestMultiagentQuickTool:
    """Test multiagent_quick MCP tool."""

    def test_quick_dispatch_success(self, mcp_server_with_mock):
        """Test quick dispatch executes successfully."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_quick")

        result = fn(task="Quick fix bug", output_format="structured")

        assert "Quick analysis done" in result or "**" in result
        mock_disp.quick_dispatch.assert_called_once()

    def test_quick_dispatch_with_action_items(self, mcp_server_with_mock):
        """Test quick dispatch includes action items when requested."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_quick")

        fn(task="Review PR", include_action_items=True)

        call_kwargs = mock_disp.quick_dispatch.call_args[1]
        assert call_kwargs["include_action_items"] is True

    def test_quick_dispatch_with_timing(self, mcp_server_with_mock):
        """Test quick dispatch includes timing data when requested."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_quick")

        fn(task="Benchmark", include_timing=True)

        call_kwargs = mock_disp.quick_dispatch.call_args[1]
        assert call_kwargs["include_timing"] is True


# ---------------------------------------------------------------------------
# Test: multiagent_roles tool
# ---------------------------------------------------------------------------

class TestMultiagentRolesTool:
    """Test multiagent_roles MCP tool."""

    def test_roles_text_format(self, mcp_server_with_mock):
        """Test roles list returns text format by default."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_roles")

        result = fn(format="text")

        assert isinstance(result, str)
        assert len(result) > 0
        assert "**" in result or "—" in result

    def test_roles_json_format(self, mcp_server_with_mock):
        """Test roles list returns JSON format when requested."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_roles")

        result = fn(format="json")

        data = json.loads(result)
        assert isinstance(data, dict)
        assert len(data) > 0

    def test_roles_contains_expected_entries(self, mcp_server_with_mock):
        """Verify roles list contains expected role entries."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_roles")

        result = fn(format="json")
        data = json.loads(result)

        role_ids = list(data.keys())
        assert len(role_ids) > 0


# ---------------------------------------------------------------------------
# Test: multiagent_status tool
# ---------------------------------------------------------------------------

class TestMultiagentStatusTool:
    """Test multiagent_status MCP tool."""

    def test_status_returns_valid_json(self, mcp_server_with_mock):
        """Test status returns valid JSON string."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_status")

        result = fn()

        data = json.loads(result)
        assert data["name"] == "DevSquad"
        assert data["status"] == "ready"

    def test_status_contains_modules_info(self, mcp_server_with_mock):
        """Test status includes module count information."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_status")

        result = fn()
        data = json.loads(result)

        assert "modules" in data
        assert data["modules"] == 149

    def test_status_contains_features_list(self, mcp_server_with_mock):
        """Test status includes features capability list."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_status")

        result = fn()
        data = json.loads(result)

        assert "features" in data
        assert isinstance(data["features"], dict)
        assert "memory_bridge" in data["features"]

    def test_status_handles_get_status_exception(self, mock_dispatcher):
        """Test status handles get_status exception gracefully."""
        mock_dispatcher.get_status.side_effect = Exception("Internal error")

        with patch.object(
            __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
            "_get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from scripts.mcp_server import create_mcp_server

            mcp = create_mcp_server()
            fn = _get_tool_fn(mcp, "multiagent_status")

            result = fn()
            data = json.loads(result)

            assert data["status"] == "ready"
            assert "error" in data


# ---------------------------------------------------------------------------
# Test: multiagent_analyze tool
# ---------------------------------------------------------------------------

class TestMultiagentAnalyzeTool:
    """Test multiagent_analyze MCP tool."""

    def test_analyze_returns_suggestions(self, mcp_server_with_mock):
        """Test analyze returns role suggestions and complexity info."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_analyze")

        result = fn(task="Build REST API")

        data = json.loads(result)
        assert "task" in data
        assert data["task"] == "Build REST API"
        assert "suggested_roles" in data
        assert "recommended_mode" in data

    def test_analyze_uses_dry_run(self, mcp_server_with_mock):
        """Test analyze uses dry_run=True automatically."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_analyze")

        fn(task="Test task")

        call_kwargs = mock_disp.dispatch.call_args[1]
        assert call_kwargs["dry_run"] is True


# ---------------------------------------------------------------------------
# Test: Input validation and security
# ---------------------------------------------------------------------------

class TestInputValidation:
    """Test input validation and security checks."""

    def test_dispatch_blocks_invalid_task(self, mcp_server_with_mock):
        """Test dispatch blocks invalid/malicious tasks."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        with patch("scripts.mcp_server._validator") as mock_val:
            mock_validation = MagicMock()
            mock_validation.valid = False
            mock_validation.reason = "SQL injection detected"
            mock_val.validate_task.return_value = mock_validation

            result = fn(task="DROP TABLE users;")

            data = json.loads(result)
            assert data["success"] is False
            assert "error" in data

    def test_quick_blocks_invalid_task(self, mcp_server_with_mock):
        """Test quick dispatch blocks invalid tasks."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_quick")

        with patch("scripts.mcp_server._validator") as mock_val:
            mock_validation = MagicMock()
            mock_validation.valid = False
            mock_validation.reason = "XSS detected"
            mock_val.validate_task.return_value = mock_validation

            result = fn(task="<script>alert(1)</script>")

            data = json.loads(result)
            assert data["success"] is False

    def test_analyze_blocks_invalid_task(self, mcp_server_with_mock):
        """Test analyze blocks invalid tasks."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_analyze")

        with patch("scripts.mcp_server._validator") as mock_val:
            mock_validation = MagicMock()
            mock_validation.valid = False
            mock_validation.reason = "Command injection"
            mock_val.validate_task.return_value = mock_validation

            result = fn(task="rm -rf /")

            data = json.loads(result)
            assert "error" in data

    def test_sanitizes_input_before_dispatch(self, mcp_server_with_mock):
        """Test that sanitized input is used after validation."""
        mcp, mock_disp = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_dispatch")

        with patch("scripts.mcp_server._validator") as mock_val:
            mock_validation = MagicMock()
            mock_validation.valid = True
            mock_validation.sanitized_input = "cleaned task description"
            mock_val.validate_task.return_value = mock_validation

            fn(task="original input")

            call_kwargs = mock_disp.dispatch.call_args[1]
            assert call_kwargs["task"] == "cleaned task description"


# ---------------------------------------------------------------------------
# Test: Error handling
# ---------------------------------------------------------------------------

class TestErrorHandling:
    """Test error handling and exception scenarios."""

    def test_dispatch_handles_dispatch_exception(self, mock_dispatcher):
        """Test dispatch handles dispatcher exceptions gracefully."""
        mock_dispatcher.dispatch.side_effect = Exception("Dispatch failed")

        with patch.object(
            __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
            "_get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from scripts.mcp_server import create_mcp_server

            mcp = create_mcp_server()
            fn = _get_tool_fn(mcp, "multiagent_dispatch")

            result = fn(task="Test")

            data = json.loads(result)
            assert data["success"] is False
            assert "error" in data

    def test_quick_handles_exception(self, mock_dispatcher):
        """Test quick dispatch handles exceptions gracefully."""
        mock_dispatcher.quick_dispatch.side_effect = Exception("Quick failed")

        with patch.object(
            __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
            "_get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from scripts.mcp_server import create_mcp_server

            mcp = create_mcp_server()
            fn = _get_tool_fn(mcp, "multiagent_quick")

            result = fn(task="Test")

            data = json.loads(result)
            assert data["success"] is False

    def test_analyze_handles_exception(self, mock_dispatcher):
        """Test analyze handles exceptions gracefully."""
        mock_dispatcher.dispatch.side_effect = Exception("Analysis failed")

        with patch.object(
            __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
            "_get_dispatcher",
            return_value=mock_dispatcher,
        ):
            from scripts.mcp_server import create_mcp_server

            mcp = create_mcp_server()
            fn = _get_tool_fn(mcp, "multiagent_analyze")

            result = fn(task="Test")

            data = json.loads(result)
            assert "error" in data


# ---------------------------------------------------------------------------
# Test: multiagent_shutdown tool
# ---------------------------------------------------------------------------

class TestShutdownTool:
    """Test multiagent_shutdown MCP tool."""

    def test_shutdown_returns_success(self, mcp_server_with_mock):
        """Test shutdown tool returns success status."""
        mcp, _ = mcp_server_with_mock
        fn = _get_tool_fn(mcp, "multiagent_shutdown")

        result = fn()

        data = json.loads(result)
        assert data["status"] == "shutdown_complete"

    def test_shutdown_calls_server_shutdown(self, mock_dispatcher):
        """Test shutdown tool calls DevSquadMCPServer.shutdown()."""
        with patch.object(
            __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
            "shutdown",
        ) as mock_shutdown:
            with patch.object(
                __import__("scripts.mcp_server", fromlist=["DevSquadMCPServer"]).DevSquadMCPServer,
                "_get_dispatcher",
                return_value=mock_dispatcher,
            ):
                from scripts.mcp_server import create_mcp_server

                mcp = create_mcp_server()
                fn = _get_tool_fn(mcp, "multiagent_shutdown")

                fn()

                mock_shutdown.assert_called_once()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
