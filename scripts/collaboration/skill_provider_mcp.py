#!/usr/bin/env python3
"""MCPSkillProvider — bridges MCP tools as DevSquad skills (V4.5.0).

Implements the ``SkillProvider`` protocol by exposing MCP tools through the
same register/discover/instantiate/invoke interface used by the built-in
provider. This is a NEW capability: the agent core can now invoke MCP tools
without knowing they are MCP tools — it only sees the ``SkillProvider``
protocol.

Design:
    Each registered skill carries an MCP tool spec (server_name, tool_name).
    ``invoke()`` routes the call through an injectable ``mcp_invoker``
    callable with signature ``invoker(server_name, tool_name, kwargs_dict)``
    when the skill is bound to an MCP server. When no invoker is configured
    (or the skill has no ``mcp_server``), invoke() falls back to executing
    the skill class's ``run()`` method directly — enabling local testing and
    offline operation without a live MCP connection.

Anti-ghost: class-level ``_call_counter`` increments on every public method
call, proving the provider path is exercised (not ghost code).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)


class MCPSkillProvider:
    """MCP skill provider bridging MCP tools as DevSquad skills.

    Implements the :class:`SkillProvider` protocol. Each registered skill
    wraps an MCP tool spec and ``invoke()`` routes the call through an
    injectable MCP invoker callable. This decouples the agent core from the
    MCP transport: the core only knows the protocol, not whether a skill is
    a Python import or an MCP tool.

    Args:
        mcp_invoker: Optional callable with signature
            ``invoker(server_name: str, tool_name: str, kwargs: dict) -> Any``.
            When provided and a skill is bound to an MCP server, ``invoke()``
            routes through it. When ``None`` (default), invoke() falls back
            to the skill class's ``run()`` method (local mode).
    """

    # Anti-ghost counter (class-level). Incremented by every public method.
    _call_counter: int = 0

    def __init__(self, mcp_invoker: Callable[..., Any] | None = None) -> None:
        # tool spec: name -> {name, skill_cls, description, version, mcp_server, mcp_tool}
        self._tools: dict[str, dict[str, Any]] = {}
        self._mcp_invoker = mcp_invoker

    def register(self, name: str, skill_cls: type) -> None:
        """Register an MCP-tool-backed skill.

        The skill class may expose optional class attributes ``mcp_server``
        and ``mcp_tool`` to bind it to a real MCP tool. If absent, the skill
        is treated as a local skill invoked via ``run()``.

        Args:
            name: Skill identifier.
            skill_cls: A class (typically a ``BaseSkill`` subclass) exposing
                ``name``/``description`` attributes and a ``run()`` method.
        """
        MCPSkillProvider._call_counter += 1
        self._tools[name] = {
            "name": name,
            "skill_cls": skill_cls,
            "description": getattr(skill_cls, "description", ""),
            "version": getattr(skill_cls, "version", "1.0.0"),
            "mcp_server": getattr(skill_cls, "mcp_server", ""),
            "mcp_tool": getattr(skill_cls, "mcp_tool", name),
        }
        logger.debug(
            "MCPSkillProvider.register: %s (server=%s, tool=%s)",
            name,
            self._tools[name]["mcp_server"],
            self._tools[name]["mcp_tool"],
        )

    def discover(self) -> dict[str, Any]:
        """Discover all registered MCP-tool skills.

        Returns a dict mapping skill name -> skill info dict, including the
        MCP binding (server/tool) and a ``source`` marker of "mcp".
        """
        MCPSkillProvider._call_counter += 1
        return {
            name: {
                "name": s["name"],
                "description": s["description"],
                "version": s["version"],
                "source": "mcp",
                "mcp_server": s["mcp_server"],
                "mcp_tool": s["mcp_tool"],
            }
            for name, s in self._tools.items()
        }

    def instantiate(self, name: str) -> Any:
        """Instantiate the skill wrapper for an MCP tool.

        Args:
            name: Skill identifier.

        Returns:
            A skill instance.

        Raises:
            ValueError: When the skill is not found.
        """
        MCPSkillProvider._call_counter += 1
        return self._get_wrapper(name)

    def invoke(self, name: str, **kwargs: Any) -> Any:
        """Invoke an MCP tool skill.

        If an ``mcp_invoker`` was configured at construction and the skill is
        bound to an MCP server, the call is routed through it:
        ``mcp_invoker(server_name, tool_name, kwargs_dict)``. Otherwise, the
        skill class's ``run()`` method is invoked directly (local fallback).

        Args:
            name: Skill identifier.
            **kwargs: Forwarded to the MCP tool or to ``run()``.

        Returns:
            The value returned by the MCP invoker or the skill's ``run()``.

        Raises:
            ValueError: When the skill is not found.
        """
        MCPSkillProvider._call_counter += 1
        spec = self._tools.get(name)
        if spec is None:
            raise ValueError(
                f"MCP skill '{name}' not found. Available: {sorted(self._tools.keys())}"
            )
        if self._mcp_invoker is not None and spec["mcp_server"]:
            return self._mcp_invoker(spec["mcp_server"], spec["mcp_tool"], kwargs)
        # Local fallback: instantiate and run (no live MCP connection needed).
        inst = spec["skill_cls"]()
        return inst.run(**kwargs)

    # ------------------------------------------------------------------
    # Internal helpers (no counter increment — avoids double counting)
    # ------------------------------------------------------------------

    def _get_wrapper(self, name: str) -> Any:
        """Resolve a skill instance for an MCP-tool skill by name."""
        spec = self._tools.get(name)
        if spec is None:
            raise ValueError(
                f"MCP skill '{name}' not found. Available: {sorted(self._tools.keys())}"
            )
        return spec["skill_cls"]()


__version__ = "1.0.0"
__all__ = ["MCPSkillProvider"]
