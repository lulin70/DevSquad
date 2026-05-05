"""
DevSquad MCP (Model Context Protocol) Server — For OpenClaw / Claude Code Tool Integration.

This server exposes MultiAgentDispatcher capabilities as MCP tools, enabling
any MCP-compatible AI agent (OpenClaw, Claude Code, Cursor, etc.) to invoke
multi-agent collaboration directly.

Usage:
    python scripts/mcp_server.py          # Start stdio transport (default)
    python scripts/mcp_server.py --port 8080  # Start SSE transport

MCP Tools Exposed:
    1. multiagent_dispatch     — Execute a multi-agent collaboration task
    2. multiagent_quick        — Quick dispatch with format options
    3. multiagent_roles        — List available roles
    4. multiagent_status       — System status and capabilities
    5. multiagent_analyze      — Analyze task intent (dry-run)

Dependencies (optional, graceful fallback):
    pip install mcp             # For MCP protocol support
"""
import json
import sys
import os
import logging
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DevSquad-MCP")

try:
    from scripts.collaboration.input_validator import InputValidator
    _validator = InputValidator()
except ImportError:
    _validator = None

try:
    from mcp.server.fastmcp import FastMCP
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. Run: pip install mcp")

from scripts.collaboration.dispatcher import MultiAgentDispatcher
from scripts.collaboration.permission_guard import PermissionLevel
from scripts.collaboration.models import ROLE_REGISTRY


class DevSquadMCPServer:
    """MCP Server wrapper for DevSquad."""

    def __init__(self):
        self._dispatcher: Optional[MultiAgentDispatcher] = None

    def _get_dispatcher(self, **kwargs) -> MultiAgentDispatcher:
        """Lazy-init dispatcher with caching."""
        if self._dispatcher is None:
            self._dispatcher = MultiAgentDispatcher(**kwargs)
        return self._dispatcher

    def shutdown(self):
        """Clean up dispatcher."""
        if self._dispatcher:
            self._dispatcher.shutdown()
            self._dispatcher = None


