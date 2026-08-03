#!/usr/bin/env python3
"""V4.5.0 SkillProvider Protocol unit tests.

Implements the 10 test cases from docs/testing/V4.4.3-V4.5.0_TEST_PLAN.md
section 4.1. Verifies:
  - BuiltinSkillProvider wraps the existing import-based registry (backward compat)
  - MCPSkillProvider bridges MCP tools as skills (new capability)
  - SkillRegistry delegates to the active provider and supports swapping
  - Anti-ghost: _call_counter > 0 after operations

Iron Rules:
  - Rule 1 (Documentation First): signatures verified against source, not memory.
  - Rule 2 (Failure Means Report): assertions reflect real behavior.
  - Rule 3 (Dimension Completeness): Happy/Error/Boundary/Config/Integration/Anti-Ghost.
  - Real components used throughout (real BaseSkill subclasses, real invoker fn).
"""

from __future__ import annotations

import pytest

from scripts.collaboration.protocols import SkillProvider
from scripts.collaboration.skill_provider_builtin import BuiltinSkillProvider
from scripts.collaboration.skill_provider_mcp import MCPSkillProvider
from scripts.collaboration.skill_registry import SkillEntry, SkillRegistry
from skills.registry import BaseSkill

# The 6 core sub-skills documented in skills/__init__.py (dispatch/intent/
# review/security/test/retrospective). The registry actually loads 8 (also
# prototype + teach); tests assert the 6 core are present (>= 6) rather than
# an exact count, to stay robust to additional skills being added.
CORE_SKILLS = {"dispatch", "intent", "review", "security", "test", "retrospective"}


# ---------------------------------------------------------------------------
# Real skill classes used as test fixtures (NOT Mock).
# ---------------------------------------------------------------------------


class _EchoSkill(BaseSkill):
    """Real lightweight skill echoing kwargs — used for register/invoke tests."""

    name = "echo"
    description = "echo test skill"

    def run(self, **kwargs):  # type: ignore[override]
        return {"echo": kwargs}

    def info(self):  # type: ignore[override]
        return {"name": self.name, "description": self.description, "version": self.version}


class _McpBoundSkill(BaseSkill):
    """Real skill bound to a (fake) MCP server for MCPSkillProvider tests."""

    name = "mcp-echo"
    description = "mcp-bound echo skill"
    mcp_server = "test_server"
    mcp_tool = "echo_tool"

    def run(self, **kwargs):  # type: ignore[override]
        return {"local_fallback": kwargs}


def _real_mcp_invoker(server_name: str, tool_name: str, kwargs: dict):
    """Real invoker function (not a Mock) recording the MCP routing."""
    return {"server": server_name, "tool": tool_name, "args": kwargs}


# ---------------------------------------------------------------------------
# 1. BuiltinSkillProvider.register
# ---------------------------------------------------------------------------


def test_builtin_provider_register():
    """Happy: register a skill, discover finds it."""
    provider = BuiltinSkillProvider()
    provider.register("echo", _EchoSkill)
    discovered = provider.discover()
    assert "echo" in discovered
    assert discovered["echo"]["name"] == "echo"


# ---------------------------------------------------------------------------
# 2. BuiltinSkillProvider.discover
# ---------------------------------------------------------------------------


def test_builtin_provider_discover():
    """Happy: discover returns the existing sub-skills (>= 6 core skills)."""
    provider = BuiltinSkillProvider()
    discovered = provider.discover()
    # The 6 core sub-skills must all be discoverable through the protocol.
    missing = CORE_SKILLS - set(discovered.keys())
    assert not missing, f"Core skills missing from discover(): {missing}"
    # Each entry is an info dict with at least a name.
    for name, info in discovered.items():
        assert isinstance(info, dict)
        assert info.get("name") == name


# ---------------------------------------------------------------------------
# 3. BuiltinSkillProvider.instantiate
# ---------------------------------------------------------------------------


def test_builtin_provider_instantiate():
    """Happy: instantiate returns a real skill instance."""
    provider = BuiltinSkillProvider()
    inst = provider.instantiate("intent")
    # IntentSkill is a real BaseSkill subclass with name == "intent".
    assert isinstance(inst, BaseSkill)
    assert inst.name == "intent"


# ---------------------------------------------------------------------------
# 4. BuiltinSkillProvider.invoke
# ---------------------------------------------------------------------------


def test_builtin_provider_invoke():
    """Side-Effect: invoke returns a real result from a built-in skill.

    Uses the 'teach' skill (lightweight, mock-mode, has a run() entry point).
    """
    provider = BuiltinSkillProvider()
    result = provider.invoke("teach", topic="overview")
    assert isinstance(result, dict)
    assert result["topic"] == "overview"
    assert "title" in result
    assert "content" in result


# ---------------------------------------------------------------------------
# 5. Provider swap
# ---------------------------------------------------------------------------


