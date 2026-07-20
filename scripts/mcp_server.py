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

import importlib.util
import json
import logging
import os
import sys
from contextlib import suppress
from dataclasses import dataclass
from enum import IntEnum
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
from scripts.collaboration.dispatch_rbac import DispatchRBAC, PermissionResult  # noqa: E402
from scripts.collaboration.dispatcher import MultiAgentDispatcher  # noqa: E402
from scripts.collaboration.models import ROLE_REGISTRY  # noqa: E402

# ------------------------------------------------------------------
# V4.1.1: MCP Permission Control (Dimension 1) — tool permission levels
# ------------------------------------------------------------------


class MCPPermissionLevel(IntEnum):
    """Permission level required to invoke an MCP tool.

    Levels are ordered: READ_ONLY < WRITE < ADMIN. A caller's level must
    be >= the tool's required level to be permitted.
    """

    READ_ONLY = 0
    WRITE = 1
    ADMIN = 2


# Mapping from MCP tool name → minimum permission level required.
# Unknown tools default to ADMIN (fail-closed).
MCP_TOOL_PERMISSIONS: dict[str, MCPPermissionLevel] = {
    "multiagent_dispatch": MCPPermissionLevel.WRITE,
    "multiagent_quick": MCPPermissionLevel.WRITE,
    "multiagent_roles": MCPPermissionLevel.READ_ONLY,
    "multiagent_status": MCPPermissionLevel.READ_ONLY,
    "multiagent_analyze": MCPPermissionLevel.READ_ONLY,
    "multiagent_shutdown": MCPPermissionLevel.ADMIN,
    "codegraph_explore": MCPPermissionLevel.READ_ONLY,
    "codegraph_status": MCPPermissionLevel.READ_ONLY,
    "codegraph_refresh": MCPPermissionLevel.WRITE,
}


# Mapping from user role string → permission level.
# Aligns with DispatchRBAC roles (admin / operator / viewer).
MCP_ROLE_LEVELS: dict[str, MCPPermissionLevel] = {
    "admin": MCPPermissionLevel.ADMIN,
    "operator": MCPPermissionLevel.WRITE,
    "viewer": MCPPermissionLevel.READ_ONLY,
}


# Tools that trigger dispatch operations and require RBAC checks in
# addition to the permission-level check (Dimension 2).
_RBAC_GUARDED_TOOLS: frozenset[str] = frozenset(
    {"multiagent_dispatch", "multiagent_quick"}
)


@dataclass
class MCPPermissionResult:
    """Result of an MCP tool permission check.

    Attributes
    ----------
    allowed:
        True if the caller is permitted to invoke the tool.
    reason:
        Human-readable explanation of the decision.
    tool_name:
        The requested tool name.
    required_level:
        The permission level required for the tool.
    user_level:
        The caller's permission level (None if undeterminable).
    """

    allowed: bool
    reason: str
    tool_name: str
    required_level: MCPPermissionLevel
    user_level: MCPPermissionLevel | None

# V3.9-02: CodeKnowledgeGraph integration (graceful fallback when unavailable).
_CODEGRAPH_AVAILABLE = importlib.util.find_spec("scripts.collaboration.code_knowledge_graph") is not None

if _CODEGRAPH_AVAILABLE:
    from scripts.collaboration.code_knowledge_graph import CodeKnowledgeGraph  # noqa: E402
else:
    CodeKnowledgeGraph = None  # type: ignore[assignment, misc]


def _default_codegraph_db_path() -> Path:
    """Return the default on-disk path for the code knowledge graph database."""
    return Path(os.environ.get("DEVSQUAD_CODEGRAPH_DB", ".devsquad_data/codegraph.db"))


