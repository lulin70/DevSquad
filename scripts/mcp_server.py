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
    6. codegraph_explore      — V3.9-02: Query the code knowledge graph
    7. codegraph_status       — V3.9-02: Get code graph build status/stats
    8. codegraph_refresh      — V3.9-02: Incremental/full rebuild of the graph

Dependencies (optional, graceful fallback):
    pip install mcp             # For MCP protocol support
"""

import json
import logging
import os
import sys
from contextlib import suppress
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

logging.basicConfig(level=logging.WARNING, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("DevSquad-MCP")

try:
    from scripts.collaboration.input_validator import InputValidator

    _validator: InputValidator | None = InputValidator()
except ImportError:
    _validator = None

try:
    from mcp.server.fastmcp import FastMCP

    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    logger.warning("MCP SDK not installed. Run: pip install mcp")

from scripts.collaboration._version import __version__ as DEVSQUAD_VERSION  # noqa: E402
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402
from scripts.collaboration.models import ROLE_REGISTRY  # noqa: E402

# V3.9-02: CodeKnowledgeGraph integration (graceful fallback when unavailable).
try:
    from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph  # noqa: E402

    _CODEGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover — defensive: optional dependency
    _CODEGRAPH_AVAILABLE = False
    CodeKnowledgeGraph = None  # type: ignore[assignment,misc]


def _default_codegraph_db_path() -> Path:
    """Return the default on-disk path for the code knowledge graph database."""
    return Path(os.environ.get("DEVSQUAD_CODEGRAPH_DB", ".devsquad_data/codegraph.db"))


class DevSquadMCPServer:
    """MCP Server wrapper for DevSquad."""

    def __init__(self) -> None:
        self._dispatcher: MultiAgentDispatcher | None = None
        # V3.9-02: lazily-constructed CodeKnowledgeGraph (only when first needed).
        self._code_graph: Any = None
        self._code_graph_db_path: Path = _default_codegraph_db_path()

    def _get_dispatcher(self, **kwargs: Any) -> MultiAgentDispatcher:
        """Lazy-init dispatcher with caching."""
        if self._dispatcher is None:
            self._dispatcher = MultiAgentDispatcher(**kwargs)
        return self._dispatcher

    def _get_code_graph(self) -> Any:
        """Lazy-init the CodeKnowledgeGraph instance.

        Returns None when CodeKnowledgeGraph is not importable. The instance
        is cached so subsequent calls reuse the same SQLite connection.
        """
        if not _CODEGRAPH_AVAILABLE:
            return None
        if self._code_graph is None:
            try:
                self._code_graph_db_path.parent.mkdir(parents=True, exist_ok=True)
                self._code_graph = CodeKnowledgeGraph(self._code_graph_db_path)
            except (OSError, ValueError, RuntimeError) as e:
                logger.warning("CodeKnowledgeGraph init failed: %s", e)
                self._code_graph = None
        return self._code_graph

    def shutdown(self) -> None:
        """Clean up dispatcher and code graph."""
        if self._code_graph is not None:
            with suppress(AttributeError, OSError, RuntimeError):
                self._code_graph.close()
            self._code_graph = None
        if self._dispatcher:
            self._dispatcher.shutdown()
            self._dispatcher = None


def create_mcp_server(host: str = "127.0.0.1", port: int = 8000) -> "FastMCP":
    """Create and configure the MCP server with all tools."""
    if not MCP_AVAILABLE:
        raise ImportError("MCP SDK not installed. Run: pip install mcp")

    mcp = FastMCP("DevSquad", host=host, port=port)
    server = DevSquadMCPServer()

    @mcp.tool()
    def multiagent_dispatch(
        task: str,
        roles: list[str] | None = None,
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
            # MultiAgentDispatcher.dispatch's first parameter is ``task_description``,
            # but the public MCP tool contract (and its tests) pass ``task``. We keep
            # ``task=`` to honor that contract; the resulting mypy call-arg error is
            # suppressed here. (tests/ and scripts/collaboration/ are out of scope,
            # so the dispatcher signature cannot be reconciled here.)
            result = disp.dispatch(  # type: ignore[call-arg]
                task=task,
                roles=roles,
                mode=mode,
                dry_run=dry_run,
            )
            if output_format == "json":
                return json.dumps(
                    {
                        "success": result.success,
                        "matched_roles": getattr(result, "matched_roles", None),
                        "summary": result.summary,
                        "report": result.to_markdown(),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            elif output_format == "compact":
                return result.summary
            return result.to_markdown()
        except Exception as e:
            logger.error("Dispatch error: %s", e, exc_info=True)
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
            return result.to_markdown() if hasattr(result, "to_markdown") else str(result)
        except Exception as e:
            logger.error("Quick dispatch error: %s", e, exc_info=True)
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
            disp.get_status() if hasattr(disp, "get_status") else {}
            return json.dumps(
                {
                    "name": "DevSquad",
                    "version": DEVSQUAD_VERSION,
                    "status": "ready",
                    "modules": 149,
                    "tests": 2861,
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
                },
                ensure_ascii=False,
                indent=2,
            )
        except (AttributeError, RuntimeError) as e:
            logger.error("Status check failed: %s", e, exc_info=True)
            return json.dumps(
                {"name": "DevSquad", "version": DEVSQUAD_VERSION, "status": "error", "error": str(e)}
            )
        except Exception as e:
            logger.error("Unexpected error in status check: %s", e, exc_info=True)
            return json.dumps(
                {"name": "DevSquad", "version": DEVSQUAD_VERSION, "status": "ready", "error": "Internal error occurred"}
            )

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
            return json.dumps(
                {
                    "task": task,
                    "suggested_roles": getattr(result, "matched_roles", []),
                    "summary": result.summary,
                    "complexity": "estimated from task analysis",
                    "recommended_mode": "auto",
                },
                ensure_ascii=False,
                indent=2,
            )
        except (ValueError, RuntimeError, ConnectionError) as e:
            logger.error("Task analysis failed: %s", e, exc_info=True)
            return json.dumps({"error": str(e)}, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error("Unexpected error in task analysis: %s", e, exc_info=True)
            return json.dumps({"error": "Internal error occurred"}, ensure_ascii=False, indent=2)

    @mcp.tool()
    def multiagent_shutdown() -> str:
        """
        Shutdown the DevSquad dispatcher and free resources.
        Call this when done to clean up memory and connections.
        """
        server.shutdown()
        return json.dumps({"status": "shutdown_complete"})

    # ------------------------------------------------------------------
    # V3.9-02: Code Knowledge Graph MCP tools
    # ------------------------------------------------------------------

    @mcp.tool()
    def codegraph_explore(query: str, query_type: str = "symbol") -> str:
        """V3.9-02: Query the persistent code knowledge graph.

        Args:
            query: The query string (symbol name, function name, module path,
                or signature depending on ``query_type``).
            query_type: One of:
                - ``"symbol"`` (default): find symbols by exact name.
                - ``"callers"``: find symbols that call the given function.
                - ``"callees"``: find symbols called by the given function.
                - ``"dependencies"``: find import dependencies of a module.
                - ``"graph"``: BFS call graph from an entry point (max depth 3).
                - ``"similar"``: find symbols with a similar signature.

        Returns:
            JSON string with the query results. When no graph is configured
            (e.g. CodeKnowledgeGraph unavailable or not yet built), returns
            a helpful error message with ``available=false``.
        """
        graph = server._get_code_graph()
        if graph is None:
            return json.dumps(
                {
                    "available": False,
                    "error": (
                        "CodeKnowledgeGraph is not available. Build the graph "
                        "first by calling codegraph_refresh, or set "
                        "DEVSQUAD_CODEGRAPH_DB to a writable path."
                    ),
                    "query": query,
                    "query_type": query_type,
                },
                ensure_ascii=False,
            )

        try:
            q = graph.query()
            if query_type == "symbol":
                results = q.find_symbol(query)
                payload = [r.__dict__ for r in results]
            elif query_type == "callers":
                results = q.find_callers(query)
                payload = [r.__dict__ for r in results]
            elif query_type == "callees":
                results = q.find_callees(query)
                payload = [r.__dict__ for r in results]
            elif query_type == "dependencies":
                results = q.find_dependencies(query)
                payload = [r.__dict__ for r in results]
            elif query_type == "graph":
                payload = q.get_call_graph(query, max_depth=3)
            elif query_type == "similar":
                results = q.find_similar(query)
                payload = [r.__dict__ for r in results]
            else:
                return json.dumps(
                    {
                        "available": True,
                        "error": f"Unknown query_type: {query_type!r}",
                        "valid_types": [
                            "symbol",
                            "callers",
                            "callees",
                            "dependencies",
                            "graph",
                            "similar",
                        ],
                    },
                    ensure_ascii=False,
                )

            return json.dumps(
                {
                    "available": True,
                    "query": query,
                    "query_type": query_type,
                    "count": len(payload) if isinstance(payload, list) else len(payload.get("nodes", [])),
                    "results": payload,
                },
                ensure_ascii=False,
                indent=2,
            )
        except (ValueError, AttributeError, TypeError, RuntimeError) as e:
            logger.error("codegraph_explore failed: %s", e, exc_info=True)
            return json.dumps(
                {"available": True, "error": str(e), "query": query, "query_type": query_type},
                ensure_ascii=False,
            )

    @mcp.tool()
    def codegraph_status() -> str:
        """V3.9-02: Get code knowledge graph build status and statistics.

        Returns:
            JSON with keys: ``built`` (bool), ``symbol_count``, ``edge_count``,
            ``last_update``, ``file_count``. When the graph is unavailable,
            returns ``built=false`` with an explanatory error.
        """
        graph = server._get_code_graph()
        if graph is None:
            return json.dumps(
                {
                    "built": False,
                    "symbol_count": 0,
                    "edge_count": 0,
                    "file_count": 0,
                    "last_update": None,
                    "error": "CodeKnowledgeGraph is not available.",
                },
                ensure_ascii=False,
            )

        try:
            stats = graph.get_stats()
            # Normalize keys from CodeGraphStorage.get_stats().
            symbol_count = int(stats.get("symbols", 0))
            edge_count = int(stats.get("call_edges", 0)) + int(stats.get("dependencies", 0))
            file_count = int(stats.get("files", 0))
            return json.dumps(
                {
                    "built": symbol_count > 0,
                    "symbol_count": symbol_count,
                    "edge_count": edge_count,
                    "file_count": file_count,
                    "last_update": stats.get("last_update"),
                    "raw_stats": stats,
                },
                ensure_ascii=False,
                indent=2,
            )
        except (ValueError, AttributeError, TypeError, RuntimeError) as e:
            logger.error("codegraph_status failed: %s", e, exc_info=True)
            return json.dumps(
                {"built": False, "error": str(e)},
                ensure_ascii=False,
            )

    @mcp.tool()
    def codegraph_refresh(force: bool = False) -> str:
        """V3.9-02: Refresh the code knowledge graph.

        Args:
            force: When True, perform a full rebuild (re-parse every file).
                When False (default), perform an incremental update — only
                re-parse files whose SHA-256 hash has changed.

        Returns:
            JSON with keys: ``updated_files``, ``new_symbols``, ``duration_ms``.
            When the graph is unavailable, returns an error.
        """
        import time as _time

        graph = server._get_code_graph()
        if graph is None:
            return json.dumps(
                {
                    "updated_files": 0,
                    "new_symbols": 0,
                    "duration_ms": 0,
                    "error": "CodeKnowledgeGraph is not available.",
                },
                ensure_ascii=False,
            )

        # Default project root: the DevSquad project directory (parent of scripts/).
        project_root = Path(os.environ.get("DEVSQUAD_CODEGRAPH_ROOT", os.getcwd()))
        start = _time.time()
        try:
            if force:
                # Full rebuild: re-parse every Python file under project_root.
                new_symbols = graph.build_from_project(project_root)
                # Treat every indexed file as "updated" for reporting.
                stats = graph.get_stats()
                updated_files = int(stats.get("files", 0))
            else:
                # Incremental update: only changed files are re-parsed.
                updated_files = graph.update_project(project_root)
                # Symbol count delta is not directly available; report total.
                stats = graph.get_stats()
                new_symbols = int(stats.get("symbols", 0))

            duration_ms = round((_time.time() - start) * 1000.0, 2)
            return json.dumps(
                {
                    "updated_files": updated_files,
                    "new_symbols": new_symbols,
                    "duration_ms": duration_ms,
                    "force": force,
                    "project_root": str(project_root),
                },
                ensure_ascii=False,
                indent=2,
            )
        except (ValueError, AttributeError, TypeError, RuntimeError, OSError) as e:
            logger.error("codegraph_refresh failed: %s", e, exc_info=True)
            return json.dumps(
                {
                    "updated_files": 0,
                    "new_symbols": 0,
                    "duration_ms": round((_time.time() - start) * 1000.0, 2),
                    "error": str(e),
                },
                ensure_ascii=False,
            )

    return mcp


def main() -> None:
    """Start the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(description="DevSquad MCP Server")
    parser.add_argument("--port", "-p", type=int, default=None, help="SSE transport port (default: stdio)")
    parser.add_argument("--host", default="127.0.0.1", help="SSE host (default: 127.0.0.1)")
    args = parser.parse_args()

    if not MCP_AVAILABLE:
        logger.error("MCP SDK required. Install with: pip install mcp")
        sys.exit(1)

    mcp = create_mcp_server(
        host=args.host,
        port=args.port if args.port is not None else 8000,
    )

    if args.port:
        logger.info("Starting SSE server on %s:%s", args.host, args.port)
        mcp.run(transport="sse")
    else:
        logger.info("Starting stdio server")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