def test_provider_swap():
    """Config: swap BuiltinProvider with another, same invoke result."""
    registry = SkillRegistry(storage_path="/tmp/_devsquad_skill_provider_swap")

    # Register the same skill on the default provider and invoke.
    registry.provider.register("echo", _EchoSkill)
    result1 = registry.invoke("echo", msg="hello")

    # Swap to a fresh provider that also has the skill registered.
    new_provider = BuiltinSkillProvider()
    new_provider.register("echo", _EchoSkill)
    registry.set_provider(new_provider)
    result2 = registry.invoke("echo", msg="hello")

    assert result1 == result2 == {"echo": {"msg": "hello"}}
    # Confirm the swap actually took effect.
    assert registry.provider is new_provider


# ---------------------------------------------------------------------------
# 6. None provider -> graceful error
# ---------------------------------------------------------------------------


def test_provider_none():
    """Error: None provider -> graceful ValueError (not a cryptic crash)."""
    registry = SkillRegistry(storage_path="/tmp/_devsquad_skill_provider_none")
    registry.set_provider(None)
    with pytest.raises(ValueError, match="provider"):
        registry.discover()
    with pytest.raises(ValueError, match="provider"):
        registry.invoke("echo", msg="x")


# ---------------------------------------------------------------------------
# 7. Empty registry
# ---------------------------------------------------------------------------


def test_empty_registry():
    """Boundary: an empty MCP provider registry -> discover returns {}."""
    provider = MCPSkillProvider()
    assert provider.discover() == {}


# ---------------------------------------------------------------------------
# 8. Backward compatibility
# ---------------------------------------------------------------------------


def test_backward_compat():
    """Config: existing SkillRegistry API works without the provider param."""
    registry = SkillRegistry(storage_path="/tmp/_devsquad_skill_provider_compat")
    # Existing SkillEntry-based API must remain fully functional.
    skill = SkillEntry(name="compat-skill", description="backward compat check", category="test")
    sid = registry.register(skill)
    assert sid == skill.skill_id
    retrieved = registry.get(sid)
    assert retrieved is not None
    assert retrieved.name == "compat-skill"
    # list_skills returns the SkillEntry dicts (existing API).
    listed = registry.list_skills()
    assert any(s["name"] == "compat-skill" for s in listed)
    # A default provider was attached (V4.5.0) without breaking construction.
    assert registry.provider is not None
    # The new protocol-style discover() also works alongside the old API.
    discovered = registry.discover()
    assert isinstance(discovered, dict)


# ---------------------------------------------------------------------------
# 9. MCPSkillProvider
# ---------------------------------------------------------------------------


def test_mcp_provider():
    """Integration: MCPSkillProvider register/discover/instantiate/invoke."""
    # --- Local fallback path (no invoker) ---
    provider = MCPSkillProvider()
    provider.register("mcp-echo", _McpBoundSkill)

    discovered = provider.discover()
    assert "mcp-echo" in discovered
    assert discovered["mcp-echo"]["source"] == "mcp"
    assert discovered["mcp-echo"]["mcp_server"] == "test_server"
    assert discovered["mcp-echo"]["mcp_tool"] == "echo_tool"

    inst = provider.instantiate("mcp-echo")
    assert isinstance(inst, _McpBoundSkill)

    local_result = provider.invoke("mcp-echo", query="hi")
    assert local_result == {"local_fallback": {"query": "hi"}}

    # --- MCP routing path (with real invoker) ---
    routed = MCPSkillProvider(mcp_invoker=_real_mcp_invoker)
    routed.register("mcp-echo", _McpBoundSkill)
    routed_result = routed.invoke("mcp-echo", query="hi")
    assert routed_result == {
        "server": "test_server",
        "tool": "echo_tool",
        "args": {"query": "hi"},
    }


# ---------------------------------------------------------------------------
# 10. Anti-ghost call counter
# ---------------------------------------------------------------------------


def test_call_counter():
    """Anti-Ghost: _call_counter > 0 after operations for both providers."""
    # Exercise BuiltinSkillProvider.
    builtin = BuiltinSkillProvider()
    builtin.register("echo", _EchoSkill)
    builtin.discover()
    builtin.instantiate("intent")
    builtin.invoke("echo", x=1)
    assert BuiltinSkillProvider._call_counter > 0
    # Protocol conformance (runtime_checkable): the provider structurally
    # satisfies the SkillProvider protocol.
    assert isinstance(builtin, SkillProvider)

    # Exercise MCPSkillProvider.
    mcp = MCPSkillProvider()
    mcp.register("mcp-echo", _McpBoundSkill)
    mcp.discover()
    mcp.instantiate("mcp-echo")
    mcp.invoke("mcp-echo", x=1)
    assert MCPSkillProvider._call_counter > 0
    assert isinstance(mcp, SkillProvider)

    # The protocols module also exposes a module-level anti-ghost counter.
    from scripts.collaboration import protocols as protocols_mod

    assert hasattr(protocols_mod, "_call_counter")