class DevSquadMCPServer:
    """MCP Server wrapper for DevSquad."""

    def __init__(
        self,
        enable_permission_check: bool = True,
        auth_manager: Any | None = None,
        rbac: DispatchRBAC | None = None,
    ) -> None:
        """Initialize the MCP server wrapper.

        Parameters
        ----------
        enable_permission_check:
            When True (default, production-safe), every tool invocation is
            gated by :meth:`_check_mcp_permission` and, for dispatch tools,
            :meth:`_check_rbac_permission`. When False, permission checks
            are skipped (development mode — insecure).
        auth_manager:
            Optional AuthManager instance. When provided, the RBAC engine
            uses it to look up user roles. When None, the caller's role is
            read from the ``DEV_SQUAD_MCP_USER_ROLE`` environment variable.
        rbac:
            Optional pre-configured :class:`DispatchRBAC` instance. When
            None, a default DispatchRBAC is created (open mode when no
            auth_manager, fail-closed when auth_manager is provided).
        """
        self._dispatcher: MultiAgentDispatcher | None = None
        # V3.9-02: lazily-constructed CodeKnowledgeGraph (only when first needed).
        self._code_graph: Any = None
        self._code_graph_db_path: Path = _default_codegraph_db_path()
        # V4.1.1: Permission control state (Dimensions 1 & 2).
        self._enable_permission_check = enable_permission_check
        self._auth_manager = auth_manager
        if rbac is not None:
            self._rbac: DispatchRBAC = rbac
        elif auth_manager is not None:
            self._rbac = DispatchRBAC(auth_manager=auth_manager, fail_closed=True)
        else:
            self._rbac = DispatchRBAC(fail_closed=False)

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

    # ------------------------------------------------------------------
    # V4.1.1: Permission control (Dimension 1) + RBAC (Dimension 2)
    # ------------------------------------------------------------------

    def _resolve_user_context(self) -> dict[str, str] | None:
        """Resolve the caller's user context for permission checks.

        The user role is read from the ``DEV_SQUAD_MCP_USER_ROLE``
        environment variable (one of ``admin`` / ``operator`` / ``viewer``).
        The user ID is read from ``DEV_SQUAD_MCP_USER_ID`` (defaults to
        ``"mcp_user"``).

        Returns
        -------
        dict | None
            A dict with ``role`` and ``user_id`` keys, or None if the role
            cannot be determined (fail-closed: callers will be denied).
        """
        role = os.environ.get("DEV_SQUAD_MCP_USER_ROLE")
        if not role:
            return None
        user_id = os.environ.get("DEV_SQUAD_MCP_USER_ID", "mcp_user")
        return {"role": role, "user_id": user_id}

    def _check_mcp_permission(
        self,
        tool_name: str,
        user_context: dict[str, str] | None,
    ) -> MCPPermissionResult:
        """Check whether the caller may invoke ``tool_name`` (Dimension 1).

        Implements fail-closed semantics:
        - If ``user_context`` is None → DENY (no caller identity).
        - If the caller's role is unknown → DENY.
        - If the tool is not in the permission map → DENY (unknown tools
          require ADMIN, and an unknown caller cannot have ADMIN).
        - If the caller's level < tool's required level → DENY.
        - Otherwise → ALLOW.

        Parameters
        ----------
        tool_name:
            The MCP tool name being invoked.
        user_context:
            The caller's context dict (``role`` + ``user_id``), or None.

        Returns
        -------
        MCPPermissionResult
            The permission decision with reason.
        """
        # Unknown tools default to ADMIN (fail-closed).
        required = MCP_TOOL_PERMISSIONS.get(tool_name, MCPPermissionLevel.ADMIN)

        # Fail-closed: no user context → deny.
        if user_context is None:
            return MCPPermissionResult(
                allowed=False,
                reason="No user context (fail-closed): caller identity unknown",
                tool_name=tool_name,
                required_level=required,
                user_level=None,
            )

        role = user_context.get("role")
        if not role:
            return MCPPermissionResult(
                allowed=False,
                reason="No role in user context (fail-closed)",
                tool_name=tool_name,
                required_level=required,
                user_level=None,
            )

        user_level = MCP_ROLE_LEVELS.get(role)
        if user_level is None:
            return MCPPermissionResult(
                allowed=False,
                reason=f"Unknown role '{role}' (fail-closed)",
                tool_name=tool_name,
                required_level=required,
                user_level=None,
            )

        if user_level >= required:
            return MCPPermissionResult(
                allowed=True,
                reason=f"Role '{role}' (level={user_level.name}) permits {tool_name} (required={required.name})",
                tool_name=tool_name,
                required_level=required,
                user_level=user_level,
            )

        return MCPPermissionResult(
            allowed=False,
            reason=(
                f"Role '{role}' (level={user_level.name}) insufficient for "
                f"{tool_name} (required={required.name})"
            ),
            tool_name=tool_name,
            required_level=required,
            user_level=user_level,
        )

    def _check_rbac_permission(
        self,
        user_context: dict[str, str] | None,
        roles: list[str],
        mode: str,
    ) -> PermissionResult:
        """Check RBAC permission for a dispatch operation (Dimension 2).

        Delegates to the :class:`DispatchRBAC` engine. When no
        ``auth_manager`` is configured, RBAC runs in open mode (allows all
        dispatch roles/modes) — the MCP permission-level check (Dimension 1)
        is still the primary gate. When ``auth_manager`` IS configured, RBAC
        enforces the full role/mode permission matrix.

        Parameters
        ----------
        user_context:
            The caller's context dict, or None.
        roles:
            The dispatch roles requested.
        mode:
            The dispatch mode requested.

        Returns
        -------
        PermissionResult
            The RBAC decision.
        """
        user_id = (user_context or {}).get("user_id", "mcp_user")
        return self._rbac.check_dispatch_permission(user_id, list(roles), mode)

    def _enforce_tool_permission(
        self,
        tool_name: str,
        roles: list[str] | None = None,
        mode: str | None = None,
    ) -> str | None:
        """Enforce permission checks before tool execution.

        This combines Dimension 1 (permission level) and Dimension 2 (RBAC)
        checks. It should be called at the start of every tool function.

        Parameters
        ----------
        tool_name:
            The MCP tool name being invoked.
        roles:
            The dispatch roles (for RBAC-guarded tools only).
        mode:
            The dispatch mode (for RBAC-guarded tools only).

        Returns
        -------
        str | None
            A JSON denial string if the call is denied, or None if allowed.
            When permission checking is disabled, always returns None.
        """
        if not self._enable_permission_check:
            return None

        user_ctx = self._resolve_user_context()

        # Dimension 1: permission-level check.
        perm = self._check_mcp_permission(tool_name, user_ctx)
        if not perm.allowed:
            logger.warning(
                "MCP permission DENIED: tool=%s user=%s reason=%s",
                tool_name,
                user_ctx,
                perm.reason,
            )
            return json.dumps(
                {"error": perm.reason, "success": False, "denied": True},
                ensure_ascii=False,
            )

        # Dimension 2: RBAC check for dispatch-related tools.
        if tool_name in _RBAC_GUARDED_TOOLS:
            rbac_roles = roles if roles is not None else []
            rbac_mode = mode or "auto"
            rbac_result = self._check_rbac_permission(user_ctx, rbac_roles, rbac_mode)
            if not rbac_result.allowed:
                logger.warning(
                    "MCP RBAC DENIED: tool=%s user=%s reason=%s",
                    tool_name,
                    user_ctx,
                    rbac_result.reason,
                )
                return json.dumps(
                    {"error": rbac_result.reason, "success": False, "denied": True},
                    ensure_ascii=False,
                )

        return None

    def shutdown(self) -> None:
        """Clean up dispatcher and code graph."""
        if self._code_graph is not None:
            with suppress(AttributeError, OSError, RuntimeError):
                self._code_graph.close()
            self._code_graph = None
        if self._dispatcher:
            self._dispatcher.shutdown()
            self._dispatcher = None