def create_mcp_server() -> "FastMCP":
    """Create and configure the MCP server with all tools."""
    if not MCP_AVAILABLE:
        raise ImportError("MCP SDK not installed. Run: pip install mcp")

    mcp = FastMCP("DevSquad")
    server = DevSquadMCPServer()

    @mcp.tool()
    def multiagent_dispatch(
        task: str,
        roles: Optional[List[str]] = None,
        mode: str = "auto",
        output_format: str = "markdown",
        dry_run: bool = False,
    ) -> str:
        """
        Execute a full multi-agent collaboration task.

        Args:
            task: The task description to collaborate on.
            roles: Optional list of roles (arch/pm/sec/test/coder/infra/ui).
                   If omitted, auto-matches based on task intent (supports CN+EN keywords).
            mode: Execution mode — 'auto'(default), 'parallel', 'sequential', or 'consensus'.
            output_format: Output format — 'markdown'(default), 'json', or 'compact'.
            dry_run: If True, only analyze without execution.

        Returns:
            Markdown or JSON formatted collaboration result with findings,
            conflicts resolution, and action items.
        """
        disp = server._get_dispatcher()
        if _validator:
            vresult = _validator.validate_task(task)
            if not vresult.valid:
                return json.dumps({"error": f"Invalid task: {vresult.reason}", "success": False})
            task = vresult.sanitized_input or task
        try:
            result = disp.dispatch(
                task=task,
                roles=roles,
                mode=mode,
                dry_run=dry_run,
            )
            if output_format == "json":
                return json.dumps({
                    "success": result.success,
                    "matched_roles": getattr(result, 'matched_roles', None),
                    "summary": result.summary,
                    "report": result.to_markdown(),
                }, ensure_ascii=False, indent=2)
            elif output_format == "compact":
                return result.summary
            return result.to_markdown()
        except Exception as e:
            logger.error(f"Dispatch error: {e}", exc_info=True)
            return json.dumps({"error": "Internal error occurred", "success": False})

    @mcp.tool()
    def multiagent_quick(
        task: str,
        output_format: str = "structured",
        include_action_items: bool = True,
        include_timing: bool = False,
    ) -> str:
        """
        Quick dispatch with simplified interface and 3 output formats.

        Args:
            task: Task description.
            output_format: 'structured'(default table), 'compact'(one-line), or 'detailed'(full).
            include_action_items: Include H/M/L priority action items.
            include_timing: Include execution timing data.

        Returns:
            Formatted collaboration result optimized for quick reading.
        """
        disp = server._get_dispatcher()
        if _validator:
            vresult = _validator.validate_task(task)
            if not vresult.valid:
                return json.dumps({"error": f"Invalid task: {vresult.reason}", "success": False})
            task = vresult.sanitized_input or task
        try:
            result = disp.quick_dispatch(
                task=task,
                output_format=output_format,
                include_action_items=include_action_items,
                include_timing=include_timing,
            )
            return result.to_markdown() if hasattr(result, 'to_markdown') else str(result)
        except Exception as e:
            logger.error(f"Quick dispatch error: {e}", exc_info=True)
            return json.dumps({"error": "Internal error occurred", "success": False})

    @mcp.tool()
    def multiagent_roles(format: str = "text") -> str:
        """
        List all available agent roles with descriptions.

        Args:
            format: 'text' or 'json'.

        Returns:
            Role list with descriptions showing expertise areas.
        """
        roles = {}
        for rid, rdef in ROLE_REGISTRY.items():
            display_id = rdef.aliases[0] if rdef.aliases else rid
            status_tag = " [planned]" if rdef.status == "planned" else ""
            roles[display_id] = f"{rdef.description}{status_tag}"
        if format == "json":
            return json.dumps(roles, ensure_ascii=False, indent=2)
        lines = [f"**{role}** — {desc}" for role, desc in roles.items()]
        return "\n".join(lines)

    @mcp.tool()
    def multiagent_status() -> str:
        """
        Get system status, version info, and capability summary.

        Returns:
            JSON with version, status, available roles/modes, and module info.
        """
        disp = server._get_dispatcher()
        try:
            stats = disp.get_status() if hasattr(disp, 'get_status') else {}
            return json.dumps({
                "name": "DevSquad",
                "version": "3.4.0-Prod",
                "status": "ready",
                "modules": 27,
                "tests": 129,
                "roles": 7,
                "modes": ["auto", "parallel", "sequential", "consensus"],
                "backends": ["mock", "openai", "anthropic"],
                "languages": ["zh", "en", "ja"],
                "features": {
                    "memory_bridge": True,
                    "mce_adapter": True,
                    "workbuddy_claw": True,
                    "context_compression": True,
                    "permission_guard": True,
                    "skill_learning": True,
                    "streaming": True,
                    "checkpoint": True,
                    "workflow_engine": True,
                    "prompt_injection_detection": True,
                    "i18n": True,
                },
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"name": "DevSquad", "version": "3.4.0-Prod", "status": "ready", "error": "Internal error occurred"})

    @mcp.tool()
    def multiagent_analyze(task: str) -> str:
        """
        Analyze a task's intent and suggest optimal role configuration (dry-run).

        Args:
            task: Task description to analyze.

        Returns:
            Analysis including suggested roles, estimated complexity, and mode recommendation.
        """
        disp = server._get_dispatcher(enable_warmup=False)
        if _validator:
            vresult = _validator.validate_task(task)
            if not vresult.valid:
                return json.dumps({"error": f"Invalid task: {vresult.reason}"})
            task = vresult.sanitized_input or task
        try:
            result = disp.dispatch(task, dry_run=True)
            return json.dumps({
                "task": task,
                "suggested_roles": getattr(result, 'matched_roles', []),
                "summary": result.summary,
                "complexity": "estimated from task analysis",
                "recommended_mode": "auto",
            }, ensure_ascii=False, indent=2)
        except Exception as e:
            return json.dumps({"error": "Internal error occurred"}, ensure_ascii=False, indent=2)

    @mcp.tool()
    def multiagent_shutdown() -> str:
        """
        Shutdown the DevSquad dispatcher and free resources.
        Call this when done to clean up memory and connections.
        """
        server.shutdown()
        return json.dumps({"status": "shutdown_complete"})

    return mcp


def main():
    """Start the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="DevSquad MCP Server")
    parser.add_argument("--port", "-p", type=int, default=None, help="SSE transport port (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="SSE host (default: 127.0.0.1)")
    args = parser.parse_args()

    if not MCP_AVAILABLE:
        print("ERROR: MCP SDK required. Install with: pip install mcp", file=sys.stderr)
        sys.exit(1)

    mcp = create_mcp_server()

    if args.port:
        logger.info(f"Starting SSE server on {args.host}:{args.port}")
        mcp.run(transport="sse", host=args.host, port=args.port)
    else:
        logger.info("Starting stdio server")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
