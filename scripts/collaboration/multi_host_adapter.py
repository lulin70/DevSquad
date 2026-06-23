#!/usr/bin/env python3
"""Multi-host adapter layer — DevSquad integration with AI coding platforms.

Inspired by ponytail's multi-platform plugin architecture and codegraph's
multi-agent support. Allows DevSquad to be invoked from different AI host
platforms (Claude Code, Cursor, Codex CLI, etc.) through a unified adapter.

Supported hosts
---------------
- ``claude-code``  : Anthropic Claude Code CLI
- ``cursor``       : Cursor IDE
- ``codex``        : OpenAI Codex CLI
- ``cline``        : Cline VS Code extension
- ``trae``         : Trae IDE (default)
- ``generic``      : Any MCP-compatible host

Usage::

    from scripts.collaboration.multi_host_adapter import (
        MultiHostAdapter,
        HostType,
    )

    adapter = MultiHostAdapter(HostType.CLAUDE_CODE)
    result = adapter.dispatch("Design auth system", roles=["architect", "security"])
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .dispatcher import MultiAgentDispatcher

logger = logging.getLogger(__name__)


class HostType(str, Enum):
    """Supported AI host platform types."""

    CLAUDE_CODE = "claude-code"
    CURSOR = "cursor"
    CODEX = "codex"
    CLINE = "cline"
    TRAE = "trae"
    GENERIC = "generic"


@dataclass
class HostConfig:
    """Configuration for a specific host platform.

    Attributes:
        host_type: The host platform type.
        max_output_chars: Maximum output characters before slicing.
        supports_streaming: Whether the host supports streaming output.
        supports_mcp: Whether the host supports MCP protocol.
        prompt_prefix: Prefix prepended to all prompts sent to this host.
        prompt_suffix: Suffix appended to all prompts sent to this host.
        role_mapping: Custom role name mapping (host_role → DevSquad_role).
    """

    host_type: HostType
    max_output_chars: int = 8000
    supports_streaming: bool = False
    supports_mcp: bool = True
    prompt_prefix: str = ""
    prompt_suffix: str = ""
    role_mapping: dict[str, str] = field(default_factory=dict)


# Predefined configurations for each host type.
HOST_CONFIGS: dict[HostType, HostConfig] = {
    HostType.CLAUDE_CODE: HostConfig(
        host_type=HostType.CLAUDE_CODE,
        max_output_chars=12000,
        supports_streaming=True,
        supports_mcp=True,
        prompt_prefix="You are working with DevSquad multi-role AI team.\n",
        role_mapping={
            "analyst": "product-manager",
            "engineer": "solo-coder",
            "reviewer": "tester",
        },
    ),
    HostType.CURSOR: HostConfig(
        host_type=HostType.CURSOR,
        max_output_chars=10000,
        supports_streaming=False,
        supports_mcp=False,
        prompt_prefix="[DevSquad] ",
        role_mapping={},
    ),
    HostType.CODEX: HostConfig(
        host_type=HostType.CODEX,
        max_output_chars=8000,
        supports_streaming=True,
        supports_mcp=True,
        prompt_prefix="",
        role_mapping={
            "developer": "solo-coder",
        },
    ),
    HostType.CLINE: HostConfig(
        host_type=HostType.CLINE,
        max_output_chars=8000,
        supports_streaming=False,
        supports_mcp=True,
        prompt_prefix="[DevSquad] ",
        role_mapping={},
    ),
    HostType.TRAE: HostConfig(
        host_type=HostType.TRAE,
        max_output_chars=15000,
        supports_streaming=True,
        supports_mcp=True,
        prompt_prefix="",
        role_mapping={},
    ),
    HostType.GENERIC: HostConfig(
        host_type=HostType.GENERIC,
        max_output_chars=8000,
        supports_streaming=False,
        supports_mcp=True,
        prompt_prefix="",
        role_mapping={},
    ),
}


class MultiHostAdapter:
    """Unified adapter for dispatching DevSquad tasks from any AI host.

    Wraps :class:`MultiAgentDispatcher` with host-specific configuration,
    including output formatting, role name mapping, and prompt adaptation.

    Attributes:
        host_type: The host platform type.
        config: Host-specific configuration.
        dispatcher: The underlying MultiAgentDispatcher instance.
    """

    def __init__(
        self,
        host_type: HostType = HostType.TRAE,
        dispatcher: MultiAgentDispatcher | None = None,
        config: HostConfig | None = None,
    ):
        """Initialize the multi-host adapter.

        Args:
            host_type: The host platform type (default: TRAE).
            dispatcher: Optional pre-configured dispatcher. If None, creates a new one.
            config: Optional custom host config. If None, uses predefined config.
        """
        self.host_type = host_type
        self.config = config or HOST_CONFIGS.get(host_type, HOST_CONFIGS[HostType.GENERIC])
        self.dispatcher = dispatcher or MultiAgentDispatcher()
        logger.info("MultiHostAdapter initialized for host: %s", host_type.value)

    def dispatch(
        self,
        task: str,
        roles: list[str] | None = None,
        mode: str = "auto",
        **kwargs: Any,
    ) -> dict:
        """Dispatch a task through the host adapter.

        Applies host-specific role mapping, prompt adaptation, and output
        formatting before delegating to the underlying dispatcher.

        Args:
            task: Task description string.
            roles: Optional list of role names (host-native or DevSquad names).
                   If None, auto-matches roles.
            mode: Dispatch mode (auto/parallel/sequential/consensus).
            **kwargs: Additional arguments passed to dispatcher.dispatch().

        Returns:
            Dictionary with keys:
                - success: bool
                - host: str (host type value)
                - report: str (formatted markdown report, truncated to max_output_chars)
                - roles: list[str] (matched DevSquad roles)
                - raw_result: DispatchResult (full result object)
        """
        # Map host-native role names to DevSquad roles.
        mapped_roles = self._map_roles(roles)

        # Apply prompt prefix/suffix.
        adapted_task = self._adapt_prompt(task)

        # Dispatch.
        result = self.dispatcher.dispatch(
            task_description=adapted_task,
            roles=mapped_roles,
            mode=mode,
            **kwargs,
        )

        # Format output for host.
        report = result.to_markdown()
        if len(report) > self.config.max_output_chars:
            report = self._slice_output(report)

        return {
            "success": result.success,
            "host": self.host_type.value,
            "report": report,
            "roles": result.matched_roles,
            "raw_result": result,
        }

    def get_host_info(self) -> dict:
        """Get information about the current host configuration.

        Returns:
            Dictionary with host_type, supports_streaming, supports_mcp,
            max_output_chars, and available_role_mappings.
        """
        return {
            "host_type": self.host_type.value,
            "supports_streaming": self.config.supports_streaming,
            "supports_mcp": self.config.supports_mcp,
            "max_output_chars": self.config.max_output_chars,
            "role_mappings": self.config.role_mapping,
        }

    def _map_roles(self, roles: list[str] | None) -> list[str] | None:
        """Map host-native role names to DevSquad role names.

        Args:
            roles: List of role names (may be host-native or already DevSquad names).

        Returns:
            List of DevSquad role names, or None if input is None.
        """
        if roles is None:
            return None

        mapping = self.config.role_mapping
        if not mapping:
            return roles

        mapped: list[str] = []
        for role in roles:
            mapped.append(mapping.get(role, role))
        return mapped

    def _adapt_prompt(self, task: str) -> str:
        """Apply host-specific prompt prefix and suffix.

        Args:
            task: Original task description.

        Returns:
            Adapted task string with prefix/suffix applied.
        """
        parts: list[str] = []
        if self.config.prompt_prefix:
            parts.append(self.config.prompt_prefix)
        parts.append(task)
        if self.config.prompt_suffix:
            parts.append(self.config.prompt_suffix)
        return "\n".join(parts)

    def _slice_output(self, report: str) -> str:
        """Truncate output to max_output_chars with a continuation marker.

        Args:
            report: Full markdown report string.

        Returns:
            Truncated report string with continuation marker, or original
            if under the limit.
        """
        max_chars = self.config.max_output_chars
        if len(report) <= max_chars:
            return report
        marker = "\n\n[... output truncated at {max} chars ...]"
        available = max_chars - len(marker.format(max=max_chars))
        if available <= 0:
            return report[:max_chars]
        return report[:available] + marker.format(max=max_chars)

    def shutdown(self) -> None:
        """Shut down the underlying dispatcher."""
        self.dispatcher.shutdown()