def create_mcp_server(
    host: str = "127.0.0.1",
    port: int = 8000,
    enable_permission_check: bool = True,
    auth_manager: Any | None = None,
    rbac: DispatchRBAC | None = None,
) -> "FastMCP":
    """Create and configure the MCP server with all tools.

    Parameters
    ----------
    host:
        SSE transport host (default 127.0.0.1).
    port:
        SSE transport port (default 8000).
    enable_permission_check:
        When True (default), enforce MCP permission-level checks (Dimension 1)
        and RBAC checks (Dimension 2) on every tool invocation.
    auth_manager:
        Optional AuthManager instance for RBAC role lookup.
    rbac:
        Optional pre-configured DispatchRBAC instance.
    """
    if not MCP_AVAILABLE:
        raise ImportError("MCP SDK not installed. Run: pip install mcp")

    mcp = FastMCP("DevSquad", host=host, port=port)
    server = DevSquadMCPServer(
        enable_permission_check=enable_permission_check,
        auth_manager=auth_manager,
        rbac=rbac,
    )

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
        denial = server._enforce_tool_permission("multiagent_dispatch", roles=roles, mode=mode)
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("multiagent_quick")
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("multiagent_roles")
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("multiagent_status")
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("multiagent_analyze")
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("multiagent_shutdown")
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("codegraph_explore")
        if denial is not None:
            return denial
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
                    "count": len(payload) if isinstance(payload, list) else len(payload.get("nodes", [])),  # type: ignore[attr-defined]
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
        denial = server._enforce_tool_permission("codegraph_status")
        if denial is not None:
            return denial
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
        denial = server._enforce_tool_permission("codegraph_refresh")
        if denial is not None:
            return denial
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
